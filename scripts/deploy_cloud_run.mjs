import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const project = process.env.GOOGLE_CLOUD_PROJECT_ID || process.env.GOOGLE_CLOUD_PROJECT || "project-8a5841fe-0024-4917-95b";
const region = process.env.GOOGLE_CLOUD_REGION || "asia-northeast1";
const service = process.env.CLOUD_RUN_SERVICE || "dockmind";

function readDotenv() {
  const env = {};
  if (!fs.existsSync(".env")) return env;
  for (const raw of fs.readFileSync(".env", "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) continue;
    const index = line.indexOf("=");
    const key = line.slice(0, index).trim();
    const value = line.slice(index + 1).trim().replace(/^['"`]|['"`]$/g, "");
    env[key] = value;
  }
  return env;
}

function yamlQuote(value) {
  return String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

const env = { ...readDotenv(), ...process.env };
env.QWEN_MODEL ||= "qwen-plus,qwen-turbo,qwen-max";
env.GBRAIN_ENABLED ||= "true";

const keys = [
  "QWEN_API_KEY",
  "QWEN_MODEL",
  "CRUSTDATA_API_KEY",
  "SHISA_API_KEY",
  "SHISA_API_URL",
  "GBRAIN_ENABLED",
];

const envFile = path.join(os.tmpdir(), `dockmind-cloudrun-env-${process.pid}.yaml`);
const lines = keys.filter((key) => env[key]).map((key) => `${key}: "${yamlQuote(env[key])}"`);

if (!env.QWEN_API_KEY) {
  console.error("QWEN_API_KEY is missing from .env or process env.");
  process.exit(1);
}

try {
  fs.writeFileSync(envFile, `${lines.join("\n")}\n`, { mode: 0o600 });
  const args = [
    "run",
    "deploy",
    service,
    "--source",
    ".",
    "--region",
    region,
    "--project",
    project,
    "--allow-unauthenticated",
    "--env-vars-file",
    envFile,
    "--memory",
    "4Gi",
    "--cpu",
    "2",
    "--timeout",
    "300",
    "--quiet",
  ];
  const result = spawnSync("gcloud", args, { stdio: "inherit" });
  process.exitCode = result.status ?? 1;
} finally {
  try {
    fs.unlinkSync(envFile);
  } catch {
    // Best effort cleanup only.
  }
}
