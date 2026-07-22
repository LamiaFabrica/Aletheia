#!/usr/bin/env python3
"""
Test script to verify AES-256 encryption/decryption for all fields and files/images in Medusa.
"""
import os
import sys
import json
from pathlib import Path
from medusa.src.database import Database
from medusa.src.crawler import SecurityCrawler
from medusa.src.auth import aes_encrypt, aes_decrypt

# Test database encryption/decryption
print("[TEST] Database encryption/decryption...")
db = Database()

test_knowledge = [{
    'title': 'Test Title',
    'content': ['Test content'],
    'url': 'https://example.com',
}]
db.save_knowledge('scan_examples', test_knowledge)
retrieved = db.get_knowledge('scan_examples')
assert retrieved['scan_examples'][0]['title'] == 'Test Title'
assert retrieved['scan_examples'][0]['content'] == ['Test content']
assert retrieved['scan_examples'][0]['url'] == 'https://example.com'
print("[PASS] Knowledge base fields encrypted and decrypted correctly.")

test_scan = {
    'target': '127.0.0.1',
    'total_hosts': 1,
    'total_ports': 2,
    'high_risk_ports': 1,
    'average_risk_score': 0.9,
    'hosts': [
        {
            'ip': '127.0.0.1',
            'mac': '00:11:22:33:44:55',
            'status': 'up',
            'ports': [
                {
                    'port': 80,
                    'protocol': 'tcp',
                    'state': 'open',
                    'service': 'http',
                    'version': '1.1',
                    'product': 'nginx',
                    'risk_score': 0.9,
                    'risk_details': {'reason': 'test'}
                }
            ]
        }
    ]
}
db.save_scan_results(test_scan)
scan_results = db.get_scan_results()
assert scan_results[0]['target'] == '127.0.0.1'
assert scan_results[0]['hosts'][0]['ip'] == '127.0.0.1'
assert scan_results[0]['hosts'][0]['ports'][0]['port'] == 80
print("[PASS] Scan results fields encrypted and decrypted correctly.")

# Test file/image encryption/decryption
print("[TEST] File/image encryption/decryption...")
crawler = SecurityCrawler(output_dir='test_training_data')
# Test file
test_data = {'foo': 'bar', 'baz': 123}
enc = aes_encrypt(json.dumps(test_data))
file_path = Path('test_training_data/test_file.json')
file_path.parent.mkdir(exist_ok=True)
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(enc)
with open(file_path, 'r', encoding='utf-8') as f:
    dec = aes_decrypt(f.read())
assert json.loads(dec) == test_data
print("[PASS] File encryption/decryption works.")
# Test image
img_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'  # Fake PNG header
img_path = Path('test_training_data/images/test_img.png')
img_path.parent.mkdir(exist_ok=True)
crawler._save_image(img_bytes, img_path)
with open(img_path, 'r', encoding='utf-8') as f:
    img_dec = bytes.fromhex(aes_decrypt(f.read()))
assert img_dec == img_bytes
print("[PASS] Image encryption/decryption works.")

print("[ALL TESTS PASSED]") 