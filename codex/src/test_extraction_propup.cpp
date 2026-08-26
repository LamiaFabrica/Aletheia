#include <algorithm>
#include <chrono>
#include <cstddef>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "codex/extraction_module.hpp"

namespace {

class PropupLog {
public:
    explicit PropupLog(const std::string& path) {
        if (!path.empty()) {
            file_.open(path, std::ios::app);
        }
    }

    void info(const std::string& msg) { write("[*] " + msg); }
    void pass(const std::string& stage) { write("PASS: " + stage); }

    void fail(const std::string& name) {
        std::cerr << "[PROPUP FAIL] " << name << " DID NOT execute correctly.\n" << std::flush;
        if (file_.is_open()) {
            file_ << "[PROPUP FAIL] " << name << " DID NOT execute correctly.\n" << std::flush;
        }
    }

private:
    void write(const std::string& line) {
        std::cout << line << '\n' << std::flush;
        if (file_.is_open()) {
            file_ << line << '\n' << std::flush;
        }
    }

    std::ofstream file_;
};

void print_metrics(PropupLog& log, const Athenea::Extraction::ExtractionModule::Metrics& m) {
    log.info("load_time_ms=" + std::to_string(m.load_time_ms));
    log.info("rss_after_load_gb=" + std::to_string(m.rss_after_load_gb));
    log.info("vram_used_mib=" + std::to_string(m.vram_used_mib));
    log.info("vram_total_mib=" + std::to_string(m.vram_total_mib));
}

double median(std::vector<double> v) {
    std::sort(v.begin(), v.end());
    return v[v.size() / 2];
}

double mean(const std::vector<double>& v) {
    double sum = 0.0;
    for (double x : v) {
        sum += x;
    }
    return sum / static_cast<double>(v.size());
}

int scenario_extraction(PropupLog& log, const std::string& model_path) {
    log.info("mode=extraction");
    Athenea::Extraction::ExtractionModule::Config cfg;
    cfg.model_path = model_path;
    log.info("loading model + dimension gate");
    Athenea::Extraction::ExtractionModule module(cfg);
    log.pass("model_loaded");
    log.info("n_embd=" + std::to_string(module.embedding_dim()));

    if (module.embedding_dim() != Athenea::Extraction::ExtractionModule::EXPECTED_EMBD) {
        return 1;
    }
    log.pass("embd_dim_2560");

    const std::string prompt =
        "Explain how a unified latent engine extracts a 2560-dimensional embedding from a Qwen3 4B model.";

    const std::vector<float> vec = module.extract(prompt);
    if (vec.size() != Athenea::Extraction::ExtractionModule::EXPECTED_EMBD) {
        return 1;
    }
    log.pass("embedding_extracted");
    log.info("embedding[0]=" + std::to_string(vec[0]) + " embedding[2559]=" + std::to_string(vec[2559]));

    std::vector<double> latencies;
    const auto t0 = std::chrono::steady_clock::now();
    for (int i = 0; i < 5; ++i) {
        const auto start = std::chrono::steady_clock::now();
        const std::vector<float> v = module.extract(prompt);
        const auto end = std::chrono::steady_clock::now();
        if (v.size() != Athenea::Extraction::ExtractionModule::EXPECTED_EMBD) {
            return 1;
        }
        latencies.push_back(std::chrono::duration<double, std::milli>(end - start).count());
    }
    const auto t1 = std::chrono::steady_clock::now();
    log.info("batch5_elapsed_ms=" + std::to_string(std::chrono::duration<double, std::milli>(t1 - t0).count()));
    log.info("latency_runs_ms=" + std::to_string(latencies[0]) + "," + std::to_string(latencies[1]) + "," +
             std::to_string(latencies[2]) + "," + std::to_string(latencies[3]) + "," + std::to_string(latencies[4]));
    log.info("latency_mean_ms=" + std::to_string(mean(latencies)));
    log.info("latency_median_ms=" + std::to_string(median(latencies)));
    log.pass("latency_measured");

    print_metrics(log, module.metrics());
    log.pass("metrics_recorded");
    return 0;
}

int scenario_batch(PropupLog& log, const std::string& model_path) {
    log.info("mode=batch");
    Athenea::Extraction::ExtractionModule::Config cfg;
    cfg.model_path = model_path;
    Athenea::Extraction::ExtractionModule module(cfg);
    log.pass("model_loaded");

    const std::vector<std::string> prompts = {
        "Define a lambda that returns the square of an integer in C++.",
        "Explain the difference between stack and heap allocation.",
        "Write a function that reverses a string in place.",
        "Describe cache coherence in multi-core systems.",
        "What is the worst-case time complexity of quicksort?",
        "Explain how virtual memory and page tables work.",
        "Write a recursive Fibonacci function in C++.",
        "Describe the observer design pattern with an example.",
        "Explain the difference between TCP and UDP.",
        "Write a binary search implementation in C++.",
        "Describe how a CPU branch predictor works.",
        "Explain the single responsibility principle.",
        "Write a function that checks whether a string is a palindrome.",
        "Describe the difference between a mutex and a semaphore.",
        "Explain how tracing garbage collection works.",
        "Write a snippet that splits a CSV line into fields.",
    };

    const auto t0 = std::chrono::steady_clock::now();
    const std::vector<std::vector<float>> vecs = module.extract_batch(prompts);
    const auto t1 = std::chrono::steady_clock::now();

    if (vecs.size() != prompts.size()) {
        return 1;
    }
    log.pass("batch_16_prompts");

    bool all_dims_ok = true;
    for (std::size_t i = 0; i < vecs.size(); ++i) {
        if (vecs[i].size() != Athenea::Extraction::ExtractionModule::EXPECTED_EMBD) {
            all_dims_ok = false;
        }
    }
    if (!all_dims_ok) {
        return 1;
    }
    log.pass("batch_dims_2560x16");

    double sq_dist_sum = 0.0;
    std::size_t pair_count = 0;
    for (std::size_t i = 0; i < vecs.size(); ++i) {
        for (std::size_t j = i + 1; j < vecs.size(); ++j) {
            double d2 = 0.0;
            for (std::size_t k = 0; k < Athenea::Extraction::ExtractionModule::EXPECTED_EMBD; ++k) {
                const double diff = static_cast<double>(vecs[i][k]) - static_cast<double>(vecs[j][k]);
                d2 += diff * diff;
            }
            sq_dist_sum += d2;
            ++pair_count;
        }
    }
    const double mean_pairwise_sq_dist = sq_dist_sum / static_cast<double>(pair_count);
    log.info("pairwise_l2_sq_mean=" + std::to_string(mean_pairwise_sq_dist));
    log.info("batch_elapsed_ms=" + std::to_string(std::chrono::duration<double, std::milli>(t1 - t0).count()));

    if (mean_pairwise_sq_dist <= 0.01) {
        return 1;
    }
    log.pass("batch_vectors_differ");

    print_metrics(log, module.metrics());
    log.pass("metrics_recorded");
    return 0;
}

int scenario_empty(PropupLog& log, const std::string& model_path) {
    log.info("mode=empty");
    Athenea::Extraction::ExtractionModule::Config cfg;
    cfg.model_path = model_path;
    Athenea::Extraction::ExtractionModule module(cfg);
    log.pass("model_loaded");

    bool rejected_empty = false;
    try {
        module.extract("");
    } catch (const std::invalid_argument&) {
        rejected_empty = true;
    }
    if (!rejected_empty) {
        log.info("empty prompt did NOT throw std::invalid_argument");
        return 1;
    }
    log.pass("empty_prompt_rejected_cleanly");

    bool rejected_whitespace = false;
    try {
        module.extract("   \t\n  ");
    } catch (const std::invalid_argument&) {
        rejected_whitespace = true;
    }
    if (!rejected_whitespace) {
        log.info("whitespace prompt did NOT throw std::invalid_argument");
        return 1;
    }
    log.pass("whitespace_prompt_rejected_cleanly");

    log.info("no crash, no hang, clean rejection path confirmed");
    return 0;
}

int usage() {
    std::cerr << "Usage: extraction_propup <extraction|batch|empty> <model_path> [evidence_file]\n";
    return 2;
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        return usage();
    }

    const std::string mode = argv[1];
    const std::string model_path = argv[2];
    const std::string evidence_path = (argc >= 4) ? argv[3] : "";

    PropupLog log(evidence_path);
    log.info("=== task-3-" + mode + " start ===");

    int rc = 0;
    try {
        if (mode == "extraction") {
            rc = scenario_extraction(log, model_path);
        } else if (mode == "batch") {
            rc = scenario_batch(log, model_path);
        } else if (mode == "empty") {
            rc = scenario_empty(log, model_path);
        } else {
            return usage();
        }
    } catch (const std::exception& e) {
        std::cerr << "[-] fatal: " << e.what() << '\n' << std::flush;
        rc = 1;
    }

    if (rc == 0) {
        log.info("=== task-3-" + mode + " ok ===");
    } else {
        log.fail(mode);
    }
    return rc;
}
