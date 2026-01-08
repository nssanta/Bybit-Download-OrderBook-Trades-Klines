#!/usr/bin/env python3
"""
Загрузчик Order Book данных Bybit со Streaming конвертацией в Parquet.
Скачиваем → Конвертируем → Удаляем ZIP.
Экономим место на диске в 2-3 раза по сравнению с хранением ZIP.
"""

import os
import io
import json
import time
import shutil
import zipfile
import argparse
import tempfile
import requests
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Dict, Any, List

import polars as pl


def get_disk_free_gb(path: Path) -> float:
    """
    Получаем свободное место на диске в ГБ.

    params:
        path: Путь для проверки
    return:
        Свободное место в ГБ
    """
    stat = shutil.disk_usage(path)
    return stat.free / (1024 ** 3)


def parse_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Парсим одну запись Order Book в плоскую структуру.

    params:
        data: Сырая JSON запись
    return:
        Плоский словарь
    """
    return {
        'ts': data['ts'],
        'cts': data.get('cts'),
        'type': data['type'],
        'u': data['data']['u'],
        'seq': data['data']['seq'],
        'bids': json.dumps(data['data'].get('b', [])),
        'asks': json.dumps(data['data'].get('a', [])),
    }


def download_and_convert(url: str, output_path: Path, 
                         batch_size: int = 50000, 
                         max_retries: int = 3) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Скачиваем ZIP, конвертируем в Parquet, удаляем ZIP.

    params:
        url: URL источника
        output_path: Путь для Parquet файла
        batch_size: Записей на батч (для экономии памяти)
        max_retries: Количество попыток скачивания
    return:
        Кортеж (успех, сообщение, статистика)
    """
    if output_path.exists():
        return True, "exists", {'status': 'skipped'}
    
    temp_zip = None
    
    for attempt in range(max_retries):
        try:
            # Скачиваем во временный файл
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 404:
                    return False, "not_found", {'status': 'not_found'}
                r.raise_for_status()
                
                total_size = int(r.headers.get('content-length', 0))
                
                # Создаём временный файл
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        temp_zip.write(chunk)
                temp_zip.close()
                
                if total_size > 0:
                    actual_size = Path(temp_zip.name).stat().st_size
                    if actual_size != total_size:
                        raise IOError(f"Incomplete download: {actual_size}/{total_size}")
            
            # Конвертируем в Parquet
            batches: List[pl.DataFrame] = []
            current_batch: List[Dict[str, Any]] = []
            total_records = 0
            errors = 0
            
            with zipfile.ZipFile(temp_zip.name, 'r') as zf:
                data_file = zf.namelist()[0]
                with zf.open(data_file) as f:
                    for line in f:
                        try:
                            data = json.loads(line.decode('utf-8').strip())
                            record = parse_record(data)
                            current_batch.append(record)
                            
                            if len(current_batch) >= batch_size:
                                batches.append(pl.DataFrame(current_batch))
                                total_records += len(current_batch)
                                current_batch = []
                                
                        except Exception:
                            errors += 1
                    
                    if current_batch:
                        batches.append(pl.DataFrame(current_batch))
                        total_records += len(current_batch)
            
            # Сохраняем Parquet
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df = pl.concat(batches)
            df.write_parquet(output_path, compression="zstd", compression_level=19)
            
            # Удаляем временный ZIP
            os.unlink(temp_zip.name)
            
            size_mb = output_path.stat().st_size / 1024 / 1024
            zip_size_mb = total_size / 1024 / 1024
            
            return True, f"{size_mb:.1f}MB (ZIP: {zip_size_mb:.1f}MB)", {
                'status': 'success',
                'records': total_records,
                'parquet_mb': size_mb,
                'zip_mb': zip_size_mb,
                'errors': errors
            }
            
        except requests.exceptions.Timeout:
            time.sleep(5)
        except Exception as e:
            time.sleep(2)
        finally:
            # Очистка временного файла при ошибке
            if temp_zip and Path(temp_zip.name).exists():
                try:
                    os.unlink(temp_zip.name)
                except Exception:
                    pass
            
    return False, "failed", {'status': 'failed'}


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


