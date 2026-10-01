// After the app is built, place neuroglancer's second worker where it is loaded.
//
// neuroglancer uses a second kind of background worker for decompression
// ("async computation" — e.g. unpacking the blosc-compressed image chunks).
// The main chunk worker loads it at runtime from "../async_computation.bundle.js"
// relative to its own location, which resolves to the site root
// (/async_computation.bundle.js). Vite does not emit that file on its own (for
// the same reason it does not compile the workers — see precompile-workers.mjs), so
// without this step the decompression worker 404s: image chunks are fetched but
// never decoded, and the picture never fills in.
//
// precompile-workers.mjs has already compiled a real, self-contained
// async_computation.bundle.js into neuroglancer's lib folder. Here we simply
// copy that compiled worker into dist at the path the chunk worker asks for.

import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { copyFile, stat } from "node:fs/promises";

const here = dirname(fileURLToPath(import.meta.url));
const src = join(here, "..", "node_modules", "neuroglancer", "lib", "async_computation.bundle.js");
const dst = join(here, "..", "..", "page", "async_computation.bundle.js");

const { size } = await stat(src);
if (size < 50 * 1024) {
  throw new Error(
    `async_computation.bundle.js is only ${Math.round(size / 1024)} KB — it looks ` +
      `like the uncompiled stub. Run precompile-workers.mjs first (the build script does).`,
  );
}
await copyFile(src, dst);
console.log(`placed async_computation worker into dist (${Math.round(size / 1024)} KB)`);
