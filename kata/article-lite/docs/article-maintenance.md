# 公開済み記事の定期点検 (メンテナンス) 運用

**対象**: example.com の公開済み記事 (`supports.article_md`)
**初版**: 2026-07-25

## なぜこの文書があるか

このサイトには**記事を作る仕組み**はあるが、**作った後に見る仕組み**が無かった。

| フェーズ | 担当 | 既存の仕組み |
|---|---|---|
| 執筆時 | ライター (`support-writer`) | `support-article-writer` skill |
| 公開前査読 | レビュアー (`support-reviewer`) | `support-article-reviewer` skill (29 項目 + `check_article` E01〜E19) |
| **公開後** | **なし** | **なし** ← この文書が埋める穴 |

2026-07-25、外部レビュー (ChatGPT) に指摘されるまで、**26 枚中 10 枚の図解が別制度の画像だった**ことに誰も気づけなかった。
公開前査読は通っていた。通ったあと誰も見ていなかったから、事故が何日も放置された。

### 設計の材料にした 8 つの実例

| # | 起きたこと | 何が問題だったか | 本運用での捕まえ方 |
|---|---|---|---|
| 1 | 図解 26 枚中 10 枚が別制度の画像 (画像内が「認可保育園 保育料」「ゴールドカード比較」「春のイベントスケジュール」) | alt は正しく、URL も HTTP 200。**機械では中身を判定できない** | L3 目視点検 (M14) + M18 (命名規約・使い回しの機械検出) |
| 2 | 記事4: 本文の表は正しいのに図だけ「在学中12か月」と誤り | 図と本文の突き合わせをしていなかった | L3 目視点検 (図の数値を本文の表と照合) |
| 3 | 図を直したのに alt に旧図の誤りが残った | alt は本文の一部という認識が無かった | **M15 (alt 内の数値が本文に無ければ検出)** |
| 4 | 記事11 に「東京都に住んでいるだけで年22万円上乗せ」等の断定が 5 箇所 | writer skill に禁止ルールがあるのに公開されていた | **M05 (断定表現の grep。質問文・否定文は INFO に降格)** |
| 5 | 記事13: 都営住宅の定期募集を「5月と11月の年2回」と記載。実際は 8月・2月 の定期募集もある | 制度の運用そのものが記事と違った | **M16 (時期・回数の断定を照合キューに抽出)** + L4 一次情報再検証 |
| 6 | 記事11: 「令和9年4月申請分まで」— 公式資料に存在しない終期 | 存在しない情報を書いていた | **M09 (未来年度の言及を検出)** + L4 |
| 7 | 記事13 の電話番号。GPT が「古い」と指摘 → 一次情報を確認したら**現行番号だった** | 指摘のまま直していたら読者を誤った窓口へ誘導していた | **L5 外部レビュー手順 (指摘は必ず一次情報で検証してから直す)** + M17 (電話番号の抽出) |
| 8 | 年度改正 (毎年4月の金額改定、税制改正) で記事が陳腐化する | 年次の見直しサイクルが無い | **年次点検カレンダー** + M07/M08/M09/M12 |

---

## 点検の 5 層 (頻度を分ける)

全記事に 29 項目のフルレビューを毎回かけるのは非現実的。**軽い自動チェックを高頻度で、重い人手/AI レビューを低頻度で**回す。

| 層 | 内容 | 頻度 | 実行者 | コマンド | 所要 |
|---|---|---|---|---|---|
| **L1** | 静的ヘルスチェック (grep・日付・DB 整合) | **週次** + 記事を直すたび | スクリプト (手動 or cron) | `bash scripts/article-health-check.sh --quick` | 数秒 |
| **L2** | L1 + URL/画像の到達性 | **月次** | スクリプト | `bash scripts/article-health-check.sh` | 2〜3 分 |
| **L3** | 図解画像の目視点検 | **四半期** + 図を作り直した記事は都度 | AI (Claude) or 人 | `bash scripts/article-health-check.sh --images` → Read で 1 枚ずつ | 記事あたり 5 分 |
| **L4** | 一次情報との突き合わせ (制度内容の再検証) | **年次 (4〜5月)**。優先度上位 5 記事は**半期** | AI (`support-article-maintenance` skill) | skill の手順 | 記事あたり 20〜30 分 |
| **L5** | 外部レビュー (GPT 等) の受領対応 | **随時** | AI + 人 | skill の手順 | 指摘 1 件あたり 5〜15 分 |

### 何を機械化し、何を目視に残したか

**機械で検出できる (= `scripts/article-health-check.sh` が全部やる)**

