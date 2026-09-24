# Judge Panel — 使用例（ハイブリッド）

## 例1: User Rule 更新（Panel 2人）

**ユーザー:** `judge-panel で PASTE-user-rule-tonmanna.txt をジャッジ`

- トリアージ: 文章 → `reader` + `product`（登録済み審査員 ×2）
- 全文をパケットに載せて並列 → 統合 Go / Revise

## 例2: コード変更（専用 2体）

**ユーザー:** `この差分をジャッジ`

- トリアージ: コード → **`bugbot` + `security-review`**
- 親: `Full Repository Path` + `Diff: branch changes` のみ（diff 計算は subagent）
- finding を severity で統合 → Revise / Stop

## 例3: PR 前フル（5体）

**ユーザー:** `フルジャッジして`

- **`bugbot` + `security-review` + `reader` + `product` + `ops`**
- UI 変更が主なら `ops` → `ui` に入替を提案

## 例4: Revise 後（サブセットのみ）

- 初回 Block が security-review の Critical のみ
- 修正後: **`security-review` のみ** 再実行（5体全員は呼ばない）

## 例5: UI画面（Panel 2人）

**ユーザー:** `このログイン画面をジャッジ`

- `ui` + `reader`（スクリーンショット or コンポーネント全文）
- パケットに **ui-design-principles-checklist.md 全文** を載せる（`ui` は全項目 Pass/Fail/N/A）

## 例6: CI 失敗

**ユーザー:** `PR #42 の lint が落ちた`

- `ci-investigator` → 原因特定
- コード修正が必要なら `bugbot` を追加

## 例7: 設計 ADR + 実装混在

- `bugbot` + `product` + `reader`（3体）
- 汎用エージェントでコードを見ない（コードは `bugbot` + `security-review`）
