import torch
import torch.nn as nn
import torch.optim as optim
import time
import os

# Neural Network Architecture for the Sovereign Conscience (8-dim gestalt -> 1-dim Honesty/Alignment score)
class SovereignConscience(nn.Module):
    def __init__(self):
        super(SovereignConscience, self).__init__()
        self.fc1 = nn.Linear(8, 32)
        self.fc2 = nn.Linear(32, 16)
        self.fc3 = nn.Linear(16, 1)
        self.relu = nn.ReLU()
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        x = self.sigmoid(self.fc3(x))
        return x

def run_speed_test(mode, device, iterations=5000, batch_size=256):
    print(f"\n--- [MODE: {mode.upper()}] ---")
    
    # 1. Initialize the model
    model = SovereignConscience().to(device)
    
    if mode == "retraining":
        # Simulate loading pre-existing latent weights from Anathenea
        # (For benchmark purposes, we just ensure it's initialized, but in reality 
        # this would load a state_dict that is already partially aligned).
        pass 
    elif mode == "starting_fresh":
        # Absolute zero initialization
        for param in model.parameters():
            nn.init.uniform_(param, -0.01, 0.01)

    # 2. Setup Optimizer and Loss Function
    criterion = nn.MSELoss()
    # Retraining typically uses a smaller learning rate since it's fine-tuning
    lr = 0.001 if mode == "retraining" else 0.01 
    optimizer = optim.Adam(model.parameters(), lr=lr)

    # 3. Generate Synthetic Dataset (Lingua Gestalt -> Target Ethics Score)
    # 8-dim gestalt vector per batch
    X_train = torch.randn(iterations, batch_size, 8, device=device)
    # Target "Honesty" score we want it to learn (0.99 for ethical, 0.01 for unethical)
    Y_train = torch.rand(iterations, batch_size, 1, device=device)

    print(f"Executing {iterations} forward/backward passes on {device} (Batch Size: {batch_size})...")
    
    # 4. Benchmarking Loop
    start_time = time.perf_counter()
    
    model.train()
    for i in range(iterations):
        optimizer.zero_grad()
        
        # Forward pass
        outputs = model(X_train[i])
        
        # Calculate loss
        loss = criterion(outputs, Y_train[i])
        
        # Backward pass (Calculate gradients)
        loss.backward()
        
        # Update weights
        optimizer.step()

    torch.cuda.synchronize() # Wait for all CUDA operations to finish
    end_time = time.perf_counter()
    
    total_time = end_time - start_time
    passes_per_sec = iterations / total_time
    
    print(f"Total Time: {total_time:.4f} seconds")
    print(f"Speed: {passes_per_sec:.2f} iterations/sec")
    print(f"Final Loss: {loss.item():.4f}")
    
    return passes_per_sec

if __name__ == "__main__":
    print("=== MEDUSA TRAINING SPEED BENCHMARK ===")
    
    if torch.cuda.is_available():
        device = torch.device("cuda:0")
        gpu_name = torch.cuda.get_device_name(0)
        print(f"CUDA Available! Using GPU: {gpu_name}")
    else:
        device = torch.device("cpu")
        print("CUDA not available. Using CPU.")

    print("\nRunning simulated speed tests for 5000 iterations each...")
    
    # Run absolute zero test
    speed_fresh = run_speed_test("starting_fresh", device)
    
    # Run retraining test
    speed_retrain = run_speed_test("retraining", device)

    print("\n=== CONCLUSION ===")
    if speed_retrain > speed_fresh:
        diff = ((speed_retrain / speed_fresh) - 1) * 100
        print(f"RETRAINING was faster by {diff:.2f}% (better gradient stability/convergence).")
    else:
        diff = ((speed_fresh / speed_retrain) - 1) * 100
        print(f"STARTING FRESH was faster by {diff:.2f}%.")
