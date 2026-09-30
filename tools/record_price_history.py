# -*- coding: utf-8 -*-
"""
협회(koreagiftcard.co.kr) 실시간 시세를 data/price-history.json 에 축적
- GitHub Actions 가 하루 4회 실행 (.github/workflows/price-history.yml)
- 같은 updated_at 스냅샷은 중복 저장하지 않음
"""
import json
import ssl
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
HISTORY = SITE / "data" / "price-history.json"
RATES_URL = "https://koreagiftcard.co.kr/rates.json"

ctx = ssl.create_default_context()


def main():
    req = urllib.request.Request(RATES_URL, headers={"User-Agent": "kv-gift-history-bot"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        rates = json.loads(r.read().decode("utf-8"))

    if HISTORY.exists():
        hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    else:
        hist = {"face": rates.get("face", 100000), "series": {}}

    t = rates["updated_at"]
    added = 0
    for s in rates.get("summary", []):
        brand = s["brand"]
        arr = hist["series"].setdefault(brand, [])
        if arr and arr[-1]["t"] == t:
            continue  # 같은 스냅샷 중복 방지
        arr.append({
            "t": t,
            "buy": s["bestBuy"]["price"],
            "sell": s["bestSell"]["price"],
        })
        # 최근 400개(약 100일치)만 유지
        del arr[:-400]
        added += 1

    HISTORY.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"기록 완료: {t} / 브랜드 {added}개 추가")


if __name__ == "__main__":
    main()
