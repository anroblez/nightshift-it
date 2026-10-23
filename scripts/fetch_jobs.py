import json
import re
import urllib.request
import urllib.parse
import urllib.error
import datetime
import pathlib
import html
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = datetime.datetime.now(datetime.timezone.utc)

ROLE = re.compile(r'help[ -]?desk|service[ -]?desk|technical support|it support|support (engineer|specialist|analyst|technician)|desktop support|application support|noc|network operations|soc|security operations|cybersecurity|cloud (support|engineer|administrator|operations)|systems? administrator|network support', re.I)
REMOTE = re.compile(r'\bremote\b|work[ -]from[ -]home|distributed|telecommut', re.I)
NIGHT = re.compile(r'overnight|night[ -]shift|graveyard|third shift|3rd shift|after[ -]hours|late shift|24[ /x×-]?7|24[ -]?hour', re.I)
EVENING = re.compile(r'evening|second shift|2nd shift|weekends?|saturday|sunday', re.I)
FLEX = re.compile(r'flexible (hours|schedule|working)|flex[ -]?time|asynchronous|async[ -]?first|set your own hours', re.I)
PART = re.compile(r'part[ -]?time|less than 30 hours|20 hours per week', re.I)

jobs = []

def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'NightShiftIT/1.1 (personal job discovery)', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def add(company, title, url, location, description, date, source, remote_flag=False):
    if not url or not title or not ROLE.search(title):
        return
    plain = html.unescape(re.sub(r'<[^>]*>', ' ', description or ''))
    location = location or ''
    if not (remote_flag or REMOTE.search(location + ' ' + plain[:6000])):
        return
    blob = title + ' ' + plain[:12000]
    categories = []
    if NIGHT.search(blob): categories.append('overnight')
    if EVENING.search(blob): categories.append('evening')
    if FLEX.search(blob): categories.append('flexible')
    if PART.search(blob): categories.append('parttime')
    shift = 'Possible night/evening' if 'overnight' in categories or 'evening' in categories else 'Schedule unverified'
    if 'flexible' in categories and shift == 'Schedule unverified': shift = 'Possible flexible schedule'
    if 'parttime' in categories and shift == 'Schedule unverified': shift = 'Possible part-time'
    evidence = ', '.join(categories) if categories else 'Remote IT role; schedule not confirmed'
    jobs.append(dict(id=source + ':' + url, company=company or 'Unknown employer', title=title, url=url, location=location or 'Remote (eligibility unverified)', posted=str(date or ''), source=source, shift=shift, evidence=evidence, notes='Verify the actual schedule, US work eligibility, state restrictions, and whether the listing is still open.'))

sources = [
    ('Remotive', 'https://remotive.com/api/remote-jobs?limit=1000'),
    ('Arbeitnow', 'https://www.arbeitnow.com/api/job-board-api'),
]

for name, url in sources:
    try:
        data = get(url)
        if name == 'Remotive':
            records = data.get('jobs', [])
            print('Remotive returned', len(records), 'records')
            for x in records:
                add(x.get('company_name'), x.get('title'), x.get('url'), x.get('candidate_required_location', 'Remote'), x.get('description'), x.get('publication_date'), name, remote_flag=True)
        else:
            records = data.get('data', [])
            print('Arbeitnow returned', len(records), 'records')
            for x in records:
                if x.get('remote'):
                    add(x.get('company_name'), x.get('title'), x.get('url'), 'Remote', x.get('description'), x.get('created_at'), name, remote_flag=True)
    except Exception as exc:
        print(name, 'fetch failed:', repr(exc))

seen = set()
unique = []
for item in jobs:
    key = item['url'].rstrip('/').lower()
    if key not in seen:
        seen.add(key)
        unique.append(item)

output = {'updated_at': NOW.isoformat(), 'jobs': unique, 'disclaimer': 'Candidate matches only; remote eligibility and schedule are not independently confirmed.'}
(ROOT / 'jobs.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print('Wrote', len(unique), 'potential remote IT jobs')
