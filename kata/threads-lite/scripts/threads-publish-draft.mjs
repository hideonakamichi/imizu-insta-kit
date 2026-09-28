import fs from "node:fs/promises";
import { loadLocalEnv } from "./lib/load-local-env.mjs";

await loadLocalEnv();

const DRAFTS_PATH = "data/threads-drafts.json";
const POSTS_PATH = "data/threads-posts.json";
const WAIT_SECONDS = Number(process.env.THREADS_PUBLISH_WAIT_SECONDS || 30);
const PUBLISH_RETRIES = Number(process.env.THREADS_PUBLISH_RETRIES || 3);

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  if (value.includes("THAA...") || value.includes("your-") || value.includes("実際の")) {
    throw new Error(`${name} still looks like a placeholder.`);
  }
  return value;
}

function argValue(name) {
  const match = process.argv.find((arg) => arg.startsWith(`${name}=`));
  return match?.slice(name.length + 1);
}

function isLiveMode() {
  if (process.argv.includes("--live")) return true;
  return String(process.env.THREADS_DRY_RUN || "True").toLowerCase() === "false";
}

function hasFlag(name, envName) {
  return process.argv.includes(name) || String(process.env[envName] || "False").toLowerCase() === "true";
}

function shouldSkipPosted() {
  return hasFlag("--skip-posted", "THREADS_SKIP_POSTED");
}

function shouldSkipToday() {
  return hasFlag("--skip-today", "THREADS_SKIP_TODAY");
}

function allowDuplicate() {
  return hasFlag("--allow-duplicate", "THREADS_ALLOW_DUPLICATE");
}

async function parseJsonResponse(response, label) {
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${label} returned non-JSON response (${response.status}): ${text.slice(0, 300)}`);
  }
  if (!response.ok) {
    const error = new Error(`${label} failed (${response.status}): ${JSON.stringify(json)}`);
    error.status = response.status;
    error.payload = json;
    throw error;
  }
  return json;
}

function isTransientApiError(error) {
  const apiError = error?.payload?.error;
  return Boolean(apiError?.is_transient) || Number(error?.status || 0) >= 500;
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

function postKey(item) {
  return [item.topicId ?? "", item.strategy || "", item.body || item.text || ""].join("::");
}

function jstDateKey(value = new Date()) {
  const date = value instanceof Date ? value : new Date(value);
  return new Date(date.getTime() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

function findPostToday(postsLog) {
  const today = jstDateKey();
  return (postsLog?.posts || []).find((item) => item.postedAt && jstDateKey(item.postedAt) === today);
}

function selectDraft(payload, postsLog = null) {
  const draftIndex = Number(argValue("--draft-index") || 0);
  const strategy = argValue("--strategy");
  const postedKeys = new Set((postsLog?.posts || []).map(postKey));

  if (strategy || shouldSkipPosted()) {
    const draft = payload.drafts.find((item) => {
      const strategyMatches = strategy ? item.strategy === strategy : true;
      const notPosted = shouldSkipPosted() ? !postedKeys.has(postKey(item)) : true;
      return strategyMatches && notPosted;
    });
    if (!draft) throw new Error(`まだ投稿していない下書きがありません（strategy=${strategy || "*"}）。Claude Code に「ネタを補充して」と頼んでください。`);
    return draft;
  }

  const draft = payload.drafts[draftIndex];
  if (!draft) throw new Error(`No draft found at --draft-index=${draftIndex}`);
  return draft;
}

async function createContainer({ userId, accessToken, text }) {
  const response = await fetch(`https://graph.threads.net/v1.0/${encodeURIComponent(userId)}/threads`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      media_type: "TEXT",
      text,
      access_token: accessToken
    })
  });
  return parseJsonResponse(response, "Create Threads container");
}

async function publishContainer({ userId, accessToken, creationId }) {
  const response = await fetch(`https://graph.threads.net/v1.0/${encodeURIComponent(userId)}/threads_publish`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      creation_id: creationId,
      access_token: accessToken
    })
  });
  return parseJsonResponse(response, "Publish Threads container");
}

async function publishContainerWithRetry({ userId, accessToken, creationId }) {
  let lastError;
  for (let attempt = 1; attempt <= PUBLISH_RETRIES; attempt += 1) {
    try {
      return await publishContainer({ userId, accessToken, creationId });
    } catch (error) {
      lastError = error;
      if (!isTransientApiError(error) || attempt === PUBLISH_RETRIES) throw error;
      const waitMs = attempt * 15000;
      console.log(`Transient publish error. Retry ${attempt + 1}/${PUBLISH_RETRIES} in ${Math.round(waitMs / 1000)}s.`);
      await sleep(waitMs);
    }
  }
  throw lastError;
}

async function readPostsLog() {
  try {
    return JSON.parse(await fs.readFile(POSTS_PATH, "utf8"));
  } catch {
    return { updatedAt: null, count: 0, posts: [] };
  }
}

function buildPostUrl({ username, postCode }) {
  if (!username || !postCode) return null;
  return `https://www.threads.com/@${username}/post/${postCode}`;
}

