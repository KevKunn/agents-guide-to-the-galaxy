"""Usage: python serve-report.py [sweep_dir] [--port 8765] [--host 127.0.0.1]
Serves <sweep_dir>/report and keeps report/review-decisions.json in sync with the review page (GET/PUT /api/decisions, newest entry wins)."""
import argparse, datetime, functools, http.server, json, os, threading

ap = argparse.ArgumentParser()
ap.add_argument('dir', nargs='?', default=os.path.dirname(os.path.abspath(__file__)))
ap.add_argument('--port', type=int, default=8765)
ap.add_argument('--host', default='127.0.0.1')
args = ap.parse_args()

REPORT = os.path.join(os.path.abspath(args.dir), 'report')
FILE = os.path.join(REPORT, 'review-decisions.json')
API = '/api/decisions'
LOCK = threading.Lock()
ORIGINS = {f'http://{h}:{args.port}' for h in (args.host, '127.0.0.1', 'localhost')}


def read():
    try:
        return json.load(open(FILE, encoding='utf-8'))
    except FileNotFoundError:
        return {}


def write(doc):
    tmp = FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE)


class Handler(http.server.SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def end_headers(self):
        if not self.path.startswith(API):
            self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == API:
            with LOCK:
                return self._json(200, read())
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/ui-sweep-report.html')
            self.end_headers()
            return
        super().do_GET()

    def do_PUT(self):
        if self.path.split('?')[0] != API:
            return self._json(404, {'error': 'not found'})
        origin = self.headers.get('Origin')
        if origin and origin not in ORIGINS:
            return self._json(403, {'error': 'foreign origin'})
        n = int(self.headers.get('Content-Length') or 0)
        if n > 20_000_000:
            return self._json(413, {'error': 'too large'})
        try:
            body = json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            return self._json(400, {'error': 'invalid JSON'})
        incoming = body.get('decisions') if isinstance(body, dict) else None
        if not isinstance(incoming, dict):
            return self._json(400, {'error': 'decisions missing'})
        with LOCK:
            doc = read()
            cur = doc.get('decisions') or {}
            changed = 0
            for k, v in incoming.items():
                if isinstance(v, dict) and (k not in cur or str(v.get('at', '')) > str((cur[k] or {}).get('at', ''))):
                    cur[k] = v
                    changed += 1
            if changed or not os.path.exists(FILE):
                doc = {'report': body.get('report') or doc.get('report', ''), 'saved': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'decisions': cur}
                write(doc)
                self.log_message('saved %d changed of %d decisions', changed, len(cur))
            return self._json(200, doc)

    do_POST = do_PUT

    def log_request(self, code='-', size='-'):
        if self.command != 'GET' or str(code) not in ('200', '304'):
            super().log_request(code, size)


os.makedirs(REPORT, exist_ok=True)
server = http.server.ThreadingHTTPServer((args.host, args.port), functools.partial(Handler, directory=REPORT))
print(f'Review page: http://{args.host}:{args.port}/ui-sweep-report.html  ·  decisions: {FILE}', flush=True)
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
