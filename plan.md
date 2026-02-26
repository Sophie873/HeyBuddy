# 음성 CLI 에이전트 로드맵

작성일: 2026-02-25

## 현재 상태

- Python 3.14 환경의 기존 의존성(텍스트/기본) 설치는 완료됨.
- `PyAudio`는 네트워크/배포판 제약과 Python 3.14 조합 때문에 현재 환경에서 미설치 상태였음.
- `requirements.txt`에서 음성용 필수 항목(`PyAudio`)를 분리하고 `requirements-audio.txt`로 관리하도록 변경함.
- `README.md`에 음성용 의존성 설치 가이드를 반영함.
- 실행기는 onedir 기반 실행 경로를 기본으로 사용하도록 유지됨.

## 설치 로드맵(너가 지금 막 설치한 3.13 기준)

1. Python 3.13.x 확인
   - `py -0p` 실행해서 3.13 경로가 보이는지 확인
2. 프로젝트 가상환경 생성
   - `cd D:\Codex\음성`
   - `py -3.13 -m venv .venv`
3. 가상환경 활성화
   - `.venv\Scripts\activate`
4. 기본 패키지 설치
   - `pip install -r requirements.txt`
5. 음성 패키지 설치
   - `pip install -r requirements-audio.txt`
6. 실행 체크
   - 텍스트: `python app.py --text`
   - 음성: `launch_voice_agent_onedir.bat`에서 `1` 선택

## 완료 항목

- [x] 핵심 코드 및 런처 안정성 개선
- [x] 텍스트 모드 실행 정상화
- [x] `requirements.txt`에서 `PyAudio` 분리
- [x] `requirements-audio.txt` 신규 추가
- [x] 설치 가이드 반영

## 남은 항목

- [ ] Python 3.13 가상환경에서 `pip install -r requirements-audio.txt` 실행
- [ ] 음성 모드 마이크 입력 테스트(실제 `종료` 인식 포함)
- [ ] 음성 응답 성능 확인(오디오 장치/마이크 드라이버/권한 체크)
- [ ] 3.13 가상환경으로 launcher 실행 경로 고정(선택)

## 실패 원인 기록

- `PyAudio`는 현재 환경에서 `pip` 저장소/프록시 이슈와 Python 3.14 조합 때문에 바로 설치되지 않음.
- 핵심 동작은 코드/실행기 자체 문제보다 **환경 의존성 제약** 때문에 멈춘 상태.
