#ifndef HW_H
#define HW_H
#define W 200
#define H 300
#define MAXV 232
#define MAXT 232
#define NMODELS 4

#define SPAN   ((volatile unsigned int*)0)      /* 200 w : (depth<<16)|colour */
#define SXA    ((volatile int*)800)             /* MAXV w */
#define SYA    ((volatile int*)1728)
#define SZA    ((volatile int*)2656)
#define TYR    ((volatile unsigned int*)3584)   /* MAXT w */
#define SINT   ((volatile int*)4512)            /*  65 w */
#define MODEL1 ((volatile int*)4800)            /* word 1200 */
#define MODEL2 ((volatile int*)8000)            /* word 2000 */
#define MODEL3 ((volatile int*)11200)           /* word 2800 */
#define MODEL4 ((volatile int*)14400)           /* word 3600 */
#define MOUSE  (*(volatile unsigned int*)32764) /* word 8191, all-ones addr[13..0] */

static inline void ppxl(int a,int c){ __asm__ volatile(".insn s 0x23,0x4,%1,0(%0)"::"r"(a),"r"(c)); }
static inline int  pbr(void){ int r; __asm__ volatile(".insn i 0x03,0x3,%0,zero,0":"=r"(r)); return r; }
#endif
