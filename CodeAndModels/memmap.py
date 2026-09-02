# byte addresses in DATA RAM (2048 words, 0..8191). Must match hw.h
SPAN_B  = 0        # 200 words
SX_B    = 800      # 232 words
SY_B    = 1728
SZ_B    = 2656
TYR_B   = 3584     # 232 words, packed (ymax<<16)|ymin
SIN_B   = 4512     #  65 words
MODEL_B = 4800     # [nv][nt][verts][tris][cols]
STACK_TOP = 8184
MODEL_CAP = (7672 - MODEL_B)//4    # 718 words
MAXV = MAXT = 232
