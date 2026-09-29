"""PUNARVAS scoring engine, a Python port of the logic in index.html.

Keeps the same numbers as the map so the SHAP tab explains exactly what the map shows:
  RPI = 100 * (Wh*hazard + We*exposure + Wv*vulnerability + Wd*history) / (Wh+We+Wv+Wd)

The RPI is additive, so SHAP values are easy to interpret: each factor's SHAP value is the number
of RPI points it adds or removes compared with the average village in the dataset.
"""
from __future__ import annotations

import math

import numpy as np

HZ = ("landslide", "flood", "cloudburst")
FEATURES = ("Hazard", "Exposure", "Vulnerability", "Disaster history")
THR = 0.75  # susceptibility at or above this is a Red Zone
DEFAULT_WEIGHTS = {"h": 35, "e": 25, "v": 25, "d": 15}
TIER_WINDOW = {
    "Immediate": "0-6 months",
    "Short-term": "6-24 months",
    "Medium-term": "2-5 years",
    "Monitor": "monitor only",
}

# Real event: Meppadi panchayat, Wayanad, 30 July 2024. Village names and the Elstone Estate site are real.
# Coordinates are approximate; households and susceptibility values are indicative inputs, not survey data.
HAB = [
    dict(id="mundakkai", name="Mundakkai", lon=76.196, lat=11.487, hh=200, V=.70, D=.60, hz=(.88, .70, .55)),
    dict(id="chooralmala", name="Chooralmala", lon=76.183, lat=11.480, hh=120, V=.65, D=.45, hz=(.72, .65, .45)),
    dict(id="attamala", name="Attamala", lon=76.203, lat=11.492, hh=80, V=.60, D=.50, hz=(.85, .55, .50)),
    dict(id="punchirimattam", name="Punchirimattam", lon=76.208, lat=11.500, hh=50, V=.60, D=.55, hz=(.90, .50, .60)),
    dict(id="vellarimala", name="Vellarimala", lon=76.215, lat=11.470, hh=60, V=.55, D=.40, hz=(.80, .30, .55)),
    dict(id="thondernad", name="Thondernad", lon=76.100, lat=11.530, hh=150, V=.40, D=.30, hz=(.45, .55, .30)),
    dict(id="meppadi", name="Meppadi", lon=76.135, lat=11.552, hh=400, V=.20, D=.20, hz=(.35, .50, .25)),
]
SITES = [
    dict(id="A", name="Elstone Estate, Kalpetta", lon=76.105, lat=11.605, caps=(410, 410, 410), suit=82),
    dict(id="B", name="Parcel B (placeholder)", lon=76.145, lat=11.525, caps=(200, 150, 220), suit=70),
    dict(id="C", name="Parcel C (placeholder)", lon=76.170, lat=11.560, caps=(120, 140, 90), suit=64),
]
for _s in SITES:
    _s["cap"] = min(_s["caps"])
    _s["lim"] = ("land", "water", "services")[_s["caps"].index(_s["cap"])]


def _round(x: float) -> int:
    """Round half up, like JavaScript's Math.round."""
    return int(math.floor(x + 0.5))


def tier_of(rpi: int) -> str:
    return "Immediate" if rpi >= 70 else "Short-term" if rpi >= 55 else "Medium-term" if rpi >= 35 else "Monitor"


def alert_of(rain: float) -> str:
    return "Normal" if rain < 60 else "Watch" if rain < 120 else "Warning" if rain < 200 else "Evacuate"


def hazard_label(v: float) -> str:
    return "Very High" if v >= .75 else "High" if v >= .6 else "Moderate" if v >= .4 else "Low" if v >= .2 else "Very Low"


def km(a: dict, b: dict) -> float:
    d = math.pi / 180
    x = (b["lon"] - a["lon"]) * d * math.cos((a["lat"] + b["lat"]) / 2 * d)
    y = (b["lat"] - a["lat"]) * d
    return 6371 * math.hypot(x, y)


def normalised_weights(w: dict) -> np.ndarray:
    arr = np.array([w["h"], w["e"], w["v"], w["d"]], dtype=float)
    total = arr.sum() or 1.0
    return arr / total


