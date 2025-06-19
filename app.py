import os
import re
import csv
import io
import json
import time
import smtplib
import socket
import dns.resolver
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 1. Syntax validation
def is_valid_syntax(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

# 2. MX record check
def get_mx_records(domain):
    try:
        return dns.resolver.resolve(domain, 'MX')
    except:
        return None

# 3. SMTP check with fallback and timeout
def smtp_check(email, mx_records, fallback_ip=None):
    for mx in sorted(mx_records, key=lambda r: r.preference):
        try:
            mail_server = str(mx.exchange)
            server = smtplib.SMTP(timeout=10)
            server.connect(mail_server)
            server.helo('test.com')
            server.mail('verify@test.com')
            code, _ = server.rcpt(email)
            server.quit()

            if code == 250:
                return 'Valid'
            elif code in (451, 452, 550, 551, 552, 553):
                return 'Invalid'
            else:
                return 'Unknown'
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout):
            continue
        except:
            continue

    # Fallback IP (optional)
    if fallback_ip:
        try:
            server = smtplib.SMTP(fallback_ip, timeout=10)
            server.helo('test.com')
            server.mail('verify@test.com')
            code, _ = server.rcpt(email)
            server.quit()
            return 'Valid (Fallback)' if code == 250 else 'Invalid (Fallback)'
        except:
            return 'Fallback Failed'

    return 'SMTP Failed'

# 4. Main Verification Endpoint (with streaming)
@app.route('/verify', methods=['POST'])
def verify_emails_stream():
    file = request.files['file']
    stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
    reader = csv.reader(stream)

    def generate():
        for row in reader:
            email = row[0].strip()

            if not is_valid_syntax(email):
                status = 'Invalid Syntax'
            else:
                domain = email.split('@')[1]
                mx_records = get_mx_records(domain)
                if not mx_records:
                    status = 'Invalid Domain'
                else:
                    status = smtp_check(email, mx_records, fallback_ip='8.8.8.8')

            result = {'email': email, 'status': status}
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.2)

    return Response(generate(), mimetype='text/event-stream')

# 5. Root route for Railway health check
@app.route('/')
def home():
    return '✅ Email Verifier API is Running!'

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
