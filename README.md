# 毎朝AIニュースをLINEに届けるアプリ

このリポジトリは、AI・ITニュースを毎朝自動で収集し、日本語で要約してLINEへ通知するアプリです。詳細版はHTMLとして `docs` フォルダに保存し、GitHub Pagesで公開します。

現在の実装では、GitHub Actionsの `schedule` / `cron` は使いません。Google Apps Scriptの時間主導トリガーが毎朝7:07 JSTごろにGitHub Actionsを起動し、7:37 JSTごろにバックアップ起動します。これは、GitHub Actionsのcronが混雑で大幅に遅れて夜に実行されたことがあるためです。

このREADMEは、GitHub、GitHub Actions、Google Apps Script、LINE Developersを初めて触る人でも、上から順番に作業すれば運用できるように書いています。

## 最初に読む結論

このアプリは2つの部品で動きます。

| 部品 | 役割 |
| --- | --- |
| GitHub Actions | OpenAIでニュースを収集・要約し、HTMLを作り、LINEに送ります |
| Google Apps Script | LINE友だち追加のWebhook、登録申請、管理者承認、毎朝のGitHub Actions起動を担当します |

現在の正式な定期実行ルートは次です。

1. Google Apps Scriptの時間主導トリガーが7:07 JSTごろに動く。
2. GASの `dispatchDailyAiNewsWorkflow()` がGitHub APIの `workflow_dispatch` を呼ぶ。
3. GitHub Actionsの `daily_ai_news` が起動する。
4. Pythonの `main.py` がOpenAI Responses API + `web_search` toolでニュースを生成する。
5. `docs/YYYY-MM-DD.html` と `docs/latest.html` を作る。
6. LINE Messaging APIで短縮版を送る。
7. `docs` の変更と送信済みマーカーをGitHubへcommit/pushする。
8. 7:37 JSTごろのバックアップ実行は、送信済みマーカーがあればスキップする。

重要な注意点です。

- 実際の起動は7:07 JSTごろです。ただし、ニュース詳細版の表記はこれまで通り `7:00 JST` としています。
- GitHub Actionsのcronは使いません。
- `OPENAI_MODEL` をGitHub Secretsに設定している場合、その値が最優先されます。
- `OPENAI_MODEL` が未設定の場合、コードのデフォルトは `gpt-5.5-2026-04-23` です。
- OpenAI Billingの残高が0以下、またはAuto rechargeがOFFで残高不足の場合、OpenAI APIは失敗します。`429 Too Many Requests` と出ることがあります。
- LINE公式アカウントを友だち追加しただけではニュースは届きません。承認制を使う場合は、管理者が `approve` した人だけに届きます。
- `LINE_TO_ID` だけ設定する従来の単独送信モードも残っています。

## このアプリでできること

- AI・IT技術ニュースを毎朝自動収集します。
- OpenAI Responses APIの `web_search` toolを使って、7:00 JSTのブリーフィング時点から過去24時間以内に公開されたニュースだけを調査します。
- 日本語でLINE短縮版と詳細版を作ります。
- LINE短縮版は固定テンプレートで送ります。
- 詳細版はGitHub Pagesで読めるHTMLにします。
- LINE短縮版と詳細版で、重要ニュースの内容・順序・重要度・信頼度・URLがずれないように、`news_items` という共通リストを正本にします。
- LINE公式アカウントを友だち追加した人を `pending` として保存し、管理者が承認した人だけへ配信できます。
- 7:07 JST実行が失敗した場合に備えて、7:37 JSTごろにバックアップ実行できます。
- 成功済みの日は送信済みマーカーで二重送信を防ぎます。

## ニュース収集対象

現在のプロンプトは、Appleだけを最優先にはしていません。Apple、Google、Microsoft、Meta、Amazon、OpenAI、Anthropic、NVIDIAを同じ重要度の対象企業として扱い、AI・IT技術全体で重要度が高いニュースを優先します。

対象範囲は次です。

- AIモデル、生成AI、AIエージェント、AIアプリ
- Apple、Google、Microsoft、Meta、Amazon、OpenAI、Anthropic、NVIDIAの主要ニュース
- Apple、Google、MicrosoftなどのOS・端末・ブラウザ・アプリへのAI統合
- AIアシスタント、AIエージェント、AI検索、AIブラウザ
- API、開発基盤、開発者向けAIツール、AIコーディング
- NVIDIA、AMD、Intel、Qualcomm、ArmなどのAI半導体・AI実行基盤
- AI PC、オンデバイスAI、ローカルAI、エッジAI、AI搭載スマートフォン
- クラウドAI、データセンター、電力、冷却、GPU、メモリ、ストレージ
- セキュリティ、プライバシー、著作権、規制などAI利用に影響する重要トピック

採用するソースは、原則として次の条件を満たすものだけです。

- 7:00 JSTのブリーフィング時点から過去24時間以内に公開された記事または公式発表である。
- 見出しだけでなく、本文、公式発表、記事スニペット、要約、または信頼できる補強ソースで内容を確認できる。
- 日本語記事を優先する。ただし、英語・海外記事が一次情報、より詳細、より速い、より信頼できる、または日本語記事が不十分な場合は英語・海外記事を使う。
- 有料記事やペイウォール記事は、見出しだけでは使わない。内容を確認できる場合だけ `有料記事・確認済み` として扱う。

24時間より古い記事は、背景説明や続報のソースとしても原則使いません。古い出来事に触れる場合は、過去24時間以内の記事本文の中で参照されている場合だけにし、ソース記事自体が新しいことが分かるようにします。

選定順位は次です。

1. Apple、Google、Microsoft、Meta、Amazon、OpenAI、Anthropic、NVIDIAの、ユーザー影響またはプラットフォーム戦略への影響が大きいニュース。
2. 上記以外でも、AIエージェント、オンデバイスAI、AIコーディング、AIセキュリティ、モデル能力、AIインフラ、チップ、メモリ、ストレージ、データセンター、電力、冷却、AI搭載端末・OSに実質的影響があるニュース。
3. 競争環境、規制・アクセス、エコシステム戦略、製品方向性を変える広いAI業界ニュース。

同じ優先度の中では、ユーザー影響とプラットフォーム重要度、新しさ、ソース信頼性、実用性、技術的な面白さの順で判断します。

除外するものです。

