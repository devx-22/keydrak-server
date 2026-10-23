import http.server
import socketserver
import json
import sqlite3
import os
from datetime import datetime

PORT = int(os.environ.get("PORT", 5000))
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'unused',
            used_by TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

class LicenseHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            return self.send_json(200, {"status": "online", "service": "KeyDrak Cloud Auth"})
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/activate":
            self.handle_activate()
        elif self.path == "/api/verify":
            self.handle_verify()
        else:
            self.send_response(404)
            self._send_cors_headers()
            self.end_headers()

    def handle_activate(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode("utf-8"))
            key = data.get("key", "").strip().upper()
            install_id = data.get("installId", "").strip()
        except Exception:
            return self.send_json(400, {"success": False, "message": "Invalid JSON"})

        if not key or not install_id:
            return self.send_json(400, {"success": False, "message": "Key and installId required"})

        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, used_by FROM licenses WHERE license_key = ?", (key,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return self.send_json(400, {"success": False, "message": "Invalid license key"})

        status, used_by = row

        if status == "revoked":
            conn.close()
            return self.send_json(403, {"success": False, "message": "License has been revoked!"})

        if status == "used" and used_by != install_id:
            conn.close()
            return self.send_json(403, {"success": False, "message": "Key already activated on another device!"})

        if status == "used" and used_by == install_id:
            conn.close()
            return self.send_json(200, {"success": True, "message": "Restored for this device", "lifetime": True})

        now = datetime.utcnow().isoformat()
        cursor.execute("UPDATE licenses SET status = 'used', used_by = ?, activated_at = ? WHERE license_key = ?", 
                       (install_id, now, key))
        conn.commit()
        conn.close()

        print(f"[KeyDrak Cloud] Activated {key} for {install_id}")
        return self.send_json(200, {"success": True, "message": "Lifetime activated!", "lifetime": True})

    def handle_verify(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data.decode("utf-8"))
            key = data.get("key", "").strip().upper()
            install_id = data.get("installId", "").strip()
        except Exception:
            return self.send_json(400, {"valid": False})

        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT status, used_by FROM licenses WHERE license_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return self.send_json(200, {"valid": False, "message": "Not found"})

        status, used_by = row
        if status == "revoked":
            return self.send_json(200, {"valid": False, "revoked": True, "message": "Revoked"})

        if status == "used" and used_by == install_id:
            return self.send_json(200, {"valid": True, "lifetime": True})

        return self.send_json(200, {"valid": False})

    def send_json(self, status_code, data):
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

def run():
    init_db()
    with socketserver.ThreadingTCPServer(("", PORT), LicenseHandler) as httpd:
        print(f"KeyDrak Cloud Server listening on port {PORT}...")
        httpd.serve_forever()

if __name__ == "__main__":
    run()
