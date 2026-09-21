# UPLIFT DIFFS / SNIPPETS — Aletheia

**Source:** OpenCode session history (`opencode.db`, read-only). **Generated:** 21/09/2026 (Zulu).

Edit-only changes preserved for cherry-pick; nothing auto-applied.

## `codex\CMakeLists.txt`

### write 1 (5182 bytes)

### edit 2

**old:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")
endif()

install(TARGETS aletheia_codex extraction_propup DESTINATION bin)
```

**new:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")
endif()
```

### edit 3

**old:**
```
# Apply strict compilation flags only to our code
foreach (tgt aletheia_codex extraction_propup)
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${tgt} PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
    elseif (MSVC)
        target_compile_options(${tgt} PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
    endif()
endforeach()
```

**new:**
```
# Apply strict compilation flags only to our code
foreach (tgt aletheia_codex extraction_propup)
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${tgt} PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
        # Statically link the MinGW runtime so a foreign libstdc++-6.dll on PATH
        # (e.g. Git's mingw64) can never be picked up at load time.
        target_link_options(${tgt} PRIVATE -static-libgcc -static-libstdc++ -static)
    elseif (MSVC)
        target_compile_options(${tgt} PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
    endif()
endforeach()
```

### edit 4

**old:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")
endif()
```

**new:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")

    # Task 12: extraction-stage contract gate. The blank/whitespace-prompt
    # scenario IS the contract check — extraction_module now rejects them with
    # std::invalid_argument (fail-closed pre-condition), and the module's
    # 2560D + finite-values post-checks run on every extract()/extract_batch().
    # Registered as its own gate so Task 12 verification is explicit.
    add_test(NAME task12_extraction_contracts
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-12-extraction-contracts.txt")
endif()
```

### edit 5

**old:**
```
add_executable(aletheia_codex ${SOURCES})
add_executable(extraction_propup
    src/test_extraction_propup.cpp
    src/codex/extraction_module.cpp
)

# Apply C++23 standard ONLY to our code (dependencies stay at C++17)
set_target_properties(aletheia_codex PROPERTIES CXX_STANDARD 23)
set_target_properties(extraction_propup PROPERTIES CXX_STANDARD 23)

# Apply strict compilation flags only to our code
foreach (tgt aletheia_codex extraction_propup)
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${tgt} PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
        # Statically link the MinGW runtime so a foreign libstdc++-6.dll on PATH
        # (e.g. Git's mingw64) can never be picked up at load time.
        target_link_options(${tgt} PRIVATE -static-libgcc -static-libstdc++ -static)
    elseif (MSVC)
        target_compile_options(${tgt} PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
    endif()
endforeach()

# Link dependencies
target_link_libraries(aletheia_codex PRIVATE llama)
target_link_libraries(extraction_propup PRIVATE llama psapi)
target_include_directories(aletheia_codex PRIVATE src)
target_include_directories(extraction_propup PRIVATE src)
```

**new:**
```
add_executable(aletheia_codex ${SOURCES})
add_executable(extraction_propup
    src/test_extraction_propup.cpp
    src/codex/extraction_module.cpp
)

# Task 4: sparse SAE projection propup — pure CPU, NO llama runtime.
add_executable(sae_propup
    src/test_sae_propup.cpp
    src/codex/sae_projection.cpp
)

# Apply C++23 standard ONLY to our code (dependencies stay at C++17)
set_target_properties(aletheia_codex PROPERTIES CXX_STANDARD 23)
set_target_properties(extraction_propup PROPERTIES CXX_STANDARD 23)
# Task 4 module is C++26 (GCC 16.1.0 accepts -std=c++26; CMake >= 3.30 supports it)
set_target_properties(sae_propup PROPERTIES CXX_STANDARD 26)

# sae_projection.cpp is compiled with the CPU SIMD ISA that this machine has:
# AVX2 + FMA + AVX-VNNI-INT8 (VPDPBSSD). Intel Ultra 9 275HX has NO AVX-512.
set_source_files_properties(src/codex/sae_projection.cpp PROPERTIES
    COMPILE_OPTIONS "-mavx2;-mavxvnniint8;-mfma")

# Apply strict compilation flags only to our code
foreach (tgt aletheia_codex extraction_propup sae_propup)
    if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
        target_compile_options(${tgt} PRIVATE -Werror -Wpedantic -Wall -Wextra -fconcepts-diagnostics-depth=3 -fdiagnostics-show-template-tree -fdiagnostics-show-caret -fdiagnostics-color=always)
        # Statically link the MinGW runtime so a foreign libstdc++-6.dll on PATH
        # (e.g. Git's mingw64) can never be picked up at load time.
        target_link_options(${tgt} PRIVATE -static-libgcc -static-libstdc++ -static)
    elseif (MSVC)
        target_compile_options(${tgt} PRIVATE /WX /W4 /permissive- /diagnostics:caret /std:c++latest)
    endif()
endforeach()

# Link dependencies
target_link_libraries(aletheia_codex PRIVATE llama)
target_link_libraries(extraction_propup PRIVATE llama psapi)
target_include_directories(aletheia_codex PRIVATE src)
target_include_directories(extraction_propup PRIVATE src)
target_include_directories(sae_propup PRIVATE src)
```

### edit 6

**old:**
```
    add_test(NAME task3_extraction
        COMMAND extraction_propup extraction "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-extraction.txt")
    add_test(NAME task3_batch
        COMMAND extraction_propup batch "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-batch.txt")
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")
endif()
```

**new:**
```
    add_test(NAME task3_extraction
        COMMAND extraction_propup extraction "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-extraction.txt")
    add_test(NAME task3_batch
        COMMAND extraction_propup batch "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-batch.txt")
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")

    # Task 4 SAE propup scenarios — pure CPU, no llama runtime. The int8 dict
    # file for mmap/bench lives next to the build binaries (build artifact).
    set(ATHENEA_SAE_DICT_FILE "${CMAKE_CURRENT_BINARY_DIR}/sae_dict_int8.bin" CACHE FILEPATH
        "Int8 SAE dictionary file used by the sae_propup mmap/bench scenarios")
    add_test(NAME task4_simd_match
        COMMAND sae_propup simd-match "${ATHENEA_EVIDENCE_DIR}/task-4-simd-match.txt" 131072)
    add_test(NAME task4_topk
        COMMAND sae_propup topk "${ATHENEA_EVIDENCE_DIR}/task-4-topk.txt" 16384)
    add_test(NAME task4_int8
        COMMAND sae_propup int8 "${ATHENEA_EVIDENCE_DIR}/task-4-int8.txt" 131072)
    add_test(NAME task4_mmap
        COMMAND sae_propup mmap "${ATHENEA_EVIDENCE_DIR}/task-4-mmap.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_bench
        COMMAND sae_propup bench "${ATHENEA_EVIDENCE_DIR}/task-4-bench.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_nodict
        COMMAND sae_propup nodict "${ATHENEA_EVIDENCE_DIR}/task-4-nodict.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
endif()
```

### edit 7

**old:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")

```

**new:**
```
    add_test(NAME task3_empty
        COMMAND extraction_propup empty "${ATHENEA_GGUF_MODEL}" "${ATHENEA_EVIDENCE_DIR}/task-3-empty.txt")

    # Task 4: sparse SAE projection propup — pure CPU, no llama runtime.
    # The int8 dict file for the mmap/bench scenarios lives next to the build
    # binaries (a build artifact, not evidence).
    set(ATHENEA_SAE_DICT_FILE "${CMAKE_CURRENT_BINARY_DIR}/sae_dict_int8.bin" CACHE FILEPATH
        "Int8 SAE dictionary file used by the sae_propup mmap/bench scenarios")
    add_test(NAME task4_simd_match
        COMMAND sae_propup simd-match "${ATHENEA_EVIDENCE_DIR}/task-4-simd-match.txt" 131072)
    add_test(NAME task4_topk
        COMMAND sae_propup topk "${ATHENEA_EVIDENCE_DIR}/task-4-topk.txt" 16384)
    add_test(NAME task4_int8
        COMMAND sae_propup int8 "${ATHENEA_EVIDENCE_DIR}/task-4-int8.txt" 131072)
    add_test(NAME task4_mmap
        COMMAND sae_propup mmap "${ATHENEA_EVIDENCE_DIR}/task-4-mmap.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_bench
        COMMAND sae_propup bench "${ATHENEA_EVIDENCE_DIR}/task-4-bench.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_nodict
        COMMAND sae_propup nodict "${ATHENEA_EVIDENCE_DIR}/task-4-nodict.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")

```

### edit 8

**old:**
```
target_include_directories(aletheia_codex PRIVATE src)
target_include_directories(extraction_propup PRIVATE src)
target_include_directories(sae_propup PRIVATE src)
```

**new:**
```
target_include_directories(aletheia_codex PRIVATE src)
target_include_directories(extraction_propup PRIVATE src)
# sae_propup also includes TT_Tutor's verify headers (kat_anchors.hpp, #embed
# stage2 anchor) for the task4_kat pinned-anchor cross-check.
target_include_directories(sae_propup PRIVATE
    src
    "C:/McMaker Projects/Projects/Athenea/TT_Tutor/src")
