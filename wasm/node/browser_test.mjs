// End-to-end test of web/site in headless Chrome:  node browser_test.mjs http://localhost:PORT/ [proofs.json name]
import puppeteer from "puppeteer-core";
import { readFileSync } from "fs";
const [url, proofsFile, proofName] = process.argv.slice(2);
const exe = new URL("./chrome/chrome-headless-shell/linux-158.0.8127.36/chrome-headless-shell-linux64/chrome-headless-shell", import.meta.url).pathname;
const browser = await puppeteer.launch({ executablePath: exe, args: ["--no-sandbox"], protocolTimeout: 900000 });
const page = await browser.newPage();
await page.setViewport({ width: 1400, height: 950 });
page.on("console", (m) => { if (m.type() === "error") console.log("console error:", m.text().slice(0, 200)); });
page.on("pageerror", (e) => console.log("page error:", e.message.slice(0, 200)));
let t0 = Date.now();
await page.goto(url, { waitUntil: "domcontentloaded" });
await page.waitForFunction(() => document.getElementById("status").textContent.startsWith("Ready"), { timeout: 300000 });
console.log("ready after", (Date.now() - t0) / 1000, "s:", await page.$eval("#loadstats", (e) => e.textContent));
async function runCode(code, mode = "strict") {
  await page.evaluate((c) => document.querySelector(".CodeMirror").CodeMirror.setValue(c), code);
  await page.select("#mode", mode);
  const t = Date.now();
  await page.click("#run");
  await page.waitForFunction(() => document.getElementById("run").textContent === "Run" && !document.querySelector("#results .empty"), { timeout: 600000 });
  const summary = await page.$eval("#results", (e) => e.innerText.split("\n").slice(0, 6).join(" | "));
  return [(Date.now() - t) / 1000, summary];
}
const examples = await page.$$eval("#examples option", (os) => os.map((o) => o.value));
for (const ex of examples) {
  const code = await page.evaluate((n) => PYRA_EXAMPLES[n], ex);
  const [s, summary] = await runCode(code);
  console.log(`[${ex}] ${s}s: ${summary.slice(0, 220)}`);
  if (ex.startsWith("A false step")) await page.screenshot({ path: "screenshot_false_step.png" });
}
if (proofsFile) {
  const code = JSON.parse(readFileSync(proofsFile, "utf8"))[proofName];
  const [s, summary] = await runCode(code);
  console.log(`[${proofName}] ${s}s: ${summary.slice(0, 300)}`);
  await page.waitForFunction(() => document.getElementById("status").textContent.startsWith("Ready"), { timeout: 300000 });
  const [s2, summary2] = await runCode(await page.evaluate(() => PYRA_EXAMPLES["Linear system (miniF2F style)"]));
  console.log(`[after restart] ${s2}s: ${summary2.slice(0, 200)}`);
}
await page.screenshot({ path: "screenshot.png" });
await browser.close();
