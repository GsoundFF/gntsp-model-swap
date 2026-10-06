#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""swap_character.py -- put character S's *appearance* onto character T's slot
in `Naruto Shippuuden Gekitou Ninja Taisen! SP` (Wii, disc id 3800805), while
T keeps its own animations and moveset.

Why this works
--------------
A fighter lives in two places that must agree:

    DATA/files/chr/<code>/                     loose files
    DATA/files/fpack/chr/<code>/0000.fpk       the same files, packed

The game reads *both* paths (main.dol contains `fpack/chr/%s/` and `chr/%s`),
so a half-done swap leaves the original model visible in whichever path was
missed.  This script always patches both.

Inside a character folder the files are:

    0000.brres   main model (MDL0)   <- appearance, take from S
    0001.brres   secondary model     <- appearance, take from S
    0002.brres   extra variant       <- appearance, take from S
    0100.brres   alternate costume   <- appearance, take from S
    0000.brtex   textures            <- appearance, take from S
    0100.brtex   textures            <- appearance, take from S
    0000.brplt   palette             <- appearance, take from S
    0100.brplt   palette             <- appearance, take from S
    0000.mot     animation           <- KEEP T's (this is the whole point)
    0000.seq     moveset script      <- KEEP T's

Model and animation stay compatible across characters because `0000.mot`
addresses bones by *global bone index*, not by any per-file table -- so S's
mesh renders correctly under T's animation even though the two skeletons
differ in bone count and bone order.

Usage
-----
    # Hatata's model on Kurenai's slot, Kurenai's moves kept (the usual job)
    python swap_character.py --game-root <decrypted tree> --out <new tree> \
        --slot krn --source hnt

    # full transplant: S's model, animation, moveset and effects on T's slot
    python swap_character.py --game-root <tree> --out <new tree> \
        --slot krn --source tnd --mode full

`--game-root` must be the *pristine* tree (e.g. `mod/game_root`, produced by
`DolphinTool extract -i game.wbfs -o <dir> -g`), never a tree that was already
modded -- otherwise you stack swaps on top of each other.

Nothing here touches the disc image: the output is a runnable directory tree
that Dolphin opens directly via `DATA/sys/main.dol`.
"""

import argparse
import hashlib
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fpk_tool  # noqa: E402

# Files that define how a character LOOKS.  Everything else (motion, script,
# camera, CPU AI, effects) belongs to the slot and is deliberately untouched.
APPEARANCE_EXTS = ('.brres', '.brtex', '.brplt')

# Files inside an FPK that must never be taken from the source character.
NEVER_SWAP_EXTS = ('.mot', '.seq')


def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def human(n):
    return '{:,}'.format(n)


def find_char_dir(game_root, code):
    return os.path.join(game_root, 'DATA', 'files', 'chr', code)


def find_fpk(game_root, code):
    return os.path.join(game_root, 'DATA', 'files', 'fpack', 'chr', code, '0000.fpk')


def is_appearance(name):
    return name.lower().endswith(APPEARANCE_EXTS)


def copy_tree(src, dst):
    """Copy a decrypted game tree, skipping Subversion metadata."""
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.svn'), dirs_exist_ok=True)


def swap_loose(slot_dir, source_dir):
    """Overwrite the slot's appearance files with the source character's.

    Returns (swapped, missing_here, missing_there):
      swapped      -- names actually overwritten
      missing_here -- files the source has that the slot does not (harmless)
      missing_there-- files the slot has that the source does not (WARNING:
                      these keep the original appearance)
    """
    source_names = sorted(n for n in os.listdir(source_dir)
                          if is_appearance(n) and os.path.isfile(os.path.join(source_dir, n)))
    slot_names = sorted(n for n in os.listdir(slot_dir)
                        if is_appearance(n) and os.path.isfile(os.path.join(slot_dir, n)))

    swapped, missing_here = [], []
    for name in source_names:
        src = os.path.join(source_dir, name)
        dst = os.path.join(slot_dir, name)
        if os.path.exists(dst):
            shutil.copyfile(src, dst)
            swapped.append(name)
        else:
            missing_here.append(name)
    missing_there = [n for n in slot_names if n not in source_names]
    return swapped, missing_here, missing_there


def ensure_fpk_unpacked(game_root, slot, work_dir, verbose=True):
    """Unpack the slot's pristine FPK once and cache it under work_dir."""
    unpacked = os.path.join(work_dir, '%s_fpk_orig' % slot)
    marker = os.path.join(work_dir, '.%s_fpk_orig.ok' % slot)
    if os.path.isdir(unpacked) and os.path.exists(marker):
        return unpacked
    fpk = find_fpk(game_root, slot)
    if not os.path.exists(fpk):
        raise SystemExit('missing FPK: %s' % fpk)
    if verbose:
        print('  unpacking pristine %s' % fpk)
    if os.path.isdir(unpacked):
        shutil.rmtree(unpacked)
    os.makedirs(unpacked, exist_ok=True)
    fpk_tool.unpack_fpk(fpk, unpacked, verbose=False)
    with open(marker, 'w', encoding='utf-8') as f:
        f.write(md5_file(fpk))
    return unpacked


