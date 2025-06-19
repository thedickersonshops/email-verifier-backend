import os, re, csv, io, json, time, smtplib, socket, dns.resolver, requests, socks
from flask import Flask, request, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------[ Settings ]---------
SOCKS_PROXY = os.getenv("SOCKS_PROXY")  # e.g., 127.0.0.1:9050
KICKBOX_KEY = os.getenv("KICKBOX_KEY")
VERIMAIL_KEY = os.getenv("VERIMAIL_KEY")
MAILBOXLAYER_KEY = os.getenv("MAILBOXLAYER_KEY")

# ---------[ Email Checks ]---------
def is_valid_syntax(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def get_mx_records(domain):
    try:
        return dns.resolver.resolve(domain, 'MX')
    except:
        return None

def smtp_check(email, mx_records, use_proxy=False):
    for mx in sorted(mx_records, key=lambda r: r.preference):
        try:
            if use_proxy and SOCKS_PROXY:
                proxy_host, proxy_port = SOCKS_PROXY.split(":")
                socks.setdefaultproxy(socks.SOCKS5, proxy_host, int(proxy_port))
                socks.wrapmodule(smtplib)

            server = smtplib.SMTP(timeout=10)
            server.connect(str(mx.exchange))
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
        except Exception:
            continue
    return 'Unknown'

def fallback_api_check(email):
    # Kickbox
    try:
        r = requests.get(f'https://api.kickbox.com/v2/verify?email={email}&apikey={KICKBOX_KEY}').json()
        if r.get("result") == "deliverable":
            return "Valid (Kickbox)"
        elif r.get("result") == "undeliverable":
            return "Invalid (Kickbox)"
    except: pass

    # Verimail
    try:
        r = requests.get(f'https://verimail.io/api/v1/verify?email={email}&key={VERIMAIL_KEY}').json()
        if r.get("deliverable") is True:
            return "Valid (Verimail)"
        elif r.get("deliverable") is False:
            return "Invalid (Verimail)"
    except: pass

    # MailboxLayer
    try:
        r = requests.get(f'http://apilayer.net/api/check?access_key={MAILBOXLAYER_KEY}&email={email}&smtp=1&format=1').json()
        if r.get("smtp_check") and r.get("format_valid"):
            return "Valid (MailboxLayer)"
        else:
            return "Invalid (MailboxLayer)"
    except: pass

    return "Fallback Failed"

# ---------[ API Endpoint ]---------
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
                    status = smtp_check(email, mx_records, use_proxy=True)
                    if status == "Unknown":
                        status = fallback_api_check(email)

            result = {'email': email, 'status': status}
            print(result)
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.2)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/')
def home():
    return '✅ Email Verifier API with SOCKS + Fallback is Running!'

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
