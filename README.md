# kv-gift.co.kr — 한국상품권거래소 (정적 사이트)

영카트(그누보드) 사이트에서 프론트를 추출해 정적 HTML로 재구성한 버전입니다.
GitHub → Cloudflare Pages 자동 배포용. 원본에서 서버(DB·로그인)가 필요했던 기능은 아래 "변경 사항"처럼 대체했습니다.

## 폴더 구조
```
kv-gift-site/
├─ index.html                 메인 (시세표 · 등록업체 · 추천 쇼핑몰 · 게시판 요약 · 공지)
├─ intro.html                 회사소개
├─ guide.html                 이용안내
├─ faq.html                   자주 묻는 질문
├─ provision.html             이용약관
├─ privacy.html               개인정보처리방침
├─ noemail.html               이메일 무단수집거부
├─ disclaimer.html            책임의 한계와 법적고지
├─ business.html              거래소 등록업체 (필터: 인증/지역/취급상품권)
├─ data/prices.json           ★ 시세표 데이터 — 이 파일만 고치면 메인 시세가 바뀜
├─ data/businesses.json       ★ 등록업체 데이터 — 이 파일만 고치면 업체 목록이 바뀜
├─ css/  colorset.css(사이트 커스텀) · default/apms/basic/bootstrap · swiper · font-awesome
├─ js/   main.js(사이트 스크립트) · jquery · swiper · bootstrap
├─ img/  로고·아이콘·배경 / img/banner/(하단 배너, 아래 스크립트로 채움) / img/editor/(팝업 이미지)
├─ fonts/                     font-awesome · glyphicons
├─ download-banner-images.sh  하단·플로팅 배너 10개 다운로드
├─ scripts-banner-images.txt  배너 URL 목록
├─ robots.txt / sitemap.xml / _headers / .gitignore
```

## 1. 배너 이미지 채우기 (배포 전 1회)
```bash
cd /mnt/c/Users/OK/Desktop/kv-gift-site && bash download-banner-images.sh
ls img/banner | wc -l      # 10 이면 완료
```

## 2. 시세 갱신 방법
`data/prices.json` 을 열어 `updated` 날짜와 각 행의 `buy`/`buy_rate`/`sell`/`sell_rate` 를 수정한 뒤 `git push` 하면 됩니다.
행 추가/삭제도 같은 형식으로 하면 되고, `paper`(지류) / `mobile`(모바일) 두 배열로 나뉩니다.

## 2-1. 등록업체 추가/수정 방법
`data/businesses.json` 을 열어 `businesses` 배열 **맨 앞에** 아래 형식으로 추가하고 `git push` 하면 됩니다.
(GitHub 웹사이트에서 파일을 직접 편집·커밋해도 자동 배포됩니다)
```json
{
  "name": "업체명",
  "desc": "업체 한 줄 소개",
  "phone": "010-0000-0000",
  "homepage": "https://example.com/",
  "certified": true,
  "regions": ["서울"],
  "products": ["컬쳐랜드", "백화점"]
}
```
- `phone` / `homepage` 는 없으면 `""` 로 두면 해당 버튼이 숨겨집니다.
- `certified: true` 면 "인증업체" 필터에 포함됩니다.
- `regions`(지역) / `products`(취급 상품권) 는 business.html 필터에 쓰입니다. 온라인 전용 업체는 `regions: []`.
- 메인 화면의 "거래소 등록업체" 카드와 "최근등록업체" 플로팅 목록은 이 파일의 **앞 10개**가 자동 표시됩니다.

## 3. 로컬 확인
```bash
python3 -m http.server 8080     # http://localhost:8080  (file:// 로 열면 스타일이 안 붙음)
```

## 4. GitHub + Cloudflare Pages
```bash
git init && git add . && git commit -m "kv-gift 정적 사이트 초기 버전"
git branch -M main
git remote add origin https://github.com/increw01-alt/kv-gift-site.git
git push -u origin main
```
Cloudflare Pages: Connect to Git → `kv-gift-site` → Framework **None**, Build command 비움, Output `/` → Custom domain `kv-gift.co.kr`, `www.kv-gift.co.kr` → SSL/TLS Full.

## 원본 대비 변경 사항
- 로그인·회원가입·검색·MY·사이드바·접속자 통계 제거
- **시세표**: 서버 렌더링 → `data/prices.json` + JS 렌더링 (2026-09-29 기준 값 수록)
- **거래소 등록업체**: 원본 DB 대신 `data/businesses.json` + JS 렌더링. 원본 사이트에 공개된 업체 38곳(업체명·소개·전화·홈페이지·인증·지역·취급상품권) 수록. 전용 페이지 `business.html`(인증/지역/상품권 필터) 신설, 메인 카드 10개·최근등록업체 플로팅도 같은 데이터로 자동 표시
- **지역별/상품권별 검색**: 메인 빠른검색·메뉴에서 `business.html?region=…` / `?product=…` 필터 링크로 연결
- **게시판(구매·판매·자유·TIP·공지)**: 메인의 최근 글 제목은 당시 스냅샷 그대로, 클릭 없음 / "더보기"는 네이버 카페·상품권뉴스(vipvip.or.kr)·공지 앵커로 연결
- **메뉴**: 커뮤니티 → 네이버 카페, 상품권 정보 → 상품권뉴스, 협회 소식 → koreagiftcard.co.kr, 1:1문의 → 채널톡
- jQuery 1.8/3.7 이중 로딩, Swiper 이중 로딩 정리, 라이브러리 로컬 번들화, Pretendard 웹폰트 CDN 적용
- canonical / OG / sitemap / robots 추가, GTM(GTM-TRDLP9JG)·GA4(G-G8CXQD45G3)·네이버 애널리틱스 코드 유지
- 자유게시판 목록에 있던 **악성 스크립트 삽입 글(XSS 시도)** 과 스팸성 글 제거

## 배포 전 확인
- [ ] `img/og_img.png` (1200×630) 추가 — 원본 서버에 없던 파일
- [ ] 푸터 사업자 정보(대표자·개인정보책임자·주소·번호)가 현재 기준으로 맞는지 확인
- [ ] 게시판 최근 글 목록이 오래되어 보이면 해당 블록 삭제 또는 갱신
- [ ] 네이버 서치어드바이저 kv-gift.co.kr 재등록 후 `naver-site-verification` 교체
- [ ] 팝업 이미지(`img/editor/popup-20260731.png`) 내용이 현재 유효한지 확인
