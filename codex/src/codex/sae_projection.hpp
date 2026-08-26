#pragma once
// sae_projection.hpp — Task 4: sparse SAE projection (SIMD + top-k + int8).
//
// Port of the LatentDecipher sparse projection (PsiForceDB::Codex) to C++26 with
// three innovations:
//   1. Vectorized 131072 x 2560 dictionary matrix-vector product.
//   2. top-k sparse activation (k=64) via partial heap selection.
//   3. int8-quantized SAE dictionary (per-row scale / zero-point) for ~4x
//      memory reduction and faster SIMD loads.
//
// SIMD selection (documented fallback, see learnings.md Task 4):
//   - std::simd (P1928) is NOT available in GCC 16.1.0 (no <simd> header; only
//     the TS <experimental/simd> exists). A std::simd path is compiled in
//     whenever __has_include(<simd>) is true (future toolchains); otherwise the
//     intrinsic path is used.
//   - Intel Ultra 9 275HX has NO AVX-512 (CPUID AVX512F=0 — the "AVX-512" note
//     in earlier learnings was wrong). It DOES have AVX2+FMA and
//     AVX-VNNI-INT8 (VPDPBSSD). The int8 kernel uses _mm256_dpbssd_epi32
//     (32 int8xint8 MACs/instruction); the float kernel uses _mm256_fmadd_ps.
//
// NO-NOISE GUARANTEE (fail closed): the constructor provisions NO weights.
// The dictionary must be provisioned explicitly via generate_float_dictionary()
// (deterministic: std::mt19937(42) + std::normal_distribution<float>(0,0.02),
// bias -0.01 — byte-identical to T5's kat_sae_scalar reference) OR loaded from
// a real file (load_float_dictionary / load_int8_mmap). Any projection call
// before provisioning throws std::runtime_error. Random/uninitialized weights
// are NEVER used.
//
// 8D OUTPUT CONTRACT (matches reference latent_decipher.cpp extract_primers):
//   topology, probability, ontology, teleology, graph, dataset,
//   dimensionality, human_anomaly = per-dimension sum of ReLU'd sparse
//   features over 8 contiguous calibration ranges of width dict_size/8
//   (identical to get_lingua_calibration_map() at dict_size=131072).

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <vector>

namespace Athenea {
namespace SAE {

// 8D Lingua Gestalt — the output contract shared with latent_decipher.cpp.
struct Gestalt8 {
    float topology = 0.0f;
    float probability = 0.0f;
    float ontology = 0.0f;
    float teleology = 0.0f;
    float graph = 0.0f;
    float dataset = 0.0f;
    float dimensionality = 0.0f;
    float human_anomaly = 0.0f;

    float& operator[](std::size_t i) {
        return (&topology)[i];  // packed floats, declaration order
    }
    const float& operator[](std::size_t i) const { return (&topology)[i]; }
};

// Top-k sparse feature set produced by the projection.
struct SparseFeatures {
    std::vector<std::uint32_t> indices;  // feature indices (heap order)
    std::vector<float> values;           // ReLU'd activations at indices
    std::size_t count() const noexcept { return indices.size(); }
};

// Dictionary storage kinds (informational; float and int8 may coexist).
enum class DictKind { None, FloatMemory, Int8Memory, Int8Mmap };

// Persistent int8 dictionary file layout (all little-endian, no padding).
//   [0]    header 64 bytes
//   [64]   weights  int8  [dict_size * latent_dim]
//   [..]   scales   float [dict_size]
//   [..]   zero_pts int8  [dict_size]   (symmetric quantization => all 0)
//   [..]   biases   float [dict_size]
// Rows are latent_dim int8 = 2560 bytes = 32-aligned (and 64-aligned) stride.
struct DictFileHeader {
    std::uint32_t magic;       // 'SAE8'
    std::uint32_t version;     // 1
    std::uint32_t dict_size;
    std::uint32_t latent_dim;
    std::uint32_t top_k;       // informational
    std::uint32_t reserved0;
    std::uint32_t weights_offset;  // 64
    std::uint32_t weights_bytes;
    std::uint32_t scales_offset;
    std::uint32_t scales_bytes;
    std::uint32_t zps_offset;
    std::uint32_t zps_bytes;
    std::uint32_t biases_offset;
    std::uint32_t biases_bytes;
    std::uint32_t total_bytes;
    std::uint32_t reserved1;
};
static_assert(sizeof(DictFileHeader) == 64, "DictFileHeader must be 64 bytes");

class SaeProjection {
public:
    static constexpr std::size_t DEFAULT_DICT_SIZE = 131072;
    static constexpr std::size_t DEFAULT_LATENT_DIM = 2560;
    static constexpr std::size_t DEFAULT_TOP_K = 64;
    static constexpr std::size_t ROW_ALIGNMENT = 32;  // mandated by the plan

    explicit SaeProjection(std::size_t dict_size = DEFAULT_DICT_SIZE,
                           std::size_t latent_dim = DEFAULT_LATENT_DIM,
                           std::size_t top_k = DEFAULT_TOP_K);
    ~SaeProjection();
    SaeProjection(const SaeProjection&) = delete;
    SaeProjection& operator=(const SaeProjection&) = delete;
    SaeProjection(SaeProjection&&) noexcept;
    SaeProjection& operator=(SaeProjection&&) noexcept;

