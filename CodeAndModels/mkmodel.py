import sys, math
from conv import load_obj, pack_v, pack_t, colour_of
from memmap import *
def build(objpath, out):
    V,F,MTL = load_obj(objpath)
    need = 2 + len(V) + 2*len(F)
    assert len(V) <= MAXV, f"{len(V)} vertices exceeds MAXV={MAXV}"
    assert len(F) <= MAXT, f"{len(F)} triangles exceeds MAXT={MAXT}"
    assert need <= MODEL_CAP, f"model needs {need} words, cap {MODEL_CAP}"
    mem = {}
    for k in range(65):
        mem[SIN_B//4 + k] = round(256*math.sin(2*math.pi*k/256)) & 0xFFFFFFFF
    base = MODEL_B//4
    mem[base]   = len(V)
    mem[base+1] = len(F)
    for i,v in enumerate(V):            mem[base+2+i] = pack_v(v)
    for i,f in enumerate(F):            mem[base+2+len(V)+i] = pack_t(f)
    for i,f in enumerate(F):            mem[base+2+len(V)+len(F)+i] = colour_of(f[3],MTL)
    lines=["DEPTH = 2048;","WIDTH = 32;","ADDRESS_RADIX = DEC;","DATA_RADIX = HEX;","CONTENT BEGIN"]
    prev=-1
    for a in sorted(mem):
        if a != prev+1 and a > prev+1:
            lines.append(f"[{prev+1}..{a-1}] : 00000000;")
        lines.append(f"{a} : {mem[a]:08X};")
        prev=a
    lines.append(f"[{prev+1}..2047] : 00000000;")
    lines.append("END;")
    open(out,'w').write("\n".join(lines)+"\n")
    print(f"{objpath}: {len(V)} verts, {len(F)} tris, {need}/{MODEL_CAP} model words -> {out}")
    return V,F
if __name__=='__main__':
    build(sys.argv[1] if len(sys.argv)>1 else 'house.obj',
          sys.argv[2] if len(sys.argv)>2 else '/mnt/user-data/outputs/model.mif')
