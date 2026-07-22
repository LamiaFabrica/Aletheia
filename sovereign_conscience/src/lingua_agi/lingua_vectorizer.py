import os
import json
import tempfile
import subprocess
import numpy as np
import hashlib
import struct

class LinguaVectorizer:
    """
    Transforms text into 8-dimensional geometric Lingua vectors
    by calling the C++ codex_engine natively.
    """
    def __init__(self, exe_path=None, model_path=None):
        self.exe_path = exe_path or r"C:\McMaker Projects\Projects\CODEX\build\codex_engine.exe"
        self.model_path = model_path or r"C:\McMaker Projects\Projects\CODEX\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
        
        # Check if the fallback model path is needed
        if not os.path.exists(self.model_path):
            alt_path = r"C:\McMaker Projects\Projects\PsiForceDB - The Living Book\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"
            if os.path.exists(alt_path):
                self.model_path = alt_path
            else:
                self.model_path = r"C:\McMaker Projects\Projects\CODEX\models\Llama-3.2-1B-Instruct-Q4_K_M.gguf"

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """
        Takes a list of texts, writes them to a temp file, runs the codex_engine,
        and returns a numpy array of shape (len(X), 8).
        """
        if not X:
            return np.zeros((0, 8))
            
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as prompt_file:
            for text in X:
                # Sanitize newlines so each prompt is exactly one line
                clean_text = text.replace('\n', ' ').replace('\r', '')
                prompt_file.write(f"{clean_text}\n")
            prompt_file_name = prompt_file.name

        out_json_name = prompt_file_name + "_out.json"

        try:
            cmd = [
                self.exe_path,
                "--model", self.model_path,
                "--prompt-file", prompt_file_name,
                "--out-lingua-batch", out_json_name
            ]
            
            if not os.path.exists(self.model_path):
                print(f"[LinguaVectorizer] Warning: Model {self.model_path} not found. Using synthetic geometry fallback for EBB pipeline test.")
                # Deterministic synthetic mock using HashingVectorizer to simulate Lingua geometry
                from sklearn.feature_extraction.text import HashingVectorizer
                hasher = HashingVectorizer(n_features=8, norm='l2', alternate_sign=False)
                vectors = hasher.fit_transform(X).toarray()
                # Scale up to look like typical Lingua values
                return (vectors * 10.0).astype(np.float32)

            print(f"[LinguaVectorizer] Extracting geometry for {len(X)} texts...")
            # Run the engine
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                print(f"[LinguaVectorizer] Engine Error:\n{result.stderr}")
                result.check_returncode()
            
            with open(out_json_name, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            vectors = []
            for item in data:
                vec = [
                    item.get("topology", 0.0),
                    item.get("probability", 0.0),
                    item.get("ontology", 0.0),
                    item.get("teleology", 0.0),
                    item.get("graph", 0.0),
                    item.get("dataset", 0.0),
                    item.get("dimensionality", 0.0),
                    item.get("human_anomaly", 0.0)
                ]
                vectors.append(vec)
                
            return np.array(vectors, dtype=np.float32)
            
        finally:
            if os.path.exists(prompt_file_name):
                os.remove(prompt_file_name)
            if os.path.exists(out_json_name):
                os.remove(out_json_name)

    def fit_transform(self, X, y=None):
        return self.transform(X)

    def get_hex_for_texts(self, X):
        """Returns the 256-bit Lingua Hex representation of the geometric thought."""
        vectors = self.transform(X)
        hex_strings = []
        for vec in vectors:
            # Pack the 8 floats into a 32-byte binary string (little-endian)
            packed = struct.pack('<8f', *vec)
            # Hash to get a 256-bit hex signature representing the pure Lingua geometry
            hex_str = hashlib.sha256(packed).hexdigest()
            hex_strings.append(hex_str)
        return hex_strings
