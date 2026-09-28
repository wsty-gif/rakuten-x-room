# X + 楽天ROOM アフィリエイト自動化

毎日決まった時間に「今日は誰向けに何を出すか」を決め、楽天の売れ筋から商品を選び、投稿文を作ってXに投稿するツールです。
楽天ROOMへの追加だけは規約上、人が行います（1商品あたり3タップ、1日2〜3分）。

## 仕組み

```
[カレンダー] セール・季節・ギフト行事・5と0のつく日
[楽天API]   年代×性別のリアルタイムランキング / ジャンル別ランキング / キーワード検索
      ↓  trend_engine.py が毎回テーマ（誰向け×何）を決定
      ↓  selector.py がレビュー数・評価・料率・価格帯でスコアリング、30日以内の重複を除外
      ↓  writer.py が投稿文を生成（Claude API があればClaude、無ければテンプレート）
      ↓  x_poster.py が X 公式APIで投稿（画像付き、URLなし、#PR付き）
      ↓  room_todo.py が「ROOMに追加する商品リスト」を output/ に書き出す
```

## 何が自動で、何が手動か

| 工程 | 自動化 | 理由 |
|---|---|---|
| ジャンル・誰向けの決定 | 自動（毎回変わる） | カレンダー＋ランキングで判断 |
| 商品の選定 | 自動 | 楽天ウェブサービスAPI（無料） |
| 投稿文の作成 | 自動 | Claude API またはテンプレート |
| Xへの投稿 | 自動 | X公式API（従量課金） |
| 楽天ROOMへの「コレ！」 | **手動** | ROOM規約で機械的な投稿が禁止。違反すると利用停止 |
| 反応を見て調整 | 手動（週1回） | `data/calendar.json` と `.env` を触るだけ |

## セットアップ

### 1. 楽天側（無料・審査なし）

1. 楽天アフィリエイト https://affiliate.rakuten.co.jp/ に登録。「サイト情報」に **XアカウントのURL** と **ROOMのURL** を登録する（未登録媒体へのリンク掲載は規約違反）。
2. アフィリエイトIDを控える。
3. 楽天ROOMアプリを入れ、ROOMを開設。プロフィールにXのIDを書く。
4. 楽天ウェブサービス https://webservice.rakuten.co.jp/ で「アプリID発行」。アプリURLにはXのプロフィールURLを入れる。アプリIDとアクセスキーを控える。

### 2. X側

1. Xアカウントを作り、プロフィールに ROOM の URL を貼る。
2. 設定 → アカウント → 「自動化されたアカウント」ラベルを付ける（管理者は自分のアカウント）。Xの自動化ルールで必須。
3. https://developer.x.com/ で開発者アカウントを作り、アプリを作成。
   - App permissions を **Read and Write** にする（先に変更してからトークンを発行）
   - API Key / API Secret / Access Token / Access Token Secret の4つを控える
4. 従量課金クレジットを最低額（5ドル前後）チャージし、**月の支出上限を設定**する（初期値は無制限）。
   - URLなし投稿 1件 約0.015ドル（約2円）。1日3投稿で月7ドル未満。画像添付分は別途かかる可能性あり
   - **本文にURLを入れると1件0.2ドル（約30円）** になるので、このツールはURLを入れない設計

### 3. このフォルダ

```bash
pip install -r requirements.txt
copy .env.example .env
```

`.env` を開いてキーを貼る。Claude API（ANTHROPIC_API_KEY）は任意。無い場合はテンプレート文で投稿する。

### 4. 動作確認

```bash
python main.py plan --mock
```
キー無しでサンプルデータで流れを確認できる。

```bash
python main.py plan
```
本物の楽天APIで今日のテーマと候補15件を表示（投稿はしない）。

```bash
python main.py run --dry-run
```
投稿文まで作って表示。Xには投げない。

```bash
python main.py run
```
本番投稿。`output/room_todo_YYYY-MM-DD.md` にROOMへ追加する商品が書き出される。

### 5. 自動実行（1日3回）

PowerShell で:
```powershell
.\setup_schedule.ps1
```
毎日 7:30 / 12:15 / 20:30 に実行される（時間は ps1 内で変更可）。PCがスリープしていると動かない。

