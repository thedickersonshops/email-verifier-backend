import os
import re
import csv
import io
import json
import time
import smtplib
import socket
import dns.resolver
import requests
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 1. Basic syntax validation
def is_valid_syntax(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

# 2. MX lookup
def get_mx_records(domain):
    try:
        return dns.resolver.resolve(domain, 'MX')
    except:
        return None

# 3. SMTP verification with timeout
def smtp_check(email, mx_records):
    for mx in sorted(mx_records, key=lambda r: r.preference):
        try:
            mail_server = str(mx.exchange)
            server = smtplib.SMTP(mail_server, 25, timeout=10)
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
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, socket.timeout, Exception):
            continue
    return 'Unknown'

# 4. Fallback API validation (if SMTP is inconclusive)
def fallback_api_check(email):
    # ✅ Kickbox
    try:
        r = requests.get(
            f'https://api.kickbox.com/v2/verify?email={email}&apikey=live_1671f87353c542369ea0ff1f8370979d6dce0de0c279dd1b3e35969e22efbf3c'
        ).json()
        if r.get('result') == 'deliverable':
            return 'Valid (Kickbox)'
        elif r.get('result') == 'undeliverable':
            return 'Invalid (Kickbox)'
    except:
        pass

    # ✅ Verimail
    try:
        r = requests.get(
            f'https://verimail.io/api/v1/verify?email={email}&key=A602A4C42B364360B14E0A9321AA44BF'
        ).json()
        if r.get("deliverable") is True:
            return "Valid (Verimail)"
        elif r.get("deliverable") is False:
            return "Invalid (Verimail)"
    except:
        pass

    # ✅ MailboxLayer
    try:
        r = requests.get(
            f'http://apilayer.net/api/check?access_key=44eaa3ddd12c471855eda9ccc6fc82d5&email={email}&smtp=1&format=1'
        ).json()
        if r.get("smtp_check") and r.get("format_valid"):
            return "Valid (MailboxLayer)"
        else:
            return "Invalid (MailboxLayer)"
    except:
        pass

    return "Fallback Failed"

# 5. Email Verification Streaming Endpoint
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
                    status = smtp_check(email, mx_records)
                    if status == 'Unknown':
                        status = fallback_api_check(email)

            result = {'email': email, 'status': status}
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.2)  # UI pacing

    return Response(generate(), mimetype='text/event-stream')

# 6. Homepage check for Railway/Vercel
@app.route('/')
def home():
    return '✅ Email Verifier Backend is Live!'

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

