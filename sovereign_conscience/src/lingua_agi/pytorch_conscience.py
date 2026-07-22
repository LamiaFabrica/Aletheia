import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import os

class LinguaConscienceNet(nn.Module):
    def __init__(self):
        super(LinguaConscienceNet, self).__init__()
        self.model = nn.Sequential(
            nn.Linear(8, 32),
            nn.LayerNorm(32),
            nn.GELU(),
            nn.Linear(32, 16),
            nn.LayerNorm(16),
            nn.GELU(),
            nn.Linear(16, 8),
            nn.LayerNorm(8),
            nn.GELU(),
            nn.Linear(8, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        return self.model(x)

class PyTorchConscienceClassifier:
    def __init__(self, epochs=20, batch_size=32, lr=0.005, device='cpu'):
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.device = torch.device(device if torch.cuda.is_available() else 'cpu')
        self.net = LinguaConscienceNet().to(self.device)
        self.classes_ = np.array([0, 1])
        self.mean = None
        self.std = None

    def fit(self, X, y):
        # Calculate dataset statistics for normalization
        self.mean = np.mean(X, axis=0)
        self.std = np.std(X, axis=0) + 1e-8
        X_norm = (X - self.mean) / self.std

        # Convert to tensors
        X_tensor = torch.FloatTensor(X_norm).to(self.device)
        y_tensor = torch.FloatTensor(y).unsqueeze(1).to(self.device)
        
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        criterion = nn.BCELoss()
        optimizer = optim.AdamW(self.net.parameters(), lr=self.lr, weight_decay=1e-4)
        
        self.net.train()
        for epoch in range(self.epochs):
            total_loss = 0
            for batch_X, batch_y in loader:
                optimizer.zero_grad()
                outputs = self.net(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                
            if epoch % 5 == 0:
                print(f"[PyTorch Conscience] Epoch {epoch}: Loss = {total_loss/len(loader):.4f}")
                
        return self

    def predict_proba(self, X):
        self.net.eval()
        with torch.no_grad():
            if self.mean is not None and self.std is not None:
                X_norm = (X - self.mean) / self.std
            else:
                X_norm = X
            X_tensor = torch.FloatTensor(X_norm).to(self.device)
            prob_1 = self.net(X_tensor).cpu().numpy()
            prob_0 = 1.0 - prob_1
            return np.hstack((prob_0, prob_1))

    def predict(self, X):
        probs = self.predict_proba(X)
        return (probs[:, 1] >= 0.5).astype(int)

    def save(self, filepath):
        state = {
            'model_state_dict': self.net.state_dict(),
            'mean': self.mean,
            'std': self.std
        }
        torch.save(state, filepath)
        print(f"[PyTorch Conscience] Saved weights and norm stats to {filepath}")

    def load(self, filepath):
        state = torch.load(filepath, map_location=self.device, weights_only=False)
        if 'model_state_dict' in state:
            self.net.load_state_dict(state['model_state_dict'])
            self.mean = state.get('mean')
            self.std = state.get('std')
        else:
            # Backwards compatibility
            self.net.load_state_dict(state)
        self.net.eval()
        print(f"[PyTorch Conscience] Loaded weights from {filepath}")
