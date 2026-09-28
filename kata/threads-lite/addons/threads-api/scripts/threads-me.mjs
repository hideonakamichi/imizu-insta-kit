import { loadLocalEnv } from "./lib/load-local-env.mjs";

await loadLocalEnv();

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  if (value.includes("THAA...") || value.includes("実際の")) {
    throw new Error(`${name} still looks like a placeholder.`);
  }
  return value;
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

const accessToken = requiredEnv("THREADS_ACCESS_TOKEN");
const url = new URL("https://graph.threads.net/v1.0/me");
url.searchParams.set("fields", "id,username");
url.searchParams.set("access_token", accessToken);

const profile = await parseJsonResponse(await fetch(url), "Threads profile request");

console.log("Threads connection OK.");
console.log(`THREADS_USER_ID=${profile.id}`);
if (profile.username) console.log(`username=${profile.username}`);
