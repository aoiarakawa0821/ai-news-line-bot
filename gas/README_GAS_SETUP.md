# Google Apps Scriptで承認制登録と定期起動を作る手順

このREADMEは、`gas/Code.gs` をGoogle Apps Scriptへ反映し、LINE友だち追加の承認管理と、毎朝7:07 / 7:37 JSTのGitHub Actions起動を設定するための手順です。

全体の完全な手順はリポジトリ直下の `README.md` にあります。このファイルはGAS部分だけを集中して確認したいときに使います。

## GASが担当すること

- LINE Webhookを `doPost(e)` で受け取る。
- `follow` イベントと `message` イベントを処理する。
- 友だち追加またはメッセージ送信したユーザーを `pending` としてスプレッドシートに保存する。
- LINEプロフィールAPIで `displayName` を取得する。
- 管理者へ登録申請を通知する。
- 管理者コマンド `approve` / `reject` / `list pending` / `list approved` / `help` を処理する。
- 承認済みユーザー一覧APIを `doGet(e)` で返す。
- `dispatchDailyAiNewsWorkflow()` でGitHub Actionsの `daily_ai_news` workflowを起動する。
- `setupDailyAiNewsWorkflowTriggers()` で7:07 / 7:37 JSTごろの時間主導トリガーを作る。

## 1. Googleスプレッドシートを作る

1. `https://sheets.google.com/` を開きます。
2. `空白` をクリックします。
3. ファイル名を `AIニュース配信ユーザー管理` などに変更します。
4. URLを確認します。

URLは次の形です。

```text
https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
```

`/d/` と `/edit` の間が `SPREADSHEET_ID` です。

シート名や列はGASが自動で整えます。使うシート名は `users` です。

列は次です。

```text
userId, displayName, status, createdAt, updatedAt, approvedAt, rejectedAt, note
```

スプレッドシートは全体公開しないでください。

## 2. Apps Scriptプロジェクトを作る

1. 作成したスプレッドシートを開きます。
2. 上部メニューの `拡張機能` → `Apps Script` をクリックします。
3. Apps Scriptエディタが開きます。
4. 左上のプロジェクト名を `AIニュースLINE承認Webhook` などに変更します。
5. 最初からある `Code.gs` の中身をすべて削除します。
6. リポジトリの `gas/Code.gs` の中身をすべてコピーします。
7. Apps Scriptの `Code.gs` に貼り付けます。
8. 保存アイコンをクリックします。

GitHub上の `gas/Code.gs` を変更してもApps Scriptには自動反映されません。変更したら貼り直し、必要に応じて再デプロイします。

## 3. スクリプトプロパティを設定する

Apps Script画面で、左メニューの歯車アイコン `プロジェクトの設定` → `スクリプト プロパティ` を開きます。

次を登録します。

| プロパティ名 | 値 |
| --- | --- |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging APIチャネルアクセストークン |
| `LINE_CHANNEL_SECRET` | LINE Basic settingsのChannel secret |
| `ADMIN_LINE_USER_ID` | 管理者のLINE userId。通常はGitHub Secretsの `LINE_TO_ID` と同じ |
| `SPREADSHEET_ID` | スプレッドシートURLの `/d/` と `/edit` の間 |
| `APPROVED_USERS_API_KEY` | GitHub Secretsにも同じ値を入れる長いランダム文字列 |
| `GITHUB_DISPATCH_TOKEN` | GitHub Actionsを起動するためのGitHub token |
| `GITHUB_REPOSITORY` | `owner/repo`。例: `aoiarakawa0821/ai-news-line-bot` |
| `GITHUB_WORKFLOW_FILE` | 通常は `daily_ai_news.yml` |
| `GITHUB_WORKFLOW_REF` | 通常は `main` |

`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_CHANNEL_SECRET`、`GITHUB_DISPATCH_TOKEN`、`APPROVED_USERS_API_KEY` は公開しないでください。

## 4. GITHUB_DISPATCH_TOKENを作る

1. GitHubにログインします。
2. 右上の自分のアイコン → `Settings` をクリックします。
3. 左メニュー下部の `Developer settings` をクリックします。
4. `Personal access tokens` → `Fine-grained tokens` を開きます。
5. `Generate new token` をクリックします。
6. 対象リポジトリをこのリポジトリだけに限定します。
7. `Actions: Read and write` を付けます。
8. tokenを作成します。
9. 表示されたtokenをApps Scriptの `GITHUB_DISPATCH_TOKEN` に貼ります。

表示されたtokenは一度しか見られません。

## 5. Webアプリとしてデプロイする

1. Apps Script画面右上の `デプロイ` をクリックします。
2. `新しいデプロイ` をクリックします。
3. 種類の選択で歯車アイコンをクリックします。
4. `ウェブアプリ` を選びます。
5. `説明` に `LINE Webhook` などと入力します。
6. `次のユーザーとして実行` は `自分` を選びます。
7. `アクセスできるユーザー` は `全員` を選びます。
8. `デプロイ` をクリックします。
9. 初回はGoogleの承認画面が出るので許可します。
10. 表示された `ウェブアプリ URL` をコピーします。

