ENTRY(_start)
PHDRS { text PT_LOAD FLAGS(5); }
SECTIONS {
  . = 0;
  .text : { *(.text.start) *(.text*) *(.rodata*) *(.srodata*) } :text
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) *(.riscv.attributes) }
}
