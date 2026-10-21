"""Usage: python gen-report.py [sweep_dir] [out.html]  ->  default <sweep_dir>/report/ui-sweep-report.html
Register it with review-hub.py (or serve it with serve-report.py) so decisions are saved to report/review-decisions.json."""
import base64, datetime, glob, html, json, os, re, sys
from collections import Counter

S = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
F = os.path.join(S, 'findings')
OUT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(S, 'report', 'ui-sweep-report.html')


def load(name, default):
    p = os.path.join(S, name)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else default


cfg = load('sweep.config.json', {})
status = load('status.json', {})
briefs = load('briefs.json', {})

TITLE = cfg.get('title', 'UI sweep')
LANG = (cfg.get('locale') or 'en').split('-')[0]
UI_LANG = cfg.get('uiLanguage', 'the product language')
VPS = cfg.get('viewports') or [{'width': 1600, 'height': 900}, {'width': 1280, 'height': 720}]
VP_MAIN = f'{VPS[0]["width"]}×{VPS[0]["height"]}'
VP_NARROW = f'{VPS[-1]["width"]}×{VPS[-1]["height"]}' if len(VPS) > 1 else VP_MAIN
LBL_B, LBL_A = cfg.get('beforeLabel', 'Before'), cfg.get('afterLabel', 'After')
SHOW_COVERAGE = cfg.get('coverage', True)
KEY = cfg.get('decisionsKey') or re.sub(r'[^a-z0-9]+', '-', TITLE.lower()).strip('-') + '-review-v1'

CHECKS = [tuple(c) for c in cfg.get('checks', [])] or [
    ('C1', 'Truncated text, horizontal', 'Captions, labels, column headers, tab titles, buttons, nav items, field and combo values. Defect: a word is cut or ellipsized so it is not readable. Measured: visible vs needed width in px.'),
    ('C2', 'Clipped text, vertical', 'Multi-line captions or values cut at top/bottom. Defect: any glyph cut. Measured: text height vs visible height.'),
    ('C3', 'Missing or broken icons', '404 images, empty SVGs, actions/nav items/object types without icon where siblings have one, generic placeholder icons.'),
    ('C4', 'Padding', 'Gap between text and its box edge (border, bar, background, button). Defect: < 4 px on any side.'),
    ('C5', 'Spacing', 'Gap between visually distinct boxes/rows/groups. Defect: < 4 px, or equivalent siblings differing by > 4 px.'),
    ('C6', 'Alignment', 'Edges/baselines of labels, values, columns, buttons meant to line up. Defect: > 2 px difference, or inconsistent label widths in one group.'),
    ('C7', 'Missing/empty/raw text', 'Empty captions, buttons without text/icon/tooltip, "N/A", "null", "{0}", auto-generated captions, technical names, leftover placeholders.'),
    ('C8', 'Language', f'Text not in {UI_LANG} or mixed (captions, buttons, tooltips, placeholders, empty states, dialogs, validation), spelling/grammar, inconsistent terminology.'),
    ('C9', 'Overlap', 'Unrelated elements drawn over each other. Defect: > 2 px overlap.'),
    ('C10', 'Overflow / scrollbars', 'Unintended horizontal scrollbars, content wider than its container, popups cut by the viewport, buttons out of view.'),
    ('C11', 'Narrow viewport', f'C1, C2, C9, C10 repeated at {VP_NARROW}; reported only when it breaks at {VP_NARROW} but not at {VP_MAIN}.'),
    ('C12', 'Console/network errors', 'Browser console errors and failed image requests; a finding only when it causes a visible defect.'),
    ('C13', 'Fonts and text metrics', 'Requested vs resolved font per surface (browser, reports, exports, chart images, mails, against the render host and embedded PDF fonts). Defect: silent fallback, labels cut with "…", mid-word breaks, changed line breaks/row heights/page count, replacement glyphs.'),
]
CHECK_TITLE = {c: t for c, t, _ in CHECKS}

AREAS, PREEXISTING = {}, set()
for a, v in (cfg.get('areas') or {}).items():
    AREAS[a] = v['title'] if isinstance(v, dict) else v
    if isinstance(v, dict) and v.get('preexisting'):
        PREEXISTING.add(a)

STATUS_ORDER = ['fixed', 'partly', 'decision', 'open', 'legacy', 'data', 'bydesign']
STATUS_LABEL = {
    'fixed': 'Fixed', 'partly': 'Partly fixed', 'decision': 'Needs your decision', 'open': 'Not fixed (open)',
    'legacy': 'Same in the old app (accepted)', 'data': 'Data / deployment, not code', 'bydesign': 'By design / not a defect',
}
STATUS_SHORT = {'fixed': 'Fixed', 'partly': 'Partly fixed', 'decision': 'Decision', 'open': 'Open', 'legacy': 'Legacy', 'data': 'Data', 'bydesign': 'By design'}
SEV_ORDER = {'high': 0, 'medium': 1, 'low': 2}
EFFORT = {'S': 'small (under 2 h)', 'M': 'medium (half a day to a day)', 'L': 'large'}

GROUPS = briefs.get('groups', {})
BRIEF_OF = {}
for gk, g in GROUPS.items():
    for m in g.get('members', []):
        BRIEF_OF[m] = dict(g, _gkey=re.sub(r'[^\w-]', '_', gk))
for fid, b in briefs.get('findings', {}).items():
    BRIEF_OF[fid] = b


def b64(p):
    return 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode() if os.path.exists(p) else None


def esc(s):
    return html.escape(str(s if s is not None else ''))


def area_of(fid):
    return fid.rsplit('-', 1)[0]


findings = []
for f in glob.glob(os.path.join(F, '*', '*.json')):
    if os.path.basename(f) == 'coverage.json':
        continue
    j = json.load(open(f, encoding='utf-8'))
    if 'id' not in j:
        continue
    d = os.path.dirname(f)
    j['_before'] = b64(os.path.join(d, j['id'] + '.before.png'))
    j['_after'] = b64(os.path.join(d, j['id'] + '.after.png'))
    j['_pairs'] = [(pr.get('caption', ''), b64(os.path.join(d, pr['before'])) if pr.get('before') else None,
                    b64(os.path.join(d, pr['after'])) if pr.get('after') else None) for pr in j.get('pairs') or []]
    st = status.get(j['id'], {'status': 'open', 'fix': ''})
    j['_status'] = st['status'] if st['status'] in STATUS_LABEL else 'open'
    j['_fix'] = st.get('fix', '')
    j['_issue'] = (BRIEF_OF.get(j['id']) or {}).get('issue') or st.get('issue') or ''
    j['_own'] = st.get('issue') or ''
    findings.append(j)

findings.sort(key=lambda j: (STATUS_ORDER.index(j['_status']), SEV_ORDER.get(j.get('severity'), 3), j['id']))
ordered, placed = [], set()
for j in findings:
    if j['id'] in placed:
        continue
    gk = (BRIEF_OF.get(j['id']) or {}).get('_gkey')
    members = [m for m in findings if gk and (BRIEF_OF.get(m['id']) or {}).get('_gkey') == gk] or [j]
    for m in members:
        m['_group'] = gk if gk and len(members) > 1 else ''
        ordered.append(m)
        placed.add(m['id'])
findings = ordered

coverage = []
for f in sorted(glob.glob(os.path.join(F, '*', 'coverage.json'))):
    a = os.path.basename(os.path.dirname(f))
    for e in json.load(open(f, encoding='utf-8')):
        e['_agent'] = a
        coverage.append(e)

sev = Counter(j.get('severity') for j in findings if area_of(j['id']) not in PREEXISTING)
stc = Counter(j['_status'] for j in findings)
checkc = Counter(j.get('check') for j in findings)
cova = Counter(e['_agent'] for e in coverage)
fa = Counter(area_of(j['id']) for j in findings)
for a in sorted(set(cova) | set(fa)):
    AREAS.setdefault(a, '')
covc = Counter()
for e in coverage:
    for c, _, _ in CHECKS:
        v = str((e.get('checks') or {}).get(c, 'n/a'))
        covc['pass' if v == 'pass' else 'fail' if v.startswith('fail') else 'na'] += 1

DECISIONS_FILE = os.path.join(os.path.dirname(OUT), 'review-decisions.json')
preload = json.load(open(DECISIONS_FILE, encoding='utf-8')).get('decisions', {}) if os.path.exists(DECISIONS_FILE) else {}


def brief_out(b):
    if not b:
        return None
    m = re.match(r'Option (\d)', b.get('rec', ''))
    try:
        recn = int(b.get('recOption') or (m.group(1) if m else 0))
    except (TypeError, ValueError):
        recn = 0
    return {'title': b.get('title', ''), 'issue': b.get('issue', ''), 'options': b.get('options') or [], 'recn': recn,
            'rec': b.get('rec', ''), 'effort': EFFORT.get(b.get('effort'), b.get('effort') or ''), 'open': bool(b.get('open')),
            'reply': b.get('reply', '')}


IMG, data_findings, data_groups, data_briefs = {}, [], {}, {}
for j in findings:
    vp = j.get('viewport') or VPS[0]
    if j['_before']:
        IMG[j['id'] + ':b'] = j['_before']
    if j['_after']:
        IMG[j['id'] + ':a'] = j['_after']
    for n, (_, pb, pa) in enumerate(j['_pairs'], 1):
        if pb:
            IMG[f'{j["id"]}~{n}:b'] = pb
        if pa:
            IMG[f'{j["id"]}~{n}:a'] = pa
    desc = j.get('description') or ''
    data_findings.append({
        'id': j['id'], 'title': j.get('title', ''), 'page': j.get('page', ''), 'route': j.get('route', ''),
        'status': j['_status'], 'statusLabel': STATUS_LABEL[j['_status']], 'sev': j.get('severity') or '',
        'check': j.get('check') or '', 'checkTitle': CHECK_TITLE.get(j.get('check'), ''),
        'env': ' · '.join(str(x) for x in (j.get('tenant'), j.get('user'), j.get('module')) if x),
        'vp': f'{vp.get("width")}×{vp.get("height")}', 'area': AREAS.get(area_of(j['id']), ''), 'areaKey': area_of(j['id']),
        'issue': j['_issue'] or desc, 'desc': desc, 'own': j['_own'] or desc, 'fix': j['_fix'],
        'changed': j['_status'] in ('fixed', 'partly'),
        'measured': ', '.join(f'{k}: {v}' for k, v in (j.get('measurements') or {}).items()),
        'expected': j.get('expected') or '', 'cause': j.get('suspectedCause') or '',
        'also': '; '.join(map(str, j.get('alsoAffects') or [])), 'group': j['_group'],
        'shots': ([j.get('shotCaption') or 'Main'] + [c or f'Pair {n}' for n, (c, _, _) in enumerate(j['_pairs'], 1)]) if j['_pairs'] else [],
    })
    if j['_group']:
        if j['_group'] not in data_groups:
            data_groups[j['_group']] = brief_out(BRIEF_OF.get(j['id']))
    elif BRIEF_OF.get(j['id']):
        data_briefs[j['id']] = brief_out(BRIEF_OF[j['id']])

