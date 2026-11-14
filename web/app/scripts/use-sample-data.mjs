// Copies sample data to web/public/site_data.json so /story has something to draw.
// Prefers the export agent's data/sample/site_data.sample.json when it exists, else the app fixture.
// Never overwrites a real export unless --force is passed.
import { copyFileSync, existsSync, readFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..", "..");
const dest = join(repo, "web", "public", "site_data.json");
const candidates = [join(repo, "data", "sample", "site_data.sample.json"), join(here, "..", "fixtures", "site_data.sample.json")];
const src = candidates.find(existsSync);
if (!src) { console.error("No sample found. Run `npm run make-fixture` first."); process.exit(1); }
if (existsSync(dest) && !process.argv.includes("--force")) {
  try { if (!JSON.parse(readFileSync(dest, "utf8"))?.story?.sample) { console.error(`${dest} looks like a real export; pass --force to replace it.`); process.exit(1); } } catch { /* unreadable: replace */ }
}
mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`copied ${src} -> ${dest}`);