| コード | 検出内容 | 層 |
|---|---|---|
| M01 | `official_url` / `source_url` の到達性 | L2 |
| M02 | 本文中の外部 URL のリンク切れ | L2 |
| M03 | 図解画像 URL の配信 (200 / 枚数 2 枚以上) | L2 |
| M04 | 内部リンクの実在性・公開状態・`editorial-url-rules` のパス整合 (全国 `/support/{id}` vs 地域 `/{pref}/support/{id}`) | L1 |
| M05 | 対象者の断定・過度の一般化 (writer skill 「対象者の断定禁止」の再走査) | L1 |
| M06 | 根拠なし全国傾向表現 (reviewer E19 と同一語彙) | L1 |
| M07 | 免責注意書きの欠落 / 時点表記の陳腐化 (6 か月で WARN、12 か月で CRIT) | L1 |
| M08 | `updated_at` からの経過 (180 日 WARN / 365 日 CRIT) | L1 |
| M09 | 年度リテラル (旧年度の残存 / 未来年度の言及) | L1 |
| M10 | `reviewer_verifications` の欠落・陳腐化、`sources` 3 件未満 | L1 |
| M11 | 前回メンテナンス点検からの経過 | L1 |
| M12 | DB の `amount_max` と本文金額の不一致 | L1 |
| M13 | 表示崩れ (全角コロン / `HH:MM` / mark 未閉じ / ディレクティブ開閉 / FAQ_JSON) + AI 臭フレーズ | L1 |
| M15 | **alt の数値が本文に存在しない** (図を直して alt が旧のまま、の検出) | L1 |
| M18 | 画像ファイル名が `{id}-*` 規約に合わない / 画像 URL を他記事と共有 / 画像バイナリが他記事と同一 | L1 (バイナリ照合は `--images` 時) |

**機械では判定できない (必ず人 or AI が一次情報に当たる)**

| コード | 内容 | どこで |
|---|---|---|
| M14 | 図解画像の**中身**が記事の制度と一致しているか。HTTP 200 は合格の根拠にならない | L3。判定基準は `support-article-reviewer` skill の **10c / E15 をそのまま使う** (再定義しない) |
| — | 図の数値が本文の表と一致しているか | L3 |
| M16 | 時期・回数・期限の断定 (「年6回」「5月と11月」「令和9年4月申請分まで」) が公式資料と一致するか | L4。スクリプトは**照合対象を列挙するだけ**で正誤は判定しない |
| M17 | 電話番号・窓口が現行のものか | L4 |
| — | 制度の内容そのものが現行と一致しているか | L4 (`official_url` を WebFetch) |
| — | 外部レビューの指摘自体が正しいか | L5 |

> M14 / M16 / M17 は「異常件数」ではなく**照合キュー**。0 件でないことが問題を意味するわけではない。

---

## 優先度の付け方

全記事を同時に見直せないので、着手順を機械的に決める。
`article-health-check.sh` が以下のスコアで並べ替えたランキングを先頭に出力する。

```
priority_score =
    内部被リンク数 × 10          ← 他記事から参照されている記事ほど読者が流入する
  + カテゴリ係数                 ← 手当/年金 20, 給付金 18, 税制 15, 貸付/助成 10, サービス 5
  + (更新からの経過日数 / 30) × 5
  + CRIT 件数 × 30
  + WARN 件数 × 5
```

- **内部被リンク数をアクセス数の代理指標にしている**。GA4 等の実アクセスデータをまだ DB に取り込んでいないため。
  将来アクセス数を取り込んだら `scripts/article_health_check.py` の `check_article()` 内スコア計算を差し替える。
- **カテゴリ係数**は年度改定の当たりやすさで決めている (手当・年金は毎年4月に金額改定、税制は毎年の税制改正)。
- 上記スコアに加えて、以下は**スコアを無視して最優先**で見る:
  1. 金額が改定された制度 (4月の改定告示・税制改正大綱で名指しされたもの)
  2. 外部から誤りの指摘を受けた記事
  3. 図解を作り直した記事 (作り直しの過程で新しい崩れが生まれる)

---

## 年次点検カレンダー (年度改正)

毎年4月の金額改定と税制改正で記事は必ず陳腐化する。時期を決めて先回りする。

| 時期 | やること | 対象 |
|---|---|---|
| **12月〜1月** | 「令和{X}年度 税制改正大綱」(財務省) を確認し、控除額・所得要件の改正と適用開始年分を記事に反映 | 税制カテゴリ (ひとり親控除 等) |
| **3月中旬** | 次年度の改定額を先読み。`WebSearch("{制度名} 令和{X}年度 額改定 政令")` / こども家庭庁・日本年金機構の報道発表 | 手当・年金カテゴリ |
| **4月1日〜4月中** | ★年次フル点検★ L4 を全記事に実施。金額・所得制限・年度表記を一次情報と全件照合 | **全記事** |
| **4月〜5月** | `--quick` の M09 で旧年度リテラルの残存を洗い出し、ゼロにする | 全記事 |
| **8月** | 現況届シーズン (児童扶養手当)。手続き時期の記述を再確認 | 手当カテゴリ |
| **10月〜11月** | 年度途中の制度新設・拡充 (補正予算) を確認 | 全記事 (L1 + 気になるものだけ L4) |