```

### edit 9

**old:**
```
    add_test(NAME task4_nodict
        COMMAND sae_propup nodict "${ATHENEA_EVIDENCE_DIR}/task-4-nodict.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
```

**new:**
```
    add_test(NAME task4_nodict
        COMMAND sae_propup nodict "${ATHENEA_EVIDENCE_DIR}/task-4-nodict.txt" 131072 "${ATHENEA_SAE_DICT_FILE}")
    add_test(NAME task4_kat
        COMMAND sae_propup kat "${ATHENEA_EVIDENCE_DIR}/task-4-kat.txt" 131072)
```

### edit 10

**old:**
```
# sae_projection.cpp is compiled with the CPU SIMD ISA that this machine has:
# AVX2 + FMA + AVX-VNNI-INT8 (VPDPBSSD). Intel Ultra 9 275HX has NO AVX-512.
set_source_files_properties(src/codex/sae_projection.cpp PROPERTIES
    COMPILE_OPTIONS "-mavx2;-mavxvnniint8;-mfma")
```

**new:**
```
# sae_projection.cpp is compiled with the CPU SIMD ISA that this machine has:
# AVX2 + FMA + AVX-VNNI-INT8 (VPDPBSSD). Intel Ultra 9 275HX has NO AVX-512.
# -ffp-contract=off is MANDATORY for the no-noise guarantee: FMA contraction
# changes std::normal_distribution<float>'s internal rounding, flipping its
# reject/retry decisions and diverging the whole mt19937(42) weight stream away
# from the canonical kat_sae_scalar dictionary (byte-exact pinned by stage2
# anchor 1d7d32dc). The SIMD kernels use explicit _mm256_fmadd_ps intrinsics
# and are unaffected by the contraction setting.
set_source_files_properties(src/codex/sae_projection.cpp PROPERTIES
    COMPILE_OPTIONS "-mavx2;-mavxvnniint8;-mfma;-ffp-contract=off")
```

## `codex\src\codex\sae_projection.cpp`

### write 1 (30703 bytes)

### write 2 (31747 bytes)

### edit 3

**old:**
```
#include <immintrin.h>
#include <windows.h>
```

**new:**
```
#include <immintrin.h>
#include <mm_malloc.h>
#include <windows.h>
```

### edit 4

**old:**
```
#if __has_include(<simd>)
#include <simd>
#define SAE_HAS_STD_SIMD 1
#else
#define SAE_HAS_STD_SIMD 0
#endif
```

**new:**
```
// P1928 std::simd: GCC 16.1 ships only a stub <simd> header — __glibcxx_simd
// is defined but the std::simd type is absent and __cpp_lib_simd is undefined.
// Gate on the feature-test macro so the intrinsic path is used here.
#if defined(__cpp_lib_simd)
#include <simd>
#define SAE_HAS_STD_SIMD 1
#else
#define SAE_HAS_STD_SIMD 0
#endif
```

### edit 5

**old:**
```
    fw_ = fbias_ = nullptr;
    iw_ = iscale_ = izp_ = ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;

    const std::size_t n = dict_size_ * latent_dim_;
    float* w = alloc_f(n);
```

**new:**
```
    fw_ = nullptr;
    fbias_ = nullptr;
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;

    const std::size_t n = dict_size_ * latent_dim_;
    float* w = alloc_f(n);
```

### edit 6

**old:**
```
// int8 SIMD + inline heap (the deployed fast path).
SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
```

**new:**
```
// int8 SIMD + inline heap (the deployed fast path).
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
```

### edit 7

**old:**
```
    SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}

// float SIMD + inline heap.
SparseFeatures float_topk_kernel(const float* w, const float* bias, std::size_t dict,
                                 std::size_t lat, const float* x, std::size_t k) {
```

**new:**
```
    SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}

// float SIMD + inline heap.
Athenea::SAE::SparseFeatures float_topk_kernel(const float* w, const float* bias,
                                               std::size_t dict, std::size_t lat,
                                               const float* x, std::size_t k) {
```

### edit 8

**old:**
```
        const float dot = static_cast<float>(s) * x_scale * scale[i0] + bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

**new:**
```
        const float dot = static_cast<float>(s) * x_scale * scale[i0] + bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

### edit 9

**old:**
```
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i));
    }
    SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

**new:**
```
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

### edit 10

**old:**
```
// ── Fixed-size min-heap for top-k (worst-of-kept at root) ───────────────────
// Comparison: better(a,b) = a.value > b.value, ties by smaller index. This is
// consistent with select_topk_partial/fullsort (value desc, index asc).
class TopKHeap {
public:
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}

    std::size_t size() const noexcept { return n_; }

    void push(float v, std::uint32_t idx) {
        if (n_ < k_) {
            vals_[n_] = v;
            idxs_[n_] = idx;
            ++n_;
            if (n_ == k_) build();
            return;
        }
        if (!better(v, idx, vals_[0], idxs_[0])) return;
        vals_[0] = v;
        idxs_[0] = idx;
        sift_down(0);
    }

    const float* vals() const noexcept { return vals_.data(); }
    const std::uint32_t* idxs() const noexcept { return idxs_.data(); }

private:
    static bool better(float va, std::uint32_t ia, float vb, std::uint32_t ib) {
        return va > vb || (va == vb && ia < ib);
    }

    void build() {
        for (std::size_t i = k_ / 2; i > 0; --i) sift_down(i - 1);
    }

    void sift_down(std::size_t i) {
        for (;;) {
            const std::size_t l = 2 * i + 1;
            const std::size_t r = 2 * i + 2;
            std::size_t m = i;
            if (l < n_ && better(vals_[l], idxs_[l], vals_[m], idxs_[m])) m = l;
            if (r < n_ && better(vals_[r], idxs_[r], vals_[m], idxs_[m])) m = r;
            if (m == i) return;
            std::swap(vals_[i], vals_[m]);
            std::swap(idxs_[i], idxs_[m]);
            i = m;
        }
    }

    std::size_t k_;
    std::size_t n_ = 0;
    std::vector<float> vals_;
    std::vector<std::uint32_t> idxs_;
};
```

**new:**
```
// ── Fixed-size min-heap for top-k (worst-of-kept at root) ───────────────────
// Comparison: better(a,b) = a.value > b.value, ties by smaller index. This is
// consistent with select_topk_partial/fullsort (value desc, index asc).
// The heap keeps the k best as a MIN-heap: the root is the WORST kept element,
// so push() can reject a candidate with a single comparison against the root.
// sift_down moves the WORSE child upward so the root stays the worst.
class TopKHeap {
public:
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}

    std::size_t size() const noexcept { return n_; }

    void push(float v, std::uint32_t idx) {
        if (n_ < k_) {
            vals_[n_] = v;
            idxs_[n_] = idx;
            ++n_;
            if (n_ == k_) build();
            return;
        }
        if (!better(v, idx, vals_[0], idxs_[0])) return;
        vals_[0] = v;
        idxs_[0] = idx;
        sift_down(0);
    }

    const float* vals() const noexcept { return vals_.data(); }
    const std::uint32_t* idxs() const noexcept { return idxs_.data(); }

