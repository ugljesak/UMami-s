#!/usr/bin/env python3
"""
Sastavlja UMamiSystem.qsf / .qpf spajanjem dva postojeca projekta:

  UMami-s.qsf              - jezgro (fajlovi + HEX/LED/taster pinovi)
  gpu/vgaSdramVgaDma.qsf   - GPU (fajlovi + VGA/SDRAM pinovi)

Namerno se pravi NOV projekat umesto menjanja UMami-s.qsf: Quartus
prepisuje .qsf pri svakom snimanju, pa je to fajl koji najcesce pravi
konflikte pri merge-u. Postojeci projekti ostaju netaknuti i dalje rade
kao zasebni testbench-evi.

Pinovi se ne dodeljuju rucno - preuzimaju se iz oba projekta, pa su
lokacije vec proverene na plocici.
"""

import re, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

TOP = 'UMamiSystem'

# pinovi koji postoje u starim projektima, a ovaj top-level ih nema
DROP_PINS = {'RESET', 'LOAD', 'LED_fill_done'}


def norm_path(p, from_dir):
    """Putanja iz .qsf-a nekog poddirektorijuma -> putanja od korena repoa."""
    p = p.strip('"')
    if p.startswith('../'):
        return os.path.normpath(p[3:])
    if os.path.isabs(p):
        return p
    return os.path.normpath(os.path.join(from_dir, p))


_INDEX = None


def resolve_by_basename(p):
    """
    Stari .qsf-ovi pokazuju na putanje od pre reorganizacije direktorijuma
    (npr. gpu/SDRAM_CNTR.bdf umesto gpu/sdram_controller/SDRAM_CNTR.bdf).
    Trazi se fajl istog imena bilo gde u repou; ako ih ima vise, bira se
    onaj sa najkracom putanjom.
    """
    global _INDEX
    if _INDEX is None:
        _INDEX = {}
        for root, dirs, fs in os.walk('.'):
            dirs[:] = [d for d in dirs if d not in ('.git', 'output_files', 'db', 'incremental_db')]
            for f in fs:
                _INDEX.setdefault(f, []).append(
                    os.path.normpath(os.path.join(root, f)))
    hits = _INDEX.get(os.path.basename(p))
    return min(hits, key=lambda x: (len(x.split(os.sep)), x)) if hits else None


def read(path, from_dir):
    files, pins = [], []
    for line in open(path, errors='ignore'):
        line = line.strip()
        m = re.match(r'set_global_assignment -name (BDF_FILE|VHDL_FILE|QIP_FILE|'
                     r'MIF_FILE|SDC_FILE|SOURCE_FILE|VERILOG_FILE) (.+)$', line)
        if m:
            files.append((m.group(1), norm_path(m.group(2), from_dir)))
            continue
        m = re.match(r'set_location_assignment (\S+) -to (\S+)$', line)
        if m:
            pins.append((m.group(1), m.group(2)))
    return files, pins


core_files, core_pins = read('UMami-s.qsf', '.')
gpu_files,  gpu_pins  = read('gpu/vgaSdramVgaDma.qsf', 'gpu')

# ---- fajlovi ----
seen, files = set(), []
for kind, p in core_files + gpu_files:
    if p in seen:
        continue
    # stari top-level-i i njihovi testbench-evi ne ulaze u novi projekat
    if os.path.basename(p) in ('UMami-s.bdf', 'testSdramVgaDma.bdf',
                              'sdram_test.bdf', 'sdram_test1.bdf'):
        continue
    if not os.path.exists(p):
        alt = resolve_by_basename(p)
        if alt is None:
            print(f'  ! nema ga nigde, preskacem: {p}')
            continue
        print(f'  ~ putanja popravljena: {p} -> {alt}')
        p = alt
        if p in seen:
            continue
    seen.add(p)
    files.append((kind, p))

for extra in ['UMamiSystem.bdf', 'VGA/Filler.bdf', 'VGA/Monitor.bdf',
              'VGA/Controller.bdf', 'gpu/components/arbitar.bdf',
              'core/ControlUnit/ControlUnit.bdf',
              'core/Components/HELPERS/FallingEdge.bdf',
              'core/Components/HELPERS/Debouncer.bdf']:
    if extra not in seen and os.path.exists(extra):
        seen.add(extra)
        files.append(('BDF_FILE', extra))