> 年次フル点検は 1 日で終わらない。優先度ランキングの上位から着手し、**着手済み/未着手を `research_notes.maintenance_checks` の `checked_at` で判別する** (L1 の M11 が未点検記事を教えてくれる)。

---

## 点検結果の記録先

### 判断: 既存の `research_notes` に **`maintenance_checks` という新しいキー**を足す

- ❌ `reviewer_verifications` に混ぜない。あれは**公開前査読の合格記録**で、`overall_verdict: "approved"` が公開ゲートの意味を持つ。定期点検の結果を同じ配列に足すと「いつ公開承認されたのか」が読めなくなる。
- ❌ 新テーブルは作らない。記事 13 本の規模で履歴分析の要件も無いため、`research_notes` (JSONB) にキーを足すだけで足りる (スキーマ変更不要)。
- ⏭ **切り出す条件**: 記事が 100 本を超える、または「先月 CRIT が何件出たか」のような**横断集計を定常的に見たくなったら** `maintenance_logs` テーブルに切り出す。そのときは `maintenance_checks` を移送すれば済む。

### スキーマ (`research_notes.maintenance_checks[]`)

```json
{
  "checked_at": "2026-07-25T09:00:00Z",
  "checked_by": "support-article-maintenance",
  "level": "L1",
  "basis_date": "2026-07-25",
  "findings": { "CRIT": 0, "WARN": 2, "INFO": 5 },
  "visual_review": {
    "images_checked": 2,
    "verdict": "ng",
    "notes": "13-schedule.png が 5月・11月・毎月の3枚看板で、本文の表 (8月・2月の定期募集あり) と不整合"
  },
  "primary_source_recheck": [
    {
      "claim": "都営住宅の定期募集は5月・11月・8月・2月の年4回",
      "source_url": "https://www.juutakuseisaku.metro.tokyo.lg.jp/...",
      "verdict": "confirmed",
      "action": "図解を作り直し"
    }
  ],
  "external_feedback": {
    "source": "ChatGPT 2026-07-25",
    "items_total": 8,
    "items_confirmed": 6,
    "items_rejected": 2,
    "rejected_reason": "電話番号「古い」の指摘は誤り。公式ページで現行番号と確認したため修正しない"
  },
  "actions_taken": ["図解 13-schedule.png を再生成", "alt を修正"],
  "next_due": "2026-10-25"
}
```

