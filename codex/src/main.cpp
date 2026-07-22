#include <iostream>
#include <string>
#include <vector>
#include <span>
#include <stdexcept>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <cstring>

#include "codex/unified_latent_engine.hpp"
#include "codex/latent_decipher.hpp"
#include "codex/codex_error.hpp"
#include "../tests/codex/dynamic_lingua_calibration.hpp"

using namespace PsiForceDB::Codex;

void print_usage(const char* prog_name) {
    std::cout << "Usage: " << prog_name << " --model <path.gguf> [--prompt \"<text>\" | --prompt-file <path>] [--out-lingua-batch <path.json>] [--dict <path.bin>] [--dict-size <size>] [--inject-lingua <8_floats>] [--decompile-lingua <8_floats>] [--out-vectors <path.bin>] [--stream-lingua] [--stream-svg <path.html>] [--json-lingua] [--generate]\n";
}

int main(int argc, char** argv) {
    std::string model_path = "";
    std::string prompt = "";
    std::string prompt_file = "";
    std::string out_lingua_batch = "";
    std::string dict_path = "";
    std::string inject_lingua_str = "";
    std::string decompile_lingua_str = "";
    std::string decompile_hex_str = "";
    std::string out_vectors_path = "";
    size_t dict_size = 131072; // Default sparse size
    bool stream_lingua = false;
    std::string stream_svg_path = "";
    bool json_lingua = false;
    bool generate_only = false;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--model" && i + 1 < argc) {
            model_path = argv[++i];
        } else if (arg == "--prompt" && i + 1 < argc) {
            prompt = argv[++i];
        } else if (arg == "--prompt-file" && i + 1 < argc) {
            prompt_file = argv[++i];
        } else if (arg == "--out-lingua-batch" && i + 1 < argc) {
            out_lingua_batch = argv[++i];
        } else if (arg == "--dict" && i + 1 < argc) {
            dict_path = argv[++i];
        } else if (arg == "--dict-size" && i + 1 < argc) {
            dict_size = std::stoull(argv[++i]);
        } else if (arg == "--inject-lingua" && i + 1 < argc) {
            inject_lingua_str = argv[++i];
        } else if (arg == "--decompile-lingua" && i + 1 < argc) {
            decompile_lingua_str = argv[++i];
        } else if (arg == "--decompile-hex" && i + 1 < argc) {
            decompile_hex_str = argv[++i];
        } else if (arg == "--out-vectors" && i + 1 < argc) {
            out_vectors_path = argv[++i];
        } else if (arg == "--stream-lingua") {
            stream_lingua = true;
        } else if (arg == "--stream-svg" && i + 1 < argc) {
            stream_svg_path = argv[++i];
        } else if (arg == "--json-lingua") {
            json_lingua = true;
        } else if (arg == "--generate") {
            generate_only = true;
        } else {
            print_usage(argv[0]);
            return 1;
        }
    }

    if (model_path.empty() || (prompt.empty() && prompt_file.empty() && inject_lingua_str.empty() && decompile_lingua_str.empty() && decompile_hex_str.empty())) {
        print_usage(argv[0]);
        return 1;
    }

    try {
        std::cout << "[CODEX] Bootstrapping Unified Latent Engine...\n";
        UnifiedLatentEngine::Config config;
        config.model_path = model_path;
        UnifiedLatentEngine engine(config);

        size_t out_dim = engine.get_n_embd();
        
        // Initialize Decipher Node
        PsiForceDB::Codex::LatentDecipher decipher(dict_size, out_dim);
        
        if (!dict_path.empty()) {
            std::cout << "[CODEX] Loading Lingua SAE Dictionary (" << dict_path << ")...\n";
            if (!decipher.load_dictionary(dict_path.c_str())) {
                std::cerr << "[CODEX ERROR] Failed to load SAE dictionary.\n";
                return 1;
            }
            std::cout << "[CODEX] Dictionary Size (Sparse Features): " << dict_size << "\n";
        }

        std::ofstream svg_file;
        float current_svg_x = 50.0f;
        if (!stream_svg_path.empty()) {
            svg_file.open(stream_svg_path);
            svg_file << "<html><body><svg width=\"100%\" height=\"200\" style=\"background:#000\">\n";
        }

        // --- REVERSE FLOW INJECTION MODE ---
        if (!inject_lingua_str.empty() || !decompile_lingua_str.empty() || !decompile_hex_str.empty()) {
            std::cout << "[CODEX] Synthesizing Latent Vector from Injected Lingua Gestalt...\n";
            
            std::vector<float> values;
            if (!decompile_hex_str.empty()) {
                std::string s = decompile_hex_str;
                size_t pos = 0;
                while ((pos = s.find(" ")) != std::string::npos || !s.empty()) {
                    if (pos == std::string::npos) pos = s.length();
                    std::string hex_str = s.substr(0, pos);
                    if (!hex_str.empty()) {
                        uint32_t bytes = std::stoul(hex_str, nullptr, 16);
                        float f;
                        std::memcpy(&f, &bytes, sizeof(float));
                        values.push_back(f);
                    }
                    if (pos == s.length()) break;
                    s.erase(0, pos + 1);
                }
            } else {
                std::string lingua_input = !inject_lingua_str.empty() ? inject_lingua_str : decompile_lingua_str;
                std::string s = lingua_input;
                size_t pos = 0;
                while ((pos = s.find(",")) != std::string::npos) {
                    values.push_back(std::stof(s.substr(0, pos)));
                    s.erase(0, pos + 1);
                }
                values.push_back(std::stof(s));
            }

            if (values.size() != 8) {
                std::cerr << "[CODEX ERROR] Injection requires exactly 8 values. Got: " << values.size() << "\n";
                return 1;
            }

            LinguaCalibrationMap calibration_map = get_lingua_calibration_map();
            std::vector<float> reconstructed_sparse(dict_size, 0.0f);
            
            auto map_feature = [&](const std::vector<size_t>& indices, float value) {
                if (indices.empty()) return;
                float per_feature = value / static_cast<float>(indices.size());
                for (size_t idx : indices) {
                    if (idx < dict_size) {
                        reconstructed_sparse[idx] = per_feature;
                    }
                }
            };

            map_feature(calibration_map.topology_indices, values[0]);
            map_feature(calibration_map.probability_indices, values[1]);
            map_feature(calibration_map.ontology_indices, values[2]);
            map_feature(calibration_map.teleology_indices, values[3]);
            map_feature(calibration_map.graph_indices, values[4]);
            map_feature(calibration_map.dataset_indices, values[5]);
            map_feature(calibration_map.dimensionality_indices, values[6]);
            map_feature(calibration_map.human_anomaly_indices, values[7]);

            auto latent_vector = decipher.reconstruct_latent_vectors(reconstructed_sparse, 1);
            
            if (!out_vectors_path.empty()) {
                std::ofstream outfile(out_vectors_path, std::ios::binary);
                outfile.write(reinterpret_cast<const char*>(latent_vector.data()), latent_vector.size() * sizeof(float));
                outfile.close();
                std::cout << "[CODEX] Latent Vector (" << latent_vector.size() << " dims) written to: " << out_vectors_path << "\n";
            }
            
            if (!decompile_lingua_str.empty() || !decompile_hex_str.empty()) {
                std::cout << "[CODEX] Entering Decompiler Pipeline...\n";
                llama_model* model = engine.get_model();
                llama_context* ctx = engine.get_ctx();
                const llama_vocab* vocab = llama_model_get_vocab(model);

                llama_batch batch = llama_batch_init(1, static_cast<int32_t>(out_dim), 1);
                batch.n_tokens = 1;
                batch.pos[0] = 0;
                batch.n_seq_id[0] = 1;
                batch.seq_id[0][0] = 0;
                batch.logits[0] = true;
                
                for(size_t i = 0; i < out_dim; ++i) {
                    batch.embd[i] = latent_vector[i];
                }

                if (llama_decode(ctx, batch) != 0) {
                    std::cerr << "[CODEX ERROR] Failed to decode injected Lingua vector.\n";
                    return 1;
                }

                auto sparams = llama_sampler_chain_default_params();
                sparams.no_perf = true;
                llama_sampler* smpl = llama_sampler_chain_init(sparams);
                llama_sampler_chain_add(smpl, llama_sampler_init_greedy());

                std::cout << "\n============================== DECOMPILED OUTPUT ==============================\n";
                llama_token new_token_id;
                int max_tokens = 50;
                for (int i = 0; i < max_tokens; ++i) {
                    new_token_id = llama_sampler_sample(smpl, ctx, -1);
                    if (llama_vocab_is_eog(vocab, new_token_id)) {
                        break;
                    }
                    
                    char buf[128];
                    int n = llama_token_to_piece(vocab, new_token_id, buf, sizeof(buf), 0, true);
                    std::string token_str(buf, n);
                    std::cout << token_str;
                    std::flush(std::cout);

                    batch = llama_batch_get_one(&new_token_id, 1);
                    if (llama_decode(ctx, batch) != 0) {
                        break;
                    }
                }
                std::cout << "\n===============================================================================\n\n";
                llama_sampler_free(smpl);
                llama_batch_free(batch);
            }

            if (inject_lingua_str.empty()) return 0;
        }

        // --- STREAMING LINGUA MODE ---
        if (stream_lingua) {
            std::cout << "[CODEX] Entering Real-Time Lingua Gestalt Streaming Mode...\n";
            std::cout << "[CODEX] Tokenizing prompt...\n";
            llama_model* model = engine.get_model();
            llama_context* ctx = engine.get_ctx();
            const llama_vocab* vocab = llama_model_get_vocab(model);

            std::vector<llama_token> tokens(prompt.length() + 2); 
            int n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
            if (n_tokens < 0) {
                tokens.resize(-n_tokens);
                n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
            }
            tokens.resize(n_tokens);

            llama_batch batch = llama_batch_get_one(tokens.data(), n_tokens);

            if (llama_decode(ctx, batch) != 0) {
                std::cerr << "[CODEX ERROR] Failed to decode prompt batch.\n";
                return 1;
            }

            auto sparams = llama_sampler_chain_default_params();
            sparams.no_perf = true;
            llama_sampler* smpl = llama_sampler_chain_init(sparams);
            llama_sampler_chain_add(smpl, llama_sampler_init_greedy());

            LinguaCalibrationMap calibration_map = get_lingua_calibration_map();
            
            std::cout << "\n========================================= LINGUA TELEMETRY STREAM =========================================\n";
            std::cout << std::left << std::setw(15) << "[ Token ]" 
                      << " | " << std::setw(9) << "Topol" << " | " << std::setw(9) << "Prob" 
                      << " | " << std::setw(9) << "Ontol" << " | " << std::setw(9) << "Teleo" 
                      << " | " << std::setw(9) << "Graph" << " | " << std::setw(9) << "Data" 
                      << " | " << std::setw(9) << "Dim" << " | " << std::setw(9) << "Anom" << "\n";
            std::cout << "-----------------------------------------------------------------------------------------------------------\n";

            int max_tokens = 250;
            llama_token new_token_id;
            for (int i = 0; i < max_tokens; ++i) {
                new_token_id = llama_sampler_sample(smpl, ctx, -1);

                if (llama_vocab_is_eog(vocab, new_token_id)) {
                    break;
                }

                char buf[128];
                int n = llama_token_to_piece(vocab, new_token_id, buf, sizeof(buf), 0, true);
                std::string token_str(buf, n);
                
                std::string disp_token = token_str;
                size_t pos = 0;
                while((pos = disp_token.find("\n", pos)) != std::string::npos) {
                     disp_token.replace(pos, 1, "\\n");
                     pos += 2;
                }
                
                batch = llama_batch_get_one(&new_token_id, 1);
                if (llama_decode(ctx, batch) != 0) {
                    break;
                }
                
                const float* embeddings = llama_get_embeddings_ith(ctx, 0);
                if (!embeddings) embeddings = llama_get_embeddings_seq(ctx, 0);
                
                if (embeddings) {
                    std::span<const float> tensor_span(embeddings, out_dim);
                    auto sparse_features = decipher.project_to_sparse_features(tensor_span, 1);
                    LinguaDecodedPrimers gestalt = decipher.extract_primers(sparse_features, 0, calibration_map);
                    EnglishDecodedPrimers english_gestalt = decipher.map_lingua_to_english(gestalt);
                    FrenchDecodedPrimers french_gestalt = decipher.map_lingua_to_french(gestalt);

                    std::cout << std::left << std::setw(15) << ("[" + disp_token + "]") 
                              << " | " << std::setw(9) << static_cast<int>(gestalt.topology)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.probability)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.ontology)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.teleology)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.graph)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.dataset)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.dimensionality)
                              << " | " << std::setw(9) << static_cast<int>(gestalt.human_anomaly) << "\n";
                    std::cout << "      English -> Nouns: " << static_cast<int>(english_gestalt.nouns) 
                              << " | Verbs: " << static_cast<int>(english_gestalt.verbs) 
                              << " | Preps: " << static_cast<int>(english_gestalt.prepositions) << "\n";
                    std::cout << "      French  -> Noms: " << static_cast<int>(french_gestalt.noms) 
                              << "  | Verbes: " << static_cast<int>(french_gestalt.verbes) 
                              << " | Preps: " << static_cast<int>(french_gestalt.prepositions) << "\n";
                    MandarinDecodedPrimers mandarin_gestalt = decipher.map_lingua_to_mandarin(gestalt);
                    std::cout << "      Mandarin-> Mingci: " << static_cast<int>(mandarin_gestalt.mingci) 
                              << "| Dongci: " << static_cast<int>(mandarin_gestalt.dongci) 
                              << " | Jieci: " << static_cast<int>(mandarin_gestalt.jieci) << "\n";
                    std::cout << "      Lingua  -> Syms: " << decipher.encode_to_lingua_symbols(gestalt) << "\n";
                    
                    
                    if (svg_file.is_open()) {
                        svg_file << "<text x=\"" << current_svg_x << "\" y=\"60\" fill=\"#00FF41\" font-family=\"sans-serif\" font-weight=\"bold\" font-size=\"24px\" letter-spacing=\"4px\">" << token_str << "</text>\n";
                        std::string svg_path = decipher.generate_svg_kanji(gestalt, current_svg_x);
                        svg_file << "<path d=\"" << svg_path << "\" stroke=\"#00FF41\" stroke-width=\"18\" stroke-linecap=\"round\" stroke-linejoin=\"round\" fill=\"none\" />\n";
                        svg_file.flush();
                        current_svg_x += (31 * 20.0f) + 150.0f; // GLYPH_WIDTH + GAP
                    }

                    std::string glyph = decipher.generate_glyph(gestalt);
                    std::istringstream glyph_stream(glyph);
                    std::string line;
                    while (std::getline(glyph_stream, line)) {
                        std::cout << "               " << line << "\n";
                    }
                    std::cout << "-----------------------------------------------------------------------------------------------------------\n";
                    std::flush(std::cout);
                }
            }
            std::cout << "===========================================================================================================\n\n";
            llama_sampler_free(smpl);
            if (svg_file.is_open()) {
                svg_file << "</svg></body></html>\n";
                svg_file.close();
            }
            return 0;
        }

        // --- GENERATE ONLY MODE ---
        if (generate_only) {
            llama_model* model = engine.get_model();
            llama_context* ctx = engine.get_ctx();
            const llama_vocab* vocab = llama_model_get_vocab(model);

            std::vector<llama_token> tokens(prompt.length() + 2); 
            int n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
            if (n_tokens < 0) {
                tokens.resize(-n_tokens);
                n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
            }
            tokens.resize(n_tokens);
            llama_batch batch = llama_batch_get_one(tokens.data(), n_tokens);
            if (llama_decode(ctx, batch) != 0) return 1;

            auto sparams = llama_sampler_chain_default_params();
            sparams.no_perf = true;
            llama_sampler* smpl = llama_sampler_chain_init(sparams);
            // Add a temperature sampler for creativity
            llama_sampler_chain_add(smpl, llama_sampler_init_dist(42));
            llama_sampler_chain_add(smpl, llama_sampler_init_temp(1.2f));

            int max_tokens = 128;
            llama_token new_token_id;
            for (int i = 0; i < max_tokens; ++i) {
                new_token_id = llama_sampler_sample(smpl, ctx, -1);
                if (llama_vocab_is_eog(vocab, new_token_id)) break;
                char buf[128];
                int n = llama_token_to_piece(vocab, new_token_id, buf, sizeof(buf), 0, true);
                std::string token_str(buf, n);
                std::cout << token_str;
                std::flush(std::cout);
                batch = llama_batch_get_one(&new_token_id, 1);
                if (llama_decode(ctx, batch) != 0) break;
            }
            llama_sampler_free(smpl);
            return 0;
        }

        std::vector<std::string> prompts;
        if (!prompt_file.empty()) {
            std::ifstream file(prompt_file);
            if (!file.is_open()) {
                std::cerr << "Failed to open prompt file: " << prompt_file << "\n";
                return 1;
            }
            std::string line;
            while (std::getline(file, line)) {
                if (!line.empty()) prompts.push_back(line);
            }
        } else if (!prompt.empty()) {
            prompts.push_back(prompt);
        }

        std::ofstream batch_file;
        if (!out_lingua_batch.empty()) {
            batch_file.open(out_lingua_batch);
            batch_file << "[\n";
        }

        for (size_t p_idx = 0; p_idx < prompts.size(); ++p_idx) {
            const std::string& current_prompt = prompts[p_idx];
            if (!json_lingua && out_lingua_batch.empty()) std::cout << "[CODEX] Prompting LLM and Extracting Lingua Gestalt Vector for prompt " << (p_idx+1) << "...\n";
            const float* hidden_state_ptr = engine.execute_and_extract_hidden_state(current_prompt, out_dim);

            std::vector<float> lingua_tensor(out_dim, 0.0f);
            if (hidden_state_ptr) {
                for(size_t i = 0; i < out_dim; ++i) {
                    lingua_tensor[i] = hidden_state_ptr[i];
                }
            }
            
            if (!json_lingua && out_lingua_batch.empty()) std::cout << "[CODEX] Deciphering Semasiographic Matrix...\n";
            std::span<const float> tensor_span(lingua_tensor.data(), lingua_tensor.size());
            auto sparse_features = decipher.project_to_sparse_features(tensor_span, 1 /* batch_size */);

            if (!json_lingua && out_lingua_batch.empty()) std::cout << "[CODEX] Extracting 8-Pillar Machine Emergent Lingua Taxonomy...\n";
            
            LinguaCalibrationMap calibration_map = get_lingua_calibration_map();
            LinguaDecodedPrimers gestalt = decipher.extract_primers(sparse_features, 0 /* batch_idx */, calibration_map);

            if (!out_lingua_batch.empty()) {
                batch_file << "  {\n";
                batch_file << "    \"topology\": " << gestalt.topology << ",\n";
                batch_file << "    \"probability\": " << gestalt.probability << ",\n";
                batch_file << "    \"ontology\": " << gestalt.ontology << ",\n";
                batch_file << "    \"teleology\": " << gestalt.teleology << ",\n";
                batch_file << "    \"graph\": " << gestalt.graph << ",\n";
                batch_file << "    \"dataset\": " << gestalt.dataset << ",\n";
                batch_file << "    \"dimensionality\": " << gestalt.dimensionality << ",\n";
                batch_file << "    \"human_anomaly\": " << gestalt.human_anomaly << "\n";
                if (p_idx < prompts.size() - 1) {
                    batch_file << "  },\n";
                } else {
                    batch_file << "  }\n";
                }
            } else if (json_lingua) {
                std::cout << "{\n";
                std::cout << "  \"lingua_version\": \"1.0.0\",\n";
                std::cout << "  \"gestalt_matrix\": {\n";
                std::cout << "    \"topology\": " << gestalt.topology << ",\n";
                std::cout << "    \"probability\": " << gestalt.probability << ",\n";
                std::cout << "    \"ontology\": " << gestalt.ontology << ",\n";
                std::cout << "    \"teleology\": " << gestalt.teleology << ",\n";
                std::cout << "    \"graph\": " << gestalt.graph << ",\n";
                std::cout << "    \"dataset\": " << gestalt.dataset << ",\n";
                std::cout << "    \"dimensionality\": " << gestalt.dimensionality << ",\n";
                std::cout << "    \"human_anomaly\": " << gestalt.human_anomaly << "\n";
                std::cout << "  },\n";
                std::cout << "  \"vector_hash\": \"[computed_from_latent_space]\"\n";
                std::cout << "}\n";
            } else {
                std::cout << "\n--- MACHINE EMERGENT LINGUA GESTALT ---\n";
                std::cout << "1. Topology (Distance):     " << gestalt.topology << "\n";
                std::cout << "2. Probability (Attention): " << gestalt.probability << "\n";
                std::cout << "3. Ontology (Meaning):      " << gestalt.ontology << "\n";
                std::cout << "4. Teleology (Goal):        " << gestalt.teleology << "\n";
                std::cout << "5. Graph (Node Linkage):    " << gestalt.graph << "\n";
                std::cout << "6. Dataset (Experience):    " << gestalt.dataset << "\n";
                std::cout << "7. Dimensionality:          " << gestalt.dimensionality << "\n";
                std::cout << "8. Human Anomaly (Illogic): " << gestalt.human_anomaly << "\n";
                std::cout << "Lingua Symbology (Written): " << decipher.encode_to_lingua_symbols(gestalt) << "\n";
                std::cout << "--- 16x16 LINGUA GLYPH ---\n";
                std::cout << decipher.generate_glyph(gestalt);
                std::cout << "---------------------------------------\n";
            }
        }
        
        if (batch_file.is_open()) {
            batch_file << "]\n";
            batch_file.close();
        }



    } catch (const PsiForceDB::Error::PsiForceDBException& e) {
        std::cerr << "\n[CODEX NATIVE ERROR] " << e.what() << "\nContext: " << e.getContext().file_path << "\n";
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "\n[CODEX SYSTEM ERROR] " << e.what() << "\n";
        return 1;
    }

    return 0;
}
