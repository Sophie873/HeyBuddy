# 운영 가이드

## 설치
```bash
cd D:\Codex\음성
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

`PyAudio` 설치 실패 시:
```bash
pip install pipwin
pipwin install pyaudio
```

## 실행
- 음성 모드: `python app.py`
- 텍스트 모드: `python app.py --text`
- Vosk 사용:
  - `VOICE_STT_PROVIDER=vosk`
  - `VOICE_VOSK_MODEL_PATH=모델경로`

## 환경변수 체크리스트
- `AGENT_COMMAND` 또는 `USE_OPENAI=true + OPENAI_API_KEY`
- `VOICE_WAKE_PHRASES` (필요하면 설정)
- `VOICE_EXIT_PHRASES`, `VOICE_CANCEL_PHRASES`
- `VOICE_BEEP_ENABLED` / `VOICE_TTS_ENABLED`

## 자주 묻는 이슈
- 인식이 안 됨: 마이크 권한, `VOICE_PHRASE_TIME_LIMIT` 조정
- 너무 느림: `VOICE_PHRASE_TIME_LIMIT` 축소, `ambient_adjust` 수치 줄이기
- 소리가 안 나옴: `VOICE_TTS_PROVIDER`와 `VOICE_TTS_ENABLED` 확인, `pyttsx3` 설치
