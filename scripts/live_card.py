#!/usr/bin/env python3
"""Render the "live" card shown in README.md: local time and weather in Paris
and Tanger, whether my sites are up, and when this last ran.

    python scripts/live_card.py dist/

Runs every hour from .github/workflows/profile.yml and is published to the
`output` branch. Standard library only; weather comes from Open-Meteo (no key).
"""
import datetime as dt
import json
import sys
import time
import urllib.request
import zoneinfo
from pathlib import Path
from xml.sax.saxutils import escape

CITIES = [
    ("Paris", 48.8566, 2.3522, "Europe/Paris"),
    ("Tanger", 35.7595, -5.8340, "Africa/Casablanca"),
]
SITES = [
    ("boxspot.ma", "https://boxspot.ma"),
    ("northstars.studio", "https://northstars.studio"),
]
# WMO weather codes -> (label, kind)
WMO = {
    0: ("clear sky", "sun"), 1: ("mostly clear", "sun"), 2: ("partly cloudy", "cloud"),
    3: ("overcast", "cloud"), 45: ("fog", "cloud"), 48: ("fog", "cloud"),
    51: ("drizzle", "rain"), 53: ("drizzle", "rain"), 55: ("drizzle", "rain"),
    56: ("freezing drizzle", "rain"), 57: ("freezing drizzle", "rain"),
    61: ("light rain", "rain"), 63: ("rain", "rain"), 65: ("heavy rain", "rain"),
    66: ("freezing rain", "rain"), 67: ("freezing rain", "rain"),
    71: ("light snow", "snow"), 73: ("snow", "snow"), 75: ("heavy snow", "snow"), 77: ("snow grains", "snow"),
    80: ("showers", "rain"), 81: ("showers", "rain"), 82: ("heavy showers", "rain"),
    85: ("snow showers", "snow"), 86: ("snow showers", "snow"),
    95: ("thunderstorm", "storm"), 96: ("thunderstorm", "storm"), 99: ("thunderstorm", "storm"),
}
THEMES = {
    "dark": dict(card="#0F1217", border="#1C2129", text="#ECEEF2", muted="#8A94A6", faint="#5B6575",
                 accent="#F5B445", up="#3DDC97", down="#FF6B6B", sun="#F5B445", cloud="#8A94A6",
                 rain="#5FA8FF", snow="#CFE8FF", storm="#C084FC"),
    "light": dict(card="#F6F8FA", border="#D0D7DE", text="#1F2328", muted="#656D76", faint="#7D8590",
                  accent="#D97706", up="#1A7F37", down="#CF222E", sun="#D97706", cloud="#656D76",
                  rain="#0969DA", snow="#54AEFF", storm="#8250DF"),
}
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'Cascadia Code', 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"
W, H = 880, 150


def get_json(url, timeout=15):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "glaspaxx-profile"}), timeout=timeout) as r:
        return json.load(r)


def weather(lat, lon, tz):
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&current=temperature_2m,weather_code&timezone={tz}")
    try:
        cur = get_json(url)["current"]
        label, kind = WMO.get(int(cur["weather_code"]), ("", "cloud"))
        return round(cur["temperature_2m"]), label, kind
    except Exception as e:  # noqa: BLE001 - keep the card rendering whatever happens
        print("weather failed:", e, file=sys.stderr)
        return None, "", "cloud"


def ping(url):
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "glaspaxx-profile"})
        with urllib.request.urlopen(req, timeout=12) as r:
            ok = 200 <= r.status < 400
    except Exception as e:  # noqa: BLE001
        print("ping failed:", url, e, file=sys.stderr)
        ok = False
    return ok, int((time.perf_counter() - t0) * 1000)


