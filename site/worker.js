// Pyra in a Web Worker: Pyodide (CPython on WebAssembly) + the Pyra kernel/elaborator compiled to WebAssembly.
// Messages in:  {type: "init", fullCheck}  |  {type: "run", id, source, mode, timeout}
// Messages out: {type: "status", text} | {type: "ready", stats} | {type: "result", id, result} | {type: "error", id?, text}
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.8/full/";
const WHEEL = "pyra-0.5.2-cp312-cp312-pyodide_2024_0_wasm32.whl";
importScripts(PYODIDE + "pyodide.js");

let py = null, web = null;
const status = (text) => postMessage({ type: "status", text });

async function init(fullCheck) {
  const t0 = performance.now();
  status("Starting Python (Pyodide)…");
  py = await loadPyodide({ indexURL: PYODIDE });
  status("Downloading the Pyra kernel (WebAssembly) and the Lean core + Mathlib library…");
  await py.loadPackage(["sympy", new URL(WHEEL, self.location.href).href], { messageCallback: () => {} });
  status(fullCheck ? "Re-checking every library declaration in the kernel (several minutes)…"
                   : "Loading 33,128 Lean core + Mathlib declarations into the kernel…");
  web = py.pyimport("pyra_web");
  const stats = JSON.parse(web.load(!!fullCheck));
  stats.total_seconds = Math.round((performance.now() - t0) / 100) / 10;
  postMessage({ type: "ready", stats });
}

self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    if (m.type === "init") await init(m.fullCheck);
    else if (m.type === "run") {
      const result = JSON.parse(web.run(m.source, m.mode || "strict", m.timeout || 30));
      postMessage({ type: "result", id: m.id, result });
    }
  } catch (e) {
    const text = String(e && e.message || e);
    // A JavaScript-engine stack overflow (or memory fault) inside the kernel leaves Pyodide unusable:
    // the page restarts the worker.
    const fatal = !!(e && e.pyodide_fatal_error) || /fatally failed|Maximum call stack|memory access out of bounds/.test(text);
    postMessage({ type: fatal ? "fatal" : "error", id: m.id, text });
  }
};
