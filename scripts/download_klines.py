#!/usr/bin/env python3
"""
Загрузчик Klines данных Bybit.
Поддерживает Spot (через API) и Futures/Perpetuals (через архивы).
"""

import os
import time
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import polars as pl


# ============================================================
# API DOWNLOADER (Spot & Futures)
# ============================================================

def fetch_klines_api(category: str, symbol: str, interval: str, start_ms: int, end_ms: int, 
                     limit: int = 1000) -> List[List]:
    """
    Получаем klines через Bybit API.

    params:
        category: spot, linear, inverse
        symbol: Торговая пара (BTCUSDT)
        interval: Интервал (1, 5, 15, 30, 60, 240, D, W)
        start_ms: Начало периода в миллисекундах
        end_ms: Конец периода в миллисекундах
        limit: Количество свечей (max 1000)
    return:
        Список свечей [[startTime, open, high, low, close, volume, turnover], ...]
    """
    url = "https://api.bybit.com/v5/market/kline"
    
    params = {
        "category": category,
        "symbol": symbol,
        "interval": interval,
        "start": start_ms,
        "end": end_ms,
        "limit": limit
    }
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()
        
        if data.get("retCode") != 0:
            return []
        
        return data.get("result", {}).get("list", [])
        
    except Exception:
        return []


def download_klines_api(category: str, symbol: str, interval: str, start_date: str, end_date: str,
                        output_dir: Path, rate_limit: float = 0.2) -> Dict[str, Any]:
    """
    Скачиваем klines по API с пагинацией.

    params:
        category: spot или linear (futures)
        symbol: Торговая пара
        interval: Интервал свечей
        start_date: Начало
        end_date: Конец
        output_dir: Директория для сохранения
        rate_limit: Пауза между запросами
    return:
        Статистика
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    
    interval_map = {
        "1": 60 * 1000, "5": 5 * 60 * 1000, "15": 15 * 60 * 1000,
        "30": 30 * 60 * 1000, "60": 60 * 60 * 1000, "240": 240 * 60 * 1000,
        "D": 24 * 60 * 60 * 1000, "W": 7 * 24 * 60 * 60 * 1000,
    }
    
    if interval not in interval_map:
        print(f"Интервал {interval} не поддерживается. Доступны: {list(interval_map.keys())}")
        return {'status': 'error'}
    
    interval_ms = interval_map[interval]
    batch_size = 1000 * interval_ms
    
    total_requests = ((end_ms - start_ms) // batch_size) + 1
    print(f"API Загрузка ({category.upper()}): ~{total_requests} запросов")
    
    all_klines = []
    current_start = start_ms
    request_count = 0
    
    while current_start < end_ms:
        current_end = min(current_start + batch_size, end_ms)
        klines = fetch_klines_api(category, symbol, interval, current_start, current_end)
        
        if klines:
            all_klines.extend(klines)
            request_count += 1
            if request_count % 50 == 0:
                print(f"  Запросов: {request_count}, Свечей: {len(all_klines)}")
        
        current_start = current_end
        time.sleep(rate_limit)
    
    if not all_klines:
        print("Нет данных")
        return {'status': 'error', 'candles': 0}
    
    df = pl.DataFrame({
        'timestamp': [int(k[0]) for k in all_klines],
        'open': [float(k[1]) for k in all_klines],
        'high': [float(k[2]) for k in all_klines],
        'low': [float(k[3]) for k in all_klines],
        'close': [float(k[4]) for k in all_klines],
        'volume': [float(k[5]) for k in all_klines],
        'turnover': [float(k[6]) for k in all_klines],
    })
    
    df = df.unique(subset=['timestamp']).sort('timestamp')
    df = df.with_columns((pl.col('timestamp').cast(pl.Datetime('ms'))).alias('datetime'))
    
    output_file = output_dir / f"{symbol}_{category}_{interval}_{start_date}_{end_date}.parquet"
    df.write_parquet(output_file, compression="zstd")
    
    # Simple CSV for verification
    csv_file = output_file.with_suffix('.csv')
    df.write_csv(csv_file)
    
    print(f"\n✓ {category.upper()} Klines: {len(df):,} свечей → {output_file.name}")
    return {'status': 'success', 'candles': len(df), 'file': str(output_file)}


# ============================================================
# ARCHIVE DOWNLOADER (Only for Futures history)
# ============================================================

def download_file(url: str, filepath: Path, max_retries: int = 3) -> Tuple[bool, str]:
    """
    Скачиваем файл с атомарной записью.

    params:
        url: URL источника
        filepath: Путь для сохранения
        max_retries: Количество попыток
    return:
        Кортеж (успех, сообщение)
    """
    temp_path = filepath.with_suffix('.tmp')
    
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=60) as r:
                if r.status_code == 404:
                    return False, "not_found"
                r.raise_for_status()
                
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                os.replace(temp_path, filepath)
                return True, "ok"
                
        except Exception:
            time.sleep(2)
        finally:
            if temp_path.exists():
                temp_path.unlink()
            
    return False, "failed"


def month_range(start: datetime, end: datetime):
    """
    Генерируем первый день каждого месяца.

    params:
        start: Начальная дата
        end: Конечная дата
    return:
        Итератор дат
    """
    current = start.replace(day=1)
    while current <= end:
        yield current
        current += relativedelta(months=1)


def download_archive_klines(symbol: str, interval: str, start_date: str, end_date: str,
                            output_dir: Path) -> Dict[str, Any]:
    """
    Скачиваем Futures klines из архивов MT4.

    params:
        symbol: Торговая пара
        interval: Интервал свечей
        start_date: Начало
        end_date: Конец
        output_dir: Директория для сохранения
    return:
        Статистика
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    tasks = []
    
    for date in month_range(start, end):
        year = date.strftime("%Y")
        month_start = date.strftime("%Y-%m-01")
        next_month = date + relativedelta(months=1)
        month_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        
        filename = f"{symbol}_{interval}_{month_start}_{month_end}.csv.gz"
        url = f"https://public.bybit.com/kline_for_metatrader4/{symbol}/{year}/{filename}"
        filepath = output_dir / filename
        
        if not filepath.exists():
            tasks.append((url, filepath))
        else:
            print(f"  Skip: {filename}")
    
    if not tasks:
        print("Все файлы уже скачаны")
        return {'status': 'skipped'}
    
    print(f"К скачиванию: {len(tasks)} файлов")
    
    success = 0
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(download_file, url, path): path for url, path in tasks}
        for future in as_completed(futures):
            path = futures[future]
            ok, msg = future.result()
            if ok:
                print(f"  ✓ {path.name}")
                success += 1
            else:
                print(f"  ✗ {path.name} ({msg})")
    
    print(f"\n✓ Archive Klines: {success} файлов загружено")
    return {'status': 'success', 'files': success}


