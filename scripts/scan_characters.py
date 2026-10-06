#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_characters.py -- table of every character's model size and bone count.

Run this against a pristine game tree to see the whole roster at a glance:

    python scan_characters.py <game_root>\\DATA\\files\\chr

Each row is one character folder and its `0000.brres` (the main model).  The
bone count is the reason a swap must replace only mesh/texture/palette data:
no two characters share a skeleton layout, so a whole-file model copy would
make the slot's animation drive the wrong bones.

Add `--ids` to also print the bone id sets, and `--csv` for machine-readable
output.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brres_bones  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description='Scan a chr/ folder for model size and bone counts.')
    ap.add_argument('chr_dir', help='path to DATA/files/chr')
    ap.add_argument('--csv', action='store_true', help='emit CSV instead of a table')
    ap.add_argument('--ids', action='store_true', help='also print the bone id set')
    args = ap.parse_args(argv)

    codes = sorted(d for d in os.listdir(args.chr_dir)
                   if os.path.isdir(os.path.join(args.chr_dir, d)) and d != '.svn')
    if not codes:
        print('no character folders under %s' % args.chr_dir, file=sys.stderr)
        return 1

    rows = []
    for code in codes:
        model = os.path.join(args.chr_dir, code, '0000.brres')
        if not os.path.exists(model):
            rows.append((code, None, None, None, None))
            continue
        info = brres_bones.parse_brres(model)
        if info is None or not info['bones']:
            rows.append((code, info['size'] if info else None, None, None, None))
            continue
        ids = [b['bone_id'] for b in info['bones']]
        rows.append((code, info['size'], len(ids), min(ids), len(set(ids))))
        if args.ids:
            rows[-1] = rows[-1] + (' '.join(str(v) for v in ids),)

    if args.csv:
        print('code,filesize,bones,bone_id_min,distinct_bone_ids')
        for r in rows:
            print(','.join('' if v is None else str(v) for v in r[:5]))
        return 0

    print('%-6s %10s %7s %8s %8s' % ('code', 'bytes', 'bones', 'id min', 'distinct'))
    print('-' * 46)
    for r in rows:
        code, size, bones, idmin, distinct = r[:5]
        print('%-6s %10s %7s %8s %8s'
              % (code,
                 size if size is not None else '-',
                 bones if bones is not None else '?',
                 idmin if idmin is not None else '-',
                 distinct if distinct is not None else '-'))
    counts = [r[2] for r in rows if r[2]]
    if counts:
        print('-' * 46)
        print('%d characters with a readable model; bones %d..%d'
              % (len(counts), min(counts), max(counts)))
    if args.ids:
        print()
        for r in rows:
            if len(r) > 5:
                print('%s: %s' % (r[0], r[5]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
