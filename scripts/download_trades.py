#!/usr/bin/env python3
"""
Загрузчик Trades данных Bybit.
Скачиваем исторические тиковые данные сделок с публичного хранилища.
"""

import os
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple


def download_file(url: str, filepath: Path) -> Tuple[bool, str]:
    """
    Скачиваем файл по URL.

    params:
        url: URL источника
        filepath: Путь для сохранения
    return:
        Кортеж (успех, сообщение)
    """
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code == 404:
                return False, "not_found"
            r.raise_for_status()
            
            total_size = int(r.headers.get('content-length', 0))
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            size_mb = total_size / 1024 / 1024
            return True, f"{size_mb:.1f} MB"
            
    except Exception as e:
        return False, str(e)


def daterange(start: datetime, end: datetime):
    """
    Генерируем даты от start до end включительно.

    params:
        start: Начальная дата
        end: Конечная дата
    return:
        Итератор дат
    """
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main() -> None:
    """
    Точка входа.

    params:
        None
    return:
        None
    """
    parser = argparse.ArgumentParser(
        description="Скачиваем Trades данные Bybit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python download_trades.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
  python download_trades.py ETHUSDT --start-date 2025-01-01 --end-date 2025-12-31 --workers 10
        """
    )
    parser.add_argument("symbol", nargs="?", default="BTCUSDT",
                        help="Торговая пара (default: BTCUSDT)")
    parser.add_argument("--start-date", type=str, required=True,
                        help="Начальная дата (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True,
                        help="Конечная дата (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default="data/raw/trades",
                        help="Директория для сохранения")
    parser.add_argument("--workers", type=int, default=5,
                        help="Количество параллельных загрузок")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать URL без скачивания")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) / args.symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    total_days = (end - start).days + 1
    
    print(f"Bybit Trades Downloader")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.start_date} to {args.end_date} ({total_days} days)")
    print(f"Output: {output_dir}")
    print("-" * 50)
    
    tasks = []
    skipped = 0
    
    for date in daterange(start, end):
        date_str = date.strftime("%Y-%m-%d")
        filename = f"{args.symbol}_{date_str}.csv.gz"
        url = f"https://public.bybit.com/spot/{args.symbol}/{filename}"
        filepath = output_dir / filename
        
        if args.dry_run:
            print(f"  {url}")
            continue
            
        if filepath.exists():
            skipped += 1
            continue
            
        tasks.append((url, filepath))
    
    if args.dry_run:
        return
    
    print(f"To download: {len(tasks)}, Skipped: {skipped}")
    
    if not tasks:
        print("All files already downloaded.")
        return
    
    success = 0
    failed = 0
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_file, url, path): path for url, path in tasks}
        for future in as_completed(futures):
            path = futures[future]
            ok, msg = future.result()
            if ok:
                print(f"  ✓ {path.name} ({msg})")
                success += 1
            elif msg == "not_found":
                print(f"  - {path.name} (not available)")
            else:
                print(f"  ✗ {path.name} ({msg})")
                failed += 1
    
    print("-" * 50)
    print(f"Done: {success} downloaded, {failed} failed")


if __name__ == "__main__":
    main()
