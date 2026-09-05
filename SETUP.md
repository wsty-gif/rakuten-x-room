# 初期設定の手順書（初心者向け）

全部で30〜60分。順番どおりに進めてください。控えた値は最後に `.env` に貼ります。

---

## 準備するもの

- 楽天会員ID（無ければ https://www.rakuten.co.jp/ で無料登録）
- 携帯電話番号（Xの本人確認に使う）
- クレジットカードまたはデビットカード（X APIの5ドルチャージ用）
- メモ帳（控える値が8個あります）

控える値の一覧:

| 控える値 | 取得する場所 | `.env` の項目名 |
|---|---|---|
| アフィリエイトID | 楽天アフィリエイト | RAKUTEN_AFFILIATE_ID |
| ROOMのURL | 楽天ROOMアプリ | ROOM_URL |
| アプリID | 楽天ウェブサービス | RAKUTEN_APP_ID |
| アクセスキー（pk_で始まる） | 楽天ウェブサービス | RAKUTEN_ACCESS_KEY |
| API Key | X開発者コンソール | X_API_KEY |
| API Key Secret | X開発者コンソール | X_API_SECRET |
| Access Token | X開発者コンソール | X_ACCESS_TOKEN |
| Access Token Secret | X開発者コンソール | X_ACCESS_TOKEN_SECRET |

---

## 手順1. Xアカウントを作る（10分）

**なぜ先か:** 楽天アフィリエイトの「サイト登録」にXのURLが必要なので、Xを先に作ります。

1. https://x.com/ で「アカウント作成」。メールと電話番号で登録。
2. ユーザー名（@から始まるID）を決める。後で変えられるが、ROOMにも書くので最初に決めておく。
   例: `@raku_kurashi`（楽天・暮らし系だと分かる名前がよい）
3. プロフィールを書く。「楽天で見つけた良いものを毎日紹介 / リンクは下のROOMから」のように、何のアカウントか一目で分かる文にする。
4. **プロフィールのWebサイト欄は、あとで手順3のROOMのURLを貼るので今は空欄でOK。**
5. アイコンとヘッダー画像を設定する（無いとbot扱いされやすい）。
6. **自動化ラベルを付ける。** 設定とプライバシー → アカウント → 「アカウント情報」または「自動化」→「自動化されたアカウント」をオンにし、管理者として自分のアカウントを指定する。Xの自動化ルールで必須。
7. XのプロフィールURLを控える。`https://x.com/あなたのユーザー名`

**つまずきポイント:** 作った直後に大量フォローや連投をすると凍結されます。最初の1週間は1日1〜3投稿にとどめてください。

---

## 手順2. 楽天アフィリエイトに登録する（10分）

**なぜ必要か:** 報酬を受け取る本体です。ここに登録しないとROOMで紹介しても1円も入りません。

1. https://affiliate.rakuten.co.jp/ を開き、楽天会員IDでログイン。
2. 利用規約に同意して「新規登録」。審査はありません。
3. 「サイト情報の登録」に進む。**ここが最重要。** 登録していない媒体にリンクを貼ると規約違反になります。
   - サイト名: Xのアカウント名
   - URL: 手順1で控えたXのプロフィールURL
   - サイト種別: SNS → X（Twitter）
   - もう1件、手順3が終わったらROOMのURLも追加する（ROOMは自動で登録されることが多いが、念のため確認）
4. 「アフィリエイトID」を控える。管理画面の右上や「アカウント情報」に表示される、ドットで区切られた英数字（例: `1a2b3c4d.5e6f7a8b.1a2b3c4d.5e6f7a8b`）。
5. 報酬の受け取り設定を確認する。月3,000円までは楽天キャッシュで受け取れる。それ以上を現金で受け取るには楽天カードか楽天銀行が必要になるので、稼げてきたら用意する。

---

## 手順3. 楽天ROOMを開設する（5分）

