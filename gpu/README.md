# SDRAM kontroler (UMAMI-S)

Kontroler za eksternu SDRAM memoriju na Terasic DE0 pločici. Realizovan u
potpunosti šematskim unosom (BDF), bez pisanja VHDL/Verilog koda.

## Ciljni hardver

| Stavka | Vrednost |
|---|---|
| FPGA | Cyclone III EP3C16F484 |
| SDRAM čip | ISSI IS42S16400, 8 MB |
| Organizacija | 4 banke × 4096 redova × 256 kolona × 16 bita |
| Sistemski takt | 50 MHz (period 20 ns) |
| Refresh interval | 15.625 µs (4096 redova / 64 ms) |
| CAS latencija | 2 |
| Alat | Quartus II 13.1 Web Edition |

Adresni prostor je 22 bita (4 194 304 reči po 16 bita):

```
addr[21:20] → banka    (BA[1:0])
addr[19:8]  → red      (ADDR[11:0] pri ACTIVATE)
addr[7:0]   → kolona   (ADDR[7:0] pri READ/WRITE)
```

## Princip rada

Kontroler je mikroprogramirani konačni automat. Umesto mreže kapija koja iz
stanja računa upravljačke signale, koristi se ROM u kome svaki red predstavlja
jedno stanje.

```
ROM (registrovana adresa = stanje)
  │
  ├─→ cmd_sel  → MUX8×4  → CS_N, RAS_N, CAS_N, WE_N
  ├─→ addr_sel → MUX8×14 → BA[1:0], ADDR[11:0]
  ├─→ cond_sel → MUX8×1  ─┐
  ├─→ next_T ─────────────┤ MUX2×6 → nazad u adresu ROM-a
  └─→ next_F ─────────────┘
```

Jedan takt = jedan red ROM-a. Čekanje na tajming parametre (tRCD, tRP, tRFC)
se izražava kao redovi koji šalju NOP i prelaze na sledeći red — nema tajmera
ni brojača unutar automata.

Adresa sledećeg reda je uvek eksplicitna. Svaki red nosi dve adrese (`next_T`
i `next_F`) i bira između njih na osnovu testiranog uslova, pa nema
inkrementera.

### Format mikroinstrukcije (24 bita)

| Biti | Polje | Opis |
|---|---|---|
| 23:18 | `next_T` | sledeće stanje ako je uslov tačan |
| 17:12 | `next_F` | sledeće stanje ako uslov nije tačan |
| 11:9 | `cond_sel` | izbor uslova za testiranje |
| 8:6 | `cmd_sel` | izbor SDRAM komande |
| 5:3 | `addr_sel` | izbor izvora za adresne pinove |
| 2 | `ready` | signal završetka ka sistemu |
| 1 | `dq_oe` | dozvola tri-state bafera na DQ |
| 0 | `latch_rd` | hvatanje pročitanog podatka |

### Tabela komandi (`cmd_sel` → `MUX8×4`)

Redosled bita: `{CS_N, RAS_N, CAS_N, WE_N}`

| `cmd_sel` | Komanda | Vrednost |
|---|---|---|
| 0 | Command Inhibit | `1111` |
| 1 | NOP | `0111` |
| 2 | ACTIVATE | `0011` |
| 3 | READ | `0101` |
| 4 | WRITE | `0100` |
| 5 | PRECHARGE | `0010` |
| 6 | AUTO REFRESH | `0001` |
| 7 | LOAD MODE REGISTER | `0000` |

### Tabela adresnih izvora (`addr_sel` → `MUX8×14`)

Redosled bita: `{BA1, BA0, A11..A0}`

| `addr_sel` | Namena | Sadržaj |
|---|---|---|
| 0 | neutralno (NOP) | 14 nula |
| 1 | aktivacija reda | `addr[21..8]` |
| 2 | kolona + auto-precharge | `addr[21..20], 0,1,0,0, addr[7..0]` |
| 3 | kolona bez auto-precharge | `addr[21..20], 0,0,0,0, addr[7..0]` |
| 4 | precharge svih banaka | `A10 = 1`, ostalo nule |
| 5 | mode registar (`0x020`) | `A5 = 1`, ostalo nule |
| 6, 7 | rezerva | 14 nula |

Mode registar `0x020` znači: burst dužine 1, sekvencijalni redosled,
CAS latencija 2, burst i za upis.

### Tabela uslova (`cond_sel` → `MUX8×1`)

| `cond_sel` | Signal |
|---|---|
| 0 | `GND` (nikad — uvek `next_F`) |
| 1 | `VCC` (uvek — bezuslovni skok) |
| 2 | `refresh_req` |
| 3 | `REQ` |
| 4 | `WE` |
| 5 | `init_done` |
| 6, 7 | `GND` |

## Interfejs

### Ka sistemu

| Signal | Širina | Smer | Opis |
|---|---|---|---|
| `CLK` | 1 | ulaz | iz PLL, izlaz `c0` |
| `RST` | 1 | ulaz | reset |
| `REQ` | 1 | ulaz | zahtev za pristup |
| `WE` | 1 | ulaz | 1 = upis, 0 = čitanje |
| `addr` | 22 | ulaz | adresa memorijske reči |
| `wdata` | 16 | ulaz | podatak za upis |
| `rdata` | 16 | izlaz | pročitani podatak |
| `ready` | 1 | izlaz | impuls po završetku transakcije |
| `busy` | 1 | izlaz | transakcija u toku |

### Ka SDRAM čipu

