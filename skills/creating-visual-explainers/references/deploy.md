# 図解 — 公開（任意）

問1が **要** のとき、またはユーザーが「SURGEして」と明示したときだけ実行する。

失敗したら **ローカル HTML だけで完了** する。スキルを止めない。

## 手順

1. `node --version` が失敗したら [node-install-guide.md](node-install-guide.md) を案内し、ローカルで終える
2. 公開するファイルは **案件の `output/{slug}.html`**（スキル内パスではない）
3. **Surge はフォルダ単位。** HTML ファイルを直指定すると `ENOTDIR` で失敗する。必ずスクリプトを使う

**Windows:**

```powershell
powershell -File "$env:USERPROFILE\.claude\skills\creating-visual-explainers\scripts\deploy-diagram.ps1" -HtmlFile "{案件のhtmlの絶対パス}" -Slug "{slug}"
```

**macOS / Git Bash:**

```bash
bash ~/.claude/skills/creating-visual-explainers/scripts/deploy-diagram.sh "{htmlパス}" {slug}
```

ドメインが使えないときは、日付入りなど別ドメインを1回だけ試す。それでも失敗したらローカルで終える。

## 削除

ユーザーが明示したときだけ `npx surge teardown {ドメイン}`。
