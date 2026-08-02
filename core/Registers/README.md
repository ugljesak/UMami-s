# core/Registers

Registri procesora. Svaki fajl je zasebna BDF šema iz koje se izvozi simbol.

## Zajednička konvencija

- **CLK** — uzlazna ivica.
- **CL** — sinhrono brisanje, **prioritet nad LD**. Traje jedan pun takt.
  Ne aktivirati CL i LD istovremeno osim kad je cilj brisanje.
- **Veze su po imenu.** Ime žice mora znak-u-znak da odgovara imenu pina.
  Najčešća greška: port simbola je `Ii[31..0]`, a pin `I[31..0]`.
- Konstante: `ZERO[31..0]` iz GND, `ONE` iz VCC. Ne koristiti imena `0` i `1`.

| CL | LD | Na uzlaznu ivicu CLK |
|----|----|----------------------|
| 1  | X  | `A <- 0`             |
| 0  | 1  | `A <- I`             |
| 0  | 0  | drži staru vrednost  |

## Fajlovi

| Fajl | Simbol | Ulazi | Izlazi |
|------|--------|-------|--------|
| `IR` | REG32_LD_CL | LD, CL, CLK, I[31..0] | A[31..0] |
| `PC` | REG32_LD_CL + ADD32 + MUX2_32 | LD, CL, CLK, INC4, I[31..0] | A[31..0], Anext[31..0] |
| `MAR` | REG32_LD_CL_INC | LD, CL, CLK, INC, I[31..0] | A[31..0] |
| `MDR` | REG32_LD_CL | LD, CL, CLK, I[31..0] | A[31..0] |
| `mtvec` | REG32_LD_CL | LD, CL, CLK, I[31..0] | A[31..0] |
| `mepc` | REG32_LD_CL | LD, CL, CLK, I[31..0] | A[31..0] |
| `mcause` | REG32_LD_CL | LD, CL, CLK, I[31..0] | A[31..0] |
| `mstatus` | 2x DFF + SOP logika | TRAP_EN, MRET_EN, CSR_WR, CSR_IN[31..0], CL, CLK | A[31..0] |

## Napomene po registru

**PC** — `INC4=1` bira `PC+4`, `INC4=0` bira `I` (skok/grana).
`LD` registra = `LD OR INC4`. `Anext[31..0]` je kombinacioni izlaz sabirača
(`PC+4`) i koristi se za `rd` kod JAL/JALR, u istom taktu.
`CL` daje reset vektor `PC=0`, pa program mora počinjati na adresi 0.

**MAR** — `INC` služi za sekvencijalne pristupe (SDRAM burst, linijski bafer).

**MDR** — bez INC, prost registar.

**mtvec / mepc / mcause** — prosti registri. Multipleksiranje izvora podatka
(PC vs CSR_IN kod mepc, kod uzroka vs CSR_IN kod mcause) radi se **izvan**,
u zajedničkoj CSR write-data putanji.

**mstatus** — jedini registar sa bit-nivo logikom. Koriste se samo dva bita:

| Bit | Naziv | Značenje |
|-----|-------|----------|
| 3 | MIE | globalno dozvoli prekide |
| 7 | MPIE | sačuvana vrednost MIE od pre prekida |

Ostali bitovi su hardverski 0. Prioritet: `CL > TRAP_EN > MRET_EN > CSR_WR > hold`.

```
MIE_D  = nCL · nTRAP · ( MRET_EN·MPIE
                       + nMRET·CSR_WR·CSR_IN[3]
                       + nMRET·nCSR·MIE )

MPIE_D = nCL · ( TRAP_EN·MIE
               + nTRAP·MRET_EN
               + nTRAP·nMRET·CSR_WR·CSR_IN[7]
               + nTRAP·nMRET·nCSR·MPIE )
```

Izlaz: `A[31..0] = { zero[31..8], MPIE, zero[6..4], MIE, zero[2..0] }`.

## CSR read-modify-write

Pojedinačni CSR registri primaju samo `LD` + gotovu vrednost.
Logika za CSRRS/CSRRC je centralizovana u CSR bloku:

```
CSR_IN = CSRRW -> rs1
         CSRRS -> stara_vrednost OR rs1
         CSRRC -> stara_vrednost AND (NOT rs1)
```

## Stall

Registri nemaju poseban `EN` ulaz. Zaustavljanje se radi spolja:
`LD_efektivno = LD AND (NOT Stall)`. Odnosi se na PC i IR.
