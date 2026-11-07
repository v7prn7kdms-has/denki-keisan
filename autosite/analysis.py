"""公式スペックから比較表を計算する。価格は扱わない（API経由でない価格表示は規約で不可）。"""
from datetime import date, timedelta
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USABLE_RATIO = 0.85
STALE_AFTER_DAYS = 180
MIN_ROWS = 3


def load_json(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def fresh_products(today):
    limit = today - timedelta(days=STALE_AFTER_DAYS)
    return [p for p in load_json("data/products.json")
            if date.fromisoformat(p["verified_on"]) >= limit]


def wh(value):
    return f"{value:g}Wh"


def label(p):
    return f'{p["brand"]} {p["model"]}'


def usable_wh(p):
    return p["capacity_wh"] * USABLE_RATIO


def _runtime(topic, products, appliances):
    a = appliances[topic["appliance"]]
    rows = sorted(((p, usable_wh(p) / a["avg_w"]) for p in products), key=lambda x: -x[1])
    return {
        "headers": ["機種", "容量", "使える電力量の目安", f'{a["name"]}の連続使用目安'],
        "rows": [[label(p), wh(p["capacity_wh"]), f"{usable_wh(p):.0f}Wh", f"約{h:.0f}時間"] for p, h in rows],
        "products": [p for p, _ in rows],
        "best": (label(rows[0][0]), f"約{rows[0][1]:.0f}時間"),
        "worst": (label(rows[-1][0]), f"約{rows[-1][1]:.0f}時間"),
        "assumption": f'{a["name"]}は平均{a["avg_w"]}W（{a["basis"]}）、変換後に使える電力量は容量の{USABLE_RATIO:.0%}と仮定しています。',
    }


def _capability(topic, products, appliances):
    a = appliances[topic["appliance"]]
    rows = sorted(products, key=lambda p: -p["ac_output_w"])
    verdict = lambda p: "定格内" if p["ac_output_w"] >= a["peak_w"] else "定格超過"
    ok = [p for p in rows if p["ac_output_w"] >= a["peak_w"]]
    return {
        "headers": ["機種", "定格出力", f'{a["name"]}（{a["peak_w"]}W想定）', "余裕"],
        "rows": [[label(p), f'{p["ac_output_w"]}W', verdict(p), f'{p["ac_output_w"] - a["peak_w"]:+d}W'] for p in rows],
        "products": rows,
        "best": (label(rows[0]), f'{rows[0]["ac_output_w"]}W'),
        "worst": (label(rows[-1]), f'{rows[-1]["ac_output_w"]}W'),
        "count_ok": f"{len(ok)}機種",
        "assumption": f'{a["name"]}の消費電力は{a["peak_w"]}W（{a["basis"]}）と仮定しています。実機の銘板を確認してください。',
    }


def _density(topic, products, appliances):
    known = sorted((p for p in products if p["weight_kg"]), key=lambda p: -p["capacity_wh"] / p["weight_kg"])
    den = lambda p: p["capacity_wh"] / p["weight_kg"]
    return {
        "headers": ["機種", "容量", "重さ", "1kgあたりの容量"],
        "rows": [[label(p), wh(p["capacity_wh"]), f'約{p["weight_kg"]}kg', f"{den(p):.0f}Wh/kg"] for p in known],
        "products": known,
        "best": (label(known[0]), f"{den(known[0]):.0f}Wh/kg") if known else None,
        "worst": (label(known[-1]), f"{den(known[-1]):.0f}Wh/kg") if known else None,
        "assumption": "重さの公式値が確認できた機種のみを掲載しています。",
    }


def lifetime_kwh(p):
    return p["cycles"] * p["capacity_wh"] * (1 + p["retention"]) / 2 / 1000


def _lifetime(topic, products, appliances):
    known = sorted((p for p in products if p["cycles"] and p["retention"]), key=lambda p: -lifetime_kwh(p))
    return {
        "headers": ["機種", "サイクル数", "残存容量", "累計で取り出せる電力量の試算"],
        "rows": [[label(p), f'{p["cycles"]}回', f'{p["retention"]:.0%}', f"約{lifetime_kwh(p):,.0f}kWh"] for p in known],
        "products": known,
        "best": (label(known[0]), f"約{lifetime_kwh(known[0]):,.0f}kWh") if known else None,
        "worst": (label(known[-1]), f"約{lifetime_kwh(known[-1]):,.0f}kWh") if known else None,
        "assumption": "容量が初期値から公称の残存率まで直線的に下がると仮定した試算です。保証値ではありません。サイクル数と残存率の両方を確認できた機種のみ掲載しています。",
    }


def _scenario(topic, products, appliances):
    loads = [(appliances[k], h) for k, h in topic["loads"]]
    need = sum(a["avg_w"] * h for a, h in loads)
    days = lambda p: usable_wh(p) / need
    rows = sorted(products, key=lambda p: -days(p))
    detail = "、".join(f'{a["name"]}{a["avg_w"]}W×{h}時間' for a, h in loads)
    breakdown = {
        "headers": ["家電", "消費電力の目安", "1日の使用時間", "1日の電力量", "割合"],
        "rows": [[a["name"], f'{a["avg_w"]}W', f"{h}時間", f'{a["avg_w"] * h}Wh', f'{a["avg_w"] * h / need:.0%}']
                 for a, h in loads] + [["合計", "", "", f"{need}Wh", "100%"]],
    }
    return {
        "breakdown": breakdown,
        "headers": ["機種", "容量", "使える電力量の目安", "持つ日数の目安"],
        "rows": [[label(p), wh(p["capacity_wh"]), f"{usable_wh(p):.0f}Wh", f"約{days(p):.1f}日"] for p in rows],
        "products": rows,
        "best": (label(rows[0]), f"約{days(rows[0]):.1f}日"),
        "worst": (label(rows[-1]), f"約{days(rows[-1]):.1f}日"),
        "assumption": f"1日の使用量は{detail}で合計{need}Whと仮定し、使える電力量は容量の{USABLE_RATIO:.0%}としています。",
    }


def _charges(topic, products, appliances):
    devices = [appliances[k] for k in topic["devices"]]
    rows = sorted(products, key=lambda p: -p["capacity_wh"])
    count = lambda p, d: usable_wh(p) / d["battery_wh"]
    first = devices[0]
    return {
        "headers": ["機種", "容量", "定格出力"] + [f'{d["name"]}の充電回数' for d in devices],
        "rows": [[label(p), wh(p["capacity_wh"]), f'{p["ac_output_w"]}W'] + [f"約{count(p, d):.0f}回" for d in devices]
                 for p in rows],
        "products": rows,
        "best": (label(rows[0]), f"約{count(rows[0], first):.0f}回") if rows else None,
        "worst": (label(rows[-1]), f"約{count(rows[-1], first):.0f}回") if rows else None,
        "assumption": "、".join(f'{d["name"]}は{d["battery_wh"]}Wh（{d["basis"]}）' for d in devices)
                      + f"、充電に使える電力量は容量の{USABLE_RATIO:.0%}と仮定しています。",
    }


def _charge_speed(topic, products, appliances):
    known = sorted((p for p in products if p["ac_full_charge_min"]),
                   key=lambda p: -p["capacity_wh"] / p["ac_full_charge_min"])
    rate = lambda p: p["capacity_wh"] / p["ac_full_charge_min"]
    return {
        "headers": ["機種", "容量", "AC満充電の時間", "1分あたりの充電量"],
        "rows": [[label(p), wh(p["capacity_wh"]), f'約{p["ac_full_charge_min"]}分', f"約{rate(p):.1f}Wh/分"] for p in known],
        "products": known,
        "best": (label(known[0]), f"約{rate(known[0]):.1f}Wh/分") if known else None,
        "worst": (label(known[-1]), f"約{rate(known[-1]):.1f}Wh/分") if known else None,
        "assumption": "満充電の時間は公式の公表値（専用アプリの超急速モードなどは除いた値）です。公表値がある機種のみ掲載しています。",
    }


CLASSES = [("小型（600Wh以下）", 0, 600), ("1kWhクラス（601〜1500Wh）", 601, 1500), ("2kWhクラス（1501Wh以上）", 1501, 10 ** 6)]


def _classes(topic, products, appliances):
    fridge = appliances["fridge"]
    span = lambda vals, fmt: (fmt(min(vals)) if min(vals) == max(vals) else f"{fmt(min(vals))}〜{fmt(max(vals))}")
    rows, shown = [], []
    for name, low, high in CLASSES:
        group = [p for p in products if low <= p["capacity_wh"] <= high]
        if not group:
            continue
        shown += group
        weights = [p["weight_kg"] for p in group if p["weight_kg"]]
        rows.append([name, f"{len(group)}機種", span([p["ac_output_w"] for p in group], lambda v: f"{v}W"),
                     span(weights, lambda v: f"約{v}kg") if weights else "公表値未確認",
                     span([usable_wh(p) / fridge["avg_w"] for p in group], lambda v: f"約{v:.0f}時間")])
    return {
        "headers": ["容量帯", "掲載数", "定格出力", "重さ", "冷蔵庫の連続使用目安"],
        "rows": rows,
        "products": sorted(shown, key=lambda p: p["capacity_wh"]),
        "best": None,
        "worst": None,
        "assumption": f'冷蔵庫は平均{fridge["avg_w"]}W（{fridge["basis"]}）、使える電力量は容量の{USABLE_RATIO:.0%}と仮定しています。重さは公式値を確認できた機種のみの範囲です。',
    }


KINDS = {"runtime": _runtime, "capability": _capability, "density": _density,
         "lifetime": _lifetime, "scenario": _scenario, "charges": _charges,
         "charge_speed": _charge_speed, "classes": _classes}


def analyze(topic, products, appliances):
    products = [p for p in products
                if topic.get("min_wh", 0) <= p["capacity_wh"] <= topic.get("max_wh", float("inf"))]
    return KINDS[topic["kind"]](topic, products, appliances)


def facts_key(analysis):
    """解説文を作った時の表と一致しているかを判定するための値。"""
    return json.dumps([analysis["headers"], analysis["rows"], analysis.get("breakdown")], ensure_ascii=False)
