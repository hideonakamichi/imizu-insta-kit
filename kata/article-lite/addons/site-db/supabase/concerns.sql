-- =============================================================================
-- 「困りごと」タグを DB に移すための DDL + データ移行 SQL
-- =============================================================================
-- ★このファイルはまだ実行していません★ (2026-07-26 時点)
--
-- いまの実装:
--   site/lib/concerns.js が唯一の定義。CONCERNS (困りごとの一覧・表示順・リード文) と
--   CONCERN_MAP (program_code → 困りごと id[]) をリポジトリ側で持ち、
--   /start はそれと supports テーブルを突き合わせて生成している。
--
-- なぜリポジトリ側で始めたか:
--   supports に列を足すと Supabase の SQL Editor で人が DDL を実行する必要があり、
--   その待ちの間ページを出せない。困りごとタグは「編集判断」であってデータ収集では
--   ないので、まずコードで持ってレビューできる形にした。
--
-- DB に移したくなる合図:
--   - 制度が 100 件を超えて、CONCERN_MAP の手入れが現実的でなくなったとき
--   - 執筆パイプライン (エージェント) にタグ付けまでやらせたいとき
--   - 困りごとごとの PV を DB 側で集計したくなったとき
--
-- 移行手順:
--   1. 下の DDL を Supabase の SQL Editor で実行
--   2. 下の INSERT (concerns / support_concerns) を実行
--      ★INSERT の中身は site/lib/concerns.js と1対1で対応させてある★
--        片方だけ直すと /start とDBがずれるので、移行するときは
--        concerns.js から CONCERN_MAP を削除し、lib/supabase.js 側で join すること
--   3. site/lib/supabase.js の getConcernSupports() を
--      support_concerns の join に差し替え、concerns.js は表示順とリード文だけ残す
--
-- 注意:
--   supports 本体には手を入れない (別エージェントが記事を執筆中のため)。
--   タグは必ず別テーブル (support_concerns) に持つこと。
-- =============================================================================


-- -----------------------------------------------------------------------------
-- concerns (困りごとマスター)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS concerns (
  id          TEXT PRIMARY KEY,          -- URL アンカーにそのまま使う (例: money-now)。日本語は入れない
  label       TEXT NOT NULL,             -- 見出しに出す読者の言葉 (例: 今月の生活費が足りない)
  lead        TEXT,                      -- 見出し直下の1文。「この見出しで何が見つかるか」を書く
  sort_order  INTEGER NOT NULL,          -- 表示順 (小さいほど上)
  created_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE concerns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "concerns_read" ON concerns;
CREATE POLICY "concerns_read" ON concerns
  FOR SELECT USING (true);


-- -----------------------------------------------------------------------------
-- support_concerns (制度 × 困りごとの many-to-many)
-- 1制度に複数の困りごとを付けてよい (例: 母子父子寡婦福祉資金貸付金は4つ)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS support_concerns (
  support_id  INTEGER REFERENCES supports(id) ON DELETE CASCADE,
  concern_id  TEXT    REFERENCES concerns(id) ON DELETE CASCADE,
  PRIMARY KEY (support_id, concern_id)
);

CREATE INDEX IF NOT EXISTS idx_support_concerns_concern ON support_concerns(concern_id);

ALTER TABLE support_concerns ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "support_concerns_read" ON support_concerns;
CREATE POLICY "support_concerns_read" ON support_concerns
  FOR SELECT USING (true);


-- -----------------------------------------------------------------------------
-- 困りごと 12件 (site/lib/concerns.js の CONCERNS と同じ内容・同じ順)
-- -----------------------------------------------------------------------------
INSERT INTO concerns (id, label, lead, sort_order) VALUES
  ('money-now',  '今月の生活費が足りない',   '毎月・定期的に受け取れるお金と、当面をしのぐための貸付・相談先です。', 1),
  ('medical',    '病院代が心配',             '子どもや親自身の医療費の自己負担を軽くする制度です。', 2),
  ('housing',    '家賃・引っ越しが不安',     '住まいを借りる・住み続けるための家賃の支援、公営住宅、住む場所そのものの支援です。', 3),
  ('utilities',  '水道・光熱費が高い',       '水道料金などの減免です。お住まいの水道事業者・自治体ごとに扱いが異なります。', 4),
  ('tax',        '税金・保険料が払えない',   '所得税・住民税が安くなる控除と、年金・健康保険の保険料の免除・軽減です。', 5),
  ('childcare',  '保育園・学童のこと',       '保育料の無償化と、放課後の預け先に関する制度です。', 6),
  ('school',     '小中学校の費用',           '給食費・学用品費・修学旅行費など、義務教育でかかるお金の援助です。', 7),
  ('highschool', '高校・大学の費用',         '授業料、授業料以外の教育費、受験にかかる費用、進学のための貸付です。', 8),
  ('work',       '資格をとって働きたい',     '資格取得や職業訓練の費用と、訓練中の生活費を支える給付です。', 9),
  ('help',       '家事・育児を手伝ってほしい', '家に来てもらう・預かってもらうなど、人の手を借りるための制度です。', 10),
  ('divorce',    '養育費・離婚の手続き',     '養育費の取決めや、離婚前後の手続きを支える公的な支援です。', 11),
  ('bereaved',   '死別したあとのこと',       '配偶者と死別したご家庭が受け取れる年金です。', 12)
ON CONFLICT (id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 制度 × 困りごと (site/lib/concerns.js の CONCERN_MAP と同じ内容)
-- ★supports.id ではなく program_code で引く★ id は登録順で動くため
-- -----------------------------------------------------------------------------
-- ★配布版はサンプル 3 件です★
-- 本番のひもづけ (数十件) は同梱していません。
-- supabase/seed.sql のサンプルに対応する形だけ残してあります。
-- ★推測で付けないこと。★ 一次情報に「対象経費・目的」として書かれているものだけ付ける。
INSERT INTO support_concerns (support_id, concern_id)
SELECT s.id, v.concern_id
FROM (VALUES
  ('sample-teate-a',      'money-now'),
  ('sample-josei-b',      'medical'),
  ('sample-kashitsuke-c', 'money-now'),
  ('sample-kashitsuke-c', 'housing'),
  ('sample-kashitsuke-c', 'highschool'),
  ('sample-kashitsuke-c', 'work')
) AS v(program_code, concern_id)
JOIN supports s ON s.program_code = v.program_code
ON CONFLICT DO NOTHING;
