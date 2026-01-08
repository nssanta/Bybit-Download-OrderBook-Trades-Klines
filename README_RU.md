# Bybit Market Data Downloader

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bybit](https://img.shields.io/badge/Exchange-Bybit-orange.svg)](https://www.bybit.com/)

CLI-инструменты для скачивания исторических **Spot** данных с Bybit. API ключи не нужны.

[Русская версия](README_RU.md) | [English](README.md)

---

## 🚀 Возможности

- **📊 Order Book** — 200 уровней, обновление 200мс
- **💹 Trades** — Тиковые данные сделок
- **📈 Klines** — Spot и Futures через API v5
- **🗜️ Parquet Streaming** — Скачивание и конвертация за один шаг, экономия ~22% места
- **🔒 Атомарная запись** — Защита от прерываний
- **🔄 Retry** — Устойчивость к сбоям сети
- **💾 Защита диска** — Автоостановка при нехватке места

## 📦 Установка

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Использование

### Order Book (Streaming — Рекомендуется)
Скачивание и конвертация в Parquet за один шаг. Экономит ~22% места.

```bash
# Один символ (рекомендуется: 3 воркера, 10с задержка)
python scripts/download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31 --workers 3 --stagger 10

# Несколько символов
python scripts/download_orderbook_stream.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --start-date 2025-05-01 --end-date 2025-05-31 --workers 3

# С порогом свободного места (остановка если < 100 ГБ)
python scripts/download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-12-31 --min-disk 100
```

**Флаги:**
- `--workers N` — параллельных загрузок (рекомендуется: 3-5, больше может вызвать таймауты)
- `--stagger N` — случайная задержка 0-N секунд перед стартом каждого воркера
- `--min-disk N` — остановка если места на диске меньше N ГБ

### Order Book (Legacy — только ZIP)
Скачивание ZIP архивов без конвертации.

```bash
python scripts/download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Конвертация ZIP в Parquet
Конвертация ранее скачанных ZIP архивов.

```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

### Скачать Trades
```bash
python scripts/download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Klines (API)
Скачивание Spot или Futures свечей через API.

```bash
# Spot Market
python scripts/download_klines.py BTCUSDT --source spot --start-date 2025-01-01 --end-date 2025-01-31 --interval 1

# Futures Market
python scripts/download_klines.py BTCUSDT --source linear --start-date 2025-01-01 --end-date 2025-01-31 --interval 60
```

## 📁 Структура данных

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/      # ZIP архивы (legacy)
│   └── trades/BTCUSDT/         # CSV.gz файлы
├── parquet/
│   └── orderbook/BTCUSDT/      # Parquet файлы (рекомендуется)
└── klines/
    ├── spot/BTCUSDT/           # Spot свечи
    └── futures/BTCUSDT/        # Futures свечи
```

## 📋 Форматы и размеры данных

| Тип | Источник | Сырой формат | Parquet | Размер/день |
|-----|----------|--------------|---------|-------------|
| Order Book | quote-saver.bycsi.com | ZIP (JSON, 450 МБ) | ZSTD (~65 МБ) | **65-100 МБ** |
| Trades | public.bybit.com/spot | CSV.gz | — | ~5-50 МБ |
| Klines | Bybit API v5 | — | ZSTD | ~1-5 МБ |

### Схема Order Book Parquet

| Колонка | Тип | Описание |
|---------|-----|----------|
| ts | int64 | Серверный timestamp (мс) |
| cts | int64 | Клиентский timestamp (мс) |
| type | string | `snapshot` или `delta` |
| u | int64 | Update ID |
| seq | int64 | Порядковый номер |
| bids | string | JSON массив `[["price", "qty"], ...]` |
| asks | string | JSON массив `[["price", "qty"], ...]` |

## ⏰ Доступность данных

| Тип данных | Доступно с |
|------------|------------|
| Order Book | Май 2025 |
| Trades | 2020 |

## ⚠️ Важные замечания

- **Используй Streaming для Order Book**: `download_orderbook_stream.py` — экономит ~22% места.
- **Внимание к размерам**: Order Book данные большие! ~65-100 МБ/день = **~24-36 ГБ/год** на символ.
- **Проверяй здоровье диска**: Установи `smartmontools` и запускай `sudo smartctl -a /dev/sdX`.

## 🔧 Проверка здоровья диска (Linux)

```bash
# Установка smartmontools
sudo apt install smartmontools

# Проверка здоровья диска
sudo smartctl -a /dev/sda
```

## 📄 Лицензия

MIT