| Signal | Širina | Opis |
|---|---|---|
| `DRAM_CS`, `DRAM_RAS`, `DRAM_CAS`, `DRAM_WE` | 1 | komandni pinovi |
| `DRAM_ADDR` | 12 | multipleksirana adresa (red / kolona) |
| `DRAM_BA` | 2 | izbor banke |
| `DRAM_DQ` | 16 | dvosmerna magistrala podataka |

Signali koji se vezuju u top-level šemi, ne u ovom bloku:
`DRAM_CKE` → `VCC`, `DRAM_DQM0/1` → `GND`, `DRAM_CLK` → PLL izlaz `c1`
sa faznim pomerajem −3 ns.

## Trenutno stanje

Realizovano u šemi:

- ROM 64 × 24 bita (M9K, registrovan adresni ulaz, neregistrovan `q` izlaz)
- `MUX8×1` — izbor uslova
- `MUX2×6` — izbor sledećeg stanja
- `MUX8×4` — generisanje komandi
- `MUX8×14` — generisanje adresa
- Brojač 16 bita za odbrojavanje početnog čekanja (`a[14]` → 327 µs)
- Reset logika: 6 × AND2 između izlaza `MUX2×6` i adrese ROM-a
- Izlazni pinovi za komandne i adresne signale

Mikroprogram: implementirana je **samo init sekvenca** (adrese 0–13).

| Adr | Komanda | Opis |
|---|---|---|
| 0 | NOP | petlja na samu sebe dok `init_done` = 0 |
| 1 | PRECHARGE | zatvaranje svih banaka (`A10 = 1`) |
| 2 | NOP | tRP |
| 3 | AUTO REFRESH | |
| 4–6 | NOP ×3 | tRFC |
| 7 | AUTO REFRESH | |
| 8–10 | NOP ×3 | tRFC |
| 11 | LOAD MODE REGISTER | CAS latencija 2, burst 1 |
| 12–13 | NOP ×2 | tMRD, zatim skok na 16 |

Sadržaj `.mif` fajla (heksadecimalno):

```
0  : 040A40;   8  : 240240;
1  : 080360;   9  : 280240;
2  : 0C0240;  10  : 2C0240;
3  : 100380;  11  : 3003E8;
4  : 140240;  12  : 340240;
5  : 180240;  13  : 380240;
6  : 1C0240;
7  : 200380;  [14..63] : 000000;
```

U toku: funkcionalna simulacija init sekvence u University Program VWF.

## Naredni koraci

### 1. Verifikacija init faze

Simulirati i potvrditi da se na komandnim pinovima pojavljuje redosled
`NOP → PRECHARGE → REFRESH → REFRESH → LOAD MODE REGISTER`.

Za bržu simulaciju privremeno smanjiti brojač (koristiti `a[5]` umesto `a[14]`,
čekanje 32 takta umesto 16384) i vratiti pre implementacije na pločici.

### 2. Refresh

- Brojač 9 bita, uslov `q[8]` (512 taktova ≈ 10.2 µs)
- DFF za `refresh_req`, briše se komparatorom na poslednje stanje refresh rutine
- Mikrokod: stanja 16–17 (IDLE) i 32–37 (PRECHARGE ALL → REFRESH → tRFC)

Refresh mora imati najviši prioritet u IDLE stanju.

### 3. Upis jedne reči

- 16 DFF-ova + 16 TRI bafera na `DRAM_DQ`, `OE` iz registrovanog `dq_oe`
- Mikrokod: stanja 24–27 (tRCD → WRITE → tWR → tRP)

### 4. Čitanje jedne reči

- Registar 16 bita sa `ENA` iz `latch_rd`, ulaz `DRAM_DQ`, izlaz `rdata`
- Mikrokod: stanja 18–23 (tRCD → READ → CL → latch → ready)

Poziciju `latch_rd` verovatno će trebati podesiti eksperimentalno (CAS
latencija 2 ili 3 efektivnih taktova zbog kašnjenja pinova).

### 5. Izlazni registri

Svaki signal ka čipu mora proći kroz DFF taktovan sistemskim taktom. Nijedan
kombinacioni signal ne sme direktno u izlazni pin — mux-evi imaju različita
kašnjenja po bitovima i prelazne vrednosti se mogu protumačiti kao komande.

### 6. Verifikacija na pločici

- PLL sa dva izlaza: `c0` za logiku, `c1` sa faznim pomerajem −3 ns za `DRAM_CLK`
- Pin assignment iz Terasic System Builder-a
- Test: upis `0xBEEF` na adresu 0, čitanje, poređenje, indikacija na LED
- Proširenje: 1000 adresa sa uzorkom `addr XOR 0xA5A5`, provera u trajanju od
  jednog minuta radi verifikacije refresh logike

### 7. Integracija

- Blok za računanje adrese piksela iz koordinata
- Arbitar između VGA čitanja i upisa piksela (prioritet: refresh > VGA > upis)
- Burst čitanje za VGA linijski bafer

Planirana raspodela po bankama:

| Banka | Sadržaj |
|---|---|
| 0 | frejmbafer A |
| 1 | frejmbafer B |
| 2 | Z-bafer |
| 3 | slobodna |

Ovakva raspodela omogućava da tri korisnika istovremeno drže otvorene redove u
različitim bankama, čime se izbegavaju dodatne ACTIVATE/PRECHARGE sekvence.

## Reference

- IS42S16400 datasheet — Command Truth Table, Mode Register Definition,
  Initialization, AC Characteristics
- Micron MT48LC4M16A2 datasheet — funkcionalno ekvivalentan čip, detaljniji
  dijagram stanja
- DE0 User Manual — pin assignment za SDRAM
- Cyclone III Device Handbook — M9K blokovi, ALTPLL
