[README_GAS_SETUP.md](https://github.com/user-attachments/files/29171021/README_GAS_SETUP.md)
# Google Apps Scriptで承認制登録を作る手順

この手順は、LINE公式アカウントを友だち追加した人をすぐ配信対象にせず、管理者が承認した人だけに毎朝AIニュースを届けるための設定です。

GitHub Actionsは毎朝ニュースを作って送る担当です。Google Apps ScriptはLINE Webhookを受け取り、友だち追加、登録申請、承認、拒否、承認済み一覧APIを担当します。

## 1. Googleスプレッドシートを作る

1. ブラウザで [Google Sheets](https://sheets.google.com/) を開きます。
2. `空白` をクリックします。
3. 左上のファイル名を `AIニュース配信ユーザー管理` などに変更します。
4. URLを見ます。

URLが次の形になっています。

```text
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

`/d/` と `/edit` の間の長い文字列が `SPREADSHEET_ID` です。あとで使うので控えてください。

シート名は自動で `users` が作られます。手で列を作らなくても大丈夫です。

## 2. Google Apps Scriptプロジェクトを作る

1. 作成したスプレッドシートを開きます。
2. 上部メニューの `拡張機能` → `Apps Script` をクリックします。
3. 新しいタブでApps Scriptエディタが開きます。
4. 左上のプロジェクト名を `AIニュースLINE承認管理` などに変更します。
5. 最初からある `Code.gs` の中身をすべて削除します。
6. このリポジトリの `gas/Code.gs` の中身をすべてコピーして貼り付けます。
7. 上部の保存アイコンをクリックします。

## 3. スクリプトプロパティを設定する

1. Apps Script画面の左メニューで歯車アイコンの `プロジェクトの設定` をクリックします。
2. `スクリプト プロパティ` を探します。
3. `スクリプト プロパティを追加` をクリックします。
4. 次の名前と値を登録します。

| プロパティ名 | 値 |
| --- | --- |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers ConsoleのMessaging APIチャネルアクセストークン |
| `LINE_CHANNEL_SECRET` | LINE Developers ConsoleのBasic settingsにあるChannel secret |
| `ADMIN_LINE_USER_ID` | 管理者のLINE userId。既存の`LINE_TO_ID`と同じ値でOK |
| `SPREADSHEET_ID` | GoogleスプレッドシートURLの`/d/`と`/edit`の間 |
| `APPROVED_USERS_API_KEY` | 推測されにくい長い文字列。GitHub Secretsにも同じ値を入れます |
| `GITHUB_DISPATCH_TOKEN` | GASからGitHub Actionsを起動するためのGitHub token |
| `GITHUB_REPOSITORY` | `aoiarakawa0821/ai-news-line-bot` のような `owner/repo` |
| `GITHUB_WORKFLOW_FILE` | 任意。通常は `daily_ai_news.yml` |
| `GITHUB_WORKFLOW_REF` | 任意。通常は `main` |

`APPROVED_USERS_API_KEY` の例:

```text
daily-ai-news-approved-users-2026-long-random-text-123456
```

実運用ではもっと長く、他人に推測されにくい文字列にしてください。

`GITHUB_DISPATCH_TOKEN` はGitHubのFine-grained personal access tokenを使うのがおすすめです。GitHub右上のアイコン → `Settings` → `Developer settings` → `Personal access tokens` → `Fine-grained tokens` → `Generate new token` を開き、対象リポジトリをこのリポジトリだけに限定し、`Actions: Read and write` を付けて作成します。作成後に表示されるtokenは一度しか見られないので、GASのスクリプトプロパティへ貼り付けます。READMEやコードには貼らないでください。

## 4. Webアプリとしてデプロイする

1. Apps Script画面右上の `デプロイ` をクリックします。
2. `新しいデプロイ` をクリックします。
3. 種類の選択で歯車アイコンをクリックし、`ウェブアプリ` を選びます。
4. `説明` に `LINE Webhook` などと入力します。
5. `次のユーザーとして実行` は `自分` を選びます。
6. `アクセスできるユーザー` は `全員` を選びます。
7. `デプロイ` をクリックします。
8. 初回はGoogleの承認画面が出るので、案内に従って許可します。
9. 表示された `ウェブアプリ URL` をコピーします。

このURLがLINE Developers Consoleに設定するWebhook URLです。また、GitHub Secretsの `APPROVED_USERS_ENDPOINT` にも使います。

## 5. LINE Developers ConsoleにWebhook URLを設定する

1. [LINE Developers Console](https://developers.line.biz/console/) を開きます。
2. 対象のProviderを開きます。
3. Messaging APIチャネルを開きます。
4. `Messaging API` タブを開きます。
5. `Webhook URL` にGASの `ウェブアプリ URL` を貼り付けます。
6. `Update` をクリックします。
7. `Use webhook` をONにします。
8. `Verify` をクリックして成功するか確認します。

GAS Webアプリは環境によってLINE署名ヘッダーを取得できないことがあります。`gas/Code.gs` は `LINE_CHANNEL_SECRET` が設定され、かつ署名ヘッダーを取得できる場合は検証します。ヘッダーを取得できない場合はログに警告を出して処理を続けます。セキュリティをさらに強くしたい場合は、Cloudflare Workersなどヘッダーを確実に扱える環境を検討してください。

## 6. GitHub Secretsに追加する

GitHub側では、毎朝のPythonアプリがGASから承認済みユーザー一覧を取得します。

1. GitHubのリポジトリ画面を開きます。
2. `Settings` → `Secrets and variables` → `Actions` を開きます。
3. `New repository secret` をクリックします。
4. 次を追加します。

| Secret名 | 値 |
| --- | --- |
| `APPROVED_USERS_ENDPOINT` | GASのウェブアプリURL |
| `APPROVED_USERS_API_KEY` | GASのスクリプトプロパティと同じ文字列 |

既存の `LINE_TO_ID` は管理者へのエラー通知や後方互換のため残しておくのがおすすめです。

## 7. GASからGitHub Actionsを起動する

GitHub Actionsのscheduleは、GitHub側の混雑で朝の実行が夜に遅れて作成されることがあります。このアプリでは夜の遅延配信を防ぐため、GitHub Actionsのscheduleは使わず、GASの時間主導トリガーでGitHub Actionsを起動します。

1. Apps Script画面を開きます。
2. `gas/Code.gs` の最新版を貼り付けて保存します。
3. 必要なら `デプロイ` → `デプロイを管理` → 鉛筆アイコン → `バージョン` で `新バージョン` を選び、再デプロイします。
4. 上部の関数選択で `testDispatchDailyAiNewsWorkflow` を選びます。
5. `実行` をクリックします。
6. GitHubの `Actions` タブで `daily_ai_news` が起動することを確認します。
7. 問題なければ、関数選択で `setupDailyAiNewsWorkflowTriggers` を選びます。
8. `実行` をクリックします。
9. 左メニューの時計アイコン `トリガー` を開き、`dispatchDailyAiNewsWorkflow` が2つ作られていることを確認します。

この2つのトリガーは、毎日7:07 JSTごろと7:37 JSTごろにGitHub Actionsを起動します。GASの時間主導トリガーも完全に秒単位ぴったりではありませんが、GitHub Actionsのscheduleより夜の大幅遅延を避けやすくなります。

GASから起動したworkflowは `scheduled_dispatch=true` として実行されます。そのため、通常のschedule実行と同じく送信済みマーカーで二重送信を防ぎます。GitHub画面から普通に手動実行する場合は、`scheduled_dispatch` をONにしないでください。

GASトリガーを止めたい場合は、Apps Script左メニューの `トリガー` を開き、`dispatchDailyAiNewsWorkflow` のトリガーを削除します。または関数 `deleteDailyAiNewsWorkflowTriggers` を実行します。

## 8. 管理者コマンド

管理者はLINE公式アカウントに次のメッセージを送れます。

```text
approve
reject
list pending
list approved
help
```

`approve` は一番古いpendingユーザーを承認します。複数pendingがいる場合に特定ユーザーを承認したいときは、通知や一覧に表示されたuserIdを付けます。

```text
approve Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
reject Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

管理者以外がこれらのコマンドを送っても実行されません。

## 9. 友人に登録してもらう流れ

1. 友人にLINE公式アカウントのQRコードや友だち追加リンクを送ります。
2. 友人がLINE公式アカウントを友だち追加します。
3. 友人が `登録` など任意のメッセージを送ります。
4. GASがuserIdとdisplayNameを取得し、スプレッドシートに `pending` として保存します。
5. 管理者に登録申請通知が届きます。
6. 管理者が `approve` を送ると、そのユーザーが `approved` になります。
7. 承認されたユーザーには「承認されました。明日からAIニュースが届きます」と届きます。
8. 翌朝のGitHub Actionsが `approved` ユーザー全員へニュースを送ります。

友だち追加だけではニュースは届きません。管理者が承認した人だけに届きます。

## 10. 動作確認

### 非管理者が自己承認できないことを確認する

コード更新後、Apps Scriptエディタで `runAdminSecurityTests` を選んで実行します。エラーが出なければ、次の条件をコード上で確認できています。

- 非管理者が `approve 自分のuserId` を送っても承認処理に到達しません。
- 非管理者が `approve 他人のuserId` や `reject userId` を送っても承認・拒否処理に到達しません。
- 非管理者が `list pending` / `list approved` を送っても一覧取得処理に到達しません。
- `ADMIN_LINE_USER_ID` が未設定の場合、管理者コマンドはすべて拒否されます。
- `please approve ...` や `approve userId now` のような曖昧な文は管理者コマンドとして扱われません。

実際のLINEでも次の手順で確認できます。

1. 管理者ではないLINEアカウントで公式アカウントにメッセージを送り、スプレッドシートに `pending` として登録されることを確認します。
2. その非管理者アカウントから `approve 自分のuserId` を送ります。
3. 返信が「このコマンドは管理者だけが実行できます。」になることを確認します。
4. スプレッドシート上の自分の `status` が `pending` のまま変わっていないことを確認します。
5. 同じ非管理者アカウントから `approve 他人のuserId`、`reject 他人のuserId`、`list pending`、`list approved` を送っても、承認・拒否・一覧取得が実行されないことを確認します。

### GAS Webhookログを見る

1. Apps Script画面を開きます。
2. 左メニューの `実行数` をクリックします。
3. 最新の実行をクリックします。
4. エラーや `console.error` の内容を確認します。

### GitHub Actionsログを見る

1. GitHubのリポジトリ画面を開きます。
2. `Actions` → `daily_ai_news` を開きます。
3. 最新の実行をクリックします。
4. `APPROVED_USERS_ENDPOINTから承認済み送信先を読み込みました。count=...` が出ているか確認します。

## 11. うまく動かない場合

- LINE Developers Consoleで `Use webhook` がONか確認します。
- Webhook URLがGASのウェブアプリURLになっているか確認します。
- GASを修正した後は、必要に応じて `デプロイ` → `デプロイを管理` → 編集 → 新しいバージョンで再デプロイします。
- `SPREADSHEET_ID` が正しいか確認します。
- `ADMIN_LINE_USER_ID` が管理者自身のuserIdか確認します。
- `APPROVED_USERS_API_KEY` がGASとGitHub Secretsで同じか確認します。
- GASからGitHub Actionsが起動しない場合は、`GITHUB_DISPATCH_TOKEN` に `Actions: Read and write` が付いているか、`GITHUB_REPOSITORY` が `owner/repo` 形式か確認します。
- スプレッドシートを全体公開しないでください。
- LINEアクセストークン、Channel secret、GitHub token、APIキーをREADMEやコードに書かないでください。