def main() -> None:
    """
    Точка входа.

    params:
        None
    return:
        None
    """
    parser = argparse.ArgumentParser(
        description="Скачиваем Klines данные Bybit (API v5 + Archives)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Spot (API)
  python download_klines.py BTCUSDT --source spot --start-date 2025-01-01 --end-date 2025-01-31 --interval 1
  
  # Futures (API - свежие данные)
  python download_klines.py BTCUSDT --source linear --start-date 2026-01-01 --end-date 2026-01-08 --interval 60
  
  # Futures (Archive - исторические данные, быстро)
  python download_klines.py BTCUSDT --source archive --start-date 2024-01-01 --end-date 2024-12-31 --interval 1
        """
    )
    parser.add_argument("symbol", nargs="?", default="BTCUSDT",
                        help="Торговая пара (default: BTCUSDT)")
    parser.add_argument("--source", type=str, choices=["spot", "linear", "archive"], required=True,
                        help="Источник: spot (API), linear (Futures API), archive (Futures Monthly)")
    parser.add_argument("--start-date", type=str, required=True,
                        help="Начальная дата (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True,
                        help="Конечная дата (YYYY-MM-DD)")
    parser.add_argument("--interval", type=str, default="1",
                        help="Интервал (1, 5, 60, D, etc)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Директория для сохранения")
    
    args = parser.parse_args()
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        # Автоматическая структура
        subdir = "spot" if args.source == "spot" else "futures"
        output_dir = Path(f"data/klines/{subdir}/{args.symbol}")
    
    print(f"Bybit Klines Downloader")
    print(f"Symbol: {args.symbol}")
    print(f"Source: {args.source.upper()}")
    print(f"Period: {args.start_date} to {args.end_date}")
    
    if args.source == "archive":
        download_archive_klines(args.symbol, args.interval, args.start_date, args.end_date, output_dir)
    else:
        # spot или linear (API)
        download_klines_api(args.source, args.symbol, args.interval, args.start_date, args.end_date, output_dir)


if __name__ == "__main__":
    main()
