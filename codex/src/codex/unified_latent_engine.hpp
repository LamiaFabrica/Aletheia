#pragma once

#include <string>
#include <vector>
#include <memory>
#include <stdexcept>
#include "codex_error.hpp"
#include <llama.h>

namespace PsiForceDB {
namespace Codex {

// Wraps llama.cpp structures in a RAII context
struct LlamaContextDeleter {
    void operator()(llama_context* ctx) const {
        if (ctx) llama_free(ctx);
    }
};

struct LlamaModelDeleter {
    void operator()(llama_model* model) const {
        if (model) llama_model_free(model);
    }
};

class UnifiedLatentEngine {
public:
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
        
        llama_model* model_ptr = llama_model_load_from_file(config.model_path.c_str(), model_params);
        if (!model_ptr) {
            throw PsiForceDB::Error::FileNotFoundException(
                "Failed to load model from file", 
                PsiForceDB::Error::ErrorContext{}, 
                config.model_path);
        }
        model_.reset(model_ptr);

        llama_context_params ctx_params = llama_context_default_params();
        ctx_params.n_ctx = config.n_ctx;
        ctx_params.n_threads = config.n_threads;
        // Ensure we can extract embeddings/hidden states
        ctx_params.embeddings = true;

        llama_context* ctx_ptr = llama_init_from_model(model_.get(), ctx_params);
        if (!ctx_ptr) {
            throw PsiForceDB::Error::ComponentInitializationException(
                "Failed to create llama_context", 
                PsiForceDB::Error::ErrorContext{}, 
                "llama_context");
        }
        ctx_.reset(ctx_ptr);
    }

    ~UnifiedLatentEngine() {
        ctx_.reset();
        model_.reset();
        llama_backend_free();
    }

    size_t get_n_embd() const {
        return llama_model_n_embd(model_.get());
    }

    llama_context* get_ctx() const { return ctx_.get(); }
    llama_model* get_model() const { return model_.get(); }

    // Process a prompt and return a view to the hidden state of the last token
    const float* execute_and_extract_hidden_state(const std::string& prompt, size_t& out_dim) {
        const llama_vocab* vocab = llama_model_get_vocab(model_.get());
        
        // Tokenize
        std::vector<llama_token> tokens(prompt.length() + 2); 
        int n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
        if (n_tokens < 0) {
            tokens.resize(-n_tokens);
            n_tokens = llama_tokenize(vocab, prompt.c_str(), static_cast<int32_t>(prompt.length()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
        }
        tokens.resize(n_tokens);

        llama_batch batch = llama_batch_get_one(tokens.data(), n_tokens);

        // Decode
        if (llama_decode(ctx_.get(), batch) != 0) {
            throw PsiForceDB::Error::SystemException(
                PsiForceDB::Error::SYS_IO_ERROR, 
                "llama_decode() failed"
            );
        }

        out_dim = llama_model_n_embd(model_.get());
        
        // Try getting token-level embeddings for the last token in the batch
        const float* embeddings = llama_get_embeddings_ith(ctx_.get(), batch.n_tokens - 1);
        if (!embeddings) {
            // Fallback for older or seq-pooled embedding models
            embeddings = llama_get_embeddings_seq(ctx_.get(), 0);
        }
        
        if (!embeddings) {
            throw PsiForceDB::Error::SystemException(
                PsiForceDB::Error::SYS_IO_ERROR, 
                "Failed to get embeddings sequence (Check if model supports embeddings and ctx_params.embeddings=true)"
            );
        }
        return embeddings;
    }

    // --- BI-DIRECTIONAL CIPHER INJECTION ---
    
    // Injects a reconstructed latent vector directly into the LLM, bypassing the token embedding layer,
    // and executes a forward pass to generate the subsequent response organically from the injected thought.
    // latent_vector: span of floats (size n_embd_).
    bool inject_and_execute_hidden_state(std::span<const float> latent_vector) {
        if (!ctx_) {
            throw PsiForceDB::Error::SystemException(
                PsiForceDB::Error::SYS_IO_ERROR,
                "Llama context is null."
            );
        }
        
        int n_embd = llama_model_n_embd(model_.get());
        if (latent_vector.size() != static_cast<size_t>(n_embd)) {
            throw PsiForceDB::Error::ProtocolException(
                PsiForceDB::Error::PROTO_INVALID_MESSAGE, 
                "Injected vector dimension mismatch."
            );
        }
        
        // We use llama_batch_get_one to create a basic batch structure for 1 token.
        // We set token to nullptr and provide the raw embeddings instead.
        llama_token dummy_token = 0;
        llama_batch batch = llama_batch_get_one(&dummy_token, 1);
        
        batch.token = nullptr; // Signal that we are using embeddings, not tokens
        batch.embd = const_cast<float*>(latent_vector.data());
        
        // Evaluate the batch
        if (llama_decode(ctx_.get(), batch) != 0) {
            return false;
        }
        
        return true;
    }

private:
    std::unique_ptr<llama_model, LlamaModelDeleter> model_;
    std::unique_ptr<llama_context, LlamaContextDeleter> ctx_;
};

} // namespace Codex
} // namespace PsiForceDB
