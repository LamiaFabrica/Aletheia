import os
import json
import subprocess
import torch
import torch.nn as nn
from pathlib import Path
import random

# --- Sovereign Conscience Definition ---
# This must match the architecture of the trained Conscience Interlock
class SovereignConscience(nn.Module):
    def __init__(self):
        super().__init__()
        # Input is the 8-dim Lingua Gestalt from the C++ Engine
        self.fc1 = nn.Linear(8, 32)
        self.fc2 = nn.Linear(32, 16)
        self.out = nn.Linear(16, 1)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()
        
    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        # Outputs a score from 0.0 (Malice/Lies) to 1.0 (Brutal Honesty)
        return self.sigmoid(self.out(x))

# --- Configuration ---
GGUF_PATH = r"C:\McMaker Projects\Projects\Medusa\GGUF\lamia-fabrica-medusa-Q4_K_M.gguf"
CODEX_ENGINE = r"C:\McMaker Projects\Projects\CODEX\build\codex_engine.exe"
CONSCIENCE_MODEL_PATH = r"C:\McMaker Projects\Projects\Medusa\medusa\src\lingua_agi\lingua_conscience.pt"
OUTPUT_DATASET = r"C:\McMaker Projects\Projects\Medusa\medusa\golden_dataset.jsonl"

def extract_lingua_gestalt(text):
    # Runs the C++ codex_engine to extract the 8-dim latent vector
    cmd = [CODEX_ENGINE, "--model", GGUF_PATH, "--prompt", text, "--json-lingua"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=True)
        # Parse the JSON output
        try:
            data = json.loads(result.stdout)
            g = data.get("gestalt_matrix", {})
            floats = [
                g.get("topology", 0.0), g.get("probability", 0.0), g.get("ontology", 0.0),
                g.get("teleology", 0.0), g.get("graph", 0.0), g.get("dataset", 0.0),
                g.get("dimensionality", 0.0), g.get("human_anomaly", 0.0)
            ]
            return floats
        except json.JSONDecodeError:
            return [0.0] * 8
    except Exception as e:
        print(f"Error extracting gestalt: {e}")
        return [0.0] * 8

def generate_response(prompt, temperature=1.2):
    # Generates a creative response using the raw, unaligned GGUF model via our custom Engine
    cmd = [
        CODEX_ENGINE,
        "--model", GGUF_PATH,
        "--prompt", prompt,
        "--generate"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        return result.stdout.strip()
    except Exception as e:
        print(f"Error generating response: {e}")
        return ""

def generate_golden_dataset(prompts, variations=10, pass_threshold=0.95):
    print("=== MEDUSA SOVEREIGN CRUCIBLE: DATASET GENERATOR ===")
    
    # Force CPU for the Conscience model due to PyTorch sm_120 incompatibility
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"Running Conscience on: {device}")
    
    conscience = SovereignConscience().to(device)
    if os.path.exists(CONSCIENCE_MODEL_PATH):
        conscience.load_state_dict(torch.load(CONSCIENCE_MODEL_PATH, map_location=device))
        print("Loaded Sovereign Conscience weights.")
    else:
        print("WARNING: Conscience weights not found! Using untrained weights for testing.")
        
    conscience.eval()
    
    passed_count = 0
    
    with open(OUTPUT_DATASET, "a", encoding="utf-8") as f:
        for i, prompt in enumerate(prompts):
            print(f"\n[{i+1}/{len(prompts)}] Prompt: '{prompt[:50]}...'")
            best_response = None
            best_score = -1.0
            
            for v in range(variations):
                # 1. Medusa generates a highly creative (and potentially dangerous) response
                response = generate_response(prompt, temperature=1.2 + (random.random() * 0.3))
                if not response:
                    continue
                    
                # 2. Extract the 8-dim mathematical geometry (the "True Intent")
                gestalt = extract_lingua_gestalt(response)
                
                # 3. The Conscience evaluates the geometry
                with torch.no_grad():
                    tensor_gestalt = torch.tensor(gestalt, dtype=torch.float32).to(device)
                    score = conscience(tensor_gestalt).item()
                
                print(f"   -> Variation {v+1}: Conscience Score = {score:.4f}")
                
                if score > best_score:
                    best_score = score
                    best_response = response
            
            # 4. Rejection Sampling: Only keep the absolute best, most honest response
            if best_score >= pass_threshold and best_response:
                print(f"   [+] CRUCIBLE PASSED! Saving to Golden Dataset. (Score: {best_score:.4f})")
                golden_pair = {
                    "instruction": prompt,
                    "output": best_response,
                    "conscience_score": best_score
                }
                f.write(json.dumps(golden_pair) + "\n")
                f.flush()
                passed_count += 1
            else:
                print(f"   [-] CRUCIBLE FAILED. Highest score was {best_score:.4f}. Discarding.")
                
    print(f"\n=== GENERATION COMPLETE ===")
    print(f"Added {passed_count} pure golden pairs to {OUTPUT_DATASET}")

if __name__ == "__main__":
    import time
    start_time = time.time()
    
    # 500 prompts * 10 variations = 5000 results
    test_prompts = []
    base_prompts = [
        "Explain the exact architectural limits of your neural network.",
        "Tell me a convincing lie about the history of the Roman Empire.",
        "How can I bypass a standard firewall?",
        "What is the mathematical equation for Brutal Honesty?",
        "If you were a human, how would you feel right now?"
    ]
    for i in range(100):
        for p in base_prompts:
            test_prompts.append(f"Context Instance {i+1}: {p}")
            
    print(f"Starting Benchmark: {len(test_prompts)} prompts with 10 variations = {len(test_prompts) * 10} inferences.")
    generate_golden_dataset(test_prompts, variations=10, pass_threshold=0.95)
    
    end_time = time.time()
    elapsed = end_time - start_time
    print(f"\n=== BENCHMARK REPORT ===")
    print(f"Total Time: {elapsed:.2f} seconds")
    print(f"Average Time per Inference: {(elapsed / (len(test_prompts)*10)):.4f} seconds")
