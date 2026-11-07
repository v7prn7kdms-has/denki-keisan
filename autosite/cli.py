"""build: サイト生成 / publish: 次の記事を1本公開 / announce: 公開済みの新着を告知"""
import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys

from . import analysis as an
from . import announce, commentary, gate, render, report

STATE = an.ROOT / "state" / "published.json"
DIST = an.ROOT / "dist"
PREVIEW = {"site_name": "電源の計算室（プレビュー）", "site_url": "https://example.com",
           "operator": "プレビュー運営者", "tag": "preview-22"}


def load_config(preview):
    if preview:
        return dict(PREVIEW)
    cfg = {"site_name": os.environ.get("SITE_NAME", ""), "site_url": os.environ.get("SITE_URL", ""),
           "operator": os.environ.get("OPERATOR_NAME", ""), "tag": os.environ.get("AMAZON_TAG", "")}
    missing = [k for k, v in cfg.items() if not v and k != "tag"]
    if missing:
        sys.exit(f"設定が未入力です: {', '.join(missing)}")
    if cfg["tag"] and not re.fullmatch(r"[A-Za-z0-9-]+-22", cfg["tag"]):
        sys.exit("AMAZON_TAG は日本のトラッキングID（末尾 -22）を指定してください")
    return cfg


def next_topic(published, products, appliances):
    done = {e["slug"] for e in published}
    for topic in an.load_json("data/topics.json"):
        if topic["slug"] not in done and len(an.analyze(topic, products, appliances)["rows"]) >= an.MIN_ROWS:
            return topic
    return None


def build(cfg, entries, today, client=None):
    products = an.fresh_products(today)
    if len(products) < an.MIN_ROWS:
        sys.exit("確認から180日以内の機種が足りないため公開を止めました。data/products.json を更新してください")
    appliances = an.load_json("data/appliances.json")
    topics = {t["slug"]: t for t in an.load_json("data/topics.json")}
    shutil.rmtree(DIST, ignore_errors=True)
    (DIST / "articles").mkdir(parents=True)
    shown = []
    for entry in entries:
        topic = topics[entry["slug"]]
        result = an.analyze(topic, products, appliances)
        if len(result["rows"]) < an.MIN_ROWS:
            continue  # 古い機種を外した結果、比較が成り立たない記事は載せない
        key = an.facts_key(result)
        if entry.get("text") and entry.get("facts_key") == key:
            text = entry["text"]
        else:  # 機種の追加などで表が変わったら、古い解説文は使わない
            text = commentary.write(topic, result, client)
        entry["text"], entry["facts_key"] = text, key
        (DIST / "articles" / f'{topic["slug"]}.html').write_text(
            render.article(cfg, topic, result, text, entry["date"]), encoding="utf-8")
        shown.append(topic)
    (DIST / "index.html").write_text(render.home(cfg, shown, products), encoding="utf-8")
    (DIST / "about.html").write_text(render.about(cfg), encoding="utf-8")
    root = cfg["site_url"].rstrip("/")
    urls = [f"{root}/"] + [f'{root}/articles/{t["slug"]}.html' for t in shown]
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{u}</loc></url>" for u in urls) + "</urlset>", encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {root}/sitemap.xml\n", encoding="utf-8")
    problems = gate.check_site(DIST, cfg["tag"])
    if problems:
        shutil.rmtree(DIST, ignore_errors=True)
        sys.exit("品質ゲートで停止しました:\n" + "\n".join(problems))


def save(entries):
    STATE.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_publish(cfg, today):
    entries = json.loads(STATE.read_text(encoding="utf-8"))
    products = an.fresh_products(today)
    topic = next_topic(entries, products, an.load_json("data/appliances.json"))
    if topic:
        entries.append({"slug": topic["slug"], "title": topic["title"], "date": today.isoformat()})
    build(cfg, entries, today)
    save(entries)
    print(f'published: {topic["slug"]}' if topic else "no new topic; site rebuilt")


def cmd_announce(cfg):
    if not cfg["tag"]:
        print("announce skipped: AMAZON_TAG is not set")  # 登録後に順次告知する
        return
    entries = json.loads(STATE.read_text(encoding="utf-8"))
    pending = [e for e in entries if not e.get("announced")]
    for entry in pending[:1]:
        url = f'{cfg["site_url"].rstrip("/")}/articles/{entry["slug"]}.html'
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if announce.send(announce.build_post(entry["title"], url, now)):
            entry["announced"] = True
    save(entries)


def main():
    parser = argparse.ArgumentParser(prog="autosite")
    parser.add_argument("command", choices=["build", "publish", "announce", "report"])
    parser.add_argument("--preview", action="store_true", help="全記事を設定なしで dist/ に生成する")
    parser.add_argument("--repo", default="v7prn7kdms-has/denki-keisan")
    parser.add_argument("--site", default="https://v7prn7kdms-has.github.io/denki-keisan")
    parser.add_argument("--tag", default="denkikeisan-22")
    parser.add_argument("--associate-since", default="2026-11-07")
    args = parser.parse_args()
    today = date.today()
    if args.command == "report":  # 公開用の設定は使わず、公開中のサイトとGitHubを読むだけ
        print(report.run(args.repo, args.site, args.tag, args.associate_since, today))
        return
    cfg = load_config(args.preview)
    if args.command == "publish":
        cmd_publish(cfg, today)
    elif args.command == "announce":
        cmd_announce(cfg)
    elif args.preview:
        entries = [{"slug": t["slug"], "title": t["title"], "date": today.isoformat()}
                   for t in an.load_json("data/topics.json")]
        build(cfg, entries, today)
        print("preview built in dist/")
    else:
        build(cfg, json.loads(STATE.read_text(encoding="utf-8")), today)


if __name__ == "__main__":
    main()
