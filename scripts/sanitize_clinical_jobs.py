import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PATH = DATA_DIR / "clinical_jobs.json"

SPACE_RE = re.compile(r"\s+")
KEYWORDS = ["임상병리", "임상병리사", "진단검사", "진단검사의학", "검체", "병리사", "의료기사"]

# Keep only Seoul/Gyeonggi living area
POSITIVE_REGION_HINTS = [
    "서울", "경기", "서울/경기",
    "강북구", "금천구", "성북", "의정부", "파주", "화성", "오산", "성남",
    "수원", "안양", "의왕", "군포", "과천", "광명", "안산", "용인", "고양",
    "부천", "하남", "남양주", "평택", "구리", "김포", "시흥"
]

# Explicitly exclude these regions even if the current region field is sloppy
NEGATIVE_REGION_HINTS = [
    "대전", "대구", "경남", "경북", "칠곡", "창원", "세종", "인천", "청라",
    "부산", "광주", "울산", "전북", "전남", "충남", "충북", "제주", "강원"
]

def clean(s: str) -> str:
    return SPACE_RE.sub(" ", (s or "")).strip()

def has_keyword(blob: str) -> bool:
    return any(k in blob for k in KEYWORDS)

def has_positive_region(blob: str) -> bool:
    return any(k in blob for k in POSITIVE_REGION_HINTS)

def has_negative_region(blob: str) -> bool:
    return any(k in blob for k in NEGATIVE_REGION_HINTS)

def normalize_region(blob: str) -> str:
    if "서울" in blob and ("경기" in blob or any(k in blob for k in ["의정부","파주","화성","오산","성남","수원","안양","의왕","군포","과천","광명","안산","용인","고양","부천","하남","남양주","평택","구리","김포","시흥"])):
        return "서울/경기"
    if "서울" in blob or any(k in blob for k in ["강북구", "금천구", "성북"]):
        return "서울"
    return "경기"

def keep(job: dict) -> bool:
    title = clean(job.get("title", ""))
    desc = clean(job.get("description", ""))
    org = clean(job.get("organization", ""))
    region = clean(job.get("region", ""))
    blob = f"{title} {desc} {org} {region}"

    if not has_keyword(blob):
        return False

    # Strong negative filter first
    if has_negative_region(blob):
        return False

    # Keep only when Seoul/Gyeonggi hints are actually present
    if not has_positive_region(blob):
        return False

    return True

def main():
    if not PATH.exists():
        print("[WARN] clinical_jobs.json not found")
        return

    payload = json.loads(PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    raw = len(jobs)

    kept = []
    seen = set()
    for job in jobs:
        if not keep(job):
            continue

        title = clean(job.get("title", ""))
        desc = clean(job.get("description", ""))
        org = clean(job.get("organization", ""))
        blob = f"{title} {desc} {org}"

        job["title"] = title[:120]
        job["description"] = desc[:140]
        job["organization"] = org[:60]
        job["region"] = normalize_region(blob)

        key = (job.get("title", ""), job.get("organization", ""), job.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(job)

    payload["jobs"] = kept
    meta = payload.setdefault("meta", {})
    meta["rawCount"] = raw
    meta["keptCount"] = len(kept)
    meta["source"] = "clinical"
    notes = meta.get("notes", [])
    if not isinstance(notes, list):
        notes = [str(notes)]
    notes.append("phase18: strict Seoul/Gyeonggi-only clinical filtering")
    meta["notes"] = notes[-5:]

    PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] clinical_jobs.json: raw={raw} kept={len(kept)}")

if __name__ == "__main__":
    main()
