#!/usr/bin/env python3
"""
bdfgen.py - generator sematskih (.bdf) fajlova za Quartus II.

Zasto postoji
-------------
Top-level sema koja spaja ceo sistem ima ~20 blokova i ~60 veza. Crtanje toga
mishem je sporo, a jos gore - nemoguce je code-review-ovati u pull requestu.
Ovaj alat generise .bdf iz kratkog opisa, pa je izvor istine tekstualni fajl
koji se cita i menja.

Kako BDF povezuje signale
-------------------------
Dva mehanizma, oba se koriste ovde:

1. Geometrijski - segment (connector) ciji se kraj poklapa sa apsolutnom
   koordinatom porta simbola. Apsolutna koordinata = (rect.x1 + pt.x,
   rect.y1 + pt.y), gde je `pt` relativan u odnosu na gornji levi ugao simbola.

2. Po imenu - dva segmenta sa istim labelom su ista zica, ma gde bile na
   listu. Isto vazi i za pin: ime pina JE ime mreze. Quartus razume i
   podopsege, pa `debug[7..0]` pin hvata donjih 8 bita mreze `debug[31..0]`.

Generator koristi oba: svaki port simbola dobije kratak "pikavac" (stub)
segment sa labelom. Povezivanje je onda ciste po imenu, sto je isti stil koji
projekat vec koristi (vidi core/Registers/README.md).

Simboli
-------
Blok `(symbol ...)` iz .bsf fajla se ubacuje u .bdf doslovno; menja se samo
`(rect ...)` (pozicija) i tekst imena instance. Quartus primitivi (VCC, GND,
NOT, AND2, ...) nemaju .bsf u repou, pa se njihovi blokovi "beru" iz
postojecih .bdf fajlova.
"""

import re, os, sys

HEADER = '''/*
WARNING: Do NOT edit the input and output ports in this file in a text
editor if you plan to continue editing the block that represents it in
the Block Editor! File corruption is VERY likely to occur.
*/
/*
Copyright (C) 1991-2013 Altera Corporation
Your use of Altera Corporation's design tools, logic functions 
and other software and tools, and its AMPP partner logic 
functions, and any output files from any of the foregoing 
(including device programming or simulation files), and any 
associated documentation or information are expressly subject 
to the terms and conditions of the Altera Program License 
Subscription Agreement, Altera MegaCore Function License 
Agreement, or other applicable license agreement, including, 
without limitation, that your use is for the sole purpose of 
programming logic devices manufactured by Altera and sold by 
Altera or its authorized distributors.  Please refer to the 
applicable agreement for further details.
*/
(header "graphic" (version "1.4"))
'''


def _strip_comments(s):
    return re.sub(r'/\*.*?\*/', '', s, flags=re.S)


def _sexps(s):
    """Iteriraj top-level (kind ...) blokove."""
    i, n = 0, len(s)
    while i < n:
        if s[i] == '(':
            depth, j, instr = 0, i, False
            while j < n:
                c = s[j]
                if c == '"':
                    instr = not instr
                elif not instr:
                    if c == '(':
                        depth += 1
                    elif c == ')':
                        depth -= 1
                        if depth == 0:
                            break
                j += 1
            blk = s[i:j + 1]
            m = re.match(r'\((\w+)', blk)
            if m:
                yield m.group(1), blk
            i = j + 1
        else:
            i += 1


