# 에이전트 연동 계약

이 프로젝트는 CLI 에이전트와 텍스트만으로 통신한다.

## 입력 계약
- 기본: `python app.py`가 인식한 문장을 `AGENT_COMMAND`에 전달한다.
- `AGENT_COMMAND` 형식:
  - 인자 템플릿: `your-cli --prompt "{prompt}"`
  - stdin 모드: `AGENT_USE_STDIN=true` 로 설정하면 명령어는 `stdin`으로 전달됨
- 예시
  - `AGENT_COMMAND=codex run --prompt "{prompt}"`
  - `AGENT_COMMAND=python -m my_agent`
  - `AGENT_USE_STDIN=true` + `AGENT_COMMAND=python -m my_agent`

## 출력 계약
- 에이전트 응답은 stdout 텍스트를 그대로 사용한다.
- 실패 시 stderr는 `[agent error] ...` 형태로 출력한다.
- 출력이 비어 있으면 `"(No output from agent)"`로 처리한다.

## 운영 제약
- 긴 응답은 `AGENT_TIMEOUT_SECONDS` 초 초과 시 타임아웃 처리한다.
- 응답이 비어 있으면 음성 응답은 생략한다.
