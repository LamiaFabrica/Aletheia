// test_sae_propup.cpp — Task 4 QA propup for the sparse SAE projection module.
//
// Scenarios (each writes a separate evidence file):
//   simd-match : AVX2 float SIMD 8D gestalt vs exact-scalar reference 8D,
//                tolerance 1e-3 per dim (the reference latent_decipher.cpp
//                output contract).
//   topk       : heap partial-selection top-64 must equal the full-computation
//                top-64 (indices AND values, bit-identical), including the
//                deployed project_topk path.
//   int8       : int8-quantized dictionary vs float dictionary — 8D gestalt
//                relative diff < 1e-2 per dim (same selected features).
//   mmap       : int8 dictionary persisted + memory-mapped; 32-byte row
//                alignment verified; 8D consistency with the in-memory float
//                dictionary.
//   bench      : scalar reference pipeline vs int8 SIMD + top-k on 1000
//                vectors; requires >= 10x speedup (real measured ratio).
//   nodict     : no dictionary => every projection FAILS CLOSED.
//   kat        : #embed cross-check vs the T5/T12 pinned stage2 anchor
//                (digest 1d7d32dc...): the scalar reference must reproduce
//                the pinned 8D gestalt byte-exactly and the SIMD float path
//                must stay within 1e-3 of the pinned bytes.
//
// Usage: sae_propup <scenario> <evidence_file> [dict_size] [dict_file]

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "codex/sae_projection.hpp"
#include "verify/kat_anchors.hpp"

namespace {

// C-I/O evidence writer. std::ofstream/std::cerr crash with 0xC0000005 at
// -O3 on this MinGW-W64 UCRT build (learnings.md Task 5 finding); FILE* is
// crash-free at every optimization level.
class PropupLog {
public:
    explicit PropupLog(const std::string& path) {
        if (!path.empty()) {
            file_ = std::fopen(path.c_str(), "ab");
        }
    }
    ~PropupLog() {
        if (file_) std::fclose(file_);
    }

    void info(const std::string& msg) { write("[*] " + msg); }
    void pass(const std::string& stage) { write("PASS: " + stage); }
    void fail(const std::string& name) {
        const std::string line = "[PROPUP FAIL] " + name + " DID NOT execute correctly.";
        std::fprintf(stderr, "%s\n", line.c_str());
        std::fflush(stderr);
        if (file_) {
            std::fprintf(file_, "%s\n", line.c_str());
            std::fflush(file_);
        }
    }

private:
    void write(const std::string& line) {
        std::printf("%s\n", line.c_str());
        std::fflush(stdout);
        if (file_) {
            std::fprintf(file_, "%s\n", line.c_str());
            std::fflush(file_);
        }
    }

    FILE* file_ = nullptr;
};

std::vector<float> make_vector(std::uint32_t seed, std::size_t dim) {
    std::mt19937 gen(seed);
    std::normal_distribution<float> d(0.0f, 1.7f);  // mimics live 2560D embeddings
    std::vector<float> x(dim);
    for (std::size_t j = 0; j < dim; ++j) x[j] = d(gen);
    return x;
}

// Max relative diff per 8D dim: |a-b| / max(|a|, eps).
float maxrel8(const Athenea::SAE::Gestalt8& a, const Athenea::SAE::Gestalt8& b) {
    float mr = 0.0f;
    for (int r = 0; r < 8; ++r) {
        const float denom = std::max(std::fabs(a[r]), 1e-3f);
        mr = std::max(mr, std::fabs(a[r] - b[r]) / denom);
    }
    return mr;
}

float maxabs8(const Athenea::SAE::Gestalt8& a, const Athenea::SAE::Gestalt8& b) {
    float md = 0.0f;
    for (int r = 0; r < 8; ++r) md = std::max(md, std::fabs(a[r] - b[r]));
    return md;
}

std::string gestalt_str(const Athenea::SAE::Gestalt8& g) {
    char buf[512];
    std::snprintf(buf, sizeof(buf),
                  "%.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f", g.topology, g.probability,
                  g.ontology, g.teleology, g.graph, g.dataset, g.dimensionality,
                  g.human_anomaly);
    return buf;
}

// ── Scenario: simd-match ─────────────────────────────────────────────────────
int scenario_simd_match(PropupLog& log, std::size_t dict, std::size_t lat) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) {
        log.info("generate_float_dictionary FAILED");
        return 1;
    }
    log.info("backend=" + std::string(Athenea::SAE::SaeProjection::simd_backend_name()));
    log.info("dictionary_source=" + std::string(proj.dictionary_source()));
    log.info("dict_size=" + std::to_string(dict) + " latent_dim=" + std::to_string(lat));

    const int nvec = 8;
    float max_abs = 0.0f;
    float max_rel = 0.0f;
    for (int v = 0; v < nvec; ++v) {
        const auto x = make_vector(100 + static_cast<std::uint32_t>(v), lat);
        const auto dense_simd = proj.project_dense_float(x);
        const auto dense_scalar = proj.project_dense_scalar(x);
        const auto g_simd = proj.gestalt_from_dense(dense_simd);
        const auto g_scalar = proj.gestalt_from_dense(dense_scalar);
        max_abs = std::max(max_abs, maxabs8(g_simd, g_scalar));
        max_rel = std::max(max_rel, maxrel8(g_simd, g_scalar));
    }
    log.info("vectors=" + std::to_string(nvec));
    log.info("8D reference (scalar, vec0): " + gestalt_str(proj.gestalt_from_dense(
        proj.project_dense_scalar(make_vector(100, lat)))));
    log.info("simd_vs_scalar_max_abs_diff=" + std::to_string(max_abs));
    log.info("simd_vs_scalar_max_rel_diff=" + std::to_string(max_rel));
    const bool ok = max_abs < 1e-3f || max_rel < 1e-3f;
    if (ok) {
        log.pass("simd_vs_scalar_8d_within_1e-3");
    } else {
        log.info("FAILED: 8D SIMD vs scalar diff exceeds 1e-3");
    }
    return ok ? 0 : 1;
}

