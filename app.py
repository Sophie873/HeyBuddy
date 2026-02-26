from __future__ import annotations

import argparse
import glob as _glob_mod
import json
import os
import sys
import shlex
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _fallback_load_dotenv(*paths: str) -> None:
    """Small local .env loader used when python-dotenv is unavailable."""
    candidate_paths: List[Path] = []
    if not paths:
        candidate_paths.append(Path(".env"))
    else:
        for path in paths:
            candidate_paths.append(Path(path))

    for path in candidate_paths:
        resolved = path.expanduser()
        if not resolved.exists():
            continue
        try:
            for raw in resolved.read_text(encoding="utf-8").splitlines():
                text = raw.strip()
                if not text or text.startswith("#"):
                    continue
                if text.lower().startswith("export "):
                    text = text[7:].strip()
                if "=" not in text:
                    continue
                key, value = text.split("=", 1)
                key = key.strip()
                value = value.strip().strip().strip("'\"")
                if key and value:
                    os.environ.setdefault(key, value)
        except Exception:
            pass
            break


def _env_file_candidates() -> List[Path]:
    base = Path(__file__).resolve()
    cwd = Path.cwd()
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None

    candidates: List[Path] = []
    for path in [
        base.with_name(".env"),
        cwd / ".env",
        base.parent / ".env",
        base.parent.parent / ".env",
        exe_dir / ".env" if exe_dir is not None else None,
        exe_dir.parent / ".env" if exe_dir is not None else None,
        exe_dir.parent.parent / ".env" if exe_dir is not None else None,
    ]:
        if path is None:
            continue
        candidates.append(path)

    unique: List[Path] = []
    seen = set()
    for path in candidates:
        resolved = path.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


try:
    from dotenv import load_dotenv as _dotenv_load_dotenv
except Exception:
    load_dotenv = _fallback_load_dotenv
else:
    load_dotenv = _dotenv_load_dotenv


def _load_app_env() -> None:
    env_paths = _env_file_candidates()
    for path in env_paths:
        try:
            load_dotenv(dotenv_path=path)
        except Exception:
            continue


_load_app_env()


try:
    import speech_recognition as sr
except ImportError as e:  # pragma: no cover
    sr = None
    _SR_IMPORT_ERROR = e
else:
    _SR_IMPORT_ERROR = None

try:
    import pyttsx3
except Exception as e:  # pragma: no cover
    pyttsx3 = None
    _PYTTSX3_IMPORT_ERROR = e
else:  # pragma: no cover
    _PYTTSX3_IMPORT_ERROR = None

try:
    from vosk import Model as _VoskModel
    from vosk import KaldiRecognizer as _VoskKaldiRecognizer
except Exception:  # pragma: no cover
    _VoskModel = None
    _VoskKaldiRecognizer = None


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _status(level: str, message: str) -> None:
    print(f"[{_timestamp()}] [{level.upper():8}] {message}", flush=True)


def _str_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        _status("warn", f"{name} is invalid. fallback: {default}")
        return default


def _split_csv(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _list_input_device_indices() -> List[int]:
    try:
        import pyaudio
    except Exception:
        return []
    if pyaudio is None:
        return []

    indices: List[int] = []
    try:
        pa = pyaudio.PyAudio()
    except Exception:
        return []

    try:
        count = pa.get_device_count()
        for index in range(count):
            try:
                info = pa.get_device_info_by_index(index)
            except Exception:
                continue
            if (info.get("maxInputChannels", 0) or 0) > 0:
                indices.append(index)
    finally:
        try:
            pa.terminate()
        except Exception:
            pass
    return indices


def _default_input_rate(device_index: Optional[int]) -> int:
    try:
        import pyaudio
    except Exception:
        return 16000

    pa = None
    try:
        pa = pyaudio.PyAudio()
        if device_index is None:
            try:
                info = pa.get_default_input_device_info()
            except Exception:
                return 16000
        else:
            info = pa.get_device_info_by_index(int(device_index))
        raw_rate = info.get("defaultSampleRate", 16000)
        rate = int(raw_rate)
        if rate > 0:
            return rate
    except Exception:
        return 16000
    finally:
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
    return 16000


def _can_open_microphone(device_index: Optional[int]) -> bool:
    try:
        import pyaudio
    except Exception:
        return False

    pa = None
    try:
        pa = pyaudio.PyAudio()
        if device_index is None:
            try:
                info = pa.get_default_input_device_info()
                idx = int(info.get("index", -1))
            except Exception:
                idx = None
        else:
            idx = int(device_index)
            info = pa.get_device_info_by_index(idx)

        if info.get("maxInputChannels", 0) <= 0:
            return False

        default_rate = _default_input_rate(idx if idx >= 0 else None)
        max_channels = max(1, min(2, int(info.get("maxInputChannels", 1))))
        rates = [default_rate, 16000, 22050, 32000, 44100, 48000]

        for rate in rates:
            if rate <= 0:
                continue
            for channels in (1, max_channels):
                if channels < 1:
                    continue
                try:
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=channels,
                        rate=rate,
                        input=True,
                        input_device_index=idx if idx is not None else None,
                        frames_per_buffer=1024,
                    )
                    stream.close()
                    return True
                except Exception:
                    continue
    except Exception:
        return False
    finally:
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
    return False


