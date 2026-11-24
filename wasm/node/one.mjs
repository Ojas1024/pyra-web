// Verify one proof in a fresh Pyodide: node one.mjs proofs.json NAME [timeout]  -> prints a JSON line
import { loadPyodide } from "pyodide";
import { readFileSync, readdirSync } from "fs";
const site = new URL("../../site/", import.meta.url).pathname;
const py = await loadPyodide();
await py.loadPackage(["sympy", site + readdirSync(site).find(f => f.endsWith(".whl"))], { messageCallback: () => {} });
py.FS.writeFile("/tmp/pyra_supplement.ndjson.gz", readFileSync(site + "pyra_supplement.ndjson.gz"));
py.runPython("import os; os.environ['PYRA_WEB_SUPPLEMENT'] = '/tmp/pyra_supplement.ndjson.gz'");
const web = py.pyimport("pyra_web"); web.load(false);
const name = process.argv[3], code = JSON.parse(readFileSync(process.argv[2], "utf8"))[name];
let out = { name };
try {
  const t0 = Date.now();
  const r = JSON.parse(web.run(code, "strict", +(process.argv[4] || 10)));
  const th = r.theorems.find(t => t.name === name) || r.theorems.at(-1);
  out.verified = !!(th && th.ok && th.verified); out.seconds = (Date.now() - t0) / 1000;
  if (!out.verified) out.error = ((th && (th.error || "")) || r.error || "").split("\n").slice(0, 3).join(" | ").slice(0, 300);
} catch (e) { out.verified = false; out.error = String(e.message || e).slice(0, 120); }
console.log("@@" + JSON.stringify(out));
process.exit(0);
