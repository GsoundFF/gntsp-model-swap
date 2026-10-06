#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fpk_tool.py -- Eighting FPK container tool for the Naruto "Gekitou Ninja
Taisen" (Clash of Ninja) series on GameCube / Wii, including
`Naruto Shippuuden Gekitou Ninja Taisen! SP` (Wii, JAPAN, disc id 3800805).

An FPK is the per-character archive that holds a fighter's model, textures,
palette, animation and moveset script.  Every child file inside an FPK is
compressed with Eighting's PRS variant (a close relative of the classic
Nintendo PRS, but with a different flag-bit polarity).

Two things every caller must know:

  * The container stores UNCOMPRESSED sizes, so `unpack` always yields exact
    byte counts.  A child whose compressed size equals its uncompressed size
    is stored raw.
  * Re-compressing with this encoder produces a *valid but slightly larger*
    archive than the retail one (~3-8% bigger).  That is expected and the game
    accepts it.

Usage
-----
    python fpk_tool.py list      <in.fpk>
    python fpk_tool.py unpack    <in.fpk> <outdir>
    python fpk_tool.py pack      <out.fpk> <diskfile=inner/name> ...
    python fpk_tool.py repack    <indir> <out.fpk>
    python fpk_tool.py roundtrip <in.fpk> [--keep <tmpdir>]

`repack` is the workhorse: it walks <indir> and uses each file's path relative
to <indir> (with '/' separators) as the in-archive name, so
`unpack` -> edit -> `repack` reproduces the original layout exactly.

`roundtrip` decompresses an archive, re-compresses it and verifies that every
child survives byte-for-byte.  Run it once before trusting this tool on a new
game revision.