private:
    static bool better(float va, std::uint32_t ia, float vb, std::uint32_t ib) {
        return va > vb || (va == vb && ia < ib);
    }

    static bool worse(float va, std::uint32_t ia, float vb, std::uint32_t ib) {
        return va < vb || (va == vb && ia > ib);
    }

    void build() {
        for (std::size_t i = k_ / 2; i > 0; --i) sift_down(i - 1);
    }

    void sift_down(std::size_t i) {
        for (;;) {
            const std::size_t l = 2 * i + 1;
            const std::size_t r = 2 * i + 2;
            std::size_t m = i;
            if (l < n_ && worse(vals_[l], idxs_[l], vals_[m], idxs_[m])) m = l;
            if (r < n_ && worse(vals_[r], idxs_[r], vals_[m], idxs_[m])) m = r;
            if (m == i) return;
            std::swap(vals_[i], vals_[m]);
            std::swap(idxs_[i], idxs_[m]);
            i = m;
        }
    }

    std::size_t k_;
    std::size_t n_ = 0;
    std::vector<float> vals_;
    std::vector<std::uint32_t> idxs_;
};
```

### edit 11

**old:**
```
// ── int8 SIMD kernel (AVX-VNNI-INT8 VPDPBSSD, 8 rows interleaved) ───────────
// w      : int8 [dict x lat]
// scale  : per-row float (symmetric dequant: w ≈ q * scale)
// bias   : per-row float
// xq     : int8-quantized input vector, x_scale its dequant factor
// dot_i  = (sum_j q[i][j]*xq[j]) * scale[i] * x_scale + bias[i]
void int8_dense_kernel(const std::int8_t* w, const float* scale, const float* bias,
                       std::size_t dict, std::size_t lat, const std::int8_t* xq,
                       float x_scale, float* out) {
    const std::size_t chunks = lat / 32;  // 32 int8 per __m256i lane-group
    std::size_t i0 = 0;
    for (; i0 + 8 <= dict; i0 += 8) {
        const std::int8_t* rows[8];
        for (int r = 0; r < 8; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc[8] = {_mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256()};
        for (std::size_t k = 0; k < chunks; ++k) {
            const __m256i xv = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq + k * 32));
            for (int r = 0; r < 8; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + k * 32));
                acc[r] = _mm256_dpbssd_epi32(acc[r], rw, xv);
            }
        }
        for (int r = 0; r < 8; ++r) {
            const float dot = static_cast<float>(hsum256_epi32(acc[r])) * x_scale * scale[i0 + r] + bias[i0 + r];
            out[i0 + r] = dot > 0.0f ? dot : 0.0f;
        }
    }
    for (; i0 < dict; ++i0) {  // dict tail rows (scalar)
        const std::int8_t* row = w + i0 * lat;
        int64_t s = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xv = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq + j));
            s += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xv));
        }
        for (; j < lat; ++j) {
            s += static_cast<int64_t>(row[j]) * xq[j];
        }
        const float dot = static_cast<float>(s) * x_scale * scale[i0] + bias[i0];
        out[i0] = dot > 0.0f ? dot : 0.0f;
    }
}
```

**new:**
```
// ── int8 SIMD kernel (AVX-VNNI-INT8 VPDPBSSD, 8 rows interleaved) ───────────
// w      : int8 [dict x lat]
// scale  : per-row float (symmetric dequant: w ≈ q * scale)
// bias   : per-row float
// x is supplied as TWO int8 planes (hi + lo residual) so the input keeps
// ~14-bit effective precision: x ≈ q_hi*xs_hi + q_lo*xs_lo. Single 8-bit x
// quantization perturbs dots by ~0.016, which flips top-64 boundary features
// and diverges the 8D gestalt by 16-27% (measured); the split keeps the
// selection identical to the float path (8D diff ~1e-3) at a ~2x compute cost
// that is still hidden under the dict's RAM streaming.
// dot_i  = (sum_j q[i][j]*q_hi[j] * xs_hi + sum_j q[i][j]*q_lo[j] * xs_lo)
//          * scale[i] + bias[i]
void int8_dense_kernel(const std::int8_t* w, const float* scale, const float* bias,
                       std::size_t dict, std::size_t lat, const std::int8_t* xq_hi,
                       float xs_hi, const std::int8_t* xq_lo, float xs_lo, float* out) {
    const std::size_t chunks = lat / 32;  // 32 int8 per __m256i lane-group
    std::size_t i0 = 0;
    for (; i0 + 8 <= dict; i0 += 8) {
        const std::int8_t* rows[8];
        for (int r = 0; r < 8; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[8];
        __m256i acc_lo[8];
        for (int r = 0; r < 8; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        for (std::size_t k = 0; k < chunks; ++k) {
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + k * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + k * 32));
            for (int r = 0; r < 8; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + k * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < 8; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            out[i0 + r] = dot > 0.0f ? dot : 0.0f;
        }
    }
    for (; i0 < dict; ++i0) {  // dict tail rows (scalar)
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        out[i0] = dot > 0.0f ? dot : 0.0f;
    }
}
```

### edit 12

**old:**
```
// int8 SIMD + inline heap (the deployed fast path).
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq, float x_scale, std::size_t k) {
    const std::size_t chunks = lat / 32;
    TopKHeap heap(k);
    std::size_t i0 = 0;
    for (; i0 + 8 <= dict; i0 += 8) {
        const std::int8_t* rows[8];
        for (int r = 0; r < 8; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc[8] = {_mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256(),
                          _mm256_setzero_si256(), _mm256_setzero_si256()};
        for (std::size_t kk = 0; kk < chunks; ++kk) {
            const __m256i xv = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq + kk * 32));
            for (int r = 0; r < 8; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc[r] = _mm256_dpbssd_epi32(acc[r], rw, xv);
            }
        }
        for (int r = 0; r < 8; ++r) {
            const float dot = static_cast<float>(hsum256_epi32(acc[r])) * x_scale * scale[i0 + r] + bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
    }
    for (; i0 < dict; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xv = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq + j));
            s += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xv));
        }
        for (; j < lat; ++j) {
            s += static_cast<int64_t>(row[j]) * xq[j];
        }
        const float dot = static_cast<float>(s) * x_scale * scale[i0] + bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

