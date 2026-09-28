import fs from "node:fs/promises";

export async function loadLocalEnv(path = ".env.local") {
  let raw;
  try {
    raw = await fs.readFile(path, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return;
    throw error;
  }

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;

    const [key, ...valueParts] = trimmed.split("=");
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
    if (process.env[key]) continue;

    process.env[key] = valueParts.join("=").trim().replace(/^["']|["']$/g, "");
  }
}
