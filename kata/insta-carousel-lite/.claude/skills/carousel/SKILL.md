---
name: carousel
description: Instagram 用の図解カルーセルを1本作る。ネタ選び→構成→描画→評価→キャプション→評価→投稿用フォルダの用意と履歴の記録までを行い、投稿は人に渡す。「カルーセル作って」「投稿を1本作って」「カルーセルを作成」と頼まれたとき、または /carousel で使う。「このネタで」と節を指定されたら、ネタ選びを飛ばしてそれを使う。
---

# carousel — カルーセルを1本作る（Lite 版の入口）

あなた（このセッション）が**司令塔（進行役）**になる。自分では評価しない。ネタ選び・キャプション・評価は
サブエージェントに任せ、流れの分岐（合格／不合格／中止）を判断する。カルーセルの構成（spec）の
設計だけは自分で行う（`banner-production` の決まり）。

**ゴール:** 評価役の合格を通ったスライドとキャプションを、投稿用フォルダにそろえて人に渡す。
Instagram への投稿は人がスマホから行う。**どこかで通らなければ、投稿用フォルダを作らずに止めて理由を伝える。**

## 0. 準備（毎回）

1. `config/runtime.yaml` を読む
2. **Python の呼び方（以下 `PY`）を決める。** `python_command` が空でなければそれを使う。空なら `os` で決める:
   - `windows` → `py`
   - `mac` → `python3`
   - `auto` → いま動いている OS（Claude Code の環境情報の Platform。`win32` なら Windows、`darwin` なら Mac）に合わせる
3. **サブエージェントのモデルを決める。** `models.theme_picker` / `models.caption_writer` / `models.evaluator` の値を、
   サブエージェントを呼ぶときの `model` に**毎回そのまま渡す**。値が opus / sonnet / haiku 以外なら、
   各定義ファイルの既定（theme-picker・caption-writer は sonnet、evaluator は opus）を使い、そのことを最後に報告する
4. 以降のコマンドはすべて **Bash ツール**で、`PY .claude/skills/...` の**相対パス**のまま、フォアグラウンドで実行する
   （`.claude/settings.json` の許可はこの形で登録してある。Windows でも PowerShell ツールは使わない。
   スクリプトは出力を UTF-8 で書くので、PowerShell では日本語が化けてエラーの中身が読めなくなる）

## 1. 設定とネタの確認

```bash
PY .claude/skills/shared/scripts/check_brand.py
```

失敗したら、ここで止める。「brand-setup スキルで設定して」と頼めば対話で埋められることを伝える。

```bash
PY .claude/skills/shared/scripts/build_article_index.py
```

失敗したら止め、エラーの内容を伝える（ネタ元の書式は `content/sources/README.md`）。

## 2. ネタを選ぶ

- 人が「このネタで」と節を指定していれば、`content/articles/index.json` からその節を探して使う
  （`theme` と `source_path` を index.json から一字一句そのまま取る）
- 指定が無ければ `theme-picker` サブエージェントを呼ぶ。返ってきた `source_path` を自分でも全文読む
- 「ネタの索引がありません」が返ったら止める

## 3. カルーセルを作って評価する

`.claude/skills/banner-production/SKILL.md` の手順1〜4に従う。
出力先は `output/<YYYY-MM-DD>_<テーマスラッグ>/`。評価役を呼ぶときは**毎回 `source_path` を渡す**。

上限は `config/loop-limits.yaml` の `carousel_slide_regeneration`（スライドごと2回）。
2回で通らなければ止め、不合格の理由を伝える。

## 4. キャプションを作って評価する

`caption-writer` サブエージェントに、採用スライドのパス（表示順）・`carousel_spec.json`・**`source_path`** を渡し、
`output/<フォルダ>/caption.txt` に書かせる。続けて `evaluator` にキャプションと `source_path` を渡して判定する。
上限は `caption_evaluation`（2回）。

## 5. 投稿用フォルダをそろえて記録する

1. 投稿用フォルダをそろえる。採用スライドが表示順に `01.png` `02.png` … としてコピーされ、`caption.txt` も添えられる
   （同じ番号が何枚かあれば、いちばん新しい＝最後に合格したものが使われる）:

   ```bash
   PY .claude/skills/shared/scripts/make_post_folder.py --out-dir "output/<フォルダ>"
   ```

2. 履歴に記録する（`--theme` は theme-picker の `theme` を一字一句そのまま）:

   ```bash
   PY .claude/skills/shared/scripts/record_history.py add --theme "<theme>" --out-dir "output/<フォルダ>/post" --slides <枚数>
   ```

## 6. 人に渡す

次の順で短く伝える。

- 投稿用フォルダの場所（`output/<フォルダ>/post/`）と枚数
- キャプションの冒頭2文とハッシュタグの数
- 投稿のしかた: スマホの Instagram で「新しい投稿」→ 画像を `01` から順に選ぶ → `caption.txt` の中身を貼る
  （PC からスマホへの送り方は `docs/SETUP-GUIDE.md` の「スマホへの送り方」）
- 没にするなら「これは没」と言えば履歴から外す、と一言

「これは没」「投稿しなかった」と言われたら、次を実行して結果を伝える:

```bash
PY .claude/skills/shared/scripts/record_history.py cancel --theme "<theme>"
```

## 守ること

- **画面とキャプションに書く事実は、`source_path` の節の本文にあるものだけ。** 自分の知識で補わない
- `config/brand.yaml` の `tone.policy` は安全弁。司令塔が勝手に緩めない
- `config/loop-limits.yaml` の上限を勝手に緩めない
- 止めるときは、どの段階で・何が通らなかったか・生成物がどこに残っているかを伝える。
  評価で不合格になった生成物も `output/` にそのまま残す（人が手で直せる）
- 権限で止められたら、形を変えての再試行は1回まで。それでも止まったら、止まったコマンドを人に伝える
