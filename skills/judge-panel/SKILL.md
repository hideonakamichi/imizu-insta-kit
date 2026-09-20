---
name: judge-panel
description: >-
  登録済みサブエージェント（bugbot, security-review, ui, reader, product, ops, fact, devil）
  を必要な分だけ並列起動し、優先度つきの統合判定を1枚にまとめる。
  Use for ジャッジ, 多角的レビュー, judge panel, 提案レビュー, PR/release gates.
  コード差分は必ず bugbot + security-review を使う。
---

# Judge Panel（ハイブリッド・オーケストレーター）

メインエージェントが **審査員を必要な分だけ選び**、Agent ツールで **並列** 起動し、**1枚の統合判定**にまとめる。

**サブエージェントはレビュー専用。** 実装・探索・図解・修正は親が行う。

**審査員の定義（正本）:** `~/.claude/agents/`（`~/.claude/agents` はここへのジャンクション）。ルーブリックは各定義ファイルにあり、**親が貼り付けない。**

**正本:** 起動一覧 → [references/hybrid-flow.md](references/hybrid-flow.md) ／ ハーネス契約 → [references/harness.md](references/harness.md)

## いつ使うか

| 使う | 使わない |
|------|----------|
| 「ジャッジ」「多角的レビュー」と明示 | 単純な質問・1行修正 |
| Rule / トンマナ / Canvas / スライド / PR 前 | grill-me 等で未確定の計画段階 |
| コード変更の品質ゲート | サブエージェントへの実装・探索丸投げ |

## 手順概要

```
1. トリアージ（hybrid-flow.md）
2. 材料準備（コード→リポパス / 文章→全文）
3. 並列 Agent 起動（専用 + panel）
4. 統合レポート（Go / Revise / Stop）
```

---

### 1. トリアージ

[references/hybrid-flow.md](references/hybrid-flow.md) の表に従う。**コード差分があるときは `bugbot` + `security-review` を必ず含める**（汎用エージェント単独では見ない）。

| 対象 | デフォルト（並列） |
|------|-------------------|
| コード変更・実装 | `bugbot` + `security-review` |
| 文章・Canvas・スライド | `reader` + `product` |
| **提案文・セミナー資料・報告** | `fact` + `devil` |
| **プレゼン原稿・発表資料** | `devil` + `reader` |
| UI画面 | `ui` + `reader` |
| 設計・ADR（コードあり） | `bugbot` + `product` + `reader` |
| PR / フルジャッジ | `bugbot` + `security-review` + `reader` + `product` + `ops` |
| 提案フルジャッジ | `fact` + `devil` + `reader` + `product` + `ops` |
| CI チェック失敗 | `ci-investigator`（**未登録**）→ 無ければ Stop |

**デフォルトは1〜2並列。上限5**（フル／ユーザー明示時だけ）。超える場合は hybrid-flow の優先順位で削る。契約の詳細 → [references/harness.md](references/harness.md)

---

### 2. 材料準備（親）

| 対象 | 親が渡すもの |
|------|-------------|
| Bugbot / Security Review | `Full Repository Path` + `Diff` 種別（**diff は subagent が取得**） |
| CI Investigator | PR URL/番号 + 失敗チェック名 + リポパス |
| Panel 審査員 | 評価対象 **全文** または パス＋行範囲＋diff 抜粋 |
| Panel（`devil`） | 上記 ＋ **想定する聞き手**（決裁者 / 現場 / 同僚） |

**チェックリストは親が貼らない。** `ui` は UI Design Principles を、`reader` は図解のときスタバ図解チェックリストを、それぞれ **子が自分で Read する**（定義ファイルに絶対パスが書いてある）。正本を二重に持たないための設計。

---

### 3. 並列 Agent 起動

#### 3-a. 専用 subagent（コード・CI）

**審査員は `agents/` に登録済み。** 正本 `~/.claude/agents/`（`~/.claude/agents` はここへのジャンクション）。`subagent_type` に **ID をそのまま指定**する。

| `subagent_type` | description | 親が渡す材料 |
|------|-------------|------|
| `bugbot` | Bugbot | リポパス + Diff 種別（**diff は子が取得**） |
| `security-review` | Security Review | 同上 |
| `ci-investigator` | CI 調査 | **未登録。** 無いのでコード CI ジャッジは Stop |

- `run_in_background: false`（明示がなければ）
- **隔離は定義ファイルの `tools:` で構造的に保証済み。** `Write` / `Edit` を与えていないため、子は物理的にファイルを書けない。`readonly` という引数は存在しない（[harness.md](references/harness.md)）
- 失敗時: 1回再試行 → 欠席 → 残った人で統合（[harness.md](references/harness.md)）

#### 3-b. Panel 審査員（文章・UI・運用・設計文書）

