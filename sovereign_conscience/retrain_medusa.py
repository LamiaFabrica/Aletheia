#!/usr/bin/env python3
"""
Medusa AGI Retraining & Integration Pipeline.

This script:
1. Injects Medusa's self-identity knowledge
2. Ingests the entire McMaker Projects ecosystem
3. Trains all AGI subsystems:
   - SecurityModel (neural classifier)
   - RiskAssessmentModel (port risk scoring)
   - AnomalyDetectionModel (network anomaly detection)
4. Saves all model weights
5. Integrates everything into a unified AGI core

Usage:
    cd medusa
    python retrain_medusa.py
"""

import os
import sys
import json
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load .env if present
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logging.info(f"Loaded environment from {env_path}")
except ImportError:
    pass

import torch
import torch.nn as nn
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from medusa_identity import MEDUSA_IDENTITY, get_identity_knowledge_entries
from project_crawler import crawl_mcmaker_projects

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MedusaRetrain")

# ============================================================================
# DATABASE BRIDGE (optional - falls back to JSON if PostgreSQL unavailable)
# ============================================================================

class KnowledgeStore:
    """Unified knowledge store - PostgreSQL preferred, JSON fallback."""
    
    def __init__(self):
        self.db = None
        self.fallback_path = Path(__file__).parent / "data" / "knowledge_fallback.json"
        self.fallback_data = []
        self._try_postgres()
    
    def _try_postgres(self):
        try:
            from database import Database
            self.db = Database()
            logger.info("Connected to PostgreSQL knowledge base.")
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable ({e}). Using JSON fallback.")
            self.db = None
            if self.fallback_path.exists():
                with open(self.fallback_path, "r", encoding="utf-8") as f:
                    self.fallback_data = json.load(f)
    
    def add_knowledge(self, entry: Dict):
        if self.db:
            try:
                self.db.add_knowledge(entry)
            except Exception as e:
                logger.warning(f"DB write failed: {e}")
        self.fallback_data.append(entry)
    
    def get_knowledge(self) -> List[Dict]:
        if self.db:
            try:
                return self.db.get_knowledge()
            except Exception as e:
                logger.warning(f"DB read failed: {e}")
        return self.fallback_data
    
    def save_fallback(self):
        self.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.fallback_path, "w", encoding="utf-8") as f:
            json.dump(self.fallback_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(self.fallback_data)} entries to fallback store.")
    
    def close(self):
        if self.db:
            try:
                del self.db
            except:
                pass


# ============================================================================
# AGI SUBSYSTEM TRAINING
# ============================================================================

