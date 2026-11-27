#!/usr/bin/env python3
"""Read-only download shelf for the deposited documents. No external dependencies."""
import argparse
import csv
import html
import mimetypes
import shutil
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from build_archives import build_archives

ROOT = Path(__file__).resolve().parent
with (ROOT / 'manifest.csv').open(encoding='utf-8', newline='') as f:
    holdings = {r['id']: r for r in csv.DictReader(f)}

TOPICS = {
    '01-Alterations-and-proposals.zip': ('Alteration Acts and bills', 'First–Fifth instruments, proposal texts and the 36-state LG vote table.'),
    '02-Statutes-and-rules.zip': ('Statutes and rules', 'Federal and state laws, including signed Electoral Acts, in their identified editions.'),
    '03-Court-texts-and-historical-baseline.zip': ('Courts and constitutional history', 'SERAP merits, two short LG extracts, Decree 24 and the original-constitution working text.'),
    '04-Implementation-and-reports.zip': ('Implementation and reports', 'Public revenue, elections, state-law trackers, spill records and development indicators.'),
    '05-Comparative-sources.zip': ('Comparative sources', 'Constitutional texts, oversight caseloads and historical economic series.'),
}
PDF = holdings['H001']['repository_path']
# Preserve old bookmarks; always send the actual descriptive filename to the browser.
DIRECT = {'/PLAC-Constitution-through-Fifth.pdf': PDF}
for key, record in holdings.items():
    DIRECT['/files/' + key] = DIRECT['/' + record['repository_path']] = record['repository_path']
# Only the public deliverables listed here can be served. No directory listings or arbitrary extraction.
PUBLIC = set(TOPICS) | {'pdfs/README.md', 'pdfs/SHA256SUMS.txt', 'README.md', 'guide.html', 'originals.html', 'manifest.csv', 'originals.csv',
                        'March-2023-crosswalk.csv', 'constitution-page-check.csv', 'get-originals.py',
                        'verify-holdings.py'}

STYLE = '''
:root{font:16px/1.5 system-ui,sans-serif;color:#202e2a;background:#fafbf8;--green:#194c3e;--line:#cfdbd1}
*{box-sizing:border-box}body{margin:0}main,footer{max-width:74rem;margin:auto;padding:0 clamp(1rem,4vw,3rem)}
header{padding:2.3rem 0 1.15rem;border-bottom:1px solid var(--line)}h1,h2,h3,p{margin:0}h1,h2{font:600 clamp(1.9rem,4.6vw,3.45rem)/1.15 Georgia,serif;letter-spacing:-.03em;color:var(--green)}h2{font-size:1.8rem}h3{font-size:1.03rem}a{color:#185747;text-underline-offset:.15em}a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #c08820;outline-offset:2px}
.kicker,.num,.meta{font-size:.82rem;letter-spacing:.025em;color:#51615a}.kicker{font-weight:750;text-transform:uppercase;letter-spacing:.12em;margin-bottom:.6rem}.intro{margin-top:.6rem;max-width:64ch}.lead{padding:1.25rem clamp(1rem,3vw,2rem);margin:1.35rem 0;display:flex;align-items:center;justify-content:space-between;gap:1rem;background:#e7efe8;border:1px solid #c7d8ca;border-radius:.5rem}.lead h2{font-size:1.6rem}.lead p{max-width:64ch;margin:.3rem 0}.button{display:inline-block;text-decoration:none;background:var(--green);color:white;font-weight:650;border-radius:.35rem;padding:.66rem 1rem;white-space:nowrap}.button:hover{background:#0d392d}
nav{display:flex;flex-wrap:wrap;gap:.35rem 1.2rem}section{margin:1.8rem 0 2rem}.packages{margin:.85rem 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr));gap:.68rem}.pkg{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:.45rem;padding:1rem;background:white}.pkg p{font-size:.91rem;flex:1;margin:.38rem 0 .7rem;color:#485952}.pkg a,.num{font-weight:650}.controls{display:flex;flex-wrap:wrap;gap:.7rem;margin:1.1rem 0 .5rem}label{display:flex;flex-direction:column;font-size:.85rem;font-weight:650;gap:.2rem}input,select{font:inherit;font-size:.98rem;color:inherit;background:white;border:1px solid #a9b9ad;border-radius:.3rem;padding:.48rem .65rem;max-width:100%}input{width:min(80vw,28rem)}.list{margin:.6rem 0;list-style:none;padding:0}.list li{display:grid;grid-template-columns:3.2rem minmax(0,1fr) auto;gap:.7rem;align-items:baseline;border-top:1px solid var(--line);padding:.7rem 0}.list li[hidden]{display:none}.list a{white-space:nowrap;font-size:.9rem}.detail{font-size:.85rem;color:#50615b;overflow-wrap:anywhere}.actions{font-size:.9rem}.lead .meta{margin-top:.25rem}footer{font-size:.85rem;color:#53615a;border-top:1px solid var(--line);padding-top:1rem;padding-bottom:2rem}
@media(max-width:40rem){.lead{align-items:start;flex-direction:column}.list li{grid-template-columns:minmax(0,1fr) auto}.list .num{display:none}}'''


def size(n):
    return f'{n / 1048576:.1f} MiB' if n >= 1048576 else f'{max(1, round(n / 1024))} KiB'


