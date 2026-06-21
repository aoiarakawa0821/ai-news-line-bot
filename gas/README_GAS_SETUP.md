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

`APPROVED_USERS_API_KEY` の例:

```text
daily-ai-news-approved-users-2026-long-random-text-123456
```

実運用ではもっと長く、他人に推測されにくい文字列にしてください。

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

## 7. 管理者コマンド

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

## 8. 友人に登録してもらう流れ

1. 友人にLINE公式アカウントのQRコードや友だち追加リンクを送ります。
2. 友人がLINE公式アカウントを友だち追加します。
3. 友人が `登録` など任意のメッセージを送ります。
4. GASがuserIdとdisplayNameを取得し、スプレッドシートに `pending` として保存します。
5. 管理者に登録申請通知が届きます。
6. 管理者が `approve` を送ると、そのユーザーが `approved` になります。
7. 承認されたユーザーには「承認されました。明日からAIニュースが届きます」と届きます。
8. 翌朝のGitHub Actionsが `approved` ユーザー全員へニュースを送ります。

友だち追加だけではニュースは届きません。管理者が承認した人だけに届きます。

## 9. 動作確認

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

## 10. うまく動かない場合

- LINE Developers Consoleで `Use webhook` がONか確認します。
- Webhook URLがGASのウェブアプリURLになっているか確認します。
- GASを修正した後は、必要に応じて `デプロイ` → `デプロイを管理` → 編集 → 新しいバージョンで再デプロイします。
- `SPREADSHEET_ID` が正しいか確認します。
- `ADMIN_LINE_USER_ID` が管理者自身のuserIdか確認します。
- `APPROVED_USERS_API_KEY` がGASとGitHub Secretsで同じか確認します。
- スプレッドシートを全体公開しないでください。
- LINEアクセストークン、Channel secret、APIキーをREADMEやコードに書かないでください。

