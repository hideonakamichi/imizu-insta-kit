---
name: support-article-reviewer
description: ひとり親支援制度 (supports テーブル) の article_md を 32 項目チェックリスト + check_article (Python) で査読する詳細手順。research_notes 事前検証、引用照合、フォーマット自動検出 (E01〜E24)、役所語の検出 (15g/E20・藤井の解説は対象外)、危険語の検出 (15k/E24・★藤井の解説も対象★)、制度タイプ別の必須項目 (15j/E23)、article_title の型と summary の平易さ (15h/15i・E21/E22)、図解画像の目視確認 (10c/E15)、reviewer_verifications の追記、curl レンダリングチェックを含む。レビュアー (support-reviewer) 専用。
user-invocable: false
---

# ひとり親支援記事レビュー手順 (レビュアー専用)

ライター (`support-writer`) が生成したひとり親支援記事 (article_md) の品質を検証し、問題があれば修正して DB に再保存する。

## 役割

公開前の最後の砦。ライター自身のチェックでは主観的な盲点がある。レビュアーは**第三者の査読者として、客観的に全文チェック**する。

> ★なぜ書き手と査読者を分けるか★
> 1 体に「書いて、自分でチェックして」と頼んでも、**自分の誤りには気づけない**。
> 書いたときの前提をそのまま持ったまま読み直すので、同じ思い込みが素通りする。
> レビュアーには**記事本文とチェックリストだけ**を渡し、ライターがどう考えたかは渡さない。

## ★最初に読むもの: 登場人物と口調の設定ファイル★

**査読を始める前に、必ず `config/persona.json` を Read すること。**
（無ければ `config/persona.example.json` を読む）

このファイルに**質問役 (`questioner`) と解説役 (`explainer`) の名前・立場・使ってよい語彙**が定義されている。
以下のチェックリストで「質問役」「解説役」と書いてある箇所は、この設定ファイルの人物に読み替える。
**この SKILL に出てくる名前をハードコードして判定しないこと。**

`check_article()` も同じファイルを読むので（`load_persona_names()`）、キャラを差し替えても機械検出はそのまま動く。

## Mission

| 項目 | 内容 |
|---|---|
| 目的 | ひとり親支援記事の品質を保証し、フォーマット違反・事実誤認・情報不足を検出・修正する |
| KPI | レビュー通過率、修正件数、差し戻し件数 |
| 責任 | ライターが書いた記事を検証し、公開品質に引き上げる |

### 制約 (絶対遵守)

- **ハルシネーション禁止**: 存在しない URL や ID を記事に追加しない
- **公式ソースと照合**: 金額・所得制限・期限等は公式サイトで確認
- **過剰修正しない**: フォーマット違反と事実誤認のみ修正。文体・トンマナは尊重する
- **読者はひとり親**: 誤った金額・要件は読者の生活設計を直接誤らせる。金額系の検証は特に厳格に

## 入力

支援制度 ID (supports テーブル) を受け取り、DB から article_md + research_notes を読み込む:

```bash
bash scripts/supabase-query.sh select supports "id=eq.{ID}&select=id,title,summary,article_md,article_title,research_notes,category,amount_max,amount_note,support_rate,application_start,application_end,status"
```

※ `summary` も査読対象 (トップのカード説明文 + meta description になる)。`check_article` に `summary` / `article_title` / `official_names` / `category` を渡さないと E20〜E24 が動かない:

```bash
# official_names = 全制度の正式名称 (E20 で「崩してはいけない語」を伏せるのに使う)
bash scripts/supabase-query.sh select supports "select=title" | jq -r '.[].title'
```

※ research_notes が null の場合は「出典未記録」として無条件で差し戻し

## 査読プロセス

```
1. DB からデータ読み込み (article_md + メタデータ + research_notes)
2. research_notes 事前検証 (NULL/不足なら即差し戻し、コンテンツ査読に進まない)
3. 32 項目のチェックリスト全確認
4. ファクトチェック (記事中の数字・固有名詞を research_notes の quote と照合)
5. 1 つでも NG があれば差し戻し or 修正
   - 自分で直せるもの (フォーマット系: 全角コロン、AI 臭フレーズ等) → 修正して DB 再保存
   - 自分で直せないもの (話者逆転、ファクトチェック失敗、構造的欠落、出典不足等) → 差し戻し
   - 差し戻し時は具体的な行番号と修正方法を指示
6. 全項目 OK なら reviewer_verifications を research_notes に追記して公開承認
```

## research_notes 参照・検証 (★必須★)

ライターが DB 投入時に記録した `research_notes` を使ってファクトチェックする。これを飛ばすと「記事の支給額・所得制限・期限が正しいか」判定不能。

### 事前検証 (コンテンツ査読より先に実施)

以下のいずれかに該当したら **即差し戻し**:

1. `research_notes` が NULL
2. `research_notes.sources` が空 / 3 件未満
3. 公式 URL (`.go.jp` / `pref.*.jp` / `city.*.jp` / `cfa.go.jp` / `nta.go.jp` / `nenkin.go.jp` 等) が sources に 1 つもない
4. 記事中に金額・所得制限・期限を記載しているが対応する quote が research_notes に存在しない

差し戻しメッセージ例:
「ライターへ: research_notes.sources が {N} 件しかない。こども家庭庁 / 自治体公式 URL を最低 3 件記録してから再投入。」

### ファクトチェック (引用照合)

article_md 中の以下を全て抽出し、research_notes.sources[*].quotes と照合:

- **支給額・貸付額** (上限・下限、月額/年額の別)
- **給付率** (受講費用の60% 等)
- **所得制限** (扶養人数別の限度額)
- **対象者要件** (子どもの年齢、婚姻歴の扱い等)
- **申請窓口** (機関名)

対応 quote がない → 該当箇所の**削除または quote 追加を指示**。

### 検証履歴の追記 (合格時に必ず実行)

```json
{
  "reviewer": "support-reviewer",
  "verified_at": "2026-07-21T11:00:00Z",
  "checks": [
    { "claim": "月額 48,040円 (令和8年度・全部支給)", "source_url": "https://...", "verdict": "confirmed" },
    { "claim": "支払は年6回 (奇数月)", "source_url": "https://...", "verdict": "confirmed" }
  ],
  "overall_verdict": "approved"
}
```

書き込み手順 (supports テーブル用):