## Pinterest（RSS 自動公開・無料・審査なし）

Pinterest の API は個人向けの Trial だとピンが自分にしか見えず、公開には動画提出つきの審査が要る。
代わりに Pinterest 公式の「RSSフィードから自動公開」を使う。ブログが商品ごとの RSS を出し、Pinterest が毎日読んでピンを作る。

生成されるフィード（`build_site.py`）:
- `pin/all.xml` 全商品の新着60件
- `pin/<persona>.xml` 誰向け別（30s_woman / mama / 20s_woman / 20s_man / 30s_man / 40s_man）
各 item: タイトル（商品名＋割引 or 1位）、説明（誰向け・特徴・レビュー・実質価格・#PR）、リンク（ブログの日別記事）、画像（楽天の元画像）。

### 設定手順（初回のみ、20分）
1. Pinterest でビジネスアカウントを作る（無料。既存アカウントの「ビジネスアカウントに切り替え」でも可）。プロフィールのリンクにブログURL。
2. **ウェブサイトを認証する**: 設定 → 認証済みアカウント（Claimed accounts）→ ウェブサイト → `https://wsty-gif.github.io/` を入力 → **「HTMLタグを追加」** を選び、
   `<meta name="p:domain_verify" content="XXXX">` の XXXX をコピー。
3. GitHub の rakuten-x-room → Settings → Secrets and variables → Actions → **Variables** → New repository variable で
   Name `PINTEREST_VERIFICATION`、Value に XXXX を登録。Actions → Run workflow（dry_run=false）を1回実行してブログを更新。
4. Pinterest に戻り「認証」を押す。通ると「認証済み」になる。
5. ボードを作る（例: 「楽天で売れている物」「30代女性に人気」「子育てグッズ」…）。
6. 設定 → **ピンの一括作成（Bulk create Pins）** → **自動公開（Auto-publish）** → 「RSSフィードをリンク」 に
   `https://wsty-gif.github.io/pin/all.xml` を入れ、保存先ボードを選ぶ。誰向け別に分けるなら `pin/30s_woman.xml` などを追加（フィードごとに1ボード）。
7. 24〜48時間後に最初のピンが作られ、以降は毎日自動。1日200件まで。

注意: Pinterest でもアフィリエイト明示が必要。説明文に #PR を入れている。ピンの保存先ページ（ブログ）に広告表記があるので規約上も問題ない。

## カード画像（Pinterest 2:3 / Instagram 4:5）

`build_site.py` が直近7日の商品について、商品写真＋商品名＋評価・レビュー件数＋価格・実質価格＋バッジの
「情報カード画像」を自動生成する（`src/pin_image.py`）。`docs/pins/<code>.jpg`（1000×1500）と `docs/ig/<code>.jpg`（1080×1350）。
Pinterest のフィードはこのカード画像を使う（縦長のほうがフィードで大きく表示される）。
GitHub Actions では `fonts-noto-cjk` を入れて日本語を描く。Pages への公開は `keep_files: true` なので過去のカードも残る。

Pinterest のタイトルは「検索語が先頭」（例: 敬老の日のギフトに｜骨取りさば｜半額）。記事ページにはリッチピン用の
`article:published_time` 等を入れているので、https://developers.pinterest.com/tools/url-debugger/ で記事URLを1本検証すると
以降のピンがリッチピン（記事タイトル・更新日つき）になる。

## Instagram（フィード自動投稿・無料）

X に投稿した商品のうち `INSTAGRAM_SLOTS`（既定 noon,night = 1日2件）のものを、ブログ公開後にカード画像で投稿する。
Threads と同じ Meta 開発者アプリで、自分のアカウントなら審査不要。

1. Instagram アカウントを **プロアカウント（ビジネス or クリエイター）** に切り替える（設定 → アカウントの種類とツール）。
   プロフィールのリンクにブログURL、自己紹介に「楽天で売れている物を毎日｜PR」。
