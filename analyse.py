"""Compute CI, TTI and PTI per route, hour and study period from data/raw/*.csv.

Free-flow reference: for each route, the median speed of all 2:00 to 3:59 am IST runs
across the study. Ratios are taken on speed (distance / time) rather than raw time, so a
run where Google picks a slightly longer or shorter path is still compared fairly.

    TTI = free-flow speed / observed speed   (= observed time / free-flow time on the same path)
    CI  = TTI - 1                            (share of extra time over free flow)
    PTI = 95th percentile of TTI in a group  (planning time over free-flow time)

Outputs go to outputs/.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
OUT = ROOT / 'outputs'
STUDY_START, STUDY_END = '2026-10-20 00:00', '2026-11-30 23:59'
BASELINE_HOURS = (2, 3)  # 2:00 to 3:59 am IST

# Study periods (IST, inclusive). Diwali (Lakshmi Puja) is Sunday 8 Nov 2026; the
# non-BS-VI ban on vehicles registered outside Delhi starts 1 Nov 2026.
PERIODS = [
    ('1 Before restrictions', '2026-10-20', '2026-10-31'),
    ('2 Before Diwali', '2026-11-01', '2026-11-07'),
    ('3 Diwali', '2026-11-08', '2026-11-08'),
    ('4 Just after Diwali', '2026-11-09', '2026-11-11'),
    ('5 Later', '2026-11-12', '2026-11-30'),
]


def load():
    files = sorted((ROOT / 'data' / 'raw').glob('*.csv'))
    if not files:
        sys.exit('No data in data/raw')
    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df = df[df['status'] == 'OK'].copy()
    df['slot'] = pd.to_datetime(df['slot_ist'])
    df = df[(df['slot'] >= STUDY_START) & (df['slot'] <= STUDY_END)]
    # A slot can be collected twice (manual plus scheduled run); keep the first.
    df = df.sort_values('run_ist').drop_duplicates(['slot', 'route'])
    df['hour'] = df['slot'].dt.hour
    df['date'] = df['slot'].dt.normalize()
    df['weekday'] = df['slot'].dt.day_name()
    df['period'] = None
    for name, start, end in PERIODS:
        df.loc[df['date'].between(start, end), 'period'] = name
    return df


def add_ratios(df):
    night = df[df['hour'].isin(BASELINE_HOURS)]
    ff = night.groupby('route').agg(
        ff_speed_kmph=('speed_kmph', 'median'),
        ff_time_s=('duration_in_traffic_s', 'median'),
        baseline_runs=('speed_kmph', 'size'),
    )
    df = df.join(ff, on='route')
    df['tti'] = df['ff_speed_kmph'] / df['speed_kmph']
    df['ci'] = df['tti'] - 1
    return df, ff


def summarise(df, keys):
    g = df.groupby(keys)
    return pd.DataFrame({
        'runs': g.size(),
        'mean_time_min': g['duration_in_traffic_s'].mean() / 60,
        'mean_speed_kmph': g['speed_kmph'].mean(),
        'TTI': g['tti'].mean(),
        'CI': g['ci'].mean(),
        'PTI': g['tti'].quantile(0.95),
    }).round(3).reset_index()


def coverage(df):
    """Hours collected per day, to spot dropped GitHub runs."""
    return df.groupby('date')['slot'].nunique().rename('hours_collected').reset_index()


def main():
    OUT.mkdir(exist_ok=True)
    df, ff = add_ratios(load())
    ff.round(2).to_csv(OUT / 'free_flow_by_route.csv')
    coverage(df).to_csv(OUT / 'coverage_by_day.csv', index=False)
    summarise(df, ['period', 'hour']).to_csv(OUT / 'by_period_hour.csv', index=False)
    summarise(df, ['period', 'route']).to_csv(OUT / 'by_period_route.csv', index=False)
    summarise(df, ['period', 'weekday', 'hour']).to_csv(OUT / 'by_period_weekday_hour.csv', index=False)
    summarise(df, ['route', 'hour']).to_csv(OUT / 'by_route_hour.csv', index=False)
    path_changes = df.groupby('route')['path_id'].nunique().rename('distinct_paths')
    path_changes.to_csv(OUT / 'path_changes_by_route.csv')

    print(f"{len(df)} route-hours from {df['slot'].min()} to {df['slot'].max()} IST")
    print(summarise(df, ['period']).to_string(index=False))


if __name__ == '__main__':
    main()
