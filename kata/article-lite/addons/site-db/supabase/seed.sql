-- ============================================================
-- supports テーブルの動作確認用サンプルデータ (3 件)
--
-- ★配布版はサンプルです★
--   本番運用していたデータセットは同梱していません。
--   ここに入っているのは「スキーマの使い方を示すための 3 件」だけです。
--   金額・要件はすべてダミーなので、そのまま公開しないでください
--   (記事を書かせると Writer が公式ソースで必ず再照合します)。
--
-- 使い方:
--   schema.sql を実行した後、Supabase の SQL Editor で実行する。
--   article_md は NULL のままなので、パイプラインを回すと
--   「未記事化」として Writer に投げられる対象になります。
--
-- ★別テーマで使う場合★
--   supports = 「読者に紹介する対象」を入れる箱です。
--   制度 → 商品 / イベント / 講座 / 補助金 / 求人 …と読み替えられます。
--   最低限 program_code (一意キー)・title・summary・category・official_url
--   さえ埋まっていれば、パイプラインは動きます。
-- ============================================================

INSERT INTO supports (
  program_code, title, summary, category,
  amount_max, amount_note, support_rate,
  is_nationwide, organizer, source_url, official_url, status
) VALUES
(
  'sample-teate-a',
  'サンプル手当A',
  '(サンプル) ひとり親家庭の生活を支えるために支給される手当。所得に応じて全部支給・一部支給があります。実在の制度の値は入っていません。',
  '手当',
  48050,
  '月額・第1子全部支給。第2子以降は加算あり。★サンプル値★',
  NULL,
  true,
  'サンプル省庁',
  'https://example.go.jp/sample/teate-a',
  'https://example.go.jp/sample/teate-a',
  'active'
),
(
  'sample-josei-b',
  'サンプル医療費助成B',
  '(サンプル) 医療費の自己負担分を自治体が助成する制度。助成範囲・自己負担額・所得制限は自治体により異なる、というタイプの制度の書き方を確認するためのダミーです。',
  '助成',
  NULL,
  '医療費自己負担分を助成 (内容は自治体により異なる)。★サンプル値★',
  NULL,
  true,
  '各都道府県・市区町村',
  'https://example.go.jp/sample/josei-b',
  'https://example.go.jp/sample/josei-b',
  'active'
),
(
  'sample-kashitsuke-c',
  'サンプル貸付C',
  '(サンプル) 修学資金・生活資金などを無利子または低利で貸し付ける制度。「もらえる」ではなく「返す」タイプなので、危険語チェック (E24) の動作確認に向いています。',
  '貸付',
  NULL,
  '資金種別ごとに限度額が異なる。無利子 (保証人あり) または年1.0%。★サンプル値★',
  NULL,
  true,
  'サンプル都道府県',
  'https://example.go.jp/sample/kashitsuke-c',
  'https://example.go.jp/sample/kashitsuke-c',
  'active'
)
ON CONFLICT (program_code) DO NOTHING;

-- ============================================================
-- 対象範囲の仕分け (target_scope)
--   hitorioya    = ひとり親専用
--   all_families = 子育て世帯全般 (ひとり親目線の活用法を厚く書く)
--   bereaved     = 死別のみ対象
--
-- ★別テーマで使う場合★
--   「その記事を誰に向けて書くか」の軸を、自分のテーマの分類に置き換えてください
--   (例: 初心者向け / 経験者向け、法人向け / 個人向け)。
--   Writer はこの値で書き分けの重心を変えます。
-- ============================================================
UPDATE supports SET target_scope = 'hitorioya'
  WHERE program_code IN ('sample-teate-a','sample-josei-b','sample-kashitsuke-c');