2. https://developers.facebook.com/ の既存アプリ（Threads 用）→ 「ユースケースを追加」→ **「Instagram」**（Instagram API with Instagram Login）。
3. ユースケース → Instagram → 設定 → 権限 `instagram_business_basic` と `instagram_business_content_publish` を追加。
4. 「アプリの役割」→ Instagram テスターとして自分の Instagram アカウントを追加 → Instagram アプリ側で 設定 → アプリとウェブサイト → テスター招待 を承認。
5. ユースケース → Instagram → 設定 → **「User Token Generator」** で自分のトークンを生成（60日、ツールが自動更新）。
6. `python setup_env.py` で `INSTAGRAM_ACCESS_TOKEN` に貼る。GitHub の Secrets にも `INSTAGRAM_ACCESS_TOKEN` を追加。
7. 次の昼・夜の実行から投稿される。確認: `python main.py instagram --dry-run`。

## 特集記事（行事・カテゴリ別、検索向け）

`python main.py topics`（夜枠で自動実行）が楽天の商品検索から特集用の商品を集め `data/topics.json` に保存、
`build_site.py` が `topics/<slug>.html` を生成する。日別記事と違い、検索されるキーワード単位の「まとめ記事」。

- **定番テーマ**（`data/topics_config.json` の evergreen、30件）: 「着る毛布」「無洗米 10kg」「電気圧力鍋」など。7日ごとに取り直す。
  `months` に検索が増える月を入れると、その月は一覧やサイドバーで上に出る。テーマの追加はこのファイルに1行足すだけ。
- **行事テーマ**（`data/calendar.json` の events）: 開始の45日前から自動で記事化し、2日ごとに更新。終了30日後に消える。
- 記事の構成: タイトル（「○○のおすすめ15選【2026年9月】レビューが多くて評価が高い順」）→ 導入文（数種類を切り替え）→ 目次 →
  データから作る「選び方」（価格帯の中央値、レビュー件数と評価の範囲、ポイント倍率、送料無料の割合、行事の日程）→ 商品15点 → 基準 → 関連特集。
  推測や効能は書かず、数字で言えることだけ。
- 導線: ナビ「特集」、トップの特集カード6枚、サイドバー「特集記事」、特集一覧 `topics/index.html`、サイトマップ、構造化データ（Article/ItemList）。
- Pinterest: `pin/topics.xml`（行事は6点、定番は3点ずつ、リンク先は特集記事）。Pinterest の自動公開に追加すると、
  30〜45日先の行事を探している人に先回りできる。

## Instagram ストーリーズとリール（自動）

- **ストーリーズ**: 各枠（朝・昼・夜）で X に投稿した商品の 9:16 カード（`docs/story/<code>.jpg`）を投稿する。
  24時間で消える。スタンプやリンクは API から付けられないので、画像内の「詳しくはプロフィールのリンクから」で誘導。
  枠は `INSTAGRAM_STORY_SLOTS`（既定 morning,noon,night）。
- **リール**: 夜枠で `python main.py reel-build` が「タイトル → 今日の商品3点（ゆっくりズーム）→ 締め」の約15秒の 9:16 動画を
  `docs/reels/YYYY-MM-DD.mp4` に作り、ブログ公開後に `main.py instagram` がリールとして投稿する（フィードにも表示）。
  `INSTAGRAM_REEL=0` で無効。ffmpeg はシステム版か `imageio-ffmpeg` 同梱版を使う。
- **BGM**: `assets/bgm/` に mp3 を1曲置くと自動で埋め込む（フェードイン・アウト付き）。無ければ無音トラック。
  著作権フリーで商用利用可のものを（DOVA-SYNDROME、甘茶の音楽工房、BGMer など）。音ありのほうがリールは伸びる。
- Pages への公開は毎回1コミットに置き換える（`force_orphan`）ので、動画を毎日出しても公開リポジトリは肥大化しない。

## ROOM で買われるための仕組み（売上の主戦場）

X/Threads は「知ってもらう」役、購入が起きるのは ROOM。ROOM のランクS/Aは「投稿から楽天市場へ誘導した人数」で決まり、
ボーナス +2〜3% が付くので、ROOM に出す点数を増やすこと自体が報酬率にも効く。

