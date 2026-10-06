import json,glob,re,unicodedata,statistics as st,sys
import os; H=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'history') + os.sep
dr=json.load(open(H+'drivers_openwheel.json'))
def norm(n): return re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',n).encode('ascii','ignore').decode().lower())
wk={};S={}
for s in ['usf2000','pro_mazda','indy_lights','irl_indycar','cart_champcar']:
    S[s]={}
    for f in sorted(glob.glob(H+s+'/*.json')):
        d=json.load(open(f)); S[s][d['year']]=d
        for r in d.get('standings') or []:
            if r.get('wiki'): wk.setdefault(norm(r['name']),r['wiki'])
def key(r): return r.get('wiki') or wk.get(norm(r['name'])) or norm(r['name'])
def by(s,ft=False):
    P={}
    for y,d in S[s].items():
        n=len([x for x in d.get('schedule') or [] if not x.get('cancelled')])
        for r in d.get('standings') or []:
            if ft and not (r.get('starts') and n and r['starts']>=0.7*n): continue
            if r.get('starts')==0: continue
            P.setdefault(key(r),[]).append(y)
    return P
def age(k,y):
    b=dr.get(k,{}).get('birth_date'); return y-int(b[:4]) if b else None
top={}
for s in ['irl_indycar','cart_champcar']:
    for k,v in by(s).items(): top.setdefault(k,[]).extend(v)
out={}
for a,b,y0,y1 in [('usf2000','pro_mazda',2010,2021),('pro_mazda','indy_lights',2007,2021),('indy_lights','top',1995,2021),('usf2000','top',2010,2019),('pro_mazda','top',2007,2019)]:
    A=by(a,ft=True); B=top if b=='top' else by(b)
    ages=[];gaps=[]
    for k,ys in A.items():
        y=min(ys)
        if y<y0 or y>y1: continue
        later=[x for x in B.get(k,[]) if x>y]
        if later:
            fy=min(later); g=age(k,fy)
            if g: ages.append(g)
            gaps.append(fy-y)
    ages.sort()
    out[a+'->'+b]={'n_movers':len(ages),'age_at_arrival_median':st.median(ages),'p10':ages[int(len(ages)*.1)],'p90':ages[int(len(ages)*.9)-1],'years_from_first_ft_season_median':st.median(gaps)}
print(json.dumps(out,indent=1)); json.dump(out,open(sys.argv[1],'w'),indent=1)
