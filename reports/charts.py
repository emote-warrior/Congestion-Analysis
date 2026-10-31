"""Hand-drawn SVG charts in the Portfolio style (paper, ink, crimson accent, warm ramps,
hairline axes, mono labels, direct labels instead of legends). Units are millimetres; the
SVGs are placed inline in the HTML so they pick up the @font-face fonts."""
import math

import numpy as np

PAPER, PAPER_DEEP, WHITE = '#F2EEE3', '#E8E1D0', '#FFFDF8'
INK, TEAL_INK, MID, HAIR = '#1B191A', '#1E3837', '#6F6A60', '#CBC3B1'
CRIMSON, ORANGE, GREEN, LAV, SAGE, TEAL, OCHRE = '#C9353B', '#EC6433', '#2F6F52', '#B7A7CB', '#A7B288', '#7AA8A4', '#CF9043'
MONO, SANS = "'Everett Mono', monospace", "'Garnett', sans-serif"
PT = 0.3528  # mm per point

WARM = [(0.0, '#F2EEE3'), (0.25, '#F3D3A8'), (0.5, '#EC9A5E'), (0.75, '#EC6433'), (1.0, '#C9353B'), (1.4, '#5A1F24')]
DIVERGE = [(-1.0, '#1E3837'), (-0.6, '#2F6F52'), (-0.25, '#A7B288'), (0.0, '#F2EEE3'), (0.25, '#EC9A5E'), (0.6, '#C9353B'), (1.0, '#5A1F24')]


def _rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], float)


def ramp(stops, v):
    v = min(max(v, stops[0][0]), stops[-1][0])
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if v <= b:
            t = 0 if b == a else (v - a) / (b - a)
            c = _rgb(ca) * (1 - t) + _rgb(cb) * t
            return '#%02X%02X%02X' % tuple(int(round(x)) for x in c)
    return stops[-1][1]


def text_on(fill):
    r, g, b = _rgb(fill) / 255
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return PAPER if lum < 0.45 else INK


def tx(x, y, t, size=6.5, color=INK, anchor='start', font=MONO, weight=400, upper=True, extra=''):
    t = str(t)
    if upper and font == MONO:
        t = t.upper()
        extra += ' letter-spacing="0.06em"'
    t = t.replace('&', '&amp;').replace('<', '&lt;')
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-family="{font}" font-size="{size * PT:.3f}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}" {extra}>{t}</text>')


def line(x1, y1, x2, y2, color=HAIR, w=0.15, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{w}"{d}/>'


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}mm" height="{h}mm" '
            f'style="display:block;overflow:visible">{body}</svg>')


def path(pts):
    return 'M' + ' L'.join(f'{x:.2f},{y:.2f}' for x, y in pts)


def signed(v, unit='%'):
    r = round(v)
    return ('0' if r == 0 else f'{r:+d}'.replace('-', '−')) + unit


def hour_label(h):
    return f'{h:02d}:00'


