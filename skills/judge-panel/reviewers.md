# Judge Panel — 審査員一覧（索引）

**ルーブリックの正本はここではない。** 各審査員の判定基準・出力フォーマットは、登録済みサブエージェントの定義ファイルにある。

```
~/.claude/agents/<ID>.md
（~/.claude/agents はここへのジャンクション）
```

ルーブリックを直すときは **定義ファイルを直す。** このファイルには写しを置かない（二重管理を避けるため）。

トリアージ・起動一覧 → [references/hybrid-flow.md](references/hybrid-flow.md)

---

## 審査員一覧

| ID | 役割 | 主な観点 | 使うツール |
|----|------|----------|-----------|
| `bugbot` | コードのバグ | 正しさ、回帰、型、エラー処理、テスト、依頼外の変更 | Read / Grep / Glob / Bash |
| `security-review` | セキュリティ | 秘密情報、認証・権限、入力、注入、依存、通信と保存 | Read / Grep / Glob / Bash |
| `ui` | UI/UX デザイナー | 階層、状態、A11y、操作性、UI Design Principles 全項目 | Read / Grep / Glob |
| `reader` | 読者・トンマナ | 結論先行、用語定義、長さ、図の要否、次の一手 | Read / Grep / Glob |
| `product` | 要件・スコープ | 依頼一致、成功条件、スコープ、トレードオフ | Read / Grep / Glob |
| `ops` | 運用・コスト | 保守、復旧、単一障害点、費用、手間、正本の重複 | Read / Grep / Glob |
| `fact` | 根拠・事実確認 | 事実と解釈の分離、数字の出所、断定の強さ、反証 | Read / Grep / Glob |
| `devil` | 想定反論 | 費用と工数、やらない場合、代案、実行の現実性 | Read / Grep / Glob |

`ci-investigator` は **未登録**。CI 調査が必要な場面では Stop し、理由を報告する。

`bugbot` と `security-review` は **コード差分を前提**にしている。コードを含まない設計文書は `product` + `reader` + `ops` で見る（旧 `tech` / `security` の文書専用ルーブリックはこれに統合し、廃止した）。

## 役割の境界（越境させない）

同じ対象でも見る角度を分ける。重なると統合レポートに同じ指摘が二重に載る。

| 迷いやすい組 | 分け方 |
|---|---|
| `product` と `devil` | `product` は **内側から**「頼まれたことに答えているか」。`devil` は **外側から**「聞き手がどう反撃するか」 |
| `fact` と `product` | `fact` は主張の**裏づけ**。`product` は依頼との**一致** |
| `reader` と `ui` | `reader` は**文章**。`ui` は**画面**。UI 対象の `reader` は認知負荷・可読性だけを見る |
| `bugbot` と `security-review` | `bugbot` は**壊れるか**。`security-review` は**悪用できるか** |

## 隔離の仕組み

定義ファイルの `tools:` に `Write` / `Edit` を書いていないため、**子は物理的にファイルを書けない。** Cursor 時代のようにプロンプトだけで禁止しているのではない。`readonly` という引数は存在しない（[references/harness.md](references/harness.md)）。

## 優先度（全審査員に必須）

すべての審査員が、指摘に **最重要 / 高 / 中 / 低** を付けて返す。親はそれを束ねて優先度順に並べ直す。判定への効き方は [SKILL.md](SKILL.md) の統合節が正本。

## 上書きキーワード

| 発話 | 解釈 |
|------|------|
| 軽く / さっと | 1体（コード→`bugbot`、文章→`reader`、UI→`ui`、提案→`devil`） |
| フル / 全部 | hybrid-flow の PR 行（5体） |
| セキュリティだけ | `security-review` |
| バグ / 技術だけ（コード） | `bugbot` |
| トンマナだけ | `reader` |
| UIだけ | `ui` |
| 根拠 / 数字を確認 | `fact` |
| 反論 / 突っ込まれそうなところ | `devil` |
| UIも見て | `ui` 追加（5体上限で `ops` 等と入替） |

## 審査員を増やすとき

1. `agents/<ID>.md` を1本作る（既存ファイルと同じ構成：役割 → 最初に読むもの → 観点 → 判定の原則 → 優先度 → 出力フォーマット → ブロッカー例）
2. 上の一覧表に1行足す
3. [references/hybrid-flow.md](references/hybrid-flow.md) のトリアージ表に1行足す

**増やす前に、既存の誰かの観点を広げれば済まないかを確認する。** 役割が近い審査員を並べると、同じ指摘が二重に返る。