- 株価中心の記事
- 決算中心の記事
- 投資家向けニュース
- アナリスト評価、目標株価
- M&A観測中心の記事
- 内容が薄い転載記事、広告記事、SEO目的の記事
- kintone、社内業務改善、業務フロー設計、WWDC資料作成向け観点

ただし、消費者向け製品価格、製品提供・在庫・発売時期、サブスクリプション価格、AIハードウェア費用、メモリ・ストレージ費用、AI搭載端末の採用や普及などは、購入判断やユーザー体験、プラットフォーム戦略に影響する場合は採用対象です。

噂情報は、信頼できる媒体に限って扱い、必ず「噂」または「未確認情報」と明記する方針です。

## LINEに届く形式

LINEには詳細版全文は送りません。短縮版だけを送ります。

現在の `line_message` は次の固定テンプレートです。

```text
【今日の結論】
今日の全体傾向を2〜4文で説明します。

【重要ニュース】

1. カテゴリ｜ニュース見出し
    概要：何が起きたか
    重要度：高/中/低
    信頼度：公式/大手報道/専門メディア/噂/有料記事・確認済み
    意味：個人の製品体験、技術トレンド、購入判断、主要企業動向の理解として何を意味するか

【今日読むべき記事】

1. 記事タイトル
    理由：読むべき理由
    URL：URL

【補足】
今日のニュースの読み方、ニュースが少ない場合の補足など

詳細版: https://...
```

LINEメッセージが長い場合、`line_sender.py` が複数メッセージに分割します。分割時も、最初の1通に「今日の結論」「重要ニュース」「詳細版リンク」が入るようにしています。

## 詳細版HTMLの形式

詳細版は `docs/YYYY-MM-DD.html` と `docs/latest.html` に保存されます。

構成は次です。

```text
AIニュース詳細版｜YYYY年MM月DD日 7:00 JST

Selection basis
今日の結論
Apple
Google
Microsoft
Meta/Amazon
Other AI
今日読むべき記事
深掘り候補
補足
```

`Selection basis` には、24時間の対象範囲、除外したもの、ランキングロジック、ソース方針、トップニュースを選んだ理由が入ります。

詳細版はカテゴリ別に整理します。ただし、LINE短縮版と詳細版で、同じニュースのタイトル、重要度、信頼度、URLが変わらないように、内部では `news_items` という共通リストを正本にしています。カテゴリ内では `news_items` の相対順序を保ちます。

詳細版の各ニュース見出し番号は、カテゴリ内の連番ではなく、LINE短縮版の「重要ニュース」と同じ全体順位番号です。たとえばLINEの1番が `Other AI` のニュースなら、詳細版では `Other AI` セクション内に `### 1.` として出ます。これにより、LINEと詳細版を見比べても同じニュースを追えるようにしています。

各ニュースには次を入れます。

- 見出し
- 3行要約
- 公開タイミング
- 重要度
- 信頼度
- 選定理由
- 中長期的な意味
- 自分向けの意味
- 解釈・評価
- 今後の見通し
- ソースURL

該当カテゴリに過去24時間以内の主要ニュースがない場合は、古いニュースで埋めず「過去24時間以内に条件に合う主要ニュースはありません」と表示します。

実際の配信は7:07 JSTごろですが、見出し表記はニュース便として `7:00 JST` のままにしています。

## ファイル構成と役割

| ファイル | 役割 |
| --- | --- |
| `README.md` | この手順書です |
| `requirements.txt` | Python依存ライブラリ一覧です |
| `main.py` | 全体の入口です。設定読み込み、ニュース生成、HTML生成、LINE送信、送信済みマーカー作成を行います |
| `config.py` | GitHub Secrets / 環境変数を読み込みます。デフォルトモデルもここにあります |
| `news_briefing.py` | OpenAI Responses API + `web_search` toolでニュースを生成します。Structured OutputsのJSON Schemaもここにあります |
| `line_sender.py` | LINE Messaging APIのpush messageで、単独または複数ユーザーへ送信します |
| `approved_users.py` | 送信先を `APPROVED_USERS_ENDPOINT`、`LINE_TO_IDS`、`LINE_TO_ID` の優先順位で解決します |
| `site_generator.py` | 詳細版MarkdownをHTMLへ変換し、`docs` に保存します |
| `daily_run_guard.py` | GAS定期実行の判定と送信済みマーカーを扱います |
| `get_line_user_id.py` | `LINE_TO_ID` 確認用の一時的なローカルFlaskアプリです |
| `.github/workflows/daily_ai_news.yml` | GitHub Actions workflowです。現在は `workflow_dispatch` のみです |
| `gas/Code.gs` | GAS側のLINE Webhook、承認管理、承認済み一覧API、GitHub Actions起動処理です |
| `gas/README_GAS_SETUP.md` | GAS部分だけを設定するときの補助READMEです |
| `.env.example` | ローカル実行時の環境変数例です。本物の値は入れません |
| `.gitignore` | `.env` やキャッシュなど、GitHubに上げないファイルを指定します |
| `docs/` | GitHub Pagesで公開するHTML置き場です |

## GitHub SecretsとGASスクリプトプロパティの全体像

GitHub Actionsで使うものはGitHub Secretsに入れます。

| GitHub Secrets名 | 必須 | 用途 |
| --- | --- | --- |
| `OPENAI_API_KEY` | 必須 | OpenAI APIを呼ぶためのAPIキー |
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | Python側がLINEへpush messageを送るためのトークン |
| `LINE_TO_ID` | 推奨 | 管理者のLINE userId。単独送信、管理者エラー通知、承認制失敗時の退避先に使います |
| `OPENAI_MODEL` | 任意 | 実行モデル。設定されていればコードのデフォルトより優先されます |
| `SITE_BASE_URL` | 任意 | GitHub PagesのURL。推定URLが404になる場合に設定します |
| `LINE_TO_IDS` | 任意 | `APPROVED_USERS_ENDPOINT` を使わず複数人に直接送る場合のカンマ区切りID |
| `APPROVED_USERS_ENDPOINT` | 任意 | GAS WebアプリURL。承認済みユーザー一覧APIとして使います |
| `APPROVED_USERS_API_KEY` | 任意 | GASの承認済み一覧APIを守る共有キー |

GASで使うものはApps Scriptのスクリプトプロパティに入れます。

