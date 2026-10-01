// Pre-compile neuroglancer's background workers before the app is built.
//
// Why this exists: neuroglancer ships its two worker entry points
// (chunk_worker.bundle.js and async_computation.bundle.js) as tiny *source*
// stubs — each is just a list of `#src/...` imports that only a bundler can
// resolve. Vite, when it meets `new Worker(new URL(...))` inside a dependency,
// does not run those stubs through its own worker compiler; it copies the raw
// stub verbatim. A browser cannot resolve `#src/...`, so the worker throws on
// load, never signals "ready", and — because the main thread queues all
// messages until the worker is ready — the whole data-loading half of the
// viewer silently does nothing. The image never appears.
//
// The fix is to compile those two entry points ourselves, with esbuild, into
// self-contained bundles (all `#src/...` imports resolved and inlined) and put
// them where neuroglancer expects them. Then Vite simply copies a real,
// working worker. This script runs automatically before every build.

import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { rename } from "node:fs/promises";
import { statSync } from "node:fs";

const here = dirname(fileURLToPath(import.meta.url));
const lib = join(here, "..", "node_modules", "neuroglancer", "lib");

// The two worker entry points neuroglancer launches at runtime.
const workers = ["chunk_worker.bundle.js", "async_computation.bundle.js"];

for (const name of workers) {
  const entry = join(lib, name);
  // Compile to a temporary file first, then overwrite the stub — esbuild cannot
  // safely read and write the same path in one step.
  const out = join(lib, name.replace(".js", ".compiled.js"));
  await build({
    entryPoints: [entry],
    bundle: true,
    format: "esm", // the workers are ES-module workers ({type:"module"})
    outfile: out,
    logLevel: "error",
    // Resolve neuroglancer's "#src/*" and "#datasource/*" subpath imports via
    // its package.json "imports" map (the "default" condition).
    conditions: ["default"],
    legalComments: "none",
    // The workers run in the Data viewer window too, Qt WebEngine 5.15 (Chromium
    // 83): its syntax, and the browser features it lacks, put first.
    target: "chrome83",
    inject: [join(here, "..", "src", "legacy_browser.js")],
  });
  await rename(out, entry);
  const kb = Math.round(statSync(entry).size / 1024);
  if (kb < 50) {
    throw new Error(
      `Worker ${name} compiled to only ${kb} KB — expected a few hundred KB. ` +
        `The bundle is probably still the unresolved stub; the viewer would ` +
        `load but never show pixels. Aborting.`,
    );
  }
  console.log(`compiled worker ${name}: ${kb} KB`);
}