    // ── Dictionary provisioning (fail closed: projection throws until ready) ──
    // Deterministic "real" dictionary: mt19937(42) + N(0, 0.02), bias -0.01.
    // Byte-identical weight stream to kat_sae_scalar.cpp (T5 reference).
    bool generate_float_dictionary();
    // Quantize the float dictionary to per-row int8 (symmetric scale, zp=0).
    // The float dictionary is KEPT; the int8 copy is the fast/memory-light
    // backend. Returns false if no float dictionary is present.
    bool quantize_to_int8();
    // Serialize the in-memory int8 dictionary to a file (for mmap loading).
    bool save_int8_file(const std::string& path) const;
    // Memory-map an int8 dictionary file. Rows are 32-byte aligned (verified).
    // On failure returns false and the module stays unprovisioned (fail closed).
    // The float dictionary, if present, is kept.
    bool load_int8_mmap(const std::string& path);
    // Load a raw float dictionary file: [weights: dict*latent][biases: dict].
    bool load_float_dictionary(const std::string& path);

    bool ready() const noexcept { return fw_ != nullptr || iw_ != nullptr; }
    bool has_float() const noexcept { return fw_ != nullptr; }
    bool has_int8() const noexcept { return iw_ != nullptr; }
    bool is_int8_storage() const noexcept { return iw_ != nullptr; }
    bool is_mmap_storage() const noexcept { return int8_mmap_ && iw_ != nullptr; }
    DictKind storage_kind() const noexcept {
        if (int8_mmap_ && iw_) return DictKind::Int8Mmap;
        if (iw_) return DictKind::Int8Memory;
        if (fw_) return DictKind::FloatMemory;
        return DictKind::None;
    }

    // ── Projection ──
    // Full dense projection: dict_size ReLU'd activations.
    // project_dense_float : AVX2 FMA SIMD (or std::simd when available).
    // project_dense_int8  : AVX-VNNI-INT8 SIMD (int8 x int8, dequantized).
    // project_dense       : dispatch — int8 if present, else float.
    std::vector<float> project_dense_float(std::span<const float> x) const;
    std::vector<float> project_dense_int8(std::span<const float> x) const;
    std::vector<float> project_dense(std::span<const float> x) const;
    // Exact scalar reference (per-element accumulation, vectorization disabled):
    // reproduces kat_sae_scalar math byte-for-byte. Float dictionary required.
    std::vector<float> project_dense_scalar(std::span<const float> x) const;

    // top-k sparse projection (deployed fast path):
    // int8 backend  -> VNNI SIMD + inline 64-element min-heap.
    // float backend -> AVX2 SIMD + inline 64-element min-heap.
    SparseFeatures project_topk_float(std::span<const float> x) const;
    SparseFeatures project_topk_int8(std::span<const float> x) const;
    SparseFeatures project_topk(std::span<const float> x) const;

    // top-k selection over an existing dense activation array (storage-free).
    // partial  = heap-based partial selection (partial_sort)
    // fullsort = full descending sort then take k (the "full computation")
    // Both use (value desc, index asc) so results are bit-identical.
    SparseFeatures select_topk_partial(std::span<const float> dense,
                                       std::size_t k) const;
    SparseFeatures select_topk_fullsort(std::span<const float> dense,
                                        std::size_t k) const;

    // ── 8D Lingua gestalt ──
    // Sums ReLU'd features per contiguous calibration range (width dict/8).
    Gestalt8 gestalt_from_dense(std::span<const float> dense) const;
    Gestalt8 gestalt_from_sparse(const SparseFeatures& s) const;

    // ── Reflection / alignment ──
    std::size_t dict_size() const noexcept { return dict_size_; }
    std::size_t latent_dim() const noexcept { return latent_dim_; }
    std::size_t top_k() const noexcept { return top_k_; }
    // Byte address of row `row` within the weights buffer (for alignment checks).
    std::uintptr_t row_address(std::size_t row) const noexcept;
    // True if the weights base and the last row satisfy `align`.
    bool rows_aligned_to(std::size_t align) const noexcept;
    // On-disk size of the int8 dictionary file for this configuration.
    std::size_t int8_file_bytes() const noexcept;
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

private:
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
    // int8 pointers are _mm_malloc'd EXCEPT when int8_mmap_ is set (they point
    // inside mmap_view_): never _mm_free a mapped pointer (0xC0000005), never
    // UnmapViewOfFile a heap pointer.
    void release_int8_storage() noexcept;

    std::size_t dict_size_;
    std::size_t latent_dim_;
    std::size_t top_k_;

    // float weights [dict x latent], 64-byte aligned (_mm_malloc). Owned.
    float* fw_ = nullptr;
    float* fbias_ = nullptr;  // [dict]
    // int8 weights [dict x latent], 64-byte aligned. Owned (heap or mmap).
    std::int8_t* iw_ = nullptr;
    float* iscale_ = nullptr;   // [dict]
    std::int8_t* izp_ = nullptr;  // [dict] (symmetric => 0)
    float* ibias_ = nullptr;    // [dict]
    // memory-mapped int8 dictionary (Int8Mmap storage)
    void* mmap_view_ = nullptr;
    std::uint64_t mmap_size_ = 0;
    bool int8_mmap_ = false;
};

// TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
// array into the k=3 heap and verifies it keeps the k LARGEST with
// (value desc, index asc) tie-break and root=WORST. Trace to stdout.
bool heap_self_test();

}  // namespace SAE
}  // namespace Athenea