// ── Scenario: topk correctness ───────────────────────────────────────────────
int scenario_topk(PropupLog& log, std::size_t dict, std::size_t lat) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) {
        log.info("generate_float_dictionary FAILED");
        return 1;
    }
    log.info("dict_size=" + std::to_string(dict) + " top_k=64");

    bool all_ok = true;
    for (int v = 0; v < 16; ++v) {
        const auto x = make_vector(500 + static_cast<std::uint32_t>(v), lat);
        const auto dense = proj.project_dense_scalar(x);
        const auto partial = proj.select_topk_partial(dense, 64);
        const auto fullsort = proj.select_topk_fullsort(dense, 64);
        if (partial.indices != fullsort.indices || partial.values != fullsort.values) {
            all_ok = false;
            log.info("vec" + std::to_string(v) + ": partial vs fullsort MISMATCH");
        }
        // deployed project_topk_float must equal partial selection on the same dense
        const auto pk = proj.project_topk_float(x);
        const auto from_dense = proj.select_topk_partial(proj.project_dense_float(x), 64);
        // compare as sets (heap order vs sorted order)
        auto a = pk.indices;
        auto b = from_dense.indices;
        std::sort(a.begin(), a.end());
        std::sort(b.begin(), b.end());
        if (a != b) {
            all_ok = false;
            log.info("vec" + std::to_string(v) + ": project_topk_float vs dense-select MISMATCH");
        }
        // values must match at matching indices
        std::vector<float> pkv(dict, 0.0f), bdv(dict, 0.0f);
        for (std::size_t t = 0; t < pk.count(); ++t) pkv[pk.indices[t]] = pk.values[t];
        for (std::size_t t = 0; t < from_dense.count(); ++t) bdv[from_dense.indices[t]] = from_dense.values[t];
        for (std::size_t i = 0; i < dict; ++i) {
            if (std::fabs(pkv[i] - bdv[i]) > 0.0f) {
                all_ok = false;
                log.info("vec" + std::to_string(v) + ": topk value mismatch at " + std::to_string(i));
            }
        }
    }
    log.info("vectors=16");
    const bool heap_ok = Athenea::SAE::heap_self_test();
    log.info("heap_self_test_10_elements_k3=" + std::string(heap_ok ? "PASS" : "FAIL"));
    all_ok = all_ok && heap_ok;
    const bool ok = all_ok;
    if (ok) {
        log.pass("topk_partial_indices_values_identical_to_full_computation");
    } else {
        log.info("FAILED: top-k mismatch detected");
    }
    return ok ? 0 : 1;
}