このURLを、LINE Developers ConsoleのWebhook URLと、GitHub Secretsの `APPROVED_USERS_ENDPOINT` に使います。

GASを修正した後は、`デプロイ` → `デプロイを管理` → 鉛筆アイコン → `バージョン` で新バージョンを選び、再デプロイしてください。

## 6. LINE Developers ConsoleにWebhook URLを設定する

1. LINE Developers Consoleを開きます。
2. 対象のMessaging APIチャネルを開きます。
3. `Messaging API` タブを開きます。
4. `Webhook URL` にGASの `ウェブアプリ URL` を貼ります。
5. `Update` をクリックします。
6. `Use webhook` をONにします。
7. `Verify` をクリックします。

Webhook検証で `302 Found` になる場合は、`doPost(e)` が `HtmlService.createHtmlOutput("OK")` を返す最新版の `gas/Code.gs` になっているか確認してください。

現在の `gas/Code.gs` は、正常時も例外時も `okResponse_()` でHTTP 200相当のOKを返します。署名検証に失敗した場合だけ拒否します。

## 7. GitHub Secretsに承認済み一覧APIを設定する

GitHubリポジトリで次を設定します。

```text
Settings → Secrets and variables → Actions → New repository secret
```

追加する値です。

| Secret名 | 値 |
| --- | --- |
| `APPROVED_USERS_ENDPOINT` | GASのWebアプリURL |
| `APPROVED_USERS_API_KEY` | GASスクリプトプロパティと同じ文字列 |

`LINE_TO_ID` は管理者へのエラー通知や後方互換のため残してください。

## 8. GASからGitHub Actionsを起動する

1. Apps Script画面を開きます。
2. 上部の関数選択で `testDispatchDailyAiNewsWorkflow` を選びます。
3. `実行` をクリックします。
4. GitHubの `Actions` タブで `daily_ai_news` が起動したか確認します。
5. 問題なければ、関数選択で `setupDailyAiNewsWorkflowTriggers` を選びます。
6. `実行` をクリックします。
7. 左メニューの時計アイコン `トリガー` を開きます。
8. `dispatchDailyAiNewsWorkflow` の時間ベーストリガーが2つあることを確認します。

この2つは、毎日7:07 JSTごろと7:37 JSTごろにGitHub Actionsを起動します。

GitHub Actions側にはcronはありません。GASが正式なスケジューラです。

## 9. 管理者コマンド

管理者はLINE公式アカウントに次を送れます。

```text
approve
approve Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
reject
reject Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
list pending
list approved
help
```

管理者以外が送っても実行されません。管理者判定は `ADMIN_LINE_USER_ID` と送信者userIdの完全一致です。

## 10. 登録申請の流れ

1. 友人がLINE公式アカウントを友だち追加します。
2. 友人が任意のメッセージを送ります。
3. GASが未登録ユーザーを `pending` として保存します。
4. 管理者に登録申請通知が届きます。
5. 管理者が `approve` を送ります。
6. 対象ユーザーが `approved` になります。
7. 対象ユーザーに「承認されました。明日からAIニュースが届きます」と届きます。
8. 翌朝、GitHub Actionsがapprovedユーザー全員へ送ります。

友だち追加だけではニュースは届きません。

## 11. 非管理者が自己承認できないことを確認する

Apps Scriptエディタで `runAdminSecurityTests` を選んで実行します。エラーが出なければ、次を確認できています。

- 非管理者の `approve 自分のuserId` は承認処理に到達しない。
- 非管理者の `approve 他人のuserId` は承認処理に到達しない。
- 非管理者の `reject userId` は拒否処理に到達しない。
- 非管理者の `list pending` / `list approved` は一覧取得に到達しない。
- `ADMIN_LINE_USER_ID` 未設定時は管理者コマンドがすべて拒否される。
- 曖昧な文章は管理者コマンドとして扱われない。

実際のLINEでも、非管理者アカウントから `approve 自分のuserId` を送り、返信が「このコマンドは管理者だけが実行できます。」で、スプレッドシートのstatusが変わらないことを確認します。

## 12. ログ確認

GASのログを見る場所です。

```text
Apps Script → 実行数 → 最新の実行
```

GitHub Actionsのログを見る場所です。

```text
GitHub → Actions → daily_ai_news → 最新の実行
```

見るポイントです。

- GASで `GitHub workflow_dispatch accepted...` が出ているか。
- GitHub Actionsで `OpenAIニュース生成に成功しました` が出ているか。
- `APPROVED_USERS_ENDPOINTから承認済み送信先を読み込みました。count=...` が出ているか。
- `LINE送信結果: success=... failure=...` が出ているか。

## 13. 停止方法

GASの自動起動を止めるには、Apps Scriptの `トリガー` から `dispatchDailyAiNewsWorkflow` の2つのトリガーを削除します。

または、Apps Scriptで `deleteDailyAiNewsWorkflowTriggers` を実行します。

Webhookを止めるには、LINE Developers ConsoleのMessaging APIタブで `Use webhook` をOFFにします。

GitHub Actions自体を止めるには、GitHubの `Actions` → `daily_ai_news` → `Disable workflow` を使います。
