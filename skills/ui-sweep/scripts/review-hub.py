"""One local page for every review page (ui-sweep, old-new-review): http://127.0.0.1:42042/

  python review-hub.py register <report_dir> [--page X.html] [--title T] [--project P] [--session S]
        adds or updates the review and starts the hub if it is not running; prints the hub and review URLs
  python review-hub.py list | remove <id> | start | serve [--port 42042]

Each review is served under /r/<id>/ with the same decisions API as serve-report.py (report/review-decisions.json)."""
import argparse, datetime, http.server, json, mimetypes, os, re, socket, subprocess, sys, threading, time, urllib.parse

HOME = os.path.join(os.path.expanduser('~'), '.claude', 'review-hub')
REG = os.path.join(HOME, 'registry.json')
PORT = int(os.environ.get('REVIEW_HUB_PORT', '42042'))
HOST = '127.0.0.1'
LOCK = threading.Lock()


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def jload(p, default):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (FileNotFoundError, ValueError):
        return default


def jsave(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def registry():
    return jload(REG, {'reviews': []})


def running(port=PORT):
    try:
        socket.create_connection((HOST, port), 0.3).close()
        return True
    except OSError:
        return False


def start(port=PORT):
    if running(port):
        return True
    os.makedirs(HOME, exist_ok=True)
    log = open(os.path.join(HOME, 'hub.log'), 'a', encoding='utf-8')
    cmd = [sys.executable, os.path.abspath(__file__), 'serve', '--port', str(port)]
    if os.name == 'nt':
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags | 0x01000000, close_fds=True)
        except OSError:
            subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    else:
        subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL, start_new_session=True)
    for _ in range(50):
        if running(port):
            return True
        time.sleep(0.1)
    return False


def summary(r):
    d = r['dir']
    meta = jload(os.path.join(d, 'review-meta.json'), None)
    dec = jload(os.path.join(d, 'review-decisions.json'), {}).get('decisions') or {}
    page = r.get('page') or (meta or {}).get('page', '')
    out = dict(r, exists=os.path.isfile(os.path.join(d, page)), url=f'/r/{r["id"]}/{urllib.parse.quote(page)}')
    if not meta:
        out.update(steps=None)
        return out

    def kind(i):
        e = dec.get(i) or {}
        return e.get('decision') if e.get('decision') in ('approved', 'rework') else 'commented' if (e.get('comment') or '').strip() else 'undecided'
    c = {'approved': 0, 'rework': 0, 'commented': 0, 'undecided': 0}
    openq = 0
    for s in meta['steps']:
        k = 'undecided' if any(kind(i) == 'undecided' for i in s['ids']) else kind(s['ids'][0])
        c[k] += 1
        openq += s.get('open') and k == 'undecided'
    stamps = [os.path.getmtime(os.path.join(d, f)) for f in (page, 'review-decisions.json') if os.path.isfile(os.path.join(d, f))]
    out.update(steps=len(meta['steps']), findings=meta.get('findings'), counts=c, openQuestions=openq, metaTitle=meta.get('title'),
               generated=meta.get('generated'), changed=datetime.datetime.fromtimestamp(max(stamps)).astimezone().isoformat(timespec='seconds') if stamps else None)
    return out


def merge_decisions(path, body):
    incoming = body.get('decisions') if isinstance(body, dict) else None
    if not isinstance(incoming, dict):
        return None
    doc = jload(path, {})
    cur = doc.get('decisions') or {}
    changed = 0
    for k, v in incoming.items():
        if isinstance(v, dict) and (k not in cur or str(v.get('at', '')) > str((cur[k] or {}).get('at', ''))):
            cur[k] = v
            changed += 1
    if changed or not os.path.exists(path):
        doc = {'report': body.get('report') or doc.get('report', ''), 'saved': now(), 'decisions': cur}
        jsave(path, doc)
    return doc