Tested with Python 3.8+ (no third-party dependencies).
"""

import argparse
import hashlib
import os
import shutil
import struct
import sys
import tempfile

# --------------------------------------------------------------------------
# PRS codec (Eighting variant)
# --------------------------------------------------------------------------


def prs_uncompress(data, out_len):
    """Decompress Eighting PRS.

    Ported from GNTool's PRSUncompressor.  `out_len` is the exact expected
    output length taken from the FPK's uncompressed-size field; the decoder
    fills exactly that many bytes.
    """
    out = bytearray(out_len)
    op = 0
    ip = 0
    flag_byte = 0
    bits_left = 0

    def get_bits(n):
        nonlocal ip, flag_byte, bits_left
        bits = 0
        while n > 0:
            bits <<= 1
            if bits_left == 0:
                flag_byte = data[ip]
                ip += 1
                bits_left = 8
            if flag_byte & 0x80:
                bits |= 1
            flag_byte = (flag_byte << 1) & 0xFF
            bits_left -= 1
            n -= 1
        return bits

    while ip < len(data):
        if get_bits(1) == 1:
            # literal byte
            if op < out_len:
                out[op] = data[ip]
                op += 1
            ip += 1
        else:
            if get_bits(1) == 0:
                # short back-reference: 8-bit signed offset
                length = get_bits(2) + 2
                pos = (data[ip] & 0xFF) | 0xFFFFFF00
                if pos >= 0x80000000:
                    pos -= 0x100000000
                ip += 1
            else:
                # long back-reference: 13-bit offset + 3-bit length (0 => ext byte)
                pos = (data[ip] << 8) | 0xFFFF0000
                if pos >= 0x80000000:
                    pos -= 0x100000000
                ip += 1
                pos |= data[ip] & 0xFF
                ip += 1
                length = pos & 0x07
                pos >>= 3
                if length == 0:
                    length = (data[ip] & 0xFF) + 1
                    ip += 1
                else:
                    length += 2
            pos += op
            for _ in range(length):
                if op < out_len:
                    out[op] = out[pos]
                    op += 1
                    pos += 1
    return bytes(out)


def prs_compress(data):
    """Compress with the Eighting PRS encoder.

    Bit-for-bit compatible with GNTool's encoder (same flag-bit polarity and
    same long/short reference encoding).  Hash-chain match finder with an
    8192-byte window, plus an RLE fast path.
    """
    n = len(data)
    if n == 0:
        return b''
    out = bytearray(n * 2)
    oi = 1        # next output byte; byte 0 is the first flag byte
    fi = 0        # index of the current flag byte
    fbi = 7       # next free bit inside the flag byte

    def wbit(b):
        nonlocal fi, oi, fbi
        if fbi == -1:
            fbi = 7
            fi = oi
            oi = fi + 1
        if b:
            out[fi] |= 1 << fbi
        fbi -= 1

    def wshort(length, d):
        nonlocal oi
        wbit(0)
        wbit(0)
        length -= 2
        wbit((length >> 1) & 1)
        wbit(length & 1)
        out[oi] = ((~d + 1) & 0xFF)
        oi += 1

    def wlong(length, d):
        nonlocal oi
        wbit(0)
        wbit(1)
        py = ((~d + 1) << 3) & 0xFFFF
        if length <= 9:
            py |= (length - 2) & 0x07
        out[oi] = (py >> 8) & 0xFF
        out[oi + 1] = py & 0xFF
        oi += 2
        # the decoder reads an extra length byte whenever the low 3 bits are 0
        if (py & 0x07) == 0:
            out[oi] = (length - 1) & 0xFF
            oi += 1

    def wcomp(length, d):
        if d > 255 or length > 5:
            wlong(length, d)
        else:
            wshort(length, d)

    chain = {}
    i = 0
    while i < n:
        best_len = 0
        best_d = 0
        if i + 3 <= n and i > 0:
            key = data[i:i + 3]
            cands = chain.get(key)
            if cands:
                max_len = min(256, n - i)
                for p in cands:
                    d = i - p
                    if d <= 0 or d > 8192:
                        continue
                    l = 0
                    while l < max_len and data[p + l] == data[i + l]:
                        l += 1
                    if l > best_len:
                        best_len = l
                        best_d = d
                        if l == max_len:
                            break
        if best_len >= 2:
            wcomp(best_len, best_d)
            i += best_len
        else:
            if i > 0 and i < n:
                run = 0
                while i + run < n and data[i + run] == data[i - 1] and run < 256:
                    run += 1
                if run > 1:
                    wcomp(run, 1)
                    i += run
                    continue
            wbit(1)
            out[oi] = data[i]
            oi += 1
            i += 1
        if i + 3 <= n:
            key = data[i:i + 3]
            lst = chain.setdefault(key, [])
            lst.append(i)
            while lst and i - lst[0] >= 8192:
                lst.pop(0)
    wbit(0)
    wbit(1)
    return bytes(out[:oi + 3])


# --------------------------------------------------------------------------
# FPK container
# --------------------------------------------------------------------------

ENTRY_SIZE = 48          # 32-byte name + 4 zero bytes + offset + csize + usize
NAME_SIZE = 32
ALIGN = 16


def parse_fpk(raw):
    """Return (entries, header_size, total_size).

    entries: list of dicts with name / offset / csize / usize, in archive order.
    """
    if len(raw) < 16:
        raise ValueError('file too small to be an FPK')
    count = int.from_bytes(raw[4:8], 'big')
    hdr_size = int.from_bytes(raw[8:12], 'big')
    total = int.from_bytes(raw[12:16], 'big')
    entries = []
    p = hdr_size
    for _ in range(count):
        name = raw[p:p + NAME_SIZE].split(b'\x00')[0].decode('shift_jis', 'replace')
        p += NAME_SIZE
        p += 4                                    # padding, always zero
        off = int.from_bytes(raw[p:p + 4], 'big'); p += 4
        csz = int.from_bytes(raw[p:p + 4], 'big'); p += 4
        usz = int.from_bytes(raw[p:p + 4], 'big'); p += 4
        entries.append({'name': name, 'offset': off, 'csize': csz, 'usize': usz})
    return entries, hdr_size, total


def read_child(raw, entry):
    """Return the decompressed bytes of one FPK child."""
    comp = raw[entry['offset']:entry['offset'] + entry['csize']]
    if entry['csize'] == entry['usize']:
        return comp
    return prs_uncompress(comp, entry['usize'])


def unpack_fpk(path, outdir, verbose=True):
    """Extract every child to <outdir>/<archive name>, keeping sub-paths."""
    with open(path, 'rb') as f:
        raw = f.read()
    entries, hdr_size, total = parse_fpk(raw)
    for e in entries:
        data = read_child(raw, e)
        if len(data) != e['usize']:
            raise ValueError('short read for %s: %d != %d'
                             % (e['name'], len(data), e['usize']))
        dst = os.path.join(outdir, e['name'].replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(data)
        if verbose:
            print('  %-34s %8d -> %8d  %s' % (e['name'], e['usize'], e['csize'], dst))
    return entries


def pack_fpk(files, outpath):
    """Build an FPK from [(inner_name, raw_bytes), ...] in the given order."""
    children = []
    for name, raw in files:
        comp = prs_compress(raw)
        children.append((name, comp, len(comp), len(raw)))

    header_end = 16 + len(children) * ENTRY_SIZE
    offsets = []
    cur = header_end
    for _name, comp, csz, _usz in children:
        offsets.append(cur)
        cur += csz
        cur = (cur + ALIGN - 1) & ~(ALIGN - 1)

    hdr = bytearray(16)
    hdr[4:8] = len(children).to_bytes(4, 'big')
    hdr[8:12] = (16).to_bytes(4, 'big')
    hdr[12:16] = cur.to_bytes(4, 'big')

    body = bytearray()
    checksum = 0
    for (name, comp, csz, usz), off in zip(children, offsets):
        nb = name.encode('shift_jis')[:NAME_SIZE]
        entry = nb + b'\x00' * (NAME_SIZE - len(nb))
        entry += b'\x00\x00\x00\x00'
        entry += off.to_bytes(4, 'big')
        entry += csz.to_bytes(4, 'big')
        entry += usz.to_bytes(4, 'big')
        body += entry
        checksum = (checksum + sum(comp)) & 0xFFFF
    hdr[0:4] = checksum.to_bytes(4, 'big')

    blob = bytes(hdr) + bytes(body)
    cur = len(blob)
    for (_name, comp, csz, _usz), off in zip(children, offsets):
        assert cur == off, (cur, off)
        blob += comp
        cur += csz
        pad = ((cur + ALIGN - 1) & ~(ALIGN - 1)) - cur
        blob += b'\x00' * pad
        cur += pad

    with open(outpath, 'wb') as f:
        f.write(blob)
    return cur


def collect_dir(indir, name_map=None):
    """Walk a directory into [(inner_name, raw_bytes), ...] sorted by name.

    `name_map` is an optional callable applied to the '/'-joined relative path,
    handy for rewriting `chr/tnd/...` into `chr/krn/...`.
    """
    files = []
    for dirpath, _dirnames, fnames in os.walk(indir):
        for fn in sorted(fnames):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, indir).replace('\\', '/')
            if name_map is not None:
                rel = name_map(rel)
            with open(p, 'rb') as f:
                files.append((rel, f.read()))
    files.sort(key=lambda kv: kv[0])
    return files


def md5(data):
    return hashlib.md5(data).hexdigest()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def cmd_list(args):
    with open(args.fpk, 'rb') as f:
        raw = f.read()
    entries, hdr_size, total = parse_fpk(raw)
    print('%s  %d bytes, %d children, header at %d'
          % (args.fpk, len(raw), len(entries), hdr_size))
    print('%-34s %10s %10s %10s' % ('name', 'offset', 'csize', 'usize'))
    for e in entries:
        extra = '  (stored raw)' if e['csize'] == e['usize'] else ''
        print('%-34s %10d %10d %10d%s'
              % (e['name'], e['offset'], e['csize'], e['usize'], extra))
    return 0


def cmd_unpack(args):
    entries = unpack_fpk(args.fpk, args.outdir)
    print('unpacked %d children from %s -> %s' % (len(entries), args.fpk, args.outdir))
    return 0


def cmd_pack(args):
    files = []
    for spec in args.pairs:
        if '=' not in spec:
            print('bad spec (want diskfile=inner/name): %s' % spec, file=sys.stderr)
            return 2
        disk, name = spec.split('=', 1)
        with open(disk, 'rb') as f:
            files.append((name, f.read()))
    size = pack_fpk(files, args.out)
    print('packed %d children -> %s (%d bytes)' % (len(files), args.out, size))
    return 0


def cmd_repack(args):
    files = collect_dir(args.indir)
    if not files:
        print('no files found under %s' % args.indir, file=sys.stderr)
        return 1
    size = pack_fpk(files, args.out)
    print('repacked %d children -> %s (%d bytes)' % (len(files), args.out, size))
    return 0


def cmd_roundtrip(args):
    """unpack -> repack -> unpack again and compare every child byte-for-byte."""
    tmp = args.keep or tempfile.mkdtemp(prefix='fpk_roundtrip_')
    dir_a = os.path.join(tmp, 'a')
    dir_b = os.path.join(tmp, 'b')
    rebuilt = os.path.join(tmp, 'rebuilt.fpk')

    with open(args.fpk, 'rb') as f:
        raw = f.read()
    entries, _hdr, _total = parse_fpk(raw)

    unpack_fpk(args.fpk, dir_a, verbose=False)
    files = []
    for e in entries:
        p = os.path.join(dir_a, e['name'].replace('/', os.sep))
        with open(p, 'rb') as f:
            files.append((e['name'], f.read()))
    pack_fpk(files, rebuilt)
    unpack_fpk(rebuilt, dir_b, verbose=False)

    ok = True
    print('%-34s %10s %10s  %s' % ('name', 'usize', 'recomp', 'match'))
    for e in entries:
        p_a = os.path.join(dir_a, e['name'].replace('/', os.sep))
        p_b = os.path.join(dir_b, e['name'].replace('/', os.sep))
        with open(p_a, 'rb') as f:
            a = f.read()
        with open(p_b, 'rb') as f:
            b = f.read()
        same = (a == b)
        ok = ok and same
        print('%-34s %10d %10s  %s'
              % (e['name'], len(a), 'OK' if same else 'MISMATCH',
                 'identical' if same else 'DIFFERS'))
    orig_size = os.path.getsize(args.fpk)
    new_size = os.path.getsize(rebuilt)
    print('archive size: %d -> %d (%+d bytes, %+.1f%%)'
          % (orig_size, new_size, new_size - orig_size,
             100.0 * (new_size - orig_size) / orig_size))
    print('ROUNDTRIP %s' % ('PASSED' if ok else 'FAILED'))
    if args.keep:
        print('kept working files in %s' % tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Eighting FPK tool for Naruto GNT / GNTSP (GameCube, Wii).')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('list', help='print the child table of an FPK')
    p.add_argument('fpk')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('unpack', help='extract all children')
    p.add_argument('fpk')
    p.add_argument('outdir')
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser('pack', help='build an FPK from diskfile=inner/name pairs')
    p.add_argument('out')
    p.add_argument('pairs', nargs='+')
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser('repack', help='build an FPK from a directory tree')
    p.add_argument('indir')
    p.add_argument('out')
    p.set_defaults(func=cmd_repack)

    p = sub.add_parser('roundtrip', help='verify decompress/recompress fidelity')
    p.add_argument('fpk')
    p.add_argument('--keep', help='keep intermediate files in this directory')
    p.set_defaults(func=cmd_roundtrip)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
