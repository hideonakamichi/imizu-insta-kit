---
name: note-publishing-toolkit
description: note.com に記事を 1 本仕上げる全工程ツールキット (汎用版)。テーマ決定 → 競合分析 (Jina Reader) → 記事生成 → ファクトチェック → 画像生成 (Gemini 3.1 Flash Image) → 入稿 (Chrome DevTools MCP) → デザイン QA → 公開 → 振り返りの 9 ステップ。「note 記事自動投稿」「note 入稿」「note 下書き」と言われたらこのスキルを使う。業界・テーマ・人格に依存しない汎用版で、業界固有の情報は呼び出し側 agent.md で定義する想定。
---

# note 記事入稿ツールキット (汎用版)

note.com に高品質な記事を 1 本投稿する 9 ステップ完全ガイド。
**業界・テーマ・人格に依存しない汎用版**。

## 設計方針

> **SKILL = 業界横断の「手順書」**
> **agent.md = 業界・人格・データソース固有**

このスキルは「**どう書くか / どう入稿するか**」を定義する。
「**何を書くか / 誰の口調で書くか / どこからデータを取るか**」は呼び出し側 agent.md が定義する。

## いつ使うか

- note.com に記事を投稿するエージェント全般
- 具体例: コラム / 業界解説 / 商品レビュー / ニュース要約 / ライフイベント解説 / etc

## いつ使わないか

- はてなブログ / Medium / 自社オウンドメディア (別ツールキット)
- X / Threads / Instagram (短文 SNS は別)
- メールマガジン (note の API ではない)

## 必要な環境変数 (`.env.local`)

| キー | 必須 | 用途 | 取得先 |
|---|---|---|---|
| `NOTE_EMAIL` | ✅ | note ログイン | https://note.com |
| `NOTE_PASSWORD` | ✅ | note ログイン | 同上 |
| `JINA_API_KEY` | ✅ | 競合分析 + ファクトチェック | https://jina.ai/api-dashboard/ |
| `GEMINI_API_KEY` | ✅ | 画像生成 | https://aistudio.google.com/ |

→ **画像はぜんぶ note 直接アップロードで完結する** (サムネも図解も)。外部画像ホスト (R2 / S3 / Cloudinary 等) は不要。

## 必要な MCP

- `chrome-devtools` (note 入稿、必須)

## 呼び出し側 agent.md に求めるもの

呼び出し元エージェントは以下を agent.md 内で定義する:

1. **テーマプール** — どんなジャンルの記事を書くか (例: 出産 / 子育て / コラム / 業界ニュース)
2. **書き手の人格** — 一人称・語り口・体験ベース表現の書き方
3. **データソース** — 本文素材の取得方法 (DB / API / Web スクレイピング / 手動入力)
4. **自社サイト URL 規約** — リンクを貼る時の正しい URL 形式
5. **業界固有のハードルール** — 「金額の正確性」「制度の有効性」等
6. **起動チェック** — 前回ログ確認等の自己保護

## 9 ステップ全工程

```
[Step 0] 起動チェック (任意、agent.md 定義)
   ↓
[Step 1] テーマ決定 (agent.md のテーマプールから)
   ↓
[Step 2] 競合分析 (★ Jina Reader で上位 5 記事を全文取得 → 比較表 → 勝ち筋)
   ↓
[Step 3] 記事生成 (★ 5 構成パターンから選択 → agent.md の人格で執筆)
   ↓
[Step 4] ファクトチェック (★ Jina Reader で公式ソース照合)
   ↓
[Step 5] 画像生成 (Gemini 3.1 Flash Image でサムネ + 図解)
   ↓
[Step 6] note 入稿 (Chrome DevTools MCP で実 Chrome 操作 + ローカル画像直接アップ)
   ↓
[Step 7] デザイン QA (PC + モバイル スクショ → Read tool 目視)
   ↓
[Step 8] 公開 + 通知 + 振り返り
```

★ = 省略禁止のコアステップ

---

## Step 0: 起動チェック (agent.md で定義)

呼び出し側 agent.md が「前回の重複回避」「自己フィードバック確認」を担当する。
このスキル本体には起動チェックロジックを書かない (業界固有のため)。

---

## Step 1: テーマ決定 (agent.md のテーマプールから選択)

agent.md で定義された **テーマプール** から 1 つ選ぶ。