class Handler(http.server.BaseHTTPRequestHandler):
    def send(self, code, body, ctype='application/json; charset=utf-8', extra=()):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode() if ctype.startswith('application/json') else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store' if ctype.startswith('application/json') else 'no-cache')
        for k, v in extra:
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def same_origin(self):
        o = self.headers.get('Origin')
        return not o or o in {f'http://{h}:{self.server.server_port}' for h in ('127.0.0.1', 'localhost')}

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > 20_000_000:
            return None
        try:
            return json.loads(self.rfile.read(n) or b'{}')
        except ValueError:
            return None

    def review(self, rid):
        return next((r for r in registry()['reviews'] if r['id'] == rid), None)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split('?')[0])
        if path in ('/', '/index.html'):
            return self.send(200, INDEX, 'text/html; charset=utf-8')
        if path == '/api/reviews':
            with LOCK:
                return self.send(200, {'reviews': [summary(r) for r in registry()['reviews']], 'now': now()})
        m = re.match(r'^/r/([^/]+)(/.*)?$', path)
        if not m:
            return self.send(404, {'error': 'not found'})
        r = self.review(m.group(1))
        if not r:
            return self.send(404, 'This review is no longer registered. Back to the hub: /', 'text/plain; charset=utf-8')
        rest = m.group(2) or '/'
        if rest == '/api/decisions':
            with LOCK:
                return self.send(200, jload(os.path.join(r['dir'], 'review-decisions.json'), {}))
        if rest == '/':
            return self.send(302, b'', 'text/plain', [('Location', f'/r/{r["id"]}/{urllib.parse.quote(r["page"])}')])
        root = os.path.realpath(r['dir'])
        f = os.path.realpath(os.path.join(root, rest.lstrip('/')))
        if os.path.commonpath([root, f]) != root or not os.path.isfile(f):
            return self.send(404, {'error': 'not found'})
        return self.send(200, open(f, 'rb').read(), mimetypes.guess_type(f)[0] or 'application/octet-stream')

    do_HEAD = do_GET

    def do_PUT(self):
        path = urllib.parse.unquote(self.path.split('?')[0])
        if not self.same_origin():
            return self.send(403, {'error': 'foreign origin'})
        m = re.match(r'^/r/([^/]+)/api/decisions$', path)
        if m:
            r = self.review(m.group(1))
            b = self.body()
            if not r or b is None:
                return self.send(400, {'error': 'unknown review or invalid JSON'})
            with LOCK:
                doc = merge_decisions(os.path.join(r['dir'], 'review-decisions.json'), b)
            return self.send(200, doc) if doc is not None else self.send(400, {'error': 'decisions missing'})
        m = re.match(r'^/api/reviews/([^/]+)$', path)
        if m:
            b = self.body() or {}
            with LOCK:
                reg = registry()
                r = next((x for x in reg['reviews'] if x['id'] == m.group(1)), None)
                if not r:
                    return self.send(404, {'error': 'not found'})
                if 'archived' in b:
                    r['archived'] = bool(b['archived'])
                jsave(REG, reg)
            return self.send(200, r)
        return self.send(404, {'error': 'not found'})

    do_POST = do_PUT

    def do_DELETE(self):
        m = re.match(r'^/api/reviews/([^/]+)$', urllib.parse.unquote(self.path.split('?')[0]))
        if not m or not self.same_origin():
            return self.send(404, {'error': 'not found'})
        with LOCK:
            reg = registry()
            reg['reviews'] = [x for x in reg['reviews'] if x['id'] != m.group(1)]
            jsave(REG, reg)
        return self.send(200, {'removed': m.group(1)})

    def log_request(self, code='-', size='-'):
        if self.command != 'GET' or str(code) not in ('200', '302', '304'):
            super().log_request(code, size)


def register(a):
    d = os.path.abspath(a.dir)
    if os.path.isdir(os.path.join(d, 'report')) and not os.path.isfile(os.path.join(d, 'review-meta.json')):
        d = os.path.join(d, 'report')
    meta = jload(os.path.join(d, 'review-meta.json'), {})
    page = a.page or meta.get('page') or next((f for f in sorted(os.listdir(d)) if f.endswith('.html')), None)
    if not page or not os.path.isfile(os.path.join(d, page)):
        sys.exit(f'no review page in {d}: pass --page')
    with LOCK:
        reg = registry()
        r = next((x for x in reg['reviews'] if os.path.normcase(x['dir']) == os.path.normcase(d) and x['page'] == page), None)
        if not r:
            base = re.sub(r'[^a-z0-9]+', '-', (a.id or f'{a.project or ""} {os.path.splitext(page)[0]}').lower()).strip('-')[:50] or 'review'
            rid, n = base, 2
            while any(x['id'] == rid for x in reg['reviews']):
                rid, n = f'{base}-{n}', n + 1
            r = {'id': rid, 'dir': d, 'page': page, 'registered': now()}
            reg['reviews'].append(r)
        r.update({k: v for k, v in (('title', a.title or meta.get('title')), ('project', a.project), ('session', a.session)) if v})
        r['updated'] = now()
        r['archived'] = False
        jsave(REG, reg)
    ok = a.no_start or start(a.port)
    print(f'Review hub: http://{HOST}:{a.port}/' + ('' if ok else '  (NOT running: see ' + os.path.join(HOME, 'hub.log') + ')'))
    print(f'This review: http://{HOST}:{a.port}/r/{r["id"]}/{urllib.parse.quote(page)}')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('register')
    p.add_argument('dir')
    for o in ('--page', '--title', '--project', '--session', '--id'):
        p.add_argument(o)
    p.add_argument('--no-start', action='store_true')
    p.add_argument('--port', type=int, default=PORT)
    sub.add_parser('list')
    p = sub.add_parser('remove')
    p.add_argument('id')
    for name in ('start', 'serve'):
        p = sub.add_parser(name)
        p.add_argument('--port', type=int, default=PORT)
    a = ap.parse_args()
    if a.cmd == 'register':
        register(a)
    elif a.cmd == 'list':
        for r in registry()['reviews']:
            s = summary(r)
            todo = s['counts']['undecided'] if s.get('steps') else '?'
            print(f'{r["id"]:<40} {todo!s:>4} open  {"archived " if r.get("archived") else ""}{r.get("title", "")}  ({r["dir"]})')
    elif a.cmd == 'remove':
        reg = registry()
        reg['reviews'] = [x for x in reg['reviews'] if x['id'] != a.id]
        jsave(REG, reg)
    elif a.cmd == 'start':
        print(f'http://{HOST}:{a.port}/' if start(a.port) else 'failed, see ' + os.path.join(HOME, 'hub.log'))
    else:
        if running(a.port):
            sys.exit(f'port {a.port} is in use')
        srv = http.server.ThreadingHTTPServer((HOST, a.port), Handler)
        print(f'{now()} review hub on http://{HOST}:{a.port}/  registry {REG}', flush=True)
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