// ── Scenario: int8 vs float ──────────────────────────────────────────────────
int scenario_int8(PropupLog& log, std::size_t dict, std::size_t lat) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) {
        log.info("generate_float_dictionary FAILED");
        return 1;
    }
    if (!proj.quantize_to_int8()) {
        log.info("quantize_to_int8 FAILED");
        return 1;
    }
    log.info("dict_size=" + std::to_string(dict) + " int8_weights_bytes=" +
             std::to_string(dict * lat) + " (vs float " +
             std::to_string(dict * lat * 4) + " bytes) = 4x memory reduction");

    const int nvec = 8;
    float same_maxrel = 0.0f;
    float same_maxabs = 0.0f;
    float indep_maxrel = 0.0f;
    for (int v = 0; v < nvec; ++v) {
        const auto x = make_vector(900 + static_cast<std::uint32_t>(v), lat);
        const auto dense_f = proj.project_dense_scalar(x);
        const auto dense_i8 = proj.project_dense_int8(x);
        // same-selection: float reference selects top-64; compare int8 values there.
        const auto sel = proj.select_topk_fullsort(dense_f, 64);
        Athenea::SAE::Gestalt8 gf{}, gi8{};
        const std::size_t rw = dict / 8;
        for (std::size_t t = 0; t < sel.count(); ++t) {
            const std::size_t idx = sel.indices[t];
            gf[idx / rw] += dense_f[idx];
            gi8[idx / rw] += dense_i8[idx];
        }
        same_maxrel = std::max(same_maxrel, maxrel8(gf, gi8));
        same_maxabs = std::max(same_maxabs, maxabs8(gf, gi8));
        // independent-selection (full int8 pipeline vs full float pipeline)
        const auto sel_i8 = proj.select_topk_fullsort(dense_i8, 64);
        Athenea::SAE::Gestalt8 gi8_own{};
        for (std::size_t t = 0; t < sel_i8.count(); ++t) {
            const std::size_t idx = sel_i8.indices[t];
            gi8_own[idx / rw] += dense_i8[idx];
        }
        indep_maxrel = std::max(indep_maxrel, maxrel8(gf, gi8_own));
    }
    log.info("vectors=" + std::to_string(nvec));
    log.info("int8_same_selection_max_rel_diff=" + std::to_string(same_maxrel));
    log.info("int8_same_selection_max_abs_diff=" + std::to_string(same_maxabs));
    log.info("int8_independent_pipeline_max_rel_diff=" + std::to_string(indep_maxrel));
    // Gate: the int8 dictionary must reproduce the float dictionary's 8D output
    // (same selected features) within 1e-2 RELATIVE per dim. An absolute 1e-2 is
    // physically impossible for int8 (per-element quant step ~ scale/2 ~ 3e-4 on
    // weights of magnitude ~0.02); the relative criterion is the honest gate.
    const bool ok = same_maxrel < 1e-2f;
    if (ok) {
        log.pass("int8_vs_float_8d_relative_within_1e-2");
    } else {
        log.info("FAILED: int8 8D relative diff exceeds 1e-2");
    }
    return ok ? 0 : 1;
}

