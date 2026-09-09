#include "hw.h"

static int isin(int t){
    t &= 255;
    int k = t & 63, q = (t >> 6) & 3;
    int a = SINT[k], b = SINT[64 - k];
    if (q == 0) return  a;
    if (q == 1) return  b;
    if (q == 2) return -a;
    return -b;
}
static int icos(int t){ return isin(t + 64); }

/* Four "1"/"2"/"3"/"4" buttons in a row at bottom-right.
   Each 20 wide x 20 tall, spaced 3 apart. Right edge at x=196.
   Button 4: 176..196, Button 3: 153..173, Button 2: 130..150, Button 1: 107..127
   All buttons share y = 275..294. */
#define B_W    20
#define B_GAP  3
#define B_RIGHT 196
#define BY0    275
#define BY1    294
#define B1_X0  107
#define B1_X1  127
#define B2_X0  130
#define B2_X1  150
#define B3_X0  153
#define B3_X1  173
#define B4_X0  176
#define B4_X1  196

static int in_rect(int cx, int cy, int x0, int x1){
    return (cx >= x0 && cx <= x1 && cy >= BY0 && cy <= BY1);
}
static int on_button_pixel(int x, int y, int x0, int x1){
    if (x < x0 || x > x1 || y < BY0 || y > BY1) return 0;
    if ((x==x0 && y==BY0) || (x==x1 && y==BY0) ||
        (x==x0 && y==BY1) || (x==x1 && y==BY1)) return 0;
    return 1;
}

/* 3x5 glyphs for digits 1..4, centered at (dx,dy)=(0,0) in the button */
static int glyph_pixel(int digit, int dx, int dy){
    /* returns 1 if this pixel is part of the digit */
    if (dy < -2 || dy > 2 || dx < -1 || dx > 1) return 0;
    switch (digit){
    case 1:
        if (dy==-2) return dx== 0;
        if (dy==-1) return dx==-1 || dx==0;
        if (dy== 0) return dx== 0;
        if (dy== 1) return dx== 0;
        if (dy== 2) return dx>=-1 && dx<=1;
        return 0;
    case 2:
        if (dy==-2) return dx>=-1 && dx<=1;
        if (dy==-1) return dx== 1;
        if (dy== 0) return dx>=-1 && dx<=1;
        if (dy== 1) return dx==-1;
        if (dy== 2) return dx>=-1 && dx<=1;
        return 0;
    case 3:
        if (dy==-2) return dx>=-1 && dx<=1;
        if (dy==-1) return dx== 1;
        if (dy== 0) return dx>=-1 && dx<=1;
        if (dy== 1) return dx== 1;
        if (dy== 2) return dx>=-1 && dx<=1;
        return 0;
    case 4:
        if (dy==-2) return dx==-1 || dx==1;
        if (dy==-1) return dx==-1 || dx==1;
        if (dy== 0) return dx>=-1 && dx<=1;
        if (dy== 1) return dx== 1;
        if (dy== 2) return dx== 1;
        return 0;
    }
    return 0;
}

/* returns overlay color if (x,y) is inside a button, else -1.
   No arrays — unrolled so GCC folds constants into immediates instead of
   generating .rodata loads (which would go through the ROM bus incorrectly). */
static int button_overlay(int x, int y, int active){
    if (on_button_pixel(x, y, B1_X0, B1_X1)){
        int cx = (B1_X0 + B1_X1) >> 1, cy = (BY0 + BY1) >> 1;
        if (glyph_pixel(1, x - cx, y - cy)) return 0xFFF;
        return (active == 0) ? 0x0F0 : 0x333;
    }
    if (on_button_pixel(x, y, B2_X0, B2_X1)){
        int cx = (B2_X0 + B2_X1) >> 1, cy = (BY0 + BY1) >> 1;
        if (glyph_pixel(2, x - cx, y - cy)) return 0xFFF;
        return (active == 1) ? 0x0F0 : 0x333;
    }
    if (on_button_pixel(x, y, B3_X0, B3_X1)){
        int cx = (B3_X0 + B3_X1) >> 1, cy = (BY0 + BY1) >> 1;
        if (glyph_pixel(3, x - cx, y - cy)) return 0xFFF;
        return (active == 2) ? 0x0F0 : 0x333;
    }
    if (on_button_pixel(x, y, B4_X0, B4_X1)){
        int cx = (B4_X0 + B4_X1) >> 1, cy = (BY0 + BY1) >> 1;
        if (glyph_pixel(4, x - cx, y - cy)) return 0xFFF;
        return (active == 3) ? 0x0F0 : 0x333;
    }
    return -1;
}

/* which button (0..3) contains (cx,cy), or -1. Also inline, no array. */
static int hit_button(int cx, int cy){
    if (in_rect(cx, cy, B1_X0, B1_X1)) return 0;
    if (in_rect(cx, cy, B2_X0, B2_X1)) return 1;
    if (in_rect(cx, cy, B3_X0, B3_X1)) return 2;
    if (in_rect(cx, cy, B4_X0, B4_X1)) return 3;
    return -1;
}

