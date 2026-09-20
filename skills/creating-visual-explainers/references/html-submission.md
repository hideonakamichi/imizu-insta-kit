# 図解 — 提出物モード HTML

**構造** は ADS サンプル（`output/sample/`）。**色** はパターン1/2（`tm1` / `tm2`）のみ。`ads.*` 禁止。

参照: [typography.md](typography.md) / [icons.md](icons.md)

## 情報の順序

1. **バッジ + h1** — 問3の一言。導入段落（「ひとことで言うと」）は **出さない**
2. **サマリーカード** — フロー図 + タグピル
3. **Why → What → How → When** — 左線見出し
4. **Before/After** — 比較（任意だが推奨）
5. **ここがポイント** — 1枚
6. **まとめ3点** — 01/02/03
7. **出典** — 公式URL
8. **フッタークレジット** — **出さない**

## ADS 構造パーツ

| パーツ | 提出物での使い方 |
|--------|------------------|
| カテゴリバッジ | テーマに合う1語 + icon |
| サマリーカード | 一言 + 3ノードフロー + ピル |
| 左線 h2 | Why/What/How/When 各セクション |
| 3列カード | Why の理由 |
| Before/After | 会話AI vs 本体 |
| 番号ステップ | How |
| 3列数字カード | When |
| ポイント箱 | 差の核心 |
| まとめ | 3カード |

## 色の置換（ADS → tm1）

| ADS（使わない） | パターン1 |
|-----------------|-----------|
| `bg-ads-bg` | `bg-tm1-bg` |
| `bg-ads-surface` | `bg-tm1-surface` |
| `border-ads-border` | `border-tm1-frame/20` |
| `text-ads-text` | `text-tm1-text` |
| `text-ads-muted` | `text-tm1-text/70` |
| `text-ads-accent` | `text-tm1-accent` |
| `border-ads-accent` | `border-tm1-accent` |

パターン2は `tm1` → `tm2` に一括置換。

- 最大幅: `max-w-3xl md:max-w-4xl lg:max-w-5xl mx-auto px-4 md:px-8`
- 補助文: `text-tm1-muted` / `text-tm2-muted`（`text-*/70` 禁止）
- 「ひとことで言うと ──」導入
- フッターに作成ツール名やスクール名を入れる
- 比較マトリックスだけで終わる
- 段落だらだら
