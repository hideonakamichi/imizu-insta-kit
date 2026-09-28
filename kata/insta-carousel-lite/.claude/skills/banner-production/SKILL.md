---
name: banner-production
description: Instagramフィード投稿用の図解カルーセル（3〜6枚、4:5 1080x1350）を描く手順。theme-pickerが選んだ節を根拠にcarousel_spec.jsonを設計し、DESIGN.md準拠のMinimalデザインで描画して評価役の判定を通す。carousel スキルの手順3から使う。
---

# banner-production

自分の文章の1節を紹介する、Instagramフィード用の**図解カルーセル**
（表紙→中身→まとめの3〜6枚。基本は5〜6枚）を描く手順。
目的は `config/brand.yaml` の `account.purpose` の達成。**「保存される投稿」にすること**を
最優先する（保存率が伸びの鍵）。

コマンドの `PY` は Python の呼び方（Windows: `py` / Mac: `python3`）。決め方は `carousel` スキルの手順0。

## 前提

- 作業前に `config/brand.yaml` を読む（読者・トーン・オファー・パレットの参照元）
- **theme-picker が返した `source_path`（節の根拠テキスト）を全文読む。**
  画面に書く事実はその本文にあるものだけ。読まずに設計すると一般論になり中身が薄くなる
  （理由は `references/carousel-spec.md` 冒頭）
- カルーセル構成（`carousel_spec.json`）は**司令塔自身が設計する**。
  スキーマ・文字量上限・role別指針は `references/carousel-spec.md` に従う（厳守）
- デザインは `docs/DESIGN.md` のMinimal方針が絶対（3色以内・全テキスト日本語・
  1枚=1メッセージ・数字は意味とセット）。`scripts/render_slides.py` のレイアウトに
  組み込み済み（フォントサイズ・座標・線幅はすべて数値で固定）
- **画像は Pillow で決定論的に描く。画像生成AIは使わない。**
  同じ spec なら毎回同じ絵になる。書体はキットに同梱した Noto Sans JP（`assets/fonts/`）なので、
  Windows でも Mac でも同じ絵になる。見た目を変えたいときはプロンプトではなく `render_slides.py` の数値を直す
- **承認済み逸脱**: 最終スライド（summary）に限り、控えめな誘導1行（`cta`）を入れてよい。
  文言は `brand.yaml` の `offer.cta_line` を使う。`offer.enabled` が false の場合は
  `cta` を入れない。ボタン風・URL表記・煽り文言は引き続き禁止
- パレット3色は spec で**具体的hex値として固定**する（`brand.yaml` の `design.palette`）。
  これが全スライドのスタイル一貫性を担保する（AI任せにしない）

## 手順

1. **carousel_spec.json を設計する**
   - `references/carousel-spec.md` の「記事紹介として設計する」・スキーマ・テーマ軸別
     推奨構成に沿って、`source_path` の節から 5〜6枚（cover 1 + content 3〜4 + summary 1）の
     構成を設計する。節が短く3枚ぶんの固有情報が取れないときだけ content を減らす
   - 文字量上限（headline 13字・sub 20字・points 各15字×3・cta 18字）を厳守。
     超えると詰め込みになり余白が死ぬ。削れないなら content を1枚増やして分割する
   - headline に半角スペースを1つ入れると、そこで2行に割られる（例「机の上の物 3つに絞る」）。
     入れなければ1行に収まるまで縮小し、収まらないときだけ中央付近で自動改行する
   - 設計後、同ファイル末尾の「設計時のチェック」を自分で通す
   - `output/<YYYY-MM-DD>_<テーマスラッグ>/carousel_spec.json` に保存する。
     テーマスラッグは `source_path` のフォルダ名（記事スラッグ）と節番号から作る半角英数字とハイフン

2. **スライドを描画する（1コマンドで全枚）**

   ```bash
   PY .claude/skills/banner-production/scripts/banner.py --spec output/<YYYY-MM-DD>_<テーマスラッグ>/carousel_spec.json --out-dir output/<YYYY-MM-DD>_<テーマスラッグ>/
   ```

   - 全枚で数秒。APIもサインインも不要（Claude の利用量もかからない）
   - 出力は `slide_<n>_<role>_<ts>.png`（4:5、1080x1350）と `.layout.json`（描画パラメータ）
   - スクリプトが spec の構造検証・文字量チェックを行う。警告が出たら spec を見直す
   - 特定スライドだけ描き直すときは `--only-slide <番号>`（spec を直したあとに使う）

3. **evaluatorに評価を依頼する**
   - 生成した**全スライドの `.png`** と `carousel_spec.json`、**`source_path`** を
     evaluator サブエージェントに渡し（モデルは `config/runtime.yaml` の `models.evaluator`）、
     スライド単位＋カルーセル全体＋ネタ元との照合の合否を得る
   - **不合格の場合**: 描画は決定論的なので、**同じ spec を描き直しても結果は変わらない**。
     不合格理由は必ず spec（文言・構成・煽り・NGワード）か、レイアウトの数値のどちらかに
     ある。spec の問題なら spec を直して該当スライドを描き直す:

     ```bash
     PY .claude/skills/banner-production/scripts/banner.py --spec ... --out-dir ... --only-slide <不合格スライド番号>
     ```

     レイアウトの問題（文字が大きすぎる・余白が足りない等）なら、spec ではなく
     `render_slides.py` の数値の問題なので、その場で直さずに止めて人に報告する
   - 再描画後、そのスライドと前後のスライド（一貫性確認のため）を evaluator に再提出する
   - 上限は `config/loop-limits.yaml` の `carousel_slide_regeneration`（スライドごと最大2回）。
     2回で合格しない場合は止めて、不合格の理由を人に伝える

4. **採用スライドを確定する**
   - 各スライド番号につき**最新の合格 `.png` 1枚**を採用する（同番号で複数世代ある場合は
     タイムスタンプ最新の合格版）
   - 不採用版・`.layout.json` は `output/` 配下にそのまま残す（あとで見返せる）
   - 採用スライドのパスを**表示順に**並べて、`carousel` スキルの手順4へ進む

## 出力

- `output/<YYYY-MM-DD>_<テーマスラッグ>/carousel_spec.json`（構成設計書）
- `output/<YYYY-MM-DD>_<テーマスラッグ>/slide_<n>_<role>_<ts>.png`（4:5、1080x1350）
- 同ディレクトリに `.layout.json`（描画パラメータ。投稿には使わない）

---

## 単発1枚バナー（通常は使わない）

カルーセルが不要な特殊ケース（告知1枚もの等）では、単発モードを使える:

```bash
PY .claude/skills/banner-production/scripts/banner.py --headline "<見出し>" --sub "<サブテキスト>" --out-dir output/<YYYY-MM-DD>_<テーマスラッグ>/
```

表紙スライドと同じレイアウトで1枚描く（パレットは `brand.yaml` の `design.palette`）。
evaluator評価（`banner_evaluation`: 最大2回）のあと、投稿用フォルダには `01.png` として置く。