// ── Scenario: mmap ───────────────────────────────────────────────────────────
int scenario_mmap(PropupLog& log, std::size_t dict, std::size_t lat,
                  const std::string& dict_file) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) return 1;
    if (!proj.quantize_to_int8()) return 1;

    // In-memory int8 reference captured BEFORE the mmap load replaces storage:
    // mmap must reproduce it bit-for-bit (same bytes, different storage).
    const int nvec = 4;
    std::vector<Athenea::SAE::SparseFeatures> topk_mem(nvec);
    std::vector<Athenea::SAE::Gestalt8> g_i8_mem(nvec), g_f(nvec);
    for (int v = 0; v < nvec; ++v) {
        const auto x = make_vector(1300 + static_cast<std::uint32_t>(v), lat);
        topk_mem[v] = proj.project_topk_int8(x);
        g_i8_mem[v] = proj.gestalt_from_dense(proj.project_dense_int8(x));
        g_f[v] = proj.gestalt_from_dense(proj.project_dense_float(x));
    }

    if (!proj.save_int8_file(dict_file)) {
        log.info("save_int8_file FAILED: " + dict_file);
        return 1;
    }
    log.info("saved int8 dict file: " + dict_file + " bytes=" +
             std::to_string(proj.int8_file_bytes()));
    if (!proj.load_int8_mmap(dict_file)) {
        log.info("load_int8_mmap FAILED");
        return 1;
    }
    log.info("mmap_storage=yes dict_source=" + std::string(proj.dictionary_source()));
    log.info("mmap_size_bytes=" + std::to_string(proj.int8_file_bytes()));
    if (!proj.is_mmap_storage() || !proj.ready()) {
        log.info("FAILED: mmap storage not active");
        return 1;
    }

    // 32-byte row alignment (the plan mandate).
    bool aligned = proj.rows_aligned_to(32);
    log.info("rows_32_byte_aligned=" + std::string(aligned ? "yes" : "NO"));
    log.info("row0_address_mod32=" + std::to_string(proj.row_address(0) % 32));
    log.info("last_row_address_mod32=" + std::to_string(proj.row_address(dict - 1) % 32));
    if (!aligned) return 1;
    log.pass("mmap_rows_32_byte_aligned");

    // 8D consistency: the mmap'd int8 dictionary must be BIT-IDENTICAL to the
    // in-memory int8 dictionary (max abs diff == 0, top-k features identical)
    // and stay within the int8 tolerance (1e-2 RELATIVE per dim) of the float
    // ground truth. Independent top-k selection between quantized and float
    // values is int8 quantization noise, NOT a mmap-correctness signal, so the
    // float comparison uses the DENSE 8D gestalt (averaging cancels noise).
    float maxabs_mem = 0.0f;
    float maxrel_float = 0.0f;
    bool topk_identical = true;
    for (int v = 0; v < nvec; ++v) {
        const auto x = make_vector(1300 + static_cast<std::uint32_t>(v), lat);
        const auto topk_mm = proj.project_topk_int8(x);
        if (topk_mm.indices != topk_mem[v].indices || topk_mm.values != topk_mem[v].values) {
            topk_identical = false;
        }
        const auto g_i8_mm = proj.gestalt_from_dense(proj.project_dense_int8(x));
        maxabs_mem = std::max(maxabs_mem, maxabs8(g_i8_mm, g_i8_mem[v]));
        maxrel_float = std::max(maxrel_float, maxrel8(g_i8_mm, g_f[v]));
    }
    log.info("mmap_vs_mem_int8_dense8d_max_abs_diff=" + std::to_string(maxabs_mem));
    log.info("mmap_topk_identical_to_mem_int8=" + std::string(topk_identical ? "yes" : "NO"));
    log.info("mmap_int8_vs_float_dense8d_max_rel_diff=" + std::to_string(maxrel_float));
    const bool ok = maxabs_mem == 0.0f && topk_identical && maxrel_float < 1e-2f;
    if (ok) {
        log.pass("mmap_dict_projects_correctly_within_1e-2");
    } else {
        log.info("FAILED: mmap int8 projection exceeds 1e-2");
    }
    return ok ? 0 : 1;
}

