#!/usr/bin/env python3
"""
Generise UMamiSystem.bdf - top-level sema celog sistema.

            CLK 50 MHz ────┬──────────────────────────────────────┐
                           │                                      │
                        GPUPLL ── c1 (fazni pomeraj) ── DRAM_CLK  │
                           │                                      │
   ControlUnit ─ gfx_req ──┤                                      │
    (RV32IM)   ─ gfx_addr ─┤   arbitar ── grant ── SDRAM_CNTR ── SDRAM cip
               ─ gfx_wdata ┤      │                    │
               ← gfx_done ─┘      │                    │ rdata
                                  │                    ▼
                        Filler ───┘              Filler → Monitor → VGA

Adresni prostor procesora
-------------------------
  0x0000_0000 .. 0x0000_3FFF   interna RAM (4096 x 32, M9K)
  0x8000_0000 .. 0x807F_FFFF   framebuffer u SDRAM-u (upis, `sh`)

Framebuffer
-----------
  320 x 256 piksela, 16 bita po pikselu (RGB444 u bitovima [11..0]),
  korak reda 512 reci:   adresa_polureci = y * 512 + x
  Prikaz je 2x uvecan, tj. slika zauzima 640 x 512 od 800 x 600 ekrana.

Arbitraza
---------
Filler ide na dma2 jer arbitar daje prednost tom ulazu. Procesorska
transakcija je jedna rec, pa Filler ceka najvise jedan SDRAM ciklus.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bdfgen

b = bdfgen.Bdf()

# ---- simboli ----
for p in ['core/ControlUnit/ControlUnit.bsf',
          'gpu/components/GPUPLL.bsf',
          'gpu/components/arbitar.bsf',
          'gpu/components/lpm_mux10.bsf',
          'gpu/sdram_controller/SDRAM_CNTR.bsf',
          'VGA/Filler.bsf',
          'VGA/Monitor.bsf',
          'TestUtils/Binary2BCD.bsf',
          'TestUtils/SevenSegmentInterfaceDEC.bsf',
          'core/Components/HELPERS/FallingEdge.bsf',
          'core/Components/HELPERS/Debouncer.bsf']:
    b.load_bsf(p)

missing = b.harvest('core/ControlUnit/ControlUnit.bdf',
                    ['AND2', 'OR2', 'NOT', 'VCC', 'GND'])
if missing:
    raise SystemExit(f'nedostaju primitivi: {missing}')

# =====================================================================
# 1. TAKT I RESET
# =====================================================================
b.label('1.  TAKT I RESET', -560, 40, 10)

b.pin('input', 'CLK', -560, 120)          # PIN_G21, 50 MHz
b.pin('input', 'RST', -560, 168)          # PIN_H2,  BUTTON[0], aktivan nisko
b.pin('input', 'sw',  -560, 216)          # PIN_J6,  SW[0], debug "peek"

b.place('GND', -320, 300, 'gnd0', {'1': '0'})
b.place('VCC', -320, 380, 'vcc0', {'1': '1'})

b.place('GPUPLL', -160, 120, 'pll', {
    'inclk0': 'CLK',
    'areset': '0',
    'c0':     'c0_unused',
    'c1':     'c1',
    'locked': 'lock',
})

# nLock = NOT lock          -> drzi sistem u resetu dok se PLL ne zakljuca
b.place('NOT', 240, 420, 'n_lock', {'IN': 'lock', 'OUT': 'nLock'})

# rst_btn = NOT RST         -> taster je aktivan nisko, pravimo aktivan visoko
b.place('NOT', 240, 500, 'n_rst', {'IN': 'RST', 'OUT': 'rst_btn'})

# sys_reset = rst_btn OR nLock
b.place('OR2', 440, 480, 'or_rst',
        {'IN1': 'rst_btn', 'IN2': 'nLock', 'OUT': 'sys_reset'})

# Procesor ocekuje IMPULS na RESET. Uzima se silazna ivica sistemskog reseta,
# pa se jezgro startuje samo od sebe cim se PLL zakljuca - bez pritiska tastera.
b.place('FallingEdge', 680, 460, 'fe_rst',
        {'IN': 'sys_reset', 'CLK': 'CLK', 'OUT': 'cpu_reset'})

b.place('Debouncer', 680, 620, 'db_sw',
        {'IN': 'sw', 'CLK': 'CLK', 'OUT': 'read_btn'})

# =====================================================================
# 2. PROCESOR
# =====================================================================
b.label('2.  PROCESOR  (RV32IM)', -560, 820, 10)

b.place('ControlUnit', -160, 880, 'cpu', {
    'CLKIn':            'CLK',
    'RESET':            'cpu_reset',
    'READ':             'read_btn',
    'gfx_done':         'gfx_done',
    'gfx_addr[21..0]':  'cpu_addr[21..0]',
    'gfx_wdata[15..0]': 'cpu_wdata[15..0]',
    'gfx_req':          'cpu_req',
    'debug[31..0]':     'debug[31..0]',
})

# =====================================================================
# 3. ARBITRAZA SDRAM MAGISTRALE
# =====================================================================
b.label('3.  ARBITRAZA  (dma2 = Filler ima prednost)', 560, 820, 10)

b.place('arbitar', 640, 880, 'arb', {
    'CLK':      'CLK',
    'dma1_req': 'cpu_req',       # procesor - upis piksela
    'dma2_req': 'fill_req',      # Filler   - citanje za sliku
    'busy':     'arb_busy',
    'dma1_grt': 'cpu_grt',
    'dma2_grt': 'fill_grt',
})

# REQ ka kontroleru = bilo ko od dvoje ko je dobio magistralu
b.place('OR2', 960, 1080, 'or_req',
        {'IN1': 'cpu_grt', 'IN2': 'fill_grt', 'OUT': 'sdram_req'})

# ready se mora razvrstati na vlasnika transakcije, inace bi Filler
# upisao u linijski bafer podatak od procesorskog upisa.
b.place('AND2', 960, 1200, 'and_done',
        {'IN1': 'sdram_ready', 'IN2': 'cpu_grt', 'OUT': 'gfx_done'})
b.place('AND2', 960, 1320, 'and_valid',
        {'IN1': 'sdram_ready', 'IN2': 'fill_grt', 'OUT': 'fill_valid'})

# multipleks adrese: sel = 1 -> Filler
b.place('lpm_mux10', 640, 1440, 'amux', {
    'data0x[21..0]':  'cpu_addr[21..0]',
    'data1x[21..0]':  'fill_addr[21..0]',
    'sel':            'fill_grt',
    'result[21..0]':  'sdram_addr[21..0]',
})

# =====================================================================
# 4. SDRAM KONTROLER
# =====================================================================
b.label('4.  SDRAM KONTROLER', 1360, 820, 10)

b.place('SDRAM_CNTR', 1440, 880, 'sdram', {
    'CLK':             'CLK',
    'CLK_DRAM':        'c1',
    'RST':             'sys_reset',
    'REQ':             'sdram_req',
    'WE':              'cpu_grt',          # samo procesor pise, Filler samo cita
    'addr[21..0]':     'sdram_addr[21..0]',
    'wdata[15..0]':    'cpu_wdata[15..0]',
    'rdata[15..0]':    'rdata[15..0]',
    'ready':           'sdram_ready',
    'busy':            'sdram_busy',
    'DRAM_CS':         'CS',
    'DRAM_RAS':        'RAS',
    'DRAM_CAS':        'CAS',
    'DRAM_WE':         'WE',
    'DRAM_ADDR[11..0]': 'ADDR[11..0]',
    'DRAM_BA[1..0]':   'ba[1..0]',
    'CKE':             'CKE',
    'DQM[1..0]':       'DQM[1..0]',
    'DRAM_CLK':        'DRAM_CLK',
    'DRAM_DQ[15..0]':  'DRAM_DQ[15..0]',
})

# =====================================================================
# 5. SLIKA
# =====================================================================
b.label('5.  SCANOUT  (Filler cita SDRAM -> Monitor prikazuje)', 560, 1760, 10)

b.place('Filler', 640, 1840, 'filler', {
    'CLK':                 'CLK',
    'pulse':               'mon_pulse',
    'vblank_pulse':        'mon_vblank',
    'Y[9..0]':             'mon_Y[9..0]',
    'sdram_data[15..0]':   'rdata[15..0]',
    'sdram_valid':         'fill_valid',
    'sdram_addr[21..0]':   'fill_addr[21..0]',
    'sdram_req':           'fill_req',
    'write_data[15..0]':   'fb_data[15..0]',
    'write_address[8..0]': 'fb_addr[8..0]',
    'valid':               'fb_valid',
})

b.place('Monitor', 1440, 1840, 'mon', {
    'CLK':               'CLK',
    'write_data[15..0]': 'fb_data[15..0]',
    'write_addr[8..0]':  'fb_addr[8..0]',
    'valid':             'fb_valid',
    'HS':                'HS',
    'VS':                'VS',
    'RED[3..0]':         'RED[3..0]',
    'GREEN[3..0]':       'GREEN[3..0]',
    'BLUE[3..0]':        'BLUE[3..0]',
    'pulse':             'mon_pulse',
    'Y[9..0]':           'mon_Y[9..0]',
    'vblank_pulse':      'mon_vblank',
})

# =====================================================================
# 6. DEBUG  (debug[7..0] -> LED i tri sedmosegmentna displeja)
# =====================================================================
b.label('6.  DEBUG', -560, 2200, 10)

b.place('Binary2BCD', -160, 2260, 'bcd', {
    'input[7..0]':        'debug[7..0]',
    'bcd_units[3..0]':    'units[3..0]',
    'bcd_tens[3..0]':     'tens[3..0]',
    'bcd_hundreds[3..0]': 'hund[3..0]',
})

for i, (grp, src) in enumerate([('unitsH', 'units[3..0]'),
                                ('tensH',  'tens[3..0]'),
                                ('hundH',  'hund[3..0]')]):
    conns = {'x[3..0]': src, 'dot': '0', 'en': '1'}
    for seg, bit in zip('abcdefg', range(7)):
        conns[seg] = f'{grp}[{bit}]'
    b.place('SevenSegmentInterfaceDEC', 240 + i * 400, 2260, f'seg_{grp}', conns)

# =====================================================================
# 7. IZLAZNI PINOVI
# =====================================================================
PINX = 2200
outs = [
    ('HS', None), ('VS', None),
    ('RED[3..0]', None), ('GREEN[3..0]', None), ('BLUE[3..0]', None),
    ('CS', None), ('RAS', None), ('CAS', None), ('WE', None),
    ('ADDR[11..0]', None), ('ba[1..0]', None), ('CKE', None),
    ('DQM[1..0]', None), ('DRAM_CLK', None),
    ('unitsH[6..0]', None), ('tensH[6..0]', None), ('hundH[6..0]', None),
    ('debug[7..0]', None),
]
for i, (nm, net) in enumerate(outs):
    b.pin('output', nm, PINX, 120 + i * 48, net=net)

b.pin('bidir', 'DRAM_DQ[15..0]', PINX, 120 + len(outs) * 48)

b.label('UMAMI-S  --  full system top level', -560, -80, 12)

path = b.write('UMamiSystem.bdf')
print(f'{path}: {len(b.parts)} elemenata')
