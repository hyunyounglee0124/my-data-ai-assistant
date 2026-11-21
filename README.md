# 내 데이터를 아는 AI 비서

날짜, 값, 메모를 SQLite에 저장하고, 시계열 분석 및 Codyssey OpenAI 호환 API를 통해 데이터 기반 채팅을 제공하는 FastAPI 웹 서비스입니다.

## 실행 방법 (Python 3.10 이상)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
python -m uvicorn app.main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속.

## 실제 API 키 입력

`.env`의 `CODYSSEY_API_KEY=여기에_발급받은_API_키_입력`을 실제 키로 교체하고 서버를 재시작합니다. **키를 GitHub에 업로드하거나 채팅에 공유하지 마세요.** `.env`는 `.gitignore`에 포함되어 있습니다.

Codyssey 호환 API URL은 `https://copa.codyssey.kr/v1`, 기본 모델은 `gpt-5-mini`입니다. 실제 계정에서 해당 모델이 허용되는지 확인하세요. 외부 API 연결은 유효한 키가 있어야 검증할 수 있습니다.

## 기능

- 기록 CRUD: 날짜, 실수 값, 메모 입력·조회·수정·삭제
- SQLite 데이터 영구 저장 및 날짜 인덱스
- 시계열 일별 합계, 건수, 합계, 평균, 최소·최대, 첫날 대비 마지막 날 변화
- 차트(Chart.js CDN, 인터넷 연결 필요), 모바일 대응
- 분석 결과 스냅샷 저장과 최근 30개 조회 API
- 데이터 요약 및 최근 300개 원시 기록을 AI 프롬프트에 포함한 채팅
- API 키 미설정 또는 API 오류 시 기본 분석 모드와 안내 표시
- 로딩 상태, 입력 검증, 삭제 확인

## API 문서

http://127.0.0.1:8000/docs 에서 자동 생성된 API 문서 확인.

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET/POST | `/api/records` | 목록/등록 |
| PUT/DELETE | `/api/records/{id}` | 수정/삭제 |
| GET | `/api/analysis` | 현재 분석 |
| POST | `/api/analysis/save` | 분석 저장 |
| GET | `/api/analysis/history` | 저장된 분석 이력 |
| POST | `/api/chat` | 데이터 기반 질문 |

## 테스트

```bash
python -m pytest -q
```

## 참고 및 제한

- 입력값에는 단위가 없으므로 원/명/건 등으로 임의 해석하지 않습니다.
- 동일 날짜의 기록은 차트에서 합산합니다.
- AI 입력에 최근 300건을 포함하며 전체 집계는 항상 반영합니다. 300건 이전의 세부 메모를 질문할 경우 AI가 정확히 확인하지 못할 수 있습니다.
- 로컬 학습용 앱입니다. 인터넷 공개 배포 전 로그인, 접근 권한, HTTPS, 요청 제한 등을 추가해야 합니다.
- `.env.example`은 실제 비밀키를 포함하지 않습니다.
