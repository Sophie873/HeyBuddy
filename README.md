# 음성 CLI 에이전트

마이크 음성 입력 -> 텍스트 변환 -> 에이전트 -> 음성 응답까지 한 번에 처리하는 실시간 CLI 입니다.

## 설치

```bash
cd D:\Codex\음성
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

기본 설치는 텍스트 모드(의존성 최소) 위주라 바로 설치가 끝납니다.

음성 모드까지 쓰려면 PyAudio를 추가로 설치해야 합니다:
```bash
pip install -r requirements-audio.txt
```

Python 3.14에서는 PyAudio 배포판 제약으로 실패할 수 있으니,
가능하면 Python 3.12/3.13 환경에서 설치해 주세요.

`No Default Input Device Available`가 나오는 경우, 마이크 기본 입력 장치가 미설정입니다.
- 윈도우 `설정 > 개인정보 보호 및 보안 > 마이크`에서 앱 접근 허용
- 오디오 출력이 아니라 입력 장치가 기본으로 잡혔는지 확인
- 임시로 장치 인덱스 고정이 필요하면 `.env`에 `VOICE_INPUT_DEVICE_INDEX` 추가

입력 장치 번호 확인(현재 세션에서 인식되는 입력 장치만):

```bash
.\.venv\Scripts\python.exe -c "import pyaudio; pa=pyaudio.PyAudio(); print([(i, pa.get_device_info_by_index(i)['name']) for i in range(pa.get_device_count()) if pa.get_device_info_by_index(i).get('maxInputChannels',0)>0]); pa.terminate()"
```

## 실행

음성 모드:

```bash
python app.py
```

### 음성 사용 방법
- 마이크가 켜지면 바로 듣기 시작한다.
- 대기어가 비어 있으면, 말을 하면 바로 명령으로 처리된다.
- 예: `오늘 할 일을 정리해줘`
- 텍스트는 에이전트 처리 후 음성으로 다시 재생된다.
- 종료: `종료`, `끝`, `exit`, `quit`, `그만`
- 취소: `취소`, `cancel`, `중단`

`No Default Input Device Available`가 뜨면 장치 인덱스를 고정하세요.
```bash
.\.venv\Scripts\python.exe -c "import pyaudio; pa=pyaudio.PyAudio(); print([(i, pa.get_device_info_by_index(i)['name']) for i in range(pa.get_device_count()) if pa.get_device_info_by_index(i).get('maxInputChannels',0)>0]); pa.terminate()"
```

위 출력에서 사용하려는 마이크 인덱스를 `.env`에 넣습니다.
```bash
VOICE_INPUT_DEVICE_INDEX=21
```

### Ollama 준비

```bash
ollama pull llama3.1:8b
ollama serve
```
ollama가 없으면 AGENT_COMMAND가 실행되지 않고 `AGENT_COMMAND not found: ollama`가 나옵니다.
`where.exe ollama`로 설치 위치를 확인하세요. 경로가 안 나오면 절대경로를 넣으세요.

```bash
AGENT_COMMAND=C:\Program Files\Ollama\ollama.exe run llama3.1:8b
```

원클릭 실행(권장):

```bash
launch_voice_agent_onedir.bat
```

또는 직접 실행:

`D:\Codex\음성\release\voice-cli-agent-dir-2\voice-cli-agent-dir.exe`

`voice-cli-agent-dir-2`는 최신 빌드입니다. 기존 `voice-cli-agent-dir`는 권한 문제로 교체 실패가 있으면 유지됩니다.

원클릭 실행(기존 런처):

```bash
launch_voice_agent.bat
```

> 기존 `voice-cli-agent.exe`(onefile)는 현재 환경에서 `VCRUNTIME140.dll` 추출 권한 이슈로 시작 직후 바로 종료될 수 있습니다.
> 실제 사용은 onedir(`voice-cli-agent-dir`)를 권장합니다.

텍스트 모드:

```bash
python app.py --text
```

STT 공급자 오버라이드(한 번 실행만):

```bash
python app.py --stt-provider vosk
```

작업 폴더 오버라이드:

```bash
python app.py --workdir D:\프로젝트\경로
```

종료 키워드: `종료`, `끝`, `quit`, `exit`, `그만`

## .env 예시

```bash
VOICE_LANGUAGE=ko-KR
VOICE_LISTEN_TIMEOUT=3
VOICE_PHRASE_TIME_LIMIT=12
VOICE_ADJUST_DURATION=0.8
VOICE_PAUSE_THRESHOLD=0.8
VOICE_EXIT_PHRASES=종료,끝,quit,exit,그만
VOICE_CANCEL_PHRASES=취소,cancel,중단
VOICE_WAKE_PHRASES=

# STT
VOICE_STT_PROVIDER=google
# 오프라인 전환용
# VOICE_STT_PROVIDER=vosk
# VOICE_VOSK_MODEL_PATH=D:\models\vosk-model-ko
VOICE_INPUT_DEVICE_INDEX=
VOICE_STT_FALLBACK=true
VOICE_VOSK_SAMPLE_RATE=16000

# CLI 에이전트
# OLLAMA 권장(로컬, 비용 없음)
AGENT_COMMAND=ollama run llama3.1:8b
AGENT_WORKDIR=
AGENT_USE_STDIN=true
AGENT_TIMEOUT_SECONDS=180

# OpenAI fallback
USE_OPENAI=false
OPENAI_MODEL=gpt-4o-mini
OPENAI_API_KEY=
OPENAI_SYSTEM_PROMPT=You are a concise voice assistant style CLI agent.
OPENAI_STREAM=true
OPENAI_STREAM_PRINT=true

# TTS
VOICE_TTS_PROVIDER=pyttsx3
VOICE_TTS_ENABLED=true
VOICE_TTS_RATE=180
VOICE_TTS_VOLUME=1.0
VOICE_TTS_VOICE=

# 피드백
VOICE_BEEP_ENABLED=true
VOICE_BEEP_LISTEN_FREQ=1100
VOICE_BEEP_LISTEN_DUR=70
VOICE_BEEP_HEARD_FREQ=1500
VOICE_BEEP_HEARD_DUR=80
VOICE_BEEP_SPEAK_FREQ=900
VOICE_BEEP_SPEAK_DUR=90

# 선택: 턴 단위 로그 기록(로그파일 경로 지정 시)
VOICE_LOG_PATH=
``` 

## 구조

- `app.py`: 음성 루프, STT, TTS, 에이전트 호출 엔진
- `requirements.txt`: Python 의존성
- `AGENTS.md`: 운영 규칙
- `SPECS.md`: 기능 정의
- `AGENT_CONTRACT.md`: CLI 연동 계약
- `ROADMAP.md`: 다음 작업 계획
- `ops.md`: 운영 메모

## 동작 플로우

1. 마이크에서 녹음
2. STT(`google` 또는 `vosk`)로 텍스트 변환
3. 텍스트 기반 제어(종료/취소/웨이크)
4. 에이전트 호출
5. 응답 TTS

`VOICE_STT_PROVIDER=vosk`를 사용하면 모델 경로가 준비된 상태에서 오프라인 기반 전환이 가능합니다.