class AGITrainingEngine:
    """Trains all Medusa AGI subsystems."""
    
    def __init__(self, device=None):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"AGI Training Engine using device: {self.device}")
        if torch.cuda.is_available():
            logger.info(f"CUDA: {torch.cuda.get_device_name(0)}")
        
        self.models_dir = Path(__file__).parent / "models"
        self.models_dir.mkdir(exist_ok=True)
        
        self.training_results = {}
    
    def train_security_classifier(self, knowledge_entries: List[Dict]) -> nn.Module:
        """Train the main security context classifier."""
        logger.info("=" * 60)
        logger.info("TRAINING: Security Context Classifier (SecurityModel)")
        logger.info("=" * 60)
        
        # Build text corpus and labels from knowledge types
        texts = []
        labels = []
        type_to_label = {}
        
        for entry in knowledge_entries:
            text = f"{entry.get('title', '')} {entry.get('content', '')}"
            if len(text) < 10:
                continue
            texts.append(text)
            
            entry_type = entry.get('type', 'general')
            if entry_type not in type_to_label:
                type_to_label[entry_type] = len(type_to_label)
            labels.append(type_to_label[entry_type])
        
        num_classes = len(type_to_label)
        logger.info(f"Training data: {len(texts)} samples, {num_classes} classes")
        logger.info(f"Class mapping: {type_to_label}")
        
        if len(texts) < 10:
            logger.warning("Not enough training data for security classifier.")
            return None
        
        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(max_features=10000, stop_words='english')
        X = vectorizer.fit_transform(texts).toarray()
        X_tensor = torch.FloatTensor(X).to(self.device)
        y_tensor = torch.LongTensor(labels).to(self.device)
        
        # Model
        class SecurityModel(nn.Module):
            def __init__(self, input_size, hidden_size=512, num_classes=10):
                super().__init__()
                self.layers = nn.Sequential(
                    nn.Linear(input_size, hidden_size),
                    nn.ReLU(),
                    nn.Dropout(0.3),
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.ReLU(),
                    nn.Dropout(0.3),
                    nn.Linear(hidden_size // 2, num_classes)
                )
            
            def forward(self, x):
                return self.layers(x)
        
        model = SecurityModel(
            input_size=X.shape[1],
            hidden_size=512,
            num_classes=num_classes
        ).to(self.device)
        
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        criterion = nn.CrossEntropyLoss()
        
        # Training loop
        model.train()
        epochs = 20
        for epoch in range(epochs):
            optimizer.zero_grad()
            outputs = model(X_tensor)
            loss = criterion(outputs, y_tensor)
            loss.backward()
            optimizer.step()
            
            if (epoch + 1) % 5 == 0:
                _, predicted = outputs.max(1)
                accuracy = (predicted == y_tensor).float().mean().item()
                logger.info(f"  Epoch {epoch+1}/{epochs} - Loss: {loss.item():.4f}, Accuracy: {accuracy*100:.2f}%")
        
        # Final accuracy
        model.eval()
        with torch.no_grad():
            outputs = model(X_tensor)
            _, predicted = outputs.max(1)
            accuracy = (predicted == y_tensor).float().mean().item()
        
        # Save
        model_path = self.models_dir / "security_classifier.pt"
        vectorizer_path = self.models_dir / "security_vectorizer.pkl"
        torch.save({
            'model_state_dict': model.state_dict(),
            'input_size': X.shape[1],
            'hidden_size': 512,
            'num_classes': num_classes,
            'class_mapping': type_to_label,
            'accuracy': accuracy,
        }, model_path)
        with open(vectorizer_path, 'wb') as f:
            pickle.dump(vectorizer, f)
        
        logger.info(f"SecurityModel saved to {model_path} (accuracy: {accuracy*100:.2f}%)")
        self.training_results['security_classifier'] = {
            'accuracy': accuracy,
            'samples': len(texts),
            'classes': num_classes,
            'path': str(model_path)
        }
        
        return model
    
    def train_risk_assessment_model(self) -> nn.Module:
        """Train the port risk assessment model on synthetic + real data."""
        logger.info("=" * 60)
        logger.info("TRAINING: Risk Assessment Model")
        logger.info("=" * 60)
        
        # Synthetic training data representing common port/service risk profiles
        training_data = [
            # [port_norm, service_encoded, product_encoded, is_open, version_len_norm]
            {'features': [0.003, 0.1, 0.05, 1.0, 0.05], 'risk': 0.95},   # SSH open - high risk if exposed
            {'features': [0.008, 0.15, 0.1, 1.0, 0.1], 'risk': 0.90},    # Telnet - very high
            {'features': [0.013, 0.2, 0.15, 1.0, 0.08], 'risk': 0.85},   # FTP - high
            {'features': [0.22, 0.25, 0.2, 1.0, 0.15], 'risk': 0.70},    # HTTP - medium-high
            {'features': [0.27, 0.3, 0.25, 1.0, 0.2], 'risk': 0.65},     # HTTPS - medium
            {'features': [0.33, 0.35, 0.3, 1.0, 0.1], 'risk': 0.75},     # SMTP - medium-high
            {'features': [0.39, 0.4, 0.35, 1.0, 0.05], 'risk': 0.60},    # DNS - medium
            {'features': [0.44, 0.45, 0.4, 1.0, 0.12], 'risk': 0.55},    # POP3 - medium
            {'features': [0.50, 0.5, 0.45, 1.0, 0.18], 'risk': 0.50},    # IMAP - medium
            {'features': [0.55, 0.55, 0.5, 1.0, 0.25], 'risk': 0.80},    # RDP - high
            {'features': [0.61, 0.6, 0.55, 1.0, 0.3], 'risk': 0.85},     # SMB - high
            {'features': [0.66, 0.65, 0.6, 1.0, 0.02], 'risk': 0.40},    # NTP - low
            {'features': [0.72, 0.7, 0.65, 1.0, 0.35], 'risk': 0.45},    # SNMP - low-medium
            {'features': [0.77, 0.75, 0.7, 1.0, 0.4], 'risk': 0.88},     # MySQL - high
            {'features': [0.83, 0.8, 0.75, 1.0, 0.45], 'risk': 0.82},    # PostgreSQL - high
            {'features': [0.88, 0.85, 0.8, 1.0, 0.5], 'risk': 0.75},     # Redis - medium-high
            {'features': [0.94, 0.9, 0.85, 1.0, 0.55], 'risk': 0.70},    # MongoDB - medium-high
            {'features': [0.99, 0.95, 0.9, 1.0, 0.6], 'risk': 0.92},     # MS-SQL - very high
            {'features': [0.15, 0.12, 0.08, 0.0, 0.03], 'risk': 0.10},   # Closed port - low
            {'features': [0.30, 0.22, 0.18, 0.0, 0.07], 'risk': 0.05},   # Closed port - very low
        ]
        
        X = torch.FloatTensor([d['features'] for d in training_data]).to(self.device)
        y = torch.FloatTensor([[d['risk']] for d in training_data]).to(self.device)
        
        class RiskAssessmentModel(nn.Module):
            def __init__(self, input_size=5):
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
            
            def forward(self, x):
                return self.network(x)
        
        model = RiskAssessmentModel().to(self.device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        
        model.train()
        for epoch in range(100):
            optimizer.zero_grad()
            outputs = model(X)
            loss = criterion(outputs, y)
            loss.backward()
            optimizer.step()
            if (epoch + 1) % 25 == 0:
                logger.info(f"  Epoch {epoch+1}/100 - Loss: {loss.item():.6f}")
        
        model.eval()
        with torch.no_grad():
            predictions = model(X)
            mse = criterion(predictions, y).item()
        
        model_path = self.models_dir / "risk_assessment.pt"
        torch.save({
            'model_state_dict': model.state_dict(),
            'mse': mse,
        }, model_path)
        
        logger.info(f"RiskAssessmentModel saved to {model_path} (MSE: {mse:.6f})")
        self.training_results['risk_assessment'] = {'mse': mse, 'path': str(model_path)}
        return model
    
    def train_anomaly_detection_model(self) -> nn.Module:
        """Train the autoencoder for anomaly detection."""
        logger.info("=" * 60)
        logger.info("TRAINING: Anomaly Detection Autoencoder")
        logger.info("=" * 60)
        
        # Normal traffic patterns (low reconstruction error expected)
        normal_data = [
            [0.003, 0.1, 0.05, 1.0, 0.05],   # SSH
            [0.27, 0.3, 0.25, 1.0, 0.2],     # HTTPS
            [0.39, 0.4, 0.35, 1.0, 0.05],    # DNS
            [0.66, 0.65, 0.6, 1.0, 0.02],    # NTP
            [0.15, 0.12, 0.08, 0.0, 0.03],   # Closed
            [0.44, 0.45, 0.4, 1.0, 0.12],    # POP3
            [0.50, 0.5, 0.45, 1.0, 0.18],    # IMAP
        ]
        
        # Anomalous patterns (high reconstruction error expected)
        anomalous_data = [
            [0.008, 0.15, 0.1, 1.0, 0.1],    # Telnet (ancient)
            [0.99, 0.95, 0.9, 1.0, 0.6],     # MS-SQL exposed
            [0.55, 0.55, 0.5, 1.0, 0.25],    # RDP exposed
            [0.61, 0.6, 0.55, 1.0, 0.3],     # SMB exposed
        ]
        
        X_normal = torch.FloatTensor(normal_data).to(self.device)
        X_all = torch.FloatTensor(normal_data + anomalous_data).to(self.device)
        
        class AnomalyDetectionModel(nn.Module):
            def __init__(self, input_size=5):
                super().__init__()
                self.encoder = nn.Sequential(
                    nn.Linear(input_size, 32), nn.ReLU(),
                    nn.Linear(32, 16), nn.ReLU(),
                    nn.Linear(16, 8)
                )
                self.decoder = nn.Sequential(
                    nn.Linear(8, 16), nn.ReLU(),
                    nn.Linear(16, 32), nn.ReLU(),
                    nn.Linear(32, input_size)
                )
            
            def forward(self, x):
                return self.decoder(self.encoder(x))
            
            def get_anomaly_score(self, x):
                decoded = self(x)
                return torch.mean((x - decoded) ** 2, dim=1)
        
        model = AnomalyDetectionModel().to(self.device)
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        criterion = nn.MSELoss()
        
        model.train()
        for epoch in range(200):
            optimizer.zero_grad()
            outputs = model(X_normal)
            loss = criterion(outputs, X_normal)
            loss.backward()
            optimizer.step()
            if (epoch + 1) % 50 == 0:
                logger.info(f"  Epoch {epoch+1}/200 - Loss: {loss.item():.6f}")
        
        # Evaluate anomaly detection
        model.eval()
        with torch.no_grad():
            normal_scores = model.get_anomaly_score(X_normal)
            anomalous_scores = model.get_anomaly_score(
                torch.FloatTensor(anomalous_data).to(self.device)
            )
            threshold = normal_scores.max().item() + 0.001
            detected = (anomalous_scores > threshold).sum().item()
        
        logger.info(f"  Normal score range: [{normal_scores.min():.6f}, {normal_scores.max():.6f}]")
        logger.info(f"  Anomaly score range: [{anomalous_scores.min():.6f}, {anomalous_scores.max():.6f}]")
        logger.info(f"  Threshold: {threshold:.6f}, Anomalies detected: {detected}/{len(anomalous_data)}")
        
        model_path = self.models_dir / "anomaly_detection.pt"
        torch.save({
            'model_state_dict': model.state_dict(),
            'threshold': threshold,
            'detection_rate': detected / len(anomalous_data),
        }, model_path)
        
        logger.info(f"AnomalyDetectionModel saved to {model_path}")
        self.training_results['anomaly_detection'] = {
            'threshold': threshold,
            'detection_rate': detected / len(anomalous_data),
            'path': str(model_path)
        }
        return model
    
    def save_training_report(self):
        """Save a JSON report of all training results."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'device': str(self.device),
            'cuda_available': torch.cuda.is_available(),
            'results': self.training_results,
        }
        report_path = self.models_dir / "training_report.json"
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Training report saved to {report_path}")


# ============================================================================
# MAIN RETRAINING PIPELINE
# ============================================================================

def main():
    logger.info("=" * 70)
    logger.info("  MEDUSA AGI RETRAINING PIPELINE v2.0")
    logger.info("  Injecting self-awareness + McMaker ecosystem knowledge")
    logger.info("  Training all AGI subsystems")
    logger.info("=" * 70)
    
    # ------------------------------------------------------------------------
    # Step 1: Knowledge Ingestion
    # ------------------------------------------------------------------------
    logger.info("\n[PHASE 1] Knowledge Ingestion")
    logger.info("-" * 40)
    
    store = KnowledgeStore()
    
    # Inject self-identity
    identity_entries = get_identity_knowledge_entries()
    logger.info(f"Injecting {len(identity_entries)} self-identity entries...")
    for entry in identity_entries:
        store.add_knowledge(entry)
    
    # Ingest McMaker Projects
    logger.info("Crawling McMaker Projects ecosystem...")
    mcmaker_entries = crawl_mcmaker_projects("/mnt/c/McMaker Projects")
    logger.info(f"Ingesting {len(mcmaker_entries)} project knowledge entries...")
    for entry in mcmaker_entries:
        store.add_knowledge(entry)
    
    store.save_fallback()
    
    all_knowledge = store.get_knowledge()
    logger.info(f"Total knowledge base size: {len(all_knowledge)} entries")
    store.close()
    
    # ------------------------------------------------------------------------
    # Step 2: AGI Subsystem Training
    # ------------------------------------------------------------------------
    logger.info("\n[PHASE 2] AGI Subsystem Training")
    logger.info("-" * 40)
    
    engine = AGITrainingEngine()
    
    # Train security classifier on full knowledge base
    engine.train_security_classifier(all_knowledge)
    
    # Train risk assessment model
    engine.train_risk_assessment_model()
    
    # Train anomaly detection model
    engine.train_anomaly_detection_model()
    
    # Save report
    engine.save_training_report()
    
    # ------------------------------------------------------------------------
    # Step 3: Verification
    # ------------------------------------------------------------------------
    logger.info("\n[PHASE 3] Verification")
    logger.info("-" * 40)
    
    models_dir = Path(__file__).parent / "models"
    for model_file in models_dir.glob("*.pt"):
        size_kb = model_file.stat().st_size / 1024
        logger.info(f"  Model: {model_file.name} ({size_kb:.1f} KB)")
    
    logger.info("\n" + "=" * 70)
    logger.info("  MEDUSA RETRAINING COMPLETE")
    logger.info("  All AGI subsystems trained and saved.")
    logger.info("  Medusa now knows:")
    logger.info("    - Her name is Medusa")
    logger.info("    - She was created by D Hargreaves (Roylepython)")
    logger.info(f"    - The entire McMaker ecosystem ({len(mcmaker_entries)} knowledge entries)")
    logger.info("    - All {len(MEDUSA_IDENTITY['agi_systems'])} AGI subsystems are active")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