def text(x, y, s, size, fill, family=SANS, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')


def icon(kind, x, y, t):
    c = t[kind]
    if kind == "sun":
        rays = "".join(f'<line x1="{x}" y1="{y-9}" x2="{x}" y2="{y-12}" stroke="{c}" stroke-width="1.6" transform="rotate({a} {x} {y})"/>' for a in range(0, 360, 45))
        return f'<circle cx="{x}" cy="{y}" r="5" fill="{c}"/>{rays}'
    if kind == "rain":
        return (f'<path d="M{x-8} {y} a6 6 0 0 1 2-11 a7 7 0 0 1 13 1 a5 5 0 0 1 1 10 z" fill="{c}" opacity="0.85"/>'
                f'<line x1="{x-4}" y1="{y+4}" x2="{x-6}" y2="{y+9}" stroke="{c}" stroke-width="1.6"/>'
                f'<line x1="{x+1}" y1="{y+4}" x2="{x-1}" y2="{y+9}" stroke="{c}" stroke-width="1.6"/>')
    if kind == "snow":
        return "".join(f'<line x1="{x}" y1="{y-8}" x2="{x}" y2="{y+8}" stroke="{c}" stroke-width="1.6" transform="rotate({a} {x} {y})"/>' for a in (0, 60, 120))
    if kind == "storm":
        return f'<path d="M{x+2} {y-10} L{x-5} {y+1} L{x} {y+1} L{x-2} {y+10} L{x+5} {y-1} L{x} {y-1} Z" fill="{c}"/>'
    return f'<path d="M{x-9} {y+3} a6 6 0 0 1 2-11 a7 7 0 0 1 13 1 a5 5 0 0 1 1 10 z" fill="{c}" opacity="0.9"/>'


def render(t, cities, sites, stamp):
    b = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="16" fill="{t["card"]}" stroke="{t["border"]}"/>']
    b.append(text(28, 34, "LIVE", 11, t["accent"], MONO, 600))
    b.append(f'<circle cx="64" cy="30" r="3" fill="{t["up"]}"><animate attributeName="opacity" values="1;0.2;1" dur="2s" repeatCount="indefinite"/></circle>')
    b.append(text(W - 28, 34, f"refreshed {stamp} · every hour via GitHub Actions", 11, t["faint"], MONO, anchor="end"))

    x = 28
    for name, local, temp, label, kind in cities:
        b.append(icon(kind, x + 10, 78, t))
        b.append(text(x + 30, 72, name, 15, t["text"], SANS, 600))
        b.append(text(x + 30, 92, local, 12, t["muted"], MONO))
        wtxt = f"{temp}°C · {label}" if temp is not None else "weather unavailable"
        b.append(text(x + 30, 112, wtxt, 12, t["muted"], MONO))
        x += 230
    b.append(f'<line x1="{x-18}" y1="58" x2="{x-18}" y2="{H-30}" stroke="{t["border"]}"/>')

    b.append(text(x + 4, 72, "Sites", 15, t["text"], SANS, 600))
    for i, (host, ok, ms) in enumerate(sites):
        y = 92 + i * 20
        b.append(f'<circle cx="{x+9}" cy="{y-4}" r="3.5" fill="{t["up"] if ok else t["down"]}"/>')
        b.append(text(x + 20, y, f"{host}  {'up' if ok else 'down'}  {ms} ms", 12, t["muted"], MONO))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="Live: time and weather in Paris and Tanger, site status">\n' + "\n".join(b) + "\n</svg>\n")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    out.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    cities = []
    for name, lat, lon, tz in CITIES:
        temp, label, kind = weather(lat, lon, tz)
        local = now.astimezone(zoneinfo.ZoneInfo(tz)).strftime("%a %H:%M")
        cities.append((name, local, temp, label, kind))
    sites = [(host, *ping(url)) for host, url in SITES]
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    for name, t in THEMES.items():
        (out / f"live-{name}.svg").write_text(render(t, cities, sites, stamp), encoding="utf-8")
    print("live card:", cities, sites, stamp)


if __name__ == "__main__":
    main()