# ------------------------------------------------------------------ hourly profile (area + band)
def profile(c, w, h, t_label, r_label, ymax=None, annotate=True):
    """Target day as a crimson area, reference days as a band (min to max) and a dashed mean."""
    L, R, T, B = 9.0, 22.0, 5.0, 7.0
    pw, ph = w - L - R, h - T - B
    t_h, r_days = c['t_h'], c['r_days']
    ymax = ymax or max(3.0, math.ceil(max(t_h.max(), r_days.max().max()) * 2) / 2 + 0.25)
    X = lambda hr: L + pw * hr / 23
    Y = lambda v: T + ph * (1 - (v - 1) / (ymax - 1)) if v >= 1 else T + ph + (1 - v) * 0
    o = []
    for g in np.arange(1, ymax + 0.01, 0.5):
        o.append(line(L, Y(g), L + pw, Y(g), HAIR, 0.12))
        o.append(tx(L - 1.5, Y(g) + 0.8, f'{g:.1f}', 6, MID, 'end'))
    # peak shading
    for a, b in ((8, 11), (17, 21)):
        o.append(f'<rect x="{X(a):.2f}" y="{T:.2f}" width="{X(b) - X(a):.2f}" height="{ph:.2f}" fill="{PAPER_DEEP}" opacity="0.6"/>')
    o.append(tx((X(8) + X(11)) / 2, T - 1.2, 'morning peak', 5.5, MID, 'middle'))
    o.append(tx((X(17) + X(21)) / 2, T - 1.2, 'evening peak', 5.5, MID, 'middle'))
    # reference band
    cols = [hr for hr in r_days.columns if r_days[hr].notna().any()]
    lo, hi, mu = r_days[cols].min(), r_days[cols].max(), r_days[cols].mean()
    band = [(X(hr), Y(hi[hr])) for hr in cols] + [(X(hr), Y(lo[hr])) for hr in reversed(cols)]
    o.append(f'<path d="{path(band)} Z" fill="{LAV}" opacity="0.45"/>')
    o.append(f'<path d="{path([(X(hr), Y(mu[hr])) for hr in cols])}" fill="none" stroke="{TEAL_INK}" stroke-width="0.35" stroke-dasharray="1.2 0.8"/>')
    for hr in cols:
        o.append(f'<circle cx="{X(hr):.2f}" cy="{Y(mu[hr]):.2f}" r="0.45" fill="{TEAL_INK}"/>')
    # target area
    th = t_h.dropna()
    pts = [(X(hr), Y(max(v, 1))) for hr, v in th.items()]
    o.append(f'<path d="{path([(pts[0][0], Y(1))] + pts + [(pts[-1][0], Y(1))])} Z" fill="{CRIMSON}" opacity="0.16"/>')
    o.append(f'<path d="{path(pts)}" fill="none" stroke="{CRIMSON}" stroke-width="0.55"/>')
    # axes
    o.append(line(L, Y(1), L + pw, Y(1), MID, 0.2))
    for hr in range(0, 24, 3):
        o.append(line(X(hr), Y(1), X(hr), Y(1) + 1, MID, 0.15))
        o.append(tx(X(hr), Y(1) + 4, hour_label(hr), 6, MID, 'middle'))
    o.append(tx(L - 1.5, T - 1.2, 'TTI', 6, MID, 'end'))
    # direct labels at the right
    last_t = th.index[-1]
    last_r = cols[-1]
    yt, yr = Y(th[last_t]), Y(mu[last_r])
    if abs(yt - yr) < 4:
        yt, yr = (yt - 2, yr + 2) if yt <= yr else (yt + 2, yr - 2)
    o.append(tx(X(23) + 2, yt + 0.8, t_label, 6, CRIMSON))
    o.append(tx(X(23) + 2, yr + 0.8, r_label, 6, TEAL_INK))
    if annotate:
        pk = c['peak_h']
        o.append(f'<circle cx="{X(pk):.2f}" cy="{Y(t_h[pk]):.2f}" r="0.9" fill="{CRIMSON}"/>')
        o.append(tx(X(pk) + 1.6, Y(t_h[pk]) - 1.2, f'peak {t_h[pk]:.2f} at {hour_label(pk)}', 6, CRIMSON))
    return svg(w, h, ''.join(o))


# ------------------------------------------------------------------ tabular heatmap with numbers
def heat_table(values, row_names, w, h, stops=DIVERGE, scale=50.0, fmt='{:+.0f}', hours=range(24),
               title_l='', note_missing='–'):
    """values: DataFrame (rows = routes in display order, columns = hours). Cell colour from
    stops on value/scale; the number is printed in the cell."""
    L, R, T, B = 40.0, 1.0, 6.0, 1.0
    hours = list(hours)
    nr = len(row_names)
    cw, rh = (w - L - R) / len(hours), (h - T - B) / nr
    o = []
    for j, hr in enumerate(hours):
        o.append(tx(L + cw * (j + 0.5), T - 1.6, f'{hr:02d}', 5.5, MID, 'middle'))
    if title_l:
        o.append(tx(0, T - 1.6, title_l, 5.5, MID))
    for i, (r, name) in enumerate(row_names):
        y = T + rh * i
        o.append(tx(L - 1.5, y + rh * 0.68, name, 6.2, INK, 'end', SANS, upper=False))
        for j, hr in enumerate(hours):
            v = values.loc[r, hr] if (r in values.index and hr in values.columns) else np.nan
            x = L + cw * j
            if v is None or (isinstance(v, float) and math.isnan(v)):
                o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cw - 0.3:.2f}" height="{rh - 0.3:.2f}" fill="none" stroke="{HAIR}" stroke-width="0.1"/>')
                continue
            fill = ramp(stops, v / scale)
            o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cw - 0.3:.2f}" height="{rh - 0.3:.2f}" fill="{fill}"/>')
            o.append(tx(x + (cw - 0.3) / 2, y + rh * 0.66, fmt.format(v), 4.6, text_on(fill), 'middle'))
    return svg(w, h, ''.join(o))


