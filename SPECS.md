# 기능 명세

## 1. 음성 대화 기본 동작
- 입력: Windows 마이크 또는 Linux 장치에서 실시간 수신.
- 인식: 기본 `google`, 오프라인 전환 시 `vosk`.
- 처리: 인식 텍스트를 `AGENT_COMMAND` 또는 OpenAI로 전달.
- 출력: `pyttsx3` 음성 읽기.
- 종료 키워드: 기본 `종료, 끝, quit, exit, 그만`.

## 2. 오프라인 모드 전환 (요청 반영)
- 환경변수 `VOICE_STT_PROVIDER`를 `google` 또는 `vosk`로 설정.
- `vosk` 선택 시 `VOICE_VOSK_MODEL_PATH`를 지정.
- `VOICE_STT_FALLBACK=true`일 때 Vosk 실패 시 Google STT로 폴백.

## 3. 상태 피드백
- 터미널 상태 라벨:
  - LISTEN, HEARD, AGENT, INFO, WARN, ERROR.
- 비프 피드백:
  - 듣기 시작, 음성 인식 완료, 응답 재생 시 각각 음향 표시.
- 비프 토글: `VOICE_BEEP_ENABLED=false`.

## 4. 인터럽트/컨트롤
- 취소 키워드: `VOICE_CANCEL_PHRASES` (기본 `취소, cancel, 중단`)
- 웨이크 키워드: `VOICE_WAKE_PHRASES` (기본 비활성)
- 웨이크 키워드를 설정하면, 말한 문장이 웨이크 키워드로 시작할 때만 명령으로 처리.
