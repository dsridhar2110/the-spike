"""Build a compact London borough map + per-borough metrics for the visual page.

Source geometry: 33-borough GeoJSON (radoi90/housequest-data), fetched once to /tmp.
We simplify it hard — the page must stay small and render instantly on a projector.

Output: pre-projected SVG-ready polygon paths in a 0-1000 box, plus every metric the
map needs to colour and label itself.
"""
import json
import math
import pathlib

RAW = json.load(open("/tmp/t.json"))
FIND = json.load(open("../outputs/findings.json"))
TOOL = json.load(open("../outputs/tool_data.json"))
APPR = json.load(open("../outputs/approval_results.json"))

# GeoJSON name -> our name
ALIAS = {
    "Kensington and Chelsea": "Kensington",
    "Kingston upon Thames": "Kingston",
    "Richmond upon Thames": "Richmond",
}
OURS = set(TOOL["boroughs"])


def _dp(pts, tol):
    """Douglas-Peucker on an OPEN polyline."""
    if len(pts) < 3:
        return pts
    keep = {0, len(pts) - 1}
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        n = math.hypot(dx, dy)
        best, bi = tol, None
        for i in range(a + 1, b):
            px, py = pts[i]
            if n < 1e-12:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / n
            if d > best:
                best, bi = d, i
        if bi is not None:
            keep.add(bi); stack += [(a, bi), (bi, b)]
    return [pts[i] for i in sorted(keep)]


def simplify(ring, tol):
    """Simplify a CLOSED ring. Split at the point farthest from the start first —
    otherwise the start==end segment has zero length and DP collapses to 2 points."""
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 6:
        return ring
    x0, y0 = ring[0]
    m = max(range(1, len(ring)), key=lambda i: (ring[i][0]-x0)**2 + (ring[i][1]-y0)**2)
    return _dp(ring[:m + 1], tol) + _dp(ring[m:], tol)[1:]


# collect rings, tracking global bounds
feats = []
for f in RAW["features"]:
    nm = ALIAS.get(f["properties"]["name"], f["properties"]["name"])
    g = f["geometry"]
    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
    rings = []
    for poly in polys:
        outer = poly[0]
        if len(outer) < 8:
            continue
        s = simplify([(p[0], p[1]) for p in outer], 0.0012)
        if len(s) >= 6:
            rings.append(s)
    if rings:
        rings.sort(key=len, reverse=True)
        feats.append({"name": nm, "rings": rings[:2], "ours": nm in OURS})

xs = [p[0] for f in feats for r in f["rings"] for p in r]
ys = [p[1] for f in feats for r in f["rings"] for p in r]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
midlat = (miny + maxy) / 2
kx = math.cos(math.radians(midlat))          # crude equirectangular correction
W = 1000.0
H = W * ((maxy - miny) / ((maxx - minx) * kx))
print(f"viewbox 1000 x {H:.0f} | {len(feats)} boroughs | "
      f"{sum(len(r) for f in feats for r in f['rings']):,} points after simplify")


def path(rings):
    out = []
    for r in rings:
        pts = []
        for x, y in r:
            px = (x - minx) / (maxx - minx) * W
            py = H - (y - miny) / (maxy - miny) * H
            pts.append(f"{px:.1f},{py:.1f}")
        out.append("M" + "L".join(pts) + "Z")
    return "".join(out)


def centroid(rings):
    r = rings[0]
    cx = sum(p[0] for p in r) / len(r); cy = sum(p[1] for p in r) / len(r)
    return round((cx - minx) / (maxx - minx) * W, 1), round(H - (cy - miny) / (maxy - miny) * H, 1)


# why each excluded borough is excluded — so the map can tell that story
import sqlite3, pandas as pd
_c = sqlite3.connect("../data/raw/housing.sqlite")
_d = pd.read_sql("""select area_name, app_state, target_decision_date from applications_tidy
 where app_size='Small' and start_date>='2018-01-01' and decided_date is not null
 and app_state in ('Permitted','Conditions','Rejected')""", _c)
REASONS = {}
for _b, _s in _d.groupby("area_name"):
    if _b in OURS:
        continue
    _wt = int(_s.target_decision_date.notna().sum())
    _rr = 100 * float((_s.app_state == "Rejected").mean())
    if _wt == 0:
        REASONS[_b] = {"kind": "notarget", "headline": "No deadline published",
                       "detail": f"{len(_s):,} applications, but this council never publishes a "
                                 f"target decision date — so the deadline can't be measured.",
                       "n": int(len(_s))}
    elif _rr < 2:
        REASONS[_b] = {"kind": "broken", "headline": f"{_rr:.1f}% refusal rate",
                       "detail": f"Records {_rr:.1f}% refusals across {_wt:,} decisions. "
                                 f"No council refuses nothing — the data is wrong, so we excluded it.",
                       "n": _wt}
    else:
        REASONS[_b] = {"kind": "thin", "headline": f"Only {_wt:,} decisions",
                       "detail": f"Below our 1,500 minimum — a percentage on {_wt:,} rows is noise.",
                       "n": _wt}

bun = {b["name"]: b for b in FIND["boroughs"]}
link = {x["borough"]: x for x in APPR["bunch_approval_link"]}
appeals = {a["name"]: a for a in FIND["appeals"]}

out_feats = []
for f in feats:
    nm = f["name"]
    rec = {"name": nm, "d": path(f["rings"]), "c": centroid(f["rings"]), "in": f["ours"]}
    if not f["ours"]:
        rec["why"] = REASONS.get(nm, {"kind": "absent", "headline": "Not in the dataset",
                                      "detail": "This borough was never scraped — zero rows.",
                                      "n": 0})
    if f["ours"]:
        t = TOOL["boroughs"][nm]; b = bun.get(nm, {}); l = link.get(nm, {})
        rec |= {
            "rush": b.get("on_day_pct"), "approval": t["approval"],
            "days": t["median_days"], "p90": t["p90_days"], "n": t["n"],
            "app_norm": l.get("approve_not_bunched"), "app_rush": l.get("approve_bunched"),
            "gap": l.get("gap_pp"), "refusal": b.get("refusal_pct"),
            "appeal": appeals.get(nm, {}).get("overturn_pct"),
        }
    out_feats.append(rec)

covered = [f for f in out_feats if f["in"]]
print(f"with data: {len(covered)} | no data: {len(out_feats)-len(covered)}")
for k in ("rush", "approval", "days"):
    vs = [f[k] for f in covered if f.get(k) is not None]
    print(f"  {k:9s} min {min(vs)} max {max(vs)}")

json.dump({"w": 1000, "h": round(H), "features": out_feats,
           "london": TOOL["london"]},
          open("../outputs/map.json", "w"), separators=(",", ":"))
print(f"\nwrote ../outputs/map.json "
      f"({pathlib.Path('../outputs/map.json').stat().st_size/1024:.0f} KB)")
