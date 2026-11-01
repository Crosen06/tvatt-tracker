// Bundles the SPA into backend/app/static. Usage: node build.mjs [--watch]
// Uses ./node_modules when present, otherwise falls back to NODE_TOOLS (a shared node_modules dir).
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "../backend/app/static");
const fallback = process.env.NODE_TOOLS || "/opt/npm-tools/node_modules";
const nodePaths = existsSync(path.join(here, "node_modules")) ? [] : [fallback];
const require = createRequire(nodePaths.length ? path.join(fallback, "x.js") : import.meta.url);
const esbuild = require("esbuild");

const options = {
  entryPoints: { app: path.join(here, "src/main.jsx") },
  bundle: true,
  minify: true,
  sourcemap: false,
  format: "esm",
  target: ["chrome100", "safari15", "firefox100"],
  jsx: "automatic",
  loader: { ".jsx": "jsx" },
  nodePaths,
  external: ["/fonts/*"],
  define: { "process.env.NODE_ENV": '"production"' },
  outdir: out,
  entryNames: "[name]",
  write: true,
  logLevel: "info",
};

function writeIndex() {
  const js = readFileSync(path.join(out, "app.js"));
  const css = existsSync(path.join(out, "app.css")) ? readFileSync(path.join(out, "app.css")) : Buffer.from("");
  const hash = createHash("sha1").update(js).update(css).digest("hex").slice(0, 10);
  const html = readFileSync(path.join(here, "src/index.html"), "utf8").replaceAll("__V__", hash);
  writeFileSync(path.join(out, "index.html"), html);
  cpSync(path.join(here, "public"), out, { recursive: true });
}

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context({
    ...options,
    plugins: [{ name: "index", setup: (b) => b.onEnd(() => writeIndex()) }],
  });
  await ctx.watch();
} else {
  await esbuild.build(options);
  writeIndex();
}
