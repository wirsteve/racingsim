import json,glob,re,statistics as st,unicodedata,sys
import os; H=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'history') + os.sep
dr=json.load(open(H+'drivers_openwheel.json'))
def norm(n):
    n=unicodedata.normalize('NFKD',n).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z]','',n)
def key(r):
    w=r.get('wiki') or wiki_by_key.get(norm(r['name']))
    return ('w:'+w) if w else norm(r['name'])
wiki_by_key={}
def load(s):
    out={}
    for f in sorted(glob.glob(H+s+'/*.json')):
        d=json.load(open(f)); y=d['year']
        n_rounds=len([x for x in d.get('schedule') or [] if not x.get('cancelled')])
        out[y]={'level':d.get('data_level'),'rounds':n_rounds,'st':d.get('standings') or []}
        for r in out[y]['st']:
            if r.get('wiki'): wiki_by_key.setdefault(norm(r['name']),r['wiki'])
    return out
S={s:load(s) for s in ['usf2000','pro_mazda','indy_lights','irl_indycar','cart_champcar']}
def age(r,y):
    w=r.get('wiki') or wiki_by_key.get(norm(r['name']))
    b=dr.get(w,{}).get('birth_date') if w else None
    if not b: return None
    return y-int(b[:4])  # age during season (approx, season-year minus birth year)
# top-tier participation: key -> list of (year,starts)
top={}
for s in ['irl_indycar','cart_champcar']:
    for y,d in S[s].items():
        for r in d['st']:
            st_=r.get('starts')
            if st_ is None or st_>0:
                top.setdefault(key(r),[]).append((y,st_ or 1,s))
def top_after(k,y,min_starts=1):
    return [t for t in top.get(k,[]) if t[0]>y and t[1]>=min_starts]
def fulltime_top(k,y):
    # any later season with >=10 starts
    return [t for t in top.get(k,[]) if t[0]>y and t[1]>=10]
def seriesparticip(s):
    p={}
    for y,d in S[s].items():
        for r in d['st']:
            p.setdefault(key(r),[]).append(y)
    return p
P={s:seriesparticip(s) for s in S}
res={}
def cohort(s,y0,y1,label,ft_frac=0.7):
    champs=[];ft=[];all_=[]
    for y in range(y0,y1+1):
        d=S[s].get(y)
        if not d: continue
        for r in d['st']:
            k=key(r)
            rec={'name':r['name'],'year':y,'pos':r['pos'],'age':age(r,y),
                 'top_any':bool(top_after(k,y)),'top_ft':bool(fulltime_top(k,y)),
                 'first_top':min([t[0] for t in top_after(k,y)],default=None)}
            if r['pos']==1 and not any(c['year']==y for c in champs): champs.append(rec)
            if d['level']=='full' and r.get('starts') and d['rounds'] and r['starts']>=ft_frac*d['rounds']:
                ft.append(rec)
            all_.append(rec)
    def summ(L):
        L2={}
        for x in L: L2.setdefault(x['name'],x)  # first appearance per driver
        L=list(L2.values())
        n=len(L)
        if not n: return None
        ages=[x['age'] for x in L if x['age']]
        gaps=[x['first_top']-x['year'] for x in L if x['first_top']]
        return {'n_drivers':n,'share_any_top_start':round(sum(x['top_any'] for x in L)/n,3),
                'share_fulltime_top_season':round(sum(x['top_ft'] for x in L)/n,3),
                'age_median':st.median(ages) if ages else None,'age_p10_p90':[sorted(ages)[int(len(ages)*.1)],sorted(ages)[int(len(ages)*.9)-1]] if len(ages)>4 else None,
                'years_to_first_top_start_median':st.median(gaps) if gaps else None}
    res[label]={'series':s,'years':[y0,y1],'champions':summ(champs),'fulltimers':summ(ft),
                'champion_list':[(c['year'],c['name'],c['age'],c['top_any'],c['top_ft']) for c in champs]}