選択基準 (汎用):
- **同じテーマを連続で出さない** (note ユーザーに「テンプレ感」を与える)
- 前回の記事を確認して被らないようにする (agent.md の起動チェックで取得した情報を使う)

→ 選んだテーマを **メイン KW** として記事タイトルに使う。

---

## Step 2: 競合分析 (★ 最重要、省略禁止)

### a. 上位 5 記事の URL 取得 (Jina Search)

```bash
source .env.local
curl -s "https://s.jina.ai/${MAIN_KW}" \
  -H "Authorization: Bearer ${JINA_API_KEY}" \
  -H "X-Return-Format: text"
```

→ 上位 5 記事の URL を記録。

### b. 公式以外の上位記事を 3 本以上、Jina Reader で全文取得

```bash
curl -s "https://r.jina.ai/${ARTICLE_URL}" \
  -H "Authorization: Bearer ${JINA_API_KEY}" \
  -H "X-Return-Format: text"
```

**Jina Reader の意義**: 任意の Web ページを LLM 用 Markdown に変換して返す。
スクレイピング・パース・広告除去が **1 行 curl** で完了する。

### c. 比較表を作る (この表がないと次に進めない)

| 項目 | 競合 A | 競合 B | 競合 C | うちの記事 (計画) |
|---|---|---|---|---|
| タイトル | | | | |
| 文字数 | | | | |
| 見出し数 | | | | |
| 情報の網羅性 | | | | |
| 数値・事実の正確性 | | | | |
| 具体性 (実例・固有名詞) | | | | |
| 独自視点 | | | | |
| 画像・図解 | | | | |
| 弱点 | | | | |

### d. 勝ち筋を 3 つ以上明文化

例:
- 「競合 A は要素を 2 つしか紹介してない → うちは 3 つ + 全体像で網羅性で勝つ」
- 「競合 B は情報が古い (2024 年) → うちは最新データ」
- 「どの競合も図解がない → 視覚的に差別化」

→ 勝ち筋を **記事構成に直接反映** する (Step 3 で使う)。

### 絶対のルール (競合分析)

1. **本文に競合への直接言及を入れない** — 「他のサイトでは」「どこよりも」「網羅的に」は使わない (読者は競合との比較に興味がない)
2. **比較表を作らないと次のステップに進めない** — 「検索結果のタイトルを見た」だけでは不可
3. **公式以外を最低 3 本** 全文取得する (公式ページは「まとめ」になりがちで参考にならない)

---

## Step 3: 記事生成

### 構成パターン (5 種から 1 つ選ぶ、前回と被らせない)

| パターン | 内容 | 向くテーマ |
|---|---|---|
| **羅列型** | 各要素を h2 で並べる | 制度・商品・選択肢の比較 |
| **時系列型** | 時間順に展開 | 手順・ストーリー・履歴 |
| **Q&A 型** | 読者の質問に答える | FAQ・初心者向け解説 |
| **数値シミュレーション型** | 数字から逆算 | コスト・効果の試算系 |
| **難易度順** | 簡単 → 難しい / 安い → 高い | 入門ガイド・段階別解説 |

### 構成設計の手順

a. **競合の弱点を突く構成** にする (Step 2-d の勝ち筋から逆算)
b. **競合にない独自セクション** を 1 つ以上入れる
c. **見出し構成を競合と変える** (h2 の数・順序を意図的にずらす)

### 人格・口調 (agent.md で定義した「書き手」を使う)

呼び出し側 agent.md に書かれた「人格」を必ず使う:
- 一人称 (例: わたし / 僕 / 私)
- 語り口 (例: ですよね / なんです / だと思います)
- 体験ベース表現 (例: 「〇〇していた頃〜」)

### 禁止表現 (汎用 AI 表現リスト)

```
〜することができます    →  〜できます
〜が可能です            →  〜できます
幅広く                  →  具体的に書く
網羅的に                →  具体的に書く
他のサイトでは          →  そもそも言及しない
どこよりも              →  そもそも言及しない
一助となれば            →  そもそも書かない
ぜひ参考にしてください  →  別の締め方
```

→ 上記表現が 1 つでも入ったら Step 3 やり直し。

### 記事メタデータ

