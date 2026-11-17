import json,re,csv,collections
rows=json.load(open(__import__('sys').argv[1] if len(__import__('sys').argv)>1 else 'sau_catalog_2026_27_raw.json'))
SUBJ=r'[A-Z]{1,4}(?: [A-Z]{1,3})?'
CODE=re.compile(rf'\b({SUBJ}) ?(\d{{4,5}}[A-Z]?)\b')
def codes(s): return [f"{a} {n}" for a,n in CODE.findall(s)]
def expand_slash(s):  # "BIOL 2063 /2061" -> "BIOL 2063 / BIOL 2061"
    return re.sub(rf'\b({SUBJ}) ?(\d{{4,5}}[A-Z]?)\s*/\s*(\d{{4,5}}[A-Z]?)\b', r'\1 \2 / \1 \3', s)
def clean(s): return re.sub(r'\s+([.,;])',r'\1',re.sub(r'\s+',' ',s)).strip()
def parse_pre(pre):
    """Return (groups, other, review_reasons). groups: list of AND items, each item 'A' or 'A|B' (any one)."""
    t=expand_slash(pre)
    t=re.sub(r'\bor (higher|better|above)\b','',t,flags=re.I)
    t=re.sub(r'\b(conditional|unconditional) or (conditional|unconditional)\b','\\1',t,flags=re.I)
    t=t.rstrip('.')
    groups=[];other=[];review=[]
    clauses=[c.strip() for c in re.split(r';|,|\band\b',t) if c.strip()]
    for c in clauses:
        cs=codes(c)
        has_or=bool(re.search(r'\bor\b',c))
        if not cs:
            other.append(c); continue
        if '/' in c and has_or:
            review.append('mixed or + lecture/lab pair'); groups.append('|'.join(cs)); continue
        if '/' in c:
            groups.extend(cs); continue
        if has_or:
            rest=CODE.sub('',c); rest=re.sub(r'\b(or|in|a|of|grade|minimum|[A-D])\b|[^A-Za-z]','',rest,flags=re.I)
            if rest: review.append('course OR non-course alternative'); other.append(c)
            groups.append('|'.join(cs)); continue
        if len(cs)>1: groups.extend(cs)
        else: groups.append(cs[0])
        rest=re.sub(r'\b(grade|of|minimum|in|a|an|with|C|B|D)\b|[^A-Za-z]','',CODE.sub('',c),flags=re.I)
        if rest: other.append(c)
    if re.search(r'\(|\beither\b',pre,re.I): review.append('complex wording')
    if re.search(r'\bor\b',t) and re.search(r'\band\b',t) and not any('|' in g for g in groups): review.append('and/or mix')
    return list(dict.fromkeys(groups)),other,list(dict.fromkeys(review))
out=[]
for coid,t,b in rows:
    m=re.match(r'^(.+?)\s+(\d{4,5}[A-Z]?)\s+-\s+(.+)$',t.strip())
    code=f"{re.sub(r'\s+',' ',m[1])} {m[2]}"; title=m[3].strip()
    pre=co='';desc=[]
    for line in (b or '').split('\n'):
        line=line.strip()
        if line.startswith('Prerequisites:'): pre=line[14:]
        elif line.startswith('Corequisites:'): co=line[13:]
        elif line.startswith('ACTS Course Equivalent:') or not line: continue
        else: desc.append(line)
    pre,co,desc=clean(pre),clean(co),clean(' '.join(desc))
    groups,other,rev=parse_pre(pre) if pre else ([],[],[])
    if any(x in rev for x in ('and/or mix','complex wording','mixed or + lecture/lab pair')):
        groups=[]; rev.append('prereqs left blank so the checker does not block wrongly; enter by hand')
    if not b: rev.insert(0,'SAU detail page is broken, no description')
    cg,_,_=parse_pre(co) if co else ([],[],[])
    out.append(dict(code=code,title=title,description=desc,prereqs=';'.join(groups),
        other_requirements='; '.join(other),prereq_text=pre,coreqs=';'.join(cg),coreq_text=co,needs_review='; '.join(rev)))
cols=list(out[0].keys())
with open('course_info.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); w.writerows(out)
rv=[r for r in out if r['needs_review']]
print('courses',len(out),'| with description',sum(1 for r in out if r['description']),'| with prereq text',sum(1 for r in out if r['prereq_text']),
      '| with course prereqs',sum(1 for r in out if r['prereqs']),'| OR groups',sum(1 for r in out if '|' in r['prereqs']),
      '| non-course reqs',sum(1 for r in out if r['other_requirements']),'| needs_review',len(rv))
print(collections.Counter(x for r in rv for x in r['needs_review'].split('; ')))
with open('needs_review.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['code','title','prereq_text','prereqs','needs_review']); w.writeheader()
    for r in rv: w.writerow({k:r[k] for k in ['code','title','prereq_text','prereqs','needs_review']})
