/* ============================================================
   サイトの設定を 1 箇所に集めるファイル
   ------------------------------------------------------------
   ★サイト名・運営者名・ドメインなど「その人の環境だから成り立つ値」は
     コードに直接書かず、すべて環境変数 (.env.local) から読みます。★

   配布物にそのまま個人情報や独自ドメインが残らないようにするための作りです。
   値が未設定でもページが落ちないよう、それぞれ無難な既定値を持たせています。

   設定する場所: プロジェクト直下の .env.example を .env.local にコピーして編集
                 (サイト側は site/.env.local も必要。README のセットアップ手順を参照)
   ============================================================ */

/* 空文字も「未設定」として扱う。
   .env に `KEY=` と書いただけの行は '' になるので、|| では拾えるが
   意図を明示するために関数にしている */
const env = (v, fallback) => (v && v.trim() !== '' ? v.trim() : fallback);

/* ---------- 公開 URL ---------- */
/* Vercel にデプロイすると VERCEL_PROJECT_PRODUCTION_URL が自動で入るので、
   PUBLIC_SITE_URL の設定を忘れても本番 URL が使われる */
export const SITE_URL = env(
  process.env.PUBLIC_SITE_URL,
  process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : 'http://localhost:3000'
);

/* ---------- サイト名・説明 ---------- */
export const SITE_NAME = env(process.env.NEXT_PUBLIC_SITE_NAME, 'サイト名（未設定）');
/* ロゴは 2 段組み。1 段目は小さい前置き、2 段目が大きい本体。
   1 段目が空なら 1 行のロゴになる */
export const SITE_NAME_PRE = env(process.env.NEXT_PUBLIC_SITE_NAME_PRE, '');
export const SITE_NAME_MAIN = env(process.env.NEXT_PUBLIC_SITE_NAME_MAIN, SITE_NAME);
export const SITE_TAGLINE = env(process.env.NEXT_PUBLIC_SITE_TAGLINE, '');
export const SITE_DESCRIPTION = env(
  process.env.NEXT_PUBLIC_SITE_DESCRIPTION,
  'このサイトの説明文が未設定です。NEXT_PUBLIC_SITE_DESCRIPTION を設定してください。'
);

/* ---------- 運営者 (YMYL 分野では明示が必要) ---------- */
export const OPERATOR_ORG = env(process.env.NEXT_PUBLIC_OPERATOR_ORG, '運営者名（未設定）');
export const OPERATOR_NAME = env(process.env.NEXT_PUBLIC_OPERATOR_NAME, '運営責任者名（未設定）');
export const OPERATOR_EMAIL = env(process.env.NEXT_PUBLIC_OPERATOR_EMAIL, '');
export const POLICY_DATE = env(process.env.NEXT_PUBLIC_POLICY_DATE, '（制定日未設定）');

/* ---------- アクセス解析 / LINE ---------- */
/* どちらも空なら、対応するタグ・導線を一切描画しない (痕跡を残さない) */
export const GA_ID = env(process.env.NEXT_PUBLIC_GA_ID, '');
export const LINE_ADD_URL = env(process.env.NEXT_PUBLIC_LINE_ADD_URL, '');

/* ---------- 画像置き場 (Supabase Storage) ---------- */
/* バケット名もフォルダ名も環境変数。別の CDN に移すときはここだけ変える */
const SUPABASE_URL = env(process.env.NEXT_PUBLIC_SUPABASE_URL, '');
export const STORAGE_BUCKET = env(process.env.NEXT_PUBLIC_STORAGE_BUCKET, 'article-images');
export const STORAGE_SECTIONS_DIR = env(process.env.NEXT_PUBLIC_STORAGE_SECTIONS_DIR, 'sections');
export const STORAGE_CHARACTERS_DIR = env(process.env.NEXT_PUBLIC_STORAGE_CHARACTERS_DIR, 'characters');
export const STORAGE_BASE = SUPABASE_URL
  ? `${SUPABASE_URL}/storage/v1/object/public/${STORAGE_BUCKET}`
  : '';

/* ---------- ブランド素材 ---------- */
/* 配布版はダミーの SVG。差し替え方は site/public/brand/README.md */
export const LOGO_MARK = env(process.env.NEXT_PUBLIC_LOGO_MARK, '/brand/mark-placeholder.svg');
/* OGP = SNS でシェアされたときに出るサムネイル画像。未設定なら出力しない */
export const OGP_IMAGE = env(process.env.NEXT_PUBLIC_OGP_IMAGE, '');
