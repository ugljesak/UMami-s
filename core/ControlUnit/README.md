# core/ControlUnit/CSR

Dekodiranje CSR adrese i upravljanje pristupom kontrolno-statusnim registrima.

## CSRDecoder.bdf

Pretvara 12-bitnu CSR adresu iz `IR[31:20]` u one-hot izbor registra.

### Pinovi

| Pin | Smer | Opis |
|-----|------|------|
| `CSR_ADDR[11..0]` | in | `IR[31..20]` |
| `CSR_WE` | in | 1 za bilo koju CSR instrukciju koja upisuje |
| `SEL_MSTATUS` | out | izbor za read mux |
| `SEL_MTVEC` | out | |
| `SEL_MEPC` | out | |
| `SEL_MCAUSE` | out | |
| `LD_MSTATUS` | out | `SEL_MSTATUS AND CSR_WE` |
| `LD_MTVEC` | out | |
| `LD_MEPC` | out | |
| `LD_MCAUSE` | out | |

### Adrese

| CSR | Adresa | `CSR_ADDR[11..0]` |
|-----|--------|-------------------|
| mstatus | 0x300 | `0011 0000 0000` |
| mtvec | 0x305 | `0011 0000 0101` |
| mepc | 0x341 | `0011 0100 0001` |
| mcause | 0x342 | `0011 0100 0010` |

### Struktura

Sva cetiri registra dele prefiks: bitovi `[11:7] = 00110` i `[5:3] = 000`.
Prefiks se dekodira jednom, pa se registri razlikuju samo po bitu 6 i po `[2:0]`.

```
PFX1   = nC11 & nC10 & C9 & C8 & nC7      (inst11, AND5)
PFXA   = nC5 & nC4                        (inst12)
PFXB   = PFXA & nC3                       (inst13)
PREFIX = PFXB & PFX1                      (inst14)

SEL_MSTATUS = PREFIX & nC6 & nC2 & nC1 & nC0    (inst15)
SEL_MTVEC   = PREFIX & nC6 &  C2 & nC1 &  C0    (inst16)
SEL_MEPC    = PREFIX &  C6 & nC2 & nC1 &  C0    (inst17)
SEL_MCAUSE  = PREFIX &  C6 & nC2 &  C1 & nC0    (inst18)

LD_x = SEL_x & CSR_WE                     (inst19..inst22)
```

`nCn` su izlazi NOT gejtova `inst1..inst10`.

### Sadrzaj

10x NOT, 5x AND5, 7x AND2. Bez custom komponenti, samo Quartus primitivi.

## Sta ide oko ovoga (jos nije napravljeno)

**Trap/mret upis.** Dekoder pokriva samo softverski put. U roditelju:

```
mepc.LD    = LD_MEPC   OR TRAP_EN
mcause.LD  = LD_MCAUSE OR TRAP_EN
mepc.I     = TRAP_EN ? PC : CSR_WDATA
mcause.I   = TRAP_EN ? kod_uzroka : CSR_WDATA
```

`mstatus` ne koristi `LD_MSTATUS` na taj nacin - on prima `CSR_WR` direktno,
plus `TRAP_EN` i `MRET_EN` kao zasebne pinove (vidi core/Registers/README.md).

**CSR read mux.** MUX4_32 nad izlazima cetiri registra, selekcija iz `SEL_*`.
Rezultat ide u `rd` (svaka CSR instrukcija vraca staru vrednost).

**CSR write-data (RMW).** Racuna se centralno, van pojedinacnih registara:

```
CSR_WDATA = CSRRW / CSRRWI -> operand
            CSRRS / CSRRSI -> stara_vrednost OR operand
            CSRRC / CSRRCI -> stara_vrednost AND (NOT operand)
```

`operand` = `rs1` kod CSRRW/CSRRS/CSRRC, ili nula-prosireno `IR[19:15]`
kod immediate varijanti (funct3 bit `IR14` bira).
`stara_vrednost` = izlaz read muxa.

## Poznata ogranicenja

- `CSRRS`/`CSRRC` sa `rs1 = x0` po specifikaciji ne smeju da upisu.
  Trenutno `CSR_WE` to ne uzima u obzir. Ako zatreba:
  `CSR_WE = csr_instr AND NOT(set_ili_clear AND rs1_je_x0)`.
- Nema detekcije nepostojece CSR adrese. Ako zatreba `illegal_csr`,
  dodaj `NOR(SEL_MSTATUS, SEL_MTVEC, SEL_MEPC, SEL_MCAUSE) AND csr_instr`.
- Nema provere prava pristupa (`CSR_ADDR[11:10]` = read-only opseg).
  Sva cetiri registra su read-write, pa za sada nije relevantno.
