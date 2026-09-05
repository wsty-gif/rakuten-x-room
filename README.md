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
6. 以降は毎日 7:30 / 12:15 / 20:30（日本時間）に自動実行される。GitHub側の混雑で数分〜十数分遅れることがある。
7. PC側のタスクスケジューラは二重投稿を避けるため解除する: `.\setup_schedule.ps1 -Remove`

スマホでやること: 通知をタップ → 楽天アプリで商品ページが開く → 共有ボタン →「ROOMに投稿」→ 通知に書かれたコメント案を貼って投稿。1件10秒。

手動で今すぐ投稿したいときは、スマホの GitHub アプリ（または ブラウザ）で Actions → Run workflow を押す。

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