class SymbolDef:
    """Graficka definicija jednog simbola, spremna za instanciranje."""

    def __init__(self, name, block):
        self.name = name
        self.block = block
        r = re.search(r'\(rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)\)', block)
        x1, y1, x2, y2 = (int(v) for v in r.groups())
        self.w, self.h = x2 - x1, y2 - y1
        self.ports = []          # (ime, smer, relx, rely)
        for pm in re.finditer(r'\(port\s*(.*?)\n\t\)', block, re.S):
            b = pm.group(1)
            pt = re.search(r'\(pt (-?\d+) (-?\d+)\)', b)
            if not pt:
                continue
            d = ('in' if '(input)' in b else
                 'out' if '(output)' in b else 'bidir')
            t = re.search(r'\(text "([^"]*)"', b)
            self.ports.append((t.group(1) if t else '?', d,
                               int(pt.group(1)), int(pt.group(2))))

    def port(self, name):
        for p in self.ports:
            if p[0] == name:
                return p
        raise KeyError(
            f"simbol {self.name} nema port '{name}'; ima: "
            + ', '.join(p[0] for p in self.ports))

    def instantiate(self, x, y, inst):
        """Blok simbola pomeren na (x, y) i sa imenom instance `inst`."""
        blk = self.block
        # prvi (rect ...) je okvir simbola
        blk = re.sub(r'\(rect -?\d+ -?\d+ -?\d+ -?\d+\)',
                     f'(rect {x} {y} {x + self.w} {y + self.h})', blk, count=1)
        # drugi (text ...) je ime instance (prvi je ime simbola)
        hits = list(re.finditer(r'\(text "[^"]*"', blk))
        if len(hits) >= 2:
            h = hits[1]
            blk = blk[:h.start()] + f'(text "{inst}"' + blk[h.end():]
        return blk