def rebuild_fpk_model_mode(slot, source_dir, unpacked_dir, out_fpk, verbose=True):
    """Repack the slot's archive: source's appearance files, slot's everything else."""
    files = fpk_tool.collect_dir(unpacked_dir)
    prefix = 'chr/%s/' % slot
    replaced = []
    for i, (name, _data) in enumerate(files):
        if not name.startswith(prefix):
            continue
        base = name[len(prefix):]
        if '/' in base or base.lower().endswith(NEVER_SWAP_EXTS):
            continue
        if not is_appearance(base):
            continue
        src = os.path.join(source_dir, base)
        if not os.path.exists(src):
            if verbose:
                print('  keep   %-28s (source has no %s)' % (name, base))
            continue
        with open(src, 'rb') as f:
            files[i] = (name, f.read())
        replaced.append(name)
        if verbose:
            print('  swap   %-28s <- source/%s' % (name, base))
    size = fpk_tool.pack_fpk(files, out_fpk)
    return replaced, size


def rebuild_fpk_full_mode(slot, source, unpacked_dir, out_fpk, verbose=True):
    """Repack the source's archive with every path rewritten to the slot code."""
    files = fpk_tool.collect_dir(unpacked_dir)
    needle = '/%s/' % source
    rewritten = []
    for name, data in files:
        new = name.replace(needle, '/%s/' % slot)
        rewritten.append((new, data))
        if verbose:
            print('  fpk    %-28s -> %s' % (name, new))
    size = fpk_tool.pack_fpk(rewritten, out_fpk)
    return [n for n, _ in rewritten], size


def swap_full(slot_dir, source_dir):
    """Wipe the slot folder's contents and copy the source's files wholesale."""
    removed = []
    for name in os.listdir(slot_dir):
        p = os.path.join(slot_dir, name)
        if os.path.isfile(p):
            os.remove(p)
            removed.append(name)
    copied = []
    for name in sorted(os.listdir(source_dir)):
        p = os.path.join(source_dir, name)
        if not os.path.isfile(p):
            continue
        shutil.copyfile(p, os.path.join(slot_dir, name))
        copied.append(name)
    return removed, copied


