#!/usr/bin/env python3
"""
Загрузчик Klines (свечей) данных Bybit.
Скачиваем исторические OHLCV данные с публичного хранилища.
Файлы выгружаются помесячно.
"""

import os
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.relativedelta import relativedelta
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
                    
            size_kb = total_size / 1024
            return True, f"{size_kb:.0f} KB"
            
    except Exception as e:
        return False, str(e)


def month_range(start: datetime, end: datetime):
    """
    Генерируем первый день каждого месяца от start до end.

    params:
        start: Начальная дата
        end: Конечная дата
    return:
        Итератор дат (первый день месяца)
    """
    current = start.replace(day=1)
    while current <= end:
        yield current
        current += relativedelta(months=1)


def main() -> None:
    """
    Точка входа.

    params:
        None
    return:
        None
    """
    parser = argparse.ArgumentParser(
        description="Скачиваем Klines данные Bybit (помесячно)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python download_klines.py BTCUSDT --start-date 2025-01-01 --end-date 2025-12-31
  python download_klines.py ETHUSDT --start-date 2025-05-01 --end-date 2025-05-31 --interval 5
        """
    )
    parser.add_argument("symbol", nargs="?", default="BTCUSDT",
                        help="Торговая пара (default: BTCUSDT)")
    parser.add_argument("--start-date", type=str, required=True,
                        help="Начальная дата (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True,
                        help="Конечная дата (YYYY-MM-DD)")
    parser.add_argument("--interval", type=str, default="1",
                        help="Интервал свечи: 1, 5, 15, 30, 60 (default: 1)")
    parser.add_argument("--output-dir", type=str, default="data/raw/klines",
                        help="Директория для сохранения")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать URL без скачивания")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) / args.symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    
    print(f"Bybit Klines Downloader")
    print(f"Symbol: {args.symbol}, Interval: {args.interval}m")
    print(f"Period: {args.start_date} to {args.end_date}")
    print(f"Output: {output_dir}")
    print("-" * 50)
    
    tasks = []
    skipped = 0
    
    for date in month_range(start, end):
        year = date.strftime("%Y")
        month_start = date.strftime("%Y-%m-01")
        next_month = date + relativedelta(months=1)
        month_end = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
        
        filename = f"{args.symbol}_{args.interval}_{month_start}_{month_end}.csv.gz"
        url = f"https://public.bybit.com/kline_for_metatrader4/{args.symbol}/{year}/{filename}"
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
    
    with ThreadPoolExecutor(max_workers=3) as executor:
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
