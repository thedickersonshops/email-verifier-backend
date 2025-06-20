import os, requests
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import random
from werkzeug.utils import secure_filename
import tempfile, csv

app = Flask(__name__)
CORS(app)

# Backend servers
BACKENDS = [
    "http://127.0.0.1:10000",  # Railway itself
    "http://ec2-44-201-247-203.compute-1.amazonaws.com:10000",  # AWS 1
    "http://ec2-52-53-243-135.us-west-1.compute.amazonaws.com:10000"  # AWS 2
]

# Disposable domains
DISPOSABLE_DOMAINS = set([
    "mailinator.com", "yopmail.com", "10minutemail.com", "guerrillamail.com",
    "getnada.com", "tempmail.com", "trashmail.com", "dispostable.com",
    "fakeinbox.com", "moakt.com", "emailondeck.com", "dropmail.me"
])

def is_disposable(email):
    domain = email.split('@')[-1].lower()
    return domain in DISPOSABLE_DOMAINS

@app.route('/')
def home():
    return '✅ Railway Load Balancer Backend is Running!'

@app.route('/verify', methods=['POST'])
def verify():
    backend = random.choice(BACKENDS)
    try:
        uploaded_file = request.files['file']
        proxy = request.form.get('proxy', '')
        proxy_user = request.form.get('proxyUser', '')
        proxy_pass = request.form.get('proxyPass', '')

        # Read emails and intercept disposable ones
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        uploaded_file.save(temp_file.name)

        disposable_emails = []
        valid_emails = []

        with open(temp_file.name, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row: continue
                email = row[0].strip()
                if is_disposable(email):
                    disposable_emails.append(email)
                else:
                    valid_emails.append(email)

        if not valid_emails:
            os.unlink(temp_file.name)
            def stream_disposables():
                for email in disposable_emails:
                    yield f"data: {{"f'\"email\": \"{email}\", \"status\": \"Invalid (Disposable)\"'}}\n\n"
            return Response(stream_disposables(), mimetype='text/event-stream')

        # Write valid emails to a new temporary CSV
        with open(temp_file.name, 'w', newline='') as f:
            writer = csv.writer(f)
            for email in valid_emails:
                writer.writerow([email])

        # Proxy only valid ones to backend
        with open(temp_file.name, 'rb') as f:
            files = {'file': (secure_filename(uploaded_file.filename), f)}
            data = {
                'proxy': proxy,
                'proxyUser': proxy_user,
                'proxyPass': proxy_pass
            }
            resp = requests.post(f"{backend}/verify", files=files, data=data, stream=True)

            def generate():
                # Stream disposables first
                for email in disposable_emails:
                    yield f"data: {{"f'\"email\": \"{email}\", \"status\": \"Invalid (Disposable)\"'}}\n\n"
                # Then backend results
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

    