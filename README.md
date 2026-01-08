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
- **📈 Klines** — Spot & Futures via Bybit API v5
- **🗜️ Parquet Converter** — Lossless ZSTD compression
- **🔒 Atomic writes** — Safe from interruptions
- **🔄 Smart Retry** — Robust network handling

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

### Klines (API - Recommended)
Download Spot or Futures (Perpetual) klines directly from Bybit API (most accurate).

```bash
# Spot Market (API)
python scripts/download_klines.py BTCUSDT --source spot --start-date 2025-01-01 --end-date 2025-01-31 --interval 1

# Futures Market (API)
python scripts/download_klines.py BTCUSDT --source linear --start-date 2025-01-01 --end-date 2025-01-31 --interval 60
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
    ├── spot/BTCUSDT/        # API Spot Klines
    └── futures/BTCUSDT/     # API Futures Klines
```

## 📋 Data Formats

| Type | Source | Format | Size/day |
|------|--------|--------|----------|
| Order Book | quote-saver.bycsi.com | JSON (200 lvls) | ~400 MB |
| Trades | public.bybit.com/spot | CSV.gz | ~5-50 MB |
| Klines | Bybit API v5 | Parquet/CSV | ~1-5 MB |

## ⏰ Availability

| Data Type | Available From |
|-----------|---------------|
| Order Book | May 2025 |
| Trades | 2020 |

## ⚠️ Important Notes

- **API Recommended**: For Klines, use `--source spot` or `--source linear` (API) for the most accurate data.
- **Atomic Writes**: Scripts use temporary files to prevent corruption.

## 📄 License

MIT