- **文字数**: 800〜1,500 字 (note の読み手心理に最適)
- **見出し**: h2 を 3〜6 個、h3 は h2 の中で必要なら使う
- **リンク**: agent.md の URL 規約に従う、生 URL を貼らずテキストリンクで

→ `.claude/data/note-drafts/${SLUG}.md` に保存。

---

## Step 4: ファクトチェック (★ 公開前に必ず実施)

### a. 記事中の事実を抽出してリスト化

- 数値 (金額・期間・パーセンテージ)
- 期限 (申請期限・公開日)
- 固有名詞 (制度名・商品名・人名)
- 条件 (適用条件・除外条件)

### b. 各事実の公式ソース URL を Jina Reader で取得

```bash
curl -s "https://r.jina.ai/${OFFICIAL_URL}" \
  -H "Authorization: Bearer ${JINA_API_KEY}" \
  -H "X-Return-Format: text"
```

### c. 突き合わせ判定

| 項目 | 判定基準 |
|---|---|
| 数値 | 完全一致するか |
| 期限 | 最新の期限と一致するか |
| 固有名詞 | 公式の正式名称と一致するか |
| 有効性 | 公式ページで「終了」「廃止」になっていないか |

### d. 不一致への対応

| パターン | アクション |
|---|---|
| 数値が古い | 記事を修正 (公式に合わせる) |
| 略称・通称 | 正式名称に修正 |
| 終了している | **その項目を記事から除外** |
| 公式ページが 404 | 別の公式ソースを探す or 項目除外 |

### e. ファクトチェック結果を通知

agent.md の通知設定 (Discord / Slack / ログファイル等) に従って結果を通知。

---

## Step 5: 画像生成 (Gemini 3.1 Flash Image)

### サムネイル仕様 (必須)

- **サイズ**: 1280×670 px (note カバー画像サイズ)
- **スタイル**: フラットイラスト、パステルカラー、やわらかい (好みで調整)
- **テキスト**: タイトルの主要 KW を大きく入れる
- **内容**: テーマを象徴するイラスト

### 図解画像仕様 (任意、0〜2 枚)

- **サイズ**: 1280×720 px (16:9)
- **例**: フローチャート / 内訳図 / 比較表
- **日本語テキスト**: 大きく読みやすく
- **使う基準**: 文章で説明するより図のほうが伝わる場合のみ

### Gemini API 呼び出し

★ **必ず `gemini-3.1-flash-image-preview` を使用**。旧モデル (2.5 Flash 等) は日本語が崩れる。

```bash
source .env.local

PROMPT="ここにプロンプト"
OUTPUT=".claude/data/note-images/${SLUG}-thumb.png"

curl -s "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image-preview:generateContent?key=${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg p "$PROMPT" '{
    contents: [{parts: [{text: $p}]}],
    generationConfig: {
      responseModalities: ["TEXT", "IMAGE"]
    }
  }')" \
  > /tmp/gemini-response.json

# レスポンスから base64 画像を抽出して保存
jq -r '.candidates[0].content.parts[] | select(.inlineData) | .inlineData.data' \
  /tmp/gemini-response.json | base64 -d > "$OUTPUT"
```

### 品質チェック (Read tool で確認)

- [ ] 日本語テキストが崩れていない (ひらがな・漢字とも)
- [ ] 数値が記事と一致している (画像内の文字)
- [ ] 人物の指は 5 本、顔が自然
- [ ] サイズが指定通り

→ NG ならプロンプト調整して再生成。**手作業で直さない**。

---

## Step 6: note 入稿 (Chrome DevTools MCP)

画像ホストは不要。サムネも本文中の図解も、Step 5 で生成したローカル PNG を MCP の `upload_file` でそのまま note エディタに渡す。

### 6-1: Markdown → 入稿プラン JSON 変換

`scripts/note-publish.py` で記事 Markdown を構造化 JSON に変換しておくと、後段のブロック入力ループが楽:

```bash
python3 .claude/skills/note-publishing-toolkit/scripts/note-publish.py \
  --article path/to/article.md \
  --thumbnail path/to/thumb.png \
  > /tmp/note-plan.json
```

出力: `{title, thumbnail, blocks: [{kind: h2|h3|p|quote|list|code|tweet|hr, text|items}]}`

### 6-2: ページ起動 + ログイン

```
mcp__chrome-devtools__new_page → https://note.com/notes/new
```

