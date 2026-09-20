# 入出力契約（アプリ化の正本候補）

スキルと将来アプリで共有する契約。変更したら `SKILL.md` の「入出力契約」表と矛盾がないか確認する。

## 入力

| フィールド | 必須 | 説明 |
|---|---|---|
| `scriptMarkdown` | Yes | `writing-presentations` 形式の読み上げ原稿（①〜⑥見出し） |
| `proposalMarkdown` | No | 提案の提出用完成稿（参照用。スライドの正にはしない） |
| `audience` | No | 聞き手（例: 直属の上司） |
| `durationMinutes` | No | 尺（分） |
| `locale` | No | 既定 `ja-JP` |

入力にない体験・数字を補完してよいのはユーザー確認後のみ。

## 出力: deck JSON

```json
{
  "version": "0.1",
  "meta": {
    "title": "string",
    "audience": "string | null",
    "durationMinutes": 10,
    "source": "writing-presentations",
    "locale": "ja-JP"
  },
  "slides": [
    {
      "id": "s1",
      "order": 1,
      "role": "hook | conclusion | why | how | outcome | ask | risk",
      "title": "画面見出し（短い）",
      "message": "この1枚で伝えること（1文）",
      "bullets": ["画面に載せる短い箇条"],
      "speakOnly": ["載せない・口頭のみ"],
      "speakerNotes": "話し手用。原稿の要約。創作しない",
      "sourceSteps": ["①", "②"]
    }
  ]
}
```

### role の意味

| role | 対応しがちな原稿 |
|---|---|
| `hook` | ① |
| `conclusion` | ② |
| `why` | ③ |
| `how` | ④ |
| `outcome` | ⑤ |
| `risk` | ⑥の懸念先出し |
| `ask` | ⑥のお願い（Yes/No） |

## 出力: 人が読む Markdown

JSON と同じ枚・同じ文言を、`SKILL.md` の「Slide N」テンプレで書く。どちらか一方だけ更新して食い違わせない。

## 出力: Gemini プロンプト（C）

Step 4b で必ず出力。詳細 → [gemini-slides-prompt.md](gemini-slides-prompt.md)

| フィールド | 説明 |
|---|---|
| `promptMarkdown` | 使い方3行 ＋ fenced code 内のプロンプト全文 |
| `attachmentHint` | 添付する設計図ファイル名（例: `スライド設計_◯◯.md`） |
| `deckTitle` | `deck.meta.title` と一致 |
| `slideCount` | `deck.slides.length` と一致 |

プロンプト内の枚一覧・枚数は **deck JSON から導出** し、Markdown 設計図と矛盾させない。

## 非ゴール（v0）

- PPTX / Google Slides バイナリの必須生成
- Gemini 出力を正本として設計図を後追い修正すること
- アニメーション・高度なデザインシステム
- 原稿にない社内データの自動取得
