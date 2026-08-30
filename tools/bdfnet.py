#!/usr/bin/env python3
"""Minimal Quartus BDF netlist extractor / checker."""
import sys, re, collections

def toplevel_blocks(s):
    """Yield (kind, body) for each top-level (kind ...) sexp."""
    i=0; n=len(s)
    while i<n:
        if s[i]=='(':
            depth=0; j=i; instr=False
            while j<n:
                c=s[j]
                if c=='"': instr = not instr
                elif not instr:
                    if c=='(': depth+=1
                    elif c==')':
                        depth-=1
                        if depth==0: break
                j+=1
            blk=s[i:j+1]
            m=re.match(r'\((\w+)', blk)
            if m: yield m.group(1), blk
            i=j+1
        else: i+=1

def parse(path):
    s=open(path,errors='ignore').read()
    # strip C comments
    s=re.sub(r'/\*.*?\*/','',s,flags=re.S)
    syms=[]; pins=[]; conns=[]
    for kind, blk in toplevel_blocks(s):
        if kind=='symbol':
            r=[int(x) for x in re.search(r'\(rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)\)', blk).groups()]
            texts=re.findall(r'\(text "([^"]*)"', blk)
            name=texts[0] if texts else '?'
            inst=texts[1] if len(texts)>1 else '?'
            ports=[]
            for pm in re.finditer(r'\(port\s*(.*?)\n\t\)', blk, re.S):
                b=pm.group(1)
                pt=re.search(r'\(pt (-?\d+) (-?\d+)\)', b)
                d='in' if '(input)' in b else ('out' if '(output)' in b else 'bidir')
                t=re.search(r'\(text "([^"]*)"', b)
                if pt:
                    ports.append((t.group(1) if t else '?', d,
                                  (r[0]+int(pt.group(1)), r[1]+int(pt.group(2)))))
            syms.append(dict(name=name, inst=inst, rect=r, ports=ports))
        elif kind=='pin':
            r=[int(x) for x in re.search(r'\(rect (-?\d+) (-?\d+) (-?\d+) (-?\d+)\)', blk).groups()]
            d='in' if '(input)' in blk else ('out' if '(output)' in blk else 'bidir')
            texts=[t for t in re.findall(r'\(text "([^"]*)"', blk)
                   if t not in ('INPUT','OUTPUT','BIDIR','VCC','GND')]
            pt=re.search(r'\(pt (-?\d+) (-?\d+)\)', blk)
            pins.append(dict(name=texts[0] if texts else '?', dir=d,
                             pt=(r[0]+int(pt.group(1)), r[1]+int(pt.group(2)))))
        elif kind=='connector':
            pts=[(int(a),int(b)) for a,b in re.findall(r'\(pt (-?\d+) (-?\d+)\)', blk)]
            t=re.search(r'\(text "([^"]*)"', blk)
            conns.append(dict(pts=pts, label=t.group(1) if t else None,
                              bus='(bus)' in blk))
    return syms, pins, conns

def netlist(syms, pins, conns):
    parent={}
    def find(x):
        parent.setdefault(x,x)
        while parent[x]!=x: parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[ra]=rb
    # nodes = coordinates
    for c in conns:
        for p in c['pts']: find(p)
        for a,b in zip(c['pts'], c['pts'][1:]): union(a,b)
    for s in syms:
        for _,_,p in s['ports']: find(p)
    for p in pins: find(p['pt'])

    # T-junctions: endpoint lying on another axis-aligned segment
    allpts=list(parent.keys())
    segs=[]
    for c in conns:
        for a,b in zip(c['pts'], c['pts'][1:]): segs.append((a,b))
    for (a,b) in segs:
        for p in allpts:
            if p==a or p==b: continue
            if a[0]==b[0]==p[0] and min(a[1],b[1])<=p[1]<=max(a[1],b[1]): union(p,a)
            elif a[1]==b[1]==p[1] and min(a[0],b[0])<=p[0]<=max(a[0],b[0]): union(p,a)

    # label groups
    lbl={}
    for c in conns:
        if c['label'] and c['pts']:
            lbl.setdefault(c['label'], []).append(c['pts'][0])
    for name, ps in lbl.items():
        for p in ps[1:]: union(ps[0], p)

    nets=collections.defaultdict(lambda: dict(labels=set(), members=[]))
    for c in conns:
        if c['label'] and c['pts']:
            nets[find(c['pts'][0])]['labels'].add(c['label'])
    for s in syms:
        for pn,d,p in s['ports']:
            nets[find(p)]['members'].append(f"{s['name']}({s['inst']}).{pn}:{d}")
    for p in pins:
        nets[find(p['pt'])]['members'].append(f"PIN {p['name']}:{p['dir']}")
    return nets

if __name__=='__main__':
    path=sys.argv[1]
    filt=sys.argv[2] if len(sys.argv)>2 else None
    syms,pins,conns=parse(path)
    nets=netlist(syms,pins,conns)
    print(f"# {path}: {len(syms)} symbols, {len(pins)} pins, {len(conns)} connectors, {len(nets)} nets")
    for k,v in nets.items():
        nm=','.join(sorted(v['labels'])) or '(unnamed)'
        line=f"{nm:45s} <- {'; '.join(v['members'])}"
        if filt is None or re.search(filt, line, re.I): print(line)