- 飛び先が `/login` ならログイン処理:
  ```
  mcp__chrome-devtools__navigate_page → https://note.com/login
  mcp__chrome-devtools__fill_form → email / password (env)
  mcp__chrome-devtools__click → ログインボタン
  mcp__chrome-devtools__wait_for → URL 変化
  ```
- `/reset_password` 検知時は **即 abort** + 通知「手動再ログイン要」

### 6-3: サムネイルアップロード (ローカルファイル直接)

```
mcp__chrome-devtools__click → button[aria-label="画像を追加"] (記事カバー領域)
mcp__chrome-devtools__upload_file → ローカルのサムネ画像パス
mcp__chrome-devtools__click → 「保存」
```

### 6-4: タイトル + 本文入力 (★ 2 パス方式 ★)

タイトル:

```
mcp__chrome-devtools__click → textarea[placeholder*="タイトル"]
mcp__chrome-devtools__type_text → タイトル文字列
```

本文は **`document.execCommand` 流し込み + ツールバー整形** の 2 パス方式 (実装詳細・ハマり所は `references/editor-guide.md` 参照)。

#### Pass 1: 全段落を `execCommand` で一括流し込み

`type_text + Enter` は段落分割しない (`<br>` の soft break になる)。`document.execCommand('insertParagraph')` のみ信頼できる:

```javascript
// 単一の evaluate_script で blocks[] を一括投入
async (blocks) => {
  const editor = document.querySelector('.ProseMirror');
  editor.focus();
  document.execCommand('selectAll');
  document.execCommand('delete');
  for (let i = 0; i < blocks.length; i++) {
    document.execCommand('insertText', false, blocks[i].text);
    if (i < blocks.length - 1) document.execCommand('insertParagraph');
  }
  return { count: editor.children.length };
}
```

**markdown プレフィックスは付けない**。`> ` `## ` `- ` 等は autocomplete を誘発するが連続入力時の挙動が壊れているので使わない。

#### Pass 2: ブロック単位でリッチ整形

各 `kind` に対応するレシピ:

| `kind` | 操作 | 安定性 |
|---|---|---|
| `p` (段落) | 何もしない | ✅ |
| `quote` (引用) | 段落を選択 → floating toolbar の「引用」を click | ✅ JS click 可 |
| `h2` (大見出し) | 段落を選択 → 「見出し」expandable → 「大見出し」 | ✅ JS click 可 |
| `h3` (中見出し) | 同上 → 「小見出し」 | ✅ JS click 可 |
| `list-item` (リスト) | **1 段落ずつ** 「リスト」expandable → 「箇条書きリスト」 | ⚠️ 不安定。`take_snapshot` → `click(uid)` で叩くのが確実。連続段落が別々の `<ul>` になるので Pass 3 で merge |
| `code` (コード) | 段落を選択 → ツールバー「コード」 | ✅ JS click 可 |
| `image` (図解) | 段落の「+」メニュー → 「画像」→ `upload_file` | ✅ |
| `tweet` (X 埋め込み) | URL を単独段落として残せばリンクカード化される | ✅ |
| `hr` (区切り線) | execCommand で `---` を 1 段落として入れれば自動変換 | ✅ |

**floating toolbar を呼び出すには Selection だけでは足りず、対象段落上で mousedown/mouseup を `dispatchEvent` する必要がある**。レシピは `references/editor-guide.md` の「Pass 2-A」セクション参照。

#### Pass 3: 一括修復 + UL 連結

最後に `references/editor-guide.md` の Pass 3 スクリプトを実行:

- 空 h2 / 空 li を削除 (誤爆で生成された artifact を一掃)
- **連続する `<ul>` を 1 つに merge** (Pass 2 で list-item ごとに分かれた UL を統合)
- 連続空段落の整理

→ これで note エディタ上の構造が markdown ソースと一致する。

### 6-5: 下書き保存

```
mcp__chrome-devtools__press_key → Meta+s (Mac) / Ctrl+s (Win)
mcp__chrome-devtools__wait_for → "下書き保存しました" テキスト出現
```

### 6-6: Draft URL 取得

```
mcp__chrome-devtools__evaluate_script → window.location.href
```

→ `https://editor.note.com/notes/{id}/edit/`

---

## Step 7: デザイン QA

### スクショ撮影 (PC + モバイル両方、必須)

