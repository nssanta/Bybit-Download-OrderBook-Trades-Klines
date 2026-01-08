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
- **🗜️ Parquet Streaming** — Download & convert in one step, saves ~22% vs ZIP
- **🔒 Atomic writes** — Safe from interruptions
- **🔄 Smart Retry** — Robust network handling
- **💾 Disk Protection** — Auto-stop when disk space is low

## 📦 Installation

```bash
git clone https://github.com/nssanta/Bybit-Download-OrderBook-Trades-Klines.git
cd Bybit-Download-OrderBook-Trades-Klines
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 📖 Usage

### Order Book (Streaming — Recommended)
Download and convert to Parquet in one step. Saves disk space (~22% smaller than ZIP).

```bash
# Single symbol (recommended: 3 workers, 10s stagger)
python scripts/download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31 --workers 3 --stagger 10

# Multiple symbols
python scripts/download_orderbook_stream.py --symbols BTCUSDT,ETHUSDT,SOLUSDT --start-date 2025-05-01 --end-date 2025-05-31 --workers 3

# With disk space threshold (stop if < 100 GB free)
python scripts/download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-12-31 --min-disk 100
```

**Flags:**
- `--workers N` — parallel downloads (recommended: 3-5, more may cause timeouts)
- `--stagger N` — random delay 0-N seconds before each worker starts (prevents connection flood)
- `--min-disk N` — stop if disk space drops below N GB

### Order Book (Legacy — ZIP only)
Download raw ZIP archives without conversion.

```bash
python scripts/download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Convert ZIP to Parquet
Convert previously downloaded ZIP archives to Parquet.

```bash
python scripts/convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
```

### Download Trades
```bash
python scripts/download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
```

### Klines (API)
Download Spot or Futures (Perpetual) klines directly from Bybit API.

```bash
# Spot Market
python scripts/download_klines.py BTCUSDT --source spot --start-date 2025-01-01 --end-date 2025-01-31 --interval 1

# Futures Market
python scripts/download_klines.py BTCUSDT --source linear --start-date 2025-01-01 --end-date 2025-01-31 --interval 60
```

## 📁 Data Structure

```
data/
├── raw/
│   ├── orderbook/BTCUSDT/      # ZIP archives (legacy)
│   └── trades/BTCUSDT/         # CSV.gz files
├── parquet/
│   └── orderbook/BTCUSDT/      # Parquet files (recommended)
└── klines/
    ├── spot/BTCUSDT/           # Spot klines
    └── futures/BTCUSDT/        # Futures klines
```

## 📋 Data Formats & Sizes

| Type | Source | Raw Format | Parquet | Size/day |
|------|--------|------------|---------|----------|
| Order Book | quote-saver.bycsi.com | ZIP (JSON, 450 MB) | ZSTD (~65 MB) | **65-100 MB** |
| Trades | public.bybit.com/spot | CSV.gz | — | ~5-50 MB |
| Klines | Bybit API v5 | — | ZSTD | ~1-5 MB |

### Order Book Parquet Schema

| Column | Type | Description |
|--------|------|-------------|
| ts | int64 | Server timestamp (ms) |
| cts | int64 | Client timestamp (ms) |
| type | string | `snapshot` or `delta` |
| u | int64 | Update ID |
| seq | int64 | Sequence number |
| bids | string | JSON array `[["price", "qty"], ...]` |
| asks | string | JSON array `[["price", "qty"], ...]` |

## ⏰ Data Availability

| Data Type | Available From |
|-----------|---------------|
| Order Book | May 2025 |
| Trades | 2020 |

## ⚠️ Important Notes

- **Use Streaming for Order Book**: `download_orderbook_stream.py` is recommended — saves ~22% disk space.
- **Disk Space Warning**: Order Book data is large! ~65-100 MB/day per symbol = **~24-36 GB/year** per symbol.
- **Check Disk Health**: For HDD, install `smartmontools` and run `sudo smartctl -a /dev/sdX`.

## 🔧 Disk Health Check (Linux)

```bash
# Install smartmontools
sudo apt install smartmontools

# Check disk health
sudo smartctl -a /dev/sda
```

## 📄 License

MIT
