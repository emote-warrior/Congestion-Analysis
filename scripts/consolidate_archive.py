"""Consolidate the old per-run Excel files (Sep 2024 to Apr 2026) into one long CSV.

Each traffic_data_DD-MM-YYYY HH-MM.xlsx holds 25 routes with Google's text duration
("22 mins", "1 hour 5 mins"). File names are in UTC (GitHub runner clock).
Output: data/archive/archive_long.csv with run_utc, run_ist, slot_ist (run rounded down
to the IST hour), route, duration_in_traffic_s. Route 13 (a copy of Route 12) is dropped
to match the current collection.
"""
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'archive' / 'archive_long.csv'
IST = timedelta(hours=5, minutes=30)


def to_seconds(text):
    if text is None:
        return None
    t = str(text)
    h = re.search(r'(\d+)\s*hour', t)
    m = re.search(r'(\d+)\s*min', t)
    if not h and not m:
        return None
    return (int(h.group(1)) if h else 0) * 3600 + (int(m.group(1)) if m else 0) * 60


def read(path):
    run_utc = datetime.strptime(path.stem[len('traffic_data_'):], '%d-%m-%Y %H-%M')
    run_ist = run_utc + IST
    rows = []
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or r[0] is None:
            continue
        route = int(str(r[0]).replace('Route', '').strip())
        if route == 13:
            continue
        rows.append((run_utc, run_ist, run_ist.replace(minute=0, second=0), route, to_seconds(r[3])))
    wb.close()
    return rows


def main():
    files = sorted(ROOT.glob('traffic_data_*.xlsx'))
    with ProcessPoolExecutor() as pool:
        out = [row for rows in pool.map(read, files, chunksize=50) for row in rows]
    df = pd.DataFrame(out, columns=['run_utc', 'run_ist', 'slot_ist', 'route', 'duration_in_traffic_s'])
    df = df.sort_values(['run_ist', 'route'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, date_format='%Y-%m-%d %H:%M')
    print(f'{len(files)} files, {len(df)} rows, {df.duration_in_traffic_s.isna().sum()} unparsed -> {OUT}')


if __name__ == '__main__':
    main()
