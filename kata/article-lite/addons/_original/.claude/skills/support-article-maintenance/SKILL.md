---
name: support-article-maintenance
description: 公開済みひとり親支援記事 (supports.article_md IS NOT NULL) の定期点検手順。L1 静的チェック (scripts/article-health-check.sh の M01〜M22) / L2 URL・画像到達性 / L3 図解画像の目視 / L4 一次情報との突き合わせ (年度改正) / L5 外部レビュー指摘の一次情報検証。優先度スコアによる着手順、research_notes.maintenance_checks への記録まで。公開前査読 (support-article-reviewer) とは対象も頻度も異なる。
user-invocable: false
---

# 公開済み記事の定期点検手順

**対象**: `supports` テーブルで `article_md IS NOT NULL` の記事 (= 公開済み)
**運用の背景・頻度設計・優先度の根拠**: `docs/article-maintenance.md` (先に読むこと)

## この skill の位置づけ (既存 skill との住み分け)

| skill | 対象 | いつ |
|---|---|---|
| `support-article-writer` | 新規執筆 | `article_md IS NULL` の制度 |
| `support-article-reviewer` | 公開前査読 (32 項目 + E01〜E22) | 執筆直後・1 回だけ |
| **本 skill** | **公開後の定期点検 (M01〜M22)** | **公開後・週次〜年次で繰り返し** |

- **判定基準を再定義しない**。図解画像の目視基準は `support-article-reviewer` skill の **10c / E15 をそのまま使う**。
- **禁止表現のルール本体は `support-article-writer` skill にある**。本 skill はそれを公開後に再走査するだけ。
  ルールを変えるときは writer 側を先に直し、こちらの `Mxx` を同期する。
- エラーコードは **`Mxx`** (reviewer の `Exx` と番号空間を分けている)。

## Mission

| 項目 | 内容 |
|---|---|
| 目的 | 公開済み記事が「今も正しい」状態を保つ。リンク切れ・年度陳腐化・図と本文の矛盾・断定表現の残存を検出して直す |
| KPI | CRIT 0 件の維持 / 年次フル点検の完了率 / 外部指摘を受ける前に自分で見つけた件数 |
| 責任 | 公開後に腐った情報を放置しないこと |

### 制約 (絶対遵守)

- **一次情報に当たる**。記事・過去の research_notes・外部レビューのどれも「二次情報」。判断は必ず公式ページで裏を取る
- **外部レビューの指摘を鵜呑みにしない**。実例: 記事13 の電話番号を GPT が「古い」と指摘 → 公式ページを確認したら**現行番号だった**。指摘のまま直していたら読者を誤った窓口へ誘導していた
- **公式資料に無いものを書き足さない** (実例: 記事11 の「令和9年4月申請分まで」は公式資料に存在しなかった)
- **HTTP 200 は画像が正しい根拠にならない**。26 枚中 10 枚が別制度の画像だった事故はすべて 200 だった
- **直したら再チェックする**。修正の過程で新しい崩れが入る

---

## 実行フロー

```
0. 対象・層を決める (L1〜L5 のどれを回すのか)
1. L1: 静的チェック   bash scripts/article-health-check.sh --quick
2. L2: 到達性チェック  bash scripts/article-health-check.sh
3. 優先度ランキングの上位から着手
4. L3: 図解の目視     bash scripts/article-health-check.sh --images → Read で1枚ずつ
5. L4: 一次情報の突き合わせ (照合キュー M09/M12/M16/M17 + official_url を WebFetch)
6. 修正 → DB 再保存 → L1〜L3 を再実行
7. research_notes.maintenance_checks に記録
8. 報告 (下記フォーマット)
```

---

## L1 / L2: 機械チェック

```bash
# L1 (週次・記事を直すたび。ネットワーク不要・数秒)
bash scripts/article-health-check.sh --quick

# L2 (月次。URL/画像の到達性込み)
bash scripts/article-health-check.sh --json .scratch/maintenance/health.json

# 記事を絞る
bash scripts/article-health-check.sh --id 13 --id 11
```

終了コード `0` = CRIT なし / `1` = CRIT あり。生成物は `.scratch/maintenance/` (gitignore 済み)。

### 検出コードと対応

