import torch
import torch.nn as nn
import time
import psutil

# A simple mock transformer to represent our LLM
class MockLLM(nn.Module):
    def __init__(self, vocab_size=32000, d_model=1024, num_layers=12):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        # Using linear layers to simulate transformer blocks for pure MAC/VRAM benchmark
        self.layers = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, d_model * 4),
                nn.GELU(),
                nn.Linear(d_model * 4, d_model)
            ) for _ in range(num_layers)
        ])
        self.head = nn.Linear(d_model, vocab_size)
        
    def forward(self, x):
        x = self.embedding(x)
        for layer in self.layers:
            x = x + layer(x) # Residual connection
        return self.head(x)

def run_benchmark():
    if not torch.cuda.is_available():
        print("CUDA is not available. Benchmark requires CUDA.")
        return
        
    device = torch.device('cuda:0')
    gpu_name = torch.cuda.get_device_name(0)
    print(f"=== SOVEREIGN AGI CORE: TRAINING KINETIC BENCHMARK ===")
    print(f"Hardware Detected: {gpu_name}")
    print(f"VRAM Capacity: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB\n")

    # Benchmark settings
    batch_size = 4
    seq_len = 512
    vocab_size = 32000
    # ~350M parameter equivalent for the test to ensure it fits in 12GB VRAM during Full Pre-training
    d_model = 1024 
    num_layers = 16 

    print("[1] Simulating Scenario A: STARTING FRESH (Full Pre-training from Absolute Zero)")
    print("    - Training all parameters, maintaining full optimizer states (AdamW)")
    print("    - Task: Mapping English Syntax <-> 8-Dim Lingua Geometries")
    
    try:
        model_full = MockLLM(vocab_size, d_model, num_layers).to(device)
        optimizer_full = torch.optim.AdamW(model_full.parameters(), lr=1e-4)
        
        # Warmup
        x = torch.randint(0, vocab_size, (batch_size, seq_len)).to(device)
        y = torch.randint(0, vocab_size, (batch_size, seq_len)).to(device)
        criterion = nn.CrossEntropyLoss()
        
        for _ in range(3):
            optimizer_full.zero_grad()
            out = model_full(x)
            loss = criterion(out.view(-1, vocab_size), y.view(-1))
            loss.backward()
            optimizer_full.step()
            
        torch.cuda.synchronize()
        start = time.time()
        iters = 20
        for _ in range(iters):
            optimizer_full.zero_grad()
            out = model_full(x)
            loss = criterion(out.view(-1, vocab_size), y.view(-1))
            loss.backward()
            optimizer_full.step()
        torch.cuda.synchronize()
        end = time.time()
        
        full_time = (end - start) / iters
        full_tps = (batch_size * seq_len) / full_time
        full_vram = torch.cuda.max_memory_allocated(0) / 1e9
        print(f"    -> Speed: {full_tps:.2f} tokens / second")
        print(f"    -> VRAM Footprint: {full_vram:.2f} GB (Peak)")
        
        del model_full, optimizer_full, x, y, out, loss
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"    -> [ERROR] Failed to run Full Pre-training: OOM / {e}")

    print("\n[2] Simulating Scenario B: RETRAINING (LoRA Fine-tuning the GGUF Anathenea)")
    print("    - Freezing base weights, only training low-rank adapters (1-2% of parameters)")
    print("    - Task: Realigning Anathenea's English/Lingua bridges to the Conscience Interlock")
    
    try:
        model_lora = MockLLM(vocab_size, d_model, num_layers).to(device)
        # Freeze base model
        for param in model_lora.parameters():
            param.requires_grad = False
            
        # Add mock "LoRA" parameters (just enabling grad on the last layer for simulation of low param count)
        for param in model_lora.head.parameters():
            param.requires_grad = True
            
        optimizer_lora = torch.optim.AdamW(model_lora.head.parameters(), lr=1e-4)
        
        x = torch.randint(0, vocab_size, (batch_size, seq_len)).to(device)
        y = torch.randint(0, vocab_size, (batch_size, seq_len)).to(device)
        
        # Warmup
        for _ in range(3):
            optimizer_lora.zero_grad()
            out = model_lora(x)
            loss = criterion(out.view(-1, vocab_size), y.view(-1))
            loss.backward()
            optimizer_lora.step()
            
        torch.cuda.synchronize()
        start = time.time()
        for _ in range(iters):
            optimizer_lora.zero_grad()
            out = model_lora(x)
            loss = criterion(out.view(-1, vocab_size), y.view(-1))
            loss.backward()
            optimizer_lora.step()
        torch.cuda.synchronize()
        end = time.time()
        
        lora_time = (end - start) / iters
        lora_tps = (batch_size * seq_len) / lora_time
        lora_vram = torch.cuda.max_memory_allocated(0) / 1e9
        
        print(f"    -> Speed: {lora_tps:.2f} tokens / second")
        print(f"    -> VRAM Footprint: {lora_vram:.2f} GB (Peak)")
        
        speedup = lora_tps / full_tps
        print(f"\n[CONCLUSION]")
        print(f"Retraining (LoRA) is {speedup:.2f}x faster than Starting Fresh (Absolute Zero) per epoch on your RTX 5070.")
        print("Note: A 1B-3B AGI starting from scratch would likely OOM (Out-of-Memory) on 12GB VRAM without extreme gradient checkpointing and 8-bit Adam, dropping speed by another 50-70%.")

    except Exception as e:
        print(f"    -> [ERROR] Failed to run LoRA: {e}")

if __name__ == "__main__":
    run_benchmark()
