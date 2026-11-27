#!/usr/bin/env python3
"""Check the repository files and/or downloaded topic ZIPs against manifest.csv."""
import argparse
import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile


def check(stream, row):
    digest, n = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
        n += len(block)
    if n != int(row['bytes']) or digest.hexdigest() != row['sha256']:
        raise ValueError('hash or length mismatch: ' + (row['member'] or row['delivery_file']))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dir', type=Path, default=Path(__file__).resolve().parent,
                   help='directory with the downloaded archives, standalone Constitution and manifest.csv')
    p.add_argument('--only', action='append', help='verify only this delivery filename (repeatable)')
    a = p.parse_args()
    groups = defaultdict(list)
    with (a.dir / 'manifest.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            groups[r['delivery_file']].append(r)
    if a.only and set(a.only) - groups.keys():
        p.error('unrecognized delivery filename; see the delivery_file column of manifest.csv')
    checkout = (a.dir / 'pdfs').is_dir() and all('repository_path' in r for rows in groups.values() for r in rows)
    total = 0
    for name, rows in groups.items():
        if a.only and name not in a.only:
            continue
        if checkout:
            for r in rows:
                with (a.dir / r['repository_path']).open('rb') as f:
                    check(f, r)
        delivery = a.dir / name
        if rows[0]['member'] and (delivery.exists() or not checkout):
            with ZipFile(delivery) as z:
                names = z.namelist()
                expected = {r['member'] for r in rows} | {'CONTENTS.csv'}
                if set(names) != expected or len(names) != len(expected):
                    raise ValueError('unexpected archive directory: ' + name)
                with z.open('CONTENTS.csv') as f:
                    embedded = list(csv.DictReader(f.read().decode('utf-8').splitlines()))
                if embedded != rows:
                    raise ValueError('embedded inventory does not match manifest: ' + name)
                for r in rows:
                    with z.open(r['member']) as f:
                        check(f, r)
        elif not checkout:
            if len(rows) != 1:
                raise ValueError('invalid loose-file manifest: ' + name)
            with (a.dir / name).open('rb') as f:
                check(f, rows[0])
        print(f'OK  {name}  ({len(rows)} source file(s))')
        total += len(rows)
    print(f'Verified {total} source files. Hashes identify the deposited bytes, not their legal status.')


if __name__ == '__main__':
    try:
        main()
    except Exception as err:
        sys.exit('Verification failed: ' + str(err))
