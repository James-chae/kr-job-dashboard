from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parents[1] / 'data'
OUTPUT_PATH = DATA_DIR / 'cabin_jobs.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7,zh-CN;q=0.6,zh;q=0.5,ja;q=0.4',
}

DATE_RE = re.compile(r'(20\d{2})[./-](\d{1,2})[./-](\d{1,2})')
NOISE_PATTERNS = [
    r'Please enable JavaScript.*',
    r'We\'re sorry but .*?doesn\'t work properly without JavaScript enabled\.?',
    r'a:link, a:visited \{.*',
    r'body\s*\{.*',
]

KOREAN_SOURCES = [
    {
        'name': '대한항공',
        'url': 'https://koreanair.recruiter.co.kr/career/jobs/99647',
        'region': '서울',
        'title_hint': '객실승무원',
        'clean_title': '대한항공 객실승무원 채용',
    },
    {
        'name': '아시아나항공',
        'url': 'https://flyasiana.recruiter.co.kr/career/jobs/88541',
        'region': '서울',
        'title_hint': '객실승무원',
        'clean_title': '아시아나항공 객실승무원 채용',
    },
    {
        'name': '제주항공',
        'url': 'https://jejuair.recruiter.co.kr/career/jobs/103719',
        'region': '서울',
        'title_hint': '객실승무원',
        'clean_title': '제주항공 객실승무원 채용',
    },
    {
        'name': '진에어',
        'url': 'https://jinair.recruiter.co.kr/app/jobnotice/view?jobnoticeSn=236027&systemKindCode=MRS2',
        'region': '서울',
        'title_hint': '객실승무원',
        'clean_title': '진에어 객실승무원 채용',
    },
    {
        'name': '티웨이항공',
        'url': 'https://twayair.recruiter.co.kr/career/jobs/82723',
        'region': '부산',
        'title_hint': '객실승무원',
        'clean_title': '티웨이항공 객실승무원 채용',
    },
]

CATHAY_LIST_URL = 'https://careers.cathaypacific.com/en/careers/jobs'
CATHAY_ALLOWED_LOCS = {'Japan', 'Chinese Mainland', 'Hong Kong SAR (China)', 'Singapore', 'Taiwan', 'Hong Kong'}

CHINA_SOURCES = [
    {
        'name': '중국동방항공',
        'url': 'https://job.ceair.com/',
        'region': '중국',
        'title_hint': '乘务、安全员招聘',
        'clean_title': '중국동방항공 승무원 채용',
    },
    {
        'name': '중국남방항공',
        'url': 'https://job.csair.com/',
        'region': '중국',
        'title_hint': '乘务招聘',
        'clean_title': '중국남방항공 승무원 채용',
    },
]


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def normalize_space(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def decode_response_text(resp: requests.Response) -> str:
    # Prefer declared encoding when trustworthy; otherwise use apparent_encoding.
    for enc in [resp.encoding, getattr(resp, 'apparent_encoding', None), 'utf-8', 'gb18030', 'gbk', 'big5']:
        if not enc:
            continue
        try:
            return resp.content.decode(enc, errors='replace')
        except Exception:
            continue
    return resp.text


def clean_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    text = soup.get_text(' ', strip=True)
    text = normalize_space(text)
    for pat in NOISE_PATTERNS:
        text = re.sub(pat, '', text, flags=re.I | re.S)
    return normalize_space(text)


def parse_date(text: str) -> str:
    if not text:
        return ''
    m = DATE_RE.search(text)
    if not m:
        return ''
    y, mo, d = m.groups()
    try:
        return f'{int(y):04d}-{int(mo):02d}-{int(d):02d}'
    except Exception:
        return ''


def make_job_id(source: str, title: str, url: str) -> str:
    return f"cabin-{abs(hash((source, title, url)))}"


def infer_date_span(text: str) -> tuple[str, str]:
    matches = DATE_RE.findall(text)
    if not matches:
        return '', ''
    if len(matches) == 1:
        y, m, d = matches[0]
        return f'{int(y):04d}-{int(m):02d}-{int(d):02d}', ''
    a, b = matches[0], matches[1]
    return (
        f'{int(a[0]):04d}-{int(a[1]):02d}-{int(a[2]):02d}',
        f'{int(b[0]):04d}-{int(b[1]):02d}-{int(b[2]):02d}',
    )


def generic_recruiter_job(sess: requests.Session, name: str, url: str, region: str, title_hint: str, clean_title: str) -> tuple[dict | None, str | None]:
    try:
        r = sess.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return None, f'{url}: {e}'

    html = decode_response_text(r)
    visible_text = clean_visible_text(html)

    # If the page is JS-only or still too noisy, fall back to clean known title.
    js_only = 'enable javascript' in visible_text.lower() or len(visible_text) < 20

    title = ''
    og = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if og:
        title = normalize_space(og.group(1))
    if not title:
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I | re.S)
        if h1:
            title = normalize_space(clean_visible_text(h1.group(1)))
    if not title:
        t = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
        if t:
            title = normalize_space(clean_visible_text(t.group(1)))

    # Reject mojibake / CSS-looking titles.
    if not title or re.search(r'[ÃÄÅÆÉÈÖØÐ][^ ]|a:link|a:visited|cursor:|text-decoration', title):
        title = clean_title

    posted, deadline = infer_date_span(visible_text)
    description = ''
    if not js_only:
        description = visible_text[:220]
        if re.search(r'cursor:|a:visited|a:link|text-decoration', description, re.I):
            description = ''
    return {
        'id': make_job_id(name, title, url),
        'title': title,
        'organization': name,
        'category': 'cabin',
        'track': 'cabin',
        'region': region,
        'employmentType': '승무원',
        'postedAt': posted,
        'deadline': deadline,
        'status': 'unknown',
        'source': f'{name} 채용',
        'sourceType': 'airline-career-site',
        'url': url,
        'description': description,
    }, None


