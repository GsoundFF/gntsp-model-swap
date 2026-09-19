#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""brres_bones.py -- dump and compare the skeleton tables of .brres models.

This tool explains *why* a GNTSP appearance swap has to be surgical, using
numbers measured from the retail game rather than folklore.

A fighter's `0000.brres` is a BRRES container whose MDL0 resource owns a bone
dictionary.  Every 16-byte entry starts with a `u16` that is a bone identity
drawn from a numbering space shared by all characters, while the bones
themselves are laid out in a *different order* per character:

    character        bones    bone-id range
    Kurenai  (krn)      78    0..94
    Tsunade  (tnd)      94    0..109
    Hinata   (hnt)     106    0..101
    Ino      (ino)     127    0..102

The id sets overlap heavily (krn and hnt share 35 ids) but the orders differ,
so dropping one model file on top of another makes the slot's animation drive
the wrong bones -- invisible model, tangled body, or a crash on entering the
battle.  The animation `0000.mot` addresses bones through that shared id
space, which is exactly why "new model + old animation" works.

Usage
-----
    python brres_bones.py model.brres
    python brres_bones.py slot.brres source.brres
    python brres_bones.py --sequence slot.brres source.brres   # print full id lists

Reading is pure Python; no dependencies.
"""

import struct
import sys

DICT_ENTRY_SIZE = 16
DICT_HEADER = 0x18
MDL0_SECTION_COUNT = 12


def be16(d, o):
    return struct.unpack_from('>H', d, o)[0]


def be32(d, o):
    return struct.unpack_from('>I', d, o)[0]


def find_mdl0(d):
    """Return (offset, size) of the MDL0 resource, or (None, None)."""
    for off in range(0x20, max(0x20, len(d) - 8), 4):
        if d[off:off + 4] == b'MDL0':
            size = be32(d, off + 4)
            if 0 < size and off + size <= len(d) and size > 0x1000:
                return off, size
    return None, None


def read_sections(d, mdl0):
    """The MDL0 header holds up to 12 section offsets, relative to MDL0."""
    sections = []
    for i in range(MDL0_SECTION_COUNT):
        rel = be32(d, mdl0 + 0x10 + i * 4)
        if rel == 0:
            sections.append(None)
            continue
        a = mdl0 + rel
        sections.append({'index': i, 'rel': rel, 'off': a,
                         'size': be32(d, a), 'count': be32(d, a + 4)})
    return sections


def find_bone_section(sections):
    """The bone dictionary is the 16-bytes-per-entry section with most entries."""
    best = None
    for s in sections:
        if s is None or s['count'] <= 4 or s['size'] <= DICT_HEADER:
            continue
        body = s['size'] - DICT_HEADER
        if body % s['count']:
            continue
        if body // s['count'] == DICT_ENTRY_SIZE:
            if best is None or s['count'] > best['count']:
                best = s
    return best


def parse_brres(path):
    """Return a dict describing the model's skeleton, or None if not a model."""
    with open(path, 'rb') as f:
        d = f.read()
    mdl0, mdl0_size = find_mdl0(d)
    if mdl0 is None:
        return None
    sections = read_sections(d, mdl0)
    bone_sub = find_bone_section(sections)
    bones = []
    if bone_sub is not None:
        for i in range(bone_sub['count']):
            e = bone_sub['off'] + DICT_HEADER + i * DICT_ENTRY_SIZE
            if e + DICT_ENTRY_SIZE > len(d):
                break
            bones.append({
                'slot': i,                        # position inside this model
                'bone_id': be16(d, e),            # shared cross-character id
                'unk1': be16(d, e + 2),
                'left': be16(d, e + 4),           # dictionary tree links
                'right': be16(d, e + 6),
                'data_off': be32(d, e + 12),      # bone transform data
            })
    return {'path': path, 'size': len(d), 'mdl0': mdl0, 'mdl0_size': mdl0_size,
            'sections': sections, 'bone_section': bone_sub, 'bones': bones}