def shelf():
    esc = html.escape
    counts = Counter(r['delivery_file'] for r in holdings.values())
    cards, options, rows = [], ['<option value="">All topics</option>', '<option value="00">Constitution PDF</option>'], []
    for name, (title, descr) in TOPICS.items():
        topic = name[:2]
        cards.append(f'<article class="pkg"><span class="kicker">Collection {topic}</span><h3>{esc(title)}</h3>'
                     f'<p>{esc(descr)}</p><div><a download href="{name}">Download ZIP</a> '
                     f'<span class="meta"> · {counts[name]} files · {size((ROOT / name).stat().st_size)}</span></div></article>')
        options.append(f'<option value="{topic}">{esc(title)}</option>')
    for k, r in holdings.items():
        file = r['repository_path']
        fmt = Path(file).suffix[1:].upper()
        topic = r['delivery_file'][:2] if r['member'] else '00'
        rows.append(f'<li data-topic="{topic}" data-search="{esc(file.lower(), quote=True)}"><span class="num">{esc(k)}</span>'
                    f'<div><strong>{esc(r["title"])}</strong><div class="detail">{esc(r["edition_or_date"])}'
                    f' · {esc(r["local_form"])}</div></div><a download="{esc(Path(file).name)}" href="{esc(file, quote=True)}" '
                    f'aria-label="Download {esc(r["title"], quote=True)}">{fmt} ↓</a></li>')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nigeria · Research document library</title><style>{STYLE}</style><main>
<header><p class="kicker">Document collection &nbsp; / &nbsp; Nigeria</p><h1>Constitutional research library</h1>
<p class="intro">{len(holdings)} source files, collected through 27 November 2026. Download a topic archive or choose an individual document below.</p></header>
<div class="lead"><div><div class="kicker">Start with the text</div><h2>The Constitution through the Fifth Alteration</h2>
<p>PLAC’s October 2023 revision, reprinted September 2024. Not a Government Printer consolidation certified through 2026.</p>
<p class="meta">280 pages · 8.2 MiB · <a href="constitution-page-check.csv">Margin checks</a></p></div><a class="button" href="{PDF}" download>Download PDF</a></div>
<nav aria-label="Collection resources"><a href="guide.html">Reader’s guide and gaps</a><a href="manifest.csv" download>File manifest (CSV)</a><a href="originals.html">External originals</a><a href="March-2023-crosswalk.csv" download>March 2023 gazettes (CSV)</a></nav>
<section><h2>Download by topic</h2><div class="packages">{''.join(cards)}</div></section>
<section><h2>Individual files</h2><p>Each link downloads a named file. The same documents are also available from the <a href="https://github.com/officialliterallyspeaking-oss/otherworks/blob/main/research/pdfs/README.md">GitHub PDF index</a>.</p>
<div class="controls"><label>Search documents<input type="search" id="q" placeholder="Title, file name, edition or format"></label>
<label>Topic<select id="topic">{''.join(options)}</select></label></div><p class="meta" id="count" aria-live="polite">{len(rows)} files</p>
<ul class="list">{''.join(rows)}</ul></section></main>
<footer>Source attribution, hash and limitations are recorded for each file. A bill is not an Act; an extract is not a certified judgment; an allocation is not a receipt.</footer>
<script>const q=document.getElementById('q'), t=document.getElementById('topic'), items=[...document.querySelectorAll('.list li')];
function filter(){{const s=q.value.trim().toLowerCase();let n=0;for(const li of items){{li.hidden=!!((t.value&&li.dataset.topic!==t.value)||!(li.textContent.toLowerCase()+' '+li.dataset.search).includes(s));if(!li.hidden)n++;}}document.getElementById('count').textContent=n?n+' file'+(n===1?'':'s'):'No matching files';}}q.addEventListener('input',filter);t.addEventListener('change',filter);</script></html>'''.encode('utf-8')


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.serve(body=False)

    def do_GET(self):
        self.serve(body=True)

    def headers_for(self, name, length, attachment):
        mime = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
        self.send_header('Content-Length', str(length))
        self.send_header('X-Content-Type-Options', 'nosniff')
        if attachment:
            # name comes from the local manifest, not a user-supplied path.
            self.send_header('Content-Disposition', f'attachment; filename="{Path(name).name}"')
        self.end_headers()

    def serve(self, body):
        path = urlsplit(self.path).path
        try:
            if path in ('/', '/index.html'):
                content = shelf()
                self.headers_for('index.html', len(content), False)
                if body:
                    self.wfile.write(content)
                return
            if path in DIRECT:
                name = DIRECT[path]
                attachment = True
            elif path[1:] in PUBLIC:
                name = path[1:]
                attachment = not name.endswith('.html')
            else:
                self.send_error(404, 'Not in the public collection')
                return
            file = ROOT / name
            with file.open('rb') as f:
                self.headers_for(name, file.stat().st_size, attachment)
                if body:
                    shutil.copyfileobj(f, self.wfile, 65536)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Browser stopped the download.
        except FileNotFoundError:
            self.send_error(404, 'Download file missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    build_archives(ROOT)
    with ThreadingHTTPServer(('0.0.0.0', args.port), Handler) as server:
        print(f'Document library ready on port {args.port}', flush=True)
        server.serve_forever()