def _device_names_for_indices(indices: List[int]) -> List[str]:
    names: List[str] = []
    if not indices:
        return names
    try:
        import pyaudio
    except Exception:
        return ["" for _ in indices]

    try:
        pa = pyaudio.PyAudio()
    except Exception:
        return ["" for _ in indices]

    try:
        for idx in indices:
            try:
                names.append(pa.get_device_info_by_index(idx).get("name", ""))
            except Exception:
                names.append("")
    finally:
        try:
            pa.terminate()
        except Exception:
            pass
    return names


def _play_beep(settings: "Settings", mode: str) -> None:
    if not settings.beep_enabled:
        return
    if os.name == "nt":
        try:
            import winsound

            if mode == "listen":
                freq = settings.beep_listen_freq
                dur = settings.beep_listen_dur
            elif mode == "heard":
                freq = settings.beep_heard_freq
                dur = settings.beep_heard_dur
            elif mode == "speak":
                freq = settings.beep_speak_freq
                dur = settings.beep_speak_dur
            else:
                freq = 700
                dur = 70
            winsound.Beep(max(37, min(32767, freq)), max(10, min(300, dur)))
            return
        except Exception:
            pass
    print("\a", end="", flush=True)


def _resolve_log_path(raw_path: str) -> Optional[Path]:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    try:
        if str(path).strip():
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
    except Exception:
        return None
    return None


def _write_log(
    log_path: Optional[Path],
    mode: str,
    raw_text: str,
    action: str,
    payload: str,
    reply: str,
) -> None:
    if log_path is None:
        return
    try:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "raw": raw_text,
            "action": action,
            "payload": payload,
            "reply": reply,
        }
        with log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Conversation session history
# ---------------------------------------------------------------------------

_SESSIONS_DIR_NAME = "sessions"


def _sessions_dir() -> Path:
    base = Path(__file__).resolve().parent if not getattr(sys, "frozen", False) else Path(sys.executable).resolve().parent
    d = base / _SESSIONS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