| コード | 内容 | 出たときの対応 |
|---|---|---|
| M01 | `official_url` / `source_url` 到達不能 | 公式サイトの URL 変更を探して DB を UPDATE。制度自体が終了していれば `status='closed'` を検討 |
| M02 | 本文リンク切れ | 移転先を探して差し替え。見つからなければリンクを外す (**推測 URL を書かない**) |
| M03 | 画像配信 NG / 2 枚未満 | Storage を確認。消えていれば `support-article-writer` skill の画像生成手順で作り直す |
| M04 | 内部リンクの実在性・パス整合 | `editorial-url-rules` skill に従って修正。「記事未執筆 (空ページ)」はリンクを外すか記事を書く |
| M05 | 対象者の断定・過度の一般化 | writer skill 「対象者の断定禁止」の形に書き換える。`※質問文中` `※直後が否定` の INFO は原則対応不要 (誤検出の可能性が高い) |
| M06 | 根拠なし全国傾向表現 | 「〜する自治体があります」「自治体によって異なります」に言い換える。統計的根拠があるなら出典を research_notes に足す |
| M07 | 免責の時点が古い | **時点だけ書き換えてはいけない**。L4 で内容を再検証してから時点を更新する |
| M08 | 最終更新から半年/1年 | L4 の対象に入れる |
| M09 | 旧年度リテラル / 未来年度 | 一次情報で当年度の額・要件を確認。未来年度は**公式資料に実在するか**を確認 (無ければ削除) |
| M10 | 査読記録なし / sources 3 件未満 | 公開前査読を経ていない可能性。L4 を優先実施し、結果を記録 |
| M11 | 前回点検からの経過 | 年次フル点検の未着手記事の判別に使う |
| M12 | `amount_max` と本文の不一致 | 一次情報で正しい額を確認し、**記事と DB の両方**を直す |
| M13 | 表示崩れ・AI 臭 | 該当行を修正。表示崩れ (全角コロン等) は公開後の手直しで混入しやすい |
| M14 | 図解の目視キュー | → **L3 へ (省略禁止)** |
| M15 | alt の数値が本文に無い | 図を直して alt が旧のまま、の疑い。図と alt の両方を確認して同期 |
| M16 | 時期・回数・期限の照合キュー | → **L4 へ**。公式ページの年間スケジュールと突き合わせる |
| M17 | 電話番号の照合キュー | → **L4 へ**。公式ページの現行番号と突き合わせる |
| M18 | 画像の命名規約違反 / 他記事との共有・重複 | 別記事の図の流用を疑う。L3 で中身を確認し、違えば作り直す |
| M19 | 役所語の残存 (`article_title` / `summary` / みさきの発言 / 見出し) | `support-article-writer` skill 「読者の言葉で書くルール」の言い換え表どおりに置換する。★**藤井先生の解説は検出対象外**★ (社労士の役割上、制度用語を使ってよい)。制度の正式名称・金額・所得制限額・期限・法令要件は**言い換えない** (置換で事実が変わるなら直さない)。INFO の `かっこ説明がない` は「所得（収入から必要な分を差し引いた額）」の形で補足を足す |
| M20 | **危険語** = 平易化のときに正確性を落としやすい表現 | ★**禁止ではなく「本当に正しいか一次情報で再確認せよ」の合図**★。一次情報 (official_url) に当たって、書いてある内容が事実ならそのままでよい。事実でなければ「安全な言い換え」に直す。★**M19 と違い藤井の解説も検出対象**★ (下の「なぜ藤井も対象なのか」参照) |
| M21 | 制度タイプ別の必須項目もれ | `supports.category` から判定した型で「必ず確認する項目」に本文が一度も触れていない。キーワードの有無しか見ていないので、まず記事を読んで本当に欠けているかを確認する。欠けていれば L4 で一次情報を取って書き足す |
| M22 | 記事末尾の構成順 | `support-article-writer` skill 「記事末尾の構成」の順 (基本情報まとめ → 併用できる制度 → よくある質問 → 公式情報・問い合わせ先) からのずれ。**INFO 固定**。既存記事の一括作り直しはしない (新規記事から適用し、記事を触る機会があれば直す) |

### M20 の運用 (危険語)

M19 (役所語) は「難しすぎる」を検出する。**M20 はその逆方向 ── 平易にしたら不正確になった ── を検出する。**
実際に 2 度事故が起きている:

1. 児童扶養手当を「毎月お金が入る」と書いた → 実際は**奇数月・年6回**
2. 千葉県医療費助成を「自己負担300円まで」と書いた → 実際は**市町村が定める1回あたりの負担額**で、総額の上限ではない

どちらも `article_md` 本体は正しく、**あとから書き換えた `article_title` / `summary` だけ**が誤りを持ち込んでいた。

