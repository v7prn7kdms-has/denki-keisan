"""表の解説文を作る。Claudeの文は数値を検証し、通らなければ計算結果だけの文に戻す。"""
import json
import os
import re

NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
SCHEMA = {
    "type": "object",
    "properties": {
        "points": {"type": "array", "items": {"type": "string"}},
        "caution": {"type": "string"},
    },
    "required": ["points", "caution"],
    "additionalProperties": False,
}
SYSTEM = (
    "ポータブル電源の比較記事の解説を日本語で書きます。渡された計算結果だけを根拠にしてください。"
    "渡されていない数値は書かないでください。実際に使った体験談のように書かないでください。"
    "「最強」「絶対」「必ず」など断定や誇張の表現は使わないでください。価格や評判には触れないでください。"
    "pointsは読者が機種を選ぶための考察を3つ、cautionは計算の限界や注意点を1つ書いてください。"
)


def fallback(analysis):
    points = []
    if analysis["best"]:
        points.append(f'この比較で最も大きい値は{analysis["best"][0]}の{analysis["best"][1]}です。')
        points.append(f'最も小さい値は{analysis["worst"][0]}の{analysis["worst"][1]}です。')
    if "count_ok" in analysis:
        points.append(f'定格出力の範囲に収まるのは{analysis["count_ok"]}です。')
    return {"points": points, "caution": "計算値は目安です。家電の実際の消費電力や使用環境で変わります。"}


def numbers_allowed(text, analysis):
    source = json.dumps(analysis_facts(analysis), ensure_ascii=False)
    allowed = {n.replace(",", "") for n in NUM.findall(source)}
    return all(n.replace(",", "") in allowed for n in NUM.findall(text))


def analysis_facts(analysis):
    return {k: analysis.get(k) for k in ("headers", "rows", "assumption", "best", "worst", "count_ok")}


def ask_claude(topic, analysis, client=None):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": json.dumps(
            {"title": topic["title"], "facts": analysis_facts(analysis)}, ensure_ascii=False)}],
    )
    if response.stop_reason != "end_turn":
        raise ValueError(f"unusable stop_reason: {response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def write(topic, analysis, client=None):
    if client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        return fallback(analysis)
    try:
        draft = ask_claude(topic, analysis, client)
    except Exception as exc:  # 生成失敗で週次の公開を止めない
        print(f"commentary fallback ({topic['slug']}): {exc}")
        return fallback(analysis)
    if all(numbers_allowed(t, analysis) for t in draft["points"] + [draft["caution"]]):
        return draft
    print(f"commentary fallback ({topic['slug']}): unverified number")
    return fallback(analysis)
