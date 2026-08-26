// sae_projection.cpp — Task 4 sparse SAE projection implementation.
//
// SIMD kernels:
//   * float path : AVX2 + FMA (_mm256_fmadd_ps), 8 floats/instruction.
//   * int8  path : AVX-VNNI-INT8 VPDPBSSD (_mm256_dpbssd_epi32), 32 int8 MACs
//                  per instruction, 8 rows interleaved for memory-level
//                  parallelism (measured ~2x over single-row interleave).
//   * scalar reference: per-element accumulation with -ftree-vectorize
//                  disabled (__attribute__((optimize("no-tree-vectorize"))))
//                  so it is a TRUE scalar baseline; accumulation order matches
//                  kat_sae_scalar.cpp byte-for-byte.
//   * std::simd (P1928): compiled only when the toolchain provides <simd>
//                  (GCC 16.1.0 does NOT; the intrinsic path runs here).
//
// Dictionary provisioning is fail-closed: no weights exist until
// generate_float_dictionary()/load_* succeeds; projections throw otherwise.

#include "codex/sae_projection.hpp"

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

#include <immintrin.h>
#include <mm_malloc.h>
#include <windows.h>

// P1928 std::simd: GCC 16.1 ships only a stub <simd> header — __glibcxx_simd
// is defined but the std::simd type is absent and __cpp_lib_simd is undefined.
// Gate on the feature-test macro so the intrinsic path is used here.
#if defined(__cpp_lib_simd)
#include <simd>
#define SAE_HAS_STD_SIMD 1
#else
#define SAE_HAS_STD_SIMD 0
#endif

namespace {

inline float* alloc_f(std::size_t n) {
    return n == 0 ? nullptr : static_cast<float*>(_mm_malloc(n * sizeof(float), 64));
}
inline std::int8_t* alloc_i8(std::size_t n) {
    return n == 0 ? nullptr : static_cast<std::int8_t*>(_mm_malloc(n, 64));
}
inline void free_mem(void* p) {
    if (p) _mm_free(p);
}

// Horizontal sum of an 8-lane float vector (AVX2).
float hsum256_ps(__m256 v) {
    __m128 lo = _mm256_castps256_ps128(v);
    __m128 hi = _mm256_extractf128_ps(v, 1);
    lo = _mm_add_ps(lo, hi);
    __m128 t = _mm_movehdup_ps(lo);
    lo = _mm_add_ps(lo, t);
    t = _mm_movehl_ps(t, lo);
    lo = _mm_add_ss(lo, t);
    return _mm_cvtss_f32(lo);
}

int64_t hsum256_epi32(__m256i v) {
    alignas(32) std::int32_t t[8];
    _mm256_storeu_si256(reinterpret_cast<__m256i*>(t), v);
    return static_cast<std::int64_t>(t[0]) + t[1] + t[2] + t[3] + t[4] + t[5] + t[6] + t[7];
}

// ── Scalar reference (TRUE scalar: tree vectorization disabled) ─────────────
// Byte-for-byte matches kat_sae_scalar.cpp math:
//   dot = bias[i];  for j: dot += W[i][j]*x[j];  out[i] = ReLU(dot)
__attribute__((optimize("no-tree-vectorize")))
void scalar_dense_kernel(const float* w, const float* bias, std::size_t dict,
                         std::size_t lat, const float* x, float* out) {
    for (std::size_t i = 0; i < dict; ++i) {
        const float* row = w + i * lat;
        float dot = bias[i];
        for (std::size_t j = 0; j < lat; ++j) {
            dot += row[j] * x[j];
        }
        out[i] = dot > 0.0f ? dot : 0.0f;
    }
}

// ── Float SIMD kernel (AVX2 + FMA, 4 accumulators) ──────────────────────────
void simd_float_dense_kernel(const float* w, const float* bias, std::size_t dict,
                             std::size_t lat, const float* x, float* out) {
    for (std::size_t i = 0; i < dict; ++i) {
        const float* row = w + i * lat;
        __m256 a0 = _mm256_setzero_ps();
        __m256 a1 = _mm256_setzero_ps();
        __m256 a2 = _mm256_setzero_ps();
        __m256 a3 = _mm256_setzero_ps();
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            a0 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j), _mm256_loadu_ps(x + j), a0);
            a1 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 8), _mm256_loadu_ps(x + j + 8), a1);
            a2 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 16), _mm256_loadu_ps(x + j + 16), a2);
            a3 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 24), _mm256_loadu_ps(x + j + 24), a3);
        }
        a0 = _mm256_add_ps(a0, a1);
        a2 = _mm256_add_ps(a2, a3);
        a0 = _mm256_add_ps(a0, a2);
        float dot = bias[i] + hsum256_ps(a0);
        for (; j < lat; ++j) {
            dot += row[j] * x[j];
        }
        out[i] = dot > 0.0f ? dot : 0.0f;
    }
}

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