def report_table(rows, title):
    print()
    print(title)
    width = max([len(r[0]) for r in rows] + [12])
    for name, size, note in rows:
        print('  %-*s  %12s  %s' % (width, name, size, note))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Swap one character\'s appearance onto another\'s slot '
                    '(Naruto Gekitou Ninja Taisen! SP, Wii).')
    ap.add_argument('--game-root', required=True,
                    help='pristine decrypted game tree containing DATA/')
    ap.add_argument('--out', required=True,
                    help='output tree to create (Dolphin opens its DATA/sys/main.dol)')
    ap.add_argument('--slot', required=True,
                    help='target character code, keeps moves/animations (e.g. krn)')
    ap.add_argument('--source', required=True,
                    help='source character code, supplies the look (e.g. hnt)')
    ap.add_argument('--mode', choices=['model', 'full'], default='model',
                    help='model = source look + slot moves (default); '
                         'full = source look + moves + effects')
    ap.add_argument('--work-dir', default=None,
                    help='cache for unpacked pristine FPKs '
                         '(default: <out>/../.work)')
    ap.add_argument('--fresh', action='store_true',
                    help='delete --out first (otherwise it is reused/updated)')
    ap.add_argument('--dry-run', action='store_true',
                    help='report what would change, write nothing')
    args = ap.parse_args(argv)

    game_root = os.path.abspath(args.game_root)
    out = os.path.abspath(args.out)
    slot, source = args.slot, args.source

    slot_dir_src = find_char_dir(game_root, slot)
    source_dir = find_char_dir(game_root, source)
    for label, path in (('slot', slot_dir_src), ('source', source_dir)):
        if not os.path.isdir(path):
            raise SystemExit('%s character folder not found: %s' % (label, path))

    work_dir = args.work_dir or os.path.join(os.path.dirname(out), '.work')
    slot_dir = os.path.join(out, 'DATA', 'files', 'chr', slot)
    out_fpk = os.path.join(out, 'DATA', 'files', 'fpack', 'chr', slot, '0000.fpk')

    print('=' * 72)
    print('GNTSP appearance swap: %s (%s) <- %s (%s)   [%s mode]'
          % (slot, os.path.basename(slot_dir_src), source, os.path.basename(source_dir),
             args.mode))
    print('=' * 72)
    print('  game root : %s' % game_root)
    print('  output    : %s' % out)
    print('  work dir  : %s' % work_dir)

    if args.dry_run:
        src_names = sorted(n for n in os.listdir(source_dir) if is_appearance(n))
        print('\n[dry run] would copy %d appearance files from %s:'
              % (len(src_names), source_dir))
        for n in src_names:
            print('  %-16s %s' % (n, 'overwrite' if os.path.exists(
                os.path.join(slot_dir_src, n)) else 'NEW'))
        print('\n[dry run] would repack %s' % out_fpk)
        return 0

    # ---- 1. materialise the output tree -------------------------------
    if args.fresh and os.path.isdir(out):
        print('\n[1/4] removing previous output tree')
        shutil.rmtree(out)
    if os.path.isdir(out):
        print('\n[1/4] reusing existing output tree (appearance files are re-copied)')
    else:
        print('\n[1/4] copying pristine game tree -> %s' % out)
        copy_tree(game_root, out)

    # ---- 2. loose files ------------------------------------------------
    print('\n[2/4] loose files in DATA/files/chr/%s' % slot)
    if args.mode == 'model':
        swapped, missing_here, missing_there = swap_loose(slot_dir, source_dir)
        for name in swapped:
            print('  swap   %-16s <- %s' % (name, os.path.join(source, name)))
        if missing_here:
            for name in missing_here:
                print('  note   %-16s source has it, slot does not (skipped)' % name)
        if missing_there:
            for name in missing_there:
                print('  WARN   %-16s slot has it, source does not -> '
                      'stays the ORIGINAL character' % name)
    else:
        removed, copied = swap_full(slot_dir, source_dir)
        print('  removed %d slot files, copied %d source files' % (len(removed), len(copied)))
        for name in copied:
            print('  copy   %-16s <- %s/%s' % (name, source, name))

    # ---- 3. FPK --------------------------------------------------------
    print('\n[3/4] rebuilding fpack/chr/%s/0000.fpk' % slot)
    if args.mode == 'model':
        unpacked = ensure_fpk_unpacked(game_root, slot, work_dir)
        replaced, fpk_size = rebuild_fpk_model_mode(slot, source_dir, unpacked, out_fpk)
        print('  %d archive entries taken from %s, everything else kept from %s'
              % (len(replaced), source, slot))
    else:
        source_fpk = find_fpk(game_root, source)
        if not os.path.exists(source_fpk):
            raise SystemExit('missing source FPK: %s' % source_fpk)
        unpacked = os.path.join(work_dir, '%s_fpk_orig' % source)
        if not os.path.isdir(unpacked):
            print('  unpacking pristine %s' % source_fpk)
            os.makedirs(unpacked, exist_ok=True)
            fpk_tool.unpack_fpk(source_fpk, unpacked, verbose=False)
        _names, fpk_size = rebuild_fpk_full_mode(slot, source, unpacked, out_fpk)
        print('  archive rebuilt entirely from %s (paths rewritten to %s)'
              % (source, slot))

    # ---- 4. verification summary --------------------------------------
    print('\n[4/4] verification')
    rows = []
    for name in sorted(os.listdir(slot_dir)):
        p = os.path.join(slot_dir, name)
        if not os.path.isfile(p):
            continue
        here = os.path.getsize(p)
        src_p = os.path.join(source_dir, name)
        orig_p = os.path.join(slot_dir_src, name)
        if args.mode == 'full':
            note = 'from %s' % source if os.path.exists(src_p) else '-'
        elif name.endswith(NEVER_SWAP_EXTS):
            note = 'KEPT %s (must equal pristine)' % slot
        elif os.path.exists(src_p) and md5_file(p) == md5_file(src_p):
            note = 'OK  == %s/%s' % (source, name)
        elif os.path.exists(orig_p) and md5_file(p) == md5_file(orig_p):
            note = 'UNCHANGED (still %s)' % slot
        else:
            note = '??'
        rows.append((name, human(here), note))
    report_table(rows, '  DATA/files/chr/%s/' % slot)

    orig_fpk = find_fpk(game_root, slot)
    if os.path.exists(orig_fpk):
        print('\n  fpack/chr/%s/0000.fpk: %s -> %s bytes (%+d, recompression '
              'always grows a little)'
              % (slot, human(os.path.getsize(orig_fpk)), human(fpk_size),
                 fpk_size - os.path.getsize(orig_fpk)))

    problems = [r for r in rows if r[2].startswith('UNCHANGED') or r[2] == '??']
    print()
    if problems:
        print('  NOTE: %d file(s) are still the original %s:' % (len(problems), slot))
        for r in problems:
            print('    %s' % r[0])
        print('  If the source really has no counterpart, some costume/variant')
        print('  screens will still show the original character. That is a')
        print('  missing-asset situation, not a bug in the swap.')
    else:
        if args.mode == 'full':
            print('  All files in the slot folder now come from %s.' % source)
        else:
            print('  All appearance files in the slot folder now come from %s.' % source)

    print()
    print('Done.  Test with:')
    print('  Dolphin -> File -> Open -> %s' % os.path.join(out, 'DATA', 'sys', 'main.dol'))
    print('  then pick character "%s" in VS mode.' % slot)
    print('  Expect harmless "invalid read" popups; do NOT enable MMU for them.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
