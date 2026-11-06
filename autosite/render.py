"""静的HTMLの生成。Amazonの画像・価格・レビューは載せない。"""
from html import escape
import json
from urllib.parse import quote

CSS = """
:root{--bg:#fbfaf7;--ink:#1f2421;--muted:#5d665f;--line:#dcdfd8;--accent:#17603f;--tint:#eaf3ed}
@media (prefers-color-scheme:dark){:root{--bg:#161a18;--ink:#e8ebe7;--muted:#a3ada5;--line:#333b36;--accent:#7fd1a4;--tint:#1f2c25}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.8 "Hiragino Sans","Noto Sans JP",sans-serif}
main,header,footer{max-width:760px;margin:auto;padding:0 16px}header{padding-top:20px}
.brand{font-weight:700;color:var(--ink);text-decoration:none}a{color:var(--accent)}
h1{font-size:1.65rem;line-height:1.4;margin:.6em 0 .4em}h2{font-size:1.2rem;margin-top:2em}
.pr{font-size:.82rem;color:var(--muted);border:1px solid var(--line);padding:8px 12px;border-radius:6px;margin:12px 0}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:520px;font-size:.92rem}
th,td{border-bottom:1px solid var(--line);padding:8px 10px;text-align:left}th{background:var(--tint)}
.calc{background:var(--tint);padding:14px 16px;border-radius:8px}.calc label{display:inline-block;margin-right:14px}
input{width:6em;padding:4px;font:inherit}footer{color:var(--muted);font-size:.82rem;padding-top:24px;padding-bottom:32px}
"""


def amazon_url(product, tag):
    if product.get("asin"):
        return f'https://www.amazon.co.jp/dp/{product["asin"]}?tag={quote(tag)}'
    return f'https://www.amazon.co.jp/s?k={quote(product["search"])}&tag={quote(tag)}'


def disclosure(cfg):
    if not cfg["tag"]:  # 登録前はアソシエイトではないので開示文も出さない
        return ""
    return f'Amazonのアソシエイトとして、{escape(cfg["operator"])}は適格販売により収入を得ています。'


def promotion(cfg):
    return f"本ページはプロモーションを含みます。{disclosure(cfg)}<br>" if cfg["tag"] else ""


def page(cfg, title, description, body, base, path):
    canonical = f'{cfg["site_url"].rstrip("/")}/{path}'
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(description)}">
<link rel="canonical" href="{escape(canonical)}"><style>{CSS}</style></head><body>
<header><a class="brand" href="{base}index.html">{escape(cfg["site_name"])}</a>
<p class="pr">{promotion(cfg)}本文はAIにより作成し、数値は公式スペックからの自動計算で検証しています。</p></header>
<main>{body}</main>
<footer><a href="{base}about.html">運営者情報と調査方法</a><br>{disclosure(cfg)}</footer></body></html>"""


def table(headers, rows):
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def article(cfg, topic, analysis, text, published_on):
    links = "".join(
        f'<li>{escape(p["brand"])} {escape(p["model"])}：'
        + (f'<a rel="sponsored nofollow" href="{escape(amazon_url(p, cfg["tag"]))}">Amazonで見る</a>' if cfg["tag"] else "")
        + f'（<a href="{escape(p["source_url"])}">公式情報</a>、{p["verified_on"]}確認）'
        + (f'<br><small>{escape(p["note"])}</small>' if p.get("note") else "") + "</li>"
        for p in analysis["products"])
    points = "".join(f"<li>{escape(t)}</li>" for t in text["points"])
    body = f"""<article><h1>{escape(topic["title"])}</h1><p>{escape(topic["lead"])}</p>
<h2>計算結果</h2>{table(analysis["headers"], analysis["rows"])}
<p><small>{escape(analysis["assumption"])}</small></p>
<h2>選ぶときのポイント</h2><ul>{points}</ul><p>{escape(text["caution"])}</p>
<h2>掲載機種と情報源</h2><ul>{links}</ul>
<p><small>公開日 {published_on}。最新の仕様、価格、在庫は各リンク先で確認してください。</small></p></article>"""
    return page(cfg, topic["title"], topic["lead"], body, "../", f'articles/{topic["slug"]}.html')


def home(cfg, published, products):
    items = "".join(f'<li><a href="articles/{escape(t["slug"])}.html">{escape(t["title"])}</a></li>' for t in published)
    data = json.dumps([{"n": f'{p["brand"]} {p["model"]}', "c": p["capacity_wh"], "o": p["ac_output_w"]} for p in products],
                      ensure_ascii=False).replace("<", "\\u003c")
    body = f"""<h1>ポータブル電源を、計算で選ぶ</h1>
<p>メーカー公式の仕様をもとに、使える時間や動かせる家電を計算して比較します。</p>
<h2>必要な容量の計算機</h2><div class="calc"><label>消費電力 <input id="w" type="number" min="1" value="100">W</label>
<label>使う時間 <input id="h" type="number" min="0.1" step="0.5" value="8">時間</label>
<p id="out" aria-live="polite"></p></div><h2>比較記事</h2><ul>{items or "<li>準備中です</li>"}</ul>
<script>const P={data},R=0.85,f=()=>{{const w=+document.getElementById('w').value,h=+document.getElementById('h').value;
const n=P.filter(p=>p.o>=w&&p.c*R>=w*h).map(p=>p.n);
document.getElementById('out').textContent='必要な容量の目安は'+Math.ceil(w*h/R)+'Whです。条件を満たす掲載機種：'+(n.join('、')||'なし');}};
['w','h'].forEach(i=>document.getElementById(i).addEventListener('input',f));f();</script>"""
    return page(cfg, cfg["site_name"], "公式スペックからの計算でポータブル電源を比較します。", body, "", "index.html")


def about(cfg):
    ads = (f'<h2>広告について</h2><p>{disclosure(cfg)} リンクから購入された場合、当サイトが紹介料を受け取ることがありますが、'
           "計算結果には影響しません。</p>") if cfg["tag"] else ""
    body = f"""<h1>運営者情報と調査方法</h1><p>運営者：{escape(cfg["operator"])}</p>
<h2>調査方法</h2><p>各機種の数値はメーカー公式の公開情報から確認し、確認日を記載しています。
実機の検証は行っていません。比較表は仮定を明記した計算値であり、実際の性能を保証するものではありません。</p>
{ads}<h2>AIの利用</h2><p>本文の作成にAIを利用しています。本文中の数値は計算結果と自動で照合しています。</p>"""
    return page(cfg, f'運営者情報｜{cfg["site_name"]}', "運営者情報と調査方法", body, "", "about.html")