def legend_ramp(w, stops, lo, hi, ticks, label, fmt='{:+.0f}%'):
    o = [tx(0, 2.2, label, 5.5, MID)]
    n = 60
    bw = w
    for i in range(n):
        v = lo + (hi - lo) * i / (n - 1)
        o.append(f'<rect x="{bw * i / n:.2f}" y="3.4" width="{bw / n + 0.05:.2f}" height="1.8" fill="{ramp(stops, v / max(abs(lo), abs(hi)) if stops is DIVERGE else (v - lo) / (hi - lo) * 1.4 if False else v)}"/>')
    for t in ticks:
        o.append(tx(bw * (t - lo) / (hi - lo), 8.2, fmt.format(t), 5.5, MID, 'middle'))
    return svg(w, 9, ''.join(o))


def legend_div(w, scale, label, ticks):
    o = [tx(0, 2.2, label, 5.5, MID)]
    n = 60
    for i in range(n):
        v = -scale + 2 * scale * i / (n - 1)
        o.append(f'<rect x="{w * i / n:.2f}" y="3.4" width="{w / n + 0.05:.2f}" height="1.8" fill="{ramp(DIVERGE, v / scale)}"/>')
    for t in ticks:
        o.append(tx(w * (t + scale) / (2 * scale), 8.2, f'{t:+.0f}%' if t else '0', 5.5, MID, 'middle'))
    return svg(w, 9, ''.join(o))


def legend_warm(w, lo, hi, label, ticks):
    o = [tx(0, 2.2, label, 5.5, MID)]
    n = 60
    for i in range(n):
        v = lo + (hi - lo) * i / (n - 1)
        o.append(f'<rect x="{w * i / n:.2f}" y="3.4" width="{w / n + 0.05:.2f}" height="1.8" fill="{ramp(WARM, (v - 1) / 2.5)}"/>')
    for t in ticks:
        o.append(tx(w * (t - lo) / (hi - lo), 8.2, f'{t:.1f}', 5.5, MID, 'middle'))
    return svg(w, 9, ''.join(o))


# ------------------------------------------------------------------ dumbbell per route
def dumbbell(route_day, w, h, t_label, r_label):
    L, R, T, B = 40.0, 12.0, 10.0, 6.0
    rows = route_day.sort_values('chg', ascending=False)
    n = len(rows)
    vmax = math.ceil(max(rows['target'].max(), rows['ref'].max()) * 2) / 2
    X = lambda v: L + (w - L - R) * (v - 1) / (vmax - 1)
    rh = (h - T - B) / n
    o = []
    for g in np.arange(1, vmax + 0.01, 0.5):
        o.append(line(X(g), T - 1, X(g), T + rh * n, HAIR, 0.12))
        o.append(tx(X(g), T + rh * n + 3.6, f'{g:.1f}', 5.5, MID, 'middle'))
    o.append(tx(L, T - 2.4, 'daily mean TTI', 5.5, MID))
    for i, (r, row) in enumerate(rows.iterrows()):
        y = T + rh * (i + 0.5)
        up = row['chg'] > 0
        col = CRIMSON if up else GREEN
        o.append(tx(L - 1.5, y + 0.9, row['name'], 6.2, INK, 'end', SANS, upper=False))
        o.append(line(X(row['ref']), y, X(row['target']), y, col, 0.6))
        o.append(f'<circle cx="{X(row["ref"]):.2f}" cy="{y:.2f}" r="0.8" fill="{PAPER}" stroke="{TEAL_INK}" stroke-width="0.3"/>')
        o.append(f'<circle cx="{X(row["target"]):.2f}" cy="{y:.2f}" r="0.9" fill="{col}"/>')
        o.append(tx(w - R + 11.5, y + 0.8, signed(row["chg"]), 5.8, col, 'end'))
    # key
    o.append(f'<circle cx="{L + 0.8:.2f}" cy="{1.6:.2f}" r="0.8" fill="{PAPER}" stroke="{TEAL_INK}" stroke-width="0.3"/>')
    o.append(tx(L + 2.4, 2.4, r_label, 5.5, TEAL_INK))
    o.append(f'<circle cx="{L + 34:.2f}" cy="{1.6:.2f}" r="0.9" fill="{CRIMSON}"/>')
    o.append(tx(L + 35.6, 2.4, t_label, 5.5, CRIMSON))
    return svg(w, h, ''.join(o))


