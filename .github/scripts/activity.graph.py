#!/usr/bin/env python3
import datetime as dt
import json
import os
import sys
import urllib.request

USER = os.environ.get("GH_USER", "chevasatrio")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.environ.get("OUT", "assets/activity-graph.svg")
DAYS = int(os.environ.get("DAYS", "31"))

BG, RED, TEXT, MUTED, GRID = "#0D1117", "#FF2C2C", "#E6EDF3", "#8B949E", "#30363D"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}
"""


def fetch_counts():
    if not TOKEN:
        raise RuntimeError("GH_TOKEN kosong")
    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=DAYS)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    body = json.dumps({
        "query": QUERY,
        "variables": {"login": USER, "from": start.strftime(fmt), "to": now.strftime(fmt)},
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "profile-readme-updater",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if data.get("errors") or not data.get("data", {}).get("user"):
        raise RuntimeError(f"GraphQL error: {data.get('errors') or 'user tidak ditemukan'}")
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    counts = {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    today = now.date()
    days = [today - dt.timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    return [(d, counts.get(d.isoformat(), 0)) for d in days]


def render(series):
    W, H = 900, 320
    L, R, T, B = 55, 25, 60, 50
    pw, ph = W - L - R, H - T - B
    peak = max(c for _, c in series)
    ymax = max(4, peak + (-peak % 4))          # kelipatan 4, minimal 4
    step = ymax // 4

    def x(i):
        return L + pw * i / (len(series) - 1)

    def y(v):
        return T + ph * (1 - v / ymax)

    pts = [(x(i), y(c)) for i, (_, c) in enumerate(series)]
    line = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        xm = (x0 + x1) / 2
        line += f" C{xm:.1f},{y0:.1f} {xm:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    base = T + ph
    area = f"{line} L{pts[-1][0]:.1f},{base:.1f} L{pts[0][0]:.1f},{base:.1f} Z"

    grid = "".join(
        f'<line x1="{L}" y1="{y(v):.1f}" x2="{W - R}" y2="{y(v):.1f}" stroke="{GRID}" stroke-dasharray="3 4"/>'
        f'<text x="{L - 10}" y="{y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}" font-size="11">{v}</text>'
        for v in range(0, ymax + 1, step)
    )
    xlabels = "".join(
        f'<text x="{x(i):.1f}" y="{base + 20}" text-anchor="middle" fill="{MUTED}" font-size="11">{d.day}</text>'
        for i, (d, _) in enumerate(series)
    )
    dots = "".join(
        f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.2" fill="#FFFFFF" stroke="{RED}" stroke-width="1.5">'
        f'<title>{d.strftime("%d %b %Y")}: {c} kontribusi</title></circle>'
        for (px, py), (d, c) in zip(pts, series)
    )
    total = sum(c for _, c in series)
    first, last = series[0][0], series[-1][0]
    rng = f'{first.strftime("%d %b")} – {last.strftime("%d %b %Y")}'

    return f"""<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" fill="none" xmlns="http://www.w3.org/2000/svg" font-family="'Segoe UI', Ubuntu, Sans-Serif">
<title>Contribution graph {rng}</title>
<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{RED}" stop-opacity="0.35"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient></defs>
<rect width="{W}" height="{H}" rx="6" fill="{BG}"/>
<text x="{L}" y="30" fill="{RED}" font-size="18" font-weight="600">Contribution Graph</text>
<text x="{W - R}" y="30" text-anchor="end" fill="{MUTED}" font-size="12">{rng} · {total} kontribusi</text>
{grid}
<path d="{area}" fill="url(#g)"/>
<path d="{line}" stroke="{RED}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
{dots}
{xlabels}
<text x="{L + pw / 2:.0f}" y="{H - 8}" text-anchor="middle" fill="{MUTED}" font-size="12">Days</text>
</svg>
"""


def main():
    svg = render(fetch_counts())
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(svg)
    os.replace(tmp, OUT)
    print(f"✅ [Activity Graph] ditulis ke {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ [Activity Graph] gagal: {e}. File lama dipertahankan.")
        sys.exit(1)
