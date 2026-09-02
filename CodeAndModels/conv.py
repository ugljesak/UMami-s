import sys, math
PALETTE = {  # fallback if the .mtl has no entry
 'default':0x0888,
}
def colour_of(mat, mtl):
    if mat in mtl: return mtl[mat]
    return PALETTE.get(mat, PALETTE['default'])
def load_mtl(path):
    """Blender writes Kd per material -> 12-bit 0xBGR."""
    import os
    cols={}; cur=None
    if not os.path.exists(path): return cols
    for ln in open(path):
        t=ln.split()
        if not t: continue
        if t[0]=='newmtl': cur=t[1]
        elif t[0]=='Kd' and cur:
            r,g,b=[max(0,min(15,int(round(float(v)*15)))) for v in t[1:4]]
            cols[cur]=(b<<8)|(g<<4)|r
    return cols

def load_obj(path, coord_max=255):
    import os
    V=[]; F=[]; mat='default'; mtl={}
    for ln in open(path):
        t=ln.split()
        if t and t[0]=='mtllib':
            mtl.update(load_mtl(os.path.join(os.path.dirname(path) or '.', t[1])))
    for ln in open(path):
        t=ln.split()
        if not t: continue
        if t[0]=='v': V.append([float(t[1]),float(t[2]),float(t[3])])
        elif t[0]=='usemtl': mat=t[1]
        elif t[0]=='f':
            idx=[int(p.split('/')[0])-1 for p in t[1:]]
            for k in range(1,len(idx)-1):        # fan-triangulate anything non-tri
                F.append((idx[0],idx[k],idx[k+1],mat))
    cx=[(min(v[i] for v in V)+max(v[i] for v in V))/2 for i in range(3)]
    r=max(max(abs(v[i]-cx[i]) for v in V) for i in range(3))
    V=[[int(round((v[i]-cx[i])/r*coord_max)) for i in range(3)] for v in V]
    return V,F,mtl
def pack_v(v):
    return ((v[0]&0x3FF)) | ((v[1]&0x3FF)<<10) | ((v[2]&0x3FF)<<20)
def pack_t(f):
    return f[0] | (f[1]<<8) | (f[2]<<16)
if __name__=='__main__':
    V,F,M=load_obj(sys.argv[1] if len(sys.argv)>1 else 'house.obj')
    print(f"{len(V)} vertices, {len(F)} triangles")
    print(f"coord range: {min(min(v) for v in V)} .. {max(max(v) for v in V)}")
    print("packed verts:", [f"{pack_v(v):08X}" for v in V[:4]], "...")
    print("packed tris :", [f"{pack_t(f):08X}" for f in F[:4]], "...")
    print("materials   :", {m:f"{colour_of(m,M):03X}" for m in sorted({f[3] for f in F})})
    words = len(V) + 2*len(F)
    print(f"ROM data: {words} words -> ~{words*2}-{words*3} instructions")
