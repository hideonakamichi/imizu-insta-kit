import {
  getSupportList,
  getGlossaryList,
  getRoundtableList,
  getPrefectureList,
  getPrefectureSupportPairs,
} from '@/lib/supabase';

const BASE =
  process.env.PUBLIC_SITE_URL ||
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : 'http://localhost:3000');

export default async function sitemap() {
  const supports = await getSupportList();
  const words = await getGlossaryList();
  const roundtables = await getRoundtableList();
  /* 地域制度。記事が1本以上ある県のハブと、その県の制度記事だけを載せる
     (執筆前の県を sitemap に入れても評価されないため) */
  const prefectures = await getPrefectureList();
  const prefSupports = await getPrefectureSupportPairs();
  return [
    { url: `${BASE}/`, changeFrequency: 'weekly', priority: 1 },
    /* 困りごとから探す。制度記事へのハブなのでトップに次ぐ優先度にする */
    { url: `${BASE}/start`, changeFrequency: 'weekly', priority: 0.9 },
    { url: `${BASE}/calendar`, changeFrequency: 'monthly', priority: 0.7 },
    { url: `${BASE}/words`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/roundtable`, changeFrequency: 'weekly', priority: 0.7 },
    { url: `${BASE}/characters`, changeFrequency: 'monthly', priority: 0.4 },
    { url: `${BASE}/about`, changeFrequency: 'monthly', priority: 0.5 },
    { url: `${BASE}/privacy`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${BASE}/disclaimer`, changeFrequency: 'yearly', priority: 0.3 },
    ...supports.map((s) => ({
      url: `${BASE}/support/${s.id}`,
      changeFrequency: 'weekly',
      priority: 0.8,
    })),
    ...prefectures.map((p) => ({
      url: `${BASE}/${p.slug}`,
      changeFrequency: 'weekly',
      priority: 0.8,
    })),
    ...prefSupports.map((p) => ({
      url: `${BASE}/${p.pref}/support/${p.id}`,
      changeFrequency: 'weekly',
      priority: 0.7,
    })),
    ...words
      .filter((w) => w.has_article)
      .map((w) => ({
        url: `${BASE}/words/${w.slug}`,
        changeFrequency: 'monthly',
        priority: 0.6,
      })),
    ...roundtables
      .filter((r) => r.has_article)
      .map((r) => ({
        url: `${BASE}/roundtable/${r.slug}`,
        changeFrequency: 'monthly',
        priority: 0.6,
      })),
  ];
}