| GASスクリプトプロパティ名 | 必須 | 用途 |
| --- | --- | --- |
| `LINE_CHANNEL_ACCESS_TOKEN` | 必須 | GASがLINEへ返信・管理者通知・承認通知を送るためのトークン |
| `LINE_CHANNEL_SECRET` | 推奨 | LINE Webhook署名検証用のChannel secret |
| `ADMIN_LINE_USER_ID` | 必須 | 管理者のLINE userId。通常はGitHub Secretsの `LINE_TO_ID` と同じ値 |
| `SPREADSHEET_ID` | 必須 | ユーザー一覧を保存するGoogleスプレッドシートID |
| `APPROVED_USERS_API_KEY` | 必須 | GitHub Secretsの同名キーと同じ長い文字列 |
| `GITHUB_DISPATCH_TOKEN` | 必須 | GASからGitHub Actionsを起動するためのGitHub token |
| `GITHUB_REPOSITORY` | 必須 | `owner/repo` 形式。例: `aoiarakawa0821/ai-news-line-bot` |
| `GITHUB_WORKFLOW_FILE` | 任意 | 通常は `daily_ai_news.yml` |
| `GITHUB_WORKFLOW_REF` | 任意 | 通常は `main` |

秘密情報をREADME、コード、Issue、チャット、スクリーンショットに貼らないでください。

## OpenAIのモデル設定

コード上のデフォルトモデルは次です。

```text
gpt-5.5-2026-04-23
```

ただし、GitHub Secretsに `OPENAI_MODEL` が存在する場合は、Secretの値が最優先されます。つまり、`config.py` を変えても、GitHub Secretsの `OPENAI_MODEL` に別のモデルが入っていると、その別モデルが使われます。

実運用で確実に `gpt-5.5-2026-04-23` を使うには、GitHubの次の場所を確認します。

```text
GitHubにログイン
→ リポジトリ aoiarakawa0821/ai-news-line-bot
→ Settings
→ Secrets and variables
→ Actions
→ Repository secrets
→ OPENAI_MODEL
```

`OPENAI_MODEL` がある場合は、`Update` から次を上書きします。

```text
gpt-5.5-2026-04-23
```

GitHub Secretsは保存後に値を読み返せません。確認できるのはSecret名と更新日時だけです。値が不安な場合は、同じ値で上書きしてください。

## OpenAI Billing確認

OpenAI APIは、月間上限に余裕があっても、Credit balanceが0以下だと失敗します。残高不足でもGitHub Actionsログでは `429 Too Many Requests` のように見えることがあります。

確認場所です。

- Usage: `https://platform.openai.com/usage`
- Limits: `https://platform.openai.com/settings/organization/limits`
- Billing: `https://platform.openai.com/settings/organization/billing/overview`

Billingで見る項目です。

- `Credit balance` が0より大きいか
- `Auto recharge` がONか
- 支払い方法が有効か
- 月間spend limitに達していないか

残高がマイナス、または0の場合は、次のどちらかを行います。

1. `Add to credit balance` でクレジットを追加する。
2. `Setup auto recharge` で自動チャージを有効にする。

## セットアップ全体の順番

初めて作る場合は、次の順番で進めます。

1. GitHubアカウントを作る。
2. GitHubリポジトリを作る。
3. このファイル一式をリポジトリに入れる。
4. OpenAI APIキーを作る。
5. OpenAI Billingで残高とAuto rechargeを確認する。
6. LINE公式アカウントとMessaging APIチャネルを作る。
7. 自分のLINEアプリで公式アカウントを友だち追加する。
8. `LINE_CHANNEL_ACCESS_TOKEN` を取得する。
9. `LINE_TO_ID` を取得する。
10. GitHub Secretsを設定する。
11. GitHub Pagesを `main / docs` で設定する。
12. Googleスプレッドシートを作る。
13. Google Apps Scriptに `gas/Code.gs` を貼る。
14. GASスクリプトプロパティを設定する。
15. GAS Webアプリをデプロイする。
16. LINE Developers ConsoleにGAS WebアプリURLをWebhook URLとして設定する。
17. GASからGitHub Actionsを起動できるかテストする。
18. GASの7:07 / 7:37トリガーを作る。
19. GitHub Actionsを手動実行して確認する。
20. 友人の登録申請と管理者承認を確認する。

## GitHubアカウント作成手順

1. ブラウザで `https://github.com/` を開きます。
2. 右上の `Sign up` をクリックします。
3. メールアドレスを入力します。
4. パスワードを入力します。
5. ユーザー名を入力します。
6. 画面の案内に従ってメール認証を完了します。
7. ログインできたら準備完了です。

## 新しいリポジトリ作成手順

最初のクリック手順は必ず次です。

```text
GitHubにログイン → 右上の＋ → New repository
```

その後の手順です。

1. `Repository name` にリポジトリ名を入れます。例: `ai-news-line-bot`
2. GitHub Pagesを無料で使いやすくするため、まずは `Public` を選びます。
3. `Add a README file` は、すでにこのREADMEを使うならチェックなしでも構いません。
4. `Create repository` をクリックします。
5. リポジトリ画面が表示されれば成功です。

## ファイルをGitHubに置く方法

GitHub Desktopを使う場合は、ローカルの本番作業フォルダをリポジトリとして開き、変更をcommit/pushします。

ブラウザからアップロードする場合です。

1. GitHubのリポジトリ画面を開きます。
2. `Add file` をクリックします。
3. `Upload files` をクリックします。
4. ファイルをドラッグ&ドロップします。
5. `Commit changes` をクリックします。

`.github/workflows/daily_ai_news.yml` はフォルダ構造が重要です。GitHub上で次の形になっている必要があります。

```text
.github/
  workflows/
    daily_ai_news.yml
```

## GitHub DesktopでPullを求められる理由

GitHub Actionsが `docs` フォルダのHTMLや送信済みマーカーを自動でcommit/pushします。そのため、GitHub上にはローカルPCにない新しいcommitが増えます。

GitHub Desktopで `Pull origin` と表示されるのは、多くの場合これが理由です。

`Pull origin` は、GitHub上の最新commitをローカルPCに取り込む操作です。ローカルに未保存の変更がない場合は、通常そのままPullして問題ありません。

## OpenAI APIキーの取得手順

1. `https://platform.openai.com/` を開きます。
2. ログインします。
3. API keysの画面を開きます。
4. `Create new secret key` をクリックします。
5. 表示されたAPIキーをコピーします。
6. GitHub Secretsに `OPENAI_API_KEY` として登録します。

APIキーは一度閉じると再表示できないことがあります。コピーし忘れた場合は新しく作り直してください。