| 危険な表現 | なぜ危険か | 安全な言い換え (例) |
|---|---|---|
| 毎月もらえる・毎月安くなる・毎月入る | 実際の振込頻度と食い違う | 月額で計算される／1か月あたりで算定される |
| 最大◯円もらえる | 全員がもらえるように読める | 条件を満たす場合の上限は◯円 |
| ◯円まで | 総額の上限に見える | 1回・1日など所定の単位で◯円 |
| 対象◯市 | 市の全域が対象に見える | ◯市内の対象区域 |
| 入学すれば返済不要 | 免除申請と認定が必要 | 入学後に免除申請をして認められた場合 |
| 当選確率が◯倍 | 実際の確率は応募状況で変わる | 抽せん番号が通常の◯倍割り当てられる |
| 申請期限は◯日 | 特別申請等の機会を見落とす | 通常の申請期限は◯日。ほかの申請機会の有無も確認 |
| 無料・全員・自動・誰でも | 例外や要件を落としている | (要件を添える) |

**重大度の設計** — これらは**文脈によっては正しい** (本当に毎月振り込まれる制度、本当に所得制限がない制度もある)。
禁止にすると正しい表現まで書けなくなるので、CRIT にはしない:

| 面 | 重大度 | 理由 |
|---|---|---|
| `article_title` / `summary` / 見出し | **WARN** | 読者が最初に読む面。補足を置く余地がないので、そのまま誤読される |
| みさき / 藤井の発言 | **INFO** | 前後で補足できる面なので参考扱い |

誤検出の扱いも面によって変えている:

- **タイトル・summary・見出し**: 質問文／直後が否定／同じ文に条件・単位の補足がある場合は WARN → INFO に落とす。**捨てない** (この面は見落としのほうが高くつく)
- **吹き出し**: 上記の補足があるものは**出さない**。「自動的に支給されるものではなく、修了後に別途申請が必要です」のように打ち消して書くのが吹き出しの正しい形であり、これを全部出すと本当に危ない 1 件が埋もれる

### なぜ藤井の解説も対象なのか (M19 との違い)

M19 は藤井を**対象外**にしている。M20 は**対象に含める**。理由:

- M19 が見ているのは「**読みやすさ**」。藤井は社労士なので制度用語を使うほうがむしろ正確で、指摘するとかえって記事が悪くなる
- M20 が見ているのは「**正確さ**」。役割は言い訳にならない。むしろ**藤井の口から出た誤りこそ読者に最も信じられてしまう**ので、除外する理由がない

実際、この設計で `id=19` の藤井の発言「もし毎月お金が入る制度を確認したいなら、児童扶養手当は…」を検出できた
(児童扶養手当は奇数月・年6回なので、事故①と同じ誤り)。藤井を除外していたら見逃していた。

---

## L3: 図解画像の目視点検 (★省略禁止★)

**機械では中身を判定できない唯一の領域**。26 枚中 10 枚が別制度の画像だった事故は、alt も HTTP ステータスも正常だった。

```bash
bash scripts/article-health-check.sh --images --id {ID}
# → .scratch/maintenance/{ID}/01-*.png … に落ちる。レポート末尾に "Read <path>" が並ぶ
```

**落ちた画像を 1 枚ずつ Read ツールで開く。まとめて眺めない。**

判定基準は `support-article-reviewer` skill の **10c / E15 を参照** (ここで再定義しない)。要点だけ再掲:

- ① 画像内のタイトル・ラベルが**その記事の制度名**と一致しているか
- ② 金額・数値・年度が**本文の表と一致**しているか
- ③ 日本語が破綻していないか (「マル1」「政府所」「健康保／保険証」等)
- ④ 同じ文言が二重に描かれていないか
- ⑤ 制度と無関係なモチーフが入っていないか

**メンテナンス固有の追加観点** (公開後にしか起きない):

- ⑥ **本文を直したあと、図が旧内容のまま取り残されていないか**
  実例 (2026-07-25 の初回実行で検出): 記事13 の `13-schedule.png` は「5月 定期募集 / 11月 定期募集 / 毎月 随時募集」の3枚看板だが、本文の表は 8月・2月 の定期募集も載せている (優遇抽せん対象外)。本文だけ直して図が置き去りになった状態
- ⑦ **alt テキストも本文の一部**。図を直したら alt も直す (M15 が数値レベルでは検出するが、文言は目視)

小さい文字は拡大して確認する:

```bash
python -c "from PIL import Image; im=Image.open('x.png'); w,h=im.size; im.crop((0,int(h*0.75),w,h)).resize((w*2,int(h*0.25)*2)).save('_zoom.png')"
```

