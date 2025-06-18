from flask import Flask, request, jsonify
from flask_cors import CORS
import re, dns.resolver, smtplib
import csv, io

app = Flask(__name__)
CORS(app)

def is_valid_syntax(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def has_mx(domain):
    try:
        dns.resolver.resolve(domain, 'MX')
        return True
    except:
        return False

def smtp_check(email):
    domain = email.split('@')[1]
    try:
        mx_record = str(dns.resolver.resolve(domain, 'MX')[0].exchange)
        server = smtplib.SMTP(timeout=10)
        server.connect(mx_record)
        server.helo()
        server.mail('test@example.com')
        code, _ = server.rcpt(email)
        server.quit()
        return code == 250
    except:
        return False

@app.route('/verify', methods=['POST'])
def verify_emails():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    except Exception as e:
        return jsonify({'error': f'File decoding failed: {str(e)}'}), 400

    reader = csv.reader(stream)
    results = []

    for row in reader:
        if len(row) == 0:
            continue  # skip empty rows
        email = row[0].strip()
        if not email:
            continue
        print(f"Checking: {email}")  # debug print

        if not is_valid_syntax(email):
            status = 'Invalid Syntax'
        elif not has_mx(email.split('@')[1]):
            status = 'Invalid Domain'
        elif not smtp_check(email):
            status = 'SMTP Failed'
        else:
            status = 'Valid'

        results.append({'email': email, 'status': status})

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
