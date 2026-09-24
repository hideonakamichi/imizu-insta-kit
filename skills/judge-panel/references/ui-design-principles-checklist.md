# UI Design Principles — ジャッジ用チェックリスト

**SSoT（正本）:** `USERS RULE/user-rules/user-rule-ui-design-principles.md`  
**この一覧が正本。** 他のファイルを見にいく必要はない。

Panel 審査員（`ui` / UI 対象の `reader`）起動時、親が共有パケットに **全文または本ファイル** を載せる。  
`ui` 審査員は各項目を **Pass / Fail / N/A** で判定し、Fail は「悪い点・リスク」に必ず書く。

---

## 1. Cognitive Clarity（認知の明瞭性）

| 原則 | レビュー観点 |
|------|-------------|
| Hick's Law | Primary CTA が1画面1つか。副次は Secondary / テキストリンクか |
| Miller's Law | 一覧・メニューが3〜7項目の塊か。超過時にグループ化・段階開示があるか |
| Visual Hierarchy | h1 が1ページ1つか。サイズ・ウェイト・余白で優先順位が付いているか |

## 2. Interaction & Usability（操作性）

| 原則 | レビュー観点 |
|------|-------------|
| Fitts's Law | 主要ボタン min 44×44px 相当か。モバイルで親指圏に置けるか |
| Recognition over Recall | 履歴・「続きから」・選択肢の可視化で記憶に頼らせていないか |
| Flexibility | 初期導線がシンプルか。上級ショートカットが主タスクを阻害しないか |

## 3. System Behavior（システムの振る舞い）

| 原則 | レビュー観点 |
|------|-------------|
| System Status | Loading / Success / Error / Empty が示されるか |
| User Control | 破壊的操作に確認があるか。Cancel / Undo の脱出口があるか |
| 入力の寛容性 | trim・正規化・自動補完等で入力負荷を下げているか |

## 4. Aesthetic & Mental Model（直感と美学）

| 原則 | レビュー観点 |
|------|-------------|
| Mental Model | 既知の比喩（フォルダ等）に沿うか。独自記号だけの UI でないか |
| Consistency | フォント・ボタン・挙動・アイコン意味が一貫しているか |
| Aesthetic-Usability Effect | 余白が確保され、装飾より可読性・操作性が優先されているか |

## 5. Accessibility & States（A11y・状態）

| 観点 | レビュー基準 |
|------|-------------|
| キーボード / フォーカス | 操作可能、`:focus-visible` が消えていないか |
| フォーム | ラベル必須、エラーが原因＋直し方か |
| 状態 | Default / Hover / Focus / Disabled / Loading / Error が定義されているか |
| 多様性 | コントラスト・タッチ領域 OK、色だけに依存していないか |

## 実装チェックリスト（5項目 — ui 審査員は全項目必須）

- [ ] Primary CTA が1画面1つ
- [ ] 主要ボタン 44px 以上・Loading/Error/Empty あり
- [ ] 破壊的操作に確認・Cancel/Undo あり
- [ ] フォームにラベルと具体的エラー文
- [ ] 図解（creating-visual-explainers）と役割分担 OK

**優先:** 図解の配色・フォントは `creating-visual-explainers` の `references/base.html` が基準。衝突時は **認知負荷の軽減** を最優先。