class ConversationSession:
    """Tracks turns in a single conversation session and persists to JSONL."""

    def __init__(self, mode: str = "text") -> None:
        self.session_id: str = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.started_at: str = datetime.now().isoformat(timespec="seconds")
        self.mode: str = mode
        self.turns: List[Dict[str, str]] = []
        self._file: Optional[Path] = None
        try:
            self._file = _sessions_dir() / f"{self.session_id}.jsonl"
            self._write_header()
        except Exception:
            self._file = None

    def _write_header(self) -> None:
        if self._file is None:
            return
        header = {
            "type": "session_start",
            "session_id": self.session_id,
            "started_at": self.started_at,
            "mode": self.mode,
        }
        try:
            with self._file.open("a", encoding="utf-8") as fp:
                fp.write(json.dumps(header, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def add_turn(self, user_text: str, reply: str) -> None:
        turn = {
            "type": "turn",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user": user_text,
            "reply": reply,
        }
        self.turns.append(turn)
        if self._file is not None:
            try:
                with self._file.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(turn, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def finish(self) -> None:
        footer = {
            "type": "session_end",
            "ended_at": datetime.now().isoformat(timespec="seconds"),
            "total_turns": len(self.turns),
        }
        if self._file is not None:
            try:
                with self._file.open("a", encoding="utf-8") as fp:
                    fp.write(json.dumps(footer, ensure_ascii=False) + "\n")
            except Exception:
                pass

    def summary_text(self) -> str:
        n = len(self.turns)
        if n == 0:
            return "이번 세션에서 대화가 없었습니다."
        lines = [f"세션 요약 ({self.started_at}, {n}턴):"]
        for i, t in enumerate(self.turns, 1):
            user_preview = (t["user"][:40] + "...") if len(t["user"]) > 40 else t["user"]
            reply_preview = (t["reply"][:40] + "...") if len(t["reply"]) > 40 else t["reply"]
            lines.append(f"  {i}. 나: {user_preview}")
            lines.append(f"     봇: {reply_preview}")
        return "\n".join(lines)

    def current_history_text(self) -> str:
        if not self.turns:
            return "아직 대화 내역이 없습니다."
        lines = [f"현재 세션 대화 ({len(self.turns)}턴):"]
        for i, t in enumerate(self.turns, 1):
            lines.append(f"  [{i}] 나: {t['user']}")
            lines.append(f"      봇: {t['reply']}")
        return "\n".join(lines)


def _list_past_sessions(limit: int = 10) -> str:
    try:
        d = _sessions_dir()
    except Exception:
        return "세션 디렉터리를 열 수 없습니다."

    files = sorted(d.glob("*.jsonl"), key=lambda p: p.name, reverse=True)
    if not files:
        return "저장된 세션이 없습니다."

    lines = [f"최근 세션 목록 (최대 {limit}개):"]
    for f in files[:limit]:
        try:
            first_line = f.read_text(encoding="utf-8").splitlines()[0]
            meta = json.loads(first_line)
            started = meta.get("started_at", "?")
            mode = meta.get("mode", "?")
        except Exception:
            started = "?"
            mode = "?"

        # count turns
        turn_count = 0
        try:
            for raw_line in f.read_text(encoding="utf-8").splitlines():
                entry = json.loads(raw_line)
                if entry.get("type") == "turn":
                    turn_count += 1
        except Exception:
            pass

        lines.append(f"  {f.stem}  ({mode}, {turn_count}턴, {started})")

    return "\n".join(lines)


def _show_session_detail(session_id: str) -> str:
    try:
        d = _sessions_dir()
    except Exception:
        return "세션 디렉터리를 열 수 없습니다."

    # find matching file
    matches = list(d.glob(f"{session_id}*.jsonl"))
    if not matches:
        return f"세션 '{session_id}'을(를) 찾을 수 없습니다."

    target = matches[0]
    lines = [f"세션: {target.stem}"]
    try:
        for raw_line in target.read_text(encoding="utf-8").splitlines():
            entry = json.loads(raw_line)
            if entry.get("type") == "turn":
                lines.append(f"  나: {entry.get('user', '')}")
                lines.append(f"  봇: {entry.get('reply', '')}")
                lines.append("")
            elif entry.get("type") == "session_end":
                lines.append(f"  [종료: {entry.get('ended_at', '?')}, 총 {entry.get('total_turns', '?')}턴]")
    except Exception as exc:
        lines.append(f"  파일 읽기 실패: {exc}")

    return "\n".join(lines)


def _contains_phrase(text: str, phrases: List[str]) -> Optional[str]:
    lowered = text.lower().strip()
    for phrase in phrases:
        if not phrase:
            continue
        if (
            lowered == phrase
            or lowered.startswith(f"{phrase} ")
            or lowered.endswith(f" {phrase}")
            or f" {phrase} " in lowered
        ):
            return phrase
    return None


def _strip_wake_word(text: str, wake_words: List[str]) -> Optional[str]:
    if not wake_words:
        return text
    lowered_tokens = text.lower().split()
    original_tokens = text.strip().split()
    for phrase in wake_words:
        phrase_tokens = phrase.split()
        if not phrase_tokens:
            continue
        if lowered_tokens[: len(phrase_tokens)] == phrase_tokens:
            return " ".join(original_tokens[len(phrase_tokens) :]).strip()
    return None


_SLASH_COMMANDS = {
    "/기록": "history",
    "/history": "history",
    "/지난기록": "sessions",
    "/sessions": "sessions",
    "/도움": "help",
    "/help": "help",
}


def _resolve_user_input(raw_text: str, settings: "Settings") -> Tuple[str, str]:
    text = raw_text.strip()
    if not text:
        return "empty", ""

    lowered = text.lower()

    # slash commands
    parts = lowered.split(None, 1)
    cmd_key = parts[0] if parts else ""
    cmd_arg = parts[1] if len(parts) > 1 else ""
    if cmd_key in _SLASH_COMMANDS:
        return "slash", f"{_SLASH_COMMANDS[cmd_key]}:{cmd_arg}"

    exit_match = _contains_phrase(lowered, settings.exit_phrases)
    if exit_match:
        return "exit", exit_match

    cancel_match = _contains_phrase(lowered, settings.cancel_phrases)
    if cancel_match:
        return "cancel", cancel_match

    if settings.wake_phrases:
        stripped = _strip_wake_word(lowered, settings.wake_phrases)
        if stripped is None:
            return "ignore", ""
        lowered = stripped.strip()

    return "command", lowered


@dataclass
class Settings:
    language: str = os.getenv("VOICE_LANGUAGE", "ko-KR")
    phrase_time_limit: float = float(os.getenv("VOICE_PHRASE_TIME_LIMIT", "12"))
    listen_timeout: float = float(os.getenv("VOICE_LISTEN_TIMEOUT", "3"))
    ambient_adjust: float = float(os.getenv("VOICE_ADJUST_DURATION", "0.8"))
    pause_threshold: float = float(os.getenv("VOICE_PAUSE_THRESHOLD", "0.8"))

    stt_provider: str = os.getenv("VOICE_STT_PROVIDER", "google").strip().lower()
    stt_vosk_model_path: str = os.getenv("VOICE_VOSK_MODEL_PATH", "").strip()
    stt_vosk_sample_rate: int = int(os.getenv("VOICE_VOSK_SAMPLE_RATE", "16000"))
    stt_device_index: int = _env_int("VOICE_INPUT_DEVICE_INDEX", -1)
    stt_fallback_to_google: bool = _str_bool("VOICE_STT_FALLBACK", True)

    tts_provider: str = os.getenv("VOICE_TTS_PROVIDER", "pyttsx3").strip().lower()
    tts_voice: str = os.getenv("VOICE_TTS_VOICE", "").strip()
    tts_rate: int = int(os.getenv("VOICE_TTS_RATE", "180"))
    tts_volume: float = float(os.getenv("VOICE_TTS_VOLUME", "1.0"))
    tts_enabled: bool = _str_bool("VOICE_TTS_ENABLED", True)
    tts_edge_voice: str = os.getenv("VOICE_TTS_EDGE_VOICE", "ko-KR-SunHiNeural")
    tts_edge_rate: str = os.getenv("VOICE_TTS_EDGE_RATE", "+0%")

    wake_phrases: List[str] = field(default_factory=list)
    exit_phrases: List[str] = field(default_factory=list)
    cancel_phrases: List[str] = field(default_factory=list)

    beep_enabled: bool = _str_bool("VOICE_BEEP_ENABLED", True)
    beep_listen_freq: int = int(os.getenv("VOICE_BEEP_LISTEN_FREQ", "1100"))
    beep_listen_dur: int = int(os.getenv("VOICE_BEEP_LISTEN_DUR", "70"))
    beep_heard_freq: int = int(os.getenv("VOICE_BEEP_HEARD_FREQ", "1500"))
    beep_heard_dur: int = int(os.getenv("VOICE_BEEP_HEARD_DUR", "80"))
    beep_speak_freq: int = int(os.getenv("VOICE_BEEP_SPEAK_FREQ", "900"))
    beep_speak_dur: int = int(os.getenv("VOICE_BEEP_SPEAK_DUR", "90"))

    log_path: str = os.getenv("VOICE_LOG_PATH", "").strip()

    agent_command: str = os.getenv("AGENT_COMMAND", "").strip()
    agent_workdir: str = os.getenv("AGENT_WORKDIR", "").strip()
    agent_use_stdin: bool = _str_bool("AGENT_USE_STDIN", False)
    agent_timeout: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))

    use_groq: bool = _str_bool("USE_GROQ", False)
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_system_prompt: str = os.getenv(
        "GROQ_SYSTEM_PROMPT",
        "You are a concise voice assistant. Always respond in Korean. Keep answers short (1-3 sentences).",
    )
    groq_stream: bool = _str_bool("GROQ_STREAM", True)

    use_openai: bool = _str_bool("USE_OPENAI", False)
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_system_prompt: str = os.getenv(
        "OPENAI_SYSTEM_PROMPT",
        "You are a concise voice assistant style CLI agent.",
    )
    openai_stream: bool = _str_bool("OPENAI_STREAM", True)
    openai_stream_print: bool = _str_bool("OPENAI_STREAM_PRINT", True)

    def __post_init__(self) -> None:
        self.exit_phrases = _split_csv("VOICE_EXIT_PHRASES", "종료,끝,quit,exit,그만")
        self.cancel_phrases = _split_csv("VOICE_CANCEL_PHRASES", "취소,cancel,중단")
        self.wake_phrases = _split_csv("VOICE_WAKE_PHRASES", "")

        if self.stt_provider not in {"google", "vosk"}:
            _status("warn", f"VOICE_STT_PROVIDER '{self.stt_provider}' is not supported. Fallback to google.")
            self.stt_provider = "google"

        if self.tts_provider not in {"pyttsx3", "edge", "edge-tts", "off", "none"}:
            _status("warn", f"VOICE_TTS_PROVIDER '{self.tts_provider}' is not supported. Fallback to pyttsx3.")
            self.tts_provider = "pyttsx3"


def _pick_microphone_index(settings: Settings) -> Optional[int]:
    if settings.stt_device_index >= 0:
        try:
            candidate = settings.stt_device_index
            if _can_open_microphone(candidate):
                return candidate
            _status("warn", f"Configured VOICE_INPUT_DEVICE_INDEX={candidate} is not usable.")
        except Exception as exc:
            _status(
                "warn",
                f"VOICE_INPUT_DEVICE_INDEX={settings.stt_device_index} is unavailable. "
                f"Error: {exc}",
            )

    candidates: List[Optional[int]] = [None] + _list_input_device_indices()
    seen: set[Optional[int]] = set()
    for device_index in candidates:
        if device_index in seen:
            continue
        seen.add(device_index)
        if _can_open_microphone(device_index):
            return device_index
        if device_index is None:
            _status("warn", "Default microphone unavailable, trying another device.")
        else:
            _status("warn", f"Microphone index={device_index} unavailable.")

    input_indices = _list_input_device_indices()
    names = _device_names_for_indices(input_indices)
    if names:
        listing = ", ".join(
            f"{idx}:{name or 'unknown'}"
            for idx, name in zip(input_indices, names)
        )
    else:
        listing = "No input device found"
    raise RuntimeError(
        "No usable microphone input found. "
        "Set VOICE_INPUT_DEVICE_INDEX to one of: "
        f"{listing}"
    )


class STTEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._vosk_model = self._load_vosk_model()

    def _load_vosk_model(self) -> Optional[object]:
        if self.settings.stt_provider != "vosk":
            return None
        if _VoskModel is None:
            _status(
                "warn",
                "VOICE_STT_PROVIDER=vosk is set, but vosk is not installed. pip install vosk.",
            )
            return None

        if not self.settings.stt_vosk_model_path:
            _status("warn", "VOICE_VOSK_MODEL_PATH is empty. Using Google STT fallback.")
            return None

        model_path = Path(self.settings.stt_vosk_model_path).expanduser().resolve()
        if not model_path.exists():
            _status("warn", f"Vosk model path not found: {model_path}. Using Google STT fallback.")
            return None

        try:
            return _VoskModel(str(model_path))
        except Exception as exc:
            _status("warn", f"Failed to load Vosk model: {exc}. Using Google STT fallback.")
            return None

    def _recognize_with_vosk(self, audio: "sr.AudioData") -> str:
        if self._vosk_model is None or _VoskKaldiRecognizer is None:
            return ""

        raw_audio = audio.get_raw_data(
            convert_rate=self.settings.stt_vosk_sample_rate,
            convert_width=2,
        )
        try:
            recognizer = _VoskKaldiRecognizer(self._vosk_model, self.settings.stt_vosk_sample_rate)
            if recognizer.AcceptWaveform(raw_audio):
                result = json.loads(recognizer.Result()).get("text", "")
            else:
                result = json.loads(recognizer.FinalResult()).get("text", "")
            text = (result or "").strip()
            if text:
                return text
            return json.loads(recognizer.PartialResult()).get("partial", "").strip()
        except Exception as exc:
            _status("warn", f"Vosk recognition failed: {exc}")
            return ""

    def recognize(self, recognizer: "sr.Recognizer", audio: "sr.AudioData") -> str:
        if self.settings.stt_provider == "vosk" and self._vosk_model is not None:
            text = self._recognize_with_vosk(audio)
            if text:
                return text
            if not self.settings.stt_fallback_to_google:
                return ""
            _status("warn", "Vosk returned empty result. Falling back to Google STT.")

        try:
            return recognizer.recognize_google(audio, language=self.settings.language)
        except sr.UnknownValueError:
            return ""
        except Exception as exc:
            raise RuntimeError(f"STT error: {exc}") from exc


class _AudioPlayer:
    """Stoppable audio player. Plays mp3/wav and can be interrupted mid-playback."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alias: Optional[str] = None
        self._process: Optional[subprocess.Popen] = None

    def play(self, path: str) -> None:
        """Play audio file (blocking). Can be interrupted by calling stop()."""
        if os.name == "nt":
            self._play_mci(path)
        elif sys.platform == "darwin":
            self._play_subprocess(["afplay", path])
        else:
            for cmd in [["ffplay", "-nodisp", "-autoexit"], ["aplay"]]:
                try:
                    self._play_subprocess(cmd + [path])
                    return
                except Exception:
                    continue

    def _play_mci(self, path: str) -> None:
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            alias = "tts_" + uuid.uuid4().hex[:8]
            with self._lock:
                self._alias = alias
            buf = ctypes.create_unicode_buffer(256)
            winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
            winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)
        except Exception:
            pass
        finally:
            with self._lock:
                self._alias = None

    def _play_subprocess(self, cmd: List[str]) -> None:
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self._lock:
                self._process = proc
            proc.wait(timeout=60)
        except Exception:
            pass
        finally:
            with self._lock:
                self._process = None

    def stop(self) -> None:
        """Stop playback immediately."""
        with self._lock:
            # Windows MCI
            if self._alias:
                try:
                    import ctypes
                    winmm = ctypes.windll.winmm
                    winmm.mciSendStringW(f"stop {self._alias}", None, 0, 0)
                    winmm.mciSendStringW(f"close {self._alias}", None, 0, 0)
                except Exception:
                    pass
                self._alias = None
            # subprocess (macOS/Linux)
            if self._process and self._process.poll() is None:
                try:
                    self._process.terminate()
                except Exception:
                    pass
                self._process = None


class TTSEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.enabled = bool(settings.tts_enabled) and settings.tts_provider not in {"off", "none"}
        self._use_edge = False
        self._player = _AudioPlayer()
        self._speaking = False
        self._speak_thread: Optional[threading.Thread] = None
        self._tmp_path: Optional[str] = None

        if not self.enabled:
            return

        # Try edge-tts first (natural voice)
        if settings.tts_provider in {"edge", "edge-tts"}:
            try:
                import edge_tts as _et
                self._use_edge = True
                _status("info", f"TTS: edge-tts ({settings.tts_edge_voice})")
                return
            except ImportError:
                _status("warn", "edge-tts not installed. pip install edge-tts. Falling back to pyttsx3.")

        # Fallback: pyttsx3
        if pyttsx3 is None:
            _status(
                "warn",
                f"pyttsx3 is not installed, so voice output is disabled. Cause: {_PYTTSX3_IMPORT_ERROR}",
            )
            self.enabled = False
            return

        try:
            engine = pyttsx3.init()
            engine.stop()
        except Exception as exc:
            _status("warn", f"pyttsx3 init failed. voice output disabled. Cause: {exc}")
            self.enabled = False

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    def _edge_generate_and_play(self, text: str) -> None:
        """Generate edge-tts audio and play (runs in thread)."""
        import asyncio
        import tempfile

        try:
            import edge_tts
        except ImportError:
            return

        async def _generate():
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_path = tmp.name
            tmp.close()
            self._tmp_path = tmp_path
            communicate = edge_tts.Communicate(
                text,
                voice=self.settings.tts_edge_voice,
                rate=self.settings.tts_edge_rate,
            )
            await communicate.save(tmp_path)
            return tmp_path

        try:
            loop = asyncio.new_event_loop()
            tmp_path = loop.run_until_complete(_generate())
            loop.close()
            if self._speaking:
                self._player.play(tmp_path)
        except Exception as exc:
            _status("warn", f"edge-tts error: {exc}")
        finally:
            self._speaking = False
            if self._tmp_path:
                try:
                    os.unlink(self._tmp_path)
                except Exception:
                    pass
                self._tmp_path = None

    def _pyttsx3_play(self, text: str) -> None:
        """Play using pyttsx3 (runs in thread)."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.settings.tts_rate)
            engine.setProperty("volume", self.settings.tts_volume)
            if self.settings.tts_voice:
                try:
                    voices = engine.getProperty("voices") or []
                    target = self.settings.tts_voice.lower()
                    for v in voices:
                        if target in (v.id or "").lower() or target in (v.name or "").lower():
                            engine.setProperty("voice", v.id)
                            break
                except Exception:
                    pass
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            _status("warn", f"pyttsx3 speak error: {exc}")
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            self._speaking = False

    def speak(self, text: str) -> None:
        """Speak text (blocking). Use speak_async + stop for barge-in."""
        if not self.enabled or not text:
            return
        self._speaking = True
        if self._use_edge:
            self._edge_generate_and_play(text)
        else:
            self._pyttsx3_play(text)

    def speak_async(self, text: str) -> None:
        """Start speaking in background thread (non-blocking)."""
        if not self.enabled or not text:
            return
        self.stop()  # stop any previous playback
        self._speaking = True
        target = self._edge_generate_and_play if self._use_edge else self._pyttsx3_play
        self._speak_thread = threading.Thread(target=target, args=(text,), daemon=True)
        self._speak_thread.start()

    def stop(self) -> None:
        """Interrupt current speech immediately."""
        self._speaking = False
        self._player.stop()
        if self._speak_thread and self._speak_thread.is_alive():
            self._speak_thread.join(timeout=1.0)
        self._speak_thread = None

    def wait(self) -> None:
        """Wait for async speech to finish."""
        if self._speak_thread and self._speak_thread.is_alive():
            self._speak_thread.join()


def _build_cli_args(command_template: str, prompt: str) -> List[str]:
    placeholder = "__VOICE_PROMPT_PLACEHOLDER__"
    has_placeholder = "{prompt}" in command_template
    rendered = command_template.replace("{prompt}", placeholder)
    args = shlex.split(rendered, posix=os.name == "posix")
    if has_placeholder:
        return [placeholder if arg == placeholder else arg for arg in args]
    return args + [prompt]


def _run_cli_agent(prompt: str, settings: Settings) -> str:
    if not settings.agent_command:
        return ""

    try:
        if settings.agent_use_stdin:
            args = shlex.split(settings.agent_command, posix=os.name == "posix")
            executable = args[0] if args else settings.agent_command
            proc = subprocess.run(
                args,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=settings.agent_timeout,
                cwd=settings.agent_workdir or None,
            )
        else:
            args = _build_cli_args(settings.agent_command, prompt)
            args = [prompt if arg == "__VOICE_PROMPT_PLACEHOLDER__" else arg for arg in args]
            executable = args[0] if args else settings.agent_command
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=settings.agent_timeout,
                cwd=settings.agent_workdir or None,
            )
    except FileNotFoundError:
        return f"AGENT_COMMAND not found: {executable}"
    except subprocess.TimeoutExpired:
        return "Agent execution timed out."

    if proc.returncode != 0 and proc.stderr:
        return f"[agent error] {proc.stderr.strip()}"
    return (proc.stdout or "").strip() or "(No output from agent)"


