#!/usr/bin/env python3
"""
Vosk Voice Typing — печатай голосом в любой программе.
────────────────────────────────────────────────────
Нажми и удерживай ПРАВЫЙ CTRL → говори в микрофон
Отпусти — распознанный текст напечатается в активном окне
           (через буфер обмена + Ctrl+V — работает с любой раскладкой!)

Esc — выход из программы.

Движок: faster-whisper
  Модели (чем больше — тем точнее, но медленнее):
    tiny   39 MB  — ⚡ очень быстро, но с ошибками
    base   74 MB  — быстро и приемлемо  ← рекомендую начать с этой
    small 244 MB  — хороший баланс
    medium 769 MB — хорошо, но медленно на старых CPU
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from faster_whisper import WhisperModel
from pynput import keyboard


# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────

HOTKEY = keyboard.Key.ctrl_r        # Клавиша push-to-talk
WHISPER_MODEL = "small"             # tiny / base / small / medium / large-v3
DEVICE = "cpu"                      # cpu или cuda
COMPUTE_TYPE = "int8"               # int8 / float16 / float32 (int8 быстрее на CPU)
LANGUAGE = "ru"                     # язык распознавания

# ─── ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ────────────────────────────────────────────────────

model = None
rec_process = None
recording = False
recognized_text = ""
TEMP_DIR = Path(tempfile.mkdtemp(prefix="whisper_dictation_"))
TEMP_WAV = TEMP_DIR / "recording.wav"


# ─── ЗАГРУЗКА МОДЕЛИ ─────────────────────────────────────────────────────────

def load_model():
    """Загружает модель faster-whisper."""
    global model
    print(f"⏳ Загрузка модели {WHISPER_MODEL} ({DEVICE}, {COMPUTE_TYPE})…",
          file=sys.stderr)
    model = WhisperModel(
        WHISPER_MODEL,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=4,
        num_workers=1,
    )
    print(f"✅ Модель {WHISPER_MODEL} загружена!", file=sys.stderr)


# ─── ПОИСК МИКРОФОНА ─────────────────────────────────────────────────────────

def get_audio_sources():
    """Возвращает список источников через pactl."""
    try:
        result = subprocess.run(
            ["pactl", "list", "sources", "short"],
            capture_output=True, text=True, timeout=3
        )
        sources = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                sources.append({"index": parts[0], "name": parts[1]})
        return sources
    except Exception as e:
        print(f"⚠️  Ошибка pactl: {e}", file=sys.stderr)
        return []


def find_best_source():
    """Находит лучший источник: Bluetooth → встроенный → любой."""
    sources = get_audio_sources()

    if not sources:
        print("❌ Не найдено аудиоисточников!", file=sys.stderr)
        return None

    print("📢 Доступные источники:", file=sys.stderr)
    bt_source = None
    analog_source = None
    first_source = None

    for src in sources:
        name = src["name"]
        print(f"    [{src['index']}] {name}", file=sys.stderr)
        if first_source is None:
            first_source = name
        if "bluez_input" in name:
            bt_source = name
            print(f"       └─ 🎧 Bluetooth-гарнитура!", file=sys.stderr)
        elif "analog-stereo" in name and "input" in name:
            analog_source = name

    chosen = bt_source or analog_source or first_source
    print(f"✅ Выбран источник: {chosen}", file=sys.stderr)
    return chosen


# ─── ЗАХВАТ АУДИО ────────────────────────────────────────────────────────────

SOURCE_NAME = None


def start_recording():
    """Запускает pw-record, пишет WAV-файл (16кГц, моно, s16)."""
    global rec_process
    cmd = [
        "pw-record",
        "--format=s16",
        "--rate=16000",
        "--channels=1",
        "--latency=100",
        f"--target={SOURCE_NAME}",
        str(TEMP_WAV),
    ]
    rec_process = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def stop_recording():
    """Останавливает pw-record."""
    global rec_process
    if rec_process is not None:
        rec_process.terminate()
        try:
            rec_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            rec_process.kill()
        rec_process = None

    # Ждём, пока файл допишется
    time.sleep(0.3)


# ─── РАСПОЗНАВАНИЕ ───────────────────────────────────────────────────────────

def transcribe():
    """Распознаёт записанный WAV через faster-whisper."""
    global recognized_text

    if not TEMP_WAV.exists() or TEMP_WAV.stat().st_size < 1000:
        print("⚠️  Слишком короткая запись, пропускаю", file=sys.stderr)
        return

    file_size = TEMP_WAV.stat().st_size
    print(f"📦 Файл: {file_size // 1024} КБ", file=sys.stderr)

    try:
        segments, info = model.transcribe(
            str(TEMP_WAV),
            language=LANGUAGE,
            beam_size=3,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.5,
                min_speech_duration_ms=300,
                min_silence_duration_ms=800,
            ),
        )

        # Собираем текст
        texts = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                texts.append(text)
                print(f"  💬 [{seg.start:.1f}s-{seg.end:.1f}s] {text}",
                      file=sys.stderr)

        recognized_text = " ".join(texts)

    except Exception as e:
        print(f"⚠️  Ошибка распознавания: {e}", file=sys.stderr)

    # Удаляем временный файл
    try:
        TEMP_WAV.unlink(missing_ok=True)
    except Exception:
        pass


# ─── ВВОД ТЕКСТА ─────────────────────────────────────────────────────────────

def copy_to_clipboard(text: str) -> bool:
    """Копирует текст в буфер обмена через xclip."""
    try:
        p = subprocess.Popen(
            ["xclip", "-selection", "clipboard"],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        p.communicate(text.encode("utf-8"), timeout=3)
        return p.returncode == 0
    except Exception as e:
        print(f"⚠️  Ошибка xclip: {e}", file=sys.stderr)
        return False


def paste_via_pynput():
    """Эмулирует Ctrl+V через pynput (Latin клавиши — в любой раскладке)."""
    ctrl = keyboard.Controller()
    ctrl.press(keyboard.Key.ctrl)
    ctrl.press("v")
    ctrl.release("v")
    ctrl.release(keyboard.Key.ctrl)


def type_text(text: str):
    """Копирует текст в буфер и вставляет через Ctrl+V."""
    if not text:
        return

    print(f"📋 Копирую в буфер обмена…", file=sys.stderr)
    ok = copy_to_clipboard(text)
    if not ok:
        print("⚠️  Не удалось скопировать в буфер обмена!", file=sys.stderr)
        return

    time.sleep(0.15)
    print(f"✍️  Ctrl+V ({len(text)} символов)…", file=sys.stderr)
    paste_via_pynput()
    print(f"✅ Готово!", file=sys.stderr)


# ─── ГОРЯЧИЕ КЛАВИШИ ─────────────────────────────────────────────────────────

def on_press(key):
    global recording, recognized_text

    if key == HOTKEY and not recording:
        recording = True
        recognized_text = ""
        print(f"\n🎙️  ЗАПИСЬ… (отпустите Правый Ctrl)", file=sys.stderr)
        start_recording()


def on_release(key):
    global recording, recognized_text

    if key == HOTKEY and recording:
        recording = False
        print(f"\n⏳ Останавливаю запись…", file=sys.stderr)

        stop_recording()
        print(f"🔊 Распознаю через Whisper…", file=sys.stderr)

        start_time = time.time()
        transcribe()
        elapsed = time.time() - start_time

        if recognized_text:
            print(f"📝 Распознано за {elapsed:.1f}с: «{recognized_text}»",
                  file=sys.stderr)
            type_text(recognized_text)
        else:
            print(f"⚠️  Ничего не распознано (тишина?) за {elapsed:.1f}с",
                  file=sys.stderr)

    if key == keyboard.Key.esc:
        print("\n👋 Выход по Esc.", file=sys.stderr)
        os.kill(os.getpid(), signal.SIGTERM)


# ─── ГЛАВНАЯ ─────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
╔══════════════════════════════════════════════════════╗
║     🎤  VOICE TYPING — faster-whisper  🎤             ║
║                                                      ║
║  Нажми и УДЕРЖИВАЙ ПРАВЫЙ CTRL → говори в микрофон   ║
║  Отпусти → текст появится в активном окне             ║
║                                                      ║
║  Модель: {WHISPER_MODEL} / Язык: {LANGUAGE}                 ║
║  📋 Вставка через буфер обмена (Ctrl+V)               ║
║  🎧 Bluetooth-гарнитура: автоматически                ║
║  Esc — выход                                         ║
╚══════════════════════════════════════════════════════╝
""", file=sys.stderr)


def cleanup():
    """Удаляет временные файлы."""
    try:
        TEMP_WAV.unlink(missing_ok=True)
        TEMP_DIR.rmdir()
    except Exception:
        pass


def main():
    global SOURCE_NAME
    print_banner()

    SOURCE_NAME = find_best_source()
    if SOURCE_NAME is None:
        print("❌ Не удалось определить источник аудио.", file=sys.stderr)
        sys.exit(1)

    load_model()

    print(file=sys.stderr)
    print("⏳ Ожидание нажатия Правого Ctrl…", file=sys.stderr)

    try:
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        listener.join()
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()