# 追加パック（addons）

Lite 版で外した機能を、フル版（insta-autopost-kit）のファイルのまま置いています。

| パック | できること | 要るもの | 月の費用の目安（フル版の実績） |
|---|---|---|---|
| `auto-post/` | Instagram への自動投稿 | Meta for Developers・Cloudflare R2・Discord | R2 は投稿のたびに消すのでほぼゼロ |
| `reel/` | 縦型動画（リール）の生成 | Grok（SuperGrok か X Premium+）・Fish Audio・ffmpeg | Grok のサブスク＋Fish Audio の従量。リール1回の Claude 利用量は平均 $3.8〜6.3 |
| `schedule/` | 決まった時刻の自動実行・週次点検 | 常時起動の Mac（launchd） | ― |
| `_original/` | フル版の README・CLAUDE.md・SETUP-GUIDE・設定ファイル | ― | ― |

## いまの状態（足す前に読んでください）

- **どれもまだ Mac 専用です。** シェルスクリプト・launchd・`fcntl`（Mac と Linux にしかない部品）・ヒラギノ書体を前提にしています
- **Lite 版の本体とは、まだつながっていません。** たとえば自動投稿は投稿履歴を `logs/posted.jsonl` に書きますが、
  Lite 版の作成履歴は `logs/history.jsonl` です。そのまま混ぜると、ネタの重複防止が効きません
- そのため、いま自動投稿やリールを使いたいときは、**フル版の insta-autopost-kit をそのまま使うのが確実です。**
  手順はフル版の文書（`_original/README.md` と `_original/SETUP-GUIDE.md`）にあります

Lite 版に組み込み直す作業（Windows 対応と、履歴の統一）は、本体を運用してから順に進める予定です。
