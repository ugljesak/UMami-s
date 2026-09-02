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

int main(void){
    int nv = MODEL[0], nt = MODEL[1];
    volatile int *VP = MODEL + 2, *TP = VP + nv, *CP = TP + nt;
    int yaw = 0, pit = 22, opx = 0, opy = 0, first = 1;

    for(;;){
        unsigned m = MOUSE;
        int mx = (m >> 8) & 255, my = (m >> 16) & 255, btn = m & 7;
        if (first){ opx = mx; opy = my; first = 0; }
        if (btn){
            yaw -= mx - opx;
            pit -= my - opy;
            if (pit >  60) pit =  60;
            if (pit < -60) pit = -60;
        } else yaw += 1;
        opx = mx; opy = my;
        yaw &= 255;
        int ccx = (mx * W) >> 8;                 /* cursor centre */
        int ccy = ((255 - my) * H) >> 8;         /* mouse Y is inverted */

        int cy = icos(yaw), sy = isin(yaw);
        int cp = icos(pit), sp = isin(pit);

        for (int i = 0; i < nv; i++){
            int p = VP[i];
            int vx = (p << 22) >> 22, vy = (p << 12) >> 22, vz = (p << 2) >> 22;
            int rx = (vx*cy + vz*sy) >> 8;
            int rz = (vz*cy - vx*sy) >> 8;
            int ty = (vy*cp + rz*sp) >> 8;
            int tz = (rz*cp - vy*sp) >> 8;
            SXA[i] = 100 + ((rx * 62)  >> 8);
            SYA[i] = 150 - ((ty * 124) >> 8);
            SZA[i] = (tz * 64) + 32768;      /* 256x finer depth */
        }
        for (int t = 0; t < nt; t++){
            int w = TP[t];
            int i0 = w & 255, i1 = (w >> 8) & 255, i2 = (w >> 16) & 255;
            int ax = SXA[i0], ay = SYA[i0];
            int bx = SXA[i1], by = SYA[i1];
            int cx = SXA[i2], cyy = SYA[i2];
            if ((bx-ax)*(cyy-ay) - (by-ay)*(cx-ax) <= 0){ TYR[t] = 1u; continue; }
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
            if (dy > -2 && dy < 2){ clo = ccx - 3; chi = ccx + 3; }   /* bar */
            else if (dy > -7 && dy < 7){ clo = ccx; chi = ccx; }      /* stem */
            else { clo = 1; chi = 0; }                                /* none */
            for (int x = 0; x < W; x++){
                int col = (x >= clo && x <= chi) ? 0xFFF : (int)(SPAN[x] & 0xFFF);
                while (!pbr());
                ppxl(x, col);
            }
        }
    }
    return 0;
}
