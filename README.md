# Bybit Market Data Downloader

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bybit](https://img.shields.io/badge/Exchange-Bybit-orange.svg)](https://www.bybit.com/)

CLI tools for downloading historical market data from Bybit. No API keys required.

[Русская версия](README_RU.md) | [English](README.md)

---

## 🚀 Features

- **📊 Order Book** — 200 levels, 200ms updates
- **💹 Trades** — Tick-by-tick trade history
- **📈 Klines** — OHLCV candles (1m, 5m, 15m, 30m, 1h)
- **🗜️ Parquet Converter** — Lossless ZSTD compression

## 📦 Installation

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Usage

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

### Convert to Parquet
```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

## 📁 Data Structure

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/   # ZIP archives
│   ├── trades/BTCUSDT/      # CSV.gz files
│   └── klines/BTCUSDT/      # CSV.gz files
└── parquet/
    └── BTCUSDT/             # Parquet files
```

## 📋 Data Formats

| Type | Format | Frequency | Size/day |
|------|--------|-----------|----------|
| Order Book | JSON (200 lvls) | 200ms | ~400 MB |
| Trades | CSV.gz | Tick | ~5-50 MB |
| Klines | CSV.gz | Monthly | ~700 KB |

## ⏰ Availability

| Data Type | Available From |
|-----------|---------------|
| Order Book | May 2025 |
| Trades | 2020 |
| Klines | 2020 |

## 📄 License

MIT
