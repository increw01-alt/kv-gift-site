# kv-gift.co.kr — 한국상품권거래소 (정적 사이트)

영카트(그누보드) 사이트에서 프론트를 추출해 정적 HTML로 재구성한 버전입니다.
GitHub → Cloudflare Pages 자동 배포용. 원본에서 서버(DB·로그인)가 필요했던 기능은 아래 "변경 사항"처럼 대체했습니다.

## 최신 운영 기록

- [2026-10-21 예약 실행 지연 복구 · 하루 10편 부족분 보충](docs/AUTOMATION_RECOVERY_2026-10-21.md)
- [2026-10-20 작업 기록 · 하루 10회 자동 게시 · 사용량과 비용 확인](docs/WORK_LOG_2026-10-20.md)
- [게시판 글·이미지 자동 게시 상세 안내](tools/BOARD_AUTOMATION.md)

현재 게시판은 개별 게시글과 최신글 목록을 제공하며, 자동 검수를 통과한 글과 이미지를 별도 승인 없이 게시합니다. 아래 초기 전환 기록과 이후 운영 상태가 다를 때는 위 최신 안내를 기준으로 합니다.

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
`data/businesses.json`의 `businesses` 배열을 수정한 뒤 `node tools/build_businesses.cjs`를 실행해 메인과 전체 목록의 정적 HTML을 갱신합니다. 변경 파일을 함께 커밋·푸시하면 배포됩니다.
```json
{
  "name": "업체명",
  "desc": "업체 한 줄 소개",
  "phone": "010-0000-0000",
  "homepage": "https://example.com/",
  "certified": false,
  "mine": true,
  "featured": true,
  "enabled": true,
  "category": "구입·할부",
  "image": "/img/kv_random8.jpg",
  "imageAlt": "업체 안내용 업무 사진",
  "regions": ["서울"],
  "products": ["컬쳐랜드", "백화점"]
}
```
- 모든 카드의 하단 버튼은 **홈페이지 바로가기** 하나입니다. `homepage`는 실제 HTTP(S) 주소가 필요합니다. `phone`은 보존용이며 카드에 표시하지 않습니다.
- `featured: true`인 노출 후보에서 방문할 때마다 중복 없이 10개를 무작위 선택합니다. 2026-10-28 적용 기준 후보는 21개입니다.
- 전체 목록은 기존 등록업체 6곳을 포함해 27개이며, `enabled: false` 항목과 www 유무만 다른 중복 도메인은 표시하지 않습니다. 데이터에 중복을 추가하면 정적 빌드가 중단됩니다.
- `certified`는 기존 인증 필터용입니다. 신규 사이트 등록 자체를 인증으로 간주하지 않습니다.
- `regions`, `products`, `category`는 전체 목록의 지역·상품권 정보·분야 필터에 사용합니다. 확인하지 못한 정보는 빈 배열로 둡니다.
- `js/business-cards.js`를 브라우저와 정적 빌드가 함께 사용합니다. JavaScript나 데이터 요청이 실패해도 기본 10개 및 전체 27개의 설명과 홈페이지 링크를 이용할 수 있습니다.
- 이미지·문구는 사이트별로 고정되며 무작위 선택은 대상과 순서만 바꿉니다. 기존 사진은 안내용이며 해당 업체의 실제 사무실·직원 촬영 사진으로 표시하지 않습니다.

## 2-2. 상품권 결제 정보 관리

