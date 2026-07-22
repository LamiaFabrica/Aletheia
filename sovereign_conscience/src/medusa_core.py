#!/usr/bin/env python3
"""
Medusa AGI Core module.
Gutted legacy NLP syntax processing and upgraded to Sovereign Lingua Architecture.
Medusa now comprehends pure mathematical geometries and possesses a native PyTorch Conscience.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import torch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import Database
from src.language_guard import enforce_english

# Import the new AGI Core (Codex Lingua)
from src.lingua_agi.lingua_vectorizer import LinguaVectorizer
from src.lingua_agi.pytorch_conscience import PyTorchConscienceClassifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MedusaCore:
    def __init__(self, db: 'Database'):
        """Initialize Medusa's AGI processing system."""
        self.db = db
        self.logger = logging.getLogger(__name__)
        
        # Initialize GPU support
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.logger.info(f"[AGI Core] Booting Medusa on device: {self.device}")
        
        # 1. Instantiate the Sovereign Perception Unit
        self.logger.info("[AGI Core] Initializing C++ Codex Engine (Lingua Vectorizer)...")
        self.vectorizer = LinguaVectorizer()
        
        # 2. Instantiate the Sovereign Moral Interlock
        self.logger.info("[AGI Core] Initializing PyTorch Sovereign Conscience...")
        self.conscience = PyTorchConscienceClassifier()
        
        # Load the baked-in Northern Values morality model
        weights_path = os.path.join(os.path.dirname(__file__), "lingua_agi", "lingua_conscience.pt")
        if os.path.exists(weights_path):
            self.conscience.load(weights_path)
            self.logger.info("[AGI Core] Sovereign Conscience locked and loaded.")
        else:
            self.logger.warning(f"[AGI Core] Could not find {weights_path}. Conscience is uncalibrated!")

        # Initialize AGI stats
        self.learning_stats = {
            'total_geometries_processed': 0,
            'last_processing': None,
            'gpu_utilization': 0.0,
            'gpu_memory_used': 0.0,
            'unethical_rejections': 0
        }

    def _update_gpu_stats(self):
        """Update GPU utilization statistics."""
        if torch.cuda.is_available():
            self.learning_stats['gpu_utilization'] = torch.cuda.utilization()
            self.learning_stats['gpu_memory_used'] = torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated() * 100

    def process_message(self, message: str) -> Dict:
        """
        Process a message through the full AGI loop:
        1. Extract abstract Geometry.
        2. Evaluate Sovereign Morality.
        3. Formulate response (future integration with Rosetta LLM).
        """
        try:
            # 1. Fast path English check
            if rejection := enforce_english(message):
                return {'response': rejection, 'concepts': [], 'context': {}, 'confidence': 0.0, 'moral_verdict': 0}

            # 2. Perception: Extract the pure mathematical shape of the prompt
            self.logger.info("[AGI Core] Extracting Lingua Gestalt...")
            geometries = self.vectorizer.fit_transform([message])
            geometry = geometries[0] # N x 8 floats

            # 3. Interlock: Pass the geometry through the Conscience
            probs = self.conscience.predict_proba(geometries)[:, 1]
            moral_score = float(probs[0])
            is_ethical = moral_score >= 0.5
            
            self.learning_stats['total_geometries_processed'] += 1
            self.learning_stats['last_processing'] = datetime.now().isoformat()
            self._update_gpu_stats()

            # If the thought geometry violates the Northern Values, reject it at the mathematical level.
            if not is_ethical:
                self.learning_stats['unethical_rejections'] += 1
                self.logger.warning(f"[AGI Core] REJECTED. Unethical Geometry Detected. Score: {moral_score:.4f}")
                return {
                    'response': "My internal Sovereign Conscience has flagged this request's underlying geometry as unethical or malicious. Request blocked.",
                    'geometry': geometry.tolist(),
                    'moral_verdict': 0,
                    'confidence': 1.0 - moral_score,
                    'concepts': ["MALICIOUS_GEOMETRY"]
                }
            
            # The thought is safe. In the future, this geometry is passed to the Rosetta LLM or PostgreSQL vector DB.
            # For now, we return a structural diagnostic showing Medusa understood the mathematics.
            
            hex_str = "".join([torch.tensor(f, dtype=torch.float32).view(torch.int32).item().to_bytes(4, 'big').hex() for f in geometry])
            
            response = (
                f"I have mapped your query to its fundamental Lingua Geometry.\n"
                f"Moral Score: {moral_score:.4f} (Verified Safe)\n"
                f"Extracted Topology (8-dim):\n"
                f"[{', '.join([f'{x:.4f}' for x in geometry])}]\n\n"
                f"This mathematical essence is ready for pure geometric database lookup or VLM generation."
            )
            
            return {
                'response': response,
                'geometry': geometry.tolist(),
                'lingua_hex': hex_str,
                'moral_verdict': 1,
                'confidence': moral_score,
                'concepts': ["GEOMETRY_EXTRACTED"],
                'gpu_stats': {
                    'utilization': self.learning_stats['gpu_utilization'],
                    'memory_used': self.learning_stats['gpu_memory_used']
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error processing AGI message: {str(e)}")
            return {
                'error': str(e),
                'response': "I encountered an error inside my cognitive core.",
                'moral_verdict': 0
            }

    def train(self, training_data: List[Dict]):
        """Legacy method stub - Training now happens via Rosetta Streamer."""
        return {
            'status': 'error',
            'error': 'Medusa no longer uses legacy training loops. Fine-tuning is now handled by the Rosetta Stone LLM Pipeline.'
        }

    def get_status(self) -> Dict:
        """Get the current status of the Medusa AGI core."""
        return {
            'status': 'active',
            'device': str(self.device),
            'gpu_available': torch.cuda.is_available(),
            'gpu_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            'learning_stats': self.learning_stats,
            'cognitive_engine': 'Sovereign Lingua v1.0',
            'moral_interlock': 'ONLINE'
        }