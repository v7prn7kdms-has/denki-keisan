"""週次の点検。結果をMarkdownで出す。何も変更しない。"""
from datetime import date, datetime, timedelta, timezone
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import analysis as an
from . import gate

ASSOCIATE_SALES_DAYS = 180
GITHUB_IDLE_DAYS = 60


def fetch(url):
    request = Request(url, headers={"User-Agent": "denki-keisan-weekly-report"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def remaining_topics(entries, today):
    products = an.fresh_products(today)
    appliances = an.load_json("data/appliances.json")
    done = {e["slug"] for e in entries}
    return [t for t in an.load_json("data/topics.json")
            if t["slug"] not in done and len(an.analyze(t, products, appliances)["rows"]) >= an.MIN_ROWS]


def stale_dates(today):
    """機種ごとに、掲載対象から外れる日。"""
    return sorted((date.fromisoformat(p["verified_on"]) + timedelta(days=an.STALE_AFTER_DAYS), an.label(p))
                  for p in an.load_json("data/products.json"))


def check_live(site, entries, tag):
    problems, pages = [], ["", "about.html"] + [f'articles/{e["slug"]}.html' for e in entries]
    for page in pages:
        url = f"{site.rstrip('/')}/{page}"
        try:
            html = fetch(url)
        except (HTTPError, URLError) as exc:
            problems.append(f"{url} を開けません（{exc}）")
            continue
        problems += [f"{url}: {p.split(': ', 1)[1]}" for p in gate.check_page(page or "index.html", html, tag)]
    return len(pages), problems


def run(repo, site, tag, associate_since, today=None):
    today = today or date.today()
    api = f"https://api.github.com/repos/{repo}"
    entries = json.loads(fetch(f"https://raw.githubusercontent.com/{repo}/main/state/published.json"))
    runs = json.loads(fetch(f"{api}/actions/runs?per_page=5"))["workflow_runs"]
    repo_info = json.loads(fetch(api))
    pushed = datetime.fromisoformat(repo_info["pushed_at"].replace("Z", "+00:00"))
    created = date.fromisoformat(repo_info["created_at"][:10])
    page_count, live_problems = check_live(site, entries, tag)
    todo, lines = [], [f"# 電源の計算室 週次レポート（{today}）", ""]

    lines += ["## 自動公開の実行", ""]
    for r in runs:
        mark = "成功" if r["conclusion"] == "success" else (r["conclusion"] or r["status"])
        lines.append(f'- {r["created_at"][:10]} {r["event"]}: {mark}')
        if r["conclusion"] not in ("success", None):
            todo.append(f'{r["created_at"][:10]} の実行が {r["conclusion"]} です: {r["html_url"]}')
    scheduled = [r for r in runs if r["event"] == "schedule"]
    last = date.fromisoformat(scheduled[0]["created_at"][:10]) if scheduled else created
    if (today - last).days > 8:
        todo.append("定期実行が8日以上動いていません。Actions画面で停止していないか確認してください")

    left = remaining_topics(entries, today)
    lines += ["", "## 記事", "", f"- 公開済み: {len(entries)}本", f"- 公開待ち: {len(left)}本"]
    lines.append(f'- 次回公開: {left[0]["title"]}' if left else "- 次回公開: なし（新しいテーマが必要です）")
    if not left:
        todo.append("公開待ちの記事がありません。新しい比較テーマの追加が必要です")
    lines += [f'- {e["date"]} {e["title"]}' for e in entries]

    lines += ["", "## 公開ページの検査", "", f"- 検査したページ: {page_count}", f"- 問題: {len(live_problems)}件"]
    todo += live_problems

    idle = (datetime.now(timezone.utc) - pushed).days
    stale = stale_dates(today)
    deadline = date.fromisoformat(associate_since) + timedelta(days=ASSOCIATE_SALES_DAYS)
    lines += ["", "## 期限", "",
              f"- GitHubの最終更新から{idle}日（{GITHUB_IDLE_DAYS}日で定期実行が止まる）",
              f"- 最初に掲載から外れる機種: {stale[0][1]}（{stale[0][0]}）",
              f"- Amazonの売上3件の期限の目安: {deadline}（残り{(deadline - today).days}日）"]
    if idle >= GITHUB_IDLE_DAYS - 14:
        todo.append(f"GitHubの更新が{idle}日ありません。{GITHUB_IDLE_DAYS}日で定期実行が止まります")
    if (stale[0][0] - today).days <= 30:
        todo.append(f"{stale[0][0]} に機種データの確認期限が来ます。公式ページを見直してください")

    lines += ["", "## 要対応", ""] + ([f"- {t}" for t in todo] or ["- なし"])
    lines += ["", "売上とクリック数は自動では取得していません。Amazonアソシエイトの管理画面の数字を教えてください。"]
    return "\n".join(lines)