**new:**
```
// int8 SIMD + inline heap (the deployed fast path). Split-precision x (hi+lo)
// keeps top-k selection identical to the float path (see int8_dense_kernel).
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq_hi, float xs_hi,
                                const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
    const std::size_t chunks = lat / 32;
    TopKHeap heap(k);
    std::size_t i0 = 0;
    for (; i0 + 8 <= dict; i0 += 8) {
        const std::int8_t* rows[8];
        for (int r = 0; r < 8; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[8];
        __m256i acc_lo[8];
        for (int r = 0; r < 8; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        for (std::size_t kk = 0; kk < chunks; ++kk) {
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            for (int r = 0; r < 8; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < 8; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
    }
    for (; i0 < dict; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

### edit 13

**old:**
```
// Quantize x (a latent vector) to signed int8, symmetric.
// Returns the dequant scale via *x_scale. Returns false if x has no dynamic
// range (all zeros) — xq is zeroed so the int8 dot is then exactly 0.
void quantize_x(const float* x, std::size_t lat, std::int8_t* xq, float* x_scale) {
    float mx = 0.0f;
    for (std::size_t j = 0; j < lat; ++j) {
        mx = std::max(mx, std::fabsf(x[j]));
    }
    if (!(mx > 0.0f) || !std::isfinite(mx)) {
        *x_scale = 1.0f;
        for (std::size_t j = 0; j < lat; ++j) xq[j] = 0;
        return;
    }
    const float scale = mx / 127.0f;
    *x_scale = scale;
    for (std::size_t j = 0; j < lat; ++j) {
        int q = static_cast<int>(std::lroundf(x[j] / scale));
        if (q > 127) q = 127;
        if (q < -127) q = -127;
        xq[j] = static_cast<std::int8_t>(q);
    }
}
```

**new:**
```
// Quantize x (a latent vector) to split-precision signed int8: a coarse plane
// xq_hi over the full [-mx, mx] range plus a fine plane xq_lo over the
// residual (x - q_hi*xs_hi). Reconstruction error per element ~ xs_lo/2 with
// xs_lo ~ mx/127/127, i.e. ~14 effective bits. Returns false for a degenerate
// x (all zeros / non-finite); planes are zeroed and scales set to 1 so the
// int8 dot is then exactly 0.
void quantize_x(const float* x, std::size_t lat, std::int8_t* xq_hi, float* xs_hi,
                std::int8_t* xq_lo, float* xs_lo) {
    float mx = 0.0f;
    for (std::size_t j = 0; j < lat; ++j) {
        mx = std::max(mx, std::fabsf(x[j]));
    }
    if (!(mx > 0.0f) || !std::isfinite(mx)) {
        *xs_hi = 1.0f;
        *xs_lo = 1.0f;
        for (std::size_t j = 0; j < lat; ++j) {
            xq_hi[j] = 0;
            xq_lo[j] = 0;
        }
        return;
    }
    const float s_hi = mx / 127.0f;
    *xs_hi = s_hi;
    float mres = 0.0f;
    for (std::size_t j = 0; j < lat; ++j) {
        int q = static_cast<int>(std::lroundf(x[j] / s_hi));
        if (q > 127) q = 127;
        if (q < -127) q = -127;
        xq_hi[j] = static_cast<std::int8_t>(q);
        const float res = x[j] - static_cast<float>(q) * s_hi;
        mres = std::max(mres, std::fabsf(res));
    }
    const float s_lo = mres > 0.0f ? mres / 127.0f : 1.0f;
    *xs_lo = s_lo;
    for (std::size_t j = 0; j < lat; ++j) {
        const float res = x[j] - static_cast<float>(xq_hi[j]) * s_hi;
        int q = static_cast<int>(std::lroundf(res / s_lo));
        if (q > 127) q = 127;
        if (q < -127) q = -127;
        xq_lo[j] = static_cast<std::int8_t>(q);
    }
}
```

### edit 14

**old:**
```
SaeProjection::~SaeProjection() {
    free_mem(fw_);
    free_mem(fbias_);
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
}
```

**new:**
```
SaeProjection::~SaeProjection() {
    free_mem(fw_);
    free_mem(fbias_);
    release_int8_storage();
}
```

### edit 15

**old:**
```
    require_latent(x);
    std::vector<float> out(dict_size_);
    std::vector<std::int8_t> xq(latent_dim_);
    float x_scale = 1.0f;
    quantize_x(x.data(), latent_dim_, xq.data(), &x_scale);
    int8_dense_kernel(iw_, iscale_, ibias_, dict_size_, latent_dim_, xq.data(), x_scale,
                      out.data());
    return out;
}
```

**new:**
```
    require_latent(x);
    std::vector<float> out(dict_size_);
    std::vector<std::int8_t> xq_hi(latent_dim_);
    std::vector<std::int8_t> xq_lo(latent_dim_);
    float xs_hi = 1.0f;
    float xs_lo = 1.0f;
    quantize_x(x.data(), latent_dim_, xq_hi.data(), &xs_hi, xq_lo.data(), &xs_lo);
    int8_dense_kernel(iw_, iscale_, ibias_, dict_size_, latent_dim_, xq_hi.data(), xs_hi,
                      xq_lo.data(), xs_lo, out.data());
    return out;
}
```

### edit 16

**old:**
```
SaeProjection& SaeProjection::operator=(SaeProjection&& other) noexcept {
    if (this == &other) return *this;
    free_mem(fw_);
    free_mem(fbias_);
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    if (mmap_view_) UnmapViewOfFile(mmap_view_);
```

**new:**
```
SaeProjection& SaeProjection::operator=(SaeProjection&& other) noexcept {
    if (this == &other) return *this;
    free_mem(fw_);
    free_mem(fbias_);
    release_int8_storage();
```

### edit 17

**old:**
```
bool SaeProjection::generate_float_dictionary() {
    free_mem(fw_);
    free_mem(fbias_);
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    fw_ = nullptr;
    fbias_ = nullptr;
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;
```

**new:**
```
bool SaeProjection::generate_float_dictionary() {
    free_mem(fw_);
    free_mem(fbias_);
    fw_ = nullptr;
    fbias_ = nullptr;
    release_int8_storage();
```

### edit 18

**old:**
```
    require_latent(x);
    std::vector<std::int8_t> xq(latent_dim_);
    float x_scale = 1.0f;
    quantize_x(x.data(), latent_dim_, xq.data(), &x_scale);
    return int8_topk_kernel(iw_, iscale_, ibias_, dict_size_, latent_dim_, xq.data(),
                            x_scale, top_k_);
}
```

**new:**
```
    require_latent(x);
    std::vector<std::int8_t> xq_hi(latent_dim_);
    std::vector<std::int8_t> xq_lo(latent_dim_);
    float xs_hi = 1.0f;
    float xs_lo = 1.0f;
    quantize_x(x.data(), latent_dim_, xq_hi.data(), &xs_hi, xq_lo.data(), &xs_lo);
    return int8_topk_kernel(iw_, iscale_, ibias_, dict_size_, latent_dim_, xq_hi.data(),
                            xs_hi, xq_lo.data(), xs_lo, top_k_);
}
```

### edit 19

**old:**
```
bool SaeProjection::quantize_to_int8() {
    if (!fw_ || !fbias_) return false;
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;
```

**new:**
```
bool SaeProjection::quantize_to_int8() {
    if (!fw_ || !fbias_) return false;
    release_int8_storage();
```

### edit 20

**old:**
```
bool SaeProjection::load_int8_mmap(const std::string& path) {
    // Free any in-memory int8 copy (float is kept).
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;
```

**new:**
```
bool SaeProjection::load_int8_mmap(const std::string& path) {
    // Free any in-memory int8 copy (float is kept).
    release_int8_storage();
```

### edit 21

**old:**
```
bool SaeProjection::load_float_dictionary(const std::string& path) {
    free_mem(fw_);
    free_mem(fbias_);
    free_mem(iw_);
    free_mem(iscale_);
    free_mem(izp_);
    free_mem(ibias_);
    fw_ = fbias_ = nullptr;
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    if (mmap_view_) {
        UnmapViewOfFile(mmap_view_);
        mmap_view_ = nullptr;
    }
    int8_mmap_ = false;
```

**new:**
```
bool SaeProjection::load_float_dictionary(const std::string& path) {
    free_mem(fw_);
    free_mem(fbias_);
    fw_ = fbias_ = nullptr;
    release_int8_storage();
```

### edit 22

**old:**
```
void SaeProjection::require_latent(std::span<const float> x) const {
    if (x.size() != latent_dim_) {
        throw std::invalid_argument("SaeProjection: expected latent vector of size " +
                                    std::to_string(latent_dim_) + ", got " +
                                    std::to_string(x.size()));
    }
}
```

**new:**
```
void SaeProjection::require_latent(std::span<const float> x) const {
    if (x.size() != latent_dim_) {
        throw std::invalid_argument("SaeProjection: expected latent vector of size " +
                                    std::to_string(latent_dim_) + ", got " +
                                    std::to_string(x.size()));
    }
}

void SaeProjection::release_int8_storage() noexcept {
    if (int8_mmap_) {
        if (mmap_view_) {
            UnmapViewOfFile(mmap_view_);
            mmap_view_ = nullptr;
        }
    } else {
        free_mem(iw_);
        free_mem(iscale_);
        free_mem(izp_);
        free_mem(ibias_);
    }
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    mmap_size_ = 0;
    int8_mmap_ = false;
}
```

### edit 23

**old:**
```
const char* SaeProjection::simd_backend_name() noexcept {
#if SAE_HAS_STD_SIMD
    return "std::simd (P1928)";
#else
    return "AVX2+AVX-VNNI-INT8 intrinsics (no <simd> in GCC 16.1; no AVX-512 on CPU)";
#endif
}
```

**new:**
```
const char* SaeProjection::simd_backend_name() noexcept {
#if SAE_HAS_STD_SIMD
    return "std::simd (P1928)";
#else
    return "AVX2+AVX-VNNI-INT8 intrinsics (no <simd> in GCC 16.1; no AVX-512 on CPU)";
#endif
}

// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// Runs the 64-entry min-heap on hand-checkable arrays with k=3 and prints the
// heap state after every push. Verifies: (1) the heap keeps the k LARGEST under
// (value desc, index asc); (2) the root is always the WORST kept element; (3)
// full-heap replacement + sift_down works; (4) equal-value ties keep the
// smaller index (a larger-index equal value is displaced/rejected).
bool heap_self_test() {
    using Entry = std::pair<float, std::uint32_t>;
    const auto worse = [](const Entry& a, const Entry& b) {
        return a.first < b.first || (a.first == b.first && a.second > b.second);
    };
    bool ok = true;
    const auto check_invariant = [&](const TopKHeap& h, const char* tag) {
        for (std::size_t t = 1; t < h.size(); ++t) {
            const Entry root{h.vals()[0], h.idxs()[0]};
            const Entry other{h.vals()[t], h.idxs()[t]};
            if (!worse(root, other)) {
                std::printf("[heap] %s: root (%.0f,%u) NOT worst vs (%.0f,%u)\n",
                            tag, root.first, root.second, other.first, other.second);
                ok = false;
            }
        }
    };

    // Case 1: 10 distinct values, k=3. Kept set MUST be {(8,2),(9,3),(10,9)}.
    const Entry data[] = {{5, 0}, {3, 1}, {8, 2}, {9, 3}, {1, 4},
                          {7, 5}, {6, 6}, {4, 7}, {2, 8}, {10, 9}};
    {
        TopKHeap h(3);
        for (const Entry& e : data) {
            h.push(e.first, e.second);
            std::printf("[heap] push (%.0f,%u) -> heap:", e.first, e.second);
            for (std::size_t t = 0; t < h.size(); ++t)
                std::printf(" (%.0f,%u)", h.vals()[t], h.idxs()[t]);
            std::printf("\n");
            check_invariant(h, "case1");
        }
        std::vector<Entry> got;
        for (std::size_t t = 0; t < h.size(); ++t) got.emplace_back(h.vals()[t], h.idxs()[t]);
        std::sort(got.begin(), got.end());
        const std::vector<Entry> expect = {{8, 2}, {9, 3}, {10, 9}};
        if (got != expect) {
            std::printf("[heap] case1 kept set MISMATCH\n");
            ok = false;
        } else {
            std::printf("[heap] case1 kept set = {(8,2),(9,3),(10,9)} OK\n");
        }
    }

    // Case 2: equal-value tie-break, k=3. (8,10) must be displaced by (8,3);
    // kept set MUST be {(8,2),(8,3),(9,4)}.
    const Entry seq[] = {{8, 2}, {8, 10}, {9, 4}, {8, 3}};
    {
        TopKHeap h(3);
        for (const Entry& e : seq) {
            h.push(e.first, e.second);
            std::printf("[heap] tie push (%.0f,%u) -> heap:", e.first, e.second);
            for (std::size_t t = 0; t < h.size(); ++t)
                std::printf(" (%.0f,%u)", h.vals()[t], h.idxs()[t]);
            std::printf("\n");
            check_invariant(h, "case2");
        }
        std::vector<Entry> got;
        for (std::size_t t = 0; t < h.size(); ++t) got.emplace_back(h.vals()[t], h.idxs()[t]);
        std::sort(got.begin(), got.end());
        const std::vector<Entry> expect = {{8, 2}, {8, 3}, {9, 4}};
        if (got != expect) {
            std::printf("[heap] case2 tie-break kept set MISMATCH\n");
            ok = false;
        } else {
            std::printf("[heap] case2 tie-break kept set = {(8,2),(8,3),(9,4)} OK\n");
        }
    }
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}
```

### edit 24

**old:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// Runs the 64-entry min-heap on hand-checkable arrays with k=3 and prints the
// heap state after every push. Verifies: (1) the heap keeps the k LARGEST under
// (value desc, index asc); (2) the root is always the WORST kept element; (3)
// full-heap replacement + sift_down works; (4) equal-value ties keep the
// smaller index (a larger-index equal value is displaced/rejected).
bool heap_self_test() {
```

**new:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool heap_self_test() {
```

### edit 25

**old:**
```
// ── Reflection / alignment ───────────────────────────────────────────────────

std::uintptr_t SaeProjection::row_address(std::size_t row) const noexcept {
```

**new:**
```
// ── Reflection / alignment ───────────────────────────────────────────────────

void SaeProjection::release_int8_storage() noexcept {
    if (int8_mmap_) {
        if (mmap_view_) {
            UnmapViewOfFile(mmap_view_);
            mmap_view_ = nullptr;
        }
    } else {
        free_mem(iw_);
        free_mem(iscale_);
        free_mem(izp_);
        free_mem(ibias_);
    }
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    mmap_size_ = 0;
    int8_mmap_ = false;
}

std::uintptr_t SaeProjection::row_address(std::size_t row) const noexcept {
```

### edit 26

**old:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool heap_self_test() {
```

**new:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool run_heap_self_test_impl() {
```

### edit 27

**old:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

bool SaeProjection::heap_self_test() { return run_heap_self_test_impl(); }

}  // namespace SAE
}  // namespace Athenea
```

### edit 28

**old:**
```
// ── Reflection / alignment ───────────────────────────────────────────────────

void SaeProjection::release_int8_storage() noexcept {
    if (int8_mmap_) {
        if (mmap_view_) {
            UnmapViewOfFile(mmap_view_);
            mmap_view_ = nullptr;
        }
    } else {
        free_mem(iw_);
        free_mem(iscale_);
        free_mem(izp_);
        free_mem(ibias_);
    }
    iw_ = nullptr;
    iscale_ = nullptr;
    izp_ = nullptr;
    ibias_ = nullptr;
    mmap_size_ = 0;
    int8_mmap_ = false;
}

std::uintptr_t SaeProjection::row_address(std::size_t row) const noexcept {
```

**new:**
```
// ── Reflection / alignment ───────────────────────────────────────────────────

std::uintptr_t SaeProjection::row_address(std::size_t row) const noexcept {
```

### edit 29

**old:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool run_heap_self_test_impl() {
```

**new:**
```
// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool heap_self_test() {
```

### edit 30

**old:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

bool SaeProjection::heap_self_test() { return run_heap_self_test_impl(); }

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

}  // namespace SAE
}  // namespace Athenea
```

### edit 31

**old:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

bool SaeProjection::heap_self_test() { return heap_self_test(); }

}  // namespace SAE
}  // namespace Athenea
```

### edit 32

**old:**
```
bool SaeProjection::heap_self_test() { return heap_self_test(); }
```

**new:**
```
bool SaeProjection::heap_self_test() { return Athenea::SAE::heap_self_test(); }
```

### edit 33

**old:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

bool SaeProjection::heap_self_test() { return Athenea::SAE::heap_self_test(); }

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

}  // namespace SAE
}  // namespace Athenea
```

### edit 34

**old:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

bool SaeProjection::heap_self_test() { return Athenea::SAE::heap_self_test(); }

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
    std::printf("[heap] self_test_verdict=%s\n", ok ? "PASS" : "FAIL");
    return ok;
}

}  // namespace SAE
}  // namespace Athenea
```

### edit 35

**old:**
```
    bool ok = true;
    const auto check_invariant = [&](const TopKHeap& h, const char* tag) {
        for (std::size_t t = 1; t < h.size(); ++t) {
            const Entry root{h.vals()[0], h.idxs()[0]};
            const Entry other{h.vals()[t], h.idxs()[t]};
            if (!worse(root, other)) {
                std::printf("[heap] %s: root (%.0f,%u) NOT worst vs (%.0f,%u)\n",
                            tag, root.first, root.second, other.first, other.second);
                ok = false;
            }
        }
    };
```

**new:**
```
    bool ok = true;
    // The "root is worst" min-heap invariant is only ESTABLISHED once the heap
    // is full and build() has run (n == k). Before that the internal array is
    // raw push order, so the check is only meaningful on the full heap.
    const auto check_invariant = [&](const TopKHeap& h, const char* tag, std::size_t k) {
        if (h.size() < k) return;  // not heapified yet — no invariant to assert
        for (std::size_t t = 1; t < h.size(); ++t) {
            const Entry root{h.vals()[0], h.idxs()[0]};
            const Entry other{h.vals()[t], h.idxs()[t]};
            if (!worse(root, other)) {
                std::printf("[heap] %s: root (%.0f,%u) NOT worst vs (%.0f,%u)\n",
                            tag, root.first, root.second, other.first, other.second);
                ok = false;
            }
        }
    };
```

### edit 36

**old:**
```
            std::printf("\n");
            check_invariant(h, "case1");
        }
```

**new:**
```
            std::printf("\n");
            check_invariant(h, "case1", 3);
        }
```

### edit 37

**old:**
```
            std::printf("\n");
            check_invariant(h, "case2");
        }
```

**new:**
```
            std::printf("\n");
            check_invariant(h, "case2", 3);
        }
```

### edit 38

**old:**
```
// int8 SIMD + inline heap (the deployed fast path). Split-precision x (hi+lo)
// keeps top-k selection identical to the float path (see int8_dense_kernel).
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq_hi, float xs_hi,
                                const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
    const std::size_t chunks = lat / 32;
    TopKHeap heap(k);
    std::size_t i0 = 0;
    for (; i0 + 8 <= dict; i0 += 8) {
        const std::int8_t* rows[8];
        for (int r = 0; r < 8; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[8];
        __m256i acc_lo[8];
        for (int r = 0; r < 8; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        for (std::size_t kk = 0; kk < chunks; ++kk) {
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            for (int r = 0; r < 8; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < 8; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
    }
    for (; i0 < dict; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

**new:**
```
// int8 SIMD + inline heap (the deployed fast path). Split-precision x (hi+lo)
// keeps top-k selection identical to the float path (see int8_dense_kernel).
//
// Performance notes (bench gate >= 10x, measured on Intel Ultra 9 275HX):
//   * G=4 rows in flight: 8 live ymm accumulators (4 hi + 4 lo) leave enough
//     registers for the xh/xl/rw operands — the previous G=8 variant held 16
//     accumulators and forced every operand to spill, capping the dict stream
//     at ~17 GB/s. G=4 sustains ~35-40 GB/s on the 335 MB mmap dict.
//   * The chunk loop is unrolled by 2 so each row reads 64 contiguous bytes
//     per iteration (2x32B), which the hardware prefetcher tracks as a single
//     sequential stream instead of interleaved 32B hops.
//   * The next row group's first cache line is prefetched while the current
//     group computes, hiding DRAM latency under the dot-product work.
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq_hi, float xs_hi,
                                const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
    const std::size_t chunks = lat / 32;
    constexpr int G = 4;
    TopKHeap heap(k);
    std::size_t i0 = 0;
    for (; i0 + G <= dict; i0 += G) {
        const std::int8_t* rows[G];
        for (int r = 0; r < G; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[G];
        __m256i acc_lo[G];
        for (int r = 0; r < G; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        std::size_t kk = 0;
        for (; kk + 2 <= chunks; kk += 2) {
            const __m256i xh0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            const __m256i xh1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32 + 32));
            const __m256i xl1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32 + 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                const __m256i rw1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32 + 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw0, xh0);
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw1, xh1);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw0, xl0);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw1, xl1);
            }
        }
        for (; kk < chunks; ++kk) {  // odd tail chunk (lat not divisible by 64)
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < G; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
        if (i0 + 2 * G <= dict) {
            _mm_prefetch(reinterpret_cast<const char*>(w + (i0 + 2 * G) * lat), _MM_HINT_T0);
        }
    }
    for (; i0 < dict; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

### edit 39

**old:**
```
// int8 SIMD + inline heap (the deployed fast path). Split-precision x (hi+lo)
// keeps top-k selection identical to the float path (see int8_dense_kernel).
//
// Performance notes (bench gate >= 10x, measured on Intel Ultra 9 275HX):
//   * G=4 rows in flight: 8 live ymm accumulators (4 hi + 4 lo) leave enough
//     registers for the xh/xl/rw operands — the previous G=8 variant held 16
//     accumulators and forced every operand to spill, capping the dict stream
//     at ~17 GB/s. G=4 sustains ~35-40 GB/s on the 335 MB mmap dict.
//   * The chunk loop is unrolled by 2 so each row reads 64 contiguous bytes
//     per iteration (2x32B), which the hardware prefetcher tracks as a single
//     sequential stream instead of interleaved 32B hops.
//   * The next row group's first cache line is prefetched while the current
//     group computes, hiding DRAM latency under the dot-product work.
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq_hi, float xs_hi,
                                const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
    const std::size_t chunks = lat / 32;
    constexpr int G = 4;
    TopKHeap heap(k);
    std::size_t i0 = 0;
    for (; i0 + G <= dict; i0 += G) {
        const std::int8_t* rows[G];
        for (int r = 0; r < G; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[G];
        __m256i acc_lo[G];
        for (int r = 0; r < G; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        std::size_t kk = 0;
        for (; kk + 2 <= chunks; kk += 2) {
            const __m256i xh0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            const __m256i xh1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32 + 32));
            const __m256i xl1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32 + 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                const __m256i rw1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32 + 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw0, xh0);
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw1, xh1);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw0, xl0);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw1, xl1);
            }
        }
        for (; kk < chunks; ++kk) {  // odd tail chunk (lat not divisible by 64)
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < G; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
        if (i0 + 2 * G <= dict) {
            _mm_prefetch(reinterpret_cast<const char*>(w + (i0 + 2 * G) * lat), _MM_HINT_T0);
        }
    }
    for (; i0 < dict; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}
```

**new:**
```
// ── int8 top-k row processing (one contiguous row range) ────────────────────
// G=4 rows in flight: 8 live ymm accumulators (4 hi + 4 lo) leave enough
// registers for the xh/xl/rw operands — the previous G=8 variant held 16
// accumulators and forced every operand to spill, capping the dict stream at
// ~17 GB/s. G=4 sustains ~35-40 GB/s on the 335 MB mmap dict. The chunk loop
// is unrolled by 2 so each row reads 64 contiguous bytes per iteration
// (2x32B), which the hardware prefetcher tracks as a single sequential stream
// instead of interleaved 32B hops. Deterministic: rows are processed in index
// order, so the top-k SET+VALUES are identical to any other row split.
void int8_row_range(TopKHeap& heap, const std::int8_t* w, const float* scale,
                    const float* bias, const std::int8_t* xq_hi, float xs_hi,
                    const std::int8_t* xq_lo, float xs_lo,
                    std::size_t begin, std::size_t end, std::size_t lat) {
    const std::size_t chunks = lat / 32;
    constexpr int G = 4;
    std::size_t i0 = begin;
    for (; i0 + G <= end; i0 += G) {
        const std::int8_t* rows[G];
        for (int r = 0; r < G; ++r) rows[r] = w + (i0 + r) * lat;
        __m256i acc_hi[G];
        __m256i acc_lo[G];
        for (int r = 0; r < G; ++r) {
            acc_hi[r] = _mm256_setzero_si256();
            acc_lo[r] = _mm256_setzero_si256();
        }
        std::size_t kk = 0;
        for (; kk + 2 <= chunks; kk += 2) {
            const __m256i xh0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            const __m256i xh1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32 + 32));
            const __m256i xl1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32 + 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw0 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                const __m256i rw1 = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32 + 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw0, xh0);
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw1, xh1);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw0, xl0);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw1, xl1);
            }
        }
        for (; kk < chunks; ++kk) {  // odd tail chunk (lat not divisible by 64)
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + kk * 32));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + kk * 32));
            for (int r = 0; r < G; ++r) {
                const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(rows[r] + kk * 32));
                acc_hi[r] = _mm256_dpbssd_epi32(acc_hi[r], rw, xh);
                acc_lo[r] = _mm256_dpbssd_epi32(acc_lo[r], rw, xl);
            }
        }
        for (int r = 0; r < G; ++r) {
            const float dot = (static_cast<float>(hsum256_epi32(acc_hi[r])) * xs_hi +
                               static_cast<float>(hsum256_epi32(acc_lo[r])) * xs_lo) *
                                  scale[i0 + r] +
                              bias[i0 + r];
            heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0 + r));
        }
        if (i0 + 2 * G <= end) {
            _mm_prefetch(reinterpret_cast<const char*>(w + (i0 + 2 * G) * lat), _MM_HINT_T0);
        }
    }
    for (; i0 < end; ++i0) {
        const std::int8_t* row = w + i0 * lat;
        int64_t s_hi = 0;
        int64_t s_lo = 0;
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            const __m256i rw = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(row + j));
            const __m256i xh = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_hi + j));
            const __m256i xl = _mm256_loadu_si256(reinterpret_cast<const __m256i*>(xq_lo + j));
            s_hi += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xh));
            s_lo += hsum256_epi32(_mm256_dpbssd_epi32(_mm256_setzero_si256(), rw, xl));
        }
        for (; j < lat; ++j) {
            s_hi += static_cast<int64_t>(row[j]) * xq_hi[j];
            s_lo += static_cast<int64_t>(row[j]) * xq_lo[j];
        }
        const float dot = (static_cast<float>(s_hi) * xs_hi + static_cast<float>(s_lo) * xs_lo) *
                              scale[i0] +
                          bias[i0];
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i0));
    }
}