INDEX = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review hub</title>
<style>
:root{color-scheme:light dark;--bg:#F5F6F8;--surface:#FFFFFF;--soft:#EEF0F4;--line:#E3E6EB;--line2:#D5DAE2;--ink:#18202C;--ink2:#3E4757;--mut:#5B6576;--acc:#2F5FD0;--accsoft:#E7EEFC;--onacc:#FFFFFF;
--ok:#1F7A4D;--okbg:#E3F3EA;--warn:#9A5B00;--warnbg:#FDF1DC;--info:#2F5FD0;--infobg:#E7EEFC;--rest:#D9DDE4}
@media (prefers-color-scheme:dark){:root{--bg:#191919;--surface:#202020;--soft:#2A2A2A;--line:#2F2F2F;--line2:#3A3A3A;--ink:#E6E6E4;--ink2:#BDBDBA;--mut:#9B9A97;--acc:#7EA2F2;--accsoft:#22304D;--onacc:#10182A;
--ok:#6CC797;--okbg:#1E3328;--warn:#E7B062;--warnbg:#3A2E1A;--info:#7EA2F2;--infobg:#22304D;--rest:#3A3A3A}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,-apple-system,sans-serif}
main{max-width:1100px;margin:0 auto;padding:28px 16px 48px}
header{display:flex;flex-wrap:wrap;align-items:flex-end;gap:10px 16px;margin-bottom:18px}
h1{margin:0;font-size:26px;letter-spacing:-.01em}.sub{color:var(--mut);font-size:14px}.sp{flex:1}
.seg{display:inline-flex;background:var(--soft);border-radius:8px;padding:3px;gap:2px}.seg button{border:0;background:transparent;color:var(--ink2);padding:5px 12px;border-radius:6px;font:inherit;font-size:13.5px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--surface);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.list{display:flex;flex-direction:column;gap:10px}
.card{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px 18px;align-items:center;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card.done{opacity:.75}.t{font-size:16.5px;font-weight:600;margin:0;overflow-wrap:anywhere}.t a{color:inherit;text-decoration:none}.t a:hover{color:var(--acc)}
.m{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:13px;color:var(--mut);margin-top:3px}.m code{font:12px Consolas,monospace;overflow-wrap:anywhere}
.bar{display:flex;height:6px;border-radius:3px;overflow:hidden;background:var(--rest);margin-top:10px;max-width:520px}.bar i{display:block;height:100%}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.chip{font-size:12.5px;font-weight:500;padding:1px 8px;border-radius:6px;background:var(--soft);color:var(--ink2);white-space:nowrap}
.chip.todo{background:var(--accsoft);color:var(--acc)}.chip.q{background:var(--warnbg);color:var(--warn)}.chip.ok{background:var(--okbg);color:var(--ok)}.chip.rw{background:var(--warnbg);color:var(--warn)}.chip.gone{background:var(--warnbg);color:var(--warn)}
.acts{display:flex;gap:8px;align-items:center}
.btn{border:1px solid var(--line2);background:var(--surface);color:var(--ink);border-radius:8px;padding:7px 14px;font:inherit;font-size:14px;font-weight:500;cursor:pointer;text-decoration:none;white-space:nowrap}
.btn:hover{background:var(--soft)}.btn.pri{background:var(--acc);border-color:var(--acc);color:var(--onacc)}.btn.pri:hover{filter:brightness(1.08)}.btn.q{padding:7px 10px;color:var(--mut)}
.empty{color:var(--mut);padding:40px 0;text-align:center}
@media (max-width:640px){.card{grid-template-columns:1fr}.acts{flex-wrap:wrap}}
</style></head><body><main>
<header><div><h1>Review hub</h1><div class="sub" id="sub">Loading…</div></div><span class="sp"></span>
<span class="seg" id="f"><button data-f="pending" aria-pressed="true">Pending</button><button data-f="all">All</button><button data-f="archived">Archived</button></span></header>
<div class="list" id="list"></div></main>
<script>
(()=>{let F='pending',R=[];const $=id=>document.getElementById(id),esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
try{F=localStorage.getItem('review-hub-filter')||F}catch(e){}
const ago=t=>{if(!t)return'';const s=(Date.now()-new Date(t))/1000;return s<90?'just now':s<5400?Math.round(s/60)+' min ago':s<129600?Math.round(s/3600)+' h ago':Math.round(s/86400)+' days ago'};
const todo=r=>r.steps==null?1:r.counts.undecided;
function render(){document.querySelectorAll('#f button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.f===F));
 const act=R.filter(r=>!r.archived),pend=act.filter(r=>todo(r)>0);
 $('sub').textContent=pend.length+' review'+(pend.length===1?'':'s')+' waiting · '+pend.reduce((n,r)=>n+(r.steps==null?0:r.counts.undecided),0)+' undecided steps';
 const rows=(F==='archived'?R.filter(r=>r.archived):F==='all'?act:pend).slice().sort((a,b)=>(todo(b)>0)-(todo(a)>0)||String(b.changed||b.updated).localeCompare(String(a.changed||a.updated)));
 $('list').innerHTML=rows.map(r=>{const c=r.counts||{},n=r.steps||0,pc=x=>(n?100*x/n:0)+'%';const done=r.steps!=null&&!c.undecided;
  return '<article class="card'+(done?' done':'')+'" data-id="'+esc(r.id)+'"><div><h2 class="t"><a href="'+esc(r.url)+'">'+esc(r.title||r.metaTitle||r.id)+'</a></h2>'
   +'<div class="m">'+(r.project?'<span>'+esc(r.project)+'</span>':'')+(r.session?'<span>'+esc(r.session)+'</span>':'')+'<span>'+(r.changed?'changed '+ago(r.changed):'registered '+ago(r.registered))+'</span><code>'+esc(r.dir)+'</code></div>'
   +(r.steps!=null?'<div class="bar"><i style="width:'+pc(c.approved)+';background:var(--ok)"></i><i style="width:'+pc(c.rework)+';background:var(--warn)"></i><i style="width:'+pc(c.commented)+';background:var(--info)"></i></div>':'')
   +'<div class="chips">'+(!r.exists?'<span class="chip gone">Page missing</span>':'')+(r.steps==null?'<span class="chip">No step data (regenerate the page)</span>':(c.undecided?'<span class="chip todo">'+c.undecided+' of '+n+' to decide</span>':'<span class="chip ok">All '+n+' decided</span>')
   +(r.openQuestions?'<span class="chip q">'+r.openQuestions+' open question'+(r.openQuestions===1?'':'s')+'</span>':'')+(c.approved?'<span class="chip ok">'+c.approved+' approved</span>':'')+(c.rework?'<span class="chip rw">'+c.rework+' needs work</span>':'')+(c.commented?'<span class="chip">'+c.commented+' commented</span>':''))+'</div></div>'
   +'<div class="acts"><a class="btn pri" href="'+esc(r.url)+'">'+(done?'Open':'Review')+'</a><button class="btn q" data-a="arch">'+(r.archived?'Restore':'Archive')+'</button><button class="btn q" data-a="rm" title="Remove from the hub (files stay)">Remove</button></div></article>'}).join('')
  ||'<p class="empty">'+(F==='pending'?'Nothing waiting for a review.':'Nothing here.')+'</p>'}
async function load(){try{const j=await (await fetch('/api/reviews',{cache:'no-store'})).json();R=j.reviews||[];render()}catch(e){$('sub').textContent='Hub not reachable'}}
$('f').onclick=e=>{const b=e.target.closest('button');if(!b)return;F=b.dataset.f;try{localStorage.setItem('review-hub-filter',F)}catch(x){}render()};
$('list').onclick=async e=>{const b=e.target.closest('button[data-a]');if(!b)return;const id=b.closest('.card').dataset.id,r=R.find(x=>x.id===id);
 if(b.dataset.a==='arch')await fetch('/api/reviews/'+encodeURIComponent(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({archived:!r.archived})});
 else if(confirm('Remove "'+(r.title||id)+'" from the hub? The files and decisions stay on disk.'))await fetch('/api/reviews/'+encodeURIComponent(id),{method:'DELETE'});
 load()};
load();setInterval(()=>{if(!document.hidden)load()},10000);window.addEventListener('focus',load)})();
</script></body></html>'''

if __name__ == '__main__':
    main()
