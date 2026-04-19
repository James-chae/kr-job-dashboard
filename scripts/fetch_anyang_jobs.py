from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_FILE = DATA_DIR / "anyang_jobs.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

KEYWORDS_REGION = ["안양", "평촌", "범계", "호계", "관양", "비산", "군포", "의왕", "과천"]
JOB_HINTS = ["채용", "모집", "구인", "직원", "사무보조", "계약직", "아르바이트", "알바"]
EXCLUDE_TITLE = [
    "일자리", "채용정보", "검색", "로그인", "회원가입", "브랜드", "고객센터", "지역별",
    "공고 등록", "이력서", "검색 결과", "알바 찾기", "우리동네", "상품안내", "TOP", "스크랩"
]
EXCLUDE_URL = ["/jobs/area", "/search/", "job-search", "keyword=", "areas="]
EXCLUDE_ORG = {"스크랩", "믿고보는 대기업 스크랩", "탄탄한 중견기업 스크랩"}

SOURCE_URLS = [
    {
        "name": "사람인 안양",
        "url": "https://www.saramin.co.kr/zf_user/jobs/list/domestic?searchword=%EC%95%88%EC%96%91&loc_cd=101000,101020,101030",
        "source_type": "job-board",
    },
    {
        "name": "알바천국 안양",
        "url": "https://www.alba.co.kr/job/DetailList.asp?area=13110",
        "source_type": "job-board",
    },
    {
        "name": "잡코리아 안양",
        "url": "https://www.jobkorea.co.kr/Search/?stext=%EC%95%88%EC%96%91+%EA%B5%B0%ED%8F%AC+%EC%9D%98%EC%99%95+%EA%B3%BC%EC%B2%9C",
        "source_type": "job-board",
    },
]


@dataclass
class Job:
    id: str
    title: str
    organization: str
    category: str = "short"
    track: str = "short"
    region: str = "안양"
    employmentType: str = "단기/알바"
    postedAt: str = ""
    deadline: str = ""
    source: str = ""
    sourceType: str = "job-board"
    url: str = ""
    description: str = ""


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def looks_like_noise(title: str, url: str, organization: str = "") -> bool:
    title = clean_text(title)
    if not title:
        return True
    if organization in EXCLUDE_ORG:
        return True
    if any(word in title for word in EXCLUDE_TITLE):
        return True
    if any(fragment in (url or "") for fragment in EXCLUDE_URL):
        return True
    return False


def contains_living_area(text: str) -> bool:
    blob = text or ""
    return any(k in blob for k in KEYWORDS_REGION)


def looks_like_job(text: str) -> bool:
    return any(k in (text or "") for k in JOB_HINTS)


def infer_region(text: str) -> str:
    blob = text or ""
    for region in ["안양", "군포", "의왕", "과천"]:
        if region in blob:
            return region
    return "안양"


def infer_employment(text: str) -> str:
    joined = text or ""
    if any(k in joined for k in ["정규직", "정규"]):
        return "정규직"
    if any(k in joined for k in ["계약직", "기간제"]):
        return "계약/기간제"
    if any(k in joined for k in ["알바", "아르바이트"]):
        return "알바"
    return "단기/알바"


def date_guess(text: str) -> tuple[str, str]:
    normalized = (text or "").replace("년", ".").replace("월", ".").replace("일", "")
    found = re.findall(r"(20\d{2})[./-]\s*(\d{1,2})[./-]\s*(\d{1,2})", normalized)
    values = []
    for y, m, d in found[:2]:
        try:
            values.append(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")
        except Exception:
            pass
    if len(values) >= 2:
        return values[0], values[1]
    if len(values) == 1:
        return values[0], ""
    return "", ""


def stable_id(*parts: str) -> str:
    base = "|".join(clean_text(p) for p in parts if p)
    return f"anyang-{abs(hash(base))}"


def extract_candidates(html: str, base_url: str, source_name: str) -> Iterable[Job]:
    soup = BeautifulSoup(html, "html.parser")

    for a in soup.select("a[href]"):
        href = a.get("href", "")
        title = clean_text(a.get_text(" ", strip=True))
        url = urljoin(base_url, href)
        parent = a.find_parent(["li", "tr", "div", "article"])
        block_text = clean_text(parent.get_text(" ", strip=True)) if parent else title

        org = source_name
        if parent:
            lines = [clean_text(x.get_text(" ", strip=True)) for x in parent.find_all(["strong", "span", "div"], limit=5)]
            lines = [x for x in lines if x and x != title and x not in EXCLUDE_ORG]
            if lines:
                org = lines[0]

        if looks_like_noise(title, href, org):
            continue
        if not contains_living_area(" ".join([title, block_text, url])):
            continue
        if not looks_like_job(" ".join([title, block_text])):
            continue

        desc = block_text.replace(title, "").strip() or block_text
        posted_at, deadline = date_guess(desc)

        yield Job(
            id=stable_id(title, org, url),
            title=title[:120],
            organization=org[:80],
            region=infer_region(" ".join([title, block_text, url])),
            employmentType=infer_employment(desc),
            postedAt=posted_at,
            deadline=deadline,
            source=source_name,
            sourceType="job-board",
            url=url,
            description=clean_text(desc)[:220],
        )


def dedupe_jobs(jobs: Iterable[Job]) -> list[Job]:
    out: list[Job] = []
    seen: set[tuple[str, str, str]] = set()
    for job in jobs:
        key = (clean_text(job.title), clean_text(job.organization), clean_text(job.url))
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = make_session()

    errors: list[str] = []
    jobs: list[Job] = []

    for item in SOURCE_URLS:
        try:
            resp = session.get(item["url"], timeout=20)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or resp.encoding
            jobs.extend(list(extract_candidates(resp.text, item["url"], item["name"])))
        except Exception as exc:
            errors.append(f'{item["url"]}: {exc}')

    jobs = dedupe_jobs(jobs)

    payload = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "source": "anyang-living-area-v3",
            "count": len(jobs),
            "listUrls": [x["url"] for x in SOURCE_URLS],
            "errors": errors,
            "rawCount": len(jobs),
            "keptCount": len(jobs),
            "notes": [
                "living-area focused",
                "job-board noise cleanup",
                "duplicate scrap cards removed",
            ],
        },
        "jobs": [asdict(j) for j in jobs],
    }

    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] anyang_jobs.json saved ({len(jobs)} jobs)")
    if errors:
        print("[WARN] partial errors detected:")
        for err in errors:
            print(f" - {err}")


if __name__ == "__main__":
    main()
