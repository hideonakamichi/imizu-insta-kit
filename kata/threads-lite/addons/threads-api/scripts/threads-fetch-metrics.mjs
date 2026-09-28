import fs from "node:fs/promises";
import { loadLocalEnv } from "./lib/load-local-env.mjs";

await loadLocalEnv();

const POSTS_PATH = "data/threads-posts.json";
const PERFORMANCE_PATH = "data/threads-performance.json";
const API_BASE = "https://graph.threads.net/v1.0";

// Threads Insights が返す指標名。post単位で取得できるもの。
const METRICS = ["views", "likes", "replies", "reposts", "quotes"];

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  if (value.includes("THAA...") || value.includes("your-") || value.includes("実際の")) {
    throw new Error(`${name} still looks like a placeholder.`);
  }
  return value;
}

// --live を付けたとき、または THREADS_DRY_RUN=False のときだけ実APIを叩く。
function isLiveMode() {
  if (process.argv.includes("--live")) return true;
  return String(process.env.THREADS_DRY_RUN || "True").toLowerCase() === "false";
}

async function readJson(path, fallback) {
  try {
    return JSON.parse(await fs.readFile(path, "utf8"));
  } catch {
    return fallback;
  }
}

async function parseJsonResponse(response, label) {
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${label} returned non-JSON response (${response.status}): ${text.slice(0, 300)}`);
  }
  if (!response.ok) throw new Error(`${label} failed (${response.status}): ${JSON.stringify(json)}`);
  return json;
}

// Insights API のレスポンス（data[].name / values[].value 形式）を {views, likes,...} に畳む。
function foldInsights(json) {
  const out = {};
  for (const entry of json.data || []) {
    const value = entry.total_value?.value ?? entry.values?.[0]?.value ?? 0;
    out[entry.name] = Number(value) || 0;
  }
  return out;
}

async function fetchMetricsForPost(postId, accessToken) {
  const url = new URL(`${API_BASE}/${postId}/insights`);
  url.searchParams.set("metric", METRICS.join(","));
  url.searchParams.set("access_token", accessToken);
  const json = await parseJsonResponse(await fetch(url), `Insights for ${postId}`);
  return foldInsights(json);
}

// アカウントに実在する過去投稿一覧（id/timestamp/text）を取得する。
// --from-account モードで、テンプレ経由でない既存投稿も分析対象にできる。
async function fetchAccountPosts(userId, accessToken) {
  const url = new URL(`${API_BASE}/${userId}/threads`);
  url.searchParams.set("fields", "id,timestamp,text,media_type,permalink");
  url.searchParams.set("limit", "100");
  url.searchParams.set("access_token", accessToken);
  const json = await parseJsonResponse(await fetch(url), "Account threads list");
  return (json.data || []).map((p) => ({
    threadsPostId: p.id,
    postedAt: p.timestamp,
    body: p.text || "",
    mediaType: p.media_type,
    postUrl: p.permalink
  }));
}

function fromAccountMode() {
  return process.argv.includes("--from-account");
}

// threads-posts.json（テンプレ経由の投稿記録）を threadsPostId 引きのメタ辞書にする。
// --from-account で取得した投稿に strategy/hookType/audience/ctaType を後付けし、
// summarizePerformance() が strategy 別に集計できるようにする（断線の修復）。
function buildMetaIndex(postsLog) {
  const index = new Map();
  for (const post of postsLog?.posts || []) {
    if (!post.threadsPostId) continue;
    index.set(String(post.threadsPostId), {
      strategy: post.strategy ?? null,
      hookType: post.hookType ?? null,
      audience: post.audience ?? null,
      ctaType: post.ctaType ?? null
    });
  }
  return index;
}

// アカウント投稿にローカル記録のメタを突き合わせる。
// 見つからない投稿はメタを null のまま残す（欠損は欠損として扱い、捏造しない）。
function mergeMeta(posts, metaIndex) {
  let matched = 0;
  const merged = posts.map((post) => {
    const meta = metaIndex.get(String(post.threadsPostId));
    if (meta && (meta.strategy || meta.hookType || meta.audience || meta.ctaType)) matched += 1;
    return { ...post, ...(meta || {}) };
  });
  return { merged, matched };
}

const live = isLiveMode();
const fromAccount = fromAccountMode();
const now = new Date().toISOString();

// 取得対象の決定：
// --from-account → アカウントの既存投稿（live取得が前提）
// それ以外       → テンプレ経由で投稿した記録（threads-posts.json）
let posts;
if (fromAccount) {
  if (!live) {
    console.log("DRY RUN: --from-account would list and fetch all posts in the account. Add --live to call the Threads API.");
    process.exit(0);
  }
  const accessToken = requiredEnv("THREADS_ACCESS_TOKEN");
  const userId = requiredEnv("THREADS_USER_ID");
  posts = await fetchAccountPosts(userId, accessToken);
  console.log(`Account posts found: ${posts.length}`);
  // ローカル記録（threads-posts.json）のメタを threadsPostId で突き合わせて付与する。
  const metaIndex = buildMetaIndex(await readJson(POSTS_PATH, { posts: [] }));
  const { merged, matched } = mergeMeta(posts, metaIndex);
  posts = merged;
  console.log(`Strategy meta matched from ${POSTS_PATH}: ${matched}/${posts.length}`);
} else {
  const log = await readJson(POSTS_PATH, { posts: [] });
  posts = (log.posts || []).filter((p) => p.threadsPostId);
}

if (!posts.length) {
  console.log("No posts to analyze.");
  console.log(fromAccount ? "The account returned no posts." : `Publish first or use --from-account. source=${POSTS_PATH}`);
  process.exit(0);
}

const results = [];

if (live) {
  const accessToken = requiredEnv("THREADS_ACCESS_TOKEN");
  for (const post of posts) {
    try {
      const metrics = await fetchMetricsForPost(post.threadsPostId, accessToken);
      const body = post.body || "";
      results.push({
        postId: post.threadsPostId,
        strategy: post.strategy ?? null,
        hookType: post.hookType ?? null,
        audience: post.audience ?? null,
        ctaType: post.ctaType ?? null,
        postedAt: post.postedAt,
        chars: [...body].length,
        hasQuestion: /[?？]/.test(body),
        body,
        ...metrics
      });
    } catch (error) {
      console.error(`WARN: failed to fetch ${post.threadsPostId}: ${error.message}`);
    }
  }
} else {
  // ドライラン: APIを叩かず、取得対象のpost一覧だけ表示する。
  console.log(`DRY RUN: would fetch insights for ${posts.length} post(s). Use --live to call the Threads API.`);
  for (const post of posts) {
    console.log(`  - ${post.threadsPostId} (${post.strategy || "no-strategy"})`);
  }
  process.exit(0);
}

const output = {
  _source: fromAccount ? "threads-insights-api:account" : "threads-insights-api",
  updatedAt: now,
  count: results.length,
  posts: results
};

await fs.writeFile(PERFORMANCE_PATH, `${JSON.stringify(output, null, 2)}\n`);
console.log(`Fetched metrics for ${results.length}/${posts.length} post(s).`);
console.log(`recorded=${PERFORMANCE_PATH}`);
