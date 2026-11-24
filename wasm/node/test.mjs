// Smoke test of the Pyra wheel in Pyodide under Node:  node web/wasm/node/test.mjs [file.py] [mode]
import { loadPyodide } from "pyodide";
import { readFileSync, readdirSync } from "fs";
const site = new URL("../../site/", import.meta.url).pathname;
const whl = readdirSync(site).find(f => f.endsWith(".whl"));
const t0 = Date.now();
const py = await loadPyodide();
await py.loadPackage(["sympy", site + whl]);
console.log("pyodide + wheel", (Date.now() - t0) / 1000, "s");
const web = py.pyimport("pyra_web");
let t = Date.now();
console.log("load", web.load(process.env.FULL === "1"), (Date.now() - t) / 1000, "s");
const src = process.argv[2] ? readFileSync(process.argv[2], "utf8") :
`from pyra import prove, Real

@prove
def example(x: Real, y: Real, h0: "x + y == 7", h1: "3 * x + y == 45"):
    assert x == 19
    assert x ** 2 - y ** 2 == 217

@prove
def wrong(x: Real):
    assert x * x >= 0
    assert x + 1 > x + 2
`;
t = Date.now();
const r = JSON.parse(web.run(src, process.argv[3] || "strict"));
console.log("run", (Date.now() - t) / 1000, "s", r.error);
for (const th of r.theorems)
  console.log(" ", th.name, th.ok, th.verified, th.steps.map(s => [s.line, s.badge, s.stage]), (th.error || "").slice(0, 120));
