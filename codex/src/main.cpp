#include <iostream>
#include <string>
#include <vector>
#include <span>
#include <memory>
#include <iomanip>
#include <stdexcept>

#include "codex/unified_latent_engine.hpp"
#include "codex/latent_decipher.hpp"
#include "codex/codex_error.hpp"

using namespace PsiForceDB::Codex;

// Mock calibration map for demonstration purposes.
// In production, these indices are derived from Sparse Autoencoder feature analysis.
LinguaCalibrationMap create_demo_calibration() {
    LinguaCalibrationMap map;
    map.topology_indices = {10, 42, 1024};
    map.probability_indices = {7, 88, 999};
    map.ontology_indices = {1, 2, 3};
    map.teleology_indices = {400, 500, 600};
    map.graph_indices = {700, 800};
    map.dataset_indices = {900};
    map.dimensionality_indices = {1000};
    map.human_anomaly_indices = {1111, 2222, 3333};
    return map;
}

void print_gestalt(const LinguaDecodedPrimers& gestalt) {
    std::cout << "=========================================\n";
    std::cout << "      LINGUA GESTALT TOPOLOGY (8D)       \n";
    std::cout << "=========================================\n";
    std::cout << std::fixed << std::setprecision(4);
    std::cout << " [1] Topology       (Space/Scale)    : " << gestalt.topology << "\n";
    std::cout << " [2] Probability    (Likelihood)     : " << gestalt.probability << "\n";
    std::cout << " [3] Ontology       (Truth/Fact)     : " << gestalt.ontology << "\n";
    std::cout << " [4] Teleology      (Goal/Intent)    : " << gestalt.teleology << "\n";
    std::cout << " [5] Graph          (Network)        : " << gestalt.graph << "\n";
    std::cout << " [6] Dataset        (Grounding)      : " << gestalt.dataset << "\n";
    std::cout << " [7] Dimensionality (Perspective)    : " << gestalt.dimensionality << "\n";
    std::cout << " [8] Human Anomaly  (Deception)      : " << gestalt.human_anomaly << "\n";
    std::cout << "=========================================\n";
    std::cout << " JSON EXPORT: [" 
              << gestalt.topology << "," << gestalt.probability << "," 
              << gestalt.ontology << "," << gestalt.teleology << ","
              << gestalt.graph << "," << gestalt.dataset << "," 
              << gestalt.dimensionality << "," << gestalt.human_anomaly << "]\n";
}

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0] << " <path_to_gguf_model> \"<prompt>\" [path_to_sae_dict.bin]\n";
        return 1;
    }

    std::string model_path = argv[1];
    std::string prompt = argv[2];
    std::string dict_path = (argc >= 4) ? argv[3] : "";

    try {
        std::cout << "[*] Initializing Unified Latent Engine...\n";
        UnifiedLatentEngine::Config config;
        config.model_path = model_path;
        config.n_ctx = 2048;
        config.n_threads = 8;
        UnifiedLatentEngine engine(config);

        size_t latent_dim = engine.get_n_embd();
        std::cout << "[+] Model Loaded. Latent Dimension: " << latent_dim << "\n";

        // Initialize Latent Decipher (Assumes a 131072 feature SAE dictionary)
        size_t dict_size = 131072;
        std::cout << "[*] Initializing Latent Decipher (Sparse Dictionary Size: " << dict_size << ")...\n";
        LatentDecipher decipher(dict_size, latent_dim);

        if (!dict_path.empty()) {
            if (decipher.load_dictionary(dict_path.c_str())) {
                std::cout << "[+] Sparse dictionary loaded successfully.\n";
            } else {
                std::cerr << "[-] Failed to load dictionary. Exiting.\n";
                return 1;
            }
        } else {
            std::cout << "[!] WARNING: No SAE dictionary provided. Output vectors will be uncalibrated noise.\n";
        }

        std::cout << "[*] Processing Prompt: \"" << prompt << "\"\n";
        
        // 1. Intercept raw pre-softmax latent state
        size_t extracted_dim = 0;
        const float* hidden_state = engine.execute_and_extract_hidden_state(prompt, extracted_dim);
        
        if (extracted_dim != latent_dim) {
            throw std::runtime_error("Extracted dimension mismatch");
        }

        // 2. Project high-dimensional latent state to Sparse Features
        std::span<const float> latent_span(hidden_state, latent_dim);
        std::vector<float> sparse_features = decipher.project_to_sparse_features(latent_span, 1);

        // 3. Extract 8D Gestalt Topology
        LinguaCalibrationMap calibration = create_demo_calibration();
        LinguaDecodedPrimers gestalt = decipher.extract_primers(sparse_features, 0, calibration);

        // 4. Output structured result
        print_gestalt(gestalt);

    } catch (const std::exception& e) {
        std::cerr << "[-] FATAL ERROR: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
