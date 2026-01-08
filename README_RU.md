# Bybit Market Data Downloader

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bybit](https://img.shields.io/badge/Exchange-Bybit-orange.svg)](https://www.bybit.com/)

CLI-инструменты для скачивания исторических данных с Bybit. API ключи не нужны.

[Русская версия](README_RU.md) | [English](README.md)

---

## 🚀 Возможности

- **📊 Order Book** — 200 уровней, обновление 200мс
- **💹 Trades** — Тиковые данные сделок
- **📈 Klines** — OHLCV свечи (1м, 5м, 15м, 30м, 1ч)
- **🗜️ Parquet Converter** — Сжатие ZSTD без потерь

## 📦 Установка

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Использование

### Order Book
```bash
python scripts/download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Trades
```bash
python scripts/download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Klines
```bash
python scripts/download_klines.py BTCUSDT --start-date 2025-01-01 --end-date 2025-12-31 --interval 1
```

### Конвертация в Parquet
```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

## 📁 Структура данных

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/   # ZIP архивы
│   ├── trades/BTCUSDT/      # CSV.gz файлы
│   └── klines/BTCUSDT/      # CSV.gz файлы
└── parquet/
    └── BTCUSDT/             # Parquet файлы
```

## 📋 Форматы данных

| Тип | Формат | Частота | Размер/день |
|-----|--------|---------|-------------|
| Order Book | JSON (200 ур.) | 200мс | ~400 МБ |
| Trades | CSV.gz | Тик | ~5-50 МБ |
| Klines | CSV.gz | Месяц | ~700 КБ |

## ⏰ Доступность

| Тип данных | Доступно с |
|------------|------------|
| Order Book | Май 2025 |
| Trades | 2020 |
| Klines | 2020 |

## 📄 Лицензия

MIT
