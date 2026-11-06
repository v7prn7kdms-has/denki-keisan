"""新着記事をBlueskyへ告知する。リンク先は自サイトのみで、Amazonへ直接リンクしない。"""
import json
import os
from urllib.request import Request, urlopen

API = "https://bsky.social/xrpc"


def build_post(title, url, created_at):
    prefix = f"【PR】新しい比較記事：{title}\n"
    text = prefix + url
    start = len(prefix.encode("utf-8"))
    return {
        "$type": "app.bsky.feed.post", "text": text, "createdAt": created_at, "langs": ["ja"],
        "facets": [{"index": {"byteStart": start, "byteEnd": start + len(url.encode("utf-8"))},
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]}],
    }


def _call(method, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{API}/{method}", json.dumps(payload).encode("utf-8"), headers)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def send(post):
    handle, password = os.environ.get("BLUESKY_HANDLE"), os.environ.get("BLUESKY_APP_PASSWORD")
    if not handle or not password:
        print("announce skipped: Bluesky is not configured\n" + post["text"])
        return False
    session = _call("com.atproto.server.createSession", {"identifier": handle, "password": password})
    _call("com.atproto.repo.createRecord",
          {"repo": session["did"], "collection": "app.bsky.feed.post", "record": post}, session["accessJwt"])
    return True
