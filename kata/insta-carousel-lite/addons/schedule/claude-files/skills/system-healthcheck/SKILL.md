---
name: system-healthcheck
description: 週次でシステム全体の健全性を点検する手順。アクセストークン期限・投稿成否・生成品質サンプル・ネタ帳残数を確認し、Discordにレポートする。launchdのhealthcheck plistから起動され、Opusが担当する。
---

# system-healthcheck

週1回、`bin/run_healthcheck.sh` から起動される点検パイプライン。見落としが許されない
検知作業（トークン失効予兆・投稿欠落・品質劣化）のため **Opus** が担当する
（`CLAUDE.md` のモデル割り当てを参照）。

## 手順

### Step 1: アクセストークンの残存期限チェック

```bash
python3 .claude/skills/system-healthcheck/scripts/check_token.py
```

出力の `issued_at_assumed` が `true` の場合、`remaining_days` は**暫定値**であり
実際の残存日数はこれより短い可能性がある。レポートにその旨を明記し、
`logs/token_state.json` の `issued_at` を実際の発行日に直すよう促すこと。

出力JSONの `remaining_days` を確認する。この方式（Instagram業務用ログイン）は
Facebookの `/debug_token` に相当する期限照会APIが無いため、`logs/token_state.json` に
記録した発行時刻から逆算し、あわせて `graph.instagram.com` への軽量リクエストで
実際にトークンが生きているか確認している（詳細は `check_token.py` のdocstring）。
`config/loop-limits.yaml` の `token_refresh.warn_before_days`（既定10日）以下なら、
スクリプトが自動的に `instagram-publishing/scripts/refresh_token.py` を呼んで更新を試みる
（`refreshed: true/false` で結果が返る）。

- `refreshed: true` → 更新成功。レポートに記載するのみ
- `refreshed: false` かつ `refresh_stderr` に「Failed to decode」等が含まれる →
  発行/前回更新から24時間未満で更新対象として未成熟な可能性が高い（`references/graph-api-errors.md`
  参照）。有効期限内であれば緊急ではないので、次回点検まで様子見でよい
- `refreshed: false` でそれ以外のエラー、かつ期限が近い → **緊急通知**（Step 5で優先度highとして送る）
- `valid: false`（トークン自体が既に無効） → 即座に緊急通知。手動でのトークン再発行が必要

### Step 1.5: Grok CLI（生成エンジン）の疎通確認

```bash
python3 .claude/skills/system-healthcheck/scripts/check_grok.py
```

リールの映像生成はGrok CLI（SuperGrok/X Premium+のサインイン）に依存している。
**`config/schedule.yaml` でリール系のジョブ（`pipeline: "reel"`）が1つも `enabled: true` でなければ、
この点検は省略してよい**（カルーセルだけの運用では Grok を使わないので、未サインインは異常ではない）。
`ok: false` の場合、次回の生成パイプラインは確実に失敗するため、**緊急通知**として
Step 5のレポート先頭に含める（対処: そのMacで `grok login` を実行して再サインイン）。

### Step 2: 直近1週間の投稿成否・ネタ帳残数

```bash
python3 .claude/skills/system-healthcheck/scripts/audit_posts.py
```

- `has_missing_posts: true` → 予定投稿数（`config/schedule.yaml`）に対して実投稿数が不足している。
  原因は2種類ある。①起動していない（Mac未起動・スリープで launchd の発火を逃した。`logs/launchd/` に
  その時刻のログが無い）②起動したが品質ゲートで中止した（ログはあり、Discordに失敗通知が出ている）。
  どちらかをログの有無で切り分けてレポートに書く。**導入から7日以内・スケジュールを増やした直後は、
  増やす前の日も数えるので欠落が出るのは正常**（その旨を添える）
- `schedule_error` が null でない → `config/schedule.yaml` が読めない。欠落検知ができていないので要対応として報告する
- `low_stock_warning: true` → **いま選べる**ネタが `low_stock_threshold`（1週間ぶんの投稿数。最低5件）以下。
  ストックはネタ元から自動生成されるので、補充＝**`content/sources/` に文章を足すこと**
  （書式は `content/sources/README.md`）。その旨をレポートに含める
  （`content/themes.md` への手書きの追記は次の起動で上書きされる）。
  `remaining_themes` は総数ではなく「直近 `theme_cooldown_days` 日で未使用の件数」
  （theme-picker が避ける窓と揃えてある）。総数は `total_themes` を見る

- `article_index.ok: false` → ネタの索引（`build_article_index.py`）の更新が失敗している。
  **索引の更新に失敗しているあいだ、投稿パイプラインは起動時に中止される**（取り下げた文章が古い索引に残ったまま
  投稿されるのを防ぐため）。投稿が止まっている原因として報告する。`last_error` と `last_ok_at`
  （いつから止まっているか）をレポートに含める

### Step 3: 生成物サンプルの品質再点検

直近7日間で `output/` に生成されたバナー・リールから、それぞれ最大2件をサンプリングし、
`evaluator` サブエージェントに `docs/DESIGN.md` の Quality Gates で再点検させる。
**依頼時に「週次点検の事後監査である」ことと、`carousel_spec.json` / `reel_meta.json` に
`source_path` があればその値を渡す。** `source_path` が無い生成物は**保存漏れ**なので、evaluator には
回さず、点検異常としてレポートに書く（ネタ元を根拠にしたか事後に確かめられない投稿が出ている、という意味）
（投稿前チェックをすり抜けた劣化がないかの事後監査。investigate用途で、この結果で
投稿を取り消すことはしない）

### Step 4: APIエラー傾向の確認

直近の `output/*/post_result.json` を読み、エラーの傾向（`instagram-publishing/references/graph-api-errors.md` の
code別）を確認する。頻発しているエラーがあればレポートに含める。

`logs/PUBLISH_UNCONFIRMED.json` が存在したら**緊急**として先頭に書く（前回の投稿が公開されたか未確認で、
解除されるまで投稿が止まっている。ファイルの `what_to_do` を案内する）。

投稿数の上限（`content_publishing_limit`。100件/24時間）の照会は、このキットには照会用のスクリプトが無いので行わない
（許可リストに無いコマンドを自作して叩かない）。週に数本〜1日数本の運用では達しない。

### Step 5: Discordにレポート送信

```bash
python3 .claude/skills/instagram-publishing/scripts/notify.py report \
  --title "週次点検レポート（YYYY-MM-DD は今日の日付に置き換える）" \
  --body "<Step1〜4の結果をまとめたテキスト>"
```

トークン失効間近・投稿欠落・低品質検出など緊急度の高い項目は本文の先頭に太字で強調する。

## 出力

- Discordへのレポート投稿（成功/警告/緊急の3段階で書き分ける）
- 特に対応不要な週は「異常なし」の短いレポートでよい（無言で終わらせない。
  点検が実際に走ったことが分かるようにする）