DATA = {'title': TITLE, 'key': KEY, 'findings': data_findings, 'groups': data_groups, 'briefs': data_briefs,
        'statusOrder': [s for s in STATUS_ORDER if stc[s]], 'statusShort': STATUS_SHORT,
        'lb': LBL_B, 'la': LBL_A, 'custom': 'afterLabel' in cfg}

L = []
w = L.append
w(f'<header class="lv-hero"><div class="lv-eye">{esc(cfg.get("eyebrow", "UI sweep report"))}</div>')
w(f'<h1>{esc(TITLE)}</h1>')
if cfg.get('subtitle'):
    w(f'<p class="mut">{esc(cfg["subtitle"])}</p>')
w('<nav class="lv-toc"><a href="#lv-findings">Findings</a>')
if status.get('_files'):
    w('<a href="#lv-files">Changed files</a>')
if status.get('_notes'):
    w('<a href="#lv-notes">Notes</a>')
if SHOW_COVERAGE:
    w('<a href="#lv-method">Checks</a><a href="#lv-areas">Areas</a><a href="#lv-coverage">Coverage</a>')
w('</nav></header>')
w('<section class="lv-kpis">')
if SHOW_COVERAGE:
    w(f'<div class="lv-kpi"><b>{len(coverage)}</b><span>pages / states checked</span></div>')
w(f'<div class="lv-kpi"><b>{sum(sev.values())}</b><span>findings · {sev["high"]} high · {sev["medium"]} medium · {sev["low"]} low</span></div>')
for s in STATUS_ORDER:
    if stc[s]:
        w(f'<div class="lv-kpi k-{s}"><b>{stc[s]}</b><span>{STATUS_LABEL[s]}</span></div>')
w('</section>')
if findings:
    w('<div class="lv-bar" role="img" aria-label="Findings by status">')
    for s in STATUS_ORDER:
        if stc[s]:
            w(f'<i class="b-{s}" style="width:{100 * stc[s] / len(findings):.2f}%" title="{STATUS_LABEL[s]}: {stc[s]}"></i>')
    w('</div><div class="lv-legend">')
    for s in STATUS_ORDER:
        if stc[s]:
            w(f'<span><i class="b-{s}"></i>{STATUS_SHORT[s]} {stc[s]}</span>')
    w('</div>')
w(f'<h2 id="lv-findings">Findings <span class="n">{len(findings)}</span></h2>')
w('<div class="lv-tools"><span class="rv-seg" id="lsf"><button type="button" data-s="all" aria-pressed="true">All</button>')
for s in STATUS_ORDER:
    if stc[s]:
        w(f'<button type="button" data-s="{s}" aria-pressed="false">{STATUS_SHORT[s]} {stc[s]}</button>')
w('</span><span class="rv-seg" id="ldf"><button type="button" data-d="all" aria-pressed="true">Any decision</button><button type="button" data-d="undecided" aria-pressed="false">Undecided</button>'
  '<button type="button" data-d="rework" aria-pressed="false">Needs work</button><button type="button" data-d="commented" aria-pressed="false">Commented</button>'
  '<button type="button" data-d="approved" aria-pressed="false">Approved</button><button type="button" data-d="q" aria-pressed="false">Open questions</button></span>'
  '<label class="lv-chk"><input type="checkbox" id="lhide"> Hide approved</label><span class="sp"></span><span class="mut" id="lcount"></span>'
  '<button class="rv-ghost" type="button" id="limp">Import</button><button class="rv-ghost" type="button" id="lcopy" title="Copy needs-work items and comments as text">Copy summary</button></div>'
  '<div class="lv-cards" id="lcards"></div>')

if status.get('_files'):
    w(f'<h2 id="lv-files">Changed files <span class="n">{len(status["_files"])}</span></h2><div class="lv-panel lv-tw"><table><tr><th>File</th><th>Change</th></tr>')
    for fpath, what in status['_files']:
        w(f'<tr><td><code>{esc(fpath)}</code></td><td>{esc(what)}</td></tr>')
    w('</table></div>')
if status.get('_notes'):
    w('<h2 id="lv-notes">Verification and notes</h2><div class="lv-panel"><ul class="lv-notes">')
    for t in status['_notes']:
        w(f'<li>{esc(t)}</li>')
    w('</ul></div>')
LIST_END = len(L)
w('<h2 id="lv-method">How it was checked</h2>')
w(f'<details class="lv-sec lv-panel"><summary>The {len(CHECKS)} checks applied to every page and state <span class="n">pass {covc["pass"]} · fail {covc["fail"]} · n/a {covc["na"]}</span></summary>'
  '<p class="lv-note mut">Each candidate was first measured in the DOM (bounding boxes, scroll/client widths, computed styles, image requests) and then confirmed on a screenshot. '
  'Only defects confirmed both ways were reported. One finding per root cause; other places with the same cause are listed under "Also affects".</p>'
  '<div class="lv-tw"><table><tr><th>Code</th><th>Check</th><th>Exact criterion</th><th>Findings</th></tr>')
for c, t, d in CHECKS:
    w(f'<tr><td><b>{c}</b></td><td>{esc(t)}</td><td>{esc(d)}</td><td class="num">{checkc.get(c, 0)}</td></tr>')
w('</table></div></details>')
w(f'<details class="lv-sec lv-panel" id="lv-areas"><summary>Areas <span class="n">{len(AREAS)}</span></summary><div class="lv-tw"><table><tr><th>Area</th><th>Scope</th><th>Pages/states</th><th>Findings</th></tr>')
for a, t in AREAS.items():
    w(f'<tr><td><b>{esc(a)}</b></td><td>{esc(t)}</td><td class="num">{cova.get(a, 0)}</td><td class="num">{fa.get(a, 0)}</td></tr>')
w('</table></div></details>')
w(f'<details class="lv-sec lv-panel" id="lv-coverage"><summary>Coverage: every page/state and the result of each check <span class="n">{len(coverage)} rows</span></summary>'
  '<div class="lv-ctool"><span class="rv-seg" id="ltf"><button type="button" data-t="all" aria-pressed="true">All tenants</button>')
for t in sorted({e.get('tenant') for e in coverage if e.get('tenant')}):
    w(f'<button type="button" data-t="{esc(t)}" aria-pressed="false">{esc(t)}</button>')
w('</span></div><div class="lv-cov"><table><tr><th>Area</th><th>Tenant</th><th>User</th><th>Module</th><th>Page</th><th>State</th><th>Viewports</th>')
for c, _, _ in CHECKS:
    w(f'<th>{c}</th>')
w('<th>Notes</th></tr>')
for e in coverage:
    w(f'<tr data-t="{esc(e.get("tenant"))}"><td>{esc(e["_agent"])}</td><td>{esc(e.get("tenant"))}</td><td>{esc(e.get("user"))}</td><td>{esc(e.get("module"))}</td>'
      f'<td>{esc(e.get("page"))}</td><td>{esc(e.get("state"))}</td><td>{esc(", ".join(e.get("viewports") or []))}</td>')
    for c, _, _ in CHECKS:
        v = str((e.get('checks') or {}).get(c, 'n/a'))
        cls = 'pass' if v == 'pass' else 'fail' if v.startswith('fail') else 'na'
        ids = re.findall(r'[A-Z][A-Z0-9]*-\d+', v) if cls == 'fail' else []
        txt = ' '.join(f'<a href="#{i}" data-fid="{i}">{i}</a>' for i in ids) if ids else esc(v)
        w(f'<td class="{cls}">{txt}</td>')
    w(f'<td>{esc(e.get("notes"))}</td></tr>')
w('</table></div></details>')
if not SHOW_COVERAGE:
    del L[LIST_END:]
w(f'<footer class="lv-foot">Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by gen-report.py · served by serve-report.py, decisions are saved to report/review-decisions.json; opened as a file, they stay in this browser</footer>')
LIST_HTML = ''.join(L)

LIGHT = ('--bg:#F5F6F8;--surface:#FFFFFF;--soft:#EEF0F4;--side:#FBFBFC;--line:#E3E6EB;--line2:#D5DAE2;--ink:#18202C;--ink2:#3E4757;--mut:#5B6576;'
         '--acc:#2353D3;--accbg:#E8EEFC;--accsoft:#F3F6FE;--cur:#E8EEFC;--ok:#17784A;--okbg:#E3F4EA;--okfg:#12613B;--onok:#FFFFFF;'
         '--warn:#C2540F;--warnbg:#FDF1E3;--warnfg:#8A4108;--onwarn:#FFFFFF;--medbg:#FFF4DB;--medfg:#7A5000;--highbg:#FDE8E7;--highfg:#9F1C14;'
         '--infobg:#E6EEFE;--infofg:#1D4FB8;--shotbg:#E9ECF1;--bar:rgba(255,255,255,.94);--toast:#18202C;--toastfg:#FFFFFF;--idbg:#18202C;--idfg:#FFFFFF;'
         '--ring:#B8BFCB;--segon:#FFFFFF;--apbg:#17784A;--apfg:#FFFFFF;--rwon:#C2540F;--onrw:#FFFFFF;--imgline:rgba(16,24,40,.12);'
         '--shadow:0 1px 2px rgba(16,24,40,.12);--card:0 1px 2px rgba(16,24,40,.05),0 2px 8px rgba(16,24,40,.05);color-scheme:light')
DARK = ('--bg:#191919;--surface:#202020;--soft:#2A2A2A;--side:#202020;--line:#2F2F2F;--line2:#3A3A3A;--ink:#E6E6E4;--ink2:#BDBDBA;--mut:#9B9A97;'
        '--acc:#5AA2D6;--accbg:#22323E;--accsoft:#1F262C;--cur:#2C2C2C;--ok:#58B08A;--okbg:#22382C;--okfg:#8CCBA8;--onok:#191919;'
        '--warn:#D9853B;--warnbg:#3A2B1F;--warnfg:#E8AE78;--onwarn:#191919;--medbg:#38301C;--medfg:#D8B868;--highbg:#3B2221;--highfg:#F0938A;'
        '--infobg:#1E2A36;--infofg:#8CB8DE;--shotbg:#161616;--bar:rgba(25,25,25,.92);--toast:#2F2F2F;--toastfg:#E6E6E4;--idbg:#2F2F2F;--idfg:#E6E6E4;'
        '--ring:#5A5A58;--segon:#3A3A3A;--apbg:#2F6B4F;--apfg:#EEF6F1;--rwon:#7A4320;--onrw:#F6E6D8;--imgline:rgba(255,255,255,.08);'
        '--shadow:none;--card:none;color-scheme:dark')