def feature_row(x: dict, rain: float) -> list[float]:
    """[hazard (rain-adjusted), exposure, vulnerability, disaster history], each 0 to 1."""
    r = rain / 300
    ls, fl, cb = x["hz"]
    base = max(ls, fl, cb)
    he = min(1.0, base + r * (0.2 * max(ls, cb) + 0.12 * fl))
    exposure = min(1.0, x["hh"] / 200)
    return [he, exposure, x["V"], x["D"]]


def shap_values(X: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, float, str]:
    """SHAP values of RPI = 100 * X @ w, with the villages themselves as the background data.

    Uses the shap library when it is installed. Because RPI is additive the exact answer is
    100 * w * (x - mean(x)), which is the fallback and what the library returns.
    Returns (values [n, 4], base value, method name).
    """
    closed_form = 100 * w * (X - X.mean(axis=0))
    base = float((100 * X @ w).mean())
    try:
        import shap  # type: ignore

        explainer = shap.Explainer(lambda Z: 100 * np.asarray(Z) @ w, X)
        ex = explainer(X)
        vals = np.asarray(ex.values, dtype=float)
        if vals.shape == X.shape and np.allclose(vals, closed_form, atol=1e-6):
            return vals, float(np.mean(ex.base_values)), "shap library (exact explainer)"
    except Exception:
        pass
    return closed_form, base, "exact Shapley values (closed form)"


def compute(rain: float = 30, weights: dict | None = None, budget: int = 4) -> dict:
    """Rank villages, assign relocation sites, and attach SHAP values."""
    weights = weights or DEFAULT_WEIGHTS
    w = normalised_weights(weights)
    X = np.array([feature_row(x, rain) for x in HAB])
    rpi_raw = 100 * X @ w
    vals, base_value, method = shap_values(X, w)

    villages = []
    for i, x in enumerate(HAB):
        ls, fl, cb = x["hz"]
        base = max(ls, fl, cb)
        he = X[i][0]
        rpi = _round(rpi_raw[i])
        villages.append({
            **x,
            "he": he,
            "base": base,
            "rpi": rpi,
            "tier": tier_of(rpi),
            "red": he >= THR,
            "raised": base < THR <= he,
            "dominant": HZ[x["hz"].index(base)],
            "features": dict(zip(FEATURES, X[i].tolist())),
            "shap": dict(zip(FEATURES, vals[i].tolist())),
        })
    villages.sort(key=lambda v: (-v["rpi"], -v["hh"]))

    remaining = {s["id"]: s["cap"] for s in SITES}
    for rank, v in enumerate(villages, start=1):
        v["rank"] = rank
        v["funded"] = rank <= budget
        v["site"] = None
        v["distance_km"] = None
        if not v["funded"]:
            continue
        options = sorted(SITES, key=lambda s: km(v, s) + (100 - s["suit"]) / 12)
        for s in options:
            if remaining[s["id"]] >= v["hh"]:
                remaining[s["id"]] -= v["hh"]
                v["site"] = s
                v["distance_km"] = km(v, s)
                break
    return {
        "rain": rain,
        "weights": weights,
        "budget": budget,
        "alert": alert_of(rain),
        "villages": villages,
        "remaining": remaining,
        "base_value": base_value,
        "shap_method": method,
    }


def explain_village(res: dict, village_id: str) -> str:
    """Plain-language explanation built directly from the SHAP values."""
    v = next(x for x in res["villages"] if x["id"] == village_id)
    ranked = sorted(v["shap"].items(), key=lambda kv: -abs(kv[1]))
    up = [(k, s) for k, s in ranked if s > 0.5]
    down = [(k, s) for k, s in ranked if s < -0.5]
    text = (f"**{v['name']}** is ranked **#{v['rank']}** with an RPI of **{v['rpi']}**, "
            f"compared with an average of {res['base_value']:.0f} across the seven villages.")
    if up:
        text += " Pushing its score **up**: " + ", ".join(f"{k.lower()} (+{s:.1f})" for k, s in up) + "."
    if down:
        text += " Pulling it **down**: " + ", ".join(f"{k.lower()} ({s:.1f})" for k, s in down) + "."
    if v["red"]:
        text += (f" It sits in a Red Zone for {v['dominant']} risk"
                 + (", pushed over the threshold by the rainfall forecast." if v["raised"] else "."))
    if v["funded"]:
        if v["site"]:
            text += f" Suggested site: {v['site']['name']}, {v['distance_km']:.1f} km away."
        else:
            text += " No listed site has enough room, so a field survey is needed."
    else:
        text += " It is outside the funded list at the current budget."
    return text
