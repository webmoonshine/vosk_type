# 🎤 Vosk Voice Typing — печатай голосом в любой программе

Нажми и удерживай **Правый Ctrl** → говори в микрофон → отпусти — текст появится в активном окне.

Работает в **любой программе**: браузер, текстовый редактор, терминал, чат, IDE.

---

## 🔧 Установка

### 1. Системные зависимости

```bash
sudo apt update
sudo apt install -y python3 python3-venv xclip pipewire-audio
```

- `python3` — среда выполнения
- `python3-venv` — виртуальное окружение Python
- `xclip` — работа с буфером обмена (копирование русского текста)
- `pipewire-audio` — звуковая подсистема (обычно уже есть)

### 2. Модель распознавания

Скачай русскую модель Vosk:

```bash
cd ~/HarnessTest

# Маленькая (42 МБ) — быстро, но с ошибками
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip

# ИЛИ побольше (1.5 ГБ) — точнее:
# wget https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip
# unzip vosk-model-ru-0.42.zip
```

### 3. Виртуальное окружение и Python-пакеты

```bash
cd ~/HarnessTest
python3 -m venv vosk-env
source vosk-env/bin/activate
pip install vosk pynput
```

- `vosk` — движок распознавания речи
- `pynput` — горячие клавиши и эмуляция ввода (Ctrl+V)

### 4. Скрипт

Скопируй файл **`voice_typing.py`** из этой папки или создай его.

---

## 🚀 Запуск

```bash
cd ~/HarnessTest
source vosk-env/bin/activate
python3 voice_typing.py
```

Терминал **должен оставаться открытым** — в нём живёт процесс, слушающий клавиши.

Увидишь баннер и список микрофонов:
```
📢 Доступные источники:
    [51] alsa_input.pci-0000_00_1b.0.analog-stereo
    [245602] bluez_input.CB_10_0A_7A_B2_C4.0
       └─ 🎧 Bluetooth-гарнитура!
✅ Выбран источник: bluez_input.CB_10_0A_7A_B2_C4.0

⏳ Ожидание нажатия Правого Ctrl…
```

---

## 🎯 Использование

| Действие | Результат |
|---|---|
| Нажать и **держать** Правый Ctrl | 🎙️ Начинается запись с микрофона |
| **Говорить** в микрофон | 💬 Промежуточные результаты в терминале |
| **Отпустить** Правый Ctrl | 📝 Текст распознаётся → копируется в буфер → вставляется Ctrl+V |
| Нажать **Esc** | Выход из программы |

### Как это работает

```
Голос → pw-record (PipeWire) → Vosk (распознавание) → xclip (буфер обмена) → pynput Ctrl+V → активное окно
```

Текст вставляется через **буфер обмена + Ctrl+V**, поэтому он всегда корректный, независимо от раскладки клавиатуры в целевой программе.

---

## ⚙️ Настройки

В начале файла `voice_typing.py`:

```python
HOTKEY = keyboard.Key.ctrl_r    # Клавиша push-to-talk
MODEL_PATH = "vosk-model-small-ru-0.22"  # Папка с моделью
SAMPLE_RATE = 16000             # Частота дискретизации
```

### Другие варианты клавиш

```python
HOTKEY = keyboard.Key.scroll_lock   # Scroll Lock
HOTKEY = keyboard.Key.alt_gr        # Правый Alt
HOTKEY = keyboard.Key.ctrl_l        # Левый Ctrl (осторожно: перехватит все Ctrl)
HOTKEY = keyboard.Key.pause         # Pause/Break
```

### Смена модели

Если скачал большую модель, поменяй в скрипте:

```python
MODEL_PATH = "vosk-model-ru-0.42"
```

---

## 🛠 Устранение проблем

| Проблема | Решение |
|---|---|
| `ModuleNotFoundError: No module named 'vosk'` | Не активировано окружение. Выполни: `source vosk-env/bin/activate` |
| Не определяется микрофон | Проверь список: `pactl list sources short` |
| Не слышно речь | Настрой громкость: `pavucontrol` → вкладка "Запись" |
| Текст приходит кракозябрами (`GHJDTHRF...`) | Установлен ли `xclip`? Проверь: `which xclip` |
| Ничего не вставляется в окно | Попробуй запустить скрипт из обычного терминала (не из IDE) |
| Bluetooth-гарнитура не видна | Подключи через `bluetoothctl` или настройки системы |
| Хочу смену языка | В скрипте поменяй `HOTKEY` на удобную клавишу |
| Хочу автозапуск | Создай Desktop Entry или systemd unit (см. ниже) |

### Автозапуск с системой

Создай файл `~/.config/systemd/user/vosk-typing.service`:

```
[Unit]
Description=Vosk Voice Typing
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
| `voice_typing.py` | Основной скрипт голосового ввода |
| `vosk-env/` | Виртуальное окружение Python (создаётся при установке) |
| `vosk-model-small-ru-0.22/` | Модель распознавания русской речи |
| `README.md` | Эта инструкция |

---

## 📜 Лицензия

Vosk распространяется под Apache 2.0. Скрипт — открытый исходный код.