`verdict` の値: `confirmed` (記事どおり) / `changed` (制度が変わっていた) / `not_found` (公式資料に存在しない = 事故 #6 の型) / `unreachable` (公式ページが見られない)

### 書き込み方 (reviewer skill と同じ jq パターン)

```bash
ID=13
EXISTING=$(bash scripts/supabase-query.sh select supports "id=eq.$ID&select=research_notes" | jq '.[0].research_notes')
echo "$EXISTING" | jq --argjson v "$(cat /tmp/maint-$ID.json)" \
  '.maintenance_checks = ((.maintenance_checks // []) + [$v])' > /tmp/notes-$ID.json
jq -n --slurpfile notes /tmp/notes-$ID.json '{research_notes: $notes[0]}' > /tmp/payload-$ID.json
bash scripts/supabase-query.sh update supports @/tmp/payload-$ID.json "id=eq.$ID"
```

★ ペイロードは必ず `@ファイル` 形式で渡す (Git Bash + 日本語 UTF-8 を `-d` で送ると壊れる。`scripts/supabase-query.sh` の作法)。

---

## 外部レビュー (GPT 等) を受けたときの手順

★**指摘を鵜呑みにして直さない。必ず一次情報で検証してから直す**★

2026-07-25、GPT が記事13 の電話番号を「古い」と指摘した。一次情報 (東京都住宅政策本部の公式ページ) を確認したところ**現行の番号だった**。
指摘のまま直していたら、読者を存在しない窓口に誘導していた。**外部レビューは仮説であって事実ではない。**

1. **記録する**: 受領した指摘を `docs/feedback-article-{id}-{source}.md` に全文保存する (既存の `docs/feedback-article-*-gpt.md` と同じ命名)
2. **項目に割る**: 「タイトルの金額が誤り」「電話番号が古い」のように 1 指摘 = 1 項目に分解する
3. **一次情報で検証する**: 各項目について `official_url` や制度所管の公式ページを WebFetch し、`confirmed` / `rejected` / `partial` を付ける
   - 自治体サイトの記述は**その自治体のローカル運用の可能性**を常に疑う (`support-article-writer` skill 「全国共通と自治体差の峻別ルール」)
   - 公式資料に見当たらない場合は `not_found`。**「無い」ものを記事に足さない**
4. **`confirmed` / `partial` だけ直す**。`rejected` は直さず、理由を `maintenance_checks.external_feedback.rejected_reason` に残す
5. **直したら L1〜L3 を再実行**する (修正の過程で新しい崩れが入る)

---

## 手動実行と自動実行

このPCはスリープすることがあるため、**cron に完全依存しない**設計にしている。

### 手動 (このPC・Git Bash)

```bash
bash scripts/article-health-check.sh --quick                       # 数秒。記事を直したら毎回
bash scripts/article-health-check.sh                               # 月次。URL 到達性込み
bash scripts/article-health-check.sh --images                      # 四半期。目視キュー生成
bash scripts/article-health-check.sh --id 13 --images              # 記事を絞る
bash scripts/article-health-check.sh --json .scratch/maintenance/health.json
```

- 終了コード: `0` = CRIT なし / `1` = CRIT あり。スケジューラの失敗検知に使える。
- 生成物は `.scratch/maintenance/` (`.gitignore` 済み)。
- `--today YYYY-MM-DD` で基準日を差し替えられる (年度またぎの挙動テスト用)。

### 自動 (24 時間クラウド運用に移す場合)

| タスク | 頻度 | コマンド | 失敗時 |
|---|---|---|---|
| L1 静的チェック | 毎週月曜 8:00 | `bash scripts/article-health-check.sh --quick --json .scratch/maintenance/weekly.json` | 終了コード 1 で Discord 通知 |
| L2 到達性チェック | 毎月 1 日 8:00 | `bash scripts/article-health-check.sh --json .scratch/maintenance/monthly.json` | 同上 |
| L3/L4 | 四半期・年次 | **自動化しない**。スケジューラは「点検の期限が来た」ことを通知するだけにして、判断は AI/人が行う | — |

- **スリープ耐性**: L1/L2 はどの時点で走っても結果が同じ (冪等) なので、実行漏れは次回実行で回収される。M11 が「前回点検からの経過」を出すので、走らなかった週があっても検知できる。
- **クラウドに移す場合の前提**: `.env.local` の `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` と `python3` / `curl` / `bash` があれば動く (Supabase 以外の依存なし)。
- **現状**: cron / launchd への登録は**まだ行っていない**。手動実行のみ。登録する場合は `support-pipeline-orchestrator` skill の「スケジューラー」節と同じ場所に定義を足す。

---

## 既存の仕組みとの住み分け

| skill / 文書 | 守備範囲 | このメンテ運用との関係 |
|---|---|---|
| `support-article-writer` | 執筆時の品質ルール (断定禁止・自治体差の峻別・画像プロンプト・alt の同期) | **ルールの定義元**。M05 / M06 / M18 / M15 はここのルールを公開後に再走査しているだけ。ルールを変えるならまず writer 側を直す |
| `support-article-reviewer` | 公開前査読 29 項目 + `check_article` (E01〜E19) | **判定基準の定義元**。図解の目視基準 (10c / E15) は**再定義せず参照する**。E コードと M コードは番号空間を分けてある |
| `support-pipeline-orchestrator` | 新規記事の生産ライン (未執筆記事の選定 → 執筆 → 査読) | 対象が `article_md IS NULL`。メンテは `article_md IS NOT NULL` が対象。**重ならない** |
| `editorial-url-rules` | URL 構造 (`/support/{id}` と `/{pref}/support/{id}`) | M04 がこのルールへの適合を機械チェックする |
| `docs/feedback-article-*-gpt.md` | 過去に受けた外部レビューの記録 | L5 の記録先としてこの命名を踏襲する |
| **`.claude/skills/support-article-maintenance`** | **公開済み記事の定期点検の実行手順** | 本文書が「なぜ・いつ・誰が」、skill が「どうやるか」 |

### 新しい品質ルールを追加するときのメタルール (孤立ルール防止)

`support-article-writer` / `support-article-reviewer` の既存メタルールに**メンテナンス層を1つ足す**:

1. writer の実行フロー
2. writer のプレデリバリー検証 (grep 検出)
3. writer のレンダリングチェック
4. reviewer のチェックリスト (A〜E)
5. reviewer の `check_article` (`Exx`)
6. **メンテナンス: `scripts/article_health_check.py` に `Mxx` として公開後の再走査を足す** ← 新規

公開前だけ守られて公開後に腐るルールを作らないため。

---

## 現状 (2026-07-25 初回実行時点)

- 対象: 13 記事 (id 1〜13)。id 14 / 15 は `article_md` 未執筆。
- URL 到達性: 41 URL すべて 200。
- **初回実行で見つかった問題は本文書ではなく実行レポート側に残る** (`.scratch/maintenance/health.json`)。恒久的に残したい判断は `research_notes.maintenance_checks` に書く。