int main(void){
    int yaw[NMODELS] = {0, 0, 0, 0};
    int pit[NMODELS] = {22, 22, 22, 22};
    int opx = 0, opy = 0, first = 1, prev_btn = 0;
    int active = 0;

    volatile int * const MODELS[NMODELS] = { MODEL1, MODEL2, MODEL3, MODEL4 };

    for(;;){
        volatile int *MODEL = MODELS[active];
        int nv = MODEL[0], nt = MODEL[1];
        volatile int *VP = MODEL + 2, *TP = VP + nv, *CP = TP + nt;

        unsigned m = MOUSE;
        int mx = (m >> 8) & 255, my = (m >> 16) & 255, btn = m & 7;
        if (first){ opx = mx; opy = my; first = 0; }

        int ccx = (mx * W) >> 8;
        int ccy = ((255 - my) * H) >> 8;

        int press = (btn & 1) && !(prev_btn & 1);
        if (press){
            int b = hit_button(ccx, ccy);
            if (b >= 0) active = b;
        }
        prev_btn = btn;

        int on_ui = (hit_button(ccx, ccy) >= 0);
        if ((btn & 1) && !on_ui){
            yaw[active] -= mx - opx;
            pit[active] -= my - opy;
            if (pit[active] >  60) pit[active] =  60;
            if (pit[active] < -60) pit[active] = -60;
        } else if (!(btn & 1)) {
            yaw[active] += 1;
        }
        opx = mx; opy = my;
        yaw[active] &= 255;

        int cy = icos(yaw[active]), sy = isin(yaw[active]);
        int cp = icos(pit[active]), sp = isin(pit[active]);

        for (int i = 0; i < nv; i++){
            int p = VP[i];
            int vx = (p << 22) >> 22, vy = (p << 12) >> 22, vz = (p << 2) >> 22;
            int rx = (vx*cy + vz*sy) >> 8;
            int rz = (vz*cy - vx*sy) >> 8;
            int ty = (vy*cp + rz*sp) >> 8;
            int tz = (rz*cp - vy*sp) >> 8;
            SXA[i] = 100 + ((rx * 62)  >> 8);
            SYA[i] = 150 - ((ty * 124) >> 8);
            SZA[i] = (tz * 64) + 32768;
        }
        for (int t = 0; t < nt; t++){
            int w = TP[t];
            int i0 = w & 255, i1 = (w >> 8) & 255, i2 = (w >> 16) & 255;
            int ax = SXA[i0], ay = SYA[i0];
            int bx = SXA[i1], by = SYA[i1];
            int cx0 = SXA[i2], cyy = SYA[i2];
            if ((bx-ax)*(cyy-ay) - (by-ay)*(cx0-ax) <= 0){ TYR[t] = 1u; continue; }
            int lo = ay, hi = ay;
            if (by  < lo) lo = by;   if (by  > hi) hi = by;
            if (cyy < lo) lo = cyy;  if (cyy > hi) hi = cyy;
            if (lo < 0) lo = 0;      if (hi > H-1) hi = H-1;
            TYR[t] = ((unsigned)hi << 16) | (unsigned)lo;
        }
        for (int y = 0; y < H; y++){
            for (int x = 0; x < W; x++) SPAN[x] = 0xFFFF0000u;
            for (int t = 0; t < nt; t++){
                unsigned r = TYR[t];
                if (y < (int)(r & 0xFFFF) || y > (int)(r >> 16)) continue;
                int w = TP[t];
                int ia = w & 255, ib = (w >> 8) & 255, ic = (w >> 16) & 255;
                int xmn = 99999, xmx = -99999, zmn = 0, zmx = 0;
                for (int e = 0; e < 3; e++){
                    int ya = SYA[ia], yb = SYA[ib];
                    if (ya == yb){
                        if (y == ya){
                            int xa = SXA[ia], za = SZA[ia], xb = SXA[ib], zb = SZA[ib];
                            if (xa < xmn){ xmn = xa; zmn = za; }
                            if (xa > xmx){ xmx = xa; zmx = za; }
                            if (xb < xmn){ xmn = xb; zmn = zb; }
                            if (xb > xmx){ xmx = xb; zmx = zb; }
                        }
                    } else {
                        int lo = ya, hi = yb;
                        if (lo > hi){ lo = yb; hi = ya; }
                        if (y >= lo && y <= hi){
                            int d = yb - ya;
                            int x = SXA[ia] + (y - ya) * (SXA[ib] - SXA[ia]) / d;
                            int z = SZA[ia] + (y - ya) * (SZA[ib] - SZA[ia]) / d;
                            if (x < xmn){ xmn = x; zmn = z; }
                            if (x > xmx){ xmx = x; zmx = z; }
                        }
                    }
                    int tt = ia; ia = ib; ib = ic; ic = tt;
                }
                if (xmn > xmx) continue;
                int col = CP[t];
                int dz = (xmx > xmn) ? (zmx - zmn) / (xmx - xmn) : 0;
                int x0 = xmn, z = zmn;
                if (x0 < 0){ z += (0 - x0) * dz; x0 = 0; }
                int x1 = (xmx > W-1) ? W-1 : xmx;
                for (int x = x0; x <= x1; x++){
                    unsigned p = ((unsigned)(z & 0xFFFF) << 16) | (unsigned)col;
                    if (p < SPAN[x]) SPAN[x] = p;
                    z += dz;
                }
            }
            int dy = y - ccy, clo, chi;
            if (dy > -2 && dy < 2){ clo = ccx - 3; chi = ccx + 3; }
            else if (dy > -7 && dy < 7){ clo = ccx; chi = ccx; }
            else { clo = 1; chi = 0; }
            for (int x = 0; x < W; x++){
                int col = (int)(SPAN[x] & 0xFFF);
                int ov  = button_overlay(x, y, active);
                if (ov >= 0) col = ov;
                if (x >= clo && x <= chi) col = 0xFFF;
                while (!pbr());
                ppxl(x, col);
            }
        }
    }
    return 0;
}
