# 図解 — アイコン（Lucide）

絵文字禁止。Lucide を **積極的に** 使う。額縁の `lucide.createIcons()` のみ。

## 最低数

提出物1枚あたり **15個以上**。

## 配置

| 場所 | アイコン例 | サイズ |
|------|-----------|--------|
| カテゴリバッジ | `terminal`, `sparkles` | w-4 h-4 |
| フロー図ノード | `user`, `folder-open`, `file-check` | w-7〜8 h-7〜8 |
| 矢印 | `arrow-right`, `arrow-down` | w-5 h-5 |
| タグピル | `code-2`, `search`, `git-compare`, `play` | w-3.5 h-3.5 |
| Why カード | `clipboard-copy`, `refresh-cw`, `hard-drive` | w-5 h-5 |
| Before/After | `x`, `check` | w-4 h-4 |
| How ステップ | 番号丸 + `arrow-down` | w-4 h-4 |
| When | `calendar`, `repeat`, `book-open` | w-5 h-5 |
| ポイント | `lightbulb` | w-4 h-4 |
| PDF | `download` | w-3.5 h-3.5 |
| セクション h2 | `target`, `list-checks`, `route`, `clock` | w-5 h-5 |

## 色

- **アクセント** — 強調1点・中央ノード・check
- **枠色（frame）** — 通常見出し・x
- 全アイコンをアクセントにしない（面積5%以内）

## 書き方

```html
<i data-lucide="folder-open" class="w-5 h-5 text-tm1-accent"></i>
```