PAGE = r'''<!doctype html><html lang="__LANG__" data-theme="auto"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__PTITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{__LIGHT__}
:root[data-theme=dark]{__DARK__}
@media (prefers-color-scheme:dark){:root[data-theme=auto]{__DARK__}}
*{box-sizing:border-box}html,body{margin:0}[hidden]{display:none!important}
body{background:var(--bg);color:var(--ink);font:15px/1.6 Inter,"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
button,input,textarea,select{font:inherit;color:inherit}button:focus:not(:focus-visible){outline:none}button:focus-visible{outline:2px solid var(--acc);outline-offset:2px}a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{font:12.5px/1.4 "JetBrains Mono",ui-monospace,Consolas,monospace;background:var(--soft);border-radius:4px;padding:1px 5px;overflow-wrap:anywhere}
.mut{color:var(--mut)}.sp{flex:1}
#app{display:flex;flex-direction:column;min-height:100vh}
body.m-review{overflow:hidden}body.m-review #app{height:100vh}
body.m-list #review,body.m-list #dock,body.m-review #list{display:none}
a.rv-ib{color:inherit;text-decoration:none}
.rv-top{position:sticky;top:0;z-index:8;flex:none;display:flex;align-items:center;gap:10px 16px;padding:10px 16px;background:var(--bar);border-bottom:1px solid var(--line);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px)}
.rv-ib{flex:none;width:36px;height:36px;display:inline-flex;align-items:center;justify-content:center;border:1px solid var(--line2);background:var(--surface);color:var(--ink2);border-radius:8px;cursor:pointer;padding:0}
.rv-ib:hover,.rv-ghost:hover{background:var(--soft);color:var(--ink)}
.rv-ghost{border:1px solid var(--line2);background:var(--surface);color:var(--ink);border-radius:8px;padding:7px 12px;font-size:13.5px;font-weight:500;cursor:pointer;white-space:nowrap}
.rv-seg{display:inline-flex;flex-wrap:wrap;background:var(--soft);border-radius:8px;padding:3px;gap:1px;flex:none}
.rv-seg button{border:0;border-radius:6px;padding:4px 10px;font-size:13px;font-weight:500;cursor:pointer;background:transparent;color:var(--mut);white-space:nowrap}
.rv-seg button:hover:not(:disabled){color:var(--ink)}
.rv-seg button[aria-pressed=true]{background:var(--segon);color:var(--ink);box-shadow:var(--shadow)}
.rv-seg button:disabled{color:var(--ring);cursor:default}
.rv-ttl{min-width:0;line-height:1.3;flex:1 1 auto}.rv-ttl b{display:block;font-weight:600;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rv-ttl span{font-size:12.5px;color:var(--mut);white-space:nowrap}
.rv-prog{flex:0 1 220px;height:6px;border-radius:99px;background:var(--soft);overflow:hidden;display:flex}.rv-prog i{display:block;height:100%;transition:width .25s}
.rv-pill{display:inline-flex;align-items:center;gap:7px;padding:5px 11px;border-radius:99px;font-size:12.5px;font-weight:500;white-space:nowrap;background:var(--soft);color:var(--ink2)}
.rv-pill.ok{background:var(--okbg);color:var(--okfg)}.rv-pill.warn{background:var(--warnbg);color:var(--warnfg)}
#review{flex:1;min-height:0;display:flex;position:relative}
#rail{display:none;flex:none;width:300px;border-right:1px solid var(--line);background:var(--side);overflow-y:auto;padding:14px 10px 24px}
body.rail-open #rail{display:block}
.rv-scrim{display:none}
.rv-railh{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:0 4px 10px}
.rv-lbl{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.rv-rows{display:flex;flex-direction:column;gap:1px}
.rv-row{display:flex;align-items:flex-start;gap:10px;width:100%;text-align:left;border:0;border-radius:7px;padding:7px 10px;cursor:pointer;background:transparent;color:var(--ink)}
.rv-row:hover{background:var(--soft)}.rv-row[aria-current=step]{background:var(--cur)}
.rv-dot{flex:none;width:20px;height:20px;margin-top:2px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1.5px solid var(--ring)}
.rv-dot.k-approved{background:var(--ok);border-color:var(--ok);color:var(--onok)}.rv-dot.k-rework{background:var(--warn);border-color:var(--warn);color:var(--onwarn)}.rv-dot.k-commented{background:var(--acc);border-color:var(--acc);color:var(--surface)}
.rv-rt{min-width:0;flex:1;line-height:1.35}.rv-rl{display:flex;align-items:center;gap:6px}
.rv-rid{font:600 11.5px/1.4 "JetBrains Mono",Consolas,monospace;color:var(--mut)}.rv-row[aria-current=step] .rv-rid{color:var(--acc)}
.rv-rtitle{display:block;font-size:13.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink2)}
.rv-row.k-undecided .rv-rtitle,.rv-row[aria-current=step] .rv-rtitle{color:var(--ink)}.rv-row[aria-current=step] .rv-rtitle{font-weight:600}
.rv-tag{font-size:11px;font-weight:500;color:var(--mut);background:var(--soft);border-radius:4px;padding:0 6px;white-space:nowrap}.rv-tag.q{color:var(--warnfg);background:var(--warnbg)}.rv-tag.fx{color:var(--okfg);background:var(--okbg)}
.rv-sevd{width:6px;height:6px;border-radius:50%;flex:none;margin-left:auto}.rv-sevd.high{background:var(--highfg)}.rv-sevd.medium{background:var(--medfg)}
#rmain{flex:1;min-width:0;overflow-y:auto;padding:28px 40px 40px}
.rv-art{max-width:1040px;margin:0 auto;display:grid;grid-template-columns:minmax(0,1fr);grid-template-areas:"a" "shot" "b";row-gap:26px}
.rv-a{grid-area:a;min-width:0}.rv-b{grid-area:b;min-width:0}.rv-shot{grid-area:shot;min-width:0}
.rv-area{font-size:13px;color:var(--mut);margin-bottom:12px}
.rv-chips{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
.rv-id{font:600 12.5px/1.5 "JetBrains Mono",Consolas,monospace;padding:2px 8px;border-radius:6px;background:var(--idbg);color:var(--idfg);white-space:nowrap}
.rv-chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:500;padding:2px 9px;border-radius:6px;background:var(--soft);color:var(--ink2);white-space:nowrap}
.rv-chip.high{background:var(--highbg);color:var(--highfg)}.rv-chip.medium{background:var(--medbg);color:var(--medfg)}.rv-chip.q{background:var(--warnbg);color:var(--warnfg)}
.rv-chip.st-fixed,.rv-chip.st-partly{background:var(--okbg);color:var(--okfg)}.rv-chip.st-legacy,.rv-chip.st-data,.rv-chip.st-bydesign{background:var(--infobg);color:var(--infofg)}
.rv-chip .d{width:6px;height:6px;border-radius:50%;background:currentColor}
.rv-chip.dec{font-weight:600;padding:2px 4px 2px 10px}.rv-chip.dec.approved{background:var(--okbg);color:var(--okfg)}.rv-chip.dec.rework{background:var(--warnbg);color:var(--warnfg)}
.rv-chip.dec button{border:0;border-radius:4px;padding:1px 8px;font-size:12px;font-weight:600;cursor:pointer;background:var(--surface);color:inherit}
.rv-h1{margin:12px 0 0;font-size:28px;line-height:1.25;font-weight:700;letter-spacing:-.015em;text-wrap:balance}
.rv-where{margin-top:6px;font-size:13.5px;color:var(--mut);display:flex;flex-wrap:wrap;gap:2px 14px}
.rv-members{margin-top:12px;display:flex;flex-wrap:wrap;align-items:center;gap:6px;font-size:13px;color:var(--ink2)}
.rv-members button{font:600 12px/1.5 "JetBrains Mono",Consolas,monospace;padding:1px 7px;border-radius:5px;background:var(--soft);color:var(--ink2);border:1px solid transparent;cursor:pointer}
.rv-members button[aria-pressed=true]{border-color:var(--acc);color:var(--acc)}
.rv-sect{margin-top:18px}
.rv-issue{margin:6px 0 0;font-size:17px;line-height:1.65;max-width:72ch;white-space:pre-line}
.rv-note{margin-top:12px;display:flex;gap:10px;align-items:flex-start;padding:10px 14px;border-radius:8px;max-width:80ch;font-size:14.5px;background:var(--soft);color:var(--ink2)}
.rv-note svg{flex:none;margin-top:3px}.rv-note.ok{background:var(--okbg);color:var(--okfg)}.rv-note.reply{background:var(--accsoft);color:var(--ink);box-shadow:inset 3px 0 0 var(--acc)}
.rv-note b{font-weight:600}
.rv-fig{margin:0;background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}
.rv-figbar{flex:none;display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;padding:8px 10px;border-bottom:1px solid var(--line)}
.rv-cap{flex:none;padding:8px 14px;border-bottom:1px solid var(--line);font-size:13.5px;color:var(--ink2)}.rv-cap .rv-cid{font:600 12px/1 "JetBrains Mono",Consolas,monospace;color:var(--acc);margin-right:6px}
.rv-figbody{flex:1;min-height:0;display:flex;flex-wrap:wrap;align-items:flex-start;gap:18px;padding:18px;background:var(--shotbg);overflow:auto;align-content:flex-start}
.rv-pane{flex:1 1 280px;min-width:0}.rv-pane .rv-lbl{margin-bottom:8px}
.rv-shotbtn{display:block;width:100%;border:0;padding:0;background:transparent;cursor:zoom-in}
.rv-img{display:block;max-width:100%;height:auto;margin:0 auto;border-radius:6px;background:#FFFFFF;box-shadow:0 0 0 1px var(--imgline),0 4px 14px rgba(0,0,0,.10)}
.rv-noimg{border:1px dashed var(--line2);border-radius:8px;height:160px;display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:14px;text-align:center;padding:0 16px}
.rv-h2{margin:0;font-size:16px;font-weight:600}
.rv-opts{margin-top:10px;display:flex;flex-direction:column;gap:6px}
.rv-opt{display:flex;gap:12px;align-items:flex-start;width:100%;text-align:left;cursor:pointer;border-radius:10px;padding:12px 14px;border:1px solid var(--line);background:var(--surface);color:var(--ink);font-size:15px;line-height:1.5}
.rv-opt:hover{border-color:var(--line2);background:var(--soft)}.rv-opt[aria-pressed=true]{border-color:var(--acc);background:var(--accsoft)}
.rv-radio{flex:none;width:18px;height:18px;margin-top:2px;border-radius:50%;border:1.5px solid var(--ring);background:var(--surface);display:flex;align-items:center;justify-content:center}
.rv-opt[aria-pressed=true] .rv-radio{border-color:var(--acc)}.rv-opt[aria-pressed=true] .rv-radio:after{content:"";width:8px;height:8px;border-radius:50%;background:var(--acc)}
.rv-opt .t{flex:1;min-width:0}.rv-rec{flex:none;font-size:11.5px;font-weight:500;color:var(--okfg);background:var(--okbg);border-radius:5px;padding:1px 8px;margin-top:1px}
.rv-why{margin:10px 0 0;font-size:14px;color:var(--ink2);max-width:80ch}.rv-why b{color:var(--ink);font-weight:600}
.rv-det{margin-top:16px;border-top:1px solid var(--line);padding-top:10px}.rv-det summary{cursor:pointer;font-size:13.5px;color:var(--mut);font-weight:500;width:max-content}.rv-det summary:hover{color:var(--ink)}
.rv-det dl{display:grid;grid-template-columns:130px minmax(0,1fr);gap:4px 14px;margin:10px 0 0;font-size:13.5px}.rv-det dt{color:var(--mut)}.rv-det dd{margin:0;overflow-wrap:anywhere}
.rv-cm{margin-top:14px}.rv-cm label{display:block;font-size:13.5px;font-weight:600}.rv-cm label span{font-weight:400;color:var(--mut)}
.rv-ta{margin-top:8px;width:100%;min-height:84px;resize:vertical;border:1px solid var(--line2);border-radius:8px;background:var(--surface);color:var(--ink);font-size:15px;line-height:1.55;padding:10px 12px}
.rv-ta::placeholder{color:var(--mut)}.rv-ta:focus{outline:2px solid var(--acc);outline-offset:-1px}
#dock{flex:none;display:flex;align-items:center;gap:10px;padding:10px 16px;background:var(--bar);border-top:1px solid var(--line)}
.rv-nav{border:1px solid var(--line2);background:var(--surface);color:var(--ink);border-radius:8px;padding:10px 14px;font-size:14px;font-weight:500;cursor:pointer;white-space:nowrap}
.rv-nav:hover:not(:disabled){background:var(--soft)}.rv-nav:disabled{opacity:.4;cursor:default}
.rv-auto{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ink2);cursor:pointer;padding:0 4px;white-space:nowrap}.rv-auto input{width:16px;height:16px;accent-color:var(--acc)}
.rv-decs{display:flex;gap:10px}
.rv-dec{display:inline-flex;align-items:center;justify-content:center;gap:8px;border-radius:8px;padding:10px 20px;font-size:14.5px;font-weight:600;cursor:pointer;white-space:nowrap}
.rv-dec:hover{filter:brightness(1.06)}
.rv-dec.rw{border:1px solid var(--line2);background:var(--surface);color:var(--warnfg)}.rv-dec.rw.on{border-color:var(--rwon);background:var(--rwon);color:var(--onrw)}
.rv-dec.ap{border:1px solid var(--apbg);background:var(--apbg);color:var(--apfg)}.rv-dec.ap.on{box-shadow:0 0 0 3px var(--okbg)}
.rv-kbd{font:500 11px/1 "JetBrains Mono",Consolas,monospace;opacity:.7}
#toast{position:fixed;left:50%;bottom:var(--toastb,24px);transform:translateX(-50%);z-index:20;display:flex;align-items:center;gap:12px;padding:8px 8px 8px 16px;border-radius:10px;background:var(--toast);color:var(--toastfg);border:1px solid var(--line2);font-size:14px;box-shadow:0 10px 30px rgba(0,0,0,.28);max-width:calc(100vw - 32px)}
body.m-review{--toastb:80px}body.m-review.compact{--toastb:64px}
#toast #tmsg{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#toast button{flex:none;border:0;cursor:pointer}#tundo{border-radius:6px;padding:6px 12px;font-size:13.5px;font-weight:600;background:var(--toastfg);color:var(--toast)}
#tclose{background:transparent;color:inherit;opacity:.7;font-size:18px;line-height:1;padding:4px 6px}
#help{position:fixed;right:16px;top:60px;z-index:21;width:min(340px,calc(100vw - 32px));background:var(--surface);border:1px solid var(--line2);border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.2);padding:14px 16px;font-size:13.5px}
#help h3{margin:0 0 8px;font-size:14px}#help dl{display:grid;grid-template-columns:auto 1fr;gap:5px 14px;margin:0}#help dt{font:600 12px/1.7 "JetBrains Mono",Consolas,monospace;color:var(--ink2);white-space:nowrap}#help dd{margin:0;color:var(--ink2)}
#zoom{position:fixed;inset:0;z-index:30;background:rgba(10,10,10,.94);display:flex;flex-direction:column;color:#E6E6E4}
.zbar{flex:none;display:flex;align-items:center;gap:12px;padding:10px 16px;font-size:14px}
.zbar .rv-seg{background:rgba(255,255,255,.1)}.zbar .rv-seg button{color:#BDBDBA}.zbar .rv-seg button[aria-pressed=true]{background:rgba(255,255,255,.18);color:#fff}
.zbar .zb{border:1px solid rgba(255,255,255,.28);background:transparent;color:#E6E6E4;border-radius:6px;padding:5px 12px;font-size:13.5px;cursor:pointer}.zbar .zb:hover{background:rgba(255,255,255,.08)}
#zvp{flex:1;position:relative;overflow:hidden;cursor:grab;touch-action:none}#zvp.drag{cursor:grabbing}
#zimg{position:absolute;left:0;top:0;transform-origin:0 0;max-width:none;background:#fff;border-radius:4px;user-select:none;-webkit-user-drag:none}
body.compact .rv-top{padding:6px 12px}
body.compact #rmain{padding:16px 20px 20px}
body.compact .rv-art{max-width:none;grid-template-columns:minmax(260px,var(--split,42%)) 14px minmax(0,1fr);grid-template-areas:"a gut shot" "b gut shot";grid-template-rows:auto 1fr;column-gap:4px;row-gap:16px;align-items:start}
.rv-gut{display:none}
body.compact .rv-gut{display:block;grid-area:gut;position:sticky;top:0;height:calc(100vh - 150px);min-height:320px;cursor:col-resize;touch-action:none;border-radius:6px}
body.compact .rv-gut:after{content:"";position:absolute;left:6px;top:0;bottom:0;width:2px;border-radius:1px;background:var(--line2)}
body.compact .rv-gut:hover:after,body.compact .rv-gut:focus-visible:after,body.resizing .rv-gut:after{background:var(--acc);width:3px;left:5.5px}
body.compact .rv-gut:focus-visible{outline:2px solid var(--acc);outline-offset:-2px}
body.resizing{cursor:col-resize;user-select:none}body.resizing img{pointer-events:none}
.rv-figbody.lay-row{flex-wrap:nowrap}.rv-figbody.lay-row .rv-pane{flex:1 1 0}
.rv-figbody.lay-col{flex-direction:column;flex-wrap:nowrap;align-items:stretch}.rv-figbody.lay-col .rv-pane{flex:none;width:100%}
body.compact .rv-figbody.lay-col .rv-img{max-height:none}
body.compact .rv-shot{position:sticky;top:0;height:calc(100vh - 150px);min-height:320px}
body.compact .rv-fig{height:100%}
body.compact .rv-img{max-height:calc(100vh - 260px);width:auto}
body.compact .rv-h1{font-size:21px;margin-top:8px}
body.compact .rv-issue{font-size:15px;line-height:1.55}
body.compact .rv-opt{padding:8px 12px;font-size:14px}
body.compact .rv-ta{min-height:52px;font-size:14px;padding:8px 10px}
body.compact #dock{padding:7px 12px}body.compact .rv-nav{padding:7px 12px}body.compact .rv-dec{padding:7px 16px}
body.compact .rv-area{display:none}
body.m-list .rv-dens{display:none}
#list{width:100%;max-width:1280px;margin:0 auto;padding:8px 24px 64px}
.lv-hero{padding:28px 0 4px}.lv-eye{font-size:12px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}
.lv-hero h1{font-size:30px;line-height:1.2;margin:6px 0;letter-spacing:-.01em}.lv-hero p{margin:0}
.lv-toc{display:flex;flex-wrap:wrap;gap:4px 18px;margin:12px 0 0;font-size:13px}.lv-toc a{color:var(--mut)}
#list h2{font-size:19px;margin:36px 0 12px;display:flex;align-items:baseline;gap:10px;scroll-margin-top:80px}#list h2 .n{font-size:13px;font-weight:500;color:var(--mut)}
.lv-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:22px 0 12px}
.lv-kpi{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--card)}
.lv-kpi b{font-size:26px;line-height:1.1;display:block;font-variant-numeric:tabular-nums}.lv-kpi span{color:var(--mut);font-size:13px}
.lv-bar{display:flex;height:8px;border-radius:6px;overflow:hidden;background:var(--soft);margin:4px 0 6px}.lv-bar i{display:block;height:100%}
.lv-legend{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12px;color:var(--mut)}.lv-legend i{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px}
.b-fixed,.b-partly{background:var(--ok)}.b-decision,.b-open{background:var(--warn)}.b-legacy,.b-data{background:var(--acc)}.b-bydesign{background:var(--ring)}
.lv-tools{position:sticky;top:57px;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 0;background:var(--bg)}
.lv-chk{display:flex;gap:6px;align-items:center;cursor:pointer;font-size:13px;color:var(--ink2)}.lv-chk input{accent-color:var(--acc)}
.lv-cards{display:flex;flex-direction:column;gap:10px;margin-top:6px}
.lc{display:flex;gap:16px;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--card);scroll-margin-top:120px}
.lc.k-approved{border-color:color-mix(in srgb,var(--ok) 40%,var(--line))}.lc.k-rework{border-color:color-mix(in srgb,var(--warn) 45%,var(--line))}
.lc-m{flex:1;min-width:0}.lc h3{margin:8px 0 0;font-size:16px;line-height:1.35}
.lc-t{border:0;background:none;padding:0;text-align:left;cursor:pointer;font:inherit;font-weight:600;color:var(--ink)}.lc-t:hover{color:var(--acc)}
.lc-p{margin:4px 0 0;color:var(--ink2);font-size:14px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.lc-f{display:flex;flex-wrap:wrap;gap:6px 8px;align-items:center;margin-top:10px;font-size:13px}
.lc-b{border:1px solid var(--line2);background:var(--surface);border-radius:7px;padding:4px 11px;font-size:13px;font-weight:500;cursor:pointer;white-space:nowrap}.lc-b:hover{background:var(--soft)}
.lc-b.ap.on{background:var(--apbg);border-color:var(--apbg);color:var(--apfg)}.lc-b.rw.on{background:var(--rwon);border-color:var(--rwon);color:var(--onrw)}
.lc-th{flex:none;display:flex;gap:6px;align-items:flex-start}
.lc-th button{border:0;padding:0;background:var(--shotbg);border-radius:6px;width:150px;height:96px;display:flex;align-items:center;justify-content:center;overflow:hidden;cursor:pointer}
.lc-th img{max-width:100%;max-height:100%;display:block}
.lv-panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--card);overflow:hidden}
.lv-tw{overflow-x:auto}#list table{border-collapse:collapse;width:100%}#list th,#list td{border-bottom:1px solid var(--line);padding:8px 12px;text-align:left;vertical-align:top;font-size:13.5px}
#list th{background:var(--soft);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);position:sticky;top:0}
#list tr:last-child td{border-bottom:0}td.num{text-align:right;font-variant-numeric:tabular-nums}
td.pass{background:var(--okbg);color:var(--okfg)}td.fail{background:var(--warnbg);color:var(--warnfg);font-weight:600}td.na{color:var(--ring)}
.lv-sec{margin-top:12px}.lv-sec>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:10px;padding:14px 18px;font-weight:600}
.lv-sec>summary::-webkit-details-marker{display:none}.lv-sec>summary:before{content:"›";font-size:20px;line-height:1;color:var(--mut);transition:transform .15s}
.lv-sec[open]>summary:before{transform:rotate(90deg)}.lv-sec>summary .n{font-weight:400;font-size:13px;color:var(--mut)}.lv-sec[open]>summary{border-bottom:1px solid var(--line)}
.lv-note{padding:12px 18px;margin:0;font-size:13px}.lv-notes{margin:0;padding:14px 18px 14px 36px}.lv-notes li{margin:3px 0}
.lv-ctool{padding:10px 18px;border-bottom:1px solid var(--line)}.lv-cov{overflow:auto;max-height:75vh}.lv-cov td,.lv-cov th{white-space:nowrap;font-size:12px!important;padding:5px 8px!important}
.lv-foot{margin-top:40px;color:var(--mut);font-size:12px;text-align:center}
@media (max-width:1100px){body.compact .rv-art{grid-template-columns:minmax(0,1fr);grid-template-areas:"a" "shot" "b";grid-template-rows:none}body.compact .rv-gut{display:none}body.compact .rv-shot{position:static;height:auto;min-height:0}body.compact .rv-img{max-height:none}}
@media (max-width:960px){#rail{position:absolute;top:0;bottom:0;left:0;z-index:7;width:min(320px,86vw);box-shadow:0 12px 32px rgba(0,0,0,.3)}body.rail-open .rv-scrim{display:block;position:absolute;inset:0;z-index:6;border:0;padding:0;background:rgba(10,10,10,.45);cursor:pointer}#rmain{padding:20px 20px 28px}}
@media (max-width:760px){.rv-hide-md{display:none!important}#dock{flex-wrap:wrap;gap:8px}.rv-decs{order:-1;flex:1 1 100%}.rv-dec{flex:1;padding:10px 12px}.rv-grow{display:none}.rv-nav{flex:1}.rv-h1{font-size:23px}.rv-issue{font-size:16px}.rv-kbd{display:none}body.m-review{--toastb:128px}
.lc{flex-direction:column}.lc-th button{width:120px;height:80px}#list{padding:8px 16px 48px}.lv-tools{position:static}}
@media (max-width:520px){.rv-hide-sm{display:none!important}#rmain,body.compact #rmain{padding:14px 14px 20px}.rv-figbody{padding:10px}.rv-det dl{grid-template-columns:1fr}}
</style></head><body class="m-review">
<div id="app">
<header class="rv-top">
 <a class="rv-ib" id="bhub" href="/" title="All reviews (review hub)" aria-label="All reviews"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg></a>
 <button class="rv-ib" type="button" id="brail" title="Show or hide the step list ( [ )" aria-label="Show or hide the step list"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg></button>
 <div class="rv-ttl"><b id="ttitle"></b><span id="tsub" class="rv-hide-sm"></span></div>
 <div class="rv-prog rv-hide-md" aria-hidden="true"><i id="pap" style="background:var(--ok)"></i><i id="prw" style="background:var(--warn)"></i><i id="pcm" style="background:var(--acc)"></i></div>
 <span class="rv-pill" id="sync"></span>
 <span class="rv-seg" role="group" aria-label="View"><button type="button" id="mrev">Review</button><button type="button" id="mlist">List</button></span>
 <span class="rv-seg rv-dens rv-hide-sm" role="group" aria-label="Density"><button type="button" id="dcomfy">Comfortable</button><button type="button" id="dcomp">Compact</button></span>
 <button class="rv-ib" type="button" id="btheme"></button>
 <button class="rv-ib rv-hide-sm" type="button" id="bhelp" title="Keyboard shortcuts ( ? )" aria-label="Keyboard shortcuts"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/></svg></button>
 <button class="rv-ghost rv-hide-md" type="button" id="bexp" title="Download the decisions as JSON">Export</button>
</header>
<div id="review">
 <button class="rv-scrim" type="button" id="scrim" aria-label="Close the step list"></button>
 <nav id="rail" aria-label="Steps"><div class="rv-railh"><span class="rv-lbl">Steps</span><span class="rv-seg" id="rf"><button type="button" data-f="all">All</button><button type="button" data-f="undecided">Undecided</button><button type="button" data-f="q">Questions</button></span></div><div class="rv-rows" id="rows"></div></nav>
 <main id="rmain"></main>
</div>
<div id="dock">
 <button class="rv-nav" type="button" id="fprev" title="Previous step ( ← )">← <span class="rv-hide-sm">Previous</span></button>
 <label class="rv-auto rv-hide-md"><input type="checkbox" id="fauto"> Jump to next undecided</label>
 <span class="rv-grow sp"></span>
 <div class="rv-decs"><button class="rv-dec rw" type="button" id="drw">Needs work <span class="rv-kbd">N</span></button><button class="rv-dec ap" type="button" id="dap"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg><span id="daplbl">Approve</span> <span class="rv-kbd">A</span></button></div>
 <span class="rv-grow sp"></span>
 <button class="rv-nav" type="button" id="fnext" title="Next step ( → )"><span class="rv-hide-sm">Next</span> →</button>
</div>
<div id="list">__LIST__</div>
</div>
<div id="toast" role="status" hidden><span id="tmsg"></span><button type="button" id="tundo">Undo <span class="rv-kbd">Z</span></button><button type="button" id="tclose" aria-label="Dismiss">×</button></div>
<div id="help" hidden><h3>Keyboard shortcuts</h3><dl><dt>A</dt><dd>Approve (option shown on the button)</dd><dt>N</dt><dd>Needs work</dd><dt>C</dt><dd>Write a comment</dd><dt>Z · Ctrl+Z</dt><dd>Undo the last decision</dd><dt>← → · J K</dt><dd>Previous / next step</dd><dt>[</dt><dd>Show or hide the step list</dd><dt>1 2 3</dt><dd>__LB__ / __LA__ / both</dd><dt>L</dt><dd>Both screenshots next to or below each other</dd><dt>Drag the divider</dt><dd>Wider description or screenshot (compact; ← → when focused, double-click resets)</dd><dt>F</dt><dd>Screenshot full screen</dd><dt>Esc</dt><dd>Leave the comment box, close panels</dd><dt>?</dt><dd>This list</dd></dl></div>
<div id="zoom" hidden><div class="zbar"><b id="zid" style="font-family:'JetBrains Mono',Consolas,monospace"></b><span class="rv-seg" id="ztabs"></span><span class="mut rv-hide-sm" style="color:#9B9A97">Scroll to zoom · drag to pan · double-click 100 % · 0 fits</span><span class="sp"></span><span id="zpct" style="font-variant-numeric:tabular-nums;color:#BDBDBA"></span><button class="zb" type="button" id="zfit">Fit</button><button class="zb" type="button" id="zclose">Close · Esc</button></div><div id="zvp"><img id="zimg" alt=""></div></div>
<input type="file" id="ifile" accept=".json,application/json" hidden>
<script>
(()=>{
const DATA=__DATA__,IMG=__IMG__,PRE=__PRELOAD__,KEY=DATA.key,TITLE=DATA.title,LB=DATA.lb||'Before',LA=DATA.la||'After';
const $=id=>document.getElementById(id),body=document.body,root=document.documentElement;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const store={get(k,d){try{const v=localStorage.getItem(k);return v?JSON.parse(v):d}catch(e){return d}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v));return true}catch(e){return false}}};
const now=()=>new Date().toISOString();
let D=store.get(KEY,{})||{};
const merge=src=>{let n=0;for(const[k,v]of Object.entries(src||{})){if(v&&typeof v==='object'&&(!D[k]||String(v.at||'')>String(D[k].at||''))){D[k]=v;n++}}return n};
merge(PRE);
const P=Object.assign({theme:'auto',compact:true,rail:null,auto:true,mode:'review',lay:'row',split:null},store.get(KEY+'-prefs',{}));
const savePrefs=()=>store.set(KEY+'-prefs',P);
const narrow=matchMedia('(max-width:960px)');
if(P.rail===null)P.rail=!narrow.matches;
if(narrow.matches)P.rail=false;

const F=DATA.findings,FI=Object.fromEntries(F.map(f=>[f.id,f]));
const STEPS=[];{const g=new Map();for(const f of F){if(f.group){let s=g.get(f.group);if(!s){s={key:f.group,grp:DATA.groups[f.group]||{title:f.group,options:[]},ids:[]};g.set(f.group,s);STEPS.push(s)}s.ids.push(f.id)}else STEPS.push({key:f.id,grp:null,ids:[f.id]})}}
const SEVR={high:0,medium:1,low:2};
STEPS.forEach((s,i)=>{s.i=i;s.f=FI[s.ids[0]];s.b=s.grp||DATA.briefs[s.f.id]||null;s.open=!!(s.b&&s.b.open);
 s.sev=s.ids.map(id=>FI[id].sev).sort((a,b)=>(SEVR[a]??3)-(SEVR[b]??3))[0]||'';s.title=s.grp?(s.grp.title||s.key):s.f.title;s.label=s.grp?s.key:s.f.id;
 s.opts=(s.b&&s.b.options)||[];s.recn=(s.b&&s.b.recn)||0});
const kind=id=>{const d=D[id]||{};return d.decision==='approved'?'approved':d.decision==='rework'?'rework':(d.comment||'').trim()?'commented':'undecided'};
const skind=s=>s.ids.some(id=>kind(id)==='undecided')?'undecided':kind(s.ids[0]);
const ent=s=>D[s.ids[0]]||{};
const optOf=s=>s.opts.length?(ent(s).option||s.recn||0):0;
const stepOf=id=>STEPS.find(s=>s.key===id||s.ids.includes(id));
const UI={},ui=s=>UI[s.key]||(UI[s.key]={m:0,v:null,p:0}),ik=(s,m)=>m.id+(ui(s).p?'~'+ui(s).p:'');
const ICON={approved:'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
 rework:'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" aria-hidden="true"><path d="M12 5v9"/><path d="M12 19h.01"/></svg>',
 commented:'<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/></svg>',undecided:''};
const CHECK='<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>';
const INFO='<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8h.01"/></svg>';
const SEVL={high:'High',medium:'Medium',low:'Low'};

let cur=0,railF='all',hist=[],toastT=null,lsF='all',ldF='all';
{const h=decodeURIComponent(location.hash.slice(1));const s=h&&stepOf(h);const u=STEPS.findIndex(s=>skind(s)==='undecided');cur=s?s.i:Math.max(0,u)}

const API='api/decisions',HTTP=location.protocol.startsWith('http');
let sync={mode:HTTP?'connecting':'offline',at:null},pushT=null,pushing=false,again=false;
function persist(){store.set(KEY,D);if(sync.mode!=='offline'){clearTimeout(pushT);pushT=setTimeout(push,300)}renderSync()}
async function push(){if(pushing){again=true;return}pushing=true;if(sync.mode!=='error')sync.mode='saving';renderSync();
 try{const r=await fetch(API,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({report:TITLE,decisions:D})});if(!r.ok)throw new Error('HTTP '+r.status);
  const j=await r.json();if(merge(j.decisions)){store.set(KEY,D);safeRender()}sync={mode:'saved',at:new Date()}}
 catch(e){sync.mode='error';clearTimeout(pushT);pushT=setTimeout(push,5000)}
 pushing=false;renderSync();if(again){again=false;push()}}
async function pull(){if(!HTTP||pushing)return;try{const r=await fetch(API,{cache:'no-store'});if(!r.ok)throw 0;const j=await r.json(),srv=j.decisions||{};
 if(merge(srv)){store.set(KEY,D);safeRender()}const ahead=Object.keys(D).some(k=>!srv[k]||String(D[k].at||'')>String(srv[k].at||''));
 if(sync.mode==='connecting')sync={mode:'saved',at:j.saved?new Date(j.saved):null};if(ahead)push();else renderSync()}
 catch(e){if(sync.mode==='connecting')sync.mode='offline';renderSync()}}
const typing=()=>{const a=document.activeElement;return a&&(a.tagName==='TEXTAREA'||a.tagName==='INPUT'&&a.type==='text')};
function safeRender(){if(typing()){renderRail();renderTop();renderDock()}else render()}
function ago(d){if(!d)return'';const s=(Date.now()-d)/1000;if(s<45)return'just now';if(s<3600)return Math.round(s/60)+' min ago';return d.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}
function renderSync(){const e=$('sync'),m=sync.mode;let cls='',txt,tip;
 if(m==='saved'){cls='ok';txt='Saved'+(sync.at?' · '+ago(sync.at):'');tip='Every change is written to report/review-decisions.json'}
 else if(m==='saving'){txt='Saving…';tip='Writing to report/review-decisions.json'}
 else if(m==='connecting'){txt='Connecting…';tip='Looking for serve-report.py'}
 else if(m==='error'){cls='warn';txt='Not saved, retrying';tip='The review server did not answer; changes are kept in this browser and sent again'}
 else{cls='warn';txt='Only in this browser';tip='Opened without serve-report.py: decisions stay in this browser. Use Export to keep them.'}
 e.className='rv-pill '+cls;e.title=tip;e.innerHTML=(cls==='ok'?CHECK.replace(/17/g,'15'):cls==='warn'?INFO.replace(/17/g,'15'):'')+'<span class="rv-hide-md">'+esc(txt)+'</span>'}

function toast(msg,canUndo){$('tmsg').textContent=msg;$('tundo').hidden=!canUndo;$('toast').hidden=false;clearTimeout(toastT);toastT=setTimeout(()=>$('toast').hidden=true,7000)}
function setStep(s,patch,undoable){if(undoable){hist.push({key:s.key,prev:s.ids.map(id=>({decision:(D[id]||{}).decision||'',option:(D[id]||{}).option||0}))});if(hist.length>300)hist.shift()}
 const at=now();s.ids.forEach(id=>{D[id]=Object.assign({},D[id],patch,{at})});persist()}
function undo(){const h=hist.pop();if(!h){toast('Nothing to undo',false);return}const s=STEPS.find(x=>x.key===h.key);const at=now();
 s.ids.forEach((id,i)=>{D[id]=Object.assign({},D[id],h.prev[i]||{decision:'',option:0},{at})});persist();if(P.mode==='review')go(s.i);else render();toast('Undone · '+s.label,false)}
function nextOpen(from){for(let k=1;k<=STEPS.length;k++){const j=(from+k)%STEPS.length;if(skind(STEPS[j])==='undecided')return j}return -1}
function decide(s,v){if(!s)return;const was=ent(s).decision||'',nv=was===v?'':v,patch={decision:nv};if(nv==='approved'&&s.opts.length&&!ent(s).option&&s.recn)patch.option=s.recn;
 setStep(s,patch,true);let msg=(nv==='approved'?(s.opts.length&&optOf(s)?'Approved option '+optOf(s):'Approved'):nv==='rework'?'Needs work':'Decision removed')+' · '+s.label;
 const j=nextOpen(s.i);if(nv&&j<0)msg+=' · every step has a decision';toast(msg,true);render();
 if(nv&&P.mode==='review'&&P.auto&&j>=0){const from=s.i;setTimeout(()=>{if(cur===from)go(j)},350)}}
function go(i){if(!STEPS.length)return;cur=Math.min(STEPS.length-1,Math.max(0,i));if(narrow.matches&&P.rail){P.rail=false}render();$('rmain').scrollTop=0;
 try{history.replaceState(null,'','#'+encodeURIComponent(STEPS[cur].key))}catch(e){}}
function setRail(on){P.rail=on;savePrefs();renderTop();renderRail()}
function setMode(m){P.mode=m;savePrefs();render();if(m==='list'){const c=document.querySelector('.lc[data-i="'+cur+'"]');if(c)c.scrollIntoView({block:'center'})}else{$('rmain').scrollTop=0;window.scrollTo(0,0)}}
function setView(v){const s=STEPS[cur];if(!s)return;const m=FI[s.ids[ui(s).m]],K=ik(s,m),B=IMG[K+':b'],A=IMG[K+':a'];if(v==='before'?!B:v==='after'?!A:!(A&&B))return;ui(s).v=v;renderStep()}
function focusComment(){const t=$('rcomment');if(t){t.focus();t.scrollIntoView({block:'center'})}}

function counts(){const c={approved:0,rework:0,commented:0,undecided:0};STEPS.forEach(s=>c[skind(s)]++);return c}
function renderTop(){const c=counts(),n=STEPS.length,dn=n-c.undecided;
 $('ttitle').textContent=TITLE;$('tsub').textContent=(P.mode==='review'&&n?'Step '+(cur+1)+' of '+n+' · ':n+' steps · ')+dn+' decided';
 const pc=x=>(n?100*x/n:0)+'%';$('pap').style.width=pc(c.approved);$('prw').style.width=pc(c.rework);$('pcm').style.width=pc(c.commented);
 body.classList.toggle('m-review',P.mode==='review');body.classList.toggle('m-list',P.mode==='list');body.classList.toggle('compact',!!P.compact);body.classList.toggle('rail-open',!!P.rail&&P.mode==='review');
 $('mrev').setAttribute('aria-pressed',P.mode==='review');$('mlist').setAttribute('aria-pressed',P.mode==='list');
 $('dcomfy').setAttribute('aria-pressed',!P.compact);$('dcomp').setAttribute('aria-pressed',!!P.compact);applySplit();
 $('brail').hidden=P.mode!=='review';$('brail').setAttribute('aria-expanded',!!P.rail);
 root.dataset.theme=P.theme;const tn={auto:'Theme: follows the system',light:'Theme: light',dark:'Theme: dark'}[P.theme];$('btheme').title=tn+' (click to change)';$('btheme').setAttribute('aria-label',tn);
 $('btheme').innerHTML=P.theme==='light'?'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
  :P.theme==='dark'?'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>'
  :'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 1 0 18Z" fill="currentColor"/></svg>'}
function renderRail(){document.querySelectorAll('#rf button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.f===railF));
 $('rows').innerHTML=STEPS.filter(s=>s.i===cur||railF==='all'||(railF==='undecided'?skind(s)==='undecided':s.open)).map(s=>{const k=skind(s);
  return '<button class="rv-row k-'+k+'" type="button" data-go="'+s.i+'"'+(s.i===cur?' aria-current="step"':'')+'><span class="rv-dot k-'+k+'">'+ICON[k]+'</span><span class="rv-rt"><span class="rv-rl"><span class="rv-rid">'+esc(s.label)+'</span>'
   +(s.grp?'<span class="rv-tag">'+s.ids.length+' findings</span>':'')+(s.open?'<span class="rv-tag q">question</span>':'')+(s.f.status==='fixed'?'<span class="rv-tag fx">fixed</span>':'')
   +'<span class="rv-sevd '+esc(s.sev)+'" title="'+esc(SEVL[s.sev]||'')+'"></span></span><span class="rv-rtitle">'+esc(s.title)+'</span></span></button>'}).join('');
 const r=$('rows').querySelector('[aria-current]');if(r&&P.rail)r.scrollIntoView({block:'nearest'})}
function chips(s,withDec){const e=ent(s),k=skind(s),f=s.f;let h='<span class="rv-id">'+esc(s.grp?'Group · '+s.ids.length:f.id)+'</span>';
 if(s.sev)h+='<span class="rv-chip '+esc(s.sev)+'"><span class="d"></span>'+esc(SEVL[s.sev]||s.sev)+'</span>';
 h+='<span class="rv-chip st-'+f.status+'">'+esc(f.statusLabel)+'</span>';if(s.open)h+='<span class="rv-chip q">Open question</span>';
 if(withDec&&(k==='approved'||k==='rework'))h+='<span class="rv-chip dec '+k+'">'+(k==='approved'?(optOf(s)?'Approved · option '+optOf(s):'Approved'):'Needs work')+'<button type="button" data-act="clear" title="Remove this decision">Undo</button></span>';
 else if(withDec&&k==='commented')h+='<span class="rv-chip">Commented</span>';return h}
function renderStep(){const main=$('rmain'),s=STEPS[cur];if(!s){main.innerHTML='<p class="mut">No findings.</p>';return}
 const f=s.f,b=s.b,u=ui(s),mi=Math.min(u.m,s.ids.length-1),m=FI[s.ids[mi]],K=ik(s,m),B=IMG[K+':b'],A=IMG[K+':a'];
 let v=u.v;if(!A)v='before';else if(!B)v='after';else v=v||'both';
 const issue=(b&&b.issue)||f.issue;let h='<article class="rv-art"><div class="rv-a">';
 if(f.area)h+='<div class="rv-area">Area '+esc(f.areaKey)+' · '+esc(f.area)+'</div>';
 h+='<div class="rv-chips">'+chips(s,true)+'</div><h1 class="rv-h1">'+esc(s.title)+'</h1>';
 h+='<div class="rv-where"><span>'+esc(f.page)+(f.route?' · <code>'+esc(f.route)+'</code>':'')+'</span><span>'+esc([f.env,f.vp].filter(Boolean).join(' · '))+'</span></div>';
 if(s.grp)h+='<div class="rv-members"><span>One decision covers</span>'+s.ids.map((id,i)=>'<button type="button" data-act="member" data-m="'+i+'" aria-pressed="'+(i===mi)+'" title="'+esc(FI[id].title)+'">'+esc(id)+'</button>').join('')+'</div>';
 h+='<div class="rv-sect"><div class="rv-lbl">What\'s wrong</div><p class="rv-issue">'+esc(issue)+'</p>';
 if(f.fix)h+='<div class="rv-note'+(f.changed?' ok':'')+'">'+(f.changed?CHECK:INFO)+'<div><b>'+(f.changed?'What changed.':'Decision so far.')+'</b> '+esc(f.fix)+'</div></div>';
 if(b&&b.reply)h+='<div class="rv-note reply">'+INFO+'<div><b>Answer to your comment.</b> '+esc(b.reply)+'</div></div>';
 h+='</div></div><div class="rv-gut" role="separator" aria-orientation="vertical" aria-label="Width of the description" aria-valuemin="20" aria-valuemax="75" aria-valuenow="'+Math.round(P.split||42)+'" tabindex="0" title="Drag to resize · double-click to reset"></div>'
  +'<div class="rv-shot"><figure class="rv-fig"><div class="rv-figbar"><span class="rv-seg" role="group" aria-label="Screenshot">'
  +'<button type="button" data-act="view" data-v="before" aria-pressed="'+(v==='before')+'"'+(B?'':' disabled')+'>'+esc(LB)+' <span class="rv-kbd">1</span></button>'
  +'<button type="button" data-act="view" data-v="after" aria-pressed="'+(v==='after')+'"'+(A?'':' disabled')+'>'+esc(LA)+' <span class="rv-kbd">2</span></button>'
  +'<button type="button" data-act="view" data-v="both" aria-pressed="'+(v==='both')+'"'+(A&&B?'':' disabled')+'>Both <span class="rv-kbd">3</span></button></span>';
 if(v==='both')h+='<span class="rv-seg" role="group" aria-label="Arrangement of both screenshots" title="Arrangement ( L )">'
  +'<button type="button" data-act="lay" data-l="row" aria-pressed="'+(P.lay!=='col')+'" aria-label="Next to each other"><svg width="16" height="14" viewBox="0 0 16 14" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="1" y="1.5" width="6" height="11" rx="1.2"/><rect x="9" y="1.5" width="6" height="11" rx="1.2"/></svg><span class="rv-hide-sm"> Next to each other</span></button>'
  +'<button type="button" data-act="lay" data-l="col" aria-pressed="'+(P.lay==='col')+'" aria-label="Below each other"><svg width="16" height="14" viewBox="0 0 16 14" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="2" y="0.8" width="12" height="5.4" rx="1.2"/><rect x="2" y="7.8" width="12" height="5.4" rx="1.2"/></svg><span class="rv-hide-sm"> Below each other</span></button></span>';
 if(!A)h+='<span class="mut rv-hide-sm" style="font-size:12.5px">'+(DATA.custom?'No '+esc(LA)+' screenshot':f.changed?'No after image was taken':'No after image until it is fixed')+'</span>';
 h+='<span class="sp"></span>'+((A||B)?'<button class="rv-ib" type="button" data-act="zoom" title="Full screen ( F )" aria-label="Open the screenshot full screen" style="width:32px;height:32px"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg></button>':'')+'</div>';
 if(s.grp){const own=m.own&&m.own!==issue?m.own:'';h+='<div class="rv-cap"><span class="rv-cid">'+esc(m.id)+'</span>'+esc(m.title)+(own?' <span class="mut">· '+esc(own)+'</span>':'')+'</div>'}
 if(m.shots&&m.shots.length>1)h+='<div class="rv-members rv-shots"><span>Screenshots</span>'+m.shots.map((c,i)=>'<button type="button" data-act="shot" data-p="'+i+'" aria-pressed="'+(i===(u.p||0))+'">'+esc(c)+'</button>').join('')+'</div>';
 h+='<div class="rv-figbody'+(v==='both'?(P.lay==='col'?' lay-col':' lay-row'):'')+'">';
 const pane=(w,src,lbl)=>'<div class="rv-pane">'+(v==='both'?'<div class="rv-lbl">'+lbl+'</div>':'')+(src?'<button class="rv-shotbtn" type="button" data-act="zoom" data-w="'+w+'" aria-label="Enlarge the '+lbl.toLowerCase()+' screenshot"><img class="rv-img" src="'+src+'" alt="'+lbl+': '+esc(m.title)+'"></button>':'<div class="rv-noimg">No screenshot</div>')+'</div>';
 if(v!=='after')h+=pane('b',B,LB);if(v!=='before'&&A)h+=pane('a',A,LA);
 h+='</div></figure></div><div class="rv-b">';
 if(s.opts.length){const o=optOf(s);h+='<section><div style="display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px"><h2 class="rv-h2">How should it be handled?</h2>'+(b.effort?'<span class="mut" style="font-size:12.5px">Effort of the recommendation: '+esc(b.effort)+'</span>':'')+'</div><div class="rv-opts">'
  +s.opts.map((t,i)=>'<button class="rv-opt" type="button" data-act="opt" data-n="'+(i+1)+'" aria-pressed="'+(o===i+1)+'"><span class="rv-radio"></span><span class="t">'+esc(t)+'</span>'+(s.recn===i+1?'<span class="rv-rec">Recommended</span>':'')+'</button>').join('')+'</div>'
  +(b.rec?'<p class="rv-why"><b>Recommendation.</b> '+esc(b.rec)+'</p>':'')+'</section>'}
 else if(b&&b.rec)h+='<p class="rv-why" style="margin-top:0"><b>Recommendation.</b> '+esc(b.rec)+'</p>';
 const dl=[['Observed',m.desc!==issue?m.desc:''],['Measured',m.measured],['Expected',m.expected],['Suspected cause',m.cause],['Also affects',m.also],['Check',m.check?m.check+' · '+m.checkTitle:''],['Where',s.grp?m.page+(m.route?' · '+m.route:''):'']].filter(x=>x[1]);
 if(dl.length)h+='<details class="rv-det"'+(u.det?' open':'')+'><summary>Measurements and technical details'+(s.grp?' · '+esc(m.id):'')+'</summary><dl>'+dl.map(x=>'<dt>'+x[0]+'</dt><dd>'+esc(x[1])+'</dd>').join('')+'</dl></details>';
 h+='<div class="rv-cm"><label for="rcomment">'+(s.grp?'Comment for all '+s.ids.length+' findings':'Your comment')+' <span>(optional, saved as you type)</span></label><textarea id="rcomment" class="rv-ta" placeholder="What should change, or a question for the next round">'+esc(ent(s).comment||'')+'</textarea></div></div></article>';
 main.innerHTML=h;
 const ta=$('rcomment'),flush=()=>{clearTimeout(ta._t);if(ta.value===(ent(s).comment||''))return;const at=now();s.ids.forEach(id=>{D[id]=Object.assign({},D[id],{comment:ta.value,at})});persist();renderRail();renderTop()};
 ta.addEventListener('input',()=>{clearTimeout(ta._t);ta._t=setTimeout(flush,400)});ta.addEventListener('blur',flush);
 const det=main.querySelector('.rv-det');if(det)det.addEventListener('toggle',()=>u.det=det.open)}
function renderDock(){const s=STEPS[cur],k=s?skind(s):'',d=s?ent(s).decision:'';
 $('fprev').disabled=cur<=0;$('fnext').disabled=cur>=STEPS.length-1;$('fauto').checked=!!P.auto;
 $('dap').classList.toggle('on',d==='approved');$('drw').classList.toggle('on',d==='rework');
 $('daplbl').textContent=s&&s.opts.length&&optOf(s)?'Approve option '+optOf(s):'Approve';
 $('dap').title=d==='approved'?'Approved: press again to remove ( A )':'Approve ( A )';$('drw').title=d==='rework'?'Marked as needs work: press again to remove ( N )':'Needs work ( N )'}
function renderList(){const hide=$('lhide').checked;let n=0;
 document.querySelectorAll('#lsf button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.s===lsF));document.querySelectorAll('#ldf button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.d===ldF));
 $('lcards').innerHTML=STEPS.filter(s=>{const k=skind(s);return(lsF==='all'||s.ids.some(id=>FI[id].status===lsF))&&(ldF==='all'||k===ldF||(ldF==='q'&&s.open))&&!(hide&&k==='approved'&&ldF!=='approved')}).map(s=>{n++;const k=skind(s),d=ent(s).decision,m=s.f;
  const th=s.ids.slice(0,1).flatMap(id=>[['b',LB],['a',LA]].filter(([w])=>IMG[id+':'+w]).map(([w,l])=>'<button type="button" data-act="lzoom" data-id="'+id+'" data-w="'+w+'" title="'+l+'"><img loading="lazy" src="'+IMG[id+':'+w]+'" alt="'+l+' '+esc(id)+'"></button>')).join('');
  return '<article class="lc k-'+k+'" data-i="'+s.i+'" id="lc-'+esc(s.key)+'"><div class="lc-m"><div class="rv-chips">'+chips(s,false)+(k!=='undecided'?'<span class="rv-chip dec '+k+'" style="padding-right:10px">'+{approved:'Approved'+(optOf(s)?' · option '+optOf(s):''),rework:'Needs work',commented:'Commented'}[k]+'</span>':'')+'</div>'
   +'<h3><button class="lc-t" type="button" data-act="open">'+esc(s.title)+'</button></h3><p class="lc-p">'+esc((s.b&&s.b.issue)||m.issue)+'</p>'
   +'<div class="lc-f"><span class="mut">'+(s.grp?esc(s.ids.join(', ')):esc(m.page))+'</span><span class="sp"></span><button class="lc-b rw'+(d==='rework'?' on':'')+'" type="button" data-act="lrw">Needs work</button><button class="lc-b ap'+(d==='approved'?' on':'')+'" type="button" data-act="lap">Approve</button><button class="lc-b" type="button" data-act="open">Review →</button></div></div>'
   +(th?'<div class="lc-th">'+th+'</div>':'')+'</article>'}).join('')||'<p class="mut">Nothing matches these filters.</p>';
 $('lcount').textContent=n+' of '+STEPS.length+' steps'}
function render(){renderTop();renderSync();if(P.mode==='review'){renderRail();renderStep();renderDock()}else renderList()}

if(!/^\/r\//.test(location.pathname))$('bhub').remove();
$('brail').onclick=()=>setRail(!P.rail);$('scrim').onclick=()=>setRail(false);
$('mrev').onclick=()=>setMode('review');$('mlist').onclick=()=>setMode('list');
$('dcomfy').onclick=()=>{P.compact=false;savePrefs();render()};$('dcomp').onclick=()=>{P.compact=true;savePrefs();render()};
$('btheme').onclick=()=>{P.theme={auto:'light',light:'dark',dark:'auto'}[P.theme]||'auto';savePrefs();renderTop()};
$('bhelp').onclick=()=>$('help').hidden=!$('help').hidden;
$('rf').onclick=e=>{const b=e.target.closest('button');if(b){railF=b.dataset.f;renderRail()}};
$('rows').onclick=e=>{const b=e.target.closest('[data-go]');if(b)go(+b.dataset.go)};
$('fprev').onclick=()=>go(cur-1);$('fnext').onclick=()=>go(cur+1);
$('fauto').onchange=e=>{P.auto=e.target.checked;savePrefs()};
$('dap').onclick=()=>decide(STEPS[cur],'approved');$('drw').onclick=()=>decide(STEPS[cur],'rework');
$('tundo').onclick=undo;$('tclose').onclick=()=>$('toast').hidden=true;
$('rmain').addEventListener('click',e=>{const t=e.target.closest('[data-act]');if(!t)return;const s=STEPS[cur],a=t.dataset.act;
 if(a==='view'){ui(s).v=t.dataset.v;renderStep()}else if(a==='member'){ui(s).m=+t.dataset.m;ui(s).v=null;ui(s).p=0;renderStep()}
 else if(a==='shot'){ui(s).p=+t.dataset.p;ui(s).v=null;renderStep()}
 else if(a==='opt'){setStep(s,{option:+t.dataset.n},true);renderStep();renderDock();renderRail()}
 else if(a==='clear'){setStep(s,{decision:''},true);toast('Decision removed · '+s.label,true);render()}
 else if(a==='lay')setLay(t.dataset.l)
 else if(a==='zoom')openZoom(s,ui(s).m,t.dataset.w)});
function setLay(l){P.lay=l==='col'?'col':'row';savePrefs();renderStep()}
function applySplit(){body.style.setProperty('--split',(P.split||42)+'%');const g=document.querySelector('.rv-gut');if(g)g.setAttribute('aria-valuenow',Math.round(P.split||42))}
function setSplit(p){if(!isFinite(p))return;P.split=Math.round(Math.min(75,Math.max(20,p))*10)/10;applySplit()}
$('rmain').addEventListener('pointerdown',e=>{const g=e.target.closest('.rv-gut');if(!g||e.button!==0)return;e.preventDefault();
 const r=g.parentElement.getBoundingClientRect();g.setPointerCapture(e.pointerId);body.classList.add('resizing');
 const mv=ev=>setSplit((ev.clientX-r.left-7)/r.width*100),up=()=>{g.removeEventListener('pointermove',mv);g.removeEventListener('pointerup',up);g.removeEventListener('pointercancel',up);body.classList.remove('resizing');savePrefs()};
 g.addEventListener('pointermove',mv);g.addEventListener('pointerup',up);g.addEventListener('pointercancel',up)});
$('rmain').addEventListener('dblclick',e=>{if(e.target.closest('.rv-gut')){P.split=null;applySplit();savePrefs()}});
$('lcards').addEventListener('click',e=>{const t=e.target.closest('[data-act]');if(!t)return;const c=t.closest('.lc'),s=STEPS[+c.dataset.i],a=t.dataset.act;
 if(a==='open'){cur=s.i;setMode('review');go(s.i)}else if(a==='lap')decide(s,'approved');else if(a==='lrw')decide(s,'rework');
 else if(a==='lzoom')openZoom(s,Math.max(0,s.ids.indexOf(t.dataset.id)),t.dataset.w)});
$('lsf').onclick=e=>{const b=e.target.closest('button');if(b){lsF=b.dataset.s;renderList()}};
$('ldf').onclick=e=>{const b=e.target.closest('button');if(b){ldF=b.dataset.d;renderList()}};
$('lhide').onchange=renderList;
{const tb=document.querySelectorAll('#ltf button');tb.forEach(x=>x.onclick=()=>{tb.forEach(y=>y.setAttribute('aria-pressed',y===x));const v=x.dataset.t;document.querySelectorAll('tr[data-t]').forEach(r=>r.style.display=(v==='all'||r.dataset.t===v)?'':'none')})}
document.addEventListener('click',e=>{const a=e.target.closest('a[data-fid]');if(!a)return;const s=stepOf(a.dataset.fid);if(!s)return;e.preventDefault();setMode('review');go(s.i);ui(s).m=Math.max(0,s.ids.indexOf(a.dataset.fid));renderStep()});
$('bexp').onclick=()=>{const out={report:TITLE,exported:now(),decisions:D};const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(out,null,1)],{type:'application/json'}));a.download='review-decisions.json';a.click();toast('Exported '+Object.keys(D).length+' entries',false)};
$('limp').onclick=()=>$('ifile').click();
$('ifile').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const j=JSON.parse(await f.text());const n=merge(j.decisions||j);persist();render();toast('Imported '+n+' newer entries',false)}catch(err){toast('Import failed: '+err.message,false)}e.target.value=''};
$('lcopy').onclick=async()=>{const lines=[];STEPS.forEach(s=>{const k=skind(s),d=ent(s);if(k==='rework'||k==='commented'||(k==='approved'&&optOf(s)))lines.push(s.ids.join(', ')+' ['+(k==='rework'?'needs work':k==='commented'?'comment':'approved option '+optOf(s))+']'+((d.comment||'').trim()?': '+d.comment.trim():''))});
 const txt=lines.join('\n')||'No items need work.';try{await navigator.clipboard.writeText(txt);toast('Copied '+lines.length+' items',false)}catch(err){prompt('Copy:',txt)}};

let Z=null;
function openZoom(s,mi,w){const m=FI[s.ids[mi||0]],K=(mi||0)===ui(s).m?ik(s,m):m.id,list=[['b',LB],['a',LA]].filter(([x])=>IMG[K+':'+x]);if(!list.length)return;
 const v=ui(s).v;let idx=w?list.findIndex(x=>x[0]===w):v==='after'?list.findIndex(x=>x[0]==='a'):0;Z={m,k:K,list,idx:Math.max(0,idx),s:1,x:0,y:0,fit:1};$('zoom').hidden=false;zshow()}
function zshow(){const[w]=Z.list[Z.idx],img=$('zimg');$('zid').textContent=Z.m.id;
 $('ztabs').innerHTML=Z.list.map(([x,l],i)=>'<button type="button" data-zi="'+i+'" aria-pressed="'+(i===Z.idx)+'">'+l+' <span class="rv-kbd">'+(i+1)+'</span></button>').join('');
 img.onload=zfit;img.src=IMG[Z.k+':'+w];if(img.complete&&img.naturalWidth)zfit()}
function zfit(){const r=$('zvp').getBoundingClientRect(),img=$('zimg'),iw=img.naturalWidth||1,ih=img.naturalHeight||1;const s=Math.min(1,(r.width-32)/iw,(r.height-32)/ih);Z.fit=s;Z.s=s;Z.x=(r.width-iw*s)/2;Z.y=(r.height-ih*s)/2;zapply()}
function zapply(){$('zimg').style.transform='translate('+Z.x+'px,'+Z.y+'px) scale('+Z.s+')';$('zpct').textContent=Math.round(Z.s*100)+' %'}
function zat(f,cx,cy){const ns=Math.min(8,Math.max(.05,Z.s*f));Z.x=cx-(cx-Z.x)*ns/Z.s;Z.y=cy-(cy-Z.y)*ns/Z.s;Z.s=ns;zapply()}
function zclose(){$('zoom').hidden=true;Z=null}
$('zclose').onclick=zclose;$('zfit').onclick=()=>zfit();
$('ztabs').onclick=e=>{const b=e.target.closest('[data-zi]');if(b){Z.idx=+b.dataset.zi;zshow()}};
{const vp=$('zvp');let drag=null,moved=false;
 vp.addEventListener('wheel',e=>{if(!Z)return;e.preventDefault();const r=vp.getBoundingClientRect();zat(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top)},{passive:false});
 vp.addEventListener('pointerdown',e=>{if(!Z)return;drag={x:e.clientX,y:e.clientY,ox:Z.x,oy:Z.y};moved=false;vp.setPointerCapture(e.pointerId);vp.classList.add('drag')});
 vp.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>3)moved=true;Z.x=drag.ox+dx;Z.y=drag.oy+dy;zapply()});
 const end=()=>{drag=null;vp.classList.remove('drag')};vp.addEventListener('pointerup',end);vp.addEventListener('pointercancel',end);
 vp.addEventListener('dblclick',e=>{const r=vp.getBoundingClientRect();if(Math.abs(Z.s-Z.fit)<.01&&Z.fit<1)zat(1/Z.s,e.clientX-r.left,e.clientY-r.top);else zfit()});
 vp.addEventListener('click',e=>{if(!moved&&e.target===vp)zclose()});
 window.addEventListener('resize',()=>{if(Z)zfit()})}

document.addEventListener('keydown',e=>{const key=e.key;
 if(Z){const r=$('zvp').getBoundingClientRect();if(key==='Escape')zclose();else if(key==='0')zfit();else if(key==='+'||key==='=')zat(1.25,r.width/2,r.height/2);else if(key==='-')zat(.8,r.width/2,r.height/2);
  else if(/^[12]$/.test(key)&&Z.list[+key-1]){Z.idx=+key-1;zshow()}else if((key==='ArrowRight'||key==='ArrowLeft')&&Z.list.length>1){Z.idx=1-Z.idx;zshow()}else return;e.preventDefault();return}
 const t=e.target,inField=/^(TEXTAREA|INPUT|SELECT)$/.test(t.tagName)||t.isContentEditable;
 if(key==='Escape'){if(!$('help').hidden){$('help').hidden=true;return}if(inField){t.blur();return}if(narrow.matches&&P.rail){setRail(false);return}$('toast').hidden=true;return}
 if(t.closest&&t.closest('.rv-gut')&&(key==='ArrowLeft'||key==='ArrowRight')){setSplit((P.split||42)+(key==='ArrowLeft'?-2:2));savePrefs();e.preventDefault();return}
 if(inField)return;
 if((e.ctrlKey||e.metaKey)&&!e.shiftKey&&!e.altKey&&key.toLowerCase()==='z'){undo();e.preventDefault();return}
 if(e.ctrlKey||e.metaKey||e.altKey)return;
 if(key==='?'){$('help').hidden=!$('help').hidden;e.preventDefault();return}
 if(P.mode!=='review'){if(key.toLowerCase()==='z'){undo();e.preventDefault()}return}
 const s=STEPS[cur],k=key.length===1?key.toLowerCase():key;
 const act={a:()=>decide(s,'approved'),n:()=>decide(s,'rework'),c:focusComment,z:undo,ArrowRight:()=>go(cur+1),ArrowLeft:()=>go(cur-1),j:()=>go(cur+1),k:()=>go(cur-1),'[':()=>setRail(!P.rail),
  f:()=>s&&openZoom(s,ui(s).m),'1':()=>setView('before'),'2':()=>setView('after'),'3':()=>setView('both'),l:()=>{if(s&&ui(s).v!=='before'&&ui(s).v!=='after'){setLay(P.lay==='col'?'row':'col')}}}[k];
 if(act){act();e.preventDefault()}});
narrow.addEventListener('change',()=>{if(narrow.matches&&P.rail){P.rail=false;renderTop()}});
setInterval(()=>{if(!document.hidden)pull()},15000);setInterval(renderSync,30000);window.addEventListener('focus',pull);
render();pull();
})();
</script></body></html>'''


