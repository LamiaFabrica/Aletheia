#include "codex/extraction_module.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <psapi.h>
#endif

namespace Athenea {
namespace Extraction {

namespace {

bool is_blank(const std::string& s) {
    return std::all_of(s.begin(), s.end(), [](unsigned char c) { return std::isspace(c) != 0; });
}

double now_ms() {
    const auto t = std::chrono::steady_clock::now().time_since_epoch();
    return std::chrono::duration<double, std::milli>(t).count();
}

double read_rss_gb() {
#ifdef _WIN32
    PROCESS_MEMORY_COUNTERS pmc{};
    if (GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof(pmc)) != 0) {
        return static_cast<double>(pmc.WorkingSetSize) / (1024.0 * 1024.0 * 1024.0);
    }
#endif
    return 0.0;
}

bool read_vram_mib(double& used, double& total) {
#ifdef _WIN32
    FILE* pipe = _popen("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits", "r");
    if (pipe != nullptr) {
        char buf[128] = {};
        std::string line;
        while (fgets(buf, static_cast<int>(sizeof(buf)), pipe) != nullptr) {
            line += buf;
        }
        _pclose(pipe);
        const auto comma = line.find(',');
        if (comma != std::string::npos) {
            used = std::stod(line.substr(0, comma));
            total = std::stod(line.substr(comma + 1));
            return true;
        }
    }
#endif
    return false;
}

} // namespace

ExtractionModule::ExtractionModule(const Config& config) {
    const double load_start = now_ms();

    PsiForceDB::Codex::UnifiedLatentEngine::Config engine_cfg;
    engine_cfg.model_path = config.model_path;
    engine_cfg.n_ctx = config.n_ctx;
    engine_cfg.n_threads = config.n_threads;
    engine_cfg.use_mmap = config.use_mmap;
    engine_cfg.n_gpu_layers = config.n_gpu_layers;

    engine_ = std::make_unique<PsiForceDB::Codex::UnifiedLatentEngine>(engine_cfg);
    metrics_.load_time_ms = now_ms() - load_start;
    metrics_.rss_after_load_gb = read_rss_gb();
    read_vram_mib(metrics_.vram_used_mib, metrics_.vram_total_mib);

    fail_closed_gate();
}

void ExtractionModule::fail_closed_gate() {
    embd_ = static_cast<std::size_t>(engine_->get_n_embd());
    if (embd_ != EXPECTED_EMBD) {
        std::cerr << "[FAIL-CLOSED] Model embd != 2560 — refusing to proceed (got " << embd_ << ")\n";
        throw std::runtime_error("Dimension gate rejected model: expected embd=2560, got " + std::to_string(embd_));
    }
}

std::vector<float> ExtractionModule::extract(const std::string& prompt) {
    // ── Contract pre: non-empty, non-blank prompt (fail-closed) ──
    if (prompt.empty() || is_blank(prompt)) {
        throw std::invalid_argument(
            "extraction_module: [FAIL-CLOSED] contract pre violated: prompt is empty or whitespace-only");
    }

    // Reset context KV memory so each embedding covers ONLY the current prompt.
    llama_memory_clear(llama_get_memory(engine_->get_ctx()), true);

    std::size_t out_dim = 0;
    const float* raw = engine_->execute_and_extract_hidden_state(prompt, out_dim);
    if (raw == nullptr || out_dim != embd_) {
        throw std::runtime_error("extraction_module: hidden-state extraction returned invalid dimension");
    }
    std::vector<float> vec(raw, raw + out_dim);

    // ── Contract post: exactly 2560D, finite values only (fail-closed) ──
    if (vec.size() != EXPECTED_EMBD) {
        throw std::runtime_error(
            "extraction_module: [FAIL-CLOSED] contract post violated: embedding dim is " +
            std::to_string(vec.size()) + ", expected " + std::to_string(EXPECTED_EMBD));
    }
    for (const float v : vec) {
        if (!std::isfinite(v)) {
            throw std::runtime_error(
                "extraction_module: [FAIL-CLOSED] contract post violated: embedding contains NaN/Inf");
        }
    }
    return vec;
}

std::vector<std::vector<float>> ExtractionModule::extract_batch(const std::vector<std::string>& prompts) {
    // ── Contract pre: non-empty batch (fail-closed) ──
    if (prompts.empty()) {
        throw std::invalid_argument(
            "extraction_module: [FAIL-CLOSED] contract pre violated: empty prompt batch");
    }
    std::vector<std::vector<float>> out;
    out.reserve(prompts.size());
    for (const std::string& prompt : prompts) {
        out.push_back(extract(prompt));
    }
    return out;
}

} // namespace Extraction
} // namespace Athenea
