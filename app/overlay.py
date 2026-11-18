from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json
from pathlib import Path

OVERLAY=Path(__file__).parent/'overlay.html'

def make_handler(state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=self.path.split('?',1)[0]
            if path=='/state':
                payload=json.dumps(state.snapshot(),ensure_ascii=False).encode('utf-8')
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8')
            elif path in ('/overlay','/'):
                payload=OVERLAY.read_bytes()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
            else:
                self.send_error(404);return
            self.send_header('Cache-Control','no-store, no-cache, must-revalidate')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'none'; object-src 'none'")
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers(); self.wfile.write(payload)
        def log_message(self,*args):pass
    return Handler

class OverlayServer:
    def __init__(self,state,port=8765):
        self.httpd=ThreadingHTTPServer(('127.0.0.1',int(port)),make_handler(state))
        self.thread=Thread(target=self.httpd.serve_forever,daemon=True,name='overlay-http')
    def start(self):self.thread.start()
    def stop(self):self.httpd.shutdown();self.httpd.server_close();self.thread.join(timeout=3)
