---
name: publish-toolkit
description: Publish専門スキル。lp-publisher サブエージェントが呼ぶ実行手順。lp-designer が作った LP（_sections.json＋セクション画像）を静的サイト（index.html + assets/）に組み立て、Vercel にデプロイして公開URLを発行する。「LPを公開」「Vercelにデプロイ」「LPのURLを発行」など、LP公開の実コマンドが必要なときに参照する。
allowed-tools: Bash(.venv/bin/python *), Read, Write, Edit, Glob, Grep
---

# publish-toolkit — ステージ5: LP静的サイト化＋Vercelデプロイ

lp-designer の成果物（`_sections.json`＋セクション画像）から公開可能な静的LPを組み立て、
Vercel にデプロイして URL を発行する。

設計の*理由*は [../../../design.md](../../../design.md) を参照。

## 前提（最初に必ず確認）

- **作業ディレクトリ**: コマンドは `creative-pipeline-orchestrated/`（プロジェクト直下）からの相対パス。
- **Python**: `.venv/bin/python`
- **Vercel認証**: `.env` の `VERCEL_TOKEN`、または `vercel login` 済みであること。Node.js（npx）必須。
- **スクリプト**: このスキル内 `.claude/skills/publish-toolkit/scripts/publish.py`
- **入力**: `data/<クエリ>/lp/<lp_id>_sections.json` と `data/<クエリ>/lp/images/<lp_id>/` の各セクション画像
  （各セクションの**最新タイムスタンプのPNG**が自動採用される）

```
.venv/bin/python                                   # = PY
.claude/skills/publish-toolkit/scripts             # = S
```

---

## 手順

1. **ビルドのみ（まず必ずこれ）**: 静的サイトを生成し、Readで index.html を目視確認する。

```bash
$PY $S/publish.py --json "data/<クエリ>/lp/<lp_id>_sections.json"
```

2. **デプロイ**: 目視確認が済んだらプレビューデプロイ → 問題なければ `--prod`。

```bash
# プレビューデプロイ（確認用URL）
$PY $S/publish.py --json "data/<クエリ>/lp/<lp_id>_sections.json" --deploy

# 本番デプロイ＋CTAリンク指定
$PY $S/publish.py --json "data/<クエリ>/lp/<lp_id>_sections.json" --deploy --prod --cta-url "https://example.com/apply"
```

主なオプション:
- `--cta-url`: 追従CTAボタンのリンク先（LINE友だち追加・申込フォーム等）。未指定なら環境変数 `CTA_URL`、それも無ければ `#`
- `--accent`: CTAボタンの色（既定はチャコール `#34352f`。LPのトーンに合わせて変更可）
- `--deploy` / `--prod`: デプロイ実行／本番昇格

出力:
- サイト: `data/<クエリ>/lp/site/<lp-id>/`（index.html + assets/）
- 公開URL: 標準出力と `site/<lp-id>/deploy_url.txt`

> **公開注意**: デプロイは外部公開になる。**必ずビルド→目視→プレビューデプロイ→ユーザー確認→本番**の順。
> いきなり `--prod` で回さない。生成LPには `noindex` が入っている（検証用途のため）。

## 呼び出し元への返却

公開が終わったら、次を呼び出し元（orchestrator）に返す:
- サイトディレクトリのパスと目視確認の結果
- 公開URL（deploy_url.txt の中身）

## トラブルシュート

- `デプロイ失敗` → `.env` に `VERCEL_TOKEN` を記入するか `npx vercel login`。Node.js が無ければインストール
- `セクション画像が1枚もありません` → 先に lp-toolkit（lp_image.py）で画像を生成する
- CTAが `#` のまま → `--cta-url` を渡す（本番前に必ず実リンクへ差し替える）