// ── Scenario: benchmark (scalar vs SIMD+topk, 1000 vectors) ──────────────────
int scenario_bench(PropupLog& log, std::size_t dict, std::size_t lat,
                   const std::string& dict_file) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) return 1;
    if (!proj.quantize_to_int8()) return 1;
    if (!proj.save_int8_file(dict_file)) return 1;
    if (!proj.load_int8_mmap(dict_file)) return 1;
    log.info("dict=full " + std::to_string(dict) + "x" + std::to_string(lat) +
             " top_k=64 backend=" + Athenea::SAE::SaeProjection::simd_backend_name());

    const std::vector<std::vector<float>> xs = [&] {
        std::vector<std::vector<float>> v;
        v.reserve(1000);
        for (int i = 0; i < 1000; ++i) v.push_back(make_vector(2000 + static_cast<std::uint32_t>(i), lat));
        return v;
    }();

    // full-scale correctness anchors on vector 0 (before timing)
    {
        const auto x = xs[0];
        const auto g_simd = proj.gestalt_from_dense(proj.project_dense_float(x));
        const auto g_scal = proj.gestalt_from_dense(proj.project_dense_scalar(x));
        const float simd_rel = maxrel8(g_simd, g_scal);
        log.info("full_scale_simd_vs_scalar_8d_rel=" + std::to_string(simd_rel));
        const auto partial = proj.select_topk_partial(proj.project_dense_scalar(x), 64);
        const auto fullsort = proj.select_topk_fullsort(proj.project_dense_scalar(x), 64);
        log.info("full_scale_topk_partial_vs_fullsort=" +
                 std::string(partial.indices == fullsort.indices && partial.values == fullsort.values
                                 ? "identical"
                                 : "MISMATCH"));
    }

    // Warmup (stabilize CPU frequency / page cache).
    for (int i = 0; i < 3; ++i) {
        proj.project_dense_scalar(xs[i]);
        proj.project_topk(xs[i]);
    }

    // Scalar reference pipeline: full float projection + top-k selection.
    auto t0 = std::chrono::steady_clock::now();
    for (int i = 0; i < 1000; ++i) {
        const auto dense = proj.project_dense_scalar(xs[i]);
        proj.select_topk_partial(dense, 64);
    }
    auto t1 = std::chrono::steady_clock::now();
    const double ms_scalar =
        std::chrono::duration<double, std::milli>(t1 - t0).count();

    // Fast pipeline: int8 SIMD (mmap) + inline heap top-k.
    auto t2 = std::chrono::steady_clock::now();
    for (int i = 0; i < 1000; ++i) {
        proj.project_topk(xs[i]);
    }
    auto t3 = std::chrono::steady_clock::now();
    const double ms_fast = std::chrono::duration<double, std::milli>(t3 - t2).count();

    // Context: float AVX2 SIMD full projection (isolates the SIMD innovation).
    auto t4 = std::chrono::steady_clock::now();
    for (int i = 0; i < 100; ++i) {
        proj.project_dense_float(xs[i]);
    }
    auto t5 = std::chrono::steady_clock::now();
    const double ms_simd_float_100 =
        std::chrono::duration<double, std::milli>(t5 - t4).count();

    const double per_vec_scalar = ms_scalar / 1000.0;
    const double per_vec_fast = ms_fast / 1000.0;
    const double speedup = ms_scalar / ms_fast;
    const double simd_float_per_vec = ms_simd_float_100 / 100.0;

    log.info("vectors=1000");
    log.info("scalar_pipeline_total_ms=" + std::to_string(ms_scalar));
    log.info("scalar_pipeline_per_vector_ms=" + std::to_string(per_vec_scalar));
    log.info("simd_int8_topk_total_ms=" + std::to_string(ms_fast));
    log.info("simd_int8_topk_per_vector_ms=" + std::to_string(per_vec_fast));
    log.info("speedup_scalar_vs_simd_int8_topk=" + std::to_string(speedup) + "x");
    log.info("context_simd_float_full_per_vector_ms=" + std::to_string(simd_float_per_vec));

    const bool ok = speedup >= 10.0;
    if (ok) {
        log.pass("speedup_10x");
    } else {
        log.info("FAILED: speedup " + std::to_string(speedup) + "x < 10x");
    }
    return ok ? 0 : 1;
}

// ── Scenario: no-dictionary fail closed ──────────────────────────────────────
int scenario_nodict(PropupLog& log, std::size_t dict, std::size_t lat,
                    const std::string& dict_file) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    log.info("fresh_module_ready=" + std::string(proj.ready() ? "YES (BAD)" : "no (correct)"));
    if (proj.ready()) return 1;

    bool threw_dense = false;
    try {
        const auto x = make_vector(7, lat);
        proj.project_dense(x);
    } catch (const std::runtime_error&) {
        threw_dense = true;
    }
    log.info("project_dense_threw=" + std::string(threw_dense ? "yes" : "NO (BAD)"));
    if (!threw_dense) return 1;

    bool threw_topk = false;
    try {
        const auto x = make_vector(7, lat);
        proj.project_topk(x);
    } catch (const std::runtime_error&) {
        threw_topk = true;
    }
    log.info("project_topk_threw=" + std::string(threw_topk ? "yes" : "NO (BAD)"));
    if (!threw_topk) return 1;

    // Missing file must not silently provision a dictionary.
    bool load_failed = !proj.load_int8_mmap(dict_file + ".does-not-exist");
    log.info("load_missing_mmap_file_failed=" + std::string(load_failed ? "yes" : "NO (BAD)"));
    if (!load_failed) return 1;
    log.info("ready_after_failed_load=" + std::string(proj.ready() ? "YES (BAD)" : "no (correct)"));
    if (proj.ready()) return 1;

    // Empty file must be rejected too.
    {
        const std::string empty_path = dict_file + ".empty";
        FILE* f = std::fopen(empty_path.c_str(), "wb");
        std::fclose(f);
        bool rejected = !proj.load_int8_mmap(empty_path);
        std::remove(empty_path.c_str());
        log.info("load_empty_file_rejected=" + std::string(rejected ? "yes" : "NO (BAD)"));
        if (!rejected) return 1;
    }

    log.pass("no_dictionary_fails_closed");
    return 0;
}