- 운영 경로: `/payment/`. 승인된 사진형 안내 화면에 카드 조건 비교, 카드명·확인 범위 검색, 확인 항목·카드사 필터, 비용 계산기, 체크리스트, FAQ와 상담 링크를 제공합니다.
- `data/payment-cards.json`에 카드별 범위·전월실적·혜택 적용·발급 상태 메모·공식 출처·확인일을 기록합니다. 2026-10-29 기준 5개 카드사 14종입니다. 실적 조건이 없는 상품과 상품권 혜택 적용을 구분합니다.
- `benefitType`은 `conditional`(지정 구매처 적립 조건 직접 명시), `review`(거래 분류·실적 확인 필요), `excluded`(각 행의 범위에서 제외)로 구분합니다. 조건부 적립 및 실적 검토 사례는 `source.evidence`에 판단 근거를 기록합니다. 제외 목록에 일반 상품권이 없다는 이유만으로 실적 인정을 확정하지 않습니다.
- Hi-Point 기존형·Nano의 지정 CJ 구매처 기본적립을 보유자용으로 수록하고 신규발급·유효기간 연장 중단, 구간별 적립률, 월 한도, 무이자 제외를 명시합니다. Deep Oil은 실적 제외 목록 검토 사례이며 인정 확정이 아닙니다. Hi-Point Plan의 상품권 실적·적립 제외와 혼동하지 않도록 비교합니다.
- 카드사 공식 페이지 또는 상품설명서를 직접 확인한 뒤 데이터를 수정하고 `node tools/build_payment_page.cjs`로 정적 HTML을 갱신합니다. 일반 쇼핑 혜택이나 수집 자료의 키워드 분류만으로 상품권 혜택을 판정하지 않습니다.
- 화면 원본은 `tools/templates/payment-page.html`, 스타일은 `css/payment-info.css`, 동작은 `js/payment-info.js`입니다. 생성기는 홈의 기존 GTM·GA4·네이버 분석 코드를 재사용합니다.
- 홈페이지 시세 다음 영역의 바로가기와 PC·모바일 상품권 정보 메뉴에서 연결합니다. JavaScript 없이도 14종 전체 조건과 출처를 읽을 수 있습니다.
- 비용 계산은 입력한 구매 결제금액·별도 수수료·전체 할부이자를 합산합니다. 미입력 비용은 확인 필요로 표시하고, 예상 포인트를 차감하거나 이자를 추정하지 않습니다.
- 배포 전 PC·모바일에서 검색·필터·빈 결과·비용 입력 오류·상담 링크와 고유 canonical을 확인합니다. 변경한 데이터와 생성된 HTML을 함께 커밋합니다.

### 공통 메뉴 관리

- 모든 운영 HTML은 같은 `tools/templates/site-header.html` 메뉴를 사용합니다. `css/site-navigation.css`와 `js/site-navigation.js`가 PC 하위 메뉴·모바일 전체 메뉴·현재 메뉴 표시를 담당합니다.
- 상단 순서는 상품권 시세 → 거래소 등록업체 → 추천 쇼핑몰 → 상품권 결제 정보 → 상품권 커뮤니티 → 상품권 정보 → 안내사항 → 고객센터입니다. 하위 메뉴에도 카드 조건·비용 계산·체크리스트 링크를 제공합니다.
- 공통 원본을 바꾸면 프로젝트 폴더에서 `node tools/build_site_navigation.cjs`를 실행합니다. 기존 본문·메타데이터·분석 코드는 유지하며 헤더와 공통 자산 링크만 갱신합니다. 네이버 소유확인 파일과 도구 템플릿은 대상에서 제외합니다.
- 결제 페이지 생성기는 공통 메뉴를 재사용합니다. 게시판·시세 생성기는 공통 메뉴가 적용된 `faq.html`에서 셸을 읽고, 자동 게시 글은 같은 메뉴가 적용된 `board/general_notice/42.html`에서 생성하므로 이후 생성되는 페이지에도 반영됩니다.

## 2-3. 게시글 조회수 카운터 활성화 (1회 설정)
글을 열 때마다 조회수가 +1 되는 기능은 Cloudflare Workers KV를 씁니다. 대시보드에서 한 번만 설정하면 켜집니다:
1. Cloudflare 대시보드 → **Workers & Pages → KV** → "Create namespace" → 이름 `kv_gift_views`
2. **Workers & Pages → kv-gift-site(Pages 프로젝트) → Settings → Functions → KV namespace bindings** → "Add binding"
   - Variable name: `VIEWS` (정확히 이 이름), KV namespace: `kv_gift_views` → Save
3. 저장 후 다음 배포부터(또는 Retry deployment) 카운터가 작동합니다.
설정 전에는 오류 없이 크롤 시점의 기본 조회수만 표시됩니다. 코드: `functions/api/views/`.

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
