import os, re, csv, io, json, time, smtplib, socket, dns.resolver, requests, socks
from flask import Flask, request, Response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------[ API Keys from Railway Env ]---------
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

def smtp_check(email, mx_records, proxy=None, proxy_user=None, proxy_pass=None):
    original_socket = socket.socket  # backup original socket

    # Setup proxy if given
    if proxy:
        try:
            ip, port = proxy.split(":")
            port = int(port)
            if proxy_user and proxy_pass:
                socks.set_default_proxy(socks.SOCKS5, ip, port, True, proxy_user, proxy_pass)
            else:
                socks.set_default_proxy(socks.SOCKS5, ip, port)
            socket.socket = socks.socksocket
        except Exception as e:
            print("Proxy setup error:", e)

    for mx in sorted(mx_records, key=lambda r: r.preference):
        try:
            server = smtplib.SMTP(timeout=10)
            server.connect(str(mx.exchange))
            server.helo('test.com')
            server.mail('verify@test.com')
            code, _ = server.rcpt(email)
            server.quit()
            socket.socket = original_socket  # Restore socket after use

            if code == 250:
                return 'Valid'
            elif code in (451, 452, 550, 551, 552, 553):
                return 'Invalid'
            else:
                return 'Unknown'
        except:
            continue

    socket.socket = original_socket
    return 'Unknown'

def fallback_api_check(email):
    try:
        r = requests.get(f'https://api.kickbox.com/v2/verify?email={email}&apikey={KICKBOX_KEY}').json()
        if r.get("result") == "deliverable":
            return "Valid (Kickbox)"
        elif r.get("result") == "undeliverable":
            return "Invalid (Kickbox)"
    except: pass

    try:
        r = requests.get(f'https://verimail.io/api/v1/verify?email={email}&key={VERIMAIL_KEY}').json()
        if r.get("deliverable") is True:
            return "Valid (Verimail)"
        elif r.get("deliverable") is False:
            return "Invalid (Verimail)"
    except: pass

    try:
        r = requests.get(f'http://apilayer.net/api/check?access_key={MAILBOXLAYER_KEY}&email={email}&smtp=1&format=1').json()
        if r.get("smtp_check") and r.get("format_valid"):
            return "Valid (MailboxLayer)"
        else:
            return "Invalid (MailboxLayer)"
    except: pass

    return "Fallback Failed"

# ---------[ Streaming Verification Route ]---------
@app.route('/verify', methods=['POST'])
def verify_emails_stream():
    file = request.files['file']
    proxy = request.form.get('proxy')
    proxy_user = request.form.get('proxyUser')  # match frontend keys!
    proxy_pass = request.form.get('proxyPass')

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
                    status = smtp_check(email, mx_records, proxy, proxy_user, proxy_pass)
                    if status == 'Unknown':
                        status = fallback_api_check(email)

            result = {'email': email, 'status': status}
            print(result)
            yield f"data: {json.dumps(result)}\n\n"
            time.sleep(0.2)

    return Response(generate(), mimetype='text/event-stream')

# ---------[ Proxy Test Endpoint ]---------
@app.route('/test-proxy', methods=['POST'])
def test_proxy():
    data = request.get_json()
    proxy = data.get('proxy')
    proxy_user = data.get('proxyUser')
    proxy_pass = data.get('proxyPass')

    try:
        ip, port = proxy.split(":")
        port = int(port)
        if proxy_user and proxy_pass:
            socks.set_default_proxy(socks.SOCKS5, ip, port, True, proxy_user, proxy_pass)
        else:
            socks.set_default_proxy(socks.SOCKS5, ip, port)

        socket.socket = socks.socksocket
        test_sock = socket.create_connection(("smtp.gmail.com", 587), timeout=8)
        test_sock.close()
        socket.socket = socket._socketobject if hasattr(socket, "_socketobject") else socket.socket
        return jsonify({"status": "Proxy working ✅"})
    except Exception as e:
        print("Proxy Test Failed:", e)
        socket.socket = socket._socketobject if hasattr(socket, "_socketobject") else socket.socket
        return jsonify({"status": "Proxy connection failed"}), 400

# ---------[ Homepage ]---------
@app.route('/')
def home():
    return '✅ Email Verifier API with Auth-Proxies + Fallback APIs is Running!'

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
