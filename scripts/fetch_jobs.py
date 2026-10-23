def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'NightShiftIT/3.0 (personal job discovery)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=35) as response:
        return json.load(response)

def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))

def add(company, title, url, location, description, posted, source, direct=False, employment=''):
    company, title, url, location = (str(v or '').strip() for v in (company, title, url, location))
    description = plain(description)
    if not company or not title or not url.startswith('https://'):
        return
    if not ROLE.search(title) or EXCLUDE_ROLE.search(title):
        return
    hostname = (urlparse(url).hostname or '').lower()
    if hostname in ('bit.ly', 'tinyurl.com', 't.me', 'wa.me', ''):
        return
    allowed = {
        'Remotive': ('remotive.com',),
        'Arbeitnow': ('arbeitnow.com',),
        'Greenhouse': ('greenhouse.io', 'greenhouse.com'),
        'Lever': ('lever.co',),
    }
    if not any(hostname == domain or hostname.endswith('.' + domain) for domain in allowed[source]):
        return
    if NOT_REMOTE.search(location):
        return
    # Location must indicate remote; descriptions can establish remote status when location is broad.
    if not (REMOTE.search(location) or REMOTE.search(description[:5000])):
        return
    if EXCLUDED_LOCATION.search(location):
        return
    # A location such as 'London, UK' is not evidence of US remote eligibility.
    # Allow remote + city/state labels for employer-direct listings, flagged for verification.
    if location and not US_LOCATION.search(location) and not direct and source != 'Arbeitnow':
        return
    if url in seen:
        return
    seen.add(url)
    schedule_text = ' '.join((title, description[:12000], str(employment)))
    schedule = [name for name, pattern in SHIFT.items() if pattern.search(schedule_text)]
    clearance = 'Mentioned' if CLEARANCE.search(schedule_text) else 'Not mentioned'
    schedule_label = ', '.join(schedule) if schedule else 'Schedule unconfirmed'
    source_label = ('Employer-direct · ' if direct else 'Trusted feed · ') + source
    notes = ('Employer career-board listing.' if direct else 'Third-party feed; confirm on employer career page.')
    notes += ' Verify schedule, U.S. state eligibility, employer legitimacy, and whether the opening is still active.'
    if clearance == 'Mentioned':
        notes += ' Clearance mentioned; check level and requirements.'
    items.append({
        'id': source + ':' + url, 'company': company, 'title': title, 'url': url,
        'location': location or 'Remote (eligibility unconfirmed)',
        'posted': str(posted or ''), 'source': source_label,
        'shift': schedule_label, 'hours': str(employment or ''),
        'evidence': schedule_label, 'clearance': clearance,
        'notes': notes, 'status': 'Saved',
    })

def remotive():
    rows = get('https://remotive.com/api/remote-jobs').get('jobs', [])
    print('Remotive listings received:', len(rows), flush=True)
    for x in rows:
        add(x.get('company_name'), x.get('title'), x.get('url'),
            x.get('candidate_required_location'), x.get('description'),
            x.get('publication_date'), 'Remotive', employment=x.get('job_type'))

def arbeitnow():
    rows = get('https://www.arbeitnow.com/api/job-board-api').get('data', [])
    print('Arbeitnow listings received:', len(rows), flush=True)
    for x in rows:
        if x.get('remote'):
            add(x.get('company_name'), x.get('title'), x.get('url'),
                'Remote', x.get('description'), x.get('created_at'), 'Arbeitnow')

def greenhouse(company, token):
    rows = get('https://boards-api.greenhouse.io/v1/boards/' + token + '/jobs?content=true').get('jobs', [])
    print('Greenhouse', company, 'listings received:', len(rows), flush=True)
    for x in rows:
        if x.get('internal_job_id', 1) is None:
            continue
        add(company, x.get('title'), x.get('absolute_url'),
            (x.get('location') or {}).get('name'), x.get('content'),
            x.get('updated_at'), 'Greenhouse', direct=True)

def lever(company, token):
    rows = get('https://api.lever.co/v0/postings/' + token + '?mode=json&limit=100')
    print('Lever', company, 'listings received:', len(rows), flush=True)
    for x in rows:
        description = ' '.join(str(v or '') for v in [
            x.get('descriptionPlain'), x.get('additionalPlain'),
            ' '.join(str(i.get('content', '')) for i in x.get('lists', [])),
        ])
        location = (x.get('categories') or {}).get('location', '')
        add(company, x.get('text'), x.get('hostedUrl'), location,
            description, x.get('createdAt'), 'Lever', direct=True,
            employment=(x.get('categories') or {}).get('commitment', ''))

def run(label, fn):
    before = len(items)
    try:
        fn()
        print(label, 'accepted:', len(items) - before, flush=True)
    except Exception as exc:
        print(label, 'ERROR:', type(exc).__name__, str(exc), flush=True)

if __name__ == '__main__':
    config = {'greenhouse': {}, 'lever': {}}
    if CONFIG.exists():
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
    run('Remotive', remotive)
    run('Arbeitnow', arbeitnow)
    for company, token in config.get('greenhouse', {}).items():
        if re.fullmatch(r'[a-zA-Z0-9_-]+', str(token)):
            run('Greenhouse ' + company, lambda c=company, t=token: greenhouse(c, t))
    for company, token in config.get('lever', {}).items():
        if re.fullmatch(r'[a-zA-Z0-9_-]+', str(token)):
            run('Lever ' + company, lambda c=company, t=token: lever(c, t))
    print('New matching jobs:', len(items), flush=True)
    if items:
        output = {
            'updated_at': NOW.isoformat(),
            'jobs': sorted(items, key=lambda x: str(x['posted']), reverse=True),
            'disclaimer': 'Candidate matches only; schedules, clearance, and US eligibility are not independently confirmed.',
        }
        OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
