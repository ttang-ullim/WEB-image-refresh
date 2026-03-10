# 루멕스 이미지 리프레시 (Web)

Flask 기반 이미지 변환 도구 + AdSense 승인용 정적 안내 사이트를 함께 포함한 프로젝트입니다.

## 구조
- `app.py`: 이미지 변환 API/웹 도구(Free Web Service)
- `site/`: 항상 켜져 있는 정적 안내 사이트(Free Static Site)
- `templates/`, `static/`: Flask 웹 UI

## 포함 기능(Flask 도구)
- 파일/폴더 업로드, 랜덤 변형 옵션, ZIP 다운로드
- 숨김 방문자 API (`/api/owner/visitors?token=...`)

## 포함 기능(정적 사이트: `site/`)
- 홈/가이드/소개/이용약관/개인정보처리방침/문의 페이지
- `ads.txt`, `robots.txt`, `sitemap.xml`
- AdSense 스크립트 포함

## 로컬 실행(Flask)
```powershell
python -m pip install -r requirements.txt
python app.py
```
접속: `http://127.0.0.1:5000`

## Render 배포(권장: Blueprint)
이 repo의 `render.yaml`은 서비스 2개를 만듭니다.
1. Web Service: `lumex-image-refresh` (Flask 도구)
2. Static Site: `rumex-image-refresh-site` (`site/` 배포)

### 배포 후 꼭 할 것
- Static Site 도메인이 확정되면 `site/robots.txt`, `site/sitemap.xml`의 도메인을 실제 값으로 교체 후 다시 push
- AdSense 심사는 Static Site 도메인으로 진행

## AdSense 점검 URL(Static Site)
- `/ads.txt`
- `/robots.txt`
- `/sitemap.xml`
- `/privacy.html`
- `/terms.html`
- `/contact.html`

## 환경변수
- `CONTACT_EMAIL` (기본: `rumex.soft@gmail.com`)
- `LUMEX_OWNER_TOKEN`

## 폴더 구조 관련
상위 폴더가 여러 겹이어도 문제 없습니다. GitHub에는 `이미지변환기` 폴더를 repo 루트로 올리면 됩니다.
