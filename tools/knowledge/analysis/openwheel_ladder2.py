import json,glob,re,unicodedata,statistics as st,sys
import os; H=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'history') + os.sep
def norm(n): return re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',n).encode('ascii','ignore').decode().lower())
wk={}
S={}
for s in ['usf2000','pro_mazda','indy_lights','irl_indycar','cart_champcar']:
    S[s]={}
    for f in sorted(glob.glob(H+s+'/*.json')):
        d=json.load(open(f)); S[s][d['year']]=d
        for r in d.get('standings') or []:
            if r.get('wiki'): wk.setdefault(norm(r['name']),r['wiki'])
def key(r):
    w=r.get('wiki') or wk.get(norm(r['name'])); return w or norm(r['name'])
out={}
# seasons per driver in each series (full data years only, among drivers with >=1 full-time season), window ending 2022
for s,(y0,y1) in {'usf2000':(2010,2022),'pro_mazda':(2007,2022),'indy_lights':(2002,2022)}.items():
    yrs={}
    for y in range(y0,y1+1):
        d=S[s].get(y)
        if not d or d.get('data_level')!='full': continue
        n=len([x for x in d['schedule'] if not x.get('cancelled')])
        for r in d['standings']:
            if r.get('starts') and r['starts']>=0.5*n: yrs.setdefault(key(r),set()).add(y)
    c=[len(v) for v in yrs.values()]
    out[s+'_seasons_per_driver']={'n':len(c),'median':st.median(c),'share_1':round(sum(1 for x in c if x==1)/len(c),3),'share_2':round(sum(1 for x in c if x==2)/len(c),3),'share_3plus':round(sum(1 for x in c if x>=3)/len(c),3)}
# IndyCar career length (seasons with >=10 starts) for drivers debuting 2008-2016
first={};ft={}
for s in ['irl_indycar','cart_champcar']:
    for y,d in S[s].items():
        for r in d['standings']:
            k=key(r); first[k]=min(first.get(k,9999),y)
            if (r.get('starts') or 0)>=10: ft.setdefault(k,set()).add(y)
coh=[k for k,y in first.items() if 2008<=y<=2016]
c=[len(ft.get(k,())) for k in coh]
out['indycar_fulltime_seasons_debut_2008_2016']={'n':len(c),'median':st.median(c),'share_0':round(sum(1 for x in c if x==0)/len(c),3),'share_1_3':round(sum(1 for x in c if 1<=x<=3)/len(c),3),'share_4_9':round(sum(1 for x in c if 4<=x<=9)/len(c),3),'share_10plus':round(sum(1 for x in c if x>=10)/len(c),3)}
# Indy 500-only / one-off share: debutants with max starts in a season <=2
json.dump(out,open(sys.argv[1],'w'),indent=1); print(json.dumps(out,indent=1))
