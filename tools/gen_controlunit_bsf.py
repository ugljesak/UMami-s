#!/usr/bin/env python3
"""
Generise core/ControlUnit/ControlUnit.bsf tako da odgovara portovima
ControlUnit.bdf posle MMIO zakrpe.

.bsf je auto-generisan fajl, ali MORA da bude u repou: kad se portovi promene,
a simbol ostane star, Quartus puca porukama koje ne pokazuju na pravi uzrok.
"""
W = 240                      # sirina simbola
INPUTS = [
    ('CLKIn',    False),
    ('RESET',    False),
    ('READ',     False),
    ('gfx_done', False),
]
OUTPUTS = [
    ('PC[31..0]',        True),
    ('IR[31..0]',        True),
    ('di[31..0]',        True),
    ('stall',            False),
    ('TRAP_REQ',         False),
    ('memDebug[31..0]',  True),
    ('debug[31..0]',     True),
    ('gfx_addr[21..0]',  True),
    ('gfx_wdata[15..0]', True),
    ('gfx_req',          False),
]

HEADER = open('core/ControlUnit/ControlUnit.bsf').read().split('(header')[0]


def port(name, y, out, bus):
    w = 6 * len(name)
    lw = '(line_width 3)' if bus else ''
    if out:
        px, ix = W, W - 16
        lbl = f'(rect {ix - w} {y - 5} {ix - 3} {y + 9})'
    else:
        px, ix = 0, 16
        lbl = f'(rect {ix + 5} {y - 5} {ix + 5 + w} {y + 9})'
    return (f'\t(port\n'
            f'\t\t(pt {px} {y})\n'
            f'\t\t({"output" if out else "input"})\n'
            f'\t\t(text "{name}" (rect 0 0 {w} 14)(font "Arial" (font_size 8)))\n'
            f'\t\t(text "{name}" {lbl}(font "Arial" (font_size 8)))\n'
            f'\t\t(line (pt {px} {y})(pt {ix} {y}){lw})\n'
            f'\t)\n')


n = max(len(INPUTS), len(OUTPUTS))
H = 32 + 16 * n + 16                       # 32 gore, 16 po portu, 16 dole
body = [f'(header "symbol" (version "1.2"))\n'
        f'(symbol\n'
        f'\t(rect 16 16 {16 + W} {16 + H})\n'
        f'\t(text "ControlUnit" (rect 5 0 66 14)(font "Arial" (font_size 8)))\n'
        f'\t(text "inst" (rect 8 {H - 16} 25 {H - 4})(font "Arial" ))\n']

for i, (nm, bus) in enumerate(INPUTS):
    body.append(port(nm, 32 + 16 * i, False, bus))
for i, (nm, bus) in enumerate(OUTPUTS):
    body.append(port(nm, 32 + 16 * i, True, bus))

body.append(f'\t(drawing\n\t\t(rectangle (rect 16 16 {W - 16} {H - 16}))\n\t)\n)\n')

open('core/ControlUnit/ControlUnit.bsf', 'w').write(HEADER + ''.join(body))
print(f'ControlUnit.bsf: {len(INPUTS)} ulaza, {len(OUTPUTS)} izlaza, {W}x{H}')