- **点数**: 1回の実行で `ROOM_PICKS_PER_RUN`（既定4）点をROOMに送る。セール中は1.5倍、5と0のつく日は+1。1日12〜18点。
- **選定基準**（`src/room_picks.py`）: ROOMで動く食品・日用品・子ども用品・キッチン・コスメを加点、1,000〜5,000円を優先、
  買い回り中は1,000〜2,000円の送料無料を強く加点、1万円超は減点。同じ商品は60日再送しない。
- **コメント**（`src/room_comment.py`）: 誰向け → 商品説明文から拾った具体的な特徴 → レビュー件数・評価 → 割引・締切・実質価格。
  効能表現・保管方法などの定型文は除外。通知本文＝コメントなので、長押しコピーで貼れる。
- **セール前ブースト**（`python main.py presale`、19:37 JST）: セール開始日・最終日・5と0のつく日だけ、8点をまとめて送る。
  20時開始の購買ピーク前に ROOM へ入れておくのが目的。対象日でなければ何もしない。`--force` で強制実行。
- **コレクション案**: `output/room_todo_*.md` の末尾に「コレクション」のまとめ方を出す。ROOM内の回遊とついで買いが増える。

ROOM 側で人がやること（1日5分）: 通知を順に「コレ！」、月に3〜5枚は手元の商品のオリジナル写真を投稿（ランクB条件）、
同ジャンルのROOMを10人フォロー＆いいね、コメントが付いたら返す。

## 実行を確実にする（外部cronから起動）

GitHub の定期実行は混雑時に丸ごと落ちることがある（夜枠が消える日がある）。無料の外部cron（cron-job.org）から
決まった時刻に「今すぐ実行」を送ると、数秒以内に確実に起動する。GitHub 側の20分おきの起動は保険として残す。

1. GitHub → 右上アイコン → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token。
   Repository access: Only select repositories → `rakuten-x-room`。Permissions → Repository permissions → **Actions: Read and write**。
   Expiration は1年。生成された `github_pat_...` を控える（1回しか表示されない）。
2. https://cron-job.org/ で無料登録 → 「Create cronjob」。
   - URL: `https://api.github.com/repos/wsty-gif/rakuten-x-room/actions/workflows/post.yml/dispatches`
   - Request method: **POST**
   - Headers（Advanced → Headers）:
     `Accept: application/vnd.github+json`
     `Authorization: Bearer github_pat_...`
     `X-GitHub-Api-Version: 2022-11-28`
     `User-Agent: cronjob`
   - Request body: `{"ref":"main","inputs":{"slot":"auto","dry_run":"false"}}`
   - Schedule（タイムゾーン Asia/Tokyo）: 毎日 07:00 / 12:00 / 18:25 / 19:40 / 20:15 の5回（同じジョブに複数時刻を設定できる）
   - 成功すると HTTP 204 が返る。`slot=auto` なので、その時間帯の枠を `slot_due.py` が判定し、済んでいれば何もしない。

## 反応を取る投稿（1日1回、18時台）

商品紹介だけだと「いいね・返信」が付かず、Xのアルゴリズムに表示を絞られる。
そのため 18:23 に `python main.py engage` が動き、投票 / 質問 / 楽天の小ネタ を日替わりで1本投稿する（`src/engage.py`）。
投票はXの投票機能を使うので押すだけで反応になり、最も効く。文面は事実ベースで効能表現は入れない。

## 毎日やること（2〜3分）

```bash
python room_open.py
```

未追加の商品ページがブラウザで順に開き、ROOM用コメントがクリップボードに入る。
ページ内の「ROOMに投稿する」を押し、コメントを貼り付けて投稿したら Enter。これを繰り返すだけ。
（スマホ派なら `output/room_todo_latest.md` の商品URLをROOMアプリの「コレ！」で検索してもよい）

夜の投稿が一番売れるので、少なくとも夜の分は投稿前（20時まで）にROOMへ入れておく。

## PCを開かずスマホだけで運用する（GitHub Actions + ntfy）

PCの代わりに GitHub の無料クラウド（GitHub Actions）で毎日3回スクリプトを動かし、
投稿した商品をスマホに通知する構成。PCの電源は不要になる。

