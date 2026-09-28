-- ひとり親支援エージェント用 Supabase スキーマ
--
-- 使い方:
--   1. Supabase プロジェクトを作成
--   2. SQL Editor でこのファイル全体を実行
--   3. Storage で `article-images` バケット (public) を作成
--   4. .env.local に NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY を設定
--
-- 含まれるもの:
--   - supports (ひとり親支援制度マスター)
--   - support_prefectures (制度×都道府県 join)
--   - prefectures (都道府県マスター)
--   - sync_logs (同期実行ログ)
--   - glossary (用語集 = /words)
--   - roundtables (おしゃべりコーナー = /roundtable)
--   - RLS ポリシー (anon 読み取り専用 / service_role 全権)

-- =============================================================================
-- 旧テーマ (補助金) のテーブルを撤去
-- =============================================================================
DROP TABLE IF EXISTS subsidy_prefectures;
DROP TABLE IF EXISTS subsidies;

-- =============================================================================
-- prefectures
-- =============================================================================
CREATE TABLE IF NOT EXISTS prefectures (
  id          SERIAL PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,
  name_ja     TEXT NOT NULL,
  name_en     TEXT,
  region      TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE prefectures ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "prefectures_read" ON prefectures;
CREATE POLICY "prefectures_read" ON prefectures
  FOR SELECT USING (true);

-- =============================================================================
-- supports (ひとり親支援制度マスター)
-- =============================================================================
CREATE TABLE IF NOT EXISTS supports (
  id                  SERIAL PRIMARY KEY,
  program_code        TEXT UNIQUE,                -- 制度スラッグ (例: jido-fuyo-teate)
  title               TEXT NOT NULL,
  summary             TEXT,                       -- 概要 (ai_summary 相当)
  category            TEXT,                       -- 手当 / 助成 / 給付金 / 貸付 / 税制 / 年金 / サービス
  target_scope        TEXT,                       -- hitorioya (ひとり親専用) / all_families (子育て世帯全般) / bereaved (死別のみ)
  amount_max          BIGINT,                     -- 支給・給付上限額 (円)。加算込みの真の上限額を入れる。金額型でない制度は NULL
  amount_min          BIGINT,                     -- 下限額 (あれば)
  amount_note         TEXT,                       -- 金額の補足 (例: "月額・全部支給時 (令和8年度)")
  support_rate        TEXT,                       -- 給付率・助成率 (例: "受講費用の60%")
  application_start   DATE,                       -- 申請受付開始 (通年なら NULL)
  application_end     DATE,                       -- 申請期限 (これより前なら closed に自動更新。通年なら NULL)
  is_nationwide       BOOLEAN DEFAULT false,      -- 全国制度なら true (都道府県 join 不要)
  organizer           TEXT,                       -- 実施機関 (こども家庭庁 / 各自治体 等)
  source_url          TEXT,                       -- 一次ソース URL
  official_url        TEXT,                       -- 公式案内 URL
  status              TEXT DEFAULT 'active',      -- active / closed / draft
  article_md          TEXT,                       -- 生成された記事本文 (Markdown)
  article_title       TEXT,                       -- 生成された記事タイトル
  research_notes      JSONB,                      -- 調査メモ + 引用 + reviewer_verifications
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_supports_status ON supports(status);
CREATE INDEX IF NOT EXISTS idx_supports_article_null ON supports(article_md) WHERE article_md IS NULL;
CREATE INDEX IF NOT EXISTS idx_supports_application_end ON supports(application_end);
CREATE INDEX IF NOT EXISTS idx_supports_category ON supports(category);

ALTER TABLE supports ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "supports_read" ON supports;
CREATE POLICY "supports_read" ON supports
  FOR SELECT USING (true);

-- updated_at 自動更新トリガー
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_supports_updated_at ON supports;
CREATE TRIGGER trg_supports_updated_at
  BEFORE UPDATE ON supports
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- support_prefectures (制度 × 都道府県の many-to-many)
-- 全国制度 (is_nationwide=true) は join 不要。自治体独自制度で使う
-- =============================================================================
CREATE TABLE IF NOT EXISTS support_prefectures (
  support_id     INTEGER REFERENCES supports(id) ON DELETE CASCADE,
  prefecture_id  INTEGER REFERENCES prefectures(id) ON DELETE CASCADE,
  PRIMARY KEY (support_id, prefecture_id)
);

ALTER TABLE support_prefectures ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "support_prefectures_read" ON support_prefectures;
CREATE POLICY "support_prefectures_read" ON support_prefectures
  FOR SELECT USING (true);

-- =============================================================================
-- sync_logs (データ同期の実行ログ)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sync_logs (
  id              SERIAL PRIMARY KEY,
  mode            TEXT,                  -- 'diff' / 'full'
  status          TEXT DEFAULT 'running',-- running / success / error
  items_fetched   INTEGER DEFAULT 0,
  items_upserted  INTEGER DEFAULT 0,
  items_closed    INTEGER DEFAULT 0,
  error_message   TEXT,
  started_at      TIMESTAMPTZ DEFAULT now(),
  ended_at        TIMESTAMPTZ
);

ALTER TABLE sync_logs ENABLE ROW LEVEL SECURITY;

-- sync_logs は service_role でのみ書き込み・読み込み (anon には公開しない)
-- (PostgREST デフォルトで anon には非公開、明示ポリシー不要)

-- =============================================================================
-- Storage バケット (public bucket: article-images)
-- =============================================================================
-- ★ 注意: バケット作成は Supabase Dashboard の Storage 画面から行ってください
--    バケット名: article-images
--    Public: ON

-- =============================================================================
-- 都道府県 47 件 (シード)
-- =============================================================================
INSERT INTO prefectures (slug, name_ja, region) VALUES
  ('hokkaido', '北海道', '北海道'),
  ('aomori', '青森県', '東北'),
  ('iwate', '岩手県', '東北'),
  ('miyagi', '宮城県', '東北'),
  ('akita', '秋田県', '東北'),
  ('yamagata', '山形県', '東北'),
  ('fukushima', '福島県', '東北'),
  ('ibaraki', '茨城県', '関東'),
  ('tochigi', '栃木県', '関東'),
  ('gunma', '群馬県', '関東'),
  ('saitama', '埼玉県', '関東'),
  ('chiba', '千葉県', '関東'),
  ('tokyo', '東京都', '関東'),
  ('kanagawa', '神奈川県', '関東'),
  ('niigata', '新潟県', '中部'),
  ('toyama', '富山県', '中部'),
  ('ishikawa', '石川県', '中部'),
  ('fukui', '福井県', '中部'),
  ('yamanashi', '山梨県', '中部'),
  ('nagano', '長野県', '中部'),
  ('gifu', '岐阜県', '中部'),
  ('shizuoka', '静岡県', '中部'),
  ('aichi', '愛知県', '中部'),
  ('mie', '三重県', '近畿'),
  ('shiga', '滋賀県', '近畿'),
  ('kyoto', '京都府', '近畿'),
  ('osaka', '大阪府', '近畿'),
  ('hyogo', '兵庫県', '近畿'),
  ('nara', '奈良県', '近畿'),
  ('wakayama', '和歌山県', '近畿'),
  ('tottori', '鳥取県', '中国'),
  ('shimane', '島根県', '中国'),
  ('okayama', '岡山県', '中国'),
  ('hiroshima', '広島県', '中国'),
  ('yamaguchi', '山口県', '中国'),
  ('tokushima', '徳島県', '四国'),
  ('kagawa', '香川県', '四国'),
  ('ehime', '愛媛県', '四国'),
  ('kochi', '高知県', '四国'),
  ('fukuoka', '福岡県', '九州'),
  ('saga', '佐賀県', '九州'),
  ('nagasaki', '長崎県', '九州'),
  ('kumamoto', '熊本県', '九州'),
  ('oita', '大分県', '九州'),
  ('miyazaki', '宮崎県', '九州'),
  ('kagoshima', '鹿児島県', '九州'),
  ('okinawa', '沖縄県', '沖縄')
ON CONFLICT (slug) DO NOTHING;

-- =============================================================================
-- glossary (用語集 = /words)
-- 制度記事 (supports) より易しい「生活者の基本語」を解説する用語集。
-- 読者は制度用語に不慣れなシングルマザー等。article_md は後工程で執筆する。
-- 初期データは supabase/seed-glossary.sql を参照。
-- =============================================================================
CREATE TABLE IF NOT EXISTS glossary (
  id                  SERIAL PRIMARY KEY,
  slug                TEXT UNIQUE NOT NULL,       -- URL用スラッグ (例: fuyou)
  term                TEXT NOT NULL,              -- 表示名 (例: 扶養)
  reading             TEXT,                       -- よみがな (例: ふよう)
  short_def           TEXT,                       -- 一言定義 (60字以内)
  level               TEXT,                       -- L1 生活の基本語 / L2 制度でよく出る語 / L3 手続き語
  sort_order          INTEGER,                    -- 表示順 (小さいほど上)
  article_md          TEXT,                       -- 解説本文 (Markdown / 後で執筆)
  research_notes      JSONB,                      -- 調査メモ + 引用 + reviewer_verifications
  related_support_ids INTEGER[],                  -- 関連する supports.id の配列
  status              TEXT DEFAULT 'active',      -- active / draft
  created_at          TIMESTAMPTZ DEFAULT now(),
  updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_glossary_slug ON glossary(slug);
CREATE INDEX IF NOT EXISTS idx_glossary_level ON glossary(level);
CREATE INDEX IF NOT EXISTS idx_glossary_article_null ON glossary(article_md) WHERE article_md IS NULL;

ALTER TABLE glossary ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "glossary_read" ON glossary;
CREATE POLICY "glossary_read" ON glossary
  FOR SELECT USING (true);

-- updated_at 自動更新 (supports と同じ set_updated_at() を流用)
DROP TRIGGER IF EXISTS trg_glossary_updated_at ON glossary;
CREATE TRIGGER trg_glossary_updated_at
  BEFORE UPDATE ON glossary
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- =============================================================================
-- roundtables (おしゃべりコーナー = /roundtable)
-- 制度解説では扱えない「暮らしのリアル」を当事者同士が語る企画。
-- 登場人物: みさき (離婚2年目) / あかり (事実婚を選択) / 藤井先生 (末尾で制度補足のみ)。
-- article_md は後工程 (執筆パイプライン) で埋める。初期データは supabase/seed-roundtables.sql を参照。
-- =============================================================================
CREATE TABLE IF NOT EXISTS roundtables (
  id                      SERIAL PRIMARY KEY,
  slug                    TEXT UNIQUE NOT NULL,       -- URL用スラッグ (例: jijitsukon-to-iu-sentaku)
  title                   TEXT NOT NULL,              -- おしゃべりのタイトル
  theme                   TEXT,                       -- テーマ区分 (結婚の形 / 離婚のプロセス / 子どもとの関係 / 仕事と暮らし など)
  lead                    TEXT,                       -- 導入文 (120字程度)。カード表示と meta description に使う
  participants            TEXT[],                     -- 登場人物名の配列 (例: ARRAY['みさき','あかり'])
  article_md              TEXT,                       -- 本文 (Markdown / 後で執筆)
  research_notes          JSONB,                      -- 調査メモ + 引用 + reviewer_verifications
  related_support_ids     INTEGER[],                  -- 関連する supports.id の配列
  related_glossary_slugs  TEXT[],                     -- 関連する glossary.slug の配列
  status                  TEXT DEFAULT 'active',      -- active / draft
  published_at            DATE,                       -- 公開日 (未公開は NULL)
  sort_order              INTEGER,                    -- 表示順 (小さいほど上)
  created_at              TIMESTAMPTZ DEFAULT now(),
  updated_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_roundtables_slug ON roundtables(slug);
CREATE INDEX IF NOT EXISTS idx_roundtables_theme ON roundtables(theme);
CREATE INDEX IF NOT EXISTS idx_roundtables_article_null ON roundtables(article_md) WHERE article_md IS NULL;

ALTER TABLE roundtables ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "roundtables_read" ON roundtables;
CREATE POLICY "roundtables_read" ON roundtables
  FOR SELECT USING (true);

-- updated_at 自動更新 (supports と同じ set_updated_at() を流用)
DROP TRIGGER IF EXISTS trg_roundtables_updated_at ON roundtables;
CREATE TRIGGER trg_roundtables_updated_at
  BEFORE UPDATE ON roundtables
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();