def _fallback_agent_reply(prompt: str) -> str:
    normalized = (prompt or "").strip()
    if not normalized:
        return "입력한 내용이 비어 있습니다."

    lowered = normalized.lower()
    if "시간" in lowered:
        now = datetime.now()
        return f"현재 시간은 {now.strftime('%Y-%m-%d %H:%M:%S')}입니다."

    if "날짜" in lowered:
        now = datetime.now()
        return f"오늘 날짜는 {now.strftime('%Y-%m-%d')}입니다."

    return normalized


def _run_groq_agent(prompt: str, settings: Settings, emit: bool = True) -> str:
    """Call Groq free API (OpenAI-compatible SDK)."""
    try:
        from openai import OpenAI
    except Exception:
        return ""

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return ""

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    messages = [
        {"role": "system", "content": settings.groq_system_prompt},
        {"role": "user", "content": prompt},
    ]

    try:
        if settings.groq_stream:
            chunks: List[str] = []
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=512,
                temperature=0.3,
                stream=True,
            )
            if emit:
                _status("agent", f"groq ({settings.groq_model}):")
                print("> ", end="", flush=True)
            for chunk in response:
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                chunks.append(delta)
                if emit:
                    print(delta, end="", flush=True)
            if emit:
                print()
            return "".join(chunks).strip() or ""
        else:
            response = client.chat.completions.create(
                model=settings.groq_model,
                messages=messages,
                max_tokens=512,
                temperature=0.3,
                stream=False,
            )
            return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        _status("warn", f"Groq API error: {exc}")
        return ""


