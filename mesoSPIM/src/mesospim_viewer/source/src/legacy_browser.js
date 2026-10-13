// What the page needs from a browser that the Data viewer window's lacks.
//
// The window is Qt WebEngine from PyQtWebEngine 5.15, which mesoSPIM-control's
// PyQt5 pins: Chromium 83, from 2020. Neuroglancer 2.41 uses browser features
// added since. Without the first of them, `AbortSignal.throwIfAborted`, every
// image source fails to load and the window stays black.
//
// Each feature is added only where the browser lacks it, so a current browser
// runs exactly as before. This file runs first in the page (main.js imports it
// before anything else) and in both background workers (scripts/neuroglancer.mjs
// injects it), since the workers fetch and decode the image chunks. The build
// also targets Chrome 83, which rewrites newer syntax; these are the runtime
// features syntax rewriting cannot supply.

const define = (target, name, value) => {
  if (target && !(name in target)) {
    Object.defineProperty(target, name, { value, writable: true, configurable: true });
  }
};

// ---- aborting (Chrome 100, 116)
if (typeof AbortSignal !== "undefined") {
  define(AbortSignal.prototype, "throwIfAborted", function throwIfAborted() {
    if (this.aborted) {
      throw this.reason !== undefined ? this.reason : new DOMException("signal is aborted without reason", "AbortError");
    }
  });
  define(AbortSignal, "any", function any(signals) {
    const controller = new AbortController();
    for (const signal of signals) {
      if (signal.aborted) {
        controller.abort(signal.reason);
        return controller.signal;
      }
    }
    const onAbort = (event) => controller.abort(event.target.reason);
    for (const signal of signals) signal.addEventListener("abort", onAbort, { once: true });
    return controller.signal;
  });
  define(AbortSignal, "timeout", function timeout(ms) {
    const controller = new AbortController();
    setTimeout(() => controller.abort(new DOMException("signal timed out", "TimeoutError")), ms);
    return controller.signal;
  });
}

// ---- promises (Chrome 85, 119)
if (typeof AggregateError === "undefined") {
  globalThis.AggregateError = class AggregateError extends Error {
    constructor(errors, message) {
      super(message);
      this.name = "AggregateError";
      this.errors = Array.from(errors);
    }
  };
}
define(Promise, "any", function any(promises) {
  return new Promise((resolve, reject) => {
    const list = Array.from(promises);
    const errors = new Array(list.length);
    let pending = list.length;
    if (!pending) reject(new AggregateError([], "All promises were rejected"));
    list.forEach((promise, i) =>
      Promise.resolve(promise).then(resolve, (error) => {
        errors[i] = error;
        if (--pending === 0) reject(new AggregateError(errors, "All promises were rejected"));
      }));
  });
});
define(Promise, "withResolvers", function withResolvers() {
  let resolve, reject;
  const promise = new this((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
});

// ---- objects, arrays and strings (Chrome 85-117)
define(Object, "hasOwn", (object, key) => Object.prototype.hasOwnProperty.call(object, key));

const groupBy = (items, key) => {
  const groups = new Map();
  let i = 0;
  for (const item of items) {
    const k = key(item, i++);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(item);
  }
  return groups;
};
define(Map, "groupBy", groupBy);
define(Object, "groupBy", (items, key) => Object.assign(Object.create(null), Object.fromEntries(groupBy(items, key))));

function at(index) {
  const n = Math.trunc(index) || 0;
  const i = n < 0 ? this.length + n : n;
  return i < 0 || i >= this.length ? undefined : this[i];
}
function findLast(predicate, self) {
  for (let i = this.length - 1; i >= 0; i--) if (predicate.call(self, this[i], i, this)) return this[i];
  return undefined;
}
function findLastIndex(predicate, self) {
  for (let i = this.length - 1; i >= 0; i--) if (predicate.call(self, this[i], i, this)) return i;
  return -1;
}
const typedArray = Object.getPrototypeOf(Int8Array.prototype);
for (const proto of [Array.prototype, typedArray, String.prototype]) define(proto, "at", at);
for (const proto of [Array.prototype, typedArray]) {
  define(proto, "findLast", findLast);
  define(proto, "findLastIndex", findLastIndex);
}
define(String.prototype, "replaceAll", function replaceAll(pattern, replacement) {
  if (pattern instanceof RegExp) {
    if (!pattern.global) throw new TypeError("replaceAll must be called with a global RegExp");
    return this.replace(pattern, replacement);
  }
  // A string pattern, matched literally everywhere: the same as replace with an
  // escaped global expression, replacement patterns and functions included.
  const literal = String(pattern).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return this.replace(new RegExp(literal, "g"), replacement);
});

// ---- the page (Chrome 86); there is no document in a worker
if (typeof Element !== "undefined") {
  function replaceChildren(...nodes) {
    while (this.lastChild) this.removeChild(this.lastChild);
    if (nodes.length) this.append(...nodes);
  }
  for (const proto of [Element.prototype, Document.prototype, DocumentFragment.prototype]) {
    define(proto, "replaceChildren", replaceChildren);
  }
}

// ---- structuredClone (Chrome 98): the plain data neuroglancer clones
function clone(value, seen) {
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return seen.get(value);
  let copy;
  if (ArrayBuffer.isView(value)) copy = value.slice();
  else if (value instanceof ArrayBuffer) copy = value.slice(0);
  else if (value instanceof Date) copy = new Date(value.getTime());
  else if (value instanceof RegExp) copy = new RegExp(value.source, value.flags);
  else if (value instanceof Map) {
    copy = new Map();
    seen.set(value, copy);
    for (const [k, v] of value) copy.set(clone(k, seen), clone(v, seen));
    return copy;
  } else if (value instanceof Set) {
    copy = new Set();
    seen.set(value, copy);
    for (const v of value) copy.add(clone(v, seen));
    return copy;
  } else {
    copy = Array.isArray(value) ? [] : {};
    seen.set(value, copy);
    for (const key of Object.keys(value)) copy[key] = clone(value[key], seen);
    return copy;
  }
  seen.set(value, copy);
  return copy;
}
if (typeof globalThis.structuredClone === "undefined") {
  globalThis.structuredClone = (value) => clone(value, new Map());
}
