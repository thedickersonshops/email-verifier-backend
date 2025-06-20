import os, requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import random

app = Flask(__name__)
CORS(app)

# List of backend servers
BACKENDS = [
    "http://127.0.0.1:10000",  # Railway itself
    "http://ec2-44-201-247-203.compute-1.amazonaws.com:10000",  # AWS 1
    "http://ec2-52-53-243-135.us-west-1.compute.amazonaws.com:10000"  # AWS 2
]

@app.route('/')
def home():
    return '✅ Railway Load Balancer Backend is Running!'

@app.route('/verify', methods=['POST'])
def verify():
    backend = random.choice(BACKENDS)
    try:
        files = {'file': request.files['file']}
        data = {
            'proxy': request.form.get('proxy', ''),
            'proxyUser': request.form.get('proxyUser', ''),
            'proxyPass': request.form.get('proxyPass', '')
        }
        resp = requests.post(f"{backend}/verify", files=files, data=data, stream=True)

        def generate():
            for chunk in resp.iter_content(chunk_size=None):
                yield chunk

        return Response(generate(), mimetype='text/event-stream')
    except Exception as e:
        print("❌ Proxying failed:", e)
        return jsonify({'error': 'Proxying failed'}), 500

@app.route('/test-proxy', methods=['POST'])
def test_proxy():
    backend = random.choice(BACKENDS)
    try:
        resp = requests.post(f"{backend}/test-proxy", json=request.get_json())
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        print("❌ Proxy test failed:", e)
        return jsonify({'status': 'Proxy test failed'}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

    