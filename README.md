# Bybit Market Data Downloader

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Bybit](https://img.shields.io/badge/Exchange-Bybit-orange.svg)](https://www.bybit.com/)

CLI tools for downloading historical **Spot** market data from Bybit. No API keys required.

[Русская версия](README_RU.md) | [English](README.md)

---

## 🚀 Features

- **📊 Order Book** — 200 levels, 200ms updates
- **💹 Trades** — Tick-by-tick trade history
- **📈 Klines** — Generated from trades (any timeframe)
- **🗜️ Parquet Converter** — Lossless ZSTD compression
- **🔒 Atomic writes** — Safe from interruptions

## 📦 Installation

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Usage

### Download Order Book
```bash
python scripts/download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Download Trades
```bash
python scripts/download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Generate Klines from Trades
```bash
# First download trades, then generate klines
python scripts/generate_klines.py BTCUSDT --interval 1m
python scripts/generate_klines.py BTCUSDT --interval 1h
python scripts/generate_klines.py BTCUSDT --interval 1d
```

### Convert Order Book to Parquet
```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

## 📁 Data Structure

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/   # ZIP archives
│   └── trades/BTCUSDT/      # CSV.gz files
├── parquet/
│   └── BTCUSDT/             # Parquet files
└── klines/
    └── BTCUSDT/             # Generated OHLCV
```

## 📋 Data Formats

| Type | Source | Format | Size/day |
|------|--------|--------|----------|
| Order Book | quote-saver.bycsi.com | JSON (200 lvls) | ~400 MB |
| Trades | public.bybit.com/spot | CSV.gz | ~5-50 MB |
| Klines | Generated from Trades | Parquet/CSV | ~1 MB |

## ⏰ Availability

| Data Type | Available From |
|-----------|---------------|
| Order Book | May 2025 |
| Trades | 2020 |

## ⚠️ Important Notes

- All data is **Spot** market data
- Klines are **generated from trades** (not downloaded separately)
- Scripts use **atomic writes** (safe from interruptions)

## 📄 License

MIT