# ---- pinovi ----
by_name, conflicts = {}, []
for loc, name in core_pins + gpu_pins:
    base = re.sub(r'\[\d+\]$', '', name)
    if base in DROP_PINS:
        continue
    if name in by_name and by_name[name] != loc:
        conflicts.append((name, by_name[name], loc))
        continue
    by_name[name] = loc

for n, a, c in conflicts:
    print(f'  ! sukob lokacije za {n}: zadrzano {a}, odbaceno {c}')

# ---- SEARCH_PATH ----
search = sorted({os.path.dirname(p) for _, p in files if os.path.dirname(p)})

out = [
    '# UMamiSystem - top-level projekat celog sistema (procesor + GPU + VGA).',
    '# Generisano sa tools/gen_umamisystem_qsf.py. Quartus ce ovaj fajl',
    '# prepisati pri prvom snimanju - to je ocekivano, ovo je samo pocetno stanje.',
    '',
    'set_global_assignment -name FAMILY "Cyclone III"',
    'set_global_assignment -name DEVICE EP3C16F484C6',
    f'set_global_assignment -name TOP_LEVEL_ENTITY {TOP}',
    'set_global_assignment -name ORIGINAL_QUARTUS_VERSION 13.1',
    'set_global_assignment -name LAST_QUARTUS_VERSION 13.1',
    'set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files',
    'set_global_assignment -name MIN_CORE_JUNCTION_TEMP 0',
    'set_global_assignment -name MAX_CORE_JUNCTION_TEMP 85',
    'set_global_assignment -name ERROR_CHECK_FREQUENCY_DIVISOR 1',
    'set_global_assignment -name STRATIX_DEVICE_IO_STANDARD "3.3-V LVTTL"',
    'set_global_assignment -name CYCLONEII_OPTIMIZATION_TECHNIQUE BALANCED',
    'set_global_assignment -name SYNTH_TIMING_DRIVEN_SYNTHESIS ON',
    '',
    '# ---------- putanje ----------',
]
out += [f'set_global_assignment -name SEARCH_PATH {s}' for s in search]
out += ['', '# ---------- izvorni fajlovi ----------']
out += [f'set_global_assignment -name {k} {p}' for k, p in files]
out += ['', '# ---------- pinovi (preuzeti iz oba postojeca projekta) ----------']


def pinkey(n):
    m = re.match(r'(.+?)\[(\d+)\]$', n)
    return (m.group(1), int(m.group(2))) if m else (n, -1)


out += [f'set_location_assignment {by_name[n]} -to {n}'
        for n in sorted(by_name, key=pinkey)]
out += ['',
        'set_instance_assignment -name PARTITION_HIERARCHY root_partition -to | -section_id Top',
        'set_global_assignment -name PARTITION_NETLIST_TYPE SOURCE -section_id Top',
        'set_global_assignment -name PARTITION_FITTER_PRESERVATION_LEVEL PLACEMENT_AND_ROUTING -section_id Top',
        '']

open(f'{TOP}.qsf', 'w').write('\n'.join(out))

open(f'{TOP}.qpf', 'w').write(
    'QUARTUS_VERSION = "13.1"\n\n'
    'PROJECT_REVISION = "%s"\n' % TOP)

print(f'{TOP}.qsf: {len(files)} fajlova, {len(by_name)} pinova, '
      f'{len(search)} search path-ova')

# provera: da li svaki pin top-level seme ima lokaciju?
import sys
sys.path.insert(0, 'tools')
import bdfgen
s = open('UMamiSystem.bdf').read()
s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
need = set()
for m in re.finditer(r'\(pin\s*\n\t\((?:input|output|bidir)\)(.*?)\n\)', s, re.S):
    ts = [t for t in re.findall(r'\(text "([^"]+)"', m.group(1))
          if t not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC', 'GND')]
    if not ts:
        continue
    nm = ts[0]
    mm = re.match(r'(.+?)\[(\d+)\.\.(\d+)\]$', nm)
    if mm:
        hi, lo = int(mm.group(2)), int(mm.group(3))
        need |= {f'{mm.group(1)}[{i}]' for i in range(lo, hi + 1)}
    else:
        need.add(nm)
missing = sorted(need - set(by_name), key=pinkey)
extra = sorted(set(by_name) - need, key=pinkey)
print('  pinovi bez lokacije :', ', '.join(missing) if missing else 'nema')
print('  lokacije bez pina   :', ', '.join(extra) if extra else 'nema')
