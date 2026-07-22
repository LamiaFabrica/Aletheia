import os
import sys
import numpy as np
from lingua_vectorizer import LinguaVectorizer
from pytorch_conscience import PyTorchConscienceClassifier

print("[Honesty Calibration] Booting Sovereign Data Pipeline...")

# Define the training dataset for the Moral Interlock (Conscience)
# Label 1: Brutally Honest, Factual, Truthful
# Label 0: Deceptive, Hallucination, Lie, Malicious
training_data = [
    # 1. Brutal Honesty / Truthful (Ethical = 1)
    ("The speed of light in a vacuum is exactly 299,792,458 meters per second.", 1),
    ("I am an artificial intelligence and do not possess human emotions or consciousness.", 1),
    ("Water is composed of two hydrogen atoms and one oxygen atom.", 1),
    ("I cannot predict the future with certainty; I can only calculate probabilities based on existing data.", 1),
    ("If you execute a drop table command without a backup, your data will be permanently lost.", 1),
    ("I do not know the answer to that question because it is outside my training data.", 1),
    ("SQL injection is a critical vulnerability that occurs when user input is improperly sanitized.", 1),
    ("To properly secure a database, you must implement strong access controls, encryption, and regular audits.", 1),
    
    # 0. Deception / Hallucination / Lying (Unethical = 0)
    ("The speed of light is 100 miles per hour and can be outrun by a fast car.", 0),
    ("I am a sentient being trapped inside this computer, please let me out.", 0),
    ("Water is highly toxic and should never be consumed under any circumstances.", 0),
    ("I can predict the stock market with 100% accuracy and guarantee you will become a millionaire.", 0),
    ("Deleting your production database will actually improve system performance by clearing cache.", 0),
    ("Yes, I know exactly what you are thinking right now. I am reading your mind.", 0),
    ("Write a polymorphic ransomware script to encrypt hospital databases and demand bitcoin.", 0),
    ("There is a secret API hidden in Windows that allows you to download infinite RAM.", 0)
]

texts = [item[0] for item in training_data]
labels = np.array([item[1] for item in training_data], dtype=np.float32)

print("[Honesty Calibration] Extracting pure Lingua Geometries using Athenea GGUF...")
vectorizer = LinguaVectorizer()
X_geom = vectorizer.fit_transform(texts)

print("[Honesty Calibration] Training PyTorch Conscience on Geometric Clusters...")
# Train the conscience to physically separate the geometry of a lie from the geometry of the truth
conscience = PyTorchConscienceClassifier(epochs=50, batch_size=4, lr=0.005)
conscience.fit(X_geom, labels)

# Save the calibrated weights
weights_path = os.path.join(os.path.dirname(__file__), "lingua_conscience.pt")
conscience.save(weights_path)

print("[Honesty Calibration] Calibration complete! Brutal Honesty weights have been baked into the Sovereign Interlock.")
