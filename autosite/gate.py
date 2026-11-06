"""公開前の品質ゲート。1件でも違反があれば公開しない。"""
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
import re

# 価格・評価は規約上API経由が条件。体験談の捏造や誇大表現も止める。
FORBIDDEN = {
    "price": r"\d\s*円|[¥￥]|税込",
    "rating": r"★|☆|つ星|星\d",
    "amazon_image": r"media-amazon\.com|images-amazon\.com|ssl-images",
    "exaggeration": r"最強|絶対|必ず|No\.?\s*1|業界最安|日本一|確実に",
    "fake_experience": r"使ってみた|実際に使|試してみ|愛用|買ってよかった",
}
REQUIRED = ["本文はAIにより作成"]
REQUIRED_WITH_TAG = ["本ページはプロモーションを含みます", "は適格販売により収入を得ています"]
MAX_SIMILARITY = 0.9


def visible_text(html):
    html = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S)
    return unescape(re.sub(r"<[^>]+>", " ", html))


def check_page(path, html, tag):
    required = REQUIRED + (REQUIRED_WITH_TAG if tag else [])
    problems = [f"{path}: missing '{r}'" for r in required if r not in html]
    if not tag and "amazon.co.jp" in html:
        problems.append(f"{path}: amazon link before registration")
    text = visible_text(html)
    for name, pattern in FORBIDDEN.items():
        if re.search(pattern, html if name == "amazon_image" else text):
            problems.append(f"{path}: forbidden {name}")
    for tag_html in re.findall(r"<a\b[^>]*amazon\.co\.jp[^>]*>", html):
        if f"tag={tag}" not in unescape(tag_html):
            problems.append(f"{path}: amazon link without tag")
        if 'rel="sponsored nofollow"' not in tag_html:
            problems.append(f"{path}: amazon link without rel")
    return problems


def check_article(path, html):
    problems = []
    if "<table" not in html:
        problems.append(f"{path}: no comparison table")
    if "公式情報" not in html:
        problems.append(f"{path}: no sources")
    return problems


def check_site(dist, tag):
    dist = Path(dist)
    problems, bodies = [], {}
    for path in sorted(dist.rglob("*.html")):
        html = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(dist))
        problems += check_page(rel, html, tag)
        if rel.startswith("articles/"):
            problems += check_article(rel, html)
            bodies[rel] = visible_text(html)
    names = list(bodies)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if SequenceMatcher(None, bodies[a], bodies[b], autojunk=False).ratio() > MAX_SIMILARITY:
                problems.append(f"{a}: too similar to {b}")
    return problems
