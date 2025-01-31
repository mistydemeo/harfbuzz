#!/usr/bin/env python

from __future__ import print_function, division, absolute_import

import io, os.path, sys, re

if len (sys.argv) != 2:
	print("usage: ./gen-ucd-table ucd.nonunihan.grouped.xml", file=sys.stderr)
	sys.exit(1)


# https://github.com/harfbuzz/packtab
import packTab
import packTab.ucdxml

ucdxml = packTab.ucdxml.load_ucdxml(sys.argv[1])
ucd = packTab.ucdxml.ucdxml_get_repertoire(ucdxml)


gc = [u['gc'] for u in ucd]
ccc = [int(u['ccc']) for u in ucd]
bmg = [int(v, 16) - int(u) if v else 0 for u,v in enumerate(u['bmg'] for u in ucd)]
#gc_ccc_non0 = set((cat,klass) for cat,klass in zip(gc,ccc) if klass)
#gc_bmg_non0 = set((cat,mirr) for cat,mirr in zip(gc, bmg) if mirr)

sc = [u['sc'] for u in ucd]

dm = {i:tuple(int(v, 16) for v in u['dm'].split()) for i,u in enumerate(ucd)
      if u['dm'] != '#' and u['dt'] == 'can' and not (0xAC00 <= i < 0xAC00+11172)}
ce = {i for i,u in enumerate(ucd) if u['Comp_Ex'] == 'Y'}

assert not any(v for v in dm.values() if len(v) not in (1,2))
dm1 = sorted(set(v for v in dm.values() if len(v) == 1))
dm1_u16_array = ['0x%04Xu' % v for v in dm1 if v[0] <= 0xFFFF]
dm1_u32_array = ['0x%04Xu' % v for v in dm1 if v[0] >  0xFFFF]
dm1_order = {v:i+1 for i,v in enumerate(dm1)}
dm2 = sorted((v, i) for i,v in dm.items() if len(v) == 2)
dm2 = [("HB_CODEPOINT_ENCODE3 (0x%04Xu, 0x%04Xu, 0x%04Xu)" %
        (v+(i if i not in ce and not ccc[i] else 0,)), v)
       for v,i in dm2]
dm2_array = [s for s,v in dm2]
l = 1 + len(dm1_u16_array) + len(dm1_u32_array)
dm2_order = {v[1]:i+l for i,v in enumerate(dm2)}
dm_order = {None: 0}
dm_order.update(dm1_order)
dm_order.update(dm2_order)

gc_order = packTab.AutoMapping()
for _ in ('Cc', 'Cf', 'Cn', 'Co', 'Cs', 'Ll', 'Lm', 'Lo', 'Lt', 'Lu',
          'Mc', 'Me', 'Mn', 'Nd', 'Nl', 'No', 'Pc', 'Pd', 'Pe', 'Pf',
          'Pi', 'Po', 'Ps', 'Sc', 'Sk', 'Sm', 'So', 'Zl', 'Zp', 'Zs',):
    gc_order[_]

sc_order = packTab.AutoMapping()
sc_array = []
sc_re = re.compile(" (HB_SCRIPT_[_A-Z]*).*HB_TAG [(]'(.)','(.)','(.)','(.)'[)]")
for line in open('hb-common.h'):
    m = sc_re.search (line)
    if not m: continue
    name = m.group(1)
    tag = ''.join(m.group(i) for i in range(2, 6))
    i = sc_order[tag]
    assert i == len(sc_array)
    sc_array.append(name)

# TODO Currently if gc_order or sc_order do not capture all values, we get in
# trouble because they silently add new values.  We should be able to "freeze"
# them, or just do the mapping ourselves.

DEFAULT = 1
COMPACT = 3


print("/* == Start of generated table == */")
print("/*")
print(" * The following table is generated by running:")
print(" *")
print(" *   ./gen-ucd-table.py ucd.nonunihan.grouped.xml")
print(" *")
print(" * on file with this description:", ucdxml.description)
print(" */")
print()
print("#ifndef HB_UCD_TABLE_HH")
print("#define HB_UCD_TABLE_HH")
print()

print()
print('#include "hb.hh"')
print()

code = packTab.Code('_hb_ucd')
sc_array, _ = code.addArray('hb_script_t', 'sc_map', sc_array)
dm1_16_array, _ = code.addArray('uint16_t', 'dm1_u16_map', dm1_u16_array)
dm1_32_array, _ = code.addArray('uint32_t', 'dm1_u32_map', dm1_u32_array)
dm2_array, _ = code.addArray('uint64_t', 'dm2_map', dm2_array)
code.print_c(linkage='static inline')

for compression in (DEFAULT, COMPACT):
    print()
    if compression == DEFAULT:
        print('#ifndef HB_OPTIMIZE_SIZE')
    else:
        print('#else')
    print()

    code = packTab.Code('_hb_ucd')

    packTab.pack_table(gc, 'Cn', mapping=gc_order, compression=compression).genCode(code, 'gc')
    packTab.pack_table(ccc, 0, compression=compression).genCode(code, 'ccc')
    packTab.pack_table(bmg, 0, compression=compression).genCode(code, 'bmg')
    packTab.pack_table(sc, 'Zzzz', mapping=sc_order, compression=compression).genCode(code, 'sc')
    packTab.pack_table(dm, None, mapping=dm_order, compression=compression).genCode(code, 'dm')

    code.print_c(linkage='static inline')


    if compression != DEFAULT:
        print()
        print('#endif')
    print()

print()
print("#endif /* HB_UCD_TABLE_HH */")
print()
print("/* == End of generated table == */")
