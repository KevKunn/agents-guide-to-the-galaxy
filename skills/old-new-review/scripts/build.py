"""Usage: python build.py <spec.json> [--contact]
Crops and marks the old/new shots named in the spec, writes a ui-sweep style work dir and renders the review page.
--contact also writes contact-<n>.png sheets of every crop for checking the boxes."""
import json, os, shutil, subprocess, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, '..', '..', 'ui-sweep', 'scripts', 'gen-report.py')
SPEC = os.path.abspath(sys.argv[1])
spec = json.load(open(SPEC, encoding='utf-8'))
BASE = os.path.dirname(SPEC)
RID = spec['id']
SHOTS = os.path.normpath(os.path.join(BASE, spec.get('shotsDir', '.')))
WORK = os.path.normpath(os.path.join(BASE, spec.get('workDir', f'review-{RID}')))
OUT = os.path.join(WORK, 'report', f'{RID}-review.html')
DECISIONS = os.path.join(WORK, 'report', 'review-decisions.json')
SEVERITY = {'BLOCKER': 'high', 'MAJOR': 'high', 'MINOR': 'medium', 'COSMETIC': 'low'}


def shot(side, dest):
    if not side:
        return
    im = Image.open(os.path.join(SHOTS, side['file'])).convert('RGB')
    d = ImageDraw.Draw(im)
    for m in side.get('marks', []):
        d.rectangle(m, outline=(220, 30, 40), width=4)
    if side.get('crop'):
        im = im.crop(side['crop'])
    im.save(dest, optimize=True)


kept = open(DECISIONS, encoding='utf-8').read() if os.path.exists(DECISIONS) else None
shutil.rmtree(WORK, ignore_errors=True)
fdir = os.path.join(WORK, 'findings', RID.upper())
os.makedirs(fdir)
os.makedirs(os.path.dirname(OUT))
if kept:
    open(DECISIONS, 'w', encoding='utf-8').write(kept)
status, briefs = {}, {'findings': {}}
for r in spec['rows']:
    fid = r['id']
    shot(r.get('old'), os.path.join(fdir, fid + '.before.png'))
    shot(r.get('new'), os.path.join(fdir, fid + '.after.png'))
    pairs = []
    for n, pr in enumerate(r.get('pairs', []), 1):
        b, a = f'{fid}.p{n}.before.png', f'{fid}.p{n}.after.png'
        shot(pr.get('old'), os.path.join(fdir, b))
        shot(pr.get('new'), os.path.join(fdir, a))
        pairs.append({'caption': pr['caption'], 'before': b, 'after': a})
    finding = {'id': fid, 'tenant': spec.get('sidesTag', 'old ↔ new'), 'user': r.get('roles', ''), 'steps': '', 'page': r.get('page', ''),
               'check': r['item'], 'severity': SEVERITY.get(r['severity'], 'low'), 'title': f'{r["title"]} ({r["severity"]})',
               'description': r.get('detail', r['issue']), 'expected': r.get('expected', ''), 'suspectedCause': r.get('cause', ''),
               'measurements': r.get('measurements'), 'pairs': pairs}
    json.dump(finding, open(os.path.join(fdir, fid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    status[fid] = {'status': r.get('status', 'decision'), 'fix': r.get('decision', '')}
    briefs['findings'][fid] = {'issue': r['issue'], 'options': r['options'], 'rec': r['rec'], 'recOption': r['recOption'],
                               'effort': r.get('effort'), 'reply': r.get('reply'), 'open': bool(r.get('open'))}
status['_notes'] = spec.get('notes', [])
cfg = {'title': spec['title'], 'subtitle': spec.get('subtitle', ''), 'locale': 'en', 'eyebrow': spec.get('eyebrow', 'Old vs new review'),
       'pageTitle': spec.get('pageTitle', f'{RID} Review'), 'beforeLabel': spec.get('oldLabel', 'Old app'), 'afterLabel': spec.get('newLabel', 'New app'),
       'checks': spec.get('items', []), 'areas': {RID.upper(): spec['title']},
       'decisionsKey': f'old-new-review-{RID}-v1', 'viewports': [{'width': 1920, 'height': 1080}], 'coverage': False}
for name, data in (('sweep.config.json', cfg), ('status.json', status), ('briefs.json', briefs)):
    json.dump(data, open(os.path.join(WORK, name), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
subprocess.run([sys.executable, GEN, WORK, OUT], check=True, stdout=subprocess.DEVNULL)

if '--contact' in sys.argv:
    files = sorted(f for f in os.listdir(fdir) if f.endswith('.png'))
    sheets, rows, height = [], [], 0
    for f in files:
        im = Image.open(os.path.join(fdir, f))
        im = im.resize((1000, max(1, im.height * 1000 // im.width)))
        if rows and height + im.height + 30 > 1800:
            sheets.append(rows)
            rows, height = [], 0
        rows.append((f, im))
        height += im.height + 30
    sheets.append(rows)
    for n, rows in enumerate(sheets):
        c = Image.new('RGB', (1000, sum(im.height + 30 for _, im in rows)), 'white')
        d, y = ImageDraw.Draw(c), 0
        for f, im in rows:
            d.text((5, y + 8), f, fill='black')
            c.paste(im, (0, y + 30))
            y += im.height + 30
        c.save(os.path.join(WORK, f'contact-{n}.png'))
    print('contact sheets:', len(sheets))
print(OUT, f'{os.path.getsize(OUT) / 1e6:.1f} MB')
