# 毎朝AIニュースをLINEに届けるアプリ

このリポジトリは、毎朝7:00 JSTにAIニュースを収集し、日本語で要約してLINEへ通知するPythonアプリです。詳細版はGitHub PagesでHTMLとして公開します。

GitHubを初めて使う人が上から順番に作業できるように、かなり丁寧に書いています。

## 1. このアプリでできること

- 毎朝7:00 JSTに自動実行します。
- Apple / Google / OpenAI / Anthropic / Microsoft / NVIDIA / AI搭載端末・OS のニュースを集めます。
- OpenAI Responses APIの `web_search` toolでニュースを探し、OpenAI APIで日本語要約します。
- LINEには短縮版だけを送ります。
- 詳細版は `docs/YYYY-MM-DD.html` と `docs/latest.html` に保存し、GitHub Pagesで公開します。

LINEに届く内容は次の4つだけです。

- 今日の結論
- 重要ニュース3〜5本
- 今日読むべき記事1〜3本
- 詳細版リンク

## 2. 全体の仕組み

登場するものは4つです。

- GitHub: プログラムを置く場所です。
- GitHub Actions: 決まった時間にプログラムを自動実行する機能です。
- GitHub Pages: `docs` フォルダのHTMLをWebページとして公開する機能です。
- LINE Messaging API: LINE公式アカウントから自分のLINEへメッセージを送る機能です。

流れは次の通りです。

1. GitHub Actionsが毎日22:00 UTCに起動します。
2. 22:00 UTCは日本時間の翌朝7:00です。
3. `main.py` がOpenAI APIでニュースを収集・要約します。
4. `docs/YYYY-MM-DD.html` と `docs/latest.html` を作ります。
5. LINE Messaging APIで短縮版を送ります。
6. 生成したHTMLをGitHubへcommit/pushします。

## 3. 必要なもの

- GitHubアカウント
- OpenAI APIキー
- LINEアカウント
- LINE Developersアカウント
- LINE公式アカウントとMessaging APIチャネル
- このリポジトリのファイル一式

秘密情報はコードに書きません。GitHub Secretsに登録します。

必要なSecretsは次の3つです。

