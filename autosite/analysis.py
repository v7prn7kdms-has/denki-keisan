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


def label(p):
    return f'{p["brand"]} {p["model"]}'


def usable_wh(p):
    return p["capacity_wh"] * USABLE_RATIO


def _runtime(topic, products, appliances):
    a = appliances[topic["appliance"]]
    rows = sorted(((p, usable_wh(p) / a["avg_w"]) for p in products), key=lambda x: -x[1])
    return {
        "headers": ["機種", "容量", "使える電力量の目安", f'{a["name"]}の連続使用目安'],
        "rows": [[label(p), f'{p["capacity_wh"]}Wh', f"{usable_wh(p):.0f}Wh", f"約{h:.0f}時間"] for p, h in rows],
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
        "rows": [[label(p), f'{p["capacity_wh"]}Wh', f'約{p["weight_kg"]}kg', f"{den(p):.0f}Wh/kg"] for p in known],
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
    return {
        "headers": ["機種", "容量", "使える電力量の目安", "持つ日数の目安"],
        "rows": [[label(p), f'{p["capacity_wh"]}Wh', f"{usable_wh(p):.0f}Wh", f"約{days(p):.1f}日"] for p in rows],
        "products": rows,
        "best": (label(rows[0]), f"約{days(rows[0]):.1f}日"),
        "worst": (label(rows[-1]), f"約{days(rows[-1]):.1f}日"),
        "assumption": f"1日の使用量は{detail}で合計{need}Whと仮定し、使える電力量は容量の{USABLE_RATIO:.0%}としています。",
    }


KINDS = {"runtime": _runtime, "capability": _capability, "density": _density,
         "lifetime": _lifetime, "scenario": _scenario}


def analyze(topic, products, appliances):
    return KINDS[topic["kind"]](topic, products, appliances)
