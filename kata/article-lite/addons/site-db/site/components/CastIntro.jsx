// 記事冒頭に毎回表示するキャラクター紹介。
// ★人物設定の正本は config/persona.json (無ければ config/persona.example.json)。そちらと同期させること★
/* ★画像置き場のバケット名・フォルダ名は環境変数から (lib/siteConfig.js が組み立てる)★ */
import { STORAGE_BASE, STORAGE_CHARACTERS_DIR } from '@/lib/siteConfig';

const AVATAR_BASE = `${STORAGE_BASE}/${STORAGE_CHARACTERS_DIR}`;

export default function CastIntro() {
  return (
    <aside className="cast-intro" aria-label="この記事の登場人物">
      <div className="cast-member">
        <img
          className="cast-avatar cast-avatar-misaki"
          src={`${AVATAR_BASE}/misaki.png`}
          alt="みさき"
          width="38"
          height="38"
        />
        <div>
          <strong>みさき</strong>
          <p>34歳。小2の娘・ひなちゃんとふたり暮らし。制度のことはよくわからない、読者代表。</p>
        </div>
      </div>
      <div className="cast-member">
        <img
          className="cast-avatar cast-avatar-fujii"
          src={`${AVATAR_BASE}/fujii.png`}
          alt="藤井先生"
          width="38"
          height="38"
        />
        <div>
          <strong>藤井先生</strong>
          <p>ひとり親家庭の支援制度に詳しい社会保険労務士。金額と手続きまで具体的に解説。</p>
        </div>
      </div>
      <a href="/characters" className="cast-more">ふたりの紹介をくわしく見る →</a>
    </aside>
  );
}
