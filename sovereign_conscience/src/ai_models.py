#!/usr/bin/env python3
"""
AI models module for Medusa project.
Implements PyTorch-based models for risk assessment and anomaly detection.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PortFeatureExtractor:
    """Extracts and normalizes features from port data."""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.service_encoder = {}  # For encoding service names
        self.product_encoder = {}  # For encoding product names
    
    def _encode_service(self, service: str) -> int:
        """Encode service name to numeric value."""
        if service not in self.service_encoder:
            self.service_encoder[service] = len(self.service_encoder)
        return self.service_encoder[service]
    
    def _encode_product(self, product: str) -> int:
        """Encode product name to numeric value."""
        if product not in self.product_encoder:
            self.product_encoder[product] = len(self.product_encoder)
        return self.product_encoder[product]
    
    def extract_features(self, port_data: Dict) -> np.ndarray:
        """Extract features from port data."""
        features = [
            port_data['port'] / 65535.0,  # Normalize port number
            self._encode_service(port_data.get('service', 'unknown')) / max(1, len(self.service_encoder)),
            self._encode_product(port_data.get('product', 'unknown')) / max(1, len(self.product_encoder)),
            1.0 if port_data.get('state') == 'open' else 0.0,
            len(port_data.get('version', '')) / 100.0,  # Normalize version length
        ]
        return np.array(features)
    
    def fit(self, port_data_list: List[Dict]):
        """Fit the feature extractor to the data."""
        features = [self.extract_features(port) for port in port_data_list]
        self.scaler.fit(features)
    
    def transform(self, port_data: Dict) -> np.ndarray:
        """Transform port data to normalized features."""
        features = self.extract_features(port_data)
        return self.scaler.transform(features.reshape(1, -1))[0]

class PortDataset(Dataset):
    """Dataset for port data."""
    
    def __init__(self, port_data_list: List[Dict], feature_extractor: PortFeatureExtractor):
        self.features = []
        self.labels = []
        
        for port in port_data_list:
            features = feature_extractor.transform(port)
            self.features.append(features)
            self.labels.append(port.get('risk_score', 0.0))
    
    def __len__(self) -> int:
        return len(self.features)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return (
            torch.FloatTensor(self.features[idx]),
            torch.FloatTensor([self.labels[idx]])
        )

class RiskAssessmentModel(nn.Module):
    """Neural network for risk assessment."""
    
    def __init__(self, input_size: int = 5):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

class AnomalyDetectionModel(nn.Module):
    """Autoencoder for anomaly detection."""
    
    def __init__(self, input_size: int = 5):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_size, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 8)
        )
        
        self.decoder = nn.Sequential(
            nn.Linear(8, 16),
            nn.ReLU(),
            nn.Linear(16, 32),
            nn.ReLU(),
            nn.Linear(32, input_size)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(x)
        decoded = self.decoder(encoded)
        return decoded
    
    def get_anomaly_score(self, x: torch.Tensor) -> torch.Tensor:
        """Calculate anomaly score using reconstruction error."""
        decoded = self(x)
        return torch.mean((x - decoded) ** 2, dim=1)

class AIModelManager:
    """Manages AI models for risk assessment and anomaly detection."""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(exist_ok=True)
        
        self.feature_extractor = PortFeatureExtractor()
        self.risk_model = RiskAssessmentModel()
        self.anomaly_model = AnomalyDetectionModel()
        
        # Load models if they exist
        self._load_models()
    
    def _load_models(self):
        """Load saved models if they exist."""
        try:
            if (self.model_dir / "risk_model.pt").exists():
                self.risk_model.load_state_dict(torch.load(self.model_dir / "risk_model.pt"))
                logger.info("Loaded risk assessment model")
            
            if (self.model_dir / "anomaly_model.pt").exists():
                self.anomaly_model.load_state_dict(torch.load(self.model_dir / "anomaly_model.pt"))
                logger.info("Loaded anomaly detection model")
            
            if (self.model_dir / "feature_extractor.json").exists():
                with open(self.model_dir / "feature_extractor.json", 'r') as f:
                    data = json.load(f)
                    self.feature_extractor.service_encoder = data['service_encoder']
                    self.feature_extractor.product_encoder = data['product_encoder']
                logger.info("Loaded feature extractor")
                
        except Exception as e:
            logger.error(f"Error loading models: {e}")
    
    def _save_models(self):
        """Save models to disk."""
        try:
            torch.save(self.risk_model.state_dict(), self.model_dir / "risk_model.pt")
            torch.save(self.anomaly_model.state_dict(), self.model_dir / "anomaly_model.pt")
            
            with open(self.model_dir / "feature_extractor.json", 'w') as f:
                json.dump({
                    'service_encoder': self.feature_extractor.service_encoder,
                    'product_encoder': self.feature_extractor.product_encoder
                }, f)
            
            logger.info("Saved models successfully")
            
        except Exception as e:
            logger.error(f"Error saving models: {e}")
    
    def train_risk_model(self, port_data_list: List[Dict], epochs: int = 100, batch_size: int = 32):
        """Train the risk assessment model."""
        # Prepare data
        self.feature_extractor.fit(port_data_list)
        dataset = PortDataset(port_data_list, self.feature_extractor)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        # Setup training
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.risk_model.parameters())
        
        # Training loop
        self.risk_model.train()
        for epoch in range(epochs):
            total_loss = 0
            for features, labels in dataloader:
                optimizer.zero_grad()
                outputs = self.risk_model(features)
                loss = criterion(outputs, labels)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
        self._save_models()
    
    def train_anomaly_model(self, port_data_list: List[Dict], epochs: int = 100, batch_size: int = 32):
        """Train the anomaly detection model."""
        # Prepare data
        self.feature_extractor.fit(port_data_list)
        dataset = PortDataset(port_data_list, self.feature_extractor)
        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        # Setup training
        criterion = nn.MSELoss()
        optimizer = optim.Adam(self.anomaly_model.parameters())
        
        # Training loop
        self.anomaly_model.train()
        for epoch in range(epochs):
            total_loss = 0
            for features, _ in dataloader:
                optimizer.zero_grad()
                outputs = self.anomaly_model(features)
                loss = criterion(outputs, features)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {total_loss/len(dataloader):.4f}")
        
        self._save_models()
    
    def predict_risk(self, port_data: Dict) -> float:
        """Predict risk score for a port."""
        self.risk_model.eval()
        with torch.no_grad():
            features = torch.FloatTensor(self.feature_extractor.transform(port_data))
            risk_score = self.risk_model(features).item()
        return risk_score
    
    def detect_anomaly(self, port_data: Dict) -> Tuple[bool, float]:
        """Detect if a port is anomalous."""
        self.anomaly_model.eval()
        with torch.no_grad():
            features = torch.FloatTensor(self.feature_extractor.transform(port_data))
            anomaly_score = self.anomaly_model.get_anomaly_score(features).item()
            is_anomaly = anomaly_score > 0.1  # Threshold for anomaly detection
        return is_anomaly, anomaly_score 