# 🎤 Voice Typing — печатай голосом в любой программе

Нажми и удерживай **Правый Ctrl** → говори в микрофон → отпусти — текст появится в активном окне.

Работает в **любой программе**: браузер, текстовый редактор, терминал, чат, IDE.

---

## 🚀 Два варианта

| | `voice_typing.py` (Vosk) | `voice_typing_whisper.py` (faster-whisper) |
|---|---|---|
| **Скорость** | ⚡ Мгновенно (0.1–2 сек) | ~1–3 сек после отпускания |
| **Точность** | Средняя / Высокая (зависит от модели) | Очень высокая |
| **Streaming** | ✅ Частичные результаты в реальном времени | ❌ Только после полной записи |
| **ОЗУ** | ~300 МБ – 2 ГБ | ~300 МБ – 2 ГБ |

**Vosk** — для быстрого ввода (push-to-talk без задержки)  
**Whisper** — когда точность важнее скорости

---

## 🔧 Установка (общая часть)

### 1. Системные зависимости

```bash
sudo apt update
sudo apt install -y python3 python3-venv xclip pipewire-audio
```

- `python3` — среда выполнения
- `xclip` — работа с буфером обмена (копирование русского текста)
- `pipewire-audio` — звуковая подсистема (обычно уже есть)

### 2. Виртуальное окружение

```bash
cd ~/HarnessTest
python3 -m venv vosk-env
source vosk-env/bin/activate
```

---

## 📦 Вариант 1 — Vosk

### Установка

```bash
# Модель
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip

# Пакеты
pip install vosk pynput
```

### Запуск

```bash
source vosk-env/bin/activate
python3 voice_typing.py
```

### Смена модели Vosk

| Модель | Размер | Точность (WER) |
|---|---|---|
| `vosk-model-small-ru-0.22` | 45 МБ | ~22% |
| `vosk-model-ru-0.22` | 1.5 ГБ | ~13% |
| `vosk-model-ru-0.42` | 1.8 ГБ | ~11% |

Скачать большую модель и указать в скрипте `MODEL_PATH = "vosk-model-ru-0.42"`.

---

## 📦 Вариант 2 — faster-whisper

### Установка

```bash
source vosk-env/bin/activate
pip install faster-whisper pynput

# Модель скачается автоматически при первом запуске (base — 74 МБ)
```

### Запуск

```bash
source vosk-env/bin/activate
python3 voice_typing_whisper.py
```

### Настройки Whisper

В начале файла `voice_typing_whisper.py`:

```python
WHISPER_MODEL = "base"        # tiny / base / small / medium / large-v3
DEVICE = "cpu"                # cpu или cuda (GPU)
COMPUTE_TYPE = "int8"         # int8 / float16 / float32
```

**Модели (чем больше — тем точнее, но медленнее):**

| Модель | Размер | Задержка на i5-3470 |
|---|---|---|
| `tiny` | 39 МБ | ~1 сек |
| `base` | 74 МБ | ~1–2 сек |
| `small` | 244 МБ | ~2–3 сек |
| `medium` | 769 МБ | ~5–8 сек |
| `large-v3` | 3.1 ГБ | ~15+ сек |

Рекомендуется начать с **`base`** — оптимальный баланс на старых CPU.

---

## 🎯 Использование (для обоих вариантов)

| Действие | Результат |
|---|---|
| Нажать и **держать** Правый Ctrl | 🎙️ Начинается запись с микрофона |
| **Говорить** в микрофон | 💬 Промежуточные результаты в терминале |
| **Отпустить** Правый Ctrl | 📝 Текст вставляется в активное окно |
| Нажать **Esc** | Выход из программы |

### Как это работает

```
Голос → pw-record (PipeWire) → Vosk/Whisper → xclip (буфер обмена) → Ctrl+V → активное окно
```

Текст вставляется через **буфер обмена + Ctrl+V** — работает с любой раскладкой клавиатуры.

### 🖊️ Пунктуация

Скрипт автоматически расставляет знаки препинания эвристиками:
- Точка после слов-маркеров (да, нет, ладно, спасибо, стоп и т.д.)
- Заглавная буква в начале предложения
- Точка в конце каждой фразы

Эвристики работают мгновенно, без ML-модели и без зависимостей.

---

## ⚙️ Общие настройки

### Другие варианты клавиш

```python
HOTKEY = keyboard.Key.scroll_lock   # Scroll Lock
HOTKEY = keyboard.Key.alt_gr        # Правый Alt
HOTKEY = keyboard.Key.ctrl_l        # Левый Ctrl (осторожно: перехватит все Ctrl)
HOTKEY = keyboard.Key.pause         # Pause/Break
```

---

## 🛠 Устранение проблем

| Проблема | Решение |
|---|---|
| `ModuleNotFoundError: No module named ...` | Не активировано окружение: `source vosk-env/bin/activate` |
| Не определяется микрофон | Проверь список: `pactl list sources short` |
| Текст приходит кракозябрами (`GHJDTHRF...`) | Установлен ли `xclip`? Проверь: `which xclip` |
| Ничего не вставляется в окно | Запусти скрипт из обычного терминала (не из IDE) |
| Bluetooth-гарнитура не видна | Подключи через настройки системы |
| Хочу автозапуск | Создай systemd unit (см. ниже) |

### Автозапуск с системой

Создай файл `~/.config/systemd/user/vosk-typing.service`:

```
[Unit]
Description=Voice Typing
After=graphical-session.target

[Service]
ExecStart=/home/dvt/HarnessTest/vosk-env/bin/python3 /home/dvt/HarnessTest/voice_typing.py
WorkingDirectory=/home/dvt/HarnessTest
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable vosk-typing.service
systemctl --user start vosk-typing.service
```

---

## 📦 Состав проекта

| Файл | Назначение |
|---|---|
| `voice_typing.py` | Скрипт с **Vosk** (быстрый) |
| `voice_typing_whisper.py` | Скрипт с **faster-whisper** (точный) |
| `vosk-env/` | Виртуальное окружение Python |
| `vosk-model-*/` | Модели распознавания (скачиваются отдельно) |
| `README.md` | Эта инструкция |

---

## 📜 Лицензия

Vosk — Apache 2.0. faster-whisper — MIT. Скрипты — открытый исходный код.