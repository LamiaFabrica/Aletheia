import os
import sys
import subprocess
import threading
import time
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

MEDUSA_CMD = [sys.executable, 'run.py']
MEDUSA_DIR = os.path.join(os.path.dirname(__file__))
medusa_process = None
process_lock = threading.Lock()


def is_running():
    global medusa_process
    return medusa_process is not None and medusa_process.poll() is None


def start_medusa():
    global medusa_process
    with process_lock:
        if is_running():
            return False  # Already running
        medusa_process = subprocess.Popen(MEDUSA_CMD, cwd=MEDUSA_DIR)
        return True


def stop_medusa():
    global medusa_process
    with process_lock:
        if is_running():
            medusa_process.terminate()
            try:
                medusa_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                medusa_process.kill()
            medusa_process = None
            return True
        return False


@app.route('/start', methods=['POST'])
def api_start():
    if request.remote_addr != '127.0.0.1':
        abort(403)
    started = start_medusa()
    return jsonify({'status': 'started' if started else 'already running'})


@app.route('/restart', methods=['POST'])
def api_restart():
    if request.remote_addr != '127.0.0.1':
        abort(403)
    stopped = stop_medusa()
    started = start_medusa()
    return jsonify({'status': 'restarted' if started else 'failed to start'})


@app.route('/status', methods=['GET'])
def api_status():
    return jsonify({'running': is_running()})


def run_watchdog():
    app.run(host='127.0.0.1', port=5050, debug=False)

if __name__ == '__main__':
    run_watchdog() 