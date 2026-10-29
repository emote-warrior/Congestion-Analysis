"""Collect travel time in traffic for fixed Delhi routes from the Google Maps Directions API.

Each run appends one row per route to data/raw/YYYY-MM.csv (IST month). Times are stored
in seconds, distances in metres and timestamps in IST, so the analysis can compute
CI, TTI and PTI directly. A run is skipped if its IST hour slot is already collected,
which lets the workflow schedule a backup trigger without paying for duplicate calls.
"""
import csv
import hashlib
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

API_KEY = os.getenv('GOOGLE_API_KEY')
API_URL = 'https://maps.googleapis.com/maps/api/directions/json'
IST = timezone(timedelta(hours=5, minutes=30))
DATA_DIR = Path(__file__).parent / 'data' / 'raw'

# Route ids match the old Excel files. Route 13 was a copy of Route 12 and is dropped.
ROUTES = {
    1: ('28.5759808,77.2186263', '28.5827828,77.256016'),
    2: ('28.5513964,77.273842', '28.5952797,77.2420698'),
    3: ('28.5732655,77.179352', '28.5665441,77.2525954'),
    4: ('28.5653553,77.2470071', '28.5709028,77.1820616'),
    5: ('28.5714791,77.2092125', '28.5295786,77.1917679'),
    6: ('28.5433288,77.2098753', '28.5565,77.2685888'),
    7: ('28.5596205,77.2309816', '28.5460173,77.2500933'),
    8: ('28.4831199,77.1281886', '28.5104244,77.180204'),
    9: ('28.5067604,77.1755274', '28.5420982,77.1997711'),
    10: ('28.4919892,77.0827023', '28.5427483,77.1181807'),
    11: ('28.5834153,77.1462548', '28.5320683,77.1058261'),
    12: ('28.6194026,77.2358173', '28.6281678,77.2515234'),
    14: ('28.6153882,77.2368631', '28.6066081,77.2530604'),
    15: ('28.6190247,77.2404836', '28.6058065,77.2533136'),
    16: ('28.6642427,77.2079688', '28.6706521,77.2333587'),
    17: ('28.6735575,77.2257548', '28.6457822,77.2403703'),
    18: ('28.6450377,77.2230123', '28.6566159,77.1854754'),
    19: ('28.6499997,77.2387382', '28.6683998,77.2274198'),
    20: ('28.6191512,77.2357817', '28.6389426,77.2410317'),
    21: ('28.6328374,77.0862014', '28.6204838,77.0200444'),
    22: ('28.6672416,77.1660713', '28.642202,77.1094069'),
    23: ('28.7449272,77.1308618', '28.7521189,77.0781651'),
    24: ('28.697844,77.1860764', '28.7453743,77.1517715'),
    25: ('28.5112722,77.257023', '28.5229734,77.1914886'),
}

FIELDS = [
    'run_ist', 'slot_ist', 'route', 'origin', 'destination', 'status',
    'distance_m', 'duration_s', 'duration_in_traffic_s', 'speed_kmph',
    'via', 'path_id', 'attempts', 'error',
]
RETRY_STATUSES = {'OVER_QUERY_LIMIT', 'UNKNOWN_ERROR'}
MAX_ATTEMPTS = 2
# India pricing gives 35,000 free Directions Advanced calls a month; stop well short of it.
MONTHLY_CALL_LIMIT = int(os.getenv('MONTHLY_CALL_LIMIT', '33000'))


def fetch_route(session, route, origin, destination):
    """Returns one result row for a route; never raises, so one failure cannot sink the run."""
    row = {'route': route, 'origin': origin, 'destination': destination}
    params = {
        'origin': origin,
        'destination': destination,
        'key': API_KEY,
        'departure_time': 'now',
        'traffic_model': 'best_guess',
    }
    for attempt in range(1, MAX_ATTEMPTS + 1):
        row['attempts'] = attempt
        try:
            response = session.get(API_URL, params=params, timeout=30)
            data = response.json()
            status = data.get('status', f'HTTP_{response.status_code}')
        except (requests.RequestException, ValueError) as exc:
            status, data = 'REQUEST_FAILED', {'error_message': str(exc)}

        if status == 'OK':
            leg = data['routes'][0]['legs'][0]
            in_traffic = leg.get('duration_in_traffic', {}).get('value')
            distance = leg['distance']['value']
            polyline = data['routes'][0]['overview_polyline']['points']
            row.update(
                status='OK' if in_traffic else 'NO_TRAFFIC_DATA',
                distance_m=distance,
                duration_s=leg['duration']['value'],
                duration_in_traffic_s=in_traffic,
                speed_kmph=round(distance / in_traffic * 3.6, 2) if in_traffic else None,
                via=data['routes'][0].get('summary', ''),
                path_id=hashlib.md5(polyline.encode()).hexdigest()[:8],
            )
            return row

        row.update(status=status, error=data.get('error_message', ''))
        if status not in RETRY_STATUSES and status != 'REQUEST_FAILED':
            return row
        time.sleep(2 ** attempt)
    return row


def calls_this_month(path):
    """Counts API calls already made this IST month, retries included."""
    if not path.exists():
        return 0
    with path.open(newline='', encoding='utf-8') as f:
        return sum(int(r.get('attempts') or 1) for r in csv.DictReader(f))


def slot_collected(path, slot):
    """True if any route already has an OK row for this IST hour slot."""
    if not path.exists():
        return False
    with path.open(newline='', encoding='utf-8') as f:
        return any(r['slot_ist'] == slot and r['status'] == 'OK' for r in csv.DictReader(f))


def main():
    if not API_KEY:
        sys.exit('GOOGLE_API_KEY is not set')

    now = datetime.now(IST)
    slot = now.replace(minute=0, second=0, microsecond=0).strftime('%Y-%m-%d %H:%M')
    path = DATA_DIR / f'{now:%Y-%m}.csv'
    if os.getenv('FORCE_RUN') != 'true' and slot_collected(path, slot):
        print(f'Slot {slot} IST already collected, skipping')
        return
    used = calls_this_month(path)
    if used + len(ROUTES) * MAX_ATTEMPTS > MONTHLY_CALL_LIMIT:
        sys.exit(f'{used} calls used this month; stopping to stay under the free limit')

    # All routes are queried in parallel so they share one moment in time.
    with requests.Session() as session, ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda r: fetch_route(session, r[0], *r[1]), ROUTES.items()))

    run_ist = now.strftime('%Y-%m-%d %H:%M:%S')
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow({'run_ist': run_ist, 'slot_ist': slot, **row})

    failed = [r for r in rows if r['status'] != 'OK']
    for r in rows:
        minutes = f"{r['duration_in_traffic_s'] / 60:.1f} min" if r.get('duration_in_traffic_s') else r['status']
        print(f"Route {r['route']:>2}: {minutes}")
    print(f'{len(rows) - len(failed)}/{len(rows)} routes OK, slot {slot} IST, saved to {path}')
    # Fail the job (so GitHub flags it) when more than half the routes fail.
    if len(failed) > len(rows) / 2:
        sys.exit(f'{len(failed)} routes failed: {sorted({r["status"] for r in failed})}')


if __name__ == '__main__':
    main()