# ------------------------------------------------------------------ ridge (stacked day profiles)
def ridge(days, w, h, highlight=None, hours=range(24)):
    """days: list of (label, Series hour->TTI). Each day is a filled profile above its own base
    line; the highlighted day is crimson, the rest ink-teal outlines on lavender."""
    L, R, T, B = 22.0, 2.0, 4.0, 6.0
    pw = w - L - R
    n = len(days)
    vmax = max(3.0, max(float(s.max()) for _, s in days))
    T = T + (3.0 if n <= 3 else 6.0)
    pitch = (h - T - B) / n
    amp = pitch * (0.95 if n <= 3 else 1.9) * (vmax - 1) / 2.0
    X = lambda hr: L + pw * hr / 23
    o = []
    for a, b in ((8, 11), (17, 21)):
        o.append(f'<rect x="{X(a):.2f}" y="{T - 1:.2f}" width="{X(b) - X(a):.2f}" height="{h - B - T + 1:.2f}" fill="{PAPER_DEEP}" opacity="0.6"/>')
    for i, (label, s) in enumerate(days):
        base = T + pitch * (i + 1)
        s = s.dropna()
        hl = label == highlight
        pts = [(X(hr), base - amp * max(v - 1, 0) / (vmax - 1)) for hr, v in s.items()]
        poly = [(pts[0][0], base)] + pts + [(pts[-1][0], base)]
        o.append(f'<path d="{path(poly)} Z" fill="{CRIMSON if hl else LAV}" fill-opacity="{0.85 if hl else 0.55}" stroke="{PAPER}" stroke-width="0.3"/>')
        o.append(f'<path d="{path(pts)}" fill="none" stroke="{CRIMSON if hl else TEAL_INK}" stroke-width="{0.4 if hl else 0.2}"/>')
        o.append(line(L, base, L + pw, base, MID, 0.12))
        o.append(tx(L - 1.5, base - 0.4, label, 5.8, CRIMSON if hl else INK, 'end', weight=500 if hl else 400))
    for hr in range(0, 24, 6):
        o.append(tx(X(hr), h - B + 4, hour_label(hr), 5.5, MID, 'middle'))
    # height scale
    x0 = L + pw + 0.8
    b0 = T + pitch
    o.append(line(x0, b0, x0, b0 - amp * 1 / (vmax - 1), INK, 0.2))
    o.append(tx(x0 - 0.8, b0 - amp * 0.5 / (vmax - 1) + 0.8, 'TTI +1', 5, INK, 'end'))
    return svg(w, h, ''.join(o))


# ------------------------------------------------------------------ delay bars (extra minutes)
def delay_area(series_a, series_b, w, h, la, lb):
    """Two hourly series of extra minutes (sum over routes, one trip each): a as crimson area,
    b as a dashed teal line."""
    L, R, T, B = 9.0, 22.0, 4.0, 7.0
    pw, ph = w - L - R, h - T - B
    vmax = max(series_a.max(), series_b.max() if series_b is not None else 0)
    step = next(st for st in (15, 30, 60, 100, 200, 500) if vmax / st <= 6)
    vmax = math.ceil(vmax / step) * step
    X = lambda hr: L + pw * hr / 23
    Y = lambda v: T + ph * (1 - v / vmax)
    o = []
    for g in range(0, int(vmax) + 1, step):
        o.append(line(L, Y(g), L + pw, Y(g), HAIR, 0.12))
        o.append(tx(L - 1.5, Y(g) + 0.8, f'{g}', 6, MID, 'end'))
    bw = pw / 24 * 0.7
    for hr, v in series_a.dropna().items():
        o.append(f'<rect x="{X(hr) - bw / 2:.2f}" y="{Y(max(v, 0)):.2f}" width="{bw:.2f}" height="{Y(0) - Y(max(v, 0)):.2f}" fill="{CRIMSON}" opacity="0.8"/>')
    if series_b is not None:
        sb = series_b.dropna()
        o.append(f'<path d="{path([(X(hr), Y(max(v, 0))) for hr, v in sb.items()])}" fill="none" stroke="{TEAL_INK}" stroke-width="0.35" stroke-dasharray="1.2 0.8"/>')
        o.append(tx(X(23) + 2, Y(max(sb.iloc[-1], 0)) + 0.8, lb, 6, TEAL_INK))
    o.append(tx(X(23) + 2, Y(max(series_a.dropna().iloc[-1], 0)) - 2.5, la, 6, CRIMSON))
    o.append(line(L, Y(0), L + pw, Y(0), MID, 0.2))
    for hr in range(0, 24, 3):
        o.append(tx(X(hr), Y(0) + 4, hour_label(hr), 6, MID, 'middle'))
    o.append(tx(L - 1.5, T - 1.2, 'MIN', 6, MID, 'end'))
    return svg(w, h, ''.join(o))
