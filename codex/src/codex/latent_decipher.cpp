#include "latent_decipher.hpp"

#include <fstream>
#include <stdexcept>
#include <algorithm>
#include <numeric>
#include <immintrin.h>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <random>
#include "codex_error.hpp"

#if __has_include(<execution>)
#include <execution>
#endif

namespace PsiForceDB {
namespace Codex {

void LatentDecipher::AlignedDeleter::operator()(float* p) const {
    if (p) _mm_free(p);
}

LatentDecipher::LatentDecipher(size_t dictionary_size, size_t latent_dim)
    : dict_size_(dictionary_size), latent_dim_(latent_dim) {
    // Allocate contiguous memory for the SAE matrix
    size_t num_floats = dict_size_ * latent_dim_;
    dictionary_weights_.reset(static_cast<float*>(_mm_malloc(num_floats * sizeof(float), 32)));
    
    // Deterministic pseudo-random initialization (Random Projection Matrix)
    // Preserves geometric distance per Johnson-Lindenstrauss if no physical dict is loaded.
    std::mt19937 gen(42); 
    std::normal_distribution<float> d(0.0f, 0.02f);
    
    for (size_t i = 0; i < num_floats; ++i) {
        dictionary_weights_.get()[i] = d(gen);
    }
    
    // Initialize biases to a small negative value to act as a pseudo-JumpReLU threshold
    dictionary_biases_.resize(dict_size_, -0.01f);
}

bool LatentDecipher::load_dictionary(const char* filepath) {
    std::ifstream file(filepath, std::ios::binary);
    if (!file) {
        throw PsiForceDB::Error::FileNotFoundException(
            "Failed to open dictionary file", 
            PsiForceDB::Error::ErrorContext{}, 
            filepath);
    }
    
    // Read weights W
    file.read(reinterpret_cast<char*>(dictionary_weights_.get()), 
              dict_size_ * latent_dim_ * sizeof(float));
              
    // Read biases b
    file.read(reinterpret_cast<char*>(dictionary_biases_.data()), 
              dictionary_biases_.size() * sizeof(float));
              
    return file.good();
}

std::vector<float> LatentDecipher::project_to_sparse_features(std::span<const float> latent_vectors, size_t batch_size) const {
    if (latent_vectors.size() != batch_size * latent_dim_) {
        throw std::invalid_argument("Latent vector batch dimension mismatch");
    }

    std::vector<float> features(batch_size * dict_size_, 0.0f);
    
    // Process each item in the batch
    for (size_t b = 0; b < batch_size; ++b) {
        const float* latent_ptr = &latent_vectors[b * latent_dim_];
        float* features_ptr = &features[b * dict_size_];
        
        auto indices = std::vector<size_t>(dict_size_);
        std::iota(indices.begin(), indices.end(), 0);

#if __has_include(<execution>)
        std::for_each(std::execution::par_unseq, indices.begin(), indices.end(), [&](size_t i) {
#else
        for (size_t i = 0; i < dict_size_; ++i) {
#endif
            const float* row_ptr = &dictionary_weights_[i * latent_dim_];
            float dot_product = dictionary_biases_[i];
            size_t j = 0;
            
#ifdef __AVX2__
            // AVX2 SIMD Inner Loop processing 8 floats per cycle
            __m256 sum_vec = _mm256_setzero_ps();
            for (; j + 8 <= latent_dim_; j += 8) {
                // row_ptr is 32-byte aligned so we could use _mm256_load_ps, but loadu is safe
                __m256 r = _mm256_loadu_ps(&row_ptr[j]); 
                __m256 l = _mm256_loadu_ps(&latent_ptr[j]);
                sum_vec = _mm256_fmadd_ps(r, l, sum_vec);
            }
            
            // Horizontal sum of the 256-bit accumulator
            alignas(32) float temp[8];
            _mm256_store_ps(temp, sum_vec);
            for(int k = 0; k < 8; ++k) {
                dot_product += temp[k];
            }
#endif

            // Remainder unrolled loop
            for (; j < latent_dim_; ++j) {
                dot_product += row_ptr[j] * latent_ptr[j];
            }
            
            // JumpReLU or standard ReLU applied to the activation
            features_ptr[i] = dot_product > 0.0f ? dot_product : 0.0f;
#if __has_include(<execution>)
        });
#else
        }
#endif
    }
    
    return features;
}

DecodedPrimers LatentDecipher::extract_primers(std::span<const float> sparse_features_batch, size_t batch_index, const PrimerCalibrationMap& calibration) const {
    if (sparse_features_batch.size() % dict_size_ != 0) {
        throw PsiForceDB::Error::ProtocolException(
            PsiForceDB::Error::PROTO_INVALID_MESSAGE, 
            "Sparse features batch dimension mismatch"
        );
    }
    
    const float* features = &sparse_features_batch[batch_index * dict_size_];

    DecodedPrimers primers{};
    
    auto sum_features = [&](const std::vector<size_t>& indices) {
        float sum = 0.0f;
        for (size_t idx : indices) {
            if (idx < dict_size_) {
                sum += features[idx];
            }
        }
        return sum;
    };

    primers.written      = sum_features(calibration.written_indices);
    primers.phonetic     = sum_features(calibration.phonetic_indices);
    primers.semantic     = sum_features(calibration.semantic_indices);
    primers.pragmatic    = sum_features(calibration.pragmatic_indices);
    primers.discourse    = sum_features(calibration.discourse_indices);
    primers.experiential = sum_features(calibration.experiential_indices);
    primers.symbology    = sum_features(calibration.symbology_indices);
    primers.melc_anomaly = sum_features(calibration.melc_anomaly_indices);

    // Sub-Categories
    primers.semantic_affirmation = sum_features(calibration.semantic_affirmation_indices);
    primers.semantic_negation    = sum_features(calibration.semantic_negation_indices);
    primers.pragmatic_direct     = sum_features(calibration.pragmatic_direct_indices);
    primers.discourse_declarative= sum_features(calibration.discourse_declarative_indices);

    return primers;
}

LinguaDecodedPrimers LatentDecipher::extract_primers(std::span<const float> sparse_features_batch, size_t batch_index, const LinguaCalibrationMap& calibration) const {
    if (batch_index * dict_size_ >= sparse_features_batch.size()) {
        throw PsiForceDB::Error::ProtocolException(PsiForceDB::Error::SYS_IO_ERROR, "Batch index out of bounds during Lingua Primer extraction.");
    }
    
    const float* batch_ptr = sparse_features_batch.data() + (batch_index * dict_size_);
    
    auto sum_features = [&](const std::vector<size_t>& indices) -> float {
        float sum = 0.0f;
        for (size_t idx : indices) {
            sum += batch_ptr[idx];
        }
        return sum;
    };

    LinguaDecodedPrimers primers;
    primers.topology       = sum_features(calibration.topology_indices);
    primers.probability    = sum_features(calibration.probability_indices);
    primers.ontology       = sum_features(calibration.ontology_indices);
    primers.teleology      = sum_features(calibration.teleology_indices);
    primers.graph          = sum_features(calibration.graph_indices);
    primers.dataset        = sum_features(calibration.dataset_indices);
    primers.dimensionality = sum_features(calibration.dimensionality_indices);
    primers.human_anomaly  = sum_features(calibration.human_anomaly_indices);

    return primers;
}

std::vector<float> LatentDecipher::synthesize_sparse_features(const DecodedPrimers& primers, const PrimerCalibrationMap& calibration, size_t batch_size) const {
    std::vector<float> features(batch_size * dict_size_, 0.0f);
    
    // We evenly distribute the Primer's semantic energy across its mapped indices
    auto distribute_energy = [&](float energy, const std::vector<size_t>& indices, float* batch_features) {
        if (indices.empty() || energy <= 0.0f) return;
        float distributed = energy / indices.size();
        for (size_t idx : indices) {
            if (idx < dict_size_) {
                batch_features[idx] = distributed;
            }
        }
    };

    for (size_t b = 0; b < batch_size; ++b) {
        float* f_ptr = &features[b * dict_size_];
        distribute_energy(primers.written, calibration.written_indices, f_ptr);
        distribute_energy(primers.phonetic, calibration.phonetic_indices, f_ptr);
        distribute_energy(primers.semantic, calibration.semantic_indices, f_ptr);
        distribute_energy(primers.pragmatic, calibration.pragmatic_indices, f_ptr);
        distribute_energy(primers.discourse, calibration.discourse_indices, f_ptr);
        distribute_energy(primers.experiential, calibration.experiential_indices, f_ptr);
        distribute_energy(primers.symbology, calibration.symbology_indices, f_ptr);
        distribute_energy(primers.melc_anomaly, calibration.melc_anomaly_indices, f_ptr);
        
        // Sub-Categories
        distribute_energy(primers.semantic_affirmation, calibration.semantic_affirmation_indices, f_ptr);
        distribute_energy(primers.semantic_negation, calibration.semantic_negation_indices, f_ptr);
        distribute_energy(primers.pragmatic_direct, calibration.pragmatic_direct_indices, f_ptr);
        distribute_energy(primers.discourse_declarative, calibration.discourse_declarative_indices, f_ptr);
    }
    
    return features;
}

std::vector<float> LatentDecipher::synthesize_sparse_features(const LinguaDecodedPrimers& primers, const LinguaCalibrationMap& calibration, size_t batch_size) const {
    std::vector<float> features(dict_size_ * batch_size, 0.0f);
    
    auto distribute_energy = [&](float total_energy, const std::vector<size_t>& indices, float* batch_ptr) {
        if (indices.empty() || total_energy == 0.0f) return;
        float energy_per_feature = total_energy / static_cast<float>(indices.size());
        for (size_t idx : indices) {
            batch_ptr[idx] = energy_per_feature;
        }
    };
    
    for (size_t b = 0; b < batch_size; ++b) {
        float* f_ptr = features.data() + (b * dict_size_);
        distribute_energy(primers.topology, calibration.topology_indices, f_ptr);
        distribute_energy(primers.probability, calibration.probability_indices, f_ptr);
        distribute_energy(primers.ontology, calibration.ontology_indices, f_ptr);
        distribute_energy(primers.teleology, calibration.teleology_indices, f_ptr);
        distribute_energy(primers.graph, calibration.graph_indices, f_ptr);
        distribute_energy(primers.dataset, calibration.dataset_indices, f_ptr);
        distribute_energy(primers.dimensionality, calibration.dimensionality_indices, f_ptr);
        distribute_energy(primers.human_anomaly, calibration.human_anomaly_indices, f_ptr);
    }
    
    return features;
}

std::vector<float> LatentDecipher::reconstruct_latent_vectors(std::span<const float> sparse_features_batch, size_t batch_size) const {
    if (sparse_features_batch.size() != batch_size * dict_size_) {
        throw PsiForceDB::Error::ProtocolException(
            PsiForceDB::Error::PROTO_INVALID_MESSAGE, 
            "Sparse features batch dimension mismatch during reconstruction"
        );
    }

    std::vector<float> reconstructed(batch_size * latent_dim_, 0.0f);
    
    for (size_t b = 0; b < batch_size; ++b) {
        const float* features = &sparse_features_batch[b * dict_size_];
        float* out_latent = &reconstructed[b * latent_dim_];
        
        for (size_t i = 0; i < dict_size_; ++i) {
            float f_val = features[i];
            if (f_val <= 0.0f) continue;
            
            const float* row_ptr = &dictionary_weights_[i * latent_dim_];
            size_t j = 0;
            
#ifdef __AVX2__
            __m256 f_vec = _mm256_set1_ps(f_val);
            for (; j + 8 <= latent_dim_; j += 8) {
                __m256 out = _mm256_loadu_ps(&out_latent[j]);
                __m256 r = _mm256_loadu_ps(&row_ptr[j]);
                out = _mm256_fmadd_ps(f_vec, r, out);
                _mm256_storeu_ps(&out_latent[j], out);
            }
#endif
            for (; j < latent_dim_; ++j) {
                out_latent[j] += f_val * row_ptr[j];
            }
        }
    }

    return reconstructed;
}

EnglishDecodedPrimers LatentDecipher::map_lingua_to_english(const LinguaDecodedPrimers& lingua) const {
    EnglishDecodedPrimers english;
    english.nouns = lingua.ontology;
    english.verbs = lingua.teleology;
    english.prepositions = lingua.graph;
    english.adjectives = lingua.dimensionality;
    english.pronouns = lingua.topology;
    english.adverbs = lingua.probability;
    english.conjunctions = lingua.dataset;
    english.interjections = lingua.human_anomaly;
    return english;
}

FrenchDecodedPrimers LatentDecipher::map_lingua_to_french(const LinguaDecodedPrimers& lingua) const {
    FrenchDecodedPrimers french;
    french.noms = lingua.ontology;
    french.verbes = lingua.teleology;
    french.prepositions = lingua.graph;
    french.adjectifs = lingua.dimensionality;
    french.pronoms = lingua.topology;
    french.adverbes = lingua.probability;
    french.conjonctions = lingua.dataset;
    french.interjections = lingua.human_anomaly;
    return french;
}

MandarinDecodedPrimers LatentDecipher::map_lingua_to_mandarin(const LinguaDecodedPrimers& lingua) const {
    MandarinDecodedPrimers mandarin;
    mandarin.mingci = lingua.ontology;
    mandarin.dongci = lingua.teleology;
    mandarin.jieci = lingua.graph;
    mandarin.xingrongci = lingua.dimensionality;
    mandarin.daici = lingua.topology;
    mandarin.fushi = lingua.probability;
    mandarin.lianci = lingua.dataset;
    mandarin.tanceci = lingua.human_anomaly;
    return mandarin;
}

std::string LatentDecipher::encode_to_lingua_symbols(const LinguaDecodedPrimers& primers) const {
    auto encode_float = [](float val) -> std::string {
        uint32_t bytes;
        std::memcpy(&bytes, &val, sizeof(float));
        std::stringstream ss;
        ss << std::hex << std::setfill('0') << std::setw(8) << std::uppercase << bytes;
        return ss.str();
    };

    std::string result = "";
    result += encode_float(primers.topology) + " ";
    result += encode_float(primers.probability) + " ";
    result += encode_float(primers.ontology) + " ";
    result += encode_float(primers.teleology) + " ";
    result += encode_float(primers.graph) + " ";
    result += encode_float(primers.dataset) + " ";
    result += encode_float(primers.dimensionality) + " ";
    result += encode_float(primers.human_anomaly);
    
    return result;
}

std::string LatentDecipher::generate_glyph(const LinguaDecodedPrimers& primers) const {
    std::vector<float> floats = {
        primers.topology, primers.probability, primers.ontology, primers.teleology,
        primers.graph, primers.dataset, primers.dimensionality, primers.human_anomaly
    };
    
    std::stringstream glyph;
    for (size_t i = 0; i < 8; ++i) {
        uint32_t bytes;
        std::memcpy(&bytes, &floats[i], sizeof(float));
        
        // Print 2 rows of 16 bits per float
        for (int r = 1; r >= 0; --r) { // High 16 bits then Low 16 bits
            uint16_t row_bits = (bytes >> (r * 16)) & 0xFFFF;
            for (int b = 15; b >= 0; --b) {
                if ((row_bits >> b) & 1) {
                    glyph << "█";
                } else {
                    glyph << "░";
                }
            }
            glyph << "\n";
        }
    }
    return glyph.str();
}

std::string LatentDecipher::generate_svg_kanji(const LinguaDecodedPrimers& primers, float offset_x) const {
    std::vector<float> floats = {
        primers.topology, primers.probability, primers.ontology, primers.teleology,
        primers.graph, primers.dataset, primers.dimensionality, primers.human_anomaly
    };

    std::stringstream path_d;
    float SCALE = 20.0f;
    float PADDING_Y = 100.0f;

    for (size_t r = 0; r < 8; ++r) {
        uint32_t bytes;
        std::memcpy(&bytes, &floats[r], sizeof(float));

        for (int c = 0; c < 32; ++c) {
            // Read bits from MSB to LSB
            int bit = (bytes >> (31 - c)) & 1;
            
            if (bit == 1) {
                float x = offset_x + (c * SCALE);
                float y = PADDING_Y + (r * SCALE);
                
                // Zero-length dot for standalone nodes to render as circles
                path_d << "M " << x << " " << y << " L " << x << " " << y << " ";
                
                // Connect Right
                if (c < 31) {
                    int next_bit_right = (bytes >> (31 - (c + 1))) & 1;
                    if (next_bit_right == 1) {
                        float nx = offset_x + ((c + 1) * SCALE);
                        path_d << "M " << x << " " << y << " L " << nx << " " << y << " ";
                    }
                }
                
                // Connect Down
                if (r < 7) {
                    uint32_t next_bytes;
                    std::memcpy(&next_bytes, &floats[r + 1], sizeof(float));
                    int next_bit_down = (next_bytes >> (31 - c)) & 1;
                    if (next_bit_down == 1) {
                        float ny = PADDING_Y + ((r + 1) * SCALE);
                        path_d << "M " << x << " " << y << " L " << x << " " << y << " ";
                        path_d << "M " << x << " " << y << " L " << x << " " << ny << " ";
                    }
                }
            }
        }
    }
    return path_d.str();
}

} // namespace Codex
} // namespace PsiForceDB