cohort('usf2000',1995,2019,'usf2000_1995_2019')
cohort('usf2000',2010,2019,'usf2000_2010_2019')
cohort('pro_mazda',1995,2019,'promazda_1995_2019')
cohort('pro_mazda',2007,2019,'promazda_2007_2019')
cohort('indy_lights',1995,2021,'indylights_1995_2021')
cohort('indy_lights',1995,2001,'indylights_cart_era_1995_2001')
cohort('indy_lights',2002,2021,'indylights_irl_era_2002_2021')
cohort('indy_lights',2010,2021,'indylights_2010_2021')
# ladder step transitions (full-timers who later appear in next series)
def step(a,b,y0,y1,ft_frac=0.7):
    L={}
    for y in range(y0,y1+1):
        d=S[a].get(y)
        if not d or d['level']!='full': continue
        for r in d['st']:
            if r.get('starts') and d['rounds'] and r['starts']>=ft_frac*d['rounds']:
                L.setdefault(key(r),(y,r))
    n=len(L); hit=0; ages=[]
    for k,(y,r) in L.items():
        later=[yy for yy in P[b].get(k,[]) if yy>=y]
        if later: hit+=1
    return {'from':a,'to':b,'years':[y0,y1],'n_fulltimers':n,'share_reaching_next':round(hit/n,3) if n else None}
res['step_usf2000_promazda']=step('usf2000','pro_mazda',2010,2021)
res['step_promazda_lights']=step('pro_mazda','indy_lights',2007,2021)
res['step_usf2000_lights']=step('usf2000','indy_lights',2010,2020)
# ages of fulltimers per series recent era
def ages(s,y0,y1):
    A=[]
    for y in range(y0,y1+1):
        d=S[s].get(y)
        if not d: continue
        for r in d['st']:
            if r.get('starts') and d['rounds'] and r['starts']>=0.7*d['rounds']:
                a=age(r,y)
                if a: A.append(a)
    A.sort()
    return {'n':len(A),'median':st.median(A),'p10':A[int(len(A)*.1)],'p90':A[int(len(A)*.9)-1]} if A else None
res['ages']={s:ages(s,2010,2026) for s in S if s!='cart_champcar'}
res['ages']['cart_champcar']=ages('cart_champcar',1995,2007)
# rookie ages in indycar 2008-2026 (first season appearance, with fulltime)
first={}
for s in ['irl_indycar','cart_champcar']:
    for y,d in S[s].items():
        for r in d['st']:
            k=key(r); 
            if k not in first or y<first[k][0]: first[k]=(y,r)
ra=[age(r,y) for k,(y,r) in first.items() if y>=2008 and age(r,y)]
ra.sort(); res['indycar_debut_age_2008_2026']={'n':len(ra),'median':st.median(ra),'p10':ra[int(len(ra)*.1)],'p90':ra[int(len(ra)*.9)-1]}
# share of IndyCar debutants 2010-2026 who raced in Indy Lights / Pro Mazda / USF2000 earlier (pipeline share)
deb=[(k,y) for k,(y,r) in first.items() if y>=2010]
def prior(s,k,y): return any(yy<=y for yy in P[s].get(k,[]))
res['indycar_debutants_2010_2026']={'n':len(deb),
  'share_with_indy_lights':round(sum(prior('indy_lights',k,y) for k,y in deb)/len(deb),3),
  'share_with_pro_mazda':round(sum(prior('pro_mazda',k,y) for k,y in deb)/len(deb),3),
  'share_with_usf2000':round(sum(prior('usf2000',k,y) for k,y in deb)/len(deb),3),
  'share_with_any_ladder':round(sum(prior('indy_lights',k,y) or prior('pro_mazda',k,y) or prior('usf2000',k,y) for k,y in deb)/len(deb),3)}
# full-time indycar drivers 2020-2026 who came through ladder
ftk={}
for y in range(2020,2027):
    d=S['irl_indycar'][y]
    for r in d['st']:
        if r.get('starts') and r['starts']>=0.7*d['rounds']: ftk.setdefault(key(r),r['name'])
res['indycar_fulltimers_2020_2026']={'n':len(ftk),
  'share_with_indy_lights':round(sum(bool(P['indy_lights'].get(k)) for k in ftk)/len(ftk),3),
  'share_with_any_ladder':round(sum(bool(P['indy_lights'].get(k) or P['pro_mazda'].get(k) or P['usf2000'].get(k)) for k in ftk)/len(ftk),3)}
# field sizes (avg standings rows and fulltimers) recent
def fs(s,y0,y1):
    out=[]
    for y in range(y0,y1+1):
        d=S[s].get(y)
        if not d or d['level']!='full': continue
        ft=sum(1 for r in d['st'] if r.get('starts') and d['rounds'] and r['starts']>=0.7*d['rounds'])
        out.append((y,len(d['st']),ft,d['rounds']))
    return out
res['field_sizes']={s:fs(s,2015,2026) for s in ['usf2000','pro_mazda','indy_lights','irl_indycar']}
json.dump(res,open(sys.argv[1],'w'),indent=1,default=str)