```
mcp__chrome-devtools__resize_page (1280, 1200) → take_screenshot → /tmp/note-${SLUG}-pc.png
mcp__chrome-devtools__emulate (iPhone 12) → take_screenshot → /tmp/note-${SLUG}-mobile.png
```

→ **両方を Read tool で必ず目視確認**。片方だけは NG (モバイル崩れを見落とす)。

### チェック項目

PC + モバイル共通:
- [ ] サムネが正しく表示 (切れ・歪みなし)
- [ ] 見出し (h2/h3) が太字で正しく変換
- [ ] 引用ブロックが灰色背景
- [ ] リストが箇条書きスタイル
- [ ] コードブロックが等幅フォント
- [ ] 図解画像が正しい位置・サイズ
- [ ] リンクがリンクカード化 (生 URL ではない)
- [ ] 不要な空段落・空 li がない
- [ ] テキスト化け・重複がない

モバイル特有:
- [ ] 長いタイトルが画面幅に収まる
- [ ] 引用ブロックがはみ出していない
- [ ] 画像が画面幅いっぱいに表示
- [ ] サムネが上下に切れていない

### NG 時のリカバリ

a. 問題を特定 → Markdown を修正
b. 壊れた下書きを note.com で削除 (手動)
c. Step 7 を再実行
d. 再度両スクショをチェック (OK になるまで繰り返す)

★ スクショを確認せず公開してはならない。

---

## Step 8: 公開 + 通知 + 振り返り

### 8-1: 公開 (現状手動推奨)

下書き OK ならユーザー or note.com 上で:
1. 「公開に進む」
2. ハッシュタグ追加
3. 記事タイプ選択 (無料 / 有料)
4. 「投稿する」

→ 完全自動化は note 側の bot 検知リスクあり、手動推奨。

### 8-2: 通知

agent.md の通知設定に従って完了報告。
- Discord / Slack / メール / ログファイル / DB へのレコード追加 等

通知に含めるべき情報:
- 記事タイトル + URL
- 文字数
- 自社サイトへのリンク数
- ファクトチェック結果 (全件 OK or 修正内容)
- デザインチェック結果
- 画像枚数 (サムネ + 図解)

### 8-3: 振り返り (4 層分離推奨)

agent.md の永続化先 (DB / ログファイル) に以下を 4 層に分けて記録:

| 層 | 中身 | 読む相手 |
|---|---|---|
| `result_full` | 記事 URL + タイトル + 抜粋 + サムネ URL | 人間 |
| `what_done` | やったこと (箇条書き) | 人間 + メタ |
| `quality_check` | 自己診断 ✅/❌ (業界固有項目は agent.md で定義) | 人間 + メタ |
| `self_improvement` | 自分 (エージェント) の改善案 | 自律改善エージェント |
| `content_improvement` | 記事側の改善案 | コンテンツ改善エージェント |

→ この 4 層分離が **次回起動時の自己学習** + **メタエージェントの自律改善** の起点になる。

---

## ハードルール (集約)

1. **1 回の実行で投稿するのは最大 1 記事**
2. **競合分析なしに記事を書き始めてはならない** (Step 2 必須)
3. **記事構成は競合分析から逆算で決める** (前回コピペ禁止)
4. **「どこよりも専門性が高い」記事でなければ公開しない**
5. **生 URL を貼らない** (テキストリンクで)
6. **サムネイル画像は省略禁止** (失敗時は下書きで止める)
7. **公開前に必ずファクトチェック**
8. **公開前に必ず下書き保存してスクリーンショット確認** (PC + モバイル両方)
9. **画像は `gemini-3.1-flash-image-preview` のみ** (旧モデル禁止)
10. **800 字未満の記事は公開しない**
11. **本文に競合への直接言及を入れない** ("他のサイトでは" 等)
12. **AI 表現禁止リスト** (Step 3 参照) を 1 つでも含んだら書き直し

## このスキルだけで完結する

関連スキルなし。`note-publishing-toolkit` 1 個でフロー完結を意図的に設計。
理由: エージェントが「どのスキルを呼ぶ?」と迷わないため、フロー全体を 1 ファイルで一覧できることを優先。

→ 将来「画像生成だけ別エージェントでも使う」状況になれば `gemini-image-generation` を分離する判断を取る。
それまでは YAGNI に従い、このまま 1 個に集約。
