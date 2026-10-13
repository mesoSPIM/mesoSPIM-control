/**
 * In the engine's chunk worker: read again only what has landed on disk.
 *
 * The engine remembers every chunk it asked for, the ones that were not there
 * included: a chunk of a tile the microscope has not written yet is kept as
 * "empty" for as long as the page lives. Stock neuroglancer can only forget a
 * whole source at once, which blanks the tile and fetches all of it again.
 *
 * Here each chunk remembers the file it was read from, and one message names
 * the files that have appeared since: exactly the chunks that were found
 * missing in those files are queued again. A chunk that was read with data in
 * it stays on the graphics card -- the writers write a file once, and the page
 * often reads a file before it is told of it -- so nothing flashes, and nothing
 * that is still missing is asked for twice.
 *
 * Nothing in the installed engine is edited: the zarr source's download is
 * wrapped here, in the worker bundle the build compiles (scripts/neuroglancer.mjs).
 */
import { ChunkPriorityTier, ChunkState } from "neuroglancer/unstable/chunk_manager/base.js";
import { ZarrVolumeChunkSource } from "neuroglancer/unstable/datasource/zarr/backend.js";
import { registerRPC } from "neuroglancer/unstable/worker_rpc.js";

export const LANDED_RPC_ID = "mesospim.landed";
export const WANT_RPC_ID = "mesospim.want";

// The chunk whose download has just begun: the key it asks its store for is
// worked out before the download first waits, so it is caught synchronously.
let starting = null;

function rememberKeys(store) {
  if (store.mesospimKeys) return;
  store.mesospimKeys = true;
  const stock = store.getChunkKey;
  store.getChunkKey = (position, baseKey) => {
    const key = stock(position, baseKey);
    // A chunk inside a shard is read from the shard's file.
    let file = key;
    while (typeof file !== "string") file = file.base;
    if (starting !== null) starting.fileKey = file;
    return key;
  };
}

const stockDownload = ZarrVolumeChunkSource.prototype.download;
ZarrVolumeChunkSource.prototype.download = function download(chunk, signal) {
  rememberKeys(this.chunkKvStore);
  chunk.absent = false;
  starting = chunk;
  let pending;
  try {
    pending = stockDownload.call(this, chunk, signal);
  } finally {
    starting = null;
  }
  return pending.then(
    () => {
      // No file, or a shard without this chunk: the engine draws nothing for it.
      chunk.absent = chunk.data === null;
    },
    (error) => {
      // Half-written or unreadable: worth another try when the file is named again.
      chunk.absent = true;
      throw error;
    },
  );
};

function forgetShardIndexes(store, files) {
  // A sharded store keeps each shard's index, the missing ones as "no shard".
  for (let level = store.kvStore; level?.indexCache; level = level.base) {
    for (const [key, cached] of level.indexCache.chunks) {
      let file;
      try {
        file = JSON.parse(key);
      } catch {
        continue;
      }
      if (typeof file === "string" && files(file)) cached.asyncMemoize = undefined;
    }
  }
}

function readAgain(manager, chunk) {
  switch (chunk.state) {
    case ChunkState.QUEUED:
      return;
    case ChunkState.DOWNLOADING: {
      const controller = chunk.downloadAbortController;
      chunk.downloadAbortController = undefined;
      controller?.abort(new DOMException("chunk download cancelled", "AbortError"));
      break;
    }
    case ChunkState.GPU_MEMORY:
      manager.freeChunkGPUMemory(chunk);
    // fallthrough
    case ChunkState.SYSTEM_MEMORY_WORKER:
    case ChunkState.SYSTEM_MEMORY:
      manager.freeChunkSystemMemory(chunk);
      break;
  }
  manager.updateChunkState(chunk, ChunkState.QUEUED);
}

/**
 * `{ source, prefix, files }`: of the chunk source `source`, read again the
 * chunks whose file, below `prefix`, is listed in `files`. Without `files`,
 * every chunk that was found missing is read again.
 */
registerRPC(LANDED_RPC_ID, function landed(x) {
  const source = this.get(x.source);
  if (source === undefined || source.chunks === undefined) return;
  const prefix = x.prefix ?? "";
  const listed = x.files ? new Set(x.files) : null;
  // The store's own part of the address, wherever the engine's key begins.
  const named = (file) => {
    if (typeof file !== "string") return false;
    const at = file.indexOf(prefix);
    return at !== -1 && (listed === null || listed.has(file.slice(at + prefix.length)));
  };
  if (source.chunkKvStore) forgetShardIndexes(source.chunkKvStore, named);
  const manager = source.chunkManager.queueManager;
  let any = false;
  for (const chunk of Array.from(source.chunks.values())) {
    if (chunk.fileKey === undefined || !named(chunk.fileKey)) continue;
    // Read, with data in it: it stays. One whose download is still going on may
    // have asked before the file was there, and is asked for again.
    if (!chunk.absent && chunk.state !== ChunkState.DOWNLOADING) continue;
    readAgain(manager, chunk);
    any = true;
  }
  if (any) manager.scheduleUpdate();
});

// -- chunks wanted before they are looked at ---------------------------------------
//
// Stepping to a plane whose chunk is not loaded shows nothing until it is: the
// engine drops the plane it was on at once. A view that follows a running
// acquisition would blink black with every new plane. So the page names the
// chunk of the plane it is about to go to, the chunk is asked for here exactly
// as if it were on screen, and the page steps once it has arrived.

const wanted = new Map(); // chunk source id -> { source, positions }

function hold(chunkManager) {
  if (chunkManager.mesospimWanted) return;
  chunkManager.mesospimWanted = true;
  chunkManager.recomputeChunkPriorities.add(() => {
    for (const { source, positions } of wanted.values()) {
      if (source.chunkManager !== chunkManager) continue;
      for (const position of positions) {
        chunkManager.requestChunk(source.getChunk(position), ChunkPriorityTier.VISIBLE, 0);
      }
    }
  });
}

/** `{ source, positions }`: keep these chunks of the source loaded as if on screen; none lets them go. */
registerRPC(WANT_RPC_ID, function want(x) {
  const source = this.get(x.source);
  if (source === undefined || typeof source.getChunk !== "function") return;
  if (x.positions?.length) {
    wanted.set(x.source, { source, positions: x.positions.map((position) => Float32Array.from(position)) });
  } else {
    wanted.delete(x.source);
  }
  hold(source.chunkManager);
  source.chunkManager.scheduleUpdateChunkPriorities();
});
