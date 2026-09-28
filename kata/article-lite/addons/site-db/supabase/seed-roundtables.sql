-- おしゃべりコーナー (roundtables) のサンプルシード (1 件)
--
-- ★配布版はサンプルです★ 本番の企画リストは同梱していません。
--
-- 使い方: schema.sql を実行して roundtables テーブルを作ったあと、
--         Supabase の SQL Editor でこのファイル全体を実行してください。
--
-- 注意:
--   - article_md は NULL のまま。本文は後工程 (執筆パイプライン) で埋めます。
--   - related_support_ids は supports.id を想定。seed.sql のサンプル 3 件を入れた
--     直後なら 1〜3 になります。環境によって id はずれるので投入前に確認してください。
--   - 再実行しても既存行は壊さないよう ON CONFLICT (slug) DO NOTHING にしています。
--
-- ★別テーマで使う場合★
--   roundtables = 「制度そのものではなく、暮らしのリアルを当事者どうしで語る」枠。
--   制度記事 (supports) が "What"、こちらが "How it feels" を担当します。
--   別テーマなら「ユーザー座談会」「体験談」に読み替えられます。
--   ★倫理チェックが 15 項目中 6 項目ある★のはこの枠だけ (skill 参照)。

INSERT INTO roundtables (slug, title, theme, lead, participants, related_support_ids, related_glossary_slugs, sort_order) VALUES
  (
    'sample-roundtable',
    '（サンプル）暮らしの選択をめぐるおしゃべり — 制度の説明だけでは分からないこと',
    'サンプルテーマ',
    'みさき (当事者) とあかり (別の立場の当事者) が、制度の外にある迷いや選択について語り合います。制度への影響は、藤井先生が最後に整理します。★配布版のダミー企画です★',
    ARRAY['みさき','あかり','藤井先生'],
    ARRAY[1,2],
    ARRAY['fuyou','kojo'],
    10
  )
ON CONFLICT (slug) DO NOTHING;