**なぜ必要か:** Xの投稿からの受け皿です。ここに商品を置き、Xのプロフィールからここへ誘導します。

1. スマホに「楽天ROOM」アプリを入れ、楽天会員IDでログイン。
2. プロフィールを設定する。名前はXと同じにする（同一人物だと分かるように）。
3. プロフィール文にXのユーザー名を書く。
4. **自分のROOMのURLを控える。** アプリのプロフィール画面 → 共有ボタン → リンクをコピー。`https://room.rakuten.co.jp/room_xxxxxxxx/items` のような形。
5. Xに戻り、プロフィールのWebサイト欄にこのURLを貼る。**投稿本文にはURLを貼らず、常にここへ誘導する設計です。**
6. 練習として、手元にある気に入った楽天商品を3〜5個「コレ！」しておく。空っぽのROOMだと来た人が帰ってしまう。

---

## 手順4. 楽天ウェブサービスでアプリIDを発行する（5分）

**なぜ必要か:** ツールが楽天のランキングや商品情報を自動で取るための「鍵」です。無料、審査なし。

1. https://webservice.rakuten.co.jp/ を開き、楽天会員IDでログイン。
2. 右上の「+ アプリID発行」をクリック。
3. フォームに入力する。
   - アプリ名: `rakuten-x-room-bot` など何でもよい
   - アプリURL: 手順1のXプロフィールURL
   - アプリタイプ: 「Webサービス」や「その他」があれば選ぶ
   - **許可されたWebサイト: `www.rakuten.co.jp` と入力する。** 空欄や間違いだと403エラーになる
   - データ利用目的: 「SNSで楽天商品を紹介するため、ランキングと商品情報を取得」
   - 想定QPS: `1`
   - **APIアクセススコープ: 「楽天市場API」にチェックを入れる。** 未チェックだと全APIが403（REQUESTED_SCOPES_NOT_ALLOWED）になる
4. 発行された **アプリID（数字の列）** と **アクセスキー（`pk_` で始まる文字列）** を控える。
5. 同じ画面でアフィリエイトIDを紐づける欄があれば、手順2のアフィリエイトIDを入れる。

**つまずきポイント:** 2026年2月にAPIの仕様が変わりました。古い解説記事の手順やURLは動きません。アクセスキーが表示されない場合は、既存アプリを編集せず「新規」で発行し直してください。

---

## 手順5. X開発者コンソールでAPIキーを発行し、5ドルチャージする（15分）

**なぜ必要か:** ツールがあなたのXアカウントとして投稿するための鍵4つと、投稿1件ごとの料金の前払いです。

### 5-1. 開発者登録

1. 手順1のXアカウントでログインした状態で https://console.x.com/ を開く。
   （古い developer.twitter.com は使えません）
2. 「Sign up」または「Get started」。利用目的を聞かれたら、日本語で構わないので次のように書く。
   「自分のXアカウントで、楽天市場のおすすめ商品を1日3回自動投稿するツールを個人で運用します。読み取りは行いません。」
3. 3つの規約にチェックして送信。メール認証が来るので承認。

### 5-2. プロジェクトとアプリを作る

1. 「Create Project」。名前は何でもよい。用途は「Building tools for businesses」や「Making a bot」など近いものを選ぶ。
2. プロジェクトの中で「Create App」。アプリ名は世界で一意である必要があるので、`raku-room-bot-2026-あなたのID` のようにする。
3. **ここで表示される API Key と API Key Secret はこの1回しか表示されない。** すぐに控える。閉じてしまったら「Keys and tokens」→「Regenerate」で再発行できる（古いものは無効になる）。

### 5-3. 権限を「読み書き」にする（アクセストークンを作る前に！）

