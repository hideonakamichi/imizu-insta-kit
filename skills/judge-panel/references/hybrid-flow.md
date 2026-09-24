# ハイブリッド・ジャッジ — サブエージェント正本

judge-panel の審査員は **すべて `agents/` に登録済みのサブエージェント**。`subagent_type` に ID をそのまま指定して起動する。定義の正本は `~/.claude/agents/<ID>.md`。

## サブエージェント一覧（役割分担）

| `subagent_type` | 得意領域 | 材料 |
|-----------------|----------|-----------|
| `bugbot` | バグ・ロジック・型・回帰 | リポパス + Diff 種別（**diff は子が取得**） |
| `security-review` | 秘密情報・権限・注入・依存 | 同上 |
| `ui` | 画面の階層・状態・A11y・操作性 | 対象の全文またはパス（**チェックリストは子が読む**） |
| `reader` | 文章の結論先行・用語・トンマナ | 対象の全文またはパス |
| `product` | 依頼一致・スコープ・トレードオフ | 対象 + **ユーザーの依頼の要約** |
| `ops` | 保守・復旧・費用・単一障害点 | 対象 + 運用体制が分かるもの |
| `fact` | 主張の裏づけ・数字の出所 | 対象の全文（**外部調査はしない**） |
| `devil` | 想定反論・想定問答 | 対象 + **想定する聞き手** |
| `ci-investigator` | CI チェック失敗の原因 | **未登録。** 無いので該当時は Stop |

**原則:** 実行可能な **コード差分** があるときは、必ず `bugbot` + `security-review` を使う。汎用エージェント単独でコードを見ない。

---

## トリアージ（デフォルト）

| 対象 | 並列起動（最大5） |
|------|-------------------|
| **コード変更・実装** | `bugbot` + `security-review` |
| **トンマナ・文章・Canvas・スライド設計** | `reader` + `product` |
| **提案文・セミナー資料・報告** | `fact` + `devil` |
| **プレゼン原稿・発表資料** | `devil` + `reader` |
| **UI画面・コンポーネント** | `ui` + `reader` |
| **設計・ADR（コード混在）** | `bugbot` + `product` + `reader` |
| **設計・ADR（文書のみ）** | `product` + `reader` + `ops` |
| **PR / リリース相当** | `bugbot` + `security-review` + `reader` + `product` + `ops` |
| **提案フルジャッジ** | `fact` + `devil` + `reader` + `product` + `ops` |
| **PR CI 失敗調査** | `ci-investigator` が未登録のため **Stop**（理由を報告） |
| **ユーザー「フルジャッジ」** | 対象に応じ PR 行 または 提案フル行（UI 主体なら `ui` を `ops` と入替） |

### 上書きキーワード

| 発話 | 解釈 |
|------|------|
| セキュリティだけ | `security-review` のみ |
| バグだけ / 技術だけ（コード） | `bugbot` のみ |
| トンマナだけ | `reader` のみ |
| UIだけ | `ui` のみ |
| 根拠 / 数字を確認 | `fact` のみ |
| 反論 / 突っ込まれそうなところ | `devil` のみ |
| CI / チェック落ち | `ci-investigator` は未登録 → Stop |
| 軽く / さっと | 対象に応じ 1〜2（コードなら bugbot のみ等） |

---

## 専用 subagent の起動（親の責務）

### Bugbot / Security Review

審査基準の正本 → `agents/bugbot.md` / `agents/security-review.md`。

```text
Full Repository Path: <absolute path>
Diff: branch changes | uncommitted changes
Base Branch: <必要時のみ>
Custom Instructions: <ユーザー指定時のみ>
```

- **親は diff を事前計算しない**（subagent が取得）
- `run_in_background: false`（明示がなければ）
- `description`: `"Bugbot"` / `"Security Review"`
- 隔離・失敗時の劣化 → [harness.md](harness.md)
- `bugbot` が無い環境ではコード・ジャッジを Stop する（代替審査員でごまかさない）

### CI Investigator（未登録）

`ci-investigator` は `agents/` に定義がない。CI 調査を求められたら **Stop** し、「専用審査員が未登録である」ことを理由として報告する。代替の審査員でごまかさない。

### Panel 審査員（`ui` / `reader` / `product` / `ops` / `fact` / `devil`）

[../SKILL.md](../SKILL.md) の共有パケット。prompt 先頭: `[judge:REVIEW-ONLY:<ID>]`

- 文章・設計書は **全文 or ファイルパス＋行範囲** を必ず載せる
- 500行超は diff / 抜粋 + パス
- **チェックリストは親が貼らない。** `ui` は UI Design Principles を、`reader` は図解のときスタバ図解チェックリストを、それぞれ子が自分で Read する（定義ファイルに絶対パスがある）
- **`devil` 起動時のみ:** 想定する聞き手（決裁者 / 現場 / 同僚）をパケットに書く

---

## 出力の統合マッピング

すべての審査員が **最重要 / 高 / 中 / 低** を付けて返すので、親はそのまま優先度順に並べる。外部ツール由来の severity 表記が混ざった場合だけ、次のように読み替える。

| finding severity | 優先度 |
|------------------|--------------|
| Critical / High | **最重要** |
| Medium | **高** |
| Low | **中** |
| Info | **低** |

判定は **最重要が1件でもあれば Stop、無くて高があれば Revise、どちらも無ければ Go**（正本は [../SKILL.md](../SKILL.md) の統合節）。

審査員別サマリ表:

| 審査員 | 判定寄与 | 最重要指摘 |
|--------|----------|------------|
| bugbot | Approve / Revise / Block | 最も優先度の高い指摘1行 |
| security-review | 同上 | 同上 |
| reader / product / ops / ui / fact / devil | 同上 | 同上 |

---

## 再ジャッジ（最大1回）

| 初回ブロッカー | 再実行 |
|----------------|--------|
| bugbot のみ | `bugbot` のみ |
| security-review のみ | `security-review` のみ |
| reader + product | 同じサブセット |
| 複合 | **失敗した subagent / 審査員だけ** |

---

## 禁止

| NG | 代替 |
|----|------|
| コード差分を汎用エージェントだけで見る | `bugbot` + `security-review` |
| 親が diff を要約だけ渡して bugbot を呼ぶ | Full Repository Path + Diff 指定 |
| Explore / Bash でレビュー丸投げ | 登録済みの審査員を使う |
| 6体以上同時起動 | 優先度で5に絞る。通常は1〜2 |
| チェックリスト全文を親がパケットに貼る | 子が自分で Read する（正本の二重化を避ける） |
| 優先度なしで指摘を並べる | 全指摘に最重要 / 高 / 中 / 低 を付ける |
| `Agent` に `readonly: true` を渡す | その引数は無い。隔離は定義ファイルの `tools:` |
| `AskUserQuestion` / `Agent` が無いのに必須扱いして止まる | harness.md の代替1段。無ければ Stop |
