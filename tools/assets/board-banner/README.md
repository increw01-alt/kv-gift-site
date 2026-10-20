# 승인된 게시판 이미지 기준

2026-10-20 사용자가 승인하고 게시한 공지사항 배너의 이미지 스타일과 드라이브 로고입니다.

- `approved-notice-style-20261020.png`: 공지사항 43번에 게시한 최신 승인본. 아이보리·네이비·골드 종이 질감, 짧은 한글 제목, 하단 KV 로고 배치를 참고합니다. 각 글의 주제에 맞게 사물과 구도는 바꿉니다.
- `approved-style.png`: 이전 상품권TIP 스타일 원본을 보존한 파일입니다. 현재 API 입력에는 사용하지 않습니다.
- `kv-symbol.png`: 사용자가 제공한 드라이브의 KV 심벌 원본 PNG. 원본의 형태·색상·비율을 참고합니다.
- 드라이브 폴더: https://drive.google.com/drive/folders/1czPaOATHI_vQtxQfK_WrFdSKzxXOgx2r
- 원본 파일: https://drive.google.com/file/d/1GTGUDvf81ewtR_DfL8zONUujE7DedXiO/view
- 드라이브 위치: `01_로고 / 자사브랜드 / 한국상품권협회 / 한국상품권협회_투명배경 로고1.png`

`board_banner.py`가 이 두 파일을 이미지 편집 API의 입력 이미지로 전송합니다.
본문 제목·설명은 HTML로 표시하고, 생성 이미지 상단에는 글의 요점을 담은 짧은 한글 제목 하나만 넣습니다.
작은 KV 심벌은 하단 오른쪽의 독립된 발행 매체 표시로 배치합니다.
상품권·영수증·결제카드 위에는 로고를 넣지 않아 상품권 발행사나 판매처로 오해하지 않도록 합니다.
협회 로고를 임의로 거래소 이름으로 바꾸지 않습니다.

드라이브 로그인이나 매 실행 시 다운로드에 의존하지 않도록 승인된 원본을 저장소에 보관합니다.
드라이브 파일이 바뀌어도 자동으로 교체하지 않으며, 변경본을 확인한 뒤 이 파일을 갱신합니다.
로고의 완전한 재현은 생성 모델만으로 보장되지 않으므로 검토 PR에서 로고 모양과 색상도 확인한 뒤 게시합니다.

API 문서: https://developers.openai.com/api/reference/resources/images/methods/edit
