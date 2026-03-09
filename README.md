# 루멕스 이미지 리프레시 (Web)

기존 Tkinter "이미지 세탁기" 기능을 웹으로 옮긴 Flask 버전입니다.

## 포함 기능
- 파일 또는 폴더(브라우저 업로드) 선택
- 원본 1장당 N개 생성
- 메타데이터 재생성(EXIF 제거)
- 랜덤 크롭
- 랜덤 리사이즈(100% ± X%)
- 랜덤 회전(-X° ~ +X°) + 안전 크롭
- 보이지 않는 노이즈 오버레이
- 랜덤 밝기/채도 조정
- 테두리(고정/랜덤)
- 출력 포맷: 원본 유지 / JPG / PNG / WEBP
- 결과 ZIP 다운로드
- 숨김 방문자 API(오너 토큰 필요)

## 로컬 실행
1. 라이브러리 설치
```powershell
python -m pip install -r requirements.txt
```

2. 서버 실행
```powershell
python app.py
```

3. 브라우저 접속
- `http://127.0.0.1:5000`

## Render 배포
이 프로젝트는 `render.yaml`이 포함되어 있어 GitHub 연결 후 자동 인식됩니다.

1. GitHub에 현재 폴더(`이미지변환기`)를 그대로 push
2. Render 대시보드에서 `New +` -> `Blueprint` 선택
3. 저장소 선택 후 배포

수동으로 Web Service 만들 경우:
- Runtime: `Python`
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300`

## 방문자 통계(숨김)
- 엔드포인트: `/api/owner/visitors?token=...`
- 기본 토큰: `lumex-refresh-owner`
- 운영에서는 Render 환경변수 `LUMEX_OWNER_TOKEN`을 꼭 바꿔주세요.

## 폴더 구조 관련
- `폴더 -> 폴더 -> 이미지변환기`처럼 깊은 구조여도 문제 없습니다.
- GitHub에는 "최종 프로젝트 루트(이미지변환기)"만 저장소로 올리면 됩니다.
