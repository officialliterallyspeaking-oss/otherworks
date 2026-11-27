#!/usr/bin/env python3
"""Retrieve selected PDF targets from originals.csv. Python 3; no account or packages needed."""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
BLOCK = 1024 * 1024


def pdf_filename(row):
    # Friendly titles plus stable IDs disambiguate editions and sharing months.
    title = unicodedata.normalize('NFKD', row['title']).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^A-Za-z0-9]+', '-', title).strip('-')[:110].rstrip('-') or 'Document'
    return f"{slug}--{row['id']}.pdf"


def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(BLOCK), b''):
            digest.update(block)
    return digest.hexdigest()


def retrieve(row, dest, limit):
    """Never publish an incomplete response (or an HTML error page) as a PDF."""
    req = Request(row['url'], headers={
        'User-Agent': 'ConstitutionalResearchReader/1.0',
        'Accept': 'application/pdf, application/octet-stream;q=0.9, */*;q=0.5',
    })
    tmp = None
    try:
        with urlopen(req, timeout=45) as reply:
            resolved = urlsplit(reply.geturl())
            if reply.status != 200 or resolved.scheme != 'https':
                raise ValueError('expected a complete HTTPS 200 response')
            size = reply.headers.get('Content-Length')
            expected = int(size) if size is not None else None
            if expected is not None and expected > limit:
                raise ValueError('document exceeds --max-mib')
            digest = hashlib.sha256()
            total, tail = 0, b''
            with tempfile.NamedTemporaryFile(dir=dest.parent, suffix='.part', delete=False) as out:
                tmp = Path(out.name)
                while True:
                    block = reply.read(BLOCK)
                    if not block:
                        break
                    if total == 0 and not block.lstrip()[:5] == b'%PDF-':
                        raise ValueError('not a PDF (possibly an HTML landing/login/error page)')
                    total += len(block)
                    if total > limit:
                        raise ValueError('document exceeds --max-mib')
                    out.write(block)
                    digest.update(block)
                    tail = (tail + block)[-8192:]
        if not total or b'%%EOF' not in tail or (expected is not None and total != expected):
            raise ValueError('empty or incomplete PDF')
        if dest.exists():
            raise FileExistsError('destination already exists; not replacing it')
        # Exclusive creation without a partial final file; temp is on the same filesystem.
        os.link(tmp, dest)
        return {'status': 'saved', 'bytes': total, 'sha256': digest.hexdigest(),
                'resolved_host_and_path': urlunsplit((resolved.scheme, resolved.netloc, resolved.path, '', ''))}
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--id', action='append', default=[], help='source ID; repeatable')
    parser.add_argument('--group', action='append', default=[], help='source group; repeatable')
    parser.add_argument('--list', action='store_true', help='list matching records without accessing the network')
    parser.add_argument('--out', type=Path, default=Path('downloaded-originals'))
    parser.add_argument('--max-mib', type=int, default=200, help='per-file maximum; default 200 MiB')
    args = parser.parse_args()
    if args.max_mib <= 0:
        parser.error('--max-mib must be positive')
    with (HERE / 'originals.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    groups, ids = {r['group'] for r in rows}, {r['id'] for r in rows}
    unknown = (set(args.group) - groups) | (set(args.id) - ids)
    if unknown:
        parser.error('unknown group or ID: ' + ', '.join(sorted(unknown)))
    selected = [r for r in rows if (not args.group and not args.id)
                or r['group'] in args.group or r['id'] in args.id]
    if args.list or not (args.group or args.id):
        for r in selected:
            print(f"{r['group']:14} {r['id']:27} {r['format']:5} {r['title']}")
        return 0
    requests = [r for r in selected if r['format'] == 'pdf']
    for r in selected:
        if r['format'] != 'pdf':
            print(f"BROWSER {r['id']}: {r['url']}")
    if not requests:
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    log = args.out / 'receipts.jsonl'
    previous = {}
    if log.exists():
        with log.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get('status') == 'saved':
                        previous[entry['id'], entry['url']] = entry['sha256']
    errors = 0
    for row in requests:
        key = row['id']
        if not re.fullmatch(r'[a-z0-9-]+', key) or urlsplit(row['url']).scheme != 'https':
            raise ValueError('invalid source record: ' + key)
        path = args.out / pdf_filename(row)
        legacy = args.out / (key + '.pdf')
        if not path.exists() and legacy.is_file() and (key, row['url']) in previous:
            path = legacy  # Honour verified downloads from the older ID-only naming scheme.
        receipt = {'id': key, 'url': row['url'], 'file': path.name,
                   'utc': datetime.now(timezone.utc).isoformat()}
        try:
            if path.exists():
                actual = hash_file(path)
                if previous.get((key, row['url'])) != actual:
                    raise ValueError('existing file has no matching successful receipt; use a new --out directory')
                receipt.update(status='already-saved', sha256=actual, bytes=path.stat().st_size)
            else:
                receipt.update(retrieve(row, path, args.max_mib * BLOCK))
            print(receipt['status'].upper(), path, receipt['sha256'])
        except Exception as err:
            errors += 1
            receipt.update(status='failed', error=str(err))
            print(f'FAILED {key}: {err}', file=sys.stderr)
        with log.open('a', encoding='utf-8') as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + '\n')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
