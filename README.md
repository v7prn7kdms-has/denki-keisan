# amazon-autopilot

ポータブル電源の比較サイトを週1本ずつ自動公開し、Blueskyで告知する仕組みです。
GitHub Actions が毎週月曜 9:00 JST に実行します。

## 最初に人が行うこと

1. 手順2〜5を先に行う。`AMAZON_TAG` が空の間はAmazonリンクと開示文を出さず、告知もしない
2. このフォルダをGitHubのリポジトリに置く
3. Settings > Pages の Source を GitHub Actions にする
4. Settings > Secrets and variables > Actions に次を登録する

| 種類 | 名前 | 内容 |
| --- | --- | --- |
| Variable | `SITE_NAME` | サイト名 |
| Variable | `SITE_URL` | 公開URL |
| Variable | `OPERATOR_NAME` | 開示文に載る運営者名 |
| Variable | `AMAZON_TAG` | トラッキングID（末尾 `-22`）。登録前は未設定 |
| Secret | `ANTHROPIC_API_KEY` | 任意。未設定なら計算結果のみの文章で公開 |
| Variable | `GOOGLE_SITE_VERIFICATION` | 任意。Search Consoleの確認コード（content="…" の中身） |
| Variable | `BLUESKY_HANDLE` | 任意。未設定なら告知を省略 |
| Secret | `BLUESKY_APP_PASSWORD` | 任意。Blueskyのアプリパスワード |

5. Actions の `weekly-publish` を手動実行して確認する
6. 公開されたURLでAmazonアソシエイトに登録する
7. 発行されたトラッキングIDを `AMAZON_TAG` に登録し、もう一度手動実行する

## 定期的に人が行うこと

- 180日ごとに `data/products.json` の仕様と `verified_on` を公式情報で確認する。古い機種は自動で除外され、残りが3機種未満になると公開が止まる
- `data/topics.json` の記事がなくなると、新規公開は止まる。既存記事とは別の切り口を追加する
- 売上が付いたら、Amazonアソシエイトの審査状況と規約の改定を確認する
- 収入が発生したら、税金の申告が必要かを確認する

## 手元で確認する

```bash
python3 -m unittest discover -s tests
```

```bash
python3 -m autosite.cli build --preview
```

## 公開を止める条件

`autosite/gate.py` が次を検出すると公開しません。

- 開示文やトラッキングIDの欠落
- 価格、星評価、Amazon画像
- 誇大表現、体験談の表現
- 表や情報源がない記事、内容が近すぎる記事

## このサイトの設定値

| 名前 | 値 |
| --- | --- |
| `SITE_NAME` | 電源の計算室 |
| `OPERATOR_NAME` | 電源の計算室運営事務局 |
| `SITE_URL` | `https://v7prn7kdms-has.github.io/denki-keisan` |
