#!/usr/bin/env bash
# 하단·플로팅 배너 이미지 10개(원본은 kv-gift.com 서버)를 img/banner/ 로 내려받습니다.
# 실행: WSL2 Ubuntu에서 사이트 루트 폴더로 이동 후  bash download-banner-images.sh
set -u
cd "$(dirname "$0")"
mkdir -p img/banner
ok=0; fail=0
while IFS=$'\t' read -r url name; do
  [ -z "$url" ] && continue
  if [ -s "img/banner/$name" ]; then ok=$((ok+1)); continue; fi
  if wget -q --no-check-certificate --timeout=15 --tries=2 --user-agent="Mozilla/5.0" -O "img/banner/$name" "$url"; then
    ok=$((ok+1))
  else
    rm -f "img/banner/$name"; fail=$((fail+1)); echo "실패: $name  ($url)"
  fi
done < scripts-banner-images.txt
echo "완료: 성공 $ok / 실패 $fail  (이미지 위치: img/banner/)"