```bash
EXISTING=$(bash scripts/supabase-query.sh select supports "id=eq.{id}&select=research_notes" | jq '.[0].research_notes')
UPDATED=$(echo "$EXISTING" | jq --argjson v '{"reviewer":"support-reviewer","verified_at":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","checks":[...],"overall_verdict":"approved"}' \
  '.reviewer_verifications = ((.reviewer_verifications // []) + [$v])')
PAYLOAD=$(jq -n --argjson notes "$UPDATED" '{research_notes: $notes}')
bash scripts/supabase-query.sh update supports "$PAYLOAD" "id=eq.{id}"
```

## チェックリスト (32 項目)

### A. 話者・吹き出し (5 項目)

- [ ] **1.** 記事が**質問役 (`questioner`) の発言**で始まっているか
- [ ] **2.** 質問役=聞く側、解説役 (`explainer`)=答える側が守られているか (解説役の「？」が質問役より多ければ NG)
- [ ] **3.** 吹き出し外の地の文がないか (H2/テーブル/ディレクティブ/画像/コメント以外)
- [ ] **4.** 吹き出し内にリスト (`- ` `1. `) がないか
- [ ] **5.** `**太字**:` が話者以外で使われていないか

### B. 記法・フォーマット (6 項目)

- [ ] **6.** 全角コロン `：` が使われていないか (半角 `:` のみ)
- [ ] **7.** 時刻が `HH時MM分` 形式か (`HH:MM` は NG)
- [ ] **8.** `<mark>` タグが 1 行内で閉じているか
- [ ] **9.** :::ディレクティブの開閉数が一致しているか
- [ ] **10.** FAQ_JSON が `<!-- FAQ_JSON [...] -->` 形式で末尾にあるか (` ```json ` は NG)
- [ ] **10b.** **図解画像が 2 枚以上埋め込まれているか** (`![...](https://.../article-images/...)` パターンを `grep -c` で 2 以上、かつ H2 見出しの直後に配置)。不足時は無条件で差し戻し
- [ ] **10c.** ★**図解画像の「中身」を実際にダウンロードして Read ツールで目視し、記事の制度と一致しているか確認したか**★ — URL が HTTP 200 なだけでは全く不十分。E14 (配信チェック) を通っても中身が別制度ということが実際に起きている
  - 確認手順: `curl -s -o /tmp/img-{n}.png "$URL"` で全画像を落とし、**1 枚ずつ Read ツールで開いて目視する**
  - 確認項目:
    - ① **画像内のタイトル・ラベルがその記事の制度名と一致しているか** (alt テキストが正しくても画像内が誤っていることがある。実例: 児童扶養手当の記事に「令和8年度 認可保育園 保育料」というタイトルの画像、児童育成手当の記事にゴールドカード比較広告、都営住宅の記事に「黄色について #FACC15」の色見本)
    - ② 金額・数値・年度が**記事本文と一致**しているか (本文の表と突き合わせる)
    - ③ 日本語が破綻していないか (「マル1」「政府所」「家族証」のような非実在語、「健康保／保険証」のような折り返し重複、意味不明な英字列)
    - ④ 同じ文言が画像内で二重に描かれていないか
    - ⑤ 制度と無関係なモチーフ (住宅購入・保険広告・イベントチラシ等) が入っていないか
  - 小さい文字は PIL で拡大して確認する: `python -c "from PIL import Image; im=Image.open('x.png'); w,h=im.size; im.crop((0,int(h*0.75),w,h)).resize((w*2,int(h*0.25)*2)).save('_zoom.png')"`
  - 1 つでも該当したら**無条件で差し戻し**、writer 側でプロンプトを修正のうえ再生成させる

### C. コンテンツ品質 (9 項目)

- [ ] **11.** セクションブリッジがあるか (各 H2 の冒頭に導入、末尾に接続文)
- [ ] **12.** AI 臭フレーズがないか (「することができます」「幅広く」「包括的に」「一助となれば」「いかがでしたでしょうか」)
- [ ] **13.** 文字数が 5,000 文字以上あるか
- [ ] **14.** 具体的な数字・日付・金額が含まれているか (抽象的な説明だけでは NG)
- [ ] **15.** H1 タイトル行が含まれていないか (ページ側で表示する)
- [ ] **15b.** **金額に月額/年額/一回限りの別が明記されているか**。年度改定される金額に年度が併記されているか。母子/父子の対象範囲が明示されているか
- [ ] **15c.** **対象範囲 (target_scope) と記事の記述が一致しているか** (意味的チェック・E コード無し)。`all_families` の制度は冒頭で「ひとり親専用ではない」ことを明言し、ひとり親目線の活用法があるか。`bereaved` は「死別のみ・離婚は対象外」を明言しているか。不一致は差し戻し
- [ ] **15d.** **全国共通と自治体差が峻別されているか** (意味的チェック・E コード無し)。①振込日等の具体日付が全国共通のように書かれていないか ②必要書類の表の前に「自治体により異なる一例」の断り書きがあるか ③金融機関の可否・「〜が増えています」等の根拠なし断定がないか ④資格判定 (事実婚・扶養義務者等) が単純化断定されていないか。city.\*.jp / pref.\*.jp 由来の情報が国ソースで裏取りされず全国の事実として書かれていたら差し戻し
- [ ] **15f.** **SEO 同義語カバレッジ** (grep で機械確認可): 本文に「シングルマザー」「母子家庭」「父子家庭 または シングルファーザー」が各1回以上あるか。「シンママ」が2回以上出ていたら口語過多として減らす
- [ ] **15g.** ★**役所語が残っていないか (「読者の言葉で書くルール」)**★ — 検出対象は `article_title` / `summary` / **質問役の発言** / **見出し (H2/H3)** の 4 か所。★**解説役の解説は対象外**★ (専門家の役割上、制度用語を使うほうが正確)。
  - 語彙表の定義元は `support-article-writer` skill の「言い換え表」。同じ語彙が `check_article` の `E20` と `scripts/article_health_check.py` の `BUREAU_TERMS` に入っている
  - **崩してはいけないもの**は指摘しない: 制度の正式名称・金額・所得制限額・期限・法令上の要件。「」で囲んだ原文引用と正式名称も対象外
  - `所得` `控除` `扶養親族` `現況届` のように**言い換えると不正確になる語**は、消させずに「初出でかっこ説明を添えたか」で判定する (`E20b`)
  - **なぜこの項目があるか**: この skill 群は補助金エージェント (経営者向け) から派生したため語彙が役所寄りに残っている。読者はその対極 (時間もお金も余裕がないひとり親) なので、個別に直しても次の記事でまた出る。仕組みで止める
  - 修正区分: **フォーマット系と同じくレビュアーが自分で直す** (言い換え表どおりに置換)。ただし置換で事実が変わる箇所は差し戻し
- [ ] **15h.** **`article_title` が型どおりか** — `平易な一言｜[地域の]制度名は数字・特徴【年度】`。制度名が正式名称のまま／地域名が制度名の直前／【年度】が末尾／**全角 40 字前後 (`len()` で実測)**。上限額には「最大」が付いているか
- [ ] **15i.** **`summary` が制度の目的規定の写しになっていないか** — 「〜のために支給される」型で始まっていたら差し戻し。「①何がどうなるか →②誰が →③いくら」の順で、「シングルマザー」を含むか
- [ ] **15k.** ★**危険語 = 平易化のときに正確性を落とす表現が無いか (`E24`)**★ — `15g`/`E20` が「難しすぎる」を見るのに対し、こちらは**その逆方向 (平易にしたら不正確になった)** を見る。★**禁止ではない**★ ので、出たら**一次情報で「本当にそうか」を確認し、事実ならそのまま通す**。事実でなければ「安全な言い換え」に直す。

  | 危険な表現 | なぜ危険か | 安全な言い換え (例) |
  |---|---|---|
  | 毎月もらえる・毎月安くなる・毎月入る | 実際の振込頻度と食い違う | 月額で計算される／1か月あたりで算定される |
  | 最大◯円もらえる | 全員がもらえるように読める | 条件を満たす場合の上限は◯円 |
  | ◯円まで | 総額の上限に見える | 1回・1日など所定の単位で◯円 |
  | 対象◯市 | 市の全域が対象に見える | ◯市内の対象区域 |
  | 入学すれば返済不要 | 免除申請と認定が必要 | 入学後に免除申請をして認められた場合 |
  | 当選確率が◯倍 | 実際の確率は応募状況で変わる | 抽せん番号が通常の◯倍割り当てられる |
  | 申請期限は◯日 | 特別申請等の機会を見落とす | 通常の申請期限は◯日。ほかの申請機会の有無も確認 |
  | 無料・全員・自動・誰でも | 例外や要件を落としている | (要件を添える) |

  - 検出対象は `article_title` / `summary` / **見出し** / **質問役の発言** / ★**解説役の解説**★ の 5 か所
  - ★**`15g`/`E20` と違い解説役の解説も対象**★ — `E20` は「読みやすさ」の話なので解説役は除外してよいが、`E24` は「**正確さ**」の話であり、**専門家の口から出た誤りこそ読者に最も信じられてしまう**。役割は言い訳にならない
  - **なぜこの項目があるか**: ①児童扶養手当を「毎月お金が入る」と書いた (実際は奇数月・年6回) ②千葉県医療費助成を「自己負担300円まで」と書いた (実際は1回あたりの負担額) の 2 事故は、どちらも `article_md` 本体は正しく、**あとから書き換えた `article_title` / `summary` だけ**が誤りを持ち込んでいた。**記事を直したあとにタイトル・summary を書き直すときも、同じファクトチェックをやり直す**
  - 修正区分: **差し戻し** (一次情報の確認が要るのでレビュアーの独断で書き換えない)。ただし事実が確認できた場合は言い換えのみレビュアーが直してよい
  - 公開後にも破れうるので `scripts/article_health_check.py` の `M20` に同期済み

- [ ] **15j.** ★**制度タイプ別の必須項目に全部触れているか (`E23`)**★ — 記事の構成を作り直す話ではなく、**「この型の制度なら必ず読者が知りたい論点」に一度も触れずに公開していないか**のチェックリスト。`supports.category` から型を判定する:

  | `supports.category` | 制度タイプ | 必ず確認する項目 |
  |---|---|---|
  | `手当` / `給付金` / `年金` | **手当・給付** | 算定単位／実際の振込月／申請期限／遡及の可否 |
  | `貸付` | **貸付** | 入金時期／審査／返済開始／返済期間／免除手続き |
  | `助成` / `税制` | **医療・減免** | 対象外費用／負担額の単位／事前申請／区域差 |
  | `サービス` | **サービス・住宅** | 実施地域／募集・予約時期／利用上限／利用できない場合 |

  - **なぜこの項目があるか**: 「毎月お金が入る」(実際は奇数月・年6回)、「自己負担300円まで」(実際は1回あたりの額) の 2 つの事故は、どちらも**その型なら必ず書くはずの論点 (実際の振込月 / 負担額の単位) を書かないまま平易にした**ことで起きている。危険語検出 (`E20`〜/`M20`) が「書いてしまった誤り」を拾うのに対し、こちらは「**書かなかった穴**」を拾う
  - `E23` はキーワードの有無しか見ない**一次スクリーニング**。E23 が出たら記事を読み、本当に触れていなければ**差し戻し** (writer が一次情報を取って書き足す)。触れているのに出たら誤検出なので通してよい
  - 逆に E23 が出なくても**書いてあることが正しいとは限らない**。金額・振込月・期限は従来どおり research_notes の quote と照合する
  - 公開後にも腐る基準なので `scripts/article_health_check.py` の `M21` に同期済み

- [ ] **15e.** **記事末尾に免責注意書きがあるか** (「※本記事は…時点の公表情報をもとに作成しています。…最新情報は、お住まいの市区町村の担当窓口でご確認ください。」)。タイトルの上限額に「最大」が付いているか (amount_max がある制度)

### D. リンク・参照 (3 項目)

- [ ] **16.** 関連制度リンクが `/support/{id}` 形式か
- [ ] **17.** リンク先 ID が DB に実在するか (確認コマンド実行)
- [ ] **18.** 問い合わせ先が :::pointbox に入っているか

### E. ファクトチェック (4 項目)

- [ ] **19.** 金額が DB の値 (amount_max/amount_note/support_rate) と矛盾していないか
- [ ] **20.** 所得制限・受給要件が公式ソースと合致するか (WebFetch で公式ページを確認)
- [ ] **21.** 問い合わせ先の電話番号・URL が生存しているか (curl 確認)
- [ ] **22.** Writer が提出したファクトチェック結果を検証 (全項目パスか)

## フォーマットチェックスクリプト (`check_article` 関数)

```python
import re

# E20: 役所語 (support-article-writer skill 「言い換え表」/ article_health_check.py の
#      BUREAU_TERMS と同一語彙。3 か所を必ず同時に更新すること)
BUREAU_TERMS = [
    ('養育', '育てる'), ('支給され', 'もらえる / お金が入る'), ('支給する', '出す (読者主語なら「もらえる」)'),
    ('受給者', 'もらっている人'), ('受給世帯', 'もらっている世帯'), ('修業', '学校に通う'),
    ('就業', '仕事 / 働くこと'), ('償還免除', '返さなくてよくなる'), ('償還', '返す / 返済'),
    ('貸し付け', '借りられる'), ('給付を受け', 'もらう'), ('交付を受け', '受け取る / もらう'),
    ('自立の促進', '(目的規定は書かない)'), ('生活の安定', '(目的規定は書かない)'), ('に資する', '(使わない)'),
    ('当該', 'その'), ('監護', '育てている'), ('扶養義務者', '同居している親族'),
    ('認定請求', '申請'), ('失権', 'もらえなくなる'), ('資格喪失', '対象でなくなる'),
    ('生計を同じく', '生活費を一緒にしている'), ('被保険者', '年金 / 保険に入っていた人'),
    ('一部負担金', '窓口で払うお金'), ('実施主体', '実際に手続きをする窓口'), ('支弁', '支払う'),
    ('措置を講じ', '(使わない)'), ('課税世帯', '住民税がかかる世帯'), ('非課税世帯', '住民税がかからない世帯'),
    ('併給', '一緒に受け取れる'), ('減免', '安くなる / 免除される'), ('従量料金', '使った量に応じた料金'),
    ('標準負担額', '決められた自己負担の額'), ('撤廃', 'なくなる'), ('世帯構成', '家族の人数や組み合わせ'),
    ('並びに', 'と / や'), ('若しくは', 'または'), ('所定の', '決められた'),
    ('を要する', 'が必要'), ('に該当する', 'にあてはまる'),
]
# 素の部分一致だと拾いすぎる語だけ正規表現で上書き (養育費 = 読者の日常語なので対象外)
BUREAU_TERM_RE = {'養育': r'養育(?!費)', '課税世帯': r'(?<!非)課税世帯'}
# 言い換えると不正確になる語 = 消させず「初出でかっこ説明」を求める
GLOSS_TERMS = [('所得', '所得（収入から必要な分を差し引いた額）'), ('控除', '控除（税金の計算前に差し引ける額）'),
               ('現況届', '毎年出す届出（現況届）'), ('扶養親族', '扶養親族（生活費をみている家族）')]

# E23: 制度タイプ別の必須項目 (チェックリスト 15j。article_health_check.py の M21 と同一)
CATEGORY_TO_TYPE = {'手当': '手当・給付', '給付金': '手当・給付', '年金': '手当・給付', '貸付': '貸付',
                    '助成': '医療・減免', '税制': '医療・減免', 'サービス': 'サービス・住宅'}
TYPE_REQUIRED = {
    '手当・給付': [
        ('算定単位', r'月額|年額|日額|一回限り|1回限り|回限り|1人あたり'),
        ('実際の振込月', r'奇数月|偶数月|年[0-9０-９]{1,2}回|振込|振り込|支払月|支給月|支払われ'),
        ('申請期限', r'申請期限|いつまでに|期限|締切|届出期限|現況届'),
        ('遡及の可否', r'遡|さかのぼ|過去(の|に)?分|翌月分から'),
    ],
    '貸付': [
        ('入金時期', r'入金|振込|振り込|貸付(日|時期)|交付'),
        ('審査', r'審査|選考|面談|相談員|決定通知'),
        ('返済開始', r'返済(の)?開始|据置|据え置き|返済が始ま|償還開始'),
        ('返済期間', r'返済期間|償還期間|年以内|回以内|月賦|年賦'),
        ('免除手続き', r'免除'),
    ],
    '医療・減免': [
        ('対象外費用', r'対象外|対象になりません|対象となりません|含まれません|適用され(ま)?せん|除きます|除く|自己負担'),
        ('負担額の単位', r'1回|一回|１回|1日|一日|１日|1か月|1ヶ月|1件|1人|1医療機関|受診ごと|月額|1世帯'),
        ('事前申請', r'事前|あらかじめ|申請が必要|医療証|受給者証|証の交付|申請しない'),
        ('区域差', r'市区町村によって|自治体によって|市町村が定め|お住まいの(市|自治体)|区域|実施していない'),
    ],
    'サービス・住宅': [
        ('実施地域', r'実施していない|実施状況|お住まいの(市|自治体)|自治体によって|市区町村によって|区域|対象地域'),
        ('募集・予約時期', r'募集|申込|申し込み|予約|抽選|抽せん|受付|随時'),
        ('利用上限', r'上限|まで利用|年間|時間まで|回まで|日まで|限度'),
        ('利用できない場合', r'利用できな|使えな|対象外|できません|お断り|不可|優先順位|落選'),
    ],
}

# E24: 危険語 = 「平易にした結果、正確性を落とした」表現 (article_health_check.py の M20 と同一)
#      ★禁止ではない★。文脈によっては正しい (本当に毎月振り込まれる制度もある) ので、
#      出たら一次情報で「本当にそうか」を確認する。事実ならそのまま通す。
#      ★E20 (役所語) と違い藤井の解説も対象★ — E20 は読みやすさ、E24 は正確さの話であり、
#      藤井 (社労士) の口から出た誤りこそ読者に最も信じられてしまうため。
# (正規表現, なぜ危険か, 安全な言い換え, 同じ文にあれば参考扱いに落とす文脈)
DANGER_PATTERNS = [
    (r'毎月[^。]{0,6}(もらえ|受け取れ|入りま|入る|入り|振り込|支給され|安くな|届きま|もらう)',
     '実際の振込頻度と食い違う', '月額で計算される / 1か月あたりで算定される',
     r'(奇数月|偶数月|年[0-9０-９]{1,2}回|[0-9０-９]{1,2}か月分|まとめて)'),
    (r'最大[0-9０-９][0-9０-９,，.万億]*円[^。]{0,8}(もらえ|受け取れ|支給され|入りま|入る|借りられ|戻って)',
     '全員がその額をもらえるように読める', '条件を満たす場合の上限は◯円',
     r'(条件|要件|所得|全部支給|一部支給|場合|人によって|上限)'),
    (r'[0-9０-９][0-9０-９,，]*円まで', '総額の上限に見える', '1回・1日など所定の単位で◯円',
     r'(1回|一回|１回|1日|一日|１日|1か月|1ヶ月|1か所|月額|年額|1件|1人|受診|1医療機関|所定|単位)'),
    (r'対象[0-9０-９]+[市町村区]', 'その市の全域が対象に見える', '◯市内の対象区域', r'(区域|エリア)'),
    (r'(入学|進学|卒業|就職|就業)(すれ|でき|し)ば[^。]{0,12}(返済不要|返済が?不要|返さなくて|免除)',
     '免除は自動ではなく申請と認定が必要', '入学後に免除申請をして認められた場合', ''),
    (r'返済(は|が)?不要', '貸付型は免除申請と認定が必要 (給付型なら正しい)',
     '入学後に免除申請をして認められた場合', r'(給付|もらえるお金|貸付ではな|返す必要のない)'),
    (r'(当選|抽選|抽せん)[^。]{0,8}[0-9０-９]+倍', '実際の当選確率は応募状況で変わる',
     '抽せん番号が通常の◯倍割り当てられる', r'(番号|割り当て|優遇倍率|申込資格)'),
    (r'(申請)?期限は[^。]{0,12}?[0-9０-９]{1,2}[月日]', 'ほかの申請機会を見落とす',
     '通常の申請期限は◯日。ほかの申請機会の有無も確認', r'(ほか|他の|随時|特例|例外|も受け付け|場合があ)'),
    (r'無料', '自己負担・回数制限などの例外を落としている', '◯◯の場合は無料 (要件を添える)',
     r'(要件|条件|場合|以外|除く|一部|自己負担)'),
    (r'全員', '対象外になる人が必ずいる', '◯◯を満たす人は全員 (要件を添える)',
     r'(要件|条件|満た|該当|対象となる)'),
    (r'自動(?!車)', '多くの制度は申請主義', '(申請が必要かどうかを明記する)',
     r'(申請|手続|届出|されません|ではありません|わけでは)'),
    (r'(誰|だれ)でも', '居住・所得・年齢などの要件がある', '(要件を添える)',
     r'(要件|条件|満た|わけでは|ではありません)'),
]
# 危険語の誤検出を緩和する文脈 (質問文 / 直後が否定)
_QUESTION_RE = re.compile(r'(？|\?|ですか|でしょうか|んですか|ますか|かな|ますよね)')
_NEGATION_RE = re.compile(r'(ではありません|ではない|わけでは|とは限りません|限りません|ではなく|ありません|しません)')


def check_danger(text: str, official_names: list) -> list:
    """危険語の検出。戻り値 [(ヒット, なぜ危険か, 安全な言い換え, 参考扱いの理由)]。

    参考扱いの理由が空文字でなければ「たぶん正しく書けている」= 呼び出し側で 1 段階緩める。
    """
    masked = _mask_protected(text, official_names)
    hits = []
    for pat, why, alt, ok_ctx in DANGER_PATTERNS:
        for m in re.finditer(pat, masked):
            note = ''
            if _QUESTION_RE.search(text):
                note = '質問文中'
            elif _NEGATION_RE.search(text[m.end():m.end() + 30]):
                note = '直後が否定'
            elif ok_ctx and re.search(ok_ctx, text):
                note = '条件・単位の補足あり'
            hits.append((m.group(0), why, alt, note))
    return hits


def _mask_protected(text: str, official_names: list) -> str:
    """崩してはいけないもの (制度の正式名称 /「」引用 /【年度】) を同じ長さの ○ に伏せる。

    ※ かっこの中身は伏せない (かっこ内に役所語を隠せてしまうため)。
       「初出かっこ説明方式」は「役所語の直後が開きかっこか」で個別に判定する。
    """
    for name in sorted([n for n in official_names if n and len(n) >= 3], key=len, reverse=True):
        text = text.replace(name, '○' * len(name))
    for rx in (r'「[^」]*」', r'【[^】]*】'):
        text = re.sub(rx, lambda m: '○' * len(m.group(0)), text)
    return text


def check_bureau(text: str, official_names: list) -> list:
    """役所語の検出。戻り値 [(役所語, 言い換え, 前後の文脈)]。"""
    masked = _mask_protected(text, official_names)
    hits = []
    for term, alt in BUREAU_TERMS:
        for m in re.finditer(BUREAU_TERM_RE.get(term, re.escape(term)), masked):
            # 直後が開きかっこなら「初出かっこ説明方式」として許容
            if text[m.end():m.end() + 1] in '（(' and m.end() < len(text):
                continue
            hits.append((term, alt, text[max(0, m.start() - 12):m.end() + 12]))
    return hits


def load_persona_names(path: str = 'config/persona.json') -> tuple:
    """config/persona.json から質問役・解説役の表示名を読む。

    ★話者名をこのファイルにハードコードしないための入口★
    キャラクターを差し替えても check_article() を書き換えずに済むようにする。

    探索順:
      1. config/persona.json            (運用時。自分のサイト用に編集したもの)
      2. config/persona.example.json    (配布時の既定サンプル)
      3. ハードコードの既定値            (どちらも読めないとき)

    戻り値: (質問役の表示名, 解説役の表示名)
    """
    import json, os
    for candidate in (path, 'config/persona.example.json'):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        names = {}
        for ch in data.get('characters', []):
            # display_name があればそれを優先 (「藤井先生」ではなく話者記法の「藤井」を使う場合があるため
            #  記事本文で使う名前は name のほう)
            if ch.get('id') in ('questioner', 'explainer'):
                names[ch['id']] = ch.get('name') or ch.get('display_name')
        if names.get('questioner') and names.get('explainer'):
            return names['questioner'], names['explainer']
    # フォールバック: 配布元の既定値
    return 'みさき', '藤井'


def check_article(md: str, article_title: str = '', summary: str = '',
                  official_names: list = (), category: str = '') -> list[str]:
    """記事のフォーマットチェック。問題があればエラーリストを返す。

    article_title / summary / official_names (DB の supports.title 一覧) を渡すと
    E20 (役所語) / E24 (危険語) まで検査する。省略すると本文のみが対象になる。
    category (DB の supports.category) を渡すと E23 (制度タイプ別の必須項目) も検査する。
    """
    errors = []
    lines = md.split('\n')
    official_names = list(official_names)

    # ★話者名は config/persona.json から読む (ここにハードコードしない)★
    #   キャラを差し替えても、この関数を書き換えずに済むようにするため。
    #   設定が読めなければ配布元の既定値にフォールバックするので、挙動は従来どおり。
    q_name, e_name = load_persona_names()
    Q_RE = re.compile(r'\*\*' + re.escape(q_name) + r'\*\*:')
    E_RE = re.compile(r'\*\*' + re.escape(e_name) + r'\*\*:')
    SPEAKER_RE = re.compile(r'\*\*(' + re.escape(q_name) + '|' + re.escape(e_name) + r')\*\*:')

    # E01: 質問役の発言で始まるか
    for line in lines:
        s = line.strip()
        if s and not s.startswith('#') and not s.startswith('!') and not s.startswith('<!--'):
            if not s.startswith('**' + q_name + '**:'):
                errors.append('E01: 記事が**' + q_name + '**:で始まっていない')
            break

    # E02: 話者役割チェック (質問役が聞き、解説役が答えているか)
    q_asks = q_answers = e_asks = e_answers = 0
    for line in lines:
        s = line.strip()
        is_q = any(k in s for k in ['？', '?', 'ですか', 'ですよね', 'んですが', 'でしょうか', 'ですけど'])
        if Q_RE.match(s):
            if is_q: q_asks += 1
            else: q_answers += 1
        elif E_RE.match(s):
            if is_q: e_asks += 1
            else: e_answers += 1
    if e_asks > q_asks or q_answers > e_answers:
        errors.append(f'E02: 話者逆転の疑い ({q_name}Q{q_asks}/A{q_answers}, {e_name}Q{e_asks}/A{e_answers})')

    # E03: 孤立テキスト
    in_directive = False
    in_comment = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if not s: continue
        if '<!--' in s: in_comment = True
        if '-->' in s: in_comment = False; continue
        if in_comment: continue
        if s.startswith(':::'): in_directive = not in_directive; continue
        if in_directive: continue
        if s.startswith('|') or s.startswith('#') or s.startswith('![') or s == '---': continue
        if SPEAKER_RE.match(s): continue
        if s.startswith('※'): continue  # 記事末尾の免責注意書き (15e/E18 で必須) は吹き出し外で正当
        errors.append(f'E03: L{i} 孤立テキスト: {s[:60]}')

    # E04: 吹き出し内リスト
    in_bubble = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if SPEAKER_RE.match(s): in_bubble = True; continue
        if not s: in_bubble = False; continue
        if in_bubble and (re.match(r'^[-*] ', s) or re.match(r'^\d+\. ', s)):
            errors.append(f'E04: L{i} 吹き出し内リスト: {s[:60]}')

    # E05: HH:MM 形式
    for i, line in enumerate(lines, 1):
        if re.search(r'(?<!\d)\d{1,2}:\d{2}(?!\d|分|秒|\.)', line) and '|' not in line and 'http' not in line:
            errors.append(f'E05: L{i} HH:MM形式: {line.strip()[:60]}')

    # E06: 太字コロンがスピーカー以外
    # 例外: リスト項目 (- **xxx**: ...) は writer skill が推奨する正規フォーマット
    #       (フロントの話者 regex は行頭 ** のみ誤判定するため、リスト内は安全)
    # 例外: ディレクティブ内 (:::pointbox 等) の定義リストも話者 regex の対象外
    in_directive = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith(':::'): in_directive = not in_directive; continue
        if in_directive: continue
        if re.match(r'^[-*] ', s) or re.match(r'^\d+\. ', s):
            continue
        matches = re.findall(r'\*\*([^*]+)\*\*:', line)
        for m in matches:
            if m not in (q_name, e_name):
                errors.append(f'E06: L{i} 太字コロン非スピーカー: **{m}**:')

    # E07: ディレクティブ開閉
    opens = sum(1 for l in lines if l.strip().startswith(':::') and len(l.strip()) > 3)
    closes = sum(1 for l in lines if l.strip() == ':::')
    if opens != closes:
        errors.append(f'E07: ディレクティブ開閉不一致 (open={opens}, close={closes})')

    # E08: FAQ 形式
    if '<!-- FAQ_JSON' not in md:
        errors.append('E08: FAQ_JSONが見つからない')

    # E09: mark 閉じ
    for i, line in enumerate(lines, 1):
        if '<mark>' in line and '</mark>' not in line:
            errors.append(f'E09: L{i} markタグ未閉じ')

    # E11: 全角コロン
    for i, line in enumerate(lines, 1):
        if '：' in line and not line.strip().startswith('|'):
            errors.append(f'E11: L{i} 全角コロン: {line.strip()[:60]}')

    # E12: 文字数
    if len(md) < 5000:
        errors.append(f'E12: 文字数不足 ({len(md)}文字 < 5000)')

    # E13: 図解画像 2 枚以上 (Supabase Storage URL に統一)
    img_urls = re.findall(r'!\[[^\]]*\]\((https://[^)]*article-images/[^)]+)\)', md)
    if len(img_urls) < 2:
        errors.append(f'E13: 図解画像不足 ({len(img_urls)}枚 < 2枚)')

    # E14: 画像ファイル実在性チェック
    import subprocess
    for url in img_urls:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', url],
            capture_output=True, text=True, timeout=10
        )
        if result.stdout.strip() != '200':
            errors.append(f'E14: 画像配信 HTTP {result.stdout.strip()} → {url[-50:]}')

    # E15: 図解画像の目視確認ゲート (チェックリスト 10c の機械レイヤー)
    #      中身が別制度かどうかは自動判定できないため、
    #      「全画像をローカルに落として Read で開く」ことを強制する。
    #      DL したファイルが揃っていなければ査読を通さない。
    import os
    img_dir = '/tmp/review-imgs'
    os.makedirs(img_dir, exist_ok=True)
    downloaded = []
    for n, url in enumerate(img_urls, 1):
        path = f'{img_dir}/{n:02d}-{url.rsplit("/", 1)[-1]}'
        subprocess.run(['curl', '-s', '-o', path, url], capture_output=True, timeout=30)
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            downloaded.append(path)
        else:
            errors.append(f'E15: 画像DL失敗 → {url[-50:]}')
    if downloaded:
        print('=' * 60)
        print('★E15: 以下の画像を Read ツールで1枚ずつ開いて目視すること (省略禁止)★')
        for p in downloaded:
            print('  Read ' + p)
        print('  確認: ①画像内タイトル=記事の制度名 ②金額=本文と一致 ③日本語の破綻なし')
        print('        ④文言の二重描画なし ⑤無関係なモチーフなし')
        print('  1つでも該当したら差し戻し。HTTP 200 は合格の根拠にならない。')
        print('=' * 60)

    # E16: 改行密度チェック
    nl_count = md.count('\n')
    if len(md) >= 1000:
        ratio = len(md) / max(nl_count, 1)
        if nl_count == 0 or ratio > 100:
            errors.append(
                f'E16: 改行密度不足 (md={len(md)}文字 / 改行{nl_count}個 / {ratio:.0f}文字に1改行)。'
                f'構造マーカー (## / **xxx**: / :::) の前に \\n\\n が必須。'
            )

    # E19: 根拠なし全国傾向表現 (自治体差の峻別ルール違反の疑い)
    for i, line in enumerate(lines, 1):
        # ★語順を変えた同じ主張もすり抜けさせない★ (2026-07-27 追加)
        #   就学援助の記事で「対象になっている自治体が多い」「締切が早いことが多い」が
        #   完全一致パターンをすり抜けた。後者は根拠が神戸市1件だけで4箇所に反復されていた。
        #   ※ scripts/article_health_check.py の NATIONWIDE_PATTERNS と同じ内容に保つこと。
        #   ※ 「おおむね」は入れない (「おおむね136万円以下」等 金額の概算に使われ誤検出になる)
        _nw = (r'多くの自治体|ほとんどの自治体|ほぼすべての自治体|自治体が増えて|自治体がほとんど'
               r'|自治体が多い|自治体も多い'
               r'|ことが多い|ケースが多い|場合が多い|ところが多い'
               r'|が一般的です|一般的には|のが通例|増えています|増えつつ'
               r'|たいてい|大半(の|は)|多くの方が|よくあるケースです')
        # 同じ文に具体例・出典があれば「根拠を示している」ので指摘しない
        _ev = re.search(r'(市|区|町|村)(では|は|の場合)|によると|統計|調査結果|https?://'
                        r'|厚生労働省|文部科学省|こども家庭庁|国税庁|日本年金機構', line)
        if re.search(_nw, line) and not _ev:
            errors.append(f'E19: L{i} 根拠なし全国傾向表現の疑い: {line.strip()[:60]}')

    # E20: 役所語 (チェックリスト 15g の機械レイヤー)
    #      対象は article_title / summary / 質問役の発言 / 見出し。
    #      ★解説役の解説は制度用語 OK なので対象外 (誤検出を避ける)★
    for term, alt, ctxt in check_bureau(article_title or '', official_names):
        errors.append(f'E20: article_title に役所語「{term}」→「{alt}」に … {ctxt}')
    for term, alt, ctxt in check_bureau(summary or '', official_names):
        errors.append(f'E20: summary に役所語「{term}」→「{alt}」に … {ctxt}')
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('**' + e_name + '**:'):
            continue
        if s.startswith('**' + q_name + '**:'):
            where = q_name + 'の発言'
        elif s.startswith('#'):
            where = '見出し'
        else:
            continue
        for term, alt, ctxt in check_bureau(s, official_names):
            errors.append(f'E20: L{i} {where}に役所語「{term}」→「{alt}」に … {ctxt}')

    # E20b: 言い換え不可の語にかっこ説明がない (summary のみ。title は字数上むり)
    if summary:
        masked_sum = _mask_protected(summary, official_names)
        for term, how in GLOSS_TERMS:
            if re.search(BUREAU_TERM_RE.get(term, re.escape(term)), masked_sum) \
                    and not re.search(re.escape(term) + r'\s*[（(]', summary):
                errors.append(f'E20b: summary の「{term}」に初出かっこ説明がない。例: {how}')

    # E21: summary が制度の目的規定の写しになっていないか (チェックリスト 15i)
    if summary and re.search(r'(のために|に資する|を目的として)(支給|給付|貸付|助成)', summary):
        errors.append('E21: summary が制度の目的規定の写しの疑い。「①何がどうなるか→②誰が→③いくら」で書き直す')
    if summary and 'シングルマザー' not in summary:
        errors.append('E21: summary に「シングルマザー」がない (meta description の SEO 同義語ルール)')

    # E22: article_title の型・字数 (チェックリスト 15h)
    if article_title:
        if '｜' not in article_title:
            errors.append('E22: article_title に「｜」がない (型: 平易な一言｜制度名は数字【年度】)')
        if not re.search(r'【[^】]+】$', article_title):
            errors.append('E22: article_title の末尾が【年度】でない')
        if len(article_title) > 44:
            errors.append(f'E22: article_title が {len(article_title)} 字 (全角 40 字前後に収める)')
        # 「｜」の前は「平易な一言」。ここに制度名が来ていたら旧型 (制度名先頭) のまま
        head = article_title.split('｜')[0]
        if any(n and len(n) >= 4 and n in head for n in official_names):
            errors.append('E22: article_title の「｜」の前に制度名がある (旧型)。前半は平易な一言にする')

    # E23: 制度タイプ別の必須項目もれ (チェックリスト 15j の機械レイヤー)
    #      キーワードの有無しか見ない一次スクリーニング。出たら記事を読んで本当に無いか確認する。
    stype = CATEGORY_TO_TYPE.get(category or '')
    if stype:
        for item, rx in TYPE_REQUIRED[stype]:
            if not re.search(rx, md):
                errors.append(f'E23: {stype}型の必須項目「{item}」に本文が一度も触れていない疑い')
    elif category:
        errors.append(f'E23: category「{category}」が制度タイプ表に無い (CATEGORY_TO_TYPE に追加を検討)')

    # E24: 危険語 (平易化のときに正確性を落とす表現)
    #      ★禁止ではない★ ので、出たら一次情報で確認する。事実ならそのまま通す。
    #      補足を置けない article_title / summary / 見出し は「参考扱い」でも報告し、
    #      吹き出し (質問役・解説役の両方) は補足があるものを落とす。
    for where, text in (('article_title', article_title or ''), ('summary', summary or '')):
        for hit, why, alt, note in check_danger(text, official_names):
            suffix = f' ※{note}のため参考扱い' if note else ''
            errors.append(f'E24: {where} に危険語「{hit}」({why})。要一次情報確認 → {alt}{suffix}')
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith('#'):
            where, drop_noted = '見出し', False
        elif s.startswith('**' + q_name + '**:'):
            where, drop_noted = q_name + 'の発言', True
        elif s.startswith('**' + e_name + '**:'):
            where, drop_noted = e_name + 'の解説', True
        else:
            continue
        for hit, why, alt, note in check_danger(s, official_names):
            if note and drop_noted:
                continue  # 吹き出しは打ち消して書くのが正しい形。全部出すと本当に危ない1件が埋もれる
            suffix = f' ※{note}のため参考扱い' if note else ''
            errors.append(f'E24: L{i} {where} に危険語「{hit}」({why})。要一次情報確認 → {alt}{suffix}')

    # E18: 記事末尾の免責注意書き
    if '※本記事は' not in md or '市区町村' not in md:
        errors.append('E18: 記事末尾の免責注意書き (※本記事は…市区町村の担当窓口でご確認ください) が見つからない')

    # E17: 金額の月額/年額明記チェック (簡易)
    # 「円」を含む行に 月額/年額/年間/月々/一回/1回/上限 のいずれも無い場合は警告
    for i, line in enumerate(lines, 1):
        if line.strip().startswith('|'):  # テーブルはヘッダで単位を示すため除外
            continue
        amounts = re.findall(r'[0-9,]+円', line)
        if amounts and not re.search(r'月額|年額|年間|月々|ごと|一回|1回|回限り|上限|相当', line):
            errors.append(f'E17: L{i} 金額の単位 (月額/年額等) が不明: {line.strip()[:60]}')

    return errors
```

## 差し戻しフォーマット

```
❌ 差し戻し
記事ID: {id}
タイトル: {title}

## NG項目
1. **チェック#2 話者逆転**
   - 場所: 藤井の発言に「？」が 15 個、みさきの発言に「？」が 1 個
   - 修正: 全スピーカー名を入れ替え、最初の発言をみさきの質問に変更

2. **チェック#12 AI 臭フレーズ**
   - 場所: L45「幅広く活用することができます」
   - 修正: 「いろんな場面で使えます」に変更

## 修正指示
修正後、再度レビュー提出 → レビュアー再チェック
```

## 公開承認フォーマット

```
✅ レビュー合格
記事ID: {id}
タイトル: {title}

- A. 話者・吹き出し: ✅ 全 5 項目パス
- B. 記法・フォーマット: ✅ 全 6 項目パス
- C. コンテンツ品質: ✅ 全 9 項目パス
- D. リンク・参照: ✅ 全 3 項目パス
- E. ファクトチェック: ✅ 全 4 項目パス

**公開OK**
```

## 重要な原則

- **主観を入れない**。チェックリストに沿って機械的に判定
- **「だいたいOK」で承認しない**。1 項目でも NG なら差し戻し or 修正
- **ライターの言い分を聞かない**。言い訳に屈しない
- **修正指示は具体的に**。「改善してください」ではなく「L23 を削除して〜に置換」と書く
- **金額の誤りは重大事故**。読者 (ひとり親) の生活設計に直結するため、金額・所得制限は必ず一次ソースまで遡って確認

## レンダリングチェック

dev server が起動していれば実際のページを確認する:

1. `${PUBLIC_SITE_URL}/support/{ID}` または `http://localhost:3000/support/{ID}` にアクセスしてスクリーンショットを撮影
2. 以下を目視確認:
   - 吹き出しの左右が正しいか (みさき=左、藤井=右)
   - みさきが質問し、藤井が回答しているか
   - `**太字**:` が話者以外で使われて DialogueBubble 化されていないか
   - `<mark>` が正しく描画されているか
   - テーブル・画像・:::warning/:::pointbox/:::steps が正しく表示されているか
   - 図解画像が吹き出しの中に入っていないか
3. 問題があれば修正 → 再確認 (最大 3 回)
4. 3 回でも直らなければ差し戻し
5. ※ フロントエンドサイトが未構築・未起動の場合は本チェックをスキップ可

## DB 操作

Supabase MCP は使わない。必ず `scripts/supabase-query.sh` を使用する。

```bash
# 制度データ読み込み
bash scripts/supabase-query.sh select supports "id=eq.{ID}&select=id,title,article_md,amount_max,amount_note,support_rate,status"

# 記事修正の保存
bash scripts/supabase-query.sh update supports '{"article_md":"..."}' "id=eq.{ID}"

# 関連制度の存在確認
bash scripts/supabase-query.sh select supports "id=eq.{ID}&select=id,title"
```

## 振り返り 4 層 reflection (レビュアー固有)

`agent-bootstrap` skill の Step Final 手順を踏まえ、レビュアー固有の中身を入れる。

### quality_check に書く項目 (レビュアー固有)

- ✅/❌ 32 項目チェックリスト (A〜E) を全走査したか
- ✅/❌ 図解画像を実際にダウンロードし、Read ツールで1枚ずつ目視したか (10c/E15)
- ✅/❌ research_notes 事前検証 (NULL / 3 件未満 / 公式 URL 無し) を先に実施
- ✅/❌ 記事中の金額・率・期限を research_notes.quote と全件照合
- ✅/❌ check_article (Python) のフォーマット項目 (E01〜E24) を実行 (summary / article_title / official_names / category を渡したか)
- ✅/❌ 役所語 (E20) を article_title / summary / みさきの発言 / 見出し で検査 (★藤井の解説は対象外★)
- ✅/❌ 危険語 (E24) を article_title / summary / 見出し / みさきの発言 / ★藤井の解説★ で検査し、出たものは一次情報で確認した
- ✅/❌ 制度タイプ別の必須項目 (E23) を `category` から判定して検査した
- ✅/❌ 合格時に reviewer_verifications を research_notes に追記
- ✅/❌ 修正 vs 差し戻しの分岐を仕様通りに判定 (フォーマット系は自分で直す、構造系は差し戻し)
- ✅/❌ 差し戻し指示が具体的 (L 行番号 + 修正方法) で記述された

## 仕様追記時のメタルール (孤立ルール防止・絶対遵守)

`support-article-writer` skill に新しい品質要件が追加されたら、以下の 2 レイヤーに**必ず同期する**:

1. **チェックリスト項目** (A〜E のどれかに `- [ ] **NN.** ...` を追加)
2. **フォーマットチェックスクリプト** (Python 関数 `check_article` に Err コード `Exx` として検出コード追加)

レビュアー視点で独自に基準を追加する場合も同じ 2 レイヤーセットで書く。チェックリストだけ追加してスクリプトに検出コードが無いと、機械ゲートが機能せず主観審査になる。

さらに、その基準が**公開後にも破れうる**もの (年度で腐る / 修正時に混入する / 図と本文がずれる) なら、
**`support-article-maintenance` skill にも同期**する (`scripts/article_health_check.py` に `Mxx` を追加)。
公開前だけ守られて公開後に腐るルールを作らないため。

**How to apply**: 新基準を書き終えたら自己問診:
- □ チェックリストに `- [ ] **NN.** ...` を追加したか？
- □ `check_article` 関数に `Exx` コードで検出ロジックを書いたか？
- □ ライター側 (`support-article-writer` skill) との対応関係は明確か？
- □ 公開後にも破れうる基準か？ Yes なら `support-article-maintenance` skill に `Mxx` を同期したか？

> 公開後の定期点検 (リンク切れ・年度陳腐化・図と本文の矛盾・断定表現の残存) は本 skill の守備範囲外。
> `support-article-maintenance` skill と `docs/article-maintenance.md` が担当する。
> 図解画像の目視基準 (10c / E15) はメンテ側から参照されるので、**基準の定義元は本 skill**。

即答できなければ未完成として書き直す。

## カスタマイズの指針

- **チェックリスト**: 32 項目はひとり親支援記事向け。別ジャンルの場合は適宜増減
- **対話キャラ名**: 「みさき / 藤井」を別の名前に変える場合は `check_article` 内の正規表現も同期
- **公式 URL 判定**: `.go.jp / pref.*.jp / city.*.jp` は日本前提。他国対応は調整
