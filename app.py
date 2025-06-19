import os
from flask import Flask, request, Response
from flask_cors import CORS
import re, dns.resolver, smtplib, csv, io, json, time

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
    try:
        domain = email.split('@')[1]
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

@app.route('/')
def home():
    return "✅ Email Verifier Backend is Running. Use POST /verify to check emails."

@app.route('/verify', methods=['POST'])
def verify_emails_stream():
    file = request.files['file']
    stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
    reader = csv.reader(stream)

    def generate():
        for row in reader:
            email = row[0]
            if not is_valid_syntax(email):
                status = 'Invalid Syntax'
            elif not has_mx(email.split('@')[1]):
                status = 'Invalid Domain'
            elif not smtp_check(email):
                status = 'SMTP Failed'
            else:
                status = 'Valid'
            result = {'email': email, 'status': status}
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.5)  # Simulate progress

    return Response(generate(), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

    