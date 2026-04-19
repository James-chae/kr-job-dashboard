from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "public_jobs.json"

# 빠른 복구용 공공 통합 seed
# 목적: 공공 탭에서 의왕 외 안양/군포/과천이 반드시 노출되게 만들기
# 이후 필요하면 실제 파서 고도화 가능
SEEDED_PUBLIC_JOBS = [
    {
        "id": "public-anyang-1",
        "title": "안양시 공공기관·협력기관 채용 안내",
        "organization": "안양시",
        "category": "public",
        "track": "public",
        "region": "안양",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "안양시",
        "sourceType": "municipal",
        "url": "https://www.anyang.go.kr/main/selectBbsNttList.do?bbsNo=64&key=1771",
        "description": "안양시 공공기관·협력기관 채용 게시판 기준 공공 채용 안내"
    },
    {
        "id": "public-anyang-2",
        "title": "안양시 산하기관·협력기관 채용공고 확인",
        "organization": "안양시",
        "category": "public",
        "track": "public",
        "region": "안양",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "안양시",
        "sourceType": "municipal",
        "url": "https://www.anyang.go.kr/main/selectBbsNttList.do?bbsNo=64&key=1771",
        "description": "안양시청 공공기관·협력기관 채용 페이지 바로가기"
    },
    {
        "id": "public-gunpo-1",
        "title": "군포시 채용공고 확인",
        "organization": "군포시청",
        "category": "public",
        "track": "public",
        "region": "군포",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "군포시청",
        "sourceType": "municipal",
        "url": "https://www.gunpo.go.kr/www/selectBbsNttList.do?bbsNo=361&key=1255",
        "description": "군포시청 채용공고 게시판 기준 공공 채용 안내"
    },
    {
        "id": "public-gunpo-2",
        "title": "군포시 공공기관 채용 확인",
        "organization": "군포시청",
        "category": "public",
        "track": "public",
        "region": "군포",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "군포시청",
        "sourceType": "municipal",
        "url": "https://www.gunpo.go.kr/www/selectBbsNttList.do?bbsNo=361&key=1255",
        "description": "군포시청 공공 채용 페이지 바로가기"
    },
    {
        "id": "public-gwacheon-1",
        "title": "과천시 채용정보 확인",
        "organization": "과천시청",
        "category": "public",
        "track": "public",
        "region": "과천",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "과천시청",
        "sourceType": "municipal",
        "url": "https://www.gccity.go.kr/portal/jobOffer/list.do?mid=0301030000",
        "description": "과천시 채용정보 게시판 기준 공공 채용 안내"
    },
    {
        "id": "public-gwacheon-2",
        "title": "과천도시공사 채용공고 확인",
        "organization": "과천도시공사",
        "category": "public",
        "track": "public",
        "region": "과천",
        "employmentType": "공공/기관",
        "postedAt": "2026-04-19",
        "deadline": "",
        "status": "unknown",
        "source": "과천도시공사",
        "sourceType": "public-corporation",
        "url": "https://www.gartc.or.kr/recruit/recruit_list.do",
        "description": "과천도시공사 채용공고 페이지 바로가기"
    },
]

def main() -> None:
    payload = {
        "meta": {
            "generatedAt": datetime.now().isoformat(),
            "source": "public-region-seed-fix",
            "count": len(SEEDED_PUBLIC_JOBS),
            "notes": [
                "phase-fix: guarantee Anyang/Gunpo/Gwacheon public visibility",
                "fast restore seed for dashboard public tab"
            ],
            "errors": []
        },
        "jobs": SEEDED_PUBLIC_JOBS,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] public_jobs.json saved ({len(SEEDED_PUBLIC_JOBS)} jobs)")

if __name__ == "__main__":
    main()
