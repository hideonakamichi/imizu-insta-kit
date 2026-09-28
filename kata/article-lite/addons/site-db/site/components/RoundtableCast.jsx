// おしゃべりページ (/roundtable) の冒頭に出す参加者紹介。
// ★人物設定の正本は config/persona.json (無ければ config/persona.example.json)。そちらと同期させること★
// 制度記事の CastIntro とは別物: 当事者どうしを主役に出し、藤井先生は「制度の補足で登場」の小さい扱い。
/* ★画像置き場のバケット名・フォルダ名は環境変数から (lib/siteConfig.js が組み立てる)★ */
import { STORAGE_BASE, STORAGE_CHARACTERS_DIR } from '@/lib/siteConfig';

const AVATAR_BASE = `${STORAGE_BASE}/${STORAGE_CHARACTERS_DIR}`;

const CAST = {
  みさき: {
    file: 'misaki.png',
    cls: 'cast-avatar-misaki',
    role: '34歳・離婚2年目',
    bio: '小2の娘・ひなちゃんと2人暮らし。パート事務で働きながら、正社員への転職と資格取得を考え中。',
  },
  あかり: {
    file: 'akari.png',
    cls: 'cast-avatar-akari',
    role: '38歳・事実婚を選択',
    bio: '小5の息子とパートナーとの暮らし。婚姻届は出さないという選択をして数年。フルタイム勤務。',
  },
};

const ADVISOR = {
  name: '藤井先生',
  file: 'fujii.png',
  cls: 'cast-avatar-fujii',
  note: '社会保険労務士。おしゃべりには、最後の制度の補足で登場します。',
};

const DEFAULT_PARTICIPANTS = ['みさき', 'あかり', '藤井先生'];

export default function RoundtableCast({ participants }) {
  const names = participants && participants.length > 0 ? participants : DEFAULT_PARTICIPANTS;
  const members = names.filter((n) => CAST[n]);
  const hasAdvisor = names.some((n) => n === ADVISOR.name || n === '藤井');

  if (members.length === 0 && !hasAdvisor) return null;

  return (
    <aside className="rt-cast" aria-label="このおしゃべりの参加者">
      <p className="rt-cast-label">このおしゃべりの参加者</p>
      <div className="rt-cast-members">
        {members.map((name) => {
          const c = CAST[name];
          return (
            <div className="rt-cast-member" key={name}>
              <img
                className={`cast-avatar ${c.cls}`}
                src={`${AVATAR_BASE}/${c.file}`}
                alt={name}
                width="38"
                height="38"
              />
              <div>
                <strong>{name}</strong>
                <span className="rt-cast-role">{c.role}</span>
                <p>{c.bio}</p>
              </div>
            </div>
          );
        })}
      </div>
      {hasAdvisor && (
        <p className="rt-cast-advisor">
          <img
            className={`cast-avatar ${ADVISOR.cls}`}
            src={`${AVATAR_BASE}/${ADVISOR.file}`}
            alt={ADVISOR.name}
            width="24"
            height="24"
          />
          <span>
            <strong>{ADVISOR.name}</strong>：{ADVISOR.note}
          </span>
        </p>
      )}
      <p className="rt-cast-note">
        ※ このおしゃべりは、実際のご相談でよくうかがう声をもとにした架空の対話です。特定の生き方をおすすめしたり、否定したりするものではありません。
      </p>
    </aside>
  );
}
