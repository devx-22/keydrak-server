import http.server
import socketserver
import json
import sqlite3
import os
from datetime import datetime
PORT = int(os.environ.get("PORT", 5000))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "keydrak_admin_secret_99")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "licenses.db")
# Default pre-loaded batch of lifetime keys
INITIAL_KEYS = [
    "KDRAK-6KGR-EDPY-VSKH-7545",
    "KDRAK-J9VW-46AG-J3ZB-34CR",
    "KDRAK-7AHS-QW6G-BHEE-87TR",
    "KDRAK-T64E-M74E-N342-D335",
    "KDRAK-6NNA-5CBX-S2P3-44AG"
]
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
    # Pre-populate initial keys if not already present
    for k in INITIAL_KEYS:
        cursor.execute("INSERT OR IGNORE INTO licenses (license_key, status) VALUES (?, 'unused')", (k,))
    conn.commit()
    conn.close()
class LicenseHandler(http.server.BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Admin-Token")
    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()
    def do_GET(self):
        if self.path == "/health" or self.path == "/":
            return self.send_json(200, {"status": "online", "service": "KeyDrak Cloud Auth"})
        elif self.path == "/api/admin/list":
            self.handle_admin_list()
        else:
            self.send_response(404)
            self.end_headers()
