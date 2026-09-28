import { loadLocalEnv } from "./lib/load-local-env.mjs";

await loadLocalEnv();

const DEFAULT_SCOPES = [
  "threads_basic",
  "threads_content_publish",
  "threads_manage_insights"
];

function requiredEnv(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required.`);
  return value;
}

const clientId = requiredEnv("THREADS_CLIENT_ID");
const redirectUri = requiredEnv("THREADS_REDIRECT_URI");
const scopes = (process.env.THREADS_SCOPES || DEFAULT_SCOPES.join(","))
  .split(/[,\s]+/)
  .filter(Boolean);
const state = process.env.THREADS_AUTH_STATE || `threads-template-${Date.now()}`;

const url = new URL("https://threads.net/oauth/authorize");
url.searchParams.set("client_id", clientId);
url.searchParams.set("redirect_uri", redirectUri);
url.searchParams.set("scope", scopes.join(","));
url.searchParams.set("response_type", "code");
url.searchParams.set("state", state);

console.log("Open this URL while logged in to the Threads account you want to connect:");
console.log(url.toString());
console.log("");
console.log("After approval, copy the `code` query parameter from the redirect URL.");
console.log(`State: ${state}`);