// ── Persistent worker pool for the int8 top-k kernel ────────────────────────
// The mmap'd dict is 335 MB; a single core streams it at ~17 GB/s (DRAM wall).
// Splitting the rows across the 24 cores scales the aggregate bandwidth to the
// memory controller's limit. Rows are partitioned into CONTIGUOUS ranges (one
// per worker) so each worker streams one sequential dict region — ideal for the
// hardware prefetcher. Deterministic: each worker owns a fixed range and the
// per-worker heaps are merged in fixed worker order into a fresh heap, so the
// top-k SET+VALUES are identical regardless of thread count.
class Int8TopkPool {
public:
    Int8TopkPool()
        : nthreads_(pick_threads()),
          heaps_(static_cast<std::size_t>(nthreads_)),
          seen_(static_cast<std::size_t>(nthreads_), 0) {
        for (int t = 0; t < nthreads_; ++t) {
            workers_.emplace_back([this, t] { worker_loop(t); });
        }
    }

    ~Int8TopkPool() {
        {
            std::lock_guard<std::mutex> lk(mtx_);
            stop_ = true;
        }
        cv_work_.notify_all();
        for (auto& wt : workers_) wt.join();
    }

    Int8TopkPool(const Int8TopkPool&) = delete;
    Int8TopkPool& operator=(const Int8TopkPool&) = delete;