async function recordPublishedPost({ draft, userId, creationId, published }) {
  const log = await readPostsLog();
  const now = new Date().toISOString();
  const username = process.env.THREADS_USERNAME?.trim() || null;
  const postCode = published.code || published.permalink_code || null;
  const postUrl = argValue("--post-url") || published.permalink || buildPostUrl({ username, postCode });

  const record = {
    id: published.id,
    threadsPostId: published.id,
    creationId,
    status: "posted",
    postedAt: now,
    postUrl,
    topicId: draft.topicId,
    topicTitle: draft.topicTitle,
    strategy: draft.strategy,
    hookType: draft.hookType,
    audience: draft.audience,
    ctaType: draft.ctaType,
    hypothesis: draft.hypothesis,
    targetMetric: draft.targetMetric,
    metadata: draft.metadata || {},
    body: draft.text,
    chars: [...draft.text].length,
    linkUrl: draft.url,
    threadsUserId: userId,
    rawPublishResponse: published
  };

  const existingIndex = log.posts.findIndex((item) => item.threadsPostId === published.id);
  if (existingIndex >= 0) log.posts[existingIndex] = { ...log.posts[existingIndex], ...record };
  else log.posts.unshift(record);

  log.updatedAt = now;
  log.count = log.posts.length;
  await fs.writeFile(POSTS_PATH, `${JSON.stringify(log, null, 2)}\n`);
  return record;
}

const payload = JSON.parse(await fs.readFile(DRAFTS_PATH, "utf8"));
const postsLog = await readPostsLog();
const postedToday = findPostToday(postsLog);

if (shouldSkipToday() && postedToday) {
  console.log(`SKIP: 今日（日本時間）はもう投稿済みです（${postedToday.threadsPostId || "手で投稿"}）。1日1本までにしています。`);
  process.exit(0);
}

const draft = selectDraft(payload, postsLog);
const live = isLiveMode();

// 手で投稿したあとの記録。API は呼ばない。--skip-posted で「今日の1本」と同じ下書きが選ばれる
if (process.argv.includes("--mark-posted")) {
  const now = new Date().toISOString();
  postsLog.posts = postsLog.posts || [];
  postsLog.posts.unshift({
    id: `manual-${Date.now()}`,
    threadsPostId: null,
    status: "posted-manual",
    postedAt: now,
    postUrl: argValue("--post-url") || null,
    topicId: draft.topicId,
    topicTitle: draft.topicTitle,
    strategy: draft.strategy,
    hookType: draft.hookType,
    audience: draft.audience,
    ctaType: draft.ctaType,
    hypothesis: draft.hypothesis,
    metadata: draft.metadata || {},
    body: draft.text,
    chars: [...draft.text].length
  });
  postsLog.updatedAt = now;
  postsLog.count = postsLog.posts.length;
  await fs.writeFile(POSTS_PATH, `${JSON.stringify(postsLog, null, 2)}
`);
  console.log(`記録しました（${POSTS_PATH}）。この下書きは次から選ばれません。`);
  console.log(draft.text.slice(0, 40) + "…");
  process.exit(0);
}

if ([...draft.text].length > 500) {
  throw new Error(`Draft is too long for Threads: ${[...draft.text].length}/500`);
}

if (live && !allowDuplicate()) {
  const existing = (postsLog.posts || []).find((item) => postKey(item) === postKey(draft));
  if (existing) {
    throw new Error(`This draft already appears to be posted as ${existing.threadsPostId}. Pass --allow-duplicate only if you intentionally want to repost it.`);
  }
}

console.log(`Selected draft: topic=${draft.topicTitle || "daily-topic"} strategy=${draft.strategy} chars=${draft.chars}`);
console.log(draft.text);

if (!live) {
  await fs.mkdir("output", { recursive: true });
  await fs.writeFile("output/today.txt", `${draft.text}
`);
  console.log("");
  console.log("output/today.txt に書き出しました。中身をコピーして Threads アプリに貼ってください。");
  console.log("投稿したら npm run threads:posted で記録します（記録しないと、明日も同じ下書きが出ます）。");
  console.log("（API での投稿はしていません。手で投稿する使い方では、これで正常です）");
  process.exit(0);
}

const accessToken = requiredEnv("THREADS_ACCESS_TOKEN");
const userId = process.env.THREADS_USER_ID || "me";
const existingCreationId = argValue("--creation-id");

let creationId = existingCreationId;
if (creationId) {
  console.log(`Using existing container: ${creationId}`);
} else {
  const container = await createContainer({ userId, accessToken, text: draft.text });
  creationId = container.id;
  console.log(`Container created: ${creationId}. Waiting ${WAIT_SECONDS}s before publish.`);
  await sleep(WAIT_SECONDS * 1000);
}

const published = await publishContainerWithRetry({ userId, accessToken, creationId });
const postRecord = await recordPublishedPost({ draft, userId, creationId, published });
console.log("Threads post published.");
console.log(`threads_post_id=${published.id}`);
console.log(`recorded=${POSTS_PATH}`);
if (postRecord.postUrl) console.log(`post_url=${postRecord.postUrl}`);