def describe(info, show_sequence=False):
    print('=' * 76)
    print('FILE  %s' % info['path'])
    print('  %d bytes, MDL0 at 0x%06x (%d bytes)' % (info['size'], info['mdl0'], info['mdl0_size']))
    for s in info['sections']:
        if s is None:
            continue
        marker = '  <- bone dictionary' if info['bone_section'] is s else ''
        print('  section[%02d] rel=0x%06x abs=0x%06x size=%7d count=%4d%s'
              % (s['index'], s['rel'], s['off'], s['size'], s['count'], marker))
    bones = info['bones']
    if not bones:
        print('  no bone dictionary identified')
        return
    ids = [b['bone_id'] for b in bones]
    print('  BONES: %d   (bone id range %d..%d, %d distinct ids)'
          % (len(bones), min(ids), max(ids), len(set(ids))))
    print('  bone id sequence: %s' % ' '.join(str(v) for v in ids[:28])
          + (' ...' if len(ids) > 28 else ''))
    if show_sequence:
        print('  full sequence:')
        for b in bones:
            print('    slot %3d  bone_id %3d  tree(%3d,%3d)  data_off 0x%06x'
                  % (b['slot'], b['bone_id'], b['left'], b['right'], b['data_off']))


def compare(info_a, info_b, name_a, name_b, show_sequence=False):
    a, b = info_a['bones'], info_b['bones']
    if not a or not b:
        return
    ids_a = [x['bone_id'] for x in a]
    ids_b = [x['bone_id'] for x in b]
    set_a, set_b = set(ids_a), set(ids_b)
    common = set_a & set_b

    print('=' * 76)
    print('COMPARISON   A = %s (%d bones)   B = %s (%d bones)' % (name_a, len(a), name_b, len(b)))
    print('  shared bone ids : %d' % len(common))
    print('  only in A       : %d   %s' % (len(set_a - set_b), sorted(set_a - set_b)[:24]))
    print('  only in B       : %d   %s' % (len(set_b - set_a), sorted(set_b - set_a)[:24]))

    # For a shared id, does it land in the same slot (position) in both models?
    first_a, first_b = {}, {}
    for x in a:
        first_a.setdefault(x['bone_id'], x['slot'])
    for x in b:
        first_b.setdefault(x['bone_id'], x['slot'])
    same_slot = [i for i in common if first_a[i] == first_b[i]]
    print('  shared ids sitting at the SAME slot index in both: %d / %d'
          % (len(same_slot), len(common)))

    shifted = [(i, first_a[i], first_b[i]) for i in sorted(common)
               if first_a[i] != first_b[i]][:12]
    if shifted:
        print('  examples of reordered bones (bone_id: slot in A -> slot in B):')
        for bid, sa, sb in shifted:
            print('    bone_id %3d : slot %3d -> slot %3d' % (bid, sa, sb))
    if show_sequence:
        print('  A id sequence: %s' % ' '.join(str(v) for v in ids_a))
        print('  B id sequence: %s' % ' '.join(str(v) for v in ids_b))

    print()
    if len(a) == len(b) and len(same_slot) == len(common) and set_a == set_b:
        print('  VERDICT: the two skeletons match; a plain file copy would also work.')
    else:
        print('  VERDICT: the skeletons differ in bone count and/or bone order, while')
        print('           sharing most bone ids. Copying one whole model file over the')
        print('           other makes the slot\'s animation address the wrong bones')
        print('           (invisible model / tangled body / crash on entering battle).')
        print('           Replace mesh + texture + palette only, and keep the slot\'s')
        print('           own 0000.mot and 0000.seq -- that is what swap_character.py does.')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '-h' in argv or '--help' in argv:
        print(__doc__)
        return 0
    show_sequence = '--sequence' in argv
    argv = [a for a in argv if a not in ('--sequence', '-v', '--verbose')]
    unknown = [a for a in argv if a.startswith('-')]
    if unknown:
        print('unknown option: %s' % unknown[0], file=sys.stderr)
        print(__doc__)
        return 2
    if not argv:
        print(__doc__)
        return 2
    infos = []
    for p in argv[:2]:
        info = parse_brres(p)
        if info is None:
            print('not a BRRES model (no MDL0): %s' % p, file=sys.stderr)
            return 1
        infos.append(info)
        describe(info, show_sequence)
        print()
    if len(infos) == 2:
        # keep the folder name too: <code>/0000.brres is more useful than 0000.brres
        def label(p):
            parts = p.replace('\\', '/').rstrip('/').split('/')
            return '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        compare(infos[0], infos[1], label(argv[0]), label(argv[1]), show_sequence)
    return 0


if __name__ == '__main__':
    sys.exit(main())