def parse_cathay_jobs(sess: requests.Session) -> tuple[list[dict], list[str]]:
    jobs: list[dict] = []
    errors: list[str] = []
    try:
        r = sess.get(CATHAY_LIST_URL, timeout=20)
        r.raise_for_status()
    except Exception as e:
        return jobs, [f'{CATHAY_LIST_URL}: {e}']

    text = decode_response_text(r)
    links = list(dict.fromkeys(re.findall(r'/en/careers/jobs/[^"\'\s<>]+', text)))
    detail_urls = [f'https://careers.cathaypacific.com{p}' for p in links]
    for url in detail_urls:
        if len(jobs) >= 8:
            break
        if 'flight-attendant' not in url.lower():
            continue
        try:
            rr = sess.get(url, timeout=20)
            rr.raise_for_status()
        except Exception as e:
            errors.append(f'{url}: {e}')
            continue
        page = decode_response_text(rr)
        page_text = clean_visible_text(page)
        if 'Flight Attendant' not in page_text:
            continue
        title = ''
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', page, re.I | re.S)
        if h1:
            title = normalize_space(clean_visible_text(h1.group(1)))
        if not title:
            title = 'Cathay Pacific Flight Attendant'
        loc = ''
        loc_m = re.search(r'Flight Attendant\s+([A-Za-z()\- ,]+?)\s+(Contract|Permanent|Role Introduction)', page_text)
        if loc_m:
            loc = normalize_space(loc_m.group(1))
        if not loc:
            for cand in ['Chinese Mainland', 'Japan', 'Hong Kong SAR (China)', 'Singapore', 'Taipei']:
                if cand in page_text:
                    loc = cand
                    break
        if loc and not any(key in loc for key in CATHAY_ALLOWED_LOCS):
            continue
        deadline = ''
        dm = re.search(r'Application deadline:\s*([A-Za-z]{3,9}\s+\d{1,2}\s+20\d{2})', page_text)
        if dm:
            for fmt in ('%d %b %Y', '%B %d %Y'):
                try:
                    deadline = datetime.strptime(dm.group(1), fmt).strftime('%Y-%m-%d')
                    break
                except Exception:
                    pass
        region = '일본' if 'Japan' in loc else ('중국' if 'Chinese Mainland' in loc else '해외')
        jobs.append({
            'id': make_job_id('Cathay Pacific', title, url),
            'title': title,
            'organization': 'Cathay Pacific',
            'category': 'cabin',
            'track': 'cabin',
            'region': region,
            'employmentType': '승무원',
            'postedAt': '',
            'deadline': deadline,
            'status': 'unknown',
            'source': 'Cathay Pacific Careers',
            'sourceType': 'airline-career-site',
            'url': url,
            'description': page_text[:220],
        })
    return jobs, errors


def dedupe(jobs: Iterable[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for j in jobs:
        key = (j.get('title', ''), j.get('url', ''))
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out


def save_payload(jobs: list[dict], errors: list[str]) -> None:
    payload = {
        'meta': {
            'generatedAt': datetime.now().isoformat(),
            'source': 'cabin',
            'count': len(jobs),
            'errors': errors,
            'notes': 'Foreign airline encoding cleanup applied for China/HK sources.',
        },
        'jobs': jobs,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'[OK] cabin_jobs.json saved ({len(jobs)} jobs)')
    if errors:
        print('[WARN] partial errors detected:')
        for e in errors[:10]:
            print(' -', e)


def main() -> None:
    sess = session()
    jobs: list[dict] = []
    errors: list[str] = []

    for src in KOREAN_SOURCES:
        job, err = generic_recruiter_job(sess, **src)
        if job:
            jobs.append(job)
        if err:
            errors.append(err)

    cathay_jobs, cathay_errors = parse_cathay_jobs(sess)
    jobs.extend(cathay_jobs)
    errors.extend(cathay_errors)

    for src in CHINA_SOURCES:
        job, err = generic_recruiter_job(sess, **src)
        if job:
            jobs.append(job)
        if err:
            errors.append(err)

    jobs = dedupe(jobs)
    save_payload(jobs, errors)


if __name__ == '__main__':
    main()