1. スマホに **ntfy** アプリ（無料、アカウント不要）を入れ、「Subscribe to topic」で推測されにくい名前を1つ決めて購読する。
   例: `rakumitsu-room-7f3k9q2x`。同じ名前を `.env` の `NTFY_TOPIC` に書く。
2. GitHub アカウントを作り、**Private** リポジトリを1つ作る（名前は何でもよい）。
3. このフォルダを push する（下記コマンド）。`.env` は `.gitignore` で除外されるので上がらない。
4. リポジトリの Settings → Secrets and variables → Actions で、`python show_env_for_github.py` に表示される Name / Secret を登録する。
5. Actions タブ → 「post-to-x」→ 「Run workflow」で `dry_run=true` を一度実行し、ログで候補が出ることを確認。
6. 以降は自動実行される。GitHub の定期実行は数時間遅れることがあるため、20分おきに起動して
   `slot_due.py` が「今の時間帯に該当し、今日まだ投稿していない枠」を判定して動く（朝 6:50〜9:30 / 昼 11:45〜14:30 /
   反応投稿 18:20〜19:25 / セール前ブースト 19:30〜20:05 / 夜 20:10〜23:40）。遅れても枠内なら必ず投稿され、枠を過ぎた分は飛ばす。
   該当枠が無い回は数秒で終わるので、Actions の無料枠（月2,000分）は十分に収まる。
   分単位の正確さが欲しい場合は、無料の外部cron（cron-job.org など）から
   `POST https://api.github.com/repos/<user>/<repo>/actions/workflows/post.yml/dispatches`（body: `{"ref":"main","inputs":{"slot":"auto"}}`、
   Actions: Read and write 権限の Fine-grained token）を各時刻に呼ぶと即時に起動する。
7. PC側のタスクスケジューラは二重投稿を避けるため解除する: `.\setup_schedule.ps1 -Remove`

スマホでやること: 通知をタップ → 楽天アプリで商品ページが開く → 共有ボタン →「ROOMに投稿」→ 通知に書かれたコメント案を貼って投稿。1件10秒。

手動で今すぐ投稿したいときは、スマホの GitHub アプリ（または ブラウザ）で Actions → Run workflow を押す。

## Threads にも同時投稿する（任意）

Xに投稿した文と画像を、そのまま Threads にも投稿する。Meta の公式 Threads API を使うので規約上も問題なく、API料金は無料。

1. Threads アプリで、Xと同じ名前・アイコンのアカウントを作る（Instagramアカウントが必要）。プロフィールのリンクにROOMのURLを入れる。
2. https://developers.facebook.com/ で開発者登録（Facebook/Instagramアカウントでログイン）。
3. 「アプリを作成」→ ユースケースで **「Threads API にアクセス」** を選ぶ → アプリ名は何でもよい。
4. 左メニュー「ユースケース」→ Threads の「カスタマイズ」→ 権限 `threads_basic` と `threads_content_publish` を追加。
5. 「アプリの役割」→「役割」→「ユーザーを追加」→ **Threads テスター** として自分のThreadsアカウントを追加。
   Threads アプリ側で 設定 → アカウント → **ウェブサイトの権限 → 招待** を承認する。
6. ユースケース → Threads → 設定 の **「User Token Generator」** で自分のトークンを生成（60日有効）。
7. `python setup_env.py` で `THREADS_ACCESS_TOKEN` に貼る。GitHub Actions で動かす場合は Secrets にも `THREADS_ACCESS_TOKEN` を追加。

トークンはツールが毎日自動で更新するので、毎日動いていれば期限切れにならない。
（更新後のトークンは `data/threads_token.json` に保存され、GitHub Actions ではリポジトリにコミットされる。リポジトリは必ず Private にしておくこと）

## ブログ（GitHub Pages、無料・全自動）

投稿のたびに商品データが `data/site_items.json` に蓄積され、`build_site.py` が `docs/` に静的サイトを生成する。
GitHub Actions がそれをコミットし、GitHub Pages が公開する。費用0円、更新は全自動。