## LINE公式アカウントとMessaging APIチャネルの作成手順

LINE Notifyは使いません。LINE Notifyは終了済みです。このアプリはLINE Messaging APIを使います。

1. `https://developers.line.biz/console/` を開きます。
2. LINEアカウントでログインします。
3. 初回は開発者名などを登録します。
4. `Create a new provider` をクリックします。
5. Provider名を入力します。例: `daily-ai-news`
6. Provider作成後、`Create a Messaging API channel` をクリックします。
7. チャネル名、説明、カテゴリなどを入力します。
8. 作成を完了します。
9. `Messaging API` タブを開きます。
10. QRコードをスマホのLINEアプリで読み取り、公式アカウントを友だち追加します。

自分が友だち追加していないと、自分宛てにもLINE通知は届きません。

## LINE_CHANNEL_ACCESS_TOKENの取得手順

1. LINE Developers Consoleで対象のMessaging APIチャネルを開きます。
2. `Messaging API` タブを開きます。
3. 下の方にある `Channel access token` を探します。
4. `Issue` または `Reissue` をクリックします。
5. 表示された長い文字列をコピーします。
6. GitHub Secretsに `LINE_CHANNEL_ACCESS_TOKEN` として登録します。
7. GASスクリプトプロパティにも `LINE_CHANNEL_ACCESS_TOKEN` として登録します。

このトークンは絶対に公開しないでください。

## LINE_CHANNEL_SECRETの取得手順

`LINE_CHANNEL_SECRET` はLINE Webhook署名検証に使います。GitHub Actionsでは使いません。GASだけで使います。

1. LINE Developers Consoleで対象のMessaging APIチャネルを開きます。
2. `Basic settings` タブを開きます。
3. `Channel secret` を探します。
4. 値をコピーします。
5. Apps Scriptのスクリプトプロパティに `LINE_CHANNEL_SECRET` として登録します。

GAS環境ではWebhookヘッダーを取得できないことがあります。その場合、`gas/Code.gs` は警告をログに出し、署名検証をスキップして処理を続けます。

## LINE_TO_IDの取得方法

`LINE_TO_ID` は、LINE Messaging APIで「誰に送るか」を表すIDです。自分宛てに送る場合は `userId` を使います。

承認制配信を使う場合でも、`LINE_TO_ID` は管理者通知や障害時の退避送信先として残すことを強く推奨します。

GitHub ActionsだけではWebhookを受けられません。ローカルPCで一時的にFlaskアプリを起動し、ngrokなどで一時公開URLを作って確認します。

### ローカルで確認用サーバーを起動する

ターミナルでリポジトリのフォルダに移動し、次を実行します。

```bash
python -m pip install -r requirements.txt
python get_line_user_id.py
```

成功すると次のように表示されます。

```text
* Running on http://127.0.0.1:5000
```

### ngrokで一時公開URLを作る

1. `https://ngrok.com/` でアカウントを作ります。
2. ngrokをインストールします。
3. 別ターミナルで次を実行します。

```bash
ngrok http 5000
```

表示された `https://...ngrok-free.app` のようなURLをコピーします。

### LINE Developers ConsoleにWebhook URLを一時設定する

1. LINE Developers ConsoleでMessaging APIチャネルを開きます。
2. `Messaging API` タブを開きます。
3. `Webhook URL` に次を入れます。

```text
https://あなたのngrok URL/webhook
```

4. `Update` をクリックします。
5. `Use webhook` をONにします。
6. `Verify` をクリックし、成功することを確認します。

### LINEアプリからメッセージを送る

1. スマホのLINEアプリを開きます。
2. 作成したLINE公式アカウントのトーク画面を開きます。
3. `test` など任意のメッセージを送ります。
4. PCのターミナルを見るとWebhookのJSONが表示されます。
5. `コピーするID (userId): Uxxxxxxxx...` と表示された値をコピーします。
6. GitHub Secretsに `LINE_TO_ID` として登録します。
7. GASスクリプトプロパティに `ADMIN_LINE_USER_ID` として同じ値を登録します。

確認が終わったら、ローカルのFlaskアプリとngrokは止めて構いません。これは本番用ではなく、`LINE_TO_ID` 確認用の一時的な補助ツールです。

承認制運用をする場合は、最終的なWebhook URLをngrokではなくGAS WebアプリURLに戻します。

## GitHub Secretsの設定手順

1. GitHubのリポジトリ画面を開きます。
2. 上部メニューの `Settings` をクリックします。
3. 左メニューの `Secrets and variables` をクリックします。
4. `Actions` をクリックします。
5. `Repository secrets` を確認します。
6. `New repository secret` をクリックします。
7. `Name` にSecret名を入れます。
8. `Secret` に値を貼り付けます。
9. `Add secret` をクリックします。

最低限の単独送信で必要なSecretsです。

| Name | Secretに入れる値 |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI APIキー |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging APIのチャネルアクセストークン |
| `LINE_TO_ID` | 管理者または自分のLINE userId |

承認制配信で追加するSecretsです。

| Name | Secretに入れる値 |
| --- | --- |
| `APPROVED_USERS_ENDPOINT` | GAS WebアプリURL |
| `APPROVED_USERS_API_KEY` | GASスクリプトプロパティと同じ長いランダム文字列 |

必要に応じて使うSecretsです。

| Name | Secretに入れる値 |
| --- | --- |
| `OPENAI_MODEL` | 例: `gpt-5.5-2026-04-23` |
| `SITE_BASE_URL` | GitHub PagesのベースURL |
| `LINE_TO_IDS` | カンマ区切りの複数userId |

`APPROVED_USERS_ENDPOINT` が設定されている場合は、承認済みユーザー一覧配信が最優先です。`LINE_TO_IDS` や `LINE_TO_ID` より優先されます。

## GitHub Pagesの設定手順

このアプリはActionsによるPages Deployではなく、`Deploy from a branch` を使います。公開元は `main` ブランチの `/docs` フォルダです。

1. GitHubのリポジトリ画面を開きます。
2. `Settings` をクリックします。
3. 左メニューの `Pages` をクリックします。
4. `Build and deployment` を探します。
5. `Source` を `Deploy from a branch` にします。
6. `Branch` を `main` にします。
7. フォルダを `/docs` にします。
8. `Save` をクリックします。

しばらくするとPagesのURLが表示されます。

例です。

```text
https://aoiarakawa0821.github.io/ai-news-line-bot/
```

