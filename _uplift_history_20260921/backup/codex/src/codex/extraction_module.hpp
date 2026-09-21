#pragma once

#include <cstddef>
#include <memory>
#include <string>
#include <vector>

#include "codex/unified_latent_engine.hpp"

namespace Athenea {
namespace Extraction {

// Permanent embedding-extraction module backed by Aletheia's UnifiedLatentEngine.
// Loads the Athenea Qwen3 4B GGUF and produces 2560-dim embedding vectors.
// This is the foundation for the T8/T10 consumers; it is NOT throwaway code.
//
// CONTRACTS (Task 12): explicit fail-closed checks (NOT [[pre:]]/[[post:]] —
// GCC 16.1.0 MinGW-W64 UCRT does not parse the C++26 contract attribute
// syntax; see learnings Task 12).
//   * extract() PRE:       prompt is non-empty / non-blank (std::invalid_argument).
//   * extract() POST:      result is exactly 2560D and contains no NaN/Inf.
//   * extract_batch() PRE: prompt vector is non-empty.
//   * ctor POST:           model dim gate == 2560 (fail_closed_gate).
class ExtractionModule {
public:
    static constexpr std::size_t EXPECTED_EMBD = 2560;

    struct Config {
        std::string model_path;
        int n_ctx = 4096;
        int n_threads = 24;
        bool use_mmap = true;
        int n_gpu_layers = 99; // RTX 5070 Ti 12GB — offloads all 36 Qwen3 layers
    };

    struct Metrics {
        double load_time_ms = 0.0;
        double rss_after_load_gb = 0.0;
        double vram_used_mib = 0.0;
        double vram_total_mib = 0.0;
    };

    explicit ExtractionModule(const Config& config);

    // Batch API: one 2560-dim vector per prompt, in input order.
    std::vector<std::vector<float>> extract_batch(const std::vector<std::string>& prompts);

    // Single-prompt convenience. Throws std::invalid_argument on blank prompts.
    std::vector<float> extract(const std::string& prompt);

    std::size_t embedding_dim() const noexcept { return embd_; }
    const Metrics& metrics() const noexcept { return metrics_; }

private:
    void fail_closed_gate();

    std::unique_ptr<PsiForceDB::Codex::UnifiedLatentEngine> engine_;
    std::size_t embd_ = 0;
    Metrics metrics_;
};

} // namespace Extraction
} // namespace Athenea