- `OPENAI_API_KEY`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_TO_ID`

任意で次も使えます。

- `OPENAI_MODEL`
- `SITE_BASE_URL`

`OPENAI_MODEL` を設定しない場合、デフォルトは `gpt-4.1-mini` です。将来モデルを変えたい場合はSecretに `OPENAI_MODEL` を追加してください。

## 4. GitHubアカウント作成手順

1. ブラウザで [GitHub](https://github.com/) を開きます。
2. 右上の `Sign up` をクリックします。
3. メールアドレス、パスワード、ユーザー名を入力します。
4. 画面の案内に従ってメール認証を完了します。
5. ログインできたら準備完了です。

## 5. 新しいリポジトリ作成手順

GitHubで最初にクリックする場所はここです。

1. GitHubにログイン → 右上の `＋` → `New repository` をクリックします。
2. `Repository name` に好きな名前を入れます。例: `daily-ai-news-line`
3. `Public` を選びます。GitHub Pagesを無料で使いやすくするためです。
4. `Add a README file` はチェックしてもしなくても構いません。
5. `Create repository` をクリックします。

作成後、リポジトリの画面が表示されれば成功です。

## 6. Codexで生成されたファイルをリポジトリに置く方法

このフォルダにある次のファイルを、作成したGitHubリポジトリへ入れます。

- `README.md`
- `requirements.txt`
- `main.py`
- `news_briefing.py`
- `line_sender.py`
- `site_generator.py`
- `config.py`
- `get_line_user_id.py`
- `.env.example`
- `.gitignore`
- `.github/workflows/daily_ai_news.yml`

GitHub画面で入れる場合:

1. リポジトリ画面を開きます。
2. `Add file` → `Upload files` をクリックします。
3. ファイルをドラッグ&ドロップします。
4. `Commit changes` をクリックします。

`.github/workflows/daily_ai_news.yml` はフォルダ構造が重要です。GitHub上では `.github` フォルダの中に `workflows` フォルダ、その中に `daily_ai_news.yml` がある状態にしてください。

## 7. GitHub Secretsの設定手順

Secretsは、APIキーなどの秘密情報を安全に保存する場所です。コードに直接書くと、他人に見られる危険があります。

1. GitHubのリポジトリ画面を開きます。
2. 上部メニューの `Settings` をクリックします。
3. 左メニューの `Secrets and variables` → `Actions` をクリックします。
4. `New repository secret` をクリックします。
5. `Name` にSecret名を入れます。
6. `Secret` に値を貼り付けます。
7. `Add secret` をクリックします。

登録するSecret:

| Name | 入れる値 |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI APIキー |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン |
| `LINE_TO_ID` | LINE送信先のuserId、groupId、またはroomId |
| `OPENAI_MODEL` | 任意。例: `gpt-4.1-mini` |
| `SITE_BASE_URL` | 任意。GitHub PagesのURLが推定できない場合に使います |

## 8. OpenAI APIキーの取得手順

1. [OpenAI Platform](https://platform.openai.com/) を開きます。
2. ログインします。
3. 右上のアカウントメニューからAPI keysの画面を開きます。
4. `Create new secret key` をクリックします。
5. 表示されたキーをコピーします。
6. GitHub Secretsに `OPENAI_API_KEY` として登録します。

APIキーは一度閉じると再表示できないことがあります。コピーし忘れた場合は新しく作り直してください。

## 9. LINE公式アカウント / Messaging APIチャネルの作成手順

LINE通知にはLINE Notifyではなく、LINE Messaging APIを使います。LINE Notifyは終了済みです。

1. [LINE Developers Console](https://developers.line.biz/console/) を開きます。
2. LINEアカウントでログインします。
3. 初回は開発者名などを登録します。
4. `Create a new provider` をクリックします。
5. Provider名を入力します。例: `daily-ai-news`
6. Provider作成後、`Create a Messaging API channel` をクリックします。
7. チャネル名、説明、カテゴリなどを入力します。
8. 作成を完了します。

通知を受け取るには、自分のLINEアプリで作成したLINE公式アカウントを友だち追加する必要があります。LINE Developers ConsoleのMessaging API設定画面にQRコードが表示されます。スマホのLINEアプリで読み取り、友だち追加してください。

## 10. LINE_CHANNEL_ACCESS_TOKENの取得手順

1. LINE Developers Consoleで作成したMessaging APIチャネルを開きます。
2. `Messaging API` タブを開きます。
3. 下の方にある `Channel access token` を探します。
4. `Issue` または `Reissue` をクリックします。
5. 表示された長い文字列をコピーします。
6. GitHub Secretsに `LINE_CHANNEL_ACCESS_TOKEN` として登録します。

このトークンは絶対に公開しないでください。

## 11. LINE_TO_IDの取得方法

`LINE_TO_ID` は、LINE Messaging APIで「誰に送るか」を表すIDです。自分宛てに送る場合は `userId` を使います。

ここが初心者には一番詰まりやすいです。GitHub ActionsだけではWebhookを受信できません。そのため、ローカルPCで一時的に小さなFlaskアプリを起動し、ngrokなどで一時公開URLを作って確認します。

### 11-1. ローカルで確認用サーバーを起動する

PCのターミナルで、このリポジトリのフォルダに移動してから実行します。

```bash
python -m pip install -r requirements.txt
python get_line_user_id.py
```

成功すると、次のような表示になります。

```text
* Running on http://127.0.0.1:5000
```

### 11-2. ngrokで一時公開URLを作る

ngrokを使う場合:

1. [ngrok](https://ngrok.com/) でアカウントを作ります。
2. ngrokをインストールします。
3. 別のターミナルで次を実行します。

```bash
ngrok http 5000
```

表示された `https://...ngrok-free.app` のようなURLをコピーします。

### 11-3. LINE Developers ConsoleにWebhook URLを設定する

1. LINE Developers ConsoleでMessaging APIチャネルを開きます。
2. `Messaging API` タブを開きます。
3. `Webhook URL` に次のように入力します。

```text
https://あなたのngrok URL/webhook
```

4. `Update` をクリックします。
5. `Use webhook` をオンにします。
6. `Verify` をクリックし、成功することを確認します。

### 11-4. LINEアプリからメッセージを送る

