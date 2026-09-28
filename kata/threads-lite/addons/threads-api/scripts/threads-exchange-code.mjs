import { loadLocalEnv } from "./lib/load-local-env.mjs";

await loadLocalEnv();

const codeArg = process.argv.find((arg) => arg.startsWith("--code="));
const shouldPrintToken = process.argv.includes("--print-token");

function requiredEnv(name) {
  const value = process.env[name]?.trim();
  if (!value) throw new Error(`${name} is required.`);
  if (value.includes("your-") || value.includes("実際の")) {
    throw new Error(`${name} still looks like a placeholder.`);
  }
  return value;
}

function mask(value) {
  if (!value || value.length < 12) return "****";
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
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

const clientId = requiredEnv("THREADS_CLIENT_ID");
const clientSecret = requiredEnv("THREADS_CLIENT_SECRET");
const redirectUri = requiredEnv("THREADS_REDIRECT_URI");
const code = codeArg?.split("=")[1] || process.env.THREADS_AUTH_CODE;

if (!code) throw new Error("Authorization code is required. Pass --code=... or set THREADS_AUTH_CODE.");

const tokenResponse = await fetch("https://graph.threads.net/oauth/access_token", {
  method: "POST",
  headers: { "content-type": "application/x-www-form-urlencoded" },
  body: new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: "authorization_code",
    redirect_uri: redirectUri,
    code
  })
});

const shortLived = await parseJsonResponse(tokenResponse, "Short-lived token exchange");

const longLivedUrl = new URL("https://graph.threads.net/access_token");
longLivedUrl.searchParams.set("grant_type", "th_exchange_token");
longLivedUrl.searchParams.set("client_secret", clientSecret);
longLivedUrl.searchParams.set("access_token", shortLived.access_token);

const longLived = await parseJsonResponse(await fetch(longLivedUrl), "Long-lived token exchange");

console.log("Threads token exchange succeeded.");
console.log(`THREADS_ACCESS_TOKEN=${shouldPrintToken ? longLived.access_token : mask(longLived.access_token)}`);
if (longLived.expires_in) {
  const expiresAt = new Date(Date.now() + Number(longLived.expires_in) * 1000).toISOString();
  console.log(`expires_in=${longLived.expires_in}`);
  console.log(`expires_at=${expiresAt}`);
}
console.log("");
console.log("By default the token is masked. Re-run with --print-token only when you are ready to place it in a secret store.");
