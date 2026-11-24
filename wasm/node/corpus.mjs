// Re-verify a corpus of accepted proofs in the WebAssembly build:  node corpus.mjs proofs.json
import { loadPyodide } from "pyodide";
import { readFileSync, readdirSync } from "fs";
const site = new URL("../../site/", import.meta.url).pathname;
const py = await loadPyodide();
await py.loadPackage(["sympy", site + readdirSync(site).find(f => f.endsWith(".whl"))], { messageCallback: () => {} });
const web = py.pyimport("pyra_web");
web.load(false);
const proofs = JSON.parse(readFileSync(process.argv[2], "utf8"));
let ok = 0, n = 0, t0 = Date.now();
for (const [name, code] of Object.entries(proofs)) {
  n++;
  if (process.env.VERBOSE) console.log("RUN", name);
  const r = JSON.parse(web.run(code, "strict", 10));
  const th = r.theorems.find(t => t.name === name) || r.theorems[r.theorems.length - 1];
  const good = th && th.ok && th.verified;
  if (good) ok++;
  else console.log("NOT VERIFIED:", name, (th && th.error || r.error || "no theorem").split("\n")[0].slice(0, 160));
}
console.log(`${ok}/${n} verified in WebAssembly, ${((Date.now() - t0) / 1000).toFixed(0)} s`);