def _run_openai_agent(prompt: str, settings: Settings, emit: bool = True) -> str:
    try:
        from openai import OpenAI
    except Exception:
        return ""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return ""

    client = OpenAI(api_key=api_key)
    messages = [
        {"role": "system", "content": settings.openai_system_prompt},
        {"role": "user", "content": prompt},
    ]
    if settings.openai_stream:
        chunks: List[str] = []
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            max_tokens=1024,
            temperature=0.2,
            stream=True,
        )
        if emit and settings.openai_stream_print:
            _status("agent", "openai stream:")
            print("> ", end="", flush=True)
        for chunk in response:
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            chunks.append(delta)
            if emit and settings.openai_stream_print:
                print(delta, end="", flush=True)
        if emit and settings.openai_stream_print:
            print()
        return "".join(chunks).strip() or "(No output from OpenAI)"

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        max_tokens=1024,
        temperature=0.2,
        stream=False,
    )
    return (response.choices[0].message.content or "").strip()


def _answer(prompt: str, settings: Settings) -> str:
    # 1) CLI agent (ollama etc.)
    reply = _run_cli_agent(prompt, settings)
    if reply:
        if reply.startswith("No AGENT_COMMAND configured."):
            pass  # silent, try next
        elif reply.startswith("AGENT_COMMAND not found:"):
            _status("warn", reply)
        elif reply == "(No output from agent)":
            _status("warn", "에이전트가 빈 응답을 반환했습니다.")
        elif not reply.startswith("[agent error]"):
            return reply
        else:
            _status("warn", reply)

    # 2) Groq (free)
    if settings.use_groq:
        groq_reply = _run_groq_agent(prompt, settings)
        if groq_reply:
            return groq_reply

    # 3) OpenAI (paid)
    if settings.use_openai:
        openai_reply = _run_openai_agent(prompt, settings, emit=settings.openai_stream_print)
        if openai_reply:
            return openai_reply

    # 4) local fallback
    return _fallback_agent_reply(prompt)


