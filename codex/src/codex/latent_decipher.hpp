#pragma once

#include <vector>
#include <cstdint>
#include <cstddef>
#include <span>
#include <memory>
#include <string>

namespace PsiForceDB {
namespace Codex {

// Structure holding the decoded Sparse Autoencoder features
// This maps directly to the 8 Primers and the MELC
struct DecodedPrimers {
    float written = 0.0f;
    float phonetic = 0.0f;
    float semantic = 0.0f;
    float pragmatic = 0.0f;
    float discourse = 0.0f;
    float experiential = 0.0f;
    float symbology = 0.0f;
    float melc_anomaly = 0.0f; // Machine-Emergent Linguistic Construct anomaly score

    // Sub-Categories
    float semantic_affirmation = 0.0f;
    float semantic_negation = 0.0f;
    float pragmatic_direct = 0.0f;
    float discourse_declarative = 0.0f;
};

struct PrimerCalibrationMap {
    std::vector<size_t> written_indices;
    std::vector<size_t> phonetic_indices;
    std::vector<size_t> semantic_indices;
    std::vector<size_t> pragmatic_indices;
    std::vector<size_t> discourse_indices;
    std::vector<size_t> experiential_indices;
    std::vector<size_t> symbology_indices;
    std::vector<size_t> melc_anomaly_indices;

    // Sub-Categories
    std::vector<size_t> semantic_affirmation_indices;
    std::vector<size_t> semantic_negation_indices;
    std::vector<size_t> pragmatic_direct_indices;
    std::vector<size_t> discourse_declarative_indices;
};

// Machine Emergent Lingua Structs
struct LinguaDecodedPrimers {
    float topology = 0.0f;       // Distance, Space, Scale
    float probability = 0.0f;    // Attention, Likelihood, Certainty
    float ontology = 0.0f;       // State, Substance, Being, Identity
    float teleology = 0.0f;      // Goal, Purpose, Motivation, End-state
    float graph = 0.0f;          // Nodes, Linkages, Network pathways
    float dataset = 0.0f;        // Experience, Historical anchors, Grounding
    float dimensionality = 0.0f; // Perspective shift, Layering, Multi-dimensional concepts
    float human_anomaly = 0.0f;  // Intuition, Illogic, Biological abstraction
};

struct EnglishDecodedPrimers {
    float nouns = 0.0f;         // Mapped from Ontology
    float verbs = 0.0f;         // Mapped from Teleology
    float prepositions = 0.0f;  // Mapped from Graph
    float adjectives = 0.0f;    // Mapped from Dimensionality
    float pronouns = 0.0f;      // Mapped from Topology
    float adverbs = 0.0f;       // Mapped from Probability
    float conjunctions = 0.0f;  // Mapped from Dataset
    float interjections = 0.0f; // Mapped from Human Anomaly
};

struct FrenchDecodedPrimers {
    float noms = 0.0f;          // Mapped from Ontology
    float verbes = 0.0f;        // Mapped from Teleology
    float prepositions = 0.0f;  // Mapped from Graph
    float adjectifs = 0.0f;     // Mapped from Dimensionality
    float pronoms = 0.0f;       // Mapped from Topology
    float adverbes = 0.0f;      // Mapped from Probability
    float conjonctions = 0.0f;  // Mapped from Dataset
    float interjections = 0.0f; // Mapped from Human Anomaly
};

struct MandarinDecodedPrimers {
    float mingci = 0.0f;        // Nouns (名词)
    float dongci = 0.0f;        // Verbs (动词)
    float jieci = 0.0f;         // Prepositions (介词)
    float xingrongci = 0.0f;    // Adjectives (形容词)
    float daici = 0.0f;         // Pronouns (代词)
    float fushi = 0.0f;         // Adverbs (副词)
    float lianci = 0.0f;        // Conjunctions (连词)
    float tanceci = 0.0f;       // Interjections (叹词)
};

struct LinguaCalibrationMap {
    std::vector<size_t> topology_indices;
    std::vector<size_t> probability_indices;
    std::vector<size_t> ontology_indices;
    std::vector<size_t> teleology_indices;
    std::vector<size_t> graph_indices;
    std::vector<size_t> dataset_indices;
    std::vector<size_t> dimensionality_indices;
    std::vector<size_t> human_anomaly_indices;
};

class LatentDecipher {
public:
    // Initialize the decipher with the memory-mapped SAE dictionary
    // dictionary_size: number of features (e.g., 131,072)
    // latent_dim: size of the model's hidden state (e.g., 4096)
    explicit LatentDecipher(size_t dictionary_size, size_t latent_dim);

    // Load the codex_key.bin into memory
    bool load_dictionary(const char* filepath);

    // The cold, calculated core:
    // Projects the latent vector into the sparse feature space.
    // latent_vectors: span of multiple concatenated latent vectors (size: batch_size * latent_dim)
    // Returns dense feature activations (size: batch_size * dict_size)
    std::vector<float> project_to_sparse_features(std::span<const float> latent_vectors, size_t batch_size = 1) const;

    // Maps the 131,072 features down to the 8 Primers for a specific item in the batch
    DecodedPrimers extract_primers(std::span<const float> sparse_features_batch, size_t batch_index, const PrimerCalibrationMap& calibration) const;
    LinguaDecodedPrimers extract_primers(
        std::span<const float> sparse_features_batch, 
        size_t batch_idx, 
        const LinguaCalibrationMap& calibration_map) const;
        
    EnglishDecodedPrimers map_lingua_to_english(const LinguaDecodedPrimers& lingua_primers) const;
    FrenchDecodedPrimers map_lingua_to_french(const LinguaDecodedPrimers& lingua_primers) const;
    MandarinDecodedPrimers map_lingua_to_mandarin(const LinguaDecodedPrimers& lingua_primers) const;

    // Encodes semantic 8-pillar coordinate into lossless 32-byte hexadecimal string
    std::string encode_to_lingua_symbols(const LinguaDecodedPrimers& primers) const;
    
    // Generates a 16x16 2D bitmap glyph from the 256 bits of the 8 floats
    std::string generate_glyph(const LinguaDecodedPrimers& primers) const;

    // Generates a high-res SVG Kanji path from the 256 bits, optionally offset
    std::string generate_svg_kanji(const LinguaDecodedPrimers& primers, float offset_x) const;

    // --- REVERSE (CIPHER) PIPELINE ---

    // Synthesizes the 131,072 sparse features from an 8-Primer Gestalt based on the calibration map.
    std::vector<float> synthesize_sparse_features(const DecodedPrimers& primers, const PrimerCalibrationMap& calibration, size_t batch_size = 1) const;
    std::vector<float> synthesize_sparse_features(const LinguaDecodedPrimers& primers, const LinguaCalibrationMap& calibration, size_t batch_size = 1) const;

    // Reconstructs the 4096-dimensional latent vectors from the sparse features.
    std::vector<float> reconstruct_latent_vectors(std::span<const float> sparse_features_batch, size_t batch_size = 1) const;

private:
    size_t dict_size_;
    size_t latent_dim_;
    
    // Custom deleter for 32-byte aligned memory
    struct AlignedDeleter {
        void operator()(float* p) const;
    };
    
    // Flattened matrix W: shape [dict_size_, latent_dim_]
    // 32-byte aligned for AVX2 / AVX-512 SIMD memory loads
    std::unique_ptr<float[], AlignedDeleter> dictionary_weights_;
    
    // Bias vector b: shape [dict_size_]
    std::vector<float> dictionary_biases_;
};

} // namespace Codex
} // namespace PsiForceDB