このアプリは `SITE_BASE_URL` が設定されていればそれを最優先します。未設定の場合は `GITHUB_REPOSITORY` から次の形を推定します。

```text
https://<owner>.github.io/<repo>/
```

詳細版リンクが404になる場合は、GitHub Pages画面に表示された正しいURLをGitHub Secretsの `SITE_BASE_URL` に登録してください。

## GitHub Actions workflowの実態

現在の `.github/workflows/daily_ai_news.yml` は、`workflow_dispatch` のみです。

```yaml
on:
  workflow_dispatch:
```

`schedule:` はありません。`cron:` もありません。

workflowには次が設定されています。

```yaml
permissions:
  contents: write
```

これは、GitHub Actionsが `docs` のHTMLと送信済みマーカーをcommit/pushするために必要です。

GitHub側の権限も確認してください。

1. GitHubのリポジトリ画面を開きます。
2. `Settings` をクリックします。
3. 左メニューの `Actions` → `General` を開きます。
4. `Workflow permissions` を探します。
5. `Read and write permissions` を選びます。
6. `Save` をクリックします。

## GitHub Actionsを手動実行する方法

初回確認や障害後の復旧確認では手動実行します。

1. GitHubのリポジトリ画面を開きます。
2. `Actions` タブをクリックします。
3. 左側の `daily_ai_news` をクリックします。
4. 右側の `Run workflow` をクリックします。
5. `Branch` は `main` のままにします。
6. `scheduled_dispatch` は通常 `false` のままにします。
7. 緑色の `Run workflow` をクリックします。
8. 実行中の行をクリックします。
9. `daily-ai-news` ジョブを開きます。
10. `Generate briefing and send LINE message` のログを確認します。

通常の手動確認では `scheduled_dispatch` を `true` にしないでください。`true` にすると定期実行扱いになり、送信済みマーカーの判定対象になります。

定期実行と同じ条件をテストしたい場合だけ、`scheduled_dispatch=true` を使います。

## 初回確認で見るログ

初回確認は「LINEが届いたか」だけで判断しないでください。次を順番に確認します。

1. `AIニュース生成処理を開始します。` がある。
2. `利用モデル: ...` が意図したモデルになっている。
3. `OpenAI Responses APIでニュース生成を開始します。attempt=1` がある。
4. `OpenAIニュース生成に成功しました。sources=...` がある。
5. `GitHub Pages用HTMLを生成しました。` がある。
6. `APPROVED_USERS_ENDPOINTから承認済み送信先を読み込みました。count=...` または `LINE_TO_IDから単独送信先を読み込みました。` がある。
7. `LINE送信結果: success=... failure=...` がある。
8. `Commit generated docs if changed` でcommit/pushが成功している。
9. `docs/YYYY-MM-DD.html` と `docs/latest.html` がGitHubに増えている。
10. GitHub PagesのURLで詳細版が開ける。

## 毎朝7:07 JSTに動く仕組み

GASの `setupDailyAiNewsWorkflowTriggers()` は次の2つの時間主導トリガーを作ります。

- 7:07 JSTごろ
- 7:37 JSTごろ

GASの時間主導トリガーは秒単位ぴったりではありません。数分程度前後する可能性があります。ただし、GitHub Actionsのcronが何時間も遅れる問題を避けるため、現在はGASを正式なスケジューラにしています。

GASがGitHub Actionsを起動するとき、次のinputを渡します。

```json
{
  "scheduled_dispatch": "true"
}
```

GitHub Actions側ではこれを `SCHEDULED_DISPATCH` 環境変数に入れます。Python側の `daily_run_guard.py` は、`SCHEDULED_DISPATCH=true` の場合に定期実行扱いにします。

## 二重送信防止の仕組み

定期実行として成功した場合、Pythonは次のファイルを作ります。

```text
docs/.daily_ai_news_sent_YYYY-MM-DD
```

このファイルを送信済みマーカーと呼びます。

7:07 JSTごろの実行で次の条件を満たすと、マーカーを作ります。

- OpenAIニュース生成が成功した。
- 詳細版HTML生成が成功した。
- 送信先取得が正常だった。
- LINE送信が1件以上成功した。
- LINE送信失敗が0件だった。
- 管理者だけへの退避送信ではなかった。

7:37 JSTごろのバックアップ実行では、同じ日付のマーカーがあれば、ニュース生成もLINE送信もせず正常終了します。

次の場合はマーカーを作りません。

- OpenAI API失敗、JSON解析失敗、レート制限、残高不足などでニュース生成できなかった。
- `APPROVED_USERS_ENDPOINT` から承認済み一覧を取得できず、管理者だけに退避送信した。
- 送信先が0件だった。
- LINE送信が一部でも失敗した。
- 手動実行で `scheduled_dispatch=false` だった。

そのため、7:07で失敗した場合は7:37で再試行します。部分成功の場合は、すでに届いた人にもバックアップで再送される可能性があります。この設計は、二重送信の完全回避より、その日の配信成功率を優先しています。

注意点です。7:07でLINE送信が完全成功した後、最後の `docs` commit/pushだけ失敗した場合、GitHub上にマーカーが残らず、7:37で重複送信する可能性があります。これは現在の設計上の残リスクです。

## Googleスプレッドシートを作る

承認制配信を使う場合、ユーザー管理用のGoogleスプレッドシートを作ります。

1. `https://sheets.google.com/` を開きます。
2. `空白` をクリックします。
3. ファイル名を `AIニュース配信ユーザー管理` などに変更します。
4. URLを見ます。

URLは次の形です。

