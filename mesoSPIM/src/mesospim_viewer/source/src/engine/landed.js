/**
 * In the page: pass on to the engine's chunk worker which files have landed.
 *
 * Python names a store by the first two parts of its address (`data/3`, or
 * `live/live-2` for a stack shown from memory) and lists the files; every
 * chunk source the engine holds over that store -- one per copy of the image
 * pyramid -- is told, and reads again just the chunks that come from those
 * files (worker_landed.js).
 */
// The same names as in worker_landed.js.
const LANDED_RPC_ID = "mesospim.landed";
const WANT_RPC_ID = "mesospim.want";
const ON_THE_CARD = 0; // the engine's ChunkState.GPU_MEMORY

function pathOf(url) {
  try {
    return new URL(url, window.location.href).pathname;
  } catch {
    return "";
  }
}

/** Every chunk source the engine holds, with the path part of its address. */
function* chunkSources(viewer) {
  for (const source of viewer.chunkManager.memoize.map.values()) {
    const url = source?.parameters?.url;
    if (typeof url !== "string" || source.rpcId == null || !source.rpc) continue;
    yield [source, pathOf(url)];
  }
}

/**
 * `store` is `data/<key>`; a store read again after its shape changed is
 * `data/<key>.<revision>` in the engine's addresses, and is meant as well.
 * Without `files`, everything found missing in the store is read again.
 */
export function landed(viewer, store, files) {
  const whole = `/${store}/`;
  const revised = `/${store}.`;
  for (const [source, path] of chunkSources(viewer)) {
    if (!path.startsWith(whole) && !path.startsWith(revised)) continue;
    const prefix = `${path.split("/").slice(1, 3).join("/")}/`;
    source.rpc.invoke(LANDED_RPC_ID, { source: source.rpcId, prefix, files });
  }
}

/** Read again every chunk that was found missing, in every store. */
export function landedAnywhere(viewer) {
  for (const [source, path] of chunkSources(viewer)) {
    const prefix = `${path.split("/").slice(1, 3).join("/")}/`;
    source.rpc.invoke(LANDED_RPC_ID, { source: source.rpcId, prefix });
  }
}

function sourcesOf(viewer, store) {
  const whole = `/${store}/`;
  const revised = `/${store}.`;
  const found = [];
  for (const [source, path] of chunkSources(viewer)) {
    if (path.startsWith(whole) || path.startsWith(revised)) found.push(source);
  }
  return found;
}

/**
 * Have the engine load chunks of a store before the view goes to them, as if
 * they were on screen: `positions` are places in the store's grid of chunks, in
 * the engine's order (x, y, z, then the others). An empty list lets them go.
 */
export function want(viewer, store, positions) {
  for (const source of sourcesOf(viewer, store)) {
    source.rpc.invoke(WANT_RPC_ID, { source: source.rpcId, positions });
  }
}

/**
 * Whether a chunk of a store is loaded and ready to draw. A chunk the engine
 * asked for before its file was there counts as loaded too, only with nothing
 * in it: that one is not ready.
 */
export function isLoaded(viewer, store, position) {
  const key = position.join();
  return sourcesOf(viewer, store).some((source) => {
    const chunk = source.chunks?.get(key);
    return chunk !== undefined && chunk.state === ON_THE_CARD && chunk.data != null;
  });
}
