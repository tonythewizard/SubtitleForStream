from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore, Event, Thread
from hashlib import sha256
from collections import OrderedDict
from time import monotonic
import json
from pathlib import Path

OVERLAY=Path(__file__).parent/'overlay.html'

def make_handler(state, stopping):
    wait_slots=BoundedSemaphore(8)
    rendered=OrderedDict()

    def encode():
        payload=json.dumps(state.snapshot(),ensure_ascii=False).encode('utf-8')
        return payload, '"'+sha256(payload).hexdigest()+'"'

    class Handler(BaseHTTPRequestHandler):
        def allowed(self):
            port=self.server.server_port
            hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
            if port==80:
                hosts.update(('127.0.0.1','localhost'))
            origin=self.headers.get('Origin')
            if self.headers.get('Host','').lower() not in hosts or (
                origin is not None and origin.lower() not in {f'http://{host}' for host in hosts}
            ):
                self.send_error(403)
                return False
            return True

        def do_POST(self):
            if not self.allowed():
                return
            if self.path!='/render-ack':
                self.send_error(404)
                return
            if self.headers.get('Content-Length')!='32':
                self.send_error(400)
                return
            self.connection.settimeout(2)
            try:
                cid=self.rfile.read(32).decode('ascii')
            except (UnicodeError, OSError):
                self.send_error(400)
                return
            with state.lock:
                now=monotonic()
                for caption in state.entries.values():
                    if caption['id']==cid and caption['expires']>now and cid not in rendered:
                        rendered[cid]={'source':caption['source'],'seconds':now-caption['updated']}
                        if len(rendered)>2048:
                            rendered.popitem(last=False)
                        break
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            if not self.allowed():
                return
            path=self.path.split('?',1)[0]
            if path=='/state':
                previous=self.headers.get('If-None-Match')
                payload,tag=encode()
                if previous==tag and self.path.endswith('?wait=1') and wait_slots.acquire(False):
                    try:
                        deadline=monotonic()+2
                        with state.changed:
                            while not stopping.is_set():
                                payload,tag=encode()
                                remaining=deadline-monotonic()
                                if tag!=previous or remaining<=0:
                                    break
                                state.changed.wait(min(.25,remaining))
                    finally:
                        wait_slots.release()
                if previous==tag:
                    self.send_response(304)
                    self.send_header('ETag',tag)
                    self.end_headers()
                    return
                self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8')
                self.send_header('ETag',tag)
            elif path=='/render-metrics':
                with state.lock:
                    payload=json.dumps(list(rendered.values())).encode('utf-8')
                self.send_response(200)
                self.send_header('Content-Type','application/json; charset=utf-8')
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
        self.state=state
        self.stopping=Event()
        self.httpd=ThreadingHTTPServer(('127.0.0.1',int(port)),make_handler(state,self.stopping))
        self.thread=Thread(target=self.httpd.serve_forever,daemon=True,name='overlay-http')
    def start(self):self.thread.start()
    def stop(self):
        self.stopping.set()
        with self.state.changed:
            self.state.changed.notify_all()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