```text
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

`/d/` と `/edit` の間の長い文字列が `SPREADSHEET_ID` です。

シート名や列はGASが自動で整えます。手で列を作る必要はありません。実際に使うシート名は `users` です。

列は次です。

| 列 | 意味 |
| --- | --- |
| `userId` | LINE userId |
| `displayName` | LINEプロフィール名。取得できない場合は空欄 |
| `status` | `pending` / `approved` / `rejected` |
| `createdAt` | 初回登録日時 |
| `updatedAt` | 更新日時 |
| `approvedAt` | 承認日時 |
| `rejectedAt` | 拒否日時 |
| `note` | 処理メモ |

スプレッドシートは全体公開しないでください。管理者だけが見られる状態にします。

## Google Apps Scriptプロジェクトを作る

1. 作成したスプレッドシートを開きます。
2. 上部メニューの `拡張機能` をクリックします。
3. `Apps Script` をクリックします。
4. Apps Scriptエディタが開きます。
5. 左上のプロジェクト名を `AIニュースLINE承認Webhook` などに変更します。
6. 最初からある `Code.gs` の中身をすべて削除します。
7. このリポジトリの `gas/Code.gs` を開きます。
8. 中身をすべてコピーします。
9. Apps Scriptの `Code.gs` に貼り付けます。
10. 保存アイコンをクリックします。

GASのコードをGitHubで変更しても、Apps Script側には自動反映されません。`gas/Code.gs` を更新したときは、Apps Script側に貼り直し、必要に応じてWebアプリを新バージョンで再デプロイしてください。

## GASスクリプトプロパティを設定する

1. Apps Script画面を開きます。
2. 左メニューの歯車アイコン `プロジェクトの設定` をクリックします。
3. `スクリプト プロパティ` を探します。
4. `スクリプト プロパティを追加` をクリックします。
5. 次のプロパティを追加します。

| プロパティ名 | 入れる値 |
| --- | --- |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers ConsoleのMessaging APIチャネルアクセストークン |
| `LINE_CHANNEL_SECRET` | LINE Developers ConsoleのBasic settingsにあるChannel secret |
| `ADMIN_LINE_USER_ID` | 管理者のLINE userId。通常は `LINE_TO_ID` と同じ |
| `SPREADSHEET_ID` | GoogleスプレッドシートURLの `/d/` と `/edit` の間 |
| `APPROVED_USERS_API_KEY` | 推測されにくい長いランダム文字列。GitHub Secretsにも同じ値を入れる |
| `GITHUB_DISPATCH_TOKEN` | GASからGitHub Actionsを起動するGitHub token |
| `GITHUB_REPOSITORY` | `owner/repo`。例: `aoiarakawa0821/ai-news-line-bot` |
| `GITHUB_WORKFLOW_FILE` | 通常は `daily_ai_news.yml` |
| `GITHUB_WORKFLOW_REF` | 通常は `main` |

`APPROVED_USERS_API_KEY` の例です。

```text
daily-ai-news-approved-users-2026-long-random-text-please-change
```

これは例です。実運用では自分だけの長くランダムな文字列にしてください。

## GITHUB_DISPATCH_TOKENの作成

GASがGitHub Actionsを起動するには、GitHub APIを呼ぶtokenが必要です。

Fine-grained personal access tokenを使う場合です。

1. GitHubにログインします。
2. 右上の自分のアイコンをクリックします。
3. `Settings` をクリックします。
4. 左メニュー下部の `Developer settings` をクリックします。
5. `Personal access tokens` をクリックします。
6. `Fine-grained tokens` をクリックします。
7. `Generate new token` をクリックします。
8. Token nameに `daily-ai-news-gas-dispatch` などと入れます。
9. Repository accessで対象リポジトリだけを選びます。
10. Permissionsで `Actions: Read and write` を付けます。
11. tokenを作成します。
12. 表示されたtokenをコピーします。
13. Apps Scriptのスクリプトプロパティ `GITHUB_DISPATCH_TOKEN` に貼ります。

表示されたtokenは一度しか見られません。READMEやコードには貼らないでください。

## GASをWebアプリとしてデプロイする

1. Apps Script画面右上の `デプロイ` をクリックします。
2. `新しいデプロイ` をクリックします。
3. 種類の選択で歯車アイコンをクリックします。
4. `ウェブアプリ` を選びます。
5. `説明` に `LINE Webhook` などと入力します。
6. `次のユーザーとして実行` は `自分` を選びます。
7. `アクセスできるユーザー` は `全員` を選びます。
8. `デプロイ` をクリックします。
9. 初回はGoogleの承認画面が出ます。
10. 自分のGoogleアカウントを選びます。
11. 権限確認画面を進めます。
12. 表示された `ウェブアプリ URL` をコピーします。

このURLは次の2か所で使います。

- LINE Developers ConsoleのWebhook URL
- GitHub Secretsの `APPROVED_USERS_ENDPOINT`

GASを修正した後は、必要に応じて次を行います。

```text
デプロイ → デプロイを管理 → 鉛筆アイコン → バージョンで新バージョンを選択 → デプロイ
```

## LINE Developers ConsoleにGAS Webhook URLを設定する

1. LINE Developers Consoleを開きます。
2. 対象のProviderを開きます。
3. Messaging APIチャネルを開きます。
4. `Messaging API` タブを開きます。
5. `Webhook URL` にGASの `ウェブアプリ URL` を貼ります。
6. `Update` をクリックします。
7. `Use webhook` をONにします。
8. `Verify` をクリックします。

Webhook検証で `302 Found` が出る場合は、Apps Script側の `doPost(e)` が `HtmlService.createHtmlOutput("OK")` を返しているか確認してください。現在の `gas/Code.gs` は `okResponse_()` でHtmlServiceのOKを返す設計です。

Webhook検証で署名関連の警告が出る場合、GASが `x-line-signature` ヘッダーを取得できていない可能性があります。現在のコードは、ヘッダーが取れない場合は警告を出して処理を続けます。

## GASからGitHub Actionsを起動する設定

Apps Scriptで次を行います。

1. `gas/Code.gs` の最新版が貼られていることを確認します。
2. スクリプトプロパティがすべて入っていることを確認します。
3. 上部の関数選択で `testDispatchDailyAiNewsWorkflow` を選びます。
4. `実行` をクリックします。
5. 初回はGoogleの権限承認が出るので許可します。
6. GitHubの `Actions` タブで `daily_ai_news` が起動したか確認します。
7. 問題なければ、関数選択で `setupDailyAiNewsWorkflowTriggers` を選びます。
8. `実行` をクリックします。
9. Apps Script左メニューの時計アイコン `トリガー` を開きます。
10. `dispatchDailyAiNewsWorkflow` の時間ベーストリガーが2つあることを確認します。

この2つが7:07 JSTごろ、7:37 JSTごろの起動元です。

## 承認制配信の流れ

友人が登録される流れです。

1. 友人がLINE公式アカウントを友だち追加します。
2. 友人が公式LINEに `登録` など任意のメッセージを送ります。
3. LINEがGAS Webhookへイベントを送ります。
4. GASが `userId` を取得します。
5. GASがLINEプロフィールAPIで `displayName` を取得できれば取得します。
6. スプレッドシートに未登録なら `pending` として保存します。
7. 管理者の `ADMIN_LINE_USER_ID` に登録申請通知を送ります。
8. 管理者が `approve` を送ると `approved` になります。
9. 承認されたユーザーには「承認されました。明日からAIニュースが届きます」と届きます。
10. 翌朝、GitHub Actionsが `approved` ユーザー全員へニュースを送ります。

友だち追加だけではニュースは届きません。管理者承認が必要です。

## 管理者コマンド

管理者はLINE公式アカウントに次のメッセージを送れます。

```text
approve
approve Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
reject
reject Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
list pending
list approved
help
```

意味です。

| コマンド | 意味 |
| --- | --- |
| `approve` | 一番古い `pending` ユーザーを承認します |
| `approve userId` | 指定したuserIdを承認します |
| `reject` | 一番古い `pending` ユーザーを拒否します |
| `reject userId` | 指定したuserIdを拒否します |
| `list pending` | 承認待ち一覧を表示します |
| `list approved` | 承認済み一覧を表示します |
| `help` | コマンド一覧を表示します |

管理者以外がこれらのコマンドを送っても実行されません。管理者判定は `ADMIN_LINE_USER_ID` と送信者のLINE userIdの完全一致です。

コマンド判定は厳密です。`please approve ...` や `approve userId now` のような文は管理者コマンドとして扱いません。

## 非管理者が自己承認できないことの確認

Apps Scriptには `runAdminSecurityTests` という確認用関数があります。

1. Apps Script画面を開きます。
2. 上部の関数選択で `runAdminSecurityTests` を選びます。
3. `実行` をクリックします。
4. エラーが出なければ、非管理者が承認・拒否・一覧取得に到達しないことをコード上で確認できています。

実際のLINEでも確認できます。

1. 管理者ではないLINEアカウントで公式アカウントにメッセージを送ります。
2. スプレッドシートに `pending` として登録されたことを確認します。
3. その非管理者アカウントから `approve 自分のuserId` を送ります。
4. 返信が「このコマンドは管理者だけが実行できます。」になることを確認します。
5. スプレッドシートの `status` が `pending` のまま変わっていないことを確認します。
6. `approve 他人のuserId`、`reject 他人のuserId`、`list pending`、`list approved` でも状態変更されないことを確認します。

## 送信先解決の優先順位

Python側は次の優先順位で送信先を決めます。

1. `APPROVED_USERS_ENDPOINT` が設定されていれば、GASから `approved` ユーザー一覧を取得します。
2. `APPROVED_USERS_ENDPOINT` が未設定で `LINE_TO_IDS` があれば、カンマ区切りの複数userIdへ送ります。
3. `LINE_TO_IDS` が未設定で `LINE_TO_ID` があれば、従来通り1人へ送ります。

`APPROVED_USERS_ENDPOINT` の取得に失敗した場合、安全のため承認済みユーザー全員には送りません。`LINE_TO_ID` が設定されていれば、管理者だけに警告付きで送信します。その場合、送信済みマーカーは作らないため、バックアップ実行で再試行します。

approvedユーザーが0人の場合、ニュース生成とHTML生成は行いますが、LINE送信はスキップします。

## `.env.example` とローカル実行

GitHub Actionsでは `.env` を使いません。GitHub Secretsを使います。

ローカルで試す場合は、`.env.example` を参考に自分の `.env` を作れます。ただし、このリポジトリには `.env` をアップロードしません。`.gitignore` に `.env` が入っています。

`.env.example` の `OPENAI_MODEL` は現在のデフォルトに合わせて `gpt-5.5-2026-04-23` です。

## よくあるエラーと対処法

### OpenAI APIが `429 Too Many Requests` になる

原因候補です。

- OpenAI BillingのCredit balanceが0以下
- Auto rechargeがOFFで残高不足
- 月間spend limitに達している
- モデル別のTPM/RPM上限に当たっている
- `OPENAI_MODEL` に使えないモデル名を指定している

確認場所です。

1. OpenAI PlatformのUsageを見る。
2. OpenAI PlatformのLimitsを見る。
3. OpenAI PlatformのBillingを見る。
4. GitHub Secretsの `OPENAI_MODEL` を確認し、必要なら上書きする。

### OpenAIニュース生成に失敗した

`main.py` は通常ニュース生成に失敗した場合、承認済みユーザー全員への配信を止めます。`LINE_TO_ID` があれば管理者だけにエラー通知します。GitHub Actionsは失敗扱いになります。

この場合、7:37 JSTのバックアップ実行、または次回実行で再試行されます。

### JSONパース失敗

OpenAIから返るJSONが壊れた場合、`news_briefing.py` は再試行します。Structured OutputsのJSON Schemaを使っていますが、最終的に失敗した場合はフォールバック扱いになり、一般配信は止まります。

### LINEに通知が来ない

確認します。

1. 自分または友人がLINE公式アカウントを友だち追加しているか。
2. `LINE_CHANNEL_ACCESS_TOKEN` が正しいMessaging APIチャネルのものか。
3. `LINE_TO_ID` が正しいか。
4. 承認制ならスプレッドシートのstatusが `approved` か。
5. `APPROVED_USERS_ENDPOINT` と `APPROVED_USERS_API_KEY` が正しいか。
6. Actionsログに `LINE送信結果: success=... failure=...` があるか。
7. LINE Developers Consoleでチャネルを削除・再発行していないか。

### 詳細版リンクが404になる

確認します。

1. GitHubのリポジトリで `docs/YYYY-MM-DD.html` があるか。
2. `docs/latest.html` があるか。
3. `Settings` → `Pages` が `Deploy from a branch` になっているか。
4. Branchが `main`、フォルダが `/docs` になっているか。
5. Pages画面に表示されたURLとLINEに載っているURLが一致しているか。
6. 一致していない場合、GitHub Secretsに `SITE_BASE_URL` を設定する。

### Actionsのpushが失敗する

確認します。

1. GitHubリポジトリの `Settings` を開く。
2. `Actions` → `General` を開く。
3. `Workflow permissions` を探す。
4. `Read and write permissions` を選ぶ。
5. `Save` をクリックする。

workflowファイル側には `permissions: contents: write` が設定済みです。

### GASからGitHub Actionsが起動しない

確認します。

1. Apps Scriptの `実行数` を開く。
2. `dispatchDailyAiNewsWorkflow` の実行ログを見る。
3. `GITHUB_DISPATCH_TOKEN` が入っているか。
4. tokenに `Actions: Read and write` があるか。
5. `GITHUB_REPOSITORY` が `owner/repo` 形式か。
6. `GITHUB_WORKFLOW_FILE` が `daily_ai_news.yml` か。
7. `GITHUB_WORKFLOW_REF` が `main` か。
8. GitHub Actions workflowが無効化されていないか。

### LINE Webhook検証で302になる

GASの `doPost(e)` は最終的にHTTP 200を返す必要があります。現在の `gas/Code.gs` は `okResponse_()` で `HtmlService.createHtmlOutput("OK")` を返します。

Apps Scriptに古いコードが残っている場合は、`gas/Code.gs` を貼り直し、Webアプリを新バージョンで再デプロイしてください。

### GitHub DesktopがPullを求める

GitHub Actionsが `docs` を自動commit/pushするため、GitHub上の方が進んでいることがあります。ローカルに未コミット変更がなければ、通常は `Pull origin` して問題ありません。

## セキュリティ上の注意

絶対に公開してはいけないものです。

- `OPENAI_API_KEY`
- `LINE_CHANNEL_ACCESS_TOKEN`
- `LINE_CHANNEL_SECRET`
- `GITHUB_DISPATCH_TOKEN`
- `APPROVED_USERS_API_KEY`
- 実運用の `LINE_TO_ID`、`LINE_TO_IDS`、友人のuserId
- スプレッドシートの共有リンクを全体公開にしたもの

守ることです。

- APIキーやトークンをコードに直書きしない。
- READMEに本物のキーを書かない。
- GitHub IssueやPull Requestに秘密情報を貼らない。
- スプレッドシートは管理者だけが見られる状態にする。
- `APPROVED_USERS_API_KEY` は長くランダムにする。
- 管理者以外にApps Script編集権限を渡さない。
- GitHub tokenは対象リポジトリだけに限定する。

## カスタマイズ方法

### モデルを変える

GitHub Secretsの `OPENAI_MODEL` を変更します。

例です。

```text
gpt-5.5-2026-04-23
```

Secretを削除すると、`config.py` の `DEFAULT_OPENAI_MODEL` が使われます。

### ニュース条件を変える

`news_briefing.py` の `_build_prompt()` を編集します。

ここに、収集対象、除外条件、LINE短縮版テンプレート、詳細版テンプレート、重要度・信頼度の扱いが書かれています。

### 詳細版URLを固定する

GitHub Secretsに `SITE_BASE_URL` を設定します。

例です。

```text
https://aoiarakawa0821.github.io/ai-news-line-bot/
```

### 複数人へ直接送る

承認制を使わずに複数人へ直接送りたい場合は、GitHub Secretsの `LINE_TO_IDS` にカンマ区切りで入れます。

```text
Uxxxxx,Uyyyyy,Uzzzzz
```

ただし、`APPROVED_USERS_ENDPOINT` が設定されている場合は、承認済みユーザー一覧APIが優先されます。

### LINEメッセージ分割長を変える

`line_sender.py` の `MAX_LINE_TEXT_LENGTH` を変更します。現在は安全側で `4900` 文字です。

## 運用停止方法

### 自動配信だけ止める

GASトリガーを止めます。

1. Apps Scriptを開きます。
2. 左メニューの時計アイコン `トリガー` をクリックします。
3. `dispatchDailyAiNewsWorkflow` の時間ベーストリガーを削除します。

または、Apps Scriptで `deleteDailyAiNewsWorkflowTriggers` を実行します。

### GitHub Actionsも止める

1. GitHubのリポジトリ画面を開きます。
2. `Actions` タブをクリックします。
3. 左側の `daily_ai_news` をクリックします。
4. 右上の `...` をクリックします。
5. `Disable workflow` をクリックします。

### LINE Webhookを止める

1. LINE Developers Consoleを開きます。
2. Messaging APIチャネルを開きます。
3. `Messaging API` タブを開きます。
4. `Use webhook` をOFFにします。

### GAS Webアプリを止める

1. Apps Script画面右上の `デプロイ` をクリックします。
2. `デプロイを管理` をクリックします。
3. 対象デプロイを選びます。
4. 必要に応じて削除、または新しいアクセス制限に変更します。

## 日常運用チェックリスト

毎日見る必要はありませんが、問題が起きたらこの順番で確認します。

1. LINEに通知が届いたか。
2. GitHub Actionsの `daily_ai_news` が起動したか。
3. 起動時刻が7:07または7:37 JSTごろか。
4. OpenAIニュース生成が成功したか。
5. LINE送信成功件数が期待通りか。
6. `docs/YYYY-MM-DD.html` ができたか。
7. GitHub Pagesで詳細版が開けるか。
8. 送信済みマーカーが作られているか。
9. OpenAI Billingの残高があるか。
10. GASの実行ログにエラーがないか。

## 現在の本番運用で特に重要な確認点

このリポジトリの現在の設計では、次が整っていれば翌朝の配信は動きます。

1. GASに `dispatchDailyAiNewsWorkflow` のトリガーが2つある。
2. GASスクリプトプロパティの `GITHUB_DISPATCH_TOKEN` が有効。
3. GitHub Actions workflow `daily_ai_news` が有効。
4. GitHub ActionsのRepository secretsが正しい。
5. OpenAI BillingのCredit balanceが0より大きい。
6. `OPENAI_MODEL` が使えるモデル名になっている。
7. LINE公式アカウントを受信者が友だち追加している。
8. 承認制ならスプレッドシートで対象者が `approved` になっている。
9. GitHub Pagesが `Deploy from a branch`、`main / docs` になっている。

## 変更をGitHubへ反映する手順

ローカルでファイルを変更しただけでは、GitHub Actionsには反映されません。必ずcommit/pushします。

ターミナルで確認する場合です。

```bash
git status --short --branch
git add README.md
git commit -m "Update README"
git push
```

GitHub Desktopを使う場合です。

1. GitHub Desktopを開きます。
2. Current Repositoryが `ai-news-line-bot` になっていることを確認します。
3. Changesに変更ファイルが出ていることを確認します。
4. Summaryに変更内容を書きます。例: `Update README`
5. `Commit to main` をクリックします。
6. `Push origin` をクリックします。

GitHub Desktopに `Pull origin` が出ている場合は、先にPullが必要なことがあります。ローカルに未コミット変更がある場合は、競合を避けるため、状態を確認してから進めてください。