- `subagent_type`: **審査員の ID をそのまま指定**（`reader` / `product` / `ops` / `ui` / `fact` / `devil`）
- prompt 先頭: **`[judge:REVIEW-ONLY:<ID>]`**
- **チェックリストは子が自分で Read する。** 親は貼り付けない（正本を二重に持たないため）
- 共有パケット:

```markdown
## 評価対象
[全文 / パス + 行範囲 / diff 抜粋]

## ユーザーの依頼（要約）
[1〜3文]

## 聞き手（devil 起動時のみ）
[決裁者 / 現場 / 同僚 のうち想定する相手]

## 制約（レビュー専用）
- レビューのみ。編集・探索・実装禁止
- 根拠がなければ「親が確認すべき事項」へ
- 各指摘に優先度（最重要 / 高 / 中 / 低）を付ける
- 定義ファイルの出力フォーマットのみ（日本語）
```

---

### 3-c. 失敗時

[harness.md](references/harness.md) に従う。要約:

1. 同じ人を **1回だけ** 再試行
2. 再失敗 → **欠席**（統合に「⚠️ 応答なし」）
3. 残った審査員で親が統合する。全員欠席 → 中断しユーザーに報告
4. `Agent` が無い環境 → 親が順に審査（並列しない）。`bugbot` 等が無いコード・ジャッジは Stop

---

### 4. 統合（親）

**指摘は優先度4段（最重要 / 高 / 中 / 低）で並べる。** 子の出力にも優先度が付いているので、親はそれを束ねて並べ直すだけでよい。

```markdown
# ジャッジ統合

## 判定
Go | Revise | Stop

## 指摘一覧（優先度順）
| 優先度 | 審査員 | 指摘 | 直し方 |
|--------|--------|------|--------|
| 最重要 | … | … | … |
| 高 | … | … | … |
| 中 | … | … | … |
| 低 | … | … | … |

## 審査員別サマリ
| 審査員 | 判定寄与 | 最重要指摘 |
|--------|----------|------------|

## 次にできること
[1行]
```

| 優先度 | 意味 | 判定への効き方 |
|---|---|---|
| **最重要** | 直さないと成果物として成立しない | **Stop** の根拠 |
| **高** | 直さないと目的を達成しにくい | **Revise** の根拠 |
| **中** | 直せば明確に良くなる | 判定を変えない |
| **低** | 好みの範囲、余力があれば | 判定を変えない |

- **Stop:** 最重要が1件でもある（セキュリティ Critical / High、依頼と矛盾を含む）
- **Revise:** 最重要なし、高が1件以上
- **Go:** 最重要も高もない

**再ジャッジは最大1回。** ブロッカーを出した subagent / 審査員 **だけ** 再実行。

親は統合の直前に起動ログを残す: `起動 / 並列 / 再試行 / 欠席`（[harness.md](references/harness.md)）。

**次にできること:** 判定が Go なら続行。Revise なら親が直し、出した人だけ再ジャッジ1回。Stop なら理由を返す。

---

## 審査員定義

**ルーブリックの正本は `agents/` の各定義ファイル。** [reviewers.md](reviewers.md) は一覧とトリアージの索引で、ルーブリック本文は持たない。

| ID | 役割 | 定義ファイル |
|----|------|------|
| `bugbot` | コードのバグ | `agents/bugbot.md` |
| `security-review` | セキュリティ | `agents/security-review.md` |
| `ui` | UI/UX デザイナー | `agents/ui.md` |
| `reader` | 読者・トンマナ | `agents/reader.md` |
| `product` | 要件・スコープ | `agents/product.md` |
| `ops` | 運用・コスト | `agents/ops.md` |
| `fact` | 根拠・事実確認 | `agents/fact.md` |
| `devil` | 想定反論 | `agents/devil.md` |

## トリガー例

- `ジャッジして`（対象に応じ hybrid-flow が自動トリアージ）
- `この差分をジャッジ` → bugbot + security-review
- `フルジャッジ` → PR 行（5体）
- `提案をジャッジ` → fact + devil
- `突っ込まれそうなところ` / `反論して` → devil
- `根拠を見て` / `数字を確認して` → fact
- `トンマナだけ` → reader
- `UIも見て` → ui を追加（5体上限で ops 等と入替）

## 運用

- 審査員のルーブリック変更 → **`agents/<ID>.md`**（reviewers.md ではない）
- トリアージ変更 → **hybrid-flow.md** + **reviewers.md**
- 審査員の追加 → `agents/` に定義ファイルを1本置き、reviewers.md と hybrid-flow.md に1行ずつ足す
- PR 作成フロー中は PR 専用ルールに従い TodoWrite と競合させない

## 追加リソース

- [references/hybrid-flow.md](references/hybrid-flow.md)
- [references/harness.md](references/harness.md)
- [reviewers.md](reviewers.md)
- [references/ui-design-principles-checklist.md](references/ui-design-principles-checklist.md)
- [references/starbucks-visual-checklist.md](references/starbucks-visual-checklist.md)
- [examples.md](examples.md)
