import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs/promises";

const run = promisify(execFile);

// 完全自動改善ループの「安全ゲート」本体。
// 想定する使い方:
//   1) 分析エージェント（threads-insights-analyst, Write/Edit付与）が
//      performance を読み、改善のために対象ファイルを直接編集する。
//   2) このスクリプトを実行する。編集後の状態が壊れていないかを検証し、
//      壊れていれば編集を自動で巻き戻す。
//
//   npm run threads:improve            … 検証のみ（編集はエージェントが既に済ませた前提）
//   npm run threads:improve -- --check-only  … 検証だけして diff は戻さない
//
// 安全方針:
//   - 自動 push しない／自動 live投稿しない（このスクリプトは投稿APIを一切呼ばない）。
//   - 検証は構文チェック → 実際の下書き生成。どちらか失敗で巻き戻し。
//   - 巻き戻しは git に依存（ベースラインがコミット済みである前提）。

const ROOT = new URL("..", import.meta.url).pathname;

// エージェントが編集してよい範囲（安全のため明示。これ以外が変更されていたら警告）。
const ALLOWED_PATHS = [
  "scripts/generate-drafts.mjs",
  "data/post-plan.json",
  "data/topics.json",
  "data/lessons.json",
  ".claude/skills/threads-draft-generation/SKILL.md",
  ".claude/skills/threads-growth/SKILL.md"
];

function log(msg) {
  console.log(`[improve] ${msg}`);
}

async function git(args) {
  const { stdout } = await run("git", args, { cwd: ROOT });
  return stdout.trim();
}

// このサブツリーで、未コミットの変更があるファイル一覧（リポジトリルート相対）。
async function changedFiles() {
  // --porcelain -z で NUL 区切り。各エントリは "XY <path>\0"。
  // 行頭の状態2文字を全体 trim で削らないよう、trim せず raw を扱う。
  const { stdout } = await run("git", ["status", "--porcelain", "-z", "--", "."], { cwd: ROOT });
  return stdout
    .split("\0")
    .filter(Boolean)
    .map((entry) => entry.slice(3)) // "XY " の3文字を除いた残りがパス
    .filter(Boolean);
}

async function revertChanges() {
  // このディレクトリ配下の追跡ファイルの変更だけを破棄する。
  await git(["checkout", "--", "."]);
}

async function runStep(label, cmd, args) {
  log(`${label} ...`);
  try {
    const { stdout } = await run(cmd, args, { cwd: ROOT });
    const tail = stdout.trim().split("\n").slice(-3).join("\n");
    if (tail) log(`${label} OK: ${tail}`);
    else log(`${label} OK`);
    return true;
  } catch (error) {
    const detail = (error.stderr || error.stdout || error.message || "").trim();
    log(`${label} FAILED: ${detail.split("\n").slice(-5).join("\n")}`);
    return false;
  }
}

const checkOnly = process.argv.includes("--check-only");

// 0) ベースラインが git 管理下にあることを確認（巻き戻しの前提）。
try {
  await git(["rev-parse", "--is-inside-work-tree"]);
} catch {
  log("ERROR: git リポジトリ外です。安全ゲートは git 管理下でのみ動作します。");
  process.exit(1);
}

// 1) 変更ファイルを把握し、許可範囲外の変更が無いかを点検。
const changed = await changedFiles();
if (changed.length === 0) {
  log("変更なし。エージェントがまだ編集していないか、改善案が出なかった。");
  process.exit(0);
}
log(`変更ファイル: ${changed.join(", ")}`);

const subtreePrefix = "training/threads-automation-claude/";
const outOfScope = changed.filter((f) => {
  const rel = f.startsWith(subtreePrefix) ? f.slice(subtreePrefix.length) : f;
  return !ALLOWED_PATHS.includes(rel);
});
if (outOfScope.length > 0) {
  log(`WARNING: 許可範囲外の変更を検出: ${outOfScope.join(", ")}`);
  log("安全のため巻き戻します（ALLOWED_PATHS を見直すか、手動で確認してください）。");
  if (!checkOnly) await revertChanges();
  process.exit(1);
}

// 2) 安全ゲート: 構文チェック → 実際の下書き生成。
const okCheck = await runStep("構文チェック(npm run check)", "npm", ["run", "check"]);
const okDrafts = okCheck && (await runStep("下書き生成(npm run threads:drafts)", "npm", ["run", "threads:drafts"]));

if (!okCheck || !okDrafts) {
  if (checkOnly) {
    log("検証に失敗しましたが --check-only のため巻き戻しません。手動で確認してください。");
    process.exit(1);
  }
  log("検証に失敗。エージェントの変更を巻き戻します。");
  await revertChanges();
  log("巻き戻し完了。系は安全な状態に戻りました。");
  process.exit(1);
}

// 3) 成功: 生成された下書きの妥当性を軽く確認（500字超や空が無いか）。
const drafts = JSON.parse(await fs.readFile(`${ROOT}data/threads-drafts.json`, "utf8"));
const tooLong = (drafts.drafts || []).filter((d) => [...(d.text || "")].length > 500);
const empty = (drafts.drafts || []).filter((d) => !(d.text || "").trim());
if (tooLong.length || empty.length) {
  log(`WARNING: 生成物に問題（500字超=${tooLong.length}, 空=${empty.length}）。巻き戻します。`);
  if (!checkOnly) await revertChanges();
  process.exit(1);
}

log(`検証成功。下書き ${drafts.drafts.length} 件を生成。hasData=${drafts.performanceSummary?.hasData}`);
log("--- 変更内容(git diff) ---");
const diff = await git(["diff", "--stat", "--", "."]);
console.log(diff || "(差分なし)");
log("自動 push / 自動 live投稿はしません。内容を確認の上、必要なら手動でコミット・投稿してください。");
