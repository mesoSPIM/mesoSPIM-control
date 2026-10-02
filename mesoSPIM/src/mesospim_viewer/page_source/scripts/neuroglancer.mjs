/**
 * What the build does to the pinned neuroglancer 2.41.2, as one Vite plugin.
 *
 * Two things, both done while the page is built and never by editing the
 * installed engine in `node_modules`: what is installed stays exactly as npm
 * put it there, so building twice, or on another machine after `npm ci`,
 * makes the same page.
 *
 * 1. The background workers. neuroglancer ships its two worker entry points
 *    (chunk_worker.bundle.js, which fetches image chunks, and
 *    async_computation.bundle.js, which decompresses them) as tiny source
 *    stubs: lists of `#src/...` imports that only a bundler resolves. Vite
 *    copies such a stub as it is, a browser cannot resolve it, the worker
 *    never starts and the picture never fills in. So both are compiled here
 *    with esbuild into self-contained files at the page's root, made for the
 *    Data viewer window's Qt WebEngine 5.15 (Chromium 83) with the shims of
 *    src/legacy_browser.js put first, and the engine is pointed at them. The
 *    chunk worker asks for "../async_computation.bundle.js" next to itself,
 *    which from the root is the root.
 *
 * 2. An opt-in transparent ground for the flat (2D) view -- the same four
 *    edits the ZMART viewer 0.2.1 carries (see docs/TRANSPARENT_2D.md at the
 *    repository root). Stock neuroglancer paints the slice background opaque
 *    and finally forces the whole display's alpha to one, so a host
 *    application can never show through where nothing was imaged. With
 *    `display.transparentBackground` set by the page, these edits leave alpha
 *    at zero outside acquired pixels and at one inside them, whatever the
 *    channel weights, and keep an opaque picture opaque under translucent
 *    annotations and scale bars. Without the flag the engine behaves exactly
 *    as shipped. Only frontend modules are touched: nothing here reaches the
 *    workers.
 *
 * Every edit is anchored on the stock text, and the build stops with a message
 * when an anchor is missing: the pinned engine version has then moved.
 */
import { build } from "esbuild";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const lib = join(here, "..", "node_modules", "neuroglancer", "lib");
const shims = join(here, "..", "src", "legacy_browser.js");

const WORKERS = ["chunk_worker.bundle.js", "async_computation.bundle.js"];

// Each edit: the module it applies to (inside neuroglancer/lib), the stock text
// it is anchored on, and what that text becomes.
const PATCHES = [
  // Keep an opaque image opaque under translucent annotations and scale bars.
  ...[
    { indent: "      ", drawing: "annotations" },
    { indent: "        ", drawing: "scale bars" },
  ].map(({ indent, drawing }) => ({
    module: "sliceview/panel.js",
    anchor: `${indent}gl.blendFunc(\n${indent}  WebGL2RenderingContext.SRC_ALPHA,\n${indent}  WebGL2RenderingContext.ONE_MINUS_SRC_ALPHA\n${indent});`,
    replacement: (anchor) =>
      `${anchor}\n${indent}// Preserve image alpha under ${drawing}.\n${indent}if (this.context.transparentBackground) gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);`,
  })),
  {
    // Do not force the display's alpha to one at the end of a frame.
    module: "display_context.js",
    anchor: `    this.gl.clearColor(1, 1, 1, 1);
    this.gl.colorMask(false, false, false, true);
    gl.clear(gl.COLOR_BUFFER_BIT);
    this.gl.colorMask(true, true, true, true);`,
    replacement: (anchor) => `    if (!this.transparentBackground) {\n${anchor.replace(/^/gm, "  ")}\n    }`,
  },
  {
    // The slice background is clear, not opaque.
    module: "sliceview/panel.js",
    anchor: "    backgroundColor[3] = 1;",
    replacement: (anchor) => `${anchor}\n    if (this.context.transparentBackground) backgroundColor.fill(0);`,
  },
  {
    // Coverage is binary: acquired pixels are opaque whatever their brightness.
    module: "sliceview/frontend.js",
    anchor: `  sampledColor = uBackgroundColor;
}
emit(sampledColor * uColorFactor, 0u);`,
    replacement: () => `  sampledColor = uBackgroundColor;
}
// A transparent ground uses binary coverage, independently of channel weights.
if (uBackgroundColor.a == 0.0) sampledColor.a = float(sampledColor.a > 0.0);
emit(sampledColor * uColorFactor, 0u);`,
  },
  {
    // The chunk worker is the one compiled here, at the page's root.
    module: "data_management_context.js",
    anchor: 'new URL("./chunk_worker.bundle.js", import.meta.url)',
    replacement: () => 'new URL("/chunk_worker.bundle.js", self.location.href)',
  },
];

/** One worker entry point, compiled into one self-contained file, as text. */
async function compileWorker(name) {
  const result = await build({
    entryPoints: [join(lib, name)],
    bundle: true,
    format: "esm", // the workers are ES-module workers ({type:"module"})
    outfile: name,
    write: false,
    logLevel: "error",
    // Resolve neuroglancer's "#src/*" and "#datasource/*" subpath imports via
    // its package.json "imports" map (the "default" condition).
    conditions: ["default"],
    legalComments: "none",
    target: "chrome83",
    inject: [shims],
  });
  const text = result.outputFiles[0].text;
  if (text.length < 50 * 1024) {
    throw new Error(
      `Worker ${name} compiled to only ${Math.round(text.length / 1024)} KB -- expected a few ` +
        `hundred KB. It is probably still the unresolved stub; the viewer would load but ` +
        `never show pixels.`,
    );
  }
  return text;
}

/** The module path inside neuroglancer/lib that a Vite module id names, or null. */
function engineModule(id) {
  const path = id.split("?")[0].replace(/\\/g, "/");
  const at = path.lastIndexOf("/neuroglancer/lib/");
  return at === -1 ? null : path.slice(at + "/neuroglancer/lib/".length);
}

export function neuroglancerForQt() {
  let command = "build";
  const applied = new Set();
  return {
    name: "mesospim-neuroglancer-for-qt",
    enforce: "pre",
    configResolved(config) {
      command = config.command;
    },
    transform(code, id) {
      const module = engineModule(id);
      const patches = PATCHES.filter((patch) => patch.module === module);
      if (patches.length === 0) return null;
      let patched = code;
      for (const patch of patches) {
        if (!patched.includes(patch.anchor)) {
          this.error(`anchor not found in neuroglancer/lib/${module}: the pinned neuroglancer version has changed`);
        }
        patched = patched.replace(patch.anchor, patch.replacement(patch.anchor));
        applied.add(patch);
      }
      return { code: patched, map: null };
    },
    async generateBundle() {
      const missed = PATCHES.filter((patch) => !applied.has(patch));
      if (missed.length) {
        this.error(`never reached: neuroglancer/lib/${missed.map((patch) => patch.module).join(", ")}`);
      }
      for (const name of WORKERS) {
        this.emitFile({ type: "asset", fileName: name, source: await compileWorker(name) });
      }
    },
    configureServer(server) {
      // Under `vite dev`, the workers are compiled when first asked for.
      const compiled = new Map();
      server.middlewares.use(async (request, response, next) => {
        const name = request.url?.split("?")[0].slice(1);
        if (!WORKERS.includes(name) || command !== "serve") return next();
        try {
          if (!compiled.has(name)) compiled.set(name, await compileWorker(name));
          response.setHeader("Content-Type", "text/javascript");
          response.end(compiled.get(name));
        } catch (error) {
          next(error);
        }
      });
    },
  };
}