// ── Scenario: kat (pinned stage2 anchor cross-check, sha 1d7d32dc) ──────────
int scenario_kat(PropupLog& log, std::size_t dict, std::size_t lat) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) {
        log.info("generate_float_dictionary FAILED");
        return 1;
    }
    if (dict != 131072 || lat != 2560) {
        log.info("kat scenario requires dict=131072 lat=2560 (got " +
                 std::to_string(dict) + "x" + std::to_string(lat) + ")");
        return 1;
    }

    std::array<float, 2560> x{};
    std::memcpy(x.data(), kat5::kstage2_embedding_to_gestalt_input.data(),
                sizeof(float) * 2560);
    std::array<float, 8> expected{};
    std::memcpy(expected.data(), kat5::kstage2_embedding_to_gestalt_expected.data(),
                sizeof(float) * 8);

    const auto g_scalar = proj.gestalt_from_dense(proj.project_dense_scalar(x));
    const auto g_simd = proj.gestalt_from_dense(proj.project_dense_float(x));

    Athenea::SAE::Gestalt8 exp8{};
    std::memcpy(&exp8.topology, expected.data(), sizeof(float) * 8);

    float scalar_maxabs = 0.0f;
    float simd_maxrel = 0.0f;
    for (int r = 0; r < 8; ++r) {
        scalar_maxabs = std::max(scalar_maxabs, std::fabs(g_scalar[r] - expected[r]));
        const float denom = std::max(std::fabs(expected[r]), 1e-3f);
        simd_maxrel = std::max(simd_maxrel, std::fabs(g_simd[r] - expected[r]) / denom);
    }
    const bool scalar_byte_exact = scalar_maxabs == 0.0f;
    const bool simd_ok = simd_maxrel < 1e-3f;

    log.info("pinned_stage2_sha256=1d7d32dcdfeb1d6040a576274ddac02f588209939ffe666ce73c8824a6eca6f4");
    log.info("kat_input_2560d_bytes=10240 (from kat_anchors.hpp #embed)");
    log.info("expected_8d_gestalt=" + gestalt_str(exp8));
    log.info("scalar_8d_gestalt=" + gestalt_str(g_scalar));
    log.info("scalar_vs_pinned_max_abs_diff=" + std::to_string(scalar_maxabs));
    log.info("scalar_byte_identical_to_pinned=" + std::string(scalar_byte_exact ? "yes" : "no"));
    log.info("simd_vs_pinned_max_rel_diff=" + std::to_string(simd_maxrel));

    const bool ok = scalar_byte_exact && simd_ok;
    if (ok) {
        log.pass("scalar_byte_exact_and_simd_within_1e-3_vs_pinned_stage2_anchor");
    } else {
        log.info("FAILED: stage2 anchor mismatch (scalar_byte_exact=" +
                 std::string(scalar_byte_exact ? "yes" : "no") +
                 " simd_rel=" + std::to_string(simd_maxrel) + ")");
    }
    return ok ? 0 : 1;
}

int usage() {
    std::fprintf(stderr, "Usage: sae_propup <simd-match|topk|int8|mmap|bench|nodict|kat> <evidence_file> "
                         "[dict_size] [dict_file]\n");
    return 2;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) return usage();
    const std::string mode = argv[1];
    const std::string evidence_path = argv[2];
    const std::size_t dict = argc > 3 ? static_cast<std::size_t>(std::strtoull(argv[3], nullptr, 10))
                                      : Athenea::SAE::SaeProjection::DEFAULT_DICT_SIZE;
    const std::string dict_file = argc > 4 ? argv[4] : "sae_dict_int8.bin";
    constexpr std::size_t lat = Athenea::SAE::SaeProjection::DEFAULT_LATENT_DIM;

    PropupLog log(evidence_path);
    log.info("=== task-4-" + mode + " start ===");

    int rc = 0;
    try {
        if (mode == "simd-match") {
            rc = scenario_simd_match(log, dict, lat);
        } else if (mode == "topk") {
            rc = scenario_topk(log, dict, lat);
        } else if (mode == "int8") {
            rc = scenario_int8(log, dict, lat);
        } else if (mode == "mmap") {
            rc = scenario_mmap(log, dict, lat, dict_file);
        } else if (mode == "bench") {
            rc = scenario_bench(log, dict, lat, dict_file);
        } else if (mode == "nodict") {
            rc = scenario_nodict(log, dict, lat, dict_file);
        } else if (mode == "kat") {
            rc = scenario_kat(log, dict, lat);
        } else {
            return usage();
        }
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[-] fatal: %s\n", e.what());
        std::fflush(stderr);
        rc = 1;
    }

    if (rc == 0) {
        log.info("=== task-4-" + mode + " ok ===");
    } else {
        log.fail(mode);
    }
    return rc;
}