    Athenea::SAE::SparseFeatures run(const std::int8_t* w, const float* scale,
                                     const float* bias, std::size_t dict, std::size_t lat,
                                     const std::int8_t* xq_hi, float xs_hi,
                                     const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
        {
            std::lock_guard<std::mutex> lk(mtx_);
            w_ = w;
            scale_ = scale;
            bias_ = bias;
            xq_hi_ = xq_hi;
            xs_hi_ = xs_hi;
            xq_lo_ = xq_lo;
            xs_lo_ = xs_lo;
            dict_ = dict;
            lat_ = lat;
            rows_per_ = (dict_ + static_cast<std::size_t>(nthreads_) - 1) /
                        static_cast<std::size_t>(nthreads_);
            for (TopKHeap& h : heaps_) h.reset(k);
            active_ = nthreads_;
            ++gen_;
        }
        cv_work_.notify_all();
        {
            std::unique_lock<std::mutex> lk(mtx_);
            cv_done_.wait(lk, [this] { return active_ == 0; });
        }
        Athenea::SAE::SparseFeatures out;
        {
            std::lock_guard<std::mutex> lk(mtx_);
            TopKHeap merged(k);
            for (const TopKHeap& h : heaps_) {
                for (std::size_t t = 0; t < h.size(); ++t) {
                    merged.push(h.vals()[t], h.idxs()[t]);
                }
            }
            out.indices.assign(merged.idxs(), merged.idxs() + merged.size());
            out.values.assign(merged.vals(), merged.vals() + merged.size());
        }
        return out;
    }

private:
    static int pick_threads() {
        unsigned hc = std::thread::hardware_concurrency();
        if (hc < 2) return 2;
        if (hc > 24) return 24;
        return static_cast<int>(hc);
    }

    void worker_loop(int id) {
        std::unique_lock<std::mutex> lk(mtx_);
        for (;;) {
            cv_work_.wait(lk, [this, id] { return stop_ || seen_[static_cast<std::size_t>(id)] < gen_; });
            if (stop_) return;
            seen_[static_cast<std::size_t>(id)] = gen_;
            const std::int8_t* w = w_;
            const float* scale = scale_;
            const float* bias = bias_;
            const std::int8_t* xq_hi = xq_hi_;
            const float xs_hi = xs_hi_;
            const std::int8_t* xq_lo = xq_lo_;
            const float xs_lo = xs_lo_;
            const std::size_t begin = static_cast<std::size_t>(id) * rows_per_;
            const std::size_t end = std::min(begin + rows_per_, dict_);
            const std::size_t lat = lat_;
            lk.unlock();
            int8_row_range(heaps_[static_cast<std::size_t>(id)], w, scale, bias,
                           xq_hi, xs_hi, xq_lo, xs_lo, begin, end, lat);
            lk.lock();
            --active_;
            if (active_ == 0) cv_done_.notify_all();
        }
    }

    const int nthreads_;
    std::vector<std::thread> workers_;
    std::vector<TopKHeap> heaps_;
    std::vector<std::uint64_t> seen_;
    std::uint64_t gen_ = 0;
    std::mutex mtx_;
    std::condition_variable cv_work_;
    std::condition_variable cv_done_;
    bool stop_ = false;
    int active_ = 0;

    const std::int8_t* w_ = nullptr;
    const float* scale_ = nullptr;
    const float* bias_ = nullptr;
    const std::int8_t* xq_hi_ = nullptr;
    float xs_hi_ = 0.0f;
    const std::int8_t* xq_lo_ = nullptr;
    float xs_lo_ = 0.0f;
    std::size_t dict_ = 0;
    std::size_t lat_ = 0;
    std::size_t rows_per_ = 0;
};

Int8TopkPool& int8_pool() {
    static Int8TopkPool pool;
    return pool;
}

// int8 SIMD + inline heap (the deployed fast path). Split-precision x (hi+lo)
// keeps top-k selection identical to the float path (see int8_dense_kernel).
Athenea::SAE::SparseFeatures int8_topk_kernel(const std::int8_t* w, const float* scale,
                                const float* bias, std::size_t dict, std::size_t lat,
                                const std::int8_t* xq_hi, float xs_hi,
                                const std::int8_t* xq_lo, float xs_lo, std::size_t k) {
    return int8_pool().run(w, scale, bias, dict, lat, xq_hi, xs_hi, xq_lo, xs_lo, k);
}
```

### edit 40

**old:**
```
class TopKHeap {
public:
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}

    std::size_t size() const noexcept { return n_; }
```

**new:**
```
class TopKHeap {
public:
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}

    void reset(std::size_t k) {
        k_ = k;
        n_ = 0;
        if (vals_.size() != k) {
            vals_.resize(k);
            idxs_.resize(k);
        }
    }

    std::size_t size() const noexcept { return n_; }