class Bdf:
    def __init__(self, title=None):
        self.parts = []
        self.title = title
        self._libs = {}
        self._used_stub_rows = {}

    # ---------- ucitavanje simbola ----------

    def load_bsf(self, path):
        s = _strip_comments(open(path, errors='ignore').read())
        for kind, blk in _sexps(s):
            if kind == 'symbol':
                nm = re.search(r'\(text "([^"]*)"', blk).group(1)
                self._libs[nm] = SymbolDef(nm, blk)
                return self._libs[nm]
        raise ValueError(f'nema (symbol ...) u {path}')

    def harvest(self, path, names):
        """Pokupi blokove Quartus primitiva iz postojeceg .bdf."""
        s = _strip_comments(open(path, errors='ignore').read())
        want = set(names) - set(self._libs)
        for kind, blk in _sexps(s):
            if kind != 'symbol':
                continue
            nm = re.search(r'\(text "([^"]*)"', blk).group(1)
            if nm in want:
                self._libs[nm] = SymbolDef(nm, blk)
                want.discard(nm)
        return want  # ono sto nije nadjeno

    def sym(self, name):
        if name not in self._libs:
            raise KeyError(f'simbol "{name}" nije ucitan')
        return self._libs[name]

    # ---------- elementi seme ----------

    @staticmethod
    def _is_bus(net):
        return '[' in net and ('..' in net or ',' in net)

    def connector(self, p1, p2, label=None, bus=False):
        lbl = ''
        if label:
            lx, ly = min(p1[0], p2[0]), min(p1[1], p2[1]) - 16
            lbl = (f'\n\t(text "{label}" (rect {lx} {ly} '
                   f'{lx + 7 * len(label)} {ly + 12})(font "Arial" ))')
        b = '\n\t(bus)' if bus else ''
        self.parts.append(
            f'(connector{lbl}\n\t(pt {p1[0]} {p1[1]})\n\t(pt {p2[0]} {p2[1]}){b}\n)')

    def place(self, symname, x, y, inst, conns):
        """Instanciraj simbol i zakaci imenovane pikavce na navedene portove."""
        sd = self.sym(symname)
        self.parts.append(sd.instantiate(x, y, inst))
        for pname, net in conns.items():
            _, _, px, py = sd.port(pname)
            ax, ay = x + px, y + py
            if px == 0:                       # leva ivica -> pikavac ulevo
                other = (ax - 48, ay)
            elif px >= sd.w:                  # desna ivica -> udesno
                other = (ax + 48, ay)
            elif py == 0:                     # gornja ivica -> nagore
                other = (ax, ay - 32)
            else:                             # donja ivica -> nadole
                other = (ax, ay + 32)
            self.connector((ax, ay), other, net, self._is_bus(net))
        return sd

    def pin(self, kind, name, x, y, net=None):
        """
        Ulazni/izlazni/bidir pin. Ime pina je ujedno ime mreze; ako treba da
        se vidi kao druga mreza (npr. izrez magistrale), zadaj `net` pa se
        doda pikavac sa tim labelom.
        """
        if kind == 'input':
            w = 168
            body = (f'\t(text "INPUT" (rect 125 0 153 10)(font "Arial" (font_size 6)))\n'
                    f'\t(text "{name}" (rect 5 0 {5 + 7 * len(name)} 12)(font "Arial" ))\n'
                    f'\t(pt 168 8)\n'
                    f'\t(drawing\n'
                    f'\t\t(line (pt 84 12)(pt 109 12))\n'
                    f'\t\t(line (pt 84 4)(pt 109 4))\n'
                    f'\t\t(line (pt 113 8)(pt 168 8))\n'
                    f'\t\t(line (pt 84 12)(pt 84 4))\n'
                    f'\t\t(line (pt 109 4)(pt 113 8))\n'
                    f'\t\t(line (pt 109 12)(pt 113 8))\n'
                    f'\t)\n'
                    f'\t(text "VCC" (rect 128 7 148 17)(font "Arial" (font_size 6)))\n')
            conn = (x + 168, y + 8)
        elif kind == 'output':
            w = 176
            body = (f'\t(text "OUTPUT" (rect 1 0 39 10)(font "Arial" (font_size 6)))\n'
                    f'\t(text "{name}" (rect 90 0 {90 + 7 * len(name)} 12)(font "Arial" ))\n'
                    f'\t(pt 0 8)\n'
                    f'\t(drawing\n'
                    f'\t\t(line (pt 0 8)(pt 52 8))\n'
                    f'\t\t(line (pt 52 4)(pt 78 4))\n'
                    f'\t\t(line (pt 52 12)(pt 78 12))\n'
                    f'\t\t(line (pt 52 12)(pt 52 4))\n'
                    f'\t\t(line (pt 78 4)(pt 82 8))\n'
                    f'\t\t(line (pt 82 8)(pt 78 12))\n'
                    f'\t\t(line (pt 78 12)(pt 82 8))\n'
                    f'\t)\n')
            conn = (x, y + 8)
        else:  # bidir
            w = 182
            body = (f'\t(text "BIDIR" (rect 1 0 25 10)(font "Arial" (font_size 6)))\n'
                    f'\t(text "{name}" (rect 90 0 {90 + 7 * len(name)} 12)(font "Arial" ))\n'
                    f'\t(pt 0 8)\n'
                    f'\t(drawing\n'
                    f'\t\t(line (pt 56 4)(pt 78 4))\n'
                    f'\t\t(line (pt 0 8)(pt 52 8))\n'
                    f'\t\t(line (pt 56 12)(pt 78 12))\n'
                    f'\t\t(line (pt 78 4)(pt 82 8))\n'
                    f'\t\t(line (pt 78 12)(pt 82 8))\n'
                    f'\t\t(line (pt 56 4)(pt 52 8))\n'
                    f'\t\t(line (pt 52 8)(pt 56 12))\n'
                    f'\t)\n'
                    f'\t(text "VCC" (rect 4 7 24 17)(font "Arial" (font_size 6)))\n')
            conn = (x, y + 8)

        self.parts.append(
            f'(pin\n\t({kind})\n\t(rect {x} {y} {x + w} {y + 16})\n'
            f'{body}'
            f'\t(annotation_block (location)(rect {x - 56} {y + 16} {x} {y + 32}))\n)')

        if net and net != name:
            d = -48 if kind == 'input' else 48
            self.connector(conn, (conn[0] + d, conn[1]), net, self._is_bus(net))
        return conn

    def label(self, text, x, y, size=8):
        self.parts.append(
            f'(text "{text}" (rect {x} {y} {x + 9 * len(text)} {y + 14})'
            f'(font "Arial" (font_size {size})))')

    def box(self, x1, y1, x2, y2):
        self.parts.append(f'(rectangle (rect {x1} {y1} {x2} {y2}))')

    def write(self, path):
        with open(path, 'w') as f:
            f.write(HEADER)
            f.write('\n'.join(self.parts))
            f.write('\n')
        return path
