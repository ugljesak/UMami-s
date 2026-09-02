import sys, struct
def bin2mif(binpath, out, depth=2048):
    d = open(binpath,'rb').read()
    if len(d) % 4: d += b'\0'*(4-len(d)%4)
    words = struct.unpack('<%dI' % (len(d)//4), d)
    assert len(words) <= depth, f"{len(words)} words exceeds ROM depth {depth}"
    L=["DEPTH = %d;"%depth,"WIDTH = 32;","ADDRESS_RADIX = DEC;","DATA_RADIX = HEX;","CONTENT BEGIN"]
    for i,w in enumerate(words): L.append(f"{i} : {w:08X};")
    if len(words)<depth: L.append(f"[{len(words)}..{depth-1}] : 00000000;")
    L.append("END;")
    open(out,'w').write("\n".join(L)+"\n")
    print(f"{binpath}: {len(words)}/{depth} words -> {out}")
if __name__=='__main__':
    bin2mif(sys.argv[1], sys.argv[2])
