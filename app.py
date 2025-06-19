import os
import re
import csv
import io
import json
import time
import smtplib
import dns.resolver
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 1. Basic Syntax Check
def is_valid_syntax(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

# 2. DNS MX Record Check
def has_mx(domain):
    try:
        records = dns.resolver.resolve(domain, 'MX')
        return records
    except:
        return None

# 3. SMTP Verification with smarter fallback
def smtp_check(email, mx_records):
    domain = email.split('@')[1]
    for mx in sorted(mx_records, key=lambda r: r.preference):
        try:
            mail_server = str(mx.exchange)
            server = smtplib.SMTP(mail_server, 25, timeout=10)
            server.set_debuglevel(0)
            server.helo('test.com')
            server.mail('verify@test.com')
            code, _ = server.rcpt(email)
            server.quit()

            if code == 250:
                return 'Valid'
            elif code in (451, 452, 550):
                return 'Invalid'
            else:
                return 'Unknown'
        except Exception:
            continue
    return 'SMTP Failed'

# 4. Main Verification Endpoint
@app.route('/verify', methods=['POST'])
def verify_emails_stream():
    file = request.files['file']
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    reader = csv.reader(stream)

    def generate():
        for row in reader:
            email = row[0].strip()
            if not is_valid_syntax(email):
                status = 'Invalid Syntax'
            else:
                domain = email.split('@')[1]
                mx_records = has_mx(domain)
                if not mx_records:
                    status = 'Invalid Domain'
                else:
                    status = smtp_check(email, mx_records)

            result = {'email': email, 'status': status}
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.2)  # Prevent backend overload

    return Response(generate(), mimetype='text/event-stream')

# 5. Basic homepage route for Railway or Render
@app.route('/')
def home():
    return '✅ Email Verifier API is Running!'

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
