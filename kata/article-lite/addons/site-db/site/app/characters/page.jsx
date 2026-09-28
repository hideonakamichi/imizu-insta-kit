/* ★画像置き場のバケット名・フォルダ名は環境変数から (lib/siteConfig.js が組み立てる)★ */
import { STORAGE_BASE, STORAGE_CHARACTERS_DIR } from '@/lib/siteConfig';

export const metadata = {
  title: '登場人物紹介｜みさきさん・あかりさんと藤井先生',
  description:
    '当サイトの記事は、シングルマザーのみさきさん、事実婚を選んだあかりさん、社労士の藤井先生の3人でお届けしています。それぞれのプロフィールを紹介します。',
};

const AVATAR_BASE = `${STORAGE_BASE}/${STORAGE_CHARACTERS_DIR}`;

export default function CharactersPage() {
  return (
    <article className="characters-page">
      <header className="article-header">
        <h1>登場人物紹介</h1>
      </header>

      <p>
        当サイトは、<strong>3人の登場人物</strong>でお届けしています。
        制度の解説記事は、ひとり親当事者の<strong>みさきさん</strong>が感じる素朴な疑問に、
        社会保険労務士の<strong>藤井先生</strong>が答えていく対話形式。
        <a href="/roundtable">おしゃべりコーナー</a>では、みさきさんと、事実婚を選んだ<strong>あかりさん</strong>が
        暮らしのリアルを語り合い、制度にかかわる部分だけ藤井先生が補足します。
      </p>
      <p>
        「制度の説明はむずかしくて頭に入らない」という方も、会話を追いかけるだけで、
        金額・条件・申請方法までひととおり分かるようにつくっています。
      </p>

      <section className="char-card">
        <img
          className="char-hero"
          src={`${AVATAR_BASE}/misaki-family.png`}
          alt="みさきさんと娘のひなちゃん"
          width="1200"
          height="896"
        />
        <div className="char-head">
          <img
            className="cast-avatar cast-avatar-misaki big"
            src={`${AVATAR_BASE}/misaki.png`}
            alt=""
            width="52"
            height="52"
          />
          <div>
            <h2>早瀬 みさき（34）</h2>
            <p className="char-role">質問役・読者代表</p>
          </div>
        </div>
        <ul>
          <li>小学2年生の娘・<strong>ひなちゃん（7歳）</strong>と2人暮らし。離婚して2年目</li>
          <li>パート事務として働いていて、年収はおよそ180万円。児童扶養手当は「一部支給」の帯</li>
          <li>住まいは賃貸アパート。いまは正社員への転職と、資格取得を考え中</li>
          <li>役所の書類とお金の制度が苦手。「それ、私ももらえるんですか？」が口ぐせ</li>
          <li>制度の解説記事すべてに登場。<a href="/roundtable">おしゃべりコーナー</a>にも出ています</li>
        </ul>
      </section>

      <section className="char-card">
        <img
          className="char-hero"
          src={`${AVATAR_BASE}/akari-family.png`}
          alt="あかりさんと小学5年生の息子"
          width="1200"
          height="896"
        />
        <div className="char-head">
          <img
            className="cast-avatar cast-avatar-akari big"
            src={`${AVATAR_BASE}/akari.png`}
            alt=""
            width="52"
            height="52"
          />
          <div>
            <h2>あかり（38）</h2>
            <p className="char-role">おしゃべりの相手役・事実婚を選んだ人</p>
          </div>
        </div>
        <ul>
          <li>小学5年生の息子と暮らしています。フルタイム勤務</li>
          <li>
            パートナーとは<strong>事実婚</strong>を選んでいて、婚姻届は出していません。
            そのぶん制度面で不利になる場面も、実体験として話せます
          </li>
          <li>離婚を経たみさきさんとは、<strong>違う選択をしている対比役</strong>。
            「どちらが正しい」ではなく、それぞれの理由を言葉にしてくれます</li>
          <li>落ち着いた性格で、感情的にならずに自分の考えを話すタイプ</li>
          <li>登場するのは<a href="/roundtable">おしゃべりコーナー</a>。制度の解説記事には出ません</li>
        </ul>
      </section>

      <section className="char-card">
        <img
          className="char-hero"
          src={`${AVATAR_BASE}/fujii-large.png`}
          alt="藤井先生"
          width="1200"
          height="896"
        />
        <div className="char-head">
          <img
            className="cast-avatar cast-avatar-fujii big"
            src={`${AVATAR_BASE}/fujii.png`}
            alt=""
            width="52"
            height="52"
          />
          <div>
            <h2>藤井先生</h2>
            <p className="char-role">解説役・社会保険労務士</p>
          </div>
        </div>
        <ul>
          <li>ひとり親家庭の支援制度（手当・助成・給付金・年金・税金）に詳しい社労士</li>
          <li>「結論から言うと」で始まる説明と、具体的な金額で答えてくれるのが持ち味</li>
          <li>断定できないこと（自治体差があること）は、正直に「自治体に確認を」と言うタイプ</li>
          <li>解説記事ではみさきさんの相手役。<a href="/roundtable">おしゃべりコーナー</a>では、
            制度にかかわる話が出たときだけ短く補足します</li>
        </ul>
      </section>

      <p className="char-note">
        ※ みさきさん・あかりさんは、読者のみなさんの疑問や体験を代弁するための架空のキャラクターです。
        記事中の金額の例などは、みさきさんの設定（子ども1人・年収約180万円）をもとにした一例で、
        実際の支給額や適用は世帯の状況によって変わります。
      </p>

      <a href="/" className="back-link">← 制度一覧にもどる</a>
    </article>
  );
}
