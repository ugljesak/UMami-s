#ifndef HW_H
#define HW_H
#define W 200
#define H 300
#define MAXV 232
#define MAXT 232
#define SPAN  ((volatile unsigned int*)0)      /* 200 w : (depth<<16)|colour */
#define SXA   ((volatile int*)800)             /* MAXV w */
#define SYA   ((volatile int*)1728)
#define SZA   ((volatile int*)2656)
#define TYR   ((volatile unsigned int*)3584)   /* MAXT w : (ymax<<16)|ymin  */
#define SINT  ((volatile int*)4512)            /*  65 w : 256*sin(2pi k/256) */
#define MODEL ((volatile int*)4800)            /* [nv][nt][verts][tris][cols] */
#define MOUSE (*(volatile unsigned int*)8188)
static inline void ppxl(int a,int c){ __asm__ volatile(".insn s 0x23,0x4,%1,0(%0)"::"r"(a),"r"(c)); }
static inline int  pbr(void){ int r; __asm__ volatile(".insn i 0x03,0x3,%0,zero,0":"=r"(r)); return r; }
#endif
