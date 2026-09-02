.section .text.start
.globl _start
_start:
    li   sp, 8184
    jal  ra, main
1:  j    1b
