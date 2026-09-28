import fs from "node:fs/promises";

const TOPICS_PATH = "data/topics.json";
const OUTPUT_PATH = "data/threads-drafts.json";
const POSTS_PATH = "data/threads-posts.json";
const PERFORMANCE_PATH = "data/threads-performance.json";
const PLAN_PATH = "data/post-plan.json";
const PROFILE_PATH = "data/topic-profile.json";
const BANK_PATH = "data/draft-bank.json";
const MAX_THREADS_CHARS = 500;
const RECENT_STRATEGY_WINDOW = 6;

const siteUrl = (process.env.PUBLIC_SITE_URL || "https://example.com").replace(/\/$/, "");
const limit = Number(process.argv.find((arg) => arg.startsWith("--limit="))?.split("=")[1] || 7);
const fromBankFlag = process.argv.includes("--from-bank");

const STRATEGIES = [
  "choice-expansion",
  "parent-dialogue",
  "social-capital",
  "teacher-relief",
  "myth-busting",
  "small-step"
];

function jstDayIndex(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  return Math.floor((date.getTime() + 9 * 60 * 60 * 1000) / 86400000);
}

function compact(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function fitThreads(text) {
  const normalized = String(text || "")
    .split("\n")
    .map((line) => compact(line))
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if ([...normalized].length <= MAX_THREADS_CHARS) return normalized;
  return `${[...normalized].slice(0, MAX_THREADS_CHARS - 1).join("").trim()}…`;
}

function normalizeBody(value) {
  return String(value || "")
    .split("\n")
    .filter((line) => !line.trim().startsWith("#"))
    .join("\n")
    .replace(/https?:\/\/\S+/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function trackingUrl({ tag, index }) {
  const url = new URL("/", siteUrl);
  url.searchParams.set("utm_source", "threads");
  url.searchParams.set("utm_medium", "social");
  url.searchParams.set("utm_campaign", "daily_posts");
  url.searchParams.set("utm_content", `${tag}_${String(index + 1).padStart(2, "0")}`);
  return url.toString();
}

async function readJson(path, fallback) {
  try {
    return JSON.parse(await fs.readFile(path, "utf8"));
  } catch {
    return fallback;
  }
}

function postTimestamp(post) {
  const value = post.postedAt || post.createdAt || post.publishedAt || "";
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : 0;
}

async function readHistory() {
  const payload = await readJson(POSTS_PATH, { posts: [] });
  return (payload.posts || [])
    .map((post) => ({
      strategy: post.strategy,
      body: post.body || post.text || "",
      postedAt: post.postedAt,
      timestamp: postTimestamp(post)
    }))
    .filter((post) => post.strategy || post.body)
    .sort((a, b) => b.timestamp - a.timestamp);
}

async function readPerformance() {
  return readJson(PERFORMANCE_PATH, { posts: [] });
}

async function readPlan() {
  const plan = await readJson(PLAN_PATH, {});
  const valid = (item) => item && STRATEGIES.includes(item.strategy);
  return {
    firstPost: valid(plan.firstPost) ? plan.firstPost : null,
    pinned: Array.isArray(plan.pinned) ? plan.pinned.filter(valid) : []
  };
}

async function readProfile() {
  const profile = await readJson(PROFILE_PATH, {});
  if (!profile || profile.active !== true) return null;
  return profile;
}

async function readBank() {
  const bank = await readJson(BANK_PATH, { items: [] });
  return Array.isArray(bank.items) ? bank : { items: [] };
}

function summarizePerformance(posts) {
  const byStrategy = new Map();
  for (const post of posts || []) {
    if (!post.strategy) continue;
    const views = Number(post.views || post.impressions || 0);
    const engagement = Number(post.likes || 0) + Number(post.replies || 0) + Number(post.reposts || 0) + Number(post.quotes || 0);
    const entry = byStrategy.get(post.strategy) || { strategy: post.strategy, posts: 0, views: 0, engagement: 0 };
    entry.posts += 1;
    entry.views += views;
    entry.engagement += engagement;
    byStrategy.set(post.strategy, entry);
  }

  const strategies = [...byStrategy.values()]
    .map((entry) => ({
      ...entry,
      engagementRate: entry.views > 0 ? Number((entry.engagement / entry.views).toFixed(4)) : 0
    }))
    .sort((a, b) => b.engagementRate - a.engagementRate);

  return {
    hasData: strategies.length > 0,
    strategies,
    nextExperiment: strategies.length
      ? `${strategies[0].strategy} を基準に、hook と CTA を1つずつ変えて保存・返信率を比較`
      : "初期運用では複数の切り口を同数投稿して比較"
  };
}

// --- bank モード: AIが生成した本文配列を drafts 化する ---
function buildDraftsFromBank({ bank, profile, history }) {
  const recentBodies = new Set(history.map((item) => normalizeBody(item.body)));
  const hashtags = Array.isArray(profile?.hashtags) ? profile.hashtags.filter(Boolean) : [];
  const tagLine = hashtags.length ? `\n\n${hashtags.join(" ")}` : "";
  const theme = profile?.theme || bank.profileTheme || "custom-theme";
  const audience = profile?.audience || "";

  const drafts = [];
  for (const [i, item] of (bank.items || []).entries()) {
    const rawBody = typeof item === "string" ? item : item.body;
    if (!rawBody || !String(rawBody).trim()) continue;
    const body = fitThreads(rawBody);
    if (recentBodies.has(normalizeBody(body))) continue; // 既投稿と重複する本文は除外

    const text = fitThreads(`${body}${tagLine}`);
    drafts.push({
      topicId: null,
      topicTitle: theme,
      url: trackingUrl({ tag: "bank", index: drafts.length }),
      chars: [...text].length,
      status: "draft",
      strategy: "profile-bank",
      hookType: item.angle || "profile",
      audience,
      ctaType: "engage",
      hypothesis: "自分の文体・テーマで一貫発信すると、フォロー前提の読者に届きやすい",
      targetMetric: "保存・返信",
      body,
      text,
      metadata: {
        source: "draft-bank.json",
        plannedBy: "topic-profile",
        profileTheme: theme,
        angle: item.angle || null,
        bankIndex: typeof item.dayOffset === "number" ? item.dayOffset : i
      }
    });
    if (drafts.length >= limit) break;
  }
  return drafts;
}

// --- フォールバック: profile も bank も無いとき。topics.json から最小の下書きを作る ---
function buildDraftsFromTopics({ payload, history }) {
  const dayIndex = jstDayIndex();
  const topics = payload.topics || [];
  const recentBodies = new Set(history.map((item) => normalizeBody(item.body)));
  const drafts = [];

  for (let i = 0; i < topics.length && drafts.length < limit; i += 1) {
    const topic = topics[(dayIndex + i) % topics.length];
    const body = fitThreads(
      `${topic.title}について、今日はひとつだけ。\n\n${topic.angle || ""}\n\n${(topic.keywords || []).join(" / ")}`
    );
    if (recentBodies.has(normalizeBody(body))) continue;
    const text = body;
    drafts.push({
      topicId: topic.id,
      topicTitle: topic.title,
      url: trackingUrl({ tag: "topic", index: drafts.length }),
      chars: [...text].length,
      status: "draft",
      strategy: "topic-fallback",
      hookType: "plain",
      audience: topic.audience || "",
      ctaType: "engage",
      hypothesis: "テーマを決めて発信を続けると認知が積み上がる",
      targetMetric: "保存・返信",
      body,
      text,
      metadata: {
        source: TOPICS_PATH,
        plannedBy: "topic-fallback",
        note: "topic-profile.json を active にすると、文体模倣の本格運用に切り替わります"
      }
    });
  }
  return drafts;
}

const payload = await readJson(TOPICS_PATH, { brand: {}, topics: [] });
const history = await readHistory();
const performance = await readPerformance();
const performanceSummary = summarizePerformance(performance.posts);
const profile = await readProfile();
const bank = await readBank();

let drafts = [];
let mode = "topic-fallback";

if (profile && bank.items.length > 0) {
  mode = "profile-bank";
  drafts = buildDraftsFromBank({ bank, profile, history });
} else if (fromBankFlag) {
  // --from-bank を明示したのに使えない → 原因を伝えて止める
  const reasons = [];
  if (!profile) reasons.push(`${PROFILE_PATH} が無い、または active:false`);
  if (bank.items.length === 0) reasons.push(`${BANK_PATH} の items が空`);
  throw new Error(`--from-bank を指定しましたが bank から生成できません: ${reasons.join(" / ")}`);
} else {
  if (!payload.topics?.length) throw new Error(`${TOPICS_PATH} must contain at least one topic.`);
  drafts = buildDraftsFromTopics({ payload, history });
}

if (drafts.length === 0) {
  console.warn("WARN: 生成された下書きが0件です（全て既投稿と重複、または bank が空の可能性）。");
}

await fs.writeFile(OUTPUT_PATH, `${JSON.stringify({
  generatedAt: new Date().toISOString(),
  mode,
  source: mode === "profile-bank" ? BANK_PATH : TOPICS_PATH,
  databaseTarget: "threads_drafts",
  personaAgent: "threads-draft-strategist",
  skill: "threads-growth",
  siteUrl,
  limits: {
    maxThreadsChars: MAX_THREADS_CHARS,
    drafts: drafts.length
  },
  profileSummary: profile
    ? { active: true, theme: profile.theme || "", audience: profile.audience || "", bankItems: bank.items.length }
    : { active: false },
  historySummary: {
    source: POSTS_PATH,
    postsRead: history.length,
    recentStrategies: history.slice(0, RECENT_STRATEGY_WINDOW).map((item) => item.strategy).filter(Boolean)
  },
  performanceSummary,
  drafts
}, null, 2)}\n`);

console.log(`Generated ${drafts.length} Threads drafts (mode=${mode}): ${OUTPUT_PATH}`);
