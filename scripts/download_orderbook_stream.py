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
import random
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


def log(msg: str) -> None:
    """
    Логируем с timestamp.

    params:
        msg: Сообщение
    return:
        None
    """
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def download_and_convert(url: str, output_path: Path, 
                         worker_id: int,
                         batch_size: int = 50000, 
                         max_retries: int = 3,
                         stagger_delay: float = 0) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Скачиваем ZIP, конвертируем в Parquet, удаляем ZIP.

    params:
        url: URL источника
        output_path: Путь для Parquet файла
        worker_id: ID воркера для логов
        batch_size: Записей на батч (для экономии памяти)
        max_retries: Количество попыток скачивания
        stagger_delay: Максимальная задержка старта (сек)
    return:
        Кортеж (успех, сообщение, статистика)
    """
    if output_path.exists():
        return True, "exists", {'status': 'skipped'}
    
    # Рандомная задержка старта чтобы не забить канал
    if stagger_delay > 0:
        delay = random.uniform(0, stagger_delay)
        log(f"  [W{worker_id}] Waiting {delay:.1f}s before start...")
        time.sleep(delay)
    
    date_str = output_path.stem.split('_')[0]
    log(f"  [W{worker_id}] Starting {date_str} - downloading...")
    
    temp_zip = None
    
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            
            # Скачиваем во временный файл
            with requests.get(url, stream=True, timeout=120) as r:
                if r.status_code == 404:
                    log(f"  [W{worker_id}] {date_str} - NOT FOUND (404)")
                    return False, "not_found", {'status': 'not_found'}
                r.raise_for_status()
                
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                
                # Создаём временный файл
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        temp_zip.write(chunk)
                        downloaded += len(chunk)
                        
                        # Логируем прогресс каждые 20 MB
                        if total_size > 0 and downloaded % (20 * 1024 * 1024) < 8192:
                            pct = (downloaded / total_size) * 100
                            log(f"  [W{worker_id}] {date_str} - downloading {pct:.0f}%")
                
                temp_zip.close()
                
                if total_size > 0:
                    actual_size = Path(temp_zip.name).stat().st_size
                    if actual_size != total_size:
                        raise IOError(f"Incomplete download: {actual_size}/{total_size}")
            
            download_time = time.time() - start_time
            zip_mb = total_size / 1024 / 1024
            log(f"  [W{worker_id}] {date_str} - downloaded {zip_mb:.1f}MB in {download_time:.1f}s, converting...")
            
            # Конвертируем в Parquet
            convert_start = time.time()
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
            
            convert_time = time.time() - convert_start
            
            # Удаляем временный ZIP
            os.unlink(temp_zip.name)
            
            size_mb = output_path.stat().st_size / 1024 / 1024
            total_time = time.time() - start_time
            
            log(f"  [W{worker_id}] {date_str} ✓ {size_mb:.1f}MB ({total_records:,} rows) in {total_time:.1f}s")
            
            return True, f"{size_mb:.1f}MB (ZIP: {zip_mb:.1f}MB)", {
                'status': 'success',
                'records': total_records,
                'parquet_mb': size_mb,
                'zip_mb': zip_mb,
                'errors': errors,
                'time': total_time
            }
            
        except requests.exceptions.Timeout:
            log(f"  [W{worker_id}] {date_str} - TIMEOUT, retry {attempt+1}/{max_retries}")
            time.sleep(5)
        except Exception as e:
            log(f"  [W{worker_id}] {date_str} - ERROR: {str(e)[:50]}, retry {attempt+1}/{max_retries}")
            time.sleep(2)
        finally:
            # Очистка временного файла при ошибке
            if temp_zip and Path(temp_zip.name).exists():
                try:
                    os.unlink(temp_zip.name)
                except Exception:
                    pass
            
    log(f"  [W{worker_id}] {date_str} ✗ FAILED after {max_retries} attempts")
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
                           min_disk_gb: float, stagger_delay: float,
                           dry_run: bool) -> dict:
    """
    Скачиваем и конвертируем Order Book для одного символа.

    params:
        symbol: Торговая пара
        start: Начальная дата
        end: Конечная дата
        output_dir: Директория для сохранения Parquet
        workers: Количество параллельных обработок
        min_disk_gb: Минимальное свободное место (ГБ)
        stagger_delay: Макс задержка старта воркеров (сек)
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
    
    log(f"To process: {len(tasks)}, Already done: {skipped}")
    
    if not tasks:
        return {'success': 0, 'failed': 0, 'skipped': skipped, 'total_mb': 0}
    
    # Проверяем место
    free_gb = get_disk_free_gb(output_dir)
    log(f"Disk free: {free_gb:.1f} GB, Min required: {min_disk_gb} GB")
    
    if free_gb < min_disk_gb:
        log(f"⚠ Not enough disk space! Required: {min_disk_gb} GB")
        return {'success': 0, 'failed': 0, 'skipped': skipped, 'total_mb': 0, 'disk_full': True}
    
    success = 0
    failed = 0
    total_mb = 0
    total_time = 0
    
    log(f"Starting {workers} workers with stagger delay {stagger_delay}s...")
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for idx, (url, path) in enumerate(tasks):
            worker_id = (idx % workers) + 1
            future = executor.submit(
                download_and_convert, url, path, worker_id,
                50000, 3, stagger_delay
            )
            futures[future] = (url, path)
        
        for future in as_completed(futures):
            url, path = futures[future]
            ok, msg, stats = future.result()
            
            completed = success + failed + 1
            
            # Проверяем место периодически
            if completed % 5 == 0:
                free_gb = get_disk_free_gb(output_dir)
                if free_gb < min_disk_gb:
                    log(f"⚠ Stopping: disk space low ({free_gb:.1f} GB)")
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
                    total_mb += stats.get('parquet_mb', 0)
                    total_time += stats.get('time', 0)
                success += 1
            elif msg == "not_found":
                pass  # Уже залогировано
            else:
                failed += 1
            
            # Прогресс
            remaining = len(tasks) - completed
            log(f"Progress: {completed}/{len(tasks)} done, {remaining} remaining, {total_mb:.1f} MB written")
    
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
  - Экономия ~22%% места (Parquet вместо ZIP)
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
    parser.add_argument("--stagger", type=float, default=5.0,
                        help="Макс случайная задержка старта воркеров (сек)")
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
    
    print("=" * 60)
    print("Bybit Order Book Stream Downloader")
    print("=" * 60)
    print(f"Symbols:      {', '.join(symbols)}")
    print(f"Period:       {args.start_date} to {args.end_date} ({total_days} days)")
    print(f"Output:       {output_dir}")
    print(f"Workers:      {args.workers}")
    print(f"Stagger:      {args.stagger}s (random delay before start)")
    print(f"Min disk:     {args.min_disk} GB")
    print("=" * 60)
    
    start_time = time.time()
    total_stats = {'success': 0, 'failed': 0, 'skipped': 0, 'total_mb': 0}
    
    for i, symbol in enumerate(symbols, 1):
        log(f"[{i}/{len(symbols)}] Processing {symbol}")
        print("-" * 40)
        
        stats = download_symbol_stream(
            symbol, start, end, output_dir, 
            args.workers, args.min_disk, args.stagger, args.dry_run
        )
        
        total_stats['success'] += stats['success']
        total_stats['failed'] += stats['failed']
        total_stats['skipped'] += stats['skipped']
        total_stats['total_mb'] += stats.get('total_mb', 0)
        
        if stats.get('disk_full'):
            log("⚠ Остановлено из-за нехватки места на диске!")
            break
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    log(f"FINISHED in {elapsed/60:.1f} minutes")
    print(f"  Processed:  {total_stats['success']}")
    print(f"  Failed:     {total_stats['failed']}")
    print(f"  Skipped:    {total_stats['skipped']}")
    print(f"  Written:    {total_stats['total_mb']:.1f} MB")
    
    # Финальная проверка места
    free_gb = get_disk_free_gb(output_dir)
    print(f"  Disk free:  {free_gb:.1f} GB")
    print("=" * 60)


if __name__ == "__main__":
    main()
