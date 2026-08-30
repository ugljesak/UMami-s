#!/usr/bin/env python3
"""
Provera zatvorenosti hijerarhije za dati top-level .bdf.

Ne zamenjuje Quartus Analysis & Synthesis, ali hvata najcescu gresku pri
integraciji: sema koristi simbol za koji izvorni fajl nije u projektu, ili
.bsf i .bdf istog bloka nemaju iste portove.
"""
import re, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdfgen

QSF, TOP = sys.argv[1], sys.argv[2]

PRIMITIVES = {
    'VCC', 'GND', 'NOT', 'WIRE', 'DFF', 'TFF', 'JKFF', 'SRFF', 'LATCH',
    'BUFFER', 'TRI', 'INPUT', 'OUTPUT', 'BIDIR', 'CONSTANT', 'LCELL',
    'GLOBAL', 'CARRY', 'CASCADE', 'EXP', 'SOFT', 'OPNDRN',
}
PRIMITIVES |= {f'{g}{n}' for g in ('AND', 'OR', 'NAND', 'NOR', 'XOR', 'XNOR')
               for n in list(range(2, 13)) + ['']}

files = []
for line in open(QSF, errors='ignore'):
    m = re.match(r'set_global_assignment -name (BDF_FILE|VHDL_FILE|QIP_FILE|'
                 r'VERILOG_FILE) (.+)$', line.strip())
    if m:
        files.append(m.group(2).strip('"'))

# ime entiteta -> izvorni fajl
provided = {}
for f in files:
    provided.setdefault(os.path.splitext(os.path.basename(f))[0], []).append(f)
# QIP-ovi cesto povlace .vhd istog imena; dodaj i sve .vhd/.qip iz repoa
for root, dirs, fs in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ('.git', 'output_files', 'db')]
    for f in fs:
        if f.endswith(('.vhd', '.bdf')):
            provided.setdefault(os.path.splitext(f)[0], [])

def symbols_of(bdf):
    s = re.sub(r'/\*.*?\*/', '', open(bdf, errors='ignore').read(), flags=re.S)
    return {m.group(1) for m in re.finditer(
        r'\(symbol\s*\n\t\(rect [^)]*\)\s*\n\t\(text "([^"]+)"', s)}

bdf_by_name = {}
for f in files:
    if f.endswith('.bdf') and os.path.exists(f):
        bdf_by_name[os.path.splitext(os.path.basename(f))[0]] = f

seen, queue, problems = set(), [TOP], []
while queue:
    name = queue.pop()
    if name in seen:
        continue
    seen.add(name)
    path = bdf_by_name.get(name)
    if not path:
        continue
    for sym in sorted(symbols_of(path)):
        if sym in PRIMITIVES:
            continue
        if sym not in provided:
            problems.append(f'{path}: koristi "{sym}", a nema izvornog fajla')
        queue.append(sym)

# .bsf vs .bdf: isti portovi?
mismatch = []
for name, path in sorted(bdf_by_name.items()):
    bsf = os.path.splitext(path)[0] + '.bsf'
    if name not in seen or not os.path.exists(bsf):
        continue
    s = re.sub(r'/\*.*?\*/', '', open(path, errors='ignore').read(), flags=re.S)
    bdf_pins = set()
    for m in re.finditer(r'\(pin\s*\n\t\((?:input|output|bidir)\)(.*?)\n\)', s, re.S):
        ts = [t for t in re.findall(r'\(text "([^"]+)"', m.group(1))
              if t not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC', 'GND')]
        if ts:
            bdf_pins.add(ts[0])
    b = bdfgen.Bdf()
    sd = b.load_bsf(bsf)
    bsf_ports = {p[0] for p in sd.ports}
    if bdf_pins != bsf_ports:
        only_bsf = bsf_ports - bdf_pins
        only_bdf = bdf_pins - bsf_ports
        mismatch.append((name, sorted(only_bsf), sorted(only_bdf)))

print(f'top-level: {TOP}   obidjeno blokova: {len(seen)}')
if problems:
    print('\nNEDOSTAJU IZVORNI FAJLOVI:')
    for p in problems:
        print('  ' + p)
else:
    print('  svi koriseni simboli imaju izvorni fajl')

if mismatch:
    print('\nSIMBOL (.bsf) I SEMA (.bdf) NEMAJU ISTE PORTOVE:')
    for n, ob, od in mismatch:
        print(f'  {n}: samo u .bsf={ob}  samo u .bdf={od}')
else:
    print('  .bsf i .bdf se slazu po portovima')

sys.exit(1 if (problems or mismatch) else 0)
