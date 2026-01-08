#!/usr/bin/env python3
"""
Загрузчик Order Book данных Bybit.
Скачиваем исторические данные стакана (200 уровней) с публичного хранилища.
"""

import os
import time
import argparse
import requests
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple


def download_file(url: str, filepath: Path, max_retries: int = 3) -> Tuple[bool, str]:
    """
    Скачиваем файл по URL с повторными попытками и атомарной записью.

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
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 404:
                    return False, "not_found"
                r.raise_for_status()
                
                total_size = int(r.headers.get('content-length', 0))
                
                # Атомарная запись: пишем во временный файл
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Проверка размера
                if total_size > 0 and temp_path.stat().st_size != total_size:
                    raise IOError("Incomplete download")
                
                # Атомарное переименование
                os.replace(temp_path, filepath)
                            
                size_mb = total_size / 1024 / 1024
                return True, f"{size_mb:.1f} MB"
                
        except requests.exceptions.Timeout:
            time.sleep(5)
        except Exception:
            time.sleep(2)
        finally:
            # Очистка временного файла при ошибке
            if temp_path.exists():
                temp_path.unlink()
            
    return False, "failed"


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
        description="Скачиваем Order Book данные Bybit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python download_orderbook.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-31
  python download_orderbook.py ETHUSDT --start-date 2025-05-01 --end-date 2025-05-07 --workers 10
        """
    )
    parser.add_argument("symbol", nargs="?", default="BTCUSDT", 
                        help="Торговая пара (default: BTCUSDT)")
    parser.add_argument("--start-date", type=str, required=True,
                        help="Начальная дата (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True,
                        help="Конечная дата (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default="data/raw/orderbook",
                        help="Директория для сохранения")
    parser.add_argument("--workers", type=int, default=3,
                        help="Количество параллельных загрузок")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать URL без скачивания")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir) / args.symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    total_days = (end - start).days + 1
    
    print(f"Bybit Order Book Downloader")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.start_date} to {args.end_date} ({total_days} days)")
    print(f"Output: {output_dir}")
    print("-" * 50)
    
    tasks = []
    skipped = 0
    
    for date in daterange(start, end):
        date_str = date.strftime("%Y-%m-%d")
        filename = f"{date_str}_{args.symbol}_ob200.data.zip"
        url = f"https://quote-saver.bycsi.com/orderbook/spot/{args.symbol}/{filename}"
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