_HELP_TEXT = """사용 가능한 명령어:
  /기록, /history       - 현재 세션 대화 내역 보기
  /지난기록, /sessions  - 지난 세션 목록 보기
  /지난기록 <id>        - 특정 세션 상세 보기
  /도움, /help          - 이 도움말 보기
  종료, 끝, quit, exit  - 프로그램 종료
  취소, cancel          - 현재 동작 취소"""


def _handle_slash_command(payload: str, session: ConversationSession) -> str:
    parts = payload.split(":", 1)
    cmd = parts[0]
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "history":
        return session.current_history_text()
    elif cmd == "sessions":
        if arg:
            return _show_session_detail(arg)
        return _list_past_sessions()
    elif cmd == "help":
        return _HELP_TEXT
    return f"알 수 없는 명령어: {cmd}"


def run_voice(settings: Settings) -> None:
    if sr is None:
        _status("error", "speech_recognition 패키지가 없습니다. requirements를 설치해야 음성 모드가 동작합니다.")
        return

    session = ConversationSession(mode="voice")

    def _fallback_to_text() -> None:
        _status("warn", "음성 입력 장치가 없어 텍스트 모드로 전환합니다.")
        session.finish()
        run_text_mode(settings)

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = settings.pause_threshold
    stt = STTEngine(settings)
    tts = TTSEngine(settings)
    log_path = _resolve_log_path(settings.log_path)

    _status("info", "Voice mode started. Say '종료' to stop.")
    _status("info", f"Session: {session.session_id}")
    if settings.wake_phrases:
        _status("info", f"Wake words required: {', '.join(settings.wake_phrases)}")
    else:
        _status("info", "Wake word is disabled. Any sentence is treated as command.")

    try:
        selected_index = _pick_microphone_index(settings)
    except Exception as exc:
        _status("error", f"Microphone is not available. Install PyAudio and check microphone drivers. Cause: {exc}")
        _fallback_to_text()
        return

    mic_kwargs = {}
    if selected_index is not None:
        mic_kwargs["device_index"] = selected_index
    sample_rate = _default_input_rate(selected_index)
    if sample_rate:
        mic_kwargs["sample_rate"] = sample_rate

    if selected_index is None:
        _status("info", "Microphone selected: default input device")
    else:
        _status("info", f"Microphone selected: device index {selected_index}")

    try:
        source = sr.Microphone(**mic_kwargs)
    except Exception as exc:
        _status("error", f"Failed to initialize microphone. Cause: {exc}")
        _fallback_to_text()
        return

    try:
        with source as source:
            try:
                recognizer.adjust_for_ambient_noise(source, duration=settings.ambient_adjust)
            except Exception as exc:
                _status("warn", f"Failed to calibrate microphone. Cause: {exc}")

            while True:
                _status("listen", "Listening...")
                _play_beep(settings, "listen")

                try:
                    audio = recognizer.listen(
                        source,
                        timeout=settings.listen_timeout,
                        phrase_time_limit=settings.phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    continue
                except Exception as exc:
                    _status("error", f"Microphone listen error: {exc}")
                    _fallback_to_text()
                    return

                try:
                    text = stt.recognize(recognizer, audio)
                except RuntimeError as exc:
                    _status("error", str(exc))
                    continue

                if not text:
                    _status("warn", "Could not recognize speech. Try again.")
                    continue

                _play_beep(settings, "heard")
                _status("heard", f"user: {text}")

                action, payload = _resolve_user_input(text, settings)
                if action == "exit":
                    tts.stop()
                    _status("info", "Exit keyword detected. Bye.")
                    break
                if action == "slash":
                    result = _handle_slash_command(payload, session)
                    _status("info", result)
                    tts.speak(result)
                    continue
                if action == "cancel":
                    tts.stop()
                    _status("info", f"Cancel keyword detected: {payload}")
                    continue
                if action == "ignore":
                    _status(
                        "info",
                        "Wake word missing; message ignored. Example: '에이전트 ...'",
                    )
                    _write_log(log_path, "voice", text, "ignore", "", "")
                    continue
                if not payload:
                    continue

                _status("agent", "Running agent...")
                reply = _answer(payload, settings)
                session.add_turn(text, reply)
                _write_log(log_path, "voice", text, "command", payload, reply)
                _status("agent", f"reply: {reply}")
                _play_beep(settings, "speak")

                # --- Barge-in: speak async, listen while speaking ---
                tts.speak_async(reply)

                # Listen for interruption while TTS is playing
                while tts.is_speaking:
                    try:
                        barge_audio = recognizer.listen(
                            source,
                            timeout=1.0,
                            phrase_time_limit=settings.phrase_time_limit,
                        )
                    except sr.WaitTimeoutError:
                        continue
                    except Exception:
                        break

                    try:
                        barge_text = stt.recognize(recognizer, barge_audio)
                    except Exception:
                        continue

                    if not barge_text:
                        continue

                    # User spoke! Stop TTS and process the new input
                    tts.stop()
                    _play_beep(settings, "heard")
                    _status("heard", f"user (barge-in): {barge_text}")

                    barge_action, barge_payload = _resolve_user_input(barge_text, settings)
                    if barge_action == "exit":
                        _status("info", "Exit keyword detected. Bye.")
                        session.finish()
                        print(session.summary_text())
                        return
                    if barge_action == "cancel":
                        _status("info", f"Cancel keyword detected: {barge_payload}")
                        break
                    if barge_action == "slash":
                        result = _handle_slash_command(barge_payload, session)
                        _status("info", result)
                        break
                    if barge_action == "ignore" or not barge_payload:
                        break

                    _status("agent", "Running agent...")
                    barge_reply = _answer(barge_payload, settings)
                    session.add_turn(barge_text, barge_reply)
                    _write_log(log_path, "voice", barge_text, "command", barge_payload, barge_reply)
                    _status("agent", f"reply: {barge_reply}")
                    _play_beep(settings, "speak")
                    tts.speak_async(barge_reply)
                    # continue listening for more barge-ins
    except Exception as exc:
        _status("error", f"Microphone runtime error. Cause: {exc}")
        _fallback_to_text()

    session.finish()
    print(session.summary_text())


def run_text_mode(settings: Settings) -> None:
    session = ConversationSession(mode="text")
    tts = TTSEngine(settings)
    log_path = _resolve_log_path(settings.log_path)
    _status("info", "Text mode. Type '종료' to stop. Type '/도움' for commands.")
    _status("info", f"Session: {session.session_id}")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            _status("warn", "stdin closed. stopping text mode.")
            break
        action, payload = _resolve_user_input(text, settings)

        if action == "exit":
            break
        if action == "slash":
            result = _handle_slash_command(payload, session)
            print(result)
            continue
        if action == "cancel":
            _status("info", f"Cancel keyword detected: {payload}")
            _write_log(log_path, "text", text, "cancel", payload, "")
            continue
        if action == "ignore":
            if settings.wake_phrases:
                _status("info", "Wake word missing; message ignored.")
            _write_log(log_path, "text", text, "ignore", "", "")
            continue
        if not payload:
            _write_log(log_path, "text", text, "empty", "", "")
            continue

        reply = _answer(payload, settings)
        session.add_turn(text, reply)
        _write_log(log_path, "text", text, "command", payload, reply)
        if not (settings.use_openai and settings.openai_stream and settings.openai_stream_print):
            print(reply)
        tts.speak(reply)

    session.finish()
    print(session.summary_text())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Voice CLI Agent")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Use text input instead of microphone",
    )
    parser.add_argument(
        "--workdir",
        default=None,
        help="Override AGENT_WORKDIR",
    )
    parser.add_argument(
        "--stt-provider",
        choices=["google", "vosk"],
        default=None,
        help="Set STT provider for this run only",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        const="__list__",
        default=None,
        metavar="SESSION_ID",
        help="View past sessions. Optionally pass a session ID for detail.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    settings = Settings()
    args = parse_args()

    if args.history is not None:
        if args.history == "__list__":
            print(_list_past_sessions(limit=20))
        else:
            print(_show_session_detail(args.history))
        return

    if args.workdir:
        settings.agent_workdir = str(Path(args.workdir).expanduser().resolve())
    if args.stt_provider:
        settings.stt_provider = args.stt_provider

    if args.text:
        run_text_mode(settings)
    else:
        run_voice(settings)


if __name__ == "__main__":
    main()
