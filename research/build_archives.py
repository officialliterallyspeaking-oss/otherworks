#!/usr/bin/env python3
"""Assemble the five topic ZIPs from the checked-in documents; no network or packages needed."""
import argparse
import csv
import hashlib
import io
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parent


def zip_entry(name, date):
    entry = ZipInfo(name, tuple(map(int, date.split('-'))) + (0, 0, 0))
    entry.create_system = 3
    entry.external_attr = 0o100644 << 16
    entry.compress_type = ZIP_DEFLATED
    return entry


def build_archives(out, force=False):
    with (ROOT / 'manifest.csv').open(encoding='utf-8', newline='') as f:
        groups = defaultdict(list)
        for row in csv.DictReader(f):
            if row['member']:
                groups[row['delivery_file']].append(row)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in groups.items():
        table = io.StringIO(newline='')
        writer = csv.DictWriter(table, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        inventory = table.getvalue().encode('utf-8')
        dest = out / name
        if dest.exists() and not force:
            # Replace a package from an earlier inventory rather than serving stale filenames.
            try:
                with ZipFile(dest) as z:
                    if z.read('CONTENTS.csv') == inventory and z.namelist() == ['CONTENTS.csv'] + [r['member'] for r in rows]:
                        continue
            except (KeyError, BadZipFile):
                pass
        fd, temporary = tempfile.mkstemp(dir=out, suffix='.zip.part')
        try:
            with os.fdopen(fd, 'wb') as temp, ZipFile(temp, 'w') as z:
                z.writestr(zip_entry('CONTENTS.csv', rows[0]['accessed_utc']), inventory)
                for r in rows:
                    digest = hashlib.sha256()
                    count = 0
                    with (ROOT / r['repository_path']).open('rb') as src, z.open(zip_entry(r['member'], r['accessed_utc']), 'w') as dst:
                        for chunk in iter(lambda: src.read(1024 * 1024), b''):
                            digest.update(chunk)
                            count += len(chunk)
                            dst.write(chunk)
                    if count != int(r['bytes']) or digest.hexdigest() != r['sha256']:
                        raise ValueError('Source does not match manifest: ' + r['repository_path'])
            os.replace(temporary, dest)
            print(f'Built {name} ({len(rows)} files)', flush=True)
        finally:
            Path(temporary).unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT, help='output directory (default: research/)')
    parser.add_argument('--force', action='store_true', help='rebuild even when the inventory matches')
    args = parser.parse_args()
    build_archives(args.out, args.force)
