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
- **📈 Klines** — Генерируются из trades (любой таймфрейм)
- **🗜️ Parquet Converter** — Сжатие ZSTD без потерь
- **🔒 Атомарная запись** — Защита от прерываний

## 📦 Установка

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Использование

### Скачать Order Book
```bash
python scripts/download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Скачать Trades
```bash
python scripts/download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Сгенерировать Klines из Trades
```bash
# Сначала скачайте trades, потом генерируйте klines
python scripts/generate_klines.py BTCUSDT --interval 1m
python scripts/generate_klines.py BTCUSDT --interval 1h
python scripts/generate_klines.py BTCUSDT --interval 1d
```

### Конвертировать Order Book в Parquet
```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

## 📁 Структура данных

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/   # ZIP архивы
│   └── trades/BTCUSDT/      # CSV.gz файлы
├── parquet/
│   └── BTCUSDT/             # Parquet файлы
└── klines/
    └── BTCUSDT/             # Сгенерированные OHLCV
```

## 📋 Форматы данных

| Тип | Источник | Формат | Размер/день |
|-----|----------|--------|-------------|
| Order Book | quote-saver.bycsi.com | JSON (200 ур.) | ~400 МБ |
| Trades | public.bybit.com/spot | CSV.gz | ~5-50 МБ |
| Klines | Генерация из Trades | Parquet/CSV | ~1 МБ |

## ⏰ Доступность

| Тип данных | Доступно с |
|------------|------------|
| Order Book | Май 2025 |
| Trades | 2020 |

## ⚠️ Важные замечания

- Все данные относятся к рынку **Spot**
- Klines **генерируются из trades** (не скачиваются отдельно)
- Скрипты используют **атомарную запись** (защита от прерываний)

## 📄 Лицензия

MIT
