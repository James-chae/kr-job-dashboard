import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
TARGET_FILES = [
    DATA_DIR / "short_jobs.json",
    DATA_DIR / "anyang_jobs.json",
]

NOISE_PATTERNS = [
    r"\b\d+\s*건의\s*일자리\b",
    r"로그인",
    r"회원가입",
    r"고객센터",
    r"지역별",
    r"검색",
    r"브랜드\s*알바",
    r"공고\s*등록",
    r"이력서\s*등록",
    r"채용정보",
    r"TOP[- ]?Logo",
    r"알바토크",
    r"우리동네",
    r"메뉴버튼",
    r"유사동",
    r"초기화",
    r"상세조건",
]

AREA_HINTS = [
    "안양", "평촌", "범계", "호계", "관양", "비산",
    "의왕", "군포", "과천", "수원", "안산", "광명",
]

HTML_TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.I)

def clean_text(text: str) -> str:
    text = text or ""
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\u200b", " ").replace("\ufeff", " ")
    text = SPACE_RE.sub(" ", text).strip()
    return text

def has_area_hint(*parts: str) -> bool:
    blob = " ".join([p for p in parts if p])
    return any(h in blob for h in AREA_HINTS)

def looks_like_noise(title: str, desc: str, url: str) -> bool:
    blob = " ".join([title or "", desc or "", url or ""])
    if NOISE_RE.search(blob):
        return True
    # pure search/list pages
    lowered = blob.lower()
    if "albamon.com/jobs/area" in lowered:
        return True
    if "search" in lowered and "job" in lowered and len(title or "") < 10:
        return True
    return False

def summarize(desc: str) -> str:
    desc = clean_text(desc)
    if NOISE_RE.search(desc):
        desc = NOISE_RE.sub(" ", desc)
        desc = SPACE_RE.sub(" ", desc).strip()
    return desc[:120]

def sanitize_job(job: dict) -> dict | None:
    title = clean_text(job.get("title", ""))
    org = clean_text(job.get("organization", ""))
    desc = clean_text(job.get("description", ""))
    url = clean_text(job.get("url", ""))
    region = clean_text(job.get("region", ""))

    if not title:
        return None

    if looks_like_noise(title, desc, url):
        return None

    # Prefer 생활권 지역 short jobs only
    if (job.get("track") == "short" or job.get("category") == "short" or region in AREA_HINTS) and not has_area_hint(title, org, desc, region, url):
        # allow if region already explicitly one of target places
        if region not in AREA_HINTS:
            return None

    out = dict(job)
    out["title"] = title[:80]
    out["organization"] = org[:60]
    out["description"] = summarize(desc)
    return out

def process_file(path: Path):
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data.get("jobs", [])
    raw = len(jobs)
    kept_jobs = []
    seen = set()
    for job in jobs:
        cleaned = sanitize_job(job)
        if not cleaned:
            continue
        key = (
            cleaned.get("title",""),
            cleaned.get("organization",""),
            cleaned.get("url",""),
        )
        if key in seen:
            continue
        seen.add(key)
        kept_jobs.append(cleaned)

    data["jobs"] = kept_jobs
    meta = data.setdefault("meta", {})
    meta["rawCount"] = raw
    meta["keptCount"] = len(kept_jobs)
    notes = meta.get("notes", [])
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes.append("phase13: short/alba noise cleanup and compact summaries")
    meta["notes"] = notes[-5:]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path.name, raw, len(kept_jobs)

def main():
    results = []
    for p in TARGET_FILES:
        res = process_file(p)
        if res:
            results.append(res)
    if not results:
        print("[WARN] no short/alba data files found")
        return
    for name, raw, kept in results:
        print(f"[OK] {name}: raw={raw} kept={kept}")

if __name__ == "__main__":
    main()