1. アプリの設定画面 → 「User authentication settings」→「Set up」。
2. App permissions: **Read and write** を選ぶ（Direct message は不要）。
3. Type of App: 「Web App, Automated App or Bot」を選ぶ。
4. Callback URI: `https://localhost` と入れる（`http://` は不可。実際には使わない）。
5. Website URL: 手順1のXプロフィールURL。
6. 保存。Client ID と Client Secret が表示されるが、**このツールでは使わないので控えなくてよい。**

### 5-4. アクセストークンを発行する

1. 「Keys and tokens」タブ → 「Access Token and Secret」→「Generate」。
2. **Access Token** と **Access Token Secret** を控える。
3. 表示されている権限が「Created with Read and Write permissions」になっていることを確認する。
   「Read only」になっていたら、5-3の権限変更が先に済んでいないので、権限を直してから「Regenerate」する。

### 5-5. クレジットをチャージし、上限を設定する

1. コンソールのアカウント設定 → 「Pay-Per-Use」または「Billing」→「Add credits」。
2. 最低額の **5ドル** をカードで購入する。前払い制なので、使い切ると投稿が止まるだけで勝手に課金されない。
3. **Spending limit（支出上限）を必ず設定する。** 初期値は「無制限」。月10ドルにしておけば安全。
4. 目安: URLなし投稿は1件0.015ドル。1日3投稿で月約1.4ドル。5ドルで3か月以上もつ。

**つまずきポイント:** キーは4つとも「パスワードと同じ」です。Xの投稿やスクリーンショットに絶対に載せないでください。漏れたら「Regenerate」で無効化できます。

---

## 手順6. `.env` を作ってキーを貼る（5分）

**なぜ必要か:** ツールが読む設定ファイルです。ここに8個の値を貼れば全部つながります。

1. エクスプローラーで `C:\Users\ProBook\アフィリエイト` を開く。
2. `.env.example` を右クリック → コピー → 貼り付け。`.env.example - コピー` ができる。
3. それを右クリック → 名前の変更 → `.env` にする（先頭のドット付き、拡張子なし）。
   「拡張子を変更すると使えなくなる可能性があります」と出たら「はい」。
   もし拡張子が表示されていない設定なら、エクスプローラーの「表示」→「ファイル名拡張子」にチェックを入れてから行う。
4. `.env` を右クリック → プログラムから開く → メモ帳。
5. `=` の右側に、控えた値を貼っていく。前後にスペースや引用符は付けない。

   ```
   RAKUTEN_APP_ID=1234567890123456789
   RAKUTEN_ACCESS_KEY=pk_xxxxxxxxxxxxxxxxxxxx
   RAKUTEN_AFFILIATE_ID=1a2b3c4d.5e6f7a8b.1a2b3c4d.5e6f7a8b
   ROOM_URL=https://room.rakuten.co.jp/room_xxxxxxxx/items
   X_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxx
   X_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   X_ACCESS_TOKEN=1234567890-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   X_ACCESS_TOKEN_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```

6. `ANTHROPIC_API_KEY` は空のままでよい（テンプレート文で動く）。後で投稿文の質を上げたくなったら設定する。
7. 保存して閉じる。

---

## 手順7. 動作確認

PowerShell（スタートメニューで「PowerShell」と検索）を開き、順番に実行する。

```powershell
cd C:\Users\ProBook\アフィリエイト
```

```powershell
python main.py plan
```

今日のテーマと候補商品が15件ほど表示されれば楽天側は成功。エラーが出たら、そのエラー文をそのままClaudeに貼ってください。

```powershell
python main.py run --dry-run
```

投稿文が表示される。Xにはまだ投稿されない。文面に問題がなければ次へ。

```powershell
python main.py run
```

本番投稿。Xを開いて投稿されていることを確認する。同時に `output\room_todo_latest.md` ができるので、そこに書かれた商品をROOMアプリで「コレ！」する。

```powershell
.\setup_schedule.ps1
```

毎日7:30 / 12:15 / 20:30 の自動実行を登録。「実行ポリシー」のエラーが出たら、先に次を実行してからやり直す。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

ここまでで完成です。
