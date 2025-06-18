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
    try:
        file = request.files.get('file')
        if not file:
            return jsonify({'error': 'No file uploaded'}), 400

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.reader(stream)
        results = []

        for row in reader:
            if not row:
                continue  # skip empty lines
            email = row[0].strip()
            if not email:
                continue

            if not is_valid_syntax(email):
                status = 'Invalid Syntax'
            elif not has_mx(email.split('@')[1]):
                status = 'Invalid Domain'
            elif not smtp_check(email):
                status = 'SMTP Failed'
            else:
                status = 'Valid'

            results.append({'email': email, 'status': status})

        return jsonify(results), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
