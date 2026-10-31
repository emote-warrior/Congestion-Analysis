"""Data layer for the day-comparison reports.

Two sources:
  * new  : data/raw/*.csv, hourly from 29 Oct 2026, seconds, distance, IST slots.
  * old  : data/archive/archive_long.csv (from scripts/consolidate_archive.py), Sep 2024 to
           Apr 2026, whole minutes only, no distance, irregular run minutes.

Travel time index (TTI) = observed time / free-flow time, where free flow is the per-route
median of 2:00 to 3:59 am IST runs in the same source and window. Each source gets its own
free-flow baseline because Google picks different paths in 2026 for some routes (Route 1 now
goes over Barapullah, 8.3 km; Route 11 over the Dwarka Expressway, 20.7 km), so raw minutes
are not comparable across years but the ratio to the same year's night time is.

For new-vs-new comparisons the TTI is taken on speed (free-flow speed / observed speed), as in
analyse.py, so a run that takes a different path is still compared fairly.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BASE_HOURS = (2, 3)

# Corridor names from the "Anatomy of Delhi's Congestion" report. The report numbered routes
# without the duplicate, so its Route 13 (Purana Qila Rd) is Route 14 here.
NAMES = {
    1: 'Banda Bahadur Setu', 2: 'Jangpura Rd', 3: 'MG Rd to Ashram', 4: 'MG Rd to Moti Bagh',
    5: 'Aurobindo Marg', 6: 'Outer Ring Rd, Okhla', 7: 'Outer Ring Rd, GK', 8: 'Tulsi Marg, Qutab',
    9: 'Tulsi Marg, Hauz Khas', 10: 'NH 48 from Gurugram', 11: 'NH 48, Dhaula Kuan',
    12: 'Vikas Marg, ITO', 14: 'Purana Qila Rd', 15: 'Mathura Rd', 16: 'GT Karnal Rd, Shastri Pk',
    17: 'Lothian Rd, Delhi Gate', 18: 'DB Gupta Rd', 19: 'Lothian Rd, Jama Masjid',
    20: 'BS Zafar Marg', 21: 'Shivaji Marg, Najafgarh', 22: 'Shivaji Marg, Subhash Ngr',
    23: 'Samaypur Badli Rd', 24: 'GT Karnal Rd, Libaspur', 25: 'MB Rd, Lado Sarai',
}


def load_new():
    files = sorted((ROOT / 'data' / 'raw').glob('*.csv'))
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df = df[df['status'] == 'OK'].copy()
    df['slot'] = pd.to_datetime(df['slot_ist'])
    df = df.sort_values('run_ist').drop_duplicates(['slot', 'route'])
    df['time_min'] = df['duration_in_traffic_s'] / 60
    return _stamp(df)


def load_old():
    df = pd.read_csv(ROOT / 'data' / 'archive' / 'archive_long.csv', parse_dates=['run_ist', 'slot_ist'])
    df = df.rename(columns={'slot_ist': 'slot'}).sort_values('run_ist').drop_duplicates(['slot', 'route'])
    df['time_min'] = df['duration_in_traffic_s'] / 60
    return _stamp(df)


def _stamp(df):
    df['date'] = df['slot'].dt.normalize()
    df['hour'] = df['slot'].dt.hour
    return df


def add_tti(df, baseline_from, on='time'):
    """TTI against the per-route median 2-4 am value in `baseline_from` (same source)."""
    night = baseline_from[baseline_from['hour'].isin(BASE_HOURS)]
    if on == 'speed':
        ff = night.groupby('route')['speed_kmph'].median().rename('ff')
        df = df.join(ff, on='route')
        df['tti'] = df['ff'] / df['speed_kmph']
        ffmin = night.groupby('route')['time_min'].median().rename('ff_min')
        df = df.join(ffmin, on='route')
    else:
        ff = night.groupby('route')['time_min'].median().rename('ff')
        df = df.join(ff, on='route')
        df['tti'] = df['time_min'] / df['ff']
        df['ff_min'] = df['ff']
    # Night runs a touch under the median give TTI just below 1; keep them, they are real.
    return df


def hourly(df):
    """City TTI per date and hour: mean over the routes present."""
    return df.groupby(['date', 'hour'])['tti'].mean().unstack('hour')


def route_hour(df):
    return df.groupby(['route', 'hour'])['tti'].mean().unstack('hour')


def day_mean(df, hours):
    d = df[df['hour'].isin(hours)]
    return d.groupby('date')['tti'].mean()


def compare(target, ref, hours=None):
    """Everything the templates need, from two TTI frames (target = one day, ref = one or more days).

    hours: the hours used for the like-for-like daily figure (hours present in both).
    """
    t_h = hourly(target).iloc[0]
    r_days = hourly(ref)
    common = sorted(set(t_h.dropna().index) & set(r_days.dropna(axis=1, how='all').columns))
    hours = hours or common
    r_mean = r_days.mean()
    t_rh, r_rh = route_hour(target), route_hour(ref)
    # Change in travel time on the same path = TTI ratio - 1
    cell = (t_rh / r_rh - 1) * 100
    t_day = target[target['hour'].isin(hours)].groupby('route')['tti'].mean()
    r_day = ref[ref['hour'].isin(hours)].groupby('route')['tti'].mean()
    route_day = pd.DataFrame({'target': t_day, 'ref': r_day}).dropna()
    route_day['chg'] = (route_day['target'] / route_day['ref'] - 1) * 100
    route_day['name'] = [NAMES.get(r, f'Route {r}') for r in route_day.index]
    T = t_h[hours].mean()
    R = r_mean[hours].mean()
    ref_each = r_days[hours].mean(axis=1)
    # Extra minutes over free flow, summed over the 24 routes for one trip each, per hour (target day)
    tgt = target.assign(delay=target['time_min'] - target['ff_min'])
    delay_h = tgt.groupby('hour')['delay'].sum()
    peak_h = int(t_h[t_h.index >= 6].idxmax())
    return dict(
        hours=hours, t_h=t_h, r_days=r_days, r_mean=r_mean, cell=cell, t_rh=t_rh, r_rh=r_rh,
        route_day=route_day.sort_values('chg'), T=T, R=R, chg=(T / R - 1) * 100,
        ci_T=T - 1, ci_R=R - 1, ref_each=ref_each, delay_h=delay_h, peak_h=peak_h,
        peak_T=float(t_h[peak_h]), n_routes=int(target['route'].nunique()),
    )
