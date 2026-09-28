---
name: reel-realistic-orchestrator
description: リール投稿パイプライン（realistic スタイル固定）の司令塔。手順は reel-orchestrator と同一で、映像スタイルと顔チェックの強度だけが異なる
timeout_sec: 3600
model: opus
expects_post: true
---

# リール投稿オーケストレーター（realistic 版）

**`.claude/orchestrators/reel-orchestrator.md` を読み、そこに書かれたミッション・実行手順・
厳守事項に全面的に従う。** 手順を重複して持たないための薄い変種であり、
下に書いた差分だけが本家と異なる。

## 本家との差分（これだけ）

### 映像スタイルは `realistic` に固定する

`reel-script-writer` を呼ぶとき、**映像スタイルは `realistic` であると明示的に指定する**。
`config/brand.yaml` の `design.reel_style` は `bin/run_reel.sh` の既定値なので、
この実行では参照せず、上書きする。

`video-prompt-spec.md` の realistic 用スタイルロックを使う。
`generate_video.py --lint-only` が realistic 必須文（`People may appear ONLY as hands and
forearms ...` と明朝禁止）の有無を検査するので、欠けていれば lint が止める。

### 顔チェックの強化は本家に書いてある

評価用フレームの0.5秒間隔の抽出と、顔が1フレームでも写っていたら引き直さずに中止する決まりは、
`reel-orchestrator.md` の「映像スタイルが realistic のとき」にある。この実行は realistic なので**必ず適用する**。
（入口ごとに書くと、`brand.yaml` で realistic を選んで `bin/run_reel.sh` から起動した場合に
強化が効かなくなる。だから本家の側に、映像スタイルを条件にして置いてある）
