# core/Components

Gradivni blokovi. Svaki fajl je zasebna BDF sema iz koje se izvozi simbol.

Veze unutar sema se prave **po imenu** (isto kao u `core/Registers`).
Ime zice mora znak-u-znak da odgovara imenu pina.

## Rezervisana imena

Quartus ima ugradjene primitive `and2..and12`, `or2..or12`, `xor`, `not`,
`nand*`, `nor*`. Komponenta u projektu sa istim imenom **zasenjuje** primitiv,
pa svaka sema koja koristi gejt tog imena puca sa "port IN1 does not exist".

Zbog toga se bitske komponente sirine 8 zovu `AND8B` i `OR8B` (sufiks `B` =
bitwise), a ne `AND8` / `OR8`. Ista pravila vaze za svaku novu komponentu:
ne davati joj ime koje vec nosi neki Quartus primitiv.

## ALU

```
ulazi   a[31..0]  b[31..0]  ci  s[3..0]  e
izlazi  o[31..0]  co  EQ  LT  LTU
```

`e = 0` gasi izlaz (`o = 0`). Zastavice `EQ/LT/LTU` **ne zavise od `s`** —
uvek su validne, jer ih racuna zaseban komparator.

### Kodiranje operacije

`s[3..0]` je namerno poravnato sa RISC-V poljem `funct3`:

```
s[2..0] = funct3
s[3]    = alt bit (funct7[5])
```

Zbog toga je buduci `ALUControl` za R i I tip skoro trivijalan —
`s = funct7[5] & funct3`.

| `s[3..0]` | operacija | `o[31..0]` |
|-----------|-----------|------------|
| `0000` | ADD  | `a + b + ci` |
| `1000` | SUB  | `a - b - ci` |
| `0001` | SLL  | `a << b[4..0]` |
| `1001` | SLL  | isto (bit 3 nebitan) |
| `0010` | SLT  | `31'b0, LT` |
| `1010` | SLT  | isto |
| `0011` | SLTU | `31'b0, LTU` |
| `1011` | SLTU | isto |
| `0100` | XOR  | `a ^ b` |
| `1100` | XOR  | isto |
| `0101` | SRL  | `a >> b[4..0]`, dopuna nulama |
| `1101` | SRA  | `a >> b[4..0]`, dopuna znakom |
| `0110` | OR   | `a \| b` |
| `1110` | OR   | isto |
| `0111` | AND  | `a & b` |
| `1111` | AND  | isto |

Kolicina pomeranja je `b[4..0]` — nema poseban pin, po specifikaciji su to
donjih 5 bita drugog operanda (`rs2` kod SLL/SRL/SRA, `shamt` kod SLLI/SRLI/SRAI).

`co` prati aktivni sabirac/oduzimac:

| `s[3]` | `co` |
|--------|------|
| 0 | prenos iz `ADD32` |
| 1 | pozajmica iz `SUB32`, tj. `a < b` bez znaka |

### Struktura

`ADD32`, `SUB32`, `XOR32`, `OR32`, `AND32`, `SHIFT32` i `CMP32` rade paralelno,
`MUX16_32` bira rezultat. `ZEXT1_32` prosiruje `LT` i `LTU` na 32 bita.

## CMP32

```
ulazi   a[31..0]  b[31..0]
izlazi  EQ  LT  LTU
```

Jedan `SUB32` sa `ci = 0` daje razliku `D = a - b` i pozajmicu.

```
LTU   = pozajmica (co iz SUB32)
SDIFF = a[31] XOR b[31]
LT    = (a[31] AND SDIFF) OR (D[31] AND NOT SDIFF)
EQ    = NOT (ILI-stablo nad D[31..0])
```

Znaci se razlikuju -> manji je onaj koji je negativan. Znaci su isti ->
razlika ne moze da prekoraci opseg, pa odlucuje njen znak.

ILI-stablo: 8x `OR4` (po 4 bita) -> 2x `OR4` -> `OR2` -> `NOT`.

## SHIFT32

```
ulazi   a[31..0]  sa[4..0]  dir  ar
izlaz   o[31..0]
```

| `dir` | `ar` | operacija |
|-------|------|-----------|
| 0 | x | logicko levo |
| 1 | 0 | logicko desno |
| 1 | 1 | aritmeticko desno |

Barrel shifter: dva lanca od po 5 stepena (`MUX2_32`), stepen `k` pomera za
`2^k` ako je `sa[k] = 1`. Zavrsni `MUX2_32` bira lanac po `dir`.

Bit popune kod desnog pomeranja je `FILL = ar AND a[31]` — jedan `AND2`.
Znak se ne menja kroz aritmeticko pomeranje, pa je dovoljno uzeti `a[31]`
jednom, na ulazu.

Stara resenja `LOG_SL32`, `LOG_SR32`, `AR_SR32` pomeraju za tacno 1 mesto i
ostaju u repou, ali ih ALU vise ne koristi.

## ZEXT1_32

`o[31..0] = 31 nula, d`. Koristi se za rezultat `SLT` / `SLTU`.
