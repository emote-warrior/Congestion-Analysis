"""Build a one-page report and a two-page factsheet comparing one day with reference days.

    python reports/build.py sunday  --target 2026-11-01 --text reports/text/2026-11-01.json
    python reports/build.py weekday --target 2026-11-02 --ref 2026-10-30 --text reports/text/2026-11-02.json

Writes HTML and PDF to $REPORT_OUT (default /mnt/project-files/reports/out) and prints the
numbers the prose needs as JSON (summary.json next to the PDFs). Fonts are read from
$REPORT_FONTS (licensed Portfolio fonts; never committed to the repository).
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

import pandas as pd

import charts as C
import data as D

HERE = Path(__file__).resolve().parent
OUT = Path(os.getenv('REPORT_OUT', '/mnt/project-files/reports/out'))
FONTS = Path(os.getenv('REPORT_FONTS', '/mnt/project-files/reports/fonts'))

SUNDAYS_2025 = ['2025-10-26', '2025-11-02', '2025-11-09', '2025-11-16', '2025-11-23', '2025-11-30']
OLD_BASE = ('2025-10-27', '2025-11-30')  # nights used for the 2025 free-flow baseline
FRI_MON_2025 = [('2025-10-31', '2025-11-03'), ('2025-11-07', '2025-11-10'), ('2025-11-14', '2025-11-17'),
                ('2025-11-21', '2025-11-24'), ('2025-11-28', '2025-12-01')]


def fmt_date(d, short=False):
    d = pd.Timestamp(d)
    return d.strftime('%a %-d %b' if short else '%A %-d %B %Y')


def run(kind, target, ref, text):
    new, old = D.load_new(), D.load_old()
    tday = pd.Timestamp(target)
    new_upto = new[new['date'] <= tday + pd.Timedelta(days=1)]
    extra = {}
    if kind == 'sunday':
        old_base = old[old['date'].between(*OLD_BASE)]
        refs = pd.to_datetime(SUNDAYS_2025)
        t = D.add_tti(new[new['date'] == tday], new_upto, on='time')
        r = D.add_tti(old[old['date'].isin(refs)], old_base, on='time')
        c = D.compare(t, r)
        t_lab, r_lab = fmt_date(tday, True), '2025 Sundays'
        ridge_days = [(pd.Timestamp(d).strftime('%-d %b %Y'), c['r_days'].loc[pd.Timestamp(d)]) for d in refs]
        ridge_days.append((tday.strftime('%-d %b %Y'), c['t_h']))
        hl = tday.strftime('%-d %b %Y')
        ref_text = 'the six Sundays from 26 Oct to 30 Nov 2025'
        r_delay = None
        # Year effect: the last weekday before the rules (Fri 30 Oct 2026) against 2025 Fridays
        fri = pd.Timestamp('2026-10-30')
        fr25 = pd.to_datetime([f for f, _ in FRI_MON_2025])
        cf = D.compare(D.add_tti(new[new['date'] == fri], new_upto), D.add_tti(old[old['date'].isin(fr25)], old_base))
        dh = [h for h in cf['hours'] if 7 <= h <= 22]
        extra['year_effect_fri_day_chg'] = (cf['t_h'][dh].mean() / cf['r_mean'][dh].mean() - 1) * 100
    else:
        rday = pd.Timestamp(ref)
        t = D.add_tti(new[new['date'] == tday], new_upto, on='speed')
        r = D.add_tti(new[new['date'] == rday], new_upto, on='speed')
        c = D.compare(t, r)
        t_lab, r_lab = fmt_date(tday, True), fmt_date(rday, True)
        hl = t_lab
        ridge_days = [(r_lab, c['r_days'].iloc[0]), (t_lab, c['t_h'])]
        ref_text = fmt_date(rday)
        rr = r.assign(delay=r['time_min'] - r['ff_min'])
        r_delay = rr.groupby('hour')['delay'].sum()
        # Context: the usual Friday to Monday change in Oct-Nov 2025, same hours
        old_base = old[old['date'].between(*OLD_BASE)]
        ctx = []
        for f, m in FRI_MON_2025:
            ff = D.add_tti(old[old['date'] == pd.Timestamp(f)], old_base)
            mm = D.add_tti(old[old['date'] == pd.Timestamp(m)], old_base)
            hrs = sorted(set(ff['hour']) & set(mm['hour']) & set(c['hours']) - {0, 1, 2, 3, 4})
            fv, mv = ff[ff['hour'].isin(hrs)]['tti'].mean(), mm[mm['hour'].isin(hrs)]['tti'].mean()
            ctx.append(dict(friday=f, monday=m, fri_tti=fv, mon_tti=mv, chg=(mv / fv - 1) * 100))
        extra['fri_mon_2025'] = ctx
        extra['fri_mon_2025_mean_chg'] = sum(x['chg'] for x in ctx) / len(ctx)

    # day-time figures (7 am to 10 pm) are what readers care about; the full-day figure includes nights
    day_hours = [h for h in c['hours'] if 7 <= h <= 22]
    tdh, rdh = c['t_h'][day_hours].mean(), c['r_mean'][day_hours].mean()
    peak_m = [h for h in c['hours'] if 8 <= h <= 11]
    peak_e = [h for h in c['hours'] if 17 <= h <= 21]
    summ = dict(
        kind=kind, target=target, ref=ref_text, hours=c['hours'], n_routes=c['n_routes'],
        tti_target_all=c['T'], tti_ref_all=c['R'], chg_all=c['chg'],
        tti_target_day=tdh, tti_ref_day=rdh, chg_day=(tdh / rdh - 1) * 100,
        am_target=c['t_h'][peak_m].mean(), am_ref=c['r_mean'][peak_m].mean(),
        pm_target=c['t_h'][peak_e].mean(), pm_ref=c['r_mean'][peak_e].mean(),
        peak_hour=c['peak_h'], peak_tti=c['peak_T'],
        ref_peak_hour=int(c['r_mean'][c['r_mean'].index >= 6].idxmax()), ref_peak_tti=float(c['r_mean'][c['r_mean'].index >= 6].max()),
        ref_each=c['ref_each'].rename(lambda d: str(d.date())).to_dict(),
        target_hours_collected=int(c['t_h'].notna().sum()),
        delay_total_min=float(c['delay_h'].sum()),
        routes=c['route_day'].assign(chg=lambda d: d['chg'].round(1)).reset_index().to_dict('records'),
        routes_up=int((c['route_day']['chg'] > 0).sum()), **extra,
    )
    if r_delay is not None:
        summ['delay_ref_total_min'] = float(r_delay.sum())
    summ['am_chg'] = (summ['am_target'] / summ['am_ref'] - 1) * 100
    summ['pm_chg'] = (summ['pm_target'] / summ['pm_ref'] - 1) * 100

    tx = json.loads(Path(text).read_text()) if text and Path(text).exists() else {}
    figs = make_figs(c, kind, t_lab, r_lab, ridge_days, hl, r_delay)
    stem = f'{target}_{kind}'
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f'{stem}_summary.json').write_text(json.dumps(summ, indent=1, default=float))
    html_r = page_report(summ, tx, figs, kind, t_lab, r_lab)
    html_f = page_factsheet(summ, tx, figs, c, kind, t_lab, r_lab)
    for name, html in ((f'{stem}_report', html_r), (f'{stem}_factsheet', html_f)):
        (OUT / f'{name}.html').write_text(html)
        subprocess.run(['node', str(HERE / 'pdf.js'), str(OUT / f'{name}.html'), str(OUT / f'{name}.pdf')], check=True)
    print(json.dumps({k: v for k, v in summ.items() if k != 'routes'}, indent=1, default=float))
    return summ


def make_figs(c, kind, t_lab, r_lab, ridge_days, hl, r_delay):
    f = {}
    f['profile'] = C.profile(c, 180, 62, t_lab, r_lab)
    f['profile_small'] = C.profile(c, 180, 58, t_lab, r_lab)
    f['ridge'] = C.ridge(ridge_days, 86, 98 if kind == 'sunday' else 60, highlight=hl)
    f['dumbbell'] = C.dumbbell(c['route_day'], 88, 112, t_lab, r_lab)
    order = c['route_day'].sort_values('chg', ascending=False)
    rows = [(r, D.NAMES.get(r, f'Route {r}')) for r in order.index]
    hours = list(range(24))
    f['heat_chg'] = C.heat_table(c['cell'], rows, 180, 100, hours=hours, scale=60)
    f['heat_target'] = C.heat_table(c['t_rh'], rows, 180, 118, stops=C.WARM, scale=2.5, fmt='{:.1f}',
                                    hours=hours) if kind == 'weekday' else None
    f['legend_div'] = C.legend_div(70, 60, 'change in travel time, same hour', [-60, -30, 0, 30, 60])
    f['legend_warm'] = C.legend_warm(70, 1.0, 3.5, 'travel time index', [1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
    # heat values for warm table are TTI; shift so the ramp starts at TTI 1
    if f['heat_target']:
        f['heat_target'] = C.heat_table(c['t_rh'] - 1, rows, 180, 100, stops=C.WARM, scale=2.5, fmt='{:.1f}', hours=hours)
    f['delay'] = C.delay_area(c['delay_h'], r_delay, 180, 36, t_lab, r_lab) if r_delay is not None else None
    return f


# ------------------------------------------------------------------ HTML
def css():
    faces = [('Garnett', 'Garnett-Regular.ttf', 400), ('Garnett', 'Garnett-Medium.ttf', 500),
             ('Garnett', 'Garnett-Semibold.ttf', 600), ('Garnett', 'Garnett-Light.ttf', 300),
             ('Ogg', 'Ogg-Regular.ttf', 400), ('Everett Mono', 'TWKEverettMono-Regular.ttf', 400),
             ('Everett Mono', 'TWKEverettMono-Medium.ttf', 500)]
    ff = ''.join(f"@font-face{{font-family:'{n}';src:url('file://{FONTS / f}');font-weight:{w};}}" for n, f, w in faces)
    return ff + (HERE / 'style.css').read_text()


def head(title):
    return f'<!DOCTYPE html><html lang="en-GB"><head><meta charset="utf-8"><title>{title}</title><style>{css()}</style></head><body>'


def furniture(label, issue, page=None):
    p = f'<span>{page}</span>' if page else '<span></span>'
    return (f'<div class="topline"><span>CSE · Delhi congestion monitor</span><span>{label}</span>{p}</div>'
            f'<div class="botline"><span>Centre for Science and Environment · Sustainable Mobility</span><span>{issue}</span></div>')


def kf(value, label, tone=''):
    return f'<div class="kf {tone}"><div class="kv">{value}</div><div class="kl">{label}</div></div>'


def pct(v):
    return C.signed(v)


def key_figs(s, kind, t_lab, r_lab, n=4):
    tone = lambda v: 'up' if v > 0 else 'down'
    items = [
        kf(pct(s['chg_day']), f'daytime travel time, {t_lab} vs {r_lab} (7 am to 10 pm)', tone(s['chg_day'])),
        kf(f"{s['tti_target_day']:.2f}", f"daytime travel time index, {t_lab} ({s['tti_ref_day']:.2f} for {r_lab})"),
        kf(f"{s['peak_tti']:.2f}", f"peak index, at {s['peak_hour']:02d}:00 ({s['ref_peak_tti']:.2f} at {s['ref_peak_hour']:02d}:00 for {r_lab})"),
        kf(f"{s['routes_up']}/{len(s['routes'])}", 'routes slower than the comparison'),
    ]
    if kind == 'sunday':
        items.append(kf(pct(s['year_effect_fri_day_chg']), 'Fri 30 Oct 2026 (before the rules) vs 2025 Fridays, for scale', 'up' if s['year_effect_fri_day_chg'] > 0 else 'down'))
    if kind == 'weekday':
        items.append(kf(pct(s['fri_mon_2025_mean_chg']), 'usual Friday to Monday change, Oct to Nov 2025', tone(s['fri_mon_2025_mean_chg'])))
    return '<div class="kfs">' + ''.join(items[:n]) + '</div>'


def figure(num, title, body, source, note=''):
    n = f'<div class="note">{note}</div>' if note else ''
    return (f'<figure><figcaption><b>Figure {num}</b> {title}</figcaption>{body}{n}'
            f'<div class="src">Source: {source}</div></figure>')


SRC = 'CSE analysis of Google Maps Directions API travel times on 24 fixed Delhi routes, hourly'


def page_report(s, tx, f, kind, t_lab, r_lab):
    paras = ''.join(f'<p>{p}</p>' for p in tx.get('body', ['[Text to be written once the day\'s data is in.]']))
    note = tx.get('method', '')
    return (head(tx.get('title', 'Report')) + '<div class="page report">' + furniture(tx.get('label', ''), tx.get('issue', ''))
            + f'<div class="kicker">{tx.get("kicker", "")}</div><h1>{tx.get("title", "Title")}</h1>'
            + f'<p class="stand">{tx.get("standfirst", "")}</p>' + key_figs(s, kind, t_lab, r_lab)
            + figure(1, tx.get('fig1', 'Travel time index by hour'), f['profile'], SRC, tx.get('fig1_note', ''))
            + f'<div class="cols">{paras}</div>'
            + f'<div class="method">{note}</div></div></body></html>')


def table_routes(s, kind, t_lab, r_lab):
    rows = sorted(s['routes'], key=lambda r: -r['chg'])
    half = (len(rows) + 1) // 2
    return '<div class="two tables">' + _table(rows[:half], r_lab, t_lab) + _table(rows[half:], r_lab, t_lab) + '</div>'


def _table(rows, r_lab, t_lab):
    h = (f'<table class="data"><thead><tr><th>No.</th><th>Corridor</th><th class="n">{r_lab}</th>'
         f'<th class="n">{t_lab}</th><th class="n">Change</th></tr></thead><tbody>')
    for r in rows:
        cls = 'up' if r['chg'] > 0 else 'down'
        h += (f'<tr><td>{r["route"]}</td><td>{r["name"]}</td><td class="n">{r["ref"]:.2f}</td>'
              f'<td class="n">{r["target"]:.2f}</td><td class="n {cls}">{pct(r["chg"])}</td></tr>')
    return h + '</tbody></table>'


def page_factsheet(s, tx, f, c, kind, t_lab, r_lab):
    lab = tx.get('label', '')
    issue = tx.get('issue', '')
    p1 = ('<div class="page fact">' + furniture(lab, issue, 'Factsheet 1/2')
          + f'<div class="kicker">Factsheet</div><h2 class="ft">{tx.get("fact_title", tx.get("title", ""))}</h2>'
          + key_figs(s, kind, t_lab, r_lab, n=5)
          + figure(1, 'City travel time index by hour (mean of 24 routes)', f['profile_small'], SRC,
                   tx.get('fig1_note', ''))
          + '<div class="two">'
          + figure(2, 'Each day\'s profile, hour by hour' if kind == 'sunday' else 'The two days, hour by hour', f['ridge'], SRC,
                   'Height above each base line is the travel time index minus one; shaded bands mark the peaks.')
          + figure(3, 'Daily mean index by route', f['dumbbell'], SRC, f'Hours common to both days: {len(s["hours"])} of 24.')
          + '</div></div>')
    p2 = ('<div class="page fact">' + furniture(lab, issue, 'Factsheet 2/2')
          + figure(4, f'Change in travel time by route and hour, {t_lab} vs {r_lab} (per cent)',
                   f['legend_div'] + f['heat_chg'], SRC,
                   'Each cell compares the same route at the same hour; blank cells are hours with no run on one side. '
                   'Rows sorted by the daily change.'))
    if kind == 'weekday':
        p2 += figure(5, f'Extra minutes over free flow, one trip on each of the 24 routes', f['delay'], SRC)
    p2 += (f'<figure><figcaption><b>Table 1</b> Daily mean travel time index by route ({len(s["hours"])} common hours)</figcaption>'
           + table_routes(s, kind, t_lab, r_lab) + f'<div class="src">Source: {SRC}</div></figure>'
           + f'<div class="method">{tx.get("method", "")}</div></div>')
    return head('Factsheet') + p1 + p2 + '</body></html>'


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=['sunday', 'weekday'])
    ap.add_argument('--target', required=True)
    ap.add_argument('--ref')
    ap.add_argument('--text')
    a = ap.parse_args()
    run(a.kind, a.target, a.ref, a.text)
