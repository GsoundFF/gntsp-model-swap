#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_swap.py -- prove that a finished swap really is what you think it is.

Run this on the built tree before you hand the mod to anyone.  It answers four
questions that account for almost every "the mod does nothing" report:

  1. Are the slot's loose appearance files byte-identical to the source's?
  2. Are the slot's .mot / .seq still byte-identical to the pristine originals
     (i.e. did the moveset really stay the slot character's)?
  3. Inside fpack/chr/<slot>/0000.fpk, is every appearance entry the source's,
     and is every non-appearance entry still the pristine one?
  4. Is any file in the slot folder still identical to the original character
     (which would mean that costume/variant will render as the old model)?

Usage
-----
    python verify_swap.py --out <built tree> --slot krn --source hnt \
                          [--game-root <pristine tree>]

Exit code 0 = every check passed, 1 = at least one mismatch.
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fpk_tool  # noqa: E402

APPEARANCE_EXTS = ('.brres', '.brtex', '.brplt')
KEEP_EXTS = ('.mot', '.seq')


def md5_bytes(data):
    return hashlib.md5(data).hexdigest()


def md5_file(path):
    with open(path, 'rb') as f:
        return md5_bytes(f.read())


def load_dir(path):
    """name -> bytes for every regular file directly inside `path`."""
    out = {}
    if not os.path.isdir(path):
        return out
    for name in sorted(os.listdir(path)):
        p = os.path.join(path, name)
        if os.path.isfile(p):
            with open(p, 'rb') as f:
                out[name] = f.read()
    return out


def load_fpk(path):
    """inner name -> bytes for an FPK, decompressed in memory."""
    if not os.path.exists(path):
        return {}
    with open(path, 'rb') as f:
        raw = f.read()
    entries, _hdr, _total = fpk_tool.parse_fpk(raw)
    return {e['name']: fpk_tool.read_child(raw, e) for e in entries}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Verify a GNTSP appearance swap.')
    ap.add_argument('--out', required=True, help='the built mod tree')
    ap.add_argument('--slot', required=True, help='target character code')
    ap.add_argument('--source', required=True, help='source character code')
    ap.add_argument('--game-root', default=None,
                    help='pristine tree; enables the "moveset unchanged" checks')
    ap.add_argument('--mode', choices=['model', 'full'], default='model',
                    help='model = the slot keeps its own moves/animation (default); '
                         'full = every file is expected to come from the source')
    args = ap.parse_args(argv)

    out = os.path.abspath(args.out)
    slot, source = args.slot, args.source
    game_root = os.path.abspath(args.game_root) if args.game_root else None

    slot_dir = os.path.join(out, 'DATA', 'files', 'chr', slot)
    slot_fpk = os.path.join(out, 'DATA', 'files', 'fpack', 'chr', slot, '0000.fpk')
    if not os.path.isdir(slot_dir):
        raise SystemExit('no such slot folder: %s' % slot_dir)

    if game_root:
        src_dir = os.path.join(game_root, 'DATA', 'files', 'chr', source)
        orig_dir = os.path.join(game_root, 'DATA', 'files', 'chr', slot)
        orig_fpk = os.path.join(game_root, 'DATA', 'files', 'fpack', 'chr', slot, '0000.fpk')
        src_fpk = os.path.join(game_root, 'DATA', 'files', 'fpack', 'chr', source, '0000.fpk')
    else:
        src_dir = orig_dir = None
        orig_fpk = None
        src_fpk = None

    slot_files = load_dir(slot_dir)
    src_files = load_dir(src_dir) if src_dir else {}
    orig_files = load_dir(orig_dir) if orig_dir else {}
    slot_fpk_children = load_fpk(slot_fpk)
    orig_fpk_children = load_fpk(orig_fpk) if orig_fpk else {}
    src_fpk_children = load_fpk(src_fpk) if src_fpk else {}
    mode = args.mode

    fails = []
    warns = []
    checks = 0

    def ok(label, detail=''):
        print('  PASS  %-46s %s' % (label, detail))

    def bad(label, detail=''):
        fails.append(label)
        print('  FAIL  %-46s %s' % (label, detail))

    def warn(label, detail=''):
        warns.append(label)
        print('  WARN  %-46s %s' % (label, detail))

    # ---- 1. loose appearance files -----------------------------------
    print('=' * 78)
    print('loose files: %s' % slot_dir)
    print('=' * 78)
    for name, data in sorted(slot_files.items()):
        if mode == 'model' and not name.lower().endswith(APPEARANCE_EXTS):
            continue
        checks += 1
        if name in src_files:
            if md5_bytes(data) == md5_bytes(src_files[name]):
                ok('%s == %s/%s' % (name, source, name), '%d bytes' % len(data))
            else:
                bad('%s != %s/%s' % (name, source, name),
                    'slot=%d source=%d bytes' % (len(data), len(src_files[name])))
        elif mode == 'full':
            bad('%s has no counterpart in %s' % (name, source))
        elif name in orig_files and md5_bytes(data) == md5_bytes(orig_files[name]):
            warn('%s still the original %s' % (name, slot),
                 'source has no counterpart -> that variant stays %s' % slot)
        else:
            bad('%s matches neither source nor original' % name)

    # ---- 2. moveset / animation ---------------------------------------
    if mode == 'full':
        print()
        print('=' * 78)
        print('mode=full: moves and animation are expected to come from %s too' % source)
        print('=' * 78)
        for name in sorted(slot_files):
            if name.lower().endswith(KEEP_EXTS):
                print('  INFO  %s comes from %s (compared above)' % (name, source))
    elif game_root:
        print()
        print('=' * 78)
        print('kept files (moves + animation must still be %s)' % slot)
        print('=' * 78)
        for name in sorted(slot_files):
            if not name.lower().endswith(KEEP_EXTS):
                continue
            checks += 1
            if name not in orig_files:
                warn('%s has no pristine counterpart' % name)
            elif md5_bytes(slot_files[name]) == md5_bytes(orig_files[name]):
                ok('%s unchanged vs pristine' % name, '%d bytes' % len(slot_files[name]))
            else:
                bad('%s was modified - moves/animations are NOT the slot character' % name)

    # ---- 3. FPK contents ---------------------------------------------
    print()
    print('=' * 78)
    print('archive: %s' % slot_fpk)
    print('=' * 78)
    if not slot_fpk_children:
        bad('archive missing or unreadable')
    else:
        prefix = 'chr/%s/' % slot
        for name, data in sorted(slot_fpk_children.items()):
            if mode == 'full':
                checks += 1
                counterpart = name.replace('/%s/' % slot, '/%s/' % source)
                if counterpart not in src_fpk_children:
                    warn('%s has no counterpart in the %s archive' % (name, source))
                elif md5_bytes(data) == md5_bytes(src_fpk_children[counterpart]):
                    ok('%s == %s' % (name, counterpart), '%d bytes' % len(data))
                else:
                    bad('%s != %s' % (name, counterpart))
                continue
            base = name[len(prefix):] if name.startswith(prefix) else None
            swapped_expected = (base is not None and '/' not in base
                                and base.lower().endswith(APPEARANCE_EXTS)
                                and base in src_files)
            kept_expected = (base is not None and '/' not in base
                             and base.lower().endswith(KEEP_EXTS))
            checks += 1
            if swapped_expected:
                if md5_bytes(data) == md5_bytes(src_files[base]):
                    ok('%s == %s' % (name, source), '%d bytes' % len(data))
                else:
                    bad('%s != %s/%s' % (name, source, base))
            elif kept_expected:
                if orig_fpk_children and name in orig_fpk_children:
                    if md5_bytes(data) == md5_bytes(orig_fpk_children[name]):
                        ok('%s unchanged (slot keeps moves/animation)' % name,
                           '%d bytes' % len(data))
                    else:
                        bad('%s differs from pristine' % name)
                else:
                    ok('%s present' % name, '%d bytes' % len(data))
            else:
                # cam / cpu / eft / cmn and any non-appearance entry
                if orig_fpk_children and name in orig_fpk_children:
                    if md5_bytes(data) == md5_bytes(orig_fpk_children[name]):
                        ok('%s unchanged (not appearance)' % name, '%d bytes' % len(data))
                    else:
                        bad('%s changed but should not have' % name)
                else:
                    ok('%s present (no pristine reference)' % name, '%d bytes' % len(data))

    # ---- 4. summary ---------------------------------------------------
    print()
    print('=' * 78)
    print('%d checks, %d failed, %d warnings' % (checks, len(fails), len(warns)))
    if fails:
        print('VERIFY FAILED:')
        for f in fails:
            print('  - %s' % f)
    else:
        print('VERIFY PASSED - the swap is complete for every file the source provides.')
    if warns:
        print('Warnings (usually missing source assets, not errors):')
        for w in warns:
            print('  - %s' % w)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