1 つでも該当したら、`support-article-writer` skill の「画像内テキストの事故防止ルール」に従って**プロンプトを修正してから**再生成する (同じプロンプトで引き直すと同じ失敗を繰り返す)。既存の図の一部だけ直すときは image-to-image を第一選択にする。

---

## L4: 一次情報との突き合わせ (年次・年度改正)

対象記事の `official_url` を WebFetch し、**記事に書いてある事実を全件照合**する。

```bash
bash scripts/supabase-query.sh select supports "id=eq.{ID}&select=id,title,official_url,source_url,amount_max,amount_note,support_rate,research_notes"
```

照合する項目 (`support-article-reviewer` skill のファクトチェック項目と同じ粒度):

1. **支給額・給付率** — 年度改定を最優先で確認。`WebSearch("{制度名} 令和{当年度}年度 額改定")`
2. **所得制限** — 扶養人数別の限度額
3. **対象者要件** — 子の年齢要件、母子/父子の別
4. **申請の時期・回数・期限** — M16 の照合キューを全件つぶす (記事13「年2回の定期募集」型の事故)
5. **未来の期限表記** — M09 で出た未来年度が**公式資料に実在するか** (記事11「令和9年4月申請分まで」型の事故)
6. **問い合わせ先の電話番号・窓口名** — M17 の照合キュー
7. **年度改正で新設・拡充された制度の記載漏れ** — `WebSearch("{制度名} 令和{当年度}年度 拡充 新設 改正")`

各項目に `confirmed` / `changed` / `not_found` / `unreachable` の verdict を付け、`maintenance_checks.primary_source_recheck` に残す。

- `changed` → 記事と DB の両方を直す
- `not_found` → **記事から削除する** (公式資料に無いものは書かない)
- `unreachable` → 削除も修正もせず、次回点検に持ち越して記録に残す

免責注意書きの時点 (`※本記事は令和X年M月時点`) は、**L4 を実施した記事だけ**現在の年月に更新する。
機械チェックだけ通して時点を書き換えると「再検証したことにする」嘘になる。

---

## L5: 外部レビュー (GPT 等) の受領対応

★**指摘は仮説であって事実ではない。一次情報で検証してから直す**★

> 2026-07-25、GPT が記事13 の電話番号を「古い」と指摘した。東京都の公式ページを確認したところ**現行の番号だった**。
> 指摘のまま直していたら、読者を存在しない窓口に誘導していた。

1. 受領した指摘を `docs/feedback-article-{id}-{source}.md` に全文保存する (既存の `docs/feedback-article-*-gpt.md` と同じ命名)
2. 1 指摘 = 1 項目に分解する
3. 各項目を `official_url` / 制度所管の公式ページで検証し、`confirmed` / `partial` / `rejected` を付ける
   - 自治体サイトの記述は**その自治体のローカル運用の可能性**を疑う (`support-article-writer` skill 「全国共通と自治体差の峻別ルール」)
   - 公式資料に見当たらなければ `not_found` 扱いで、**記事に書き足さない**
4. `confirmed` / `partial` だけ直す。`rejected` は直さず理由を記録する
5. 直したら L1〜L3 を再実行する

---

## 記録 (research_notes.maintenance_checks)

**`reviewer_verifications` には書かない**。あれは公開前査読の合格記録で、`overall_verdict: "approved"` が公開ゲートの意味を持つ。
定期点検は別キー `maintenance_checks` に追記する (詳細な判断理由は `docs/article-maintenance.md`)。

```bash
ID=13
cat > /tmp/maint-$ID.json <<'JSON'
{
  "checked_at": "2026-07-25T09:00:00Z",
  "checked_by": "support-article-maintenance",
  "level": "L3",
  "basis_date": "2026-07-25",
  "findings": { "CRIT": 0, "WARN": 2, "INFO": 5 },
  "visual_review": { "images_checked": 2, "verdict": "ng", "notes": "..." },
  "primary_source_recheck": [
    { "claim": "...", "source_url": "https://...", "verdict": "confirmed", "action": "..." }
  ],
  "actions_taken": ["..."],
  "next_due": "2026-10-25"
}
JSON

EXISTING=$(bash scripts/supabase-query.sh select supports "id=eq.$ID&select=research_notes" | jq '.[0].research_notes')
echo "$EXISTING" | jq --argjson v "$(cat /tmp/maint-$ID.json)" \
  '.maintenance_checks = ((.maintenance_checks // []) + [$v])' > /tmp/notes-$ID.json
jq -n --slurpfile notes /tmp/notes-$ID.json '{research_notes: $notes[0]}' > /tmp/payload-$ID.json
bash scripts/supabase-query.sh update supports @/tmp/payload-$ID.json "id=eq.$ID"
```

