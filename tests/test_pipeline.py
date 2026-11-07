import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from autosite import analysis as an
from autosite import announce, commentary, gate, render

TODAY = date(2026, 11, 5)
CFG = {"site_name": "テスト", "site_url": "https://example.com", "operator": "運営", "tag": "abc-22"}
TOPICS = an.load_json("data/topics.json")
APPLIANCES = an.load_json("data/appliances.json")
PRODUCTS = an.fresh_products(TODAY)


def result(slug):
    topic = next(t for t in TOPICS if t["slug"] == slug)
    return topic, an.analyze(topic, PRODUCTS, APPLIANCES)


def article_html(slug="fridge-runtime"):
    topic, analysis = result(slug)
    return render.article(CFG, topic, analysis, commentary.fallback(analysis), "2026-11-05")


class FakeClient:
    def __init__(self, payload, stop="end_turn"):
        block = SimpleNamespace(type="text", text=json.dumps(payload, ensure_ascii=False))
        response = SimpleNamespace(stop_reason=stop, content=[block])
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))


class AnalysisTest(unittest.TestCase):
    def test_fridge_runtime_math(self):
        _, a = result("fridge-runtime")
        self.assertEqual(a["best"][1], "約29時間")  # 1152Wh * 0.85 / 34W = 28.8
        self.assertEqual(a["worst"][1], "約13時間")

    def test_capability_excludes_nothing_and_flags_low_output(self):
        _, a = result("dryer-output")
        self.assertEqual(a["count_ok"], "4機種")
        self.assertEqual(a["rows"][-1][2], "定格超過")

    def test_missing_specs_are_never_estimated(self):
        _, a = result("capacity-per-kg")
        self.assertNotIn("Jackery ポータブル電源 500 New", [r[0] for r in a["rows"]])

    def test_stale_products_are_dropped(self):
        self.assertEqual(an.fresh_products(date(2028, 1, 1)), [])


class CommentaryTest(unittest.TestCase):
    def test_unverified_number_falls_back(self):
        topic, a = result("fridge-runtime")
        text = commentary.write(topic, a, FakeClient({"points": ["約999時間動きます"], "caution": "目安です"}))
        self.assertEqual(text, commentary.fallback(a))

    def test_verified_text_is_used(self):
        topic, a = result("fridge-runtime")
        draft = {"points": ["容量が大きいほど長く動き、約29時間が目安です"], "caution": "目安です"}
        self.assertEqual(commentary.write(topic, a, FakeClient(draft)), draft)

    def test_refusal_falls_back(self):
        topic, a = result("fridge-runtime")
        text = commentary.write(topic, a, FakeClient({"points": [], "caution": ""}, stop="refusal"))
        self.assertEqual(text, commentary.fallback(a))


class GateTest(unittest.TestCase):
    def test_clean_article_passes(self):
        self.assertEqual(gate.check_page("a.html", article_html(), "abc-22"), [])

    def test_blocks_violations(self):
        for bad in ["12,800円", "★4.5", "最強のモデル", "実際に使ってみた"]:
            html = article_html().replace("</article>", f"<p>{bad}</p></article>")
            self.assertTrue(gate.check_page("a.html", html, "abc-22"), bad)

    def test_blocks_missing_disclosure(self):
        html = article_html().replace("は適格販売により収入を得ています", "")
        self.assertTrue(gate.check_page("a.html", html, "abc-22"))

    def test_blocks_untagged_link(self):
        html = article_html().replace("tag=abc-22", "tag=other-22")
        self.assertTrue(gate.check_page("a.html", html, "abc-22"))

    def test_blocks_duplicate_articles(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp) / "articles"
            folder.mkdir()
            (folder / "a.html").write_text(article_html(), encoding="utf-8")
            (folder / "b.html").write_text(article_html(), encoding="utf-8")
            self.assertTrue(any("too similar" in p for p in gate.check_site(tmp, "abc-22")))


class BeforeRegistrationTest(unittest.TestCase):
    def setUp(self):
        topic, analysis = result("fridge-runtime")
        self.cfg = dict(CFG, tag="")
        self.html = render.article(self.cfg, topic, analysis, commentary.fallback(analysis), "2026-11-05")

    def test_no_amazon_link_or_affiliate_claim(self):
        self.assertNotIn("amazon.co.jp", self.html)
        self.assertNotIn("適格販売", self.html)
        self.assertNotIn("プロモーション", self.html)
        self.assertEqual(gate.check_page("a.html", self.html, ""), [])

    def test_about_page_makes_no_affiliate_claim(self):
        self.assertNotIn("適格販売", render.about(self.cfg))

    def test_gate_blocks_amazon_link_without_tag(self):
        self.assertTrue(gate.check_page("a.html", article_html(), ""))


class LinkAndPostTest(unittest.TestCase):
    def test_home_canonical_matches_sitemap(self):
        self.assertIn('rel="canonical" href="https://example.com/"', render.home(CFG, [], PRODUCTS))

    def test_search_link_needs_no_asin(self):
        url = render.amazon_url(PRODUCTS[0], "abc-22")
        self.assertTrue(url.startswith("https://www.amazon.co.jp/s?k="))
        self.assertTrue(url.endswith("&tag=abc-22"))

    def test_post_facet_uses_byte_offsets(self):
        url = "https://example.com/articles/a.html"
        post = announce.build_post("冷蔵庫", url, "2026-11-05T00:00:00Z")
        index = post["facets"][0]["index"]
        self.assertEqual(post["text"].encode("utf-8")[index["byteStart"]:index["byteEnd"]].decode("utf-8"), url)
        self.assertTrue(post["text"].startswith("【PR】"))


if __name__ == "__main__":
    unittest.main()