生成されるページ:
- `index.html` トップ（今日のおすすめ・日別記事一覧・誰向けリンク）
- `posts/YYYY-MM-DD.html` 日別記事「【9月6日】スーパーSALEで買われている物 TOP12」
- `for/<persona>.html` 誰向け別のまとめ（30代女性 / 子育て世帯 など6ページ）
- `ranking.html` レビュー評価ランキング TOP50
- `feed.xml` / `sitemap.xml` / `robots.txt`

ブログには楽天アフィリエイトリンクを直接置いているので、**Xのプロフィールのリンク先をROOMからブログに変えれば、手動の「コレ！」は不要になる**（ROOMも併用するなら今まで通り）。

### 公開手順（初回のみ、10分）
無料プランの GitHub Pages は Public リポジトリでしか使えないため、ブログ専用の公開リポジトリを別に作り、
ワークフローがそこへ `docs/` を書き出す（キー類が入っている本体リポジトリは Private のまま）。

1. GitHub で新しいリポジトリを作る。名前は **必ず `<ユーザー名>.github.io`**（例 `wsty-gif.github.io`）、**Public**、「Add a README file」にチェック。
2. 書き込み用トークンを作る: GitHub 右上のアイコン → Settings → 左下 **Developer settings** → Personal access tokens → **Fine-grained tokens** → Generate new token。
   - Token name: `blog-push`、Expiration: 1年（期限が来たら作り直す）
   - Repository access: **Only select repositories** → `<ユーザー名>.github.io` を選ぶ
   - Permissions → Repository permissions → **Contents: Read and write**
   - Generate して表示された `github_pat_...` をコピー（1回しか表示されない）
3. 本体リポジトリ（rakuten-x-room）→ Settings → Secrets and variables → Actions → New repository secret で
   Name `BLOG_PUSH_TOKEN`、Secret にそのトークンを登録。
4. 次の本番実行で `https://<ユーザー名>.github.io/` にブログが公開される（初回は数分かかる）。
5. **楽天アフィリエイトの「サイト情報」にこのURLを追加する**（未登録サイトへのリンク掲載は規約違反）。
6. 必要なら Xのプロフィールのリンク先をこのURLにし、投稿文のCTAを「▶まとめはプロフのリンクから」に変える（`src/writer.py` の `CTA`）。

ローカルで確認: `python main.py run --dry-run` のあと `python build_site.py` → `docs/index.html` をブラウザで開く。

## 週1回やること

- `python main.py report` で何を投稿したか確認
- Xのアナリティクスで反応の良かった投稿のペルソナ・ジャンルを見る
- `.env` の価格帯・レビュー条件、`data/calendar.json` のイベントを調整
- 楽天のセール日程（お買い物マラソン等）は月ごとに変わるので、公式カレンダーを見て `calendar.json` を更新

## 守るべきルール（違反すると全部無駄になる）

- **#PR を外さない。** ステマ規制（2023年10月〜）とXの有償プロモーション開示ルール（2026年2月〜）の両方で必須
- **ROOMを自動化しない。** 外部ツールでのログイン・投稿は利用停止対象
- **Xは公式API以外で自動化しない。** ブラウザ自動操作やスクレイピングは凍結対象
- **自分で買わない。** 自分のリンク経由の購入・家族の購入は報酬対象外かつ規約違反
- **DM・LINE・メールにリンクを送らない。** 楽天アフィリエイト規約で禁止
- 効果効能（治る・痩せる等）を書かない。薬機法
- 投稿は1日3〜5回まで。多すぎるとスパム判定でリーチが落ちる

## ファイル構成

```
main.py              CLI（plan / run / genres / report）
setup_schedule.ps1   タスクスケジューラ登録
.env                 APIキーと運用設定（Git管理しない）
data/calendar.json   セール・季節イベントのカレンダー（ここを育てるのが運用の中心）
data/history.json    投稿履歴（重複防止・ローテーションに使う）
data/mock_products.json  動作確認用サンプル
output/room_todo_*.md    ROOMに手で追加する商品リスト
src/config.py        設定・ペルソナ定義・ジャンルID
src/rakuten_client.py 楽天API
src/trend_engine.py  テーマ決定
src/selector.py      商品スコアリング
src/writer.py        投稿文生成
src/x_poster.py      X投稿
src/room_todo.py     ROOM用リスト出力
```
