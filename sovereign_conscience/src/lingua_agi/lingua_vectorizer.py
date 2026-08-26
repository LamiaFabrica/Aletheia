import os
import json
import tempfile
import subprocess
import numpy as np
import hashlib
import struct

# The ONLY model this pipeline may use: Athenea (Qwen3 4B, embedding dim 2560).
DEFAULT_MODEL_PATH = r"C:\McMaker Projects\Projects\Athenea\GGUF\athenea-4b-coding-Q5_K_M.gguf"
EXPECTED_EMBEDDING_LENGTH = 2560
FAIL_CLOSED_MESSAGE = "[FAIL-CLOSED] Model embd != 2560 — refusing to proceed"


def _read_gguf_string(f):
    """Read a GGUF length-prefixed string (u64 length + UTF-8 bytes)."""
    length = struct.unpack('<Q', f.read(8))[0]
    return f.read(length).decode('utf-8', 'replace')


def _skip_gguf_value(f, value_type):
    """Skip a GGUF metadata value of the given type (GGUFValueType enum)."""
    if value_type == 8:          # string
        _read_gguf_string(f)
    elif value_type == 9:        # array
        elem_type = struct.unpack('<I', f.read(4))[0]
        count = struct.unpack('<Q', f.read(8))[0]
        for _ in range(count):
            _skip_gguf_value(f, elem_type)
    elif value_type in (0, 1, 7):      # u8 / i8 / bool
        f.read(1)
    elif value_type in (2, 3):         # u16 / i16
        f.read(2)
    elif value_type in (4, 5, 6):      # u32 / i32 / f32
        f.read(4)
    elif value_type in (10, 11, 12):   # u64 / i64 / f64
        f.read(8)
    else:
        raise struct.error("Unknown GGUF value type: %d" % value_type)


def _gguf_embedding_length(model_path):
    """
    Parse the GGUF header and return the model's embedding dimension
    (first '*embedding_length' metadata key), or None if undeterminable.
    """
    try:
        with open(model_path, 'rb') as f:
            if f.read(4) != b'GGUF':
                return None
            struct.unpack('<I', f.read(4))      # version
            struct.unpack('<Q', f.read(8))      # tensor_count
            kv_count = struct.unpack('<Q', f.read(8))[0]
            for _ in range(kv_count):
                key = _read_gguf_string(f)
                value_type = struct.unpack('<I', f.read(4))[0]
                if key.endswith('embedding_length') and value_type in (4, 5):
                    raw = f.read(4)
                    if len(raw) != 4:
                        return None
                    return int(struct.unpack('<I' if value_type == 4 else '<i', raw)[0])
                _skip_gguf_value(f, value_type)
            return None
    except (OSError, struct.error):
        return None


class LinguaVectorizer:
    """
    Transforms text into 8-dimensional geometric Lingua vectors
    by calling the C++ codex_engine natively.

    Dimension gate: the engine model MUST be the Athenea GGUF (Qwen3 4B,
    embedding dim 2560). Any other model — or a missing one — is refused
    (fail-closed). No synthetic/HashingVectorizer fallback exists.
    """
    def __init__(self, exe_path=None, model_path=None):
        self.exe_path = exe_path or r"C:\McMaker Projects\Projects\CODEX\build\codex_engine.exe"
        self.model_path = model_path or DEFAULT_MODEL_PATH

    def _verify_model(self):
        """Fail-closed model gate: file exists AND embedding dim == 2560."""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                "[FAIL-CLOSED] Model not found at %s" % self.model_path
            )
        embd = _gguf_embedding_length(self.model_path)
        if embd is None or embd != EXPECTED_EMBEDDING_LENGTH:
            print(FAIL_CLOSED_MESSAGE)
            raise SystemExit(1)

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        """
        Takes a list of texts, writes them to a temp file, runs the codex_engine,
        and returns a numpy array of shape (len(X), 8).
        """
        if not X:
            return np.zeros((0, 8))

        self._verify_model()  # dimension gate — fails closed on missing/wrong model

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
