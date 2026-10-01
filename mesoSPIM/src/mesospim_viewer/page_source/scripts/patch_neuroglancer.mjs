/**
 * Opt-in transparent ground for the flat (2D) view, patched into the pinned
 * neuroglancer 2.41.2 -- the same four edits the ZMART viewer 0.2.1 carries
 * (see docs/TRANSPARENT_2D.md at the repository root).
 *
 * Stock neuroglancer paints the slice background opaque and finally forces the
 * whole display's alpha to one, so a host application can never show through
 * where nothing was imaged. With `display.transparentBackground` set by the
 * page, these edits leave alpha at zero outside acquired pixels and at one
 * inside them, whatever the channel weights, and keep an opaque picture
 * opaque under translucent annotations and scale bars. Without the flag the
 * engine behaves exactly as shipped.
 *
 * Every edit is anchored on the stock text and marked once applied, so the
 * script is safe to run twice and fails loudly if the engine version moves.
 * Only frontend modules are touched: nothing here reaches the compiled worker.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const lib = join(here, "..", "node_modules", "neuroglancer", "lib");

const PATCHES = [
  // Keep an opaque image opaque under translucent annotations and scale bars.
  ...[
    { indent: "      ", drawing: "annotations" },
    { indent: "        ", drawing: "scale bars" },
  ].map(({ indent, drawing }) => ({
    file: join(lib, "sliceview", "panel.js"),
    marker: `${indent}// Preserve image alpha under ${drawing}.`,
    anchor: `${indent}gl.blendFunc(\n${indent}  WebGL2RenderingContext.SRC_ALPHA,\n${indent}  WebGL2RenderingContext.ONE_MINUS_SRC_ALPHA\n${indent});`,
    replacement: (anchor) =>
      `${anchor}\n${indent}// Preserve image alpha under ${drawing}.\n${indent}if (this.context.transparentBackground) gl.blendFuncSeparate(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA, gl.ONE, gl.ONE_MINUS_SRC_ALPHA);`,
  })),
  {
    // Do not force the display's alpha to one at the end of a frame.
    file: join(lib, "display_context.js"),
    marker: "if (!this.transparentBackground)",
    anchor: `    this.gl.clearColor(1, 1, 1, 1);
    this.gl.colorMask(false, false, false, true);
    gl.clear(gl.COLOR_BUFFER_BIT);
    this.gl.colorMask(true, true, true, true);`,
    replacement: (anchor) => `    if (!this.transparentBackground) {\n${anchor.replace(/^/gm, "  ")}\n    }`,
  },
  {
    // The slice background is clear, not opaque.
    file: join(lib, "sliceview", "panel.js"),
    marker: "if (this.context.transparentBackground) backgroundColor.fill(0)",
    anchor: "    backgroundColor[3] = 1;",
    replacement: (anchor) => `${anchor}\n    if (this.context.transparentBackground) backgroundColor.fill(0);`,
  },
  {
    // Coverage is binary: acquired pixels are opaque whatever their brightness.
    file: join(lib, "sliceview", "frontend.js"),
    marker: "sampledColor.a = float(sampledColor.a > 0.0)",
    anchor: `  sampledColor = uBackgroundColor;
}
emit(sampledColor * uColorFactor, 0u);`,
    replacement: () => `  sampledColor = uBackgroundColor;
}
// A transparent ground uses binary coverage, independently of channel weights.
if (uBackgroundColor.a == 0.0) sampledColor.a = float(sampledColor.a > 0.0);
emit(sampledColor * uColorFactor, 0u);`,
  },
];

let failed = false;
for (const patch of PATCHES) {
  const held = readFileSync(patch.file, "utf8");
  if (held.includes(patch.marker)) {
    console.log(`already patched: ${patch.file}`);
    continue;
  }
  if (!held.includes(patch.anchor)) {
    console.error(`anchor not found in ${patch.file}: the pinned neuroglancer version has changed`);
    failed = true;
    continue;
  }
  writeFileSync(patch.file, held.replace(patch.anchor, patch.replacement(patch.anchor)));
  console.log(`patched: ${patch.file}`);
}
if (failed) process.exit(1);