1. スマホのLINEアプリを開きます。
2. 作成したLINE公式アカウントのトーク画面を開きます。
3. 何でもよいのでメッセージを1通送ります。例: `test`
4. PCのターミナルを見ると、WebhookのJSONが表示されます。
5. `コピーするID (userId): Uxxxxxxxx...` と表示された値をコピーします。
6. GitHub Secretsに `LINE_TO_ID` として登録します。

確認が終わったら、ローカルのFlaskアプリとngrokは止めて構いません。これは本番用ではなく、LINE_TO_ID確認用の一時的な補助ツールです。

## 12. GitHub Pagesの設定手順

このアプリはActionsによるPages Deployではなく、`Deploy from a branch` を使います。公開元は `main` ブランチの `/docs` フォルダです。

1. GitHubのリポジトリ画面を開きます。
2. `Settings` をクリックします。
3. 左メニューの `Pages` をクリックします。
4. `Build and deployment` を探します。
5. `Source` を `Deploy from a branch` にします。
6. `Branch` を `main` にします。
7. フォルダを `/docs` にします。
8. `Save` をクリックします。

しばらくするとPagesのURLが表示されます。例:

```text
https://あなたのGitHubユーザー名.github.io/リポジトリ名/
```

このアプリは `SITE_BASE_URL` が設定されていればそれを使います。未設定の場合は `GITHUB_REPOSITORY` から次の形を推定します。

```text
https://<owner>.github.io/<repo>/
```

推定URLが404になる場合は、GitHub Pages画面に表示された正しいURLをGitHub Secretsの `SITE_BASE_URL` に登録してください。

## 13. GitHub Actionsを手動実行する方法

初回は手動実行して確認します。

1. GitHubのリポジトリ画面を開きます。
2. 上部の `Actions` タブをクリックします。
3. 左側の `daily_ai_news` をクリックします。
4. 右側の `Run workflow` をクリックします。
5. 緑色の `Run workflow` ボタンをクリックします。
6. 実行中の行をクリックするとログが見られます。

初回確認は「LINE通知が来たか」だけで判断しないでください。Actionsログで次を確認します。

1. OpenAI APIのニュース生成が成功しているか
2. `docs/YYYY-MM-DD.html` と `docs/latest.html` が生成されているか
3. `docs` 配下の変更がcommit/pushされているか
4. LINE Messaging APIへの送信がHTTP 200で成功しているか
5. GitHub PagesのURLが正しいか

## 14. 毎朝7:00 JSTに動く仕組み

GitHub Actionsの設定は `.github/workflows/daily_ai_news.yml` にあります。

```yaml
schedule:
  - cron: "0 22 * * *"
```

GitHub ActionsのcronはUTCで書きます。日本時間はUTCより9時間進んでいます。

- 22:00 UTC
- 9時間足す
- 翌朝 7:00 JST

そのため、毎日22:00 UTCに実行すると、日本では毎朝7:00に動きます。

## 15. LINEに通知が来ない場合の確認ポイント

まずActionsログを見ます。

1. `Actions` タブ → `daily_ai_news` → 最新の実行結果をクリックします。
2. `Generate briefing and send LINE message` を開きます。
3. `LINE送信に成功しました。status=200` があるか確認します。

よくある原因:

- 自分のLINEアプリでLINE公式アカウントを友だち追加していない
- `LINE_CHANNEL_ACCESS_TOKEN` が間違っている
- `LINE_TO_ID` が間違っている
- Messaging APIチャネルではないチャネルのトークンを使っている
- LINE Developers Consoleでチャネルを削除・再発行した

LINE送信失敗時はHTTPステータスコードとエラー本文をログに出します。ただし、`LINE_CHANNEL_ACCESS_TOKEN` はログに出しません。

## 16. 詳細版リンクが開けない場合の確認ポイント

1. GitHubのリポジトリ画面で `docs` フォルダを開きます。
2. `YYYY-MM-DD.html` と `latest.html` があるか確認します。
3. `Settings` → `Pages` を開きます。
4. `Source: Deploy from a branch`、`Branch: main / docs` になっているか確認します。
5. Pagesに表示されたURLを開きます。
6. 404になる場合は、その正しいURLをSecret `SITE_BASE_URL` に登録します。

例:

```text
Name: SITE_BASE_URL
Secret: https://your-name.github.io/daily-ai-news-line/
```