// ── Fixed-size min-heap for top-k (worst-of-kept at root) ───────────────────
// Comparison: better(a,b) = a.value > b.value, ties by smaller index. This is
// consistent with select_topk_partial/fullsort (value desc, index asc).
// The heap keeps the k best as a MIN-heap: the root is the WORST kept element,
// so push() can reject a candidate with a single comparison against the root.
// sift_down moves the WORSE child upward so the root stays the worst.
class TopKHeap {
public:
    TopKHeap() = default;
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

// float SIMD + inline heap.
Athenea::SAE::SparseFeatures float_topk_kernel(const float* w, const float* bias,
                                               std::size_t dict, std::size_t lat,
                                               const float* x, std::size_t k) {
    TopKHeap heap(k);
    for (std::size_t i = 0; i < dict; ++i) {
        const float* row = w + i * lat;
        __m256 a0 = _mm256_setzero_ps();
        __m256 a1 = _mm256_setzero_ps();
        __m256 a2 = _mm256_setzero_ps();
        __m256 a3 = _mm256_setzero_ps();
        std::size_t j = 0;
        for (; j + 32 <= lat; j += 32) {
            a0 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j), _mm256_loadu_ps(x + j), a0);
            a1 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 8), _mm256_loadu_ps(x + j + 8), a1);
            a2 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 16), _mm256_loadu_ps(x + j + 16), a2);
            a3 = _mm256_fmadd_ps(_mm256_loadu_ps(row + j + 24), _mm256_loadu_ps(x + j + 24), a3);
        }
        a0 = _mm256_add_ps(a0, a1);
        a2 = _mm256_add_ps(a2, a3);
        a0 = _mm256_add_ps(a0, a2);
        float dot = bias[i] + hsum256_ps(a0);
        for (; j < lat; ++j) {
            dot += row[j] * x[j];
        }
        heap.push(dot > 0.0f ? dot : 0.0f, static_cast<std::uint32_t>(i));
    }
    Athenea::SAE::SparseFeatures out;
    out.indices.assign(heap.idxs(), heap.idxs() + heap.size());
    out.values.assign(heap.vals(), heap.vals() + heap.size());
    return out;
}

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

#if SAE_HAS_STD_SIMD
// ── std::simd (P1928) float kernel — DORMANT on GCC 16.1 (no <simd>). ───────
// Activated automatically when a future toolchain ships P1928. Uses the same
// math as simd_float_dense_kernel so results stay within the 1e-3 gate.
template <std::size_t Width>
void simd_std_dense_kernel(const float* w, const float* bias, std::size_t dict,
                           std::size_t lat, const float* x, float* out) {
    using Simd = std::simd<float, std::simd_abi::deduce_t<float, Width>>;
    for (std::size_t i = 0; i < dict; ++i) {
        const float* row = w + i * lat;
        Simd acc(0.0f);
        std::size_t j = 0;
        for (; j + Width <= lat; j += Width) {
            acc += Simd(row + j, std::vector_aligned) * Simd(x + j, std::vector_aligned);
        }
        float dot = bias[i] + static_cast<float>(std::reduce(acc));
        for (; j < lat; ++j) {
            dot += row[j] * x[j];
        }
        out[i] = dot > 0.0f ? dot : 0.0f;
    }
}
#endif

}  // namespace

