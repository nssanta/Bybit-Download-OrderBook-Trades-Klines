#!/usr/bin/env python3
"""
Конвертер Order Book JSON в Parquet.
Преобразуем скачанные ZIP архивы в формат Parquet с ZSTD сжатием.
Проверяем целостность данных после конвертации.
"""

import json
import zipfile
import argparse
from pathlib import Path
from typing import Dict, Any, List

import polars as pl


def count_lines_in_zip(zip_path: Path) -> int:
    """
    Считаем строки в ZIP архиве без полной распаковки.

    params:
        zip_path: Путь к ZIP файлу
    return:
        Количество строк
    """
    count = 0
    with zipfile.ZipFile(zip_path, 'r') as zf:
        data_file = zf.namelist()[0]
        with zf.open(data_file) as f:
            for _ in f:
                count += 1
    return count


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


def convert_file(zip_path: Path, output_path: Path, 
                 batch_size: int = 50000, verify: bool = True) -> Dict[str, Any]:
    """
    Конвертируем один ZIP файл в Parquet с проверкой целостности.

    params:
        zip_path: Исходный ZIP файл
        output_path: Путь для Parquet файла
        batch_size: Записей на батч (для экономии памяти)
        verify: Проверять ли файл после записи
    return:
        Словарь со статистикой конвертации
    """
    if output_path.exists():
        print(f"  Skip: {output_path.name} (exists)")
        return {'status': 'skipped'}
    
    print(f"\n{'='*60}")
    print(f"Converting: {zip_path.name}")
    print(f"{'='*60}")
    
    print("Counting records...", end=" ", flush=True)
    original_count = count_lines_in_zip(zip_path)
    print(f"{original_count:,}")
    
    batches: List[pl.DataFrame] = []
    current_batch: List[Dict[str, Any]] = []
    total = 0
    errors = 0
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        data_file = zf.namelist()[0]
        with zf.open(data_file) as f:
            for line in f:
                try:
                    data = json.loads(line.decode('utf-8').strip())
                    record = parse_record(data)
                    current_batch.append(record)
                    
                    if len(current_batch) >= batch_size:
                        batches.append(pl.DataFrame(current_batch))
                        total += len(current_batch)
                        print(f"  Processed: {total:,}")
                        current_batch = []
                        
                except Exception:
                    errors += 1
            
            if current_batch:
                batches.append(pl.DataFrame(current_batch))
                total += len(current_batch)
    
    print(f"\nIntegrity: {total:,}/{original_count:,}", end=" ")
    if total == original_count:
        print("✓")
    else:
        print(f"⚠ ({errors} errors)")
    
    print("Saving...", end=" ", flush=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pl.concat(batches)
    df.write_parquet(output_path, compression="zstd", compression_level=3)
    print("Done")
    
    if verify:
        print("Verifying...", end=" ", flush=True)
        saved = pl.read_parquet(output_path)
        if len(saved) == total:
            print(f"✓ ({len(saved):,} records)")
        else:
            print("✗ Mismatch!")
            return {'status': 'error'}
    
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Output: {output_path.name} ({size_mb:.1f} MB)")
    
    return {'status': 'success', 'records': total, 'size_mb': size_mb}


def main() -> None:
    """
    Точка входа.

    params:
        None
    return:
        None
    """
    parser = argparse.ArgumentParser(
        description="Конвертируем Order Book ZIP в Parquet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python convert_to_parquet.py --input data/raw/orderbook/BTCUSDT --output data/parquet/BTCUSDT
        """
    )
    parser.add_argument("--input", type=str, required=True,
                        help="Директория с ZIP файлами")
    parser.add_argument("--output", type=str, required=True,
                        help="Директория для Parquet файлов")
    parser.add_argument("--no-verify", action="store_true",
                        help="Пропустить верификацию после записи")
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    zip_files = sorted(input_dir.glob("*.zip"))
    
    if not zip_files:
        print(f"No ZIP files found in {input_dir}")
        return
    
    print(f"Order Book → Parquet Converter")
    print(f"Input: {input_dir}")
    print(f"Output: {output_dir}")
    print(f"Files: {len(zip_files)}")
    print("-" * 60)
    
    verify = not args.no_verify
    success = 0
    
    for i, zip_path in enumerate(zip_files, 1):
        output_path = output_dir / f"{zip_path.stem}.parquet"
        print(f"\n[{i}/{len(zip_files)}]", end="")
        result = convert_file(zip_path, output_path, verify=verify)
        if result['status'] == 'success':
            success += 1
    
    print(f"\n{'='*60}")
    print(f"Complete: {success}/{len(zip_files)} files converted")


if __name__ == "__main__":
    main()
