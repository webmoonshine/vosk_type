#!/usr/bin/env python3
"""
Vosk Voice Typing — печатай голосом в любой программе.
────────────────────────────────────────────────────
Нажми и удерживай ПРАВЫЙ CTRL → говори в микрофон
Отпусти — распознанный текст напечатается в активном окне
           (через буфер обмена + Ctrl+V — работает с любой раскладкой!)

Esc — выход из программы.
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time

from vosk import Model, KaldiRecognizer
from pynput import keyboard


# ─── НАСТРОЙКИ ───────────────────────────────────────────────────────────────

HOTKEY = keyboard.Key.ctrl_r       # Клавиша push-to-talk
MODEL_PATH = "vosk-model-ru-0.42"    # Папка с моделью
SAMPLE_RATE = 16000                # Vosk работает на 16 кГц

# ─── X11 CLIPBOARD ───────────────────────────────────────────────────────────




# ─── ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ────────────────────────────────────────────────────

model = Model(MODEL_PATH)
recording = False
recognized_text = ""
rec_process = None        # subprocess pw-record
reader_thread = None      # поток читающий из pw-record


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
    """Запускает pw-record с выводом PCM в stdout."""
    global rec_process
    cmd = [
        "pw-record",
        "--format=s16",
        f"--rate={SAMPLE_RATE}",
        "--channels=1",
        "--latency=100",
        f"--target={SOURCE_NAME}",
        "-",
    ]
    rec_process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
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


# ─── РАСПОЗНАВАНИЕ ───────────────────────────────────────────────────────────

def recognition_worker():
    """Фоновый поток: читает PCM из пайпа pw-record и отдаёт Vosk."""
    global recognized_text, rec_process, recording

    rec = KaldiRecognizer(model, SAMPLE_RATE)
    rec.SetWords(False)

    BUFFER_SIZE = 8000  # сэмплов

    while recording and rec_process is not None and rec_process.stdout is not None:
        try:
            data = rec_process.stdout.read(BUFFER_SIZE * 2)  # 16-bit = 2 байта
            if not data:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    recognized_text += result["text"] + " "
            else:
                partial = json.loads(rec.PartialResult())
                if partial.get("partial"):
                    # Используем пробелы чтобы затереть предыдущую строку
                    print(f"  💬 {partial['partial']:<50}", end="\r", file=sys.stderr)
        except Exception as e:
            if recording:
                print(f"⚠️  Ошибка чтения: {e}", file=sys.stderr)
            break

    # Финальный остаток — читаем всё что осталось в пайпе
    remaining = b""
    try:
        while True:
            chunk = rec_process.stdout.read(16000 * 2)
            if not chunk:
                break
            remaining += chunk
    except Exception:
        pass

    if remaining:
        rec.AcceptWaveform(remaining)

    final = json.loads(rec.FinalResult())
    if final.get("text"):
        recognized_text += final["text"]

    recognized_text = recognized_text.strip()
    recognized_text = restore_punctuation(recognized_text)


# ─── ПУНКТУАЦИЯ ──────────────────────────────────────────────────────────────

def restore_punctuation(text: str) -> str:
    """Восстанавливает базовые знаки препинания эвристиками."""
    if not text:
        return text

    # Слова-маркеры конца предложения
    end_words = {
        "да", "нет", "так", "вот", "ага", "ну", "ладно",
        "пожалуйста", "спасибо", "окей", "хорошо", "конечно",
        "стоп", "хватит", "готово", "понятно", "ясно",
        "именно", "верно", "правильно",
    }

    question_words = {
        "что", "кто", "где", "когда", "куда", "откуда",
        "почему", "зачем", "как", "сколько", "какой",
        "какая", "какие", "какое", "чей", "чья", "чьё",
        "неужели", "разве", "ли",
    }

    words = text.split()
    if not words:
        return text

    result = []
    sentence_start = True

    for i, word in enumerate(words):
        is_first_word = (i == 0) or sentence_start
        is_last_word = (i == len(words) - 1)
        prev_word = words[i - 1].lower().strip("«»\"'.,!?-:;") if i > 0 else ""

        # Первое слово предложения — с заглавной
        if sentence_start:
            word = word.capitalize()
            sentence_start = False

        word_lower = word.lower().strip("«»\"'.,!?-:;")

        # Вопросительное предложение
        if word_lower in question_words and (is_last_word or is_first_word):
            question = True
            for j in range(i, len(words)):
                w = words[j].lower().strip("«»\"'.,!?-:;")
                if w in question_words or w == "?":
                    continue
                if w in end_words:
                    question = False
                    break

        # Точка после слов-маркеров
        if word_lower in end_words and not is_last_word:
            word = word + "."
            sentence_start = True

        result.append(word)

    # Последнее слово — точка
    last = result[-1]
    if not last[-1] in ".!?":
        result[-1] = last + "."

    # Объединяем и чистим двойные знаки
    text = " ".join(result)
    text = text.replace("..", ".")
    text = text.replace(". .", ".")

    return text


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
    """Эмулирует Ctrl+V через pynput (Latin клавиши работают в любой раскладке)."""
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
    global recording, recognized_text, reader_thread

    if key == HOTKEY and not recording:
        recording = True
        recognized_text = ""

        print(f"\n🎙️  ЗАПИСЬ… (отпустите Правый Ctrl)", file=sys.stderr)

        start_recording()

        reader_thread = threading.Thread(target=recognition_worker, daemon=True)
        reader_thread.start()


def on_release(key):
    global recording, recognized_text, reader_thread

    if key == HOTKEY and recording:
        recording = False

        # 1. Даём пайпу дописаться до распознавателя
        time.sleep(0.3)

        # 2. Закрываем пайп со стороны pw-record (останавливаем процесс)
        stop_recording()

        # 3. Ждём завершения потока распознавания
        if reader_thread is not None:
            reader_thread.join(timeout=5)

        if recognized_text:
            print(f"\n📝 Распознано: «{recognized_text}»", file=sys.stderr)
            type_text(recognized_text)
        else:
            print(f"\n⚠️  Ничего не распознано (тишина?)", file=sys.stderr)

    # Esc — выход
    if key == keyboard.Key.esc:
        print("\n👋 Выход по Esc.", file=sys.stderr)
        os.kill(os.getpid(), signal.SIGTERM)


# ─── ГЛАВНАЯ ─────────────────────────────────────────────────────────────────

def print_banner():
    print(f"""
╔══════════════════════════════════════════════════════╗
║        🎤  VOSK VOICE TYPING  🎤                      ║
║                                                      ║
║  Нажми и УДЕРЖИВАЙ ПРАВЫЙ CTRL → говори в микрофон   ║
║  Отпусти → текст появится в активном окне             ║
║                                                      ║
║  📋 Текст вставляется через буфер обмена (Ctrl+V)     ║
║     — работает с любой раскладкой клавиатуры!         ║
║                                                      ║
║  🎧 Bluetooth-гарнитура подключается автоматически     ║
║  Esc — выход                                         ║
╚══════════════════════════════════════════════════════╝
""", file=sys.stderr)


def main():
    global SOURCE_NAME
    print_banner()

    SOURCE_NAME = find_best_source()
    if SOURCE_NAME is None:
        print("❌ Не удалось определить источник аудио.", file=sys.stderr)
        sys.exit(1)

    print(file=sys.stderr)
    print("⏳ Ожидание нажатия Правого Ctrl…", file=sys.stderr)

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    listener.join()


if __name__ == "__main__":
    main()