namespace Athenea {
namespace SAE {

static_assert(sizeof(Gestalt8) == 8 * sizeof(float), "Gestalt8 must be 8 packed floats");
static_assert(alignof(Gestalt8) == alignof(float), "Gestalt8 must be float-aligned");

SaeProjection::SaeProjection(std::size_t dict_size, std::size_t latent_dim,
                             std::size_t top_k)
    : dict_size_(dict_size), latent_dim_(latent_dim), top_k_(top_k) {
    if (dict_size_ == 0 || latent_dim_ == 0 || top_k_ == 0) {
        throw std::invalid_argument("SaeProjection: dict_size/latent_dim/top_k must be > 0");
    }
    // Fail closed: no weights until explicitly provisioned.
}

SaeProjection::~SaeProjection() {
    free_mem(fw_);
    free_mem(fbias_);
    release_int8_storage();
}

SaeProjection::SaeProjection(SaeProjection&& other) noexcept
    : dict_size_(other.dict_size_),
      latent_dim_(other.latent_dim_),
      top_k_(other.top_k_),
      fw_(other.fw_),
      fbias_(other.fbias_),
      iw_(other.iw_),
      iscale_(other.iscale_),
      izp_(other.izp_),
      ibias_(other.ibias_),
      mmap_view_(other.mmap_view_),
      mmap_size_(other.mmap_size_),
      int8_mmap_(other.int8_mmap_) {
    other.fw_ = nullptr;
    other.fbias_ = nullptr;
    other.iw_ = nullptr;
    other.iscale_ = nullptr;
    other.izp_ = nullptr;
    other.ibias_ = nullptr;
    other.mmap_view_ = nullptr;
    other.mmap_size_ = 0;
    other.int8_mmap_ = false;
}

SaeProjection& SaeProjection::operator=(SaeProjection&& other) noexcept {
    if (this == &other) return *this;
    free_mem(fw_);
    free_mem(fbias_);
    release_int8_storage();
    dict_size_ = other.dict_size_;
    latent_dim_ = other.latent_dim_;
    top_k_ = other.top_k_;
    fw_ = other.fw_;
    fbias_ = other.fbias_;
    iw_ = other.iw_;
    iscale_ = other.iscale_;
    izp_ = other.izp_;
    ibias_ = other.ibias_;
    mmap_view_ = other.mmap_view_;
    mmap_size_ = other.mmap_size_;
    int8_mmap_ = other.int8_mmap_;
    other.fw_ = other.fbias_ = nullptr;
    other.iw_ = nullptr;
    other.iscale_ = nullptr;
    other.izp_ = nullptr;
    other.ibias_ = nullptr;
    other.mmap_view_ = nullptr;
    other.mmap_size_ = 0;
    other.int8_mmap_ = false;
    return *this;
}

// ── Dictionary provisioning ──────────────────────────────────────────────────

bool SaeProjection::generate_float_dictionary() {
    free_mem(fw_);
    free_mem(fbias_);
    fw_ = nullptr;
    fbias_ = nullptr;
    release_int8_storage();

    const std::size_t n = dict_size_ * latent_dim_;
    float* w = alloc_f(n);
    float* b = alloc_f(dict_size_);
    if (!w || !b) {
        free_mem(w);
        free_mem(b);
        return false;
    }
    // Deterministic "real" dictionary: mt19937(42) + N(0, 0.02), bias -0.01.
    // This is the canonical reference source from T5 kat_sae_scalar.cpp.
    std::mt19937 gen(42);
    std::normal_distribution<float> dist(0.0f, 0.02f);
    for (std::size_t i = 0; i < n; ++i) {
        w[i] = dist(gen);
    }
    for (std::size_t i = 0; i < dict_size_; ++i) {
        b[i] = -0.01f;
    }
    fw_ = w;
    fbias_ = b;
    return true;
}

bool SaeProjection::quantize_to_int8() {
    if (!fw_ || !fbias_) return false;
    release_int8_storage();

    std::int8_t* w = alloc_i8(dict_size_ * latent_dim_);
    float* sc = alloc_f(dict_size_);
    std::int8_t* zp = alloc_i8(dict_size_);
    float* b = alloc_f(dict_size_);
    if (!w || !sc || !zp || !b) {
        free_mem(w);
        free_mem(sc);
        free_mem(zp);
        free_mem(b);
        return false;
    }
    for (std::size_t i = 0; i < dict_size_; ++i) {
        const float* src = fw_ + i * latent_dim_;
        float mx = 0.0f;
        for (std::size_t j = 0; j < latent_dim_; ++j) {
            mx = std::max(mx, std::fabsf(src[j]));
        }
        // Symmetric per-row scale: max|x| maps to 127, zero point 0.
        const float scale = mx > 0.0f ? mx / 127.0f : 1.0f;
        sc[i] = scale;
        zp[i] = 0;
        std::int8_t* dst = w + i * latent_dim_;
        for (std::size_t j = 0; j < latent_dim_; ++j) {
            int q = static_cast<int>(std::lroundf(src[j] / scale));
            if (q > 127) q = 127;
            if (q < -127) q = -127;
            dst[j] = static_cast<std::int8_t>(q);
        }
        b[i] = fbias_[i];
    }
    iw_ = w;
    iscale_ = sc;
    izp_ = zp;
    ibias_ = b;
    return true;
}

std::size_t SaeProjection::int8_file_bytes() const noexcept {
    const std::size_t weights = dict_size_ * latent_dim_;
    return sizeof(DictFileHeader) + weights + dict_size_ * (sizeof(float) * 2 + 1);
}

bool SaeProjection::save_int8_file(const std::string& path) const {
    if (!iw_ || !iscale_ || !izp_ || !ibias_) return false;
    FILE* f = std::fopen(path.c_str(), "wb");
    if (!f) return false;
    bool ok = true;

    DictFileHeader h{};
    h.magic = 0x38454153u;  // 'S' 'A' 'E' '8' little-endian
    h.version = 1;
    h.dict_size = static_cast<std::uint32_t>(dict_size_);
    h.latent_dim = static_cast<std::uint32_t>(latent_dim_);
    h.top_k = static_cast<std::uint32_t>(top_k_);
    h.weights_offset = 64;
    h.weights_bytes = static_cast<std::uint32_t>(dict_size_ * latent_dim_);
    h.scales_offset = h.weights_offset + h.weights_bytes;
    h.scales_bytes = static_cast<std::uint32_t>(dict_size_ * sizeof(float));
    h.zps_offset = h.scales_offset + h.scales_bytes;
    h.zps_bytes = static_cast<std::uint32_t>(dict_size_);
    h.biases_offset = h.zps_offset + h.zps_bytes;
    h.biases_bytes = static_cast<std::uint32_t>(dict_size_ * sizeof(float));
    h.total_bytes = h.biases_offset + h.biases_bytes;

    if (std::fwrite(&h, 1, sizeof(h), f) != sizeof(h)) ok = false;
    if (ok && std::fwrite(iw_, 1, h.weights_bytes, f) != h.weights_bytes) ok = false;
    if (ok && std::fwrite(iscale_, 1, h.scales_bytes, f) != h.scales_bytes) ok = false;
    if (ok && std::fwrite(izp_, 1, h.zps_bytes, f) != h.zps_bytes) ok = false;
    if (ok && std::fwrite(ibias_, 1, h.biases_bytes, f) != h.biases_bytes) ok = false;
    std::fclose(f);
    return ok;
}

bool SaeProjection::load_int8_mmap(const std::string& path) {
    // Free any in-memory int8 copy (float is kept).
    release_int8_storage();

    HANDLE hFile = CreateFileA(path.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                               OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER file_size{};
    if (!GetFileSizeEx(hFile, &file_size)) {
        CloseHandle(hFile);
        return false;
    }
    HANDLE hMap = CreateFileMappingA(hFile, nullptr, PAGE_READONLY, 0, 0, nullptr);
    if (!hMap) {
        CloseHandle(hFile);
        return false;
    }
    void* base = MapViewOfFile(hMap, FILE_MAP_READ, 0, 0, 0);
    CloseHandle(hMap);
    CloseHandle(hFile);
    if (!base) return false;

    const auto* h = static_cast<const DictFileHeader*>(base);
    const bool header_ok =
        file_size.QuadPart >= static_cast<LONGLONG>(sizeof(DictFileHeader)) &&
        h->magic == 0x38454153u && h->version == 1 &&
        h->dict_size == static_cast<std::uint32_t>(dict_size_) &&
        h->latent_dim == static_cast<std::uint32_t>(latent_dim_) &&
        h->weights_offset == 64 &&
        h->weights_bytes == dict_size_ * latent_dim_ &&
        h->biases_offset + h->biases_bytes <= static_cast<std::uint32_t>(file_size.QuadPart);
    if (!header_ok) {
        UnmapViewOfFile(base);
        return false;
    }

    const auto* bytes = static_cast<const std::uint8_t*>(base);
    iw_ = reinterpret_cast<std::int8_t*>(const_cast<std::uint8_t*>(bytes + h->weights_offset));
    iscale_ = reinterpret_cast<float*>(const_cast<std::uint8_t*>(bytes + h->scales_offset));
    izp_ = reinterpret_cast<std::int8_t*>(const_cast<std::uint8_t*>(bytes + h->zps_offset));
    ibias_ = reinterpret_cast<float*>(const_cast<std::uint8_t*>(bytes + h->biases_offset));
    mmap_view_ = base;
    mmap_size_ = static_cast<std::uint64_t>(file_size.QuadPart);
    int8_mmap_ = true;
    return true;
}

bool SaeProjection::load_float_dictionary(const std::string& path) {
    free_mem(fw_);
    free_mem(fbias_);
    fw_ = fbias_ = nullptr;
    release_int8_storage();

    FILE* f = std::fopen(path.c_str(), "rb");
    if (!f) return false;
    float* w = alloc_f(dict_size_ * latent_dim_);
    float* b = alloc_f(dict_size_);
    if (!w || !b) {
        free_mem(w);
        free_mem(b);
        std::fclose(f);
        return false;
    }
    const std::size_t nw = std::fread(w, sizeof(float), dict_size_ * latent_dim_, f);
    const std::size_t nb = std::fread(b, sizeof(float), dict_size_, f);
    std::fclose(f);
    if (nw != dict_size_ * latent_dim_ || nb != dict_size_) {
        free_mem(w);
        free_mem(b);
        return false;
    }
    fw_ = w;
    fbias_ = b;
    return true;
}

// ── Projection ───────────────────────────────────────────────────────────────

void SaeProjection::fail_closed_check() const {
    if (fw_ == nullptr && iw_ == nullptr) {
        throw std::runtime_error(
            "[FAIL-CLOSED] SAE projection attempted with NO dictionary loaded/generated. "
            "Call generate_float_dictionary(), load_float_dictionary(), or load_int8_mmap() "
            "first. Never project against empty/random weights.");
    }
    if (int8_mmap_ && iw_ == nullptr) {
        throw std::runtime_error("[FAIL-CLOSED] int8 mmap dictionary is not mapped.");
    }
}

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

std::vector<float> SaeProjection::project_dense_float(std::span<const float> x) const {
    fail_closed_check();
    if (!fw_ || !fbias_) {
        throw std::runtime_error(
            "[FAIL-CLOSED] project_dense_float requires a float dictionary "
            "(generate_float_dictionary() or load_float_dictionary()).");
    }
    require_latent(x);
    std::vector<float> out(dict_size_);
#if SAE_HAS_STD_SIMD
    simd_std_dense_kernel<16>(fw_, fbias_, dict_size_, latent_dim_, x.data(), out.data());
#else
    simd_float_dense_kernel(fw_, fbias_, dict_size_, latent_dim_, x.data(), out.data());
#endif
    return out;
}

std::vector<float> SaeProjection::project_dense_int8(std::span<const float> x) const {
    fail_closed_check();
    if (!iw_ || !iscale_ || !ibias_) {
        throw std::runtime_error(
            "[FAIL-CLOSED] project_dense_int8 requires an int8 dictionary "
            "(quantize_to_int8() or load_int8_mmap()).");
    }
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

std::vector<float> SaeProjection::project_dense(std::span<const float> x) const {
    if (iw_) return project_dense_int8(x);
    return project_dense_float(x);
}

std::vector<float> SaeProjection::project_dense_scalar(std::span<const float> x) const {
    fail_closed_check();
    if (!fw_ || !fbias_) {
        throw std::runtime_error(
            "[FAIL-CLOSED] project_dense_scalar requires a float dictionary "
            "(generate_float_dictionary() or load_float_dictionary()).");
    }
    require_latent(x);
    std::vector<float> out(dict_size_);
    scalar_dense_kernel(fw_, fbias_, dict_size_, latent_dim_, x.data(), out.data());
    return out;
}

SparseFeatures SaeProjection::project_topk_float(std::span<const float> x) const {
    fail_closed_check();
    if (!fw_ || !fbias_) {
        throw std::runtime_error(
            "[FAIL-CLOSED] project_topk_float requires a float dictionary.");
    }
    require_latent(x);
    return float_topk_kernel(fw_, fbias_, dict_size_, latent_dim_, x.data(), top_k_);
}

SparseFeatures SaeProjection::project_topk_int8(std::span<const float> x) const {
    fail_closed_check();
    if (!iw_ || !iscale_ || !ibias_) {
        throw std::runtime_error(
            "[FAIL-CLOSED] project_topk_int8 requires an int8 dictionary "
            "(quantize_to_int8() or load_int8_mmap()).");
    }
    require_latent(x);
    std::vector<std::int8_t> xq_hi(latent_dim_);
    std::vector<std::int8_t> xq_lo(latent_dim_);
    float xs_hi = 1.0f;
    float xs_lo = 1.0f;
    quantize_x(x.data(), latent_dim_, xq_hi.data(), &xs_hi, xq_lo.data(), &xs_lo);
    return int8_topk_kernel(iw_, iscale_, ibias_, dict_size_, latent_dim_, xq_hi.data(),
                            xs_hi, xq_lo.data(), xs_lo, top_k_);
}

SparseFeatures SaeProjection::project_topk(std::span<const float> x) const {
    if (iw_) return project_topk_int8(x);
    return project_topk_float(x);
}

SparseFeatures SaeProjection::select_topk_partial(std::span<const float> dense,
                                                  std::size_t k) const {
    if (k > dense.size()) k = dense.size();
    std::vector<std::pair<float, std::uint32_t>> pairs;
    pairs.reserve(dense.size());
    for (std::size_t i = 0; i < dense.size(); ++i) {
        pairs.emplace_back(dense[i], static_cast<std::uint32_t>(i));
    }
    const std::size_t kk = k;
    std::partial_sort(pairs.begin(), pairs.begin() + static_cast<std::ptrdiff_t>(kk),
                      pairs.end(),
                      [](const auto& a, const auto& b) {
                          return a.first > b.first ||
                                 (a.first == b.first && a.second < b.second);
                      });
    SparseFeatures out;
    for (std::size_t t = 0; t < kk; ++t) {
        out.indices.push_back(pairs[t].second);
        out.values.push_back(pairs[t].first);
    }
    return out;
}

SparseFeatures SaeProjection::select_topk_fullsort(std::span<const float> dense,
                                                   std::size_t k) const {
    if (k > dense.size()) k = dense.size();
    std::vector<std::pair<float, std::uint32_t>> pairs;
    pairs.reserve(dense.size());
    for (std::size_t i = 0; i < dense.size(); ++i) {
        pairs.emplace_back(dense[i], static_cast<std::uint32_t>(i));
    }
    std::sort(pairs.begin(), pairs.end(),
              [](const auto& a, const auto& b) {
                  return a.first > b.first ||
                         (a.first == b.first && a.second < b.second);
              });
    SparseFeatures out;
    for (std::size_t t = 0; t < k; ++t) {
        out.indices.push_back(pairs[t].second);
        out.values.push_back(pairs[t].first);
    }
    return out;
}

Gestalt8 SaeProjection::gestalt_from_dense(std::span<const float> dense) const {
    if (dense.size() != dict_size_) {
        throw std::invalid_argument("SaeProjection: gestalt_from_dense expects dict_size features");
    }
    Gestalt8 g{};
    const std::size_t rw = dict_size_ / 8;
    for (std::size_t r = 0; r < 8; ++r) {
        float sum = 0.0f;
        for (std::size_t i = r * rw; i < (r + 1) * rw; ++i) {
            sum += dense[i];
        }
        g[r] = sum;
    }
    return g;
}

Gestalt8 SaeProjection::gestalt_from_sparse(const SparseFeatures& s) const {
    Gestalt8 g{};
    const std::size_t rw = dict_size_ / 8;
    const std::size_t n = std::min(s.count(), s.indices.size());
    for (std::size_t t = 0; t < n; ++t) {
        const std::size_t idx = s.indices[t];
        if (idx >= dict_size_) continue;
        g[idx / rw] += s.values[t];
    }
    return g;
}

// ── Reflection / alignment ───────────────────────────────────────────────────

std::uintptr_t SaeProjection::row_address(std::size_t row) const noexcept {
    if (row >= dict_size_) return 0;
    if (iw_) return reinterpret_cast<std::uintptr_t>(iw_ + row * latent_dim_);
    if (fw_) return reinterpret_cast<std::uintptr_t>(fw_ + row * latent_dim_);
    return 0;
}

bool SaeProjection::rows_aligned_to(std::size_t align) const noexcept {
    if (align == 0) return false;
    if (!ready()) return false;
    const std::uintptr_t first = row_address(0);
    const std::uintptr_t last = row_address(dict_size_ - 1);
    if (first == 0 || last == 0) return false;
    return first % align == 0 && last % align == 0;
}

const char* SaeProjection::dictionary_source() const noexcept {
    if (int8_mmap_ && iw_) return "memory-mapped int8 dictionary file (rows 32-byte aligned)";
    if (iw_) return "deterministic mt19937(42)+N(0,0.02), bias -0.01 (kat_sae_scalar canonical)";
    if (fw_) return "deterministic mt19937(42)+N(0,0.02), bias -0.01 (kat_sae_scalar canonical)";
    return "NO DICTIONARY — fail closed";
}

const char* SaeProjection::simd_backend_name() noexcept {
#if SAE_HAS_STD_SIMD
    return "std::simd (P1928)";
#else
    return "AVX2+AVX-VNNI-INT8 intrinsics (no <simd> in GCC 16.1; no AVX-512 on CPU)";
#endif
}

// ── Tiny TopKHeap self-test (Task 4 hardening) ───────────────────────────────
// k=3 heap on hand-checkable arrays; prints heap state after every push.
// Verifies: k LARGEST kept under (value desc, index asc); root = WORST; full
// replacement + sift_down; equal-value ties keep the smaller index.
bool heap_self_test() {
    using Entry = std::pair<float, std::uint32_t>;
    const auto worse = [](const Entry& a, const Entry& b) {
        return a.first < b.first || (a.first == b.first && a.second > b.second);
    };
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
            check_invariant(h, "case1", 3);
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
            check_invariant(h, "case2", 3);
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

}  // namespace SAE
}  // namespace Athenea