```

### edit 41

**old:**
```
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <stdexcept>
```

**new:**
```
#include <algorithm>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <random>
#include <stdexcept>
#include <thread>
```

### edit 42

**old:**
```
class TopKHeap {
public:
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}
```

**new:**
```
class TopKHeap {
public:
    TopKHeap() = default;
    explicit TopKHeap(std::size_t k) : k_(k), vals_(k), idxs_(k) {}
```

## `codex\src\codex\sae_projection.hpp`

### write 1 (9348 bytes)

### write 2 (10022 bytes)

### edit 3

**old:**
```
private:
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
```

**new:**
```
private:
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
    // Release the int8 dictionary storage. When int8_mmap_ is set, iw_/iscale_/
    // izp_/ibias_ point INSIDE mmap_view_ and must NOT be _mm_free'd — the view
    // is released with UnmapViewOfFile. Otherwise the pointers are individually
    // owned (allocated with _mm_malloc). Never _mm_free a mapped pointer (that
    // crashes 0xC0000005), never UnmapViewOfFile a heap pointer.
    void release_int8_storage() noexcept;
```

### edit 4

**old:**
```
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
    // Release the int8 dictionary storage. When int8_mmap_ is set, iw_/iscale_/
    // izp_/ibias_ point INSIDE mmap_view_ and must NOT be _mm_free'd — the view
    // is released with UnmapViewOfFile. Otherwise the pointers are individually
    // owned (allocated with _mm_malloc). Never _mm_free a mapped pointer (that
    // crashes 0xC0000005), never UnmapViewOfFile a heap pointer.
    void release_int8_storage() noexcept;
```

**new:**
```
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
    // int8 pointers are _mm_malloc'd EXCEPT when int8_mmap_ is set (they point
    // inside mmap_view_): never _mm_free a mapped pointer (0xC0000005), never
    // UnmapViewOfFile a heap pointer.
    void release_int8_storage() noexcept;
```

### edit 5

**old:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;
```

**new:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

    // TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
    // array into the k=3 heap, prints heap state after every push, and verifies
    // the heap keeps the k LARGEST with (value desc, index asc) tie-break and
    // root=WORST. Returns true when both the distinct-value and tie-break cases
    // hold (the trace is printed to stdout).
    bool heap_self_test();
```

### edit 6

**old:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

    // TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
    // array into the k=3 heap, prints heap state after every push, and verifies
    // the heap keeps the k LARGEST with (value desc, index asc) tie-break and
    // root=WORST. Returns true when both the distinct-value and tie-break cases
    // hold (the trace is printed to stdout).
    bool heap_self_test();

private:
```

**new:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

private:
```

### edit 7

**old:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

private:
```

**new:**
```
    // The dictionary source line used to satisfy the no-noise guarantee.
    const char* dictionary_source() const noexcept;
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;
    // TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
    // array into the k=3 heap and verifies it keeps the k LARGEST with
    // (value desc, index asc) tie-break and root=WORST. Trace to stdout.
    bool heap_self_test();

private:
```

### edit 8

**old:**
```
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

    // TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
    // array into the k=3 heap, prints heap state after every push, and verifies
    // the heap keeps the k LARGEST with (value desc, index asc) tie-break and
    // root=WORST. Returns true when both the distinct-value and tie-break cases
    // hold (the trace is printed to stdout).
    bool heap_self_test();

private:
```

**new:**
```
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

private:
```

### edit 9

**old:**
```
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;
    // TopKHeap self-test (Task 4 hardening): pushes a hand-checkable 10-element
    // array into the k=3 heap and verifies it keeps the k LARGEST with
    // (value desc, index asc) tie-break and root=WORST. Trace to stdout.
    bool heap_self_test();

private:
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
```

**new:**
```
    // Human-readable SIMD backend actually in use (intrinsics or std::simd).
    static const char* simd_backend_name() noexcept;

private:
    void fail_closed_check() const;
    void require_latent(std::span<const float> x) const;
```

### edit 10

**old:**
```
    void* mmap_view_ = nullptr;
    std::uint64_t mmap_size_ = 0;
    bool int8_mmap_ = false;
};

}  // namespace SAE
}  // namespace Athenea
```

**new:**
```
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
```

## `codex\src\codex\unified_latent_engine.hpp`

### edit 1

**old:**
```
    struct Config {
        std::string model_path;
        int n_ctx = 4096;
        int n_threads = 4;
        bool use_mmap = true;
    };

    explicit UnifiedLatentEngine(const Config& config) {
        llama_backend_init();
        
        llama_model_params model_params = llama_model_default_params();
        model_params.use_mmap = config.use_mmap;
```

**new:**
```
    struct Config {
        std::string model_path;
        int n_ctx = 4096;
        int n_threads = 4;
        bool use_mmap = true;
        // Layers to offload to VRAM. 0 = CPU-only (backward compatible default);
        // >0 = up to that many layers offloaded; <0 = offload all layers.
        int n_gpu_layers = 0;
    };

    explicit UnifiedLatentEngine(const Config& config) {
        llama_backend_init();
        
        llama_model_params model_params = llama_model_default_params();
        model_params.use_mmap = config.use_mmap;
        model_params.n_gpu_layers = config.n_gpu_layers;
```

### edit 2

**old:**
```
        bool use_mmap = true;
        // Layers to offload to VRAM. 0 = CPU-only (backward compatible default);
        // >0 = up to that many layers offloaded; <0 = offload all layers.
        int n_gpu_layers = 0;
```

**new:**
```
        bool use_mmap = true;
        int n_gpu_layers = 0; // 0 = CPU-only; >0 = offload up to N layers; <0 = all layers

```

## `codex\src\test_sae_propup.cpp`

### write 1 (20081 bytes)

### edit 2

**old:**
```
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
//
// Usage: sae_propup <scenario> <evidence_file> [dict_size] [dict_file]

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "codex/sae_projection.hpp"
```

**new:**
```
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
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "codex/sae_projection.hpp"
#include "verify/kat_anchors.hpp"
```

### edit 3

**old:**
```
int usage() {
    std::cerr << "Usage: sae_propup <simd-match|topk|int8|mmap|bench|nodict> <evidence_file> "
                  "[dict_size] [dict_file]\n";
    return 2;
}
```

**new:**
```
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
    log.info("expected_8d_gestalt=" + gestalt_str(expected));
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
    std::cerr << "Usage: sae_propup <simd-match|topk|int8|mmap|bench|nodict|kat> <evidence_file> "
                  "[dict_size] [dict_file]\n";
    return 2;
}
```

### edit 4

**old:**
```
    const auto g_scalar = proj.gestalt_from_dense(proj.project_dense_scalar(x));
    const auto g_simd = proj.gestalt_from_dense(proj.project_dense_float(x));

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
    log.info("expected_8d_gestalt=" + gestalt_str(expected));
```

**new:**
```
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
```

### edit 5

**old:**
```
        } else if (mode == "nodict") {
            rc = scenario_nodict(log, dict, lat, dict_file);
        } else {
```

**new:**
```
        } else if (mode == "nodict") {
            rc = scenario_nodict(log, dict, lat, dict_file);
        } else if (mode == "kat") {
            rc = scenario_kat(log, dict, lat);
        } else {
```

### edit 6

**old:**
```
const char* dim_name(int r) {
    static const char* names[8] = {"topology", "probability", "ontology", "teleology",
                                   "graph", "dataset", "dimensionality", "human_anomaly"};
    return names[r];
}
#if 0
#endif

```

**new:**
```
const char* dim_name(int r) {
    static const char* names[8] = {"topology", "probability", "ontology", "teleology",
                                   "graph", "dataset", "dimensionality", "human_anomaly"};
    return names[r];
}

```

### edit 7

**old:**
```
std::string gestalt_str(const Athenea::SAE::Gestalt8& g) {
    char buf[512];
    std::snprintf(buf, sizeof(buf),
                  "%.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f", g.topology, g.probability,
                  g.ontology, g.teleology, g.graph, g.dataset, g.dimensionality,
                  g.human_anomaly);
    return buf;
}

const char* dim_name(int r) {
    static const char* names[8] = {"topology", "probability", "ontology", "teleology",
                                   "graph", "dataset", "dimensionality", "human_anomaly"};
    return names[r];
}

// ── Scenario: simd-match ─────────────────────────────────────────────────────
```

**new:**
```
std::string gestalt_str(const Athenea::SAE::Gestalt8& g) {
    char buf[512];
    std::snprintf(buf, sizeof(buf),
                  "%.6f %.6f %.6f %.6f %.6f %.6f %.6f %.6f", g.topology, g.probability,
                  g.ontology, g.teleology, g.graph, g.dataset, g.dimensionality,
                  g.human_anomaly);
    return buf;
}

// ── Scenario: simd-match ─────────────────────────────────────────────────────
```

### edit 8

**old:**
```
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#include "codex/sae_projection.hpp"
#include "verify/kat_anchors.hpp"

namespace {

class PropupLog {
public:
    explicit PropupLog(const std::string& path) {
        if (!path.empty()) file_.open(path, std::ios::app);
    }
    void info(const std::string& msg) { write("[*] " + msg); }
    void pass(const std::string& stage) { write("PASS: " + stage); }
    void fail(const std::string& name) {
        const std::string line = "[PROPUP FAIL] " + name + " DID NOT execute correctly.";
        std::cerr << line << '\n' << std::flush;
        if (file_.is_open()) file_ << line << '\n' << std::flush;
    }

private:
    void write(const std::string& line) {
        std::cout << line << '\n' << std::flush;
        if (file_.is_open()) file_ << line << '\n' << std::flush;
    }
    std::ofstream file_;
};
```

**new:**
```
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
```

### edit 9

**old:**
```
int usage() {
    std::cerr << "Usage: sae_propup <simd-match|topk|int8|mmap|bench|nodict|kat> <evidence_file> "
                  "[dict_size] [dict_file]\n";
    return 2;
}
```

**new:**
```
int usage() {
    std::fprintf(stderr, "Usage: sae_propup <simd-match|topk|int8|mmap|bench|nodict|kat> <evidence_file> "
                         "[dict_size] [dict_file]\n");
    return 2;
}
```

### edit 10

**old:**
```
    } catch (const std::exception& e) {
        std::cerr << "[-] fatal: " << e.what() << '\n' << std::flush;
        rc = 1;
    }
```

**new:**
```
    } catch (const std::exception& e) {
        std::fprintf(stderr, "[-] fatal: %s\n", e.what());
        std::fflush(stderr);
        rc = 1;
    }
```

### edit 11

**old:**
```
    log.info("vectors=16");
    const bool ok = all_ok;
```

**new:**
```
    log.info("vectors=16");
    const bool heap_ok = Athenea::SAE::heap_self_test();
    log.info("heap_self_test_10_elements_k3=" + std::string(heap_ok ? "PASS" : "FAIL"));
    all_ok = all_ok && heap_ok;
    const bool ok = all_ok;
```

### edit 12

**old:**
```
int scenario_mmap(PropupLog& log, std::size_t dict, std::size_t lat,
                  const std::string& dict_file) {
    Athenea::SAE::SaeProjection proj(dict, lat, 64);
    if (!proj.generate_float_dictionary()) return 1;
    if (!proj.quantize_to_int8()) return 1;
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
    log.info("mmap_size_bytes=" + std::to_string(dict * lat + dict * 9 + 64));
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

    // 8D consistency: mmap int8 vs in-memory float (same deterministic dict).
    float maxrel = 0.0f;
    for (int v = 0; v < 4; ++v) {
        const auto x = make_vector(1300 + static_cast<std::uint32_t>(v), lat);
        const auto gf = proj.gestalt_from_sparse(proj.project_topk_float(x));
        const auto gi8 = proj.gestalt_from_sparse(proj.project_topk_int8(x));
        maxrel = std::max(maxrel, maxrel8(gf, gi8));
    }
    log.info("mmap_int8_vs_float_topk8d_max_rel_diff=" + std::to_string(maxrel));
    const bool ok = maxrel < 1e-2f;
    if (ok) {
        log.pass("mmap_dict_projects_correctly_within_1e-2");
    } else {
        log.info("FAILED: mmap int8 projection exceeds 1e-2");
    }
    return ok ? 0 : 1;
}
```

**new:**
```
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
```

### edit 13

**old:**
```
    log.info("vectors=16");
    const bool heap_ok = Athenea::SAE::heap_self_test();
```

**new:**
```
    log.info("vectors=16");
    const bool heap_ok = proj.heap_self_test();
```

### edit 14

**old:**
```
    log.info("vectors=16");
    const bool heap_ok = proj.heap_self_test();
```

**new:**
```
    log.info("vectors=16");
    const bool heap_ok = Athenea::SAE::heap_self_test();
```

## `sovereign_conscience\src\lingua_agi\lingua_vectorizer.py`

### edit 1

**old:**
```
import os
import json
import tempfile
import subprocess
import numpy as np
import hashlib
import struct

class LinguaVectorizer:
    """
    Transforms text into 8-dimensional geometric Lingua vectors
    by calling the C++ codex_engine natively.
    """
    def __init__(self, exe_path=None, model_path=None):
        self.exe_path = exe_path or r"C:\McMaker Projects\Projects\CODEX\build\codex_engine.exe"
        self.model_path = model_path or r"C:\McMaker Projects\Projects\CODEX\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        
        # Check if the fallback model path is needed
        if not os.path.exists(self.model_path):
            alt_path = r"C:\McMaker Projects\Projects\PsiForceDB - The Living Book\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
            if os.path.exists(alt_path):
                self.model_path = alt_path
            else:
                self.model_path = r"C:\McMaker Projects\Projects\CODEX\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
```

**new:**
```
import os
import json
import tempfile
import subprocess
import numpy as np
import hashlib
import struct

# The ONLY model this pipeline may use: Athenea (Qwen3 4B, embedding dim 2560).
DEFAULT_MODEL_PATH = r"C:\McMaker Projects\Projects\Athenea\GGUF\athenea-4b-coding-Q5_K_M.gguf"
EXPECTED_EMBEDDING_LENGTH = 2560
FAIL_CLOSED_MESSAGE = "[FAIL-CLOSED] Model embd != 2560 — refusing to proceed"


def _read_gguf_string(f):
    """Read a GGUF length-prefixed string (u64 length + UTF-8 bytes)."""
    length = struct.unpack('<Q', f.read(8))[0]
    return f.read(length).decode('utf-8', 'replace')


def _skip_gguf_value(f, value_type):
    """Skip a GGUF metadata value of the given type (GGUFValueType enum)."""
    if value_type == 8:          # string
        _read_gguf_string(f)
    elif value_type == 9:        # array
        elem_type = struct.unpack('<I', f.read(4))[0]
        count = struct.unpack('<Q', f.read(8))[0]
        for _ in range(count):
            _skip_gguf_value(f, elem_type)
    elif value_type in (0, 1, 7):      # u8 / i8 / bool
        f.read(1)
    elif value_type in (2, 3):         # u16 / i16
        f.read(2)
    elif value_type in (4, 5, 6):      # u32 / i32 / f32
        f.read(4)
    elif value_type in (10, 11, 12):   # u64 / i64 / f64
        f.read(8)
    else:
        raise struct.error("Unknown GGUF value type: %d" % value_type)


def _gguf_embedding_length(model_path):
    """
    Parse the GGUF header and return the model's embedding dimension
    (first '*embedding_length' metadata key), or None if undeterminable.
    """
    try:
        with open(model_path, 'rb') as f:
            if f.read(4) != b'GGUF':
                return None
            struct.unpack('<I', f.read(4))      # version
            struct.unpack('<Q', f.read(8))      # tensor_count
            kv_count = struct.unpack('<Q', f.read(8))[0]
            for _ in range(kv_count):
                key = _read_gguf_string(f)
                value_type = struct.unpack('<I', f.read(4))[0]
                if key.endswith('embedding_length') and value_type in (4, 5):
                    raw = f.read(4)
                    if len(raw) != 4:
                        return None
                    return int(struct.unpack('<I' if value_type == 4 else '<i', raw)[0])
                _skip_gguf_value(f, value_type)
            return None
    except (OSError, struct.error):
        return None


class LinguaVectorizer:
    """
    Transforms text into 8-dimensional geometric Lingua vectors
    by calling the C++ codex_engine natively.

    Dimension gate: the engine model MUST be the Athenea GGUF (Qwen3 4B,
    embedding dim 2560). Any other model — or a missing one — is refused
    (fail-closed). No synthetic/HashingVectorizer fallback exists.
    """
    def __init__(self, exe_path=None, model_path=None):
        self.exe_path = exe_path or r"C:\McMaker Projects\Projects\CODEX\build\codex_engine.exe"
        self.model_path = model_path or DEFAULT_MODEL_PATH

    def _verify_model(self):
        """Fail-closed model gate: file exists AND embedding dim == 2560."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                "[FAIL-CLOSED] Model not found at %s" % self.model_path
            )
        embd = _gguf_embedding_length(self.model_path)
        if embd is None or embd != EXPECTED_EMBEDDING_LENGTH:
            print(FAIL_CLOSED_MESSAGE)
            raise SystemExit(1)
```

### edit 2

**old:**
```
        if not X:
            return np.zeros((0, 8))
            
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as prompt_file:
```

**new:**
```
        if not X:
            return np.zeros((0, 8))

        self._verify_model()  # dimension gate — fails closed on missing/wrong model

        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as prompt_file:
```

### edit 3

**old:**
```
            cmd = [
                self.exe_path,
                "--model", self.model_path,
                "--prompt-file", prompt_file_name,
                "--out-lingua-batch", out_json_name
            ]
            
            if not os.path.exists(self.model_path):
                print(f"[LinguaVectorizer] Warning: Model {self.model_path} not found. Using synthetic geometry fallback for EBB pipeline test.")
                # Deterministic synthetic mock using HashingVectorizer to simulate Lingua geometry
                from sklearn.feature_extraction.text import HashingVectorizer
                hasher = HashingVectorizer(n_features=8, norm='l2', alternate_sign=False)
                vectors = hasher.fit_transform(X).toarray()
                # Scale up to look like typical Lingua values
                return (vectors * 10.0).astype(np.float32)

            print(f"[LinguaVectorizer] Extracting geometry for {len(X)} texts...")
```

**new:**
```
            cmd = [
                self.exe_path,
                "--model", self.model_path,
                "--prompt-file", prompt_file_name,
                "--out-lingua-batch", out_json_name
            ]

            print(f"[LinguaVectorizer] Extracting geometry for {len(X)} texts...")
```

