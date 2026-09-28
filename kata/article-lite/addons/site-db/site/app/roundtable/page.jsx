import { getRoundtableList } from '@/lib/supabase';

export const revalidate = 300;

export const metadata = {
  // 画面上の呼称は「おしゃべり」に統一。<title>・description だけは検索語 (座談会) を併記する
  title: 'おしゃべり（座談会）｜ひとり親の「暮らしのリアル」を当事者どうしで語る',
  description:
    '事実婚という選択、離婚のプロセス、子どもへの説明、戸籍や名字——制度の説明だけでは分からない暮らしのリアルを、シングルマザーの当事者どうしが語り合うおしゃべり（座談会）コーナーです。',
};

// テーマの表示順 (ここにない theme は後ろにそのまま並ぶ)
const THEME_ORDER = ['結婚の形', '離婚のプロセス', '子どもとの関係', '仕事と暮らし'];

export default async function RoundtableIndexPage() {
  const items = await getRoundtableList();

  const byTheme = new Map();
  for (const r of items) {
    const key = r.theme || 'その他';
    if (!byTheme.has(key)) byTheme.set(key, []);
    byTheme.get(key).push(r);
  }
  const themes = [
    ...THEME_ORDER.filter((t) => byTheme.has(t)),
    ...[...byTheme.keys()].filter((t) => !THEME_ORDER.includes(t)),
  ];

  return (
    <>
      <section className="hero">
        <h1>
          制度の話だけでは足りない、<em>暮らしのリアル</em>を。
        </h1>
        <p>
          婚姻届を出す・出さない、子どもへの伝え方、戸籍や名字のこと。ひとり親として暮らす人どうしが、それぞれの選択を語り合うコーナーです。制度にかかわる話には、社労士の藤井先生が最後に補足を入れます。
        </p>
      </section>

      {items.length === 0 ? (
        <p className="rt-empty">おしゃべりの記事は現在準備中です。もうしばらくお待ちください。</p>
      ) : (
        themes.map((theme) => (
          <section key={theme} className="cat-section">
            <h2 className="cat-title">{theme}</h2>
            <ul className="card-list">
              {byTheme.get(theme).map((r) => {
                const inner = (
                  <>
                    <h3>{r.title}</h3>
                    <p>{r.lead}</p>
                    <span className="meta">
                      {(r.participants || []).map((p) => (
                        <span key={p} className="badge badge-person">
                          {p}
                        </span>
                      ))}
                      {!r.has_article && <span className="badge badge-pending">準備中</span>}
                    </span>
                  </>
                );
                return (
                  <li key={r.slug}>
                    {r.has_article ? (
                      <a href={`/roundtable/${r.slug}`} className="card rt-card">
                        {inner}
                      </a>
                    ) : (
                      <div className="card rt-card rt-card-pending">{inner}</div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))
      )}

      <a href="/" className="back-link">← 制度一覧にもどる</a>
    </>
  );
}
