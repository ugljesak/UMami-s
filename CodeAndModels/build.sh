#!/bin/sh
set -e
riscv64-linux-gnu-gcc -march=rv32im -mabi=ilp32 -O2 -fwrapv -ffreestanding -nostdlib \
  -nostartfiles -static -fno-jump-tables -Wl,--build-id=none -Wl,--no-check-sections \
  -Wl,-n -T link.ld crt0.S render.c -o render.elf 2>/dev/null
riscv64-linux-gnu-objcopy -O binary -j .text render.elf render.bin