末尾の `/` はあってもなくても動きます。

## 17. よくあるエラーと対処法

### `OPENAI_API_KEY が設定されていません`

GitHub Secretsに `OPENAI_API_KEY` がありません。`Settings` → `Secrets and variables` → `Actions` から追加してください。

### `LINE_CHANNEL_ACCESS_TOKEN が設定されていません`

GitHub Secretsに `LINE_CHANNEL_ACCESS_TOKEN` がありません。LINE Developers Consoleから取得して登録してください。

### `LINE_TO_ID が設定されていません`

GitHub Secretsに `LINE_TO_ID` がありません。`get_line_user_id.py` とngrokで `userId` を確認してください。

### OpenAI APIのレート制限

短時間に使いすぎた、または利用上限に達した可能性があります。OpenAI PlatformのBillingやUsageを確認してください。

### JSONパース失敗

OpenAIの返却JSONが壊れた場合、このアプリは自動で再試行します。最終的に失敗した場合は、安全なフォールバックHTMLを作ります。

### ニュースが少ない

条件に合うニュースが少ない日は、無理に水増ししません。詳細版やLINEには「本日は条件に合う重要ニュースが少なめです」と表示されます。

### Actionsのpushが失敗する

次を確認します。

1. `Settings` → `Actions` → `General` を開きます。
2. `Workflow permissions` を探します。
3. `Read and write permissions` を選びます。
4. `Save` をクリックします。

workflow側にも次を設定済みです。

```yaml
permissions:
  contents: write
```

## 18. APIキーをコードに書いてはいけない理由

GitHubに置いたコードは、設定によっては誰でも見られます。APIキーやLINEトークンをコードに書くと、他人に使われて料金が発生したり、自分のLINEに勝手に送信されたりする危険があります。

このアプリは秘密情報を環境変数から読み込みます。GitHub Actionsでは環境変数の値をGitHub Secretsから渡します。

ローカル確認用に `.env.example` はありますが、本物の `.env` はGitHubにアップロードしません。`.gitignore` に `.env` を入れてあります。

## 19. カスタマイズ方法

### モデルを変える

GitHub Secretsに `OPENAI_MODEL` を追加します。

例:

```text
gpt-4.1-mini
```

### 詳細版URLを固定する

推定URLが外れる場合は `SITE_BASE_URL` を追加します。

例:

```text
https://your-name.github.io/daily-ai-news-line/
```

### ニュース条件を変える

`news_briefing.py` の `_build_prompt()` を編集します。Apple優先、株価・決算除外、噂の扱いなどはここに書いてあります。

### LINEメッセージの分割長を変える

`line_sender.py` の `MAX_LINE_TEXT_LENGTH` を変更します。

## 20. 運用停止方法

自動実行を止める方法は2つあります。

### 方法A: workflowを無効化する

1. GitHubのリポジトリ画面を開きます。
2. `Actions` タブをクリックします。
3. 左側の `daily_ai_news` をクリックします。
4. 右上の `...` から `Disable workflow` をクリックします。

### 方法B: cronを消す

`.github/workflows/daily_ai_news.yml` の次の部分を削除します。

```yaml
schedule:
  - cron: "0 22 * * *"
```

`workflow_dispatch` を残せば、手動実行だけはできます。

## ファイルの役割

| ファイル | 役割 |
| --- | --- |
| `main.py` | 全体の実行入口。設定読み込み、ニュース生成、HTML生成、LINE送信を行います |
| `config.py` | 環境変数とSecretの読み込み、詳細版URLの推定を行います |
| `news_briefing.py` | OpenAI Responses APIとweb_search toolでニュースを生成します |
| `site_generator.py` | MarkdownをHTMLに変換し、`docs` に保存します |
| `line_sender.py` | LINE Messaging APIのpush messageで送信します |
| `get_line_user_id.py` | LINE_TO_ID確認用の一時的なFlaskアプリです |
| `requirements.txt` | Python依存ライブラリ一覧です |
| `.github/workflows/daily_ai_news.yml` | GitHub Actionsの自動実行設定です |
| `.env.example` | ローカル用環境変数の見本です。本物の秘密情報は入れません |
| `.gitignore` | `.env` などGitHubに上げないファイルを指定します |