def js(v):
    return json.dumps(v, ensure_ascii=False).replace('</', '<\\/')


os.makedirs(os.path.dirname(OUT), exist_ok=True)
page = (PAGE.replace('__LIGHT__', LIGHT).replace('__DARK__', DARK).replace('__LANG__', esc(LANG)).replace('__LB__', esc(LBL_B)).replace('__LA__', esc(LBL_A).lower()).replace('__PTITLE__', esc(cfg.get('pageTitle', 'UI Sweep Report'))).replace('__LIST__', LIST_HTML)
        .replace('__DATA__', js(DATA)).replace('__PRELOAD__', js(preload)).replace('__IMG__', js(IMG)))
open(OUT, 'w', encoding='utf-8').write(page)
meta_steps, by_group = [], {}
for f in data_findings:
    g = f['group']
    if g and g in by_group:
        by_group[g]['ids'].append(f['id'])
        continue
    st = {'key': g or f['id'], 'ids': [f['id']], 'open': bool(((data_groups.get(g) if g else data_briefs.get(f['id'])) or {}).get('open'))}
    if g:
        by_group[g] = st
    meta_steps.append(st)
json.dump({'title': TITLE, 'subtitle': cfg.get('subtitle', ''), 'page': os.path.basename(OUT), 'findings': len(findings),
           'generated': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'steps': meta_steps},
          open(os.path.join(os.path.dirname(OUT), 'review-meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
missing = sorted(j['id'] for j in findings if j['id'] not in status)
no_desc = sorted(j['id'] for j in findings if not j['_issue'])
print('written', OUT, round(os.path.getsize(OUT) / 1e6, 1), 'MB;', len(findings), 'findings;', len(coverage), 'coverage rows; without status:', ' '.join(missing) or '-',
      '; without plain-language issue (card falls back to the finding description):', ' '.join(no_desc) or '-')