def download_symbol_stream(symbol: str, start: datetime, end: datetime,
                           output_dir: Path, workers: int, 
                           min_disk_gb: float, dry_run: bool) -> dict:
    """
    Скачиваем и конвертируем Order Book для одного символа.

    params:
        symbol: Торговая пара
        start: Начальная дата
        end: Конечная дата
        output_dir: Директория для сохранения Parquet
        workers: Количество параллельных обработок
        min_disk_gb: Минимальное свободное место (ГБ)
        dry_run: Только показать URL
    return:
        Статистика {success, failed, skipped, total_mb}
    """
    symbol_dir = output_dir / symbol
    symbol_dir.mkdir(parents=True, exist_ok=True)
    
    tasks = []
    skipped = 0
    
    for date in daterange(start, end):
        date_str = date.strftime("%Y-%m-%d")
        zip_filename = f"{date_str}_{symbol}_ob200.data.zip"
        url = f"https://quote-saver.bycsi.com/orderbook/spot/{symbol}/{zip_filename}"
        
        parquet_filename = f"{date_str}_{symbol}_ob200.parquet"
        output_path = symbol_dir / parquet_filename
        
        if dry_run:
            print(f"  {url}")
            print(f"    → {output_path}")
            continue
            
        if output_path.exists():
            skipped += 1
            continue
            
        tasks.append((url, output_path))
    
    if dry_run:
        return {'success': 0, 'failed': 0, 'skipped': 0, 'total_mb': 0}
    
    print(f"  To process: {len(tasks)}, Already done: {skipped}")
    
    if not tasks:
        return {'success': 0, 'failed': 0, 'skipped': skipped, 'total_mb': 0}
    
    # Проверяем место
    free_gb = get_disk_free_gb(output_dir)
    print(f"  Disk free: {free_gb:.1f} GB")
    
    if free_gb < min_disk_gb:
        print(f"  ⚠ Not enough disk space! Required: {min_disk_gb} GB")
        return {'success': 0, 'failed': 0, 'skipped': skipped, 'total_mb': 0, 'disk_full': True}
    
    success = 0
    failed = 0
    total_mb = 0
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_and_convert, url, path): (url, path) 
                   for url, path in tasks}
        
        for future in as_completed(futures):
            url, path = futures[future]
            ok, msg, stats = future.result()
            
            # Проверяем место периодически
            if success % 5 == 0 and success > 0:
                free_gb = get_disk_free_gb(output_dir)
                if free_gb < min_disk_gb:
                    print(f"\n  ⚠ Stopping: disk space low ({free_gb:.1f} GB)")
                    executor.shutdown(wait=False, cancel_futures=True)
                    return {
                        'success': success, 
                        'failed': failed, 
                        'skipped': skipped, 
                        'total_mb': total_mb,
                        'disk_full': True
                    }
            
            if ok:
                if msg != "exists":
                    print(f"    ✓ {path.name} ({msg})")
                    total_mb += stats.get('parquet_mb', 0)
                success += 1
            elif msg == "not_found":
                print(f"    - {path.name} (not available)")
            else:
                print(f"    ✗ {path.name} ({msg})")
                failed += 1
    
    return {'success': success, 'failed': failed, 'skipped': skipped, 'total_mb': total_mb}


def main() -> None:
    """
    Точка входа.

    params:
        None
    return:
        None
    """
    parser = argparse.ArgumentParser(
        description="Скачиваем Order Book и сразу конвертируем в Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Скачать и конвертировать BTCUSDT за 5 дней
  python download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-05-05
  
  # Несколько символов с 5 воркерами
  python download_orderbook_stream.py --symbols BTCUSDT,ETHUSDT --start-date 2025-05-01 --end-date 2025-05-31 --workers 5
  
  # С минимальным порогом места на диске 100 ГБ
  python download_orderbook_stream.py BTCUSDT --start-date 2025-05-01 --end-date 2025-12-31 --min-disk 100

Преимущества перед download_orderbook.py:
  - Экономия ~50%% места (Parquet вместо ZIP)
  - Не нужно отдельно запускать convert_to_parquet.py
  - Автоматическая защита от переполнения диска
        """
    )
    parser.add_argument("symbol", nargs="?", default=None, 
                        help="Торговая пара (можно использовать --symbols)")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Список пар через запятую: BTCUSDT,ETHUSDT,SOLUSDT")
    parser.add_argument("--start-date", type=str, required=True,
                        help="Начальная дата (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, required=True,
                        help="Конечная дата (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default="data/parquet/orderbook",
                        help="Директория для Parquet файлов")
    parser.add_argument("--workers", type=int, default=3,
                        help="Количество параллельных обработок")
    parser.add_argument("--min-disk", type=float, default=50.0,
                        help="Минимальное свободное место на диске (ГБ)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Показать URL без скачивания")
    
    args = parser.parse_args()
    
    # Определяем список символов
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
    elif args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = ["BTCUSDT"]
    
    output_dir = Path(args.output_dir)
    start = datetime.strptime(args.start_date, "%Y-%m-%d")
    end = datetime.strptime(args.end_date, "%Y-%m-%d")
    total_days = (end - start).days + 1
    
    print(f"Bybit Order Book Stream Downloader")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Period: {args.start_date} to {args.end_date} ({total_days} days)")
    print(f"Output: {output_dir}")
    print(f"Workers: {args.workers}")
    print(f"Min disk: {args.min_disk} GB")
    print("=" * 50)
    
    total_stats = {'success': 0, 'failed': 0, 'skipped': 0, 'total_mb': 0}
    
    for i, symbol in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}] {symbol}")
        print("-" * 30)
        
        stats = download_symbol_stream(
            symbol, start, end, output_dir, 
            args.workers, args.min_disk, args.dry_run
        )
        
        total_stats['success'] += stats['success']
        total_stats['failed'] += stats['failed']
        total_stats['skipped'] += stats['skipped']
        total_stats['total_mb'] += stats.get('total_mb', 0)
        
        if stats.get('disk_full'):
            print("\n⚠ Остановлено из-за нехватки места на диске!")
            break
    
    print("\n" + "=" * 50)
    print(f"ИТОГО: {total_stats['success']} обработано, {total_stats['failed']} ошибок, {total_stats['skipped']} пропущено")
    print(f"Записано: {total_stats['total_mb']:.1f} MB")
    
    # Финальная проверка места
    free_gb = get_disk_free_gb(output_dir)
    print(f"Свободно на диске: {free_gb:.1f} GB")


if __name__ == "__main__":
    main()