★ ペイロードは必ず `@ファイル` 形式で渡す (Git Bash + 日本語 UTF-8 を `-d` で送ると壊れる)。

記事本文を直した場合は、`article_md` の UPDATE も同じ `@ファイル` 方式で行う (`support-article-writer` skill の「DB 保存」節と同じ)。

---

## 報告フォーマット

```
🔧 定期点検レポート ({層}: L1/L2/L3/L4/L5)
基準日: {YYYY-MM-DD} / 対象: {N} 記事
CRIT {a} · WARN {b} · INFO {c} / URL 到達性 {200×N}

## 着手した記事 (優先度順)
1. ${PUBLIC_SITE_URL}/support/{id} — {title}
   - 検出: M05 L237 対象者の断定
   - 一次情報: {url} で確認 → verdict=changed
   - 対応: 本文修正 + DB の amount_max 更新
2. ...

## 目視 (L3) の結果
- 画像 {N} 枚を Read で確認。NG {M} 枚 (理由)

## 外部指摘の扱い (L5)
- 受領 {N} 件 / 一次情報で confirmed {A} 件・rejected {B} 件
- rejected の理由: {...}

## 持ち越し
- {id}: unreachable のため次回に持ち越し

記録: research_notes.maintenance_checks に {N} 件追記
```

---

## 振り返り 4 層 reflection (メンテナンス固有)

`agent-bootstrap` skill の Step Final を踏まえ、以下を `quality_check` に入れる:

- ✅/❌ `article-health-check.sh` を実行し、CRIT を残さず処理 or 持ち越し理由を記録したか
- ✅/❌ 優先度ランキングの上位から着手したか (思いつき順で着手していないか)
- ✅/❌ L3 で図解画像を **1 枚ずつ Read** で目視したか (HTTP 200 で済ませていないか)
- ✅/❌ 図と**本文の表**を突き合わせたか / alt も同期したか
- ✅/❌ 修正した事実をすべて**一次情報**で確認したか (記事・過去の research_notes を根拠にしていないか)
- ✅/❌ 外部レビューの指摘を一次情報で検証してから反映したか (`rejected` の理由を記録したか)
- ✅/❌ 公式資料に無い情報を書き足していないか
- ✅/❌ 免責の時点を更新したのは L4 を実施した記事だけか
- ✅/❌ 修正後に L1〜L3 を再実行したか
- ✅/❌ `research_notes.maintenance_checks` に追記したか (`reviewer_verifications` を汚していないか)

---

## 仕様追記時のメタルール (孤立ルール防止・絶対遵守)

`support-article-writer` / `support-article-reviewer` に新しい品質要件が追加されたら、**公開後にも効くか**を必ず判定する:

- □ そのルールは公開後に破れうるか？ (年度で腐る / 修正時に混入する / 図と本文がずれる) → **Yes なら本 skill にも同期する**
- □ 同期する場合、`scripts/article_health_check.py` に `Mxx` として検出ロジックを書いたか？
- □ 機械で判定できないものは、L3 (目視) / L4 (一次情報) のどちらの手順に置いたか明記したか？
- □ 検出コード表 (本 skill の「検出コードと対応」) に行を足したか？

チェックリストだけ足してスクリプトに検出コードが無いと、機械ゲートが機能せず主観審査になる (reviewer skill と同じメタルール)。

## カスタマイズの指針

- **頻度**: `docs/article-maintenance.md` の 5 層テーブルが正。記事数が増えたら L4 の年次フル点検を四半期ごとの分割実施に変える
- **優先度スコア**: 現在は内部被リンク数をアクセス数の代理指標にしている。GA4 等を DB に取り込んだら `scripts/article_health_check.py` の `check_article()` 内の計算式を差し替える
- **記録先**: 記事 100 本超 or 横断集計が必要になったら `maintenance_logs` テーブルへ切り出す (判断基準は `docs/article-maintenance.md`)
- **禁止表現の語彙**: `scripts/article_health_check.py` 冒頭の `ASSERTION_PATTERNS` / `NATIONWIDE_PATTERNS` / `AI_PHRASES` / `SCHEDULE_PATTERNS` を編集する。writer skill 側のルール本体と必ず同時に直す
