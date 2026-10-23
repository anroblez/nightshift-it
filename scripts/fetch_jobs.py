import json, re, urllib.request, datetime, pathlib, html
ROOT=pathlib.Path(__file__).resolve().parents[1]
NOW=datetime.datetime.now(datetime.timezone.utc)
terms=re.compile(r'help.?desk|service desk|technical support|it support|noc|network operations|soc analyst|desktop support|application support|support analyst',re.I)
shifts=re.compile(r'overnight|night shift|graveyard|third shift|3rd shift|after.hours|late shift|evening|weekend|24/7|24x7|24.hour',re.I)
remote=re.compile(r'\bremote\b|work from home|work-from-home|distributed',re.I)
items=[]
def get(url):
 req=urllib.request.Request(url,headers={'User-Agent':'NightShiftIT/1.0 (personal job discovery)'})
 with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
def add(company,title,url,location,description,date,source):
 plain=html.unescape(re.sub('<[^>]+>',' ',description or ''))
 blob=' '.join([title,plain[:12000]])
 if not terms.search(title):return
 if not remote.search(location+' '+plain[:2500]):return
 if not shifts.search(blob):return
 mentions=sorted(set(m.group(0).lower() for m in shifts.finditer(blob)))
 items.append(dict(id=source+':'+url,company=company,title=title,url=url,location=location,posted=date,source=source,shift='Possible night/evening/weekend',evidence=', '.join(mentions[:6]),notes='Automated keyword match. Verify schedule, employer, remote state eligibility and availability on the official listing.'))
try:
 data=get('https://remotive.com/api/remote-jobs?category=customer-support&limit=300')
 for x in data.get('jobs',[]):add(x.get('company_name',''),x.get('title',''),x.get('url',''),x.get('candidate_required_location','Remote'),x.get('description',''),x.get('publication_date',''),'Remotive')
except Exception as e:print('Remotive:',e)
try:
 data=get('https://www.arbeitnow.com/api/job-board-api')
 for x in data.get('data',[]):
  if x.get('remote'):add(x.get('company_name',''),x.get('title',''),x.get('url',''),'Remote',x.get('description',''),str(x.get('created_at','')),'Arbeitnow')
except Exception as e:print('Arbeitnow:',e)
seen=set();dedup=[]
for x in items:
 if x['url'] not in seen:seen.add(x['url']);dedup.append(x)
out={'updated_at':NOW.isoformat(),'jobs':dedup,'disclaimer':'Candidate matches only; shifts and state eligibility are not independently confirmed.'}
(ROOT/'jobs.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
print('Wrote',len(dedup),'potential jobs')
