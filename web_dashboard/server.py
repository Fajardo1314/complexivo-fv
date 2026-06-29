"""
Servidor HTTP combinado: sirve archivos estáticos del dashboard
y expone un endpoint /api/send-email para enviar correos OTP
usando smtplib de Python (sin dependencias externas).
"""
import http.server
import json
import os
import smtplib
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "smartstock97@gmail.com"
SMTP_PASS = "F@jardo123"

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Sirve archivos estáticos y maneja POST /api/send-email"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_POST(self):
        if self.path == "/api/send-email":
            self._handle_send_email()
        else:
            self.send_error(404, "Endpoint no encontrado")

    def _handle_send_email(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            to_addr = data.get("to", "")
            subject = data.get("subject", "Smart Stock - Código OTP")
            body_text = data.get("body", "")

            if not to_addr:
                self._json_response(400, {"error": "Falta campo 'to'"})
                return

            # Construir el correo
            msg = MIMEMultipart("alternative")
            msg["From"] = SMTP_USER
            msg["To"] = to_addr
            msg["Subject"] = subject
            msg.attach(MIMEText(body_text, "plain", "utf-8"))

            # Enviar vía SMTP
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, to_addr, msg.as_string())

            print(f"[Email] Correo enviado exitosamente a: {to_addr}")
            self._json_response(200, {"ok": True, "message": "Correo enviado"})

        except smtplib.SMTPAuthenticationError as e:
            print(f"[Email] Error de autenticación SMTP: {e}")
            self._json_response(500, {"error": "Error de autenticación SMTP"})
        except Exception as e:
            print(f"[Email] Error al enviar correo: {e}")
            self._json_response(500, {"error": str(e)})

    def _json_response(self, code, data):
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response)

    def do_OPTIONS(self):
        """Manejar preflight CORS"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Silenciar logs de archivos estáticos, solo mostrar API
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


if __name__ == "__main__":
    PORT = 8080
    print(f"🚀 Smart Stock Dashboard corriendo en http://localhost:{PORT}")
    print(f"   Sirviendo archivos desde: {DASHBOARD_DIR}")
    print(f"   API de correo: http://localhost:{PORT}/api/send-email")
    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido.")
        server.server_close()