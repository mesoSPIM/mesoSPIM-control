var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __esm = (fn, res) => function __init() {
  return fn && (res = (0, fn[__getOwnPropNames(fn)[0]])(fn = 0)), res;
};
var __commonJS = (cb, mod) => function __require() {
  return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
};
var __export = (target2, all) => {
  for (var name in all)
    __defProp(target2, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target2) => (target2 = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target2, "default", { value: mod, enumerable: true }) : target2,
  mod
));

// src/legacy_browser.js
function at(index) {
  const n = Math.trunc(index) || 0;
  const i = n < 0 ? this.length + n : n;
  return i < 0 || i >= this.length ? void 0 : this[i];
}
function findLast(predicate, self2) {
  for (let i = this.length - 1; i >= 0; i--) if (predicate.call(self2, this[i], i, this)) return this[i];
  return void 0;
}
function findLastIndex(predicate, self2) {
  for (let i = this.length - 1; i >= 0; i--) if (predicate.call(self2, this[i], i, this)) return i;
  return -1;
}
function clone(value, seen) {
  if (value === null || typeof value !== "object") return value;
  if (seen.has(value)) return seen.get(value);
  let copy7;
  if (ArrayBuffer.isView(value)) copy7 = value.slice();
  else if (value instanceof ArrayBuffer) copy7 = value.slice(0);
  else if (value instanceof Date) copy7 = new Date(value.getTime());
  else if (value instanceof RegExp) copy7 = new RegExp(value.source, value.flags);
  else if (value instanceof Map) {
    copy7 = /* @__PURE__ */ new Map();
    seen.set(value, copy7);
    for (const [k, v] of value) copy7.set(clone(k, seen), clone(v, seen));
    return copy7;
  } else if (value instanceof Set) {
    copy7 = /* @__PURE__ */ new Set();
    seen.set(value, copy7);
    for (const v of value) copy7.add(clone(v, seen));
    return copy7;
  } else {
    copy7 = Array.isArray(value) ? [] : {};
    seen.set(value, copy7);
    for (const key of Object.keys(value)) copy7[key] = clone(value[key], seen);
    return copy7;
  }
  seen.set(value, copy7);
  return copy7;
}
var define2, groupBy, typedArray;
var init_legacy_browser = __esm({
  "src/legacy_browser.js"() {
    define2 = (target2, name, value) => {
      if (target2 && !(name in target2)) {
        Object.defineProperty(target2, name, { value, writable: true, configurable: true });
      }
    };
    if (typeof AbortSignal !== "undefined") {
      define2(AbortSignal.prototype, "throwIfAborted", function throwIfAborted() {
        if (this.aborted) {
          throw this.reason !== void 0 ? this.reason : new DOMException("signal is aborted without reason", "AbortError");
        }
      });
      define2(AbortSignal, "any", function any3(signals) {
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
      define2(AbortSignal, "timeout", function timeout(ms) {
        const controller = new AbortController();
        setTimeout(() => controller.abort(new DOMException("signal timed out", "TimeoutError")), ms);
        return controller.signal;
      });
    }
    if (typeof AggregateError === "undefined") {
      globalThis.AggregateError = class AggregateError extends Error {
        constructor(errors2, message) {
          super(message);
          this.name = "AggregateError";
          this.errors = Array.from(errors2);
        }
      };
    }
    define2(Promise, "any", function any(promises) {
      return new Promise((resolve, reject) => {
        const list2 = Array.from(promises);
        const errors2 = new Array(list2.length);
        let pending2 = list2.length;
        if (!pending2) reject(new AggregateError([], "All promises were rejected"));
        list2.forEach((promise, i) => Promise.resolve(promise).then(resolve, (error) => {
          errors2[i] = error;
          if (--pending2 === 0) reject(new AggregateError(errors2, "All promises were rejected"));
        }));
      });
    });
    define2(Promise, "withResolvers", function withResolvers() {
      let resolve, reject;
      const promise = new this((res, rej) => {
        resolve = res;
        reject = rej;
      });
      return { promise, resolve, reject };
    });
    define2(Object, "hasOwn", (object, key) => Object.prototype.hasOwnProperty.call(object, key));
    groupBy = (items, key) => {
      const groups = /* @__PURE__ */ new Map();
      let i = 0;
      for (const item of items) {
        const k = key(item, i++);
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(item);
      }
      return groups;
    };
    define2(Map, "groupBy", groupBy);
    define2(Object, "groupBy", (items, key) => Object.assign(/* @__PURE__ */ Object.create(null), Object.fromEntries(groupBy(items, key))));
    typedArray = Object.getPrototypeOf(Int8Array.prototype);
    for (const proto of [Array.prototype, typedArray, String.prototype]) define2(proto, "at", at);
    for (const proto of [Array.prototype, typedArray]) {
      define2(proto, "findLast", findLast);
      define2(proto, "findLastIndex", findLastIndex);
    }
    define2(String.prototype, "replaceAll", function replaceAll(pattern, replacement) {
      if (pattern instanceof RegExp) {
        if (!pattern.global) throw new TypeError("replaceAll must be called with a global RegExp");
        return this.replace(pattern, replacement);
      }
      const literal = String(pattern).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      return this.replace(new RegExp(literal, "g"), replacement);
    });
    if (typeof Element !== "undefined") {
      let replaceChildren = function(...nodes) {
        while (this.lastChild) this.removeChild(this.lastChild);
        if (nodes.length) this.append(...nodes);
      };
      for (const proto of [Element.prototype, Document.prototype, DocumentFragment.prototype]) {
        define2(proto, "replaceChildren", replaceChildren);
      }
    }
    if (typeof globalThis.structuredClone === "undefined") {
      globalThis.structuredClone = (value) => clone(value, /* @__PURE__ */ new Map());
    }
  }
});

// node_modules/core-js/internals/global-this.js
var require_global_this = __commonJS({
  "node_modules/core-js/internals/global-this.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var check2 = function(it) {
      return it && it.Math === Math && it;
    };
    module.exports = // eslint-disable-next-line es/no-global-this -- safe
    check2(typeof globalThis == "object" && globalThis) || check2(typeof window == "object" && window) || // eslint-disable-next-line no-restricted-globals -- safe
    check2(typeof self == "object" && self) || check2(typeof global == "object" && global) || check2(typeof exports == "object" && exports) || // eslint-disable-next-line no-new-func -- fallback
    /* @__PURE__ */ (function() {
      return this;
    })() || Function("return this")();
  }
});

// node_modules/core-js/internals/path.js
var require_path = __commonJS({
  "node_modules/core-js/internals/path.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    module.exports = globalThis2;
  }
});

// node_modules/core-js/internals/fails.js
var require_fails = __commonJS({
  "node_modules/core-js/internals/fails.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    module.exports = function(exec) {
      try {
        return !!exec();
      } catch (error) {
        return true;
      }
    };
  }
});

// node_modules/core-js/internals/function-bind-native.js
var require_function_bind_native = __commonJS({
  "node_modules/core-js/internals/function-bind-native.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var fails = require_fails();
    module.exports = !fails(function() {
      var test = function() {
      }.bind();
      return typeof test != "function" || test.hasOwnProperty("prototype");
    });
  }
});

// node_modules/core-js/internals/function-uncurry-this.js
var require_function_uncurry_this = __commonJS({
  "node_modules/core-js/internals/function-uncurry-this.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var NATIVE_BIND = require_function_bind_native();
    var FunctionPrototype = Function.prototype;
    var call = FunctionPrototype.call;
    var uncurryThisWithBind = NATIVE_BIND && FunctionPrototype.bind.bind(call, call);
    module.exports = NATIVE_BIND ? uncurryThisWithBind : function(fn) {
      return function() {
        return call.apply(fn, arguments);
      };
    };
  }
});

// node_modules/core-js/internals/is-null-or-undefined.js
var require_is_null_or_undefined = __commonJS({
  "node_modules/core-js/internals/is-null-or-undefined.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    module.exports = function(it) {
      return it === null || it === void 0;
    };
  }
});

// node_modules/core-js/internals/require-object-coercible.js
var require_require_object_coercible = __commonJS({
  "node_modules/core-js/internals/require-object-coercible.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var isNullOrUndefined = require_is_null_or_undefined();
    var $TypeError = TypeError;
    module.exports = function(it) {
      if (isNullOrUndefined(it)) throw new $TypeError("Can't call method on " + it);
      return it;
    };
  }
});

// node_modules/core-js/internals/to-object.js
var require_to_object = __commonJS({
  "node_modules/core-js/internals/to-object.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var requireObjectCoercible = require_require_object_coercible();
    var $Object = Object;
    module.exports = function(argument) {
      return $Object(requireObjectCoercible(argument));
    };
  }
});

// node_modules/core-js/internals/has-own-property.js
var require_has_own_property = __commonJS({
  "node_modules/core-js/internals/has-own-property.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var uncurryThis = require_function_uncurry_this();
    var toObject = require_to_object();
    var hasOwnProperty2 = uncurryThis({}.hasOwnProperty);
    module.exports = Object.hasOwn || function hasOwn(it, key) {
      return hasOwnProperty2(toObject(it), key);
    };
  }
});

// node_modules/core-js/internals/is-pure.js
var require_is_pure = __commonJS({
  "node_modules/core-js/internals/is-pure.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    module.exports = false;
  }
});

// node_modules/core-js/internals/define-global-property.js
var require_define_global_property = __commonJS({
  "node_modules/core-js/internals/define-global-property.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var defineProperty = Object.defineProperty;
    module.exports = function(key, value) {
      try {
        defineProperty(globalThis2, key, { value, configurable: true, writable: true });
      } catch (error) {
        globalThis2[key] = value;
      }
      return value;
    };
  }
});

// node_modules/core-js/internals/shared-store.js
var require_shared_store = __commonJS({
  "node_modules/core-js/internals/shared-store.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var IS_PURE = require_is_pure();
    var globalThis2 = require_global_this();
    var defineGlobalProperty = require_define_global_property();
    var SHARED = "__core-js_shared__";
    var store = module.exports = globalThis2[SHARED] || defineGlobalProperty(SHARED, {});
    (store.versions || (store.versions = [])).push({
      version: "3.50.0",
      mode: IS_PURE ? "pure" : "global",
      copyright: "\xA9 2013\u20132025 Denis Pushkarev (zloirock.ru), 2025\u20132026 CoreJS Company (core-js.io). All rights reserved.",
      license: "https://github.com/zloirock/core-js/blob/v3.50.0/LICENSE",
      source: "https://github.com/zloirock/core-js"
    });
  }
});

// node_modules/core-js/internals/shared.js
var require_shared = __commonJS({
  "node_modules/core-js/internals/shared.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var store = require_shared_store();
    var create6 = Object.create || Object;
    module.exports = function(key, value) {
      return store[key] || (store[key] = value || create6(null));
    };
  }
});

// node_modules/core-js/internals/uid.js
var require_uid = __commonJS({
  "node_modules/core-js/internals/uid.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var uncurryThis = require_function_uncurry_this();
    var id = 0;
    var postfix = Math.random();
    var toString = uncurryThis(1.1.toString);
    module.exports = function(key) {
      return "Symbol(" + (key === void 0 ? "" : key) + ")_" + toString(++id + postfix, 36);
    };
  }
});

// node_modules/core-js/internals/environment-user-agent.js
var require_environment_user_agent = __commonJS({
  "node_modules/core-js/internals/environment-user-agent.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var navigator2 = globalThis2.navigator;
    var userAgent = navigator2 && navigator2.userAgent;
    module.exports = userAgent ? String(userAgent) : "";
  }
});

// node_modules/core-js/internals/environment-v8-version.js
var require_environment_v8_version = __commonJS({
  "node_modules/core-js/internals/environment-v8-version.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var userAgent = require_environment_user_agent();
    var process = globalThis2.process;
    var Deno = globalThis2.Deno;
    var versions = process && process.versions || Deno && Deno.version;
    var v8 = versions && versions.v8;
    var match;
    var version;
    if (v8) {
      match = v8.split(".");
      version = match[0] > 0 && match[0] < 4 ? 1 : +(match[0] + match[1]);
    }
    if (!version && userAgent) {
      match = userAgent.match(/Edge\/(\d+)/);
      if (!match || match[1] >= 74) {
        match = userAgent.match(/Chrome\/(\d+)/);
        if (match) version = +match[1];
      }
    }
    module.exports = version;
  }
});

// node_modules/core-js/internals/symbol-constructor-detection.js
var require_symbol_constructor_detection = __commonJS({
  "node_modules/core-js/internals/symbol-constructor-detection.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var V8_VERSION = require_environment_v8_version();
    var fails = require_fails();
    var globalThis2 = require_global_this();
    var $String = globalThis2.String;
    module.exports = !!Object.getOwnPropertySymbols && !fails(function() {
      var symbol = Symbol("symbol detection");
      return !$String(symbol) || !(Object(symbol) instanceof Symbol) || // Chrome 38-40 symbols are not inherited from DOM collections prototypes to instances
      !Symbol.sham && V8_VERSION && V8_VERSION < 41;
    });
  }
});

// node_modules/core-js/internals/use-symbol-as-uid.js
var require_use_symbol_as_uid = __commonJS({
  "node_modules/core-js/internals/use-symbol-as-uid.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var NATIVE_SYMBOL = require_symbol_constructor_detection();
    module.exports = NATIVE_SYMBOL && !Symbol.sham && typeof Symbol.iterator == "symbol";
  }
});

// node_modules/core-js/internals/well-known-symbol.js
var require_well_known_symbol = __commonJS({
  "node_modules/core-js/internals/well-known-symbol.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var shared = require_shared();
    var hasOwn = require_has_own_property();
    var uid = require_uid();
    var NATIVE_SYMBOL = require_symbol_constructor_detection();
    var USE_SYMBOL_AS_UID = require_use_symbol_as_uid();
    var Symbol3 = globalThis2.Symbol;
    var WellKnownSymbolsStore = shared("wks");
    var createWellKnownSymbol = USE_SYMBOL_AS_UID ? Symbol3["for"] || Symbol3 : Symbol3 && Symbol3.withoutSetter || uid;
    module.exports = function(name) {
      if (!hasOwn(WellKnownSymbolsStore, name)) {
        WellKnownSymbolsStore[name] = NATIVE_SYMBOL && hasOwn(Symbol3, name) ? Symbol3[name] : createWellKnownSymbol("Symbol." + name);
      }
      return WellKnownSymbolsStore[name];
    };
  }
});

// node_modules/core-js/internals/well-known-symbol-wrapped.js
var require_well_known_symbol_wrapped = __commonJS({
  "node_modules/core-js/internals/well-known-symbol-wrapped.js"(exports) {
    "use strict";
    init_legacy_browser();
    var wellKnownSymbol = require_well_known_symbol();
    exports.f = wellKnownSymbol;
  }
});

// node_modules/core-js/internals/descriptors.js
var require_descriptors = __commonJS({
  "node_modules/core-js/internals/descriptors.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var fails = require_fails();
    module.exports = !fails(function() {
      return Object.defineProperty({}, 1, { get: function() {
        return 7;
      } })[1] !== 7;
    });
  }
});

// node_modules/core-js/internals/is-callable.js
var require_is_callable = __commonJS({
  "node_modules/core-js/internals/is-callable.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var documentAll = typeof document == "object" && document.all;
    module.exports = typeof documentAll == "undefined" && documentAll !== void 0 ? function(argument) {
      return typeof argument == "function" || argument === documentAll;
    } : function(argument) {
      return typeof argument == "function";
    };
  }
});

// node_modules/core-js/internals/is-object.js
var require_is_object = __commonJS({
  "node_modules/core-js/internals/is-object.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var isCallable = require_is_callable();
    module.exports = function(it) {
      return typeof it == "object" ? it !== null : isCallable(it);
    };
  }
});

// node_modules/core-js/internals/document-create-element.js
var require_document_create_element = __commonJS({
  "node_modules/core-js/internals/document-create-element.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var isObject2 = require_is_object();
    var document2 = globalThis2.document;
    var EXISTS = isObject2(document2) && isObject2(document2.createElement);
    module.exports = function(it) {
      return EXISTS ? document2.createElement(it) : {};
    };
  }
});

// node_modules/core-js/internals/ie8-dom-define.js
var require_ie8_dom_define = __commonJS({
  "node_modules/core-js/internals/ie8-dom-define.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var DESCRIPTORS = require_descriptors();
    var fails = require_fails();
    var createElement = require_document_create_element();
    module.exports = !DESCRIPTORS && !fails(function() {
      return Object.defineProperty(createElement("div"), "a", {
        get: function() {
          return 7;
        }
      }).a !== 7;
    });
  }
});

// node_modules/core-js/internals/v8-prototype-define-bug.js
var require_v8_prototype_define_bug = __commonJS({
  "node_modules/core-js/internals/v8-prototype-define-bug.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var DESCRIPTORS = require_descriptors();
    var fails = require_fails();
    module.exports = DESCRIPTORS && fails(function() {
      return Object.defineProperty(function() {
      }, "prototype", {
        value: 42,
        writable: false
      }).prototype !== 42;
    });
  }
});

// node_modules/core-js/internals/an-object.js
var require_an_object = __commonJS({
  "node_modules/core-js/internals/an-object.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var isObject2 = require_is_object();
    var $String = String;
    var $TypeError = TypeError;
    module.exports = function(argument) {
      if (isObject2(argument)) return argument;
      throw new $TypeError($String(argument) + " is not an object");
    };
  }
});

// node_modules/core-js/internals/function-call.js
var require_function_call = __commonJS({
  "node_modules/core-js/internals/function-call.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var NATIVE_BIND = require_function_bind_native();
    var call = Function.prototype.call;
    module.exports = NATIVE_BIND ? call.bind(call) : function() {
      return call.apply(call, arguments);
    };
  }
});

// node_modules/core-js/internals/get-built-in.js
var require_get_built_in = __commonJS({
  "node_modules/core-js/internals/get-built-in.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var isCallable = require_is_callable();
    var aFunction = function(argument) {
      return isCallable(argument) ? argument : void 0;
    };
    module.exports = function(namespace, method) {
      return arguments.length < 2 ? aFunction(globalThis2[namespace]) : globalThis2[namespace] && globalThis2[namespace][method];
    };
  }
});

// node_modules/core-js/internals/object-is-prototype-of.js
var require_object_is_prototype_of = __commonJS({
  "node_modules/core-js/internals/object-is-prototype-of.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var uncurryThis = require_function_uncurry_this();
    module.exports = uncurryThis({}.isPrototypeOf);
  }
});

// node_modules/core-js/internals/is-symbol.js
var require_is_symbol = __commonJS({
  "node_modules/core-js/internals/is-symbol.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var getBuiltIn = require_get_built_in();
    var isCallable = require_is_callable();
    var isPrototypeOf = require_object_is_prototype_of();
    var USE_SYMBOL_AS_UID = require_use_symbol_as_uid();
    var $Object = Object;
    module.exports = USE_SYMBOL_AS_UID ? function(it) {
      return typeof it == "symbol";
    } : function(it) {
      var $Symbol = getBuiltIn("Symbol");
      return isCallable($Symbol) && isPrototypeOf($Symbol.prototype, $Object(it));
    };
  }
});

// node_modules/core-js/internals/try-to-string.js
var require_try_to_string = __commonJS({
  "node_modules/core-js/internals/try-to-string.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var $String = String;
    module.exports = function(argument) {
      try {
        return $String(argument);
      } catch (error) {
        return "Object";
      }
    };
  }
});

// node_modules/core-js/internals/a-callable.js
var require_a_callable = __commonJS({
  "node_modules/core-js/internals/a-callable.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var isCallable = require_is_callable();
    var tryToString = require_try_to_string();
    var $TypeError = TypeError;
    module.exports = function(argument) {
      if (isCallable(argument)) return argument;
      throw new $TypeError(tryToString(argument) + " is not a function");
    };
  }
});

// node_modules/core-js/internals/get-method.js
var require_get_method = __commonJS({
  "node_modules/core-js/internals/get-method.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var aCallable = require_a_callable();
    var isNullOrUndefined = require_is_null_or_undefined();
    module.exports = function(V, P) {
      var func = V[P];
      return isNullOrUndefined(func) ? void 0 : aCallable(func);
    };
  }
});

// node_modules/core-js/internals/ordinary-to-primitive.js
var require_ordinary_to_primitive = __commonJS({
  "node_modules/core-js/internals/ordinary-to-primitive.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var call = require_function_call();
    var isCallable = require_is_callable();
    var isObject2 = require_is_object();
    var $TypeError = TypeError;
    module.exports = function(input, pref) {
      var fn, val;
      if (pref === "string" && isCallable(fn = input.toString) && !isObject2(val = call(fn, input))) return val;
      if (isCallable(fn = input.valueOf) && !isObject2(val = call(fn, input))) return val;
      if (pref !== "string" && isCallable(fn = input.toString) && !isObject2(val = call(fn, input))) return val;
      throw new $TypeError("Can't convert object to primitive value");
    };
  }
});

// node_modules/core-js/internals/to-primitive.js
var require_to_primitive = __commonJS({
  "node_modules/core-js/internals/to-primitive.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var call = require_function_call();
    var isObject2 = require_is_object();
    var isSymbol2 = require_is_symbol();
    var getMethod = require_get_method();
    var ordinaryToPrimitive = require_ordinary_to_primitive();
    var wellKnownSymbol = require_well_known_symbol();
    var $TypeError = TypeError;
    var TO_PRIMITIVE = wellKnownSymbol("toPrimitive");
    module.exports = function(input, pref) {
      if (!isObject2(input) || isSymbol2(input)) return input;
      var exoticToPrim = getMethod(input, TO_PRIMITIVE);
      var result;
      if (exoticToPrim) {
        if (pref === void 0) pref = "default";
        result = call(exoticToPrim, input, pref);
        if (!isObject2(result) || isSymbol2(result)) return result;
        throw new $TypeError("Can't convert object to primitive value");
      }
      if (pref === void 0) pref = "number";
      return ordinaryToPrimitive(input, pref);
    };
  }
});

// node_modules/core-js/internals/to-property-key.js
var require_to_property_key = __commonJS({
  "node_modules/core-js/internals/to-property-key.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var toPrimitive = require_to_primitive();
    var isSymbol2 = require_is_symbol();
    module.exports = function(argument) {
      var key = toPrimitive(argument, "string");
      return isSymbol2(key) ? key : key + "";
    };
  }
});

// node_modules/core-js/internals/object-define-property.js
var require_object_define_property = __commonJS({
  "node_modules/core-js/internals/object-define-property.js"(exports) {
    "use strict";
    init_legacy_browser();
    var DESCRIPTORS = require_descriptors();
    var IE8_DOM_DEFINE = require_ie8_dom_define();
    var V8_PROTOTYPE_DEFINE_BUG = require_v8_prototype_define_bug();
    var anObject = require_an_object();
    var toPropertyKey = require_to_property_key();
    var $TypeError = TypeError;
    var $defineProperty = Object.defineProperty;
    var $getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
    var ENUMERABLE = "enumerable";
    var CONFIGURABLE = "configurable";
    var WRITABLE = "writable";
    exports.f = DESCRIPTORS ? V8_PROTOTYPE_DEFINE_BUG ? function defineProperty(O, P, Attributes) {
      anObject(O);
      P = toPropertyKey(P);
      anObject(Attributes);
      if (typeof O === "function" && P === "prototype" && "value" in Attributes && WRITABLE in Attributes && !Attributes[WRITABLE]) {
        var current = $getOwnPropertyDescriptor(O, P);
        if (current && current[WRITABLE]) {
          O[P] = Attributes.value;
          Attributes = {
            configurable: CONFIGURABLE in Attributes ? Attributes[CONFIGURABLE] : current[CONFIGURABLE],
            enumerable: ENUMERABLE in Attributes ? Attributes[ENUMERABLE] : current[ENUMERABLE],
            writable: false
          };
        }
      }
      return $defineProperty(O, P, Attributes);
    } : $defineProperty : function defineProperty(O, P, Attributes) {
      anObject(O);
      P = toPropertyKey(P);
      anObject(Attributes);
      if (IE8_DOM_DEFINE) try {
        return $defineProperty(O, P, Attributes);
      } catch (error) {
      }
      if ("get" in Attributes || "set" in Attributes) throw new $TypeError("Accessors not supported");
      if ("value" in Attributes) O[P] = Attributes.value;
      return O;
    };
  }
});

// node_modules/core-js/internals/well-known-symbol-define.js
var require_well_known_symbol_define = __commonJS({
  "node_modules/core-js/internals/well-known-symbol-define.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var path = require_path();
    var hasOwn = require_has_own_property();
    var wrappedWellKnownSymbolModule = require_well_known_symbol_wrapped();
    var defineProperty = require_object_define_property().f;
    module.exports = function(NAME) {
      var Symbol3 = path.Symbol || (path.Symbol = {});
      if (!hasOwn(Symbol3, NAME)) defineProperty(Symbol3, NAME, {
        value: wrappedWellKnownSymbolModule.f(NAME)
      });
    };
  }
});

// node_modules/core-js/internals/object-property-is-enumerable.js
var require_object_property_is_enumerable = __commonJS({
  "node_modules/core-js/internals/object-property-is-enumerable.js"(exports) {
    "use strict";
    init_legacy_browser();
    var $propertyIsEnumerable = {}.propertyIsEnumerable;
    var getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
    var NASHORN_BUG = getOwnPropertyDescriptor && !$propertyIsEnumerable.call({ 1: 2 }, 1);
    exports.f = NASHORN_BUG ? function propertyIsEnumerable(V) {
      var descriptor = getOwnPropertyDescriptor(this, V);
      return !!descriptor && descriptor.enumerable;
    } : $propertyIsEnumerable;
  }
});

// node_modules/core-js/internals/create-property-descriptor.js
var require_create_property_descriptor = __commonJS({
  "node_modules/core-js/internals/create-property-descriptor.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    module.exports = function(bitmap, value) {
      return {
        enumerable: !(bitmap & 1),
        configurable: !(bitmap & 2),
        writable: !(bitmap & 4),
        value
      };
    };
  }
});

// node_modules/core-js/internals/classof-raw.js
var require_classof_raw = __commonJS({
  "node_modules/core-js/internals/classof-raw.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var uncurryThis = require_function_uncurry_this();
    var toString = uncurryThis({}.toString);
    var stringSlice = uncurryThis("".slice);
    module.exports = function(it) {
      return stringSlice(toString(it), 8, -1);
    };
  }
});

// node_modules/core-js/internals/indexed-object.js
var require_indexed_object = __commonJS({
  "node_modules/core-js/internals/indexed-object.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var uncurryThis = require_function_uncurry_this();
    var fails = require_fails();
    var classof = require_classof_raw();
    var $Object = Object;
    var split = uncurryThis("".split);
    module.exports = fails(function() {
      return !$Object("z").propertyIsEnumerable(0);
    }) ? function(it) {
      return classof(it) === "String" ? split(it, "") : $Object(it);
    } : $Object;
  }
});

// node_modules/core-js/internals/to-indexed-object.js
var require_to_indexed_object = __commonJS({
  "node_modules/core-js/internals/to-indexed-object.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var IndexedObject = require_indexed_object();
    var requireObjectCoercible = require_require_object_coercible();
    module.exports = function(it) {
      return IndexedObject(requireObjectCoercible(it));
    };
  }
});

// node_modules/core-js/internals/object-get-own-property-descriptor.js
var require_object_get_own_property_descriptor = __commonJS({
  "node_modules/core-js/internals/object-get-own-property-descriptor.js"(exports) {
    "use strict";
    init_legacy_browser();
    var DESCRIPTORS = require_descriptors();
    var call = require_function_call();
    var propertyIsEnumerableModule = require_object_property_is_enumerable();
    var createPropertyDescriptor = require_create_property_descriptor();
    var toIndexedObject = require_to_indexed_object();
    var toPropertyKey = require_to_property_key();
    var hasOwn = require_has_own_property();
    var IE8_DOM_DEFINE = require_ie8_dom_define();
    var $getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
    exports.f = DESCRIPTORS ? $getOwnPropertyDescriptor : function getOwnPropertyDescriptor(O, P) {
      O = toIndexedObject(O);
      P = toPropertyKey(P);
      if (IE8_DOM_DEFINE) try {
        return $getOwnPropertyDescriptor(O, P);
      } catch (error) {
      }
      if (hasOwn(O, P)) return createPropertyDescriptor(!call(propertyIsEnumerableModule.f, O, P), O[P]);
    };
  }
});

// node_modules/core-js/modules/es.symbol.dispose.js
var require_es_symbol_dispose = __commonJS({
  "node_modules/core-js/modules/es.symbol.dispose.js"() {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var defineWellKnownSymbol = require_well_known_symbol_define();
    var defineProperty = require_object_define_property().f;
    var getOwnPropertyDescriptor = require_object_get_own_property_descriptor().f;
    var Symbol3 = globalThis2.Symbol;
    defineWellKnownSymbol("dispose");
    if (Symbol3) {
      descriptor = getOwnPropertyDescriptor(Symbol3, "dispose");
      if (descriptor.enumerable && descriptor.configurable && descriptor.writable) {
        defineProperty(Symbol3, "dispose", { value: descriptor.value, enumerable: false, configurable: false, writable: false });
      }
    }
    var descriptor;
  }
});

// node_modules/core-js/es/symbol/dispose.js
var require_dispose = __commonJS({
  "node_modules/core-js/es/symbol/dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    require_es_symbol_dispose();
    var WrappedWellKnownSymbolModule = require_well_known_symbol_wrapped();
    module.exports = WrappedWellKnownSymbolModule.f("dispose");
  }
});

// node_modules/core-js/stable/symbol/dispose.js
var require_dispose2 = __commonJS({
  "node_modules/core-js/stable/symbol/dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var parent = require_dispose();
    module.exports = parent;
  }
});

// node_modules/core-js/modules/esnext.symbol.dispose.js
var require_esnext_symbol_dispose = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.dispose.js"() {
    "use strict";
    init_legacy_browser();
    require_es_symbol_dispose();
  }
});

// node_modules/core-js/actual/symbol/dispose.js
var require_dispose3 = __commonJS({
  "node_modules/core-js/actual/symbol/dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var parent = require_dispose2();
    require_esnext_symbol_dispose();
    module.exports = parent;
  }
});

// node_modules/core-js/modules/es.symbol.async-dispose.js
var require_es_symbol_async_dispose = __commonJS({
  "node_modules/core-js/modules/es.symbol.async-dispose.js"() {
    "use strict";
    init_legacy_browser();
    var globalThis2 = require_global_this();
    var defineWellKnownSymbol = require_well_known_symbol_define();
    var defineProperty = require_object_define_property().f;
    var getOwnPropertyDescriptor = require_object_get_own_property_descriptor().f;
    var Symbol3 = globalThis2.Symbol;
    defineWellKnownSymbol("asyncDispose");
    if (Symbol3) {
      descriptor = getOwnPropertyDescriptor(Symbol3, "asyncDispose");
      if (descriptor.enumerable && descriptor.configurable && descriptor.writable) {
        defineProperty(Symbol3, "asyncDispose", { value: descriptor.value, enumerable: false, configurable: false, writable: false });
      }
    }
    var descriptor;
  }
});

// node_modules/core-js/es/symbol/async-dispose.js
var require_async_dispose = __commonJS({
  "node_modules/core-js/es/symbol/async-dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    require_es_symbol_async_dispose();
    var WrappedWellKnownSymbolModule = require_well_known_symbol_wrapped();
    module.exports = WrappedWellKnownSymbolModule.f("asyncDispose");
  }
});

// node_modules/core-js/stable/symbol/async-dispose.js
var require_async_dispose2 = __commonJS({
  "node_modules/core-js/stable/symbol/async-dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var parent = require_async_dispose();
    module.exports = parent;
  }
});

// node_modules/core-js/modules/esnext.symbol.async-dispose.js
var require_esnext_symbol_async_dispose = __commonJS({
  "node_modules/core-js/modules/esnext.symbol.async-dispose.js"() {
    "use strict";
    init_legacy_browser();
    require_es_symbol_async_dispose();
  }
});

// node_modules/core-js/actual/symbol/async-dispose.js
var require_async_dispose3 = __commonJS({
  "node_modules/core-js/actual/symbol/async-dispose.js"(exports, module) {
    "use strict";
    init_legacy_browser();
    var parent = require_async_dispose2();
    require_esnext_symbol_async_dispose();
    module.exports = parent;
  }
});

// node_modules/fflate/lib/browser.cjs
var require_browser = __commonJS({
  "node_modules/fflate/lib/browser.cjs"(exports) {
    "use strict";
    init_legacy_browser();
    exports.deflate = deflate;
    exports.deflateSync = deflateSync;
    exports.inflate = inflate;
    exports.inflateSync = inflateSync;
    exports.gzip = gzip;
    exports.compress = gzip;
    exports.gzipSync = gzipSync;
    exports.compressSync = gzipSync;
    exports.gunzip = gunzip;
    exports.gunzipSync = gunzipSync;
    exports.zlib = zlib;
    exports.zlibSync = zlibSync;
    exports.unzlib = unzlib;
    exports.unzlibSync = unzlibSync;
    exports.gzip = gzip;
    exports.compress = gzip;
    exports.decompress = decompress;
    exports.decompressSync = decompressSync;
    exports.strToU8 = strToU8;
    exports.strFromU8 = strFromU8;
    exports.zip = zip;
    exports.zipSync = zipSync;
    exports.unzip = unzip;
    exports.unzipSync = unzipSync;
    var ch2 = {};
    var node_worker_1 = {};
    node_worker_1["default"] = (function(c, id, msg, transfer, cb) {
      var w = new Worker(ch2[id] || (ch2[id] = URL.createObjectURL(new Blob([
        c + ';addEventListener("error",function(e){e=e.error;postMessage({$e$:[e.message,e.code,e.stack]})})'
      ], { type: "text/javascript" }))));
      w.onmessage = function(e) {
        var d = e.data, ed = d.$e$;
        if (ed) {
          var err2 = new Error(ed[0]);
          err2["code"] = ed[1];
          err2.stack = ed[2];
          cb(err2, null);
        } else
          cb(null, d);
      };
      w.postMessage(msg, transfer);
      return w;
    });
    var u8 = Uint8Array;
    var u16 = Uint16Array;
    var i32 = Int32Array;
    var fleb = new u8([
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      0,
      1,
      1,
      1,
      1,
      2,
      2,
      2,
      2,
      3,
      3,
      3,
      3,
      4,
      4,
      4,
      4,
      5,
      5,
      5,
      5,
      0,
      /* unused */
      0,
      0,
      /* impossible */
      0
    ]);
    var fdeb = new u8([
      0,
      0,
      0,
      0,
      1,
      1,
      2,
      2,
      3,
      3,
      4,
      4,
      5,
      5,
      6,
      6,
      7,
      7,
      8,
      8,
      9,
      9,
      10,
      10,
      11,
      11,
      12,
      12,
      13,
      13,
      /* unused */
      0,
      0
    ]);
    var clim = new u8([16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15]);
    var freb = function(eb, start) {
      var b = new u16(31);
      for (var i2 = 0; i2 < 31; ++i2) {
        b[i2] = start += 1 << eb[i2 - 1];
      }
      var r = new i32(b[30]);
      for (var i2 = 1; i2 < 30; ++i2) {
        for (var j = b[i2]; j < b[i2 + 1]; ++j) {
          r[j] = j - b[i2] << 5 | i2;
        }
      }
      return { b, r };
    };
    var _a = freb(fleb, 2);
    var fl = _a.b;
    var revfl = _a.r;
    fl[28] = 258, revfl[258] = 28;
    var _b = freb(fdeb, 0);
    var fd = _b.b;
    var revfd = _b.r;
    var rev = new u16(32768);
    for (i = 0; i < 32768; ++i) {
      x = (i & 43690) >> 1 | (i & 21845) << 1;
      x = (x & 52428) >> 2 | (x & 13107) << 2;
      x = (x & 61680) >> 4 | (x & 3855) << 4;
      rev[i] = ((x & 65280) >> 8 | (x & 255) << 8) >> 1;
    }
    var x;
    var i;
    var hMap = (function(cd, mb, r) {
      var s = cd.length;
      var i2 = 0;
      var l = new u16(mb);
      for (; i2 < s; ++i2) {
        if (cd[i2])
          ++l[cd[i2] - 1];
      }
      var le = new u16(mb);
      for (i2 = 1; i2 < mb; ++i2) {
        le[i2] = le[i2 - 1] + l[i2 - 1] << 1;
      }
      var co;
      if (r) {
        co = new u16(1 << mb);
        var rvb = 15 - mb;
        for (i2 = 0; i2 < s; ++i2) {
          if (cd[i2]) {
            var sv = i2 << 4 | cd[i2];
            var r_1 = mb - cd[i2];
            var v = le[cd[i2] - 1]++ << r_1;
            for (var m = v | (1 << r_1) - 1; v <= m; ++v) {
              co[rev[v] >> rvb] = sv;
            }
          }
        }
      } else {
        co = new u16(s);
        for (i2 = 0; i2 < s; ++i2) {
          if (cd[i2]) {
            co[i2] = rev[le[cd[i2] - 1]++] >> 15 - cd[i2];
          }
        }
      }
      return co;
    });
    var flt = new u8(288);
    for (i = 0; i < 144; ++i)
      flt[i] = 8;
    var i;
    for (i = 144; i < 256; ++i)
      flt[i] = 9;
    var i;
    for (i = 256; i < 280; ++i)
      flt[i] = 7;
    var i;
    for (i = 280; i < 288; ++i)
      flt[i] = 8;
    var i;
    var fdt = new u8(32);
    for (i = 0; i < 32; ++i)
      fdt[i] = 5;
    var i;
    var flm = /* @__PURE__ */ hMap(flt, 9, 0);
    var flrm = /* @__PURE__ */ hMap(flt, 9, 1);
    var fdm = /* @__PURE__ */ hMap(fdt, 5, 0);
    var fdrm = /* @__PURE__ */ hMap(fdt, 5, 1);
    var max4 = function(a) {
      var m = a[0];
      for (var i2 = 1; i2 < a.length; ++i2) {
        if (a[i2] > m)
          m = a[i2];
      }
      return m;
    };
    var bits = function(d, p, m) {
      var o = p / 8 | 0;
      return (d[o] | d[o + 1] << 8) >> (p & 7) & m;
    };
    var bits16 = function(d, p) {
      var o = p / 8 | 0;
      return (d[o] | d[o + 1] << 8 | d[o + 2] << 16) >> (p & 7);
    };
    var shft = function(p) {
      return (p + 7) / 8 | 0;
    };
    var slc = function(v, s, e) {
      if (s == null || s < 0)
        s = 0;
      if (e == null || e > v.length)
        e = v.length;
      return new u8(v.subarray(s, e));
    };
    exports.FlateErrorCode = {
      UnexpectedEOF: 0,
      InvalidBlockType: 1,
      InvalidLengthLiteral: 2,
      InvalidDistance: 3,
      StreamFinished: 4,
      NoStreamHandler: 5,
      InvalidHeader: 6,
      NoCallback: 7,
      InvalidUTF8: 8,
      ExtraFieldTooLong: 9,
      InvalidDate: 10,
      FilenameTooLong: 11,
      StreamFinishing: 12,
      InvalidZipData: 13,
      UnknownCompressionMethod: 14
    };
    var ec = [
      "unexpected EOF",
      "invalid block type",
      "invalid length/literal",
      "invalid distance",
      "stream finished",
      "no stream handler",
      ,
      // determined by compression function
      "no callback",
      "invalid UTF-8 data",
      "extra field too long",
      "date not in range 1980-2099",
      "filename too long",
      "stream finishing",
      "invalid zip data"
      // determined by unknown compression method
    ];
    var err = function(ind, msg, nt) {
      var e = new Error(msg || ec[ind]);
      e.code = ind;
      if (Error.captureStackTrace)
        Error.captureStackTrace(e, err);
      if (!nt)
        throw e;
      return e;
    };
    var inflt = function(dat, st, buf, dict) {
      var sl = dat.length, dl = dict ? dict.length : 0;
      if (!sl || st.f && !st.l)
        return buf || new u8(0);
      var noBuf = !buf;
      var resize = noBuf || st.i != 2;
      var noSt = st.i;
      if (noBuf)
        buf = new u8(sl * 3);
      var cbuf = function(l2) {
        var bl = buf.length;
        if (l2 > bl) {
          var nbuf = new u8(Math.max(bl * 2, l2));
          nbuf.set(buf);
          buf = nbuf;
        }
      };
      var final = st.f || 0, pos = st.p || 0, bt = st.b || 0, lm = st.l, dm = st.d, lbt = st.m, dbt = st.n;
      var tbts = sl * 8;
      do {
        if (!lm) {
          final = bits(dat, pos, 1);
          var type = bits(dat, pos + 1, 3);
          pos += 3;
          if (!type) {
            var s = shft(pos) + 4, l = dat[s - 4] | dat[s - 3] << 8, t = s + l;
            if (t > sl) {
              if (noSt)
                err(0);
              break;
            }
            if (resize)
              cbuf(bt + l);
            buf.set(dat.subarray(s, t), bt);
            st.b = bt += l, st.p = pos = t * 8, st.f = final;
            continue;
          } else if (type == 1)
            lm = flrm, dm = fdrm, lbt = 9, dbt = 5;
          else if (type == 2) {
            var hLit = bits(dat, pos, 31) + 257, hcLen = bits(dat, pos + 10, 15) + 4;
            var tl = hLit + bits(dat, pos + 5, 31) + 1;
            pos += 14;
            var ldt = new u8(tl);
            var clt = new u8(19);
            for (var i2 = 0; i2 < hcLen; ++i2) {
              clt[clim[i2]] = bits(dat, pos + i2 * 3, 7);
            }
            pos += hcLen * 3;
            var clb = max4(clt), clbmsk = (1 << clb) - 1;
            var clm = hMap(clt, clb, 1);
            for (var i2 = 0; i2 < tl; ) {
              var r = clm[bits(dat, pos, clbmsk)];
              pos += r & 15;
              var s = r >> 4;
              if (s < 16) {
                ldt[i2++] = s;
              } else {
                var c = 0, n = 0;
                if (s == 16)
                  n = 3 + bits(dat, pos, 3), pos += 2, c = ldt[i2 - 1];
                else if (s == 17)
                  n = 3 + bits(dat, pos, 7), pos += 3;
                else if (s == 18)
                  n = 11 + bits(dat, pos, 127), pos += 7;
                while (n--)
                  ldt[i2++] = c;
              }
            }
            var lt = ldt.subarray(0, hLit), dt = ldt.subarray(hLit);
            lbt = max4(lt);
            dbt = max4(dt);
            lm = hMap(lt, lbt, 1);
            dm = hMap(dt, dbt, 1);
          } else
            err(1);
          if (pos > tbts) {
            if (noSt)
              err(0);
            break;
          }
        }
        if (resize)
          cbuf(bt + 131072);
        var lms = (1 << lbt) - 1, dms = (1 << dbt) - 1;
        var lpos = pos;
        for (; ; lpos = pos) {
          var c = lm[bits16(dat, pos) & lms], sym = c >> 4;
          pos += c & 15;
          if (pos > tbts) {
            if (noSt)
              err(0);
            break;
          }
          if (!c)
            err(2);
          if (sym < 256)
            buf[bt++] = sym;
          else if (sym == 256) {
            lpos = pos, lm = null;
            break;
          } else {
            var add7 = sym - 254;
            if (sym > 264) {
              var i2 = sym - 257, b = fleb[i2];
              add7 = bits(dat, pos, (1 << b) - 1) + fl[i2];
              pos += b;
            }
            var d = dm[bits16(dat, pos) & dms], dsym = d >> 4;
            if (!d)
              err(3);
            pos += d & 15;
            var dt = fd[dsym];
            if (dsym > 3) {
              var b = fdeb[dsym];
              dt += bits16(dat, pos) & (1 << b) - 1, pos += b;
            }
            if (pos > tbts) {
              if (noSt)
                err(0);
              break;
            }
            if (resize)
              cbuf(bt + 131072);
            var end = bt + add7;
            if (bt < dt) {
              var shift = dl - dt, dend = Math.min(dt, end);
              if (shift + bt < 0)
                err(3);
              for (; bt < dend; ++bt)
                buf[bt] = dict[shift + bt];
            }
            for (; bt < end; ++bt)
              buf[bt] = buf[bt - dt];
          }
        }
        st.l = lm, st.p = lpos, st.b = bt, st.f = final;
        if (lm)
          final = 1, st.m = lbt, st.d = dm, st.n = dbt;
      } while (!final);
      return bt != buf.length && noBuf ? slc(buf, 0, bt) : buf.subarray(0, bt);
    };
    var wbits = function(d, p, v) {
      v <<= p & 7;
      var o = p / 8 | 0;
      d[o] |= v;
      d[o + 1] |= v >> 8;
    };
    var wbits16 = function(d, p, v) {
      v <<= p & 7;
      var o = p / 8 | 0;
      d[o] |= v;
      d[o + 1] |= v >> 8;
      d[o + 2] |= v >> 16;
    };
    var hTree = function(d, mb) {
      var t = [];
      for (var i2 = 0; i2 < d.length; ++i2) {
        if (d[i2])
          t.push({ s: i2, f: d[i2] });
      }
      var s = t.length;
      var t2 = t.slice();
      if (!s)
        return { t: et, l: 0 };
      if (s == 1) {
        var v = new u8(t[0].s + 1);
        v[t[0].s] = 1;
        return { t: v, l: 1 };
      }
      t.sort(function(a, b) {
        return a.f - b.f;
      });
      t.push({ s: -1, f: 25001 });
      var l = t[0], r = t[1], i0 = 0, i1 = 1, i22 = 2;
      t[0] = { s: -1, f: l.f + r.f, l, r };
      while (i1 != s - 1) {
        l = t[t[i0].f < t[i22].f ? i0++ : i22++];
        r = t[i0 != i1 && t[i0].f < t[i22].f ? i0++ : i22++];
        t[i1++] = { s: -1, f: l.f + r.f, l, r };
      }
      var maxSym = t2[0].s;
      for (var i2 = 1; i2 < s; ++i2) {
        if (t2[i2].s > maxSym)
          maxSym = t2[i2].s;
      }
      var tr = new u16(maxSym + 1);
      var mbt = ln2(t[i1 - 1], tr, 0);
      if (mbt > mb) {
        var i2 = 0, dt = 0;
        var lft = mbt - mb, cst = 1 << lft;
        t2.sort(function(a, b) {
          return tr[b.s] - tr[a.s] || a.f - b.f;
        });
        for (; i2 < s; ++i2) {
          var i2_1 = t2[i2].s;
          if (tr[i2_1] > mb) {
            dt += cst - (1 << mbt - tr[i2_1]);
            tr[i2_1] = mb;
          } else
            break;
        }
        dt >>= lft;
        while (dt > 0) {
          var i2_2 = t2[i2].s;
          if (tr[i2_2] < mb)
            dt -= 1 << mb - tr[i2_2]++ - 1;
          else
            ++i2;
        }
        for (; i2 >= 0 && dt; --i2) {
          var i2_3 = t2[i2].s;
          if (tr[i2_3] == mb) {
            --tr[i2_3];
            ++dt;
          }
        }
        mbt = mb;
      }
      return { t: new u8(tr), l: mbt };
    };
    var ln2 = function(n, l, d) {
      return n.s == -1 ? Math.max(ln2(n.l, l, d + 1), ln2(n.r, l, d + 1)) : l[n.s] = d;
    };
    var lc = function(c) {
      var s = c.length;
      while (s && !c[--s])
        ;
      var cl = new u16(++s);
      var cli = 0, cln = c[0], cls = 1;
      var w = function(v) {
        cl[cli++] = v;
      };
      for (var i2 = 1; i2 <= s; ++i2) {
        if (c[i2] == cln && i2 != s)
          ++cls;
        else {
          if (!cln && cls > 2) {
            for (; cls > 138; cls -= 138)
              w(32754);
            if (cls > 2) {
              w(cls > 10 ? cls - 11 << 5 | 28690 : cls - 3 << 5 | 12305);
              cls = 0;
            }
          } else if (cls > 3) {
            w(cln), --cls;
            for (; cls > 6; cls -= 6)
              w(8304);
            if (cls > 2)
              w(cls - 3 << 5 | 8208), cls = 0;
          }
          while (cls--)
            w(cln);
          cls = 1;
          cln = c[i2];
        }
      }
      return { c: cl.subarray(0, cli), n: s };
    };
    var clen = function(cf, cl) {
      var l = 0;
      for (var i2 = 0; i2 < cl.length; ++i2)
        l += cf[i2] * cl[i2];
      return l;
    };
    var wfblk = function(out, pos, dat) {
      var s = dat.length;
      var o = shft(pos + 2);
      out[o] = s & 255;
      out[o + 1] = s >> 8;
      out[o + 2] = out[o] ^ 255;
      out[o + 3] = out[o + 1] ^ 255;
      for (var i2 = 0; i2 < s; ++i2)
        out[o + i2 + 4] = dat[i2];
      return (o + 4 + s) * 8;
    };
    var wblk = function(dat, out, final, syms, lf, df, eb, li, bs, bl, p) {
      wbits(out, p++, final);
      ++lf[256];
      var _a2 = hTree(lf, 15), dlt = _a2.t, mlb = _a2.l;
      var _b2 = hTree(df, 15), ddt = _b2.t, mdb = _b2.l;
      var _c = lc(dlt), lclt = _c.c, nlc = _c.n;
      var _d = lc(ddt), lcdt = _d.c, ndc = _d.n;
      var lcfreq = new u16(19);
      for (var i2 = 0; i2 < lclt.length; ++i2)
        ++lcfreq[lclt[i2] & 31];
      for (var i2 = 0; i2 < lcdt.length; ++i2)
        ++lcfreq[lcdt[i2] & 31];
      var _e = hTree(lcfreq, 7), lct = _e.t, mlcb = _e.l;
      var nlcc = 19;
      for (; nlcc > 4 && !lct[clim[nlcc - 1]]; --nlcc)
        ;
      var flen = bl + 5 << 3;
      var ftlen = clen(lf, flt) + clen(df, fdt) + eb;
      var dtlen = clen(lf, dlt) + clen(df, ddt) + eb + 14 + 3 * nlcc + clen(lcfreq, lct) + 2 * lcfreq[16] + 3 * lcfreq[17] + 7 * lcfreq[18];
      if (bs >= 0 && flen <= ftlen && flen <= dtlen)
        return wfblk(out, p, dat.subarray(bs, bs + bl));
      var lm, ll, dm, dl;
      wbits(out, p, 1 + (dtlen < ftlen)), p += 2;
      if (dtlen < ftlen) {
        lm = hMap(dlt, mlb, 0), ll = dlt, dm = hMap(ddt, mdb, 0), dl = ddt;
        var llm = hMap(lct, mlcb, 0);
        wbits(out, p, nlc - 257);
        wbits(out, p + 5, ndc - 1);
        wbits(out, p + 10, nlcc - 4);
        p += 14;
        for (var i2 = 0; i2 < nlcc; ++i2)
          wbits(out, p + 3 * i2, lct[clim[i2]]);
        p += 3 * nlcc;
        var lcts = [lclt, lcdt];
        for (var it = 0; it < 2; ++it) {
          var clct = lcts[it];
          for (var i2 = 0; i2 < clct.length; ++i2) {
            var len4 = clct[i2] & 31;
            wbits(out, p, llm[len4]), p += lct[len4];
            if (len4 > 15)
              wbits(out, p, clct[i2] >> 5 & 127), p += clct[i2] >> 12;
          }
        }
      } else {
        lm = flm, ll = flt, dm = fdm, dl = fdt;
      }
      for (var i2 = 0; i2 < li; ++i2) {
        var sym = syms[i2];
        if (sym > 255) {
          var len4 = sym >> 18 & 31;
          wbits16(out, p, lm[len4 + 257]), p += ll[len4 + 257];
          if (len4 > 7)
            wbits(out, p, sym >> 23 & 31), p += fleb[len4];
          var dst = sym & 31;
          wbits16(out, p, dm[dst]), p += dl[dst];
          if (dst > 3)
            wbits16(out, p, sym >> 5 & 8191), p += fdeb[dst];
        } else {
          wbits16(out, p, lm[sym]), p += ll[sym];
        }
      }
      wbits16(out, p, lm[256]);
      return p + ll[256];
    };
    var deo = /* @__PURE__ */ new i32([65540, 131080, 131088, 131104, 262176, 1048704, 1048832, 2114560, 2117632]);
    var et = /* @__PURE__ */ new u8(0);
    var dflt = function(dat, lvl, plvl, pre, post, st) {
      var s = st.z || dat.length;
      var o = new u8(pre + s + 5 * (1 + Math.ceil(s / 7e3)) + post);
      var w = o.subarray(pre, o.length - post);
      var lst = st.l;
      var pos = (st.r || 0) & 7;
      if (lvl) {
        if (pos)
          w[0] = st.r >> 3;
        var opt = deo[lvl - 1];
        var n = opt >> 13, c = opt & 8191;
        var msk_1 = (1 << plvl) - 1;
        var prev = st.p || new u16(32768), head = st.h || new u16(msk_1 + 1);
        var bs1_1 = Math.ceil(plvl / 3), bs2_1 = 2 * bs1_1;
        var hsh = function(i3) {
          return (dat[i3] ^ dat[i3 + 1] << bs1_1 ^ dat[i3 + 2] << bs2_1) & msk_1;
        };
        var syms = new i32(25e3);
        var lf = new u16(288), df = new u16(32);
        var lc_1 = 0, eb = 0, i2 = st.i || 0, li = 0, wi = st.w || 0, bs = 0;
        for (; i2 + 2 < s; ++i2) {
          var hv = hsh(i2);
          var imod = i2 & 32767, pimod = head[hv];
          prev[imod] = pimod;
          head[hv] = imod;
          if (wi <= i2) {
            var rem = s - i2;
            if ((lc_1 > 7e3 || li > 24576) && (rem > 423 || !lst)) {
              pos = wblk(dat, w, 0, syms, lf, df, eb, li, bs, i2 - bs, pos);
              li = lc_1 = eb = 0, bs = i2;
              for (var j = 0; j < 286; ++j)
                lf[j] = 0;
              for (var j = 0; j < 30; ++j)
                df[j] = 0;
            }
            var l = 2, d = 0, ch_1 = c, dif = imod - pimod & 32767;
            if (rem > 2 && hv == hsh(i2 - dif)) {
              var maxn = Math.min(n, rem) - 1;
              var maxd = Math.min(32767, i2);
              var ml = Math.min(258, rem);
              while (dif <= maxd && --ch_1 && imod != pimod) {
                if (dat[i2 + l] == dat[i2 + l - dif]) {
                  var nl = 0;
                  for (; nl < ml && dat[i2 + nl] == dat[i2 + nl - dif]; ++nl)
                    ;
                  if (nl > l) {
                    l = nl, d = dif;
                    if (nl > maxn)
                      break;
                    var mmd = Math.min(dif, nl - 2);
                    var md = 0;
                    for (var j = 0; j < mmd; ++j) {
                      var ti = i2 - dif + j & 32767;
                      var pti = prev[ti];
                      var cd = ti - pti & 32767;
                      if (cd > md)
                        md = cd, pimod = ti;
                    }
                  }
                }
                imod = pimod, pimod = prev[imod];
                dif += imod - pimod & 32767;
              }
            }
            if (d) {
              syms[li++] = 268435456 | revfl[l] << 18 | revfd[d];
              var lin = revfl[l] & 31, din = revfd[d] & 31;
              eb += fleb[lin] + fdeb[din];
              ++lf[257 + lin];
              ++df[din];
              wi = i2 + l;
              ++lc_1;
            } else {
              syms[li++] = dat[i2];
              ++lf[dat[i2]];
            }
          }
        }
        for (i2 = Math.max(i2, wi); i2 < s; ++i2) {
          syms[li++] = dat[i2];
          ++lf[dat[i2]];
        }
        pos = wblk(dat, w, lst, syms, lf, df, eb, li, bs, i2 - bs, pos);
        if (!lst) {
          st.r = pos & 7 | w[pos / 8 | 0] << 3;
          pos -= 7;
          st.h = head, st.p = prev, st.i = i2, st.w = wi;
        }
      } else {
        for (var i2 = st.w || 0; i2 < s + lst; i2 += 65535) {
          var e = i2 + 65535;
          if (e >= s) {
            w[pos / 8 | 0] = lst;
            e = s;
          }
          pos = wfblk(w, pos + 1, dat.subarray(i2, e));
        }
        st.i = s;
      }
      return slc(o, 0, pre + shft(pos) + post);
    };
    var crct = /* @__PURE__ */ (function() {
      var t = new Int32Array(256);
      for (var i2 = 0; i2 < 256; ++i2) {
        var c = i2, k = 9;
        while (--k)
          c = (c & 1 && -306674912) ^ c >>> 1;
        t[i2] = c;
      }
      return t;
    })();
    var crc = function() {
      var c = -1;
      return {
        p: function(d) {
          var cr = c;
          for (var i2 = 0; i2 < d.length; ++i2)
            cr = crct[cr & 255 ^ d[i2]] ^ cr >>> 8;
          c = cr;
        },
        d: function() {
          return ~c;
        }
      };
    };
    var adler = function() {
      var a = 1, b = 0;
      return {
        p: function(d) {
          var n = a, m = b;
          var l = d.length | 0;
          for (var i2 = 0; i2 != l; ) {
            var e = Math.min(i2 + 2655, l);
            for (; i2 < e; ++i2)
              m += n += d[i2];
            n = (n & 65535) + 15 * (n >> 16), m = (m & 65535) + 15 * (m >> 16);
          }
          a = n, b = m;
        },
        d: function() {
          a %= 65521, b %= 65521;
          return (a & 255) << 24 | (a & 65280) << 8 | (b & 255) << 8 | b >> 8;
        }
      };
    };
    var dopt = function(dat, opt, pre, post, st) {
      if (!st) {
        st = { l: 1 };
        if (opt.dictionary) {
          var dict = opt.dictionary.subarray(-32768);
          var newDat = new u8(dict.length + dat.length);
          newDat.set(dict);
          newDat.set(dat, dict.length);
          dat = newDat;
          st.w = dict.length;
        }
      }
      return dflt(dat, opt.level == null ? 6 : opt.level, opt.mem == null ? st.l ? Math.ceil(Math.max(8, Math.min(13, Math.log(dat.length))) * 1.5) : 20 : 12 + opt.mem, pre, post, st);
    };
    var mrg = function(a, b) {
      var o = {};
      for (var k in a)
        o[k] = a[k];
      for (var k in b)
        o[k] = b[k];
      return o;
    };
    var wcln = function(fn, fnStr, td2) {
      var dt = fn();
      var st = fn.toString();
      var ks = st.slice(st.indexOf("[") + 1, st.lastIndexOf("]")).replace(/\s+/g, "").split(",");
      for (var i2 = 0; i2 < dt.length; ++i2) {
        var v = dt[i2], k = ks[i2];
        if (typeof v == "function") {
          fnStr += ";" + k + "=";
          var st_1 = v.toString();
          if (v.prototype) {
            if (st_1.indexOf("[native code]") != -1) {
              var spInd = st_1.indexOf(" ", 8) + 1;
              fnStr += st_1.slice(spInd, st_1.indexOf("(", spInd));
            } else {
              fnStr += st_1;
              for (var t in v.prototype)
                fnStr += ";" + k + ".prototype." + t + "=" + v.prototype[t].toString();
            }
          } else
            fnStr += st_1;
        } else
          td2[k] = v;
      }
      return fnStr;
    };
    var ch = [];
    var cbfs = function(v) {
      var tl = [];
      for (var k in v) {
        if (v[k].buffer) {
          tl.push((v[k] = new v[k].constructor(v[k])).buffer);
        }
      }
      return tl;
    };
    var wrkr = function(fns, init, id, cb) {
      if (!ch[id]) {
        var fnStr = "", td_1 = {}, m = fns.length - 1;
        for (var i2 = 0; i2 < m; ++i2)
          fnStr = wcln(fns[i2], fnStr, td_1);
        ch[id] = { c: wcln(fns[m], fnStr, td_1), e: td_1 };
      }
      var td2 = mrg({}, ch[id].e);
      return (0, node_worker_1.default)(ch[id].c + ";onmessage=function(e){for(var k in e.data)self[k]=e.data[k];onmessage=" + init.toString() + "}", id, td2, cbfs(td2), cb);
    };
    var bInflt = function() {
      return [u8, u16, i32, fleb, fdeb, clim, fl, fd, flrm, fdrm, rev, ec, hMap, max4, bits, bits16, shft, slc, err, inflt, inflateSync, pbf, gopt];
    };
    var bDflt = function() {
      return [u8, u16, i32, fleb, fdeb, clim, revfl, revfd, flm, flt, fdm, fdt, rev, deo, et, hMap, wbits, wbits16, hTree, ln2, lc, clen, wfblk, wblk, shft, slc, dflt, dopt, deflateSync, pbf];
    };
    var gze = function() {
      return [gzh, gzhl, wbytes, crc, crct];
    };
    var guze = function() {
      return [gzs, gzl];
    };
    var zle = function() {
      return [zlh, wbytes, adler];
    };
    var zule = function() {
      return [zls];
    };
    var pbf = function(msg) {
      return postMessage(msg, [msg.buffer]);
    };
    var gopt = function(o) {
      return o && {
        out: o.size && new u8(o.size),
        dictionary: o.dictionary
      };
    };
    var cbify = function(dat, opts, fns, init, id, cb) {
      var w = wrkr(fns, init, id, function(err2, dat2) {
        w.terminate();
        cb(err2, dat2);
      });
      w.postMessage([dat, opts], opts.consume ? [dat.buffer] : []);
      return function() {
        w.terminate();
      };
    };
    var astrm = function(strm) {
      strm.ondata = function(dat, final) {
        return postMessage([dat, final], [dat.buffer]);
      };
      return function(ev) {
        if (ev.data[0]) {
          strm.push(ev.data[0], ev.data[1]);
          postMessage([ev.data[0].length]);
        } else
          strm.flush(ev.data[1]);
      };
    };
    var astrmify = function(fns, strm, opts, init, id, flush, ext) {
      var t;
      var w = wrkr(fns, init, id, function(err2, dat) {
        if (err2)
          w.terminate(), strm.ondata.call(strm, err2);
        else if (!Array.isArray(dat))
          ext(dat);
        else if (dat.length == 1) {
          strm.queuedSize -= dat[0];
          if (strm.ondrain)
            strm.ondrain(dat[0]);
        } else {
          if (dat[1])
            w.terminate();
          strm.ondata.call(strm, err2, dat[0], dat[1]);
        }
      });
      w.postMessage(opts);
      strm.queuedSize = 0;
      strm.push = function(d, f) {
        if (!strm.ondata)
          err(5);
        if (t)
          strm.ondata(err(4, 0, 1), null, !!f);
        strm.queuedSize += d.length;
        w.postMessage([d, t = f], d.buffer instanceof ArrayBuffer ? [d.buffer] : []);
      };
      strm.terminate = function() {
        w.terminate();
      };
      if (flush) {
        strm.flush = function(sync) {
          w.postMessage([0, sync]);
        };
      }
    };
    var b2 = function(d, b) {
      return d[b] | d[b + 1] << 8;
    };
    var b4 = function(d, b) {
      return (d[b] | d[b + 1] << 8 | d[b + 2] << 16 | d[b + 3] << 24) >>> 0;
    };
    var b8 = function(d, b) {
      return b4(d, b) + b4(d, b + 4) * 4294967296;
    };
    var wbytes = function(d, b, v) {
      for (; v; ++b)
        d[b] = v, v >>>= 8;
    };
    var gzh = function(c, o) {
      var fn = o.filename;
      c[0] = 31, c[1] = 139, c[2] = 8, c[8] = o.level < 2 ? 4 : o.level == 9 ? 2 : 0, c[9] = 3;
      if (o.mtime != 0)
        wbytes(c, 4, Math.floor(new Date(o.mtime || Date.now()) / 1e3));
      if (fn) {
        c[3] = 8;
        for (var i2 = 0; i2 <= fn.length; ++i2)
          c[i2 + 10] = fn.charCodeAt(i2);
      }
    };
    var gzs = function(d) {
      if (d[0] != 31 || d[1] != 139 || d[2] != 8)
        err(6, "invalid gzip data");
      var flg = d[3];
      var st = 10;
      if (flg & 4)
        st += (d[10] | d[11] << 8) + 2;
      for (var zs = (flg >> 3 & 1) + (flg >> 4 & 1); zs > 0; zs -= !d[st++])
        ;
      return st + (flg & 2);
    };
    var gzl = function(d) {
      var l = d.length;
      return (d[l - 4] | d[l - 3] << 8 | d[l - 2] << 16 | d[l - 1] << 24) >>> 0;
    };
    var gzhl = function(o) {
      return 10 + (o.filename ? o.filename.length + 1 : 0);
    };
    var zlh = function(c, o) {
      var lv = o.level, fl2 = lv == 0 ? 0 : lv < 6 ? 1 : lv == 9 ? 3 : 2;
      c[0] = 120, c[1] = fl2 << 6 | (o.dictionary && 32);
      c[1] |= 31 - (c[0] << 8 | c[1]) % 31;
      if (o.dictionary) {
        var h = adler();
        h.p(o.dictionary);
        wbytes(c, 2, h.d());
      }
    };
    var zls = function(d, dict) {
      if ((d[0] & 15) != 8 || d[0] >> 4 > 7 || (d[0] << 8 | d[1]) % 31)
        err(6, "invalid zlib data");
      if ((d[1] >> 5 & 1) == +!dict)
        err(6, "invalid zlib data: " + (d[1] & 32 ? "need" : "unexpected") + " dictionary");
      return (d[1] >> 3 & 4) + 2;
    };
    function StrmOpt(opts, cb) {
      if (typeof opts == "function")
        cb = opts, opts = {};
      this.ondata = cb;
      return opts;
    }
    var Deflate = /* @__PURE__ */ (function() {
      function Deflate2(opts, cb) {
        if (typeof opts == "function")
          cb = opts, opts = {};
        this.ondata = cb;
        this.o = opts || {};
        this.s = { l: 0, i: 32768, w: 32768, z: 32768 };
        this.b = new u8(98304);
        if (this.o.dictionary) {
          var dict = this.o.dictionary.subarray(-32768);
          this.b.set(dict, 32768 - dict.length);
          this.s.i = 32768 - dict.length;
        }
      }
      Deflate2.prototype.p = function(c, f) {
        this.ondata(dopt(c, this.o, 0, 0, this.s), f);
      };
      Deflate2.prototype.push = function(chunk, final) {
        if (!this.ondata)
          err(5);
        if (this.s.l)
          err(4);
        var endLen = chunk.length + this.s.z;
        if (endLen > this.b.length) {
          if (endLen > 2 * this.b.length - 32768) {
            var newBuf = new u8(endLen & -32768);
            newBuf.set(this.b.subarray(0, this.s.z));
            this.b = newBuf;
          }
          var split = this.b.length - this.s.z;
          this.b.set(chunk.subarray(0, split), this.s.z);
          this.s.z = this.b.length;
          this.p(this.b, false);
          this.b.set(this.b.subarray(-32768));
          this.b.set(chunk.subarray(split), 32768);
          this.s.z = chunk.length - split + 32768;
          this.s.i = 32766, this.s.w = 32768;
        } else {
          this.b.set(chunk, this.s.z);
          this.s.z += chunk.length;
        }
        this.s.l = final & 1;
        if (this.s.z > this.s.w + 8191 || final) {
          this.p(this.b, final || false);
          this.s.w = this.s.i, this.s.i -= 2;
        }
        if (final) {
          this.s = this.o = {};
          this.b = et;
        }
      };
      Deflate2.prototype.flush = function(sync) {
        if (!this.ondata)
          err(5);
        if (this.s.l)
          err(4);
        this.p(this.b, false);
        this.s.w = this.s.i, this.s.i -= 2;
        if (sync) {
          var c = new u8(6);
          c[0] = this.s.r >> 3;
          var ep = wfblk(c, this.s.r, et);
          this.s.r = 0;
          this.ondata(c.subarray(0, ep >> 3), false);
        }
      };
      return Deflate2;
    })();
    exports.Deflate = Deflate;
    var AsyncDeflate = /* @__PURE__ */ (function() {
      function AsyncDeflate2(opts, cb) {
        astrmify([
          bDflt,
          function() {
            return [astrm, Deflate];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Deflate(ev.data);
          onmessage = astrm(strm);
        }, 6, 1);
      }
      return AsyncDeflate2;
    })();
    exports.AsyncDeflate = AsyncDeflate;
    function deflate(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bDflt
      ], function(ev) {
        return pbf(deflateSync(ev.data[0], ev.data[1]));
      }, 0, cb);
    }
    function deflateSync(data, opts) {
      return dopt(data, opts || {}, 0, 0);
    }
    var Inflate = /* @__PURE__ */ (function() {
      function Inflate2(opts, cb) {
        if (typeof opts == "function")
          cb = opts, opts = {};
        this.ondata = cb;
        var dict = opts && opts.dictionary && opts.dictionary.subarray(-32768);
        this.s = { i: 0, b: dict ? dict.length : 0 };
        this.o = new u8(32768);
        this.p = new u8(0);
        if (dict)
          this.o.set(dict);
      }
      Inflate2.prototype.e = function(c) {
        if (!this.ondata)
          err(5);
        if (this.d)
          err(4);
        if (!this.p.length)
          this.p = c;
        else if (c.length) {
          var n = new u8(this.p.length + c.length);
          n.set(this.p), n.set(c, this.p.length), this.p = n;
        }
      };
      Inflate2.prototype.c = function(final) {
        this.s.i = +(this.d = final || false);
        var bts = this.s.b;
        var dt = inflt(this.p, this.s, this.o);
        this.ondata(slc(dt, bts, this.s.b), this.d);
        this.o = slc(dt, this.s.b - 32768), this.s.b = this.o.length;
        this.p = slc(this.p, this.s.p / 8 | 0), this.s.p &= 7;
      };
      Inflate2.prototype.push = function(chunk, final) {
        this.e(chunk), this.c(final);
      };
      return Inflate2;
    })();
    exports.Inflate = Inflate;
    var AsyncInflate = /* @__PURE__ */ (function() {
      function AsyncInflate2(opts, cb) {
        astrmify([
          bInflt,
          function() {
            return [astrm, Inflate];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Inflate(ev.data);
          onmessage = astrm(strm);
        }, 7, 0);
      }
      return AsyncInflate2;
    })();
    exports.AsyncInflate = AsyncInflate;
    function inflate(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bInflt
      ], function(ev) {
        return pbf(inflateSync(ev.data[0], gopt(ev.data[1])));
      }, 1, cb);
    }
    function inflateSync(data, opts) {
      return inflt(data, { i: 2 }, opts && opts.out, opts && opts.dictionary);
    }
    var Gzip = /* @__PURE__ */ (function() {
      function Gzip2(opts, cb) {
        this.c = crc();
        this.l = 0;
        this.v = 1;
        Deflate.call(this, opts, cb);
      }
      Gzip2.prototype.push = function(chunk, final) {
        this.c.p(chunk);
        this.l += chunk.length;
        Deflate.prototype.push.call(this, chunk, final);
      };
      Gzip2.prototype.p = function(c, f) {
        var raw = dopt(c, this.o, this.v && gzhl(this.o), f && 8, this.s);
        if (this.v)
          gzh(raw, this.o), this.v = 0;
        if (f)
          wbytes(raw, raw.length - 8, this.c.d()), wbytes(raw, raw.length - 4, this.l);
        this.ondata(raw, f);
      };
      Gzip2.prototype.flush = function(sync) {
        Deflate.prototype.flush.call(this, sync);
      };
      return Gzip2;
    })();
    exports.Gzip = Gzip;
    exports.Compress = Gzip;
    var AsyncGzip = /* @__PURE__ */ (function() {
      function AsyncGzip2(opts, cb) {
        astrmify([
          bDflt,
          gze,
          function() {
            return [astrm, Deflate, Gzip];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Gzip(ev.data);
          onmessage = astrm(strm);
        }, 8, 1);
      }
      return AsyncGzip2;
    })();
    exports.AsyncGzip = AsyncGzip;
    exports.AsyncCompress = AsyncGzip;
    function gzip(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bDflt,
        gze,
        function() {
          return [gzipSync];
        }
      ], function(ev) {
        return pbf(gzipSync(ev.data[0], ev.data[1]));
      }, 2, cb);
    }
    function gzipSync(data, opts) {
      if (!opts)
        opts = {};
      var c = crc(), l = data.length;
      c.p(data);
      var d = dopt(data, opts, gzhl(opts), 8), s = d.length;
      return gzh(d, opts), wbytes(d, s - 8, c.d()), wbytes(d, s - 4, l), d;
    }
    var Gunzip = /* @__PURE__ */ (function() {
      function Gunzip2(opts, cb) {
        this.v = 1;
        this.r = 0;
        Inflate.call(this, opts, cb);
      }
      Gunzip2.prototype.push = function(chunk, final) {
        Inflate.prototype.e.call(this, chunk);
        this.r += chunk.length;
        if (this.v) {
          var p = this.p.subarray(this.v - 1);
          var s = p.length > 3 ? gzs(p) : 4;
          if (s > p.length) {
            if (!final)
              return;
          } else if (this.v > 1 && this.onmember) {
            this.onmember(this.r - p.length);
          }
          this.p = p.subarray(s), this.v = 0;
        }
        Inflate.prototype.c.call(this, 0);
        if (this.s.f && !this.s.l) {
          this.v = shft(this.s.p) + 9;
          this.s = { i: 0 };
          this.o = new u8(0);
          this.push(new u8(0), final);
        } else if (final) {
          Inflate.prototype.c.call(this, final);
        }
      };
      return Gunzip2;
    })();
    exports.Gunzip = Gunzip;
    var AsyncGunzip = /* @__PURE__ */ (function() {
      function AsyncGunzip2(opts, cb) {
        var _this = this;
        astrmify([
          bInflt,
          guze,
          function() {
            return [astrm, Inflate, Gunzip];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Gunzip(ev.data);
          strm.onmember = function(offset) {
            return postMessage(offset);
          };
          onmessage = astrm(strm);
        }, 9, 0, function(offset) {
          return _this.onmember && _this.onmember(offset);
        });
      }
      return AsyncGunzip2;
    })();
    exports.AsyncGunzip = AsyncGunzip;
    function gunzip(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bInflt,
        guze,
        function() {
          return [gunzipSync];
        }
      ], function(ev) {
        return pbf(gunzipSync(ev.data[0], ev.data[1]));
      }, 3, cb);
    }
    function gunzipSync(data, opts) {
      var st = gzs(data);
      if (st + 8 > data.length)
        err(6, "invalid gzip data");
      return inflt(data.subarray(st, -8), { i: 2 }, opts && opts.out || new u8(gzl(data)), opts && opts.dictionary);
    }
    var Zlib = /* @__PURE__ */ (function() {
      function Zlib2(opts, cb) {
        this.c = adler();
        this.v = 1;
        Deflate.call(this, opts, cb);
      }
      Zlib2.prototype.push = function(chunk, final) {
        this.c.p(chunk);
        Deflate.prototype.push.call(this, chunk, final);
      };
      Zlib2.prototype.p = function(c, f) {
        var raw = dopt(c, this.o, this.v && (this.o.dictionary ? 6 : 2), f && 4, this.s);
        if (this.v)
          zlh(raw, this.o), this.v = 0;
        if (f)
          wbytes(raw, raw.length - 4, this.c.d());
        this.ondata(raw, f);
      };
      Zlib2.prototype.flush = function(sync) {
        Deflate.prototype.flush.call(this, sync);
      };
      return Zlib2;
    })();
    exports.Zlib = Zlib;
    var AsyncZlib = /* @__PURE__ */ (function() {
      function AsyncZlib2(opts, cb) {
        astrmify([
          bDflt,
          zle,
          function() {
            return [astrm, Deflate, Zlib];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Zlib(ev.data);
          onmessage = astrm(strm);
        }, 10, 1);
      }
      return AsyncZlib2;
    })();
    exports.AsyncZlib = AsyncZlib;
    function zlib(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bDflt,
        zle,
        function() {
          return [zlibSync];
        }
      ], function(ev) {
        return pbf(zlibSync(ev.data[0], ev.data[1]));
      }, 4, cb);
    }
    function zlibSync(data, opts) {
      if (!opts)
        opts = {};
      var a = adler();
      a.p(data);
      var d = dopt(data, opts, opts.dictionary ? 6 : 2, 4);
      return zlh(d, opts), wbytes(d, d.length - 4, a.d()), d;
    }
    var Unzlib = /* @__PURE__ */ (function() {
      function Unzlib2(opts, cb) {
        Inflate.call(this, opts, cb);
        this.v = opts && opts.dictionary ? 2 : 1;
      }
      Unzlib2.prototype.push = function(chunk, final) {
        Inflate.prototype.e.call(this, chunk);
        if (this.v) {
          if (this.p.length < 6 && !final)
            return;
          this.p = this.p.subarray(zls(this.p, this.v - 1)), this.v = 0;
        }
        if (final) {
          if (this.p.length < 4)
            err(6, "invalid zlib data");
          this.p = this.p.subarray(0, -4);
        }
        Inflate.prototype.c.call(this, final);
      };
      return Unzlib2;
    })();
    exports.Unzlib = Unzlib;
    var AsyncUnzlib = /* @__PURE__ */ (function() {
      function AsyncUnzlib2(opts, cb) {
        astrmify([
          bInflt,
          zule,
          function() {
            return [astrm, Inflate, Unzlib];
          }
        ], this, StrmOpt.call(this, opts, cb), function(ev) {
          var strm = new Unzlib(ev.data);
          onmessage = astrm(strm);
        }, 11, 0);
      }
      return AsyncUnzlib2;
    })();
    exports.AsyncUnzlib = AsyncUnzlib;
    function unzlib(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return cbify(data, opts, [
        bInflt,
        zule,
        function() {
          return [unzlibSync];
        }
      ], function(ev) {
        return pbf(unzlibSync(ev.data[0], gopt(ev.data[1])));
      }, 5, cb);
    }
    function unzlibSync(data, opts) {
      return inflt(data.subarray(zls(data, opts && opts.dictionary), -4), { i: 2 }, opts && opts.out, opts && opts.dictionary);
    }
    var Decompress = /* @__PURE__ */ (function() {
      function Decompress2(opts, cb) {
        this.o = StrmOpt.call(this, opts, cb) || {};
        this.G = Gunzip;
        this.I = Inflate;
        this.Z = Unzlib;
      }
      Decompress2.prototype.i = function() {
        var _this = this;
        this.s.ondata = function(dat, final) {
          _this.ondata(dat, final);
        };
      };
      Decompress2.prototype.push = function(chunk, final) {
        if (!this.ondata)
          err(5);
        if (!this.s) {
          if (this.p && this.p.length) {
            var n = new u8(this.p.length + chunk.length);
            n.set(this.p), n.set(chunk, this.p.length);
          } else
            this.p = chunk;
          if (this.p.length > 2) {
            this.s = this.p[0] == 31 && this.p[1] == 139 && this.p[2] == 8 ? new this.G(this.o) : (this.p[0] & 15) != 8 || this.p[0] >> 4 > 7 || (this.p[0] << 8 | this.p[1]) % 31 ? new this.I(this.o) : new this.Z(this.o);
            this.i();
            this.s.push(this.p, final);
            this.p = null;
          }
        } else
          this.s.push(chunk, final);
      };
      return Decompress2;
    })();
    exports.Decompress = Decompress;
    var AsyncDecompress = /* @__PURE__ */ (function() {
      function AsyncDecompress2(opts, cb) {
        Decompress.call(this, opts, cb);
        this.queuedSize = 0;
        this.G = AsyncGunzip;
        this.I = AsyncInflate;
        this.Z = AsyncUnzlib;
      }
      AsyncDecompress2.prototype.i = function() {
        var _this = this;
        this.s.ondata = function(err2, dat, final) {
          _this.ondata(err2, dat, final);
        };
        this.s.ondrain = function(size) {
          _this.queuedSize -= size;
          if (_this.ondrain)
            _this.ondrain(size);
        };
      };
      AsyncDecompress2.prototype.push = function(chunk, final) {
        this.queuedSize += chunk.length;
        Decompress.prototype.push.call(this, chunk, final);
      };
      return AsyncDecompress2;
    })();
    exports.AsyncDecompress = AsyncDecompress;
    function decompress(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      return data[0] == 31 && data[1] == 139 && data[2] == 8 ? gunzip(data, opts, cb) : (data[0] & 15) != 8 || data[0] >> 4 > 7 || (data[0] << 8 | data[1]) % 31 ? inflate(data, opts, cb) : unzlib(data, opts, cb);
    }
    function decompressSync(data, opts) {
      return data[0] == 31 && data[1] == 139 && data[2] == 8 ? gunzipSync(data, opts) : (data[0] & 15) != 8 || data[0] >> 4 > 7 || (data[0] << 8 | data[1]) % 31 ? inflateSync(data, opts) : unzlibSync(data, opts);
    }
    var fltn = function(d, p, t, o) {
      for (var k in d) {
        var val = d[k], n = p + k, op = o;
        if (Array.isArray(val))
          op = mrg(o, val[1]), val = val[0];
        if (ArrayBuffer.isView(val))
          t[n] = [val, op];
        else {
          t[n += "/"] = [new u8(0), op];
          fltn(val, n, t, o);
        }
      }
    };
    var te = typeof TextEncoder != "undefined" && /* @__PURE__ */ new TextEncoder();
    var td = typeof TextDecoder != "undefined" && /* @__PURE__ */ new TextDecoder();
    var tds = 0;
    try {
      td.decode(et, { stream: true });
      tds = 1;
    } catch (e) {
    }
    var dutf8 = function(d) {
      for (var r = "", i2 = 0; ; ) {
        var c = d[i2++];
        var eb = (c > 127) + (c > 223) + (c > 239);
        if (i2 + eb > d.length)
          return { s: r, r: slc(d, i2 - 1) };
        if (!eb)
          r += String.fromCharCode(c);
        else if (eb == 3) {
          c = ((c & 15) << 18 | (d[i2++] & 63) << 12 | (d[i2++] & 63) << 6 | d[i2++] & 63) - 65536, r += String.fromCharCode(55296 | c >> 10, 56320 | c & 1023);
        } else if (eb & 1)
          r += String.fromCharCode((c & 31) << 6 | d[i2++] & 63);
        else
          r += String.fromCharCode((c & 15) << 12 | (d[i2++] & 63) << 6 | d[i2++] & 63);
      }
    };
    var DecodeUTF8 = /* @__PURE__ */ (function() {
      function DecodeUTF82(cb) {
        this.ondata = cb;
        if (tds)
          this.t = new TextDecoder();
        else
          this.p = et;
      }
      DecodeUTF82.prototype.push = function(chunk, final) {
        if (!this.ondata)
          err(5);
        final = !!final;
        if (this.t) {
          this.ondata(this.t.decode(chunk, { stream: true }), final);
          if (final) {
            if (this.t.decode().length)
              err(8);
            this.t = null;
          }
          return;
        }
        if (!this.p)
          err(4);
        var dat = new u8(this.p.length + chunk.length);
        dat.set(this.p);
        dat.set(chunk, this.p.length);
        var _a2 = dutf8(dat), s = _a2.s, r = _a2.r;
        if (final) {
          if (r.length)
            err(8);
          this.p = null;
        } else
          this.p = r;
        this.ondata(s, final);
      };
      return DecodeUTF82;
    })();
    exports.DecodeUTF8 = DecodeUTF8;
    var EncodeUTF8 = /* @__PURE__ */ (function() {
      function EncodeUTF82(cb) {
        this.ondata = cb;
      }
      EncodeUTF82.prototype.push = function(chunk, final) {
        if (!this.ondata)
          err(5);
        if (this.d)
          err(4);
        this.ondata(strToU8(chunk), this.d = final || false);
      };
      return EncodeUTF82;
    })();
    exports.EncodeUTF8 = EncodeUTF8;
    function strToU8(str6, latin1) {
      if (latin1) {
        var ar_1 = new u8(str6.length);
        for (var i2 = 0; i2 < str6.length; ++i2)
          ar_1[i2] = str6.charCodeAt(i2);
        return ar_1;
      }
      if (te)
        return te.encode(str6);
      var l = str6.length;
      var ar = new u8(str6.length + (str6.length >> 1));
      var ai = 0;
      var w = function(v) {
        ar[ai++] = v;
      };
      for (var i2 = 0; i2 < l; ++i2) {
        if (ai + 5 > ar.length) {
          var n = new u8(ai + 8 + (l - i2 << 1));
          n.set(ar);
          ar = n;
        }
        var c = str6.charCodeAt(i2);
        if (c < 128 || latin1)
          w(c);
        else if (c < 2048)
          w(192 | c >> 6), w(128 | c & 63);
        else if (c > 55295 && c < 57344)
          c = 65536 + (c & 1023 << 10) | str6.charCodeAt(++i2) & 1023, w(240 | c >> 18), w(128 | c >> 12 & 63), w(128 | c >> 6 & 63), w(128 | c & 63);
        else
          w(224 | c >> 12), w(128 | c >> 6 & 63), w(128 | c & 63);
      }
      return slc(ar, 0, ai);
    }
    function strFromU8(dat, latin1) {
      if (latin1) {
        var r = "";
        for (var i2 = 0; i2 < dat.length; i2 += 16384)
          r += String.fromCharCode.apply(null, dat.subarray(i2, i2 + 16384));
        return r;
      } else if (td) {
        return td.decode(dat);
      } else {
        var _a2 = dutf8(dat), s = _a2.s, r = _a2.r;
        if (r.length)
          err(8);
        return s;
      }
    }
    var dbf = function(l) {
      return l == 1 ? 3 : l < 6 ? 2 : l == 9 ? 1 : 0;
    };
    var slzh = function(d, b) {
      return b + 30 + b2(d, b + 26) + b2(d, b + 28);
    };
    var zh = function(d, b, z) {
      var fnl = b2(d, b + 28), efl = b2(d, b + 30), fn = strFromU8(d.subarray(b + 46, b + 46 + fnl), !(b2(d, b + 8) & 2048)), es = b + 46 + fnl;
      var _a2 = z64hs(d, es, efl, z, b4(d, b + 20), b4(d, b + 24), b4(d, b + 42)), sc = _a2[0], su = _a2[1], off = _a2[2];
      return [b2(d, b + 10), sc, su, fn, es + efl + b2(d, b + 32), off];
    };
    var z64hs = function(d, b, l, z, sc, su, off) {
      var nsc = sc == 4294967295, nsu = su == 4294967295, noff = off == 4294967295, e = b + l;
      var nf = nsc + nsu + noff;
      if (z && nf) {
        for (; b + 4 < e; b += 4 + b2(d, b + 2)) {
          if (b2(d, b) == 1) {
            return [
              nsc ? b8(d, b + 4 + 8 * nsu) : sc,
              nsu ? b8(d, b + 4) : su,
              noff ? b8(d, b + 4 + 8 * (nsu + nsc)) : off,
              1
            ];
          }
        }
        if (z < 2)
          err(13);
      }
      return [sc, su, off, 0];
    };
    var exfl = function(ex) {
      var le = 0;
      if (ex) {
        for (var k in ex) {
          var l = ex[k].length;
          if (l > 65535)
            err(9);
          le += l + 4;
        }
      }
      return le;
    };
    var wzh = function(d, b, f, fn, u, c, ce, co) {
      var fl2 = fn.length, ex = f.extra, col = co && co.length;
      var exl = exfl(ex);
      wbytes(d, b, ce != null ? 33639248 : 67324752), b += 4;
      if (ce != null)
        d[b++] = 20, d[b++] = f.os;
      d[b] = 20, b += 2;
      d[b++] = f.flag << 1 | (c < 0 && 8), d[b++] = u && 8;
      d[b++] = f.compression & 255, d[b++] = f.compression >> 8;
      var dt = new Date(f.mtime == null ? Date.now() : f.mtime), y = dt.getFullYear() - 1980;
      if (y < 0 || y > 119)
        err(10);
      wbytes(d, b, y << 25 | dt.getMonth() + 1 << 21 | dt.getDate() << 16 | dt.getHours() << 11 | dt.getMinutes() << 5 | dt.getSeconds() >> 1), b += 4;
      if (c != -1) {
        wbytes(d, b, f.crc);
        wbytes(d, b + 4, c < 0 ? -c - 2 : c);
        wbytes(d, b + 8, f.size);
      }
      wbytes(d, b + 12, fl2);
      wbytes(d, b + 14, exl), b += 16;
      if (ce != null) {
        wbytes(d, b, col);
        wbytes(d, b + 6, f.attrs);
        wbytes(d, b + 10, ce), b += 14;
      }
      d.set(fn, b);
      b += fl2;
      if (exl) {
        for (var k in ex) {
          var exf = ex[k], l = exf.length;
          wbytes(d, b, +k);
          wbytes(d, b + 2, l);
          d.set(exf, b + 4), b += 4 + l;
        }
      }
      if (col)
        d.set(co, b), b += col;
      return b;
    };
    var wzf = function(o, b, c, d, e) {
      wbytes(o, b, 101010256);
      wbytes(o, b + 8, c);
      wbytes(o, b + 10, c);
      wbytes(o, b + 12, d);
      wbytes(o, b + 16, e);
    };
    var ZipPassThrough = /* @__PURE__ */ (function() {
      function ZipPassThrough2(filename) {
        this.filename = filename;
        this.c = crc();
        this.size = 0;
        this.compression = 0;
      }
      ZipPassThrough2.prototype.process = function(chunk, final) {
        this.ondata(null, chunk, final);
      };
      ZipPassThrough2.prototype.push = function(chunk, final) {
        if (!this.ondata)
          err(5);
        this.c.p(chunk);
        this.size += chunk.length;
        if (final)
          this.crc = this.c.d();
        this.process(chunk, final || false);
      };
      return ZipPassThrough2;
    })();
    exports.ZipPassThrough = ZipPassThrough;
    var ZipDeflate = /* @__PURE__ */ (function() {
      function ZipDeflate2(filename, opts) {
        var _this = this;
        if (!opts)
          opts = {};
        ZipPassThrough.call(this, filename);
        this.d = new Deflate(opts, function(dat, final) {
          _this.ondata(null, dat, final);
        });
        this.compression = 8;
        this.flag = dbf(opts.level);
      }
      ZipDeflate2.prototype.process = function(chunk, final) {
        try {
          this.d.push(chunk, final);
        } catch (e) {
          this.ondata(e, null, final);
        }
      };
      ZipDeflate2.prototype.push = function(chunk, final) {
        ZipPassThrough.prototype.push.call(this, chunk, final);
      };
      return ZipDeflate2;
    })();
    exports.ZipDeflate = ZipDeflate;
    var AsyncZipDeflate = /* @__PURE__ */ (function() {
      function AsyncZipDeflate2(filename, opts) {
        var _this = this;
        if (!opts)
          opts = {};
        ZipPassThrough.call(this, filename);
        this.d = new AsyncDeflate(opts, function(err2, dat, final) {
          _this.ondata(err2, dat, final);
        });
        this.compression = 8;
        this.flag = dbf(opts.level);
        this.terminate = this.d.terminate;
      }
      AsyncZipDeflate2.prototype.process = function(chunk, final) {
        this.d.push(chunk, final);
      };
      AsyncZipDeflate2.prototype.push = function(chunk, final) {
        ZipPassThrough.prototype.push.call(this, chunk, final);
      };
      return AsyncZipDeflate2;
    })();
    exports.AsyncZipDeflate = AsyncZipDeflate;
    var Zip = /* @__PURE__ */ (function() {
      function Zip2(cb) {
        this.ondata = cb;
        this.u = [];
        this.d = 1;
      }
      Zip2.prototype.add = function(file) {
        var _this = this;
        if (!this.ondata)
          err(5);
        if (this.d & 2)
          this.ondata(err(4 + (this.d & 1) * 8, 0, 1), null, false);
        else {
          var f = strToU8(file.filename), fl_1 = f.length;
          var com = file.comment, o = com && strToU8(com);
          var u = fl_1 != file.filename.length || o && com.length != o.length;
          var hl_1 = fl_1 + exfl(file.extra) + 30;
          if (fl_1 > 65535)
            this.ondata(err(11, 0, 1), null, false);
          var header = new u8(hl_1);
          wzh(header, 0, file, f, u, -1);
          var chks_1 = [header];
          var pAll_1 = function() {
            for (var _i = 0, chks_2 = chks_1; _i < chks_2.length; _i++) {
              var chk = chks_2[_i];
              _this.ondata(null, chk, false);
            }
            chks_1 = [];
          };
          var tr_1 = this.d;
          this.d = 0;
          var ind_1 = this.u.length;
          var uf_1 = mrg(file, {
            f,
            u,
            o,
            t: function() {
              if (file.terminate)
                file.terminate();
            },
            r: function() {
              pAll_1();
              if (tr_1) {
                var nxt = _this.u[ind_1 + 1];
                if (nxt)
                  nxt.r();
                else
                  _this.d = 1;
              }
              tr_1 = 1;
            }
          });
          var cl_1 = 0;
          file.ondata = function(err2, dat, final) {
            if (err2) {
              _this.ondata(err2, dat, final);
              _this.terminate();
            } else {
              cl_1 += dat.length;
              chks_1.push(dat);
              if (final) {
                var dd = new u8(16);
                wbytes(dd, 0, 134695760);
                wbytes(dd, 4, file.crc);
                wbytes(dd, 8, cl_1);
                wbytes(dd, 12, file.size);
                chks_1.push(dd);
                uf_1.c = cl_1, uf_1.b = hl_1 + cl_1 + 16, uf_1.crc = file.crc, uf_1.size = file.size;
                if (tr_1)
                  uf_1.r();
                tr_1 = 1;
              } else if (tr_1)
                pAll_1();
            }
          };
          this.u.push(uf_1);
        }
      };
      Zip2.prototype.end = function() {
        var _this = this;
        if (this.d & 2) {
          this.ondata(err(4 + (this.d & 1) * 8, 0, 1), null, true);
          return;
        }
        if (this.d)
          this.e();
        else
          this.u.push({
            r: function() {
              if (!(_this.d & 1))
                return;
              _this.u.splice(-1, 1);
              _this.e();
            },
            t: function() {
            }
          });
        this.d = 3;
      };
      Zip2.prototype.e = function() {
        var bt = 0, l = 0, tl = 0;
        for (var _i = 0, _a2 = this.u; _i < _a2.length; _i++) {
          var f = _a2[_i];
          tl += 46 + f.f.length + exfl(f.extra) + (f.o ? f.o.length : 0);
        }
        var out = new u8(tl + 22);
        for (var _b2 = 0, _c = this.u; _b2 < _c.length; _b2++) {
          var f = _c[_b2];
          wzh(out, bt, f, f.f, f.u, -f.c - 2, l, f.o);
          bt += 46 + f.f.length + exfl(f.extra) + (f.o ? f.o.length : 0), l += f.b;
        }
        wzf(out, bt, this.u.length, tl, l);
        this.ondata(null, out, true);
        this.d = 2;
      };
      Zip2.prototype.terminate = function() {
        for (var _i = 0, _a2 = this.u; _i < _a2.length; _i++) {
          var f = _a2[_i];
          f.t();
        }
        this.d = 2;
      };
      return Zip2;
    })();
    exports.Zip = Zip;
    function zip(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      var r = {};
      fltn(data, "", r, opts);
      var k = Object.keys(r);
      var lft = k.length, o = 0, tot = 0;
      var slft = lft, files = new Array(lft);
      var term = [];
      var tAll = function() {
        for (var i3 = 0; i3 < term.length; ++i3)
          term[i3]();
      };
      var cbd = function(a, b) {
        mt(function() {
          cb(a, b);
        });
      };
      mt(function() {
        cbd = cb;
      });
      var cbf = function() {
        var out = new u8(tot + 22), oe = o, cdl = tot - o;
        tot = 0;
        for (var i3 = 0; i3 < slft; ++i3) {
          var f = files[i3];
          try {
            var l = f.c.length;
            wzh(out, tot, f, f.f, f.u, l);
            var badd = 30 + f.f.length + exfl(f.extra);
            var loc = tot + badd;
            out.set(f.c, loc);
            wzh(out, o, f, f.f, f.u, l, tot, f.m), o += 16 + badd + (f.m ? f.m.length : 0), tot = loc + l;
          } catch (e) {
            return cbd(e, null);
          }
        }
        wzf(out, o, files.length, cdl, oe);
        cbd(null, out);
      };
      if (!lft)
        cbf();
      var _loop_1 = function(i3) {
        var fn = k[i3];
        var _a2 = r[fn], file = _a2[0], p = _a2[1];
        var c = crc(), size = file.length;
        c.p(file);
        var f = strToU8(fn), s = f.length;
        var com = p.comment, m = com && strToU8(com), ms = m && m.length;
        var exl = exfl(p.extra);
        var compression = p.level == 0 ? 0 : 8;
        var cbl = function(e, d) {
          if (e) {
            tAll();
            cbd(e, null);
          } else {
            var l = d.length;
            files[i3] = mrg(p, {
              size,
              crc: c.d(),
              c: d,
              f,
              m,
              u: s != fn.length || m && com.length != ms,
              compression
            });
            o += 30 + s + exl + l;
            tot += 76 + 2 * (s + exl) + (ms || 0) + l;
            if (!--lft)
              cbf();
          }
        };
        if (s > 65535)
          cbl(err(11, 0, 1), null);
        if (!compression)
          cbl(null, file);
        else if (size < 16e4) {
          try {
            cbl(null, deflateSync(file, p));
          } catch (e) {
            cbl(e, null);
          }
        } else
          term.push(deflate(file, p, cbl));
      };
      for (var i2 = 0; i2 < slft; ++i2) {
        _loop_1(i2);
      }
      return tAll;
    }
    function zipSync(data, opts) {
      if (!opts)
        opts = {};
      var r = {};
      var files = [];
      fltn(data, "", r, opts);
      var o = 0;
      var tot = 0;
      for (var fn in r) {
        var _a2 = r[fn], file = _a2[0], p = _a2[1];
        var compression = p.level == 0 ? 0 : 8;
        var f = strToU8(fn), s = f.length;
        var com = p.comment, m = com && strToU8(com), ms = m && m.length;
        var exl = exfl(p.extra);
        if (s > 65535)
          err(11);
        var d = compression ? deflateSync(file, p) : file, l = d.length;
        var c = crc();
        c.p(file);
        files.push(mrg(p, {
          size: file.length,
          crc: c.d(),
          c: d,
          f,
          m,
          u: s != fn.length || m && com.length != ms,
          o,
          compression
        }));
        o += 30 + s + exl + l;
        tot += 76 + 2 * (s + exl) + (ms || 0) + l;
      }
      var out = new u8(tot + 22), oe = o, cdl = tot - o;
      for (var i2 = 0; i2 < files.length; ++i2) {
        var f = files[i2];
        wzh(out, f.o, f, f.f, f.u, f.c.length);
        var badd = 30 + f.f.length + exfl(f.extra);
        out.set(f.c, f.o + badd);
        wzh(out, o, f, f.f, f.u, f.c.length, f.o, f.m), o += 16 + badd + (f.m ? f.m.length : 0);
      }
      wzf(out, o, files.length, cdl, oe);
      return out;
    }
    var UnzipPassThrough = /* @__PURE__ */ (function() {
      function UnzipPassThrough2() {
      }
      UnzipPassThrough2.prototype.push = function(chunk, final) {
        this.ondata(null, chunk, final);
      };
      UnzipPassThrough2.compression = 0;
      return UnzipPassThrough2;
    })();
    exports.UnzipPassThrough = UnzipPassThrough;
    var UnzipInflate = /* @__PURE__ */ (function() {
      function UnzipInflate2() {
        var _this = this;
        this.i = new Inflate(function(dat, final) {
          _this.ondata(null, dat, final);
        });
      }
      UnzipInflate2.prototype.push = function(chunk, final) {
        try {
          this.i.push(chunk, final);
        } catch (e) {
          this.ondata(e, null, final);
        }
      };
      UnzipInflate2.compression = 8;
      return UnzipInflate2;
    })();
    exports.UnzipInflate = UnzipInflate;
    var AsyncUnzipInflate = /* @__PURE__ */ (function() {
      function AsyncUnzipInflate2(_, sz) {
        var _this = this;
        if (sz < 32e4) {
          this.i = new Inflate(function(dat, final) {
            _this.ondata(null, dat, final);
          });
        } else {
          this.i = new AsyncInflate(function(err2, dat, final) {
            _this.ondata(err2, dat, final);
          });
          this.terminate = this.i.terminate;
        }
      }
      AsyncUnzipInflate2.prototype.push = function(chunk, final) {
        if (this.i.terminate)
          chunk = slc(chunk, 0);
        this.i.push(chunk, final);
      };
      AsyncUnzipInflate2.compression = 8;
      return AsyncUnzipInflate2;
    })();
    exports.AsyncUnzipInflate = AsyncUnzipInflate;
    var Unzip = /* @__PURE__ */ (function() {
      function Unzip2(cb) {
        this.onfile = cb;
        this.k = [];
        this.o = {
          0: UnzipPassThrough
        };
        this.p = et;
      }
      Unzip2.prototype.push = function(chunk, final) {
        var _this = this;
        if (!this.onfile)
          err(5);
        if (!this.p)
          err(4);
        if (this.c > 0) {
          var len4 = Math.min(this.c, chunk.length);
          var toAdd = chunk.subarray(0, len4);
          this.c -= len4;
          if (this.d)
            this.d.push(toAdd, !this.c);
          else
            this.k[0].push(toAdd);
          chunk = chunk.subarray(len4);
          if (chunk.length)
            return this.push(chunk, final);
        } else {
          var f = 0, i2 = 0, is = void 0, buf = void 0;
          if (!this.p.length)
            buf = chunk;
          else if (!chunk.length)
            buf = this.p;
          else {
            buf = new u8(this.p.length + chunk.length);
            buf.set(this.p), buf.set(chunk, this.p.length);
          }
          var l = buf.length, oc = this.c, add7 = oc && this.d;
          var _loop_2 = function() {
            var sig = b4(buf, i2);
            if (sig == 67324752) {
              f = 1, is = i2;
              this_1.d = null;
              this_1.c = 0;
              var bf = b2(buf, i2 + 6), cmp_1 = b2(buf, i2 + 8), u = bf & 2048, dd = bf & 8, fnl = b2(buf, i2 + 26), es = b2(buf, i2 + 28);
              if (l > i2 + 30 + fnl + es) {
                var chks_3 = [];
                this_1.k.unshift(chks_3);
                f = 2;
                var lsc = b4(buf, i2 + 18), lsu = b4(buf, i2 + 22);
                var fn_1 = strFromU8(buf.subarray(i2 + 30, i2 += 30 + fnl), !u);
                var _a2 = z64hs(buf, i2, es, 2, lsc, lsu, 0), sc_1 = _a2[0], su_1 = _a2[1], z64 = _a2[3];
                if (dd)
                  sc_1 = -1 - z64;
                i2 += es;
                this_1.c = sc_1;
                var d_1;
                var file_1 = {
                  name: fn_1,
                  compression: cmp_1,
                  start: function() {
                    if (!file_1.ondata)
                      err(5);
                    if (!sc_1)
                      file_1.ondata(null, et, true);
                    else {
                      var ctr = _this.o[cmp_1];
                      if (!ctr)
                        file_1.ondata(err(14, "unknown compression type " + cmp_1, 1), null, false);
                      d_1 = sc_1 < 0 ? new ctr(fn_1) : new ctr(fn_1, sc_1, su_1);
                      d_1.ondata = function(err2, dat3, final2) {
                        file_1.ondata(err2, dat3, final2);
                      };
                      for (var _i = 0, chks_4 = chks_3; _i < chks_4.length; _i++) {
                        var dat2 = chks_4[_i];
                        d_1.push(dat2, false);
                      }
                      if (_this.k[0] == chks_3 && _this.c)
                        _this.d = d_1;
                      else
                        d_1.push(et, true);
                    }
                  },
                  terminate: function() {
                    if (d_1 && d_1.terminate)
                      d_1.terminate();
                  }
                };
                if (sc_1 >= 0)
                  file_1.size = sc_1, file_1.originalSize = su_1;
                this_1.onfile(file_1);
              }
              return "break";
            } else if (oc) {
              if (sig == 134695760) {
                is = i2 += 12 + (oc == -2 && 8), f = 3, this_1.c = 0;
                return "break";
              } else if (sig == 33639248) {
                is = i2 -= 4, f = 3, this_1.c = 0;
                return "break";
              }
            }
          };
          var this_1 = this;
          for (; i2 < l - 4; ++i2) {
            var state_1 = _loop_2();
            if (state_1 === "break")
              break;
          }
          this.p = et;
          if (oc < 0) {
            var dat = f ? buf.subarray(0, is - 12 - (oc == -2 && 8) - (b4(buf, is - 16) == 134695760 && 4)) : buf.subarray(0, i2);
            if (add7)
              add7.push(dat, !!f);
            else
              this.k[+(f == 2)].push(dat);
          }
          if (f & 2)
            return this.push(buf.subarray(i2), final);
          this.p = buf.subarray(i2);
        }
        if (final) {
          if (this.c)
            err(13);
          this.p = null;
        }
      };
      Unzip2.prototype.register = function(decoder2) {
        this.o[decoder2.compression] = decoder2;
      };
      return Unzip2;
    })();
    exports.Unzip = Unzip;
    var mt = typeof queueMicrotask == "function" ? queueMicrotask : typeof setTimeout == "function" ? setTimeout : function(fn) {
      fn();
    };
    function unzip(data, opts, cb) {
      if (!cb)
        cb = opts, opts = {};
      if (typeof cb != "function")
        err(7);
      var term = [];
      var tAll = function() {
        for (var i3 = 0; i3 < term.length; ++i3)
          term[i3]();
      };
      var files = {};
      var cbd = function(a, b) {
        mt(function() {
          cb(a, b);
        });
      };
      mt(function() {
        cbd = cb;
      });
      var e = data.length - 22;
      for (; b4(data, e) != 101010256; --e) {
        if (!e || data.length - e > 65558) {
          cbd(err(13, 0, 1), null);
          return tAll;
        }
      }
      ;
      var lft = b2(data, e + 8);
      if (lft) {
        var c = lft;
        var o = b4(data, e + 16);
        var z = b4(data, e - 20) == 117853008;
        if (z) {
          var ze = b4(data, e - 12);
          z = b4(data, ze) == 101075792;
          if (z) {
            c = lft = b4(data, ze + 32);
            o = b4(data, ze + 48);
          }
        }
        var fltr = opts && opts.filter;
        var _loop_3 = function(i3) {
          var _a2 = zh(data, o, z), c_1 = _a2[0], sc = _a2[1], su = _a2[2], fn = _a2[3], no = _a2[4], off = _a2[5], b = slzh(data, off);
          o = no;
          var cbl = function(e2, d) {
            if (e2) {
              tAll();
              cbd(e2, null);
            } else {
              if (d)
                files[fn] = d;
              if (!--lft)
                cbd(null, files);
            }
          };
          if (!fltr || fltr({
            name: fn,
            size: sc,
            originalSize: su,
            compression: c_1
          })) {
            if (!c_1)
              cbl(null, slc(data, b, b + sc));
            else if (c_1 == 8) {
              var infl = data.subarray(b, b + sc);
              if (su < 524288 || sc > 0.8 * su) {
                try {
                  cbl(null, inflateSync(infl, { out: new u8(su) }));
                } catch (e2) {
                  cbl(e2, null);
                }
              } else
                term.push(inflate(infl, { size: su }, cbl));
            } else
              cbl(err(14, "unknown compression type " + c_1, 1), null);
          } else
            cbl(null, null);
        };
        for (var i2 = 0; i2 < c; ++i2) {
          _loop_3(i2);
        }
      } else
        cbd(null, {});
      return tAll;
    }
    function unzipSync(data, opts) {
      var files = {};
      var e = data.length - 22;
      for (; b4(data, e) != 101010256; --e) {
        if (!e || data.length - e > 65558)
          err(13);
      }
      ;
      var c = b2(data, e + 8);
      if (!c)
        return {};
      var o = b4(data, e + 16);
      var z = b4(data, e - 20) == 117853008;
      if (z) {
        var ze = b4(data, e - 12);
        z = b4(data, ze) == 101075792;
        if (z) {
          c = b4(data, ze + 32);
          o = b4(data, ze + 48);
        }
      }
      var fltr = opts && opts.filter;
      for (var i2 = 0; i2 < c; ++i2) {
        var _a2 = zh(data, o, z), c_2 = _a2[0], sc = _a2[1], su = _a2[2], fn = _a2[3], no = _a2[4], off = _a2[5], b = slzh(data, off);
        o = no;
        if (!fltr || fltr({
          name: fn,
          size: sc,
          originalSize: su,
          compression: c_2
        })) {
          if (!c_2)
            files[fn] = slc(data, b, b + sc);
          else if (c_2 == 8)
            files[fn] = inflateSync(data.subarray(b, b + sc), { out: new u8(su) });
          else
            err(14, "unknown compression type " + c_2);
        }
      }
      return files;
    }
  }
});

// node_modules/nifti-reader-js/dist/src/nifti-extension.js
var require_nifti_extension = __commonJS({
  "node_modules/nifti-reader-js/dist/src/nifti-extension.js"(exports) {
    "use strict";
    init_legacy_browser();
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.NIFTIEXTENSION = void 0;
    var NIFTIEXTENSION = class {
      esize;
      ecode;
      edata;
      littleEndian;
      constructor(esize, ecode, edata, littleEndian) {
        if (esize % 16 != 0) {
          throw new Error("This does not appear to be a NIFTI extension");
        }
        this.esize = esize;
        this.ecode = ecode;
        this.edata = edata;
        this.littleEndian = littleEndian;
      }
      /**
       * Returns extension as ArrayBuffer.
       * @returns {ArrayBuffer}
       */
      toArrayBuffer() {
        let byteArray = new Uint8Array(this.esize);
        let data = new Uint8Array(this.edata);
        byteArray.set(data, 8);
        let view = new DataView(byteArray.buffer);
        view.setInt32(0, this.esize, this.littleEndian);
        view.setInt32(4, this.ecode, this.littleEndian);
        return byteArray.buffer;
      }
    };
    exports.NIFTIEXTENSION = NIFTIEXTENSION;
  }
});

// node_modules/nifti-reader-js/dist/src/utilities.js
var require_utilities = __commonJS({
  "node_modules/nifti-reader-js/dist/src/utilities.js"(exports) {
    "use strict";
    init_legacy_browser();
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.Utils = void 0;
    var nifti_extension_1 = require_nifti_extension();
    var Utils = class _Utils {
      /*** Static Pseudo-constants ***/
      static crcTable = null;
      static GUNZIP_MAGIC_COOKIE1 = 31;
      static GUNZIP_MAGIC_COOKIE2 = 139;
      /*** Static methods ***/
      static getStringAt(data, start, end) {
        var str6 = "", ctr, ch;
        for (ctr = start; ctr < end; ctr += 1) {
          ch = data.getUint8(ctr);
          if (ch !== 0) {
            str6 += String.fromCharCode(ch);
          }
        }
        return str6;
      }
      static getByteAt = function(data, start) {
        return data.getUint8(start);
      };
      static getShortAt = function(data, start, littleEndian) {
        return data.getInt16(start, littleEndian);
      };
      static getIntAt(data, start, littleEndian) {
        return data.getInt32(start, littleEndian);
      }
      static getFloatAt(data, start, littleEndian) {
        return data.getFloat32(start, littleEndian);
      }
      static getDoubleAt(data, start, littleEndian) {
        return data.getFloat64(start, littleEndian);
      }
      static getInt64At(dataView2, index, littleEndian) {
        const low = dataView2.getUint32(index, littleEndian);
        const high = dataView2.getInt32(index + 4, littleEndian);
        let result;
        if (littleEndian) {
          result = high * 2 ** 32 + low;
        } else {
          result = low * 2 ** 32 + high;
        }
        if (high < 0) {
          result += -1 * 2 ** 32 * 2 ** 32;
        }
        return result;
      }
      static getExtensionsAt(data, start, littleEndian, voxOffset) {
        let extensions2 = [];
        let extensionByteIndex = start;
        while (extensionByteIndex < voxOffset) {
          let extensionLittleEndian = littleEndian;
          let esize = _Utils.getIntAt(data, extensionByteIndex, littleEndian);
          if (!esize) {
            break;
          }
          if (esize + extensionByteIndex > voxOffset) {
            extensionLittleEndian = !extensionLittleEndian;
            esize = _Utils.getIntAt(data, extensionByteIndex, extensionLittleEndian);
            if (esize + extensionByteIndex > voxOffset) {
              throw new Error("This does not appear to be a valid NIFTI extension");
            }
          }
          if (esize % 16 != 0) {
            throw new Error("This does not appear to be a NIFTI extension");
          }
          let ecode = _Utils.getIntAt(data, extensionByteIndex + 4, extensionLittleEndian);
          let edata = data.buffer.slice(extensionByteIndex + 8, extensionByteIndex + esize);
          console.log("extensionByteIndex: " + (extensionByteIndex + 8) + " esize: " + esize);
          console.log(edata);
          let extension = new nifti_extension_1.NIFTIEXTENSION(esize, ecode, edata, extensionLittleEndian);
          extensions2.push(extension);
          extensionByteIndex += esize;
        }
        return extensions2;
      }
      static toArrayBuffer(buffer) {
        var ab, view, i;
        ab = new ArrayBuffer(buffer.length);
        view = new Uint8Array(ab);
        for (i = 0; i < buffer.length; i += 1) {
          view[i] = buffer[i];
        }
        return ab;
      }
      static isString(obj) {
        return typeof obj === "string" || obj instanceof String;
      }
      static formatNumber(num, shortFormat = void 0) {
        let val;
        if (_Utils.isString(num)) {
          val = Number(num);
        } else {
          val = num;
        }
        if (shortFormat) {
          val = val.toPrecision(5);
        } else {
          val = val.toPrecision(7);
        }
        return parseFloat(val);
      }
      // http://stackoverflow.com/questions/18638900/javascript-crc32
      static makeCRCTable() {
        let c;
        let crcTable = [];
        for (var n = 0; n < 256; n++) {
          c = n;
          for (var k = 0; k < 8; k++) {
            c = c & 1 ? 3988292384 ^ c >>> 1 : c >>> 1;
          }
          crcTable[n] = c;
        }
        return crcTable;
      }
      static crc32(dataView2) {
        if (!_Utils.crcTable) {
          _Utils.crcTable = _Utils.makeCRCTable();
        }
        const crcTable = _Utils.crcTable;
        let crc = 0 ^ -1;
        for (var i = 0; i < dataView2.byteLength; i++) {
          crc = crc >>> 8 ^ crcTable[(crc ^ dataView2.getUint8(i)) & 255];
        }
        return (crc ^ -1) >>> 0;
      }
    };
    exports.Utils = Utils;
  }
});

// node_modules/nifti-reader-js/dist/src/nifti1.js
var require_nifti1 = __commonJS({
  "node_modules/nifti-reader-js/dist/src/nifti1.js"(exports) {
    "use strict";
    init_legacy_browser();
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.NIFTI1 = void 0;
    var utilities_1 = require_utilities();
    var NIFTI12 = class _NIFTI1 {
      littleEndian = false;
      dim_info = 0;
      dims = [];
      intent_p1 = 0;
      intent_p2 = 0;
      intent_p3 = 0;
      intent_code = 0;
      datatypeCode = 0;
      numBitsPerVoxel = 0;
      slice_start = 0;
      slice_end = 0;
      slice_code = 0;
      pixDims = [];
      vox_offset = 0;
      scl_slope = 1;
      scl_inter = 0;
      xyzt_units = 0;
      cal_max = 0;
      cal_min = 0;
      slice_duration = 0;
      toffset = 0;
      description = "";
      aux_file = "";
      intent_name = "";
      qform_code = 0;
      sform_code = 0;
      quatern_a = 0;
      quatern_b = 0;
      quatern_c = 0;
      quatern_d = 0;
      qoffset_x = 0;
      qoffset_y = 0;
      qoffset_z = 0;
      affine = [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
      ];
      qfac = 1;
      quatern_R;
      magic = "0";
      isHDR = false;
      extensionFlag = [0, 0, 0, 0];
      extensionSize = 0;
      extensionCode = 0;
      extensions = [];
      /*** Static Pseudo-constants ***/
      // datatype codes
      static TYPE_NONE = 0;
      static TYPE_BINARY = 1;
      static TYPE_UINT8 = 2;
      static TYPE_INT16 = 4;
      static TYPE_INT32 = 8;
      static TYPE_FLOAT32 = 16;
      static TYPE_COMPLEX64 = 32;
      static TYPE_FLOAT64 = 64;
      static TYPE_RGB24 = 128;
      static TYPE_INT8 = 256;
      static TYPE_UINT16 = 512;
      static TYPE_UINT32 = 768;
      static TYPE_INT64 = 1024;
      static TYPE_UINT64 = 1280;
      static TYPE_FLOAT128 = 1536;
      static TYPE_COMPLEX128 = 1792;
      static TYPE_COMPLEX256 = 2048;
      // transform codes
      static XFORM_UNKNOWN = 0;
      static XFORM_SCANNER_ANAT = 1;
      static XFORM_ALIGNED_ANAT = 2;
      static XFORM_TALAIRACH = 3;
      static XFORM_MNI_152 = 4;
      // unit codes
      static SPATIAL_UNITS_MASK = 7;
      static TEMPORAL_UNITS_MASK = 56;
      static UNITS_UNKNOWN = 0;
      static UNITS_METER = 1;
      static UNITS_MM = 2;
      static UNITS_MICRON = 3;
      static UNITS_SEC = 8;
      static UNITS_MSEC = 16;
      static UNITS_USEC = 24;
      static UNITS_HZ = 32;
      static UNITS_PPM = 40;
      static UNITS_RADS = 48;
      // nifti1 codes
      static MAGIC_COOKIE = 348;
      static STANDARD_HEADER_SIZE = 348;
      static MAGIC_NUMBER_LOCATION = 344;
      static MAGIC_NUMBER = [110, 43, 49];
      // n+1 (.nii)
      static MAGIC_NUMBER2 = [110, 105, 49];
      // ni1 (.hdr/.img)
      static EXTENSION_HEADER_SIZE = 8;
      /*** Prototype Methods ***/
      /**
       * Reads the header data.
       * @param {ArrayBuffer} data
       */
      readHeader(data) {
        var rawData = new DataView(data), magicCookieVal = utilities_1.Utils.getIntAt(rawData, 0, this.littleEndian), ctr, ctrOut, ctrIn, index;
        if (magicCookieVal !== _NIFTI1.MAGIC_COOKIE) {
          this.littleEndian = true;
          magicCookieVal = utilities_1.Utils.getIntAt(rawData, 0, this.littleEndian);
        }
        if (magicCookieVal !== _NIFTI1.MAGIC_COOKIE) {
          throw new Error("This does not appear to be a NIFTI file!");
        }
        this.dim_info = utilities_1.Utils.getByteAt(rawData, 39);
        for (ctr = 0; ctr < 8; ctr += 1) {
          index = 40 + ctr * 2;
          this.dims[ctr] = utilities_1.Utils.getShortAt(rawData, index, this.littleEndian);
        }
        this.intent_p1 = utilities_1.Utils.getFloatAt(rawData, 56, this.littleEndian);
        this.intent_p2 = utilities_1.Utils.getFloatAt(rawData, 60, this.littleEndian);
        this.intent_p3 = utilities_1.Utils.getFloatAt(rawData, 64, this.littleEndian);
        this.intent_code = utilities_1.Utils.getShortAt(rawData, 68, this.littleEndian);
        this.datatypeCode = utilities_1.Utils.getShortAt(rawData, 70, this.littleEndian);
        this.numBitsPerVoxel = utilities_1.Utils.getShortAt(rawData, 72, this.littleEndian);
        this.slice_start = utilities_1.Utils.getShortAt(rawData, 74, this.littleEndian);
        for (ctr = 0; ctr < 8; ctr += 1) {
          index = 76 + ctr * 4;
          this.pixDims[ctr] = utilities_1.Utils.getFloatAt(rawData, index, this.littleEndian);
        }
        this.vox_offset = utilities_1.Utils.getFloatAt(rawData, 108, this.littleEndian);
        this.scl_slope = utilities_1.Utils.getFloatAt(rawData, 112, this.littleEndian);
        this.scl_inter = utilities_1.Utils.getFloatAt(rawData, 116, this.littleEndian);
        this.slice_end = utilities_1.Utils.getShortAt(rawData, 120, this.littleEndian);
        this.slice_code = utilities_1.Utils.getByteAt(rawData, 122);
        this.xyzt_units = utilities_1.Utils.getByteAt(rawData, 123);
        this.cal_max = utilities_1.Utils.getFloatAt(rawData, 124, this.littleEndian);
        this.cal_min = utilities_1.Utils.getFloatAt(rawData, 128, this.littleEndian);
        this.slice_duration = utilities_1.Utils.getFloatAt(rawData, 132, this.littleEndian);
        this.toffset = utilities_1.Utils.getFloatAt(rawData, 136, this.littleEndian);
        this.description = utilities_1.Utils.getStringAt(rawData, 148, 228);
        this.aux_file = utilities_1.Utils.getStringAt(rawData, 228, 252);
        this.qform_code = utilities_1.Utils.getShortAt(rawData, 252, this.littleEndian);
        this.sform_code = utilities_1.Utils.getShortAt(rawData, 254, this.littleEndian);
        this.quatern_b = utilities_1.Utils.getFloatAt(rawData, 256, this.littleEndian);
        this.quatern_c = utilities_1.Utils.getFloatAt(rawData, 260, this.littleEndian);
        this.quatern_d = utilities_1.Utils.getFloatAt(rawData, 264, this.littleEndian);
        this.quatern_a = Math.sqrt(1 - (Math.pow(this.quatern_b, 2) + Math.pow(this.quatern_c, 2) + Math.pow(this.quatern_d, 2)));
        this.qoffset_x = utilities_1.Utils.getFloatAt(rawData, 268, this.littleEndian);
        this.qoffset_y = utilities_1.Utils.getFloatAt(rawData, 272, this.littleEndian);
        this.qoffset_z = utilities_1.Utils.getFloatAt(rawData, 276, this.littleEndian);
        if (this.qform_code < 1 && this.sform_code < 1) {
          this.affine[0][0] = this.pixDims[1];
          this.affine[1][1] = this.pixDims[2];
          this.affine[2][2] = this.pixDims[3];
        }
        if (this.qform_code > 0 && this.sform_code < this.qform_code) {
          const a = this.quatern_a;
          const b = this.quatern_b;
          const c = this.quatern_c;
          const d = this.quatern_d;
          this.qfac = this.pixDims[0] === 0 ? 1 : this.pixDims[0];
          this.quatern_R = [
            [
              a * a + b * b - c * c - d * d,
              2 * b * c - 2 * a * d,
              2 * b * d + 2 * a * c
            ],
            [
              2 * b * c + 2 * a * d,
              a * a + c * c - b * b - d * d,
              2 * c * d - 2 * a * b
            ],
            [
              2 * b * d - 2 * a * c,
              2 * c * d + 2 * a * b,
              a * a + d * d - c * c - b * b
            ]
          ];
          for (ctrOut = 0; ctrOut < 3; ctrOut += 1) {
            for (ctrIn = 0; ctrIn < 3; ctrIn += 1) {
              this.affine[ctrOut][ctrIn] = this.quatern_R[ctrOut][ctrIn] * this.pixDims[ctrIn + 1];
              if (ctrIn === 2) {
                this.affine[ctrOut][ctrIn] *= this.qfac;
              }
            }
          }
          this.affine[0][3] = this.qoffset_x;
          this.affine[1][3] = this.qoffset_y;
          this.affine[2][3] = this.qoffset_z;
        } else if (this.sform_code > 0) {
          for (ctrOut = 0; ctrOut < 3; ctrOut += 1) {
            for (ctrIn = 0; ctrIn < 4; ctrIn += 1) {
              index = 280 + (ctrOut * 4 + ctrIn) * 4;
              this.affine[ctrOut][ctrIn] = utilities_1.Utils.getFloatAt(rawData, index, this.littleEndian);
            }
          }
        }
        this.affine[3][0] = 0;
        this.affine[3][1] = 0;
        this.affine[3][2] = 0;
        this.affine[3][3] = 1;
        this.intent_name = utilities_1.Utils.getStringAt(rawData, 328, 344);
        this.magic = utilities_1.Utils.getStringAt(rawData, 344, 348);
        this.isHDR = this.magic === String.fromCharCode.apply(null, _NIFTI1.MAGIC_NUMBER2);
        if (rawData.byteLength > _NIFTI1.MAGIC_COOKIE) {
          this.extensionFlag[0] = utilities_1.Utils.getByteAt(rawData, 348);
          this.extensionFlag[1] = utilities_1.Utils.getByteAt(rawData, 348 + 1);
          this.extensionFlag[2] = utilities_1.Utils.getByteAt(rawData, 348 + 2);
          this.extensionFlag[3] = utilities_1.Utils.getByteAt(rawData, 348 + 3);
          let isExtensionCapable = true;
          if (!this.isHDR && this.vox_offset <= 352)
            isExtensionCapable = false;
          if (rawData.byteLength <= 352 + 16)
            isExtensionCapable = false;
          if (isExtensionCapable && this.extensionFlag[0]) {
            this.extensions = utilities_1.Utils.getExtensionsAt(rawData, this.getExtensionLocation(), this.littleEndian, this.vox_offset);
            this.extensionSize = this.extensions[0].esize;
            this.extensionCode = this.extensions[0].ecode;
          }
        }
      }
      /**
       * Returns a formatted string of header fields.
       * @returns {string}
       */
      toFormattedString() {
        var fmt = utilities_1.Utils.formatNumber, string2 = "";
        string2 += "Dim Info = " + this.dim_info + "\n";
        string2 += "Image Dimensions (1-8): " + this.dims[0] + ", " + this.dims[1] + ", " + this.dims[2] + ", " + this.dims[3] + ", " + this.dims[4] + ", " + this.dims[5] + ", " + this.dims[6] + ", " + this.dims[7] + "\n";
        string2 += "Intent Parameters (1-3): " + this.intent_p1 + ", " + this.intent_p2 + ", " + this.intent_p3 + "\n";
        string2 += "Intent Code = " + this.intent_code + "\n";
        string2 += "Datatype = " + this.datatypeCode + " (" + this.getDatatypeCodeString(this.datatypeCode) + ")\n";
        string2 += "Bits Per Voxel = " + this.numBitsPerVoxel + "\n";
        string2 += "Slice Start = " + this.slice_start + "\n";
        string2 += "Voxel Dimensions (1-8): " + fmt(this.pixDims[0]) + ", " + fmt(this.pixDims[1]) + ", " + fmt(this.pixDims[2]) + ", " + fmt(this.pixDims[3]) + ", " + fmt(this.pixDims[4]) + ", " + fmt(this.pixDims[5]) + ", " + fmt(this.pixDims[6]) + ", " + fmt(this.pixDims[7]) + "\n";
        string2 += "Image Offset = " + this.vox_offset + "\n";
        string2 += "Data Scale:  Slope = " + fmt(this.scl_slope) + "  Intercept = " + fmt(this.scl_inter) + "\n";
        string2 += "Slice End = " + this.slice_end + "\n";
        string2 += "Slice Code = " + this.slice_code + "\n";
        string2 += "Units Code = " + this.xyzt_units + " (" + this.getUnitsCodeString(_NIFTI1.SPATIAL_UNITS_MASK & this.xyzt_units) + ", " + this.getUnitsCodeString(_NIFTI1.TEMPORAL_UNITS_MASK & this.xyzt_units) + ")\n";
        string2 += "Display Range:  Max = " + fmt(this.cal_max) + "  Min = " + fmt(this.cal_min) + "\n";
        string2 += "Slice Duration = " + this.slice_duration + "\n";
        string2 += "Time Axis Shift = " + this.toffset + "\n";
        string2 += 'Description: "' + this.description + '"\n';
        string2 += 'Auxiliary File: "' + this.aux_file + '"\n';
        string2 += "Q-Form Code = " + this.qform_code + " (" + this.getTransformCodeString(this.qform_code) + ")\n";
        string2 += "S-Form Code = " + this.sform_code + " (" + this.getTransformCodeString(this.sform_code) + ")\n";
        string2 += "Quaternion Parameters:  b = " + fmt(this.quatern_b) + "  c = " + fmt(this.quatern_c) + "  d = " + fmt(this.quatern_d) + "\n";
        string2 += "Quaternion Offsets:  x = " + this.qoffset_x + "  y = " + this.qoffset_y + "  z = " + this.qoffset_z + "\n";
        string2 += "S-Form Parameters X: " + fmt(this.affine[0][0]) + ", " + fmt(this.affine[0][1]) + ", " + fmt(this.affine[0][2]) + ", " + fmt(this.affine[0][3]) + "\n";
        string2 += "S-Form Parameters Y: " + fmt(this.affine[1][0]) + ", " + fmt(this.affine[1][1]) + ", " + fmt(this.affine[1][2]) + ", " + fmt(this.affine[1][3]) + "\n";
        string2 += "S-Form Parameters Z: " + fmt(this.affine[2][0]) + ", " + fmt(this.affine[2][1]) + ", " + fmt(this.affine[2][2]) + ", " + fmt(this.affine[2][3]) + "\n";
        string2 += 'Intent Name: "' + this.intent_name + '"\n';
        if (this.extensionFlag[0]) {
          string2 += "Extension: Size = " + this.extensionSize + "  Code = " + this.extensionCode + "\n";
        }
        return string2;
      }
      /**
       * Returns a human-readable string of datatype.
       * @param {number} code
       * @returns {string}
       */
      getDatatypeCodeString = function(code) {
        if (code === _NIFTI1.TYPE_UINT8) {
          return "1-Byte Unsigned Integer";
        } else if (code === _NIFTI1.TYPE_INT16) {
          return "2-Byte Signed Integer";
        } else if (code === _NIFTI1.TYPE_INT32) {
          return "4-Byte Signed Integer";
        } else if (code === _NIFTI1.TYPE_FLOAT32) {
          return "4-Byte Float";
        } else if (code === _NIFTI1.TYPE_FLOAT64) {
          return "8-Byte Float";
        } else if (code === _NIFTI1.TYPE_RGB24) {
          return "RGB";
        } else if (code === _NIFTI1.TYPE_INT8) {
          return "1-Byte Signed Integer";
        } else if (code === _NIFTI1.TYPE_UINT16) {
          return "2-Byte Unsigned Integer";
        } else if (code === _NIFTI1.TYPE_UINT32) {
          return "4-Byte Unsigned Integer";
        } else if (code === _NIFTI1.TYPE_INT64) {
          return "8-Byte Signed Integer";
        } else if (code === _NIFTI1.TYPE_UINT64) {
          return "8-Byte Unsigned Integer";
        } else {
          return "Unknown";
        }
      };
      /**
       * Returns a human-readable string of transform type.
       * @param {number} code
       * @returns {string}
       */
      getTransformCodeString = function(code) {
        if (code === _NIFTI1.XFORM_SCANNER_ANAT) {
          return "Scanner";
        } else if (code === _NIFTI1.XFORM_ALIGNED_ANAT) {
          return "Aligned";
        } else if (code === _NIFTI1.XFORM_TALAIRACH) {
          return "Talairach";
        } else if (code === _NIFTI1.XFORM_MNI_152) {
          return "MNI";
        } else {
          return "Unknown";
        }
      };
      /**
       * Returns a human-readable string of spatial and temporal units.
       * @param {number} code
       * @returns {string}
       */
      getUnitsCodeString = function(code) {
        if (code === _NIFTI1.UNITS_METER) {
          return "Meters";
        } else if (code === _NIFTI1.UNITS_MM) {
          return "Millimeters";
        } else if (code === _NIFTI1.UNITS_MICRON) {
          return "Microns";
        } else if (code === _NIFTI1.UNITS_SEC) {
          return "Seconds";
        } else if (code === _NIFTI1.UNITS_MSEC) {
          return "Milliseconds";
        } else if (code === _NIFTI1.UNITS_USEC) {
          return "Microseconds";
        } else if (code === _NIFTI1.UNITS_HZ) {
          return "Hz";
        } else if (code === _NIFTI1.UNITS_PPM) {
          return "PPM";
        } else if (code === _NIFTI1.UNITS_RADS) {
          return "Rads";
        } else {
          return "Unknown";
        }
      };
      /**
       * Returns the qform matrix.
       * @returns {Array.<Array.<number>>}
       */
      getQformMat() {
        return this.convertNiftiQFormToNiftiSForm(this.quatern_b, this.quatern_c, this.quatern_d, this.qoffset_x, this.qoffset_y, this.qoffset_z, this.pixDims[1], this.pixDims[2], this.pixDims[3], this.pixDims[0]);
      }
      /**
       * Converts qform to an affine.  (See http://nifti.nimh.nih.gov/pub/dist/src/niftilib/nifti1_io.c)
       * @param {number} qb
       * @param {number} qc
       * @param {number} qd
       * @param {number} qx
       * @param {number} qy
       * @param {number} qz
       * @param {number} dx
       * @param {number} dy
       * @param {number} dz
       * @param {number} qfac
       * @returns {Array.<Array.<number>>}
       */
      convertNiftiQFormToNiftiSForm(qb, qc, qd, qx, qy, qz, dx, dy, dz, qfac) {
        var R = [
          [0, 0, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0],
          [0, 0, 0, 0]
        ], a, b = qb, c = qc, d = qd, xd, yd, zd;
        R[3][0] = R[3][1] = R[3][2] = 0;
        R[3][3] = 1;
        a = 1 - (b * b + c * c + d * d);
        if (a < 1e-7) {
          a = 1 / Math.sqrt(b * b + c * c + d * d);
          b *= a;
          c *= a;
          d *= a;
          a = 0;
        } else {
          a = Math.sqrt(a);
        }
        xd = dx > 0 ? dx : 1;
        yd = dy > 0 ? dy : 1;
        zd = dz > 0 ? dz : 1;
        if (qfac < 0) {
          zd = -zd;
        }
        R[0][0] = (a * a + b * b - c * c - d * d) * xd;
        R[0][1] = 2 * (b * c - a * d) * yd;
        R[0][2] = 2 * (b * d + a * c) * zd;
        R[1][0] = 2 * (b * c + a * d) * xd;
        R[1][1] = (a * a + c * c - b * b - d * d) * yd;
        R[1][2] = 2 * (c * d - a * b) * zd;
        R[2][0] = 2 * (b * d - a * c) * xd;
        R[2][1] = 2 * (c * d + a * b) * yd;
        R[2][2] = (a * a + d * d - c * c - b * b) * zd;
        R[0][3] = qx;
        R[1][3] = qy;
        R[2][3] = qz;
        return R;
      }
      /**
       * Converts sform to an orientation string (e.g., XYZ+--).  (See http://nifti.nimh.nih.gov/pub/dist/src/niftilib/nifti1_io.c)
       * @param {Array.<Array.<number>>} R
       * @returns {string}
       */
      convertNiftiSFormToNEMA(R) {
        var xi, xj, xk, yi, yj, yk, zi, zj, zk, val, detQ, detP, i, j, k, p, q, r, ibest, jbest, kbest, pbest, qbest, rbest, M, vbest, Q, P, iChar, jChar, kChar, iSense, jSense, kSense;
        k = 0;
        Q = [
          [0, 0, 0],
          [0, 0, 0],
          [0, 0, 0]
        ];
        P = [
          [0, 0, 0],
          [0, 0, 0],
          [0, 0, 0]
        ];
        xi = R[0][0];
        xj = R[0][1];
        xk = R[0][2];
        yi = R[1][0];
        yj = R[1][1];
        yk = R[1][2];
        zi = R[2][0];
        zj = R[2][1];
        zk = R[2][2];
        val = Math.sqrt(xi * xi + yi * yi + zi * zi);
        if (val === 0) {
          return null;
        }
        xi /= val;
        yi /= val;
        zi /= val;
        val = Math.sqrt(xj * xj + yj * yj + zj * zj);
        if (val === 0) {
          return null;
        }
        xj /= val;
        yj /= val;
        zj /= val;
        val = xi * xj + yi * yj + zi * zj;
        if (Math.abs(val) > 1e-4) {
          xj -= val * xi;
          yj -= val * yi;
          zj -= val * zi;
          val = Math.sqrt(xj * xj + yj * yj + zj * zj);
          if (val === 0) {
            return null;
          }
          xj /= val;
          yj /= val;
          zj /= val;
        }
        val = Math.sqrt(xk * xk + yk * yk + zk * zk);
        if (val === 0) {
          xk = yi * zj - zi * yj;
          yk = zi * xj - zj * xi;
          zk = xi * yj - yi * xj;
        } else {
          xk /= val;
          yk /= val;
          zk /= val;
        }
        val = xi * xk + yi * yk + zi * zk;
        if (Math.abs(val) > 1e-4) {
          xk -= val * xi;
          yk -= val * yi;
          zk -= val * zi;
          val = Math.sqrt(xk * xk + yk * yk + zk * zk);
          if (val === 0) {
            return null;
          }
          xk /= val;
          yk /= val;
          zk /= val;
        }
        val = xj * xk + yj * yk + zj * zk;
        if (Math.abs(val) > 1e-4) {
          xk -= val * xj;
          yk -= val * yj;
          zk -= val * zj;
          val = Math.sqrt(xk * xk + yk * yk + zk * zk);
          if (val === 0) {
            return null;
          }
          xk /= val;
          yk /= val;
          zk /= val;
        }
        Q[0][0] = xi;
        Q[0][1] = xj;
        Q[0][2] = xk;
        Q[1][0] = yi;
        Q[1][1] = yj;
        Q[1][2] = yk;
        Q[2][0] = zi;
        Q[2][1] = zj;
        Q[2][2] = zk;
        detQ = this.nifti_mat33_determ(Q);
        if (detQ === 0) {
          return null;
        }
        vbest = -666;
        ibest = pbest = qbest = rbest = 1;
        jbest = 2;
        kbest = 3;
        for (i = 1; i <= 3; i += 1) {
          for (j = 1; j <= 3; j += 1) {
            if (i !== j) {
              for (k = 1; k <= 3; k += 1) {
                if (!(i === k || j === k)) {
                  P[0][0] = P[0][1] = P[0][2] = P[1][0] = P[1][1] = P[1][2] = P[2][0] = P[2][1] = P[2][2] = 0;
                  for (p = -1; p <= 1; p += 2) {
                    for (q = -1; q <= 1; q += 2) {
                      for (r = -1; r <= 1; r += 2) {
                        P[0][i - 1] = p;
                        P[1][j - 1] = q;
                        P[2][k - 1] = r;
                        detP = this.nifti_mat33_determ(P);
                        if (detP * detQ > 0) {
                          M = this.nifti_mat33_mul(P, Q);
                          val = M[0][0] + M[1][1] + M[2][2];
                          if (val > vbest) {
                            vbest = val;
                            ibest = i;
                            jbest = j;
                            kbest = k;
                            pbest = p;
                            qbest = q;
                            rbest = r;
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        iChar = jChar = kChar = iSense = jSense = kSense = "";
        switch (ibest * pbest) {
          case 1:
            iChar = "X";
            iSense = "+";
            break;
          case -1:
            iChar = "X";
            iSense = "-";
            break;
          case 2:
            iChar = "Y";
            iSense = "+";
            break;
          case -2:
            iChar = "Y";
            iSense = "-";
            break;
          case 3:
            iChar = "Z";
            iSense = "+";
            break;
          case -3:
            iChar = "Z";
            iSense = "-";
            break;
        }
        switch (jbest * qbest) {
          case 1:
            jChar = "X";
            jSense = "+";
            break;
          case -1:
            jChar = "X";
            jSense = "-";
            break;
          case 2:
            jChar = "Y";
            jSense = "+";
            break;
          case -2:
            jChar = "Y";
            jSense = "-";
            break;
          case 3:
            jChar = "Z";
            jSense = "+";
            break;
          case -3:
            jChar = "Z";
            jSense = "-";
            break;
        }
        switch (kbest * rbest) {
          case 1:
            kChar = "X";
            kSense = "+";
            break;
          case -1:
            kChar = "X";
            kSense = "-";
            break;
          case 2:
            kChar = "Y";
            kSense = "+";
            break;
          case -2:
            kChar = "Y";
            kSense = "-";
            break;
          case 3:
            kChar = "Z";
            kSense = "+";
            break;
          case -3:
            kChar = "Z";
            kSense = "-";
            break;
        }
        return iChar + jChar + kChar + iSense + jSense + kSense;
      }
      nifti_mat33_mul = function(A, B) {
        var C = [
          [0, 0, 0],
          [0, 0, 0],
          [0, 0, 0]
        ], i, j;
        for (i = 0; i < 3; i += 1) {
          for (j = 0; j < 3; j += 1) {
            C[i][j] = A[i][0] * B[0][j] + A[i][1] * B[1][j] + A[i][2] * B[2][j];
          }
        }
        return C;
      };
      nifti_mat33_determ = function(R) {
        var r11, r12, r13, r21, r22, r23, r31, r32, r33;
        r11 = R[0][0];
        r12 = R[0][1];
        r13 = R[0][2];
        r21 = R[1][0];
        r22 = R[1][1];
        r23 = R[1][2];
        r31 = R[2][0];
        r32 = R[2][1];
        r33 = R[2][2];
        return r11 * r22 * r33 - r11 * r32 * r23 - r21 * r12 * r33 + r21 * r32 * r13 + r31 * r12 * r23 - r31 * r22 * r13;
      };
      /**
       * Returns the byte index of the extension.
       * @returns {number}
       */
      getExtensionLocation() {
        return _NIFTI1.MAGIC_COOKIE + 4;
      }
      /**
       * Returns the extension size.
       * @param {DataView} data
       * @returns {number}
       */
      getExtensionSize(data) {
        return utilities_1.Utils.getIntAt(data, this.getExtensionLocation(), this.littleEndian);
      }
      /**
       * Returns the extension code.
       * @param {DataView} data
       * @returns {number}
       */
      getExtensionCode(data) {
        return utilities_1.Utils.getIntAt(data, this.getExtensionLocation() + 4, this.littleEndian);
      }
      /**
       * Adds an extension
       * @param {NIFTIEXTENSION} extension
       * @param {number} index
       */
      addExtension(extension, index = -1) {
        if (index == -1) {
          this.extensions.push(extension);
        } else {
          this.extensions.splice(index, 0, extension);
        }
        this.vox_offset += extension.esize;
      }
      /**
       * Removes an extension
       * @param {number} index
       */
      removeExtension(index) {
        let extension = this.extensions[index];
        if (extension) {
          this.vox_offset -= extension.esize;
        }
        this.extensions.splice(index, 1);
      }
      /**
       * Returns header as ArrayBuffer.
       * @param {boolean} includeExtensions - should extension bytes be included
       * @returns {ArrayBuffer}
       */
      toArrayBuffer(includeExtensions = false) {
        const SHORT_SIZE = 2;
        const FLOAT32_SIZE = 4;
        let byteSize = 348 + 4;
        if (includeExtensions) {
          for (let extension of this.extensions) {
            byteSize += extension.esize;
          }
        }
        let byteArray = new Uint8Array(byteSize);
        let view = new DataView(byteArray.buffer);
        view.setInt32(0, 348, this.littleEndian);
        view.setUint8(39, this.dim_info);
        for (let i = 0; i < 8; i++) {
          view.setUint16(40 + SHORT_SIZE * i, this.dims[i], this.littleEndian);
        }
        view.setFloat32(56, this.intent_p1, this.littleEndian);
        view.setFloat32(60, this.intent_p2, this.littleEndian);
        view.setFloat32(64, this.intent_p3, this.littleEndian);
        view.setInt16(68, this.intent_code, this.littleEndian);
        view.setInt16(70, this.datatypeCode, this.littleEndian);
        view.setInt16(72, this.numBitsPerVoxel, this.littleEndian);
        view.setInt16(74, this.slice_start, this.littleEndian);
        for (let i = 0; i < 8; i++) {
          view.setFloat32(76 + FLOAT32_SIZE * i, this.pixDims[i], this.littleEndian);
        }
        view.setFloat32(108, this.vox_offset, this.littleEndian);
        view.setFloat32(112, this.scl_slope, this.littleEndian);
        view.setFloat32(116, this.scl_inter, this.littleEndian);
        view.setInt16(120, this.slice_end, this.littleEndian);
        view.setUint8(122, this.slice_code);
        view.setUint8(123, this.xyzt_units);
        view.setFloat32(124, this.cal_max, this.littleEndian);
        view.setFloat32(128, this.cal_min, this.littleEndian);
        view.setFloat32(132, this.slice_duration, this.littleEndian);
        view.setFloat32(136, this.toffset, this.littleEndian);
        byteArray.set(Buffer.from(this.description), 148);
        byteArray.set(Buffer.from(this.aux_file), 228);
        view.setInt16(252, this.qform_code, this.littleEndian);
        view.setInt16(254, this.sform_code, this.littleEndian);
        view.setFloat32(256, this.quatern_b, this.littleEndian);
        view.setFloat32(260, this.quatern_c, this.littleEndian);
        view.setFloat32(264, this.quatern_d, this.littleEndian);
        view.setFloat32(268, this.qoffset_x, this.littleEndian);
        view.setFloat32(272, this.qoffset_y, this.littleEndian);
        view.setFloat32(276, this.qoffset_z, this.littleEndian);
        const flattened = this.affine.flat();
        for (let i = 0; i < 12; i++) {
          view.setFloat32(280 + FLOAT32_SIZE * i, flattened[i], this.littleEndian);
        }
        byteArray.set(Buffer.from(this.intent_name), 328);
        byteArray.set(Buffer.from(this.magic), 344);
        if (includeExtensions) {
          byteArray.set(Uint8Array.from([1, 0, 0, 0]), 348);
          let extensionByteIndex = this.getExtensionLocation();
          for (const extension of this.extensions) {
            view.setInt32(extensionByteIndex, extension.esize, extension.littleEndian);
            view.setInt32(extensionByteIndex + 4, extension.ecode, extension.littleEndian);
            byteArray.set(new Uint8Array(extension.edata), extensionByteIndex + 8);
            extensionByteIndex += extension.esize;
          }
        } else {
          byteArray.set(new Uint8Array(4).fill(0), 348);
        }
        return byteArray.buffer;
      }
    };
    exports.NIFTI1 = NIFTI12;
  }
});

// node_modules/nifti-reader-js/dist/src/nifti2.js
var require_nifti2 = __commonJS({
  "node_modules/nifti-reader-js/dist/src/nifti2.js"(exports) {
    "use strict";
    init_legacy_browser();
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.NIFTI2 = void 0;
    var nifti1_1 = require_nifti1();
    var utilities_1 = require_utilities();
    var NIFTI2 = class _NIFTI2 {
      littleEndian = false;
      dim_info = 0;
      dims = [];
      intent_p1 = 0;
      intent_p2 = 0;
      intent_p3 = 0;
      intent_code = 0;
      datatypeCode = 0;
      numBitsPerVoxel = 0;
      slice_start = 0;
      slice_end = 0;
      slice_code = 0;
      pixDims = [];
      vox_offset = 0;
      scl_slope = 1;
      scl_inter = 0;
      xyzt_units = 0;
      cal_max = 0;
      cal_min = 0;
      slice_duration = 0;
      toffset = 0;
      description = "";
      aux_file = "";
      intent_name = "";
      qform_code = 0;
      sform_code = 0;
      quatern_b = 0;
      quatern_c = 0;
      quatern_d = 0;
      qoffset_x = 0;
      qoffset_y = 0;
      qoffset_z = 0;
      affine = [
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
      ];
      magic = "0";
      extensionFlag = [0, 0, 0, 0];
      extensions = [];
      extensionSize = 0;
      extensionCode = 0;
      /*** Static Pseudo-constants ***/
      static MAGIC_COOKIE = 540;
      static MAGIC_NUMBER_LOCATION = 4;
      static MAGIC_NUMBER = [
        110,
        43,
        50,
        0,
        13,
        10,
        26,
        10
      ];
      // n+2\0
      static MAGIC_NUMBER2 = [
        110,
        105,
        50,
        0,
        13,
        10,
        26,
        10
      ];
      // ni2\0
      /*** Prototype Methods ***/
      /**
       * Reads the header data.
       * @param {ArrayBuffer} data
       */
      readHeader(data) {
        var rawData = new DataView(data), magicCookieVal = utilities_1.Utils.getIntAt(rawData, 0, this.littleEndian), ctr, ctrOut, ctrIn, index, array2;
        if (magicCookieVal !== _NIFTI2.MAGIC_COOKIE) {
          this.littleEndian = true;
          magicCookieVal = utilities_1.Utils.getIntAt(rawData, 0, this.littleEndian);
        }
        if (magicCookieVal !== _NIFTI2.MAGIC_COOKIE) {
          throw new Error("This does not appear to be a NIFTI file!");
        }
        this.magic = utilities_1.Utils.getStringAt(rawData, 4, 12);
        this.datatypeCode = utilities_1.Utils.getShortAt(rawData, 12, this.littleEndian);
        this.numBitsPerVoxel = utilities_1.Utils.getShortAt(rawData, 14, this.littleEndian);
        for (ctr = 0; ctr < 8; ctr += 1) {
          index = 16 + ctr * 8;
          this.dims[ctr] = utilities_1.Utils.getInt64At(rawData, index, this.littleEndian);
        }
        this.intent_p1 = utilities_1.Utils.getDoubleAt(rawData, 80, this.littleEndian);
        this.intent_p2 = utilities_1.Utils.getDoubleAt(rawData, 88, this.littleEndian);
        this.intent_p3 = utilities_1.Utils.getDoubleAt(rawData, 96, this.littleEndian);
        for (ctr = 0; ctr < 8; ctr += 1) {
          index = 104 + ctr * 8;
          this.pixDims[ctr] = utilities_1.Utils.getDoubleAt(rawData, index, this.littleEndian);
        }
        this.vox_offset = utilities_1.Utils.getInt64At(rawData, 168, this.littleEndian);
        this.scl_slope = utilities_1.Utils.getDoubleAt(rawData, 176, this.littleEndian);
        this.scl_inter = utilities_1.Utils.getDoubleAt(rawData, 184, this.littleEndian);
        this.cal_max = utilities_1.Utils.getDoubleAt(rawData, 192, this.littleEndian);
        this.cal_min = utilities_1.Utils.getDoubleAt(rawData, 200, this.littleEndian);
        this.slice_duration = utilities_1.Utils.getDoubleAt(rawData, 208, this.littleEndian);
        this.toffset = utilities_1.Utils.getDoubleAt(rawData, 216, this.littleEndian);
        this.slice_start = utilities_1.Utils.getInt64At(rawData, 224, this.littleEndian);
        this.slice_end = utilities_1.Utils.getInt64At(rawData, 232, this.littleEndian);
        this.description = utilities_1.Utils.getStringAt(rawData, 240, 240 + 80);
        this.aux_file = utilities_1.Utils.getStringAt(rawData, 320, 320 + 24);
        this.qform_code = utilities_1.Utils.getIntAt(rawData, 344, this.littleEndian);
        this.sform_code = utilities_1.Utils.getIntAt(rawData, 348, this.littleEndian);
        this.quatern_b = utilities_1.Utils.getDoubleAt(rawData, 352, this.littleEndian);
        this.quatern_c = utilities_1.Utils.getDoubleAt(rawData, 360, this.littleEndian);
        this.quatern_d = utilities_1.Utils.getDoubleAt(rawData, 368, this.littleEndian);
        this.qoffset_x = utilities_1.Utils.getDoubleAt(rawData, 376, this.littleEndian);
        this.qoffset_y = utilities_1.Utils.getDoubleAt(rawData, 384, this.littleEndian);
        this.qoffset_z = utilities_1.Utils.getDoubleAt(rawData, 392, this.littleEndian);
        for (ctrOut = 0; ctrOut < 3; ctrOut += 1) {
          for (ctrIn = 0; ctrIn < 4; ctrIn += 1) {
            index = 400 + (ctrOut * 4 + ctrIn) * 8;
            this.affine[ctrOut][ctrIn] = utilities_1.Utils.getDoubleAt(rawData, index, this.littleEndian);
          }
        }
        this.affine[3][0] = 0;
        this.affine[3][1] = 0;
        this.affine[3][2] = 0;
        this.affine[3][3] = 1;
        this.slice_code = utilities_1.Utils.getIntAt(rawData, 496, this.littleEndian);
        this.xyzt_units = utilities_1.Utils.getIntAt(rawData, 500, this.littleEndian);
        this.intent_code = utilities_1.Utils.getIntAt(rawData, 504, this.littleEndian);
        this.intent_name = utilities_1.Utils.getStringAt(rawData, 508, 508 + 16);
        this.dim_info = utilities_1.Utils.getByteAt(rawData, 524);
        if (rawData.byteLength > _NIFTI2.MAGIC_COOKIE) {
          this.extensionFlag[0] = utilities_1.Utils.getByteAt(rawData, 540);
          this.extensionFlag[1] = utilities_1.Utils.getByteAt(rawData, 540 + 1);
          this.extensionFlag[2] = utilities_1.Utils.getByteAt(rawData, 540 + 2);
          this.extensionFlag[3] = utilities_1.Utils.getByteAt(rawData, 540 + 3);
          if (this.extensionFlag[0]) {
            this.extensions = utilities_1.Utils.getExtensionsAt(rawData, this.getExtensionLocation(), this.littleEndian, this.vox_offset);
            this.extensionSize = this.extensions[0].esize;
            this.extensionCode = this.extensions[0].ecode;
          }
        }
      }
      /**
       * Returns a formatted string of header fields.
       * @returns {string}
       */
      toFormattedString() {
        var fmt = utilities_1.Utils.formatNumber, string2 = "";
        string2 += "Datatype = " + +this.datatypeCode + " (" + this.getDatatypeCodeString(this.datatypeCode) + ")\n";
        string2 += "Bits Per Voxel =  = " + this.numBitsPerVoxel + "\n";
        string2 += "Image Dimensions (1-8): " + this.dims[0] + ", " + this.dims[1] + ", " + this.dims[2] + ", " + this.dims[3] + ", " + this.dims[4] + ", " + this.dims[5] + ", " + this.dims[6] + ", " + this.dims[7] + "\n";
        string2 += "Intent Parameters (1-3): " + this.intent_p1 + ", " + this.intent_p2 + ", " + this.intent_p3 + "\n";
        string2 += "Voxel Dimensions (1-8): " + fmt(this.pixDims[0]) + ", " + fmt(this.pixDims[1]) + ", " + fmt(this.pixDims[2]) + ", " + fmt(this.pixDims[3]) + ", " + fmt(this.pixDims[4]) + ", " + fmt(this.pixDims[5]) + ", " + fmt(this.pixDims[6]) + ", " + fmt(this.pixDims[7]) + "\n";
        string2 += "Image Offset = " + this.vox_offset + "\n";
        string2 += "Data Scale:  Slope = " + fmt(this.scl_slope) + "  Intercept = " + fmt(this.scl_inter) + "\n";
        string2 += "Display Range:  Max = " + fmt(this.cal_max) + "  Min = " + fmt(this.cal_min) + "\n";
        string2 += "Slice Duration = " + this.slice_duration + "\n";
        string2 += "Time Axis Shift = " + this.toffset + "\n";
        string2 += "Slice Start = " + this.slice_start + "\n";
        string2 += "Slice End = " + this.slice_end + "\n";
        string2 += 'Description: "' + this.description + '"\n';
        string2 += 'Auxiliary File: "' + this.aux_file + '"\n';
        string2 += "Q-Form Code = " + this.qform_code + " (" + this.getTransformCodeString(this.qform_code) + ")\n";
        string2 += "S-Form Code = " + this.sform_code + " (" + this.getTransformCodeString(this.sform_code) + ")\n";
        string2 += "Quaternion Parameters:  b = " + fmt(this.quatern_b) + "  c = " + fmt(this.quatern_c) + "  d = " + fmt(this.quatern_d) + "\n";
        string2 += "Quaternion Offsets:  x = " + this.qoffset_x + "  y = " + this.qoffset_y + "  z = " + this.qoffset_z + "\n";
        string2 += "S-Form Parameters X: " + fmt(this.affine[0][0]) + ", " + fmt(this.affine[0][1]) + ", " + fmt(this.affine[0][2]) + ", " + fmt(this.affine[0][3]) + "\n";
        string2 += "S-Form Parameters Y: " + fmt(this.affine[1][0]) + ", " + fmt(this.affine[1][1]) + ", " + fmt(this.affine[1][2]) + ", " + fmt(this.affine[1][3]) + "\n";
        string2 += "S-Form Parameters Z: " + fmt(this.affine[2][0]) + ", " + fmt(this.affine[2][1]) + ", " + fmt(this.affine[2][2]) + ", " + fmt(this.affine[2][3]) + "\n";
        string2 += "Slice Code = " + this.slice_code + "\n";
        string2 += "Units Code = " + this.xyzt_units + " (" + this.getUnitsCodeString(nifti1_1.NIFTI1.SPATIAL_UNITS_MASK & this.xyzt_units) + ", " + this.getUnitsCodeString(nifti1_1.NIFTI1.TEMPORAL_UNITS_MASK & this.xyzt_units) + ")\n";
        string2 += "Intent Code = " + this.intent_code + "\n";
        string2 += 'Intent Name: "' + this.intent_name + '"\n';
        string2 += "Dim Info = " + this.dim_info + "\n";
        return string2;
      }
      /**
       * Returns the byte index of the extension.
       * @returns {number}
       */
      getExtensionLocation = function() {
        return _NIFTI2.MAGIC_COOKIE + 4;
      };
      /**
       * Returns the extension size.
       * @param {DataView} data
       * @returns {number}
       */
      getExtensionSize = nifti1_1.NIFTI1.prototype.getExtensionSize;
      /**
       * Returns the extension code.
       * @param {DataView} data
       * @returns {number}
       */
      getExtensionCode = nifti1_1.NIFTI1.prototype.getExtensionCode;
      /**
       * Adds an extension
       * @param {NIFTIEXTENSION} extension
       * @param {number} index
       */
      addExtension = nifti1_1.NIFTI1.prototype.addExtension;
      /**
       * Removes an extension
       * @param {number} index
       */
      removeExtension = nifti1_1.NIFTI1.prototype.removeExtension;
      /**
       * Returns a human-readable string of datatype.
       * @param {number} code
       * @returns {string}
       */
      getDatatypeCodeString = nifti1_1.NIFTI1.prototype.getDatatypeCodeString;
      /**
       * Returns a human-readable string of transform type.
       * @param {number} code
       * @returns {string}
       */
      getTransformCodeString = nifti1_1.NIFTI1.prototype.getTransformCodeString;
      /**
       * Returns a human-readable string of spatial and temporal units.
       * @param {number} code
       * @returns {string}
       */
      getUnitsCodeString = nifti1_1.NIFTI1.prototype.getUnitsCodeString;
      /**
       * Returns the qform matrix.
       * @returns {Array.<Array.<number>>}
       */
      getQformMat = nifti1_1.NIFTI1.prototype.getQformMat;
      /**
       * Converts qform to an affine.  (See http://nifti.nimh.nih.gov/pub/dist/src/niftilib/nifti1_io.c)
       * @param {number} qb
       * @param {number} qc
       * @param {number} qd
       * @param {number} qx
       * @param {number} qy
       * @param {number} qz
       * @param {number} dx
       * @param {number} dy
       * @param {number} dz
       * @param {number} qfac
       * @returns {Array.<Array.<number>>}
       */
      convertNiftiQFormToNiftiSForm = nifti1_1.NIFTI1.prototype.convertNiftiQFormToNiftiSForm;
      /**
       * Converts sform to an orientation string (e.g., XYZ+--).  (See http://nimh.nih.gov/pub/dist/src/niftilib/nifti1_io.c)
       * @param {Array.<Array.<number>>} R
       * @returns {string}
       */
      convertNiftiSFormToNEMA = nifti1_1.NIFTI1.prototype.convertNiftiSFormToNEMA;
      nifti_mat33_mul = nifti1_1.NIFTI1.prototype.nifti_mat33_mul;
      nifti_mat33_determ = nifti1_1.NIFTI1.prototype.nifti_mat33_determ;
      /**
       * Returns header as ArrayBuffer.
       * @param {boolean} includeExtensions - should extension bytes be included
       * @returns {ArrayBuffer}
       */
      toArrayBuffer(includeExtensions = false) {
        const INT64_SIZE = 8;
        const DOUBLE_SIZE = 8;
        let byteSize = 540 + 4;
        if (includeExtensions) {
          for (let extension of this.extensions) {
            byteSize += extension.esize;
          }
        }
        let byteArray = new Uint8Array(byteSize);
        let view = new DataView(byteArray.buffer);
        view.setInt32(0, 540, this.littleEndian);
        byteArray.set(Buffer.from(this.magic), 4);
        view.setInt16(12, this.datatypeCode, this.littleEndian);
        view.setInt16(14, this.numBitsPerVoxel, this.littleEndian);
        for (let i = 0; i < 8; i++) {
          view.setBigInt64(16 + INT64_SIZE * i, BigInt(this.dims[i]), this.littleEndian);
        }
        view.setFloat64(80, this.intent_p1, this.littleEndian);
        view.setFloat64(88, this.intent_p2, this.littleEndian);
        view.setFloat64(96, this.intent_p3, this.littleEndian);
        for (let i = 0; i < 8; i++) {
          view.setFloat64(104 + DOUBLE_SIZE * i, this.pixDims[i], this.littleEndian);
        }
        view.setBigInt64(168, BigInt(this.vox_offset), this.littleEndian);
        view.setFloat64(176, this.scl_slope, this.littleEndian);
        view.setFloat64(184, this.scl_inter, this.littleEndian);
        view.setFloat64(192, this.cal_max, this.littleEndian);
        view.setFloat64(200, this.cal_min, this.littleEndian);
        view.setFloat64(208, this.slice_duration, this.littleEndian);
        view.setFloat64(216, this.toffset, this.littleEndian);
        view.setBigInt64(224, BigInt(this.slice_start), this.littleEndian);
        view.setBigInt64(232, BigInt(this.slice_end), this.littleEndian);
        byteArray.set(Buffer.from(this.description), 240);
        byteArray.set(Buffer.from(this.aux_file), 320);
        view.setInt32(344, this.qform_code, this.littleEndian);
        view.setInt32(348, this.sform_code, this.littleEndian);
        view.setFloat64(352, this.quatern_b, this.littleEndian);
        view.setFloat64(360, this.quatern_c, this.littleEndian);
        view.setFloat64(368, this.quatern_d, this.littleEndian);
        view.setFloat64(376, this.qoffset_x, this.littleEndian);
        view.setFloat64(384, this.qoffset_y, this.littleEndian);
        view.setFloat64(392, this.qoffset_z, this.littleEndian);
        const flattened = this.affine.flat();
        for (let i = 0; i < 12; i++) {
          view.setFloat64(400 + DOUBLE_SIZE * i, flattened[i], this.littleEndian);
        }
        view.setInt32(496, this.slice_code, this.littleEndian);
        view.setInt32(500, this.xyzt_units, this.littleEndian);
        view.setInt32(504, this.intent_code, this.littleEndian);
        byteArray.set(Buffer.from(this.intent_name), 508);
        view.setUint8(524, this.dim_info);
        if (includeExtensions) {
          byteArray.set(Uint8Array.from([1, 0, 0, 0]), 540);
          let extensionByteIndex = this.getExtensionLocation();
          for (const extension of this.extensions) {
            view.setInt32(extensionByteIndex, extension.esize, extension.littleEndian);
            view.setInt32(extensionByteIndex + 4, extension.ecode, extension.littleEndian);
            byteArray.set(new Uint8Array(extension.edata), extensionByteIndex + 8);
            extensionByteIndex += extension.esize;
          }
        } else {
          byteArray.set(new Uint8Array(4).fill(0), 540);
        }
        return byteArray.buffer;
      }
    };
    exports.NIFTI2 = NIFTI2;
  }
});

// node_modules/nifti-reader-js/dist/src/nifti.js
var require_nifti = __commonJS({
  "node_modules/nifti-reader-js/dist/src/nifti.js"(exports) {
    "use strict";
    init_legacy_browser();
    var __createBinding = exports && exports.__createBinding || (Object.create ? (function(o, m, k, k22) {
      if (k22 === void 0) k22 = k;
      var desc = Object.getOwnPropertyDescriptor(m, k);
      if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
        desc = { enumerable: true, get: function() {
          return m[k];
        } };
      }
      Object.defineProperty(o, k22, desc);
    }) : (function(o, m, k, k22) {
      if (k22 === void 0) k22 = k;
      o[k22] = m[k];
    }));
    var __setModuleDefault = exports && exports.__setModuleDefault || (Object.create ? (function(o, v) {
      Object.defineProperty(o, "default", { enumerable: true, value: v });
    }) : function(o, v) {
      o["default"] = v;
    });
    var __importStar = exports && exports.__importStar || function(mod) {
      if (mod && mod.__esModule) return mod;
      var result = {};
      if (mod != null) {
        for (var k in mod) if (k !== "default" && Object.prototype.hasOwnProperty.call(mod, k)) __createBinding(result, mod, k);
      }
      __setModuleDefault(result, mod);
      return result;
    };
    Object.defineProperty(exports, "__esModule", { value: true });
    exports.readExtensionData = exports.readExtension = exports.readImage = exports.hasExtension = exports.readHeader = exports.decompress = exports.isCompressed = exports.isNIFTI = exports.isNIFTI2 = exports.isNIFTI1 = exports.NIFTIEXTENSION = exports.Utils = exports.NIFTI2 = exports.NIFTI1 = void 0;
    var fflate = __importStar(require_browser());
    var nifti1_1 = require_nifti1();
    var nifti2_1 = require_nifti2();
    var utilities_1 = require_utilities();
    var nifti1_2 = require_nifti1();
    Object.defineProperty(exports, "NIFTI1", { enumerable: true, get: function() {
      return nifti1_2.NIFTI1;
    } });
    var nifti2_2 = require_nifti2();
    Object.defineProperty(exports, "NIFTI2", { enumerable: true, get: function() {
      return nifti2_2.NIFTI2;
    } });
    var utilities_2 = require_utilities();
    Object.defineProperty(exports, "Utils", { enumerable: true, get: function() {
      return utilities_2.Utils;
    } });
    var nifti_extension_1 = require_nifti_extension();
    Object.defineProperty(exports, "NIFTIEXTENSION", { enumerable: true, get: function() {
      return nifti_extension_1.NIFTIEXTENSION;
    } });
    function isNIFTI1(data, isHdrImgPairOK = false) {
      var buf, mag1, mag2, mag3;
      if (data.byteLength < nifti1_1.NIFTI1.STANDARD_HEADER_SIZE) {
        return false;
      }
      buf = new DataView(data);
      if (buf)
        mag1 = buf.getUint8(nifti1_1.NIFTI1.MAGIC_NUMBER_LOCATION);
      mag2 = buf.getUint8(nifti1_1.NIFTI1.MAGIC_NUMBER_LOCATION + 1);
      mag3 = buf.getUint8(nifti1_1.NIFTI1.MAGIC_NUMBER_LOCATION + 2);
      if (isHdrImgPairOK && mag1 === nifti1_1.NIFTI1.MAGIC_NUMBER2[0] && mag2 === nifti1_1.NIFTI1.MAGIC_NUMBER2[1] && mag3 === nifti1_1.NIFTI1.MAGIC_NUMBER2[2])
        return true;
      return !!(mag1 === nifti1_1.NIFTI1.MAGIC_NUMBER[0] && mag2 === nifti1_1.NIFTI1.MAGIC_NUMBER[1] && mag3 === nifti1_1.NIFTI1.MAGIC_NUMBER[2]);
    }
    exports.isNIFTI1 = isNIFTI1;
    function isNIFTI2(data, isHdrImgPairOK = false) {
      var buf, mag1, mag2, mag3;
      if (data.byteLength < nifti1_1.NIFTI1.STANDARD_HEADER_SIZE) {
        return false;
      }
      buf = new DataView(data);
      mag1 = buf.getUint8(nifti2_1.NIFTI2.MAGIC_NUMBER_LOCATION);
      mag2 = buf.getUint8(nifti2_1.NIFTI2.MAGIC_NUMBER_LOCATION + 1);
      mag3 = buf.getUint8(nifti2_1.NIFTI2.MAGIC_NUMBER_LOCATION + 2);
      if (isHdrImgPairOK && mag1 === nifti2_1.NIFTI2.MAGIC_NUMBER2[0] && mag2 === nifti2_1.NIFTI2.MAGIC_NUMBER2[1] && mag3 === nifti2_1.NIFTI2.MAGIC_NUMBER2[2])
        return true;
      return !!(mag1 === nifti2_1.NIFTI2.MAGIC_NUMBER[0] && mag2 === nifti2_1.NIFTI2.MAGIC_NUMBER[1] && mag3 === nifti2_1.NIFTI2.MAGIC_NUMBER[2]);
    }
    exports.isNIFTI2 = isNIFTI2;
    function isNIFTI(data, isHdrImgPairOK = false) {
      return isNIFTI1(data, isHdrImgPairOK) || isNIFTI2(data, isHdrImgPairOK);
    }
    exports.isNIFTI = isNIFTI;
    function isCompressed2(data) {
      var buf, magicCookie1, magicCookie2;
      if (data) {
        buf = new DataView(data);
        magicCookie1 = buf.getUint8(0);
        magicCookie2 = buf.getUint8(1);
        if (magicCookie1 === utilities_1.Utils.GUNZIP_MAGIC_COOKIE1) {
          return true;
        }
        if (magicCookie2 === utilities_1.Utils.GUNZIP_MAGIC_COOKIE2) {
          return true;
        }
      }
      return false;
    }
    exports.isCompressed = isCompressed2;
    function decompress(data) {
      return fflate.decompressSync(new Uint8Array(data)).buffer;
    }
    exports.decompress = decompress;
    function readHeader2(data, isHdrImgPairOK = false) {
      var header = null;
      if (isCompressed2(data)) {
        data = decompress(data);
      }
      if (isNIFTI1(data, isHdrImgPairOK)) {
        header = new nifti1_1.NIFTI1();
      } else if (isNIFTI2(data, isHdrImgPairOK)) {
        header = new nifti2_1.NIFTI2();
      }
      if (header) {
        header.readHeader(data);
      } else {
        console.error("That file does not appear to be NIFTI!");
      }
      return header;
    }
    exports.readHeader = readHeader2;
    function hasExtension(header) {
      return header.extensionFlag[0] != 0;
    }
    exports.hasExtension = hasExtension;
    function readImage2(header, data) {
      var imageOffset = header.vox_offset, timeDim = 1, statDim = 1;
      if (header.dims[4]) {
        timeDim = header.dims[4];
      }
      if (header.dims[5]) {
        statDim = header.dims[5];
      }
      var imageSize = header.dims[1] * header.dims[2] * header.dims[3] * timeDim * statDim * (header.numBitsPerVoxel / 8);
      return data.slice(imageOffset, imageOffset + imageSize);
    }
    exports.readImage = readImage2;
    function readExtension(header, data) {
      var loc = header.getExtensionLocation(), size = header.extensionSize;
      return data.slice(loc, loc + size);
    }
    exports.readExtension = readExtension;
    function readExtensionData(header, data) {
      var loc = header.getExtensionLocation(), size = header.extensionSize;
      return data.slice(loc + 8, loc + size);
    }
    exports.readExtensionData = readExtensionData;
  }
});

// node_modules/crc-32/crc32c.js
var require_crc32c = __commonJS({
  "node_modules/crc-32/crc32c.js"(exports) {
    init_legacy_browser();
    var CRC32C;
    (function(factory) {
      if (typeof DO_NOT_EXPORT_CRC === "undefined") {
        if ("object" === typeof exports) {
          factory(exports);
        } else if ("function" === typeof define && define.amd) {
          define(function() {
            var module2 = {};
            factory(module2);
            return module2;
          });
        } else {
          factory(CRC32C = {});
        }
      } else {
        factory(CRC32C = {});
      }
    })(function(CRC32C2) {
      CRC32C2.version = "1.2.2";
      function signed_crc_table() {
        var c = 0, table = new Array(256);
        for (var n = 0; n != 256; ++n) {
          c = n;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -2097792136 ^ c >>> 1 : c >>> 1;
          table[n] = c;
        }
        return typeof Int32Array !== "undefined" ? new Int32Array(table) : table;
      }
      var T0 = signed_crc_table();
      function slice_by_16_tables(T) {
        var c = 0, v = 0, n = 0, table = typeof Int32Array !== "undefined" ? new Int32Array(4096) : new Array(4096);
        for (n = 0; n != 256; ++n) table[n] = T[n];
        for (n = 0; n != 256; ++n) {
          v = T[n];
          for (c = 256 + n; c < 4096; c += 256) v = table[c] = v >>> 8 ^ T[v & 255];
        }
        var out = [];
        for (n = 1; n != 16; ++n) out[n - 1] = typeof Int32Array !== "undefined" ? table.subarray(n * 256, n * 256 + 256) : table.slice(n * 256, n * 256 + 256);
        return out;
      }
      var TT = slice_by_16_tables(T0);
      var T1 = TT[0], T2 = TT[1], T3 = TT[2], T4 = TT[3], T5 = TT[4];
      var T6 = TT[5], T7 = TT[6], T8 = TT[7], T9 = TT[8], Ta = TT[9];
      var Tb = TT[10], Tc = TT[11], Td = TT[12], Te = TT[13], Tf = TT[14];
      function crc32_bstr(bstr, seed) {
        var C = seed ^ -1;
        for (var i = 0, L = bstr.length; i < L; ) C = C >>> 8 ^ T0[(C ^ bstr.charCodeAt(i++)) & 255];
        return ~C;
      }
      function crc32_buf(B, seed) {
        var C = seed ^ -1, L = B.length - 15, i = 0;
        for (; i < L; ) C = Tf[B[i++] ^ C & 255] ^ Te[B[i++] ^ C >> 8 & 255] ^ Td[B[i++] ^ C >> 16 & 255] ^ Tc[B[i++] ^ C >>> 24] ^ Tb[B[i++]] ^ Ta[B[i++]] ^ T9[B[i++]] ^ T8[B[i++]] ^ T7[B[i++]] ^ T6[B[i++]] ^ T5[B[i++]] ^ T4[B[i++]] ^ T3[B[i++]] ^ T2[B[i++]] ^ T1[B[i++]] ^ T0[B[i++]];
        L += 15;
        while (i < L) C = C >>> 8 ^ T0[(C ^ B[i++]) & 255];
        return ~C;
      }
      function crc32_str(str6, seed) {
        var C = seed ^ -1;
        for (var i = 0, L = str6.length, c = 0, d = 0; i < L; ) {
          c = str6.charCodeAt(i++);
          if (c < 128) {
            C = C >>> 8 ^ T0[(C ^ c) & 255];
          } else if (c < 2048) {
            C = C >>> 8 ^ T0[(C ^ (192 | c >> 6 & 31)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c & 63)) & 255];
          } else if (c >= 55296 && c < 57344) {
            c = (c & 1023) + 64;
            d = str6.charCodeAt(i++) & 1023;
            C = C >>> 8 ^ T0[(C ^ (240 | c >> 8 & 7)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c >> 2 & 63)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | d >> 6 & 15 | (c & 3) << 4)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | d & 63)) & 255];
          } else {
            C = C >>> 8 ^ T0[(C ^ (224 | c >> 12 & 15)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c >> 6 & 63)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c & 63)) & 255];
          }
        }
        return ~C;
      }
      CRC32C2.table = T0;
      CRC32C2.bstr = crc32_bstr;
      CRC32C2.buf = crc32_buf;
      CRC32C2.str = crc32_str;
    });
  }
});

// node_modules/crc-32/crc32.js
var require_crc32 = __commonJS({
  "node_modules/crc-32/crc32.js"(exports) {
    init_legacy_browser();
    var CRC32;
    (function(factory) {
      if (typeof DO_NOT_EXPORT_CRC === "undefined") {
        if ("object" === typeof exports) {
          factory(exports);
        } else if ("function" === typeof define && define.amd) {
          define(function() {
            var module2 = {};
            factory(module2);
            return module2;
          });
        } else {
          factory(CRC32 = {});
        }
      } else {
        factory(CRC32 = {});
      }
    })(function(CRC322) {
      CRC322.version = "1.2.2";
      function signed_crc_table() {
        var c = 0, table = new Array(256);
        for (var n = 0; n != 256; ++n) {
          c = n;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          c = c & 1 ? -306674912 ^ c >>> 1 : c >>> 1;
          table[n] = c;
        }
        return typeof Int32Array !== "undefined" ? new Int32Array(table) : table;
      }
      var T0 = signed_crc_table();
      function slice_by_16_tables(T) {
        var c = 0, v = 0, n = 0, table = typeof Int32Array !== "undefined" ? new Int32Array(4096) : new Array(4096);
        for (n = 0; n != 256; ++n) table[n] = T[n];
        for (n = 0; n != 256; ++n) {
          v = T[n];
          for (c = 256 + n; c < 4096; c += 256) v = table[c] = v >>> 8 ^ T[v & 255];
        }
        var out = [];
        for (n = 1; n != 16; ++n) out[n - 1] = typeof Int32Array !== "undefined" ? table.subarray(n * 256, n * 256 + 256) : table.slice(n * 256, n * 256 + 256);
        return out;
      }
      var TT = slice_by_16_tables(T0);
      var T1 = TT[0], T2 = TT[1], T3 = TT[2], T4 = TT[3], T5 = TT[4];
      var T6 = TT[5], T7 = TT[6], T8 = TT[7], T9 = TT[8], Ta = TT[9];
      var Tb = TT[10], Tc = TT[11], Td = TT[12], Te = TT[13], Tf = TT[14];
      function crc32_bstr(bstr, seed) {
        var C = seed ^ -1;
        for (var i = 0, L = bstr.length; i < L; ) C = C >>> 8 ^ T0[(C ^ bstr.charCodeAt(i++)) & 255];
        return ~C;
      }
      function crc32_buf(B, seed) {
        var C = seed ^ -1, L = B.length - 15, i = 0;
        for (; i < L; ) C = Tf[B[i++] ^ C & 255] ^ Te[B[i++] ^ C >> 8 & 255] ^ Td[B[i++] ^ C >> 16 & 255] ^ Tc[B[i++] ^ C >>> 24] ^ Tb[B[i++]] ^ Ta[B[i++]] ^ T9[B[i++]] ^ T8[B[i++]] ^ T7[B[i++]] ^ T6[B[i++]] ^ T5[B[i++]] ^ T4[B[i++]] ^ T3[B[i++]] ^ T2[B[i++]] ^ T1[B[i++]] ^ T0[B[i++]];
        L += 15;
        while (i < L) C = C >>> 8 ^ T0[(C ^ B[i++]) & 255];
        return ~C;
      }
      function crc32_str(str6, seed) {
        var C = seed ^ -1;
        for (var i = 0, L = str6.length, c = 0, d = 0; i < L; ) {
          c = str6.charCodeAt(i++);
          if (c < 128) {
            C = C >>> 8 ^ T0[(C ^ c) & 255];
          } else if (c < 2048) {
            C = C >>> 8 ^ T0[(C ^ (192 | c >> 6 & 31)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c & 63)) & 255];
          } else if (c >= 55296 && c < 57344) {
            c = (c & 1023) + 64;
            d = str6.charCodeAt(i++) & 1023;
            C = C >>> 8 ^ T0[(C ^ (240 | c >> 8 & 7)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c >> 2 & 63)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | d >> 6 & 15 | (c & 3) << 4)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | d & 63)) & 255];
          } else {
            C = C >>> 8 ^ T0[(C ^ (224 | c >> 12 & 15)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c >> 6 & 63)) & 255];
            C = C >>> 8 ^ T0[(C ^ (128 | c & 63)) & 255];
          }
        }
        return ~C;
      }
      CRC322.table = T0;
      CRC322.bstr = crc32_bstr;
      CRC322.buf = crc32_buf;
      CRC322.str = crc32_str;
    });
  }
});

// node_modules/neuroglancer/lib/chunk_worker.bundle.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/polyfills.js
init_legacy_browser();
var import_dispose = __toESM(require_dispose3(), 1);
var import_async_dispose = __toESM(require_async_dispose3(), 1);

// node_modules/neuroglancer/lib/shared_watchable_value.js
init_legacy_browser();

// node_modules/neuroglancer/lib/trackable_value.js
init_legacy_browser();

// node_modules/lodash-es/lodash.js
init_legacy_browser();

// node_modules/lodash-es/isSymbol.js
init_legacy_browser();

// node_modules/lodash-es/_baseGetTag.js
init_legacy_browser();

// node_modules/lodash-es/_Symbol.js
init_legacy_browser();

// node_modules/lodash-es/_root.js
init_legacy_browser();

// node_modules/lodash-es/_freeGlobal.js
init_legacy_browser();
var freeGlobal = typeof global == "object" && global && global.Object === Object && global;
var freeGlobal_default = freeGlobal;

// node_modules/lodash-es/_root.js
var freeSelf = typeof self == "object" && self && self.Object === Object && self;
var root = freeGlobal_default || freeSelf || Function("return this")();
var root_default = root;

// node_modules/lodash-es/_Symbol.js
var Symbol2 = root_default.Symbol;
var Symbol_default = Symbol2;

// node_modules/lodash-es/_getRawTag.js
init_legacy_browser();
var objectProto = Object.prototype;
var hasOwnProperty = objectProto.hasOwnProperty;
var nativeObjectToString = objectProto.toString;
var symToStringTag = Symbol_default ? Symbol_default.toStringTag : void 0;
function getRawTag(value) {
  var isOwn = hasOwnProperty.call(value, symToStringTag), tag = value[symToStringTag];
  try {
    value[symToStringTag] = void 0;
    var unmasked = true;
  } catch (e) {
  }
  var result = nativeObjectToString.call(value);
  if (unmasked) {
    if (isOwn) {
      value[symToStringTag] = tag;
    } else {
      delete value[symToStringTag];
    }
  }
  return result;
}
var getRawTag_default = getRawTag;

// node_modules/lodash-es/_objectToString.js
init_legacy_browser();
var objectProto2 = Object.prototype;
var nativeObjectToString2 = objectProto2.toString;
function objectToString(value) {
  return nativeObjectToString2.call(value);
}
var objectToString_default = objectToString;

// node_modules/lodash-es/_baseGetTag.js
var nullTag = "[object Null]";
var undefinedTag = "[object Undefined]";
var symToStringTag2 = Symbol_default ? Symbol_default.toStringTag : void 0;
function baseGetTag(value) {
  if (value == null) {
    return value === void 0 ? undefinedTag : nullTag;
  }
  return symToStringTag2 && symToStringTag2 in Object(value) ? getRawTag_default(value) : objectToString_default(value);
}
var baseGetTag_default = baseGetTag;

// node_modules/lodash-es/isObjectLike.js
init_legacy_browser();
function isObjectLike(value) {
  return value != null && typeof value == "object";
}
var isObjectLike_default = isObjectLike;

// node_modules/lodash-es/isSymbol.js
var symbolTag = "[object Symbol]";
function isSymbol(value) {
  return typeof value == "symbol" || isObjectLike_default(value) && baseGetTag_default(value) == symbolTag;
}
var isSymbol_default = isSymbol;

// node_modules/lodash-es/toNumber.js
init_legacy_browser();

// node_modules/lodash-es/_baseTrim.js
init_legacy_browser();

// node_modules/lodash-es/_trimmedEndIndex.js
init_legacy_browser();
var reWhitespace = /\s/;
function trimmedEndIndex(string2) {
  var index = string2.length;
  while (index-- && reWhitespace.test(string2.charAt(index))) {
  }
  return index;
}
var trimmedEndIndex_default = trimmedEndIndex;

// node_modules/lodash-es/_baseTrim.js
var reTrimStart = /^\s+/;
function baseTrim(string2) {
  return string2 ? string2.slice(0, trimmedEndIndex_default(string2) + 1).replace(reTrimStart, "") : string2;
}
var baseTrim_default = baseTrim;

// node_modules/lodash-es/isObject.js
init_legacy_browser();
function isObject(value) {
  var type = typeof value;
  return value != null && (type == "object" || type == "function");
}
var isObject_default = isObject;

// node_modules/lodash-es/toNumber.js
var NAN = 0 / 0;
var reIsBadHex = /^[-+]0x[0-9a-f]+$/i;
var reIsBinary = /^0b[01]+$/i;
var reIsOctal = /^0o[0-7]+$/i;
var freeParseInt = parseInt;
function toNumber(value) {
  if (typeof value == "number") {
    return value;
  }
  if (isSymbol_default(value)) {
    return NAN;
  }
  if (isObject_default(value)) {
    var other = typeof value.valueOf == "function" ? value.valueOf() : value;
    value = isObject_default(other) ? other + "" : other;
  }
  if (typeof value != "string") {
    return value === 0 ? value : +value;
  }
  value = baseTrim_default(value);
  var isBinary = reIsBinary.test(value);
  return isBinary || reIsOctal.test(value) ? freeParseInt(value.slice(2), isBinary ? 2 : 8) : reIsBadHex.test(value) ? NAN : +value;
}
var toNumber_default = toNumber;

// node_modules/lodash-es/debounce.js
init_legacy_browser();

// node_modules/lodash-es/now.js
init_legacy_browser();
var now = function() {
  return root_default.Date.now();
};
var now_default = now;

// node_modules/lodash-es/debounce.js
var FUNC_ERROR_TEXT = "Expected a function";
var nativeMax = Math.max;
var nativeMin = Math.min;
function debounce(func, wait, options) {
  var lastArgs, lastThis, maxWait, result, timerId, lastCallTime, lastInvokeTime = 0, leading = false, maxing = false, trailing = true;
  if (typeof func != "function") {
    throw new TypeError(FUNC_ERROR_TEXT);
  }
  wait = toNumber_default(wait) || 0;
  if (isObject_default(options)) {
    leading = !!options.leading;
    maxing = "maxWait" in options;
    maxWait = maxing ? nativeMax(toNumber_default(options.maxWait) || 0, wait) : maxWait;
    trailing = "trailing" in options ? !!options.trailing : trailing;
  }
  function invokeFunc(time) {
    var args = lastArgs, thisArg = lastThis;
    lastArgs = lastThis = void 0;
    lastInvokeTime = time;
    result = func.apply(thisArg, args);
    return result;
  }
  function leadingEdge(time) {
    lastInvokeTime = time;
    timerId = setTimeout(timerExpired, wait);
    return leading ? invokeFunc(time) : result;
  }
  function remainingWait(time) {
    var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime, timeWaiting = wait - timeSinceLastCall;
    return maxing ? nativeMin(timeWaiting, maxWait - timeSinceLastInvoke) : timeWaiting;
  }
  function shouldInvoke(time) {
    var timeSinceLastCall = time - lastCallTime, timeSinceLastInvoke = time - lastInvokeTime;
    return lastCallTime === void 0 || timeSinceLastCall >= wait || timeSinceLastCall < 0 || maxing && timeSinceLastInvoke >= maxWait;
  }
  function timerExpired() {
    var time = now_default();
    if (shouldInvoke(time)) {
      return trailingEdge(time);
    }
    timerId = setTimeout(timerExpired, remainingWait(time));
  }
  function trailingEdge(time) {
    timerId = void 0;
    if (trailing && lastArgs) {
      return invokeFunc(time);
    }
    lastArgs = lastThis = void 0;
    return result;
  }
  function cancel() {
    if (timerId !== void 0) {
      clearTimeout(timerId);
    }
    lastInvokeTime = 0;
    lastArgs = lastCallTime = lastThis = timerId = void 0;
  }
  function flush() {
    return timerId === void 0 ? result : trailingEdge(now_default());
  }
  function debounced() {
    var time = now_default(), isInvoking = shouldInvoke(time);
    lastArgs = arguments;
    lastThis = this;
    lastCallTime = time;
    if (isInvoking) {
      if (timerId === void 0) {
        return leadingEdge(lastCallTime);
      }
      if (maxing) {
        clearTimeout(timerId);
        timerId = setTimeout(timerExpired, wait);
        return invokeFunc(lastCallTime);
      }
    }
    if (timerId === void 0) {
      timerId = setTimeout(timerExpired, wait);
    }
    return result;
  }
  debounced.cancel = cancel;
  debounced.flush = flush;
  return debounced;
}
var debounce_default = debounce;

// node_modules/lodash-es/throttle.js
init_legacy_browser();
var FUNC_ERROR_TEXT2 = "Expected a function";
function throttle(func, wait, options) {
  var leading = true, trailing = true;
  if (typeof func != "function") {
    throw new TypeError(FUNC_ERROR_TEXT2);
  }
  if (isObject_default(options)) {
    leading = "leading" in options ? !!options.leading : leading;
    trailing = "trailing" in options ? !!options.trailing : trailing;
  }
  return debounce_default(func, wait, {
    "leading": leading,
    "maxWait": wait,
    "trailing": trailing
  });
}
var throttle_default = throttle;

// node_modules/neuroglancer/lib/util/disposable.js
init_legacy_browser();
var DEBUG_REF_COUNTS = false;
function invokeDisposer(disposer) {
  if (typeof disposer === "object") {
    disposer.dispose();
  } else {
    disposer();
  }
}
function invokeDisposers(disposers) {
  for (let i = disposers.length; i > 0; --i) {
    invokeDisposer(disposers[i - 1]);
  }
}
function registerEventListener(target2, type, listener, options) {
  target2.addEventListener(type, listener, options);
  return () => target2.removeEventListener(type, listener, options);
}
var RefCounted = class {
  refCount = 1;
  wasDisposed;
  disposers;
  addRef() {
    ++this.refCount;
    return this;
  }
  disposedStacks;
  dispose() {
    if (DEBUG_REF_COUNTS) {
      (this.disposedStacks = this.disposedStacks || []).push(new Error().stack);
    }
    if (--this.refCount !== 0) {
      return;
    }
    this.refCountReachedZero();
  }
  [Symbol.dispose]() {
    this.dispose();
  }
  refCountReachedZero() {
    this.disposed();
    const { disposers } = this;
    if (disposers !== void 0) {
      invokeDisposers(disposers);
      this.disposers = void 0;
    }
    this.wasDisposed = true;
  }
  disposed() {
  }
  registerDisposer(f) {
    const { disposers } = this;
    if (disposers == null) {
      this.disposers = [f];
    } else {
      disposers.push(f);
    }
    return f;
  }
  unregisterDisposer(f) {
    const { disposers } = this;
    if (disposers != null) {
      const index = disposers.indexOf(f);
      if (index !== -1) {
        disposers.splice(index, 1);
      }
    }
    return f;
  }
  registerEventListener(target2, type, listener, options) {
    this.registerDisposer(
      registerEventListener(target2, type, listener, options)
    );
  }
  registerCancellable(cancellable) {
    this.registerDisposer(() => {
      cancellable.cancel();
    });
    return cancellable;
  }
};
var RefCountedValue = class extends RefCounted {
  constructor(value) {
    super();
    this.value = value;
  }
};

// node_modules/neuroglancer/lib/util/signal.js
init_legacy_browser();
var Signal = class {
  handlers = /* @__PURE__ */ new Set();
  /**
   * Count of number of times this signal has been dispatched.  This is incremented each time
   * `dispatch` is called prior to invoking the handlers.
   */
  count = 0;
  constructor() {
    const obj = this;
    this.dispatch = function() {
      ++obj.count;
      obj.handlers.forEach((handler) => {
        handler.apply(this, arguments);
      });
    };
  }
  /**
   * Add a handler function.  If `dispatch` is currently be called, then the new handler will be
   * called before `dispatch` returns.
   *
   * @param handler The handler function to add.
   *
   * @return A function that unregisters the handler.
   */
  add(handler) {
    this.handlers.add(handler);
    return () => {
      return this.remove(handler);
    };
  }
  addOnce(handler) {
    const { handlers: handlers2 } = this;
    function onceWrapper(...args) {
      handlers2.delete(onceWrapper);
      handler(...args);
    }
    handlers2.add(onceWrapper);
  }
  /**
   * Remove a handler function.  If `dispatch` is currently be called and the new handler has not
   * yet been called, then it will not be called.
   *
   * @param handler Handler to remove.
   * @return `true` if the handler was present, `false` otherwise.
   */
  remove(handler) {
    return this.handlers.delete(handler);
  }
  /**
   * Invokes each handler function with the same parameters (including `this`) with which it is
   * called.  Handlers are invoked in the order in which they were added.
   */
  dispatch;
  /**
   * Disposes of resources.  No methods, including `dispatch`, may be invoked afterwards.
   */
  dispose() {
    this.handlers = void 0;
  }
};
var NullarySignal = class extends Signal {
};

// node_modules/neuroglancer/lib/trackable_value.js
var WatchableValue = class {
  constructor(value_) {
    this.value_ = value_;
  }
  get value() {
    return this.value_;
  }
  set value(newValue) {
    if (newValue !== this.value_) {
      this.value_ = newValue;
      this.changed.dispatch();
    }
  }
  changed = new NullarySignal();
};
function registerNested(f, ...watchables) {
  const values = watchables.map((w) => w.value);
  const count = watchables.length;
  let context = new RefCounted();
  let result = f(context, ...values);
  const handleChange = debounce_default(() => {
    let changed = false;
    for (let i = 0; i < count; ++i) {
      const watchable = watchables[i];
      const value = watchable.value;
      if (values[i] !== value) {
        values[i] = value;
        changed = true;
      }
    }
    if (!changed) return;
    context.dispose();
    context = new RefCounted();
    result = f(context, ...values);
  }, 0);
  const signalDisposers = watchables.map((w) => w.changed.add(handleChange));
  return {
    flush() {
      handleChange.flush();
    },
    dispose() {
      handleChange.cancel();
      invokeDisposers(signalDisposers);
      context.dispose();
    },
    get value() {
      handleChange.flush();
      return result;
    }
  };
}

// node_modules/neuroglancer/lib/worker_rpc.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/abort.js
init_legacy_browser();
function scopedAbortCallback(signal, callback) {
  if (signal === void 0) return void 0;
  if (signal.aborted) {
    callback(signal.reason);
    return void 0;
  }
  function wrappedCallback() {
    callback(this.reason);
  }
  signal.addEventListener("abort", wrappedCallback, { once: true });
  return {
    [Symbol.dispose]() {
      signal.removeEventListener("abort", wrappedCallback);
    }
  };
}
var SharedAbortController = class {
  consumers = /* @__PURE__ */ new Map();
  controller = new AbortController();
  retainCount = 0;
  get signal() {
    return this.controller.signal;
  }
  addConsumer(signal) {
    if (this.controller.signal.aborted) return void 0;
    if (signal !== void 0) {
      let wrappedCallback2 = function() {
        self2.consumers.delete(wrappedCallback2);
        if (--self2.retainCount === 0) {
          self2.controller.abort();
          self2[Symbol.dispose]();
        }
      };
      var wrappedCallback = wrappedCallback2;
      if (signal.aborted) return;
      const self2 = this;
      signal.addEventListener("abort", wrappedCallback2, { once: true });
    }
    ++this.retainCount;
  }
  [Symbol.dispose]() {
    for (const [wrappedCallback, signal] of this.consumers) {
      signal.removeEventListener("abort", wrappedCallback);
    }
    this.consumers.clear();
    this.retainCount = 0;
  }
  // Marks this controller as started. Aborts if there are no consumers.
  start() {
    if (this.retainCount === 0) {
      this.controller.abort();
    }
  }
};
function promiseWithResolversAndAbortCallback(signal, abortCallback) {
  const { promise, resolve, reject } = Promise.withResolvers();
  const cleanup = scopedAbortCallback(signal, abortCallback);
  return {
    promise,
    resolve: (value) => {
      cleanup == null ? void 0 : cleanup[Symbol.dispose]();
      resolve(value);
    },
    reject: (reason) => {
      cleanup == null ? void 0 : cleanup[Symbol.dispose]();
      reject(reason);
    }
  };
}
function raceWithAbort(promise, signal) {
  if (signal === void 0) return promise;
  if (signal.aborted) return Promise.reject(signal.reason);
  return new Promise((resolve, reject) => {
    const cleanup = scopedAbortCallback(signal, (reason) => {
      reject(reason);
    });
    promise.then(
      (value) => {
        cleanup == null ? void 0 : cleanup[Symbol.dispose]();
        resolve(value);
      },
      (reason) => {
        cleanup == null ? void 0 : cleanup[Symbol.dispose]();
        reject(reason);
      }
    );
  });
}

// node_modules/neuroglancer/lib/util/progress_listener.js
init_legacy_browser();
var ProgressSpan = class {
  constructor(listener, options) {
    this.listener = listener;
    const { id = Math.random(), startTime = Date.now(), message } = options;
    this.id = id;
    this.startTime = startTime;
    this.message = message;
    listener.addSpan(this);
  }
  id;
  startTime;
  message;
  [Symbol.dispose]() {
    this.listener.removeSpan(this.id);
  }
};
var MultiSet = class {
  items = /* @__PURE__ */ new Map();
  add(item) {
    const { items } = this;
    const count = (items.get(item) ?? 0) + 1;
    items.set(item, count);
    return count;
  }
  delete(item) {
    const { items } = this;
    let count = items.get(item);
    if (count > 1) {
      count -= 1;
      items.set(item, count);
      return count;
    }
    items.delete(item);
    return 0;
  }
  has(item) {
    return this.items.has(item);
  }
  keys() {
    return this.items.keys();
  }
  entries() {
    return this.items.entries();
  }
  [Symbol.iterator]() {
    return this.items.keys();
  }
};
var KeyedMultiSet = class {
  constructor(getKey) {
    this.getKey = getKey;
  }
  items = /* @__PURE__ */ new Map();
  add(item) {
    const { items } = this;
    const key = this.getKey(item);
    const obj = items.get(key);
    if (obj === void 0) {
      items.set(key, { value: item, count: 1 });
      return 1;
    } else {
      return obj.count += 1;
    }
  }
  delete(item) {
    return this.deleteKey(this.getKey(item));
  }
  deleteKey(key) {
    const { items } = this;
    const obj = items.get(key);
    if (obj !== void 0 && obj.count > 1) {
      return obj.count -= 1;
    }
    items.delete(key);
    return 0;
  }
  has(item) {
    return this.items.has(this.getKey(item));
  }
  *[Symbol.iterator]() {
    for (const obj of this.items.values()) {
      yield obj.value;
    }
  }
};
function getId(span) {
  return span.id;
}
var ProgressSpanSet = class extends KeyedMultiSet {
  constructor() {
    super(getId);
  }
};
var MultiConsumerProgressListener = class {
  spans = new ProgressSpanSet();
  listeners = new MultiSet();
  addSpan(span) {
    if (this.spans.add(span) !== 1) return;
    for (const listener of this.listeners) {
      listener.addSpan(span);
    }
  }
  removeSpan(spanId) {
    if (this.spans.deleteKey(spanId) !== 0) return;
    for (const listener of this.listeners) {
      listener.removeSpan(spanId);
    }
  }
  addListener(listener) {
    if (listener === void 0) return;
    if (this.listeners.add(listener) !== 1) return;
    for (const span of this.spans) {
      listener.addSpan(span);
    }
  }
  removeListener(listener) {
    if (listener === void 0) return;
    if (this.listeners.delete(listener) !== 0) return;
    for (const span of this.spans) {
      listener.removeSpan(span.id);
    }
  }
};

// node_modules/neuroglancer/lib/worker_rpc.js
var IS_WORKER = !(typeof Window !== "undefined" && self instanceof Window);
var DEBUG = false;
var DEBUG_MESSAGES = false;
var PROMISE_RESPONSE_ID = "rpc.promise.response";
var PROMISE_CANCEL_ID = "rpc.promise.cancel";
var PROMISE_PROGRESS_ADD_SPAN_ID = "rpc.promise.addProgressSpan";
var PROMISE_PROGRESS_REMOVE_SPAN_ID = "rpc.promise.removeProgressSpan";
var READY_ID = "rpc.ready";
var handlers = /* @__PURE__ */ new Map();
function registerRPC(key, handler) {
  handlers.set(key, handler);
}
var ProxyProgressListener = class {
  constructor(rpc2, id) {
    this.rpc = rpc2;
    this.id = id;
  }
  addSpan(span) {
    this.rpc.invoke(PROMISE_PROGRESS_ADD_SPAN_ID, {
      id: this.id,
      span: {
        id: span.id,
        message: span.message,
        startTime: span.startTime
      }
    });
  }
  removeSpan(spanId) {
    this.rpc.invoke(PROMISE_PROGRESS_REMOVE_SPAN_ID, {
      id: this.id,
      spanId
    });
  }
};
function registerPromiseRPC(key, handler) {
  registerRPC(key, function(x) {
    const id = x.id;
    const abortController = new AbortController();
    let progressListener;
    if (x.progressListener === true) {
      progressListener = new ProxyProgressListener(this, id);
    }
    const promise = handler.call(this, x, {
      signal: abortController.signal,
      progressListener
    });
    this.set(id, { promise, abortController });
    promise.then(
      ({ value, transfers }) => {
        this.delete(id);
        this.invoke(PROMISE_RESPONSE_ID, { id, value }, transfers);
      },
      (error) => {
        this.delete(id);
        this.invoke(PROMISE_RESPONSE_ID, {
          id,
          error
        });
      }
    );
  });
}
registerRPC(PROMISE_CANCEL_ID, function(x) {
  const id = x.id;
  const request = this.get(id);
  if (request !== void 0) {
    const { abortController } = request;
    abortController.abort();
  }
});
registerRPC(PROMISE_RESPONSE_ID, function(x) {
  const id = x.id;
  const { resolve, reject } = this.get(id);
  this.delete(id);
  if (Object.prototype.hasOwnProperty.call(x, "value")) {
    resolve(x.value);
  } else {
    reject(x.error);
  }
});
registerRPC(PROMISE_PROGRESS_ADD_SPAN_ID, function(x) {
  const id = x.id;
  const { progressListener } = this.get(id);
  new ProgressSpan(progressListener, x.span);
});
registerRPC(PROMISE_PROGRESS_REMOVE_SPAN_ID, function(x) {
  const id = x.id;
  const { progressListener } = this.get(id);
  progressListener.removeSpan(x.spanId);
});
registerRPC(READY_ID, function(x) {
  x;
  this.onPeerReady();
});
var INITIAL_RPC_ID = IS_WORKER ? -1 : 0;
var RPC = class {
  constructor(target2, waitUntilReady) {
    this.target = target2;
    if (waitUntilReady) {
      this.queue = [];
    }
    target2.onmessage = (e) => {
      const data = e.data;
      if (DEBUG_MESSAGES) {
        console.log("Received message", data);
      }
      const handler = handlers.get(data.functionName);
      if (handler === void 0) {
        throw new Error(`Missing RPC function: ${data.functionName}`);
      }
      handlers.get(data.functionName).call(this, data);
    };
  }
  objects = /* @__PURE__ */ new Map();
  nextId = INITIAL_RPC_ID;
  queue;
  sendReady() {
    this.invoke(READY_ID, {});
  }
  onPeerReady() {
    const { queue } = this;
    if (queue === void 0) return;
    this.queue = void 0;
    for (const { data, transfers } of queue) {
      this.target.postMessage(data, transfers);
    }
  }
  get numObjects() {
    return this.objects.size;
  }
  set(id, value) {
    this.objects.set(id, value);
  }
  delete(id) {
    this.objects.delete(id);
  }
  get(id) {
    return this.objects.get(id);
  }
  getRef(x) {
    const rpcId = x.id;
    const obj = this.get(rpcId);
    obj.referencedGeneration = x.gen;
    obj.addRef();
    return obj;
  }
  getOptionalRef(x) {
    if (x === void 0) return void 0;
    const rpcId = x.id;
    const obj = this.get(rpcId);
    obj.referencedGeneration = x.gen;
    obj.addRef();
    return obj;
  }
  invoke(name, x, transfers) {
    x.functionName = name;
    if (DEBUG_MESSAGES) {
      console.trace("Sending message", x);
    }
    const { queue } = this;
    if (queue !== void 0) {
      queue.push({ data: x, transfers });
      return;
    }
    this.target.postMessage(x, transfers);
  }
  promiseInvoke(name, x, options) {
    let signal;
    let progressListener;
    let transfers;
    if (options !== void 0) {
      ({ signal, progressListener, transfers } = options);
    }
    if (signal == null ? void 0 : signal.aborted) {
      return Promise.reject(signal.reason);
    }
    if (progressListener !== void 0) {
      x.progressListener = true;
    }
    const id = x.id = this.newId();
    this.invoke(name, x, transfers);
    const { promise, resolve, reject } = signal === void 0 ? Promise.withResolvers() : promiseWithResolversAndAbortCallback(signal, () => {
      this.invoke(PROMISE_CANCEL_ID, { id });
    });
    this.set(id, { resolve, reject, progressListener });
    return promise;
  }
  newId() {
    return IS_WORKER ? this.nextId-- : this.nextId++;
  }
};
var SharedObject = class extends RefCounted {
  rpc = null;
  rpcId = null;
  isOwner;
  unreferencedGeneration;
  referencedGeneration;
  initializeSharedObject(rpc2, rpcId = rpc2.newId()) {
    this.rpc = rpc2;
    this.rpcId = rpcId;
    this.isOwner = false;
    rpc2.set(rpcId, this);
  }
  initializeCounterpart(rpc2, options = {}) {
    this.initializeSharedObject(rpc2);
    this.unreferencedGeneration = 0;
    this.referencedGeneration = 0;
    this.isOwner = true;
    options.id = this.rpcId;
    options.type = this.RPC_TYPE_ID;
    rpc2.invoke("SharedObject.new", options);
  }
  dispose() {
    super.dispose();
  }
  /**
   * Precondition: this.isOwner === true.
   */
  addCounterpartRef() {
    return { id: this.rpcId, gen: ++this.referencedGeneration };
  }
  refCountReachedZero() {
    if (this.isOwner === true) {
      if (this.referencedGeneration === this.unreferencedGeneration) {
        this.ownerDispose();
      }
    } else if (this.isOwner === false) {
      this.rpc.invoke("SharedObject.refCountReachedZero", {
        id: this.rpcId,
        gen: this.referencedGeneration
      });
    } else {
      super.refCountReachedZero();
    }
  }
  /**
   * Precondition: this.isOwner === true.
   */
  ownerDispose() {
    if (DEBUG) {
      console.log(`[${IS_WORKER}] #rpc object = ${this.rpc.numObjects}`);
    }
    const { rpc: rpc2, rpcId } = this;
    super.refCountReachedZero();
    rpc2.delete(rpcId);
    rpc2.invoke("SharedObject.dispose", { id: rpcId });
  }
  /**
   * Precondition: this.isOwner === true.
   *
   * This should be called when the counterpart's refCount is decremented and reaches zero.
   */
  counterpartRefCountReachedZero(generation) {
    this.unreferencedGeneration = generation;
    if (this.refCount === 0 && generation === this.referencedGeneration) {
      this.ownerDispose();
    }
  }
};
function initializeSharedObjectCounterpart(obj, rpc2, options = {}) {
  if (rpc2 != null) {
    obj.initializeSharedObject(rpc2, options.id);
  }
}
var SharedObjectCounterpart = class extends SharedObject {
  constructor(rpc2, options = {}) {
    super();
    initializeSharedObjectCounterpart(this, rpc2, options);
  }
};
registerRPC("SharedObject.dispose", function(x) {
  const obj = this.get(x.id);
  if (obj.refCount !== 0) {
    throw new Error(
      "Attempted to dispose object with non-zero reference count."
    );
  }
  if (DEBUG) {
    console.log(`[${IS_WORKER}] #rpc objects: ${this.numObjects}`);
  }
  obj.disposed();
  this.delete(obj.rpcId);
  obj.rpcId = null;
  obj.rpc = null;
});
registerRPC("SharedObject.refCountReachedZero", function(x) {
  const obj = this.get(x.id);
  const generation = x.gen;
  obj.counterpartRefCountReachedZero(generation);
});
var sharedObjectConstructors = /* @__PURE__ */ new Map();
function registerSharedObjectOwner(identifier) {
  return (constructorFunction) => {
    constructorFunction.prototype.RPC_TYPE_ID = identifier;
  };
}
function registerSharedObject(identifier) {
  return (constructorFunction) => {
    if (identifier !== void 0) {
      constructorFunction.prototype.RPC_TYPE_ID = identifier;
    } else {
      identifier = constructorFunction.prototype.RPC_TYPE_ID;
      if (identifier === void 0) {
        throw new Error("RPC_TYPE_ID should have already been defined");
      }
    }
    sharedObjectConstructors.set(identifier, constructorFunction);
  };
}
registerRPC("SharedObject.new", function(x) {
  const rpc2 = this;
  const typeName = x.type;
  const constructorFunction = sharedObjectConstructors.get(typeName);
  const obj = new constructorFunction(rpc2, x);
  --obj.refCount;
});

// node_modules/neuroglancer/lib/shared_watchable_value.js
var __defProp2 = Object.defineProperty;
var __getOwnPropDesc2 = Object.getOwnPropertyDescriptor;
var __decorateClass = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc2(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp2(target2, key, result);
  return result;
};
var CHANGED_RPC_METHOD_ID = "SharedWatchableValue.changed";
var SharedWatchableValue = class extends SharedObjectCounterpart {
  base;
  /**
   * The value is being updated to reflect a remote change.
   * @internal
   */
  updatingValue_ = false;
  constructor(rpc2, options = {}) {
    super(rpc2, options);
    if (rpc2 !== void 0) {
      this.base = new WatchableValue(options.value);
      this.setupChangedHandler();
    }
  }
  initializeCounterpart(rpc2, options = {}) {
    options.value = this.value;
    super.initializeCounterpart(rpc2, options);
  }
  setupChangedHandler() {
    this.registerDisposer(
      this.base.changed.add(() => {
        if (this.updatingValue_) {
          this.updatingValue_ = false;
        } else {
          const { rpc: rpc2 } = this;
          if (rpc2 !== null) {
            rpc2.invoke(CHANGED_RPC_METHOD_ID, {
              id: this.rpcId,
              value: this.value
            });
          }
        }
      })
    );
  }
  static makeFromExisting(rpc2, base) {
    const obj = new SharedWatchableValue();
    obj.base = base;
    obj.setupChangedHandler();
    obj.initializeCounterpart(rpc2);
    return obj;
  }
  static make(rpc2, value) {
    return SharedWatchableValue.makeFromExisting(
      rpc2,
      new WatchableValue(value)
    );
  }
  get value() {
    return this.base.value;
  }
  set value(value) {
    this.base.value = value;
  }
  get changed() {
    return this.base.changed;
  }
};
SharedWatchableValue = __decorateClass([
  registerSharedObject("SharedWatchableValue")
], SharedWatchableValue);
registerRPC(CHANGED_RPC_METHOD_ID, function(x) {
  const obj = this.get(x.id);
  obj.updatingValue_ = true;
  obj.base.value = x.value;
  obj.updatingValue_ = false;
});

// node_modules/neuroglancer/lib/chunk_manager/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/chunk_manager/base.js
init_legacy_browser();
var ChunkState = /* @__PURE__ */ ((ChunkState2) => {
  ChunkState2[ChunkState2["GPU_MEMORY"] = 0] = "GPU_MEMORY";
  ChunkState2[ChunkState2["SYSTEM_MEMORY"] = 1] = "SYSTEM_MEMORY";
  ChunkState2[ChunkState2["SYSTEM_MEMORY_WORKER"] = 2] = "SYSTEM_MEMORY_WORKER";
  ChunkState2[ChunkState2["DOWNLOADING"] = 3] = "DOWNLOADING";
  ChunkState2[ChunkState2["QUEUED"] = 4] = "QUEUED";
  ChunkState2[ChunkState2["NEW"] = 5] = "NEW";
  ChunkState2[ChunkState2["FAILED"] = 6] = "FAILED";
  ChunkState2[ChunkState2["EXPIRED"] = 7] = "EXPIRED";
  return ChunkState2;
})(ChunkState || {});
var numChunkStates = 8;
var ChunkPriorityTier = /* @__PURE__ */ ((ChunkPriorityTier2) => {
  ChunkPriorityTier2[ChunkPriorityTier2["FIRST_TIER"] = 0] = "FIRST_TIER";
  ChunkPriorityTier2[ChunkPriorityTier2["FIRST_ORDERED_TIER"] = 0] = "FIRST_ORDERED_TIER";
  ChunkPriorityTier2[ChunkPriorityTier2["VISIBLE"] = 0] = "VISIBLE";
  ChunkPriorityTier2[ChunkPriorityTier2["PREFETCH"] = 1] = "PREFETCH";
  ChunkPriorityTier2[ChunkPriorityTier2["LAST_ORDERED_TIER"] = 1] = "LAST_ORDERED_TIER";
  ChunkPriorityTier2[ChunkPriorityTier2["RECENT"] = 2] = "RECENT";
  ChunkPriorityTier2[ChunkPriorityTier2["LAST_TIER"] = 2] = "LAST_TIER";
  return ChunkPriorityTier2;
})(ChunkPriorityTier || {});
var numChunkPriorityTiers = 3;
var ChunkDownloadStatistics = /* @__PURE__ */ ((ChunkDownloadStatistics2) => {
  ChunkDownloadStatistics2[ChunkDownloadStatistics2["totalTime"] = 0] = "totalTime";
  ChunkDownloadStatistics2[ChunkDownloadStatistics2["totalChunks"] = 1] = "totalChunks";
  return ChunkDownloadStatistics2;
})(ChunkDownloadStatistics || {});
var ChunkMemoryStatistics = /* @__PURE__ */ ((ChunkMemoryStatistics2) => {
  ChunkMemoryStatistics2[ChunkMemoryStatistics2["numChunks"] = 0] = "numChunks";
  ChunkMemoryStatistics2[ChunkMemoryStatistics2["systemMemoryBytes"] = 1] = "systemMemoryBytes";
  ChunkMemoryStatistics2[ChunkMemoryStatistics2["gpuMemoryBytes"] = 2] = "gpuMemoryBytes";
  return ChunkMemoryStatistics2;
})(ChunkMemoryStatistics || {});
var numChunkMemoryStatistics = 3;
var numChunkDownloadStatistics = 2;
var numChunkStatistics = numChunkStates * numChunkPriorityTiers * numChunkMemoryStatistics + numChunkDownloadStatistics;
function getChunkStateStatisticIndex(state, priorityTier) {
  return state * numChunkPriorityTiers + priorityTier;
}
function getChunkDownloadStatisticIndex(statistic) {
  return numChunkStates * numChunkPriorityTiers * numChunkMemoryStatistics + statistic;
}
var PREFETCH_PRIORITY_MULTIPLIER = 1e13;
var CHUNK_QUEUE_MANAGER_RPC_ID = "ChunkQueueManager";
var CHUNK_MANAGER_RPC_ID = "ChunkManager";
var CHUNK_SOURCE_INVALIDATE_RPC_ID = "ChunkSource.invalidate";
var REQUEST_CHUNK_STATISTICS_RPC_ID = "ChunkQueueManager.requestChunkStatistics";
var CHUNK_LAYER_STATISTICS_RPC_ID = "ChunkManager.chunkLayerStatistics";

// node_modules/neuroglancer/lib/util/linked_list.js
init_legacy_browser();
function linkedListOperations(options) {
  const { next: NEXT, prev: PREV } = options;
  return {
    insertAfter(head, x) {
      const next = head[NEXT];
      x[NEXT] = next;
      x[PREV] = head;
      head[NEXT] = x;
      next[PREV] = x;
    },
    insertBefore(head, x) {
      const prev = head[PREV];
      x[PREV] = prev;
      x[NEXT] = head;
      head[PREV] = x;
      prev[NEXT] = x;
    },
    front(head) {
      const next = head[NEXT];
      if (next === head) {
        return null;
      }
      return next;
    },
    back(head) {
      const next = head[PREV];
      if (next === head) {
        return null;
      }
      return next;
    },
    pop(x) {
      const next = x[NEXT];
      const prev = x[PREV];
      next[PREV] = prev;
      prev[NEXT] = next;
      x[NEXT] = null;
      x[PREV] = null;
      return x;
    },
    *iterator(head) {
      for (let x = head[NEXT]; x !== head; x = x[NEXT]) {
        yield x;
      }
    },
    *reverseIterator(head) {
      for (let x = head[PREV]; x !== head; x = x[PREV]) {
        yield x;
      }
    },
    initializeHead(head) {
      head[NEXT] = head[PREV] = head;
    }
  };
}

// node_modules/neuroglancer/lib/util/memoize.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/json.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/bigint.js
init_legacy_browser();
function bigintCompare(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}
function uint64FromLowHigh(low, high) {
  return BigInt(low) | BigInt(high) << 32n;
}
function randomUint64() {
  const low = Math.random() * 4294967296 >>> 0;
  const high = Math.random() * 4294967296 >>> 0;
  return uint64FromLowHigh(low, high);
}
var UINT64_MAX = 0xffffffffffffffffn;

// node_modules/neuroglancer/lib/util/geom.js
init_legacy_browser();

// node_modules/gl-matrix/esm/index.js
init_legacy_browser();

// node_modules/gl-matrix/esm/common.js
init_legacy_browser();
var EPSILON = 1e-6;
var ARRAY_TYPE = typeof Float32Array !== "undefined" ? Float32Array : Array;
var RANDOM = Math.random;
var degree = Math.PI / 180;
if (!Math.hypot) Math.hypot = function() {
  var y = 0, i = arguments.length;
  while (i--) {
    y += arguments[i] * arguments[i];
  }
  return Math.sqrt(y);
};

// node_modules/gl-matrix/esm/mat3.js
var mat3_exports = {};
__export(mat3_exports, {
  add: () => add,
  adjoint: () => adjoint,
  clone: () => clone2,
  copy: () => copy,
  create: () => create,
  determinant: () => determinant,
  equals: () => equals,
  exactEquals: () => exactEquals,
  frob: () => frob,
  fromMat2d: () => fromMat2d,
  fromMat4: () => fromMat4,
  fromQuat: () => fromQuat,
  fromRotation: () => fromRotation,
  fromScaling: () => fromScaling,
  fromTranslation: () => fromTranslation,
  fromValues: () => fromValues,
  identity: () => identity,
  invert: () => invert,
  mul: () => mul,
  multiply: () => multiply,
  multiplyScalar: () => multiplyScalar,
  multiplyScalarAndAdd: () => multiplyScalarAndAdd,
  normalFromMat4: () => normalFromMat4,
  projection: () => projection,
  rotate: () => rotate,
  scale: () => scale,
  set: () => set,
  str: () => str,
  sub: () => sub,
  subtract: () => subtract,
  translate: () => translate,
  transpose: () => transpose
});
init_legacy_browser();
function create() {
  var out = new ARRAY_TYPE(9);
  if (ARRAY_TYPE != Float32Array) {
    out[1] = 0;
    out[2] = 0;
    out[3] = 0;
    out[5] = 0;
    out[6] = 0;
    out[7] = 0;
  }
  out[0] = 1;
  out[4] = 1;
  out[8] = 1;
  return out;
}
function fromMat4(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[4];
  out[4] = a[5];
  out[5] = a[6];
  out[6] = a[8];
  out[7] = a[9];
  out[8] = a[10];
  return out;
}
function clone2(a) {
  var out = new ARRAY_TYPE(9);
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  out[4] = a[4];
  out[5] = a[5];
  out[6] = a[6];
  out[7] = a[7];
  out[8] = a[8];
  return out;
}
function copy(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  out[4] = a[4];
  out[5] = a[5];
  out[6] = a[6];
  out[7] = a[7];
  out[8] = a[8];
  return out;
}
function fromValues(m00, m01, m02, m10, m11, m12, m20, m21, m22) {
  var out = new ARRAY_TYPE(9);
  out[0] = m00;
  out[1] = m01;
  out[2] = m02;
  out[3] = m10;
  out[4] = m11;
  out[5] = m12;
  out[6] = m20;
  out[7] = m21;
  out[8] = m22;
  return out;
}
function set(out, m00, m01, m02, m10, m11, m12, m20, m21, m22) {
  out[0] = m00;
  out[1] = m01;
  out[2] = m02;
  out[3] = m10;
  out[4] = m11;
  out[5] = m12;
  out[6] = m20;
  out[7] = m21;
  out[8] = m22;
  return out;
}
function identity(out) {
  out[0] = 1;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 1;
  out[5] = 0;
  out[6] = 0;
  out[7] = 0;
  out[8] = 1;
  return out;
}
function transpose(out, a) {
  if (out === a) {
    var a01 = a[1], a02 = a[2], a12 = a[5];
    out[1] = a[3];
    out[2] = a[6];
    out[3] = a01;
    out[5] = a[7];
    out[6] = a02;
    out[7] = a12;
  } else {
    out[0] = a[0];
    out[1] = a[3];
    out[2] = a[6];
    out[3] = a[1];
    out[4] = a[4];
    out[5] = a[7];
    out[6] = a[2];
    out[7] = a[5];
    out[8] = a[8];
  }
  return out;
}
function invert(out, a) {
  var a00 = a[0], a01 = a[1], a02 = a[2];
  var a10 = a[3], a11 = a[4], a12 = a[5];
  var a20 = a[6], a21 = a[7], a22 = a[8];
  var b01 = a22 * a11 - a12 * a21;
  var b11 = -a22 * a10 + a12 * a20;
  var b21 = a21 * a10 - a11 * a20;
  var det = a00 * b01 + a01 * b11 + a02 * b21;
  if (!det) {
    return null;
  }
  det = 1 / det;
  out[0] = b01 * det;
  out[1] = (-a22 * a01 + a02 * a21) * det;
  out[2] = (a12 * a01 - a02 * a11) * det;
  out[3] = b11 * det;
  out[4] = (a22 * a00 - a02 * a20) * det;
  out[5] = (-a12 * a00 + a02 * a10) * det;
  out[6] = b21 * det;
  out[7] = (-a21 * a00 + a01 * a20) * det;
  out[8] = (a11 * a00 - a01 * a10) * det;
  return out;
}
function adjoint(out, a) {
  var a00 = a[0], a01 = a[1], a02 = a[2];
  var a10 = a[3], a11 = a[4], a12 = a[5];
  var a20 = a[6], a21 = a[7], a22 = a[8];
  out[0] = a11 * a22 - a12 * a21;
  out[1] = a02 * a21 - a01 * a22;
  out[2] = a01 * a12 - a02 * a11;
  out[3] = a12 * a20 - a10 * a22;
  out[4] = a00 * a22 - a02 * a20;
  out[5] = a02 * a10 - a00 * a12;
  out[6] = a10 * a21 - a11 * a20;
  out[7] = a01 * a20 - a00 * a21;
  out[8] = a00 * a11 - a01 * a10;
  return out;
}
function determinant(a) {
  var a00 = a[0], a01 = a[1], a02 = a[2];
  var a10 = a[3], a11 = a[4], a12 = a[5];
  var a20 = a[6], a21 = a[7], a22 = a[8];
  return a00 * (a22 * a11 - a12 * a21) + a01 * (-a22 * a10 + a12 * a20) + a02 * (a21 * a10 - a11 * a20);
}
function multiply(out, a, b) {
  var a00 = a[0], a01 = a[1], a02 = a[2];
  var a10 = a[3], a11 = a[4], a12 = a[5];
  var a20 = a[6], a21 = a[7], a22 = a[8];
  var b00 = b[0], b01 = b[1], b02 = b[2];
  var b10 = b[3], b11 = b[4], b12 = b[5];
  var b20 = b[6], b21 = b[7], b22 = b[8];
  out[0] = b00 * a00 + b01 * a10 + b02 * a20;
  out[1] = b00 * a01 + b01 * a11 + b02 * a21;
  out[2] = b00 * a02 + b01 * a12 + b02 * a22;
  out[3] = b10 * a00 + b11 * a10 + b12 * a20;
  out[4] = b10 * a01 + b11 * a11 + b12 * a21;
  out[5] = b10 * a02 + b11 * a12 + b12 * a22;
  out[6] = b20 * a00 + b21 * a10 + b22 * a20;
  out[7] = b20 * a01 + b21 * a11 + b22 * a21;
  out[8] = b20 * a02 + b21 * a12 + b22 * a22;
  return out;
}
function translate(out, a, v) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a10 = a[3], a11 = a[4], a12 = a[5], a20 = a[6], a21 = a[7], a22 = a[8], x = v[0], y = v[1];
  out[0] = a00;
  out[1] = a01;
  out[2] = a02;
  out[3] = a10;
  out[4] = a11;
  out[5] = a12;
  out[6] = x * a00 + y * a10 + a20;
  out[7] = x * a01 + y * a11 + a21;
  out[8] = x * a02 + y * a12 + a22;
  return out;
}
function rotate(out, a, rad) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a10 = a[3], a11 = a[4], a12 = a[5], a20 = a[6], a21 = a[7], a22 = a[8], s = Math.sin(rad), c = Math.cos(rad);
  out[0] = c * a00 + s * a10;
  out[1] = c * a01 + s * a11;
  out[2] = c * a02 + s * a12;
  out[3] = c * a10 - s * a00;
  out[4] = c * a11 - s * a01;
  out[5] = c * a12 - s * a02;
  out[6] = a20;
  out[7] = a21;
  out[8] = a22;
  return out;
}
function scale(out, a, v) {
  var x = v[0], y = v[1];
  out[0] = x * a[0];
  out[1] = x * a[1];
  out[2] = x * a[2];
  out[3] = y * a[3];
  out[4] = y * a[4];
  out[5] = y * a[5];
  out[6] = a[6];
  out[7] = a[7];
  out[8] = a[8];
  return out;
}
function fromTranslation(out, v) {
  out[0] = 1;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 1;
  out[5] = 0;
  out[6] = v[0];
  out[7] = v[1];
  out[8] = 1;
  return out;
}
function fromRotation(out, rad) {
  var s = Math.sin(rad), c = Math.cos(rad);
  out[0] = c;
  out[1] = s;
  out[2] = 0;
  out[3] = -s;
  out[4] = c;
  out[5] = 0;
  out[6] = 0;
  out[7] = 0;
  out[8] = 1;
  return out;
}
function fromScaling(out, v) {
  out[0] = v[0];
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = v[1];
  out[5] = 0;
  out[6] = 0;
  out[7] = 0;
  out[8] = 1;
  return out;
}
function fromMat2d(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = 0;
  out[3] = a[2];
  out[4] = a[3];
  out[5] = 0;
  out[6] = a[4];
  out[7] = a[5];
  out[8] = 1;
  return out;
}
function fromQuat(out, q) {
  var x = q[0], y = q[1], z = q[2], w = q[3];
  var x2 = x + x;
  var y2 = y + y;
  var z2 = z + z;
  var xx = x * x2;
  var yx = y * x2;
  var yy = y * y2;
  var zx = z * x2;
  var zy = z * y2;
  var zz = z * z2;
  var wx = w * x2;
  var wy = w * y2;
  var wz = w * z2;
  out[0] = 1 - yy - zz;
  out[3] = yx - wz;
  out[6] = zx + wy;
  out[1] = yx + wz;
  out[4] = 1 - xx - zz;
  out[7] = zy - wx;
  out[2] = zx - wy;
  out[5] = zy + wx;
  out[8] = 1 - xx - yy;
  return out;
}
function normalFromMat4(out, a) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3];
  var a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7];
  var a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11];
  var a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
  var b00 = a00 * a11 - a01 * a10;
  var b01 = a00 * a12 - a02 * a10;
  var b02 = a00 * a13 - a03 * a10;
  var b03 = a01 * a12 - a02 * a11;
  var b04 = a01 * a13 - a03 * a11;
  var b05 = a02 * a13 - a03 * a12;
  var b06 = a20 * a31 - a21 * a30;
  var b07 = a20 * a32 - a22 * a30;
  var b08 = a20 * a33 - a23 * a30;
  var b09 = a21 * a32 - a22 * a31;
  var b10 = a21 * a33 - a23 * a31;
  var b11 = a22 * a33 - a23 * a32;
  var det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
  if (!det) {
    return null;
  }
  det = 1 / det;
  out[0] = (a11 * b11 - a12 * b10 + a13 * b09) * det;
  out[1] = (a12 * b08 - a10 * b11 - a13 * b07) * det;
  out[2] = (a10 * b10 - a11 * b08 + a13 * b06) * det;
  out[3] = (a02 * b10 - a01 * b11 - a03 * b09) * det;
  out[4] = (a00 * b11 - a02 * b08 + a03 * b07) * det;
  out[5] = (a01 * b08 - a00 * b10 - a03 * b06) * det;
  out[6] = (a31 * b05 - a32 * b04 + a33 * b03) * det;
  out[7] = (a32 * b02 - a30 * b05 - a33 * b01) * det;
  out[8] = (a30 * b04 - a31 * b02 + a33 * b00) * det;
  return out;
}
function projection(out, width, height) {
  out[0] = 2 / width;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = -2 / height;
  out[5] = 0;
  out[6] = -1;
  out[7] = 1;
  out[8] = 1;
  return out;
}
function str(a) {
  return "mat3(" + a[0] + ", " + a[1] + ", " + a[2] + ", " + a[3] + ", " + a[4] + ", " + a[5] + ", " + a[6] + ", " + a[7] + ", " + a[8] + ")";
}
function frob(a) {
  return Math.hypot(a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7], a[8]);
}
function add(out, a, b) {
  out[0] = a[0] + b[0];
  out[1] = a[1] + b[1];
  out[2] = a[2] + b[2];
  out[3] = a[3] + b[3];
  out[4] = a[4] + b[4];
  out[5] = a[5] + b[5];
  out[6] = a[6] + b[6];
  out[7] = a[7] + b[7];
  out[8] = a[8] + b[8];
  return out;
}
function subtract(out, a, b) {
  out[0] = a[0] - b[0];
  out[1] = a[1] - b[1];
  out[2] = a[2] - b[2];
  out[3] = a[3] - b[3];
  out[4] = a[4] - b[4];
  out[5] = a[5] - b[5];
  out[6] = a[6] - b[6];
  out[7] = a[7] - b[7];
  out[8] = a[8] - b[8];
  return out;
}
function multiplyScalar(out, a, b) {
  out[0] = a[0] * b;
  out[1] = a[1] * b;
  out[2] = a[2] * b;
  out[3] = a[3] * b;
  out[4] = a[4] * b;
  out[5] = a[5] * b;
  out[6] = a[6] * b;
  out[7] = a[7] * b;
  out[8] = a[8] * b;
  return out;
}
function multiplyScalarAndAdd(out, a, b, scale6) {
  out[0] = a[0] + b[0] * scale6;
  out[1] = a[1] + b[1] * scale6;
  out[2] = a[2] + b[2] * scale6;
  out[3] = a[3] + b[3] * scale6;
  out[4] = a[4] + b[4] * scale6;
  out[5] = a[5] + b[5] * scale6;
  out[6] = a[6] + b[6] * scale6;
  out[7] = a[7] + b[7] * scale6;
  out[8] = a[8] + b[8] * scale6;
  return out;
}
function exactEquals(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3] && a[4] === b[4] && a[5] === b[5] && a[6] === b[6] && a[7] === b[7] && a[8] === b[8];
}
function equals(a, b) {
  var a0 = a[0], a1 = a[1], a2 = a[2], a3 = a[3], a4 = a[4], a5 = a[5], a6 = a[6], a7 = a[7], a8 = a[8];
  var b0 = b[0], b1 = b[1], b2 = b[2], b3 = b[3], b4 = b[4], b5 = b[5], b6 = b[6], b7 = b[7], b8 = b[8];
  return Math.abs(a0 - b0) <= EPSILON * Math.max(1, Math.abs(a0), Math.abs(b0)) && Math.abs(a1 - b1) <= EPSILON * Math.max(1, Math.abs(a1), Math.abs(b1)) && Math.abs(a2 - b2) <= EPSILON * Math.max(1, Math.abs(a2), Math.abs(b2)) && Math.abs(a3 - b3) <= EPSILON * Math.max(1, Math.abs(a3), Math.abs(b3)) && Math.abs(a4 - b4) <= EPSILON * Math.max(1, Math.abs(a4), Math.abs(b4)) && Math.abs(a5 - b5) <= EPSILON * Math.max(1, Math.abs(a5), Math.abs(b5)) && Math.abs(a6 - b6) <= EPSILON * Math.max(1, Math.abs(a6), Math.abs(b6)) && Math.abs(a7 - b7) <= EPSILON * Math.max(1, Math.abs(a7), Math.abs(b7)) && Math.abs(a8 - b8) <= EPSILON * Math.max(1, Math.abs(a8), Math.abs(b8));
}
var mul = multiply;
var sub = subtract;

// node_modules/gl-matrix/esm/mat4.js
var mat4_exports = {};
__export(mat4_exports, {
  add: () => add2,
  adjoint: () => adjoint2,
  clone: () => clone3,
  copy: () => copy2,
  create: () => create2,
  determinant: () => determinant2,
  equals: () => equals2,
  exactEquals: () => exactEquals2,
  frob: () => frob2,
  fromQuat: () => fromQuat3,
  fromQuat2: () => fromQuat2,
  fromRotation: () => fromRotation2,
  fromRotationTranslation: () => fromRotationTranslation,
  fromRotationTranslationScale: () => fromRotationTranslationScale,
  fromRotationTranslationScaleOrigin: () => fromRotationTranslationScaleOrigin,
  fromScaling: () => fromScaling2,
  fromTranslation: () => fromTranslation2,
  fromValues: () => fromValues2,
  fromXRotation: () => fromXRotation,
  fromYRotation: () => fromYRotation,
  fromZRotation: () => fromZRotation,
  frustum: () => frustum,
  getRotation: () => getRotation,
  getScaling: () => getScaling,
  getTranslation: () => getTranslation,
  identity: () => identity2,
  invert: () => invert2,
  lookAt: () => lookAt,
  mul: () => mul2,
  multiply: () => multiply2,
  multiplyScalar: () => multiplyScalar2,
  multiplyScalarAndAdd: () => multiplyScalarAndAdd2,
  ortho: () => ortho,
  perspective: () => perspective,
  perspectiveFromFieldOfView: () => perspectiveFromFieldOfView,
  rotate: () => rotate2,
  rotateX: () => rotateX,
  rotateY: () => rotateY,
  rotateZ: () => rotateZ,
  scale: () => scale2,
  set: () => set2,
  str: () => str2,
  sub: () => sub2,
  subtract: () => subtract2,
  targetTo: () => targetTo,
  translate: () => translate2,
  transpose: () => transpose2
});
init_legacy_browser();
function create2() {
  var out = new ARRAY_TYPE(16);
  if (ARRAY_TYPE != Float32Array) {
    out[1] = 0;
    out[2] = 0;
    out[3] = 0;
    out[4] = 0;
    out[6] = 0;
    out[7] = 0;
    out[8] = 0;
    out[9] = 0;
    out[11] = 0;
    out[12] = 0;
    out[13] = 0;
    out[14] = 0;
  }
  out[0] = 1;
  out[5] = 1;
  out[10] = 1;
  out[15] = 1;
  return out;
}
function clone3(a) {
  var out = new ARRAY_TYPE(16);
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  out[4] = a[4];
  out[5] = a[5];
  out[6] = a[6];
  out[7] = a[7];
  out[8] = a[8];
  out[9] = a[9];
  out[10] = a[10];
  out[11] = a[11];
  out[12] = a[12];
  out[13] = a[13];
  out[14] = a[14];
  out[15] = a[15];
  return out;
}
function copy2(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  out[4] = a[4];
  out[5] = a[5];
  out[6] = a[6];
  out[7] = a[7];
  out[8] = a[8];
  out[9] = a[9];
  out[10] = a[10];
  out[11] = a[11];
  out[12] = a[12];
  out[13] = a[13];
  out[14] = a[14];
  out[15] = a[15];
  return out;
}
function fromValues2(m00, m01, m02, m03, m10, m11, m12, m13, m20, m21, m22, m23, m30, m31, m32, m33) {
  var out = new ARRAY_TYPE(16);
  out[0] = m00;
  out[1] = m01;
  out[2] = m02;
  out[3] = m03;
  out[4] = m10;
  out[5] = m11;
  out[6] = m12;
  out[7] = m13;
  out[8] = m20;
  out[9] = m21;
  out[10] = m22;
  out[11] = m23;
  out[12] = m30;
  out[13] = m31;
  out[14] = m32;
  out[15] = m33;
  return out;
}
function set2(out, m00, m01, m02, m03, m10, m11, m12, m13, m20, m21, m22, m23, m30, m31, m32, m33) {
  out[0] = m00;
  out[1] = m01;
  out[2] = m02;
  out[3] = m03;
  out[4] = m10;
  out[5] = m11;
  out[6] = m12;
  out[7] = m13;
  out[8] = m20;
  out[9] = m21;
  out[10] = m22;
  out[11] = m23;
  out[12] = m30;
  out[13] = m31;
  out[14] = m32;
  out[15] = m33;
  return out;
}
function identity2(out) {
  out[0] = 1;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = 1;
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[10] = 1;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function transpose2(out, a) {
  if (out === a) {
    var a01 = a[1], a02 = a[2], a03 = a[3];
    var a12 = a[6], a13 = a[7];
    var a23 = a[11];
    out[1] = a[4];
    out[2] = a[8];
    out[3] = a[12];
    out[4] = a01;
    out[6] = a[9];
    out[7] = a[13];
    out[8] = a02;
    out[9] = a12;
    out[11] = a[14];
    out[12] = a03;
    out[13] = a13;
    out[14] = a23;
  } else {
    out[0] = a[0];
    out[1] = a[4];
    out[2] = a[8];
    out[3] = a[12];
    out[4] = a[1];
    out[5] = a[5];
    out[6] = a[9];
    out[7] = a[13];
    out[8] = a[2];
    out[9] = a[6];
    out[10] = a[10];
    out[11] = a[14];
    out[12] = a[3];
    out[13] = a[7];
    out[14] = a[11];
    out[15] = a[15];
  }
  return out;
}
function invert2(out, a) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3];
  var a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7];
  var a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11];
  var a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
  var b00 = a00 * a11 - a01 * a10;
  var b01 = a00 * a12 - a02 * a10;
  var b02 = a00 * a13 - a03 * a10;
  var b03 = a01 * a12 - a02 * a11;
  var b04 = a01 * a13 - a03 * a11;
  var b05 = a02 * a13 - a03 * a12;
  var b06 = a20 * a31 - a21 * a30;
  var b07 = a20 * a32 - a22 * a30;
  var b08 = a20 * a33 - a23 * a30;
  var b09 = a21 * a32 - a22 * a31;
  var b10 = a21 * a33 - a23 * a31;
  var b11 = a22 * a33 - a23 * a32;
  var det = b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
  if (!det) {
    return null;
  }
  det = 1 / det;
  out[0] = (a11 * b11 - a12 * b10 + a13 * b09) * det;
  out[1] = (a02 * b10 - a01 * b11 - a03 * b09) * det;
  out[2] = (a31 * b05 - a32 * b04 + a33 * b03) * det;
  out[3] = (a22 * b04 - a21 * b05 - a23 * b03) * det;
  out[4] = (a12 * b08 - a10 * b11 - a13 * b07) * det;
  out[5] = (a00 * b11 - a02 * b08 + a03 * b07) * det;
  out[6] = (a32 * b02 - a30 * b05 - a33 * b01) * det;
  out[7] = (a20 * b05 - a22 * b02 + a23 * b01) * det;
  out[8] = (a10 * b10 - a11 * b08 + a13 * b06) * det;
  out[9] = (a01 * b08 - a00 * b10 - a03 * b06) * det;
  out[10] = (a30 * b04 - a31 * b02 + a33 * b00) * det;
  out[11] = (a21 * b02 - a20 * b04 - a23 * b00) * det;
  out[12] = (a11 * b07 - a10 * b09 - a12 * b06) * det;
  out[13] = (a00 * b09 - a01 * b07 + a02 * b06) * det;
  out[14] = (a31 * b01 - a30 * b03 - a32 * b00) * det;
  out[15] = (a20 * b03 - a21 * b01 + a22 * b00) * det;
  return out;
}
function adjoint2(out, a) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3];
  var a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7];
  var a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11];
  var a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
  out[0] = a11 * (a22 * a33 - a23 * a32) - a21 * (a12 * a33 - a13 * a32) + a31 * (a12 * a23 - a13 * a22);
  out[1] = -(a01 * (a22 * a33 - a23 * a32) - a21 * (a02 * a33 - a03 * a32) + a31 * (a02 * a23 - a03 * a22));
  out[2] = a01 * (a12 * a33 - a13 * a32) - a11 * (a02 * a33 - a03 * a32) + a31 * (a02 * a13 - a03 * a12);
  out[3] = -(a01 * (a12 * a23 - a13 * a22) - a11 * (a02 * a23 - a03 * a22) + a21 * (a02 * a13 - a03 * a12));
  out[4] = -(a10 * (a22 * a33 - a23 * a32) - a20 * (a12 * a33 - a13 * a32) + a30 * (a12 * a23 - a13 * a22));
  out[5] = a00 * (a22 * a33 - a23 * a32) - a20 * (a02 * a33 - a03 * a32) + a30 * (a02 * a23 - a03 * a22);
  out[6] = -(a00 * (a12 * a33 - a13 * a32) - a10 * (a02 * a33 - a03 * a32) + a30 * (a02 * a13 - a03 * a12));
  out[7] = a00 * (a12 * a23 - a13 * a22) - a10 * (a02 * a23 - a03 * a22) + a20 * (a02 * a13 - a03 * a12);
  out[8] = a10 * (a21 * a33 - a23 * a31) - a20 * (a11 * a33 - a13 * a31) + a30 * (a11 * a23 - a13 * a21);
  out[9] = -(a00 * (a21 * a33 - a23 * a31) - a20 * (a01 * a33 - a03 * a31) + a30 * (a01 * a23 - a03 * a21));
  out[10] = a00 * (a11 * a33 - a13 * a31) - a10 * (a01 * a33 - a03 * a31) + a30 * (a01 * a13 - a03 * a11);
  out[11] = -(a00 * (a11 * a23 - a13 * a21) - a10 * (a01 * a23 - a03 * a21) + a20 * (a01 * a13 - a03 * a11));
  out[12] = -(a10 * (a21 * a32 - a22 * a31) - a20 * (a11 * a32 - a12 * a31) + a30 * (a11 * a22 - a12 * a21));
  out[13] = a00 * (a21 * a32 - a22 * a31) - a20 * (a01 * a32 - a02 * a31) + a30 * (a01 * a22 - a02 * a21);
  out[14] = -(a00 * (a11 * a32 - a12 * a31) - a10 * (a01 * a32 - a02 * a31) + a30 * (a01 * a12 - a02 * a11));
  out[15] = a00 * (a11 * a22 - a12 * a21) - a10 * (a01 * a22 - a02 * a21) + a20 * (a01 * a12 - a02 * a11);
  return out;
}
function determinant2(a) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3];
  var a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7];
  var a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11];
  var a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
  var b00 = a00 * a11 - a01 * a10;
  var b01 = a00 * a12 - a02 * a10;
  var b02 = a00 * a13 - a03 * a10;
  var b03 = a01 * a12 - a02 * a11;
  var b04 = a01 * a13 - a03 * a11;
  var b05 = a02 * a13 - a03 * a12;
  var b06 = a20 * a31 - a21 * a30;
  var b07 = a20 * a32 - a22 * a30;
  var b08 = a20 * a33 - a23 * a30;
  var b09 = a21 * a32 - a22 * a31;
  var b10 = a21 * a33 - a23 * a31;
  var b11 = a22 * a33 - a23 * a32;
  return b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06;
}
function multiply2(out, a, b) {
  var a00 = a[0], a01 = a[1], a02 = a[2], a03 = a[3];
  var a10 = a[4], a11 = a[5], a12 = a[6], a13 = a[7];
  var a20 = a[8], a21 = a[9], a22 = a[10], a23 = a[11];
  var a30 = a[12], a31 = a[13], a32 = a[14], a33 = a[15];
  var b0 = b[0], b1 = b[1], b2 = b[2], b3 = b[3];
  out[0] = b0 * a00 + b1 * a10 + b2 * a20 + b3 * a30;
  out[1] = b0 * a01 + b1 * a11 + b2 * a21 + b3 * a31;
  out[2] = b0 * a02 + b1 * a12 + b2 * a22 + b3 * a32;
  out[3] = b0 * a03 + b1 * a13 + b2 * a23 + b3 * a33;
  b0 = b[4];
  b1 = b[5];
  b2 = b[6];
  b3 = b[7];
  out[4] = b0 * a00 + b1 * a10 + b2 * a20 + b3 * a30;
  out[5] = b0 * a01 + b1 * a11 + b2 * a21 + b3 * a31;
  out[6] = b0 * a02 + b1 * a12 + b2 * a22 + b3 * a32;
  out[7] = b0 * a03 + b1 * a13 + b2 * a23 + b3 * a33;
  b0 = b[8];
  b1 = b[9];
  b2 = b[10];
  b3 = b[11];
  out[8] = b0 * a00 + b1 * a10 + b2 * a20 + b3 * a30;
  out[9] = b0 * a01 + b1 * a11 + b2 * a21 + b3 * a31;
  out[10] = b0 * a02 + b1 * a12 + b2 * a22 + b3 * a32;
  out[11] = b0 * a03 + b1 * a13 + b2 * a23 + b3 * a33;
  b0 = b[12];
  b1 = b[13];
  b2 = b[14];
  b3 = b[15];
  out[12] = b0 * a00 + b1 * a10 + b2 * a20 + b3 * a30;
  out[13] = b0 * a01 + b1 * a11 + b2 * a21 + b3 * a31;
  out[14] = b0 * a02 + b1 * a12 + b2 * a22 + b3 * a32;
  out[15] = b0 * a03 + b1 * a13 + b2 * a23 + b3 * a33;
  return out;
}
function translate2(out, a, v) {
  var x = v[0], y = v[1], z = v[2];
  var a00, a01, a02, a03;
  var a10, a11, a12, a13;
  var a20, a21, a22, a23;
  if (a === out) {
    out[12] = a[0] * x + a[4] * y + a[8] * z + a[12];
    out[13] = a[1] * x + a[5] * y + a[9] * z + a[13];
    out[14] = a[2] * x + a[6] * y + a[10] * z + a[14];
    out[15] = a[3] * x + a[7] * y + a[11] * z + a[15];
  } else {
    a00 = a[0];
    a01 = a[1];
    a02 = a[2];
    a03 = a[3];
    a10 = a[4];
    a11 = a[5];
    a12 = a[6];
    a13 = a[7];
    a20 = a[8];
    a21 = a[9];
    a22 = a[10];
    a23 = a[11];
    out[0] = a00;
    out[1] = a01;
    out[2] = a02;
    out[3] = a03;
    out[4] = a10;
    out[5] = a11;
    out[6] = a12;
    out[7] = a13;
    out[8] = a20;
    out[9] = a21;
    out[10] = a22;
    out[11] = a23;
    out[12] = a00 * x + a10 * y + a20 * z + a[12];
    out[13] = a01 * x + a11 * y + a21 * z + a[13];
    out[14] = a02 * x + a12 * y + a22 * z + a[14];
    out[15] = a03 * x + a13 * y + a23 * z + a[15];
  }
  return out;
}
function scale2(out, a, v) {
  var x = v[0], y = v[1], z = v[2];
  out[0] = a[0] * x;
  out[1] = a[1] * x;
  out[2] = a[2] * x;
  out[3] = a[3] * x;
  out[4] = a[4] * y;
  out[5] = a[5] * y;
  out[6] = a[6] * y;
  out[7] = a[7] * y;
  out[8] = a[8] * z;
  out[9] = a[9] * z;
  out[10] = a[10] * z;
  out[11] = a[11] * z;
  out[12] = a[12];
  out[13] = a[13];
  out[14] = a[14];
  out[15] = a[15];
  return out;
}
function rotate2(out, a, rad, axis) {
  var x = axis[0], y = axis[1], z = axis[2];
  var len4 = Math.hypot(x, y, z);
  var s, c, t;
  var a00, a01, a02, a03;
  var a10, a11, a12, a13;
  var a20, a21, a22, a23;
  var b00, b01, b02;
  var b10, b11, b12;
  var b20, b21, b22;
  if (len4 < EPSILON) {
    return null;
  }
  len4 = 1 / len4;
  x *= len4;
  y *= len4;
  z *= len4;
  s = Math.sin(rad);
  c = Math.cos(rad);
  t = 1 - c;
  a00 = a[0];
  a01 = a[1];
  a02 = a[2];
  a03 = a[3];
  a10 = a[4];
  a11 = a[5];
  a12 = a[6];
  a13 = a[7];
  a20 = a[8];
  a21 = a[9];
  a22 = a[10];
  a23 = a[11];
  b00 = x * x * t + c;
  b01 = y * x * t + z * s;
  b02 = z * x * t - y * s;
  b10 = x * y * t - z * s;
  b11 = y * y * t + c;
  b12 = z * y * t + x * s;
  b20 = x * z * t + y * s;
  b21 = y * z * t - x * s;
  b22 = z * z * t + c;
  out[0] = a00 * b00 + a10 * b01 + a20 * b02;
  out[1] = a01 * b00 + a11 * b01 + a21 * b02;
  out[2] = a02 * b00 + a12 * b01 + a22 * b02;
  out[3] = a03 * b00 + a13 * b01 + a23 * b02;
  out[4] = a00 * b10 + a10 * b11 + a20 * b12;
  out[5] = a01 * b10 + a11 * b11 + a21 * b12;
  out[6] = a02 * b10 + a12 * b11 + a22 * b12;
  out[7] = a03 * b10 + a13 * b11 + a23 * b12;
  out[8] = a00 * b20 + a10 * b21 + a20 * b22;
  out[9] = a01 * b20 + a11 * b21 + a21 * b22;
  out[10] = a02 * b20 + a12 * b21 + a22 * b22;
  out[11] = a03 * b20 + a13 * b21 + a23 * b22;
  if (a !== out) {
    out[12] = a[12];
    out[13] = a[13];
    out[14] = a[14];
    out[15] = a[15];
  }
  return out;
}
function rotateX(out, a, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  var a10 = a[4];
  var a11 = a[5];
  var a12 = a[6];
  var a13 = a[7];
  var a20 = a[8];
  var a21 = a[9];
  var a22 = a[10];
  var a23 = a[11];
  if (a !== out) {
    out[0] = a[0];
    out[1] = a[1];
    out[2] = a[2];
    out[3] = a[3];
    out[12] = a[12];
    out[13] = a[13];
    out[14] = a[14];
    out[15] = a[15];
  }
  out[4] = a10 * c + a20 * s;
  out[5] = a11 * c + a21 * s;
  out[6] = a12 * c + a22 * s;
  out[7] = a13 * c + a23 * s;
  out[8] = a20 * c - a10 * s;
  out[9] = a21 * c - a11 * s;
  out[10] = a22 * c - a12 * s;
  out[11] = a23 * c - a13 * s;
  return out;
}
function rotateY(out, a, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  var a00 = a[0];
  var a01 = a[1];
  var a02 = a[2];
  var a03 = a[3];
  var a20 = a[8];
  var a21 = a[9];
  var a22 = a[10];
  var a23 = a[11];
  if (a !== out) {
    out[4] = a[4];
    out[5] = a[5];
    out[6] = a[6];
    out[7] = a[7];
    out[12] = a[12];
    out[13] = a[13];
    out[14] = a[14];
    out[15] = a[15];
  }
  out[0] = a00 * c - a20 * s;
  out[1] = a01 * c - a21 * s;
  out[2] = a02 * c - a22 * s;
  out[3] = a03 * c - a23 * s;
  out[8] = a00 * s + a20 * c;
  out[9] = a01 * s + a21 * c;
  out[10] = a02 * s + a22 * c;
  out[11] = a03 * s + a23 * c;
  return out;
}
function rotateZ(out, a, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  var a00 = a[0];
  var a01 = a[1];
  var a02 = a[2];
  var a03 = a[3];
  var a10 = a[4];
  var a11 = a[5];
  var a12 = a[6];
  var a13 = a[7];
  if (a !== out) {
    out[8] = a[8];
    out[9] = a[9];
    out[10] = a[10];
    out[11] = a[11];
    out[12] = a[12];
    out[13] = a[13];
    out[14] = a[14];
    out[15] = a[15];
  }
  out[0] = a00 * c + a10 * s;
  out[1] = a01 * c + a11 * s;
  out[2] = a02 * c + a12 * s;
  out[3] = a03 * c + a13 * s;
  out[4] = a10 * c - a00 * s;
  out[5] = a11 * c - a01 * s;
  out[6] = a12 * c - a02 * s;
  out[7] = a13 * c - a03 * s;
  return out;
}
function fromTranslation2(out, v) {
  out[0] = 1;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = 1;
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[10] = 1;
  out[11] = 0;
  out[12] = v[0];
  out[13] = v[1];
  out[14] = v[2];
  out[15] = 1;
  return out;
}
function fromScaling2(out, v) {
  out[0] = v[0];
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = v[1];
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[10] = v[2];
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function fromRotation2(out, rad, axis) {
  var x = axis[0], y = axis[1], z = axis[2];
  var len4 = Math.hypot(x, y, z);
  var s, c, t;
  if (len4 < EPSILON) {
    return null;
  }
  len4 = 1 / len4;
  x *= len4;
  y *= len4;
  z *= len4;
  s = Math.sin(rad);
  c = Math.cos(rad);
  t = 1 - c;
  out[0] = x * x * t + c;
  out[1] = y * x * t + z * s;
  out[2] = z * x * t - y * s;
  out[3] = 0;
  out[4] = x * y * t - z * s;
  out[5] = y * y * t + c;
  out[6] = z * y * t + x * s;
  out[7] = 0;
  out[8] = x * z * t + y * s;
  out[9] = y * z * t - x * s;
  out[10] = z * z * t + c;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function fromXRotation(out, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  out[0] = 1;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = c;
  out[6] = s;
  out[7] = 0;
  out[8] = 0;
  out[9] = -s;
  out[10] = c;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function fromYRotation(out, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  out[0] = c;
  out[1] = 0;
  out[2] = -s;
  out[3] = 0;
  out[4] = 0;
  out[5] = 1;
  out[6] = 0;
  out[7] = 0;
  out[8] = s;
  out[9] = 0;
  out[10] = c;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function fromZRotation(out, rad) {
  var s = Math.sin(rad);
  var c = Math.cos(rad);
  out[0] = c;
  out[1] = s;
  out[2] = 0;
  out[3] = 0;
  out[4] = -s;
  out[5] = c;
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[10] = 1;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function fromRotationTranslation(out, q, v) {
  var x = q[0], y = q[1], z = q[2], w = q[3];
  var x2 = x + x;
  var y2 = y + y;
  var z2 = z + z;
  var xx = x * x2;
  var xy = x * y2;
  var xz = x * z2;
  var yy = y * y2;
  var yz = y * z2;
  var zz = z * z2;
  var wx = w * x2;
  var wy = w * y2;
  var wz = w * z2;
  out[0] = 1 - (yy + zz);
  out[1] = xy + wz;
  out[2] = xz - wy;
  out[3] = 0;
  out[4] = xy - wz;
  out[5] = 1 - (xx + zz);
  out[6] = yz + wx;
  out[7] = 0;
  out[8] = xz + wy;
  out[9] = yz - wx;
  out[10] = 1 - (xx + yy);
  out[11] = 0;
  out[12] = v[0];
  out[13] = v[1];
  out[14] = v[2];
  out[15] = 1;
  return out;
}
function fromQuat2(out, a) {
  var translation = new ARRAY_TYPE(3);
  var bx = -a[0], by = -a[1], bz = -a[2], bw = a[3], ax = a[4], ay = a[5], az = a[6], aw = a[7];
  var magnitude = bx * bx + by * by + bz * bz + bw * bw;
  if (magnitude > 0) {
    translation[0] = (ax * bw + aw * bx + ay * bz - az * by) * 2 / magnitude;
    translation[1] = (ay * bw + aw * by + az * bx - ax * bz) * 2 / magnitude;
    translation[2] = (az * bw + aw * bz + ax * by - ay * bx) * 2 / magnitude;
  } else {
    translation[0] = (ax * bw + aw * bx + ay * bz - az * by) * 2;
    translation[1] = (ay * bw + aw * by + az * bx - ax * bz) * 2;
    translation[2] = (az * bw + aw * bz + ax * by - ay * bx) * 2;
  }
  fromRotationTranslation(out, a, translation);
  return out;
}
function getTranslation(out, mat) {
  out[0] = mat[12];
  out[1] = mat[13];
  out[2] = mat[14];
  return out;
}
function getScaling(out, mat) {
  var m11 = mat[0];
  var m12 = mat[1];
  var m13 = mat[2];
  var m21 = mat[4];
  var m22 = mat[5];
  var m23 = mat[6];
  var m31 = mat[8];
  var m32 = mat[9];
  var m33 = mat[10];
  out[0] = Math.hypot(m11, m12, m13);
  out[1] = Math.hypot(m21, m22, m23);
  out[2] = Math.hypot(m31, m32, m33);
  return out;
}
function getRotation(out, mat) {
  var scaling = new ARRAY_TYPE(3);
  getScaling(scaling, mat);
  var is1 = 1 / scaling[0];
  var is2 = 1 / scaling[1];
  var is3 = 1 / scaling[2];
  var sm11 = mat[0] * is1;
  var sm12 = mat[1] * is2;
  var sm13 = mat[2] * is3;
  var sm21 = mat[4] * is1;
  var sm22 = mat[5] * is2;
  var sm23 = mat[6] * is3;
  var sm31 = mat[8] * is1;
  var sm32 = mat[9] * is2;
  var sm33 = mat[10] * is3;
  var trace = sm11 + sm22 + sm33;
  var S = 0;
  if (trace > 0) {
    S = Math.sqrt(trace + 1) * 2;
    out[3] = 0.25 * S;
    out[0] = (sm23 - sm32) / S;
    out[1] = (sm31 - sm13) / S;
    out[2] = (sm12 - sm21) / S;
  } else if (sm11 > sm22 && sm11 > sm33) {
    S = Math.sqrt(1 + sm11 - sm22 - sm33) * 2;
    out[3] = (sm23 - sm32) / S;
    out[0] = 0.25 * S;
    out[1] = (sm12 + sm21) / S;
    out[2] = (sm31 + sm13) / S;
  } else if (sm22 > sm33) {
    S = Math.sqrt(1 + sm22 - sm11 - sm33) * 2;
    out[3] = (sm31 - sm13) / S;
    out[0] = (sm12 + sm21) / S;
    out[1] = 0.25 * S;
    out[2] = (sm23 + sm32) / S;
  } else {
    S = Math.sqrt(1 + sm33 - sm11 - sm22) * 2;
    out[3] = (sm12 - sm21) / S;
    out[0] = (sm31 + sm13) / S;
    out[1] = (sm23 + sm32) / S;
    out[2] = 0.25 * S;
  }
  return out;
}
function fromRotationTranslationScale(out, q, v, s) {
  var x = q[0], y = q[1], z = q[2], w = q[3];
  var x2 = x + x;
  var y2 = y + y;
  var z2 = z + z;
  var xx = x * x2;
  var xy = x * y2;
  var xz = x * z2;
  var yy = y * y2;
  var yz = y * z2;
  var zz = z * z2;
  var wx = w * x2;
  var wy = w * y2;
  var wz = w * z2;
  var sx = s[0];
  var sy = s[1];
  var sz = s[2];
  out[0] = (1 - (yy + zz)) * sx;
  out[1] = (xy + wz) * sx;
  out[2] = (xz - wy) * sx;
  out[3] = 0;
  out[4] = (xy - wz) * sy;
  out[5] = (1 - (xx + zz)) * sy;
  out[6] = (yz + wx) * sy;
  out[7] = 0;
  out[8] = (xz + wy) * sz;
  out[9] = (yz - wx) * sz;
  out[10] = (1 - (xx + yy)) * sz;
  out[11] = 0;
  out[12] = v[0];
  out[13] = v[1];
  out[14] = v[2];
  out[15] = 1;
  return out;
}
function fromRotationTranslationScaleOrigin(out, q, v, s, o) {
  var x = q[0], y = q[1], z = q[2], w = q[3];
  var x2 = x + x;
  var y2 = y + y;
  var z2 = z + z;
  var xx = x * x2;
  var xy = x * y2;
  var xz = x * z2;
  var yy = y * y2;
  var yz = y * z2;
  var zz = z * z2;
  var wx = w * x2;
  var wy = w * y2;
  var wz = w * z2;
  var sx = s[0];
  var sy = s[1];
  var sz = s[2];
  var ox = o[0];
  var oy = o[1];
  var oz = o[2];
  var out0 = (1 - (yy + zz)) * sx;
  var out1 = (xy + wz) * sx;
  var out2 = (xz - wy) * sx;
  var out4 = (xy - wz) * sy;
  var out5 = (1 - (xx + zz)) * sy;
  var out6 = (yz + wx) * sy;
  var out8 = (xz + wy) * sz;
  var out9 = (yz - wx) * sz;
  var out10 = (1 - (xx + yy)) * sz;
  out[0] = out0;
  out[1] = out1;
  out[2] = out2;
  out[3] = 0;
  out[4] = out4;
  out[5] = out5;
  out[6] = out6;
  out[7] = 0;
  out[8] = out8;
  out[9] = out9;
  out[10] = out10;
  out[11] = 0;
  out[12] = v[0] + ox - (out0 * ox + out4 * oy + out8 * oz);
  out[13] = v[1] + oy - (out1 * ox + out5 * oy + out9 * oz);
  out[14] = v[2] + oz - (out2 * ox + out6 * oy + out10 * oz);
  out[15] = 1;
  return out;
}
function fromQuat3(out, q) {
  var x = q[0], y = q[1], z = q[2], w = q[3];
  var x2 = x + x;
  var y2 = y + y;
  var z2 = z + z;
  var xx = x * x2;
  var yx = y * x2;
  var yy = y * y2;
  var zx = z * x2;
  var zy = z * y2;
  var zz = z * z2;
  var wx = w * x2;
  var wy = w * y2;
  var wz = w * z2;
  out[0] = 1 - yy - zz;
  out[1] = yx + wz;
  out[2] = zx - wy;
  out[3] = 0;
  out[4] = yx - wz;
  out[5] = 1 - xx - zz;
  out[6] = zy + wx;
  out[7] = 0;
  out[8] = zx + wy;
  out[9] = zy - wx;
  out[10] = 1 - xx - yy;
  out[11] = 0;
  out[12] = 0;
  out[13] = 0;
  out[14] = 0;
  out[15] = 1;
  return out;
}
function frustum(out, left, right, bottom, top, near, far) {
  var rl = 1 / (right - left);
  var tb = 1 / (top - bottom);
  var nf = 1 / (near - far);
  out[0] = near * 2 * rl;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = near * 2 * tb;
  out[6] = 0;
  out[7] = 0;
  out[8] = (right + left) * rl;
  out[9] = (top + bottom) * tb;
  out[10] = (far + near) * nf;
  out[11] = -1;
  out[12] = 0;
  out[13] = 0;
  out[14] = far * near * 2 * nf;
  out[15] = 0;
  return out;
}
function perspective(out, fovy, aspect, near, far) {
  var f = 1 / Math.tan(fovy / 2), nf;
  out[0] = f / aspect;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = f;
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[11] = -1;
  out[12] = 0;
  out[13] = 0;
  out[15] = 0;
  if (far != null && far !== Infinity) {
    nf = 1 / (near - far);
    out[10] = (far + near) * nf;
    out[14] = 2 * far * near * nf;
  } else {
    out[10] = -1;
    out[14] = -2 * near;
  }
  return out;
}
function perspectiveFromFieldOfView(out, fov, near, far) {
  var upTan = Math.tan(fov.upDegrees * Math.PI / 180);
  var downTan = Math.tan(fov.downDegrees * Math.PI / 180);
  var leftTan = Math.tan(fov.leftDegrees * Math.PI / 180);
  var rightTan = Math.tan(fov.rightDegrees * Math.PI / 180);
  var xScale = 2 / (leftTan + rightTan);
  var yScale = 2 / (upTan + downTan);
  out[0] = xScale;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = yScale;
  out[6] = 0;
  out[7] = 0;
  out[8] = -((leftTan - rightTan) * xScale * 0.5);
  out[9] = (upTan - downTan) * yScale * 0.5;
  out[10] = far / (near - far);
  out[11] = -1;
  out[12] = 0;
  out[13] = 0;
  out[14] = far * near / (near - far);
  out[15] = 0;
  return out;
}
function ortho(out, left, right, bottom, top, near, far) {
  var lr = 1 / (left - right);
  var bt = 1 / (bottom - top);
  var nf = 1 / (near - far);
  out[0] = -2 * lr;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  out[4] = 0;
  out[5] = -2 * bt;
  out[6] = 0;
  out[7] = 0;
  out[8] = 0;
  out[9] = 0;
  out[10] = 2 * nf;
  out[11] = 0;
  out[12] = (left + right) * lr;
  out[13] = (top + bottom) * bt;
  out[14] = (far + near) * nf;
  out[15] = 1;
  return out;
}
function lookAt(out, eye, center, up) {
  var x0, x1, x2, y0, y1, y2, z0, z1, z2, len4;
  var eyex = eye[0];
  var eyey = eye[1];
  var eyez = eye[2];
  var upx = up[0];
  var upy = up[1];
  var upz = up[2];
  var centerx = center[0];
  var centery = center[1];
  var centerz = center[2];
  if (Math.abs(eyex - centerx) < EPSILON && Math.abs(eyey - centery) < EPSILON && Math.abs(eyez - centerz) < EPSILON) {
    return identity2(out);
  }
  z0 = eyex - centerx;
  z1 = eyey - centery;
  z2 = eyez - centerz;
  len4 = 1 / Math.hypot(z0, z1, z2);
  z0 *= len4;
  z1 *= len4;
  z2 *= len4;
  x0 = upy * z2 - upz * z1;
  x1 = upz * z0 - upx * z2;
  x2 = upx * z1 - upy * z0;
  len4 = Math.hypot(x0, x1, x2);
  if (!len4) {
    x0 = 0;
    x1 = 0;
    x2 = 0;
  } else {
    len4 = 1 / len4;
    x0 *= len4;
    x1 *= len4;
    x2 *= len4;
  }
  y0 = z1 * x2 - z2 * x1;
  y1 = z2 * x0 - z0 * x2;
  y2 = z0 * x1 - z1 * x0;
  len4 = Math.hypot(y0, y1, y2);
  if (!len4) {
    y0 = 0;
    y1 = 0;
    y2 = 0;
  } else {
    len4 = 1 / len4;
    y0 *= len4;
    y1 *= len4;
    y2 *= len4;
  }
  out[0] = x0;
  out[1] = y0;
  out[2] = z0;
  out[3] = 0;
  out[4] = x1;
  out[5] = y1;
  out[6] = z1;
  out[7] = 0;
  out[8] = x2;
  out[9] = y2;
  out[10] = z2;
  out[11] = 0;
  out[12] = -(x0 * eyex + x1 * eyey + x2 * eyez);
  out[13] = -(y0 * eyex + y1 * eyey + y2 * eyez);
  out[14] = -(z0 * eyex + z1 * eyey + z2 * eyez);
  out[15] = 1;
  return out;
}
function targetTo(out, eye, target2, up) {
  var eyex = eye[0], eyey = eye[1], eyez = eye[2], upx = up[0], upy = up[1], upz = up[2];
  var z0 = eyex - target2[0], z1 = eyey - target2[1], z2 = eyez - target2[2];
  var len4 = z0 * z0 + z1 * z1 + z2 * z2;
  if (len4 > 0) {
    len4 = 1 / Math.sqrt(len4);
    z0 *= len4;
    z1 *= len4;
    z2 *= len4;
  }
  var x0 = upy * z2 - upz * z1, x1 = upz * z0 - upx * z2, x2 = upx * z1 - upy * z0;
  len4 = x0 * x0 + x1 * x1 + x2 * x2;
  if (len4 > 0) {
    len4 = 1 / Math.sqrt(len4);
    x0 *= len4;
    x1 *= len4;
    x2 *= len4;
  }
  out[0] = x0;
  out[1] = x1;
  out[2] = x2;
  out[3] = 0;
  out[4] = z1 * x2 - z2 * x1;
  out[5] = z2 * x0 - z0 * x2;
  out[6] = z0 * x1 - z1 * x0;
  out[7] = 0;
  out[8] = z0;
  out[9] = z1;
  out[10] = z2;
  out[11] = 0;
  out[12] = eyex;
  out[13] = eyey;
  out[14] = eyez;
  out[15] = 1;
  return out;
}
function str2(a) {
  return "mat4(" + a[0] + ", " + a[1] + ", " + a[2] + ", " + a[3] + ", " + a[4] + ", " + a[5] + ", " + a[6] + ", " + a[7] + ", " + a[8] + ", " + a[9] + ", " + a[10] + ", " + a[11] + ", " + a[12] + ", " + a[13] + ", " + a[14] + ", " + a[15] + ")";
}
function frob2(a) {
  return Math.hypot(a[0], a[1], a[3], a[4], a[5], a[6], a[7], a[8], a[9], a[10], a[11], a[12], a[13], a[14], a[15]);
}
function add2(out, a, b) {
  out[0] = a[0] + b[0];
  out[1] = a[1] + b[1];
  out[2] = a[2] + b[2];
  out[3] = a[3] + b[3];
  out[4] = a[4] + b[4];
  out[5] = a[5] + b[5];
  out[6] = a[6] + b[6];
  out[7] = a[7] + b[7];
  out[8] = a[8] + b[8];
  out[9] = a[9] + b[9];
  out[10] = a[10] + b[10];
  out[11] = a[11] + b[11];
  out[12] = a[12] + b[12];
  out[13] = a[13] + b[13];
  out[14] = a[14] + b[14];
  out[15] = a[15] + b[15];
  return out;
}
function subtract2(out, a, b) {
  out[0] = a[0] - b[0];
  out[1] = a[1] - b[1];
  out[2] = a[2] - b[2];
  out[3] = a[3] - b[3];
  out[4] = a[4] - b[4];
  out[5] = a[5] - b[5];
  out[6] = a[6] - b[6];
  out[7] = a[7] - b[7];
  out[8] = a[8] - b[8];
  out[9] = a[9] - b[9];
  out[10] = a[10] - b[10];
  out[11] = a[11] - b[11];
  out[12] = a[12] - b[12];
  out[13] = a[13] - b[13];
  out[14] = a[14] - b[14];
  out[15] = a[15] - b[15];
  return out;
}
function multiplyScalar2(out, a, b) {
  out[0] = a[0] * b;
  out[1] = a[1] * b;
  out[2] = a[2] * b;
  out[3] = a[3] * b;
  out[4] = a[4] * b;
  out[5] = a[5] * b;
  out[6] = a[6] * b;
  out[7] = a[7] * b;
  out[8] = a[8] * b;
  out[9] = a[9] * b;
  out[10] = a[10] * b;
  out[11] = a[11] * b;
  out[12] = a[12] * b;
  out[13] = a[13] * b;
  out[14] = a[14] * b;
  out[15] = a[15] * b;
  return out;
}
function multiplyScalarAndAdd2(out, a, b, scale6) {
  out[0] = a[0] + b[0] * scale6;
  out[1] = a[1] + b[1] * scale6;
  out[2] = a[2] + b[2] * scale6;
  out[3] = a[3] + b[3] * scale6;
  out[4] = a[4] + b[4] * scale6;
  out[5] = a[5] + b[5] * scale6;
  out[6] = a[6] + b[6] * scale6;
  out[7] = a[7] + b[7] * scale6;
  out[8] = a[8] + b[8] * scale6;
  out[9] = a[9] + b[9] * scale6;
  out[10] = a[10] + b[10] * scale6;
  out[11] = a[11] + b[11] * scale6;
  out[12] = a[12] + b[12] * scale6;
  out[13] = a[13] + b[13] * scale6;
  out[14] = a[14] + b[14] * scale6;
  out[15] = a[15] + b[15] * scale6;
  return out;
}
function exactEquals2(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3] && a[4] === b[4] && a[5] === b[5] && a[6] === b[6] && a[7] === b[7] && a[8] === b[8] && a[9] === b[9] && a[10] === b[10] && a[11] === b[11] && a[12] === b[12] && a[13] === b[13] && a[14] === b[14] && a[15] === b[15];
}
function equals2(a, b) {
  var a0 = a[0], a1 = a[1], a2 = a[2], a3 = a[3];
  var a4 = a[4], a5 = a[5], a6 = a[6], a7 = a[7];
  var a8 = a[8], a9 = a[9], a10 = a[10], a11 = a[11];
  var a12 = a[12], a13 = a[13], a14 = a[14], a15 = a[15];
  var b0 = b[0], b1 = b[1], b2 = b[2], b3 = b[3];
  var b4 = b[4], b5 = b[5], b6 = b[6], b7 = b[7];
  var b8 = b[8], b9 = b[9], b10 = b[10], b11 = b[11];
  var b12 = b[12], b13 = b[13], b14 = b[14], b15 = b[15];
  return Math.abs(a0 - b0) <= EPSILON * Math.max(1, Math.abs(a0), Math.abs(b0)) && Math.abs(a1 - b1) <= EPSILON * Math.max(1, Math.abs(a1), Math.abs(b1)) && Math.abs(a2 - b2) <= EPSILON * Math.max(1, Math.abs(a2), Math.abs(b2)) && Math.abs(a3 - b3) <= EPSILON * Math.max(1, Math.abs(a3), Math.abs(b3)) && Math.abs(a4 - b4) <= EPSILON * Math.max(1, Math.abs(a4), Math.abs(b4)) && Math.abs(a5 - b5) <= EPSILON * Math.max(1, Math.abs(a5), Math.abs(b5)) && Math.abs(a6 - b6) <= EPSILON * Math.max(1, Math.abs(a6), Math.abs(b6)) && Math.abs(a7 - b7) <= EPSILON * Math.max(1, Math.abs(a7), Math.abs(b7)) && Math.abs(a8 - b8) <= EPSILON * Math.max(1, Math.abs(a8), Math.abs(b8)) && Math.abs(a9 - b9) <= EPSILON * Math.max(1, Math.abs(a9), Math.abs(b9)) && Math.abs(a10 - b10) <= EPSILON * Math.max(1, Math.abs(a10), Math.abs(b10)) && Math.abs(a11 - b11) <= EPSILON * Math.max(1, Math.abs(a11), Math.abs(b11)) && Math.abs(a12 - b12) <= EPSILON * Math.max(1, Math.abs(a12), Math.abs(b12)) && Math.abs(a13 - b13) <= EPSILON * Math.max(1, Math.abs(a13), Math.abs(b13)) && Math.abs(a14 - b14) <= EPSILON * Math.max(1, Math.abs(a14), Math.abs(b14)) && Math.abs(a15 - b15) <= EPSILON * Math.max(1, Math.abs(a15), Math.abs(b15));
}
var mul2 = multiply2;
var sub2 = subtract2;

// node_modules/gl-matrix/esm/quat.js
var quat_exports = {};
__export(quat_exports, {
  add: () => add5,
  calculateW: () => calculateW,
  clone: () => clone6,
  conjugate: () => conjugate,
  copy: () => copy5,
  create: () => create5,
  dot: () => dot3,
  equals: () => equals5,
  exactEquals: () => exactEquals5,
  exp: () => exp,
  fromEuler: () => fromEuler,
  fromMat3: () => fromMat3,
  fromValues: () => fromValues5,
  getAngle: () => getAngle,
  getAxisAngle: () => getAxisAngle,
  identity: () => identity3,
  invert: () => invert3,
  len: () => len3,
  length: () => length4,
  lerp: () => lerp3,
  ln: () => ln,
  mul: () => mul5,
  multiply: () => multiply5,
  normalize: () => normalize3,
  pow: () => pow,
  random: () => random3,
  rotateX: () => rotateX3,
  rotateY: () => rotateY3,
  rotateZ: () => rotateZ3,
  rotationTo: () => rotationTo,
  scale: () => scale5,
  set: () => set5,
  setAxes: () => setAxes,
  setAxisAngle: () => setAxisAngle,
  slerp: () => slerp,
  sqlerp: () => sqlerp,
  sqrLen: () => sqrLen3,
  squaredLength: () => squaredLength3,
  str: () => str5
});
init_legacy_browser();

// node_modules/gl-matrix/esm/vec3.js
var vec3_exports = {};
__export(vec3_exports, {
  add: () => add3,
  angle: () => angle,
  bezier: () => bezier,
  ceil: () => ceil,
  clone: () => clone4,
  copy: () => copy3,
  create: () => create3,
  cross: () => cross,
  dist: () => dist,
  distance: () => distance,
  div: () => div,
  divide: () => divide,
  dot: () => dot,
  equals: () => equals3,
  exactEquals: () => exactEquals3,
  floor: () => floor,
  forEach: () => forEach,
  fromValues: () => fromValues3,
  hermite: () => hermite,
  inverse: () => inverse,
  len: () => len,
  length: () => length2,
  lerp: () => lerp,
  max: () => max,
  min: () => min,
  mul: () => mul3,
  multiply: () => multiply3,
  negate: () => negate,
  normalize: () => normalize,
  random: () => random,
  rotateX: () => rotateX2,
  rotateY: () => rotateY2,
  rotateZ: () => rotateZ2,
  round: () => round,
  scale: () => scale3,
  scaleAndAdd: () => scaleAndAdd,
  set: () => set3,
  sqrDist: () => sqrDist,
  sqrLen: () => sqrLen,
  squaredDistance: () => squaredDistance,
  squaredLength: () => squaredLength,
  str: () => str3,
  sub: () => sub3,
  subtract: () => subtract3,
  transformMat3: () => transformMat3,
  transformMat4: () => transformMat4,
  transformQuat: () => transformQuat,
  zero: () => zero
});
init_legacy_browser();
function create3() {
  var out = new ARRAY_TYPE(3);
  if (ARRAY_TYPE != Float32Array) {
    out[0] = 0;
    out[1] = 0;
    out[2] = 0;
  }
  return out;
}
function clone4(a) {
  var out = new ARRAY_TYPE(3);
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  return out;
}
function length2(a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  return Math.hypot(x, y, z);
}
function fromValues3(x, y, z) {
  var out = new ARRAY_TYPE(3);
  out[0] = x;
  out[1] = y;
  out[2] = z;
  return out;
}
function copy3(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  return out;
}
function set3(out, x, y, z) {
  out[0] = x;
  out[1] = y;
  out[2] = z;
  return out;
}
function add3(out, a, b) {
  out[0] = a[0] + b[0];
  out[1] = a[1] + b[1];
  out[2] = a[2] + b[2];
  return out;
}
function subtract3(out, a, b) {
  out[0] = a[0] - b[0];
  out[1] = a[1] - b[1];
  out[2] = a[2] - b[2];
  return out;
}
function multiply3(out, a, b) {
  out[0] = a[0] * b[0];
  out[1] = a[1] * b[1];
  out[2] = a[2] * b[2];
  return out;
}
function divide(out, a, b) {
  out[0] = a[0] / b[0];
  out[1] = a[1] / b[1];
  out[2] = a[2] / b[2];
  return out;
}
function ceil(out, a) {
  out[0] = Math.ceil(a[0]);
  out[1] = Math.ceil(a[1]);
  out[2] = Math.ceil(a[2]);
  return out;
}
function floor(out, a) {
  out[0] = Math.floor(a[0]);
  out[1] = Math.floor(a[1]);
  out[2] = Math.floor(a[2]);
  return out;
}
function min(out, a, b) {
  out[0] = Math.min(a[0], b[0]);
  out[1] = Math.min(a[1], b[1]);
  out[2] = Math.min(a[2], b[2]);
  return out;
}
function max(out, a, b) {
  out[0] = Math.max(a[0], b[0]);
  out[1] = Math.max(a[1], b[1]);
  out[2] = Math.max(a[2], b[2]);
  return out;
}
function round(out, a) {
  out[0] = Math.round(a[0]);
  out[1] = Math.round(a[1]);
  out[2] = Math.round(a[2]);
  return out;
}
function scale3(out, a, b) {
  out[0] = a[0] * b;
  out[1] = a[1] * b;
  out[2] = a[2] * b;
  return out;
}
function scaleAndAdd(out, a, b, scale6) {
  out[0] = a[0] + b[0] * scale6;
  out[1] = a[1] + b[1] * scale6;
  out[2] = a[2] + b[2] * scale6;
  return out;
}
function distance(a, b) {
  var x = b[0] - a[0];
  var y = b[1] - a[1];
  var z = b[2] - a[2];
  return Math.hypot(x, y, z);
}
function squaredDistance(a, b) {
  var x = b[0] - a[0];
  var y = b[1] - a[1];
  var z = b[2] - a[2];
  return x * x + y * y + z * z;
}
function squaredLength(a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  return x * x + y * y + z * z;
}
function negate(out, a) {
  out[0] = -a[0];
  out[1] = -a[1];
  out[2] = -a[2];
  return out;
}
function inverse(out, a) {
  out[0] = 1 / a[0];
  out[1] = 1 / a[1];
  out[2] = 1 / a[2];
  return out;
}
function normalize(out, a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  var len4 = x * x + y * y + z * z;
  if (len4 > 0) {
    len4 = 1 / Math.sqrt(len4);
  }
  out[0] = a[0] * len4;
  out[1] = a[1] * len4;
  out[2] = a[2] * len4;
  return out;
}
function dot(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}
function cross(out, a, b) {
  var ax = a[0], ay = a[1], az = a[2];
  var bx = b[0], by = b[1], bz = b[2];
  out[0] = ay * bz - az * by;
  out[1] = az * bx - ax * bz;
  out[2] = ax * by - ay * bx;
  return out;
}
function lerp(out, a, b, t) {
  var ax = a[0];
  var ay = a[1];
  var az = a[2];
  out[0] = ax + t * (b[0] - ax);
  out[1] = ay + t * (b[1] - ay);
  out[2] = az + t * (b[2] - az);
  return out;
}
function hermite(out, a, b, c, d, t) {
  var factorTimes2 = t * t;
  var factor1 = factorTimes2 * (2 * t - 3) + 1;
  var factor2 = factorTimes2 * (t - 2) + t;
  var factor3 = factorTimes2 * (t - 1);
  var factor4 = factorTimes2 * (3 - 2 * t);
  out[0] = a[0] * factor1 + b[0] * factor2 + c[0] * factor3 + d[0] * factor4;
  out[1] = a[1] * factor1 + b[1] * factor2 + c[1] * factor3 + d[1] * factor4;
  out[2] = a[2] * factor1 + b[2] * factor2 + c[2] * factor3 + d[2] * factor4;
  return out;
}
function bezier(out, a, b, c, d, t) {
  var inverseFactor = 1 - t;
  var inverseFactorTimesTwo = inverseFactor * inverseFactor;
  var factorTimes2 = t * t;
  var factor1 = inverseFactorTimesTwo * inverseFactor;
  var factor2 = 3 * t * inverseFactorTimesTwo;
  var factor3 = 3 * factorTimes2 * inverseFactor;
  var factor4 = factorTimes2 * t;
  out[0] = a[0] * factor1 + b[0] * factor2 + c[0] * factor3 + d[0] * factor4;
  out[1] = a[1] * factor1 + b[1] * factor2 + c[1] * factor3 + d[1] * factor4;
  out[2] = a[2] * factor1 + b[2] * factor2 + c[2] * factor3 + d[2] * factor4;
  return out;
}
function random(out, scale6) {
  scale6 = scale6 || 1;
  var r = RANDOM() * 2 * Math.PI;
  var z = RANDOM() * 2 - 1;
  var zScale = Math.sqrt(1 - z * z) * scale6;
  out[0] = Math.cos(r) * zScale;
  out[1] = Math.sin(r) * zScale;
  out[2] = z * scale6;
  return out;
}
function transformMat4(out, a, m) {
  var x = a[0], y = a[1], z = a[2];
  var w = m[3] * x + m[7] * y + m[11] * z + m[15];
  w = w || 1;
  out[0] = (m[0] * x + m[4] * y + m[8] * z + m[12]) / w;
  out[1] = (m[1] * x + m[5] * y + m[9] * z + m[13]) / w;
  out[2] = (m[2] * x + m[6] * y + m[10] * z + m[14]) / w;
  return out;
}
function transformMat3(out, a, m) {
  var x = a[0], y = a[1], z = a[2];
  out[0] = x * m[0] + y * m[3] + z * m[6];
  out[1] = x * m[1] + y * m[4] + z * m[7];
  out[2] = x * m[2] + y * m[5] + z * m[8];
  return out;
}
function transformQuat(out, a, q) {
  var qx = q[0], qy = q[1], qz = q[2], qw = q[3];
  var x = a[0], y = a[1], z = a[2];
  var uvx = qy * z - qz * y, uvy = qz * x - qx * z, uvz = qx * y - qy * x;
  var uuvx = qy * uvz - qz * uvy, uuvy = qz * uvx - qx * uvz, uuvz = qx * uvy - qy * uvx;
  var w2 = qw * 2;
  uvx *= w2;
  uvy *= w2;
  uvz *= w2;
  uuvx *= 2;
  uuvy *= 2;
  uuvz *= 2;
  out[0] = x + uvx + uuvx;
  out[1] = y + uvy + uuvy;
  out[2] = z + uvz + uuvz;
  return out;
}
function rotateX2(out, a, b, c) {
  var p = [], r = [];
  p[0] = a[0] - b[0];
  p[1] = a[1] - b[1];
  p[2] = a[2] - b[2];
  r[0] = p[0];
  r[1] = p[1] * Math.cos(c) - p[2] * Math.sin(c);
  r[2] = p[1] * Math.sin(c) + p[2] * Math.cos(c);
  out[0] = r[0] + b[0];
  out[1] = r[1] + b[1];
  out[2] = r[2] + b[2];
  return out;
}
function rotateY2(out, a, b, c) {
  var p = [], r = [];
  p[0] = a[0] - b[0];
  p[1] = a[1] - b[1];
  p[2] = a[2] - b[2];
  r[0] = p[2] * Math.sin(c) + p[0] * Math.cos(c);
  r[1] = p[1];
  r[2] = p[2] * Math.cos(c) - p[0] * Math.sin(c);
  out[0] = r[0] + b[0];
  out[1] = r[1] + b[1];
  out[2] = r[2] + b[2];
  return out;
}
function rotateZ2(out, a, b, c) {
  var p = [], r = [];
  p[0] = a[0] - b[0];
  p[1] = a[1] - b[1];
  p[2] = a[2] - b[2];
  r[0] = p[0] * Math.cos(c) - p[1] * Math.sin(c);
  r[1] = p[0] * Math.sin(c) + p[1] * Math.cos(c);
  r[2] = p[2];
  out[0] = r[0] + b[0];
  out[1] = r[1] + b[1];
  out[2] = r[2] + b[2];
  return out;
}
function angle(a, b) {
  var tempA = fromValues3(a[0], a[1], a[2]);
  var tempB = fromValues3(b[0], b[1], b[2]);
  normalize(tempA, tempA);
  normalize(tempB, tempB);
  var cosine = dot(tempA, tempB);
  if (cosine > 1) {
    return 0;
  } else if (cosine < -1) {
    return Math.PI;
  } else {
    return Math.acos(cosine);
  }
}
function zero(out) {
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  return out;
}
function str3(a) {
  return "vec3(" + a[0] + ", " + a[1] + ", " + a[2] + ")";
}
function exactEquals3(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2];
}
function equals3(a, b) {
  var a0 = a[0], a1 = a[1], a2 = a[2];
  var b0 = b[0], b1 = b[1], b2 = b[2];
  return Math.abs(a0 - b0) <= EPSILON * Math.max(1, Math.abs(a0), Math.abs(b0)) && Math.abs(a1 - b1) <= EPSILON * Math.max(1, Math.abs(a1), Math.abs(b1)) && Math.abs(a2 - b2) <= EPSILON * Math.max(1, Math.abs(a2), Math.abs(b2));
}
var sub3 = subtract3;
var mul3 = multiply3;
var div = divide;
var dist = distance;
var sqrDist = squaredDistance;
var len = length2;
var sqrLen = squaredLength;
var forEach = (function() {
  var vec = create3();
  return function(a, stride, offset, count, fn, arg) {
    var i, l;
    if (!stride) {
      stride = 3;
    }
    if (!offset) {
      offset = 0;
    }
    if (count) {
      l = Math.min(count * stride + offset, a.length);
    } else {
      l = a.length;
    }
    for (i = offset; i < l; i += stride) {
      vec[0] = a[i];
      vec[1] = a[i + 1];
      vec[2] = a[i + 2];
      fn(vec, vec, arg);
      a[i] = vec[0];
      a[i + 1] = vec[1];
      a[i + 2] = vec[2];
    }
    return a;
  };
})();

// node_modules/gl-matrix/esm/vec4.js
var vec4_exports = {};
__export(vec4_exports, {
  add: () => add4,
  ceil: () => ceil2,
  clone: () => clone5,
  copy: () => copy4,
  create: () => create4,
  cross: () => cross2,
  dist: () => dist2,
  distance: () => distance2,
  div: () => div2,
  divide: () => divide2,
  dot: () => dot2,
  equals: () => equals4,
  exactEquals: () => exactEquals4,
  floor: () => floor2,
  forEach: () => forEach2,
  fromValues: () => fromValues4,
  inverse: () => inverse2,
  len: () => len2,
  length: () => length3,
  lerp: () => lerp2,
  max: () => max2,
  min: () => min2,
  mul: () => mul4,
  multiply: () => multiply4,
  negate: () => negate2,
  normalize: () => normalize2,
  random: () => random2,
  round: () => round2,
  scale: () => scale4,
  scaleAndAdd: () => scaleAndAdd2,
  set: () => set4,
  sqrDist: () => sqrDist2,
  sqrLen: () => sqrLen2,
  squaredDistance: () => squaredDistance2,
  squaredLength: () => squaredLength2,
  str: () => str4,
  sub: () => sub4,
  subtract: () => subtract4,
  transformMat4: () => transformMat42,
  transformQuat: () => transformQuat2,
  zero: () => zero2
});
init_legacy_browser();
function create4() {
  var out = new ARRAY_TYPE(4);
  if (ARRAY_TYPE != Float32Array) {
    out[0] = 0;
    out[1] = 0;
    out[2] = 0;
    out[3] = 0;
  }
  return out;
}
function clone5(a) {
  var out = new ARRAY_TYPE(4);
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  return out;
}
function fromValues4(x, y, z, w) {
  var out = new ARRAY_TYPE(4);
  out[0] = x;
  out[1] = y;
  out[2] = z;
  out[3] = w;
  return out;
}
function copy4(out, a) {
  out[0] = a[0];
  out[1] = a[1];
  out[2] = a[2];
  out[3] = a[3];
  return out;
}
function set4(out, x, y, z, w) {
  out[0] = x;
  out[1] = y;
  out[2] = z;
  out[3] = w;
  return out;
}
function add4(out, a, b) {
  out[0] = a[0] + b[0];
  out[1] = a[1] + b[1];
  out[2] = a[2] + b[2];
  out[3] = a[3] + b[3];
  return out;
}
function subtract4(out, a, b) {
  out[0] = a[0] - b[0];
  out[1] = a[1] - b[1];
  out[2] = a[2] - b[2];
  out[3] = a[3] - b[3];
  return out;
}
function multiply4(out, a, b) {
  out[0] = a[0] * b[0];
  out[1] = a[1] * b[1];
  out[2] = a[2] * b[2];
  out[3] = a[3] * b[3];
  return out;
}
function divide2(out, a, b) {
  out[0] = a[0] / b[0];
  out[1] = a[1] / b[1];
  out[2] = a[2] / b[2];
  out[3] = a[3] / b[3];
  return out;
}
function ceil2(out, a) {
  out[0] = Math.ceil(a[0]);
  out[1] = Math.ceil(a[1]);
  out[2] = Math.ceil(a[2]);
  out[3] = Math.ceil(a[3]);
  return out;
}
function floor2(out, a) {
  out[0] = Math.floor(a[0]);
  out[1] = Math.floor(a[1]);
  out[2] = Math.floor(a[2]);
  out[3] = Math.floor(a[3]);
  return out;
}
function min2(out, a, b) {
  out[0] = Math.min(a[0], b[0]);
  out[1] = Math.min(a[1], b[1]);
  out[2] = Math.min(a[2], b[2]);
  out[3] = Math.min(a[3], b[3]);
  return out;
}
function max2(out, a, b) {
  out[0] = Math.max(a[0], b[0]);
  out[1] = Math.max(a[1], b[1]);
  out[2] = Math.max(a[2], b[2]);
  out[3] = Math.max(a[3], b[3]);
  return out;
}
function round2(out, a) {
  out[0] = Math.round(a[0]);
  out[1] = Math.round(a[1]);
  out[2] = Math.round(a[2]);
  out[3] = Math.round(a[3]);
  return out;
}
function scale4(out, a, b) {
  out[0] = a[0] * b;
  out[1] = a[1] * b;
  out[2] = a[2] * b;
  out[3] = a[3] * b;
  return out;
}
function scaleAndAdd2(out, a, b, scale6) {
  out[0] = a[0] + b[0] * scale6;
  out[1] = a[1] + b[1] * scale6;
  out[2] = a[2] + b[2] * scale6;
  out[3] = a[3] + b[3] * scale6;
  return out;
}
function distance2(a, b) {
  var x = b[0] - a[0];
  var y = b[1] - a[1];
  var z = b[2] - a[2];
  var w = b[3] - a[3];
  return Math.hypot(x, y, z, w);
}
function squaredDistance2(a, b) {
  var x = b[0] - a[0];
  var y = b[1] - a[1];
  var z = b[2] - a[2];
  var w = b[3] - a[3];
  return x * x + y * y + z * z + w * w;
}
function length3(a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  var w = a[3];
  return Math.hypot(x, y, z, w);
}
function squaredLength2(a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  var w = a[3];
  return x * x + y * y + z * z + w * w;
}
function negate2(out, a) {
  out[0] = -a[0];
  out[1] = -a[1];
  out[2] = -a[2];
  out[3] = -a[3];
  return out;
}
function inverse2(out, a) {
  out[0] = 1 / a[0];
  out[1] = 1 / a[1];
  out[2] = 1 / a[2];
  out[3] = 1 / a[3];
  return out;
}
function normalize2(out, a) {
  var x = a[0];
  var y = a[1];
  var z = a[2];
  var w = a[3];
  var len4 = x * x + y * y + z * z + w * w;
  if (len4 > 0) {
    len4 = 1 / Math.sqrt(len4);
  }
  out[0] = x * len4;
  out[1] = y * len4;
  out[2] = z * len4;
  out[3] = w * len4;
  return out;
}
function dot2(a, b) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3];
}
function cross2(out, u, v, w) {
  var A = v[0] * w[1] - v[1] * w[0], B = v[0] * w[2] - v[2] * w[0], C = v[0] * w[3] - v[3] * w[0], D = v[1] * w[2] - v[2] * w[1], E = v[1] * w[3] - v[3] * w[1], F = v[2] * w[3] - v[3] * w[2];
  var G = u[0];
  var H = u[1];
  var I = u[2];
  var J = u[3];
  out[0] = H * F - I * E + J * D;
  out[1] = -(G * F) + I * C - J * B;
  out[2] = G * E - H * C + J * A;
  out[3] = -(G * D) + H * B - I * A;
  return out;
}
function lerp2(out, a, b, t) {
  var ax = a[0];
  var ay = a[1];
  var az = a[2];
  var aw = a[3];
  out[0] = ax + t * (b[0] - ax);
  out[1] = ay + t * (b[1] - ay);
  out[2] = az + t * (b[2] - az);
  out[3] = aw + t * (b[3] - aw);
  return out;
}
function random2(out, scale6) {
  scale6 = scale6 || 1;
  var v1, v2, v3, v4;
  var s1, s2;
  do {
    v1 = RANDOM() * 2 - 1;
    v2 = RANDOM() * 2 - 1;
    s1 = v1 * v1 + v2 * v2;
  } while (s1 >= 1);
  do {
    v3 = RANDOM() * 2 - 1;
    v4 = RANDOM() * 2 - 1;
    s2 = v3 * v3 + v4 * v4;
  } while (s2 >= 1);
  var d = Math.sqrt((1 - s1) / s2);
  out[0] = scale6 * v1;
  out[1] = scale6 * v2;
  out[2] = scale6 * v3 * d;
  out[3] = scale6 * v4 * d;
  return out;
}
function transformMat42(out, a, m) {
  var x = a[0], y = a[1], z = a[2], w = a[3];
  out[0] = m[0] * x + m[4] * y + m[8] * z + m[12] * w;
  out[1] = m[1] * x + m[5] * y + m[9] * z + m[13] * w;
  out[2] = m[2] * x + m[6] * y + m[10] * z + m[14] * w;
  out[3] = m[3] * x + m[7] * y + m[11] * z + m[15] * w;
  return out;
}
function transformQuat2(out, a, q) {
  var x = a[0], y = a[1], z = a[2];
  var qx = q[0], qy = q[1], qz = q[2], qw = q[3];
  var ix = qw * x + qy * z - qz * y;
  var iy = qw * y + qz * x - qx * z;
  var iz = qw * z + qx * y - qy * x;
  var iw = -qx * x - qy * y - qz * z;
  out[0] = ix * qw + iw * -qx + iy * -qz - iz * -qy;
  out[1] = iy * qw + iw * -qy + iz * -qx - ix * -qz;
  out[2] = iz * qw + iw * -qz + ix * -qy - iy * -qx;
  out[3] = a[3];
  return out;
}
function zero2(out) {
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  out[3] = 0;
  return out;
}
function str4(a) {
  return "vec4(" + a[0] + ", " + a[1] + ", " + a[2] + ", " + a[3] + ")";
}
function exactEquals4(a, b) {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}
function equals4(a, b) {
  var a0 = a[0], a1 = a[1], a2 = a[2], a3 = a[3];
  var b0 = b[0], b1 = b[1], b2 = b[2], b3 = b[3];
  return Math.abs(a0 - b0) <= EPSILON * Math.max(1, Math.abs(a0), Math.abs(b0)) && Math.abs(a1 - b1) <= EPSILON * Math.max(1, Math.abs(a1), Math.abs(b1)) && Math.abs(a2 - b2) <= EPSILON * Math.max(1, Math.abs(a2), Math.abs(b2)) && Math.abs(a3 - b3) <= EPSILON * Math.max(1, Math.abs(a3), Math.abs(b3));
}
var sub4 = subtract4;
var mul4 = multiply4;
var div2 = divide2;
var dist2 = distance2;
var sqrDist2 = squaredDistance2;
var len2 = length3;
var sqrLen2 = squaredLength2;
var forEach2 = (function() {
  var vec = create4();
  return function(a, stride, offset, count, fn, arg) {
    var i, l;
    if (!stride) {
      stride = 4;
    }
    if (!offset) {
      offset = 0;
    }
    if (count) {
      l = Math.min(count * stride + offset, a.length);
    } else {
      l = a.length;
    }
    for (i = offset; i < l; i += stride) {
      vec[0] = a[i];
      vec[1] = a[i + 1];
      vec[2] = a[i + 2];
      vec[3] = a[i + 3];
      fn(vec, vec, arg);
      a[i] = vec[0];
      a[i + 1] = vec[1];
      a[i + 2] = vec[2];
      a[i + 3] = vec[3];
    }
    return a;
  };
})();

// node_modules/gl-matrix/esm/quat.js
function create5() {
  var out = new ARRAY_TYPE(4);
  if (ARRAY_TYPE != Float32Array) {
    out[0] = 0;
    out[1] = 0;
    out[2] = 0;
  }
  out[3] = 1;
  return out;
}
function identity3(out) {
  out[0] = 0;
  out[1] = 0;
  out[2] = 0;
  out[3] = 1;
  return out;
}
function setAxisAngle(out, axis, rad) {
  rad = rad * 0.5;
  var s = Math.sin(rad);
  out[0] = s * axis[0];
  out[1] = s * axis[1];
  out[2] = s * axis[2];
  out[3] = Math.cos(rad);
  return out;
}
function getAxisAngle(out_axis, q) {
  var rad = Math.acos(q[3]) * 2;
  var s = Math.sin(rad / 2);
  if (s > EPSILON) {
    out_axis[0] = q[0] / s;
    out_axis[1] = q[1] / s;
    out_axis[2] = q[2] / s;
  } else {
    out_axis[0] = 1;
    out_axis[1] = 0;
    out_axis[2] = 0;
  }
  return rad;
}
function getAngle(a, b) {
  var dotproduct = dot3(a, b);
  return Math.acos(2 * dotproduct * dotproduct - 1);
}
function multiply5(out, a, b) {
  var ax = a[0], ay = a[1], az = a[2], aw = a[3];
  var bx = b[0], by = b[1], bz = b[2], bw = b[3];
  out[0] = ax * bw + aw * bx + ay * bz - az * by;
  out[1] = ay * bw + aw * by + az * bx - ax * bz;
  out[2] = az * bw + aw * bz + ax * by - ay * bx;
  out[3] = aw * bw - ax * bx - ay * by - az * bz;
  return out;
}
function rotateX3(out, a, rad) {
  rad *= 0.5;
  var ax = a[0], ay = a[1], az = a[2], aw = a[3];
  var bx = Math.sin(rad), bw = Math.cos(rad);
  out[0] = ax * bw + aw * bx;
  out[1] = ay * bw + az * bx;
  out[2] = az * bw - ay * bx;
  out[3] = aw * bw - ax * bx;
  return out;
}
function rotateY3(out, a, rad) {
  rad *= 0.5;
  var ax = a[0], ay = a[1], az = a[2], aw = a[3];
  var by = Math.sin(rad), bw = Math.cos(rad);
  out[0] = ax * bw - az * by;
  out[1] = ay * bw + aw * by;
  out[2] = az * bw + ax * by;
  out[3] = aw * bw - ay * by;
  return out;
}
function rotateZ3(out, a, rad) {
  rad *= 0.5;
  var ax = a[0], ay = a[1], az = a[2], aw = a[3];
  var bz = Math.sin(rad), bw = Math.cos(rad);
  out[0] = ax * bw + ay * bz;
  out[1] = ay * bw - ax * bz;
  out[2] = az * bw + aw * bz;
  out[3] = aw * bw - az * bz;
  return out;
}
function calculateW(out, a) {
  var x = a[0], y = a[1], z = a[2];
  out[0] = x;
  out[1] = y;
  out[2] = z;
  out[3] = Math.sqrt(Math.abs(1 - x * x - y * y - z * z));
  return out;
}
function exp(out, a) {
  var x = a[0], y = a[1], z = a[2], w = a[3];
  var r = Math.sqrt(x * x + y * y + z * z);
  var et = Math.exp(w);
  var s = r > 0 ? et * Math.sin(r) / r : 0;
  out[0] = x * s;
  out[1] = y * s;
  out[2] = z * s;
  out[3] = et * Math.cos(r);
  return out;
}
function ln(out, a) {
  var x = a[0], y = a[1], z = a[2], w = a[3];
  var r = Math.sqrt(x * x + y * y + z * z);
  var t = r > 0 ? Math.atan2(r, w) / r : 0;
  out[0] = x * t;
  out[1] = y * t;
  out[2] = z * t;
  out[3] = 0.5 * Math.log(x * x + y * y + z * z + w * w);
  return out;
}
function pow(out, a, b) {
  ln(out, a);
  scale5(out, out, b);
  exp(out, out);
  return out;
}
function slerp(out, a, b, t) {
  var ax = a[0], ay = a[1], az = a[2], aw = a[3];
  var bx = b[0], by = b[1], bz = b[2], bw = b[3];
  var omega, cosom, sinom, scale0, scale1;
  cosom = ax * bx + ay * by + az * bz + aw * bw;
  if (cosom < 0) {
    cosom = -cosom;
    bx = -bx;
    by = -by;
    bz = -bz;
    bw = -bw;
  }
  if (1 - cosom > EPSILON) {
    omega = Math.acos(cosom);
    sinom = Math.sin(omega);
    scale0 = Math.sin((1 - t) * omega) / sinom;
    scale1 = Math.sin(t * omega) / sinom;
  } else {
    scale0 = 1 - t;
    scale1 = t;
  }
  out[0] = scale0 * ax + scale1 * bx;
  out[1] = scale0 * ay + scale1 * by;
  out[2] = scale0 * az + scale1 * bz;
  out[3] = scale0 * aw + scale1 * bw;
  return out;
}
function random3(out) {
  var u1 = RANDOM();
  var u2 = RANDOM();
  var u3 = RANDOM();
  var sqrt1MinusU1 = Math.sqrt(1 - u1);
  var sqrtU1 = Math.sqrt(u1);
  out[0] = sqrt1MinusU1 * Math.sin(2 * Math.PI * u2);
  out[1] = sqrt1MinusU1 * Math.cos(2 * Math.PI * u2);
  out[2] = sqrtU1 * Math.sin(2 * Math.PI * u3);
  out[3] = sqrtU1 * Math.cos(2 * Math.PI * u3);
  return out;
}
function invert3(out, a) {
  var a0 = a[0], a1 = a[1], a2 = a[2], a3 = a[3];
  var dot4 = a0 * a0 + a1 * a1 + a2 * a2 + a3 * a3;
  var invDot = dot4 ? 1 / dot4 : 0;
  out[0] = -a0 * invDot;
  out[1] = -a1 * invDot;
  out[2] = -a2 * invDot;
  out[3] = a3 * invDot;
  return out;
}
function conjugate(out, a) {
  out[0] = -a[0];
  out[1] = -a[1];
  out[2] = -a[2];
  out[3] = a[3];
  return out;
}
function fromMat3(out, m) {
  var fTrace = m[0] + m[4] + m[8];
  var fRoot;
  if (fTrace > 0) {
    fRoot = Math.sqrt(fTrace + 1);
    out[3] = 0.5 * fRoot;
    fRoot = 0.5 / fRoot;
    out[0] = (m[5] - m[7]) * fRoot;
    out[1] = (m[6] - m[2]) * fRoot;
    out[2] = (m[1] - m[3]) * fRoot;
  } else {
    var i = 0;
    if (m[4] > m[0]) i = 1;
    if (m[8] > m[i * 3 + i]) i = 2;
    var j = (i + 1) % 3;
    var k = (i + 2) % 3;
    fRoot = Math.sqrt(m[i * 3 + i] - m[j * 3 + j] - m[k * 3 + k] + 1);
    out[i] = 0.5 * fRoot;
    fRoot = 0.5 / fRoot;
    out[3] = (m[j * 3 + k] - m[k * 3 + j]) * fRoot;
    out[j] = (m[j * 3 + i] + m[i * 3 + j]) * fRoot;
    out[k] = (m[k * 3 + i] + m[i * 3 + k]) * fRoot;
  }
  return out;
}
function fromEuler(out, x, y, z) {
  var halfToRad = 0.5 * Math.PI / 180;
  x *= halfToRad;
  y *= halfToRad;
  z *= halfToRad;
  var sx = Math.sin(x);
  var cx = Math.cos(x);
  var sy = Math.sin(y);
  var cy = Math.cos(y);
  var sz = Math.sin(z);
  var cz = Math.cos(z);
  out[0] = sx * cy * cz - cx * sy * sz;
  out[1] = cx * sy * cz + sx * cy * sz;
  out[2] = cx * cy * sz - sx * sy * cz;
  out[3] = cx * cy * cz + sx * sy * sz;
  return out;
}
function str5(a) {
  return "quat(" + a[0] + ", " + a[1] + ", " + a[2] + ", " + a[3] + ")";
}
var clone6 = clone5;
var fromValues5 = fromValues4;
var copy5 = copy4;
var set5 = set4;
var add5 = add4;
var mul5 = multiply5;
var scale5 = scale4;
var dot3 = dot2;
var lerp3 = lerp2;
var length4 = length3;
var len3 = length4;
var squaredLength3 = squaredLength2;
var sqrLen3 = squaredLength3;
var normalize3 = normalize2;
var exactEquals5 = exactEquals4;
var equals5 = equals4;
var rotationTo = (function() {
  var tmpvec3 = create3();
  var xUnitVec3 = fromValues3(1, 0, 0);
  var yUnitVec3 = fromValues3(0, 1, 0);
  return function(out, a, b) {
    var dot4 = dot(a, b);
    if (dot4 < -0.999999) {
      cross(tmpvec3, xUnitVec3, a);
      if (len(tmpvec3) < 1e-6) cross(tmpvec3, yUnitVec3, a);
      normalize(tmpvec3, tmpvec3);
      setAxisAngle(out, tmpvec3, Math.PI);
      return out;
    } else if (dot4 > 0.999999) {
      out[0] = 0;
      out[1] = 0;
      out[2] = 0;
      out[3] = 1;
      return out;
    } else {
      cross(tmpvec3, a, b);
      out[0] = tmpvec3[0];
      out[1] = tmpvec3[1];
      out[2] = tmpvec3[2];
      out[3] = 1 + dot4;
      return normalize3(out, out);
    }
  };
})();
var sqlerp = (function() {
  var temp1 = create5();
  var temp2 = create5();
  return function(out, a, b, c, d, t) {
    slerp(temp1, a, d, t);
    slerp(temp2, b, c, t);
    slerp(out, temp1, temp2, 2 * t * (1 - t));
    return out;
  };
})();
var setAxes = (function() {
  var matr = create();
  return function(out, view, right, up) {
    matr[0] = right[0];
    matr[3] = right[1];
    matr[6] = right[2];
    matr[1] = up[0];
    matr[4] = up[1];
    matr[7] = up[2];
    matr[2] = -view[0];
    matr[5] = -view[1];
    matr[8] = -view[2];
    return normalize3(out, fromMat3(out, matr));
  };
})();

// node_modules/neuroglancer/lib/util/array.js
init_legacy_browser();
function filterArrayInplace(array2, predicate) {
  const length22 = array2.length;
  let outIndex = 0;
  for (let i = 0; i < length22; ++i) {
    if (predicate(array2[i], i, array2)) {
      array2[outIndex] = array2[i];
      ++outIndex;
    }
  }
  array2.length = outIndex;
}
function transposeArray2d(array2, majorSize, minorSize) {
  const transpose3 = new array2.constructor(array2.length);
  for (let i = 0; i < majorSize * minorSize; i += minorSize) {
    for (let j = 0; j < minorSize; j++) {
      const index = i / minorSize;
      transpose3[j * majorSize + index] = array2[i + j];
    }
  }
  return transpose3;
}
function binarySearch(haystack, needle, compare, low = 0, high = haystack.length) {
  while (low < high) {
    const mid = low + high - 1 >> 1;
    const compareResult = compare(needle, haystack[mid]);
    if (compareResult > 0) {
      low = mid + 1;
    } else if (compareResult < 0) {
      high = mid;
    } else {
      return mid;
    }
  }
  return ~low;
}
function binarySearchLowerBound(begin, end, predicate) {
  let count = end - begin;
  while (count > 0) {
    const step = Math.floor(count / 2);
    const i = begin + step;
    if (predicate(i)) {
      count = step;
    } else {
      begin = i + 1;
      count -= step + 1;
    }
  }
  return begin;
}
function arraysEqual(a, b) {
  const length22 = a.length;
  if (b.length !== length22) return false;
  for (let i = 0; i < length22; ++i) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

// node_modules/neuroglancer/lib/util/geom.js
var identityMat4 = mat4_exports.create();
var kAxes = [
  vec3_exports.fromValues(1, 0, 0),
  vec3_exports.fromValues(0, 1, 0),
  vec3_exports.fromValues(0, 0, 1)
];
var kZeroVec = vec3_exports.fromValues(0, 0, 0);
var kZeroVec4 = vec4_exports.fromValues(0, 0, 0, 0);
var kOneVec = vec3_exports.fromValues(1, 1, 1);
var kInfinityVec = vec3_exports.fromValues(Infinity, Infinity, Infinity);
var kIdentityQuat = quat_exports.create();
function prod3(x) {
  return x[0] * x[1] * x[2];
}
function vec3Key(x) {
  return `${x[0]},${x[1]},${x[2]}`;
}
function transformVectorByMat4(out, a, m) {
  const x = a[0];
  const y = a[1];
  const z = a[2];
  out[0] = m[0] * x + m[4] * y + m[8] * z;
  out[1] = m[1] * x + m[5] * y + m[9] * z;
  out[2] = m[2] * x + m[6] * y + m[10] * z;
  return out;
}
function transformVectorByMat4Transpose(out, a, m) {
  const x = a[0];
  const y = a[1];
  const z = a[2];
  out[0] = m[0] * x + m[1] * y + m[2] * z;
  out[1] = m[4] * x + m[5] * y + m[6] * z;
  out[2] = m[8] * x + m[9] * y + m[10] * z;
  return out;
}
function translationRotationScaleZReflectionToMat4(out, translation, rotation, scale6, zReflection) {
  const temp = out;
  out[0] = scale6[0];
  out[1] = scale6[1];
  out[2] = scale6[2] * zReflection;
  return mat4_exports.fromRotationTranslationScale(
    out,
    rotation,
    translation,
    temp
  );
}
function mat3FromMat4(out, m) {
  const m00 = m[0];
  const m01 = m[1];
  const m02 = m[2];
  const m10 = m[4];
  const m11 = m[5];
  const m12 = m[6];
  const m20 = m[8];
  const m21 = m[9];
  const m22 = m[10];
  out[0] = m00;
  out[1] = m01;
  out[2] = m02;
  out[3] = m10;
  out[4] = m11;
  out[5] = m12;
  out[6] = m20;
  out[7] = m21;
  out[8] = m22;
  return out;
}
function getFrustrumPlanes(out, m) {
  const m00 = m[0];
  const m10 = m[1];
  const m20 = m[2];
  const m30 = m[3];
  const m01 = m[4];
  const m11 = m[5];
  const m21 = m[6];
  const m31 = m[7];
  const m02 = m[8];
  const m12 = m[9];
  const m22 = m[10];
  const m32 = m[11];
  const m03 = m[12];
  const m13 = m[13];
  const m23 = m[14];
  const m33 = m[15];
  out[0] = m30 + m00;
  out[1] = m31 + m01;
  out[2] = m32 + m02;
  out[3] = m33 + m03;
  out[4] = m30 - m00;
  out[5] = m31 - m01;
  out[6] = m32 - m02;
  out[7] = m33 - m03;
  out[8] = m30 + m10;
  out[9] = m31 + m11;
  out[10] = m32 + m12;
  out[11] = m33 + m13;
  out[12] = m30 - m10;
  out[13] = m31 - m11;
  out[14] = m32 - m12;
  out[15] = m33 - m13;
  const nearA = m30 + m20;
  const nearB = m31 + m21;
  const nearC = m32 + m22;
  const nearD = m33 + m23;
  const farA = m30 - m20;
  const farB = m31 - m21;
  const farC = m32 - m22;
  const farD = m33 - m23;
  const nearNorm = Math.sqrt(nearA ** 2 + nearB ** 2 + nearC ** 2);
  out[16] = nearA / nearNorm;
  out[17] = nearB / nearNorm;
  out[18] = nearC / nearNorm;
  out[19] = nearD / nearNorm;
  const farNorm = Math.sqrt(farA ** 2 + farB ** 2 + farC ** 2);
  out[20] = farA / farNorm;
  out[21] = farB / farNorm;
  out[22] = farC / farNorm;
  out[23] = farD / farNorm;
  return out;
}
function isAABBVisible(xLower, yLower, zLower, xUpper, yUpper, zUpper, clippingPlanes) {
  for (let i = 0; i < 6; ++i) {
    const a = clippingPlanes[i * 4];
    const b = clippingPlanes[i * 4 + 1];
    const c = clippingPlanes[i * 4 + 2];
    const d = clippingPlanes[i * 4 + 3];
    const sum = Math.max(a * xLower, a * xUpper) + Math.max(b * yLower, b * yUpper) + Math.max(c * zLower, c * zUpper) + d;
    if (sum < 0) {
      return false;
    }
  }
  return true;
}
function isAABBIntersectingPlane(xLower, yLower, zLower, xUpper, yUpper, zUpper, clippingPlanes) {
  for (let i = 0; i < 4; ++i) {
    const a = clippingPlanes[i * 4];
    const b = clippingPlanes[i * 4 + 1];
    const c = clippingPlanes[i * 4 + 2];
    const d = clippingPlanes[i * 4 + 3];
    const sum = Math.max(a * xLower, a * xUpper) + Math.max(b * yLower, b * yUpper) + Math.max(c * zLower, c * zUpper) + d;
    if (sum < 0) {
      return false;
    }
  }
  {
    const i = 5;
    const a = clippingPlanes[i * 4];
    const b = clippingPlanes[i * 4 + 1];
    const c = clippingPlanes[i * 4 + 2];
    const d = clippingPlanes[i * 4 + 3];
    const maxSum = Math.max(a * xLower, a * xUpper) + Math.max(b * yLower, b * yUpper) + Math.max(c * zLower, c * zUpper);
    const minSum = Math.min(a * xLower, a * xUpper) + Math.min(b * yLower, b * yUpper) + Math.min(c * zLower, c * zUpper);
    const epsilon = Math.abs(d) * 1e-6;
    if (minSum > -d + epsilon || maxSum < -d - epsilon) return false;
  }
  return true;
}
function getViewFrustrumVolume(projectionMat) {
  if (projectionMat[15] === 1) {
    const depth = 2 / Math.abs(projectionMat[10]);
    const width = 2 / Math.abs(projectionMat[0]);
    const height = 2 / Math.abs(projectionMat[5]);
    return width * height * depth;
  }
  const a = projectionMat[10];
  const b = projectionMat[14];
  const near = 2 * b / (2 * a - 2);
  const far = (a - 1) * near / (a + 1);
  const baseArea = 4 / (projectionMat[0] * projectionMat[5]);
  return baseArea / 3 * (Math.abs(far) ** 3 - Math.abs(near) ** 3);
}
function getViewFrustrumDepthRange(projectionMat) {
  if (projectionMat[15] === 1) {
    const depth2 = 2 / Math.abs(projectionMat[10]);
    return depth2;
  }
  const a = projectionMat[10];
  const b = projectionMat[14];
  const near = 2 * b / (2 * a - 2);
  const far = (a - 1) * near / (a + 1);
  const depth = Math.abs(far - near);
  return depth;
}
var tempVec3 = vec3_exports.create();

// node_modules/neuroglancer/lib/util/json.js
function verifyFloat(obj) {
  const t = typeof obj;
  if (t === "number" || t === "string") {
    const x = parseFloat("" + obj);
    if (!Number.isNaN(x)) {
      return x;
    }
  }
  throw new Error(
    `Expected floating-point number, but received: ${JSON.stringify(obj)}.`
  );
}
function verifyFiniteFloat(obj) {
  const x = verifyFloat(obj);
  if (Number.isFinite(x)) {
    return x;
  }
  throw new Error(`Expected finite floating-point number, but received: ${x}.`);
}
function verifyFiniteNonNegativeFloat(obj) {
  const x = verifyFloat(obj);
  if (Number.isFinite(x) && x >= 0) {
    return x;
  }
  throw new Error(
    `Expected finite non-negative floating-point number, but received: ${x}.`
  );
}
function stableStringify(x) {
  if (typeof x === "object") {
    if (x === null) {
      return "null";
    }
    if (Array.isArray(x)) {
      let s2 = "[";
      const size2 = x.length;
      let i2 = 0;
      if (i2 < size2) {
        s2 += stableStringify(x[i2]);
        while (++i2 < size2) {
          s2 += ",";
          s2 += stableStringify(x[i2]);
        }
      }
      s2 += "]";
      return s2;
    }
    let s = "{";
    const keys = Object.keys(x).sort();
    let i = 0;
    const size = keys.length;
    if (i < size) {
      let key = keys[i];
      s += JSON.stringify(key);
      s += ":";
      s += stableStringify(x[key]);
      while (++i < size) {
        s += ",";
        key = keys[i];
        s += JSON.stringify(key);
        s += ":";
        s += stableStringify(x[key]);
      }
    }
    s += "}";
    return s;
  }
  if (typeof x === "bigint") {
    return x.toString();
  }
  return JSON.stringify(x);
}
var SINGLE_QUOTE_STRING_PATTERN = /('(?:[^'\\]|(?:\\.))*')/;
var DOUBLE_QUOTE_STRING_PATTERN = /("(?:[^"\\]|(?:\\.))*")/;
var SINGLE_OR_DOUBLE_QUOTE_STRING_PATTERN = new RegExp(
  `${SINGLE_QUOTE_STRING_PATTERN.source}|${DOUBLE_QUOTE_STRING_PATTERN.source}`
);
var DOUBLE_OR_SINGLE_QUOTE_STRING_PATTERN = new RegExp(
  `${DOUBLE_QUOTE_STRING_PATTERN.source}|${SINGLE_QUOTE_STRING_PATTERN.source}`
);
var DOUBLE_QUOTE_PATTERN = /^((?:[^"'\\]|(?:\\[^']))*)("|\\')/;
function convertStringLiteral(x, quoteInitial, quoteReplace, quoteSearch) {
  if (x.length >= 2 && x.charAt(0) === quoteInitial && x.charAt(x.length - 1) === quoteInitial) {
    let inner = x.substr(1, x.length - 2);
    let s = quoteReplace;
    while (inner.length > 0) {
      const m = inner.match(quoteSearch);
      if (m === null) {
        s += inner;
        break;
      }
      s += m[1];
      if (m[2] === quoteReplace) {
        s += "\\";
        s += quoteReplace;
      } else {
        s += quoteInitial;
      }
      inner = inner.substr(m.index + m[0].length);
    }
    s += quoteReplace;
    return s;
  }
  return x;
}
function normalizeStringLiteral(x) {
  return convertStringLiteral(x, "'", '"', DOUBLE_QUOTE_PATTERN);
}
function pythonLiteralToJSON(x) {
  let s = "";
  while (x.length > 0) {
    const m = x.match(SINGLE_OR_DOUBLE_QUOTE_STRING_PATTERN);
    let before;
    let replacement;
    if (m === null) {
      before = x;
      x = "";
      replacement = "";
    } else {
      before = x.substr(0, m.index);
      x = x.substr(m.index + m[0].length);
      const singleQuoteString = m[1];
      if (singleQuoteString !== void 0) {
        replacement = normalizeStringLiteral(singleQuoteString);
      } else {
        replacement = m[2];
      }
    }
    s += before.replace(/\(/g, "[").replace(/\)/g, "]").replace("True", "true").replace("False", "false").replace(/,\s*([}\]])/g, "$1");
    s += replacement;
  }
  return s;
}
function pythonLiteralParse(x) {
  return JSON.parse(pythonLiteralToJSON(x));
}
function parseArray(x, parseElement) {
  if (!Array.isArray(x)) {
    throw new Error(`Expected array, but received: ${JSON.stringify(x)}.`);
  }
  return x.map(parseElement);
}
function parseFixedLengthArray(out, obj, parseElement) {
  const length6 = out.length;
  if (!Array.isArray(obj) || obj.length !== length6) {
    throw new Error(
      `Expected length ${length6} array, but received: ${JSON.stringify(obj)}.`
    );
  }
  for (let i = 0; i < length6; ++i) {
    out[i] = parseElement(obj[i], i);
  }
  return out;
}
function verifyObject(obj) {
  if (typeof obj !== "object" || obj == null || Array.isArray(obj)) {
    throw new Error(
      `Expected JSON object, but received: ${JSON.stringify(obj)}.`
    );
  }
  return obj;
}
function verifyInt(obj) {
  const result = parseInt(obj, 10);
  if (!Number.isInteger(result)) {
    throw new Error(`Expected integer, but received: ${JSON.stringify(obj)}.`);
  }
  return result;
}
function verifyString(obj) {
  if (typeof obj !== "string") {
    throw new Error(`Expected string, but received: ${JSON.stringify(obj)}.`);
  }
  return obj;
}
function verifyOptionalString(obj) {
  if (obj === void 0) {
    return void 0;
  }
  return verifyString(obj);
}
function verifyObjectProperty(obj, propertyName, validator) {
  const value = Object.prototype.hasOwnProperty.call(obj, propertyName) ? obj[propertyName] : void 0;
  try {
    return validator(value);
  } catch (parseError) {
    throw new Error(
      `Error parsing ${JSON.stringify(propertyName)} property: ${parseError.message}`
    );
  }
}
function verifyOptionalObjectProperty(obj, propertyName, validator, defaultValue) {
  return verifyObjectProperty(
    obj,
    propertyName,
    (x) => x === void 0 ? defaultValue : validator(x)
  );
}
function verifyEnumString(obj, enumType, pattern = /^[a-zA-Z]/) {
  if (typeof obj === "string" && obj.match(pattern) !== null) {
    const objUpperCase = obj.toUpperCase();
    if (Object.prototype.hasOwnProperty.call(enumType, objUpperCase)) {
      return enumType[objUpperCase];
    }
  }
  throw new Error(`Invalid enum value: ${JSON.stringify(obj)}.`);
}
function verifyStringArray(a) {
  if (!Array.isArray(a)) {
    throw new Error(`Expected array, received: ${JSON.stringify(a)}.`);
  }
  for (const x of a) {
    if (typeof x !== "string") {
      throw new Error(`Expected string, received: ${JSON.stringify(x)}.`);
    }
  }
  return a;
}
function parseUint64(obj) {
  let n;
  switch (typeof obj) {
    case "string":
      if (obj.match(/^(?:0|[1-9][0-9]*)$/) === null) {
        throw new Error(
          `Expected base-10 number, but received: ${JSON.stringify(obj)}`
        );
      }
      n = BigInt(obj);
      break;
    case "number":
      n = BigInt(obj);
      break;
    case "bigint":
      n = obj;
      break;
    default:
      throw new Error(
        `Expected uint64 value, but received: ${JSON.stringify(obj)}`
      );
  }
  if (n < 0n || n > UINT64_MAX) {
    throw new Error(`Expected uint64 value, but received: ${n}`);
  }
  return n;
}

// node_modules/neuroglancer/lib/util/memoize.js
var Memoize = class {
  map = /* @__PURE__ */ new Map();
  /**
   * If getter throws an exception, no value is added.
   */
  get(key, getter) {
    const { map: map2 } = this;
    let obj = map2.get(key);
    if (obj === void 0) {
      obj = getter();
      obj.registerDisposer(() => {
        map2.delete(key);
      });
      map2.set(key, obj);
    } else {
      obj.addRef();
    }
    return obj;
  }
};
var StringMemoize = class extends Memoize {
  get(x, getter) {
    if (typeof x !== "string") {
      x = stableStringify(x);
    }
    return super.get(x, getter);
  }
  getUncounted(x, getter) {
    return this.get(x, () => new RefCountedValue(getter())).value;
  }
  getAsync(x, options, getter) {
    return this.getUncounted(x, () => asyncMemoizeWithProgress(getter))(
      options
    );
  }
};
function asyncMemoizeWithProgress(getter) {
  let progressListener;
  let abortController;
  let promise;
  let completed = false;
  return async (options) => {
    if (completed) {
      return promise;
    }
    const { signal } = options;
    signal == null ? void 0 : signal.throwIfAborted();
    if (promise === void 0 || abortController.signal.aborted) {
      progressListener = new MultiConsumerProgressListener();
      abortController = new SharedAbortController();
      const curAbortController = abortController;
      promise = (async () => {
        try {
          return await getter({
            signal: curAbortController.signal,
            progressListener
          });
        } catch (e) {
          if (curAbortController.signal.aborted) {
            promise = void 0;
          }
          throw e;
        } finally {
          if (promise !== void 0) {
            completed = true;
          }
          progressListener = void 0;
          curAbortController[Symbol.dispose]();
          if (abortController === curAbortController) {
            abortController = void 0;
          }
        }
      })();
    }
    abortController.addConsumer(signal);
    const curProgressListener = progressListener;
    curProgressListener.addListener(options.progressListener);
    try {
      return await raceWithAbort(promise, signal);
    } finally {
      curProgressListener.removeListener(options.progressListener);
    }
  };
}

// node_modules/neuroglancer/lib/util/pairing_heap.js
init_legacy_browser();
function makePairingHeapOperations(options) {
  const { child: CHILD, next: NEXT, prev: PREV, compare } = options;
  function combineChildren(node) {
    let cur = node[CHILD];
    if (cur === null) {
      return null;
    }
    let head = null;
    while (true) {
      const curNext = cur[NEXT];
      let next, m;
      if (curNext === null) {
        next = null;
        m = cur;
      } else {
        next = curNext[NEXT];
        m = meld(cur, curNext);
      }
      m[NEXT] = head;
      head = m;
      if (next === null) {
        break;
      }
      cur = next;
    }
    let root2 = head;
    head = head[NEXT];
    while (true) {
      if (head === null) {
        break;
      }
      const next = head[NEXT];
      root2 = meld(root2, head);
      head = next;
    }
    root2[PREV] = null;
    root2[NEXT] = null;
    return root2;
  }
  function meld(a, b) {
    if (b === null) {
      return a;
    }
    if (a === null) {
      return b;
    }
    if (compare(b, a)) {
      const temp = a;
      a = b;
      b = temp;
    }
    const aChild = a[CHILD];
    b[NEXT] = aChild;
    b[PREV] = a;
    if (aChild !== null) {
      aChild[PREV] = b;
    }
    a[CHILD] = b;
    return a;
  }
  function removeMin(root2) {
    const newRoot = combineChildren(root2);
    root2[NEXT] = null;
    root2[PREV] = null;
    root2[CHILD] = null;
    return newRoot;
  }
  function remove(root2, node) {
    if (root2 === node) {
      return removeMin(root2);
    }
    const prev = node[PREV];
    const next = node[NEXT];
    if (prev[CHILD] === node) {
      prev[CHILD] = next;
    } else {
      prev[NEXT] = next;
    }
    if (next !== null) {
      next[PREV] = prev;
    }
    const newRoot = meld(root2, combineChildren(node));
    node[NEXT] = null;
    node[PREV] = null;
    node[CHILD] = null;
    return newRoot;
  }
  function* entries(root2) {
    if (root2 !== null) {
      let child = root2[CHILD];
      yield root2;
      while (child !== null) {
        const next = child[NEXT];
        yield* entries(child);
        child = next;
      }
    }
  }
  function* removedEntries(root2) {
    if (root2 !== null) {
      let child = root2[CHILD];
      root2[CHILD] = null;
      root2[NEXT] = null;
      root2[PREV] = null;
      yield root2;
      while (child !== null) {
        const next = child[NEXT];
        child[CHILD] = null;
        child[NEXT] = null;
        child[PREV] = null;
        yield* entries(child);
        child = next;
      }
    }
  }
  return {
    compare,
    meld,
    removeMin,
    remove,
    entries,
    removedEntries
  };
}

// node_modules/neuroglancer/lib/chunk_manager/backend.js
var __defProp3 = Object.defineProperty;
var __getOwnPropDesc3 = Object.getOwnPropertyDescriptor;
var __decorateClass2 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc3(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp3(target2, key, result);
  return result;
};
var DEBUG_CHUNK_UPDATES = false;
var nextMarkGeneration = 0;
function getNextMarkGeneration() {
  return ++nextMarkGeneration;
}
var Chunk = class {
  // Node properties used for eviction/promotion heaps and LRU linked lists.
  child0 = null;
  next0 = null;
  prev0 = null;
  child1 = null;
  next1 = null;
  prev1 = null;
  source = null;
  key = null;
  state_ = ChunkState.NEW;
  error = null;
  // Used by layers for marking chunks for various purposes.
  markGeneration = -1;
  /**
   * Specifies existing priority within priority tier.  Only meaningful if priorityTier in
   * CHUNK_ORDERED_PRIORITY_TIERS.  Higher numbers mean higher priority.
   */
  priority = 0;
  /**
   * Specifies updated priority within priority tier, not yet reflected in priority queue state.
   * Only meaningful if newPriorityTier in CHUNK_ORDERED_PRIORITY_TIERS.
   */
  newPriority = 0;
  priorityTier = ChunkPriorityTier.RECENT;
  /**
   * Specifies updated priority tier, not yet reflected in priority queue state.
   */
  newPriorityTier = ChunkPriorityTier.RECENT;
  systemMemoryBytes_ = 0;
  gpuMemoryBytes_ = 0;
  downloadSlots_ = 1;
  isComputational = false;
  /**
   * Specifies lowest numeric state required by any request, if `prioritTier !==
   * ChunkPriorityTier.RECENT`, then this must be one of `GPU_MEMORY`, `SYSTEM_MEMORY`, or
   * `SYSTEM_MEMORY_WORKER`.
   */
  requestedState = ChunkState.NEW;
  newRequestedState = ChunkState.NEW;
  /**
   * Abort controller used to cancel the pending download.  Set to undefined except when state !==
   * DOWNLOADING.  This should not be accessed by code outside this module.
   */
  downloadAbortController = void 0;
  initialize(key) {
    this.key = key;
    this.priority = Number.NEGATIVE_INFINITY;
    this.priorityTier = ChunkPriorityTier.RECENT;
    this.newPriority = Number.NEGATIVE_INFINITY;
    this.newPriorityTier = ChunkPriorityTier.RECENT;
    this.error = null;
    this.state = ChunkState.NEW;
    this.requestedState = ChunkState.NEW;
    this.newRequestedState = ChunkState.NEW;
  }
  /**
   * Sets this.priority{Tier,} to this.newPriority{Tier,}, and resets this.newPriorityTier to
   * ChunkPriorityTier.RECENT.
   *
   * This does not actually update any queues to reflect this change.
   */
  updatePriorityProperties() {
    this.priorityTier = this.newPriorityTier;
    this.priority = this.newPriority;
    this.newPriorityTier = ChunkPriorityTier.RECENT;
    this.newPriority = Number.NEGATIVE_INFINITY;
    this.requestedState = this.newRequestedState;
    this.newRequestedState = ChunkState.NEW;
  }
  dispose() {
    this.source = null;
    this.error = null;
  }
  get chunkManager() {
    return this.source.chunkManager;
  }
  get queueManager() {
    return this.source.chunkManager.queueManager;
  }
  downloadFailed(error) {
    this.error = error;
    this.queueManager.updateChunkState(this, ChunkState.FAILED);
  }
  downloadSucceeded() {
    if (this.requestedState === ChunkState.SYSTEM_MEMORY) {
      this.queueManager.moveChunkToFrontend(this);
      this.queueManager.updateChunkState(this, ChunkState.SYSTEM_MEMORY);
    } else {
      this.queueManager.updateChunkState(this, ChunkState.SYSTEM_MEMORY_WORKER);
    }
  }
  freeSystemMemory() {
  }
  serialize(msg, _transfers) {
    msg.id = this.key;
    msg.source = this.source.rpcId;
    msg.new = true;
  }
  toString() {
    return this.key;
  }
  set state(newState) {
    if (newState === this.state_) {
      return;
    }
    const oldState = this.state_;
    this.state_ = newState;
    this.source.chunkStateChanged(this, oldState);
  }
  get state() {
    return this.state_;
  }
  set systemMemoryBytes(bytes) {
    updateChunkStatistics(this, -1);
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, false);
    this.systemMemoryBytes_ = bytes;
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, true);
    updateChunkStatistics(this, 1);
    this.chunkManager.queueManager.scheduleUpdate();
  }
  get systemMemoryBytes() {
    return this.systemMemoryBytes_;
  }
  set gpuMemoryBytes(bytes) {
    updateChunkStatistics(this, -1);
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, false);
    this.gpuMemoryBytes_ = bytes;
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, true);
    updateChunkStatistics(this, 1);
    this.chunkManager.queueManager.scheduleUpdate();
  }
  get gpuMemoryBytes() {
    return this.gpuMemoryBytes_;
  }
  get downloadSlots() {
    return this.downloadSlots_;
  }
  set downloadSlots(count) {
    if (count === this.downloadSlots_) return;
    updateChunkStatistics(this, -1);
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, false);
    this.downloadSlots_ = count;
    this.chunkManager.queueManager.adjustCapacitiesForChunk(this, true);
    updateChunkStatistics(this, 1);
    this.chunkManager.queueManager.scheduleUpdate();
  }
  registerListener(listener) {
    if (!this.source) {
      return false;
    }
    return this.source.registerChunkListener(this.key, listener);
  }
  unregisterListener(listener) {
    if (!this.source) {
      return false;
    }
    return this.source.unregisterChunkListener(this.key, listener);
  }
  static priorityLess(a, b) {
    return a.priority < b.priority;
  }
  static priorityGreater(a, b) {
    return a.priority > b.priority;
  }
};
var numSourceQueueLevels = 2;
var ChunkSourceBase = class extends SharedObject {
  constructor(chunkManager) {
    super();
    this.chunkManager = chunkManager;
    chunkManager.queueManager.sources.add(this);
  }
  listeners_ = /* @__PURE__ */ new Map();
  chunks = /* @__PURE__ */ new Map();
  freeChunks = new Array();
  statistics = new Float64Array(numChunkStatistics);
  /**
   * sourceQueueLevel must be greater than the sourceQueueLevel of any ChunkSource whose download
   * method depends on chunks from this source.  A normal ChunkSource with no other dependencies
   * should have a level of 0.
   */
  sourceQueueLevel = 0;
  disposed() {
    this.chunkManager.queueManager.sources.delete(this);
    super.disposed();
  }
  getNewChunk_(chunkType) {
    const freeChunks = this.freeChunks;
    const freeChunksLength = freeChunks.length;
    if (freeChunksLength > 0) {
      const chunk2 = freeChunks[freeChunksLength - 1];
      freeChunks.length = freeChunksLength - 1;
      chunk2.source = this;
      return chunk2;
    }
    const chunk = new chunkType();
    chunk.source = this;
    return chunk;
  }
  /**
   * Adds the specified chunk to the chunk cache.
   *
   * If the chunk cache was previously empty, also call this.addRef() to increment the reference
   * count.
   */
  addChunk(chunk) {
    const { chunks } = this;
    if (chunks.size === 0) {
      this.addRef();
    }
    chunks.set(chunk.key, chunk);
    updateChunkStatistics(chunk, 1);
  }
  /**
   * Remove the specified chunk from the chunk cache.
   *
   * If the chunk cache becomes empty, also call this.dispose() to decrement the reference count.
   */
  removeChunk(chunk) {
    const { chunks, freeChunks } = this;
    chunks.delete(chunk.key);
    chunk.dispose();
    freeChunks[freeChunks.length] = chunk;
    if (chunks.size === 0) {
      this.dispose();
    }
  }
  registerChunkListener(key, listener) {
    if (!this.listeners_.has(key)) {
      this.listeners_.set(key, [listener]);
    } else {
      this.listeners_.get(key).push(listener);
    }
    return true;
  }
  unregisterChunkListener(key, listener) {
    if (!this.listeners_.has(key)) {
      return false;
    }
    const keyListeners = this.listeners_.get(key);
    const idx = keyListeners.indexOf(listener);
    if (idx < 0) {
      return false;
    }
    keyListeners.splice(idx, 1);
    if (keyListeners.length === 0) {
      this.listeners_.delete(key);
    }
    return true;
  }
  chunkStateChanged(chunk, oldState) {
    const { key } = chunk;
    if (key === null) return;
    const listeners = this.listeners_.get(key);
    if (listeners === void 0) return;
    for (const listener of listeners.slice()) {
      listener(chunk, oldState);
    }
  }
};
function updateChunkStatistics(chunk, sign) {
  const { statistics } = chunk.source;
  const { systemMemoryBytes, gpuMemoryBytes } = chunk;
  const index = getChunkStateStatisticIndex(chunk.state, chunk.priorityTier);
  statistics[index * numChunkMemoryStatistics + ChunkMemoryStatistics.numChunks] += sign;
  statistics[index * numChunkMemoryStatistics + ChunkMemoryStatistics.systemMemoryBytes] += sign * systemMemoryBytes;
  statistics[index * numChunkMemoryStatistics + ChunkMemoryStatistics.gpuMemoryBytes] += sign * gpuMemoryBytes;
}
var ChunkSource = class extends ChunkSourceBase {
  constructor(rpc2, options) {
    const chunkManager = rpc2.get(options.chunkManager);
    super(chunkManager);
    initializeSharedObjectCounterpart(this, rpc2, options);
  }
};
function startChunkDownload(chunk) {
  const downloadAbortController = chunk.downloadAbortController = new AbortController();
  const startTime = Date.now();
  chunk.source.download(chunk, downloadAbortController.signal).then(
    () => {
      if (chunk.downloadAbortController === downloadAbortController) {
        chunk.downloadAbortController = void 0;
        const endTime = Date.now();
        const { statistics } = chunk.source;
        statistics[getChunkDownloadStatisticIndex(ChunkDownloadStatistics.totalTime)] += endTime - startTime;
        ++statistics[getChunkDownloadStatisticIndex(ChunkDownloadStatistics.totalChunks)];
        chunk.downloadSucceeded();
      }
    },
    (error) => {
      if (chunk.downloadAbortController === downloadAbortController) {
        chunk.downloadAbortController = void 0;
        chunk.downloadFailed(error);
        console.log(`Error retrieving chunk ${chunk}: ${error}`);
      }
    }
  );
}
function cancelChunkDownload(chunk) {
  const controller = chunk.downloadAbortController;
  chunk.downloadAbortController = void 0;
  controller.abort(new DOMException("chunk download cancelled", "AbortError"));
}
var ChunkPriorityQueue = class {
  constructor(heapOperations, linkedListOperations2) {
    this.heapOperations = heapOperations;
    this.linkedListOperations = linkedListOperations2;
    linkedListOperations2.initializeHead(this.recentHead);
  }
  /**
   * Heap roots for VISIBLE and PREFETCH priority tiers.
   */
  heapRoots = [null, null];
  /**
   * Head node for RECENT linked list.
   */
  recentHead = new Chunk();
  add(chunk) {
    const priorityTier = chunk.priorityTier;
    if (priorityTier === ChunkPriorityTier.RECENT) {
      this.linkedListOperations.insertAfter(this.recentHead, chunk);
    } else {
      const { heapRoots } = this;
      heapRoots[priorityTier] = this.heapOperations.meld(
        heapRoots[priorityTier],
        chunk
      );
    }
  }
  *candidates() {
    if (this.heapOperations.compare === Chunk.priorityLess) {
      const { linkedListOperations: linkedListOperations2, recentHead } = this;
      while (true) {
        const chunk = linkedListOperations2.back(recentHead);
        if (chunk == null) {
          break;
        }
        yield chunk;
      }
      const { heapRoots } = this;
      for (let tier = ChunkPriorityTier.LAST_ORDERED_TIER; tier >= ChunkPriorityTier.FIRST_ORDERED_TIER; --tier) {
        while (true) {
          const root2 = heapRoots[tier];
          if (root2 == null) {
            break;
          }
          yield root2;
        }
      }
    } else {
      const heapRoots = this.heapRoots;
      for (let tier = ChunkPriorityTier.FIRST_ORDERED_TIER; tier <= ChunkPriorityTier.LAST_ORDERED_TIER; ++tier) {
        while (true) {
          const root2 = heapRoots[tier];
          if (root2 == null) {
            break;
          }
          yield root2;
        }
      }
      const { linkedListOperations: linkedListOperations2, recentHead } = this;
      while (true) {
        const chunk = linkedListOperations2.front(recentHead);
        if (chunk == null) {
          break;
        }
        yield chunk;
      }
    }
  }
  /**
   * Deletes a chunk from this priority queue.
   * @param chunk The chunk to delete from the priority queue.
   */
  delete(chunk) {
    const priorityTier = chunk.priorityTier;
    if (priorityTier === ChunkPriorityTier.RECENT) {
      this.linkedListOperations.pop(chunk);
    } else {
      const heapRoots = this.heapRoots;
      heapRoots[priorityTier] = this.heapOperations.remove(
        heapRoots[priorityTier],
        chunk
      );
    }
  }
};
var linkedList0 = linkedListOperations({ next: "next0", prev: "prev0" });
var linkedList1 = linkedListOperations({ next: "next1", prev: "prev1" });
function makeChunkPriorityQueue0(compare) {
  return new ChunkPriorityQueue(
    makePairingHeapOperations({
      compare,
      child: "child0",
      next: "next0",
      prev: "prev0"
    }),
    linkedList0
  );
}
function makeChunkPriorityQueue1(compare) {
  return new ChunkPriorityQueue(
    makePairingHeapOperations({
      compare,
      child: "child1",
      next: "next1",
      prev: "prev1"
    }),
    linkedList1
  );
}
function tryToFreeCapacity(size, capacity, priorityTier, priority, evictionCandidates, evict) {
  while (capacity.availableItems < 1 || capacity.availableSize < size) {
    const evictionCandidate = evictionCandidates.next().value;
    if (evictionCandidate === void 0) {
      return false;
    }
    const evictionTier = evictionCandidate.priorityTier;
    if (evictionTier < priorityTier || evictionTier === priorityTier && evictionCandidate.priority >= priority) {
      return false;
    }
    evict(evictionCandidate);
  }
  return true;
}
var AvailableCapacity = class extends RefCounted {
  constructor(itemLimit, sizeLimit) {
    super();
    this.itemLimit = itemLimit;
    this.sizeLimit = sizeLimit;
    this.registerDisposer(itemLimit.changed.add(this.capacityChanged.dispatch));
    this.registerDisposer(sizeLimit.changed.add(this.capacityChanged.dispatch));
  }
  currentSize = 0;
  currentItems = 0;
  capacityChanged = new NullarySignal();
  /**
   * Adjust available capacity by the specified amounts.
   */
  adjust(items, size) {
    this.currentItems -= items;
    this.currentSize -= size;
  }
  get availableSize() {
    return this.sizeLimit.value - this.currentSize;
  }
  get availableItems() {
    return this.itemLimit.value - this.currentItems;
  }
  toString() {
    return `bytes=${this.currentSize}/${this.sizeLimit.value},items=${this.currentItems}/${this.itemLimit.value}`;
  }
};
var ChunkQueueManager = class extends SharedObjectCounterpart {
  gpuMemoryCapacity;
  systemMemoryCapacity;
  /**
   * Download capacity for each sourceQueueLevel.
   */
  downloadCapacity;
  computeCapacity;
  enablePrefetch;
  /**
   * Set of chunk sources associated with this queue manager.
   */
  sources = /* @__PURE__ */ new Set();
  /**
   * Contains all chunks in QUEUED state pending download, for each sourceQueueLevel.
   */
  queuedDownloadPromotionQueue = [
    makeChunkPriorityQueue1(Chunk.priorityGreater),
    makeChunkPriorityQueue1(Chunk.priorityGreater)
  ];
  /**
   * Contains all chunks in QUEUED state pending compute.
   */
  queuedComputePromotionQueue = makeChunkPriorityQueue1(
    Chunk.priorityGreater
  );
  /**
   * Contains all chunks in DOWNLOADING state, for each sourceQueueLevel.
   */
  downloadEvictionQueue = [
    makeChunkPriorityQueue1(Chunk.priorityLess),
    makeChunkPriorityQueue1(Chunk.priorityLess)
  ];
  /**
   * Contains all chunks in COMPUTING state.
   */
  computeEvictionQueue = makeChunkPriorityQueue1(Chunk.priorityLess);
  /**
   * Contains all chunks that take up memory (DOWNLOADING, SYSTEM_MEMORY,
   * GPU_MEMORY).
   */
  systemMemoryEvictionQueue = makeChunkPriorityQueue0(
    Chunk.priorityLess
  );
  /**
   * Contains all chunks in SYSTEM_MEMORY state not in RECENT priority tier.
   */
  gpuMemoryPromotionQueue = makeChunkPriorityQueue1(
    Chunk.priorityGreater
  );
  /**
   * Contains all chunks in GPU_MEMORY state.
   */
  gpuMemoryEvictionQueue = makeChunkPriorityQueue1(Chunk.priorityLess);
  // Should be `number|null`, but marked `any` to work around @types/node being pulled in.
  updatePending = null;
  gpuMemoryChanged = new NullarySignal();
  numQueued = 0;
  numFailed = 0;
  gpuMemoryGeneration = 0;
  constructor(rpc2, options) {
    super(rpc2, options);
    const getCapacity = (capacity) => {
      const result = this.registerDisposer(
        new AvailableCapacity(
          rpc2.get(capacity.itemLimit),
          rpc2.get(capacity.sizeLimit)
        )
      );
      result.capacityChanged.add(() => this.scheduleUpdate());
      return result;
    };
    this.gpuMemoryCapacity = getCapacity(options.gpuMemoryCapacity);
    this.systemMemoryCapacity = getCapacity(options.systemMemoryCapacity);
    this.enablePrefetch = rpc2.get(options.enablePrefetch);
    this.downloadCapacity = [
      getCapacity(options.downloadCapacity),
      getCapacity(options.downloadCapacity)
    ];
    this.computeCapacity = getCapacity(options.computeCapacity);
  }
  scheduleUpdate() {
    if (this.updatePending === null) {
      this.updatePending = setTimeout(this.process.bind(this), 0);
    }
  }
  *chunkQueuesForChunk(chunk) {
    switch (chunk.state) {
      case ChunkState.QUEUED:
        if (chunk.isComputational) {
          yield this.queuedComputePromotionQueue;
        } else {
          yield this.queuedDownloadPromotionQueue[chunk.source.sourceQueueLevel];
        }
        break;
      case ChunkState.DOWNLOADING:
        if (chunk.isComputational) {
          yield this.computeEvictionQueue;
        } else {
          yield this.downloadEvictionQueue[chunk.source.sourceQueueLevel];
          yield this.systemMemoryEvictionQueue;
        }
        break;
      case ChunkState.SYSTEM_MEMORY_WORKER:
      case ChunkState.SYSTEM_MEMORY:
        yield this.systemMemoryEvictionQueue;
        if (chunk.requestedState === ChunkState.GPU_MEMORY) {
          yield this.gpuMemoryPromotionQueue;
        }
        break;
      case ChunkState.GPU_MEMORY:
        yield this.systemMemoryEvictionQueue;
        yield this.gpuMemoryEvictionQueue;
        break;
    }
  }
  adjustCapacitiesForChunk(chunk, add7) {
    const factor = add7 ? -1 : 1;
    switch (chunk.state) {
      case ChunkState.FAILED:
        this.numFailed -= factor;
        break;
      case ChunkState.QUEUED:
        this.numQueued -= factor;
        break;
      case ChunkState.DOWNLOADING:
        (chunk.isComputational ? this.computeCapacity : this.downloadCapacity[chunk.source.sourceQueueLevel]).adjust(
          factor * chunk.downloadSlots,
          factor * chunk.systemMemoryBytes
        );
        this.systemMemoryCapacity.adjust(
          factor,
          factor * chunk.systemMemoryBytes
        );
        break;
      case ChunkState.SYSTEM_MEMORY:
      case ChunkState.SYSTEM_MEMORY_WORKER:
        this.systemMemoryCapacity.adjust(
          factor,
          factor * chunk.systemMemoryBytes
        );
        break;
      case ChunkState.GPU_MEMORY:
        this.systemMemoryCapacity.adjust(
          factor,
          factor * chunk.systemMemoryBytes
        );
        this.gpuMemoryCapacity.adjust(factor, factor * chunk.gpuMemoryBytes);
        break;
    }
  }
  removeChunkFromQueues_(chunk) {
    updateChunkStatistics(chunk, -1);
    for (const queue of this.chunkQueuesForChunk(chunk)) {
      queue.delete(chunk);
    }
  }
  // var freedChunks = 0;
  addChunkToQueues_(chunk) {
    if (chunk.state === ChunkState.QUEUED && chunk.priorityTier === ChunkPriorityTier.RECENT) {
      const { source } = chunk;
      source.removeChunk(chunk);
      this.adjustCapacitiesForChunk(chunk, false);
      return false;
    }
    updateChunkStatistics(chunk, 1);
    for (const queue of this.chunkQueuesForChunk(chunk)) {
      queue.add(chunk);
    }
    return true;
  }
  performChunkPriorityUpdate(chunk) {
    if (chunk.priorityTier === chunk.newPriorityTier && chunk.priority === chunk.newPriority) {
      chunk.newPriorityTier = ChunkPriorityTier.RECENT;
      chunk.newPriority = Number.NEGATIVE_INFINITY;
      return;
    }
    if (DEBUG_CHUNK_UPDATES) {
      console.log(
        `${chunk}: changed priority ${chunk.priorityTier}:${chunk.priority} -> ${chunk.newPriorityTier}:${chunk.newPriority}`
      );
    }
    this.removeChunkFromQueues_(chunk);
    chunk.updatePriorityProperties();
    if (chunk.state === ChunkState.NEW) {
      chunk.state = ChunkState.QUEUED;
      this.adjustCapacitiesForChunk(chunk, true);
    }
    this.addChunkToQueues_(chunk);
  }
  updateChunkState(chunk, newState) {
    if (newState === chunk.state) {
      return;
    }
    if (DEBUG_CHUNK_UPDATES) {
      console.log(
        `${chunk}: changed state ${ChunkState[chunk.state]} -> ${ChunkState[newState]}`
      );
    }
    this.adjustCapacitiesForChunk(chunk, false);
    this.removeChunkFromQueues_(chunk);
    chunk.state = newState;
    this.adjustCapacitiesForChunk(chunk, true);
    this.addChunkToQueues_(chunk);
    this.scheduleUpdate();
  }
  markRecentlyUsed(chunk) {
    this.removeChunkFromQueues_(chunk);
    this.addChunkToQueues_(chunk);
  }
  processGPUPromotions_() {
    const queueManager = this;
    function evictFromGPUMemory(chunk) {
      queueManager.freeChunkGPUMemory(chunk);
      chunk.source.chunkManager.queueManager.updateChunkState(
        chunk,
        ChunkState.SYSTEM_MEMORY
      );
    }
    const promotionCandidates = this.gpuMemoryPromotionQueue.candidates();
    const evictionCandidates = this.gpuMemoryEvictionQueue.candidates();
    const capacity = this.gpuMemoryCapacity;
    while (true) {
      const promotionCandidate = promotionCandidates.next().value;
      if (promotionCandidate === void 0) {
        break;
      }
      const priorityTier = promotionCandidate.priorityTier;
      const priority = promotionCandidate.priority;
      if (!tryToFreeCapacity(
        promotionCandidate.gpuMemoryBytes,
        capacity,
        priorityTier,
        priority,
        evictionCandidates,
        evictFromGPUMemory
      )) {
        break;
      }
      this.copyChunkToGPU(promotionCandidate);
      this.updateChunkState(promotionCandidate, ChunkState.GPU_MEMORY);
    }
  }
  freeChunkGPUMemory(chunk) {
    ++this.gpuMemoryGeneration;
    this.rpc.invoke("Chunk.update", {
      id: chunk.key,
      state: ChunkState.SYSTEM_MEMORY,
      source: chunk.source.rpcId
    });
  }
  freeChunkSystemMemory(chunk) {
    if (chunk.state === ChunkState.SYSTEM_MEMORY_WORKER) {
      chunk.freeSystemMemory();
    } else {
      this.rpc.invoke("Chunk.update", {
        id: chunk.key,
        state: ChunkState.EXPIRED,
        source: chunk.source.rpcId
      });
    }
  }
  retrieveChunkData(chunk) {
    return this.rpc.promiseInvoke("Chunk.retrieve", {
      key: chunk.key,
      source: chunk.source.rpcId
    });
  }
  copyChunkToGPU(chunk) {
    ++this.gpuMemoryGeneration;
    const rpc2 = this.rpc;
    if (chunk.state === ChunkState.SYSTEM_MEMORY) {
      rpc2.invoke("Chunk.update", {
        id: chunk.key,
        source: chunk.source.rpcId,
        state: ChunkState.GPU_MEMORY
      });
    } else {
      const msg = {};
      const transfers = [];
      chunk.serialize(msg, transfers);
      msg.state = ChunkState.GPU_MEMORY;
      rpc2.invoke("Chunk.update", msg, transfers);
    }
  }
  moveChunkToFrontend(chunk) {
    const rpc2 = this.rpc;
    const msg = {};
    const transfers = [];
    chunk.serialize(msg, transfers);
    msg.state = ChunkState.SYSTEM_MEMORY;
    rpc2.invoke("Chunk.update", msg, transfers);
  }
  processQueuePromotions_() {
    const evict = (chunk) => {
      switch (chunk.state) {
        case ChunkState.DOWNLOADING:
          cancelChunkDownload(chunk);
          break;
        case ChunkState.GPU_MEMORY:
          this.freeChunkGPUMemory(chunk);
        // fallthrough
        case ChunkState.SYSTEM_MEMORY_WORKER:
        case ChunkState.SYSTEM_MEMORY:
          this.freeChunkSystemMemory(chunk);
          break;
      }
      this.updateChunkState(chunk, ChunkState.QUEUED);
    };
    const promotionLambda = (promotionCandidates, evictionCandidates, capacity) => {
      const systemMemoryEvictionCandidates = this.systemMemoryEvictionQueue.candidates();
      const systemMemoryCapacity = this.systemMemoryCapacity;
      while (true) {
        const promotionCandidateResult = promotionCandidates.next();
        if (promotionCandidateResult.done) {
          return;
        }
        const promotionCandidate = promotionCandidateResult.value;
        const size = 0;
        const priorityTier = promotionCandidate.priorityTier;
        const priority = promotionCandidate.priority;
        if (!tryToFreeCapacity(
          size,
          capacity,
          priorityTier,
          priority,
          evictionCandidates,
          evict
        )) {
          return;
        }
        if (!tryToFreeCapacity(
          size,
          systemMemoryCapacity,
          priorityTier,
          priority,
          systemMemoryEvictionCandidates,
          evict
        )) {
          return;
        }
        this.updateChunkState(promotionCandidate, ChunkState.DOWNLOADING);
        startChunkDownload(promotionCandidate);
      }
    };
    for (let sourceQueueLevel = 0; sourceQueueLevel < numSourceQueueLevels; ++sourceQueueLevel) {
      promotionLambda(
        this.queuedDownloadPromotionQueue[sourceQueueLevel].candidates(),
        this.downloadEvictionQueue[sourceQueueLevel].candidates(),
        this.downloadCapacity[sourceQueueLevel]
      );
    }
    promotionLambda(
      this.queuedComputePromotionQueue.candidates(),
      this.computeEvictionQueue.candidates(),
      this.computeCapacity
    );
  }
  process() {
    if (!this.updatePending) {
      return;
    }
    this.updatePending = null;
    const gpuMemoryGeneration = this.gpuMemoryGeneration;
    this.processGPUPromotions_();
    this.processQueuePromotions_();
    this.logStatistics();
    if (this.gpuMemoryGeneration !== gpuMemoryGeneration) {
      this.gpuMemoryChanged.dispatch();
    }
  }
  logStatistics() {
    if (DEBUG_CHUNK_UPDATES) {
      console.log(
        `[Chunk status] QUEUED: ${this.numQueued}, FAILED: ${this.numFailed}, DOWNLOAD: ${this.downloadCapacity}, MEM: ${this.systemMemoryCapacity}, GPU: ${this.gpuMemoryCapacity}`
      );
    }
  }
  invalidateSourceCache(source) {
    for (const chunk of source.chunks.values()) {
      switch (chunk.state) {
        case ChunkState.DOWNLOADING:
          cancelChunkDownload(chunk);
          break;
        case ChunkState.SYSTEM_MEMORY_WORKER:
          chunk.freeSystemMemory();
          break;
      }
      this.updateChunkState(chunk, ChunkState.QUEUED);
    }
    this.rpc.invoke("Chunk.update", { source: source.rpcId });
    this.scheduleUpdate();
  }
};
ChunkQueueManager = __decorateClass2([
  registerSharedObject(CHUNK_QUEUE_MANAGER_RPC_ID)
], ChunkQueueManager);
var ChunkRenderLayerBackend = class extends SharedObjectCounterpart {
  chunkManagerGeneration = -1;
  numVisibleChunksNeeded = 0;
  numVisibleChunksAvailable = 0;
  numPrefetchChunksNeeded = 0;
  numPrefetchChunksAvailable = 0;
};
var LAYER_CHUNK_STATISTICS_INTERVAL = 200;
var ChunkManager = class extends SharedObjectCounterpart {
  queueManager;
  /**
   * Array of chunks within each existing priority tier.
   */
  existingTierChunks = [];
  /**
   * Array of chunks whose new priorities have not yet been reflected in the
   * queue states.
   */
  newTierChunks = [];
  // Should be `number|null`, but marked `any` to workaround `@types/node` being pulled in.
  updatePending = null;
  recomputeChunkPriorities = new NullarySignal();
  /**
   * Dispatched immediately after recomputeChunkPriorities is dispatched.
   * This signal should be used for handlers that depend on the result of another handler.
   */
  recomputeChunkPrioritiesLate = new NullarySignal();
  memoize = new StringMemoize();
  layers = [];
  sendLayerChunkStatistics = this.registerCancellable(
    throttle_default(() => {
      this.rpc.invoke(CHUNK_LAYER_STATISTICS_RPC_ID, {
        id: this.rpcId,
        layers: this.layers.map((layer) => ({
          id: layer.rpcId,
          numVisibleChunksAvailable: layer.numVisibleChunksAvailable,
          numVisibleChunksNeeded: layer.numVisibleChunksNeeded,
          numPrefetchChunksAvailable: layer.numPrefetchChunksAvailable,
          numPrefetchChunksNeeded: layer.numPrefetchChunksNeeded
        }))
      });
    }, LAYER_CHUNK_STATISTICS_INTERVAL)
  );
  constructor(rpc2, options) {
    super(rpc2, options);
    this.queueManager = rpc2.get(options.chunkQueueManager).addRef();
    this.registerDisposer(
      this.queueManager.gpuMemoryChanged.add(
        this.registerCancellable(
          throttle_default(
            () => this.scheduleUpdateChunkPriorities(),
            LAYER_CHUNK_STATISTICS_INTERVAL,
            { leading: false, trailing: true }
          )
        )
      )
    );
    for (let tier = ChunkPriorityTier.FIRST_TIER; tier <= ChunkPriorityTier.LAST_TIER; ++tier) {
      if (tier === ChunkPriorityTier.RECENT) {
        continue;
      }
      this.existingTierChunks[tier] = [];
    }
  }
  scheduleUpdateChunkPriorities() {
    if (this.updatePending === null) {
      this.updatePending = setTimeout(
        this.recomputeChunkPriorities_.bind(this),
        0
      );
    }
  }
  registerLayer(layer) {
    const generation = this.recomputeChunkPriorities.count;
    if (layer.chunkManagerGeneration !== generation) {
      layer.chunkManagerGeneration = generation;
      this.layers.push(layer);
      layer.numVisibleChunksAvailable = 0;
      layer.numVisibleChunksNeeded = 0;
      layer.numPrefetchChunksAvailable = 0;
      layer.numPrefetchChunksNeeded = 0;
    }
  }
  recomputeChunkPriorities_() {
    this.updatePending = null;
    this.layers.length = 0;
    this.recomputeChunkPriorities.dispatch();
    this.recomputeChunkPrioritiesLate.dispatch();
    this.updateQueueState([
      ChunkPriorityTier.VISIBLE,
      ChunkPriorityTier.PREFETCH
    ]);
    this.sendLayerChunkStatistics();
  }
  /**
   * @param chunk
   * @param tier New priority tier.  Must not equal ChunkPriorityTier.RECENT.
   * @param priority Priority within tier.
   * @param requestedState Indicates requested chunk state.
   */
  requestChunk(chunk, tier, priority, requestedState = ChunkState.GPU_MEMORY) {
    if (Number.isNaN(priority)) {
      return;
    }
    if (tier === ChunkPriorityTier.RECENT) {
      throw new Error("Not going to request a chunk with the RECENT tier");
    }
    chunk.newRequestedState = Math.min(chunk.newRequestedState, requestedState);
    if (chunk.newPriorityTier === ChunkPriorityTier.RECENT) {
      this.newTierChunks.push(chunk);
    }
    const newPriorityTier = chunk.newPriorityTier;
    if (tier < newPriorityTier || tier === newPriorityTier && priority > chunk.newPriority) {
      chunk.newPriorityTier = tier;
      chunk.newPriority = priority;
    }
  }
  /**
   * Update queue state to reflect updated contents of the specified priority tiers.  Existing
   * chunks within those tiers not present in this.newTierChunks will be moved to the RECENT tier
   * (and removed if in the QUEUED state).
   */
  updateQueueState(tiers) {
    const existingTierChunks = this.existingTierChunks;
    const queueManager = this.queueManager;
    for (const tier of tiers) {
      const chunks = existingTierChunks[tier];
      if (DEBUG_CHUNK_UPDATES) {
        console.log(
          `existingTierChunks[${ChunkPriorityTier[tier]}].length=${chunks.length}`
        );
      }
      for (const chunk of chunks) {
        if (chunk.newPriorityTier === ChunkPriorityTier.RECENT) {
          queueManager.performChunkPriorityUpdate(chunk);
        }
      }
      chunks.length = 0;
    }
    const newTierChunks = this.newTierChunks;
    for (const chunk of newTierChunks) {
      queueManager.performChunkPriorityUpdate(chunk);
      existingTierChunks[chunk.priorityTier].push(chunk);
    }
    if (DEBUG_CHUNK_UPDATES) {
      console.log(
        `updateQueueState: newTierChunks.length = ${newTierChunks.length}`
      );
    }
    newTierChunks.length = 0;
    this.queueManager.scheduleUpdate();
  }
};
ChunkManager = __decorateClass2([
  registerSharedObject(CHUNK_MANAGER_RPC_ID)
], ChunkManager);
function WithParameters(Base, parametersConstructor) {
  let C = class extends Base {
    parameters;
    constructor(...args) {
      super(...args);
      const options = args[1];
      this.parameters = options.parameters;
    }
  };
  C = __decorateClass2([
    registerSharedObjectOwner(parametersConstructor.RPC_ID)
  ], C);
  return C;
}
function withChunkManager(Base) {
  return class extends Base {
    chunkManager;
    constructor(...args) {
      super(...args);
      const rpc2 = args[0];
      const options = args[1];
      this.chunkManager = rpc2.get(options.chunkManager);
    }
  };
}
registerRPC(CHUNK_SOURCE_INVALIDATE_RPC_ID, function(x) {
  const source = this.get(x.id);
  source.chunkManager.queueManager.invalidateSourceCache(source);
});
registerPromiseRPC(
  REQUEST_CHUNK_STATISTICS_RPC_ID,
  function(x) {
    const queue = this.get(x.queue);
    const results = /* @__PURE__ */ new Map();
    for (const source of queue.sources) {
      results.set(source.rpcId, source.statistics);
    }
    return Promise.resolve({ value: results });
  }
);

// node_modules/neuroglancer/lib/kvstore/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/credentials_provider/shared_counterpart.js
init_legacy_browser();

// node_modules/neuroglancer/lib/credentials_provider/index.js
init_legacy_browser();
var CredentialsProvider = class extends RefCounted {
};
function makeCachedCredentialsGetter(getUncached) {
  let cachedCredentials;
  let pendingCredentials;
  return async (invalidCredentials, options) => {
    if (pendingCredentials === void 0 || invalidCredentials !== void 0 && (cachedCredentials == null ? void 0 : cachedCredentials.generation) === invalidCredentials.generation) {
      cachedCredentials = void 0;
      pendingCredentials = asyncMemoizeWithProgress(async (progressOptions) => {
        cachedCredentials = await getUncached(
          invalidCredentials,
          progressOptions
        );
        return cachedCredentials;
      });
    }
    return pendingCredentials(options ?? {});
  };
}
var CachingCredentialsManager = class extends RefCounted {
  constructor(base) {
    super();
    this.base = base;
  }
  memoize = new StringMemoize();
  getCredentialsProvider(key, parameters) {
    return this.memoize.get(
      { key, parameters },
      () => this.registerDisposer(
        this.base.getCredentialsProvider(key, parameters).addRef()
      )
    );
  }
};

// node_modules/neuroglancer/lib/credentials_provider/shared_common.js
init_legacy_browser();
var CREDENTIALS_PROVIDER_RPC_ID = "CredentialsProvider";
var CREDENTIALS_PROVIDER_GET_RPC_ID = "CredentialsProvider.get";
var CREDENTIALS_MANAGER_RPC_ID = "CredentialsManager";
var CREDENTIALS_MANAGER_GET_RPC_ID = "CredentialsManager.get";

// node_modules/neuroglancer/lib/credentials_provider/shared_counterpart.js
var __defProp4 = Object.defineProperty;
var __getOwnPropDesc4 = Object.getOwnPropertyDescriptor;
var __decorateClass3 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc4(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp4(target2, key, result);
  return result;
};
var SharedCredentialsProviderCounterpart = class extends SharedObjectCounterpart {
  get = makeCachedCredentialsGetter(
    (invalidCredentials, options) => this.rpc.promiseInvoke(
      CREDENTIALS_PROVIDER_GET_RPC_ID,
      { providerId: this.rpcId, invalidCredentials },
      { signal: options.signal, progressListener: options.progressListener }
    )
  );
};
SharedCredentialsProviderCounterpart = __decorateClass3([
  registerSharedObject(CREDENTIALS_PROVIDER_RPC_ID)
], SharedCredentialsProviderCounterpart);
function WithSharedCredentialsProviderCounterpart() {
  return (Base) => class extends Base {
    credentialsProvider;
    constructor(...args) {
      super(...args);
      const options = args[1];
      this.credentialsProvider = this.rpc.getOptionalRef(options.credentialsProvider);
    }
  };
}
var ProxyCredentialsProvider = class extends CredentialsProvider {
  constructor(rpc2, managerId, key, parameters) {
    super();
    this.rpc = rpc2;
    this.managerId = managerId;
    this.key = key;
    this.parameters = parameters;
  }
  get = makeCachedCredentialsGetter(
    (invalidCredentials, options) => this.rpc.promiseInvoke(
      CREDENTIALS_MANAGER_GET_RPC_ID,
      {
        managerId: this.managerId,
        key: this.key,
        parameters: this.parameters,
        invalidCredentials
      },
      { signal: options.signal, progressListener: options.progressListener }
    )
  );
};
var SharedCredentialsManagerCounterpart = class extends SharedObjectCounterpart {
  impl = new CachingCredentialsManager(this.makeBaseCredentialsManager());
  makeBaseCredentialsManager() {
    return {
      getCredentialsProvider: (key, parameters) => new ProxyCredentialsProvider(
        this.rpc,
        this.rpcId,
        key,
        parameters
      )
    };
  }
  getCredentialsProvider(key, parameters) {
    return this.impl.getCredentialsProvider(key, parameters);
  }
};
SharedCredentialsManagerCounterpart = __decorateClass3([
  registerSharedObject(CREDENTIALS_MANAGER_RPC_ID)
], SharedCredentialsManagerCounterpart);

// node_modules/neuroglancer/lib/kvstore/context.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/auto_detect.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/index.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/string.js
init_legacy_browser();
function defaultStringCompare(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

// node_modules/neuroglancer/lib/kvstore/index.js
var NotFoundError = class extends Error {
  constructor(handle, options) {
    super(`${handle.getUrl()} not found`, options);
  }
};
async function readKvStore(store, key, options = {}) {
  return readFileHandle(new KvStoreFileHandle(store, key), options);
}
async function readFileHandle(handle, options = {}) {
  const response = await handle.read(options);
  if ((options == null ? void 0 : options.throwIfMissing) === true) {
    if (response === void 0) {
      throw new NotFoundError(handle);
    }
  }
  if ((options == null ? void 0 : options.strictByteRange) === true && response !== void 0) {
    const { byteRange } = options;
    const { offset, length: length6 } = response;
    if (byteRange !== void 0) {
      if ("suffixLength" in byteRange ? length6 !== byteRange.suffixLength : offset !== byteRange.offset || length6 !== void 0 && length6 !== byteRange.length) {
        throw new Error(
          `Received truncated response for ${handle.getUrl()}, expected ${JSON.stringify(
            byteRange
          )} but received offset=${offset}, length=${length6}`
        );
      }
    }
  }
  return response;
}
function transformListResponse(response, prefix, kvStore, responseKeys) {
  switch (responseKeys) {
    case "suffix": {
      const offset = prefix.length;
      return {
        directories: response.directories.map((key) => key.substring(offset)),
        entries: response.entries.map(({ key, ...entry }) => ({
          ...entry,
          key: key.substring(offset)
        }))
      };
    }
    case "url": {
      return {
        directories: response.directories.map((key) => kvStore.getUrl(key)),
        entries: response.entries.map(({ key, ...entry }) => ({
          ...entry,
          key: kvStore.getUrl(key)
        }))
      };
    }
    default: {
      return response;
    }
  }
}
async function listKvStore(kvStore, prefix, options = {}) {
  if (!kvStore.list) {
    throw new Error("Listing not supported");
  }
  return transformListResponse(
    await kvStore.list(prefix, options),
    prefix,
    kvStore,
    options.responseKeys
  );
}
var KvStoreFileHandle = class {
  constructor(store, key) {
    this.store = store;
    this.key = key;
  }
  stat(options) {
    return this.store.stat(this.key, options);
  }
  read(options) {
    return this.store.read(this.key, options);
  }
  getUrl() {
    return this.store.getUrl(this.key);
  }
};
function normalizeListResponse(response) {
  response.entries.sort(({ key: a }, { key: b }) => defaultStringCompare(a, b));
  response.directories.sort(defaultStringCompare);
  return response;
}

// node_modules/neuroglancer/lib/kvstore/url.js
init_legacy_browser();
function kvstoreEnsureDirectoryPipelineUrl(url) {
  const m = url.match(
    /^((?:.*?\|)?)([a-zA-Z][a-zA-Z0-9-+.]*)(?:(:[^?#|]*)((?:[?#][^|]*)?))?$/
  );
  if (m === null) {
    throw new Error(`Invalid URL: ${url}`);
  }
  const [, pipelinePrefix, scheme, path, queryAndFragment] = m;
  if (path === void 0) {
    return `${pipelinePrefix}${scheme}:`;
  }
  if (path === ":" || path.endsWith("/")) return url;
  return `${pipelinePrefix}${scheme}${path}/${queryAndFragment ?? ""}`;
}
function finalPipelineUrlComponent(url) {
  const m = url.match(/.*?([^|]*)$/);
  return m[1];
}
var schemePattern = /^(?:([a-zA-Z][a-zA-Z0-9-+.]*):)?(.*)$/;
function parsePipelineUrlComponent(url) {
  const m = url.match(schemePattern);
  const scheme = m[1];
  const suffix = m[2];
  if (scheme === void 0) {
    return { url, scheme: url, suffix: void 0 };
  } else {
    return { url, scheme, suffix };
  }
}
function splitPipelineUrl(url) {
  return url.split("|").map(parsePipelineUrlComponent);
}
function pipelineUrlJoin(baseUrl, ...additionalParts) {
  let [, base, queryAndFragment] = baseUrl.match(/^(.*?[^|?#]*)([^|]*)$/);
  for (let part of additionalParts) {
    if (part.startsWith("/")) {
      part = part.substring(1);
    }
    if (part === "") continue;
    base = kvstoreEnsureDirectoryPipelineUrl(base);
    base += encodePathForUrl(part);
  }
  return base + queryAndFragment;
}
function joinPath(base, ...additionalParts) {
  for (let part of additionalParts) {
    if (part.startsWith("/")) {
      part = part.substring(1);
    }
    if (part === "") continue;
    base = ensurePathIsDirectory(base);
    base += part;
  }
  return base;
}
function ensurePathIsDirectory(path) {
  if (!pathIsDirectory(path)) {
    path += "/";
  }
  return path;
}
function ensureNoQueryOrFragmentParameters(url) {
  const { suffix } = url;
  if (suffix === void 0) return;
  if (suffix.match(/[#?]/)) {
    throw new Error(
      `Invalid URL ${url.url}: query parameters and/or fragment not supported`
    );
  }
}
function ensureEmptyUrlSuffix(url) {
  if (url.suffix) {
    throw new Error(
      `Invalid URL syntax ${JSON.stringify(url.url)}, expected "${url.scheme}:"`
    );
  }
}
function extractQueryAndFragment(url) {
  const [, base, queryAndFragment] = url.match(/^(.*?[^|?#]*)([^|]*)$/);
  return { base, queryAndFragment };
}
function resolveRelativePath(basePath, relativePath) {
  const origBasePath = basePath;
  if (basePath.endsWith("/")) {
    basePath = basePath.substring(0, basePath.length - 1);
  }
  for (const component of relativePath.split("/")) {
    if (component === "" || component === ".") {
      continue;
    }
    if (component === "..") {
      const prevSlash = basePath.lastIndexOf("/");
      if (prevSlash <= 0) {
        throw new Error(
          `Invalid relative path ${JSON.stringify(relativePath)} from base path ${JSON.stringify(origBasePath)}`
        );
      }
      basePath = basePath.substring(0, prevSlash);
      continue;
    }
    if (basePath !== "") {
      basePath += "/";
    }
    basePath += component;
  }
  if (relativePath.endsWith("/")) {
    basePath += "/";
  }
  return basePath;
}
function pathIsDirectory(path) {
  return path === "" || path.endsWith("/");
}
function encodePathForUrl(path) {
  return encodeURI(path).replace(
    /[?#@]/g,
    (c) => `%${c.charCodeAt(0).toString(16).toUpperCase()}`
  );
}
function joinBaseUrlAndPath(baseUrl, path) {
  const { base, queryAndFragment } = extractQueryAndFragment(baseUrl);
  return base + encodePathForUrl(path) + queryAndFragment;
}
function getBaseHttpUrlAndPath(url) {
  const parsed = new URL(url);
  if (parsed.hash) {
    throw new Error("fragment not supported");
  }
  if (parsed.username || parsed.password) {
    throw new Error("basic auth credentials not supported");
  }
  return {
    baseUrl: `${parsed.origin}/${parsed.search}`,
    path: decodeURIComponent(parsed.pathname.substring(1))
  };
}

// node_modules/neuroglancer/lib/kvstore/auto_detect.js
function composeMatchFunctions(specs) {
  return async (options) => {
    const matches = [];
    const results = await Promise.allSettled(
      specs.map((spec) => spec.match(options))
    );
    for (const result of results) {
      if (result.status !== "fulfilled") continue;
      matches.push(...result.value);
    }
    return matches;
  };
}
function composeAutoDetectDirectorySpecs(specs) {
  const fileNames = /* @__PURE__ */ new Set();
  const subDirectories = /* @__PURE__ */ new Set();
  for (const spec of specs) {
    const { fileNames: curFileNames, subDirectories: curSubDirectories } = spec;
    if (curFileNames !== void 0) {
      for (const fileName of curFileNames) {
        fileNames.add(fileName);
      }
    }
    if (curSubDirectories !== void 0) {
      for (const subDirectory of curSubDirectories) {
        subDirectories.add(subDirectory);
      }
    }
  }
  return { fileNames, subDirectories, match: composeMatchFunctions(specs) };
}
function composeAutoDetectFileSpecs(specs) {
  let prefixLength = 0;
  let suffixLength = 0;
  for (const spec of specs) {
    prefixLength = Math.max(prefixLength, spec.prefixLength);
    suffixLength = Math.max(suffixLength, spec.suffixLength);
  }
  return { prefixLength, suffixLength, match: composeMatchFunctions(specs) };
}
var AutoDetectRegistry = class {
  directorySpecs = [];
  fileSpecs = [];
  _directorySpec;
  _fileSpec;
  registerDirectoryFormat(spec) {
    this.directorySpecs.push(spec);
    this._directorySpec = void 0;
  }
  registerFileFormat(spec) {
    this.fileSpecs.push(spec);
    this._fileSpec = void 0;
  }
  copyTo(registry) {
    registry.directorySpecs.push(...this.directorySpecs);
    registry.fileSpecs.push(...this.fileSpecs);
    registry._fileSpec = void 0;
    registry._directorySpec = void 0;
  }
  get directorySpec() {
    return this._directorySpec ?? (this._directorySpec = this.getDirectorySpec());
  }
  getDirectorySpec() {
    return composeAutoDetectDirectorySpecs(this.directorySpecs);
  }
  get fileSpec() {
    return this._fileSpec ?? (this._fileSpec = this.getFileSpec());
  }
  getFileSpec() {
    const { fileSpecs } = this;
    const specs = [...fileSpecs];
    return composeAutoDetectFileSpecs(specs);
  }
};

// node_modules/neuroglancer/lib/kvstore/context.js
var KvStoreContext = class {
  baseKvStoreProviders = /* @__PURE__ */ new Map();
  kvStoreAdapterProviders = /* @__PURE__ */ new Map();
  autoDetectRegistry = new AutoDetectRegistry();
  getKvStore(url) {
    const pipeline = splitPipelineUrl(url);
    let kvStore;
    {
      const basePart = pipeline[0];
      kvStore = this.getBaseKvStoreProvider(basePart).getKvStore(basePart);
    }
    for (let i = 1; i < pipeline.length; ++i) {
      kvStore = this.applyKvStoreAdapterUrl(kvStore, pipeline[i]);
    }
    return kvStore;
  }
  getFileHandle(url) {
    const { store, path } = this.getKvStore(url);
    return new KvStoreFileHandle(store, path);
  }
  getBaseKvStoreProvider(url) {
    const provider = this.baseKvStoreProviders.get(url.scheme);
    if (provider === void 0) {
      const usage = this.describeProtocolUsage(url.scheme);
      let message = `Invalid base kvstore protocol "${url.scheme}:"`;
      if (usage !== void 0) {
        message += `; ${usage}`;
      }
      throw new Error(message);
    }
    return provider;
  }
  getKvStoreAdapterProvider(adapterUrl) {
    const provider = this.kvStoreAdapterProviders.get(adapterUrl.scheme);
    if (provider === void 0) {
      const usage = this.describeProtocolUsage(adapterUrl.scheme);
      let message = `Invalid kvstore adapter protocol "${adapterUrl.scheme}:"`;
      if (usage !== void 0) {
        message += `; ${usage}`;
      }
      message += `; supported schemes: ${JSON.stringify(Array.from(this.kvStoreAdapterProviders.keys()))}`;
      throw new Error(message);
    }
    return provider;
  }
  applyKvStoreAdapterUrl(base, adapterUrl) {
    return this.getKvStoreAdapterProvider(adapterUrl).getKvStore(
      adapterUrl,
      base
    );
  }
  // Describes valid uses of `protocol`, for error messages indicating an
  // invalid protocol.  If the protocol is unknown, returns `undefined`.
  describeProtocolUsage(protocol) {
    if (this.baseKvStoreProviders.has(protocol)) {
      return `"${protocol}:" may only be used as a base kvstore protocol`;
    }
    if (this.kvStoreAdapterProviders.has(protocol)) {
      return `"${protocol}:" may only be used as a kvstore adapter protocol`;
    }
    return void 0;
  }
  stat(url, options = {}) {
    const kvStore = this.getKvStore(url);
    return kvStore.store.stat(kvStore.path, options);
  }
  read(url, options = {}) {
    const kvStore = this.getKvStore(url);
    return readKvStore(kvStore.store, kvStore.path, options);
  }
  list(urlPrefix, options = {}) {
    const kvStore = this.getKvStore(urlPrefix);
    return listKvStore(kvStore.store, kvStore.path, options);
  }
  resolveRelativePath(baseUrl, relativePath) {
    const kvStore = this.getKvStore(baseUrl);
    return kvStore.store.getUrl(
      resolveRelativePath(kvStore.path, relativePath)
    );
  }
};

// node_modules/neuroglancer/lib/kvstore/register.js
init_legacy_browser();
var KvStoreProviderRegistry = class {
  baseKvStoreProviders = [];
  kvStoreAdapterProviders = [];
  autoDetectRegistry = new AutoDetectRegistry();
  registerBaseKvStoreProvider(provider) {
    this.baseKvStoreProviders.push(provider);
  }
  registerKvStoreAdapterProvider(provider) {
    this.kvStoreAdapterProviders.push(provider);
  }
  applyToContext(context) {
    const { kvStoreContext } = context;
    for (const key of [
      "baseKvStoreProviders",
      "kvStoreAdapterProviders"
    ]) {
      const map2 = kvStoreContext[key];
      for (const providerFactory of this[key]) {
        const provider = providerFactory(context);
        const { scheme } = provider;
        if (map2.has(scheme)) {
          throw new Error(`Duplicate kvstore scheme ${scheme}`);
        }
        map2.set(scheme, provider);
      }
    }
    this.autoDetectRegistry.copyTo(context.kvStoreContext.autoDetectRegistry);
  }
};
var frontendBackendIsomorphicKvStoreProviderRegistry = new KvStoreProviderRegistry();

// node_modules/neuroglancer/lib/kvstore/shared_common.js
init_legacy_browser();
var SHARED_KVSTORE_CONTEXT_RPC_ID = "SharedKvStoreContext";
var STAT_RPC_ID = "SharedKvStoreContext.stat";
var READ_RPC_ID = "SharedKvStoreContext.read";
var LIST_RPC_ID = "SharedKvStoreContext.list";
var COMPLETE_URL_RPC_ID = "SharedKvStoreContext.completeUrl";

// node_modules/neuroglancer/lib/kvstore/backend.js
var __defProp5 = Object.defineProperty;
var __getOwnPropDesc5 = Object.getOwnPropertyDescriptor;
var __decorateClass4 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc5(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp5(target2, key, result);
  return result;
};
var SharedKvStoreContextCounterpart = class extends SharedObjectCounterpart {
  kvStoreContext;
  chunkManager;
  credentialsManager;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.chunkManager = rpc2.get(options.chunkManager);
    this.credentialsManager = rpc2.get(
      options.credentialsManager
    );
    this.kvStoreContext = new KvStoreContext();
    frontendBackendIsomorphicKvStoreProviderRegistry.applyToContext(this);
    backendOnlyKvStoreProviderRegistry.applyToContext(this);
  }
};
SharedKvStoreContextCounterpart = __decorateClass4([
  registerSharedObject(SHARED_KVSTORE_CONTEXT_RPC_ID)
], SharedKvStoreContextCounterpart);
var backendOnlyKvStoreProviderRegistry = new KvStoreProviderRegistry();
function WithSharedKvStoreContextCounterpart(Base) {
  return class extends Base {
    sharedKvStoreContext;
    constructor(...args) {
      super(...args);
      const options = args[1];
      this.sharedKvStoreContext = this.rpc.get(options.sharedKvStoreContext);
    }
  };
}

// node_modules/neuroglancer/lib/sliceview/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/render_layer_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/render_layer_common.js
init_legacy_browser();
var RENDERED_VIEW_ADD_LAYER_RPC_ID = "rendered_view.addLayer";
var RENDERED_VIEW_REMOVE_LAYER_RPC_ID = "rendered_view.removeLayer";
var PROJECTION_PARAMETERS_RPC_ID = "SharedProjectionParameters";
var PROJECTION_PARAMETERS_CHANGED_RPC_METHOD_ID = "SharedProjectionParameters.changed";

// node_modules/neuroglancer/lib/render_layer_backend.js
var __defProp6 = Object.defineProperty;
var __getOwnPropDesc6 = Object.getOwnPropertyDescriptor;
var __decorateClass5 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc6(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp6(target2, key, result);
  return result;
};
var RenderLayerBackendAttachment = class extends RefCounted {
  constructor(view) {
    super();
    this.view = view;
  }
  state = void 0;
};
var RenderLayerBackend = class extends ChunkRenderLayerBackend {
  attachments = /* @__PURE__ */ new Map();
  attach(attachment) {
    attachment;
  }
};
registerRPC(RENDERED_VIEW_ADD_LAYER_RPC_ID, function(x) {
  const view = this.get(x.view);
  const layer = this.get(x.layer);
  const attachment = new RenderLayerBackendAttachment(view);
  layer.attachments.set(view, attachment);
  layer.attach(attachment);
});
registerRPC(RENDERED_VIEW_REMOVE_LAYER_RPC_ID, function(x) {
  const view = this.get(x.view);
  const layer = this.get(x.layer);
  const attachment = layer.attachments.get(view);
  layer.attachments.delete(view);
  attachment.dispose();
});
var SharedProjectionParametersBackend = class extends SharedObjectCounterpart {
  value;
  oldValue;
  changed = new Signal();
  constructor(rpc2, options) {
    super(rpc2, options);
    this.value = options.value;
    this.oldValue = Object.assign({}, this.value);
  }
};
SharedProjectionParametersBackend = __decorateClass5([
  registerSharedObject(PROJECTION_PARAMETERS_RPC_ID)
], SharedProjectionParametersBackend);
registerRPC(PROJECTION_PARAMETERS_CHANGED_RPC_METHOD_ID, function(x) {
  const obj = this.get(x.id);
  const { value, oldValue } = obj;
  Object.assign(oldValue, value);
  Object.assign(value, x.value);
  obj.changed.dispatch(oldValue, value);
});

// node_modules/neuroglancer/lib/sliceview/base.js
init_legacy_browser();

// node_modules/neuroglancer/lib/navigation_state.js
init_legacy_browser();

// node_modules/neuroglancer/lib/coordinate_transform.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/matrix.js
init_legacy_browser();
function identity4(a, lda, n) {
  for (let i = 0; i < n; ++i) {
    const start = lda * i;
    a.fill(0, start, start + n);
    a[start + i] = 1;
  }
  return a;
}
function createIdentity(c, rows, cols = rows) {
  return identity4(new c(rows * cols), rows, Math.min(rows, cols));
}
function copy6(b, ldb, a, lda, m, n) {
  for (let col = 0; col < n; ++col) {
    const aOff = col * lda;
    const bOff = col * ldb;
    for (let row = 0; row < m; ++row) {
      b[bOff + row] = a[aOff + row];
    }
  }
  return b;
}
var pivots;
function inverseInplace(a, lda, n) {
  let determinant3 = 1;
  if (pivots === void 0 || pivots.length < n) {
    pivots = new Uint32Array(n);
  }
  for (let i = 0; i < n; ++i) {
    pivots[i] = i;
  }
  for (let k = 0; k < n; ++k) {
    const kColOff = lda * k;
    let pivotRow = k;
    {
      let bestPivot = Math.abs(a[kColOff + k]);
      for (let row = k + 1; row < n; ++row) {
        const mag = Math.abs(a[kColOff + row]);
        if (mag > bestPivot) {
          bestPivot = mag;
          pivotRow = row;
        }
      }
    }
    if (k !== pivotRow) {
      determinant3 *= -1;
      for (let col = 0; col < n; ++col) {
        const off = lda * col;
        const temp = a[off + k];
        a[off + k] = a[off + pivotRow];
        a[off + pivotRow] = temp;
      }
      {
        const tempPivot = pivots[k];
        pivots[k] = pivots[pivotRow];
        pivots[pivotRow] = tempPivot;
      }
    }
    const pivotValue = a[kColOff + k];
    const pivotInv = 1 / pivotValue;
    determinant3 *= pivotValue;
    for (let j = 0; j < n; ++j) {
      a[lda * j + k] *= pivotInv;
    }
    a[kColOff + k] = pivotInv;
    for (let row = 0; row < n; ++row) {
      if (row === k) continue;
      const factor = -a[lda * k + row];
      for (let j = 0; j < n; ++j) {
        const jColOff = lda * j;
        a[jColOff + row] += factor * a[jColOff + k];
      }
      a[lda * k + row] = factor * pivotInv;
    }
  }
  for (let col = 0; col < n; ++col) {
    let targetCol = pivots[col];
    while (targetCol !== col) {
      const colOff = lda * col;
      const targetColOff = lda * targetCol;
      for (let i = 0; i < n; ++i) {
        const off1 = colOff + i;
        const off2 = targetColOff + i;
        const temp2 = a[off1];
        a[off1] = a[off2];
        a[off2] = temp2;
      }
      const temp = pivots[col] = pivots[targetCol];
      pivots[targetCol] = targetCol;
      targetCol = temp;
    }
  }
  return determinant3;
}
function inverse3(b, ldb, a, lda, n) {
  copy6(b, ldb, a, lda, n, n);
  return inverseInplace(b, ldb, n);
}

// node_modules/neuroglancer/lib/util/si_units.js
init_legacy_browser();
var preferredSiPrefixes = [
  { prefix: "Y", exponent: 24, longPrefix: "yotta" },
  { prefix: "Z", exponent: 21, longPrefix: "zetta" },
  { prefix: "E", exponent: 18, longPrefix: "exa" },
  { prefix: "P", exponent: 15, longPrefix: "peta" },
  { prefix: "T", exponent: 12, longPrefix: "tera" },
  { prefix: "G", exponent: 9, longPrefix: "giga" },
  { prefix: "M", exponent: 6, longPrefix: "mega" },
  { prefix: "k", exponent: 3, longPrefix: "kilo" },
  { prefix: "", exponent: 0, longPrefix: "" },
  { prefix: "m", exponent: -3, longPrefix: "milli" },
  { prefix: "\xB5", exponent: -6, longPrefix: "micro" },
  { prefix: "n", exponent: -9, longPrefix: "nano" },
  { prefix: "p", exponent: -12, longPrefix: "pico" },
  { prefix: "f", exponent: -15, longPrefix: "femto" },
  { prefix: "a", exponent: -18, longPrefix: "atto" },
  { prefix: "z", exponent: -21, longPrefix: "zepto" },
  { prefix: "y", exponent: -24, longPrefix: "yocto" }
];
var allSiPrefixes = [
  ...preferredSiPrefixes,
  { prefix: "h", exponent: 2, longPrefix: "hecto" },
  { prefix: "da", exponent: 1, longPrefix: "deca" },
  { prefix: "d", exponent: -1, longPrefix: "deci" },
  { prefix: "c", exponent: -2, longPrefix: "centi" }
];
var siPrefixesWithAlternatives = [
  { prefix: "u", exponent: -6 },
  // Also allow "u" for micro
  ...allSiPrefixes
];
var supportedUnits = /* @__PURE__ */ new Map();
supportedUnits.set("", { unit: "", exponent: 0 });
var exponentToPrefix = /* @__PURE__ */ new Map();
for (const { prefix, exponent } of siPrefixesWithAlternatives) {
  exponentToPrefix.set(exponent, prefix);
  for (const unit of ["m", "s", "Hz", "rad/s"]) {
    supportedUnits.set(`${prefix}${unit}`, { unit, exponent });
  }
}

// node_modules/neuroglancer/lib/util/vector.js
init_legacy_browser();
function add6(out, a, b) {
  const rank = out.length;
  for (let i = 0; i < rank; ++i) {
    out[i] = a[i] + b[i];
  }
  return out;
}
function multiply6(out, a, b) {
  const rank = out.length;
  for (let i = 0; i < rank; ++i) {
    out[i] = a[i] * b[i];
  }
  return out;
}
function prod(array2) {
  let result = 1;
  for (let i = 0, length6 = array2.length; i < length6; ++i) {
    result *= array2[i];
  }
  return result;
}
function min3(out, a, b) {
  const rank = out.length;
  for (let i = 0; i < rank; ++i) {
    out[i] = Math.min(a[i], b[i]);
  }
  return out;
}
function max3(out, a, b) {
  const rank = out.length;
  for (let i = 0; i < rank; ++i) {
    out[i] = Math.max(a[i], b[i]);
  }
  return out;
}
var kEmptyFloat32Vec = new Float32Array(0);
var kEmptyFloat64Vec = new Float64Array(0);
var kFloat64Vec3Of1 = Float64Array.of(1, 1, 1);

// node_modules/neuroglancer/lib/coordinate_transform.js
function makeCoordinateSpace(space) {
  const { names, units, scales } = space;
  const {
    valid = true,
    rank = names.length,
    timestamps = names.map(() => Number.NEGATIVE_INFINITY),
    ids = names.map((_, i) => -i),
    boundingBoxes = []
  } = space;
  const { coordinateArrays = new Array(rank) } = space;
  const { bounds = computeCombinedBounds(boundingBoxes, rank) } = space;
  return {
    valid,
    rank,
    names,
    timestamps,
    ids,
    units,
    scales,
    boundingBoxes,
    bounds,
    coordinateArrays
  };
}
var emptyInvalidCoordinateSpace = makeCoordinateSpace({
  valid: false,
  names: [],
  units: [],
  scales: kEmptyFloat64Vec,
  boundingBoxes: []
});
var emptyValidCoordinateSpace = makeCoordinateSpace({
  valid: true,
  names: [],
  units: [],
  scales: kEmptyFloat64Vec,
  boundingBoxes: []
});
function computeCombinedLowerUpperBound(boundingBox, outputDimension, outputRank) {
  const {
    box: { lowerBounds: baseLowerBounds, upperBounds: baseUpperBounds },
    transform: transform2
  } = boundingBox;
  const inputRank = baseLowerBounds.length;
  const stride = outputRank;
  const offset = transform2[stride * inputRank + outputDimension];
  let targetLower = offset;
  let targetUpper = offset;
  let hasCoefficient = false;
  for (let inputDim = 0; inputDim < inputRank; ++inputDim) {
    const c = transform2[stride * inputDim + outputDimension];
    if (c === 0) continue;
    const lower = c * baseLowerBounds[inputDim];
    const upper = c * baseUpperBounds[inputDim];
    targetLower += Math.min(lower, upper);
    targetUpper += Math.max(lower, upper);
    hasCoefficient = true;
  }
  if (!hasCoefficient) return void 0;
  return { lower: targetLower, upper: targetUpper };
}
var INTEGER_BOUNDS_EPSILON = 1e-3;
function computeCombinedBounds(boundingBoxes, outputRank) {
  const lowerBounds = new Float64Array(outputRank);
  const upperBounds = new Float64Array(outputRank);
  lowerBounds.fill(Number.NEGATIVE_INFINITY);
  upperBounds.fill(Number.POSITIVE_INFINITY);
  const halfIntegerBounds = new Array(outputRank);
  halfIntegerBounds.fill(0);
  const integerBounds = new Array(outputRank);
  integerBounds.fill(0);
  for (const boundingBox of boundingBoxes) {
    for (let outputDim = 0; outputDim < outputRank; ++outputDim) {
      const result = computeCombinedLowerUpperBound(
        boundingBox,
        outputDim,
        outputRank
      );
      if (result === void 0) continue;
      let { lower: targetLower, upper: targetUpper } = result;
      if (Number.isFinite(targetLower) && Number.isFinite(targetUpper)) {
        let lowerRound;
        let upperRound;
        let lowerFloor;
        let upperFloor;
        if (Math.abs(targetLower - (lowerRound = Math.round(targetLower))) < INTEGER_BOUNDS_EPSILON && Math.abs(targetUpper - (upperRound = Math.round(targetUpper))) < INTEGER_BOUNDS_EPSILON) {
          ++integerBounds[outputDim];
          targetLower = lowerRound;
          targetUpper = upperRound;
        } else if (Math.abs(targetLower - (lowerFloor = Math.floor(targetLower)) - 0.5) < INTEGER_BOUNDS_EPSILON && Math.abs(targetUpper - (upperFloor = Math.floor(targetUpper)) - 0.5) < INTEGER_BOUNDS_EPSILON) {
          ++halfIntegerBounds[outputDim];
          targetLower = lowerFloor + 0.5;
          targetUpper = upperFloor + 0.5;
        }
      }
      lowerBounds[outputDim] = lowerBounds[outputDim] === Number.NEGATIVE_INFINITY ? targetLower : Math.min(lowerBounds[outputDim], targetLower);
      upperBounds[outputDim] = upperBounds[outputDim] === Number.POSITIVE_INFINITY ? targetUpper : Math.max(upperBounds[outputDim], targetUpper);
    }
  }
  const voxelCenterAtIntegerCoordinates = integerBounds.map(
    (integerCount, i) => {
      const halfIntegerCount = halfIntegerBounds[i];
      return halfIntegerCount > 0 && integerCount === 0;
    }
  );
  return { lowerBounds, upperBounds, voxelCenterAtIntegerCoordinates };
}

// node_modules/neuroglancer/lib/util/trackable.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/trackable_enum.js
init_legacy_browser();

// node_modules/neuroglancer/lib/navigation_state.js
var tempVec32 = vec3_exports.create();
var tempQuat = quat_exports.create();
function displayDimensionRenderInfosEqual(a, b) {
  return arraysEqual(a.globalDimensionNames, b.globalDimensionNames) && arraysEqual(a.displayDimensionIndices, b.displayDimensionIndices) && arraysEqual(a.canonicalVoxelFactors, b.canonicalVoxelFactors) && arraysEqual(a.voxelPhysicalScales, b.voxelPhysicalScales) && a.canonicalVoxelPhysicalSize === b.canonicalVoxelPhysicalSize && arraysEqual(a.displayDimensionUnits, b.displayDimensionUnits) && arraysEqual(a.displayDimensionScales, b.displayDimensionScales);
}
function validateDisplayDimensionRenderInfoProperty(obj, expected) {
  const actual = obj.displayDimensionRenderInfo;
  if (actual === expected) return true;
  if (displayDimensionRenderInfosEqual(actual, expected)) {
    obj.displayDimensionRenderInfo = expected;
    return true;
  }
  return false;
}

// node_modules/neuroglancer/lib/projection_parameters.js
init_legacy_browser();

// node_modules/neuroglancer/lib/display_context.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/animation_frame_debounce.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/framerate.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/trackable_screenshot_mode.js
init_legacy_browser();

// node_modules/neuroglancer/lib/webgl/context.js
init_legacy_browser();

// node_modules/neuroglancer/lib/render_coordinate_transform.js
init_legacy_browser();
var zeroRankChannelSpace = {
  channelCoordinateSpace: emptyValidCoordinateSpace,
  shape: new Uint32Array(0),
  numChannels: 1,
  coordinates: new Uint32Array(0)
};
function getChunkPositionFromCombinedGlobalLocalPositions(chunkPosition, globalPosition, localPosition, layerRank, combinedGlobalLocalToChunkTransform) {
  const globalRank = globalPosition.length;
  const localRank = localPosition.length;
  const rank = chunkPosition.length;
  let valid = true;
  for (let chunkDim = 0; chunkDim < layerRank; ++chunkDim) {
    let off = chunkDim;
    let sum = 0;
    for (let globalDim = 0; globalDim < globalRank; ++globalDim) {
      sum += combinedGlobalLocalToChunkTransform[off + globalDim * layerRank] * globalPosition[globalDim];
    }
    off += globalRank * layerRank;
    for (let localDim = 0; localDim < localRank; ++localDim) {
      sum += combinedGlobalLocalToChunkTransform[off + localDim * layerRank] * localPosition[localDim];
    }
    sum += combinedGlobalLocalToChunkTransform[off + localRank * layerRank];
    if (chunkDim < rank) {
      chunkPosition[chunkDim] = sum;
    } else {
      if (sum < 0 || sum >= 1) {
        valid = false;
      }
    }
  }
  return valid;
}
function get3dModelToDisplaySpaceMatrix(out, displayDimensionRenderInfo, transform2) {
  out.fill(0);
  out[15] = 1;
  let fullRank = true;
  const { displayDimensionIndices } = displayDimensionRenderInfo;
  const { globalToRenderLayerDimensions, modelToRenderLayerTransform } = transform2;
  const layerRank = transform2.rank;
  for (let displayDim = 0; displayDim < 3; ++displayDim) {
    const globalDim = displayDimensionIndices[displayDim];
    if (globalDim === -1) {
      fullRank = false;
      continue;
    }
    const layerDim = globalToRenderLayerDimensions[globalDim];
    if (layerDim === -1) {
      fullRank = false;
      continue;
    }
    out[displayDim + 12] = modelToRenderLayerTransform[layerDim + layerRank * (layerRank + 1)];
    for (let modelDim = 0; modelDim < 3; ++modelDim) {
      out[displayDim + 4 * modelDim] = modelToRenderLayerTransform[layerDim + (layerRank + 1) * modelDim];
    }
  }
  if (!fullRank) {
    const { globalDimensionNames } = displayDimensionRenderInfo;
    const displayDimDesc = Array.from(
      displayDimensionIndices.filter((i) => i !== -1),
      (i) => globalDimensionNames[i]
    ).join(",\xA0");
    throw new Error(
      `Transform from model dimensions (${transform2.modelDimensionNames.join(
        ",\xA0"
      )}) to display dimensions (${displayDimDesc}) does not have full rank`
    );
  }
}

// node_modules/neuroglancer/lib/sliceview/chunk_layout.js
init_legacy_browser();
var ChunkLayout = class _ChunkLayout {
  /**
   * Size of each chunk in "chunk" coordinates.
   */
  size;
  /**
   * Transform from local "chunk" coordinates to global voxel coordinates.
   */
  transform;
  /**
   * Inverse of transform.  Transform from global voxel coordinates to "chunk" coordinates.
   */
  invTransform;
  /**
   * Determinant of `transform`.
   */
  detTransform;
  finiteRank;
  constructor(size, transform2, finiteRank) {
    this.size = vec3_exports.clone(size);
    this.transform = mat4_exports.clone(transform2);
    this.finiteRank = finiteRank;
    const invTransform = mat4_exports.create();
    const det = inverse3(invTransform, 4, transform2, 4, 4);
    if (det === 0) {
      throw new Error("Transform is singular");
    }
    this.invTransform = invTransform;
    this.detTransform = det;
  }
  toObject() {
    return {
      size: this.size,
      transform: this.transform,
      finiteRank: this.finiteRank
    };
  }
  static fromObject(msg) {
    return new _ChunkLayout(msg.size, msg.transform, msg.finiteRank);
  }
  /**
   * Transform global spatial coordinates to local spatial coordinates.
   */
  globalToLocalSpatial(out, globalSpatial) {
    return vec3_exports.transformMat4(out, globalSpatial, this.invTransform);
  }
  localSpatialVectorToGlobal(out, localVector) {
    return transformVectorByMat4(out, localVector, this.transform);
  }
  /**
   * Returns the unnormalized normal vector.
   */
  globalToLocalNormal(globalNormal, localNormal) {
    return transformVectorByMat4Transpose(
      globalNormal,
      localNormal,
      this.transform
    );
  }
};

// node_modules/neuroglancer/lib/util/data_type.js
init_legacy_browser();
var DataType = /* @__PURE__ */ ((DataType2) => {
  DataType2[DataType2["UINT8"] = 0] = "UINT8";
  DataType2[DataType2["INT8"] = 1] = "INT8";
  DataType2[DataType2["UINT16"] = 2] = "UINT16";
  DataType2[DataType2["INT16"] = 3] = "INT16";
  DataType2[DataType2["UINT32"] = 4] = "UINT32";
  DataType2[DataType2["INT32"] = 5] = "INT32";
  DataType2[DataType2["UINT64"] = 6] = "UINT64";
  DataType2[DataType2["FLOAT32"] = 7] = "FLOAT32";
  return DataType2;
})(DataType || {});
var DATA_TYPE_BYTES = {
  [
    0
    /* UINT8 */
  ]: 1,
  [
    1
    /* INT8 */
  ]: 1,
  [
    2
    /* UINT16 */
  ]: 2,
  [
    3
    /* INT16 */
  ]: 2,
  [
    4
    /* UINT32 */
  ]: 4,
  [
    5
    /* INT32 */
  ]: 4,
  [
    6
    /* UINT64 */
  ]: 8,
  [
    7
    /* FLOAT32 */
  ]: 4
};
var DATA_TYPE_ARRAY_CONSTRUCTOR = {
  [
    0
    /* UINT8 */
  ]: Uint8Array,
  [
    1
    /* INT8 */
  ]: Int8Array,
  [
    2
    /* UINT16 */
  ]: Uint16Array,
  [
    3
    /* INT16 */
  ]: Int16Array,
  [
    4
    /* UINT32 */
  ]: Uint32Array,
  [
    5
    /* INT32 */
  ]: Int32Array,
  [
    6
    /* UINT64 */
  ]: BigUint64Array,
  [
    7
    /* FLOAT32 */
  ]: Float32Array
};
function makeDataTypeArrayView(dataType, buffer, byteOffset = 0, byteLength = buffer.byteLength) {
  const bytesPerElement = DATA_TYPE_BYTES[dataType];
  return new DATA_TYPE_ARRAY_CONSTRUCTOR[dataType](
    buffer,
    byteOffset,
    byteLength / bytesPerElement
  );
}

// node_modules/neuroglancer/lib/sliceview/base.js
var DEBUG_VISIBLE_SOURCES = false;
var DEBUG_CHUNK_VISIBILITY = false;
var tempMat4 = mat4_exports.create();
function estimateSliceAreaPerChunk(chunkLayout, viewMatrix) {
  let viewZProjection = 0;
  let chunkVolume = Math.abs(chunkLayout.detTransform);
  const { transform: transform2, size } = chunkLayout;
  for (let i = 0; i < 3; ++i) {
    let sum = 0;
    for (let j = 0; j < 3; ++j) {
      sum += viewMatrix[j * 4 + 2] * transform2[4 * i + j];
    }
    const s = size[i];
    viewZProjection += Math.abs(sum) * s;
    chunkVolume *= s;
  }
  return chunkVolume / viewZProjection;
}
function updateFixedCurPositionInChunks(tsource, globalPosition, localPosition) {
  const { curPositionInChunks, fixedPositionWithinChunk } = tsource;
  const { nonDisplayLowerClipBound, nonDisplayUpperClipBound } = tsource;
  const { rank, chunkDataSize, lowerChunkBound, upperChunkBound } = tsource.source.spec;
  if (!getChunkPositionFromCombinedGlobalLocalPositions(
    curPositionInChunks,
    globalPosition,
    localPosition,
    tsource.layerRank,
    tsource.fixedLayerToChunkTransform
  )) {
    return false;
  }
  const EPSILON2 = 1e-3;
  for (let chunkDim = 0; chunkDim < rank; ++chunkDim) {
    const x = curPositionInChunks[chunkDim];
    if (x < nonDisplayLowerClipBound[chunkDim] - EPSILON2 || x > nonDisplayUpperClipBound[chunkDim] + EPSILON2) {
      if (DEBUG_VISIBLE_SOURCES) {
        console.log(
          "excluding source",
          tsource,
          `because of chunkDim=${chunkDim}, sum=${x}`,
          nonDisplayLowerClipBound,
          nonDisplayUpperClipBound,
          tsource.fixedLayerToChunkTransform
        );
      }
      return false;
    }
    const chunkSize = chunkDataSize[chunkDim];
    const chunk = curPositionInChunks[chunkDim] = Math.min(
      upperChunkBound[chunkDim] - 1,
      Math.max(lowerChunkBound[chunkDim], Math.floor(x / chunkSize))
    );
    fixedPositionWithinChunk[chunkDim] = x - chunk * chunkSize;
  }
  return true;
}
function pickBestAlternativeSource(viewMatrix, alternatives) {
  const numAlternatives = alternatives.length;
  let bestAlternativeIndex = 0;
  if (DEBUG_VISIBLE_SOURCES) {
    console.log(alternatives);
  }
  if (numAlternatives > 1) {
    let bestSliceArea = 0;
    for (let alternativeIndex = 0; alternativeIndex < numAlternatives; ++alternativeIndex) {
      const alternative = alternatives[alternativeIndex];
      const { chunkLayout } = alternative;
      const sliceArea = estimateSliceAreaPerChunk(chunkLayout, viewMatrix);
      if (DEBUG_VISIBLE_SOURCES) {
        console.log(
          `chunksize = ${chunkLayout.size}, sliceArea = ${sliceArea}`
        );
      }
      if (sliceArea > bestSliceArea) {
        bestSliceArea = sliceArea;
        bestAlternativeIndex = alternativeIndex;
      }
    }
  }
  return bestAlternativeIndex;
}
var tempChunkLayout = new ChunkLayout(vec3_exports.create(), mat4_exports.create(), 0);
function visibleSourcesInvalidated(oldValue, newValue) {
  if (oldValue.displayDimensionRenderInfo !== newValue.displayDimensionRenderInfo) {
    return true;
  }
  if (oldValue.pixelSize !== newValue.pixelSize) return true;
  const { viewMatrix: oldViewMatrix } = oldValue;
  const { viewMatrix: newViewMatrix } = newValue;
  for (let i = 0; i < 12; ++i) {
    if (oldViewMatrix[i] !== newViewMatrix[i]) return true;
  }
  return false;
}
var SliceViewBase = class extends SharedObject {
  constructor(projectionParameters) {
    super();
    this.projectionParameters = projectionParameters;
    this.registerDisposer(
      projectionParameters.changed.add((oldValue, newValue) => {
        if (visibleSourcesInvalidated(oldValue, newValue)) {
          this.invalidateVisibleSources();
        }
        this.invalidateVisibleChunks();
      })
    );
  }
  visibleLayers = /* @__PURE__ */ new Map();
  visibleSourcesStale = true;
  invalidateVisibleSources() {
    this.visibleSourcesStale = true;
  }
  invalidateVisibleChunks() {
  }
  /**
   * Computes the list of sources to use for each visible layer, based on the
   * current pixelSize.
   */
  updateVisibleSources() {
    if (!this.visibleSourcesStale) {
      return;
    }
    this.visibleSourcesStale = false;
    const curDisplayDimensionRenderInfo = this.projectionParameters.value.displayDimensionRenderInfo;
    const { visibleLayers } = this;
    for (const [renderLayer, visibleLayerSources] of visibleLayers) {
      const { allSources, visibleSources } = visibleLayerSources;
      visibleSources.length = 0;
      if (allSources.length === 0 || !validateDisplayDimensionRenderInfoProperty(
        visibleLayerSources,
        curDisplayDimensionRenderInfo
      )) {
        continue;
      }
      const preferredOrientationIndex = pickBestAlternativeSource(
        this.projectionParameters.value.viewMatrix,
        allSources.map((x) => x[0])
      );
      const sources = allSources[preferredOrientationIndex];
      for (const source of renderLayer.filterVisibleSources(this, sources)) {
        visibleSources.push(source);
      }
      visibleSources.reverse();
      if (DEBUG_VISIBLE_SOURCES) {
        console.log("visible sources chosen", visibleSources);
      }
    }
  }
};
function* filterVisibleSources(sliceView, renderLayer, sources) {
  const pixelSize = sliceView.projectionParameters.value.pixelSize * 1.1;
  const smallestVoxelSize = sources[0].effectiveVoxelSize;
  const renderScaleTarget = renderLayer.renderScaleTarget.value;
  const canImproveOnVoxelSize = (voxelSize) => {
    const targetSize = pixelSize * renderScaleTarget;
    for (let i = 0; i < 3; ++i) {
      const size = voxelSize[i];
      if (size > targetSize && size > 1.01 * smallestVoxelSize[i]) {
        return true;
      }
    }
    return false;
  };
  const improvesOnPrevVoxelSize = (voxelSize, prevVoxelSize2) => {
    const targetSize = pixelSize * renderScaleTarget;
    for (let i = 0; i < 3; ++i) {
      const size = voxelSize[i];
      const prevSize = prevVoxelSize2[i];
      if (Math.abs(targetSize - size) < Math.abs(targetSize - prevSize) && size < 1.01 * prevSize) {
        return true;
      }
    }
    return false;
  };
  let scaleIndex = sources.length - 1;
  let prevVoxelSize;
  if (DEBUG_VISIBLE_SOURCES) {
    console.log(`Filtering ${sources.length} visible sources`);
  }
  while (true) {
    const transformedSource = sources[scaleIndex];
    if (prevVoxelSize !== void 0 && !improvesOnPrevVoxelSize(
      transformedSource.effectiveVoxelSize,
      prevVoxelSize
    )) {
      if (DEBUG_VISIBLE_SOURCES) {
        console.log(
          `  Stopping at ${scaleIndex} because can't improve on prev voxel size: effectiveVoxelSize=${transformedSource.effectiveVoxelSize} prevVoxelSize=${prevVoxelSize}`
        );
      }
      break;
    }
    yield transformedSource;
    if (scaleIndex === 0) {
      if (DEBUG_VISIBLE_SOURCES) {
        console.log(`  Stopping because scaleIndex=0`);
      }
      break;
    }
    if (!canImproveOnVoxelSize(transformedSource.effectiveVoxelSize)) {
      if (DEBUG_VISIBLE_SOURCES) {
        console.log(
          `Stopping at at ${scaleIndex} because can't improve on voxel size ${transformedSource.effectiveVoxelSize}`
        );
      }
      break;
    }
    prevVoxelSize = transformedSource.effectiveVoxelSize;
    --scaleIndex;
  }
}
var SLICEVIEW_RPC_ID = "SliceView";
var SLICEVIEW_RENDERLAYER_RPC_ID = "sliceview/RenderLayer";
var SLICEVIEW_ADD_VISIBLE_LAYER_RPC_ID = "SliceView.addVisibleLayer";
var SLICEVIEW_REMOVE_VISIBLE_LAYER_RPC_ID = "SliceView.removeVisibleLayer";
var SLICEVIEW_REQUEST_CHUNK_RPC_ID = "ChunkManager.requestChunk";
var tempVisibleVolumetricChunkLower = new Float32Array(3);
var tempVisibleVolumetricChunkUpper = new Float32Array(3);
var tempVisibleVolumetricModelViewProjection = mat4_exports.create();
var tempVisibleVolumetricClippingPlanes = new Float32Array(24);
function forEachVolumetricChunkWithinFrustrum(clippingPlanes, transformedSource, callback, predicate) {
  const lower = tempVisibleVolumetricChunkLower;
  const upper = tempVisibleVolumetricChunkUpper;
  const { lowerChunkDisplayBound, upperChunkDisplayBound } = transformedSource;
  for (let i = 0; i < 3; ++i) {
    lower[i] = Math.max(lower[i], lowerChunkDisplayBound[i]);
    upper[i] = Math.min(upper[i], upperChunkDisplayBound[i]);
  }
  const { curPositionInChunks, chunkDisplayDimensionIndices } = transformedSource;
  function recurse() {
    if (!predicate(
      lower[0],
      lower[1],
      lower[2],
      upper[0],
      upper[1],
      upper[2],
      clippingPlanes
    )) {
      return;
    }
    let splitDim = 0;
    let splitSize = Math.max(0, upper[0] - lower[0]);
    let volume = splitSize;
    for (let i = 1; i < 3; ++i) {
      const size = Math.max(0, upper[i] - lower[i]);
      volume *= size;
      if (size > splitSize) {
        splitSize = size;
        splitDim = i;
      }
    }
    if (volume === 0) return;
    if (volume === 1) {
      curPositionInChunks[chunkDisplayDimensionIndices[0]] = lower[0];
      curPositionInChunks[chunkDisplayDimensionIndices[1]] = lower[1];
      curPositionInChunks[chunkDisplayDimensionIndices[2]] = lower[2];
      callback(lower, clippingPlanes);
      return;
    }
    const prevLower = lower[splitDim];
    const prevUpper = upper[splitDim];
    const splitPoint = Math.floor(0.5 * (prevLower + prevUpper));
    upper[splitDim] = splitPoint;
    recurse();
    upper[splitDim] = prevUpper;
    lower[splitDim] = splitPoint;
    recurse();
    lower[splitDim] = prevLower;
  }
  recurse();
}
function forEachVisibleVolumetricChunk(projectionParameters, localPosition, transformedSource, callback) {
  if (!updateFixedCurPositionInChunks(
    transformedSource,
    projectionParameters.globalPosition,
    localPosition
  )) {
    return;
  }
  const { size: chunkSize } = transformedSource.chunkLayout;
  const modelViewProjection = mat4_exports.multiply(
    tempVisibleVolumetricModelViewProjection,
    projectionParameters.viewProjectionMat,
    transformedSource.chunkLayout.transform
  );
  for (let i = 0; i < 3; ++i) {
    const s = chunkSize[i];
    for (let j = 0; j < 4; ++j) {
      modelViewProjection[4 * i + j] *= s;
    }
  }
  const clippingPlanes = tempVisibleVolumetricClippingPlanes;
  getFrustrumPlanes(clippingPlanes, modelViewProjection);
  const lower = tempVisibleVolumetricChunkLower;
  const upper = tempVisibleVolumetricChunkUpper;
  lower.fill(Number.NEGATIVE_INFINITY);
  upper.fill(Number.POSITIVE_INFINITY);
  forEachVolumetricChunkWithinFrustrum(
    clippingPlanes,
    transformedSource,
    callback,
    isAABBVisible
  );
}
function forEachPlaneIntersectingVolumetricChunk(projectionParameters, localPosition, transformedSource, chunkLayout, callback) {
  if (!updateFixedCurPositionInChunks(
    transformedSource,
    projectionParameters.globalPosition,
    localPosition
  )) {
    return;
  }
  const { size: chunkSize } = chunkLayout;
  const modelViewProjection = mat4_exports.multiply(
    tempVisibleVolumetricModelViewProjection,
    projectionParameters.viewProjectionMat,
    chunkLayout.transform
  );
  for (let i = 0; i < 3; ++i) {
    const s = chunkSize[i];
    for (let j = 0; j < 4; ++j) {
      modelViewProjection[4 * i + j] *= s;
    }
  }
  const { upperChunkDisplayBound } = transformedSource;
  const invModelViewProjection = tempMat4;
  mat4_exports.invert(invModelViewProjection, modelViewProjection);
  const lower = tempVisibleVolumetricChunkLower;
  const upper = tempVisibleVolumetricChunkUpper;
  const BIAS_EPSILON = 1e-4;
  const BOUND_EPSILON = 1e-3;
  for (let i = 0; i < 3; ++i) {
    const c = invModelViewProjection[12 + i] + BIAS_EPSILON / chunkSize[i];
    const xCoeff = Math.abs(invModelViewProjection[i]);
    const yCoeff = Math.abs(invModelViewProjection[4 + i]);
    const upperBound = upperChunkDisplayBound[i];
    let lowerValue = c - xCoeff - yCoeff;
    if (lowerValue >= upperBound && lowerValue < upperBound + BOUND_EPSILON) {
      lowerValue = upperBound - 1;
    } else {
      lowerValue = Math.floor(lowerValue);
    }
    lower[i] = lowerValue;
    upper[i] = Math.floor(c + xCoeff + yCoeff + 1);
  }
  const clippingPlanes = tempVisibleVolumetricClippingPlanes;
  for (let i = 0; i < 3; ++i) {
    const xCoeff = modelViewProjection[4 * i];
    const yCoeff = modelViewProjection[4 * i + 1];
    const zCoeff = modelViewProjection[4 * i + 2];
    clippingPlanes[i] = xCoeff;
    clippingPlanes[4 + i] = -xCoeff;
    clippingPlanes[8 + i] = +yCoeff;
    clippingPlanes[12 + i] = -yCoeff;
    clippingPlanes[16 + i] = +zCoeff;
    clippingPlanes[20 + i] = -zCoeff;
  }
  {
    const i = 3;
    const xCoeff = modelViewProjection[4 * i];
    const yCoeff = modelViewProjection[4 * i + 1];
    const zCoeff = modelViewProjection[4 * i + 2];
    clippingPlanes[i] = 1 + xCoeff;
    clippingPlanes[4 + i] = 1 - xCoeff;
    clippingPlanes[8 + i] = 1 + yCoeff;
    clippingPlanes[12 + i] = 1 - yCoeff;
    clippingPlanes[16 + i] = zCoeff;
    clippingPlanes[20 + i] = -zCoeff;
  }
  if (DEBUG_CHUNK_VISIBILITY) {
    console.log("clippingPlanes", clippingPlanes);
    console.log("modelViewProjection", modelViewProjection.join(","));
    console.log(`lower=${lower.join(",")}, upper=${upper.join(",")}`);
  }
  forEachVolumetricChunkWithinFrustrum(
    clippingPlanes,
    transformedSource,
    callback,
    isAABBIntersectingPlane
  );
}
function getNormalizedChunkLayout(projectionParameters, chunkLayout) {
  const { finiteRank } = chunkLayout;
  if (finiteRank === 3) return chunkLayout;
  tempChunkLayout.finiteRank = finiteRank;
  vec3_exports.copy(tempChunkLayout.size, chunkLayout.size);
  const transform2 = mat4_exports.copy(tempChunkLayout.transform, chunkLayout.transform);
  const invTransform = mat4_exports.copy(
    tempChunkLayout.invTransform,
    chunkLayout.invTransform
  );
  tempChunkLayout.detTransform = chunkLayout.detTransform;
  const { invViewMatrix, width, height } = projectionParameters;
  const depth = getViewFrustrumDepthRange(projectionParameters.projectionMat);
  for (let chunkRenderDim = finiteRank; chunkRenderDim < 3; ++chunkRenderDim) {
    const offset = invViewMatrix[12 + chunkRenderDim];
    let lower = offset;
    let upper = offset;
    const xc = Math.abs(invViewMatrix[chunkRenderDim] * width);
    lower -= xc;
    upper += xc;
    const yc = Math.abs(invViewMatrix[chunkRenderDim + 4] * height);
    lower -= yc;
    upper += yc;
    const zc = Math.abs(invViewMatrix[chunkRenderDim + 8] * depth);
    lower -= zc;
    upper += zc;
    const scaleFactor = Math.max(1, upper - lower);
    transform2[12 + chunkRenderDim] = lower;
    transform2[5 * chunkRenderDim] = scaleFactor;
  }
  mat4_exports.invert(invTransform, transform2);
  return tempChunkLayout;
}

// node_modules/neuroglancer/lib/util/erf.js
init_legacy_browser();
function erf(x) {
  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;
  const t = 1 / (1 + p * Math.abs(x));
  const y = 1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
  return Math.sign(x) * y;
}

// node_modules/neuroglancer/lib/util/velocity_estimation.js
init_legacy_browser();
var VELOCITY_HALF_LIFE_MS = 50;
var MODEL_HALF_LIFE_MS = 1e3;
var VelocityEstimator = class {
  constructor(velocityHalfLifeMilliseconds = VELOCITY_HALF_LIFE_MS, modelHalfLifeMilliseconds = MODEL_HALF_LIFE_MS) {
    this.velocityHalfLifeMilliseconds = velocityHalfLifeMilliseconds;
    this.modelHalfLifeMilliseconds = modelHalfLifeMilliseconds;
  }
  lastTime = Number.NEGATIVE_INFINITY;
  rank = 0;
  numSamples = 0;
  // Previous position sampled.
  prevPosition = new Float32Array();
  // Moving average of raw velocity over `velocityHalfLifeMilliseconds`.
  velocity = new Float32Array();
  // Moving average of `velocity` estimate using `modelHalfLifeMilliseconds`.
  mean = new Float32Array();
  // Moving variance of `velocity` estimate using `modelHalfLifeMilliseconds`.
  variance = new Float32Array();
  reset(rank) {
    this.lastTime = Number.NEGATIVE_INFINITY;
    this.rank = rank;
    this.numSamples = 0;
    this.velocity = new Float32Array(rank);
    this.prevPosition = new Float32Array(rank);
    this.mean = new Float32Array(rank);
    this.variance = new Float32Array(rank);
  }
  addSample(position3, time = Date.now()) {
    const rank = position3.length;
    if (rank !== this.rank) {
      this.reset(rank);
    }
    const numSamples = this.numSamples;
    ++this.numSamples;
    if (this.numSamples === 0) {
      this.prevPosition.set(position3);
      this.lastTime = time;
      return;
    }
    const deltaT = time - this.lastTime;
    this.lastTime = time;
    const velocityAlpha = 1 - 2 ** -(deltaT / this.velocityHalfLifeMilliseconds);
    const modelAlpha = 1 - 2 ** -(deltaT / this.modelHalfLifeMilliseconds);
    const { velocity, prevPosition, mean, variance } = this;
    for (let i = 0; i < rank; ++i) {
      const curVelocitySample = (position3[i] - prevPosition[i]) / Math.max(deltaT, 1);
      prevPosition[i] = position3[i];
      const prevVelocity = velocity[i];
      const newVelocity = velocity[i] = prevVelocity + velocityAlpha * (curVelocitySample - prevVelocity);
      if (numSamples === 1) {
        mean[i] = newVelocity;
      } else {
        const meanPrev = mean[i];
        const varPrev = variance[i];
        const delta = newVelocity - meanPrev;
        mean[i] = meanPrev + modelAlpha * delta;
        variance[i] = (1 - modelAlpha) * (varPrev + modelAlpha * delta * delta);
      }
    }
  }
};

// node_modules/neuroglancer/lib/visibility_priority/backend.js
init_legacy_browser();
function withSharedVisibility(Base) {
  return class extends Base {
    visibility;
    constructor(...args) {
      super(...args);
      const rpc2 = args[0];
      const options = args[1];
      this.visibility = rpc2.get(options.visibility);
      this.registerDisposer(
        this.visibility.changed.add(
          () => this.chunkManager.scheduleUpdateChunkPriorities()
        )
      );
    }
  };
}
function getPriorityTier(visibility) {
  return visibility === Number.POSITIVE_INFINITY ? ChunkPriorityTier.VISIBLE : ChunkPriorityTier.PREFETCH;
}
function getBasePriority(visibility) {
  return visibility === Number.POSITIVE_INFINITY ? 0 : visibility * PREFETCH_PRIORITY_MULTIPLIER;
}

// node_modules/neuroglancer/lib/sliceview/backend.js
var __defProp7 = Object.defineProperty;
var __getOwnPropDesc7 = Object.getOwnPropertyDescriptor;
var __decorateClass6 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc7(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp7(target2, key, result);
  return result;
};
var BASE_PRIORITY = -1e12;
var SCALE_PRIORITY_MULTIPLIER = 1e9;
var tempChunkPosition = vec3_exports.create();
var tempCenter = vec3_exports.create();
var tempChunkSize = vec3_exports.create();
var SliceViewCounterpartBase = class extends SliceViewBase {
  constructor(rpc2, options) {
    super(rpc2.get(options.projectionParameters));
    this.initializeSharedObject(rpc2, options.id);
  }
};
function disposeTransformedSources(allSources) {
  for (const scales of allSources) {
    for (const tsource of scales) {
      tsource.source.dispose();
    }
  }
}
var SliceViewIntermediateBase = withSharedVisibility(
  withChunkManager(SliceViewCounterpartBase)
);
var SliceViewBackend = class extends SliceViewIntermediateBase {
  velocityEstimator = new VelocityEstimator();
  constructor(rpc2, options) {
    super(rpc2, options);
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateVisibleChunks();
      })
    );
    this.registerDisposer(
      this.projectionParameters.changed.add(() => {
        this.velocityEstimator.addSample(
          this.projectionParameters.value.globalPosition
        );
      })
    );
  }
  invalidateVisibleChunks() {
    super.invalidateVisibleChunks();
    this.chunkManager.scheduleUpdateChunkPriorities();
  }
  handleLayerChanged = () => {
    this.chunkManager.scheduleUpdateChunkPriorities();
  };
  updateVisibleChunks() {
    const projectionParameters = this.projectionParameters.value;
    const chunkManager = this.chunkManager;
    const visibility = this.visibility.value;
    if (visibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    this.updateVisibleSources();
    const { centerDataPosition } = projectionParameters;
    const priorityTier = getPriorityTier(visibility);
    let basePriority = getBasePriority(visibility);
    basePriority += BASE_PRIORITY;
    const localCenter = tempCenter;
    const chunkSize = tempChunkSize;
    const curVisibleChunks = [];
    this.velocityEstimator.addSample(
      this.projectionParameters.value.globalPosition
    );
    for (const [layer, visibleLayerSources] of this.visibleLayers) {
      chunkManager.registerLayer(layer);
      const { visibleSources } = visibleLayerSources;
      for (let i = 0, numVisibleSources = visibleSources.length; i < numVisibleSources; ++i) {
        const tsource = visibleSources[i];
        const prefetchOffsets = chunkManager.queueManager.enablePrefetch.value ? getPrefetchChunkOffsets(this.velocityEstimator, tsource) : [];
        const { chunkLayout } = tsource;
        chunkLayout.globalToLocalSpatial(localCenter, centerDataPosition);
        const { size, finiteRank } = chunkLayout;
        vec3_exports.copy(chunkSize, size);
        for (let i2 = finiteRank; i2 < 3; ++i2) {
          chunkSize[i2] = 0;
          localCenter[i2] = 0;
        }
        const priorityIndex = i;
        const sourceBasePriority = basePriority + SCALE_PRIORITY_MULTIPLIER * priorityIndex;
        curVisibleChunks.length = 0;
        const curMarkGeneration = getNextMarkGeneration();
        forEachPlaneIntersectingVolumetricChunk(
          projectionParameters,
          tsource.renderLayer.localPosition.value,
          tsource,
          getNormalizedChunkLayout(projectionParameters, tsource.chunkLayout),
          (positionInChunks) => {
            vec3_exports.multiply(tempChunkPosition, positionInChunks, chunkSize);
            const priority = -vec3_exports.distance(localCenter, tempChunkPosition);
            const { curPositionInChunks } = tsource;
            const chunk = tsource.source.getChunk(curPositionInChunks);
            chunkManager.requestChunk(
              chunk,
              priorityTier,
              sourceBasePriority + priority
            );
            ++layer.numVisibleChunksNeeded;
            if (chunk.state === ChunkState.GPU_MEMORY) {
              ++layer.numVisibleChunksAvailable;
            }
            curVisibleChunks.push(chunk);
            chunk.markGeneration = curMarkGeneration;
          }
        );
        if (prefetchOffsets.length !== 0) {
          const { curPositionInChunks } = tsource;
          for (const visibleChunk of curVisibleChunks) {
            curPositionInChunks.set(visibleChunk.chunkGridPosition);
            for (let j = 0, length6 = prefetchOffsets.length; j < length6; ) {
              const chunkDim = prefetchOffsets[j];
              const minChunk = prefetchOffsets[j + 2];
              const maxChunk = prefetchOffsets[j + 3];
              const newPriority = prefetchOffsets[j + 4];
              const jumpOffset = prefetchOffsets[j + 5];
              const oldIndex = curPositionInChunks[chunkDim];
              const newIndex = oldIndex + prefetchOffsets[j + 1];
              if (newIndex < minChunk || newIndex > maxChunk) {
                j = jumpOffset;
                continue;
              }
              curPositionInChunks[chunkDim] = newIndex;
              const chunk = tsource.source.getChunk(curPositionInChunks);
              curPositionInChunks[chunkDim] = oldIndex;
              if (chunk.markGeneration === curMarkGeneration) {
                j = jumpOffset;
                continue;
              }
              chunkManager.requestChunk(
                chunk,
                ChunkPriorityTier.PREFETCH,
                sourceBasePriority + newPriority
              );
              ++layer.numPrefetchChunksNeeded;
              if (chunk.state === ChunkState.GPU_MEMORY) {
                ++layer.numPrefetchChunksAvailable;
              }
              j += PREFETCH_ENTRY_SIZE;
            }
          }
        }
      }
    }
  }
  removeVisibleLayer(layer) {
    const { visibleLayers } = this;
    const layerInfo = visibleLayers.get(layer);
    visibleLayers.delete(layer);
    disposeTransformedSources(layerInfo.allSources);
    layer.renderScaleTarget.changed.remove(this.invalidateVisibleSources);
    layer.localPosition.changed.remove(this.handleLayerChanged);
    this.invalidateVisibleSources();
  }
  addVisibleLayer(layer, allSources, displayDimensionRenderInfo) {
    let layerInfo = this.visibleLayers.get(layer);
    if (layerInfo === void 0) {
      layerInfo = {
        allSources,
        visibleSources: [],
        displayDimensionRenderInfo
      };
      this.visibleLayers.set(layer, layerInfo);
      layer.renderScaleTarget.changed.add(
        () => this.invalidateVisibleSources()
      );
      layer.localPosition.changed.add(this.handleLayerChanged);
    } else {
      disposeTransformedSources(layerInfo.allSources);
      layerInfo.allSources = allSources;
      layerInfo.visibleSources.length = 0;
      layerInfo.displayDimensionRenderInfo = displayDimensionRenderInfo;
    }
    this.invalidateVisibleSources();
  }
  disposed() {
    for (const layer of this.visibleLayers.keys()) {
      this.removeVisibleLayer(layer);
    }
    super.disposed();
  }
  invalidateVisibleSources() {
    super.invalidateVisibleSources();
    this.chunkManager.scheduleUpdateChunkPriorities();
  }
};
SliceViewBackend = __decorateClass6([
  registerSharedObject(SLICEVIEW_RPC_ID)
], SliceViewBackend);
function deserializeTransformedSources(rpc2, serializedSources, layer) {
  const sources = serializedSources.map(
    (scales) => scales.map((serializedSource) => {
      const source = rpc2.getRef(serializedSource.source);
      const chunkLayout = serializedSource.chunkLayout;
      const { rank } = source.spec;
      const tsource = {
        renderLayer: layer,
        source,
        chunkLayout: ChunkLayout.fromObject(chunkLayout),
        layerRank: serializedSource.layerRank,
        nonDisplayLowerClipBound: serializedSource.nonDisplayLowerClipBound,
        nonDisplayUpperClipBound: serializedSource.nonDisplayUpperClipBound,
        lowerClipBound: serializedSource.lowerClipBound,
        upperClipBound: serializedSource.upperClipBound,
        lowerClipDisplayBound: serializedSource.lowerClipDisplayBound,
        upperClipDisplayBound: serializedSource.upperClipDisplayBound,
        lowerChunkDisplayBound: serializedSource.lowerChunkDisplayBound,
        upperChunkDisplayBound: serializedSource.upperChunkDisplayBound,
        effectiveVoxelSize: serializedSource.effectiveVoxelSize,
        chunkDisplayDimensionIndices: serializedSource.chunkDisplayDimensionIndices,
        fixedLayerToChunkTransform: serializedSource.fixedLayerToChunkTransform,
        combinedGlobalLocalToChunkTransform: serializedSource.combinedGlobalLocalToChunkTransform,
        curPositionInChunks: new Float32Array(rank),
        fixedPositionWithinChunk: new Uint32Array(rank)
      };
      return tsource;
    })
  );
  return sources;
}
registerRPC(SLICEVIEW_ADD_VISIBLE_LAYER_RPC_ID, function(x) {
  const obj = this.get(x.id);
  const layer = this.get(x.layerId);
  const sources = deserializeTransformedSources(this, x.sources, layer);
  obj.addVisibleLayer(layer, sources, x.displayDimensionRenderInfo);
});
registerRPC(SLICEVIEW_REMOVE_VISIBLE_LAYER_RPC_ID, function(x) {
  const obj = this.get(x.id);
  const layer = this.get(x.layerId);
  obj.removeVisibleLayer(layer);
});
var SliceViewChunk = class extends Chunk {
  chunkGridPosition;
  source = null;
  initializeVolumeChunk(key, chunkGridPosition) {
    super.initialize(key);
    this.chunkGridPosition = Float32Array.from(chunkGridPosition);
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    msg.chunkGridPosition = this.chunkGridPosition;
  }
  downloadSucceeded() {
    super.downloadSucceeded();
  }
  freeSystemMemory() {
  }
  toString() {
    return this.source.toString() + ":" + vec3Key(this.chunkGridPosition);
  }
};
var SliceViewChunkSourceBackend = class extends ChunkSource {
  spec;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.spec = options.spec;
  }
  getChunk(chunkGridPosition) {
    const key = chunkGridPosition.join();
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(this.chunkConstructor);
      chunk.initializeVolumeChunk(key, chunkGridPosition);
      this.addChunk(chunk);
    }
    return chunk;
  }
};
var SliceViewRenderLayerBackend = class extends SharedObjectCounterpart {
  renderScaleTarget;
  localPosition;
  numVisibleChunksNeeded;
  numVisibleChunksAvailable;
  numPrefetchChunksNeeded;
  numPrefetchChunksAvailable;
  chunkManagerGeneration;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.renderScaleTarget = rpc2.get(options.renderScaleTarget);
    this.localPosition = rpc2.get(options.localPosition);
    this.numVisibleChunksNeeded = 0;
    this.numVisibleChunksAvailable = 0;
    this.numPrefetchChunksAvailable = 0;
    this.numPrefetchChunksNeeded = 0;
    this.chunkManagerGeneration = -1;
  }
  filterVisibleSources(sliceView, sources) {
    return filterVisibleSources(sliceView, this, sources);
  }
};
SliceViewRenderLayerBackend = __decorateClass6([
  registerSharedObject(SLICEVIEW_RENDERLAYER_RPC_ID)
], SliceViewRenderLayerBackend);
var PREFETCH_MS = 2e3;
var MAX_PREFETCH_VELOCITY = 0.1;
var MAX_SINGLE_DIRECTION_PREFETCH_CHUNKS = 32;
var PREFETCH_PROBABILITY_CUTOFF = 0.05;
var PREFETCH_ENTRY_SIZE = 6;
function getPrefetchChunkOffsets(velocityEstimator, tsource) {
  const offsets = [];
  const globalRank = velocityEstimator.rank;
  const { combinedGlobalLocalToChunkTransform, layerRank } = tsource;
  const { rank: chunkRank, chunkDataSize } = tsource.source.spec;
  const { mean: meanVec, variance: varianceVec } = velocityEstimator;
  for (let chunkDim = 0; chunkDim < chunkRank; ++chunkDim) {
    const isDisplayDimension = tsource.chunkDisplayDimensionIndices.includes(chunkDim);
    let mean = 0;
    let variance = 0;
    for (let globalDim = 0; globalDim < globalRank; ++globalDim) {
      const meanValue = meanVec[globalDim];
      const varianceValue = varianceVec[globalDim];
      const coeff = combinedGlobalLocalToChunkTransform[globalDim * layerRank + chunkDim];
      mean += coeff * meanValue;
      variance += coeff * coeff * varianceValue;
    }
    if (mean > MAX_PREFETCH_VELOCITY) {
      continue;
    }
    const chunkSize = chunkDataSize[chunkDim];
    const initialFraction = isDisplayDimension ? 0 : tsource.fixedPositionWithinChunk[chunkDim] / chunkSize;
    const adjustedMean = mean / chunkSize * PREFETCH_MS;
    let adjustedStddevTimesSqrt2 = Math.sqrt(2 * variance) / chunkSize * PREFETCH_MS;
    if (Math.abs(adjustedMean) < 1e-3 && adjustedStddevTimesSqrt2 < 1e-3) {
      continue;
    }
    adjustedStddevTimesSqrt2 = Math.max(1e-6, adjustedStddevTimesSqrt2);
    const cdf = (x) => 0.5 * (1 + erf((x - adjustedMean) / adjustedStddevTimesSqrt2));
    const curChunk = tsource.curPositionInChunks[chunkDim];
    const minChunk = Math.floor(tsource.lowerClipBound[chunkDim] / chunkSize);
    const maxChunk = Math.ceil(tsource.upperClipBound[chunkDim] / chunkSize) - 1;
    let groupStart = offsets.length;
    for (let i = 1; i <= MAX_SINGLE_DIRECTION_PREFETCH_CHUNKS; ++i) {
      if (!isDisplayDimension && curChunk + i > maxChunk) break;
      const probability = 1 - cdf(i - initialFraction);
      if (probability < PREFETCH_PROBABILITY_CUTOFF) break;
      offsets.push(chunkDim, i, minChunk, maxChunk, probability, 0);
    }
    let newGroupStart = offsets.length;
    for (let i = groupStart, end = offsets.length; i < end; i += PREFETCH_ENTRY_SIZE) {
      offsets[i + PREFETCH_ENTRY_SIZE - 1] = newGroupStart;
    }
    groupStart = newGroupStart;
    for (let i = 1; i <= MAX_SINGLE_DIRECTION_PREFETCH_CHUNKS; ++i) {
      if (!isDisplayDimension && curChunk - i < minChunk) break;
      const probability = cdf(-i + 1 - initialFraction);
      if (probability < PREFETCH_PROBABILITY_CUTOFF) break;
      offsets.push(chunkDim, -i, minChunk, maxChunk, probability, 0);
    }
    newGroupStart = offsets.length;
    for (let i = groupStart, end = offsets.length; i < end; i += PREFETCH_ENTRY_SIZE) {
      offsets[i + PREFETCH_ENTRY_SIZE - 1] = newGroupStart;
    }
  }
  return offsets;
}
registerPromiseRPC(
  SLICEVIEW_REQUEST_CHUNK_RPC_ID,
  async function(x, progressOptions) {
    const source = this.get(x.source);
    const { chunkManager } = source;
    const chunk = source.getChunk(x.chunkGridPosition);
    const key = chunk.key;
    if (chunk.state <= ChunkState.SYSTEM_MEMORY) {
      return { value: void 0 };
    }
    if (chunk.state === ChunkState.FAILED) {
      throw chunk.error;
    }
    const disposeRecompute = chunkManager.recomputeChunkPriorities.add(() => {
      chunkManager.requestChunk(
        chunk,
        ChunkPriorityTier.VISIBLE,
        Number.POSITIVE_INFINITY,
        ChunkState.SYSTEM_MEMORY
      );
    });
    chunkManager.scheduleUpdateChunkPriorities();
    let listener;
    const promise = new Promise((resolve, reject) => {
      listener = (chunk2) => {
        if (chunk2.state === ChunkState.FAILED) {
          reject(chunk2.error);
          return;
        }
        if (chunk2.state <= ChunkState.SYSTEM_MEMORY) {
          resolve();
        }
      };
    });
    source.registerChunkListener(key, listener);
    try {
      await raceWithAbort(promise, progressOptions.signal);
      return { value: void 0 };
    } finally {
      source.unregisterChunkListener(key, listener);
      disposeRecompute();
      chunkManager.scheduleUpdateChunkPriorities();
    }
  }
);

// node_modules/neuroglancer/lib/perspective_view/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/perspective_view/base.js
init_legacy_browser();
var PERSPECTIVE_VIEW_RPC_ID = "perspective_view/PerspectiveView";

// node_modules/neuroglancer/lib/perspective_view/backend.js
var __defProp8 = Object.defineProperty;
var __getOwnPropDesc8 = Object.getOwnPropertyDescriptor;
var __decorateClass7 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc8(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp8(target2, key, result);
  return result;
};
var PerspectiveViewBackend = class extends SharedObjectCounterpart {
  visibility;
  projectionParameters;
  constructor(...args) {
    super(...args);
    const rpc2 = args[0];
    const options = args[1];
    this.visibility = rpc2.get(options.visibility);
    this.projectionParameters = rpc2.get(options.projectionParameters);
  }
};
PerspectiveViewBackend = __decorateClass7([
  registerSharedObject(PERSPECTIVE_VIEW_RPC_ID)
], PerspectiveViewBackend);
var PerspectiveViewRenderLayerBackend = class extends RenderLayerBackend {
};

// node_modules/neuroglancer/lib/volume_rendering/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/volume_rendering/base.js
init_legacy_browser();
var VOLUME_RENDERING_RENDER_LAYER_RPC_ID = "volume_rendering/VolumeRenderingRenderLayer";
var VOLUME_RENDERING_RENDER_LAYER_UPDATE_SOURCES_RPC_ID = "volume_rendering/VolumeRenderingRenderLayer/update";
var DEBUG_CHUNK_LEVEL = false;
var tempMat3 = mat3_exports.create();
function forEachVisibleVolumeRenderingChunk(projectionParameters, localPosition, volumeRenderingDepthSamples, transformedSources, beginScale, callback) {
  if (transformedSources.length === 0) return;
  const { viewMatrix, projectionMat, displayDimensionRenderInfo } = projectionParameters;
  const { voxelPhysicalScales } = displayDimensionRenderInfo;
  const canonicalToPhysicalScale = prod3(voxelPhysicalScales);
  const depthRange = getViewFrustrumDepthRange(projectionMat);
  const targetViewSpacing = depthRange / volumeRenderingDepthSamples;
  const targetViewVolume = targetViewSpacing ** 3;
  const viewDet = mat3_exports.determinant(mat3FromMat4(tempMat3, viewMatrix));
  const histogramInformation = {
    spatialScales: /* @__PURE__ */ new Map(),
    activeIndex: -1
  };
  const getViewVolume = (scaleIndex) => {
    const tsource2 = transformedSources[scaleIndex];
    return Math.abs(tsource2.chunkLayout.detTransform * viewDet);
  };
  let bestScaleIndex = transformedSources.length - 1;
  let bestViewVolume = getViewVolume(bestScaleIndex);
  for (let scaleIndex = bestScaleIndex; scaleIndex >= 0; --scaleIndex) {
    const viewVolume = getViewVolume(scaleIndex);
    const physicalSpacing2 = Math.cbrt(
      viewVolume * canonicalToPhysicalScale / viewDet
    );
    const optimalSamples2 = depthRange / Math.cbrt(viewVolume);
    histogramInformation.spatialScales.set(physicalSpacing2, optimalSamples2);
    if (viewVolume - targetViewVolume >= 0) {
      bestViewVolume = viewVolume;
      bestScaleIndex = scaleIndex;
    }
    histogramInformation.activeIndex = bestScaleIndex;
  }
  if (DEBUG_CHUNK_LEVEL) {
    console.log(transformedSources);
    for (let scaleIndex = 0; scaleIndex < transformedSources.length; ++scaleIndex) {
      const viewVolume = getViewVolume(scaleIndex);
      const desiredSamples = depthRange / Math.cbrt(viewVolume);
      console.log(
        `scaleIndex=${scaleIndex} viewVolume=${viewVolume} bestScaleIndex=${bestScaleIndex} actualViewVolume=${targetViewVolume}, desiredSamples=${desiredSamples}, difference=${viewVolume - targetViewVolume}`
      );
    }
  }
  const physicalSpacing = Math.cbrt(
    bestViewVolume * canonicalToPhysicalScale / viewDet
  );
  const optimalSamples = depthRange / Math.cbrt(bestViewVolume);
  let firstChunk = true;
  const tsource = transformedSources[bestScaleIndex];
  forEachVisibleVolumetricChunk(
    projectionParameters,
    localPosition,
    tsource,
    (positionInChunks, clippingPlanes) => {
      if (firstChunk) {
        beginScale(
          tsource,
          bestScaleIndex,
          physicalSpacing,
          optimalSamples,
          clippingPlanes,
          histogramInformation
        );
        firstChunk = false;
      }
      callback(tsource, bestScaleIndex, positionInChunks);
    }
  );
}

// node_modules/neuroglancer/lib/volume_rendering/backend.js
var __defProp9 = Object.defineProperty;
var __getOwnPropDesc9 = Object.getOwnPropertyDescriptor;
var __decorateClass8 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc9(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp9(target2, key, result);
  return result;
};
var tempChunkPosition2 = vec3_exports.create();
var tempCenter2 = vec3_exports.create();
var tempChunkSize2 = vec3_exports.create();
var tempCenterDataPosition = vec3_exports.create();
var VolumeRenderingRenderLayerBackend = class extends withChunkManager(
  RenderLayerBackend
) {
  localPosition;
  // The render scale target for volume rendering is the number of depth samples
  renderScaleTarget;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.renderScaleTarget = rpc2.get(options.renderScaleTarget);
    this.localPosition = rpc2.get(options.localPosition);
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    this.registerDisposer(
      this.localPosition.changed.add(scheduleUpdateChunkPriorities)
    );
    this.registerDisposer(
      this.renderScaleTarget.changed.add(scheduleUpdateChunkPriorities)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(
        () => this.recomputeChunkPriorities()
      )
    );
  }
  attach(attachment) {
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    const { view } = attachment;
    attachment.registerDisposer(scheduleUpdateChunkPriorities);
    attachment.registerDisposer(
      view.projectionParameters.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(
      view.visibility.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.state = {
      displayDimensionRenderInfo: view.projectionParameters.value.displayDimensionRenderInfo,
      transformedSources: []
    };
  }
  recomputeChunkPriorities() {
    for (const attachment of this.attachments.values()) {
      const { view } = attachment;
      const visibility = view.visibility.value;
      if (visibility === Number.NEGATIVE_INFINITY) {
        continue;
      }
      const state = attachment.state;
      const { transformedSources } = state;
      if (transformedSources.length === 0 || !validateDisplayDimensionRenderInfoProperty(
        state,
        view.projectionParameters.value.displayDimensionRenderInfo
      )) {
        continue;
      }
      const projectionParameters = view.projectionParameters.value;
      const priorityTier = getPriorityTier(visibility);
      let basePriority = getBasePriority(visibility);
      basePriority += BASE_PRIORITY;
      const localCenter = tempCenter2;
      const chunkSize = tempChunkSize2;
      const centerDataPosition = tempCenterDataPosition;
      const {
        globalPosition,
        displayDimensionRenderInfo: { displayDimensionIndices }
      } = projectionParameters;
      for (let displayDim = 0; displayDim < 3; ++displayDim) {
        const globalDim = displayDimensionIndices[displayDim];
        centerDataPosition[displayDim] = globalDim === -1 ? 0 : globalPosition[globalDim];
      }
      let sourceBasePriority;
      const { chunkManager } = this;
      chunkManager.registerLayer(this);
      forEachVisibleVolumeRenderingChunk(
        projectionParameters,
        this.localPosition.value,
        this.renderScaleTarget.value,
        transformedSources[0],
        (tsource, scaleIndex) => {
          const { chunkLayout } = tsource;
          chunkLayout.globalToLocalSpatial(localCenter, centerDataPosition);
          const { size, finiteRank } = chunkLayout;
          vec3_exports.copy(chunkSize, size);
          for (let i = finiteRank; i < 3; ++i) {
            chunkSize[i] = 0;
            localCenter[i] = 0;
          }
          const priorityIndex = transformedSources[0].length - 1 - scaleIndex;
          sourceBasePriority = basePriority + SCALE_PRIORITY_MULTIPLIER * priorityIndex;
        },
        (tsource, _, positionInChunks) => {
          vec3_exports.multiply(tempChunkPosition2, positionInChunks, chunkSize);
          const priority = -vec3_exports.distance(localCenter, tempChunkPosition2);
          const chunk = tsource.source.getChunk(tsource.curPositionInChunks);
          ++this.numVisibleChunksNeeded;
          chunkManager.requestChunk(
            chunk,
            priorityTier,
            sourceBasePriority + priority
          );
          if (chunk.state === ChunkState.GPU_MEMORY) {
            ++this.numVisibleChunksAvailable;
          }
        }
      );
    }
  }
};
VolumeRenderingRenderLayerBackend = __decorateClass8([
  registerSharedObject(VOLUME_RENDERING_RENDER_LAYER_RPC_ID)
], VolumeRenderingRenderLayerBackend);
registerRPC(VOLUME_RENDERING_RENDER_LAYER_UPDATE_SOURCES_RPC_ID, function(x) {
  const view = this.get(x.view);
  const layer = this.get(x.layer);
  const attachment = layer.attachments.get(
    view
  );
  attachment.state.transformedSources = deserializeTransformedSources(this, x.sources, layer);
  attachment.state.displayDimensionRenderInfo = x.displayDimensionRenderInfo;
  layer.chunkManager.scheduleUpdateChunkPriorities();
});

// node_modules/neuroglancer/lib/annotation/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/annotation/base.js
init_legacy_browser();
var ANNOTATION_METADATA_CHUNK_SOURCE_RPC_ID = "annotation.MetadataChunkSource";
var ANNOTATION_SUBSET_GEOMETRY_CHUNK_SOURCE_RPC_ID = "annotation.SubsetGeometryChunkSource";
var ANNOTATION_REFERENCE_ADD_RPC_ID = "annotation.reference.add";
var ANNOTATION_REFERENCE_DELETE_RPC_ID = "annotation.reference.delete";
var ANNOTATION_COMMIT_UPDATE_RPC_ID = "annotation.commit";
var ANNOTATION_COMMIT_UPDATE_RESULT_RPC_ID = "annotation.commit";
var ANNOTATION_SPATIALLY_INDEXED_RENDER_LAYER_RPC_ID = "annotation/SpatiallyIndexedRenderLayer";
var ANNOTATION_PERSPECTIVE_RENDER_LAYER_UPDATE_SOURCES_RPC_ID = "annotation/PerspectiveRenderLayer:updateSources";
var ANNOTATION_RENDER_LAYER_RPC_ID = "annotation/RenderLayer";
var ANNOTATION_RENDER_LAYER_UPDATE_SEGMENTATION_RPC_ID = "annotation/RenderLayer.updateSegmentation";
var tempMat32 = mat3_exports.create();
function forEachVisibleAnnotationChunk(projectionParameters, localPosition, renderScaleTarget, transformedSources, beginScale, callback) {
  const {
    displayDimensionRenderInfo,
    viewMatrix,
    projectionMat,
    width,
    height
  } = projectionParameters;
  const { voxelPhysicalScales } = displayDimensionRenderInfo;
  const viewDet = Math.abs(
    mat3_exports.determinant(mat3FromMat4(tempMat32, viewMatrix))
  );
  const canonicalToPhysicalScale = prod3(voxelPhysicalScales);
  const viewFrustrumVolume = getViewFrustrumVolume(projectionMat) / viewDet * canonicalToPhysicalScale;
  if (transformedSources.length === 0) return;
  const baseSource = transformedSources[0];
  let sourceVolume = Math.abs(baseSource.chunkLayout.detTransform) * canonicalToPhysicalScale;
  const { lowerClipDisplayBound, upperClipDisplayBound } = baseSource;
  for (let i = 0; i < 3; ++i) {
    sourceVolume *= upperClipDisplayBound[i] - lowerClipDisplayBound[i];
  }
  const effectiveVolume = Math.min(sourceVolume, viewFrustrumVolume);
  const viewportArea = width * height;
  const targetNumAnnotations = viewportArea / renderScaleTarget ** 2;
  const physicalDensityTarget = targetNumAnnotations / effectiveVolume;
  let totalPhysicalDensity = 0;
  for (let scaleIndex = transformedSources.length - 1; scaleIndex >= 0 && totalPhysicalDensity < physicalDensityTarget; --scaleIndex) {
    const transformedSource = transformedSources[scaleIndex];
    const spec = transformedSource.source.spec;
    const { chunkLayout } = transformedSource;
    const physicalVolume = prod3(chunkLayout.size) * Math.abs(chunkLayout.detTransform) * canonicalToPhysicalScale;
    const { limit, rank } = spec;
    const { nonDisplayLowerClipBound, nonDisplayUpperClipBound } = transformedSource;
    let sliceFraction = 1;
    for (let i = 0; i < rank; ++i) {
      const b = nonDisplayUpperClipBound[i] - nonDisplayLowerClipBound[i];
      if (Number.isFinite(b)) sliceFraction /= b;
    }
    const physicalDensity = limit * sliceFraction / physicalVolume;
    let firstChunk = true;
    const newTotalPhysicalDensity = totalPhysicalDensity + physicalDensity;
    const totalPhysicalSpacing = (1 / newTotalPhysicalDensity) ** (1 / 3);
    const totalPixelSpacing = Math.sqrt(
      viewportArea / (newTotalPhysicalDensity * effectiveVolume)
    );
    const desiredCount = (physicalDensityTarget - totalPhysicalDensity) * physicalVolume / sliceFraction;
    const drawFraction = Math.min(1, desiredCount / spec.limit);
    forEachVisibleVolumetricChunk(
      projectionParameters,
      localPosition,
      transformedSource,
      () => {
        if (firstChunk) {
          beginScale(transformedSource, scaleIndex);
          firstChunk = false;
        }
        callback(
          transformedSource,
          scaleIndex,
          drawFraction,
          totalPhysicalSpacing,
          totalPixelSpacing
        );
      }
    );
    totalPhysicalDensity = newTotalPhysicalDensity;
  }
}

// node_modules/neuroglancer/lib/segmentation_display_state/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/shared_disjoint_sets.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/disjoint_sets.js
init_legacy_browser();

// node_modules/neuroglancer/lib/segmentation_graph/segment_id.js
init_legacy_browser();
var VisibleSegmentEquivalencePolicy = /* @__PURE__ */ ((VisibleSegmentEquivalencePolicy2) => {
  VisibleSegmentEquivalencePolicy2[VisibleSegmentEquivalencePolicy2["MIN_REPRESENTATIVE"] = 0] = "MIN_REPRESENTATIVE";
  VisibleSegmentEquivalencePolicy2[VisibleSegmentEquivalencePolicy2["MAX_REPRESENTATIVE"] = 1] = "MAX_REPRESENTATIVE";
  VisibleSegmentEquivalencePolicy2[VisibleSegmentEquivalencePolicy2["REPRESENTATIVE_EXCLUDED"] = 2] = "REPRESENTATIVE_EXCLUDED";
  VisibleSegmentEquivalencePolicy2[VisibleSegmentEquivalencePolicy2["NONREPRESENTATIVE_EXCLUDED"] = 4] = "NONREPRESENTATIVE_EXCLUDED";
  return VisibleSegmentEquivalencePolicy2;
})(VisibleSegmentEquivalencePolicy || {});

// node_modules/neuroglancer/lib/util/disjoint_sets.js
var Entry = class {
  constructor(value) {
    this.value = value;
    this.min = value;
  }
  rank = 0;
  parent = this;
  next = this;
  prev = this;
  min;
};
function findRepresentative(v) {
  let old = v;
  let ancestor = v.parent;
  while (ancestor !== v) {
    v = ancestor;
    ancestor = v.parent;
  }
  v = old.parent;
  while (ancestor !== v) {
    old.parent = ancestor;
    old = v;
    v = old.parent;
  }
  return ancestor;
}
function linkUnequalSetRepresentatives(i, j) {
  const iRank = i.rank;
  const jRank = j.rank;
  if (iRank > jRank) {
    j.parent = i;
    return i;
  }
  i.parent = j;
  if (iRank === jRank) {
    j.rank = jRank + 1;
  }
  return j;
}
function spliceCircularLists(i, j) {
  const iPrev = i.prev;
  const jPrev = j.prev;
  j.prev = iPrev;
  iPrev.next = j;
  i.prev = jPrev;
  jPrev.next = i;
}
function* setElementIterator(i) {
  let j = i;
  do {
    yield j.value;
    j = j.next;
  } while (j !== i);
}
function isRootElement(v) {
  return v.parent === v;
}
var DisjointUint64Sets = class {
  map = /* @__PURE__ */ new Map();
  visibleSegmentEquivalencePolicy = new WatchableValue(
    VisibleSegmentEquivalencePolicy.MIN_REPRESENTATIVE
  );
  generation = 0;
  has(x) {
    return this.map.has(x);
  }
  get(x) {
    const entry = this.map.get(x);
    if (entry === void 0) {
      return x;
    }
    return findRepresentative(entry).min;
  }
  isMinElement(x) {
    return x === this.get(x);
  }
  makeSet(x) {
    const { map: map2 } = this;
    let entry = map2.get(x);
    if (entry === void 0) {
      entry = new Entry(x);
      map2.set(x, entry);
      return entry;
    }
    return findRepresentative(entry);
  }
  /**
   * Union the sets containing `a` and `b`.
   * @returns `false` if `a` and `b` are already in the same set, otherwise `true`.
   */
  link(a, b) {
    const aEntry = this.makeSet(a);
    const bEntry = this.makeSet(b);
    if (aEntry === bEntry) {
      return false;
    }
    this.generation++;
    const newNode = linkUnequalSetRepresentatives(aEntry, bEntry);
    spliceCircularLists(aEntry, bEntry);
    const aMin = aEntry.min;
    const bMin = bEntry.min;
    const isMax = (this.visibleSegmentEquivalencePolicy.value & VisibleSegmentEquivalencePolicy.MAX_REPRESENTATIVE) !== 0;
    newNode.min = aMin < bMin === isMax ? bMin : aMin;
    return true;
  }
  linkAll(ids) {
    for (let i = 1, length6 = ids.length; i < length6; ++i) {
      this.link(ids[0], ids[i]);
    }
  }
  /**
   * Unlinks all members of the specified set.
   */
  deleteSet(x) {
    const { map: map2 } = this;
    let changed = false;
    for (const y of this.setElements(x)) {
      map2.delete(y);
      changed = true;
    }
    if (changed) {
      ++this.generation;
    }
    return changed;
  }
  *setElements(a) {
    const entry = this.map.get(a);
    if (entry === void 0) {
      yield a;
    } else {
      yield* setElementIterator(entry);
    }
  }
  clear() {
    const { map: map2 } = this;
    if (map2.size === 0) {
      return false;
    }
    ++this.generation;
    map2.clear();
    return true;
  }
  get size() {
    return this.map.size;
  }
  *mappings() {
    for (const entry of this.map.values()) {
      yield [entry.value, findRepresentative(entry).min];
    }
  }
  *roots() {
    for (const entry of this.map.values()) {
      if (isRootElement(entry)) {
        yield entry.value;
      }
    }
  }
  [Symbol.iterator]() {
    return this.mappings();
  }
  /**
   * Returns an array of arrays of strings, where the arrays contained in the outer array correspond
   * to the disjoint sets, and the strings are the base-10 string representations of the members of
   * each set.  The members are sorted in numerical order, and the sets are sorted in numerical
   * order of their smallest elements.
   */
  toJSON() {
    const sets = new Array();
    for (const entry of this.map.values()) {
      if (isRootElement(entry)) {
        const members = new Array();
        for (const member of setElementIterator(entry)) {
          members.push(member);
        }
        members.sort(bigintCompare);
        sets.push(members);
      }
    }
    sets.sort((a, b) => bigintCompare(a[0], b[0]));
    return sets.map((set6) => set6.map((element) => element.toString()));
  }
};

// node_modules/neuroglancer/lib/shared_disjoint_sets.js
var __defProp10 = Object.defineProperty;
var __getOwnPropDesc10 = Object.getOwnPropertyDescriptor;
var __decorateClass9 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc10(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp10(target2, key, result);
  return result;
};
var RPC_TYPE_ID = "DisjointUint64Sets";
var ADD_METHOD_ID = "DisjointUint64Sets.add";
var CLEAR_METHOD_ID = "DisjointUint64Sets.clear";
var HIGH_BIT_REPRESENTATIVE_CHANGED_ID = "DisjointUint64Sets.highBitRepresentativeChanged";
var DELETE_SET_METHOD_ID = "DisjointUint64Sets.deleteSet";
var SharedDisjointUint64Sets = class extends SharedObjectCounterpart {
  disjointSets = new DisjointUint64Sets();
  changed = new NullarySignal();
  /**
   * For compatibility with `WatchableValueInterface`.
   */
  get value() {
    return this;
  }
  static makeWithCounterpart(rpc2, highBitRepresentative) {
    const obj = new SharedDisjointUint64Sets();
    obj.disjointSets.visibleSegmentEquivalencePolicy = highBitRepresentative;
    obj.registerDisposer(
      highBitRepresentative.changed.add(() => {
        updateHighBitRepresentative(obj);
      })
    );
    obj.initializeCounterpart(rpc2);
    if (highBitRepresentative.value) {
      updateHighBitRepresentative(obj);
    }
    return obj;
  }
  link(a, b) {
    if (this.disjointSets.link(a, b)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke(ADD_METHOD_ID, {
          id: this.rpcId,
          a,
          b
        });
      }
      this.changed.dispatch();
      return true;
    }
    return false;
  }
  linkAll(ids) {
    for (let i = 1, length6 = ids.length; i < length6; ++i) {
      this.link(ids[0], ids[i]);
    }
  }
  has(x) {
    return this.disjointSets.has(x);
  }
  get(x) {
    return this.disjointSets.get(x);
  }
  clear() {
    if (this.disjointSets.clear()) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke(CLEAR_METHOD_ID, { id: this.rpcId });
      }
      this.changed.dispatch();
    }
  }
  setElements(a) {
    return this.disjointSets.setElements(a);
  }
  deleteSet(x) {
    if (this.disjointSets.deleteSet(x)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke(DELETE_SET_METHOD_ID, {
          id: this.rpcId,
          x
        });
      }
      this.changed.dispatch();
    }
  }
  get size() {
    return this.disjointSets.size;
  }
  toJSON() {
    return this.disjointSets.toJSON();
  }
  /**
   * Restores the state from a JSON representation.
   */
  restoreState(obj) {
    if (obj !== void 0) {
      parseArray(obj, (z) => {
        let prev;
        parseArray(z, (s) => {
          const cur = parseUint64(s);
          if (prev !== void 0) {
            this.link(prev, cur);
          }
          prev = cur;
        });
      });
    }
  }
  assignFrom(other) {
    this.clear();
    if (other instanceof SharedDisjointUint64Sets) {
      other = other.disjointSets;
    }
    for (const [a, b] of other) {
      this.link(a, b);
    }
  }
};
SharedDisjointUint64Sets = __decorateClass9([
  registerSharedObject(RPC_TYPE_ID)
], SharedDisjointUint64Sets);
registerRPC(ADD_METHOD_ID, function(x) {
  const obj = this.get(x.id);
  if (obj.disjointSets.link(x.a, x.b)) {
    obj.changed.dispatch();
  }
});
registerRPC(CLEAR_METHOD_ID, function(x) {
  const obj = this.get(x.id);
  if (obj.disjointSets.clear()) {
    obj.changed.dispatch();
  }
});
function updateHighBitRepresentative(obj) {
  obj.rpc.invoke(HIGH_BIT_REPRESENTATIVE_CHANGED_ID, {
    id: obj.rpcId,
    value: obj.disjointSets.visibleSegmentEquivalencePolicy.value
  });
}
registerRPC(HIGH_BIT_REPRESENTATIVE_CHANGED_ID, function(x) {
  const obj = this.get(x.id);
  obj.disjointSets.visibleSegmentEquivalencePolicy.value = x.value;
});
registerRPC(DELETE_SET_METHOD_ID, function(x) {
  const obj = this.get(x.id);
  if (obj.disjointSets.deleteSet(x.x)) {
    obj.changed.dispatch();
  }
});

// node_modules/neuroglancer/lib/uint64_map.js
init_legacy_browser();

// node_modules/neuroglancer/lib/gpu_hash/hash_table.js
init_legacy_browser();

// node_modules/neuroglancer/lib/gpu_hash/hash_function.js
init_legacy_browser();
var k1 = 3432918353;
var k2 = 461845907;
function hashCombine(state, value) {
  value >>>= 0;
  state >>>= 0;
  value = Math.imul(value, k1) >>> 0;
  value = (value << 15 | value >>> 17) >>> 0;
  value = Math.imul(value, k2) >>> 0;
  state = (state ^ value) >>> 0;
  state = (state << 13 | state >>> 19) >>> 0;
  state = state * 5 + 3864292196 >>> 0;
  return state;
}

// node_modules/neuroglancer/lib/util/random.js
init_legacy_browser();
function getRandomHexString(numBits = 128) {
  const numValues = Math.ceil(numBits / 32);
  const data = new Uint32Array(numValues);
  crypto.getRandomValues(data);
  let s = "";
  for (let i = 0; i < numValues; ++i) {
    s += ("00000000" + data[i].toString(16)).slice(-8);
  }
  return s;
}
function getRandomValues(array2) {
  const byteArray = new Uint8Array(
    array2.buffer,
    array2.byteOffset,
    array2.byteLength
  );
  const blockSize = 65536;
  for (let i = 0, length6 = byteArray.length; i < length6; i += blockSize) {
    crypto.getRandomValues(
      byteArray.subarray(i, Math.min(length6, i + blockSize))
    );
  }
  return array2;
}

// node_modules/neuroglancer/lib/gpu_hash/hash_table.js
var NUM_ALTERNATIVES = 3;
var DEFAULT_LOAD_FACTOR = 0.8;
var DEBUG2 = false;
var pending = 0n;
var backupPending = 0n;
var HashTableBase = class _HashTableBase {
  constructor(hashSeeds = _HashTableBase.generateHashSeeds(NUM_ALTERNATIVES)) {
    this.hashSeeds = hashSeeds;
    let initialSize = 8;
    while (initialSize < 2 * hashSeeds.length) {
      initialSize *= 2;
    }
    this.allocate(initialSize);
  }
  loadFactor = DEFAULT_LOAD_FACTOR;
  size = 0;
  table;
  tableSize;
  empty = 0xffffffffffffffffn;
  maxRehashAttempts = 5;
  maxAttempts = 5;
  capacity;
  generation = 0;
  mungedEmptyKey;
  updateHashFunctions(numHashes) {
    this.hashSeeds = _HashTableBase.generateHashSeeds(numHashes);
    this.mungedEmptyKey = void 0;
  }
  /**
   * Invokes callback with a modified version of the hash table data array.
   *
   * Replaces all slots that appear to be valid entries for `empty`, i.e. slots that
   * contain `empty` and to which `empty` hashes, with `mungedEmptyKey`.
   *
   * mungedEmptyKey is chosen such that it does not to any of the same slots as `empty`.
   *
   * This allows the modified data array to be used for lookups without special casing the empty
   * key.
   */
  tableWithMungedEmptyKey(callback) {
    const numHashes = this.hashSeeds.length;
    const emptySlots = new Array(numHashes);
    for (let i = 0; i < numHashes; ++i) {
      emptySlots[i] = this.getHash(i, this.empty);
    }
    let { mungedEmptyKey } = this;
    if (mungedEmptyKey === void 0) {
      chooseMungedEmptyKey: while (true) {
        mungedEmptyKey = randomUint64();
        for (let i = 0; i < numHashes; ++i) {
          const h = this.getHash(i, mungedEmptyKey);
          for (let j = 0; j < numHashes; ++j) {
            if (emptySlots[j] === h) {
              continue chooseMungedEmptyKey;
            }
          }
        }
        this.mungedEmptyKey = mungedEmptyKey;
        break;
      }
    }
    const { table, empty } = this;
    for (let i = 0; i < numHashes; ++i) {
      const h = emptySlots[i];
      if (table[h] === empty) {
        table[h] = mungedEmptyKey;
      }
    }
    try {
      callback(table);
    } finally {
      for (let i = 0; i < numHashes; ++i) {
        const h = emptySlots[i];
        if (table[h] === mungedEmptyKey) {
          table[h] = empty;
        }
      }
    }
  }
  static generateHashSeeds(numAlternatives = NUM_ALTERNATIVES) {
    return getRandomValues(new Uint32Array(numAlternatives));
  }
  getHash(hashIndex, x) {
    let hash = this.hashSeeds[hashIndex];
    hash = hashCombine(hash, Number(x & 0xffffffffn));
    hash = hashCombine(hash, Number(x >> 32n));
    return this.entryStride * (hash & this.tableSize - 1);
  }
  /**
   * Iterates over the uint64 keys contained in the hash set.
   */
  *keys() {
    const { empty, entryStride } = this;
    const { table } = this;
    for (let i = 0, length6 = table.length; i < length6; i += entryStride) {
      const key = table[i];
      if (key !== empty) {
        yield key;
      }
    }
  }
  /**
   * Returns the offset into the hash table of the specified element, or -1 if the element is not
   * present.
   */
  indexOf(x) {
    const { table, empty } = this;
    if (x === empty) {
      return -1;
    }
    for (let i = 0, numHashes = this.hashSeeds.length; i < numHashes; ++i) {
      const h = this.getHash(i, x);
      if (table[h] === x) {
        return h;
      }
    }
    return -1;
  }
  /**
   * Changes the empty key to a value that is not equal to the current empty key and is not present
   * in the table.
   *
   * This is called when an attempt is made to insert the empty key.
   */
  chooseAnotherEmptyKey() {
    const { empty, table, entryStride } = this;
    let newKey;
    while (true) {
      newKey = randomUint64();
      if (newKey === empty) {
        continue;
      }
      if (this.has(newKey)) {
        continue;
      }
      break;
    }
    this.empty = newKey;
    for (let h = 0, length6 = table.length; h < length6; h += entryStride) {
      if (table[h] === empty) {
        table[h] = newKey;
      }
    }
  }
  /**
   * Returns true iff the specified element is present.
   */
  has(x) {
    return this.indexOf(x) !== -1;
  }
  delete(x) {
    const index = this.indexOf(x);
    if (index !== -1) {
      const { table } = this;
      table[index] = this.empty;
      ++this.generation;
      this.size--;
      return true;
    }
    return false;
  }
  clearTable() {
    const { table, empty } = this;
    table.fill(empty);
  }
  clear() {
    if (this.size === 0) {
      return false;
    }
    this.size = 0;
    ++this.generation;
    this.clearTable();
    return true;
  }
  reserve(x) {
    if (x > this.capacity) {
      this.backupPending();
      this.grow(x);
      this.restorePending();
      return true;
    }
    return false;
  }
  swapPending(table, offset) {
    const temp = pending;
    this.storePending(table, offset);
    table[offset] = temp;
  }
  storePending(table, offset) {
    pending = table[offset];
  }
  backupPending() {
    backupPending = pending;
  }
  restorePending() {
    pending = backupPending;
  }
  tryToInsert() {
    if (DEBUG2) {
      console.log(`tryToInsert: ${pending}`);
    }
    let attempt = 0;
    const { empty, maxAttempts: maxAttempts2, table } = this;
    const numHashes = this.hashSeeds.length;
    let tableIndex = Math.floor(Math.random() * numHashes);
    while (true) {
      const h = this.getHash(tableIndex, pending);
      this.swapPending(table, h);
      if (pending === empty) {
        return true;
      }
      if (++attempt === maxAttempts2) {
        break;
      }
      tableIndex = (tableIndex + Math.floor(Math.random() * (numHashes - 1)) + 1) % numHashes;
    }
    return false;
  }
  allocate(tableSize) {
    this.tableSize = tableSize;
    const { entryStride } = this;
    this.table = new BigUint64Array(tableSize * entryStride);
    this.maxAttempts = tableSize;
    this.clearTable();
    this.capacity = tableSize * this.loadFactor;
    this.mungedEmptyKey = void 0;
  }
  rehash(oldTable, tableSize) {
    if (DEBUG2) {
      console.log("rehash begin");
    }
    this.allocate(tableSize);
    this.updateHashFunctions(this.hashSeeds.length);
    const { empty, entryStride } = this;
    for (let h = 0, length6 = oldTable.length; h < length6; h += entryStride) {
      const key = oldTable[h];
      if (key !== empty) {
        this.storePending(oldTable, h);
        if (!this.tryToInsert()) {
          if (DEBUG2) {
            console.log("rehash failed");
          }
          return false;
        }
      }
    }
    if (DEBUG2) {
      console.log("rehash end");
    }
    return true;
  }
  grow(desiredTableSize) {
    if (DEBUG2) {
      console.log(`grow: ${desiredTableSize}`);
    }
    const oldTable = this.table;
    let { tableSize } = this;
    while (tableSize < desiredTableSize) {
      tableSize *= 2;
    }
    while (true) {
      for (let rehashAttempt = 0; rehashAttempt < this.maxRehashAttempts; ++rehashAttempt) {
        if (this.rehash(oldTable, tableSize)) {
          if (DEBUG2) {
            console.log("grow end");
          }
          return;
        }
      }
      tableSize *= 2;
    }
  }
  insertInternal() {
    ++this.generation;
    if (pending === this.empty) {
      this.chooseAnotherEmptyKey();
    }
    if (++this.size > this.capacity) {
      this.backupPending();
      this.grow(this.tableSize * 2);
      this.restorePending();
    }
    while (!this.tryToInsert()) {
      this.backupPending();
      this.grow(this.tableSize);
      this.restorePending();
    }
  }
};
var HashSetUint64 = class extends HashTableBase {
  add(x) {
    if (this.has(x)) {
      return false;
    }
    if (DEBUG2) {
      console.log(`add: ${x}`);
    }
    pending = x;
    this.insertInternal();
    return true;
  }
  /**
   * Iterates over the keys.
   */
  [Symbol.iterator]() {
    return this.keys();
  }
};
HashSetUint64.prototype.entryStride = 1;
var pendingValue = 0n;
var backupPendingValue = 0n;
var HashMapUint64 = class extends HashTableBase {
  set(key, value) {
    if (this.has(key)) {
      return false;
    }
    if (DEBUG2) {
      console.log(`add: ${key} -> ${value}`);
    }
    pending = key;
    pendingValue = value;
    this.insertInternal();
    return true;
  }
  get(key) {
    const h = this.indexOf(key);
    if (h === -1) {
      return void 0;
    }
    return this.table[h + 1];
  }
  swapPending(table, offset) {
    const temp = pendingValue;
    super.swapPending(table, offset);
    table[offset + 1] = temp;
  }
  storePending(table, offset) {
    super.storePending(table, offset);
    pendingValue = table[offset + 1];
  }
  backupPending() {
    super.backupPending();
    backupPendingValue = pendingValue;
  }
  restorePending() {
    super.restorePending();
    pendingValue = backupPendingValue;
  }
  /**
   * Iterates over entries.
   */
  [Symbol.iterator]() {
    return this.entries();
  }
  /**
   * Iterates over entries.
   */
  *entries() {
    const { empty, entryStride } = this;
    const { table } = this;
    for (let i = 0, length6 = table.length; i < length6; i += entryStride) {
      const key = table[i];
      if (key !== empty) {
        const value = table[i + 1];
        yield [key, value];
      }
    }
  }
};
HashMapUint64.prototype.entryStride = 2;

// node_modules/neuroglancer/lib/uint64_map.js
var __defProp11 = Object.defineProperty;
var __getOwnPropDesc11 = Object.getOwnPropertyDescriptor;
var __decorateClass10 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc11(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp11(target2, key, result);
  return result;
};
var Uint64Map = class extends SharedObjectCounterpart {
  hashTable = new HashMapUint64();
  changed = new Signal();
  get value() {
    return this;
  }
  static makeWithCounterpart(rpc2) {
    const obj = new Uint64Map();
    obj.initializeCounterpart(rpc2);
    return obj;
  }
  set_(key, value) {
    return this.hashTable.set(key, value);
  }
  set(key, value) {
    if (this.set_(key, value)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Map.set", { id: this.rpcId, key, value });
      }
      this.changed.dispatch(key, true);
    }
  }
  has(key) {
    return this.hashTable.has(key);
  }
  get(key) {
    return this.hashTable.get(key);
  }
  [Symbol.iterator]() {
    return this.hashTable.entries();
  }
  delete_(key) {
    return this.hashTable.delete(key);
  }
  delete(key) {
    if (this.delete_(key)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Map.delete", { id: this.rpcId, key });
      }
      this.changed.dispatch(key, false);
    }
  }
  get size() {
    return this.hashTable.size;
  }
  assignFrom(other) {
    this.clear();
    for (const [key, value] of other) {
      this.set(key, value);
    }
  }
  clear() {
    if (this.hashTable.clear()) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Map.clear", { id: this.rpcId });
      }
      this.changed.dispatch(null, false);
    }
  }
  toJSON() {
    const result = {};
    for (const [key, value] of this.hashTable.entries()) {
      result[key.toString()] = value.toString();
    }
    return result;
  }
};
Uint64Map = __decorateClass10([
  registerSharedObject("Uint64Map")
], Uint64Map);
registerRPC("Uint64Map.set", function(x) {
  const obj = this.get(x.id);
  if (obj.set_(x.key, x.value)) {
    obj.changed.dispatch();
  }
});
registerRPC("Uint64Map.delete", function(x) {
  const obj = this.get(x.id);
  if (obj.delete_(x.key)) {
    obj.changed.dispatch();
  }
});
registerRPC("Uint64Map.clear", function(x) {
  const obj = this.get(x.id);
  if (obj.hashTable.clear()) {
    obj.changed.dispatch();
  }
});

// node_modules/neuroglancer/lib/uint64_set.js
init_legacy_browser();
var __defProp12 = Object.defineProperty;
var __getOwnPropDesc12 = Object.getOwnPropertyDescriptor;
var __decorateClass11 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc12(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp12(target2, key, result);
  return result;
};
var Uint64Set = class extends SharedObjectCounterpart {
  hashTable = new HashSetUint64();
  changed = new Signal();
  get value() {
    return this;
  }
  static makeWithCounterpart(rpc2) {
    const obj = new Uint64Set();
    obj.initializeCounterpart(rpc2);
    return obj;
  }
  set(x, value) {
    if (!value) {
      this.delete(x);
    } else {
      this.add(x);
    }
  }
  reserve_(x) {
    return this.hashTable.reserve(x);
  }
  reserve(x) {
    if (this.reserve_(x)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Set.reserve", { id: this.rpcId, value: x });
      }
    }
  }
  add_(x) {
    let changed = false;
    for (const v of x) {
      changed = this.hashTable.add(v) || changed;
    }
    return changed;
  }
  add(x) {
    const tmp = typeof x === "bigint" ? [x] : x;
    if (this.add_(tmp)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Set.add", { id: this.rpcId, value: tmp });
      }
      this.changed.dispatch(x, true);
    }
  }
  has(x) {
    return this.hashTable.has(x);
  }
  [Symbol.iterator]() {
    return this.hashTable.keys();
  }
  keys() {
    return this.hashTable.keys();
  }
  delete_(x) {
    let changed = false;
    for (const v of x) {
      changed = this.hashTable.delete(v) || changed;
    }
    return changed;
  }
  delete(x) {
    const tmp = typeof x === "bigint" ? [x] : x;
    if (this.delete_(tmp)) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Set.delete", { id: this.rpcId, value: tmp });
      }
      this.changed.dispatch(x, false);
    }
  }
  get size() {
    return this.hashTable.size;
  }
  clear() {
    if (this.hashTable.clear()) {
      const { rpc: rpc2 } = this;
      if (rpc2) {
        rpc2.invoke("Uint64Set.clear", { id: this.rpcId });
      }
      this.changed.dispatch(null, false);
    }
  }
  toJSON() {
    const result = new Array();
    for (const id of this.keys()) {
      result.push(id.toString());
    }
    result.sort();
    return result;
  }
  assignFrom(other) {
    this.clear();
    for (const key of other.keys()) {
      this.add(key);
    }
  }
};
Uint64Set = __decorateClass11([
  registerSharedObject("Uint64Set")
], Uint64Set);
registerRPC("Uint64Set.reserve", function(x) {
  const obj = this.get(x.id);
  if (obj.reserve_(x.value)) {
    obj.changed.dispatch();
  }
});
registerRPC("Uint64Set.add", function(x) {
  const obj = this.get(x.id);
  if (obj.add_(x.value)) {
    obj.changed.dispatch();
  }
});
registerRPC("Uint64Set.delete", function(x) {
  const obj = this.get(x.id);
  if (obj.delete_(x.value)) {
    obj.changed.dispatch();
  }
});
registerRPC("Uint64Set.clear", function(x) {
  const obj = this.get(x.id);
  if (obj.hashTable.clear()) {
    obj.changed.dispatch();
  }
});

// node_modules/neuroglancer/lib/segmentation_display_state/base.js
init_legacy_browser();
var VISIBLE_SEGMENTS_STATE_PROPERTIES = [
  "visibleSegments",
  "segmentEquivalences",
  "temporaryVisibleSegments",
  "temporarySegmentEquivalences",
  "useTemporaryVisibleSegments",
  "useTemporarySegmentEquivalences"
];
function onVisibleSegmentsStateChanged(context, state, callback) {
  context.registerDisposer(state.visibleSegments.changed.add(callback));
  context.registerDisposer(state.segmentEquivalences.changed.add(callback));
}
function onTemporaryVisibleSegmentsStateChanged(context, state, callback) {
  context.registerDisposer(
    state.temporaryVisibleSegments.changed.add(callback)
  );
  context.registerDisposer(
    state.temporarySegmentEquivalences.changed.add(callback)
  );
  context.registerDisposer(
    state.useTemporaryVisibleSegments.changed.add(callback)
  );
  context.registerDisposer(
    state.useTemporarySegmentEquivalences.changed.add(callback)
  );
}
function getObjectKey(objectId) {
  return objectId.toString();
}
function isHighBitSegment(segmentId) {
  return (segmentId & 0x8000000000000000n) !== 0n;
}
function getVisibleSegments(state) {
  return state.useTemporaryVisibleSegments.value ? state.temporaryVisibleSegments : state.visibleSegments;
}
function getSegmentEquivalences(state) {
  return state.useTemporarySegmentEquivalences.value ? state.temporarySegmentEquivalences : state.segmentEquivalences;
}
function forEachVisibleSegment(state, callback) {
  const visibleSegments = getVisibleSegments(state);
  const segmentEquivalences = getSegmentEquivalences(state);
  const equivalencePolicy = segmentEquivalences.disjointSets.visibleSegmentEquivalencePolicy.value;
  for (const rootObjectId of visibleSegments.keys()) {
    if (equivalencePolicy & VisibleSegmentEquivalencePolicy.NONREPRESENTATIVE_EXCLUDED) {
      const rootObjectId2 = segmentEquivalences.get(rootObjectId);
      callback(rootObjectId, rootObjectId2);
    } else {
      if (!segmentEquivalences.disjointSets.isMinElement(rootObjectId)) {
        continue;
      }
      for (const objectId of segmentEquivalences.setElements(rootObjectId)) {
        if (equivalencePolicy & VisibleSegmentEquivalencePolicy.REPRESENTATIVE_EXCLUDED && equivalencePolicy & VisibleSegmentEquivalencePolicy.MAX_REPRESENTATIVE && isHighBitSegment(objectId)) {
          continue;
        }
        callback(objectId, rootObjectId);
      }
    }
  }
}

// node_modules/neuroglancer/lib/segmentation_display_state/backend.js
function receiveVisibleSegmentsState(rpc2, options, target2 = {}) {
  for (const property of VISIBLE_SEGMENTS_STATE_PROPERTIES) {
    target2[property] = rpc2.get(options[property]);
  }
  return target2;
}
var withSegmentationLayerBackendState = (Base) => class SegmentationLayerState extends Base {
  visibleSegments;
  selectedSegments;
  segmentEquivalences;
  temporaryVisibleSegments;
  temporarySegmentEquivalences;
  useTemporaryVisibleSegments;
  useTemporarySegmentEquivalences;
  transform;
  renderScaleTarget;
  constructor(...args) {
    const [rpc2, options] = args;
    super(rpc2, options);
    receiveVisibleSegmentsState(rpc2, options, this);
    this.transform = rpc2.get(options.transform);
    this.renderScaleTarget = rpc2.get(options.renderScaleTarget);
    const scheduleUpdateChunkPriorities = () => {
      this.chunkManager.scheduleUpdateChunkPriorities();
    };
    onTemporaryVisibleSegmentsStateChanged(
      this,
      this,
      scheduleUpdateChunkPriorities
    );
    onVisibleSegmentsStateChanged(this, this, scheduleUpdateChunkPriorities);
    this.registerDisposer(
      this.transform.changed.add(scheduleUpdateChunkPriorities)
    );
    this.registerDisposer(
      this.renderScaleTarget.changed.add(scheduleUpdateChunkPriorities)
    );
  }
};

// node_modules/neuroglancer/lib/annotation/backend.js
var __defProp13 = Object.defineProperty;
var __getOwnPropDesc13 = Object.getOwnPropertyDescriptor;
var __decorateClass12 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc13(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp13(target2, key, result);
  return result;
};
var ANNOTATION_METADATA_CHUNK_PRIORITY = 200;
var ANNOTATION_SEGMENT_FILTERED_CHUNK_PRIORITY = 60;
var AnnotationMetadataChunk = class extends Chunk {
  annotation;
  freeSystemMemory() {
    this.annotation = void 0;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    msg.annotation = this.annotation;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = this.gpuMemoryBytes = 0;
    super.downloadSucceeded();
  }
};
var AnnotationGeometryData = class {
  data;
  typeToOffset;
  typeToIds;
  typeToIdMaps;
  typeToInstanceCounts;
  typeToSize;
  serialize(msg, transfers) {
    msg.data = this.data;
    msg.typeToOffset = this.typeToOffset;
    msg.typeToIds = this.typeToIds;
    msg.typeToIdMaps = this.typeToIdMaps;
    msg.typeToInstanceCounts = this.typeToInstanceCounts;
    msg.typeToSize = this.typeToSize;
    transfers.push(this.data.buffer);
  }
  get numBytes() {
    return this.data.byteLength;
  }
};
function GeometryChunkMixin(Base) {
  class C extends Base {
    data;
    serialize(msg, transfers) {
      super.serialize(msg, transfers);
      const { data } = this;
      if (data !== void 0) {
        data.serialize(msg, transfers);
        this.data = void 0;
      }
    }
    downloadSucceeded() {
      const { data } = this;
      this.systemMemoryBytes = this.gpuMemoryBytes = data === void 0 ? 0 : data.numBytes;
      super.downloadSucceeded();
    }
    freeSystemMemory() {
      this.data = void 0;
    }
  }
  return C;
}
var AnnotationGeometryChunk = class extends GeometryChunkMixin(
  SliceViewChunk
) {
};
var AnnotationSubsetGeometryChunk = class extends GeometryChunkMixin(Chunk) {
  objectId;
};
var AnnotationMetadataChunkSource = class extends ChunkSource {
  parent = void 0;
  getChunk(id) {
    const { chunks } = this;
    let chunk = chunks.get(id);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(AnnotationMetadataChunk);
      chunk.initialize(id);
      this.addChunk(chunk);
    }
    return chunk;
  }
  download(chunk, signal) {
    return this.parent.downloadMetadata(chunk, signal);
  }
};
AnnotationMetadataChunkSource = __decorateClass12([
  registerSharedObject(ANNOTATION_METADATA_CHUNK_SOURCE_RPC_ID)
], AnnotationMetadataChunkSource);
var AnnotationGeometryChunkSourceBackend = class extends SliceViewChunkSourceBackend {
  parent;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.parent = rpc2.get(options.parent);
  }
};
AnnotationGeometryChunkSourceBackend.prototype.chunkConstructor = AnnotationGeometryChunk;
var AnnotationSubsetGeometryChunkSource = class extends ChunkSource {
  parent = void 0;
  relationshipIndex;
  getChunk(objectId) {
    const key = getObjectKey(objectId);
    const { chunks } = this;
    let chunk = chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(AnnotationSubsetGeometryChunk);
      chunk.initialize(key);
      chunk.objectId = objectId;
      this.addChunk(chunk);
    }
    return chunk;
  }
  download(chunk, signal) {
    return this.parent.downloadSegmentFilteredGeometry(
      chunk,
      this.relationshipIndex,
      signal
    );
  }
};
AnnotationSubsetGeometryChunkSource = __decorateClass12([
  registerSharedObject(ANNOTATION_SUBSET_GEOMETRY_CHUNK_SOURCE_RPC_ID)
], AnnotationSubsetGeometryChunkSource);
var AnnotationSource = class extends SharedObjectCounterpart {
  references = /* @__PURE__ */ new Set();
  chunkManager;
  metadataChunkSource;
  segmentFilteredSources;
  constructor(rpc2, options) {
    super(rpc2, options);
    const chunkManager = this.chunkManager = rpc2.get(options.chunkManager);
    const metadataChunkSource = this.metadataChunkSource = this.registerDisposer(
      rpc2.getRef(options.metadataChunkSource)
    );
    this.segmentFilteredSources = options.segmentFilteredSource.map(
      (x, i) => {
        const source = this.registerDisposer(
          rpc2.getRef(x)
        );
        source.parent = this;
        source.relationshipIndex = i;
        return source;
      }
    );
    metadataChunkSource.parent = this;
    this.registerDisposer(
      chunkManager.recomputeChunkPriorities.add(
        () => this.recomputeChunkPriorities()
      )
    );
  }
  recomputeChunkPriorities() {
    const { chunkManager, metadataChunkSource } = this;
    for (const id of this.references) {
      chunkManager.requestChunk(
        metadataChunkSource.getChunk(id),
        ChunkPriorityTier.VISIBLE,
        ANNOTATION_METADATA_CHUNK_PRIORITY
      );
    }
  }
  add(annotation) {
    annotation;
    throw new Error("Not implemented");
  }
  delete(id) {
    id;
    throw new Error("Not implemented");
  }
  update(id, newAnnotation) {
    id;
    newAnnotation;
    throw new Error("Not implemented");
  }
};
registerRPC(ANNOTATION_REFERENCE_ADD_RPC_ID, function(x) {
  const obj = this.get(x.id);
  obj.references.add(x.annotation);
  obj.chunkManager.scheduleUpdateChunkPriorities();
});
registerRPC(ANNOTATION_REFERENCE_DELETE_RPC_ID, function(x) {
  const obj = this.get(x.id);
  obj.references.delete(x.annotation);
  obj.chunkManager.scheduleUpdateChunkPriorities();
});
registerRPC(ANNOTATION_COMMIT_UPDATE_RPC_ID, function(x) {
  const obj = this.get(x.id);
  const annotationId = x.annotationId;
  const newAnnotation = x.newAnnotation;
  let promise;
  if (annotationId === void 0) {
    promise = obj.add(newAnnotation).then((id) => ({ ...newAnnotation, id }));
  } else if (newAnnotation === null) {
    promise = obj.delete(annotationId).then(() => null);
  } else {
    promise = obj.update(annotationId, newAnnotation).then(() => newAnnotation);
  }
  promise.then(
    (result) => {
      if (!obj.wasDisposed) {
        this.invoke(ANNOTATION_COMMIT_UPDATE_RESULT_RPC_ID, {
          id: obj.rpcId,
          annotationId: annotationId || newAnnotation.id,
          newAnnotation: result
        });
      }
    },
    (error) => {
      if (!obj.wasDisposed) {
        this.invoke(ANNOTATION_COMMIT_UPDATE_RESULT_RPC_ID, {
          id: obj.rpcId,
          annotationId: annotationId || (newAnnotation == null ? void 0 : newAnnotation.id),
          error: error.message
        });
      }
    }
  );
});
var AnnotationSpatiallyIndexedRenderLayerBackend = class extends withChunkManager(
  RenderLayerBackend
) {
  localPosition;
  renderScaleTarget;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.renderScaleTarget = rpc2.get(options.renderScaleTarget);
    this.localPosition = rpc2.get(options.localPosition);
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    this.registerDisposer(
      this.localPosition.changed.add(scheduleUpdateChunkPriorities)
    );
    this.registerDisposer(
      this.renderScaleTarget.changed.add(scheduleUpdateChunkPriorities)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(
        () => this.recomputeChunkPriorities()
      )
    );
  }
  attach(attachment) {
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    const { view } = attachment;
    attachment.registerDisposer(scheduleUpdateChunkPriorities);
    attachment.registerDisposer(
      view.projectionParameters.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(
      view.visibility.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.state = {
      displayDimensionRenderInfo: view.projectionParameters.value.displayDimensionRenderInfo,
      transformedSources: []
    };
  }
  recomputeChunkPriorities() {
    this.chunkManager.registerLayer(this);
    for (const attachment of this.attachments.values()) {
      const { view } = attachment;
      const visibility = view.visibility.value;
      if (visibility === Number.NEGATIVE_INFINITY) {
        continue;
      }
      const attachmentState = attachment.state;
      const { transformedSources } = attachmentState;
      if (transformedSources.length === 0 || !validateDisplayDimensionRenderInfoProperty(
        attachmentState,
        view.projectionParameters.value.displayDimensionRenderInfo
      )) {
        continue;
      }
      const priorityTier = getPriorityTier(visibility);
      const basePriority = getBasePriority(visibility);
      const projectionParameters = view.projectionParameters.value;
      const { chunkManager } = this;
      forEachVisibleAnnotationChunk(
        projectionParameters,
        this.localPosition.value,
        this.renderScaleTarget.value,
        transformedSources[0],
        () => {
        },
        (tsource, scaleIndex) => {
          const chunk = tsource.source.getChunk(tsource.curPositionInChunks);
          ++this.numVisibleChunksNeeded;
          if (chunk.state === ChunkState.GPU_MEMORY) {
            ++this.numVisibleChunksAvailable;
          }
          const priority = 0;
          chunkManager.requestChunk(
            chunk,
            priorityTier,
            basePriority + priority + SCALE_PRIORITY_MULTIPLIER * scaleIndex
          );
        }
      );
    }
  }
};
AnnotationSpatiallyIndexedRenderLayerBackend = __decorateClass12([
  registerSharedObject(ANNOTATION_SPATIALLY_INDEXED_RENDER_LAYER_RPC_ID)
], AnnotationSpatiallyIndexedRenderLayerBackend);
registerRPC(
  ANNOTATION_PERSPECTIVE_RENDER_LAYER_UPDATE_SOURCES_RPC_ID,
  function(x) {
    const view = this.get(x.view);
    const layer = this.get(
      x.layer
    );
    const attachment = layer.attachments.get(
      view
    );
    attachment.state.transformedSources = deserializeTransformedSources(this, x.sources, layer);
    attachment.state.displayDimensionRenderInfo = x.displayDimensionRenderInfo;
    layer.chunkManager.scheduleUpdateChunkPriorities();
  }
);
var AnnotationLayerSharedObjectCounterpart = class extends withSharedVisibility(
  withChunkManager(ChunkRenderLayerBackend)
) {
  source;
  segmentationStates;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = rpc2.get(options.source);
    this.segmentationStates = new WatchableValue(
      this.getSegmentationState(options.segmentationStates)
    );
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    this.registerDisposer(
      registerNested((context, states) => {
        if (states === void 0) return;
        for (const state of states) {
          if (state == null) continue;
          onVisibleSegmentsStateChanged(
            context,
            state,
            scheduleUpdateChunkPriorities
          );
          onTemporaryVisibleSegmentsStateChanged(
            context,
            state,
            scheduleUpdateChunkPriorities
          );
        }
        scheduleUpdateChunkPriorities();
      }, this.segmentationStates)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(
        () => this.recomputeChunkPriorities()
      )
    );
  }
  recomputeChunkPriorities() {
    const visibility = this.visibility.value;
    if (visibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    const {
      segmentationStates: { value: states },
      source: { segmentFilteredSources }
    } = this;
    if (states === void 0) return;
    const { chunkManager } = this;
    chunkManager.registerLayer(this);
    const numRelationships = states.length;
    for (let i = 0; i < numRelationships; ++i) {
      const state = states[i];
      if (state == null) {
        continue;
      }
      const priorityTier = getPriorityTier(visibility);
      const basePriority = getBasePriority(visibility);
      const source = segmentFilteredSources[i];
      forEachVisibleSegment(state, (objectId) => {
        const chunk = source.getChunk(objectId);
        ++this.numVisibleChunksNeeded;
        if (chunk.state === ChunkState.GPU_MEMORY) {
          ++this.numVisibleChunksAvailable;
        }
        chunkManager.requestChunk(
          chunk,
          priorityTier,
          basePriority + ANNOTATION_SEGMENT_FILTERED_CHUNK_PRIORITY
        );
      });
    }
  }
  getSegmentationState(msg) {
    if (msg === void 0) return void 0;
    return msg.map((x) => {
      if (x == null) {
        return x;
      }
      return receiveVisibleSegmentsState(this.rpc, x);
    });
  }
};
AnnotationLayerSharedObjectCounterpart = __decorateClass12([
  registerSharedObject(ANNOTATION_RENDER_LAYER_RPC_ID)
], AnnotationLayerSharedObjectCounterpart);
registerRPC(ANNOTATION_RENDER_LAYER_UPDATE_SEGMENTATION_RPC_ID, function(x) {
  const obj = this.get(x.id);
  obj.segmentationStates.value = obj.getSegmentationState(x.segmentationStates);
});

// node_modules/neuroglancer/lib/datasource/enabled_backend_modules.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/boss/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/boss/api.js
init_legacy_browser();

// node_modules/neuroglancer/lib/credentials_provider/http_request.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/http_request.js
init_legacy_browser();
var HttpError = class _HttpError extends Error {
  url;
  status;
  statusText;
  response;
  constructor(url, status, statusText, response, options) {
    let message = `Fetching ${JSON.stringify(
      url
    )} resulted in HTTP error ${status}`;
    if (statusText) {
      message += `: ${statusText}`;
    }
    message += ".";
    super(message, options);
    this.name = "HttpError";
    this.message = message;
    this.url = url;
    this.status = status;
    this.statusText = statusText;
    if (response) {
      this.response = response;
    }
  }
  static fromResponse(response) {
    return new _HttpError(
      response.url,
      response.status,
      response.statusText,
      response
    );
  }
  static fromRequestError(input, error) {
    if (error instanceof TypeError) {
      let url;
      if (typeof input === "string") {
        url = input;
      } else {
        url = input.url;
      }
      return new _HttpError(url, 0, "Network or CORS error", void 0, {
        cause: error
      });
    }
    return error;
  }
};
var maxAttempts = 32;
var minDelayMilliseconds = 500;
var maxDelayMilliseconds = 1e4;
function pickDelay(attemptNumber) {
  return Math.min(
    2 ** attemptNumber * minDelayMilliseconds,
    maxDelayMilliseconds / 2
  ) * (1 + Math.random());
}
async function fetchOk(input, init) {
  var _a;
  for (let requestAttempt = 0; ; ) {
    (_a = init == null ? void 0 : init.signal) == null ? void 0 : _a.throwIfAborted();
    let response;
    try {
      response = await fetch(input, init);
    } catch (error) {
      throw HttpError.fromRequestError(input, error);
    }
    if (!response.ok) {
      const { status } = response;
      if (status === 429 || status === 503 || status === 504) {
        if (++requestAttempt !== maxAttempts) {
          await new Promise(
            (resolve) => setTimeout(resolve, pickDelay(requestAttempt - 1))
          );
          continue;
        }
      }
      throw HttpError.fromResponse(response);
    }
    return response;
  }
}
function isNotFoundError(e) {
  if (!(e instanceof HttpError)) return false;
  return e.status === 0 || e.status === 403 || e.status === 404;
}

// node_modules/neuroglancer/lib/credentials_provider/http_request.js
var maxCredentialsAttempts = 3;
async function fetchOkWithCredentials(credentialsProvider, input, init, applyCredentials2, errorHandler2) {
  var _a;
  let credentials;
  for (let credentialsAttempt = 0; ; ) {
    (_a = init.signal) == null ? void 0 : _a.throwIfAborted();
    if (credentialsAttempt > 1) {
      await new Promise(
        (resolve) => setTimeout(resolve, pickDelay(credentialsAttempt - 2))
      );
    }
    credentials = await credentialsProvider.get(credentials, {
      signal: init.signal ?? void 0,
      progressListener: init.progressListener
    });
    try {
      return await fetchOk(
        typeof input === "function" ? input(credentials.credentials) : input,
        applyCredentials2(credentials.credentials, init)
      );
    } catch (error) {
      if (error instanceof HttpError) {
        if (errorHandler2(error, credentials.credentials) === "refresh") {
          if (++credentialsAttempt === maxCredentialsAttempts) throw error;
          continue;
        }
      }
      throw error;
    }
  }
}
function fetchOkWithCredentialsAdapter(credentialsProvider, applyCredentials2, errorHandler2) {
  return (input, init = {}) => fetchOkWithCredentials(
    credentialsProvider,
    input,
    init,
    applyCredentials2,
    errorHandler2
  );
}

// node_modules/neuroglancer/lib/datasource/boss/api.js
async function fetchWithBossCredentials(credentialsProvider, input, init) {
  return fetchOk(input, init).catch((error) => {
    if (error.status !== 500 && error.status !== 401 && error.status !== 403 && error.status !== 504) {
      throw error;
    }
    return fetchOkWithCredentials(
      credentialsProvider,
      input,
      init,
      (credentials) => {
        const headers = new Headers(init.headers);
        headers.set("Authorization", `Bearer ${credentials}`);
        return { ...init, headers };
      },
      (error2) => {
        const { status } = error2;
        if (status === 403 || status === 401) {
          return "refresh";
        }
        throw error2;
      }
    );
  });
}

// node_modules/neuroglancer/lib/datasource/boss/base.js
init_legacy_browser();
var BossSourceParameters = class {
  baseUrl;
  collection;
  experiment;
  channel;
  resolution;
};
var VolumeChunkSourceParameters = class extends BossSourceParameters {
  encoding;
  window;
  static RPC_ID = "boss/VolumeChunkSource";
  static stringify(parameters) {
    return `boss:volume:${parameters.baseUrl}/${parameters.collection}/${parameters.experiment}/${parameters.channel}/${parameters.resolution}/${parameters.encoding}`;
  }
};
var MeshSourceParameters = class {
  baseUrl;
  static RPC_ID = "boss/MeshChunkSource";
  static stringify(parameters) {
    return `boss:mesh:${parameters.baseUrl}`;
  }
};

// node_modules/neuroglancer/lib/mesh/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/mesh/base.js
init_legacy_browser();
var MESH_LAYER_RPC_ID = "mesh/MeshLayer";
var MULTISCALE_MESH_LAYER_RPC_ID = "mesh/MultiscaleMeshLayer";
var FRAGMENT_SOURCE_RPC_ID = "mesh/FragmentSource";
var MULTISCALE_FRAGMENT_SOURCE_RPC_ID = "mesh/MultiscaleFragmentSource";
var VertexPositionFormat = /* @__PURE__ */ ((VertexPositionFormat2) => {
  VertexPositionFormat2[VertexPositionFormat2["float32"] = 0] = "float32";
  VertexPositionFormat2[VertexPositionFormat2["uint10"] = 1] = "uint10";
  VertexPositionFormat2[VertexPositionFormat2["uint16"] = 2] = "uint16";
  return VertexPositionFormat2;
})(VertexPositionFormat || {});

// node_modules/neuroglancer/lib/mesh/multiscale.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/zorder.js
init_legacy_browser();
function getOctreeChildIndex(x, y, z) {
  return x & 1 | y << 1 & 2 | z << 2 & 4;
}
function decodeZIndexCompressed(zindex, xBits, yBits, zBits) {
  const maxCoordBits = Math.max(xBits, yBits, zBits);
  let inputBit = 0;
  let x = 0;
  let y = 0;
  let z = 0;
  for (let coordBit = 0; coordBit < maxCoordBits; ++coordBit) {
    if (coordBit < xBits) {
      const bit = Number(zindex >> BigInt(inputBit++) & BigInt(1));
      x |= bit << coordBit;
    }
    if (coordBit < yBits) {
      const bit = Number(zindex >> BigInt(inputBit++) & BigInt(1));
      y |= bit << coordBit;
    }
    if (coordBit < zBits) {
      const bit = Number(zindex >> BigInt(inputBit++) & BigInt(1));
      z |= bit << coordBit;
    }
  }
  return Uint32Array.of(x, y, z);
}
function encodeZIndexCompressed3d(xBits, yBits, zBits, x, y, z) {
  const maxBits = Math.max(xBits, yBits, zBits);
  let outputBit = 0;
  let zIndex = 0n;
  function writeBit(b) {
    zIndex |= BigInt(b) << BigInt(outputBit++);
  }
  for (let bit = 0; bit < maxBits; ++bit) {
    if (bit < xBits) {
      writeBit(x >> bit & 1);
    }
    if (bit < yBits) {
      writeBit(y >> bit & 1);
    }
    if (bit < zBits) {
      writeBit(z >> bit & 1);
    }
  }
  return zIndex;
}
function encodeZIndexCompressed(position3, shape) {
  let zIndex = 0n;
  let outputBit = 0;
  const rank = position3.length;
  function writeBit(b) {
    zIndex |= BigInt(b & 1) << BigInt(outputBit++);
  }
  for (let bit = 0; bit < 32; ++bit) {
    for (let dim = 0; dim < rank; ++dim) {
      if (shape[dim] - 1 >>> bit) {
        writeBit(position3[dim] >>> bit);
      }
    }
  }
  return zIndex;
}
function lessMsb(a, b) {
  return a < b && a < (a ^ b);
}
function zorder3LessThan(x0, y0, z0, x1, y1, z1) {
  let mostSignificant0 = z0;
  let mostSignificant1 = z1;
  if (lessMsb(mostSignificant0 ^ mostSignificant1, y0 ^ y1)) {
    mostSignificant0 = y0;
    mostSignificant1 = y1;
  }
  if (lessMsb(mostSignificant0 ^ mostSignificant1, x0 ^ x1)) {
    mostSignificant0 = x0;
    mostSignificant1 = x1;
  }
  return mostSignificant0 < mostSignificant1;
}

// node_modules/neuroglancer/lib/mesh/multiscale.js
function getDesiredMultiscaleMeshChunks(manifest, modelViewProjection, clippingPlanes, detailCutoff, viewportWidth, viewportHeight, callback) {
  const { octree, lodScales, chunkGridSpatialOrigin, chunkShape } = manifest;
  const maxLod = lodScales.length - 1;
  const m00 = modelViewProjection[0];
  const m01 = modelViewProjection[4];
  const m02 = modelViewProjection[8];
  const m10 = modelViewProjection[1];
  const m11 = modelViewProjection[5];
  const m12 = modelViewProjection[9];
  const m30 = modelViewProjection[3];
  const m31 = modelViewProjection[7];
  const m32 = modelViewProjection[11];
  const m33 = modelViewProjection[15];
  const minWXcoeff = m30 > 0 ? 0 : 1;
  const minWYcoeff = m31 > 0 ? 0 : 1;
  const minWZcoeff = m32 > 0 ? 0 : 1;
  const nearA = clippingPlanes[4 * 4];
  const nearB = clippingPlanes[4 * 4 + 1];
  const nearC = clippingPlanes[4 * 4 + 2];
  const nearD = clippingPlanes[4 * 4 + 3];
  function getPointW(x, y, z) {
    return m30 * x + m31 * y + m32 * z + m33;
  }
  function getBoxW(xLower, yLower, zLower, xUpper, yUpper, zUpper) {
    return getPointW(
      xLower + minWXcoeff * (xUpper - xLower),
      yLower + minWYcoeff * (yUpper - yLower),
      zLower + minWZcoeff * (zUpper - zLower)
    );
  }
  const minWClip = getPointW(-nearD * nearA, -nearD * nearB, -nearD * nearC);
  const objectXLower = manifest.clipLowerBound[0];
  const objectYLower = manifest.clipLowerBound[1];
  const objectZLower = manifest.clipLowerBound[2];
  const objectXUpper = manifest.clipUpperBound[0];
  const objectYUpper = manifest.clipUpperBound[1];
  const objectZUpper = manifest.clipUpperBound[2];
  const xScale = Math.sqrt(
    (m00 * viewportWidth) ** 2 + (m10 * viewportHeight) ** 2
  );
  const yScale = Math.sqrt(
    (m01 * viewportWidth) ** 2 + (m11 * viewportHeight) ** 2
  );
  const zScale = Math.sqrt(
    (m02 * viewportWidth) ** 2 + (m12 * viewportHeight) ** 2
  );
  const scaleFactor = Math.max(xScale, yScale, zScale);
  function handleChunk(lod, row, priorLodScale) {
    const size = 1 << lod;
    const rowOffset = row * 5;
    const gridX = octree[rowOffset];
    const gridY = octree[rowOffset + 1];
    const gridZ = octree[rowOffset + 2];
    const childBegin = octree[rowOffset + 3];
    const childEndAndEmpty = octree[rowOffset + 4];
    let xLower = gridX * size * chunkShape[0] + chunkGridSpatialOrigin[0];
    let yLower = gridY * size * chunkShape[1] + chunkGridSpatialOrigin[1];
    let zLower = gridZ * size * chunkShape[2] + chunkGridSpatialOrigin[2];
    let xUpper = xLower + size * chunkShape[0];
    let yUpper = yLower + size * chunkShape[1];
    let zUpper = zLower + size * chunkShape[2];
    xLower = Math.max(xLower, objectXLower);
    yLower = Math.max(yLower, objectYLower);
    zLower = Math.max(zLower, objectZLower);
    xUpper = Math.min(xUpper, objectXUpper);
    yUpper = Math.min(yUpper, objectYUpper);
    zUpper = Math.min(zUpper, objectZUpper);
    if (isAABBVisible(
      xLower,
      yLower,
      zLower,
      xUpper,
      yUpper,
      zUpper,
      clippingPlanes
    )) {
      const minW = Math.max(
        minWClip,
        getBoxW(xLower, yLower, zLower, xUpper, yUpper, zUpper)
      );
      const pixelSize = minW / scaleFactor;
      if (priorLodScale === 0 || pixelSize * detailCutoff < priorLodScale) {
        const lodScale = lodScales[lod];
        if (lodScale !== 0) {
          callback(lod, row, lodScale / pixelSize, childEndAndEmpty >>> 31);
        }
        if (lod > 0 && (lodScale === 0 || pixelSize * detailCutoff < lodScale)) {
          const nextPriorLodScale = lodScale === 0 ? priorLodScale : lodScale;
          const childEnd = (childEndAndEmpty & 2147483647) >>> 0;
          for (let childRow = childBegin; childRow < childEnd; ++childRow) {
            handleChunk(lod - 1, childRow, nextPriorLodScale);
          }
        }
      }
    }
  }
  handleChunk(maxLod, octree.length / 5 - 1, 0);
}

// node_modules/neuroglancer/lib/mesh/triangle_strips.js
init_legacy_browser();
var DEBUG_TIMING = false;
function normalizeTriangleVertexOrder(indices) {
  let maxVertex = 0;
  for (let i = 0, length6 = indices.length; i < length6; i += 3) {
    let a = indices[i];
    let b = indices[i + 1];
    let c = indices[i + 2];
    let t;
    if (a > b) {
      t = a;
      a = b;
      b = t;
    }
    if (b > c) {
      t = b;
      b = c;
      c = t;
    }
    if (a > b) {
      t = a;
      a = b;
      b = t;
    }
    indices[i] = a;
    indices[i + 1] = b;
    indices[i + 2] = c;
    if (c > maxVertex) maxVertex = c;
  }
  return maxVertex;
}
var collisions = 0;
function hashTableInsert(table, numBuckets, value, emptyValue, hashCode, equals6) {
  const mask = numBuckets - 1 >>> 0;
  let bucket = (hashCode & mask) >>> 0;
  for (let probe = 0; ; ++probe) {
    const x = table[bucket];
    if (x === emptyValue) {
      table[bucket] = value;
      return value;
    }
    if (equals6(x)) {
      return x;
    }
    ++collisions;
    bucket = (bucket + probe + 1 & mask) >>> 0;
  }
}
function hashEdge(a, b) {
  return hashCombine(hashCombine(0, a), b);
}
var nextEdgeTable = 1053042;
function getNextEdge(edgeIndexAndFlipped) {
  return nextEdgeTable >>> edgeIndexAndFlipped * 3 & 7;
}
function getBaseIndex(entry) {
  return (entry >>> 2) * 3;
}
function getEdgeIndex(entry) {
  return entry & 3;
}
function vertexAIndex(edgeIndex) {
  return edgeIndex >>> 1;
}
function vertexBIndex(edgeIndex) {
  return 1 + (edgeIndex + 1 >>> 1);
}
function vertexCIndex(edgeIndex) {
  return 2 - edgeIndex;
}
function getEdgeMapSize(numIndices) {
  const numEdges = numIndices;
  const edgeMapSize = 2 ** Math.ceil(Math.log2(numEdges));
  return edgeMapSize * 4;
}
function computeTriangleAdjacencies(triangleAdjacencies, indices, edgeMap) {
  const numTriangles = indices.length / 3;
  const edgeMapSize = edgeMap.length;
  const emptyEntry = 4294967295;
  triangleAdjacencies.fill(emptyEntry);
  edgeMap.fill(emptyEntry);
  for (let triangle = 0; triangle < numTriangles; ++triangle) {
    const baseIndex = triangle * 3;
    for (let edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
      const vertexA0 = indices[baseIndex + vertexAIndex(edgeIndex)];
      const vertexB0 = indices[baseIndex + vertexBIndex(edgeIndex)];
      const newEntry = triangle << 2 | edgeIndex;
      const existingEntry = hashTableInsert(
        edgeMap,
        edgeMapSize,
        newEntry,
        emptyEntry,
        hashEdge(vertexA0, vertexB0),
        (x) => {
          const otherBaseIndex = getBaseIndex(x);
          const otherEdgeIndex = getEdgeIndex(x);
          const vertexA1 = indices[otherBaseIndex + vertexAIndex(otherEdgeIndex)];
          const vertexB1 = indices[otherBaseIndex + vertexBIndex(otherEdgeIndex)];
          return vertexA0 === vertexA1 && vertexB0 === vertexB1;
        }
      );
      if (existingEntry !== newEntry) {
        const otherBaseIndex = getBaseIndex(existingEntry);
        const otherEdgeIndex = getEdgeIndex(existingEntry);
        triangleAdjacencies[otherBaseIndex + otherEdgeIndex] = newEntry;
        triangleAdjacencies[baseIndex + edgeIndex] = existingEntry;
      }
    }
  }
  return triangleAdjacencies;
}
function emitTriangleStrips(indices, triangleAdjacencies, output, outputIndex) {
  const invalidVertex = ~0 >>> 32 - 8 * output.BYTES_PER_ELEMENT;
  const numIndices = indices.length;
  const numTriangles = numIndices / 3;
  const emptyEntry = 4294967295;
  startNewStrip: for (let triangle = 0; triangle < numTriangles; ++triangle) {
    let baseIndex = triangle * 3;
    if (indices[baseIndex] === invalidVertex) {
      continue;
    }
    for (let edgeIndex = 0; edgeIndex < 3; ++edgeIndex) {
      let entry = triangleAdjacencies[baseIndex + edgeIndex];
      if (entry === emptyEntry) continue;
      let otherBaseIndex = getBaseIndex(entry);
      if (indices[otherBaseIndex] === invalidVertex) continue;
      const otherEdgeIndex = getEdgeIndex(entry);
      output[outputIndex++] = indices[baseIndex + vertexCIndex(edgeIndex)];
      output[outputIndex++] = indices[baseIndex + vertexAIndex(edgeIndex)];
      output[outputIndex++] = indices[baseIndex + vertexBIndex(edgeIndex)];
      let edgeIndexAndFlipped = otherEdgeIndex;
      while (true) {
        indices[baseIndex] = invalidVertex;
        baseIndex = otherBaseIndex;
        output[outputIndex++] = indices[baseIndex + vertexCIndex(edgeIndexAndFlipped & 3)];
        edgeIndexAndFlipped = getNextEdge(edgeIndexAndFlipped);
        entry = triangleAdjacencies[baseIndex + (edgeIndexAndFlipped & 3)];
        if (entry === emptyEntry || indices[otherBaseIndex = getBaseIndex(entry)] === invalidVertex) {
          output[outputIndex++] = invalidVertex;
          indices[baseIndex] = invalidVertex;
          continue startNewStrip;
        }
        edgeIndexAndFlipped = getEdgeIndex(entry) | edgeIndexAndFlipped & 4;
      }
    }
    output[outputIndex++] = indices[baseIndex];
    output[outputIndex++] = indices[baseIndex + 1];
    output[outputIndex++] = indices[baseIndex + 2];
    indices[baseIndex] = invalidVertex;
    output[outputIndex++] = invalidVertex;
  }
  return outputIndex;
}
function computeTriangleStrips(indices, subChunkOffsets) {
  if (indices.length === 0) return indices;
  collisions = 0;
  if (subChunkOffsets === void 0) {
    subChunkOffsets = Uint32Array.of(0, indices.length);
  }
  let adjacenciesElapsed = 0;
  let emitElapsed = 0;
  let startTime = 0;
  let midTime = 0;
  let endTime = 0;
  const maxVertexIndex = normalizeTriangleVertexOrder(indices);
  const outputBufferSize = indices.length / 3 * 4;
  const output = maxVertexIndex >= 65535 ? new Uint32Array(outputBufferSize) : new Uint16Array(outputBufferSize);
  let outputIndex = 0;
  let maxSubChunkIndices = 0;
  const numSubChunks = subChunkOffsets.length - 1;
  for (let subChunk = 0; subChunk < numSubChunks; ++subChunk) {
    maxSubChunkIndices = Math.max(
      maxSubChunkIndices,
      subChunkOffsets[subChunk + 1] - subChunkOffsets[subChunk]
    );
  }
  const triangleAdjacencies = new Uint32Array(maxSubChunkIndices);
  const edgeMap = new Uint32Array(getEdgeMapSize(maxSubChunkIndices));
  let subChunkOffset = subChunkOffsets[0];
  for (let subChunk = 0; subChunk < numSubChunks; ++subChunk) {
    subChunkOffsets[subChunk] = outputIndex;
    const subChunkEnd = subChunkOffsets[subChunk + 1];
    const subIndices = indices.subarray(subChunkOffset, subChunkEnd);
    if (DEBUG_TIMING) startTime = Date.now();
    computeTriangleAdjacencies(triangleAdjacencies, subIndices, edgeMap);
    if (DEBUG_TIMING) midTime = Date.now();
    outputIndex = emitTriangleStrips(
      subIndices,
      triangleAdjacencies,
      output,
      outputIndex
    );
    if (DEBUG_TIMING) {
      endTime = Date.now();
      adjacenciesElapsed += midTime - startTime;
      emitElapsed += endTime - midTime;
    }
    subChunkOffset = subChunkEnd;
  }
  --outputIndex;
  subChunkOffsets[numSubChunks] = outputIndex;
  const shrunkOutput = new output.constructor(outputIndex);
  shrunkOutput.set(output.subarray(0, outputIndex));
  if (DEBUG_TIMING) {
    console.log(
      `reduced from ${indices.byteLength}(${indices.BYTES_PER_ELEMENT}) -> ${shrunkOutput.byteLength}(${shrunkOutput.BYTES_PER_ELEMENT}): adj=${adjacenciesElapsed}, emit=${emitElapsed}, ${collisions}/${indices.length} collisions`
    );
  }
  return shrunkOutput;
}

// node_modules/neuroglancer/lib/util/endian.js
init_legacy_browser();
var Endianness = /* @__PURE__ */ ((Endianness2) => {
  Endianness2[Endianness2["LITTLE"] = 0] = "LITTLE";
  Endianness2[Endianness2["BIG"] = 1] = "BIG";
  return Endianness2;
})(Endianness || {});
function determineEndianness() {
  const a = Uint16Array.of(4386);
  const b = new Uint8Array(a.buffer);
  return b[0] === 17 ? 1 : 0;
}
var ENDIANNESS = determineEndianness();
function swapEndian16(array2) {
  const view = new Uint8Array(array2.buffer, array2.byteOffset, array2.byteLength);
  for (let i = 0, length6 = view.length; i < length6; i += 2) {
    const temp = view[i];
    view[i] = view[i + 1];
    view[i + 1] = temp;
  }
}
function swapEndian32(array2) {
  const view = new Uint8Array(array2.buffer, array2.byteOffset, array2.byteLength);
  for (let i = 0, length6 = view.length; i < length6; i += 4) {
    let temp = view[i];
    view[i] = view[i + 3];
    view[i + 3] = temp;
    temp = view[i + 1];
    view[i + 1] = view[i + 2];
    view[i + 2] = temp;
  }
}
function swapEndian64(array2) {
  const view = new Uint8Array(array2.buffer, array2.byteOffset, array2.byteLength);
  for (let i = 0, length6 = view.length; i < length6; i += 8) {
    let temp = view[i];
    view[i] = view[i + 7];
    view[i + 7] = temp;
    temp = view[i + 1];
    view[i + 1] = view[i + 6];
    view[i + 6] = temp;
    temp = view[i + 2];
    view[i + 2] = view[i + 5];
    view[i + 5] = temp;
    temp = view[i + 3];
    view[i + 3] = view[i + 4];
    view[i + 4] = temp;
  }
}
function convertEndian16(array2, source, target2 = ENDIANNESS) {
  if (source !== target2) {
    swapEndian16(array2);
  }
}
function convertEndian32(array2, source, target2 = ENDIANNESS) {
  if (source !== target2) {
    swapEndian32(array2);
  }
}
function convertEndian64(array2, source, target2 = ENDIANNESS) {
  if (source !== target2) {
    swapEndian64(array2);
  }
}
function convertEndian(array2, source, elementBytes, target2 = ENDIANNESS) {
  if (source === target2 || elementBytes === 1) return;
  switch (elementBytes) {
    case 2:
      swapEndian16(array2);
      break;
    case 4:
      swapEndian32(array2);
      break;
    case 8:
      swapEndian64(array2);
      break;
  }
}

// node_modules/neuroglancer/lib/mesh/backend.js
var __defProp14 = Object.defineProperty;
var __getOwnPropDesc14 = Object.getOwnPropertyDescriptor;
var __decorateClass13 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc14(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp14(target2, key, result);
  return result;
};
var MESH_OBJECT_MANIFEST_CHUNK_PRIORITY = 100;
var MESH_OBJECT_FRAGMENT_CHUNK_PRIORITY = 50;
var CONVERT_TO_TRIANGLE_STRIPS = false;
var ManifestChunk = class extends Chunk {
  objectId = 0n;
  fragmentIds;
  // We can't save a reference to objectId, because it may be a temporary
  // object.
  initializeManifestChunk(key, objectId) {
    super.initialize(key);
    this.objectId = objectId;
  }
  freeSystemMemory() {
    this.fragmentIds = null;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    msg.fragmentIds = this.fragmentIds;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = 100;
    this.gpuMemoryBytes = 0;
    super.downloadSucceeded();
    if (this.priorityTier < ChunkPriorityTier.RECENT) {
      this.source.chunkManager.scheduleUpdateChunkPriorities();
    }
  }
  toString() {
    return this.objectId.toString();
  }
};
function serializeMeshData(data, msg, transfers) {
  const { vertexPositions, indices, vertexNormals, strips } = data;
  msg.vertexPositions = vertexPositions;
  msg.indices = indices;
  msg.strips = strips;
  msg.vertexNormals = vertexNormals;
  const vertexPositionsBuffer = vertexPositions.buffer;
  transfers.push(vertexPositionsBuffer);
  const indicesBuffer = indices.buffer;
  if (indicesBuffer !== vertexPositionsBuffer) {
    transfers.push(indicesBuffer);
  }
  transfers.push(vertexNormals.buffer);
}
function getMeshDataSize(data) {
  const { vertexPositions, indices, vertexNormals } = data;
  return vertexPositions.byteLength + indices.byteLength + vertexNormals.byteLength;
}
var FragmentChunk = class extends Chunk {
  manifestChunk = null;
  fragmentId = null;
  meshData = null;
  initializeFragmentChunk(key, manifestChunk, fragmentId) {
    super.initialize(key);
    this.manifestChunk = manifestChunk;
    this.fragmentId = fragmentId;
  }
  freeSystemMemory() {
    this.manifestChunk = null;
    this.meshData = null;
    this.fragmentId = null;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    serializeMeshData(this.meshData, msg, transfers);
    this.meshData = null;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = this.gpuMemoryBytes = getMeshDataSize(
      this.meshData
    );
    super.downloadSucceeded();
  }
};
function decodeJsonManifestChunk(chunk, response, keysPropertyName) {
  verifyObject(response);
  chunk.fragmentIds = verifyObjectProperty(
    response,
    keysPropertyName,
    verifyStringArray
  );
}
function computeVertexNormals(positions, indices) {
  const faceNormal = vec3_exports.create();
  const v1v0 = vec3_exports.create();
  const v2v1 = vec3_exports.create();
  const vertexNormals = new Float32Array(positions.length);
  const numIndices = indices.length;
  for (let i = 0; i < numIndices; i += 3) {
    const i0 = indices[i] * 3;
    const i1 = indices[i + 1] * 3;
    const i2 = indices[i + 2] * 3;
    for (let j = 0; j < 3; ++j) {
      v1v0[j] = positions[i1 + j] - positions[i0 + j];
      v2v1[j] = positions[i2 + j] - positions[i1 + j];
    }
    vec3_exports.cross(faceNormal, v1v0, v2v1);
    vec3_exports.normalize(faceNormal, faceNormal);
    for (let k = 0; k < 3; ++k) {
      const index = indices[i + k];
      const offset = index * 3;
      for (let j = 0; j < 3; ++j) {
        vertexNormals[offset + j] += faceNormal[j];
      }
    }
  }
  const numVertices = vertexNormals.length;
  for (let i = 0; i < numVertices; i += 3) {
    const vec = vertexNormals.subarray(i, i + 3);
    vec3_exports.normalize(vec, vec);
  }
  return vertexNormals;
}
function snorm8(x) {
  return Math.min(Math.max(-127, x * 127 + 0.5), 127) >>> 0;
}
function signNotZero(x) {
  return x < 0 ? -1 : 1;
}
function encodeNormals32fx3ToOctahedron8x2(out, normals) {
  const length6 = normals.length;
  let outIndex = 0;
  for (let i = 0; i < length6; i += 3) {
    const x = normals[i];
    const y = normals[i + 1];
    const z = normals[i + 2];
    const invL1Norm = 1 / (Math.abs(x) + Math.abs(y) + Math.abs(z));
    if (z < 0) {
      out[outIndex] = snorm8((1 - Math.abs(y * invL1Norm)) * signNotZero(x));
      out[outIndex + 1] = snorm8(
        (1 - Math.abs(x * invL1Norm)) * signNotZero(y)
      );
    } else {
      out[outIndex] = snorm8(x * invL1Norm);
      out[outIndex + 1] = snorm8(y * invL1Norm);
    }
    outIndex += 2;
  }
}
function decodeVertexPositionsAndIndices(verticesPerPrimitive, data, endianness, vertexByteOffset, numVertices, indexByteOffset, numPrimitives) {
  const vertexPositions = new Float32Array(
    data,
    vertexByteOffset,
    numVertices * 3
  );
  convertEndian32(vertexPositions, endianness);
  if (indexByteOffset === void 0) {
    indexByteOffset = vertexByteOffset + 12 * numVertices;
  }
  let numIndices;
  if (numPrimitives !== void 0) {
    numIndices = numPrimitives * verticesPerPrimitive;
  }
  const indices = numIndices === void 0 ? new Uint32Array(data, indexByteOffset) : new Uint32Array(data, indexByteOffset, numIndices);
  if (indices.length % verticesPerPrimitive !== 0) {
    throw new Error(
      `Number of indices is not a multiple of ${verticesPerPrimitive}: ${indices.length}.`
    );
  }
  convertEndian32(indices, endianness);
  return { vertexPositions, indices };
}
function decodeTriangleVertexPositionsAndIndices(data, endianness, vertexByteOffset, numVertices, indexByteOffset, numTriangles) {
  return decodeVertexPositionsAndIndices(
    /*verticesPerPrimitive=*/
    3,
    data,
    endianness,
    vertexByteOffset,
    numVertices,
    indexByteOffset,
    numTriangles
  );
}
var MeshSource = class extends ChunkSource {
  fragmentSource;
  constructor(rpc2, options) {
    super(rpc2, options);
    const fragmentSource = this.fragmentSource = this.registerDisposer(
      rpc2.getRef(options.fragmentSource)
    );
    fragmentSource.meshSource = this;
  }
  getChunk(objectId) {
    const key = getObjectKey(objectId);
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(ManifestChunk);
      chunk.initializeManifestChunk(key, objectId);
      this.addChunk(chunk);
    }
    return chunk;
  }
  getFragmentKey(objectKey, fragmentId) {
    return { key: `${objectKey}/${fragmentId}`, fragmentId };
  }
  getFragmentChunk(manifestChunk, fragmentId) {
    const fragmentSource = this.fragmentSource;
    const { key: fragmentKey, fragmentId: parsedFragmentId } = this.getFragmentKey(manifestChunk.key, fragmentId);
    let chunk = fragmentSource.chunks.get(fragmentKey);
    if (chunk === void 0) {
      chunk = fragmentSource.getNewChunk_(FragmentChunk);
      chunk.initializeFragmentChunk(
        fragmentKey,
        manifestChunk,
        parsedFragmentId
      );
      fragmentSource.addChunk(chunk);
    }
    return chunk;
  }
};
var FragmentSource = class extends ChunkSource {
  meshSource = null;
  download(chunk, signal) {
    return this.meshSource.downloadFragment(chunk, signal);
  }
};
FragmentSource = __decorateClass13([
  registerSharedObject(FRAGMENT_SOURCE_RPC_ID)
], FragmentSource);
var MeshLayer = class extends withSegmentationLayerBackendState(
  withSharedVisibility(withChunkManager(PerspectiveViewRenderLayerBackend))
) {
  source;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = this.registerDisposer(rpc2.getRef(options.source));
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateChunkPriorities();
      })
    );
  }
  attach(attachment) {
    const scheduleUpdateChunkPriorities = () => {
      this.chunkManager.scheduleUpdateChunkPriorities();
    };
    const { view } = attachment;
    attachment.registerDisposer(
      view.visibility.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(scheduleUpdateChunkPriorities);
    scheduleUpdateChunkPriorities();
  }
  updateChunkPriorities() {
    const visibility = this.visibility.value;
    if (visibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    this.chunkManager.registerLayer(this);
    const priorityTier = getPriorityTier(visibility);
    const basePriority = getBasePriority(visibility);
    const { source, chunkManager } = this;
    forEachVisibleSegment(this, (objectId) => {
      const manifestChunk = source.getChunk(objectId);
      ++this.numVisibleChunksNeeded;
      chunkManager.requestChunk(
        manifestChunk,
        priorityTier,
        basePriority + MESH_OBJECT_MANIFEST_CHUNK_PRIORITY
      );
      const state = manifestChunk.state;
      if (state === ChunkState.SYSTEM_MEMORY_WORKER || state === ChunkState.SYSTEM_MEMORY || state === ChunkState.GPU_MEMORY) {
        ++this.numVisibleChunksAvailable;
        for (const fragmentId of manifestChunk.fragmentIds) {
          const fragmentChunk = source.getFragmentChunk(
            manifestChunk,
            fragmentId
          );
          ++this.numVisibleChunksNeeded;
          chunkManager.requestChunk(
            fragmentChunk,
            priorityTier,
            basePriority + MESH_OBJECT_FRAGMENT_CHUNK_PRIORITY
          );
          if (fragmentChunk.state === ChunkState.GPU_MEMORY) {
            ++this.numVisibleChunksAvailable;
          }
        }
      }
    });
  }
};
MeshLayer = __decorateClass13([
  registerSharedObject(MESH_LAYER_RPC_ID)
], MeshLayer);
var MultiscaleManifestChunk = class extends Chunk {
  objectId = 0n;
  manifest;
  // We can't save a reference to objectId, because it may be a temporary
  // object.
  initializeManifestChunk(key, objectId) {
    super.initialize(key);
    this.objectId = objectId;
  }
  freeSystemMemory() {
    this.manifest = void 0;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    msg.manifest = this.manifest;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = this.manifest.octree.byteLength;
    this.gpuMemoryBytes = 0;
    super.downloadSucceeded();
    if (this.priorityTier < ChunkPriorityTier.RECENT) {
      this.source.chunkManager.scheduleUpdateChunkPriorities();
    }
  }
  toString() {
    return this.objectId.toString();
  }
};
var MultiscaleFragmentChunk = class extends Chunk {
  subChunkOffsets = null;
  meshData = null;
  lod = 0;
  chunkIndex = 0;
  manifestChunk = null;
  freeSystemMemory() {
    this.meshData = this.subChunkOffsets = null;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    serializeMeshData(this.meshData, msg, transfers);
    const { subChunkOffsets } = this;
    msg.subChunkOffsets = subChunkOffsets;
    transfers.push(subChunkOffsets.buffer);
    this.meshData = this.subChunkOffsets = null;
  }
  downloadSucceeded() {
    const { subChunkOffsets } = this;
    this.systemMemoryBytes = this.gpuMemoryBytes = getMeshDataSize(
      this.meshData
    );
    this.systemMemoryBytes += subChunkOffsets.byteLength;
    super.downloadSucceeded();
  }
};
var MultiscaleMeshSource = class extends ChunkSource {
  fragmentSource;
  format;
  constructor(rpc2, options) {
    super(rpc2, options);
    const fragmentSource = this.fragmentSource = this.registerDisposer(
      rpc2.getRef(options.fragmentSource)
    );
    this.format = options.format;
    fragmentSource.meshSource = this;
  }
  getChunk(objectId) {
    const key = getObjectKey(objectId);
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(MultiscaleManifestChunk);
      chunk.initializeManifestChunk(key, objectId);
      this.addChunk(chunk);
    }
    return chunk;
  }
  getFragmentChunk(manifestChunk, lod, chunkIndex) {
    const key = `${manifestChunk.key}/${lod}:${chunkIndex}`;
    const fragmentSource = this.fragmentSource;
    let chunk = fragmentSource.chunks.get(key);
    if (chunk === void 0) {
      chunk = fragmentSource.getNewChunk_(MultiscaleFragmentChunk);
      chunk.initialize(key);
      chunk.lod = lod;
      chunk.chunkIndex = chunkIndex;
      chunk.manifestChunk = manifestChunk;
      fragmentSource.addChunk(chunk);
    }
    return chunk;
  }
};
var MultiscaleFragmentSource = class extends ChunkSource {
  meshSource = null;
  download(chunk, signal) {
    return this.meshSource.downloadFragment(chunk, signal);
  }
};
MultiscaleFragmentSource = __decorateClass13([
  registerSharedObject(MULTISCALE_FRAGMENT_SOURCE_RPC_ID)
], MultiscaleFragmentSource);
var tempModelMatrix = mat4_exports.create();
var MultiscaleMeshLayer = class extends withSegmentationLayerBackendState(
  withSharedVisibility(withChunkManager(PerspectiveViewRenderLayerBackend))
) {
  source;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = this.registerDisposer(
      rpc2.getRef(options.source)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateChunkPriorities();
      })
    );
  }
  attach(attachment) {
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    const { view } = attachment;
    attachment.registerDisposer(
      view.projectionParameters.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(
      view.visibility.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(scheduleUpdateChunkPriorities);
    scheduleUpdateChunkPriorities();
  }
  updateChunkPriorities() {
    const maxVisibility = this.visibility.value;
    if (maxVisibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    const {
      transform: { value: transform2 }
    } = this;
    if (transform2.error !== void 0) return;
    const manifestChunks = new Array();
    this.chunkManager.registerLayer(this);
    {
      const priorityTier = getPriorityTier(maxVisibility);
      const basePriority = getBasePriority(maxVisibility);
      const { source: source2, chunkManager: chunkManager2 } = this;
      forEachVisibleSegment(this, (objectId) => {
        const manifestChunk = source2.getChunk(objectId);
        ++this.numVisibleChunksNeeded;
        chunkManager2.requestChunk(
          manifestChunk,
          priorityTier,
          basePriority + MESH_OBJECT_MANIFEST_CHUNK_PRIORITY
        );
        const state = manifestChunk.state;
        if (state === ChunkState.SYSTEM_MEMORY_WORKER || state === ChunkState.SYSTEM_MEMORY || state === ChunkState.GPU_MEMORY) {
          manifestChunks.push(manifestChunk);
          ++this.numVisibleChunksAvailable;
        }
      });
    }
    if (manifestChunks.length === 0) return;
    const { source, chunkManager } = this;
    for (const { view } of this.attachments.values()) {
      const visibility = view.visibility.value;
      if (visibility === Number.NEGATIVE_INFINITY) {
        continue;
      }
      const priorityTier = getPriorityTier(visibility);
      const basePriority = getBasePriority(visibility);
      const projectionParameters = view.projectionParameters.value;
      const modelViewProjectionMatrix = tempModelMatrix;
      try {
        get3dModelToDisplaySpaceMatrix(
          modelViewProjectionMatrix,
          projectionParameters.displayDimensionRenderInfo,
          transform2
        );
      } catch {
        continue;
      }
      mat4_exports.multiply(
        modelViewProjectionMatrix,
        projectionParameters.viewProjectionMat,
        modelViewProjectionMatrix
      );
      const clippingPlanes = getFrustrumPlanes(
        new Float32Array(24),
        modelViewProjectionMatrix
      );
      const detailCutoff = this.renderScaleTarget.value;
      for (const manifestChunk of manifestChunks) {
        const maxLod = manifestChunk.manifest.lodScales.length - 1;
        getDesiredMultiscaleMeshChunks(
          manifestChunk.manifest,
          modelViewProjectionMatrix,
          clippingPlanes,
          detailCutoff,
          projectionParameters.width,
          projectionParameters.height,
          (lod, chunkIndex, _renderScale, empty) => {
            if (empty) return;
            const fragmentChunk = source.getFragmentChunk(
              manifestChunk,
              lod,
              chunkIndex
            );
            ++this.numVisibleChunksNeeded;
            chunkManager.requestChunk(
              fragmentChunk,
              priorityTier,
              basePriority + MESH_OBJECT_FRAGMENT_CHUNK_PRIORITY - maxLod + lod
            );
            if (fragmentChunk.state === ChunkState.GPU_MEMORY) {
              ++this.numVisibleChunksAvailable;
            }
          }
        );
      }
    }
  }
};
MultiscaleMeshLayer = __decorateClass13([
  registerSharedObject(MULTISCALE_MESH_LAYER_RPC_ID)
], MultiscaleMeshLayer);
function convertMeshData(data, vertexPositionFormat) {
  const normals = computeVertexNormals(data.vertexPositions, data.indices);
  const encodedNormals = new Uint8Array(normals.length / 3 * 2);
  encodeNormals32fx3ToOctahedron8x2(encodedNormals, normals);
  let encodedIndices;
  let strips;
  if (CONVERT_TO_TRIANGLE_STRIPS) {
    encodedIndices = computeTriangleStrips(data.indices, data.subChunkOffsets);
    strips = true;
  } else {
    if (data.indices.BYTES_PER_ELEMENT === 4 && data.vertexPositions.length / 3 < 65535) {
      encodedIndices = new Uint16Array(data.indices.length);
      encodedIndices.set(data.indices);
    } else {
      encodedIndices = data.indices;
    }
    strips = false;
  }
  let encodedVertexPositions;
  if (vertexPositionFormat === VertexPositionFormat.uint10) {
    const vertexPositions = data.vertexPositions;
    const numVertices = vertexPositions.length / 3;
    encodedVertexPositions = new Uint32Array(numVertices);
    for (let inputIndex = 0, outputIndex = 0; outputIndex < numVertices; inputIndex += 3, ++outputIndex) {
      encodedVertexPositions[outputIndex] = vertexPositions[inputIndex] & 1023 | (vertexPositions[inputIndex + 1] & 1023) << 10 | (vertexPositions[inputIndex + 2] & 1023) << 20;
    }
  } else if (vertexPositionFormat === VertexPositionFormat.uint16) {
    const vertexPositions = data.vertexPositions;
    if (vertexPositions.BYTES_PER_ELEMENT === 2) {
      encodedVertexPositions = vertexPositions;
    } else {
      encodedVertexPositions = new Uint16Array(vertexPositions.length);
      encodedVertexPositions.set(vertexPositions);
    }
  } else {
    encodedVertexPositions = data.vertexPositions;
  }
  return {
    vertexPositions: encodedVertexPositions,
    vertexNormals: encodedNormals,
    indices: encodedIndices,
    strips
  };
}
function assignMeshFragmentData(chunk, data, vertexPositionFormat = VertexPositionFormat.float32) {
  chunk.meshData = convertMeshData(data, vertexPositionFormat);
}
function assignMultiscaleMeshFragmentData(chunk, data, vertexPositionFormat) {
  chunk.meshData = convertMeshData(data, vertexPositionFormat);
  chunk.subChunkOffsets = data.subChunkOffsets;
}
function generateHigherOctreeLevel(octree, priorStart, priorEnd) {
  let curEnd = priorEnd;
  for (let i = 0; i < 3; ++i) {
    octree[curEnd * 5 + i] = octree[priorStart * 5 + i] >>> 1;
  }
  octree[curEnd * 5 + 3] = priorStart;
  for (let i = priorStart + 1; i < priorEnd; ++i) {
    const x = octree[i * 5] >>> 1;
    const y = octree[i * 5 + 1] >>> 1;
    const z = octree[i * 5 + 2] >>> 1;
    if (x !== octree[curEnd * 5] || y !== octree[curEnd * 5 + 1] || z !== octree[curEnd * 5 + 2]) {
      octree[curEnd * 5 + 4] = i;
      ++curEnd;
      octree[curEnd * 5] = x;
      octree[curEnd * 5 + 1] = y;
      octree[curEnd * 5 + 2] = z;
      octree[curEnd * 5 + 3] = i;
    }
  }
  octree[curEnd * 5 + 4] = priorEnd;
  ++curEnd;
  return curEnd;
}
function computeOctreeChildOffsets(octree, childStart, childEnd, parentEnd) {
  let childNode = childStart;
  for (let parentNode = childEnd; parentNode < parentEnd; ++parentNode) {
    const parentX = octree[parentNode * 5];
    const parentY = octree[parentNode * 5 + 1];
    const parentZ = octree[parentNode * 5 + 2];
    while (childNode < childEnd) {
      const childX = octree[childNode * 5] >>> 1;
      const childY = octree[childNode * 5 + 1] >>> 1;
      const childZ = octree[childNode * 5 + 2] >>> 1;
      if (!zorder3LessThan(childX, childY, childZ, parentX, parentY, parentZ)) {
        break;
      }
      ++childNode;
    }
    octree[parentNode * 5 + 3] = childNode;
    while (childNode < childEnd) {
      const childX = octree[childNode * 5] >>> 1;
      const childY = octree[childNode * 5 + 1] >>> 1;
      const childZ = octree[childNode * 5 + 2] >>> 1;
      if (childX !== parentX || childY !== parentY || childZ !== parentZ) {
        break;
      }
      ++childNode;
    }
    octree[parentNode * 5 + 4] += childNode;
  }
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/bossNpz.js
init_legacy_browser();

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/postprocess.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/encode_compressed_segmentation_request.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/index.js
init_legacy_browser();
function asyncComputation(id) {
  return { id };
}

// node_modules/neuroglancer/lib/async_computation/encode_compressed_segmentation_request.js
var encodeCompressedSegmentationUint32 = asyncComputation("encodeCompressedSegmentationUint32");
var encodeCompressedSegmentationUint64 = asyncComputation("encodeCompressedSegmentationUint64");

// node_modules/neuroglancer/lib/async_computation/request.js
init_legacy_browser();
var numWorkers = 0;
var freeWorkers = [];
var pendingTasks = /* @__PURE__ */ new Map();
var tasks = /* @__PURE__ */ new Map();
var maxWorkers = typeof navigator.hardwareConcurrency === "undefined" ? 4 : Math.min(12, navigator.hardwareConcurrency);
var nextTaskId = 0;
function returnWorker(worker) {
  var _a;
  for (const [id, task] of pendingTasks) {
    pendingTasks.delete(id);
    (_a = task.cleanup) == null ? void 0 : _a.call(task);
    worker.postMessage(task.msg, task.transfer);
    return;
  }
  freeWorkers.push(worker);
}
function launchWorker() {
  ++numWorkers;
  const worker = new Worker(
    /* webpackChunkName: "neuroglancer_async_computation" */
    new URL("../async_computation.bundle.js", import.meta.url),
    { type: "module" }
  );
  let ready = false;
  worker.onmessage = (msg) => {
    if (!ready) {
      ready = true;
      returnWorker(worker);
      return;
    }
    const { id, value, error } = msg.data;
    returnWorker(worker);
    const callbacks = tasks.get(id);
    tasks.delete(id);
    if (callbacks === void 0) return;
    if (error !== void 0) {
      callbacks.reject(error);
    } else {
      callbacks.resolve(value);
    }
  };
}
function requestAsyncComputation(request, signal, transfer, ...args) {
  const id = nextTaskId++;
  const msg = { t: request.id, id, args };
  signal == null ? void 0 : signal.throwIfAborted();
  const promise = new Promise((resolve, reject) => {
    tasks.set(id, { resolve, reject });
  });
  if (freeWorkers.length !== 0) {
    freeWorkers.pop().postMessage(msg, transfer);
  } else {
    let cleanup;
    if (signal !== void 0) {
      let abortHandler2 = function() {
        pendingTasks.delete(id);
        const task = tasks.get(id);
        tasks.delete(id);
        task.reject(signal.reason);
      };
      var abortHandler = abortHandler2;
      signal.addEventListener("abort", abortHandler2, { once: true });
      cleanup = () => {
        signal.removeEventListener("abort", abortHandler2);
      };
    }
    pendingTasks.set(id, { msg, transfer, cleanup });
    if (tasks.size > numWorkers && numWorkers < maxWorkers) {
      launchWorker();
    }
  }
  return promise;
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/postprocess.js
async function postProcessRawData(chunk, signal, data) {
  const { spec } = chunk.source;
  if (spec.compressedSegmentationBlockSize !== void 0) {
    const { dataType } = spec;
    const chunkDataSize = chunk.chunkDataSize;
    const shape = [
      chunkDataSize[0],
      chunkDataSize[1],
      chunkDataSize[2],
      chunkDataSize[3] || 1
    ];
    switch (dataType) {
      case DataType.UINT32:
        chunk.data = await requestAsyncComputation(
          encodeCompressedSegmentationUint32,
          signal,
          [data.buffer],
          data,
          shape,
          spec.compressedSegmentationBlockSize
        );
        break;
      case DataType.UINT64:
        chunk.data = await requestAsyncComputation(
          encodeCompressedSegmentationUint64,
          signal,
          [data.buffer],
          data,
          shape,
          spec.compressedSegmentationBlockSize
        );
        break;
      default:
        throw new Error(
          `Unsupported data type for compressed segmentation: ${DataType[dataType]}`
        );
    }
  } else {
    chunk.data = data;
  }
}

// node_modules/neuroglancer/lib/util/gzip.js
init_legacy_browser();
function isGzipFormat(data) {
  const view = new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  return view.length >= 3 && view[0] === 31 && view[1] === 139 && view[2] === 8;
}
async function decodeGzip(data, format, signal) {
  try {
    const decompressedStream = decodeGzipStream(
      data instanceof Response ? data : new Response(data),
      format,
      signal
    );
    return await new Response(decompressedStream).arrayBuffer();
  } catch {
    signal == null ? void 0 : signal.throwIfAborted();
    throw new Error(`Failed to decode ${format}`);
  }
}
function decodeGzipStream(response, format, signal) {
  return response.body.pipeThrough(new DecompressionStream(format), {
    signal
  });
}

// node_modules/neuroglancer/lib/util/npy.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/numpy_dtype.js
init_legacy_browser();
var supportedDataTypes = /* @__PURE__ */ new Map();
supportedDataTypes.set("|u1", {
  endianness: Endianness.LITTLE,
  dataType: DataType.UINT8
});
supportedDataTypes.set("|i1", {
  endianness: Endianness.LITTLE,
  dataType: DataType.INT8
});
for (const [endiannessChar, endianness] of [
  ["<", Endianness.LITTLE],
  [">", Endianness.BIG]
]) {
  for (const typeChar of ["u", "i"]) {
    supportedDataTypes.set(`${endiannessChar}${typeChar}8`, {
      endianness,
      dataType: DataType.UINT64
    });
  }
  supportedDataTypes.set(`${endiannessChar}u2`, {
    endianness,
    dataType: DataType.UINT16
  });
  supportedDataTypes.set(`${endiannessChar}i2`, {
    endianness,
    dataType: DataType.INT16
  });
  supportedDataTypes.set(`${endiannessChar}u4`, {
    endianness,
    dataType: DataType.UINT32
  });
  supportedDataTypes.set(`${endiannessChar}i4`, {
    endianness,
    dataType: DataType.INT32
  });
  supportedDataTypes.set(`${endiannessChar}f4`, {
    endianness,
    dataType: DataType.FLOAT32
  });
}
function parseNumpyDtype(typestr) {
  const dtype = supportedDataTypes.get(typestr);
  if (dtype === void 0) {
    throw new Error(`Unsupported numpy data type: ${JSON.stringify(typestr)}`);
  }
  return dtype;
}

// node_modules/neuroglancer/lib/util/npy.js
var NumpyArray = class {
  constructor(data, shape, dataType, fortranOrder) {
    this.data = data;
    this.shape = shape;
    this.dataType = dataType;
    this.fortranOrder = fortranOrder;
  }
};
function parseNpy(x) {
  if (x[0] !== 147 || x[1] !== 78 || x[2] !== 85 || x[3] !== 77 || x[4] !== 80 || x[5] !== 89) {
    throw new Error("Data does not match npy format.");
  }
  const majorVersion = x[6];
  const minorVersion = x[7];
  if (majorVersion !== 1 || minorVersion !== 0) {
    throw new Error(`Unsupported npy version ${majorVersion}.${minorVersion}`);
  }
  const dv = new DataView(x.buffer, x.byteOffset, x.byteLength);
  const headerLength = dv.getUint16(
    8,
    /*littleEndian=*/
    true
  );
  const header = new TextDecoder("utf-8").decode(
    x.subarray(10, headerLength + 10)
  );
  let headerObject;
  const dataOffset = headerLength + 10;
  try {
    headerObject = pythonLiteralParse(header);
  } catch (e) {
    throw new Error(`Failed to parse npy header: ${e}`);
  }
  const dtype = headerObject.descr;
  const shape = headerObject.shape;
  let numElements = 1;
  if (!Array.isArray(shape)) {
    throw new Error("Invalid shape ${JSON.stringify(shape)}");
  }
  for (const dim of shape) {
    if (typeof dim !== "number") {
      throw new Error("Invalid shape ${JSON.stringify(shape)}");
    }
    numElements *= dim;
  }
  const { dataType, endianness } = parseNumpyDtype(dtype);
  const bytesPerElement = DATA_TYPE_BYTES[dataType];
  const arrayConstructor = DATA_TYPE_ARRAY_CONSTRUCTOR[dataType];
  if (bytesPerElement * numElements + dataOffset !== x.byteLength) {
    throw new Error("Expected length does not match length of data");
  }
  const data = new arrayConstructor(
    x.buffer,
    x.byteOffset + dataOffset,
    numElements
  );
  convertEndian(data, endianness, bytesPerElement);
  return new NumpyArray(
    data,
    shape,
    dataType,
    headerObject.fortran_order === true
  );
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/bossNpz.js
async function decodeBossNpzChunk(chunk, signal, response) {
  const parseResult = parseNpy(
    new Uint8Array(await decodeGzip(response, "deflate"))
  );
  const chunkDataSize = chunk.chunkDataSize;
  const source = chunk.source;
  const { shape } = parseResult;
  if (shape.length !== 3 || shape[0] !== chunkDataSize[2] || shape[1] !== chunkDataSize[1] || shape[2] !== chunkDataSize[0]) {
    throw new Error(
      `Shape ${JSON.stringify(shape)} does not match chunkDataSize ${vec3Key(
        chunkDataSize
      )}`
    );
  }
  const parsedDataType = parseResult.dataType;
  const { spec } = source;
  if (parsedDataType !== spec.dataType) {
    throw new Error(
      `Data type ${DataType[parsedDataType]} does not match expected data type ${DataType[spec.dataType]}`
    );
  }
  await postProcessRawData(chunk, signal, parseResult.data);
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/jpeg.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/decode_jpeg_request.js
init_legacy_browser();
var decodeJpeg = asyncComputation("decodeJpeg");

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/jpeg.js
async function decodeJpegChunk(chunk, signal, response) {
  const chunkDataSize = chunk.chunkDataSize;
  const { uint8Array: decoded } = await requestAsyncComputation(
    decodeJpeg,
    signal,
    [response],
    new Uint8Array(response),
    void 0,
    void 0,
    chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
    chunkDataSize[3] || 1,
    false
  );
  await postProcessRawData(chunk, signal, decoded);
}

// node_modules/neuroglancer/lib/sliceview/volume/backend.js
init_legacy_browser();
var VolumeChunk = class extends SliceViewChunk {
  source = null;
  data;
  chunkDataSize;
  initializeVolumeChunk(key, chunkGridPosition) {
    super.initializeVolumeChunk(key, chunkGridPosition);
    this.chunkDataSize = null;
    this.data = null;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    const chunkDataSize = this.chunkDataSize;
    if (chunkDataSize !== this.source.spec.chunkDataSize) {
      msg.chunkDataSize = chunkDataSize;
    }
    const data = msg.data = this.data;
    if (data !== null) {
      transfers.push(data.buffer);
    }
    this.data = null;
  }
  downloadSucceeded() {
    var _a;
    this.systemMemoryBytes = this.gpuMemoryBytes = ((_a = this.data) == null ? void 0 : _a.byteLength) ?? 0;
    super.downloadSucceeded();
  }
  freeSystemMemory() {
    this.data = null;
  }
};
function computeChunkBounds(source, chunk) {
  const { spec, tempChunkDataSize, tempChunkPosition: tempChunkPosition4 } = source;
  const { upperVoxelBound, rank, baseVoxelOffset } = spec;
  const origChunkDataSize = spec.chunkDataSize;
  const newChunkDataSize = tempChunkDataSize;
  const chunkPosition = multiply6(
    tempChunkPosition4,
    chunk.chunkGridPosition,
    origChunkDataSize
  );
  let partial = false;
  for (let i = 0; i < rank; ++i) {
    const upper = Math.min(
      upperVoxelBound[i],
      chunkPosition[i] + origChunkDataSize[i]
    );
    const size = newChunkDataSize[i] = upper - chunkPosition[i];
    if (size !== origChunkDataSize[i]) {
      partial = true;
    }
  }
  add6(chunkPosition, chunkPosition, baseVoxelOffset);
  if (partial) {
    chunk.chunkDataSize = Uint32Array.from(newChunkDataSize);
  } else {
    chunk.chunkDataSize = origChunkDataSize;
  }
  return chunkPosition;
}
var VolumeChunkSource = class extends SliceViewChunkSourceBackend {
  tempChunkDataSize;
  tempChunkPosition;
  constructor(rpc2, options) {
    super(rpc2, options);
    const rank = this.spec.rank;
    this.tempChunkDataSize = new Uint32Array(rank);
    this.tempChunkPosition = new Float32Array(rank);
  }
  computeChunkBounds(chunk) {
    return computeChunkBounds(this, chunk);
  }
};
VolumeChunkSource.prototype.chunkConstructor = VolumeChunk;

// node_modules/neuroglancer/lib/datasource/boss/backend.js
var __defProp15 = Object.defineProperty;
var __getOwnPropDesc15 = Object.getOwnPropertyDescriptor;
var __decorateClass14 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc15(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp15(target2, key, result);
  return result;
};
var chunkDecoders = /* @__PURE__ */ new Map();
chunkDecoders.set("npz", decodeBossNpzChunk);
chunkDecoders.set("jpeg", decodeJpegChunk);
var acceptHeaders = /* @__PURE__ */ new Map();
acceptHeaders.set("npz", "application/npygz");
acceptHeaders.set("jpeg", "image/jpeg");
function BossSource(Base, parametersConstructor) {
  return WithParameters(
    WithSharedCredentialsProviderCounterpart()(Base),
    parametersConstructor
  );
}
var BossVolumeChunkSource = class extends BossSource(
  VolumeChunkSource,
  VolumeChunkSourceParameters
) {
  chunkDecoder = chunkDecoders.get(this.parameters.encoding);
  async download(chunk, signal) {
    const { parameters } = this;
    let url = `${parameters.baseUrl}/latest/cutout/${parameters.collection}/${parameters.experiment}/${parameters.channel}/${parameters.resolution}`;
    {
      const chunkPosition = this.computeChunkBounds(chunk);
      const chunkDataSize = chunk.chunkDataSize;
      for (let i = 0; i < 3; ++i) {
        url += `/${chunkPosition[i]}:${chunkPosition[i] + chunkDataSize[i]}`;
      }
    }
    url += "/";
    if (parameters.window !== void 0) {
      url += `?window=${parameters.window[0]},${parameters.window[1]}`;
    }
    const response = await fetchWithBossCredentials(
      this.credentialsProvider,
      url,
      {
        signal,
        headers: { Accept: acceptHeaders.get(parameters.encoding) }
      }
    );
    await this.chunkDecoder(chunk, signal, await response.arrayBuffer());
  }
};
BossVolumeChunkSource = __decorateClass14([
  registerSharedObject()
], BossVolumeChunkSource);
function decodeManifestChunk(chunk, response) {
  return decodeJsonManifestChunk(chunk, response, "fragments");
}
function decodeFragmentChunk(chunk, response) {
  const dv = new DataView(response);
  const numVertices = dv.getUint32(0, true);
  assignMeshFragmentData(
    chunk,
    decodeTriangleVertexPositionsAndIndices(
      response,
      Endianness.LITTLE,
      /*vertexByteOffset=*/
      4,
      numVertices
    )
  );
}
var BossMeshSource = class extends BossSource(
  MeshSource,
  MeshSourceParameters
) {
  download(chunk, signal) {
    const { parameters } = this;
    return fetchWithBossCredentials(
      this.credentialsProvider,
      `${parameters.baseUrl}${chunk.objectId}`,
      { signal }
    ).then((response) => response.arrayBuffer()).then((response) => decodeManifestChunk(chunk, response));
  }
  downloadFragment(chunk, signal) {
    const { parameters } = this;
    return fetchWithBossCredentials(
      this.credentialsProvider,
      `${parameters.baseUrl}${chunk.fragmentId}`,
      { signal }
    ).then((response) => response.arrayBuffer()).then((response) => decodeFragmentChunk(chunk, response));
  }
};
BossMeshSource = __decorateClass14([
  registerSharedObject()
], BossMeshSource);

// node_modules/neuroglancer/lib/datasource/brainmaps/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/annotation/index.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/color.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/float32_to_string.js
init_legacy_browser();
var tempArray = new Float32Array(1);
function float32ToString(x) {
  tempArray[0] = x;
  x = tempArray[0];
  for (let digits = 1; digits < 21; ++digits) {
    const result = x.toPrecision(digits);
    tempArray[0] = parseFloat(result);
    if (tempArray[0] === x) {
      return result;
    }
  }
  return x.toString();
}

// node_modules/neuroglancer/lib/util/hex.js
init_legacy_browser();
function hexEncodeByte(x) {
  return ("0" + x.toString(16)).slice(-2);
}

// node_modules/neuroglancer/lib/util/color.js
function parseColorSerialization(x) {
  const rgbaPattern = /^rgba\(([0-9]+), ([0-9]+), ([0-9]+), (0(?:\.[0-9]+)?)\)$/;
  {
    const m = x.match(rgbaPattern);
    if (m !== null) {
      return [
        parseInt(m[1], 10),
        parseInt(m[2], 10),
        parseInt(m[3], 10),
        parseFloat(m[4])
      ];
    }
  }
  const hexPattern = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/;
  {
    const m = x.match(hexPattern);
    if (m !== null) {
      return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16), 1];
    }
  }
  throw new Error(`Invalid serialized color: ${JSON.stringify(x)}.`);
}
function parseRGBAColorSpecification(x) {
  try {
    if (typeof x !== "string") {
      throw new Error(`Expected string, but received ${JSON.stringify(x)}.`);
    }
    const context = document.createElement("canvas").getContext("2d");
    context.fillStyle = x;
    const result = parseColorSerialization(context.fillStyle);
    return vec4_exports.fromValues(
      result[0] / 255,
      result[1] / 255,
      result[2] / 255,
      result[3]
    );
  } catch (parseError) {
    throw new Error(
      `Failed to parse color specification: ${parseError.message}`
    );
  }
}
function parseRGBColorSpecification(x) {
  const result = parseRGBAColorSpecification(x);
  return result.subarray(0, 3);
}
function packColor(x) {
  const size = x[3] === void 0 ? 3 : 4;
  let result = 0;
  for (let i = 0; i < size; i++) {
    result = (result << 8 >>> 0) + Math.min(255, Math.max(0, Math.round(x[size - 1 - i] * 255)));
  }
  return result;
}
function unpackRGB(value) {
  return vec3_exports.fromValues(
    (value >>> 0 & 255) / 255,
    (value >>> 8 & 255) / 255,
    (value >>> 16 & 255) / 255
  );
}
function unpackRGBA(value) {
  return vec4_exports.fromValues(
    (value >>> 0 & 255) / 255,
    (value >>> 8 & 255) / 255,
    (value >>> 16 & 255) / 255,
    (value >>> 24 & 255) / 255
  );
}
function serializeColor(x) {
  if (x[3] === void 0 || x[3] === 1) {
    let result2 = "#";
    for (let i = 0; i < 3; ++i) {
      result2 += hexEncodeByte(
        Math.min(255, Math.max(0, Math.round(x[i] * 255)))
      );
    }
    return result2;
  }
  let result = "rgba(";
  for (let i = 0; i < 3; ++i) {
    if (i !== 0) {
      result += ", ";
    }
    result += Math.min(255, Math.max(0, Math.round(x[i] * 255)));
  }
  result += `, ${float32ToString(x[3])})`;
  return result;
}

// node_modules/neuroglancer/lib/util/lerp.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/float.js
init_legacy_browser();
var denormMin = 2 ** -1074;
var float64Buf = new Float64Array(1);
var uint32Buf = new Uint32Array(float64Buf.buffer);

// node_modules/neuroglancer/lib/util/lerp.js
var defaultDataTypeRange = {
  [DataType.UINT8]: [0, 255],
  [DataType.INT8]: [-128, 127],
  [DataType.UINT16]: [0, 65535],
  [DataType.INT16]: [-32768, 32767],
  [DataType.UINT32]: [0, 4294967295],
  [DataType.INT32]: [-2147483648, 2147483647],
  [DataType.UINT64]: [0n, 0xffffffffffffffffn],
  [DataType.FLOAT32]: [0, 1]
};

// node_modules/neuroglancer/lib/annotation/index.js
var AnnotationType = /* @__PURE__ */ ((AnnotationType2) => {
  AnnotationType2[AnnotationType2["POINT"] = 0] = "POINT";
  AnnotationType2[AnnotationType2["LINE"] = 1] = "LINE";
  AnnotationType2[AnnotationType2["AXIS_ALIGNED_BOUNDING_BOX"] = 2] = "AXIS_ALIGNED_BOUNDING_BOX";
  AnnotationType2[AnnotationType2["ELLIPSOID"] = 3] = "ELLIPSOID";
  AnnotationType2[AnnotationType2["POLYLINE"] = 4] = "POLYLINE";
  return AnnotationType2;
})(AnnotationType || {});
var annotationTypes = [
  0,
  1,
  2,
  3,
  4
  /* POLYLINE */
];
var propertyTypeDataType = {
  float32: DataType.FLOAT32,
  uint32: DataType.UINT32,
  int32: DataType.INT32,
  uint16: DataType.UINT16,
  int16: DataType.INT16,
  uint8: DataType.UINT8,
  int8: DataType.INT8,
  rgb: void 0,
  rgba: void 0
};
var annotationPropertyTypeHandlers = {
  rgb: {
    serializedBytes() {
      return 3;
    },
    alignment() {
      return 1;
    },
    serializeCode(property, offset) {
      return `dv.setUint16(${offset}, ${property}, true);dv.setUint8(${offset} + 2, ${property} >>> 16);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getUint16(${offset}, true) | (dv.getUint8(${offset} + 2) << 16);`;
    },
    deserializeJson(obj) {
      return packColor(parseRGBColorSpecification(obj));
    },
    serializeJson(value) {
      return serializeColor(unpackRGB(value));
    }
  },
  rgba: {
    serializedBytes() {
      return 4;
    },
    alignment() {
      return 1;
    },
    serializeCode(property, offset) {
      return `dv.setUint32(${offset}, ${property}, true);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getUint32(${offset}, true);`;
    },
    deserializeJson(obj) {
      return packColor(parseRGBAColorSpecification(obj));
    },
    serializeJson(value) {
      return serializeColor(unpackRGBA(value));
    }
  },
  float32: {
    serializedBytes() {
      return 4;
    },
    alignment() {
      return 4;
    },
    serializeCode(property, offset) {
      return `dv.setFloat32(${offset}, ${property}, isLittleEndian);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getFloat32(${offset}, isLittleEndian);`;
    },
    deserializeJson(obj) {
      return verifyFloat(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  uint32: {
    serializedBytes() {
      return 4;
    },
    alignment() {
      return 4;
    },
    serializeCode(property, offset) {
      return `dv.setUint32(${offset}, ${property}, isLittleEndian);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getUint32(${offset}, isLittleEndian);`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  int32: {
    serializedBytes() {
      return 4;
    },
    alignment() {
      return 4;
    },
    serializeCode(property, offset) {
      return `dv.setInt32(${offset}, ${property}, isLittleEndian);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getInt32(${offset}, isLittleEndian);`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  uint16: {
    serializedBytes() {
      return 2;
    },
    alignment() {
      return 2;
    },
    serializeCode(property, offset) {
      return `dv.setUint16(${offset}, ${property}, isLittleEndian);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getUint16(${offset}, isLittleEndian);`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  int16: {
    serializedBytes() {
      return 2;
    },
    alignment() {
      return 2;
    },
    serializeCode(property, offset) {
      return `dv.setInt16(${offset}, ${property}, isLittleEndian);`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getInt16(${offset}, isLittleEndian);`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  uint8: {
    serializedBytes() {
      return 1;
    },
    alignment() {
      return 1;
    },
    serializeCode(property, offset) {
      return `dv.setUint8(${offset}, ${property});`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getUint8(${offset});`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  },
  int8: {
    serializedBytes() {
      return 1;
    },
    alignment() {
      return 1;
    },
    serializeCode(property, offset) {
      return `dv.setInt8(${offset}, ${property});`;
    },
    deserializeCode(property, offset) {
      return `${property} = dv.getInt8(${offset});`;
    },
    deserializeJson(obj) {
      return verifyInt(obj);
    },
    serializeJson(value) {
      return value;
    }
  }
};
var MAX_BUFFER_STRIDE = 255;
function getPropertyOffsets(rank, firstGroupInitialOffset, propertySpecs) {
  let serializedBytes = 0;
  const numProperties = propertySpecs.length;
  const permutation = new Array(numProperties);
  const propertyGroupBytes = [];
  for (let i = 0; i < numProperties; ++i) {
    permutation[i] = i;
  }
  const getAlignment = (i) => annotationPropertyTypeHandlers[propertySpecs[i].type].alignment(rank);
  permutation.sort((i, j) => getAlignment(j) - getAlignment(i));
  let propertyGroupIndex = 0;
  const offsets = new Array(numProperties);
  let propertyGroupOffset = firstGroupInitialOffset;
  const nextPropertyGroup = () => {
    propertyGroupOffset += (4 - propertyGroupOffset % 4) % 4;
    serializedBytes += propertyGroupOffset;
    propertyGroupBytes[propertyGroupIndex] = propertyGroupOffset;
    propertyGroupOffset = 0;
    ++propertyGroupIndex;
  };
  for (let outputIndex = 0; outputIndex < numProperties; ++outputIndex) {
    const propertyIndex = permutation[outputIndex];
    const spec = propertySpecs[propertyIndex];
    const handler = annotationPropertyTypeHandlers[spec.type];
    const numBytes = handler.serializedBytes(rank);
    const alignment = handler.alignment(rank);
    const alignmentOffset = (alignment - propertyGroupOffset % alignment) % alignment;
    const newStartOffset = propertyGroupOffset + alignmentOffset;
    const newEndOffset = newStartOffset + numBytes;
    const newAlignedEndOffset = newEndOffset + (4 - newEndOffset % 4) % 4;
    if (newAlignedEndOffset <= MAX_BUFFER_STRIDE) {
      propertyGroupOffset += alignmentOffset;
    } else {
      nextPropertyGroup();
    }
    offsets[propertyIndex] = {
      offset: propertyGroupOffset,
      group: propertyGroupIndex
    };
    propertyGroupOffset += numBytes;
  }
  nextPropertyGroup();
  return { serializedBytes, offsets, propertyGroupBytes };
}
var AnnotationPropertySerializer = class {
  constructor(rank, firstGroupInitialOffset, propertySpecs) {
    this.rank = rank;
    this.firstGroupInitialOffset = firstGroupInitialOffset;
    this.propertySpecs = propertySpecs;
    if (propertySpecs.length === 0) {
      this.serializedBytes = firstGroupInitialOffset;
      this.serialize = this.deserialize = () => {
      };
      this.propertyGroupBytes = [firstGroupInitialOffset];
      return;
    }
    const { serializedBytes, offsets, propertyGroupBytes } = getPropertyOffsets(
      rank,
      firstGroupInitialOffset,
      propertySpecs
    );
    this.propertyGroupBytes = propertyGroupBytes;
    let groupOffsetCode = "let groupOffset0 = offset;";
    for (let groupIndex = 1; groupIndex < propertyGroupBytes.length; ++groupIndex) {
      groupOffsetCode += `let groupOffset${groupIndex} = groupOffset${groupIndex - 1} + ${propertyGroupBytes[groupIndex - 1]}*annotationCount;`;
    }
    for (let groupIndex = 0; groupIndex < propertyGroupBytes.length; ++groupIndex) {
      groupOffsetCode += `groupOffset${groupIndex} += ${propertyGroupBytes[groupIndex]}*annotationIndex;`;
    }
    let serializeCode = groupOffsetCode;
    let deserializeCode = groupOffsetCode;
    const numProperties = propertySpecs.length;
    for (let propertyIndex = 0; propertyIndex < numProperties; ++propertyIndex) {
      const { group, offset } = offsets[propertyIndex];
      const spec = propertySpecs[propertyIndex];
      const handler = annotationPropertyTypeHandlers[spec.type];
      const propId = `properties[${propertyIndex}]`;
      const offsetExpr = `groupOffset${group} + ${offset}`;
      serializeCode += handler.serializeCode(propId, offsetExpr, rank);
      deserializeCode += handler.deserializeCode(propId, offsetExpr, rank);
    }
    this.serializedBytes = serializedBytes;
    this.serialize = new Function(
      "dv",
      "offset",
      "annotationIndex",
      "annotationCount",
      "isLittleEndian",
      "properties",
      serializeCode
    );
    this.deserialize = new Function(
      "dv",
      "offset",
      "annotationIndex",
      "annotationCount",
      "isLittleEndian",
      "properties",
      deserializeCode
    );
  }
  serializedBytes;
  serialize;
  deserialize;
  propertyGroupBytes;
};
function makeAnnotationPropertySerializers(rank, propertySpecs) {
  const serializers = [];
  for (const annotationType of annotationTypes) {
    const handler = annotationTypeHandlers[annotationType];
    serializers[annotationType] = new AnnotationPropertySerializer(
      rank,
      handler.serializedBytes(rank),
      propertySpecs
    );
  }
  return serializers;
}
function serializeFloatVector(buffer, offset, isLittleEndian, rank, vec) {
  for (let i = 0; i < rank; ++i) {
    buffer.setFloat32(offset, vec[i], isLittleEndian);
    offset += 4;
  }
  return offset;
}
function serializeTwoFloatVectors(buffer, offset, isLittleEndian, rank, vecA, vecB) {
  offset = serializeFloatVector(buffer, offset, isLittleEndian, rank, vecA);
  offset = serializeFloatVector(buffer, offset, isLittleEndian, rank, vecB);
  return offset;
}
function deserializeFloatVector(buffer, offset, isLittleEndian, rank, vec) {
  for (let i = 0; i < rank; ++i) {
    vec[i] = buffer.getFloat32(offset, isLittleEndian);
    offset += 4;
  }
  return offset;
}
function deserializeTwoFloatVectors(buffer, offset, isLittleEndian, rank, vecA, vecB) {
  offset = deserializeFloatVector(buffer, offset, isLittleEndian, rank, vecA);
  offset = deserializeFloatVector(buffer, offset, isLittleEndian, rank, vecB);
  return offset;
}
function deserializeManyFloatVectors(buffer, offset, isLittleEndian, rank, points, numPoints) {
  let dataOffset = offset;
  for (let i = 0; i < numPoints; ++i) {
    points[i] = new Float32Array(rank);
    dataOffset = deserializeFloatVector(
      buffer,
      dataOffset,
      isLittleEndian,
      rank,
      points[i]
    );
  }
  return dataOffset;
}
var annotationTypeHandlers = {
  [
    1
    /* LINE */
  ]: {
    icon: "\uA579",
    description: "Line",
    toJSON(annotation) {
      return {
        pointA: Array.from(annotation.pointA),
        pointB: Array.from(annotation.pointB)
      };
    },
    restoreState(annotation, obj, rank) {
      annotation.pointA = verifyObjectProperty(
        obj,
        "pointA",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
      annotation.pointB = verifyObjectProperty(
        obj,
        "pointB",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
    },
    serializedBytes(rank) {
      return 2 * 4 * rank;
    },
    serialize(buffer, offset, isLittleEndian, rank, annotation) {
      serializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        annotation.pointA,
        annotation.pointB
      );
    },
    deserialize: (buffer, offset, isLittleEndian, rank, id) => {
      const pointA = new Float32Array(rank);
      const pointB = new Float32Array(rank);
      deserializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        pointA,
        pointB
      );
      return { type: 1, pointA, pointB, id, properties: [] };
    },
    visitGeometry(annotation, callback) {
      callback(annotation.pointA, false);
      callback(annotation.pointB, false);
    },
    defaultProperties(annotation) {
      annotation;
      return { properties: [], values: [] };
    }
  },
  [
    4
    /* POLYLINE */
  ]: {
    icon: "\u2924",
    description: "Polyline",
    toJSON(annotation) {
      return {
        points: annotation.points.map((point) => Array.from(point))
      };
    },
    restoreState(annotation, obj, rank) {
      annotation.points = verifyObjectProperty(
        obj,
        "points",
        (points) => parseArray(
          points,
          (point) => parseFixedLengthArray(
            new Float32Array(rank),
            point,
            verifyFiniteFloat
          )
        )
      );
    },
    serializedBytes(rank) {
      return 4 * rank * 2 + 4;
    },
    serialize: (buffer, offset, isLittleEndian, rank, annotation, instanceStride) => {
      for (let i = 0; i < annotation.points.length - 1; i++) {
        const pointType = i === annotation.points.length - 2 ? 1 : 0;
        const tempOffset = offset + i * instanceStride;
        buffer.setUint32(tempOffset, pointType << 31 | i, isLittleEndian);
        const firstPoint = annotation.points[i];
        const secondPoint = annotation.points[i + 1];
        serializeTwoFloatVectors(
          buffer,
          tempOffset + 4,
          isLittleEndian,
          rank,
          firstPoint,
          secondPoint
        );
      }
    },
    deserialize: (buffer, offset, isLittleEndian, rank, id, instanceStride) => {
      if (instanceStride === void 0) {
        throw new Error("Can't deserialize polyline without stride");
      }
      const points = new Array();
      if (instanceStride == 0) {
        const numPoints = buffer.getUint32(offset, isLittleEndian) & 2147483647;
        deserializeManyFloatVectors(
          buffer,
          offset + 4,
          isLittleEndian,
          rank,
          points,
          numPoints
        );
      } else {
        let currOffset = offset;
        let index = 0;
        const max_polyline_verts = 1e5;
        while (index <= max_polyline_verts) {
          const isLastLine = buffer.getUint32(currOffset, isLittleEndian) >> 31;
          const point = new Float32Array(rank);
          const tempOffset = deserializeFloatVector(
            buffer,
            currOffset + 4,
            isLittleEndian,
            rank,
            point
          );
          points.push(point);
          if (isLastLine) {
            const point2 = new Float32Array(rank);
            deserializeFloatVector(
              buffer,
              tempOffset,
              isLittleEndian,
              rank,
              point2
            );
            points.push(point2);
            break;
          }
          index++;
          currOffset += instanceStride;
        }
        if (index === max_polyline_verts) {
          throw new Error("Reached max iters on polyline deserializing");
        }
      }
      return { type: 4, points, id, properties: [] };
    },
    visitGeometry(annotation, callback) {
      for (const point of annotation.points) {
        callback(point, false);
      }
    },
    defaultProperties(annotation) {
      return {
        properties: [
          {
            type: "uint32",
            identifier: "Num vertices",
            default: 0,
            description: "Number of points in the polyline"
          }
        ],
        values: [annotation.points.length]
      };
    }
  },
  [
    0
    /* POINT */
  ]: {
    icon: "\u26AC",
    description: "Point",
    toJSON: (annotation) => {
      return {
        point: Array.from(annotation.point)
      };
    },
    restoreState: (annotation, obj, rank) => {
      annotation.point = verifyObjectProperty(
        obj,
        "point",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
    },
    serializedBytes: (rank) => rank * 4,
    serialize: (buffer, offset, isLittleEndian, rank, annotation) => {
      serializeFloatVector(
        buffer,
        offset,
        isLittleEndian,
        rank,
        annotation.point
      );
    },
    deserialize: (buffer, offset, isLittleEndian, rank, id) => {
      const point = new Float32Array(rank);
      deserializeFloatVector(buffer, offset, isLittleEndian, rank, point);
      return { type: 0, point, id, properties: [] };
    },
    visitGeometry(annotation, callback) {
      callback(annotation.point, false);
    },
    defaultProperties(annotation) {
      annotation;
      return { properties: [], values: [] };
    }
  },
  [
    2
    /* AXIS_ALIGNED_BOUNDING_BOX */
  ]: {
    icon: "\u2751",
    description: "Bounding Box",
    toJSON: (annotation) => {
      return {
        pointA: Array.from(annotation.pointA),
        pointB: Array.from(annotation.pointB)
      };
    },
    restoreState: (annotation, obj, rank) => {
      annotation.pointA = verifyObjectProperty(
        obj,
        "pointA",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
      annotation.pointB = verifyObjectProperty(
        obj,
        "pointB",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
    },
    serializedBytes: (rank) => 2 * 4 * rank,
    serialize(buffer, offset, isLittleEndian, rank, annotation) {
      serializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        annotation.pointA,
        annotation.pointB
      );
    },
    deserialize: (buffer, offset, isLittleEndian, rank, id) => {
      const pointA = new Float32Array(rank);
      const pointB = new Float32Array(rank);
      deserializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        pointA,
        pointB
      );
      return {
        type: 2,
        pointA,
        pointB,
        id,
        properties: []
      };
    },
    visitGeometry(annotation, callback) {
      callback(annotation.pointA, false);
      callback(annotation.pointB, false);
    },
    defaultProperties(annotation) {
      annotation;
      return { properties: [], values: [] };
    }
  },
  [
    3
    /* ELLIPSOID */
  ]: {
    icon: "\u25CE",
    description: "Ellipsoid",
    toJSON: (annotation) => {
      return {
        center: Array.from(annotation.center),
        radii: Array.from(annotation.radii)
      };
    },
    restoreState: (annotation, obj, rank) => {
      annotation.center = verifyObjectProperty(
        obj,
        "center",
        (x) => parseFixedLengthArray(new Float32Array(rank), x, verifyFiniteFloat)
      );
      annotation.radii = verifyObjectProperty(
        obj,
        "radii",
        (x) => parseFixedLengthArray(
          new Float32Array(rank),
          x,
          verifyFiniteNonNegativeFloat
        )
      );
    },
    serializedBytes: (rank) => 2 * 4 * rank,
    serialize(buffer, offset, isLittleEndian, rank, annotation) {
      serializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        annotation.center,
        annotation.radii
      );
    },
    deserialize: (buffer, offset, isLittleEndian, rank, id) => {
      const center = new Float32Array(rank);
      const radii = new Float32Array(rank);
      deserializeTwoFloatVectors(
        buffer,
        offset,
        isLittleEndian,
        rank,
        center,
        radii
      );
      return {
        type: 3,
        center,
        radii,
        id,
        properties: []
      };
    },
    visitGeometry(annotation, callback) {
      callback(annotation.center, false);
      callback(annotation.radii, true);
    },
    defaultProperties(annotation) {
      annotation;
      return { properties: [], values: [] };
    }
  }
};
function serializeAnnotations(allAnnotations, propertySerializers) {
  let totalBytes = 0;
  const typeToOffset = [];
  const typeToSize = [];
  for (const annotationType of annotationTypes) {
    const propertySerializer = propertySerializers[annotationType];
    const serializedPropertiesBytes = propertySerializer.serializedBytes;
    typeToOffset[annotationType] = totalBytes;
    const annotations = allAnnotations[annotationType];
    const count = annotations.length;
    if (annotationType === 4) {
      typeToSize[annotationType] = 0;
      for (const annotation of annotations) {
        const polyLinePairs = annotation.points.length - 1;
        totalBytes += serializedPropertiesBytes * polyLinePairs;
        typeToSize[annotationType] += polyLinePairs;
      }
    } else {
      totalBytes += serializedPropertiesBytes * count;
    }
  }
  const typeToIds = [];
  const typeToIdMaps = [];
  const typeToInstanceCounts = [];
  const data = new ArrayBuffer(totalBytes);
  const dataView2 = new DataView(data);
  const isLittleEndian = ENDIANNESS === Endianness.LITTLE;
  for (const annotationType of annotationTypes) {
    const propertySerializer = propertySerializers[annotationType];
    const { rank } = propertySerializer;
    const serializeProperties = propertySerializer.serialize;
    const annotations = allAnnotations[annotationType];
    typeToInstanceCounts[annotationType] = Array.from(
      { length: annotations.length },
      (_, i) => i
    );
    typeToIds[annotationType] = annotations.map((x) => x.id);
    typeToIdMaps[annotationType] = new Map(
      annotations.map((x, i) => [x.id, i])
    );
    const handler = annotationTypeHandlers[annotationType];
    const serialize = handler.serialize;
    const offset = typeToOffset[annotationType];
    const instanceStride = propertySerializer.propertyGroupBytes[0];
    let polylineInstanceIndex = 0;
    for (let i = 0, count = annotations.length; i < count; ++i) {
      const annotation = annotations[i];
      if (annotationType === 4) {
        const polyline = annotation;
        serialize(
          dataView2,
          offset + polylineInstanceIndex * instanceStride,
          isLittleEndian,
          rank,
          polyline,
          instanceStride
        );
        typeToInstanceCounts[annotationType][i] = polylineInstanceIndex;
        for (let j = 0; j < polyline.points.length - 1; j++) {
          serializeProperties(
            dataView2,
            offset,
            polylineInstanceIndex + j,
            typeToSize[annotationType],
            isLittleEndian,
            polyline.properties
          );
        }
        polylineInstanceIndex += polyline.points.length - 1;
      } else {
        serialize(
          dataView2,
          offset + i * instanceStride,
          isLittleEndian,
          rank,
          annotation,
          instanceStride
        );
        serializeProperties(
          dataView2,
          offset,
          i,
          count,
          isLittleEndian,
          annotation.properties
        );
      }
    }
    if (annotationType !== 4) {
      typeToSize[annotationType] = annotations.length;
    }
  }
  return {
    data: new Uint8Array(data),
    typeToInstanceCounts,
    typeToIds,
    typeToOffset,
    typeToIdMaps,
    typeToSize
  };
}
var AnnotationSerializer = class {
  constructor(propertySerializers) {
    this.propertySerializers = propertySerializers;
  }
  annotations = [[], [], [], [], []];
  add(annotation) {
    this.annotations[annotation.type].push(annotation);
  }
  serialize() {
    return serializeAnnotations(this.annotations, this.propertySerializers);
  }
};

// node_modules/neuroglancer/lib/datasource/brainmaps/api.js
init_legacy_browser();

// node_modules/neuroglancer/lib/credentials_provider/oauth2.js
init_legacy_browser();
function applyCredentials(credentials, init) {
  if (!credentials.accessToken) return init;
  const headers = new Headers(init.headers);
  headers.set(
    "Authorization",
    `${credentials.tokenType} ${credentials.accessToken}`
  );
  return { ...init, headers };
}
function errorHandler(error, credentials) {
  const { status } = error;
  if (status === 401) {
    return "refresh";
  }
  if (status === 403 && !credentials.accessToken) {
    return "refresh";
  }
  if (error instanceof Error && credentials.email !== void 0) {
    error.message += `  (Using credentials for ${JSON.stringify(
      credentials.email
    )})`;
  }
  throw error;
}
function fetchOkWithOAuth2Credentials(credentialsProvider, input, init) {
  if (credentialsProvider === void 0) {
    return fetchOk(input, init);
  }
  return fetchOkWithCredentials(
    credentialsProvider,
    input,
    init,
    applyCredentials,
    errorHandler
  );
}
function fetchOkWithOAuth2CredentialsAdapter(credentialsProvider) {
  if (credentialsProvider === void 0) return fetchOk;
  return fetchOkWithCredentialsAdapter(
    credentialsProvider,
    applyCredentials,
    errorHandler
  );
}

// node_modules/neuroglancer/lib/datasource/brainmaps/api.js
function makeRequest(instance2, credentialsProvider, path, init = {}) {
  return fetchOkWithOAuth2Credentials(
    credentialsProvider,
    `${instance2.serverUrl}${path}`,
    init
  );
}

// node_modules/neuroglancer/lib/datasource/brainmaps/base.js
init_legacy_browser();
var VolumeChunkEncoding = /* @__PURE__ */ ((VolumeChunkEncoding22) => {
  VolumeChunkEncoding22[VolumeChunkEncoding22["RAW"] = 0] = "RAW";
  VolumeChunkEncoding22[VolumeChunkEncoding22["JPEG"] = 1] = "JPEG";
  VolumeChunkEncoding22[VolumeChunkEncoding22["COMPRESSED_SEGMENTATION"] = 2] = "COMPRESSED_SEGMENTATION";
  return VolumeChunkEncoding22;
})(VolumeChunkEncoding || {});
var VolumeSourceParameters = class {
  instance;
  volumeId;
  scaleIndex;
  encoding;
  jpegQuality;
  changeSpec;
  static RPC_ID = "brainmaps/VolumeChunkSource";
};
var MultiscaleMeshSourceParameters = class {
  instance;
  volumeId;
  info;
  changeSpec;
  static RPC_ID = "brainmaps/MultiscaleMeshSource";
};
var MeshSourceParameters2 = class {
  instance;
  volumeId;
  meshName;
  changeSpec;
  static RPC_ID = "brainmaps/MeshSource";
};
var SkeletonSourceParameters = class {
  instance;
  volumeId;
  meshName;
  changeSpec;
  static RPC_ID = "brainmaps/SkeletonSource";
};
var AnnotationSourceParameters = class {
  instance;
  volumeId;
  changestack;
  upperVoxelBound;
  static RPC_ID = "brainmaps/Annotation";
};
var AnnotationSpatialIndexSourceParameters = class {
  instance;
  volumeId;
  changestack;
  static RPC_ID = "brainmaps/AnnotationSpatialIndex";
};

// node_modules/neuroglancer/lib/skeleton/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/skeleton/base.js
init_legacy_browser();
var SKELETON_LAYER_RPC_ID = "skeleton/SkeletonLayer";

// node_modules/neuroglancer/lib/skeleton/backend.js
var __defProp16 = Object.defineProperty;
var __getOwnPropDesc16 = Object.getOwnPropertyDescriptor;
var __decorateClass15 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc16(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp16(target2, key, result);
  return result;
};
var SKELETON_CHUNK_PRIORITY = 60;
var SkeletonChunk = class extends Chunk {
  objectId = 0n;
  vertexPositions = null;
  vertexAttributes = null;
  indices = null;
  initializeSkeletonChunk(key, objectId) {
    super.initialize(key);
    this.objectId = objectId;
  }
  freeSystemMemory() {
    this.vertexPositions = this.indices = null;
  }
  getVertexAttributeBytes() {
    let total = this.vertexPositions.byteLength;
    const { vertexAttributes } = this;
    if (vertexAttributes != null) {
      vertexAttributes.forEach((a) => {
        total += a.byteLength;
      });
    }
    return total;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    const vertexPositions = this.vertexPositions;
    const indices = this.indices;
    msg.numVertices = vertexPositions.length / 3;
    msg.indices = indices;
    transfers.push(indices.buffer);
    const { vertexAttributes } = this;
    if (vertexAttributes != null && vertexAttributes.length > 0) {
      const vertexData = new Uint8Array(this.getVertexAttributeBytes());
      vertexData.set(
        new Uint8Array(
          vertexPositions.buffer,
          vertexPositions.byteOffset,
          vertexPositions.byteLength
        )
      );
      const vertexAttributeOffsets = msg.vertexAttributeOffsets = new Uint32Array(vertexAttributes.length + 1);
      vertexAttributeOffsets[0] = 0;
      let offset = vertexPositions.byteLength;
      vertexAttributes.forEach((a, i) => {
        vertexAttributeOffsets[i + 1] = offset;
        vertexData.set(
          new Uint8Array(a.buffer, a.byteOffset, a.byteLength),
          offset
        );
        offset += a.byteLength;
      });
      transfers.push(vertexData.buffer);
      msg.vertexAttributes = vertexData;
    } else {
      msg.vertexAttributes = new Uint8Array(
        vertexPositions.buffer,
        vertexPositions.byteOffset,
        vertexPositions.byteLength
      );
      msg.vertexAttributeOffsets = Uint32Array.of(0);
      if (vertexPositions.buffer !== transfers[0]) {
        transfers.push(vertexPositions.buffer);
      }
    }
    this.vertexPositions = this.indices = this.vertexAttributes = null;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = this.gpuMemoryBytes = this.indices.byteLength + this.getVertexAttributeBytes();
    super.downloadSucceeded();
  }
};
var SkeletonSource = class extends ChunkSource {
  getChunk(objectId) {
    const key = getObjectKey(objectId);
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(SkeletonChunk);
      chunk.initializeSkeletonChunk(key, objectId);
      this.addChunk(chunk);
    }
    return chunk;
  }
};
var SkeletonLayer = class extends withSegmentationLayerBackendState(
  withSharedVisibility(withChunkManager(ChunkRenderLayerBackend))
) {
  source;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = this.registerDisposer(
      rpc2.getRef(options.source)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateChunkPriorities();
      })
    );
  }
  updateChunkPriorities() {
    const visibility = this.visibility.value;
    if (visibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    this.chunkManager.registerLayer(this);
    const priorityTier = getPriorityTier(visibility);
    const basePriority = getBasePriority(visibility);
    const { source, chunkManager } = this;
    forEachVisibleSegment(this, (objectId) => {
      const chunk = source.getChunk(objectId);
      ++this.numVisibleChunksNeeded;
      if (chunk.state === ChunkState.GPU_MEMORY) {
        ++this.numVisibleChunksAvailable;
      }
      chunkManager.requestChunk(
        chunk,
        priorityTier,
        basePriority + SKELETON_CHUNK_PRIORITY
      );
    });
  }
};
SkeletonLayer = __decorateClass15([
  registerSharedObject(SKELETON_LAYER_RPC_ID)
], SkeletonLayer);
function decodeSkeletonVertexPositionsAndIndices(chunk, data, endianness, vertexByteOffset, numVertices, indexByteOffset, numEdges) {
  const meshData = decodeVertexPositionsAndIndices(
    /*verticesPerPrimitive=*/
    2,
    data,
    endianness,
    vertexByteOffset,
    numVertices,
    indexByteOffset,
    numEdges
  );
  chunk.vertexPositions = meshData.vertexPositions;
  chunk.indices = meshData.indices;
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/compressed_segmentation.js
init_legacy_browser();
async function decodeCompressedSegmentationChunk(chunk, signal, response) {
  signal;
  chunk.data = new Uint32Array(response);
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/raw.js
init_legacy_browser();
async function decodeRawChunk(chunk, signal, response, endianness = ENDIANNESS, byteOffset = 0, byteLength = response.byteLength) {
  signal;
  const { spec } = chunk.source;
  const { dataType } = spec;
  const numElements = prod(chunk.chunkDataSize);
  const bytesPerElement = DATA_TYPE_BYTES[dataType];
  const expectedBytes = numElements * bytesPerElement;
  if (expectedBytes !== byteLength) {
    throw new Error(
      `Raw-format chunk is ${byteLength} bytes, but ${numElements} * ${bytesPerElement} = ${expectedBytes} bytes are expected.`
    );
  }
  const data = makeDataTypeArrayView(
    dataType,
    response,
    byteOffset,
    byteLength
  );
  convertEndian(data, endianness, bytesPerElement);
  await postProcessRawData(chunk, signal, data);
}

// node_modules/neuroglancer/lib/datasource/brainmaps/backend.js
var __defProp17 = Object.defineProperty;
var __getOwnPropDesc17 = Object.getOwnPropertyDescriptor;
var __decorateClass16 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc17(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp17(target2, key, result);
  return result;
};
var CHUNK_DECODERS = /* @__PURE__ */ new Map([
  [VolumeChunkEncoding.RAW, decodeRawChunk],
  [VolumeChunkEncoding.JPEG, decodeJpegChunk],
  [
    VolumeChunkEncoding.COMPRESSED_SEGMENTATION,
    decodeCompressedSegmentationChunk
  ]
]);
function applyChangeStack(changeStack, payload) {
  if (!changeStack) {
    return;
  }
  payload.change_spec = {
    change_stack_id: changeStack.changeStackId
  };
  if (changeStack.timeStamp) {
    payload.change_spec.time_stamp = changeStack.timeStamp;
  }
  if (changeStack.skipEquivalences) {
    payload.change_spec.skip_equivalences = changeStack.skipEquivalences;
  }
}
function BrainmapsSource(Base, parametersConstructor) {
  return WithParameters(
    WithSharedCredentialsProviderCounterpart()(Base),
    parametersConstructor
  );
}
var BrainmapsVolumeChunkSource = class extends BrainmapsSource(
  VolumeChunkSource,
  VolumeSourceParameters
) {
  chunkDecoder = CHUNK_DECODERS.get(this.parameters.encoding);
  applyEncodingParams(payload) {
    const { encoding } = this.parameters;
    switch (encoding) {
      case VolumeChunkEncoding.RAW:
        payload.subvolume_format = "RAW";
        break;
      case VolumeChunkEncoding.JPEG:
        payload.subvolume_format = "SINGLE_IMAGE";
        payload.image_format_options = {
          image_format: "JPEG",
          jpeg_quality: this.parameters.jpegQuality
        };
        return;
      case VolumeChunkEncoding.COMPRESSED_SEGMENTATION:
        payload.subvolume_format = "RAW";
        payload.image_format_options = {
          compressed_segmentation_block_size: vec3Key(
            this.spec.compressedSegmentationBlockSize
          )
        };
        break;
      default:
        throw new Error(`Invalid encoding: ${encoding}`);
    }
  }
  async download(chunk, signal) {
    const { parameters } = this;
    const chunkPosition = this.computeChunkBounds(chunk);
    const chunkDataSize = chunk.chunkDataSize;
    const path = `/v1/volumes/${parameters.volumeId}/subvolume:binary`;
    const payload = {
      geometry: {
        corner: vec3Key(chunkPosition),
        size: vec3Key(chunkDataSize),
        scale: parameters.scaleIndex
      }
    };
    this.applyEncodingParams(payload);
    applyChangeStack(parameters.changeSpec, payload);
    const response = await makeRequest(
      parameters.instance,
      this.credentialsProvider,
      path,
      {
        method: "POST",
        body: JSON.stringify(payload),
        signal
      }
    );
    await this.chunkDecoder(chunk, signal, await response.arrayBuffer());
  }
};
BrainmapsVolumeChunkSource = __decorateClass16([
  registerSharedObject()
], BrainmapsVolumeChunkSource);
function getFragmentCorner(fragmentId, xBits, yBits, zBits) {
  const value = parseUint64(BigInt("0x" + fragmentId));
  return decodeZIndexCompressed(value, xBits, yBits, zBits);
}
function decodeMultiscaleManifestChunk(chunk, response) {
  verifyObject(response);
  const source = chunk.source;
  const fragmentKeys = verifyObjectProperty(
    response,
    "fragmentKey",
    verifyStringArray
  );
  const supervoxelIds = verifyObjectProperty(
    response,
    "supervoxelId",
    verifyStringArray
  );
  const length6 = fragmentKeys.length;
  if (length6 !== supervoxelIds.length) {
    throw new Error(
      "Expected fragmentKey and supervoxelId arrays to have the same length."
    );
  }
  const fragmentSupervoxelIds = /* @__PURE__ */ new Map();
  fragmentKeys.forEach((fragmentId, i) => {
    let ids = fragmentSupervoxelIds.get(fragmentId);
    if (ids === void 0) {
      ids = [];
      fragmentSupervoxelIds.set(fragmentId, ids);
    }
    ids.push(supervoxelIds[i]);
  });
  const { chunkShape } = source.parameters.info;
  const gridShape = source.parameters.info.lods[0].gridShape;
  const xBits = Math.ceil(Math.log2(gridShape[0]));
  const yBits = Math.ceil(Math.log2(gridShape[1]));
  const zBits = Math.ceil(Math.log2(gridShape[2]));
  const fragmentIdAndCorners = Array.from(fragmentSupervoxelIds.entries()).map(
    ([id, supervoxelIds2]) => ({
      fragmentId: id,
      corner: getFragmentCorner(id, xBits, yBits, zBits),
      supervoxelIds: supervoxelIds2
    })
  );
  fragmentIdAndCorners.sort((a, b) => {
    return zorder3LessThan(
      a.corner[0],
      a.corner[1],
      a.corner[2],
      b.corner[0],
      b.corner[1],
      b.corner[2]
    ) ? -1 : 1;
  });
  let clipLowerBound;
  let clipUpperBound;
  let minNumLods = 0;
  let octree;
  if (length6 === 0) {
    clipLowerBound = clipUpperBound = kZeroVec;
    octree = Uint32Array.of(0, 0, 0, 0, 2147483648);
  } else {
    const minCoord = vec3_exports.clone(kInfinityVec);
    const maxCoord = vec3_exports.clone(kZeroVec);
    fragmentIdAndCorners.forEach((x) => {
      const { corner } = x;
      for (let i = 0; i < 3; ++i) {
        minCoord[i] = Math.min(minCoord[i], corner[i]);
        maxCoord[i] = Math.max(maxCoord[i], corner[i]);
      }
    });
    minNumLods = 1;
    while (maxCoord[0] >>> minNumLods - 1 !== minCoord[0] >>> minNumLods - 1 || maxCoord[1] >>> minNumLods - 1 !== minCoord[1] >>> minNumLods - 1 || maxCoord[2] >>> minNumLods - 1 !== minCoord[2] >>> minNumLods - 1) {
      ++minNumLods;
    }
    clipLowerBound = vec3_exports.multiply(minCoord, minCoord, chunkShape);
    clipUpperBound = vec3_exports.add(
      maxCoord,
      vec3_exports.multiply(maxCoord, maxCoord, chunkShape),
      chunkShape
    );
  }
  const { lods } = source.parameters.info;
  const lodScales = new Float32Array(Math.max(lods.length, minNumLods));
  for (let lodIndex = 0; lodIndex < lods.length; ++lodIndex) {
    lodScales[lodIndex] = lods[lodIndex].scale;
  }
  if (length6 !== 0) {
    const octreeTemp = new Uint32Array(
      fragmentIdAndCorners.length * lodScales.length * 5
    );
    fragmentIdAndCorners.forEach((x, i) => {
      octreeTemp.set(x.corner, i * 5);
      octreeTemp[i * 5] = x.corner[0];
    });
    let priorStart = 0;
    let priorEnd = fragmentIdAndCorners.length;
    for (let lod = 1; lod < lodScales.length; ++lod) {
      const curEnd = generateHigherOctreeLevel(
        octreeTemp,
        priorStart,
        priorEnd
      );
      priorStart = priorEnd;
      priorEnd = curEnd;
    }
    octree = octreeTemp.slice(0, priorEnd * 5);
  }
  const manifest = {
    chunkShape,
    chunkGridSpatialOrigin: kZeroVec,
    clipLowerBound,
    clipUpperBound,
    octree,
    lodScales,
    vertexOffsets: new Float32Array(lodScales.length * 3)
  };
  chunk.manifest = manifest;
  chunk.fragmentSupervoxelIds = fragmentIdAndCorners;
}
var maxMeshBatchSize = 255;
function decodeBatchMeshResponse(response, callback) {
  const length6 = response.byteLength;
  let index = 0;
  const dataView2 = new DataView(response);
  const headerSize = (
    /*object id*/
    8 + /*fragment key length*/
    8 + /*num vertices*/
    8 + /*num triangles*/
    8
  );
  while (index < length6) {
    if (index + headerSize > length6) {
      throw new Error("Invalid batch mesh fragment response.");
    }
    const objectId = dataView2.getBigUint64(
      index,
      /*littleEndian=*/
      true
    );
    const objectIdString = objectId.toString();
    const prefix = objectIdString + "\0";
    index += 8;
    const fragmentKeyLength = dataView2.getUint32(
      index,
      /*littleEndian=*/
      true
    );
    const fragmentKeyLengthHigh = dataView2.getUint32(
      index + 4,
      /*littleEndian=*/
      true
    );
    index += 8;
    if (fragmentKeyLengthHigh !== 0) {
      throw new Error("Invalid batch mesh fragment response.");
    }
    if (index + fragmentKeyLength + /* num vertices */
    8 + /*num indices*/
    8 > length6) {
      throw new Error("Invalid batch mesh fragment response.");
    }
    const fragmentKey = new TextDecoder().decode(
      new Uint8Array(response, index, fragmentKeyLength)
    );
    const fullKey = prefix + fragmentKey;
    index += fragmentKeyLength;
    const numVertices = dataView2.getUint32(
      index,
      /*littleEndian=*/
      true
    );
    const numVerticesHigh = dataView2.getUint32(
      index + 4,
      /*littleEndian=*/
      true
    );
    index += 8;
    const numTriangles = dataView2.getUint32(
      index,
      /*littleEndian=*/
      true
    );
    const numTrianglesHigh = dataView2.getUint32(
      index + 4,
      /*littleEndian=*/
      true
    );
    index += 8;
    if (numVerticesHigh !== 0 || numTrianglesHigh !== 0) {
      throw new Error("Invalid batch mesh fragment response.");
    }
    const endOffset = index + numTriangles * 12 + numVertices * 12;
    if (endOffset > length6) {
      throw new Error("Invalid batch mesh fragment response.");
    }
    callback({
      fullKey,
      buffer: response,
      verticesOffset: index,
      numVertices,
      indicesOffset: index + 12 * numVertices,
      numIndices: numTriangles * 3
    });
    index = endOffset;
  }
}
function combineBatchMeshFragments(fragments) {
  let totalVertices = 0;
  let totalIndices = 0;
  for (const fragment of fragments) {
    totalVertices += fragment.numVertices;
    totalIndices += fragment.numIndices;
  }
  const vertexBuffer = new Float32Array(totalVertices * 3);
  const indexBuffer = new Uint32Array(totalIndices);
  let vertexOffset = 0;
  let indexOffset = 0;
  for (const fragment of fragments) {
    vertexBuffer.set(
      new Float32Array(
        fragment.buffer,
        fragment.verticesOffset,
        fragment.numVertices * 3
      ),
      vertexOffset * 3
    );
    const { numIndices } = fragment;
    const sourceIndices = new Uint32Array(
      fragment.buffer,
      fragment.indicesOffset,
      numIndices
    );
    convertEndian32(sourceIndices, Endianness.LITTLE);
    for (let i = 0; i < numIndices; ++i) {
      indexBuffer[indexOffset++] = sourceIndices[i] + vertexOffset;
    }
    vertexOffset += fragment.numVertices;
  }
  convertEndian32(vertexBuffer, Endianness.LITTLE);
  return { vertexPositions: vertexBuffer, indices: indexBuffer };
}
async function makeBatchMeshRequest(credentialsProvider, parameters, ids, signal) {
  const path = "/v1/objects/meshes:batch";
  const batches = [];
  let prevObjectId;
  let batchSize = 0;
  const pendingIds = /* @__PURE__ */ new Map();
  for (const [id, idData] of ids) {
    pendingIds.set(id, idData);
    ids.delete(id);
    const splitIndex = id.indexOf("\0");
    const objectId = id.substring(0, splitIndex);
    const fragmentId = id.substring(splitIndex + 1);
    if (objectId !== prevObjectId) {
      batches.push({ object_id: objectId, fragment_keys: [] });
    }
    batches[batches.length - 1].fragment_keys.push(fragmentId);
    if (++batchSize === maxMeshBatchSize) break;
  }
  const payload = {
    volume_id: parameters.volumeId,
    mesh_name: parameters.meshName,
    batches
  };
  try {
    return await (await makeRequest(parameters.instance, credentialsProvider, path, {
      method: "POST",
      body: JSON.stringify(payload),
      signal
    })).arrayBuffer();
  } finally {
    for (const [id, idData] of pendingIds) {
      ids.set(id, idData);
    }
  }
}
var BrainmapsMultiscaleMeshSource = class extends BrainmapsSource(
  MultiscaleMeshSource,
  MultiscaleMeshSourceParameters
) {
  listFragmentsParams = (() => {
    const { parameters } = this;
    const { changeSpec } = parameters;
    if (changeSpec !== void 0) {
      return `&header.changeStackId=${changeSpec.changeStackId}`;
    }
    return "";
  })();
  download(chunk, signal) {
    const { parameters } = this;
    const path = `/v1/objects/${parameters.volumeId}/meshes/${parameters.info.lods[0].info.name}:listfragments?object_id=${chunk.objectId}&return_supervoxel_ids=true` + this.listFragmentsParams;
    return makeRequest(parameters.instance, this.credentialsProvider, path, {
      signal
    }).then((response) => response.json()).then((response) => decodeMultiscaleManifestChunk(chunk, response));
  }
  async downloadFragment(chunk, signal) {
    const { parameters } = this;
    const manifestChunk = chunk.manifestChunk;
    const { fragmentSupervoxelIds } = manifestChunk;
    const manifest = manifestChunk.manifest;
    const { lod } = chunk;
    const { octree } = manifest;
    const numBaseChunks = fragmentSupervoxelIds.length;
    const row = chunk.chunkIndex;
    let startChunkIndex = row;
    while (startChunkIndex >= numBaseChunks) {
      startChunkIndex = octree[startChunkIndex * 5 + 3];
    }
    let endChunkIndex = row + 1;
    while (endChunkIndex > numBaseChunks) {
      endChunkIndex = octree[endChunkIndex * 5 - 1] & 2147483647;
    }
    const { relativeBlockShape, gridShape } = parameters.info.lods[lod];
    const xBits = Math.ceil(Math.log2(gridShape[0]));
    const yBits = Math.ceil(Math.log2(gridShape[1]));
    const zBits = Math.ceil(Math.log2(gridShape[2]));
    let ids = /* @__PURE__ */ new Map();
    for (let chunkIndex = startChunkIndex; chunkIndex < endChunkIndex; ++chunkIndex) {
      const gridX = Math.floor(octree[chunkIndex * 5] / relativeBlockShape[0]);
      const gridY = Math.floor(
        octree[chunkIndex * 5 + 1] / relativeBlockShape[1]
      );
      const gridZ = Math.floor(
        octree[chunkIndex * 5 + 2] / relativeBlockShape[2]
      );
      const fragmentKey = encodeZIndexCompressed3d(
        xBits,
        yBits,
        zBits,
        gridX,
        gridY,
        gridZ
      ).toString(16).padStart(16, "0");
      const entry = fragmentSupervoxelIds[chunkIndex];
      for (const supervoxelId of entry.supervoxelIds) {
        ids.set(supervoxelId + "\0" + fragmentKey, chunkIndex);
      }
    }
    const prevLod = Math.max(0, lod - 1);
    const fragments = [];
    const idArray = Array.from(ids);
    idArray.sort((a, b) => defaultStringCompare(a[0], b[0]));
    ids = new Map(idArray);
    const meshName = parameters.info.lods[lod].info.name;
    const parallelRequests = true;
    await new Promise((resolve, reject) => {
      let requestsInProgress = 0;
      let error = false;
      const maybeIssueMoreRequests = () => {
        if (error) return;
        while (ids.size !== 0) {
          ++requestsInProgress;
          makeBatchMeshRequest(
            this.credentialsProvider,
            {
              instance: parameters.instance,
              volumeId: parameters.volumeId,
              meshName
            },
            ids,
            signal
          ).then((response) => {
            --requestsInProgress;
            decodeBatchMeshResponse(
              response,
              (fragment) => {
                const chunkIndex = ids.get(fragment.fullKey);
                if (!ids.delete(fragment.fullKey)) {
                  throw new Error(
                    `Received unexpected fragment key: ${JSON.stringify(
                      fragment.fullKey
                    )}.`
                  );
                }
                fragment.chunkIndex = chunkIndex;
                fragments.push(fragment);
              }
            );
            maybeIssueMoreRequests();
          }).catch((e) => {
            error = true;
            reject(e);
          });
          if (!parallelRequests) break;
        }
        chunk.downloadSlots = Math.max(1, requestsInProgress);
        if (requestsInProgress === 0) {
          resolve(void 0);
          return;
        }
      };
      maybeIssueMoreRequests();
    });
    fragments.sort((a, b) => a.chunkIndex - b.chunkIndex);
    let indexOffset = 0;
    const numSubChunks = 1 << 3 * (lod - prevLod);
    const subChunkOffsets = new Uint32Array(numSubChunks + 1);
    let prevSubChunkIndex = 0;
    for (const fragment of fragments) {
      const row2 = fragment.chunkIndex;
      const subChunkIndex = getOctreeChildIndex(
        octree[row2 * 5] >>> prevLod,
        octree[row2 * 5 + 1] >>> prevLod,
        octree[row2 * 5 + 2] >>> prevLod
      ) & numSubChunks - 1;
      subChunkOffsets.fill(
        indexOffset,
        prevSubChunkIndex + 1,
        subChunkIndex + 1
      );
      prevSubChunkIndex = subChunkIndex;
      indexOffset += fragment.numIndices;
    }
    subChunkOffsets.fill(indexOffset, prevSubChunkIndex + 1, numSubChunks + 1);
    assignMultiscaleMeshFragmentData(
      chunk,
      { ...combineBatchMeshFragments(fragments), subChunkOffsets },
      VertexPositionFormat.float32
    );
  }
};
BrainmapsMultiscaleMeshSource = __decorateClass16([
  registerSharedObject()
], BrainmapsMultiscaleMeshSource);
function groupFragmentsIntoBatches(ids) {
  const batches = [];
  let index = 0;
  const length6 = ids.length;
  while (index < length6) {
    batches.push(JSON.stringify(ids.slice(index, index + maxMeshBatchSize)));
    index += maxMeshBatchSize;
  }
  return batches;
}
function decodeManifestChunkWithSupervoxelIds(chunk, response) {
  verifyObject(response);
  const fragmentKeys = verifyObjectProperty(
    response,
    "fragmentKey",
    verifyStringArray
  );
  const supervoxelIds = verifyObjectProperty(
    response,
    "supervoxelId",
    verifyStringArray
  );
  const length6 = fragmentKeys.length;
  if (length6 !== supervoxelIds.length) {
    throw new Error(
      "Expected fragmentKey and supervoxelId arrays to have the same length."
    );
  }
  const fragmentIds = supervoxelIds.map(
    (supervoxelId, index) => supervoxelId + "\0" + fragmentKeys[index]
  );
  chunk.fragmentIds = groupFragmentsIntoBatches(fragmentIds);
}
var BrainmapsMeshSource = class extends BrainmapsSource(
  MeshSource,
  MeshSourceParameters2
) {
  listFragmentsParams = (() => {
    const { parameters } = this;
    const { changeSpec } = parameters;
    if (changeSpec !== void 0) {
      return `&header.changeStackId=${changeSpec.changeStackId}`;
    }
    return "";
  })();
  download(chunk, signal) {
    const { parameters } = this;
    const path = `/v1/objects/${parameters.volumeId}/meshes/${parameters.meshName}:listfragments?object_id=${chunk.objectId}&return_supervoxel_ids=true` + this.listFragmentsParams;
    return makeRequest(parameters.instance, this.credentialsProvider, path, {
      signal
    }).then((response) => response.json()).then(
      (response) => decodeManifestChunkWithSupervoxelIds(chunk, response)
    );
  }
  async downloadFragment(chunk, signal) {
    const { parameters } = this;
    const ids = /* @__PURE__ */ new Map();
    for (const id of JSON.parse(chunk.fragmentId)) {
      ids.set(id, null);
    }
    const fragments = [];
    const { credentialsProvider } = this;
    while (ids.size !== 0) {
      const response = await makeBatchMeshRequest(
        credentialsProvider,
        parameters,
        ids,
        signal
      );
      decodeBatchMeshResponse(response, (fragment) => {
        if (!ids.delete(fragment.fullKey)) {
          throw new Error(
            `Received unexpected fragment key: ${JSON.stringify(
              fragment.fullKey
            )}.`
          );
        }
        fragments.push(fragment);
      });
    }
    assignMeshFragmentData(chunk, combineBatchMeshFragments(fragments));
  }
};
BrainmapsMeshSource = __decorateClass16([
  registerSharedObject()
], BrainmapsMeshSource);
function decodeSkeletonChunk(chunk, response) {
  const dv = new DataView(response);
  const numVertices = dv.getUint32(0, true);
  const numVerticesHigh = dv.getUint32(4, true);
  if (numVerticesHigh !== 0) {
    throw new Error("The number of vertices should not exceed 2^32-1.");
  }
  const numEdges = dv.getUint32(8, true);
  const numEdgesHigh = dv.getUint32(12, true);
  if (numEdgesHigh !== 0) {
    throw new Error("The number of edges should not exceed 2^32-1.");
  }
  decodeSkeletonVertexPositionsAndIndices(
    chunk,
    response,
    Endianness.LITTLE,
    /*vertexByteOffset=*/
    16,
    numVertices,
    /*indexByteOffset=*/
    void 0,
    /*numEdges=*/
    numEdges
  );
}
var BrainmapsSkeletonSource = class extends BrainmapsSource(
  SkeletonSource,
  SkeletonSourceParameters
) {
  download(chunk, signal) {
    const { parameters } = this;
    const payload = {
      object_id: `${chunk.objectId}`
    };
    const path = `/v1/objects/${parameters.volumeId}/meshes/${parameters.meshName}/skeleton:binary`;
    applyChangeStack(parameters.changeSpec, payload);
    return makeRequest(parameters.instance, this.credentialsProvider, path, {
      method: "POST",
      body: JSON.stringify(payload),
      signal
    }).then((response) => response.arrayBuffer()).then((response) => decodeSkeletonChunk(chunk, response));
  }
};
BrainmapsSkeletonSource = __decorateClass16([
  registerSharedObject()
], BrainmapsSkeletonSource);
var spatialAnnotationTypes = ["LOCATION", "LINE", "VOLUME"];
function parseCommaSeparatedPoint(x) {
  const pattern = /(-?[0-9]+),(-?[0-9]+),(-?[0-9]+)/;
  const cornerParts = x.match(pattern);
  if (cornerParts === null) {
    throw new Error(`Error parsing number triplet: ${JSON.stringify(x)}.`);
  }
  return vec3_exports.fromValues(
    parseFloat(cornerParts[1]),
    parseFloat(cornerParts[2]),
    parseFloat(cornerParts[3])
  );
}
function getIdPrefix(parameters) {
  return parameters.volumeId + ":" + parameters.changestack + ":";
}
function parseBrainmapsAnnotationId(idPrefix, fullId) {
  if (!fullId.startsWith(idPrefix)) {
    throw new Error(
      `Received annotation id ${JSON.stringify(
        fullId
      )} does not have expected prefix of ${JSON.stringify(idPrefix)}.`
    );
  }
  const id = fullId.substring(idPrefix.length);
  return id;
}
function parseObjectLabels(obj) {
  if (obj == null) {
    return void 0;
  }
  return [BigUint64Array.from(parseArray(obj, parseUint64))];
}
function parseAnnotation(entry, idPrefix, expectedId) {
  const corner = verifyObjectProperty(
    entry,
    "corner",
    (x) => parseCommaSeparatedPoint(verifyString(x))
  );
  const size = verifyObjectProperty(
    entry,
    "size",
    (x) => parseCommaSeparatedPoint(verifyString(x))
  );
  const description = verifyObjectProperty(
    entry,
    "payload",
    verifyOptionalString
  );
  const spatialAnnotationType = verifyObjectProperty(
    entry,
    "type",
    verifyString
  );
  const fullId = verifyObjectProperty(entry, "id", verifyString);
  const id = parseBrainmapsAnnotationId(idPrefix, fullId);
  const segments = verifyObjectProperty(
    entry,
    "objectLabels",
    parseObjectLabels
  );
  if (expectedId !== void 0 && id !== expectedId) {
    throw new Error(
      `Received annotation has unexpected id ${JSON.stringify(fullId)}.`
    );
  }
  switch (spatialAnnotationType) {
    case "LOCATION": {
      if (vec3_exports.equals(size, kZeroVec)) {
        return {
          type: AnnotationType.POINT,
          id,
          point: corner,
          description,
          relatedSegments: segments,
          properties: []
        };
      }
      const radii = vec3_exports.scale(vec3_exports.create(), size, 0.5);
      const center = vec3_exports.add(vec3_exports.create(), corner, radii);
      return {
        type: AnnotationType.ELLIPSOID,
        id,
        center,
        radii,
        description,
        relatedSegments: segments,
        properties: []
      };
    }
    case "LINE":
      return {
        type: AnnotationType.LINE,
        id,
        pointA: corner,
        pointB: vec3_exports.add(vec3_exports.create(), corner, size),
        description,
        relatedSegments: segments,
        properties: []
      };
    case "VOLUME":
      return {
        type: AnnotationType.AXIS_ALIGNED_BOUNDING_BOX,
        id,
        pointA: corner,
        pointB: vec3_exports.add(vec3_exports.create(), corner, size),
        description,
        relatedSegments: segments,
        properties: []
      };
    default:
      throw new Error(
        `Unknown spatial annotation type: ${JSON.stringify(
          spatialAnnotationType
        )}.`
      );
  }
}
function parseAnnotationResponse(response, idPrefix, expectedId) {
  verifyObject(response);
  const entry = verifyObjectProperty(
    response,
    "annotations",
    (x) => parseFixedLengthArray([void 0], x, verifyObject)
  )[0];
  return parseAnnotation(entry, idPrefix, expectedId);
}
var annotationPropertySerializers = makeAnnotationPropertySerializers(
  /*rank=*/
  3,
  /*propertySpecs=*/
  []
);
function parseAnnotations(chunk, responses) {
  const serializer = new AnnotationSerializer(annotationPropertySerializers);
  const source = chunk.source.parent;
  const idPrefix = getIdPrefix(source.parameters);
  responses.forEach((response, responseIndex) => {
    try {
      verifyObject(response);
      const annotationsArray = verifyObjectProperty(
        response,
        "annotations",
        (x) => x === void 0 ? [] : x
      );
      if (!Array.isArray(annotationsArray)) {
        throw new Error(
          `Expected array, but received ${JSON.stringify(
            typeof annotationsArray
          )}.`
        );
      }
      for (const entry of annotationsArray) {
        try {
          serializer.add(parseAnnotation(entry, idPrefix));
        } catch (e) {
          throw new Error(`Error parsing annotation: ${e.message}`);
        }
      }
    } catch (parseError) {
      throw new Error(
        `Error parsing ${spatialAnnotationTypes[responseIndex]} annotations: ${parseError.message}`
      );
    }
  });
  chunk.data = Object.assign(
    new AnnotationGeometryData(),
    serializer.serialize()
  );
}
function getSpatialAnnotationTypeFromId(id) {
  const index = id.indexOf(".");
  return id.substring(0, index);
}
function toCommaSeparated(v) {
  return `${Math.round(v[0])},${Math.round(v[1])},${Math.round(v[2])}`;
}
function getFullSpatialAnnotationId(parameters, id) {
  return `${parameters.volumeId}:${parameters.changestack}:${id}`;
}
function annotationToBrainmaps(annotation) {
  const payload = annotation.description || "";
  const objectLabels = annotation.relatedSegments === void 0 ? void 0 : Array.from(annotation.relatedSegments[0], (x) => x.toString());
  switch (annotation.type) {
    case AnnotationType.LINE: {
      const { pointA, pointB } = annotation;
      const size = vec3_exports.subtract(vec3_exports.create(), pointB, pointA);
      return {
        type: "LINE",
        corner: toCommaSeparated(pointA),
        size: toCommaSeparated(size),
        object_labels: objectLabels,
        payload
      };
    }
    case AnnotationType.AXIS_ALIGNED_BOUNDING_BOX: {
      const { pointA, pointB } = annotation;
      const minPoint = min3(vec3_exports.create(), pointA, pointB);
      const maxPoint = max3(vec3_exports.create(), pointA, pointB);
      const size = vec3_exports.subtract(maxPoint, maxPoint, minPoint);
      return {
        type: "VOLUME",
        corner: toCommaSeparated(minPoint),
        size: toCommaSeparated(size),
        object_labels: objectLabels,
        payload
      };
    }
    case AnnotationType.POINT: {
      return {
        type: "LOCATION",
        corner: toCommaSeparated(annotation.point),
        size: "0,0,0",
        object_labels: objectLabels,
        payload
      };
    }
    case AnnotationType.ELLIPSOID: {
      const corner = vec3_exports.subtract(
        vec3_exports.create(),
        annotation.center,
        annotation.radii
      );
      const size = vec3_exports.scale(vec3_exports.create(), annotation.radii, 2);
      return {
        type: "LOCATION",
        corner: toCommaSeparated(corner),
        size: toCommaSeparated(size),
        object_labels: objectLabels,
        payload
      };
    }
  }
}
var BrainmapsAnnotationGeometryChunkSource = class extends BrainmapsSource(
  AnnotationGeometryChunkSourceBackend,
  AnnotationSpatialIndexSourceParameters
) {
  async download(chunk, signal) {
    const { parameters } = this;
    return Promise.all(
      spatialAnnotationTypes.map(
        (spatialAnnotationType) => makeRequest(
          parameters.instance,
          this.credentialsProvider,
          `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:get`,
          {
            signal,
            method: "POST",
            body: JSON.stringify({
              type: spatialAnnotationType,
              ignore_payload: true
            })
          }
        ).then((response) => response.json())
      )
    ).then((values) => {
      parseAnnotations(chunk, values);
    });
  }
};
BrainmapsAnnotationGeometryChunkSource = __decorateClass16([
  registerSharedObject()
], BrainmapsAnnotationGeometryChunkSource);
var BrainmapsAnnotationSource = class extends BrainmapsSource(
  AnnotationSource,
  AnnotationSourceParameters
) {
  downloadSegmentFilteredGeometry(chunk, _relationshipIndex, signal) {
    const { parameters } = this;
    return Promise.all(
      spatialAnnotationTypes.map(
        (spatialAnnotationType) => makeRequest(
          parameters.instance,
          this.credentialsProvider,
          `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:get`,
          {
            signal,
            method: "POST",
            body: JSON.stringify({
              type: spatialAnnotationType,
              object_labels: [chunk.objectId.toString()],
              ignore_payload: true
            })
          }
        ).then((response) => response.json())
      )
    ).then((values) => {
      parseAnnotations(chunk, values);
    });
  }
  downloadMetadata(chunk, signal) {
    const { parameters } = this;
    const id = chunk.key;
    return makeRequest(
      parameters.instance,
      this.credentialsProvider,
      `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:get`,
      {
        signal,
        method: "POST",
        body: JSON.stringify({
          type: getSpatialAnnotationTypeFromId(id),
          id: getFullSpatialAnnotationId(parameters, id)
        })
      }
    ).then((response) => response.json()).then(
      (response) => {
        chunk.annotation = parseAnnotationResponse(
          response,
          getIdPrefix(parameters),
          id
        );
      },
      () => {
        chunk.annotation = null;
      }
    );
  }
  add(annotation) {
    const { parameters } = this;
    const brainmapsAnnotation = annotationToBrainmaps(annotation);
    return makeRequest(
      parameters.instance,
      this.credentialsProvider,
      `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:push`,
      {
        method: "POST",
        body: JSON.stringify({ annotations: [brainmapsAnnotation] })
      }
    ).then((response) => response.json()).then((response) => {
      verifyObject(response);
      const ids = verifyObjectProperty(response, "ids", verifyStringArray);
      if (ids.length !== 1) {
        throw new Error(
          `Expected list of 1 id, but received ${JSON.stringify(ids)}.`
        );
      }
      const idPrefix = getIdPrefix(this.parameters);
      return parseBrainmapsAnnotationId(idPrefix, ids[0]);
    });
  }
  update(id, annotation) {
    const { parameters } = this;
    const brainmapsAnnotation = annotationToBrainmaps(annotation);
    brainmapsAnnotation.id = getFullSpatialAnnotationId(parameters, id);
    return makeRequest(
      parameters.instance,
      this.credentialsProvider,
      `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:push`,
      {
        method: "POST",
        body: JSON.stringify({ annotations: [brainmapsAnnotation] })
      }
    ).then((response) => response.json());
  }
  delete(id) {
    const { parameters } = this;
    return makeRequest(
      parameters.instance,
      this.credentialsProvider,
      `/v1/changes/${parameters.volumeId}/${parameters.changestack}/spatials:delete`,
      {
        method: "POST",
        body: JSON.stringify({
          type: getSpatialAnnotationTypeFromId(id),
          ids: [getFullSpatialAnnotationId(parameters, id)]
        })
      }
    ).then((response) => response.json());
  }
};
BrainmapsAnnotationSource = __decorateClass16([
  registerSharedObject()
], BrainmapsAnnotationSource);

// node_modules/neuroglancer/lib/datasource/deepzoom/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/decode_png_request.js
init_legacy_browser();
var decodePng = asyncComputation("decodePng");

// node_modules/neuroglancer/lib/datasource/deepzoom/base.js
init_legacy_browser();
var ImageTileEncoding = /* @__PURE__ */ ((ImageTileEncoding2) => {
  ImageTileEncoding2[ImageTileEncoding2["JPG"] = 0] = "JPG";
  ImageTileEncoding2[ImageTileEncoding2["JPEG"] = 1] = "JPEG";
  ImageTileEncoding2[ImageTileEncoding2["PNG"] = 2] = "PNG";
  return ImageTileEncoding2;
})(ImageTileEncoding || {});
var ImageTileSourceParameters = class {
  url;
  encoding;
  format;
  tilesize;
  overlap;
  static RPC_ID = "deepzoom/ImageTileSource";
};

// node_modules/neuroglancer/lib/datasource/deepzoom/backend.js
var __defProp18 = Object.defineProperty;
var __getOwnPropDesc18 = Object.getOwnPropertyDescriptor;
var __decorateClass17 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc18(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp18(target2, key, result);
  return result;
};
var DeepzoomImageTileSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(VolumeChunkSource),
  ImageTileSourceParameters
) {
  tileKvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  gridShape = (() => {
    const gridShape = new Uint32Array(2);
    const { upperVoxelBound, chunkDataSize } = this.spec;
    for (let i = 0; i < 2; ++i) {
      gridShape[i] = Math.ceil(upperVoxelBound[i] / chunkDataSize[i]);
    }
    return gridShape;
  })();
  async download(chunk, signal) {
    const { parameters } = this;
    const { tilesize, overlap, encoding } = parameters;
    const [x, y] = chunk.chunkGridPosition;
    const ox = x === 0 ? 0 : overlap;
    const oy = y === 0 ? 0 : overlap;
    const path = `${this.tileKvStore.path}/${x}_${y}.${parameters.format}`;
    const response = await this.tileKvStore.store.read(path, {
      signal
    });
    if (response === void 0) {
      return;
    }
    const responseArray = new Uint8Array(await response.response.arrayBuffer());
    let tilewidth = 0;
    let tileheight = 0;
    let tiledata;
    switch (encoding) {
      case ImageTileEncoding.PNG: {
        const pngbitmap = await requestAsyncComputation(
          decodePng,
          signal,
          [responseArray.buffer],
          responseArray,
          void 0,
          void 0,
          void 0,
          3,
          1,
          false
        );
        ({ width: tilewidth, height: tileheight } = pngbitmap);
        tiledata = transposeArray2d(
          pngbitmap.uint8Array,
          tilewidth * tileheight,
          3
        );
        break;
      }
      case ImageTileEncoding.JPG:
      case ImageTileEncoding.JPEG: {
        const jpegbitmap = await requestAsyncComputation(
          decodeJpeg,
          signal,
          [responseArray.buffer],
          responseArray,
          void 0,
          void 0,
          void 0,
          3,
          false
        );
        ({
          uint8Array: tiledata,
          width: tilewidth,
          height: tileheight
        } = jpegbitmap);
        break;
      }
    }
    if (tiledata !== void 0) {
      const t2 = tilesize * tilesize;
      const twh = tilewidth * tileheight;
      const d = chunk.data = new Uint8Array(t2 * 3);
      for (let k = 0; k < 3; k++)
        for (let j = 0; j < tileheight; j++)
          for (let i = 0; i < tilewidth; i++)
            d[i + j * tilesize + k * t2] = tiledata[i + ox + (j + oy) * tilewidth + k * twh];
    }
  }
};
DeepzoomImageTileSource = __decorateClass17([
  registerSharedObject()
], DeepzoomImageTileSource);

// node_modules/neuroglancer/lib/datasource/dvid/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/dvid/api.js
init_legacy_browser();
var DVIDInstance = class {
  constructor(baseUrl, nodeKey) {
    this.baseUrl = baseUrl;
    this.nodeKey = nodeKey;
  }
  getNodeApiUrl(path = "") {
    return `${this.baseUrl}/api/node/${this.nodeKey}${path}`;
  }
  getRepoInfoUrl() {
    return `${this.baseUrl}/api/repos/info`;
  }
  getKeyValueUrl(dataName, key) {
    return `${this.getNodeApiUrl()}/${dataName}/key/${key}`;
  }
  getKeyValueRangeUrl(dataName, startKey, endKey) {
    return `${this.getNodeApiUrl()}/${dataName}/keyrange/${startKey}/${endKey}`;
  }
  getKeyValuesUrl(dataName) {
    return `${this.getNodeApiUrl()}/${dataName}/keyvalues?jsontar=false`;
  }
};
function appendQueryStringForDvid(url, user) {
  if (url.includes("?")) {
    url += "&";
  } else {
    url += "?";
  }
  url += "app=Neuroglancer";
  if (user) {
    url += `&u=${user}`;
  }
  return url;
}
function fetchWithDVIDCredentials(credentialsProvider, input, init) {
  return fetchOkWithCredentials(
    credentialsProvider,
    input,
    init,
    (credentials, init2) => {
      const newInit = { ...init2 };
      if (credentials.token) {
        newInit.headers = {
          ...newInit.headers,
          Authorization: `Bearer ${credentials}`
        };
      }
      return newInit;
    },
    (error) => {
      const { status } = error;
      if (status === 403 || status === 401) {
        return "refresh";
      }
      throw error;
    }
  );
}

// node_modules/neuroglancer/lib/datasource/dvid/base.js
init_legacy_browser();
var VolumeChunkEncoding2 = /* @__PURE__ */ ((VolumeChunkEncoding22) => {
  VolumeChunkEncoding22[VolumeChunkEncoding22["JPEG"] = 0] = "JPEG";
  VolumeChunkEncoding22[VolumeChunkEncoding22["RAW"] = 1] = "RAW";
  VolumeChunkEncoding22[VolumeChunkEncoding22["COMPRESSED_SEGMENTATION"] = 2] = "COMPRESSED_SEGMENTATION";
  VolumeChunkEncoding22[VolumeChunkEncoding22["COMPRESSED_SEGMENTATIONARRAY"] = 3] = "COMPRESSED_SEGMENTATIONARRAY";
  return VolumeChunkEncoding22;
})(VolumeChunkEncoding2 || {});
var DVIDSourceParameters = class {
  baseUrl;
  nodeKey;
  dataInstanceKey;
  authServer;
  user;
};
var VolumeChunkSourceParameters2 = class extends DVIDSourceParameters {
  dataScale;
  encoding;
  static RPC_ID = "dvid/VolumeChunkSource";
};
var SkeletonSourceParameters2 = class extends DVIDSourceParameters {
  static RPC_ID = "dvid/SkeletonSource";
};
var MeshSourceParameters3 = class extends DVIDSourceParameters {
  static RPC_ID = "dvid/MeshSource";
};

// node_modules/neuroglancer/lib/skeleton/decode_swc_skeleton.js
init_legacy_browser();
function decodeSwcSkeletonChunk(chunk, swcStr) {
  const swcObjects = parseSwc(swcStr);
  if (swcObjects.length < 1) {
    throw new Error("ERROR parsing swc data");
  }
  const indexMap = new Uint32Array(swcObjects.length);
  let nodeCount = 0;
  let edgeCount = 0;
  swcObjects.forEach((swcObj, i) => {
    if (swcObj) {
      indexMap[i] = nodeCount++;
      if (swcObj.parent >= 0) {
        ++edgeCount;
      }
    }
  });
  const glVertices = new Float32Array(3 * nodeCount);
  const glIndices = new Uint32Array(2 * edgeCount);
  let nodeIndex = 0;
  let edgetIndex = 0;
  swcObjects.forEach((swcObj) => {
    if (swcObj) {
      glVertices[3 * nodeIndex] = swcObj.x;
      glVertices[3 * nodeIndex + 1] = swcObj.y;
      glVertices[3 * nodeIndex + 2] = swcObj.z;
      if (swcObj.parent >= 0) {
        glIndices[2 * edgetIndex] = nodeIndex;
        glIndices[2 * edgetIndex + 1] = indexMap[swcObj.parent];
        ++edgetIndex;
      }
      ++nodeIndex;
    }
  });
  chunk.indices = glIndices;
  chunk.vertexPositions = glVertices;
}
function parseSwc(swcStr) {
  const swcInputAr = swcStr.split("\n");
  const swcObjectsAr = [];
  const float = "-?\\d*(?:\\.\\d+)?";
  const pattern = new RegExp(
    "^[ \\t]*(" + [
      "\\d+",
      // index
      "\\d+",
      // type
      float,
      // x
      float,
      // y
      float,
      // z
      float,
      // radius
      "-1|\\d+"
      // parent
    ].join(")[ \\t]+(") + ")[ \\t]*$"
  );
  swcInputAr.forEach((e) => {
    const match = e.match(pattern);
    if (match) {
      const point = swcObjectsAr[parseInt(match[1], 10)] = new PointObj();
      point.type = parseInt(match[2], 10);
      point.x = parseFloat(match[3]);
      point.y = parseFloat(match[4]);
      point.z = parseFloat(match[5]);
      point.radius = parseFloat(match[6]);
      point.parent = parseInt(match[7], 10);
    }
  });
  return swcObjectsAr;
}
var PointObj = class {
  type;
  x;
  y;
  z;
  radius;
  parent;
};

// node_modules/neuroglancer/lib/datasource/dvid/backend.js
var __defProp19 = Object.defineProperty;
var __getOwnPropDesc19 = Object.getOwnPropertyDescriptor;
var __decorateClass18 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc19(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp19(target2, key, result);
  return result;
};
function DVIDSource(Base, parametersConstructor) {
  return WithParameters(
    WithSharedCredentialsProviderCounterpart()(Base),
    parametersConstructor
  );
}
var DVIDSkeletonSource = class extends DVIDSource(
  SkeletonSource,
  SkeletonSourceParameters2
) {
  download(chunk, signal) {
    const { parameters } = this;
    const bodyid = `${chunk.objectId}`;
    const url = `${parameters.baseUrl}/api/node/${parameters.nodeKey}/${parameters.dataInstanceKey}/key/` + bodyid + "_swc";
    return fetchWithDVIDCredentials(
      this.credentialsProvider,
      appendQueryStringForDvid(url, parameters.user),
      {
        signal
      }
    ).then((response) => response.arrayBuffer()).then((response) => {
      const enc = new TextDecoder("utf-8");
      decodeSwcSkeletonChunk(chunk, enc.decode(response));
    });
  }
};
DVIDSkeletonSource = __decorateClass18([
  registerSharedObject()
], DVIDSkeletonSource);
function decodeFragmentChunk2(chunk, response) {
  const dv = new DataView(response);
  const numVertices = dv.getUint32(0, true);
  assignMeshFragmentData(
    chunk,
    decodeTriangleVertexPositionsAndIndices(
      response,
      Endianness.LITTLE,
      /*vertexByteOffset=*/
      4,
      numVertices
    )
  );
}
var DVIDMeshSource = class extends DVIDSource(
  MeshSource,
  MeshSourceParameters3
) {
  download(chunk) {
    chunk.fragmentIds = [`${chunk.objectId}`];
    return Promise.resolve(void 0);
  }
  downloadFragment(chunk, signal) {
    const { parameters } = this;
    const dvidInstance = new DVIDInstance(
      parameters.baseUrl,
      parameters.nodeKey
    );
    const meshUrl = dvidInstance.getKeyValueUrl(
      parameters.dataInstanceKey,
      `${chunk.fragmentId}.ngmesh`
    );
    return fetchWithDVIDCredentials(
      this.credentialsProvider,
      appendQueryStringForDvid(meshUrl, parameters.user),
      {
        signal
      }
    ).then((response) => response.arrayBuffer()).then((response) => decodeFragmentChunk2(chunk, response));
  }
};
DVIDMeshSource = __decorateClass18([
  registerSharedObject()
], DVIDMeshSource);
var DVIDVolumeChunkSource = class extends DVIDSource(
  VolumeChunkSource,
  VolumeChunkSourceParameters2
) {
  async download(chunk, signal) {
    const params = this.parameters;
    let path;
    {
      const chunkPosition = this.computeChunkBounds(chunk);
      const chunkDataSize = chunk.chunkDataSize;
      path = this.getPath(chunkPosition, chunkDataSize);
    }
    const decoder2 = this.getDecoder(params);
    const response = await fetchWithDVIDCredentials(
      this.credentialsProvider,
      appendQueryStringForDvid(`${params.baseUrl}${path}`, params.user),
      { signal }
    ).then((response2) => response2.arrayBuffer());
    await decoder2(
      chunk,
      signal,
      params.encoding === VolumeChunkEncoding2.JPEG ? response.slice(16) : response
    );
  }
  getPath(chunkPosition, chunkDataSize) {
    const params = this.parameters;
    if (params.encoding === VolumeChunkEncoding2.JPEG) {
      return `/api/node/${params.nodeKey}/${params.dataInstanceKey}/subvolblocks/${chunkDataSize[0]}_${chunkDataSize[1]}_${chunkDataSize[2]}/${chunkPosition[0]}_${chunkPosition[1]}_${chunkPosition[2]}`;
    }
    if (params.encoding === VolumeChunkEncoding2.RAW) {
      return `/api/node/${params.nodeKey}/${params.dataInstanceKey}/raw/0_1_2/${chunkDataSize[0]}_${chunkDataSize[1]}_${chunkDataSize[2]}/${chunkPosition[0]}_${chunkPosition[1]}_${chunkPosition[2]}/jpeg`;
    }
    if (params.encoding === VolumeChunkEncoding2.COMPRESSED_SEGMENTATIONARRAY) {
      return `/api/node/${params.nodeKey}/${params.dataInstanceKey}/raw/0_1_2/${chunkDataSize[0]}_${chunkDataSize[1]}_${chunkDataSize[2]}/${chunkPosition[0]}_${chunkPosition[1]}_${chunkPosition[2]}?compression=googlegzip&scale=${params.dataScale}`;
    }
    return `/api/node/${params.nodeKey}/${params.dataInstanceKey}/raw/0_1_2/${chunkDataSize[0]}_${chunkDataSize[1]}_${chunkDataSize[2]}/${chunkPosition[0]}_${chunkPosition[1]}_${chunkPosition[2]}?compression=googlegzip`;
  }
  getDecoder(params) {
    if (params.encoding === VolumeChunkEncoding2.JPEG || params.encoding === VolumeChunkEncoding2.RAW) {
      return decodeJpegChunk;
    }
    return decodeCompressedSegmentationChunk;
  }
};
DVIDVolumeChunkSource = __decorateClass18([
  registerSharedObject()
], DVIDVolumeChunkSource);

// node_modules/neuroglancer/lib/datasource/graphene/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/graphene/base.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/http/common.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/http/read.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/byte_range/file_handle.js
init_legacy_browser();
function composeByteRangeRequest(outer, inner) {
  if (inner === void 0) {
    return { outer, inner: { offset: 0, length: outer.length } };
  }
  if ("suffixLength" in inner) {
    const length6 = Math.min(outer.length, inner.suffixLength);
    return {
      outer: { offset: outer.offset + (outer.length - length6), length: length6 },
      inner: { offset: outer.length - length6, length: length6 }
    };
  }
  if (inner.offset + inner.length > outer.length) {
    throw new Error(
      `Requested byte range ${JSON.stringify(
        inner
      )} not valid for value of length ${outer.length}`
    );
  }
  return {
    outer: { offset: outer.offset + inner.offset, length: inner.length },
    inner
  };
}
function handleByteRangeRequestFromUint8Array(value, byteRange) {
  const {
    outer: { offset, length: length6 }
  } = composeByteRangeRequest({ offset: 0, length: value.length }, byteRange);
  return {
    offset,
    length: length6,
    totalSize: value.length,
    response: new Response(value.subarray(offset, offset + length6))
  };
}
var FileByteRangeHandle = class {
  constructor(base, byteRange) {
    this.base = base;
    this.byteRange = byteRange;
  }
  async stat(options) {
    options;
    return { totalSize: this.byteRange.length };
  }
  async read(options) {
    const { byteRange } = this;
    const { outer: outerByteRange, inner: innerByteRange } = composeByteRangeRequest(byteRange, options.byteRange);
    if (outerByteRange.length === 0) {
      return {
        response: new Response(new Uint8Array(0)),
        totalSize: byteRange.length,
        ...innerByteRange
      };
    }
    const response = await readFileHandle(this.base, {
      signal: options.signal,
      byteRange: outerByteRange,
      strictByteRange: true,
      throwIfMissing: true
    });
    return {
      response: response.response,
      totalSize: byteRange.length,
      ...innerByteRange
    };
  }
  getUrl() {
    const { offset, length: length6 } = this.byteRange;
    return `${this.base.getUrl()}|range:${offset}-${offset + length6}`;
  }
};

// node_modules/neuroglancer/lib/kvstore/http/read.js
function getRangeHeader(request) {
  if (request === void 0) return void 0;
  return `bytes=${request.offset}-${request.offset + request.length - 1}`;
}
var byteRangeCacheMode = navigator.userAgent.indexOf("Chrome") !== -1 ? "no-store" : "default";
function wasRedirectedToDirectoryListing(url, response) {
  return new URL(url).pathname + "/" === new URL(response.url).pathname;
}
function parse206ContentRangeHeader(contentRange) {
  const m = contentRange.match(/bytes ([0-9]+)-([0-9]+)\/([0-9]+|\*)/);
  if (m === null) {
    throw new Error(
      `Invalid content-range header: ${JSON.stringify(contentRange)}`
    );
  }
  const offset = parseInt(m[1], 10);
  const endPos = parseInt(m[2], 10);
  let totalSize;
  if (m[3] !== "*") {
    totalSize = parseInt(m[3], 10);
  }
  const length6 = endPos - offset + 1;
  return { offset, length: length6, totalSize };
}
async function read(store, key, url, options, fetchOkImpl = fetchOk) {
  let resolvedByteRange;
  try {
    const { byteRange: byteRangeRequest } = options;
    let rangeHeader;
    if (byteRangeRequest !== void 0) {
      if ("suffixLength" in byteRangeRequest) {
        const statResponse = await stat(store, key, url, options, fetchOkImpl);
        if (statResponse === void 0) return void 0;
        const { totalSize: totalSize2 } = statResponse;
        if (totalSize2 === void 0) {
          throw new Error(
            `Failed to determine total size of ${store.getUrl(key)} in order to fetch suffix ${JSON.stringify(byteRangeRequest)}`
          );
        }
        resolvedByteRange = composeByteRangeRequest(
          { offset: 0, length: totalSize2 },
          byteRangeRequest
        ).outer;
        if (resolvedByteRange.length === 0) {
          return {
            ...resolvedByteRange,
            totalSize: totalSize2,
            response: new Response(new Uint8Array(0))
          };
        }
        rangeHeader = getRangeHeader(resolvedByteRange);
      } else {
        resolvedByteRange = byteRangeRequest;
        if (resolvedByteRange.length === 0) {
          rangeHeader = getRangeHeader({
            offset: Math.max(resolvedByteRange.offset - 1, 0),
            length: 1
          });
        } else {
          rangeHeader = getRangeHeader(resolvedByteRange);
        }
      }
    }
    const requestInit = {
      signal: options.signal,
      progressListener: options.progressListener
    };
    if (rangeHeader !== void 0) {
      requestInit.headers = { range: rangeHeader };
      requestInit.cache = byteRangeCacheMode;
    }
    let response = await fetchOkImpl(url, requestInit);
    if (wasRedirectedToDirectoryListing(url, response)) {
      return void 0;
    }
    let offset;
    let length6;
    let totalSize;
    if (response.status === 206) {
      const contentRange = response.headers.get("content-range");
      if (contentRange === null) {
        if (resolvedByteRange !== void 0) {
          offset = resolvedByteRange.offset;
        } else {
          throw new Error(
            "Unexpected HTTP 206 response when no byte range specified."
          );
        }
      }
      if (contentRange !== null) {
        ({ offset, length: length6, totalSize } = parse206ContentRangeHeader(contentRange));
      }
    } else {
      length6 = totalSize = getBodyLength(response.headers);
    }
    if (offset === void 0) {
      offset = 0;
    }
    if (length6 === void 0) {
      length6 = getBodyLength(response.headers);
    }
    if ((resolvedByteRange == null ? void 0 : resolvedByteRange.length) === 0) {
      response = new Response(new Uint8Array(0));
      offset = resolvedByteRange.offset;
      length6 = 0;
    }
    return {
      response,
      offset,
      length: length6,
      totalSize
    };
  } catch (e) {
    if (e instanceof HttpError && e.status === 416 && (resolvedByteRange == null ? void 0 : resolvedByteRange.length) === 0 && resolvedByteRange.offset === 0) {
      return {
        response: new Response(new Uint8Array(0)),
        offset: 0,
        length: 0,
        totalSize: 0
      };
    }
    return handleThrowIfMissing(store, key, options, e);
  }
}
function getBodyLength(headers) {
  const contentLength = headers.get("content-length");
  const contentEncoding = headers.get("content-encoding");
  if (contentEncoding === null && contentLength !== null) {
    const size = Number(contentLength);
    if (!Number.isFinite(size) || size < 0) {
      throw new Error(`Invalid content-length: {contentLength}`);
    }
    return size;
  }
  return void 0;
}
function handleThrowIfMissing(store, key, options, error) {
  if (isNotFoundError(error)) {
    if (options.throwIfMissing === true) {
      throw new NotFoundError(new KvStoreFileHandle(store, key), {
        cause: error
      });
    }
    return void 0;
  }
  throw error;
}
async function stat(store, key, url, options, fetchOkImpl = fetchOk) {
  try {
    const response = await fetchOkImpl(url, {
      method: "HEAD",
      signal: options.signal,
      progressListener: options.progressListener
    });
    if (wasRedirectedToDirectoryListing(url, response)) return void 0;
    return { totalSize: getBodyLength(response.headers) };
  } catch (e) {
    if (e instanceof HttpError && (e.status === 405 || e.status === 501)) {
    } else {
      return handleThrowIfMissing(store, key, options, e);
    }
  }
  try {
    const response = await fetchOkImpl(url, {
      signal: options.signal,
      progressListener: options.progressListener,
      headers: { range: "bytes=0-0" }
    });
    if (wasRedirectedToDirectoryListing(url, response)) return void 0;
    let totalSize;
    if (response.status === 200) {
      totalSize = getBodyLength(response.headers);
    } else {
      const contentRange = response.headers.get("content-range");
      if (contentRange !== null) {
        ({ totalSize } = parse206ContentRangeHeader(contentRange));
      }
    }
    return { totalSize };
  } catch (e) {
    if (e instanceof HttpError && e.status === 416) {
      return { totalSize: 0 };
    }
    return handleThrowIfMissing(store, key, options, e);
  }
}

// node_modules/neuroglancer/lib/kvstore/http/common.js
var ReadableHttpKvStore = class {
  constructor(sharedKvStoreContext, baseUrl, baseUrlForDisplay = baseUrl, fetchOkImpl = fetchOk) {
    this.sharedKvStoreContext = sharedKvStoreContext;
    this.baseUrl = baseUrl;
    this.baseUrlForDisplay = baseUrlForDisplay;
    this.fetchOkImpl = fetchOkImpl;
  }
  stat(key, options) {
    return stat(
      this,
      key,
      joinBaseUrlAndPath(this.baseUrl, key),
      options,
      this.fetchOkImpl
    );
  }
  read(key, options) {
    return read(
      this,
      key,
      joinBaseUrlAndPath(this.baseUrl, key),
      options,
      this.fetchOkImpl
    );
  }
  getUrl(path) {
    return joinBaseUrlAndPath(this.baseUrlForDisplay, path);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};
function httpProvider(scheme, sharedKvStoreContext, httpKvStoreClass) {
  return {
    scheme,
    description: `${scheme} (unauthenticated)`,
    getKvStore(url) {
      try {
        const { baseUrl, path } = getBaseHttpUrlAndPath(url.url);
        return {
          store: new httpKvStoreClass(sharedKvStoreContext, baseUrl),
          path
        };
      } catch (e) {
        throw new Error(`Invalid URL ${JSON.stringify(url.url)}`, {
          cause: e
        });
      }
    }
  };
}
function registerProviders(registry, httpKvStoreClass) {
  for (const httpScheme of ["http", "https"]) {
    registry.registerBaseKvStoreProvider(
      (context) => httpProvider(httpScheme, context, httpKvStoreClass)
    );
  }
}

// node_modules/neuroglancer/lib/datasource/graphene/base.js
var GRAPHENE_MESH_NEW_SEGMENT_RPC_ID = "GrapheneMeshSource:NewSegment";
var ChunkedGraphSourceParameters = class {
  url;
  static RPC_ID = "graphene/ChunkedGraphSource";
};
var MeshSourceParameters4 = class {
  manifestUrl;
  fragmentUrl;
  lod;
  sharding;
  nBitsForLayerId;
  static RPC_ID = "graphene/MeshSource";
};
function isBaseSegmentId(segmentId, nBitsForLayerId) {
  const layerId = segmentId >> BigInt(64 - nBitsForLayerId);
  return layerId == 1n;
}
function getGrapheneFragmentKey(fragmentId) {
  const sharded = fragmentId.charAt(0) === "~";
  if (sharded) {
    const parts = fragmentId.substring(1).split(/:(.+)/);
    return { key: parts[0], fragmentId: parts[1] };
  }
  return { key: fragmentId, fragmentId };
}
var CHUNKED_GRAPH_LAYER_RPC_ID = "ChunkedGraphLayer";
var CHUNKED_GRAPH_RENDER_LAYER_UPDATE_SOURCES_RPC_ID = "ChunkedGraphLayer:updateSources";
var RENDER_RATIO_LIMIT = 5;
async function parseGrapheneError(e) {
  if (e.response) {
    let msg;
    if (e.response.headers.get("content-type") === "application/json") {
      msg = (await e.response.json()).message;
    } else {
      msg = await e.response.text();
    }
    return msg;
  }
  return void 0;
}
function getHttpSource(kvStoreContext, url) {
  const { store, path } = kvStoreContext.getKvStore(url);
  if (!(store instanceof ReadableHttpKvStore)) {
    throw new Error(`Non-HTTP URL ${JSON.stringify(url)} not supported`);
  }
  const { fetchOkImpl, baseUrl } = store;
  if (baseUrl.includes("?")) {
    throw new Error(`Invalid URL ${baseUrl}: query parameters not supported`);
  }
  return { fetchOkImpl, baseUrl: joinBaseUrlAndPath(baseUrl, path) };
}

// node_modules/neuroglancer/lib/datasource/precomputed/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/precomputed/base.js
init_legacy_browser();
var VolumeChunkEncoding3 = /* @__PURE__ */ ((VolumeChunkEncoding22) => {
  VolumeChunkEncoding22[VolumeChunkEncoding22["RAW"] = 0] = "RAW";
  VolumeChunkEncoding22[VolumeChunkEncoding22["JPEG"] = 1] = "JPEG";
  VolumeChunkEncoding22[VolumeChunkEncoding22["COMPRESSED_SEGMENTATION"] = 2] = "COMPRESSED_SEGMENTATION";
  VolumeChunkEncoding22[VolumeChunkEncoding22["COMPRESSO"] = 3] = "COMPRESSO";
  VolumeChunkEncoding22[VolumeChunkEncoding22["PNG"] = 4] = "PNG";
  VolumeChunkEncoding22[VolumeChunkEncoding22["JXL"] = 5] = "JXL";
  return VolumeChunkEncoding22;
})(VolumeChunkEncoding3 || {});
var VolumeChunkSourceParameters3 = class {
  url;
  encoding;
  sharding;
  static RPC_ID = "precomputed/VolumeChunkSource";
};
var MeshSourceParameters5 = class {
  url;
  lod;
  static RPC_ID = "precomputed/MeshSource";
};
var DataEncoding = /* @__PURE__ */ ((DataEncoding2) => {
  DataEncoding2[DataEncoding2["RAW"] = 0] = "RAW";
  DataEncoding2[DataEncoding2["GZIP"] = 1] = "GZIP";
  return DataEncoding2;
})(DataEncoding || {});
var ShardingHashFunction = /* @__PURE__ */ ((ShardingHashFunction2) => {
  ShardingHashFunction2[ShardingHashFunction2["IDENTITY"] = 0] = "IDENTITY";
  ShardingHashFunction2[ShardingHashFunction2["MURMURHASH3_X86_128"] = 1] = "MURMURHASH3_X86_128";
  return ShardingHashFunction2;
})(ShardingHashFunction || {});
var MultiscaleMeshSourceParameters2 = class {
  url;
  metadata;
  static RPC_ID = "precomputed/MultiscaleMeshSource";
};
var SkeletonSourceParameters3 = class {
  url;
  metadata;
  static RPC_ID = "precomputed/SkeletonSource";
};
var AnnotationSpatialIndexSourceParameters2 = class {
  url;
  sharding;
  static RPC_ID = "precomputed/AnnotationSpatialIndexSource";
};
var AnnotationSourceParameters2 = class {
  rank;
  relationships;
  properties;
  byId;
  type;
  static RPC_ID = "precomputed/AnnotationSource";
};

// node_modules/neuroglancer/lib/datasource/precomputed/sharded.js
init_legacy_browser();

// node_modules/neuroglancer/lib/chunk_manager/generic_file_source.js
init_legacy_browser();

// node_modules/neuroglancer/lib/util/object_id.js
init_legacy_browser();
var OBJECT_ID_SYMBOL = Symbol("objectId");
var nextObjectId = 0;
function getObjectId(x) {
  if (x instanceof Object) {
    let id = x[OBJECT_ID_SYMBOL];
    if (id === void 0) {
      id = x[OBJECT_ID_SYMBOL] = nextObjectId++;
    }
    return `o${id}`;
  }
  return "" + JSON.stringify(x);
}

// node_modules/neuroglancer/lib/chunk_manager/generic_file_source.js
var AsyncCacheChunk = class extends Chunk {
  asyncMemoize;
  initialize(key) {
    super.initialize(key);
  }
  freeSystemMemory() {
    this.asyncMemoize = void 0;
  }
};
var SimpleAsyncCache = class extends ChunkSourceBase {
  constructor(chunkManager, options) {
    super(chunkManager);
    this.registerDisposer(chunkManager);
    this.downloadFunction = options.get;
    this.encodeKeyFunction = options.encodeKey ?? stableStringify;
  }
  encodeKeyFunction;
  downloadFunction;
  get(key, options) {
    const encodedKey = this.encodeKeyFunction(key);
    let chunk = this.chunks.get(encodedKey);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(AsyncCacheChunk);
      chunk.initialize(encodedKey);
      this.addChunk(chunk);
    }
    if (chunk.asyncMemoize === void 0) {
      chunk.asyncMemoize = asyncMemoizeWithProgress(async (progressOptions) => {
        try {
          const { data, size } = await this.downloadFunction(
            key,
            progressOptions
          );
          chunk.systemMemoryBytes = size;
          chunk.queueManager.updateChunkState(
            chunk,
            ChunkState.SYSTEM_MEMORY_WORKER
          );
          return data;
        } catch (e) {
          chunk.queueManager.updateChunkState(chunk, ChunkState.FAILED);
          throw e;
        }
      });
    }
    if (chunk.state === ChunkState.SYSTEM_MEMORY_WORKER) {
      chunk.chunkManager.queueManager.markRecentlyUsed(chunk);
    }
    return chunk.asyncMemoize(options);
  }
};
function makeSimpleAsyncCache(chunkManager, memoizeKey, options) {
  return chunkManager.memoize.get(
    `simpleAsyncCache:${memoizeKey}`,
    () => new SimpleAsyncCache(chunkManager.addRef(), options)
  );
}
function getCachedDecodedUrl(sharedKvStoreContext, url, decodeFunction, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    `getCachedDecodedUrl:${getObjectId(decodeFunction)}`,
    () => {
      const cache2 = new SimpleAsyncCache(
        sharedKvStoreContext.chunkManager.addRef(),
        {
          get: async (url2, progressOptions) => {
            const readResponse = await sharedKvStoreContext.kvStoreContext.read(
              url2,
              { ...progressOptions, throwIfMissing: true }
            );
            try {
              return decodeFunction(readResponse, progressOptions);
            } catch (e) {
              throw new Error("Error reading ${url}", { cause: e });
            }
          }
        }
      );
      cache2.registerDisposer(sharedKvStoreContext.addRef());
      return cache2;
    }
  );
  return cache.get(url, options);
}

// node_modules/neuroglancer/lib/kvstore/gzip/file_handle.js
init_legacy_browser();
var EXPECTED_HEADER_OVERHEAD = 100;
var GzipFileHandle = class {
  constructor(base, format) {
    this.base = base;
    this.format = format;
  }
  async stat(options) {
    await this.base.stat(options);
    return { totalSize: void 0 };
  }
  async read(options) {
    const { byteRange } = options;
    if (byteRange === void 0) {
      const readResponse = await this.base.read(options);
      if (readResponse === void 0) return void 0;
      return {
        response: new Response(
          decodeGzipStream(readResponse.response, this.format)
        ),
        offset: 0,
        length: void 0,
        totalSize: void 0
      };
    }
    if ("suffixLength" in byteRange || byteRange.offset !== 0) {
      throw new Error(
        `Byte range with offset not supported: ${JSON.stringify(byteRange)}`
      );
    }
    let decodedArray = new Uint8Array(byteRange.length);
    const parts = [];
    let encodedBytesReceived = 0;
    let expectedEncodedBytes = byteRange.length + EXPECTED_HEADER_OVERHEAD;
    while (true) {
      const readResponse = await this.base.read({
        ...options,
        byteRange: {
          offset: encodedBytesReceived,
          length: expectedEncodedBytes - encodedBytesReceived
        }
      });
      if (readResponse === void 0) return void 0;
      {
        const part = new Uint8Array(await readResponse.response.arrayBuffer());
        parts.push(part);
        encodedBytesReceived += part.length;
      }
      const decompressionStream = new DecompressionStream("gzip");
      const writer = decompressionStream.writable.getWriter();
      const writePromises = [];
      for (const part of parts) {
        writePromises.push(writer.write(part));
      }
      writePromises.push(writer.close());
      const reader = decompressionStream.readable.getReader();
      let decodedOffset = 0;
      try {
        while (decodedOffset < decodedArray.length) {
          let { value } = await reader.read();
          if (value === void 0) {
            break;
          }
          const remainingLength = decodedArray.length - decodedOffset;
          if (value.length > remainingLength) {
            value = value.subarray(0, remainingLength);
          }
          decodedArray.set(value, decodedOffset);
          decodedOffset += value.length;
        }
        if (decodedOffset === decodedArray.length || encodedBytesReceived === readResponse.totalSize) {
          if (decodedOffset < decodedArray.length) {
            decodedArray = decodedArray.subarray(0, decodedOffset);
          }
          return {
            response: new Response(decodedArray),
            offset: 0,
            length: decodedArray.length,
            totalSize: void 0
          };
        }
      } finally {
        await reader.cancel();
        await Promise.allSettled(writePromises);
      }
      expectedEncodedBytes += Math.min(
        100,
        decodedArray.length - decodedOffset
      );
    }
  }
  getUrl() {
    return this.base.getUrl() + "|gzip";
  }
};

// node_modules/neuroglancer/lib/util/hash.js
init_legacy_browser();
function murmurHash3_x86_128Mix(h) {
  h ^= h >>> 16;
  h = Math.imul(h, 2246822507);
  h ^= h >>> 13;
  h = Math.imul(h, 3266489909);
  h ^= h >>> 16;
  return h;
}
function rotl32(x, r) {
  return x << r | x >>> 32 - r;
}
function murmurHash3_x86_128Hash64Bits_Bigint(seed, input) {
  let h1 = seed;
  let h2 = seed;
  let h3 = seed;
  let h4 = seed;
  const c1 = 597399067;
  const c2 = 2869860233;
  const c3 = 951274213;
  let k22 = Math.imul(Number(input >> BigInt(32)), c2);
  k22 = rotl32(k22, 16);
  k22 = Math.imul(k22, c3);
  h2 ^= k22;
  let k12 = Math.imul(Number(input & BigInt(4294967295)), c1);
  k12 = rotl32(k12, 15);
  k12 = Math.imul(k12, c2);
  h1 ^= k12;
  const len4 = 8;
  h1 ^= len4;
  h2 ^= len4;
  h3 ^= len4;
  h4 ^= len4;
  h1 = h1 + h2 >>> 0;
  h1 = h1 + h3 >>> 0;
  h1 = h1 + h4 >>> 0;
  h2 = h2 + h1 >>> 0;
  h3 = h3 + h1 >>> 0;
  h4 = h4 + h1 >>> 0;
  h1 = murmurHash3_x86_128Mix(h1);
  h2 = murmurHash3_x86_128Mix(h2);
  h3 = murmurHash3_x86_128Mix(h3);
  h4 = murmurHash3_x86_128Mix(h4);
  h1 = h1 + h2 >>> 0;
  h1 = h1 + h3 >>> 0;
  h1 = h1 + h4 >>> 0;
  h2 = h2 + h1 >>> 0;
  return BigInt(h1) | BigInt(h2) << BigInt(32);
}

// node_modules/neuroglancer/lib/datasource/precomputed/sharded.js
var shardingHashFunctions = /* @__PURE__ */ new Map([
  [
    ShardingHashFunction.MURMURHASH3_X86_128,
    (input) => murmurHash3_x86_128Hash64Bits_Bigint(
      /*seed=*/
      0,
      input
    )
  ],
  [ShardingHashFunction.IDENTITY, (input) => input]
]);
function decodeFileHandle(handle, encoding) {
  if (encoding === DataEncoding.GZIP) {
    handle = new GzipFileHandle(handle, "gzip");
  }
  return handle;
}
function makeMinishardIndexCache(chunkManager, base, sharding) {
  return new SimpleAsyncCache(chunkManager.addRef(), {
    encodeKey: (key) => key.toString(),
    get: async (shardAndMinishard, progressOptions) => {
      const minishard = shardAndMinishard & (1n << BigInt(sharding.minishardBits)) - 1n;
      const shard = (1n << BigInt(sharding.shardBits)) - 1n & shardAndMinishard >> BigInt(sharding.minishardBits);
      const shardPath = base.path + shard.toString(16).padStart(Math.ceil(sharding.shardBits / 4), "0") + ".shard";
      const shardFileHandle = new KvStoreFileHandle(base.store, shardPath);
      const shardIndexSize = BigInt(16) << BigInt(sharding.minishardBits);
      const shardIndexStart = minishard << 4n;
      const response = await readFileHandle(shardFileHandle, {
        ...progressOptions,
        byteRange: { offset: Number(shardIndexStart), length: 16 },
        strictByteRange: true
      });
      if (response === void 0) {
        return { data: void 0, size: 0 };
      }
      const shardIndexResponse = await response.response.arrayBuffer();
      const shardIndexDv = new DataView(shardIndexResponse);
      let minishardStartOffset = shardIndexDv.getBigUint64(
        0,
        /*littleEndian=*/
        true
      );
      let minishardEndOffset = shardIndexDv.getBigUint64(
        8,
        /*littleEndian=*/
        true
      );
      if (minishardStartOffset === minishardEndOffset) {
        return { data: void 0, size: 0 };
      }
      minishardStartOffset += shardIndexSize;
      minishardEndOffset += shardIndexSize;
      const minishardIndexBuffer = await (await readFileHandle(
        decodeFileHandle(
          new FileByteRangeHandle(shardFileHandle, {
            offset: Number(minishardStartOffset),
            length: Number(minishardEndOffset - minishardStartOffset)
          }),
          sharding.minishardIndexEncoding
        ),
        {
          ...progressOptions,
          strictByteRange: true,
          throwIfMissing: true
        }
      )).response.arrayBuffer();
      if (minishardIndexBuffer.byteLength % 24 !== 0) {
        throw new Error(
          `Invalid minishard index length: ${minishardIndexBuffer.byteLength}`
        );
      }
      const minishardIndex = new BigUint64Array(minishardIndexBuffer);
      convertEndian64(minishardIndex, Endianness.LITTLE);
      const minishardIndexSize = minishardIndex.byteLength / 24;
      let prevEntryKey = 0n;
      let prevStart = shardIndexSize;
      for (let i = 0; i < minishardIndexSize; ++i) {
        const entryKey = prevEntryKey + minishardIndex[i];
        prevEntryKey = minishardIndex[i] = entryKey;
        const start = prevStart + minishardIndex[minishardIndexSize + i];
        minishardIndex[minishardIndexSize + i] = start;
        const size = minishardIndex[2 * minishardIndexSize + i];
        const end = start + size;
        prevStart = end;
        minishardIndex[2 * minishardIndexSize + i] = end;
      }
      return {
        data: { data: minishardIndex, shardPath },
        size: minishardIndex.byteLength
      };
    }
  });
}
function findMinishardEntry(minishardIndex, key) {
  const minishardIndexData = minishardIndex.data;
  const minishardIndexSize = minishardIndexData.length / 3;
  for (let i = 0; i < minishardIndexSize; ++i) {
    if (minishardIndexData[i] !== key) {
      continue;
    }
    const startOffset = minishardIndexData[minishardIndexSize + i];
    const endOffset = minishardIndexData[2 * minishardIndexSize + i];
    return {
      offset: Number(startOffset),
      length: Number(endOffset - startOffset)
    };
  }
  return void 0;
}
var ShardedKvStore = class extends RefCounted {
  constructor(chunkManager, base, sharding) {
    super();
    this.base = base;
    this.sharding = sharding;
    this.minishardIndexCache = this.registerDisposer(
      makeMinishardIndexCache(chunkManager, base, sharding)
    );
  }
  minishardIndexCache;
  getUrl(key) {
    return `chunk ${key} in ${this.base.store.getUrl(this.base.path)}`;
  }
  async findKey(key, progressOptions) {
    const { sharding } = this;
    const hashFunction = shardingHashFunctions.get(sharding.hash);
    const hashCode = hashFunction(key >> BigInt(sharding.preshiftBits));
    const shardAndMinishard = hashCode & (1n << BigInt(sharding.minishardBits + sharding.shardBits)) - 1n;
    const minishardIndex = await this.minishardIndexCache.get(
      shardAndMinishard,
      progressOptions
    );
    if (minishardIndex === void 0) return void 0;
    const minishardEntry = findMinishardEntry(minishardIndex, key);
    if (minishardEntry === void 0) return void 0;
    return {
      minishardEntry,
      shardInfo: {
        shardPath: minishardIndex.shardPath,
        offset: minishardEntry.offset
      }
    };
  }
  async readWithShardInfo(key, options) {
    const { sharding } = this;
    const findResult = await this.findKey(key, options);
    if (findResult === void 0) return void 0;
    const { minishardEntry, shardInfo } = findResult;
    return {
      response: await decodeFileHandle(
        new FileByteRangeHandle(
          new KvStoreFileHandle(this.base.store, shardInfo.shardPath),
          minishardEntry
        ),
        sharding.dataEncoding
      ).read(options),
      shardInfo
    };
  }
  async stat(key, options) {
    const findResult = await this.findKey(key, options);
    if (findResult === void 0) return void 0;
    const { sharding } = this;
    if (sharding.dataEncoding !== DataEncoding.RAW) {
      return { totalSize: void 0 };
    } else {
      return { totalSize: findResult.minishardEntry.length };
    }
  }
  async read(key, options) {
    const response = await this.readWithShardInfo(key, options);
    if (response === void 0) return void 0;
    return response.response;
  }
  get supportsOffsetReads() {
    return this.sharding.dataEncoding === DataEncoding.RAW;
  }
  get supportsSuffixReads() {
    return this.sharding.dataEncoding === DataEncoding.RAW;
  }
};
function getShardedKvStoreIfApplicable(chunkSource, base, sharding) {
  if (sharding === void 0) return void 0;
  return chunkSource.registerDisposer(
    new ShardedKvStore(chunkSource.chunkManager, base, sharding)
  );
}

// node_modules/neuroglancer/lib/mesh/draco/index.js
init_legacy_browser();
var decodeResult = void 0;
var numPartitions = 0;
var wasmModule;
var libraryEnv = {
  emscripten_notify_memory_growth: (memoryIndex) => {
    memoryIndex;
  },
  neuroglancer_draco_receive_decoded_mesh: (numFaces, numVertices, indicesPointer, vertexPositionsPointer, subchunkOffsetsPointer) => {
    const numIndices = numFaces * 3;
    const memory = wasmModule.exports.memory;
    const indices = new Uint32Array(
      memory.buffer,
      indicesPointer,
      numIndices
    ).slice();
    const vertexPositions = new Uint32Array(
      memory.buffer,
      vertexPositionsPointer,
      3 * numVertices
    ).slice();
    const subChunkOffsets = new Uint32Array(
      memory.buffer,
      subchunkOffsetsPointer,
      numPartitions + 1
    ).slice();
    const mesh = {
      indices,
      vertexPositions,
      subChunkOffsets
    };
    decodeResult = mesh;
  },
  proc_exit: (code) => {
    throw `proc exit: ${code}`;
  }
};
var dracoModulePromise;
function getDracoModulePromise() {
  if (dracoModulePromise == void 0) {
    dracoModulePromise = (async () => {
      const m = wasmModule = (await WebAssembly.instantiateStreaming(
        fetch(new URL("./neuroglancer_draco.wasm", import.meta.url)),
        {
          env: libraryEnv,
          wasi_snapshot_preview1: libraryEnv
        }
      )).instance;
      m.exports._initialize();
      return m;
    })();
  }
  return dracoModulePromise;
}
async function decodeDracoPartitioned(buffer, vertexQuantizationBits, partition) {
  const m = await getDracoModulePromise();
  const offset = m.exports.malloc(buffer.byteLength);
  const heap = new Uint8Array(m.exports.memory.buffer);
  heap.set(buffer, offset);
  numPartitions = partition ? 8 : 1;
  const code = m.exports.neuroglancer_draco_decode(
    offset,
    buffer.byteLength,
    partition,
    vertexQuantizationBits,
    true
  );
  if (code === 0) {
    const r = decodeResult;
    decodeResult = void 0;
    if (r instanceof Error) throw r;
    return r;
  }
  throw new Error(`Failed to decode draco mesh: ${code}`);
}
async function decodeDraco(buffer) {
  const m = await getDracoModulePromise();
  const offset = m.exports.malloc(buffer.byteLength);
  const heap = new Uint8Array(m.exports.memory.buffer);
  heap.set(buffer, offset);
  const code = m.exports.neuroglancer_draco_decode(
    offset,
    buffer.byteLength,
    false,
    0,
    false
  );
  if (code === 0) {
    const r = decodeResult;
    decodeResult = void 0;
    if (r instanceof Error) throw r;
    r.vertexPositions = new Float32Array(r.vertexPositions.buffer);
    return r;
  }
  throw new Error(`Failed to decode draco mesh: ${code}`);
}

// node_modules/neuroglancer/lib/skeleton/decode_precomputed_skeleton.js
init_legacy_browser();
function decodeSkeletonChunk2(chunk, response, vertexAttributes) {
  const dv = new DataView(response);
  const numVertices = dv.getUint32(0, true);
  const numEdges = dv.getUint32(4, true);
  const vertexPositionsStartOffset = 8;
  let curOffset = 8 + numVertices * 4 * 3;
  decodeSkeletonVertexPositionsAndIndices(
    chunk,
    response,
    Endianness.LITTLE,
    /*vertexByteOffset=*/
    vertexPositionsStartOffset,
    numVertices,
    /*indexByteOffset=*/
    curOffset,
    /*numEdges=*/
    numEdges
  );
  curOffset += numEdges * 4 * 2;
  const attributes = [];
  for (const info of vertexAttributes.values()) {
    const bytesPerVertex = DATA_TYPE_BYTES[info.dataType] * info.numComponents;
    const totalBytes = bytesPerVertex * numVertices;
    const attribute = new Uint8Array(response, curOffset, totalBytes);
    switch (bytesPerVertex) {
      case 2:
        convertEndian16(attribute, Endianness.LITTLE);
        break;
      case 4:
      case 8:
        convertEndian32(attribute, Endianness.LITTLE);
        break;
    }
    attributes.push(attribute);
    curOffset += totalBytes;
  }
  chunk.vertexAttributes = attributes;
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/compresso.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/decode_compresso_request.js
init_legacy_browser();
var decodeCompresso = asyncComputation(
  "decodeCompresso"
);

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/compresso.js
async function decodeCompressoChunk(chunk, signal, response) {
  const image = await requestAsyncComputation(
    decodeCompresso,
    signal,
    [response],
    new Uint8Array(response)
  );
  await decodeRawChunk(chunk, signal, image.buffer);
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/jxl.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/decode_jxl_request.js
init_legacy_browser();
var decodeJxl = asyncComputation("decodeJxl");

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/jxl.js
async function decodeJxlChunk(chunk, signal, response) {
  const chunkDataSize = chunk.chunkDataSize;
  const { uint8Array: decoded } = await requestAsyncComputation(
    decodeJxl,
    signal,
    [response],
    new Uint8Array(response),
    chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
    chunkDataSize[3] || 1,
    1
    // bytesPerPixel
  );
  await postProcessRawData(chunk, signal, decoded);
}

// node_modules/neuroglancer/lib/sliceview/backend_chunk_decoders/png.js
init_legacy_browser();
async function decodePngChunk(chunk, signal, response) {
  const chunkDataSize = chunk.chunkDataSize;
  const dataType = chunk.source.spec.dataType;
  const { uint8Array: image } = await requestAsyncComputation(
    decodePng,
    signal,
    [response],
    /*buffer=*/
    new Uint8Array(response),
    /*width=*/
    void 0,
    /*height=*/
    void 0,
    /*area=*/
    chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
    /*numComponents=*/
    chunkDataSize[3] || 1,
    /*bytesPerPixel=*/
    DATA_TYPE_BYTES[dataType],
    /*convertToGrayscale=*/
    false
  );
  await decodeRawChunk(chunk, signal, image.buffer);
}

// node_modules/neuroglancer/lib/datasource/precomputed/backend.js
var __defProp20 = Object.defineProperty;
var __getOwnPropDesc20 = Object.getOwnPropertyDescriptor;
var __decorateClass19 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc20(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp20(target2, key, result);
  return result;
};
var DEBUG_MULTISCALE_INDEX = false;
function getOrNotFoundError(v) {
  if (v === void 0) throw new Error("not found");
  return v;
}
var chunkDecoders2 = /* @__PURE__ */ new Map();
chunkDecoders2.set(VolumeChunkEncoding3.RAW, decodeRawChunk);
chunkDecoders2.set(VolumeChunkEncoding3.JPEG, decodeJpegChunk);
chunkDecoders2.set(
  VolumeChunkEncoding3.COMPRESSED_SEGMENTATION,
  decodeCompressedSegmentationChunk
);
chunkDecoders2.set(VolumeChunkEncoding3.COMPRESSO, decodeCompressoChunk);
chunkDecoders2.set(VolumeChunkEncoding3.PNG, decodePngChunk);
chunkDecoders2.set(VolumeChunkEncoding3.JXL, decodeJxlChunk);
var PrecomputedVolumeChunkSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(VolumeChunkSource),
  VolumeChunkSourceParameters3
) {
  chunkDecoder = chunkDecoders2.get(this.parameters.encoding);
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  shardedKvStore = getShardedKvStoreIfApplicable(
    this,
    this.kvStore,
    this.parameters.sharding
  );
  gridShape = (() => {
    const gridShape = new Uint32Array(3);
    const { upperVoxelBound, chunkDataSize } = this.spec;
    for (let i = 0; i < 3; ++i) {
      gridShape[i] = Math.ceil(upperVoxelBound[i] / chunkDataSize[i]);
    }
    return gridShape;
  })();
  async download(chunk, signal) {
    const { shardedKvStore } = this;
    let readResponse;
    if (shardedKvStore === void 0) {
      const { kvStore } = this;
      let path;
      {
        const chunkPosition = this.computeChunkBounds(chunk);
        const chunkDataSize = chunk.chunkDataSize;
        path = `${kvStore.path}${chunkPosition[0]}-${chunkPosition[0] + chunkDataSize[0]}_${chunkPosition[1]}-${chunkPosition[1] + chunkDataSize[1]}_${chunkPosition[2]}-${chunkPosition[2] + chunkDataSize[2]}`;
      }
      readResponse = await kvStore.store.read(path, { signal });
    } else {
      this.computeChunkBounds(chunk);
      const { gridShape } = this;
      const { chunkGridPosition } = chunk;
      const xBits = Math.ceil(Math.log2(gridShape[0]));
      const yBits = Math.ceil(Math.log2(gridShape[1]));
      const zBits = Math.ceil(Math.log2(gridShape[2]));
      const chunkIndex = encodeZIndexCompressed3d(
        xBits,
        yBits,
        zBits,
        chunkGridPosition[0],
        chunkGridPosition[1],
        chunkGridPosition[2]
      );
      readResponse = await shardedKvStore.read(chunkIndex, { signal });
    }
    if (readResponse !== void 0) {
      await this.chunkDecoder(
        chunk,
        signal,
        await readResponse.response.arrayBuffer()
      );
    }
  }
};
PrecomputedVolumeChunkSource = __decorateClass19([
  registerSharedObject()
], PrecomputedVolumeChunkSource);
function decodeManifestChunk2(chunk, response) {
  return decodeJsonManifestChunk(chunk, response, "fragments");
}
function decodeFragmentChunk3(chunk, response) {
  const dv = new DataView(response);
  const numVertices = dv.getUint32(0, true);
  assignMeshFragmentData(
    chunk,
    decodeTriangleVertexPositionsAndIndices(
      response,
      Endianness.LITTLE,
      /*vertexByteOffset=*/
      4,
      numVertices
    )
  );
}
var PrecomputedMeshSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(MeshSource),
  MeshSourceParameters5
) {
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  async download(chunk, signal) {
    const { parameters, kvStore } = this;
    const response = await readKvStore(
      kvStore.store,
      `${kvStore.path}${chunk.objectId}:${parameters.lod}`,
      { signal, throwIfMissing: true }
    );
    decodeManifestChunk2(chunk, await response.response.json());
  }
  async downloadFragment(chunk, signal) {
    const { kvStore } = this;
    const response = await readKvStore(
      kvStore.store,
      `${kvStore.path}${chunk.fragmentId}`,
      { signal, throwIfMissing: true }
    );
    decodeFragmentChunk3(chunk, await response.response.arrayBuffer());
  }
};
PrecomputedMeshSource = __decorateClass19([
  registerSharedObject()
], PrecomputedMeshSource);
function decodeMultiscaleManifestChunk2(chunk, response) {
  if (response.byteLength < 28 || response.byteLength % 4 !== 0) {
    throw new Error(`Invalid index file size: ${response.byteLength}`);
  }
  const dv = new DataView(response);
  let offset = 0;
  const chunkShape = vec3_exports.fromValues(
    dv.getFloat32(
      offset,
      /*littleEndian=*/
      true
    ),
    dv.getFloat32(
      offset + 4,
      /*littleEndian=*/
      true
    ),
    dv.getFloat32(
      offset + 8,
      /*littleEndian=*/
      true
    )
  );
  offset += 12;
  const gridOrigin = vec3_exports.fromValues(
    dv.getFloat32(
      offset,
      /*littleEndian=*/
      true
    ),
    dv.getFloat32(
      offset + 4,
      /*littleEndian=*/
      true
    ),
    dv.getFloat32(
      offset + 8,
      /*littleEndian=*/
      true
    )
  );
  offset += 12;
  const numStoredLods = dv.getUint32(
    offset,
    /*littleEndian=*/
    true
  );
  offset += 4;
  if (response.byteLength < offset + (4 + 4 + 4 * 3) * numStoredLods) {
    throw new Error(
      `Invalid index file size for ${numStoredLods} lods: ${response.byteLength}`
    );
  }
  const storedLodScales = new Float32Array(response, offset, numStoredLods);
  offset += 4 * numStoredLods;
  convertEndian32(storedLodScales, Endianness.LITTLE);
  const vertexOffsets = new Float32Array(response, offset, numStoredLods * 3);
  convertEndian32(vertexOffsets, Endianness.LITTLE);
  offset += 12 * numStoredLods;
  const numFragmentsPerLod = new Uint32Array(response, offset, numStoredLods);
  offset += 4 * numStoredLods;
  convertEndian32(numFragmentsPerLod, Endianness.LITTLE);
  const totalFragments = numFragmentsPerLod.reduce((a, b) => a + b);
  if (response.byteLength !== offset + 16 * totalFragments) {
    throw new Error(
      `Invalid index file size for ${numStoredLods} lods and ${totalFragments} total fragments: ${response.byteLength}`
    );
  }
  const fragmentInfo = new Uint32Array(response, offset);
  convertEndian32(fragmentInfo, Endianness.LITTLE);
  const clipLowerBound = vec3_exports.fromValues(
    Number.POSITIVE_INFINITY,
    Number.POSITIVE_INFINITY,
    Number.POSITIVE_INFINITY
  );
  const clipUpperBound = vec3_exports.fromValues(
    Number.NEGATIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
    Number.NEGATIVE_INFINITY
  );
  let numLods = Math.max(1, storedLodScales.length);
  {
    let fragmentBase = 0;
    for (let lodIndex = 0; lodIndex < numStoredLods; ++lodIndex) {
      const numFragments = numFragmentsPerLod[lodIndex];
      if (DEBUG_MULTISCALE_INDEX) {
        for (let i = 1; i < numFragments; ++i) {
          const x0 = fragmentInfo[fragmentBase + numFragments * 0 + (i - 1)];
          const y0 = fragmentInfo[fragmentBase + numFragments * 1 + (i - 1)];
          const z0 = fragmentInfo[fragmentBase + numFragments * 2 + (i - 1)];
          const x1 = fragmentInfo[fragmentBase + numFragments * 0 + i];
          const y1 = fragmentInfo[fragmentBase + numFragments * 1 + i];
          const z1 = fragmentInfo[fragmentBase + numFragments * 2 + i];
          if (!zorder3LessThan(x0, y0, z0, x1, y1, z1)) {
            console.log(
              `Fragment index violates zorder constraint: lod=${lodIndex}, chunk ${i - 1} = [${x0},${y0},${z0}], chunk ${i} = [${x1},${y1},${z1}]`
            );
          }
        }
      }
      for (let i = 0; i < 3; ++i) {
        let upperBoundValue = Number.NEGATIVE_INFINITY;
        let lowerBoundValue = Number.POSITIVE_INFINITY;
        const base = fragmentBase + numFragments * i;
        for (let j = 0; j < numFragments; ++j) {
          const v = fragmentInfo[base + j];
          upperBoundValue = Math.max(upperBoundValue, v);
          lowerBoundValue = Math.min(lowerBoundValue, v);
        }
        if (numFragments !== 0) {
          while (upperBoundValue >>> numLods - lodIndex - 1 !== lowerBoundValue >>> numLods - lodIndex - 1) {
            ++numLods;
          }
          if (lodIndex === 0) {
            clipLowerBound[i] = Math.min(
              clipLowerBound[i],
              (1 << lodIndex) * lowerBoundValue
            );
            clipUpperBound[i] = Math.max(
              clipUpperBound[i],
              (1 << lodIndex) * (upperBoundValue + 1)
            );
          }
        }
      }
      fragmentBase += numFragments * 4;
    }
  }
  let maxFragments = 0;
  {
    let prevNumFragments = 0;
    let prevLodIndex = 0;
    for (let lodIndex = 0; lodIndex < numStoredLods; ++lodIndex) {
      const numFragments = numFragmentsPerLod[lodIndex];
      maxFragments += prevNumFragments * (lodIndex - prevLodIndex);
      prevLodIndex = lodIndex;
      prevNumFragments = numFragments;
      maxFragments += numFragments;
    }
    maxFragments += (numLods - 1 - prevLodIndex) * prevNumFragments;
  }
  const octreeTemp = new Uint32Array(5 * maxFragments);
  const offsetsTemp = new Float64Array(maxFragments + 1);
  let octree;
  {
    let priorStart = 0;
    let baseRow = 0;
    let dataOffset = 0;
    let fragmentBase = 0;
    for (let lodIndex = 0; lodIndex < numStoredLods; ++lodIndex) {
      const numFragments = numFragmentsPerLod[lodIndex];
      for (let j = 0; j < numFragments; ++j) {
        for (let i = 0; i < 3; ++i) {
          octreeTemp[5 * (baseRow + j) + i] = fragmentInfo[fragmentBase + j + i * numFragments];
        }
        const dataSize = fragmentInfo[fragmentBase + j + 3 * numFragments];
        dataOffset += dataSize;
        offsetsTemp[baseRow + j + 1] = dataOffset;
        if (dataSize === 0) {
          octreeTemp[5 * (baseRow + j) + 4] = 2147483648;
        }
      }
      fragmentBase += 4 * numFragments;
      if (lodIndex !== 0) {
        computeOctreeChildOffsets(
          octreeTemp,
          priorStart,
          baseRow,
          baseRow + numFragments
        );
      }
      priorStart = baseRow;
      baseRow += numFragments;
      while (lodIndex + 1 < numLods && (lodIndex + 1 >= storedLodScales.length || storedLodScales[lodIndex + 1] === 0)) {
        const curEnd = generateHigherOctreeLevel(
          octreeTemp,
          priorStart,
          baseRow
        );
        offsetsTemp.fill(dataOffset, baseRow + 1, curEnd + 1);
        priorStart = baseRow;
        baseRow = curEnd;
        ++lodIndex;
      }
    }
    octree = octreeTemp.slice(0, 5 * baseRow);
    chunk.offsets = offsetsTemp.slice(0, baseRow + 1);
  }
  const source = chunk.source;
  const { lodScaleMultiplier } = source.parameters.metadata;
  const lodScales = new Float32Array(numLods);
  lodScales.set(storedLodScales, 0);
  for (let i = 0; i < storedLodScales.length; ++i) {
    lodScales[i] *= lodScaleMultiplier;
  }
  chunk.manifest = {
    chunkShape,
    chunkGridSpatialOrigin: gridOrigin,
    clipLowerBound: vec3_exports.add(
      clipLowerBound,
      gridOrigin,
      vec3_exports.multiply(clipLowerBound, clipLowerBound, chunkShape)
    ),
    clipUpperBound: vec3_exports.add(
      clipUpperBound,
      gridOrigin,
      vec3_exports.multiply(clipUpperBound, clipUpperBound, chunkShape)
    ),
    octree,
    lodScales,
    vertexOffsets
  };
}
async function decodeMultiscaleFragmentChunk(chunk, response) {
  const { lod } = chunk;
  const source = chunk.manifestChunk.source;
  const rawMesh = await decodeDracoPartitioned(
    new Uint8Array(response),
    source.parameters.metadata.vertexQuantizationBits,
    lod !== 0
  );
  assignMultiscaleMeshFragmentData(
    chunk,
    rawMesh,
    source.format.vertexPositionFormat
  );
}
var PrecomputedMultiscaleMeshSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(MultiscaleMeshSource),
  MultiscaleMeshSourceParameters2
) {
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  shardedKvStore = getShardedKvStoreIfApplicable(
    this,
    this.kvStore,
    this.parameters.metadata.sharding
  );
  async download(chunk, signal) {
    const { shardedKvStore } = this;
    let readResponse;
    if (shardedKvStore === void 0) {
      const { kvStore } = this;
      readResponse = await kvStore.store.read(
        `${kvStore.path}${chunk.objectId}.index`,
        { signal }
      );
    } else {
      ({ response: readResponse, shardInfo: chunk.shardInfo } = getOrNotFoundError(
        await shardedKvStore.readWithShardInfo(chunk.objectId, {
          signal
        })
      ));
    }
    const data = await getOrNotFoundError(readResponse).response.arrayBuffer();
    decodeMultiscaleManifestChunk2(chunk, data);
  }
  async downloadFragment(chunk, signal) {
    const { kvStore } = this;
    const manifestChunk = chunk.manifestChunk;
    const chunkIndex = chunk.chunkIndex;
    const { shardInfo, offsets } = manifestChunk;
    const startOffset = offsets[chunkIndex];
    const endOffset = offsets[chunkIndex + 1];
    let requestPath;
    let adjustedStartOffset;
    let adjustedEndOffset;
    if (shardInfo !== void 0) {
      requestPath = shardInfo.shardPath;
      const fullDataSize = offsets[offsets.length - 1];
      const start = shardInfo.offset - fullDataSize + startOffset;
      const end = start + endOffset - startOffset;
      adjustedStartOffset = start;
      adjustedEndOffset = end;
    } else {
      requestPath = `${kvStore.path}${manifestChunk.objectId}`;
      adjustedStartOffset = startOffset;
      adjustedEndOffset = endOffset;
    }
    const readResponse = await readKvStore(kvStore.store, requestPath, {
      signal,
      byteRange: {
        offset: adjustedStartOffset,
        length: adjustedEndOffset - adjustedStartOffset
      },
      throwIfMissing: true,
      strictByteRange: true
    });
    await decodeMultiscaleFragmentChunk(
      chunk,
      await readResponse.response.arrayBuffer()
    );
  }
};
PrecomputedMultiscaleMeshSource = __decorateClass19([
  registerSharedObject()
], PrecomputedMultiscaleMeshSource);
async function fetchByUint64(chunkSource, id, signal) {
  const { shardedKvStore } = chunkSource;
  if (shardedKvStore === void 0) {
    const { kvStore } = chunkSource;
    return kvStore.store.read(`${kvStore.path}${id}`, {
      signal
    });
  } else {
    return shardedKvStore.read(id, { signal });
  }
}
var PrecomputedSkeletonSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(SkeletonSource),
  SkeletonSourceParameters3
) {
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  shardedKvStore = getShardedKvStoreIfApplicable(
    this,
    this.kvStore,
    this.parameters.metadata.sharding
  );
  async download(chunk, signal) {
    const { parameters } = this;
    const response = getOrNotFoundError(
      await fetchByUint64(this, chunk.objectId, signal)
    );
    decodeSkeletonChunk2(
      chunk,
      await response.response.arrayBuffer(),
      parameters.metadata.vertexAttributes
    );
  }
};
PrecomputedSkeletonSource = __decorateClass19([
  registerSharedObject()
], PrecomputedSkeletonSource);
function parseAnnotations2(buffer, parameters, propertySerializer) {
  const isLittleEndian = true;
  if (buffer.byteLength < 8) throw new Error("Expected at least 8 bytes");
  const dv = new DataView(buffer);
  const countHigh = dv.getUint32(4, isLittleEndian);
  if (countHigh !== 0) throw new Error("Annotation count too high");
  const numAnnotations = dv.getUint32(0, isLittleEndian);
  const numBytesPerInstance = propertySerializer.serializedBytes;
  let expectedNonIndexInputBytes = 8 + numBytesPerInstance * numAnnotations;
  let numInstances = numAnnotations;
  const annotationType = parameters.type;
  if (annotationType === AnnotationType.POLYLINE) {
    const result = calculatePolylineMemoryUsage(
      dv,
      parameters.rank,
      numAnnotations,
      numBytesPerInstance,
      isLittleEndian
    );
    numInstances = result.numInstances;
    expectedNonIndexInputBytes = result.totalBytes;
  }
  const ids = extractAnnotationIdsFromBuffer(
    buffer,
    dv,
    numAnnotations,
    expectedNonIndexInputBytes
  );
  const inputData = new Uint8Array(buffer, 8, expectedNonIndexInputBytes - 8);
  const geometryData = new AnnotationGeometryData();
  const typeToInstanceCounts = geometryData.typeToInstanceCounts = new Array(annotationTypes.length);
  typeToInstanceCounts.fill([]);
  const { propertyGroupBytes } = propertySerializer;
  if (propertyGroupBytes.length > 1 || annotationType === AnnotationType.POLYLINE) {
    const result = restructureAnnotationData(
      dv,
      inputData,
      propertySerializer,
      numInstances,
      numAnnotations,
      annotationType,
      parameters.rank,
      isLittleEndian
    );
    geometryData.data = result.outputData;
    typeToInstanceCounts[AnnotationType.POLYLINE] = result.polylineInstanceCounts;
  } else {
    geometryData.data = inputData;
    typeToInstanceCounts[parameters.type] = Array.from(
      { length: ids.length },
      (_, i) => i
    );
  }
  const typeToOffset = geometryData.typeToOffset = new Array(
    annotationTypes.length
  );
  typeToOffset.fill(0);
  const typeToIds = geometryData.typeToIds = new Array(
    annotationTypes.length
  );
  const typeToIdMaps = geometryData.typeToIdMaps = new Array(annotationTypes.length);
  const typeToSize = geometryData.typeToSize = new Array(
    annotationTypes.length
  );
  typeToSize.fill(0);
  typeToSize[parameters.type] = numInstances;
  typeToIds.fill([]);
  typeToIds[parameters.type] = ids;
  typeToIdMaps.fill(/* @__PURE__ */ new Map());
  typeToIdMaps[parameters.type] = new Map(ids.map((id, i) => [id, i]));
  return geometryData;
}
function restructureAnnotationData(inputDataView, inputData, propertySerializer, numInstances, numAnnotations, annotationType, rank, isLittleEndian) {
  const { propertyGroupBytes, serializedBytes: numBytesPerInstance } = propertySerializer;
  const glBufferSize = numBytesPerInstance * numInstances;
  const outputData = new Uint8Array(glBufferSize);
  let polylineInstanceCounts = [];
  if (annotationType === AnnotationType.POLYLINE) {
    polylineInstanceCounts = reformatPolylineBuffer(
      inputDataView,
      inputData,
      outputData,
      propertySerializer,
      numAnnotations,
      rank,
      isLittleEndian
    );
  }
  let dataToTransform = inputData;
  if (annotationType === AnnotationType.POLYLINE) {
    dataToTransform = new Uint8Array(outputData);
  }
  if (propertyGroupBytes.length > 1) {
    let origOffset = 0;
    let groupOffset = 0;
    for (let groupIndex = 0; groupIndex < propertyGroupBytes.length; ++groupIndex) {
      let runningTotalInstances = 0;
      const groupBytesPerAnnotation = propertyGroupBytes[groupIndex];
      for (let annotationIndex = 0; annotationIndex < numAnnotations; ++annotationIndex) {
        let numGlInstances = 1;
        if (annotationType === AnnotationType.POLYLINE) {
          if (annotationIndex === numAnnotations - 1) {
            numGlInstances = numInstances - polylineInstanceCounts[annotationIndex];
          } else {
            numGlInstances = polylineInstanceCounts[annotationIndex + 1] - polylineInstanceCounts[annotationIndex];
          }
        }
        for (let instanceIndex = 0; instanceIndex < numGlInstances; ++instanceIndex) {
          const origBase = origOffset + runningTotalInstances * numBytesPerInstance;
          const newBase = groupOffset + runningTotalInstances * groupBytesPerAnnotation;
          outputData.set(
            dataToTransform.subarray(
              origBase,
              origBase + groupBytesPerAnnotation
            ),
            newBase
          );
          ++runningTotalInstances;
        }
      }
      origOffset += groupBytesPerAnnotation;
      groupOffset += groupBytesPerAnnotation * numInstances;
    }
  }
  return { outputData, polylineInstanceCounts };
}
function reformatPolylineBuffer(inputDataView, inputData, outputData, propertySerializer, numAnnotations, rank, isLittleEndian) {
  const outputDataView = new DataView(outputData.buffer);
  let inputDataOffset = 0;
  let outputDataOffset = 0;
  const pointCountBytes = 4;
  const pointBytes = rank * 4;
  const numBytesPerInstance = propertySerializer.serializedBytes;
  const numPropertyBytes = numBytesPerInstance - 2 * pointBytes - pointCountBytes;
  const numAnnotationsOffset = 8;
  let cumulativeInstances = 0;
  const instanceCounts = new Array(numAnnotations);
  for (let i = 0; i < numAnnotations; ++i) {
    const numPoints = inputDataView.getUint32(
      inputDataOffset + numAnnotationsOffset,
      isLittleEndian
    );
    const numInstancesInAnnotation = numPoints - 1;
    inputDataOffset += pointCountBytes;
    const propertyDataStart = inputDataOffset + numPoints * pointBytes;
    instanceCounts[i] = cumulativeInstances;
    cumulativeInstances += numInstancesInAnnotation;
    for (let j = 0; j < numInstancesInAnnotation; ++j) {
      const bitCap = j === numInstancesInAnnotation - 1 ? 1 : 0;
      const instanceIndexWithBitCap = j | bitCap << 31;
      outputDataView.setUint32(
        outputDataOffset,
        instanceIndexWithBitCap,
        isLittleEndian
      );
      outputData.set(
        inputData.subarray(inputDataOffset, inputDataOffset + 2 * pointBytes),
        outputDataOffset + pointCountBytes
      );
      outputData.set(
        inputData.subarray(
          propertyDataStart,
          propertyDataStart + numPropertyBytes
        ),
        outputDataOffset + pointCountBytes + 2 * pointBytes
      );
      inputDataOffset += pointBytes;
      outputDataOffset += numBytesPerInstance;
    }
    inputDataOffset = propertyDataStart + numPropertyBytes;
  }
  return instanceCounts;
}
function calculatePolylineMemoryUsage(dv, rank, numAnnotations, numBytesPerInstance, isLittleEndian) {
  let memoryOffset = 8;
  let numInstances = 0;
  for (let i = 0; i < numAnnotations; i++) {
    const numPoints = dv.getUint32(memoryOffset, isLittleEndian);
    const numGlInstances = numPoints - 1;
    const numGeometryBytes = numPoints * rank * 4;
    const numPropertyBytes = numBytesPerInstance - 2 * rank * 4;
    memoryOffset += numGeometryBytes + numPropertyBytes;
    numInstances += numGlInstances;
  }
  return { totalBytes: memoryOffset, numInstances };
}
function extractAnnotationIdsFromBuffer(buffer, dv, numAnnotations, offset) {
  const expectedInputBytes = offset + 8 * numAnnotations;
  if (buffer.byteLength !== expectedInputBytes) {
    throw new Error(
      `Expected ${expectedInputBytes} bytes, but received: ${buffer.byteLength} bytes`
    );
  }
  const idOffset = offset;
  const ids = new Array(numAnnotations);
  for (let i = 0; i < numAnnotations; ++i) {
    ids[i] = dv.getBigUint64(
      idOffset + i * 8,
      /*littleEndian=*/
      true
    ).toString();
  }
  return ids;
}
function parseSingleAnnotation(buffer, parameters, propertySerializer, id) {
  const handler = annotationTypeHandlers[parameters.type];
  let baseNumBytes = propertySerializer.serializedBytes;
  const dv = new DataView(buffer);
  let offset = 0;
  if (parameters.type === AnnotationType.POLYLINE) {
    const numPolylinePoints = dv.getUint32(
      0,
      /*isLittleEndian=*/
      true
    ) & 2147483647;
    const numPropertyBytes = propertySerializer.serializedBytes - (2 * 4 * parameters.rank + 4);
    baseNumBytes = 4 + numPolylinePoints * 4 * parameters.rank + numPropertyBytes;
    offset = (numPolylinePoints - 2) * 4 * parameters.rank;
  }
  const numRelationships = parameters.relationships.length;
  const minNumBytes = baseNumBytes + 4 * numRelationships;
  if (buffer.byteLength < minNumBytes) {
    throw new Error(
      `Expected at least ${minNumBytes} bytes, but received: ${buffer.byteLength}`
    );
  }
  const annotation = handler.deserialize(
    dv,
    0,
    /*isLittleEndian=*/
    true,
    parameters.rank,
    id,
    0
  );
  propertySerializer.deserialize(
    dv,
    offset,
    /*annotationIndex=*/
    0,
    /*annotationCount=*/
    1,
    /*isLittleEndian=*/
    true,
    annotation.properties = new Array(parameters.properties.length)
  );
  offset = baseNumBytes;
  const relatedSegments = annotation.relatedSegments = [];
  relatedSegments.length = numRelationships;
  for (let i = 0; i < numRelationships; ++i) {
    const count = dv.getUint32(
      offset,
      /*littleEndian=*/
      true
    );
    if (buffer.byteLength < minNumBytes + count * 8) {
      throw new Error(
        `Expected at least ${minNumBytes} bytes, but received: ${buffer.byteLength}`
      );
    }
    offset += 4;
    const segments = relatedSegments[i] = new BigUint64Array(count);
    for (let j = 0; j < count; ++j) {
      segments[j] = dv.getBigUint64(
        offset,
        /*littleEndian=*/
        true
      );
      offset += 8;
    }
  }
  if (offset !== buffer.byteLength) {
    throw new Error(
      `Expected ${offset} bytes, but received: ${buffer.byteLength}`
    );
  }
  return annotation;
}
var PrecomputedAnnotationSpatialIndexSourceBackend = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(AnnotationGeometryChunkSourceBackend),
  AnnotationSpatialIndexSourceParameters2
) {
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  shardedKvStore = getShardedKvStoreIfApplicable(
    this,
    this.kvStore,
    this.parameters.sharding
  );
  async download(chunk, signal) {
    const { shardedKvStore } = this;
    const { parent } = this;
    let response;
    const { chunkGridPosition } = chunk;
    if (shardedKvStore === void 0) {
      const { kvStore } = this;
      const path = `${kvStore.path}${chunkGridPosition.join("_")}`;
      response = await kvStore.store.read(path, { signal });
    } else {
      const { upperChunkBound } = this.spec;
      const { chunkGridPosition: chunkGridPosition2 } = chunk;
      const chunkIndex = encodeZIndexCompressed(
        chunkGridPosition2,
        upperChunkBound
      );
      response = await shardedKvStore.read(chunkIndex, { signal });
    }
    if (response !== void 0) {
      chunk.data = parseAnnotations2(
        await response.response.arrayBuffer(),
        parent.parameters,
        parent.annotationPropertySerializer
      );
    }
  }
};
PrecomputedAnnotationSpatialIndexSourceBackend = __decorateClass19([
  registerSharedObject()
], PrecomputedAnnotationSpatialIndexSourceBackend);
var PrecomputedAnnotationSourceBackend = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(AnnotationSource),
  AnnotationSourceParameters2
) {
  kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.byId.url
  );
  shardedKvStore = getShardedKvStoreIfApplicable(
    this,
    this.kvStore,
    this.parameters.byId.sharding
  );
  relationshipIndexSource = this.parameters.relationships.map((x) => {
    const kvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(x.url);
    const shardedKvStore = getShardedKvStoreIfApplicable(
      this,
      kvStore,
      x.sharding
    );
    return { kvStore, shardedKvStore };
  });
  annotationPropertySerializer = new AnnotationPropertySerializer(
    this.parameters.rank,
    annotationTypeHandlers[this.parameters.type].serializedBytes(
      this.parameters.rank
    ),
    this.parameters.properties
  );
  async downloadSegmentFilteredGeometry(chunk, relationshipIndex, signal) {
    const response = await fetchByUint64(
      this.relationshipIndexSource[relationshipIndex],
      chunk.objectId,
      signal
    );
    if (response !== void 0) {
      chunk.data = parseAnnotations2(
        await response.response.arrayBuffer(),
        this.parameters,
        this.annotationPropertySerializer
      );
    }
  }
  async downloadMetadata(chunk, signal) {
    const id = BigInt(chunk.key);
    const response = await fetchByUint64(this, id, signal);
    if (response === void 0) {
      chunk.annotation = null;
    } else {
      chunk.annotation = parseSingleAnnotation(
        await response.response.arrayBuffer(),
        this.parameters,
        this.annotationPropertySerializer,
        chunk.key
      );
    }
  }
};
PrecomputedAnnotationSourceBackend = __decorateClass19([
  registerSharedObject()
], PrecomputedAnnotationSourceBackend);

// node_modules/neuroglancer/lib/datasource/graphene/backend.js
var __defProp21 = Object.defineProperty;
var __getOwnPropDesc21 = Object.getOwnPropertyDescriptor;
var __decorateClass20 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc21(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp21(target2, key, result);
  return result;
};
function downloadFragmentWithSharding(fragmentKvStore, fragmentId, signal) {
  if (fragmentId && fragmentId.charAt(0) === "~") {
    const parts = fragmentId.substring(1).split(":");
    const byteRange = { offset: Number(parts[1]), length: Number(parts[2]) };
    return readKvStore(
      fragmentKvStore.store,
      `${fragmentKvStore.path}initial/${parts[0]}`,
      { signal, byteRange, throwIfMissing: true }
    );
  }
  return readKvStore(
    fragmentKvStore.store,
    `${fragmentKvStore.path}dynamic/${fragmentId}`,
    { signal, throwIfMissing: true }
  );
}
function downloadFragment(fragmentKvStore, fragmentId, parameters, signal) {
  if (parameters.sharding) {
    return downloadFragmentWithSharding(fragmentKvStore, fragmentId, signal);
  } else {
    return readKvStore(
      fragmentKvStore.store,
      `${fragmentKvStore.path}/${fragmentId}`,
      { signal, throwIfMissing: true }
    );
  }
}
async function decodeDracoFragmentChunk(chunk, response) {
  const rawMesh = await decodeDraco(response);
  assignMeshFragmentData(chunk, rawMesh);
}
var GrapheneMeshSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(MeshSource),
  MeshSourceParameters4
) {
  manifestRequestCount = /* @__PURE__ */ new Map();
  newSegments = new Uint64Set();
  manifestHttpSource = getHttpSource(
    this.sharedKvStoreContext.kvStoreContext,
    this.parameters.manifestUrl
  );
  fragmentKvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.fragmentUrl
  );
  addNewSegment(segment) {
    const { newSegments } = this;
    newSegments.add(segment);
    const TEN_MINUTES = 1e3 * 60 * 10;
    setTimeout(() => {
      newSegments.delete(segment);
    }, TEN_MINUTES);
  }
  async download(chunk, signal) {
    const { parameters, newSegments, manifestRequestCount } = this;
    if (isBaseSegmentId(chunk.objectId, parameters.nBitsForLayerId)) {
      return decodeManifestChunk2(chunk, { fragments: [] });
    }
    const { fetchOkImpl, baseUrl } = this.manifestHttpSource;
    const manifestPath = `/manifest/${chunk.objectId}:${parameters.lod}?verify=1&prepend_seg_ids=1`;
    const response = await (await fetchOkImpl(baseUrl + manifestPath, { signal })).json();
    const chunkIdentifier = manifestPath;
    if (newSegments.has(chunk.objectId)) {
      const requestCount = (manifestRequestCount.get(chunkIdentifier) ?? 0) + 1;
      manifestRequestCount.set(chunkIdentifier, requestCount);
      setTimeout(
        () => {
          this.chunkManager.queueManager.updateChunkState(
            chunk,
            ChunkState.QUEUED
          );
        },
        2 ** requestCount * 1e3
      );
    } else {
      manifestRequestCount.delete(chunkIdentifier);
    }
    return decodeManifestChunk2(chunk, response);
  }
  async downloadFragment(chunk, signal) {
    const { response } = await downloadFragment(
      this.fragmentKvStore,
      chunk.fragmentId,
      this.parameters,
      signal
    );
    await decodeDracoFragmentChunk(
      chunk,
      new Uint8Array(await response.arrayBuffer())
    );
  }
  getFragmentKey(objectKey, fragmentId) {
    objectKey;
    return getGrapheneFragmentKey(fragmentId);
  }
};
GrapheneMeshSource = __decorateClass20([
  registerSharedObject()
], GrapheneMeshSource);
var ChunkedGraphChunk = class extends Chunk {
  chunkGridPosition;
  source = null;
  segment;
  leaves = new BigUint64Array(0);
  chunkDataSize;
  initializeVolumeChunk(key, chunkGridPosition) {
    super.initialize(key);
    this.chunkGridPosition = Float32Array.from(chunkGridPosition);
  }
  initializeChunkedGraphChunk(key, chunkGridPosition, segment) {
    this.initializeVolumeChunk(key, chunkGridPosition);
    this.chunkDataSize = null;
    this.systemMemoryBytes = 16;
    this.gpuMemoryBytes = 0;
    this.segment = segment;
  }
  downloadSucceeded() {
    this.systemMemoryBytes = 16;
    this.systemMemoryBytes += this.leaves.byteLength;
    this.queueManager.updateChunkState(this, ChunkState.SYSTEM_MEMORY_WORKER);
    if (this.priorityTier < ChunkPriorityTier.RECENT) {
      this.source.chunkManager.scheduleUpdateChunkPriorities();
    }
    super.downloadSucceeded();
  }
  freeSystemMemory() {
    this.leaves = new BigUint64Array(0);
  }
};
function decodeChunkedGraphChunk(leaves) {
  return BigUint64Array.from(leaves, parseUint64);
}
var GrapheneChunkedGraphChunkSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(ChunkSource),
  ChunkedGraphSourceParameters
) {
  spec;
  tempChunkDataSize;
  tempChunkPosition;
  httpSource = getHttpSource(
    this.sharedKvStoreContext.kvStoreContext,
    this.parameters.url
  );
  constructor(rpc2, options) {
    super(rpc2, options);
    this.spec = options.spec;
    const rank = this.spec.rank;
    this.tempChunkDataSize = new Uint32Array(rank);
    this.tempChunkPosition = new Float32Array(rank);
  }
  async download(chunk, signal) {
    const chunkPosition = this.computeChunkBounds(chunk);
    const chunkDataSize = chunk.chunkDataSize;
    const bounds = `${chunkPosition[0]}-${chunkPosition[0] + chunkDataSize[0]}_${chunkPosition[1]}-${chunkPosition[1] + chunkDataSize[1]}_${chunkPosition[2]}-${chunkPosition[2] + chunkDataSize[2]}`;
    const { fetchOkImpl, baseUrl } = this.httpSource;
    const request = fetchOkImpl(
      `${baseUrl}/${chunk.segment}/leaves?int64_as_str=1&bounds=${bounds}`,
      { signal }
    );
    await this.withErrorMessage(
      request,
      `Fetching leaves of segment ${chunk.segment} in region ${bounds}: `
    ).then((res) => res.json()).then((res) => {
      chunk.leaves = decodeChunkedGraphChunk(res.leaf_ids);
    }).catch((err) => {
      if (err instanceof Error && err.name === "AbortError") return;
      console.error(err);
    });
  }
  getChunk(chunkGridPosition, segment) {
    const key = `${vec3Key(chunkGridPosition)}-${segment}`;
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(ChunkedGraphChunk);
      chunk.initializeChunkedGraphChunk(key, chunkGridPosition, segment);
      this.addChunk(chunk);
    }
    return chunk;
  }
  computeChunkBounds(chunk) {
    return computeChunkBounds(this, chunk);
  }
  async withErrorMessage(promise, errorPrefix) {
    return promise.catch(async (e) => {
      if (e instanceof HttpError && e.response) {
        const msg = await parseGrapheneError(e);
        throw new Error(`[${e.response.status}] ${errorPrefix}${msg ?? ""}`);
      }
      throw e;
    });
  }
};
GrapheneChunkedGraphChunkSource = __decorateClass20([
  registerSharedObject()
], GrapheneChunkedGraphChunkSource);
var tempChunkPosition3 = vec3_exports.create();
var tempCenter3 = vec3_exports.create();
var tempChunkSize3 = vec3_exports.create();
var ChunkedGraphLayer = class extends withSegmentationLayerBackendState(
  withSharedVisibility(withChunkManager(RenderLayerBackend))
) {
  source;
  localPosition;
  leafRequestsActive;
  nBitsForLayerId;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = this.registerDisposer(
      rpc2.getRef(options.source)
    );
    this.localPosition = rpc2.get(options.localPosition);
    this.leafRequestsActive = rpc2.get(options.leafRequestsActive);
    this.nBitsForLayerId = rpc2.get(options.nBitsForLayerId);
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateChunkPriorities();
        this.debouncedupdateDisplayState();
      })
    );
  }
  attach(attachment) {
    const scheduleUpdateChunkPriorities = () => this.chunkManager.scheduleUpdateChunkPriorities();
    const { view } = attachment;
    attachment.registerDisposer(scheduleUpdateChunkPriorities);
    attachment.registerDisposer(
      view.projectionParameters.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.registerDisposer(
      view.visibility.changed.add(scheduleUpdateChunkPriorities)
    );
    attachment.state = {
      displayDimensionRenderInfo: view.projectionParameters.value.displayDimensionRenderInfo
    };
  }
  // Used for the sliceview to set a limit on when to
  // make get_leaves to the ChunkedGraph
  get renderRatioLimit() {
    return RENDER_RATIO_LIMIT;
  }
  updateChunkPriorities() {
    const { source, chunkManager } = this;
    chunkManager.registerLayer(this);
    for (const attachment of this.attachments.values()) {
      const { view } = attachment;
      const visibility = view.visibility.value;
      if (visibility === Number.NEGATIVE_INFINITY) {
        continue;
      }
      const attachmentState = attachment.state;
      const { transformedSource: tsource } = attachmentState;
      const projectionParameters = view.projectionParameters.value;
      if (!tsource) {
        continue;
      }
      const pixelSize = projectionParameters.pixelSize * 1.1;
      const smallestVoxelSize = tsource.effectiveVoxelSize;
      this.leafRequestsActive.value = this.renderRatioLimit >= pixelSize / Math.min(...smallestVoxelSize);
      if (!this.leafRequestsActive.value) {
        continue;
      }
      const priorityTier = getPriorityTier(visibility);
      const basePriority = getBasePriority(visibility);
      const { chunkLayout } = tsource;
      const { size, finiteRank } = chunkLayout;
      const chunkSize = tempChunkSize3;
      const localCenter = tempCenter3;
      vec3_exports.copy(chunkSize, size);
      for (let i = finiteRank; i < 3; ++i) {
        chunkSize[i] = 0;
        localCenter[i] = 0;
      }
      const { centerDataPosition } = projectionParameters;
      chunkLayout.globalToLocalSpatial(localCenter, centerDataPosition);
      forEachPlaneIntersectingVolumetricChunk(
        projectionParameters,
        this.localPosition.value,
        tsource,
        getNormalizedChunkLayout(projectionParameters, chunkLayout),
        (positionInChunks) => {
          vec3_exports.multiply(tempChunkPosition3, positionInChunks, chunkSize);
          const priority = -vec3_exports.distance(localCenter, tempChunkPosition3);
          const { curPositionInChunks } = tsource;
          forEachVisibleSegment(this, (segment, _) => {
            if (isBaseSegmentId(segment, this.nBitsForLayerId.value)) return;
            const chunk = source.getChunk(curPositionInChunks, segment);
            chunkManager.requestChunk(
              chunk,
              priorityTier,
              basePriority + priority,
              ChunkState.SYSTEM_MEMORY_WORKER
            );
            ++this.numVisibleChunksNeeded;
            if (chunk.state === ChunkState.GPU_MEMORY) {
              ++this.numVisibleChunksAvailable;
            }
          });
        }
      );
    }
  }
  forEachSelectedRootWithLeaves(callback) {
    const { source } = this;
    for (const chunk of source.chunks.values()) {
      if (chunk.state === ChunkState.SYSTEM_MEMORY_WORKER && chunk.priorityTier < ChunkPriorityTier.RECENT) {
        if (this.visibleSegments.has(chunk.segment) && chunk.leaves.length) {
          callback(chunk.segment, chunk.leaves);
        }
      }
    }
  }
  debouncedupdateDisplayState = debounce_default(() => {
    this.updateDisplayState();
  }, 100);
  updateDisplayState() {
    const visibleLeaves = /* @__PURE__ */ new Map();
    const capacities = /* @__PURE__ */ new Map();
    this.forEachSelectedRootWithLeaves((rootObject, leaves) => {
      capacities.set(
        rootObject,
        (capacities.get(rootObject) ?? 0) + leaves.length
      );
    });
    this.forEachSelectedRootWithLeaves((rootObject, leaves) => {
      if (!visibleLeaves.has(rootObject)) {
        visibleLeaves.set(rootObject, new Uint64Set());
        visibleLeaves.get(rootObject).reserve(capacities.get(rootObject));
        visibleLeaves.get(rootObject).add(rootObject);
      }
      visibleLeaves.get(rootObject).add(leaves);
    });
    for (const [root2, leaves] of visibleLeaves) {
      const filteredLeaves = [...leaves].filter(
        (x) => !this.segmentEquivalences.has(x)
      );
      for (const leaf of filteredLeaves) {
        this.segmentEquivalences.link(root2, leaf);
      }
    }
  }
};
ChunkedGraphLayer = __decorateClass20([
  registerSharedObject(CHUNKED_GRAPH_LAYER_RPC_ID)
], ChunkedGraphLayer);
registerRPC(CHUNKED_GRAPH_RENDER_LAYER_UPDATE_SOURCES_RPC_ID, function(x) {
  const view = this.get(x.view);
  const layer = this.get(x.layer);
  const attachment = layer.attachments.get(
    view
  );
  attachment.state.transformedSource = deserializeTransformedSources(this, x.sources, layer)[0][0];
  attachment.state.displayDimensionRenderInfo = x.displayDimensionRenderInfo;
  layer.chunkManager.scheduleUpdateChunkPriorities();
});
registerRPC(GRAPHENE_MESH_NEW_SEGMENT_RPC_ID, function(x) {
  const obj = this.get(x.rpcId);
  obj.addNewSegment(x.segment);
});

// node_modules/neuroglancer/lib/datasource/n5/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/decode_blosc_request.js
init_legacy_browser();
var decodeBlosc = asyncComputation(
  "decodeBlosc"
);

// node_modules/neuroglancer/lib/async_computation/decode_zstd_request.js
init_legacy_browser();
var decodeZstd = asyncComputation(
  "decodeZstd"
);

// node_modules/neuroglancer/lib/datasource/n5/base.js
init_legacy_browser();
var VolumeChunkEncoding4 = /* @__PURE__ */ ((VolumeChunkEncoding22) => {
  VolumeChunkEncoding22[VolumeChunkEncoding22["RAW"] = 0] = "RAW";
  VolumeChunkEncoding22[VolumeChunkEncoding22["ZLIB"] = 1] = "ZLIB";
  VolumeChunkEncoding22[VolumeChunkEncoding22["GZIP"] = 2] = "GZIP";
  VolumeChunkEncoding22[VolumeChunkEncoding22["BLOSC"] = 3] = "BLOSC";
  VolumeChunkEncoding22[VolumeChunkEncoding22["ZSTD"] = 4] = "ZSTD";
  return VolumeChunkEncoding22;
})(VolumeChunkEncoding4 || {});
var VolumeChunkSourceParameters4 = class {
  url;
  encoding;
  static RPC_ID = "n5/VolumeChunkSource";
};

// node_modules/neuroglancer/lib/datasource/n5/backend.js
var __defProp22 = Object.defineProperty;
var __getOwnPropDesc22 = Object.getOwnPropertyDescriptor;
var __decorateClass21 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc22(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp22(target2, key, result);
  return result;
};
async function decodeChunk(chunk, signal, response, encoding) {
  const dv = new DataView(response);
  const mode = dv.getUint16(
    0,
    /*littleEndian=*/
    false
  );
  if (mode !== 0) {
    throw new Error(`Unsupported mode: ${mode}.`);
  }
  const numDimensions = dv.getUint16(
    2,
    /*littleEndian=*/
    false
  );
  if (numDimensions !== chunk.source.spec.rank) {
    throw new Error("Number of dimensions must be 3.");
  }
  let offset = 4;
  const shape = new Uint32Array(numDimensions);
  for (let i = 0; i < numDimensions; ++i) {
    shape[i] = dv.getUint32(
      offset,
      /*littleEndian=*/
      false
    );
    offset += 4;
  }
  chunk.chunkDataSize = shape;
  let buffer = new Uint8Array(response, offset);
  switch (encoding) {
    case VolumeChunkEncoding4.ZLIB:
      buffer = new Uint8Array(await decodeGzip(buffer, "deflate"));
      break;
    case VolumeChunkEncoding4.GZIP:
      buffer = new Uint8Array(await decodeGzip(buffer, "gzip"));
      break;
    case VolumeChunkEncoding4.BLOSC:
      buffer = await requestAsyncComputation(
        decodeBlosc,
        signal,
        [buffer.buffer],
        buffer
      );
      break;
    case VolumeChunkEncoding4.ZSTD:
      buffer = await requestAsyncComputation(
        decodeZstd,
        signal,
        [buffer.buffer],
        buffer
      );
      break;
  }
  await decodeRawChunk(
    chunk,
    signal,
    buffer.buffer,
    Endianness.BIG,
    buffer.byteOffset,
    buffer.byteLength
  );
}
var PrecomputedVolumeChunkSource2 = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(VolumeChunkSource),
  VolumeChunkSourceParameters4
) {
  chunkKvStore = this.sharedKvStoreContext.kvStoreContext.getKvStore(
    this.parameters.url
  );
  async download(chunk, signal) {
    const { parameters, chunkKvStore } = this;
    const { chunkGridPosition } = chunk;
    let path = chunkKvStore.path;
    const rank = this.spec.rank;
    for (let i = 0; i < rank; ++i) {
      if (i !== 0) {
        path += "/";
      }
      path += `${chunkGridPosition[i]}`;
    }
    const response = await chunkKvStore.store.read(path, {
      signal
    });
    if (response === void 0) return;
    await decodeChunk(
      chunk,
      signal,
      await response.response.arrayBuffer(),
      parameters.encoding
    );
  }
};
PrecomputedVolumeChunkSource2 = __decorateClass21([
  registerSharedObject()
], PrecomputedVolumeChunkSource2);

// node_modules/neuroglancer/lib/datasource/nifti/backend.js
init_legacy_browser();
var import_nifti_reader_js = __toESM(require_nifti(), 1);

// node_modules/neuroglancer/lib/datasource/nifti/base.js
init_legacy_browser();
var GET_NIFTI_VOLUME_INFO_RPC_ID = "nifti/getNiftiVolumeInfo";
var VolumeSourceParameters2 = class {
  url;
  static RPC_ID = "nifti/VolumeChunkSource";
};

// node_modules/neuroglancer/lib/sliceview/volume/base.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/nifti/backend.js
var __defProp23 = Object.defineProperty;
var __getOwnPropDesc23 = Object.getOwnPropertyDescriptor;
var __decorateClass22 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc23(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp23(target2, key, result);
  return result;
};
var NiftiFileData = class {
  uncompressedData;
  header;
};
async function decodeNiftiFile(readResponse, options) {
  let buffer = await readResponse.response.arrayBuffer();
  if ((0, import_nifti_reader_js.isCompressed)(buffer)) {
    buffer = await decodeGzip(buffer, "gzip", options.signal);
  }
  const data = new NiftiFileData();
  data.uncompressedData = buffer;
  const header = (0, import_nifti_reader_js.readHeader)(buffer);
  if (header === null) {
    throw new Error("Failed to parse NIFTI header.");
  }
  data.header = header;
  return { data, size: buffer.byteLength };
}
function getNiftiFileData(sharedKvStoreContextCounterpart, url, options) {
  return getCachedDecodedUrl(
    sharedKvStoreContextCounterpart,
    url,
    decodeNiftiFile,
    options
  );
}
async function getNiftiHeaderInfo(sharedKvStoreContext, url, options) {
  const data = await getNiftiFileData(sharedKvStoreContext, url, options);
  return data.header;
}
function convertAffine(affine) {
  return mat4_exports.fromValues(
    affine[0][0],
    affine[1][0],
    affine[2][0],
    affine[3][0],
    affine[0][1],
    affine[1][1],
    affine[2][1],
    affine[3][1],
    affine[0][2],
    affine[1][2],
    affine[2][2],
    affine[3][2],
    affine[0][3],
    affine[1][3],
    affine[2][3],
    affine[3][3]
  );
}
var NiftiDataType = /* @__PURE__ */ ((NiftiDataType2) => {
  NiftiDataType2[NiftiDataType2["NONE"] = 0] = "NONE";
  NiftiDataType2[NiftiDataType2["BINARY"] = 1] = "BINARY";
  NiftiDataType2[NiftiDataType2["UINT8"] = 2] = "UINT8";
  NiftiDataType2[NiftiDataType2["INT16"] = 4] = "INT16";
  NiftiDataType2[NiftiDataType2["INT32"] = 8] = "INT32";
  NiftiDataType2[NiftiDataType2["FLOAT32"] = 16] = "FLOAT32";
  NiftiDataType2[NiftiDataType2["COMPLEX64"] = 32] = "COMPLEX64";
  NiftiDataType2[NiftiDataType2["FLOAT64"] = 64] = "FLOAT64";
  NiftiDataType2[NiftiDataType2["RGB24"] = 128] = "RGB24";
  NiftiDataType2[NiftiDataType2["INT8"] = 256] = "INT8";
  NiftiDataType2[NiftiDataType2["UINT16"] = 512] = "UINT16";
  NiftiDataType2[NiftiDataType2["UINT32"] = 768] = "UINT32";
  NiftiDataType2[NiftiDataType2["INT64"] = 1024] = "INT64";
  NiftiDataType2[NiftiDataType2["UINT64"] = 1280] = "UINT64";
  NiftiDataType2[NiftiDataType2["FLOAT128"] = 1536] = "FLOAT128";
  NiftiDataType2[NiftiDataType2["COMPLEX128"] = 1792] = "COMPLEX128";
  NiftiDataType2[NiftiDataType2["COMPLEX256"] = 2048] = "COMPLEX256";
  return NiftiDataType2;
})(NiftiDataType || {});
var DATA_TYPE_CONVERSIONS = /* @__PURE__ */ new Map([
  [256, { dataType: DataType.INT8 }],
  [2, { dataType: DataType.UINT8 }],
  [4, { dataType: DataType.INT16 }],
  [512, { dataType: DataType.UINT16 }],
  [8, { dataType: DataType.INT32 }],
  [768, { dataType: DataType.UINT32 }],
  [1024, { dataType: DataType.UINT64 }],
  [1280, { dataType: DataType.UINT64 }],
  [16, { dataType: DataType.FLOAT32 }]
]);
registerPromiseRPC(
  GET_NIFTI_VOLUME_INFO_RPC_ID,
  async function(x, progressOptions) {
    const sharedKvStoreContext = this.get(
      x.sharedKvStoreContext
    );
    const header = await getNiftiHeaderInfo(
      sharedKvStoreContext,
      x.url,
      progressOptions
    );
    const dataTypeInfo = DATA_TYPE_CONVERSIONS.get(header.datatypeCode);
    if (dataTypeInfo === void 0) {
      throw new Error(
        `Unsupported data type: ${NiftiDataType[header.datatypeCode] || header.datatypeCode}.`
      );
    }
    let spatialInvScale = 1;
    let spatialUnit = "";
    switch (header.xyzt_units & import_nifti_reader_js.NIFTI1.SPATIAL_UNITS_MASK) {
      case import_nifti_reader_js.NIFTI1.UNITS_METER:
        spatialInvScale = 1;
        spatialUnit = "m";
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_MM:
        spatialInvScale = 1e3;
        spatialUnit = "m";
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_MICRON:
        spatialInvScale = 1e6;
        spatialUnit = "m";
        break;
    }
    let timeUnit = "";
    let timeInvScale = 1;
    switch (header.xyzt_units & import_nifti_reader_js.NIFTI1.TEMPORAL_UNITS_MASK) {
      case import_nifti_reader_js.NIFTI1.UNITS_SEC:
        timeUnit = "s";
        timeInvScale = 1;
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_MSEC:
        timeUnit = "s";
        timeInvScale = 1e3;
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_USEC:
        timeUnit = "s";
        timeInvScale = 1e6;
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_HZ:
        timeUnit = "Hz";
        timeInvScale = 1;
        break;
      case import_nifti_reader_js.NIFTI1.UNITS_RADS:
        timeUnit = "rad/s";
        timeInvScale = 1;
        break;
    }
    let units = [
      spatialUnit,
      spatialUnit,
      spatialUnit,
      timeUnit,
      "",
      "",
      ""
    ];
    let sourceScales = Float64Array.of(
      header.pixDims[1] / spatialInvScale,
      header.pixDims[2] / spatialInvScale,
      header.pixDims[3] / spatialInvScale,
      header.pixDims[4] / timeInvScale,
      header.pixDims[5],
      header.pixDims[6],
      header.pixDims[7]
    );
    let viewScales = Float64Array.of(
      1 / spatialInvScale,
      1 / spatialInvScale,
      1 / spatialInvScale,
      1 / timeInvScale,
      1,
      1,
      1
    );
    let sourceNames = ["i", "j", "k", "m", "c^", "c1^", "c2^"];
    let viewNames = ["x", "y", "z", "t", "c^", "c1^", "c2^"];
    const rank = header.dims[0];
    sourceNames = sourceNames.slice(0, rank);
    viewNames = viewNames.slice(0, rank);
    units = units.slice(0, rank);
    sourceScales = sourceScales.slice(0, rank);
    viewScales = viewScales.slice(0, rank);
    const { quatern_b, quatern_c, quatern_d } = header;
    const quatern_a = Math.sqrt(
      1 - quatern_b * quatern_b - quatern_c * quatern_c - quatern_d * quatern_d
    );
    const qfac = header.pixDims[0] === -1 ? -1 : 1;
    const qoffset = vec3_exports.fromValues(
      header.qoffset_x,
      header.qoffset_y,
      header.qoffset_z
    );
    const method3Transform = convertAffine(header.affine);
    method3Transform;
    const method2Transform = translationRotationScaleZReflectionToMat4(
      mat4_exports.create(),
      qoffset,
      quat_exports.fromValues(quatern_b, quatern_c, quatern_d, quatern_a),
      kOneVec,
      qfac
    );
    const transform2 = createIdentity(Float64Array, rank + 1);
    const copyRank = Math.min(3, rank);
    for (let row = 0; row < copyRank; ++row) {
      for (let col = 0; col < copyRank; ++col) {
        transform2[col * (rank + 1) + row] = method2Transform[col * 4 + row];
      }
      transform2[rank * (rank + 1) + row] = method2Transform[12 + row];
    }
    const info = {
      rank,
      sourceNames,
      viewNames,
      units,
      sourceScales,
      viewScales,
      description: header.description,
      transform: transform2,
      dataType: dataTypeInfo.dataType,
      volumeSize: Uint32Array.from(header.dims.slice(1, 1 + rank))
    };
    return { value: info };
  }
);
var NiftiVolumeChunkSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(VolumeChunkSource),
  VolumeSourceParameters2
) {
  async download(chunk, signal) {
    chunk.chunkDataSize = this.spec.chunkDataSize;
    const data = await getNiftiFileData(
      this.sharedKvStoreContext,
      this.parameters.url,
      { signal }
    );
    const imageBuffer = (0, import_nifti_reader_js.readImage)(data.header, data.uncompressedData);
    await decodeRawChunk(
      chunk,
      signal,
      imageBuffer,
      data.header.littleEndian ? Endianness.LITTLE : Endianness.BIG
    );
  }
};
NiftiVolumeChunkSource = __decorateClass22([
  registerSharedObject()
], NiftiVolumeChunkSource);

// node_modules/neuroglancer/lib/datasource/obj/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/obj_mesh_request.js
init_legacy_browser();
var parseOBJFromArrayBuffer = asyncComputation("parseOBJFromArrayBuffer");

// node_modules/neuroglancer/lib/single_mesh/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/single_mesh/base.js
init_legacy_browser();
var SINGLE_MESH_LAYER_RPC_ID = "single_mesh/SingleMeshLayer";
var GET_SINGLE_MESH_INFO_RPC_ID = "single_mesh/getSingleMeshInfo";
var SINGLE_MESH_CHUNK_KEY = "";
var SingleMeshSourceParameters = class {
  meshSourceUrl;
};
var SingleMeshSourceParametersWithInfo = class extends SingleMeshSourceParameters {
  info;
  static RPC_ID = "single_mesh/SingleMeshSource";
};

// node_modules/neuroglancer/lib/single_mesh/backend.js
var __defProp24 = Object.defineProperty;
var __getOwnPropDesc24 = Object.getOwnPropertyDescriptor;
var __decorateClass23 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc24(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp24(target2, key, result);
  return result;
};
var SINGLE_MESH_CHUNK_PRIORITY = 50;
var SingleMeshChunk = class extends Chunk {
  data = null;
  freeSystemMemory() {
    this.data = null;
  }
  serialize(msg, transfers) {
    super.serialize(msg, transfers);
    const { vertexPositions, indices, vertexNormals, vertexAttributes } = this.data;
    msg.vertexPositions = vertexPositions;
    msg.indices = indices;
    msg.vertexNormals = vertexNormals;
    msg.vertexAttributes = vertexAttributes;
    const transferSet = /* @__PURE__ */ new Set();
    transferSet.add(vertexPositions.buffer);
    transferSet.add(indices.buffer);
    transferSet.add(vertexNormals.buffer);
    for (const data of vertexAttributes) {
      transferSet.add(data.buffer);
    }
    transfers.push(...transferSet);
    this.data = null;
  }
  downloadSucceeded() {
    const { vertexPositions, indices, vertexNormals, vertexAttributes } = this.data;
    let totalBytes = this.gpuMemoryBytes = vertexPositions.byteLength + indices.byteLength + vertexNormals.byteLength;
    for (const data of vertexAttributes) {
      totalBytes += data.byteLength;
    }
    this.systemMemoryBytes = this.gpuMemoryBytes = totalBytes;
    super.downloadSucceeded();
  }
};
var singleMeshFactories = /* @__PURE__ */ new Map();
function registerSingleMeshFactory(name, factory) {
  singleMeshFactories.set(name, factory);
}
var protocolPattern = /^(?:([a-zA-Z-+_]+):\/\/)?(.*)$/;
function getDataSource(factories, url) {
  const m = url.match(protocolPattern);
  if (m === null || m[1] === void 0) {
    throw new Error(
      `Data source URL must have the form "<protocol>://<path>".`
    );
  }
  const dataSource = m[1];
  const factory = factories.get(dataSource);
  if (factory === void 0) {
    throw new Error(`Unsupported data source: ${JSON.stringify(dataSource)}.`);
  }
  return [factory, m[2], dataSource];
}
function getMesh(sharedKvStoreContext, url, options) {
  const [factory, path] = getDataSource(singleMeshFactories, url);
  return factory.getMesh(sharedKvStoreContext, path, options);
}
function getCombinedMesh(sharedKvStoreContext, parameters, options) {
  return getMesh(sharedKvStoreContext, parameters.meshSourceUrl, options);
}
var SingleMeshSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(ChunkSource),
  SingleMeshSourceParametersWithInfo
) {
  getChunk() {
    const key = SINGLE_MESH_CHUNK_KEY;
    let chunk = this.chunks.get(key);
    if (chunk === void 0) {
      chunk = this.getNewChunk_(SingleMeshChunk);
      chunk.initialize(key);
      this.addChunk(chunk);
    }
    return chunk;
  }
  async download(chunk, signal) {
    const data = await getCombinedMesh(
      this.sharedKvStoreContext,
      this.parameters,
      {
        signal
      }
    );
    if (stableStringify(data.info) !== stableStringify(this.parameters.info)) {
      throw new Error("Mesh info has changed.");
    }
    if (data.vertexNormals === void 0) {
      data.vertexNormals = computeVertexNormals(
        data.vertexPositions,
        data.indices
      );
    }
    chunk.data = data;
  }
};
SingleMeshSource = __decorateClass23([
  registerSharedObject()
], SingleMeshSource);
var SingleMeshLayerBase = withSharedVisibility(
  withChunkManager(SharedObjectCounterpart)
);
var SingleMeshLayer = class extends SingleMeshLayerBase {
  source;
  constructor(rpc2, options) {
    super(rpc2, options);
    this.source = this.registerDisposer(
      rpc2.getRef(options.source)
    );
    this.registerDisposer(
      this.chunkManager.recomputeChunkPriorities.add(() => {
        this.updateChunkPriorities();
      })
    );
  }
  updateChunkPriorities() {
    const visibility = this.visibility.value;
    if (visibility === Number.NEGATIVE_INFINITY) {
      return;
    }
    const priorityTier = getPriorityTier(visibility);
    const basePriority = getBasePriority(visibility);
    const { source, chunkManager } = this;
    const chunk = source.getChunk();
    chunkManager.requestChunk(
      chunk,
      priorityTier,
      basePriority + SINGLE_MESH_CHUNK_PRIORITY
    );
  }
};
SingleMeshLayer = __decorateClass23([
  registerSharedObject(SINGLE_MESH_LAYER_RPC_ID)
], SingleMeshLayer);
registerPromiseRPC(
  GET_SINGLE_MESH_INFO_RPC_ID,
  async function(x, progressOptions) {
    const sharedKvStoreContext = this.get(
      x.sharedKvStoreContext
    );
    const parameters = x.parameters;
    const mesh = await getCombinedMesh(
      sharedKvStoreContext,
      parameters,
      progressOptions
    );
    return { value: mesh.info };
  }
);

// node_modules/neuroglancer/lib/datasource/obj/backend.js
async function parse(readResponse, progressOptions) {
  const buffer = await readResponse.response.arrayBuffer();
  return requestAsyncComputation(
    parseOBJFromArrayBuffer,
    progressOptions.signal,
    [buffer],
    buffer
  );
}
registerSingleMeshFactory("obj", {
  description: "OBJ",
  getMesh: (sharedKvStoreContext, url, options) => getCachedDecodedUrl(sharedKvStoreContext, url, parse, options)
});

// node_modules/neuroglancer/lib/util/false.js
init_legacy_browser();
var false_default = false;

// node_modules/neuroglancer/lib/datasource/render/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/render/base.js
init_legacy_browser();
var RenderBaseSourceParameters = class {
  baseUrl;
  owner;
  project;
  stack;
  channel;
};
var RenderSourceParameters = class extends RenderBaseSourceParameters {
  renderArgs;
};
var TileChunkSourceParameters = class extends RenderSourceParameters {
  dims;
  level;
  encoding;
  static RPC_ID = "render/TileChunkSource";
};

// node_modules/neuroglancer/lib/datasource/render/backend.js
var __defProp25 = Object.defineProperty;
var __getOwnPropDesc25 = Object.getOwnPropertyDescriptor;
var __decorateClass24 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc25(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp25(target2, key, result);
  return result;
};
var chunkDecoders3 = /* @__PURE__ */ new Map();
chunkDecoders3.set(
  "jpg",
  async (chunk, signal, response) => {
    const chunkDataSize = chunk.chunkDataSize;
    const { uint8Array: decoded } = await requestAsyncComputation(
      decodeJpeg,
      signal,
      [response],
      new Uint8Array(response),
      void 0,
      void 0,
      chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
      3,
      true
    );
    await postProcessRawData(chunk, signal, decoded);
  }
);
chunkDecoders3.set(
  "png",
  async (chunk, signal, response) => {
    const chunkDataSize = chunk.chunkDataSize;
    const { uint8Array: decoded } = await requestAsyncComputation(
      decodePng,
      signal,
      [response],
      new Uint8Array(response),
      chunkDataSize[0],
      chunkDataSize[1],
      chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
      4,
      1,
      false
    );
    await postProcessRawData(chunk, signal, decoded);
  }
);
chunkDecoders3.set(
  "png16",
  async (chunk, signal, response) => {
    const chunkDataSize = chunk.chunkDataSize;
    const { uint8Array: decoded } = await requestAsyncComputation(
      decodePng,
      signal,
      [response],
      new Uint8Array(response),
      chunkDataSize[0],
      chunkDataSize[1],
      chunkDataSize[0] * chunkDataSize[1] * chunkDataSize[2],
      1,
      2,
      false
    );
    await postProcessRawData(chunk, signal, decoded);
  }
);
chunkDecoders3.set("raw16", (chunk, signal, response) => {
  return decodeRawChunk(chunk, signal, response, Endianness.BIG);
});
var TileChunkSource = class extends WithParameters(
  VolumeChunkSource,
  TileChunkSourceParameters
) {
  chunkDecoder = chunkDecoders3.get(this.parameters.encoding);
  queryString = (() => {
    const { parameters } = this;
    const query_params = new URLSearchParams();
    if (parameters.channel !== void 0) {
      query_params.append("channel", parameters.channel);
    }
    for (const [key, value] of Object.entries(parameters.renderArgs)) {
      query_params.append(key, value);
    }
    return query_params.toString();
  })();
  async download(chunk, signal) {
    const { parameters } = this;
    const { chunkGridPosition } = chunk;
    const scale6 = 1 / 2 ** parameters.level;
    chunk.chunkDataSize = this.spec.chunkDataSize;
    const xTileSize = chunk.chunkDataSize[0] * 2 ** parameters.level;
    const yTileSize = chunk.chunkDataSize[1] * 2 ** parameters.level;
    const chunkPosition = vec3_exports.create();
    chunkPosition[0] = chunkGridPosition[0] * xTileSize;
    chunkPosition[1] = chunkGridPosition[1] * yTileSize;
    chunkPosition[2] = chunkGridPosition[2];
    let imageMethod;
    if (parameters.encoding === "raw16") {
      imageMethod = "raw16-image";
    } else if (parameters.encoding === "png16") {
      imageMethod = "png16-image";
    } else if (parameters.encoding === "png") {
      imageMethod = "png-image";
    } else {
      imageMethod = "jpeg-image";
    }
    const path = `/render-ws/v1/owner/${parameters.owner}/project/${parameters.project}/stack/${parameters.stack}/z/${chunkPosition[2]}/box/${chunkPosition[0]},${chunkPosition[1]},${xTileSize},${yTileSize},${scale6}/${imageMethod}`;
    const response = await fetchOk(
      `${parameters.baseUrl}${path}?${this.queryString}`,
      { signal }
    );
    await this.chunkDecoder(chunk, signal, await response.arrayBuffer());
  }
};
TileChunkSource = __decorateClass24([
  registerSharedObject()
], TileChunkSource);

// node_modules/neuroglancer/lib/datasource/vtk/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/async_computation/vtk_mesh_request.js
init_legacy_browser();
var parseVTKFromArrayBuffer = asyncComputation("parseVTKFromArrayBuffer");

// node_modules/neuroglancer/lib/datasource/vtk/backend.js
async function parse2(readResponse, progressOptions) {
  const buffer = await readResponse.response.arrayBuffer();
  return requestAsyncComputation(
    parseVTKFromArrayBuffer,
    progressOptions.signal,
    [buffer],
    buffer
  );
}
registerSingleMeshFactory("vtk", {
  description: "VTK",
  getMesh: async (sharedKvStoreContext, url, options) => {
    const mesh = await getCachedDecodedUrl(
      sharedKvStoreContext,
      url,
      parse2,
      options
    );
    const result = {
      info: {
        numTriangles: mesh.numTriangles,
        numVertices: mesh.numVertices,
        vertexAttributes: []
      },
      indices: mesh.indices,
      vertexPositions: mesh.vertexPositions,
      vertexAttributes: []
    };
    for (const attribute of mesh.vertexAttributes) {
      result.info.vertexAttributes.push({
        name: attribute.name,
        dataType: DataType.FLOAT32,
        numComponents: attribute.numComponents
      });
      result.vertexAttributes.push(attribute.data);
    }
    return result;
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/codec/blosc/decode.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/codec/decode.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/codec/index.js
init_legacy_browser();
var CodecKind = /* @__PURE__ */ ((CodecKind2) => {
  CodecKind2[CodecKind2["arrayToArray"] = 0] = "arrayToArray";
  CodecKind2[CodecKind2["arrayToBytes"] = 1] = "arrayToBytes";
  CodecKind2[CodecKind2["bytesToBytes"] = 2] = "bytesToBytes";
  return CodecKind2;
})(CodecKind || {});

// node_modules/neuroglancer/lib/datasource/zarr/codec/decode.js
var codecRegistry = {
  [CodecKind.arrayToArray]: /* @__PURE__ */ new Map(),
  [CodecKind.arrayToBytes]: /* @__PURE__ */ new Map(),
  [CodecKind.bytesToBytes]: /* @__PURE__ */ new Map(),
  sharding: /* @__PURE__ */ new Map()
};
function registerCodec(codec) {
  if (codec.kind === CodecKind.arrayToBytes && "getShardedKvStore" in codec) {
    codecRegistry.sharding.set(codec.name, codec);
  } else {
    codecRegistry[codec.kind].set(codec.name, codec);
  }
}
async function decodeArray(codecs, encoded, signal) {
  const bytesToBytes = codecs[CodecKind.bytesToBytes];
  for (let i = bytesToBytes.length; i--; ) {
    const codec = bytesToBytes[i];
    const impl = codecRegistry[CodecKind.bytesToBytes].get(codec.name);
    if (impl === void 0) {
      throw new Error(`Unsupported codec: ${JSON.stringify(codec.name)}`);
    }
    encoded = await impl.decode(codec.configuration, encoded, signal);
  }
  let decoded;
  {
    const codec = codecs[CodecKind.arrayToBytes];
    const impl = codecRegistry[CodecKind.arrayToBytes].get(codec.name);
    if (impl === void 0) {
      throw new Error(`Unsupported codec: ${JSON.stringify(codec.name)}`);
    }
    decoded = await impl.decode(
      codec.configuration,
      codecs.arrayInfo[codecs.arrayInfo.length - 1],
      encoded,
      signal
    );
  }
  const arrayToArray = codecs[CodecKind.arrayToArray];
  for (let i = arrayToArray.length; i--; ) {
    const codec = arrayToArray[i];
    const impl = codecRegistry[CodecKind.arrayToArray].get(codec.name);
    if (impl === void 0) {
      throw new Error(`Unsupported codec: ${JSON.stringify(codec.name)}`);
    }
    decoded = await impl.decode(
      codec.configuration,
      codecs.arrayInfo[i],
      decoded,
      signal
    );
  }
  return decoded;
}
function applySharding(chunkManager, codecs, baseKvStore) {
  let kvStore = baseKvStore.store;
  let curCodecs = codecs;
  while (true) {
    const { shardingInfo } = curCodecs;
    if (shardingInfo === void 0) break;
    const codec = curCodecs[CodecKind.arrayToBytes];
    const impl = codecRegistry.sharding.get(codec.name);
    if (impl === void 0) {
      throw new Error(`Unsupported codec: ${JSON.stringify(codec.name)}`);
    }
    kvStore = impl.getShardedKvStore(
      codec.configuration,
      chunkManager,
      kvStore
    );
    curCodecs = shardingInfo.subChunkCodecs;
  }
  const decodeCodecs = curCodecs;
  const pathPrefix = baseKvStore.path;
  function getChunkKey(chunkGridPosition, baseKey) {
    let key = pathPrefix + baseKey;
    const rank = chunkGridPosition.length;
    let curCodecs2 = codecs;
    while (curCodecs2.shardingInfo !== void 0) {
      const layoutInfo = codecs.layoutInfo[codecs.layoutInfo.length - 1];
      const { physicalToLogicalDimension, readChunkShape } = layoutInfo;
      const { subChunkShape, subChunkGridShape, subChunkCodecs } = curCodecs2.shardingInfo;
      const subChunk = new Array(rank);
      for (let fOrderPhysicalDim = 0; fOrderPhysicalDim < rank; ++fOrderPhysicalDim) {
        const subChunkDim = physicalToLogicalDimension[rank - 1 - fOrderPhysicalDim];
        subChunk[subChunkDim] = Math.floor(
          chunkGridPosition[fOrderPhysicalDim] * readChunkShape[subChunkDim] / subChunkShape[subChunkDim]
        ) % subChunkGridShape[subChunkDim];
      }
      key = { base: key, subChunk };
      curCodecs2 = subChunkCodecs;
    }
    return key;
  }
  return { kvStore, getChunkKey, decodeCodecs };
}

// node_modules/neuroglancer/lib/datasource/zarr/codec/blosc/decode.js
registerCodec({
  name: "blosc",
  kind: CodecKind.bytesToBytes,
  decode(configuration, encoded, signal) {
    configuration;
    return requestAsyncComputation(
      decodeBlosc,
      signal,
      [encoded.buffer],
      encoded
    );
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/codec/zstd/decode.js
init_legacy_browser();
registerCodec({
  name: "zstd",
  kind: CodecKind.bytesToBytes,
  decode(configuration, encoded, signal) {
    configuration;
    return requestAsyncComputation(
      decodeZstd,
      signal,
      [encoded.buffer],
      encoded
    );
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/codec/bytes/decode.js
init_legacy_browser();
registerCodec({
  name: "bytes",
  kind: CodecKind.arrayToBytes,
  async decode(configuration, decodedArrayInfo, encoded, signal) {
    signal;
    const { dataType, chunkShape } = decodedArrayInfo;
    const numElements = chunkShape.reduce((a, b) => a * b, 1);
    const bytesPerElement = DATA_TYPE_BYTES[dataType];
    const expectedBytes = numElements * bytesPerElement;
    if (encoded.byteLength !== expectedBytes) {
      throw new Error(
        `Raw-format chunk is ${encoded.byteLength} bytes, but ${numElements} * ${bytesPerElement} = ${expectedBytes} bytes are expected.`
      );
    }
    const data = makeDataTypeArrayView(
      dataType,
      encoded.buffer,
      encoded.byteOffset,
      encoded.byteLength
    );
    convertEndian(data, configuration.endian, bytesPerElement);
    return data;
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/codec/crc32c/decode.js
init_legacy_browser();
var checksumSize = 4;
registerCodec({
  name: "crc32c",
  kind: CodecKind.bytesToBytes,
  async decode(configuration, encoded, signal) {
    configuration;
    signal;
    if (encoded.length < checksumSize) {
      throw new Error(
        `Expected buffer of size at least ${checksumSize} bytes but received: ${encoded.length} bytes`
      );
    }
    return encoded.subarray(0, encoded.length - checksumSize);
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/base.js
init_legacy_browser();
var VolumeChunkSourceParameters5 = class {
  url;
  metadata;
  static RPC_ID = "zarr/VolumeChunkSource";
};

// node_modules/neuroglancer/lib/datasource/zarr/codec/gzip/decode.js
init_legacy_browser();
for (const [name, compressionFormat] of [
  ["gzip", "gzip"],
  ["zlib", "deflate"]
]) {
  registerCodec({
    name,
    kind: CodecKind.bytesToBytes,
    async decode(configuration, encoded, signal) {
      configuration;
      return new Uint8Array(
        await decodeGzip(encoded, compressionFormat, signal)
      );
    }
  });
}

// node_modules/neuroglancer/lib/datasource/zarr/codec/sharding_indexed/decode.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/codec/sharding_indexed/resolve.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/codec/resolve.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/metadata/parse_util.js
init_legacy_browser();
function parseNameAndConfiguration(obj, parseName, parseConfiguration) {
  verifyObject(obj);
  const name = verifyObjectProperty(
    obj,
    "name",
    (value) => parseName(verifyString(value))
  );
  const configuration = verifyObjectProperty(obj, "configuration", (value) => {
    if (value === void 0) {
      value = {};
    } else {
      verifyObject(value);
    }
    return parseConfiguration(value, name);
  });
  return { name, configuration };
}

// node_modules/neuroglancer/lib/datasource/zarr/codec/resolve.js
function getCodecResolver(obj) {
  const { name: resolver, configuration } = parseNameAndConfiguration(
    obj,
    (name) => {
      const resolver2 = codecRegistry2.get(name);
      if (resolver2 === void 0) {
        throw new Error(`Unknown codec: ${JSON.stringify(name)}`);
      }
      return resolver2;
    },
    (configuration2) => configuration2
  );
  return { resolver, configuration };
}
var codecRegistry2 = /* @__PURE__ */ new Map();
function registerCodec2(resolver) {
  codecRegistry2.set(resolver.name, resolver);
}
function parseCodecChainSpec(obj, decodedArrayInfo) {
  const arrayToArray = [];
  const arrayInfo = [];
  const layoutInfo = [];
  const encodedSize = [];
  arrayInfo.push(decodedArrayInfo);
  const codecSpecs = parseArray(obj, getCodecResolver);
  const numCodecs = codecSpecs.length;
  let i = 0;
  for (; i < numCodecs; ++i) {
    const { resolver, configuration: initialConfiguration } = codecSpecs[i];
    if (resolver.kind !== CodecKind.arrayToArray) {
      break;
    }
    const arrayResolver = resolver;
    const { configuration, encodedArrayInfo } = arrayResolver.resolve(
      initialConfiguration,
      decodedArrayInfo
    );
    arrayInfo.push(encodedArrayInfo);
    decodedArrayInfo = encodedArrayInfo;
    arrayToArray.push({
      kind: CodecKind.arrayToArray,
      name: resolver.name,
      configuration
    });
  }
  if (i === numCodecs || codecSpecs[i].resolver.kind !== CodecKind.arrayToBytes) {
    throw new Error("Missing array -> bytes codec");
  }
  const {
    codecSpec: arrayToBytes,
    layoutInfo: finalLayoutInfo,
    encodedSize: initialEncodedSize,
    shardingInfo
  } = (() => {
    const { resolver, configuration: initialConfiguration } = codecSpecs[i];
    const arrayToBytesResolver = resolver;
    const { configuration, shardingInfo: shardingInfo2, encodedSize: encodedSize2 } = arrayToBytesResolver.resolve(initialConfiguration, decodedArrayInfo);
    if (shardingInfo2 !== void 0) {
      if (i + 1 !== numCodecs) {
        throw new Error(
          "bytes -> bytes codecs not supported following sharding codec"
        );
      }
    }
    const layoutInfo2 = arrayToBytesResolver.getDecodedArrayLayoutInfo(
      configuration,
      decodedArrayInfo
    );
    const codecSpec = {
      name: resolver.name,
      kind: CodecKind.arrayToBytes,
      configuration
    };
    return { codecSpec, layoutInfo: layoutInfo2, encodedSize: encodedSize2, shardingInfo: shardingInfo2 };
  })();
  layoutInfo[i] = finalLayoutInfo;
  encodedSize.push(initialEncodedSize);
  const curEncodedSize = initialEncodedSize;
  const bytesToBytes = [];
  ++i;
  while (i < numCodecs) {
    const { resolver, configuration: initialConfiguration } = codecSpecs[i];
    if (resolver.kind !== CodecKind.bytesToBytes) {
      throw new Error(
        `Expected bytes -> bytes codec, but received ${JSON.stringify(
          resolver.name
        )} of kind ${CodecKind[resolver.kind]}`
      );
    }
    const bytesResolver = resolver;
    const { configuration, encodedSize: newEncodedSize } = bytesResolver.resolve(initialConfiguration, curEncodedSize);
    bytesToBytes.push({
      name: resolver.name,
      kind: resolver.kind,
      configuration
    });
    encodedSize.push(newEncodedSize);
    ++i;
  }
  for (let j = arrayToArray.length - 1; j >= 0; --j) {
    layoutInfo[j] = codecSpecs[j].resolver.getDecodedArrayLayoutInfo(
      arrayToArray[j].configuration,
      arrayInfo[j],
      layoutInfo[j + 1]
    );
  }
  return {
    [CodecKind.arrayToArray]: arrayToArray,
    [CodecKind.arrayToBytes]: arrayToBytes,
    [CodecKind.bytesToBytes]: bytesToBytes,
    arrayInfo,
    layoutInfo,
    shardingInfo,
    encodedSize
  };
}

// node_modules/neuroglancer/lib/datasource/zarr/metadata/parse.js
init_legacy_browser();

// node_modules/neuroglancer/lib/datasource/zarr/metadata/index.js
init_legacy_browser();
var ChunkKeyEncoding = /* @__PURE__ */ ((ChunkKeyEncoding22) => {
  ChunkKeyEncoding22[ChunkKeyEncoding22["DEFAULT"] = 0] = "DEFAULT";
  ChunkKeyEncoding22[ChunkKeyEncoding22["V2"] = 1] = "V2";
  return ChunkKeyEncoding22;
})(ChunkKeyEncoding || {});

// node_modules/neuroglancer/lib/datasource/zarr/metadata/parse.js
function parseChunkShape(obj, rank) {
  return parseFixedLengthArray(new Array(rank), obj, (x) => {
    if (typeof x !== "number" || !Number.isInteger(x) || x <= 0) {
      throw new Error(
        `Expected positive integer, but received: ${JSON.stringify(x)}`
      );
    }
    return x;
  });
}
var UNITS = /* @__PURE__ */ new Map([
  ["", { unit: "", scale: 1 }],
  ["angstrom", { unit: "m", scale: 1e-10 }],
  ["foot", { unit: "m", scale: 0.3048 }],
  ["inch", { unit: "m", scale: 0.0254 }],
  ["mile", { unit: "m", scale: 1609.34 }],
  // eslint-disable-next-line no-loss-of-precision
  ["parsec", { unit: "m", scale: 30856775814913670 }],
  ["yard", { unit: "m", scale: 0.9144 }],
  ["minute", { unit: "s", scale: 60 }],
  ["hour", { unit: "s", scale: 60 * 60 }],
  ["day", { unit: "s", scale: 60 * 60 * 24 }]
]);
for (const unit of ["meter", "second"]) {
  for (const siPrefix of allSiPrefixes) {
    const { longPrefix, prefix } = siPrefix;
    if (longPrefix === void 0) continue;
    const unitInfo = { unit: unit[0], scale: 10 ** siPrefix.exponent };
    UNITS.set(`${longPrefix}${unit}`, unitInfo);
    UNITS.set(`${prefix}${unit[0]}`, unitInfo);
  }
}

// node_modules/neuroglancer/lib/datasource/zarr/codec/sharding_indexed/resolve.js
var ShardIndexLocation = /* @__PURE__ */ ((ShardIndexLocation2) => {
  ShardIndexLocation2[ShardIndexLocation2["START"] = 0] = "START";
  ShardIndexLocation2[ShardIndexLocation2["END"] = 1] = "END";
  return ShardIndexLocation2;
})(ShardIndexLocation || {});
registerCodec2({
  name: "sharding_indexed",
  kind: CodecKind.arrayToBytes,
  resolve(configuration, decodedArrayInfo) {
    verifyObject(configuration);
    const subChunkShape = verifyObjectProperty(
      configuration,
      "chunk_shape",
      (value) => parseChunkShape(value, decodedArrayInfo.chunkShape.length)
    );
    const indexLocation = verifyOptionalObjectProperty(
      configuration,
      "index_location",
      (x) => verifyEnumString(x, ShardIndexLocation, /^[a-z]+$/),
      1
      /* END */
    );
    const subChunkGridShape = Array.from(
      decodedArrayInfo.chunkShape,
      (outerSize, i) => {
        const innerSize = subChunkShape[i];
        if (outerSize % innerSize !== 0) {
          throw new Error(
            `sub-chunk shape of ${JSON.stringify(
              innerSize
            )} does not evenly divide outer chunk shape of ${JSON.stringify(
              decodedArrayInfo.chunkShape
            )}`
          );
        }
        return outerSize / innerSize;
      }
    );
    const indexShape = Array.from(subChunkGridShape);
    indexShape.push(2);
    const indexCodecs = verifyObjectProperty(
      configuration,
      "index_codecs",
      (value) => parseCodecChainSpec(value, {
        dataType: DataType.UINT64,
        chunkShape: indexShape
      })
    );
    if (indexCodecs.encodedSize[indexCodecs.encodedSize.length - 1] === void 0) {
      throw new Error("index_codecs must specify fixed-size encoding");
    }
    const subChunkCodecs = verifyObjectProperty(
      configuration,
      "codecs",
      (value) => parseCodecChainSpec(value, {
        dataType: decodedArrayInfo.dataType,
        chunkShape: subChunkShape
      })
    );
    return {
      configuration: {
        indexCodecs,
        subChunkCodecs,
        subChunkShape,
        subChunkGridShape,
        indexLocation
      },
      shardingInfo: { subChunkShape, subChunkGridShape, subChunkCodecs }
    };
  },
  getDecodedArrayLayoutInfo(configuration, decodedArrayInfo) {
    decodedArrayInfo;
    return configuration.subChunkCodecs.layoutInfo[0];
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/codec/sharding_indexed/decode.js
var MISSING_VALUE = BigInt("18446744073709551615");
function makeIndexCache(chunkManager, base, configuration) {
  return new SimpleAsyncCache(chunkManager.addRef(), {
    get: async (key, progressOptions) => {
      const { indexCodecs } = configuration;
      const encodedSize = indexCodecs.encodedSize[indexCodecs.encodedSize.length - 1];
      let byteRange;
      switch (configuration.indexLocation) {
        case ShardIndexLocation.START:
          byteRange = { offset: 0, length: encodedSize };
          break;
        case ShardIndexLocation.END:
          byteRange = { suffixLength: encodedSize };
          break;
      }
      const response = await base.read(key, {
        ...progressOptions,
        byteRange
      });
      if (response === void 0) {
        return { size: 0, data: void 0 };
      }
      const index = await decodeArray(
        configuration.indexCodecs,
        new Uint8Array(await response.response.arrayBuffer()),
        progressOptions.signal
      );
      return {
        size: index.byteLength,
        data: new BigUint64Array(
          index.buffer,
          index.byteOffset,
          index.byteLength / 8
        )
      };
    }
  });
}
var ShardedKvStore2 = class extends RefCounted {
  constructor(configuration, chunkManager, base) {
    super();
    this.configuration = configuration;
    this.base = base;
    this.indexCache = this.registerDisposer(
      makeIndexCache(chunkManager, base, configuration)
    );
    const { subChunkGridShape } = this.configuration;
    const rank = subChunkGridShape.length;
    const physicalToLogicalIndexDimension = this.configuration.indexCodecs.layoutInfo[0].physicalToLogicalDimension;
    const indexStrides = this.indexStrides = new Array(rank + 1);
    let stride = 1;
    for (let physicalIndexDim = rank; physicalIndexDim >= 0; --physicalIndexDim) {
      const logicalIndexDim = physicalToLogicalIndexDimension[physicalIndexDim];
      indexStrides[logicalIndexDim] = stride;
      stride *= logicalIndexDim === rank ? 2 : subChunkGridShape[logicalIndexDim];
    }
  }
  indexCache;
  indexStrides;
  async findKey(key, progressOptions) {
    const shardIndex = await this.indexCache.get(key.base, progressOptions);
    if (shardIndex === void 0) {
      return void 0;
    }
    const rank = this.configuration.subChunkShape.length;
    const { subChunk } = key;
    const { indexStrides } = this;
    let indexOffset = 0;
    for (let logicalIndexDim = 0; logicalIndexDim < rank; ++logicalIndexDim) {
      const pos = subChunk[logicalIndexDim];
      indexOffset += pos * indexStrides[logicalIndexDim];
    }
    const dataOffset = shardIndex[indexOffset];
    const dataLength = shardIndex[indexOffset + indexStrides[rank]];
    if (dataOffset === MISSING_VALUE && dataLength === MISSING_VALUE) {
      return void 0;
    }
    return {
      offset: Number(dataOffset),
      length: Number(dataLength)
    };
  }
  async stat(key, options) {
    const fullByteRange = await this.findKey(key, options);
    if (fullByteRange === void 0) return void 0;
    return { totalSize: fullByteRange.length };
  }
  async read(key, options) {
    const fullByteRange = await this.findKey(key, options);
    if (fullByteRange === void 0) return void 0;
    return new FileByteRangeHandle(
      new KvStoreFileHandle(this.base, key.base),
      fullByteRange
    ).read(options);
  }
  getUrl(key) {
    return `subchunk ${JSON.stringify(key.subChunk)} within shard ${this.base.getUrl(key.base)}`;
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};
registerCodec({
  name: "sharding_indexed",
  kind: CodecKind.arrayToBytes,
  getShardedKvStore(configuration, chunkManager, base) {
    return new ShardedKvStore2(configuration, chunkManager, base);
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/codec/transpose/decode.js
init_legacy_browser();
registerCodec({
  name: "transpose",
  kind: CodecKind.arrayToArray,
  async decode(configuration, decodedArrayInfo, encoded, signal) {
    decodedArrayInfo;
    signal;
    configuration;
    return encoded;
  }
});

// node_modules/neuroglancer/lib/datasource/zarr/backend.js
var __defProp26 = Object.defineProperty;
var __getOwnPropDesc26 = Object.getOwnPropertyDescriptor;
var __decorateClass25 = (decorators, target2, key, kind) => {
  var result = kind > 1 ? void 0 : kind ? __getOwnPropDesc26(target2, key) : target2;
  for (var i = decorators.length - 1, decorator; i >= 0; i--)
    if (decorator = decorators[i])
      result = (kind ? decorator(target2, key, result) : decorator(result)) || result;
  if (kind && result) __defProp26(target2, key, result);
  return result;
};
var ZarrVolumeChunkSource = class extends WithParameters(
  WithSharedKvStoreContextCounterpart(VolumeChunkSource),
  VolumeChunkSourceParameters5
) {
  chunkKvStore = applySharding(
    this.chunkManager,
    this.parameters.metadata.codecs,
    this.sharedKvStoreContext.kvStoreContext.getKvStore(this.parameters.url)
  );
  async download(chunk, signal) {
    chunk.chunkDataSize = this.spec.chunkDataSize;
    const { parameters } = this;
    const { chunkGridPosition } = chunk;
    const { metadata } = parameters;
    let baseKey = "";
    const rank = this.spec.rank;
    const { physicalToLogicalDimension } = metadata.codecs.layoutInfo[0];
    let sep;
    if (metadata.chunkKeyEncoding === ChunkKeyEncoding.DEFAULT) {
      baseKey += "c";
      sep = metadata.dimensionSeparator;
    } else {
      sep = "";
      if (rank === 0) {
        baseKey += "0";
      }
    }
    const keyCoords = new Array(rank);
    const { readChunkShape } = metadata.codecs.layoutInfo[0];
    const { chunkShape } = metadata;
    for (let fOrderPhysicalDim = 0; fOrderPhysicalDim < rank; ++fOrderPhysicalDim) {
      const decodedDim = physicalToLogicalDimension[rank - 1 - fOrderPhysicalDim];
      keyCoords[decodedDim] = Math.floor(
        chunkGridPosition[fOrderPhysicalDim] * readChunkShape[decodedDim] / chunkShape[decodedDim]
      );
    }
    for (let i = 0; i < rank; ++i) {
      baseKey += `${sep}${keyCoords[i]}`;
      sep = metadata.dimensionSeparator;
    }
    const { chunkKvStore } = this;
    const response = await chunkKvStore.kvStore.read(
      chunkKvStore.getChunkKey(chunkGridPosition, baseKey),
      { signal }
    );
    if (response !== void 0) {
      const decoded = await decodeArray(
        chunkKvStore.decodeCodecs,
        new Uint8Array(await response.response.arrayBuffer()),
        signal
      );
      await postProcessRawData(chunk, signal, decoded);
    }
  }
};
ZarrVolumeChunkSource = __decorateClass25([
  registerSharedObject()
], ZarrVolumeChunkSource);

// node_modules/neuroglancer/lib/kvstore/enabled_backend_modules.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/byte_range/register.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/byte_range/index.js
init_legacy_browser();
function parseKey(key) {
  const m = key.match(/^([0-9]+)-([0-9]+)$/);
  if (m !== null) {
    const begin = Number(m[1]);
    const end = Number(m[2]);
    if (end >= begin) {
      return { offset: begin, length: end - begin };
    }
  }
  throw new Error(
    `Invalid key ${JSON.stringify(key)} for "byte-range:", expected "<begin>-<end>"`
  );
}
var ByteRangeKvStore = class {
  constructor(base) {
    this.base = base;
  }
  getUrl(key) {
    return this.base.getUrl() + `|byte-range:${key}`;
  }
  async stat(key, options) {
    const { length: length6 } = parseKey(key);
    options;
    return { totalSize: length6 };
  }
  async read(key, options) {
    const byteRange = parseKey(key);
    return new FileByteRangeHandle(this.base, byteRange).read(options);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
  get singleKey() {
    return true;
  }
};

// node_modules/neuroglancer/lib/kvstore/byte_range/register.js
function byteRangeProvider() {
  return {
    scheme: "byte-range",
    description: `byte range slicing`,
    getKvStore(url, base) {
      ensureNoQueryOrFragmentParameters(url);
      return {
        store: new ByteRangeKvStore(
          new KvStoreFileHandle(base.store, base.path)
        ),
        path: url.suffix ?? ""
      };
    }
  };
}
frontendBackendIsomorphicKvStoreProviderRegistry.registerKvStoreAdapterProvider(
  byteRangeProvider
);

// node_modules/neuroglancer/lib/kvstore/gcs/register.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/gcs/index.js
init_legacy_browser();
var __knownSymbol = (name, symbol) => (symbol = Symbol[name]) ? symbol : Symbol.for("Symbol." + name);
var __typeError = (msg) => {
  throw TypeError(msg);
};
var __using = (stack, value, async) => {
  if (value != null) {
    if (typeof value !== "object" && typeof value !== "function") __typeError("Object expected");
    var dispose, inner;
    if (async) dispose = value[__knownSymbol("asyncDispose")];
    if (dispose === void 0) {
      dispose = value[__knownSymbol("dispose")];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") __typeError("Object not disposable");
    if (inner) dispose = function() {
      try {
        inner.call(this);
      } catch (e) {
        return Promise.reject(e);
      }
    };
    stack.push([async, dispose, value]);
  } else if (async) {
    stack.push([async]);
  }
  return value;
};
var __callDispose = (stack, error, hasError) => {
  var E = typeof SuppressedError === "function" ? SuppressedError : function(e, s, m, _) {
    return _ = Error(m), _.name = "SuppressedError", _.error = e, _.suppressed = s, _;
  };
  var fail = (e) => error = hasError ? new E(e, error, "An error was suppressed during disposal") : (hasError = true, e);
  var next = (it) => {
    while (it = stack.pop()) {
      try {
        var result = it[1] && it[1].call(it[2]);
        if (it[0]) return Promise.resolve(result).then(next, (e) => (fail(e), next()));
      } catch (e) {
        fail(e);
      }
    }
    if (hasError) throw error;
  };
  return next();
};
var GcsKvStore = class {
  constructor(bucket, baseUrlForDisplay = `gs://${bucket}/`, fetchOkImpl = fetchOk) {
    this.bucket = bucket;
    this.baseUrlForDisplay = baseUrlForDisplay;
    this.fetchOkImpl = fetchOkImpl;
  }
  getObjectUrl(key) {
    return `https://storage.googleapis.com/storage/v1/b/${this.bucket}/o/${encodeURIComponent(key)}?alt=media&neuroglancer=${getRandomHexString()}`;
  }
  stat(key, options) {
    return stat(this, key, this.getObjectUrl(key), options, this.fetchOkImpl);
  }
  read(key, options) {
    return read(this, key, this.getObjectUrl(key), options, this.fetchOkImpl);
  }
  async list(prefix, options) {
    var _stack = [];
    try {
      const { progressListener } = options;
      const _span = __using(_stack, progressListener === void 0 ? void 0 : new ProgressSpan(progressListener, {
        message: `Listing prefix ${this.getUrl(prefix)}`
      }));
      const delimiter = "/";
      const response = await this.fetchOkImpl(
        `https://storage.googleapis.com/storage/v1/b/${this.bucket}/o?delimiter=${encodeURIComponent(delimiter)}&prefix=${encodeURIComponent(
          prefix
        )}&neuroglancerOrigin=${encodeURIComponent(location.origin)}`,
        {
          signal: options.signal,
          progressListener: options.progressListener
        }
      );
      const responseJson = await response.json();
      verifyObject(responseJson);
      const directories = verifyOptionalObjectProperty(
        responseJson,
        "prefixes",
        verifyStringArray,
        []
      ).map((prefix2) => prefix2.substring(0, prefix2.length - 1));
      const entries = verifyOptionalObjectProperty(
        responseJson,
        "items",
        (items) => parseArray(items, (item) => {
          verifyObject(item);
          return verifyObjectProperty(item, "name", verifyString);
        }),
        []
      ).filter((name) => !name.endsWith("_$folder$")).map((name) => ({ key: name }));
      return {
        directories,
        entries
      };
    } catch (_) {
      var _error = _, _hasError = true;
    } finally {
      __callDispose(_stack, _error, _hasError);
    }
  }
  getUrl(path) {
    return this.baseUrlForDisplay + encodePathForUrl(path);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};

// node_modules/neuroglancer/lib/kvstore/gcs/register.js
function gcsProvider(_context) {
  return {
    scheme: "gs",
    description: false_default ? "Google Cloud Storage" : "Google Cloud Storage (anonymous)",
    getKvStore(url) {
      const m = (url.suffix ?? "").match(/^\/\/([^/]+)(\/.*)?$/);
      if (m === null) {
        throw new Error("Invalid URL, expected `gs://<bucket>/<path>`");
      }
      const [, bucket, path] = m;
      return {
        store: new GcsKvStore(bucket),
        path: decodeURIComponent((path ?? "").substring(1))
      };
    }
  };
}
frontendBackendIsomorphicKvStoreProviderRegistry.registerBaseKvStoreProvider(
  gcsProvider
);

// node_modules/neuroglancer/lib/kvstore/gzip/register.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/gzip/index.js
init_legacy_browser();
var GzipKvStore = class {
  constructor(base, scheme, format) {
    this.base = base;
    this.scheme = scheme;
    this.format = format;
  }
  getUrl(key) {
    this.validatePath(key);
    return this.base.getUrl() + `|${this.scheme}`;
  }
  validatePath(path) {
    if (path) {
      throw new Error(
        `"${this.scheme}:" does not support non-empty path ${JSON.stringify(path)}`
      );
    }
  }
  async stat(key, options) {
    this.validatePath(key);
    await this.base.stat(options);
    return { totalSize: void 0 };
  }
  async read(key, options) {
    this.validatePath(key);
    return new GzipFileHandle(this.base, this.format).read(options);
  }
  get supportsOffsetReads() {
    return false;
  }
  get supportsSuffixReads() {
    return false;
  }
  get singleKey() {
    return true;
  }
};
async function detectGzip(options) {
  if (!isGzipFormat(options.prefix)) {
    return [];
  }
  return [{ suffix: "gzip:", description: "gzip-compressed" }];
}
function registerAutoDetect(registry) {
  registry.registerFileFormat({
    prefixLength: 3,
    suffixLength: 0,
    match: detectGzip
  });
}

// node_modules/neuroglancer/lib/kvstore/gzip/register.js
function gzipProvider(scheme, format) {
  return {
    scheme,
    description: `transparent ${scheme} decoding`,
    getKvStore(url, base) {
      ensureEmptyUrlSuffix(url);
      return {
        store: new GzipKvStore(
          new KvStoreFileHandle(base.store, base.path),
          scheme,
          format
        ),
        path: ""
      };
    }
  };
}
frontendBackendIsomorphicKvStoreProviderRegistry.registerKvStoreAdapterProvider(
  () => gzipProvider("gzip", "gzip")
);
registerAutoDetect(
  frontendBackendIsomorphicKvStoreProviderRegistry.autoDetectRegistry
);

// node_modules/neuroglancer/lib/kvstore/http/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/http/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/proxy.js
init_legacy_browser();
registerPromiseRPC(
  STAT_RPC_ID,
  async function(options, progressOptions) {
    const sharedKvStoreContext = this.get(
      options.sharedKvStoreContext
    );
    return {
      value: await sharedKvStoreContext.kvStoreContext.stat(
        options.url,
        progressOptions
      )
    };
  }
);
registerPromiseRPC(
  READ_RPC_ID,
  async function(options, progressOptions) {
    const sharedKvStoreContext = this.get(
      options.sharedKvStoreContext
    );
    const readResponse = await sharedKvStoreContext.kvStoreContext.read(
      options.url,
      {
        ...progressOptions,
        byteRange: options.byteRange,
        throwIfMissing: options.throwIfMissing
      }
    );
    if (readResponse === void 0) {
      return { value: void 0 };
    }
    const arrayBuffer = await readResponse.response.arrayBuffer();
    return {
      value: {
        data: arrayBuffer,
        offset: readResponse.offset,
        totalSize: readResponse.totalSize
      },
      transfers: [arrayBuffer]
    };
  }
);
function proxyList(sharedKvStoreContext, url, options) {
  return sharedKvStoreContext.rpc.promiseInvoke(
    LIST_RPC_ID,
    {
      sharedKvStoreContext: sharedKvStoreContext.rpcId,
      url
    },
    { signal: options.signal, progressListener: options.progressListener }
  );
}
registerPromiseRPC(
  LIST_RPC_ID,
  async function(options, progressOptions) {
    const sharedKvStoreContext = this.get(
      options.sharedKvStoreContext
    );
    const { store, path } = sharedKvStoreContext.kvStoreContext.getKvStore(
      options.url
    );
    return {
      value: await store.list(path, progressOptions)
    };
  }
);
registerPromiseRPC(
  COMPLETE_URL_RPC_ID,
  async function(options, progressOptions) {
    const sharedKvStoreContext = this.get(
      options.sharedKvStoreContext
    );
    const { kvStoreContext } = sharedKvStoreContext;
    const { url } = options;
    const finalComponent = finalPipelineUrlComponent(url);
    let result;
    if (finalComponent === url) {
      const parsedUrl = parsePipelineUrlComponent(finalComponent);
      const provider = kvStoreContext.getBaseKvStoreProvider(parsedUrl);
      if (provider.completeUrl !== void 0) {
        result = await provider.completeUrl({
          url: parsedUrl,
          ...progressOptions
        });
      }
    } else {
      const adapterUrl = parsePipelineUrlComponent(finalComponent);
      const provider = kvStoreContext.getKvStoreAdapterProvider(adapterUrl);
      const baseUrl = url.slice(0, url.length - finalComponent.length - 1);
      const base = kvStoreContext.getKvStore(baseUrl);
      if (provider.completeUrl !== void 0) {
        result = await provider.completeUrl({
          url: adapterUrl,
          base,
          ...progressOptions
        });
      }
    }
    return {
      value: result
    };
  }
);

// node_modules/neuroglancer/lib/kvstore/http/backend.js
var HttpKvStore = class extends ReadableHttpKvStore {
  list(prefix, options) {
    return proxyList(this.sharedKvStoreContext, this.getUrl(prefix), options);
  }
};

// node_modules/neuroglancer/lib/kvstore/http/register_backend.js
registerProviders(backendOnlyKvStoreProviderRegistry, HttpKvStore);

// node_modules/neuroglancer/lib/kvstore/icechunk/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/icechunk/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/icechunk/list.js
init_legacy_browser();
function getListResponseFromSnapshot(snapshot, prefix) {
  const { nodes } = snapshot;
  const startIndex = binarySearchLowerBound(
    0,
    nodes.length,
    (index) => nodes[index].path >= prefix
  );
  const endIndex = binarySearchLowerBound(
    Math.min(nodes.length, startIndex + 1),
    nodes.length,
    (index) => !nodes[index].path.startsWith(prefix)
  );
  const response = { entries: [], directories: [] };
  for (let index = startIndex; index < endIndex; ) {
    const node = nodes[index];
    const { path } = node;
    const i = path.indexOf("/", prefix.length);
    if (i === -1) {
      ++index;
    } else {
      if (i + 1 === path.length) {
        response.directories.push(path.slice(0, i));
      }
      const directoryPrefix = path.substring(0, i + 1);
      index = binarySearchLowerBound(
        index + 1,
        endIndex,
        (index2) => !nodes[index2].path.startsWith(directoryPrefix)
      );
    }
  }
  const lastSlash = prefix.lastIndexOf("/");
  if ("zarr.json".startsWith(prefix.slice(lastSlash + 1))) {
    const parentPath = prefix.substring(0, lastSlash + 1);
    const parentNodeIndex = binarySearch(
      nodes,
      parentPath,
      (path, node) => defaultStringCompare(path, node.path)
    );
    if (parentNodeIndex >= 0) {
      response.entries.push({ key: parentPath + "zarr.json" });
    } else {
      throw new Error(`Parent node ${JSON.stringify(parentPath)} not found`);
    }
  }
  return normalizeListResponse(response);
}

// node_modules/neuroglancer/lib/kvstore/icechunk/metadata_cache.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/icechunk/manifest.js
init_legacy_browser();

// node_modules/valibot/dist/index.mjs
init_legacy_browser();
var store$4;
var DEFAULT_CONFIG = {
  lang: void 0,
  message: void 0,
  abortEarly: void 0,
  abortPipeEarly: void 0
};
// @__NO_SIDE_EFFECTS__
function getGlobalConfig(config$1) {
  if (!config$1 && !store$4) return DEFAULT_CONFIG;
  return {
    lang: (config$1 == null ? void 0 : config$1.lang) ?? (store$4 == null ? void 0 : store$4.lang),
    message: config$1 == null ? void 0 : config$1.message,
    abortEarly: (config$1 == null ? void 0 : config$1.abortEarly) ?? (store$4 == null ? void 0 : store$4.abortEarly),
    abortPipeEarly: (config$1 == null ? void 0 : config$1.abortPipeEarly) ?? (store$4 == null ? void 0 : store$4.abortPipeEarly)
  };
}
var store$3;
// @__NO_SIDE_EFFECTS__
function getGlobalMessage(lang) {
  return store$3 == null ? void 0 : store$3.get(lang);
}
var store$2;
// @__NO_SIDE_EFFECTS__
function getSchemaMessage(lang) {
  return store$2 == null ? void 0 : store$2.get(lang);
}
var store$1;
// @__NO_SIDE_EFFECTS__
function getSpecificMessage(reference, lang) {
  var _a;
  return (_a = store$1 == null ? void 0 : store$1.get(reference)) == null ? void 0 : _a.get(lang);
}
// @__NO_SIDE_EFFECTS__
function _stringify(input) {
  var _a, _b;
  const type = typeof input;
  if (type === "string") return `"${input}"`;
  if (type === "number" || type === "bigint" || type === "boolean") return `${input}`;
  if (type === "object" || type === "function") return (input && ((_b = (_a = Object.getPrototypeOf(input)) == null ? void 0 : _a.constructor) == null ? void 0 : _b.name)) ?? "null";
  return type;
}
function _addIssue(context, label, dataset, config$1, other) {
  const input = other && "input" in other ? other.input : dataset.value;
  const expected = (other == null ? void 0 : other.expected) ?? context.expects ?? null;
  const received = (other == null ? void 0 : other.received) ?? /* @__PURE__ */ _stringify(input);
  const issue = {
    kind: context.kind,
    type: context.type,
    input,
    expected,
    received,
    message: `Invalid ${label}: ${expected ? `Expected ${expected} but r` : "R"}eceived ${received}`,
    requirement: context.requirement,
    path: other == null ? void 0 : other.path,
    issues: other == null ? void 0 : other.issues,
    lang: config$1.lang,
    abortEarly: config$1.abortEarly,
    abortPipeEarly: config$1.abortPipeEarly
  };
  const isSchema = context.kind === "schema";
  const message$1 = (other == null ? void 0 : other.message) ?? context.message ?? /* @__PURE__ */ getSpecificMessage(context.reference, issue.lang) ?? (isSchema ? /* @__PURE__ */ getSchemaMessage(issue.lang) : null) ?? config$1.message ?? /* @__PURE__ */ getGlobalMessage(issue.lang);
  if (message$1 !== void 0) issue.message = typeof message$1 === "function" ? message$1(issue) : message$1;
  if (isSchema) dataset.typed = false;
  if (dataset.issues) dataset.issues.push(issue);
  else dataset.issues = [issue];
}
// @__NO_SIDE_EFFECTS__
function _isValidObjectKey(object$1, key) {
  return Object.prototype.hasOwnProperty.call(object$1, key) && key !== "__proto__" && key !== "prototype" && key !== "constructor";
}
// @__NO_SIDE_EFFECTS__
function _joinExpects(values$1, separator) {
  const list2 = [...new Set(values$1)];
  if (list2.length > 1) return `(${list2.join(` ${separator} `)})`;
  return list2[0] ?? "never";
}
function _standardSchema(schema) {
  schema["~standard"] = {
    version: 1,
    vendor: "valibot",
    validate: (value$1) => schema["~run"]({ value: value$1 }, /* @__PURE__ */ getGlobalConfig())
  };
  return schema;
}
// @__NO_SIDE_EFFECTS__
function getDotPath(issue) {
  if (issue.path) {
    let key = "";
    for (const item of issue.path) if (typeof item.key === "string" || typeof item.key === "number") if (key) key += `.${item.key}`;
    else key += item.key;
    else return null;
    return key;
  }
  return null;
}
var ValiError = class extends Error {
  /**
  * Creates a Valibot error with useful information.
  *
  * @param issues The error issues.
  */
  constructor(issues) {
    super(issues[0].message);
    this.name = "ValiError";
    this.issues = issues;
  }
};
// @__NO_SIDE_EFFECTS__
function isValiError(error) {
  return error instanceof ValiError;
}
var EMOJI_REGEX = new RegExp("^(?:[\\u{1F1E6}-\\u{1F1FF}]{2}|\\u{1F3F4}[\\u{E0061}-\\u{E007A}]{2}[\\u{E0030}-\\u{E0039}\\u{E0061}-\\u{E007A}]{1,3}\\u{E007F}|(?:\\p{Emoji}\\uFE0F\\u20E3?|\\p{Emoji_Modifier_Base}\\p{Emoji_Modifier}?|(?![\\p{Emoji_Modifier_Base}\\u{1F1E6}-\\u{1F1FF}])\\p{Emoji_Presentation})(?:\\u200D(?:\\p{Emoji}\\uFE0F\\u20E3?|\\p{Emoji_Modifier_Base}\\p{Emoji_Modifier}?|(?![\\p{Emoji_Modifier_Base}\\u{1F1E6}-\\u{1F1FF}])\\p{Emoji_Presentation}))*)+$", "u");
// @__NO_SIDE_EFFECTS__
function check(requirement, message$1) {
  return {
    kind: "validation",
    type: "check",
    reference: check,
    async: false,
    expects: null,
    requirement,
    message: message$1,
    "~run"(dataset, config$1) {
      if (dataset.typed && !this.requirement(dataset.value)) _addIssue(this, "input", dataset, config$1);
      return dataset;
    }
  };
}
// @__NO_SIDE_EFFECTS__
function integer(message$1) {
  return {
    kind: "validation",
    type: "integer",
    reference: integer,
    async: false,
    expects: null,
    requirement: Number.isInteger,
    message: message$1,
    "~run"(dataset, config$1) {
      if (dataset.typed && !this.requirement(dataset.value)) _addIssue(this, "integer", dataset, config$1);
      return dataset;
    }
  };
}
// @__NO_SIDE_EFFECTS__
function length5(requirement, message$1) {
  return {
    kind: "validation",
    type: "length",
    reference: length5,
    async: false,
    expects: `${requirement}`,
    requirement,
    message: message$1,
    "~run"(dataset, config$1) {
      if (dataset.typed && dataset.value.length !== this.requirement) _addIssue(this, "length", dataset, config$1, { received: `${dataset.value.length}` });
      return dataset;
    }
  };
}
// @__NO_SIDE_EFFECTS__
function transform(operation) {
  return {
    kind: "transformation",
    type: "transform",
    reference: transform,
    async: false,
    operation,
    "~run"(dataset) {
      dataset.value = this.operation(dataset.value);
      return dataset;
    }
  };
}
// @__NO_SIDE_EFFECTS__
function getFallback(schema, dataset, config$1) {
  return typeof schema.fallback === "function" ? schema.fallback(dataset, config$1) : schema.fallback;
}
// @__NO_SIDE_EFFECTS__
function flatten(issues) {
  const flatErrors = {};
  for (const issue of issues) if (issue.path) {
    const dotPath = /* @__PURE__ */ getDotPath(issue);
    if (dotPath) {
      if (!flatErrors.nested) flatErrors.nested = {};
      if (Object.prototype.hasOwnProperty.call(flatErrors.nested, dotPath)) flatErrors.nested[dotPath].push(issue.message);
      else flatErrors.nested[dotPath] = [issue.message];
    } else if (flatErrors.other) flatErrors.other.push(issue.message);
    else flatErrors.other = [issue.message];
  } else if (flatErrors.root) flatErrors.root.push(issue.message);
  else flatErrors.root = [issue.message];
  return flatErrors;
}
// @__NO_SIDE_EFFECTS__
function getDefault(schema, dataset, config$1) {
  return typeof schema.default === "function" ? schema.default(dataset, config$1) : schema.default;
}
// @__NO_SIDE_EFFECTS__
function any2() {
  return _standardSchema({
    kind: "schema",
    type: "any",
    reference: any2,
    expects: "any",
    async: false,
    "~run"(dataset) {
      dataset.typed = true;
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function array(item, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "array",
    reference: array,
    expects: "Array",
    async: false,
    item,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a;
      const input = dataset.value;
      if (Array.isArray(input)) {
        dataset.typed = true;
        dataset.value = [];
        for (let key = 0; key < input.length; key++) {
          const value$1 = input[key];
          const itemDataset = this.item["~run"]({ value: value$1 }, config$1);
          if (itemDataset.issues) {
            const pathItem = {
              type: "array",
              origin: "value",
              input,
              key,
              value: value$1
            };
            for (const issue of itemDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_a = dataset.issues) == null ? void 0 : _a.push(issue);
            }
            if (!dataset.issues) dataset.issues = itemDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          if (!itemDataset.typed) dataset.typed = false;
          dataset.value.push(itemDataset.value);
        }
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function bigint(message$1) {
  return _standardSchema({
    kind: "schema",
    type: "bigint",
    reference: bigint,
    expects: "bigint",
    async: false,
    message: message$1,
    "~run"(dataset, config$1) {
      if (typeof dataset.value === "bigint") dataset.typed = true;
      else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function instance(class_, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "instance",
    reference: instance,
    expects: class_.name,
    async: false,
    class: class_,
    message: message$1,
    "~run"(dataset, config$1) {
      if (dataset.value instanceof this.class) dataset.typed = true;
      else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function map(key, value$1, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "map",
    reference: map,
    expects: "Map",
    async: false,
    key,
    value: value$1,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a, _b;
      const input = dataset.value;
      if (input instanceof Map) {
        dataset.typed = true;
        dataset.value = /* @__PURE__ */ new Map();
        for (const [inputKey, inputValue] of input) {
          const keyDataset = this.key["~run"]({ value: inputKey }, config$1);
          if (keyDataset.issues) {
            const pathItem = {
              type: "map",
              origin: "key",
              input,
              key: inputKey,
              value: inputValue
            };
            for (const issue of keyDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_a = dataset.issues) == null ? void 0 : _a.push(issue);
            }
            if (!dataset.issues) dataset.issues = keyDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          const valueDataset = this.value["~run"]({ value: inputValue }, config$1);
          if (valueDataset.issues) {
            const pathItem = {
              type: "map",
              origin: "value",
              input,
              key: inputKey,
              value: inputValue
            };
            for (const issue of valueDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_b = dataset.issues) == null ? void 0 : _b.push(issue);
            }
            if (!dataset.issues) dataset.issues = valueDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          if (!keyDataset.typed || !valueDataset.typed) dataset.typed = false;
          dataset.value.set(keyDataset.value, valueDataset.value);
        }
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function nullable(wrapped, default_) {
  return _standardSchema({
    kind: "schema",
    type: "nullable",
    reference: nullable,
    expects: `(${wrapped.expects} | null)`,
    async: false,
    wrapped,
    default: default_,
    "~run"(dataset, config$1) {
      if (dataset.value === null) {
        if (this.default !== void 0) dataset.value = /* @__PURE__ */ getDefault(this, dataset, config$1);
        if (dataset.value === null) {
          dataset.typed = true;
          return dataset;
        }
      }
      return this.wrapped["~run"](dataset, config$1);
    }
  });
}
// @__NO_SIDE_EFFECTS__
function number(message$1) {
  return _standardSchema({
    kind: "schema",
    type: "number",
    reference: number,
    expects: "number",
    async: false,
    message: message$1,
    "~run"(dataset, config$1) {
      if (typeof dataset.value === "number" && !isNaN(dataset.value)) dataset.typed = true;
      else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function picklist(options, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "picklist",
    reference: picklist,
    expects: /* @__PURE__ */ _joinExpects(options.map(_stringify), "|"),
    async: false,
    options,
    message: message$1,
    "~run"(dataset, config$1) {
      if (this.options.includes(dataset.value)) dataset.typed = true;
      else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function record(key, value$1, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "record",
    reference: record,
    expects: "Object",
    async: false,
    key,
    value: value$1,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a, _b;
      const input = dataset.value;
      if (input && typeof input === "object") {
        dataset.typed = true;
        dataset.value = {};
        for (const entryKey in input) if (/* @__PURE__ */ _isValidObjectKey(input, entryKey)) {
          const entryValue = input[entryKey];
          const keyDataset = this.key["~run"]({ value: entryKey }, config$1);
          if (keyDataset.issues) {
            const pathItem = {
              type: "object",
              origin: "key",
              input,
              key: entryKey,
              value: entryValue
            };
            for (const issue of keyDataset.issues) {
              issue.path = [pathItem];
              (_a = dataset.issues) == null ? void 0 : _a.push(issue);
            }
            if (!dataset.issues) dataset.issues = keyDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          const valueDataset = this.value["~run"]({ value: entryValue }, config$1);
          if (valueDataset.issues) {
            const pathItem = {
              type: "object",
              origin: "value",
              input,
              key: entryKey,
              value: entryValue
            };
            for (const issue of valueDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_b = dataset.issues) == null ? void 0 : _b.push(issue);
            }
            if (!dataset.issues) dataset.issues = valueDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          if (!keyDataset.typed || !valueDataset.typed) dataset.typed = false;
          if (keyDataset.typed) dataset.value[keyDataset.value] = valueDataset.value;
        }
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function strictObject(entries$1, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "strict_object",
    reference: strictObject,
    expects: "Object",
    async: false,
    entries: entries$1,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a;
      const input = dataset.value;
      if (input && typeof input === "object") {
        dataset.typed = true;
        dataset.value = {};
        for (const key in this.entries) {
          const valueSchema = this.entries[key];
          if (key in input || (valueSchema.type === "exact_optional" || valueSchema.type === "optional" || valueSchema.type === "nullish") && valueSchema.default !== void 0) {
            const value$1 = key in input ? input[key] : /* @__PURE__ */ getDefault(valueSchema);
            const valueDataset = valueSchema["~run"]({ value: value$1 }, config$1);
            if (valueDataset.issues) {
              const pathItem = {
                type: "object",
                origin: "value",
                input,
                key,
                value: value$1
              };
              for (const issue of valueDataset.issues) {
                if (issue.path) issue.path.unshift(pathItem);
                else issue.path = [pathItem];
                (_a = dataset.issues) == null ? void 0 : _a.push(issue);
              }
              if (!dataset.issues) dataset.issues = valueDataset.issues;
              if (config$1.abortEarly) {
                dataset.typed = false;
                break;
              }
            }
            if (!valueDataset.typed) dataset.typed = false;
            dataset.value[key] = valueDataset.value;
          } else if (valueSchema.fallback !== void 0) dataset.value[key] = /* @__PURE__ */ getFallback(valueSchema);
          else if (valueSchema.type !== "exact_optional" && valueSchema.type !== "optional" && valueSchema.type !== "nullish") {
            _addIssue(this, "key", dataset, config$1, {
              input: void 0,
              expected: `"${key}"`,
              path: [{
                type: "object",
                origin: "key",
                input,
                key,
                value: input[key]
              }]
            });
            if (config$1.abortEarly) break;
          }
        }
        if (!dataset.issues || !config$1.abortEarly) {
          for (const key in input) if (!Object.prototype.hasOwnProperty.call(this.entries, key)) {
            _addIssue(this, "key", dataset, config$1, {
              input: key,
              expected: "never",
              path: [{
                type: "object",
                origin: "key",
                input,
                key,
                value: input[key]
              }]
            });
            break;
          }
        }
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function strictTuple(items, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "strict_tuple",
    reference: strictTuple,
    expects: "Array",
    async: false,
    items,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a;
      const input = dataset.value;
      if (Array.isArray(input)) {
        dataset.typed = true;
        dataset.value = [];
        for (let key = 0; key < this.items.length; key++) {
          const value$1 = input[key];
          const itemDataset = this.items[key]["~run"]({ value: value$1 }, config$1);
          if (itemDataset.issues) {
            const pathItem = {
              type: "array",
              origin: "value",
              input,
              key,
              value: value$1
            };
            for (const issue of itemDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_a = dataset.issues) == null ? void 0 : _a.push(issue);
            }
            if (!dataset.issues) dataset.issues = itemDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          if (!itemDataset.typed) dataset.typed = false;
          dataset.value.push(itemDataset.value);
        }
        if (!(dataset.issues && config$1.abortEarly) && this.items.length < input.length) _addIssue(this, "type", dataset, config$1, {
          input: input[this.items.length],
          expected: "never",
          path: [{
            type: "array",
            origin: "value",
            input,
            key: this.items.length,
            value: input[this.items.length]
          }]
        });
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function string(message$1) {
  return _standardSchema({
    kind: "schema",
    type: "string",
    reference: string,
    expects: "string",
    async: false,
    message: message$1,
    "~run"(dataset, config$1) {
      if (typeof dataset.value === "string") dataset.typed = true;
      else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function tuple(items, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "tuple",
    reference: tuple,
    expects: "Array",
    async: false,
    items,
    message: message$1,
    "~run"(dataset, config$1) {
      var _a;
      const input = dataset.value;
      if (Array.isArray(input)) {
        dataset.typed = true;
        dataset.value = [];
        for (let key = 0; key < this.items.length; key++) {
          const value$1 = input[key];
          const itemDataset = this.items[key]["~run"]({ value: value$1 }, config$1);
          if (itemDataset.issues) {
            const pathItem = {
              type: "array",
              origin: "value",
              input,
              key,
              value: value$1
            };
            for (const issue of itemDataset.issues) {
              if (issue.path) issue.path.unshift(pathItem);
              else issue.path = [pathItem];
              (_a = dataset.issues) == null ? void 0 : _a.push(issue);
            }
            if (!dataset.issues) dataset.issues = itemDataset.issues;
            if (config$1.abortEarly) {
              dataset.typed = false;
              break;
            }
          }
          if (!itemDataset.typed) dataset.typed = false;
          dataset.value.push(itemDataset.value);
        }
      } else _addIssue(this, "type", dataset, config$1);
      return dataset;
    }
  });
}
// @__NO_SIDE_EFFECTS__
function _subIssues(datasets) {
  let issues;
  if (datasets) for (const dataset of datasets) if (issues) for (const issue of dataset.issues) issues.push(issue);
  else issues = dataset.issues;
  return issues;
}
// @__NO_SIDE_EFFECTS__
function union(options, message$1) {
  return _standardSchema({
    kind: "schema",
    type: "union",
    reference: union,
    expects: /* @__PURE__ */ _joinExpects(options.map((option) => option.expects), "|"),
    async: false,
    options,
    message: message$1,
    "~run"(dataset, config$1) {
      let validDataset;
      let typedDatasets;
      let untypedDatasets;
      for (const schema of this.options) {
        const optionDataset = schema["~run"]({ value: dataset.value }, config$1);
        if (optionDataset.typed) if (optionDataset.issues) if (typedDatasets) typedDatasets.push(optionDataset);
        else typedDatasets = [optionDataset];
        else {
          validDataset = optionDataset;
          break;
        }
        else if (untypedDatasets) untypedDatasets.push(optionDataset);
        else untypedDatasets = [optionDataset];
      }
      if (validDataset) return validDataset;
      if (typedDatasets) {
        if (typedDatasets.length === 1) return typedDatasets[0];
        _addIssue(this, "type", dataset, config$1, { issues: /* @__PURE__ */ _subIssues(typedDatasets) });
        dataset.typed = true;
      } else if ((untypedDatasets == null ? void 0 : untypedDatasets.length) === 1) return untypedDatasets[0];
      else _addIssue(this, "type", dataset, config$1, { issues: /* @__PURE__ */ _subIssues(untypedDatasets) });
      return dataset;
    }
  });
}
function parse3(schema, input, config$1) {
  const dataset = schema["~run"]({ value: input }, /* @__PURE__ */ getGlobalConfig(config$1));
  if (dataset.issues) throw new ValiError(dataset.issues);
  return dataset.value;
}
// @__NO_SIDE_EFFECTS__
function pipe(...pipe$1) {
  return _standardSchema({
    ...pipe$1[0],
    pipe: pipe$1,
    "~run"(dataset, config$1) {
      for (const item of pipe$1) if (item.kind !== "metadata") {
        if (dataset.issues && (item.kind === "schema" || item.kind === "transformation")) {
          dataset.typed = false;
          break;
        }
        if (!dataset.issues || !config$1.abortEarly && !config$1.abortPipeEarly) dataset = item["~run"](dataset, config$1);
      }
      return dataset;
    }
  });
}

// node_modules/neuroglancer/lib/kvstore/icechunk/decode_utils.js
init_legacy_browser();

// node_modules/msgpackr/index.js
init_legacy_browser();

// node_modules/msgpackr/pack.js
init_legacy_browser();

// node_modules/msgpackr/unpack.js
init_legacy_browser();
var decoder;
try {
  decoder = new TextDecoder();
} catch (error) {
}
var src;
var srcEnd;
var position = 0;
var EMPTY_ARRAY = [];
var strings = EMPTY_ARRAY;
var stringPosition = 0;
var currentUnpackr = {};
var currentStructures;
var srcString;
var srcStringStart = 0;
var srcStringEnd = 0;
var bundledStrings;
var referenceMap;
var currentExtensions = [];
var dataView;
var defaultOptions = {
  useRecords: false,
  mapsAsObjects: true
};
var C1Type = class {
};
var C1 = new C1Type();
C1.name = "MessagePack 0xC1";
var sequentialMode = false;
var inlineObjectReadThreshold = 2;
var readStruct;
var onLoadedStructures;
var onSaveState;
var Unpackr = class _Unpackr {
  constructor(options) {
    if (options) {
      if (options.useRecords === false && options.mapsAsObjects === void 0)
        options.mapsAsObjects = true;
      if (options.sequential && options.trusted !== false) {
        options.trusted = true;
        if (!options.structures && options.useRecords != false) {
          options.structures = [];
          if (!options.maxSharedStructures)
            options.maxSharedStructures = 0;
        }
      }
      if (options.structures)
        options.structures.sharedLength = options.structures.length;
      else if (options.getStructures) {
        (options.structures = []).uninitialized = true;
        options.structures.sharedLength = 0;
      }
      if (options.int64AsNumber) {
        options.int64AsType = "number";
      }
    }
    Object.assign(this, options);
  }
  unpack(source, options) {
    if (src) {
      return saveState(() => {
        clearSource();
        return this ? this.unpack(source, options) : _Unpackr.prototype.unpack.call(defaultOptions, source, options);
      });
    }
    if (!source.buffer && source.constructor === ArrayBuffer)
      source = typeof Buffer !== "undefined" ? Buffer.from(source) : new Uint8Array(source);
    if (typeof options === "object") {
      srcEnd = options.end || source.length;
      position = options.start || 0;
    } else {
      position = 0;
      srcEnd = options > -1 ? options : source.length;
    }
    stringPosition = 0;
    srcStringEnd = 0;
    srcString = null;
    strings = EMPTY_ARRAY;
    bundledStrings = null;
    src = source;
    try {
      dataView = source.dataView || (source.dataView = new DataView(source.buffer, source.byteOffset, source.byteLength));
    } catch (error) {
      src = null;
      if (source instanceof Uint8Array)
        throw error;
      throw new Error("Source must be a Uint8Array or Buffer but was a " + (source && typeof source == "object" ? source.constructor.name : typeof source));
    }
    if (this instanceof _Unpackr) {
      currentUnpackr = this;
      if (this.structures) {
        currentStructures = this.structures;
        return checkedRead(options);
      } else if (!currentStructures || currentStructures.length > 0) {
        currentStructures = [];
      }
    } else {
      currentUnpackr = defaultOptions;
      if (!currentStructures || currentStructures.length > 0)
        currentStructures = [];
    }
    return checkedRead(options);
  }
  unpackMultiple(source, forEach3) {
    let values, lastPosition = 0;
    try {
      sequentialMode = true;
      let size = source.length;
      let value = this ? this.unpack(source, size) : defaultUnpackr.unpack(source, size);
      if (forEach3) {
        if (forEach3(value, lastPosition, position) === false) return;
        while (position < size) {
          lastPosition = position;
          if (forEach3(checkedRead(), lastPosition, position) === false) {
            return;
          }
        }
      } else {
        values = [value];
        while (position < size) {
          lastPosition = position;
          values.push(checkedRead());
        }
        return values;
      }
    } catch (error) {
      error.lastPosition = lastPosition;
      error.values = values;
      throw error;
    } finally {
      sequentialMode = false;
      clearSource();
    }
  }
  _mergeStructures(loadedStructures, existingStructures) {
    if (onLoadedStructures)
      loadedStructures = onLoadedStructures.call(this, loadedStructures);
    loadedStructures = loadedStructures || [];
    if (Object.isFrozen(loadedStructures))
      loadedStructures = loadedStructures.map((structure) => structure.slice(0));
    for (let i = 0, l = loadedStructures.length; i < l; i++) {
      let structure = loadedStructures[i];
      if (structure) {
        structure.isShared = true;
        if (i >= 32)
          structure.highByte = i - 32 >> 5;
      }
    }
    loadedStructures.sharedLength = loadedStructures.length;
    for (let id in existingStructures || []) {
      if (id >= 0) {
        let structure = loadedStructures[id];
        let existing = existingStructures[id];
        if (existing) {
          if (structure)
            (loadedStructures.restoreStructures || (loadedStructures.restoreStructures = []))[id] = structure;
          loadedStructures[id] = existing;
        }
      }
    }
    return this.structures = loadedStructures;
  }
  decode(source, options) {
    return this.unpack(source, options);
  }
};
function checkedRead(options) {
  try {
    if (!currentUnpackr.trusted && !sequentialMode) {
      let sharedLength = currentStructures.sharedLength || 0;
      if (sharedLength < currentStructures.length)
        currentStructures.length = sharedLength;
    }
    let result;
    if (currentUnpackr.randomAccessStructure && src[position] < 64 && src[position] >= 32 && readStruct) {
      result = readStruct(src, position, srcEnd, currentUnpackr);
      src = null;
      if (!(options && options.lazy) && result)
        result = result.toJSON();
      position = srcEnd;
    } else
      result = read2();
    if (bundledStrings) {
      position = bundledStrings.postBundlePosition;
      bundledStrings = null;
    }
    if (sequentialMode)
      currentStructures.restoreStructures = null;
    if (position == srcEnd) {
      if (currentStructures && currentStructures.restoreStructures)
        restoreStructures();
      currentStructures = null;
      src = null;
      if (referenceMap)
        referenceMap = null;
    } else if (position > srcEnd) {
      throw new Error("Unexpected end of MessagePack data");
    } else if (!sequentialMode) {
      let jsonView;
      try {
        jsonView = JSON.stringify(result, (_, value) => typeof value === "bigint" ? `${value}n` : value).slice(0, 100);
      } catch (error) {
        jsonView = "(JSON view not available " + error + ")";
      }
      throw new Error("Data read, but end of buffer not reached " + jsonView);
    }
    return result;
  } catch (error) {
    if (currentStructures && currentStructures.restoreStructures)
      restoreStructures();
    clearSource();
    if (error instanceof RangeError || error.message.startsWith("Unexpected end of buffer") || position > srcEnd) {
      error.incomplete = true;
    }
    throw error;
  }
}
function restoreStructures() {
  for (let id in currentStructures.restoreStructures) {
    currentStructures[id] = currentStructures.restoreStructures[id];
  }
  currentStructures.restoreStructures = null;
}
function read2() {
  let token = src[position++];
  if (token < 160) {
    if (token < 128) {
      if (token < 64)
        return token;
      else {
        let structure = currentStructures[token & 63] || currentUnpackr.getStructures && loadStructures()[token & 63];
        if (structure) {
          if (!structure.read) {
            structure.read = createStructureReader(structure, token & 63);
          }
          return structure.read();
        } else
          return token;
      }
    } else if (token < 144) {
      token -= 128;
      if (currentUnpackr.mapsAsObjects) {
        let object = {};
        for (let i = 0; i < token; i++) {
          let key = readKey();
          if (key === "__proto__")
            key = "__proto_";
          object[key] = read2();
        }
        return object;
      } else {
        let map2 = /* @__PURE__ */ new Map();
        for (let i = 0; i < token; i++) {
          map2.set(read2(), read2());
        }
        return map2;
      }
    } else {
      token -= 144;
      let array2 = new Array(token);
      for (let i = 0; i < token; i++) {
        array2[i] = read2();
      }
      if (currentUnpackr.freezeData)
        return Object.freeze(array2);
      return array2;
    }
  } else if (token < 192) {
    let length6 = token - 160;
    if (srcStringEnd >= position) {
      return srcString.slice(position - srcStringStart, (position += length6) - srcStringStart);
    }
    if (srcStringEnd == 0 && srcEnd < 140) {
      let string2 = length6 < 16 ? shortStringInJS(length6) : longStringInJS(length6);
      if (string2 != null)
        return string2;
    }
    return readFixedString(length6);
  } else {
    let value;
    switch (token) {
      case 192:
        return null;
      case 193:
        if (bundledStrings) {
          value = read2();
          if (value > 0)
            return bundledStrings[1].slice(bundledStrings.position1, bundledStrings.position1 += value);
          else
            return bundledStrings[0].slice(bundledStrings.position0, bundledStrings.position0 -= value);
        }
        return C1;
      // "never-used", return special object to denote that
      case 194:
        return false;
      case 195:
        return true;
      case 196:
        value = src[position++];
        if (value === void 0)
          throw new Error("Unexpected end of buffer");
        return readBin(value);
      case 197:
        value = dataView.getUint16(position);
        position += 2;
        return readBin(value);
      case 198:
        value = dataView.getUint32(position);
        position += 4;
        return readBin(value);
      case 199:
        return readExt(src[position++]);
      case 200:
        value = dataView.getUint16(position);
        position += 2;
        return readExt(value);
      case 201:
        value = dataView.getUint32(position);
        position += 4;
        return readExt(value);
      case 202:
        value = dataView.getFloat32(position);
        if (currentUnpackr.useFloat32 > 2) {
          let multiplier = mult10[(src[position] & 127) << 1 | src[position + 1] >> 7];
          position += 4;
          return (multiplier * value + (value > 0 ? 0.5 : -0.5) >> 0) / multiplier;
        }
        position += 4;
        return value;
      case 203:
        value = dataView.getFloat64(position);
        position += 8;
        return value;
      // uint handlers
      case 204:
        return src[position++];
      case 205:
        value = dataView.getUint16(position);
        position += 2;
        return value;
      case 206:
        value = dataView.getUint32(position);
        position += 4;
        return value;
      case 207:
        if (currentUnpackr.int64AsType === "number") {
          value = dataView.getUint32(position) * 4294967296;
          value += dataView.getUint32(position + 4);
        } else if (currentUnpackr.int64AsType === "string") {
          value = dataView.getBigUint64(position).toString();
        } else if (currentUnpackr.int64AsType === "auto") {
          value = dataView.getBigUint64(position);
          if (value <= BigInt(2) << BigInt(52)) value = Number(value);
        } else
          value = dataView.getBigUint64(position);
        position += 8;
        return value;
      // int handlers
      case 208:
        return dataView.getInt8(position++);
      case 209:
        value = dataView.getInt16(position);
        position += 2;
        return value;
      case 210:
        value = dataView.getInt32(position);
        position += 4;
        return value;
      case 211:
        if (currentUnpackr.int64AsType === "number") {
          value = dataView.getInt32(position) * 4294967296;
          value += dataView.getUint32(position + 4);
        } else if (currentUnpackr.int64AsType === "string") {
          value = dataView.getBigInt64(position).toString();
        } else if (currentUnpackr.int64AsType === "auto") {
          value = dataView.getBigInt64(position);
          if (value >= BigInt(-2) << BigInt(52) && value <= BigInt(2) << BigInt(52)) value = Number(value);
        } else
          value = dataView.getBigInt64(position);
        position += 8;
        return value;
      case 212:
        value = src[position++];
        if (value == 114) {
          return recordDefinition(src[position++] & 63);
        } else {
          let extension = currentExtensions[value];
          if (extension) {
            if (extension.read) {
              position++;
              return extension.read(read2());
            } else if (extension.noBuffer) {
              position++;
              return extension();
            } else
              return extension(src.subarray(position, ++position));
          } else
            throw new Error("Unknown extension " + value);
        }
      case 213:
        value = src[position];
        if (value == 114) {
          position++;
          return recordDefinition(src[position++] & 63, src[position++]);
        } else
          return readExt(2);
      case 214:
        return readExt(4);
      case 215:
        return readExt(8);
      case 216:
        return readExt(16);
      case 217:
        value = src[position++];
        if (srcStringEnd >= position) {
          return srcString.slice(position - srcStringStart, (position += value) - srcStringStart);
        }
        return readString8(value);
      case 218:
        value = dataView.getUint16(position);
        position += 2;
        if (srcStringEnd >= position) {
          return srcString.slice(position - srcStringStart, (position += value) - srcStringStart);
        }
        return readString16(value);
      case 219:
        value = dataView.getUint32(position);
        position += 4;
        if (srcStringEnd >= position) {
          return srcString.slice(position - srcStringStart, (position += value) - srcStringStart);
        }
        return readString32(value);
      case 220:
        value = dataView.getUint16(position);
        position += 2;
        return readArray(value);
      case 221:
        value = dataView.getUint32(position);
        position += 4;
        return readArray(value);
      case 222:
        value = dataView.getUint16(position);
        position += 2;
        return readMap(value);
      case 223:
        value = dataView.getUint32(position);
        position += 4;
        return readMap(value);
      default:
        if (token >= 224)
          return token - 256;
        if (token === void 0) {
          let error = new Error("Unexpected end of MessagePack data");
          error.incomplete = true;
          throw error;
        }
        throw new Error("Unknown MessagePack token " + token);
    }
  }
}
var validName = /^[a-zA-Z_$][a-zA-Z\d_$]*$/;
function createStructureReader(structure, firstId) {
  function readObject() {
    if (readObject.count++ > inlineObjectReadThreshold) {
      let optimizedReadObject;
      try {
        optimizedReadObject = structure.read = new Function("r", "return function(){return " + (currentUnpackr.freezeData ? "Object.freeze" : "") + "({" + structure.map((key) => key === "__proto__" ? "__proto_:r()" : validName.test(key) ? key + ":r()" : "[" + JSON.stringify(key) + "]:r()").join(",") + "})}")(read2);
      } catch (error) {
        inlineObjectReadThreshold = Infinity;
        return readObject();
      }
      structure.read0 = optimizedReadObject;
      if (structure.highByte === 0)
        structure.read = createSecondByteReader(firstId, structure.read);
      return optimizedReadObject();
    }
    let object = {};
    for (let i = 0, l = structure.length; i < l; i++) {
      let key = structure[i];
      if (key === "__proto__")
        key = "__proto_";
      object[key] = read2();
    }
    if (currentUnpackr.freezeData)
      return Object.freeze(object);
    return object;
  }
  readObject.count = 0;
  structure.read0 = readObject;
  if (structure.highByte === 0) {
    return createSecondByteReader(firstId, readObject);
  }
  return readObject;
}
var createSecondByteReader = (firstId, read0) => {
  return function() {
    let highByte = src[position++];
    if (highByte === 0)
      return read0();
    let id = firstId < 32 ? -(firstId + (highByte << 5)) : firstId + (highByte << 5);
    let structure = currentStructures[id] || loadStructures()[id];
    if (!structure) {
      throw new Error("Record id is not defined for " + id);
    }
    if (!structure.read)
      structure.read = createStructureReader(structure, firstId);
    return structure.read();
  };
};
function loadStructures() {
  let loadedStructures = saveState(() => {
    src = null;
    return currentUnpackr.getStructures();
  });
  return currentStructures = currentUnpackr._mergeStructures(loadedStructures, currentStructures);
}
var readFixedString = readStringJS;
var readString8 = readStringJS;
var readString16 = readStringJS;
var readString32 = readStringJS;
function readStringJS(length6) {
  let result;
  if (length6 < 16) {
    if (result = shortStringInJS(length6))
      return result;
  }
  if (length6 > 64 && decoder)
    return decoder.decode(src.subarray(position, position += length6));
  const end = position + length6;
  const units = [];
  result = "";
  while (position < end) {
    const byte1 = src[position++];
    if ((byte1 & 128) === 0) {
      units.push(byte1);
    } else if ((byte1 & 224) === 192) {
      const byte2 = src[position++] & 63;
      const codePoint = (byte1 & 31) << 6 | byte2;
      if (codePoint < 128) {
        units.push(65533);
      } else {
        units.push(codePoint);
      }
    } else if ((byte1 & 240) === 224) {
      const byte2 = src[position++] & 63;
      const byte3 = src[position++] & 63;
      const codePoint = (byte1 & 31) << 12 | byte2 << 6 | byte3;
      if (codePoint < 2048 || codePoint >= 55296 && codePoint <= 57343) {
        units.push(65533);
      } else {
        units.push(codePoint);
      }
    } else if ((byte1 & 248) === 240) {
      const byte2 = src[position++] & 63;
      const byte3 = src[position++] & 63;
      const byte4 = src[position++] & 63;
      let unit = (byte1 & 7) << 18 | byte2 << 12 | byte3 << 6 | byte4;
      if (unit < 65536 || unit > 1114111) {
        units.push(65533);
      } else if (unit > 65535) {
        unit -= 65536;
        units.push(unit >>> 10 & 1023 | 55296);
        unit = 56320 | unit & 1023;
        units.push(unit);
      } else {
        units.push(unit);
      }
    } else {
      units.push(65533);
    }
    if (units.length >= 4096) {
      result += fromCharCode.apply(String, units);
      units.length = 0;
    }
  }
  if (units.length > 0) {
    result += fromCharCode.apply(String, units);
  }
  return result;
}
function readArray(length6) {
  let array2 = new Array(length6);
  for (let i = 0; i < length6; i++) {
    array2[i] = read2();
  }
  if (currentUnpackr.freezeData)
    return Object.freeze(array2);
  return array2;
}
function readMap(length6) {
  if (currentUnpackr.mapsAsObjects) {
    let object = {};
    for (let i = 0; i < length6; i++) {
      let key = readKey();
      if (key === "__proto__")
        key = "__proto_";
      object[key] = read2();
    }
    return object;
  } else {
    let map2 = /* @__PURE__ */ new Map();
    for (let i = 0; i < length6; i++) {
      map2.set(read2(), read2());
    }
    return map2;
  }
}
var fromCharCode = String.fromCharCode;
function longStringInJS(length6) {
  let start = position;
  let bytes = new Array(length6);
  for (let i = 0; i < length6; i++) {
    const byte = src[position++];
    if ((byte & 128) > 0) {
      position = start;
      return;
    }
    bytes[i] = byte;
  }
  return fromCharCode.apply(String, bytes);
}
function shortStringInJS(length6) {
  if (length6 < 4) {
    if (length6 < 2) {
      if (length6 === 0)
        return "";
      else {
        let a = src[position++];
        if ((a & 128) > 1) {
          position -= 1;
          return;
        }
        return fromCharCode(a);
      }
    } else {
      let a = src[position++];
      let b = src[position++];
      if ((a & 128) > 0 || (b & 128) > 0) {
        position -= 2;
        return;
      }
      if (length6 < 3)
        return fromCharCode(a, b);
      let c = src[position++];
      if ((c & 128) > 0) {
        position -= 3;
        return;
      }
      return fromCharCode(a, b, c);
    }
  } else {
    let a = src[position++];
    let b = src[position++];
    let c = src[position++];
    let d = src[position++];
    if ((a & 128) > 0 || (b & 128) > 0 || (c & 128) > 0 || (d & 128) > 0) {
      position -= 4;
      return;
    }
    if (length6 < 6) {
      if (length6 === 4)
        return fromCharCode(a, b, c, d);
      else {
        let e = src[position++];
        if ((e & 128) > 0) {
          position -= 5;
          return;
        }
        return fromCharCode(a, b, c, d, e);
      }
    } else if (length6 < 8) {
      let e = src[position++];
      let f = src[position++];
      if ((e & 128) > 0 || (f & 128) > 0) {
        position -= 6;
        return;
      }
      if (length6 < 7)
        return fromCharCode(a, b, c, d, e, f);
      let g = src[position++];
      if ((g & 128) > 0) {
        position -= 7;
        return;
      }
      return fromCharCode(a, b, c, d, e, f, g);
    } else {
      let e = src[position++];
      let f = src[position++];
      let g = src[position++];
      let h = src[position++];
      if ((e & 128) > 0 || (f & 128) > 0 || (g & 128) > 0 || (h & 128) > 0) {
        position -= 8;
        return;
      }
      if (length6 < 10) {
        if (length6 === 8)
          return fromCharCode(a, b, c, d, e, f, g, h);
        else {
          let i = src[position++];
          if ((i & 128) > 0) {
            position -= 9;
            return;
          }
          return fromCharCode(a, b, c, d, e, f, g, h, i);
        }
      } else if (length6 < 12) {
        let i = src[position++];
        let j = src[position++];
        if ((i & 128) > 0 || (j & 128) > 0) {
          position -= 10;
          return;
        }
        if (length6 < 11)
          return fromCharCode(a, b, c, d, e, f, g, h, i, j);
        let k = src[position++];
        if ((k & 128) > 0) {
          position -= 11;
          return;
        }
        return fromCharCode(a, b, c, d, e, f, g, h, i, j, k);
      } else {
        let i = src[position++];
        let j = src[position++];
        let k = src[position++];
        let l = src[position++];
        if ((i & 128) > 0 || (j & 128) > 0 || (k & 128) > 0 || (l & 128) > 0) {
          position -= 12;
          return;
        }
        if (length6 < 14) {
          if (length6 === 12)
            return fromCharCode(a, b, c, d, e, f, g, h, i, j, k, l);
          else {
            let m = src[position++];
            if ((m & 128) > 0) {
              position -= 13;
              return;
            }
            return fromCharCode(a, b, c, d, e, f, g, h, i, j, k, l, m);
          }
        } else {
          let m = src[position++];
          let n = src[position++];
          if ((m & 128) > 0 || (n & 128) > 0) {
            position -= 14;
            return;
          }
          if (length6 < 15)
            return fromCharCode(a, b, c, d, e, f, g, h, i, j, k, l, m, n);
          let o = src[position++];
          if ((o & 128) > 0) {
            position -= 15;
            return;
          }
          return fromCharCode(a, b, c, d, e, f, g, h, i, j, k, l, m, n, o);
        }
      }
    }
  }
}
function readOnlyJSString() {
  let token = src[position++];
  let length6;
  if (token < 192) {
    length6 = token - 160;
  } else {
    switch (token) {
      case 217:
        length6 = src[position++];
        break;
      case 218:
        length6 = dataView.getUint16(position);
        position += 2;
        break;
      case 219:
        length6 = dataView.getUint32(position);
        position += 4;
        break;
      default:
        throw new Error("Expected string");
    }
  }
  return readStringJS(length6);
}
function readBin(length6) {
  return currentUnpackr.copyBuffers ? (
    // specifically use the copying slice (not the node one)
    Uint8Array.prototype.slice.call(src, position, position += length6)
  ) : src.subarray(position, position += length6);
}
function readExt(length6) {
  let type = src[position++];
  if (currentExtensions[type]) {
    let end;
    return currentExtensions[type](src.subarray(position, end = position += length6), (readPosition) => {
      position = readPosition;
      try {
        return read2();
      } finally {
        position = end;
      }
    });
  } else
    throw new Error("Unknown extension type " + type);
}
var keyCache = new Array(4096);
function readKey() {
  let length6 = src[position++];
  if (length6 >= 160 && length6 < 192) {
    length6 = length6 - 160;
    if (srcStringEnd >= position)
      return srcString.slice(position - srcStringStart, (position += length6) - srcStringStart);
    else if (!(srcStringEnd == 0 && srcEnd < 180))
      return readFixedString(length6);
  } else {
    position--;
    return asSafeString(read2());
  }
  let key = (length6 << 5 ^ (length6 > 1 ? dataView.getUint16(position) : length6 > 0 ? src[position] : 0)) & 4095;
  let entry = keyCache[key];
  let checkPosition = position;
  let end = position + length6 - 3;
  let chunk;
  let i = 0;
  if (entry && entry.bytes == length6) {
    while (checkPosition < end) {
      chunk = dataView.getUint32(checkPosition);
      if (chunk != entry[i++]) {
        checkPosition = 1879048192;
        break;
      }
      checkPosition += 4;
    }
    end += 3;
    while (checkPosition < end) {
      chunk = src[checkPosition++];
      if (chunk != entry[i++]) {
        checkPosition = 1879048192;
        break;
      }
    }
    if (checkPosition === end) {
      position = checkPosition;
      return entry.string;
    }
    end -= 3;
    checkPosition = position;
  }
  entry = [];
  keyCache[key] = entry;
  entry.bytes = length6;
  while (checkPosition < end) {
    chunk = dataView.getUint32(checkPosition);
    entry.push(chunk);
    checkPosition += 4;
  }
  end += 3;
  while (checkPosition < end) {
    chunk = src[checkPosition++];
    entry.push(chunk);
  }
  let string2 = length6 < 16 ? shortStringInJS(length6) : longStringInJS(length6);
  if (string2 != null)
    return entry.string = string2;
  return entry.string = readFixedString(length6);
}
function asSafeString(property) {
  if (typeof property === "string") return property;
  if (typeof property === "number" || typeof property === "boolean" || typeof property === "bigint") return property.toString();
  if (property == null) return property + "";
  if (currentUnpackr.allowArraysInMapKeys && Array.isArray(property) && property.flat().every((item) => ["string", "number", "boolean", "bigint"].includes(typeof item))) {
    return property.flat().toString();
  }
  throw new Error(`Invalid property type for record: ${typeof property}`);
}
var recordDefinition = (id, highByte) => {
  let structure = read2().map(asSafeString);
  let firstByte = id;
  if (highByte !== void 0) {
    id = id < 32 ? -((highByte << 5) + id) : (highByte << 5) + id;
    structure.highByte = highByte;
  }
  let existingStructure = currentStructures[id];
  if (existingStructure && (existingStructure.isShared || sequentialMode)) {
    (currentStructures.restoreStructures || (currentStructures.restoreStructures = []))[id] = existingStructure;
  }
  currentStructures[id] = structure;
  structure.read = createStructureReader(structure, firstByte);
  return (structure.read0 || structure.read)();
};
currentExtensions[0] = () => {
};
currentExtensions[0].noBuffer = true;
currentExtensions[66] = (data) => {
  let headLength = data.byteLength % 8 || 8;
  let head = BigInt(data[0] & 128 ? data[0] - 256 : data[0]);
  for (let i = 1; i < headLength; i++) {
    head <<= BigInt(8);
    head += BigInt(data[i]);
  }
  if (data.byteLength !== headLength) {
    let view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    let decode2 = (start, end) => {
      let length6 = end - start;
      if (length6 <= 40) {
        let out = view.getBigUint64(start);
        for (let i = start + 8; i < end; i += 8) {
          out <<= BigInt(64);
          out |= view.getBigUint64(i);
        }
        return out;
      }
      let middle = start + (length6 >> 4 << 3);
      let left = decode2(start, middle);
      let right = decode2(middle, end);
      return left << BigInt((end - middle) * 8) | right;
    };
    head = head << BigInt((view.byteLength - headLength) * 8) | decode2(headLength, view.byteLength);
  }
  return head;
};
var errors = {
  Error,
  EvalError,
  RangeError,
  ReferenceError,
  SyntaxError,
  TypeError,
  URIError,
  AggregateError: typeof AggregateError === "function" ? AggregateError : null
};
currentExtensions[101] = () => {
  let data = read2();
  if (!errors[data[0]]) {
    let error = Error(data[1], { cause: data[2] });
    error.name = data[0];
    return error;
  }
  return errors[data[0]](data[1], { cause: data[2] });
};
currentExtensions[105] = (data) => {
  if (currentUnpackr.structuredClone === false) throw new Error("Structured clone extension is disabled");
  let id = dataView.getUint32(position - 4);
  if (!referenceMap)
    referenceMap = /* @__PURE__ */ new Map();
  let token = src[position];
  let target2;
  if (token >= 144 && token < 160 || token == 220 || token == 221)
    target2 = [];
  else if (token >= 128 && token < 144 || token == 222 || token == 223)
    target2 = /* @__PURE__ */ new Map();
  else if ((token >= 199 && token <= 201 || token >= 212 && token <= 216) && src[position + 1] === 115)
    target2 = /* @__PURE__ */ new Set();
  else
    target2 = {};
  let refEntry = { target: target2 };
  referenceMap.set(id, refEntry);
  let targetProperties = read2();
  if (!refEntry.used) {
    return refEntry.target = targetProperties;
  } else {
    Object.assign(target2, targetProperties);
  }
  if (target2 instanceof Map)
    for (let [k, v] of targetProperties.entries()) target2.set(k, v);
  if (target2 instanceof Set)
    for (let i of Array.from(targetProperties)) target2.add(i);
  return target2;
};
currentExtensions[112] = (data) => {
  if (currentUnpackr.structuredClone === false) throw new Error("Structured clone extension is disabled");
  let id = dataView.getUint32(position - 4);
  let refEntry = referenceMap.get(id);
  refEntry.used = true;
  return refEntry.target;
};
currentExtensions[115] = () => new Set(read2());
var typedArrays = ["Int8", "Uint8", "Uint8Clamped", "Int16", "Uint16", "Int32", "Uint32", "Float32", "Float64", "BigInt64", "BigUint64"].map((type) => type + "Array");
var glbl = typeof globalThis === "object" ? globalThis : window;
currentExtensions[116] = (data) => {
  let typeCode = data[0];
  let buffer = Uint8Array.prototype.slice.call(data, 1).buffer;
  let typedArrayName = typedArrays[typeCode];
  if (!typedArrayName) {
    if (typeCode === 16) return buffer;
    if (typeCode === 17) return new DataView(buffer);
    throw new Error("Could not find typed array for code " + typeCode);
  }
  return new glbl[typedArrayName](buffer);
};
currentExtensions[120] = () => {
  let data = read2();
  return new RegExp(data[0], data[1]);
};
var TEMP_BUNDLE = [];
currentExtensions[98] = (data) => {
  let dataSize = (data[0] << 24) + (data[1] << 16) + (data[2] << 8) + data[3];
  let dataPosition = position;
  position += dataSize - data.length;
  bundledStrings = TEMP_BUNDLE;
  bundledStrings = [readOnlyJSString(), readOnlyJSString()];
  bundledStrings.position0 = 0;
  bundledStrings.position1 = 0;
  bundledStrings.postBundlePosition = position;
  position = dataPosition;
  return read2();
};
currentExtensions[255] = (data) => {
  if (data.length == 4)
    return new Date((data[0] * 16777216 + (data[1] << 16) + (data[2] << 8) + data[3]) * 1e3);
  else if (data.length == 8)
    return new Date(
      ((data[0] << 22) + (data[1] << 14) + (data[2] << 6) + (data[3] >> 2)) / 1e6 + ((data[3] & 3) * 4294967296 + data[4] * 16777216 + (data[5] << 16) + (data[6] << 8) + data[7]) * 1e3
    );
  else if (data.length == 12)
    return new Date(
      ((data[0] << 24) + (data[1] << 16) + (data[2] << 8) + data[3]) / 1e6 + ((data[4] & 128 ? -281474976710656 : 0) + data[6] * 1099511627776 + data[7] * 4294967296 + data[8] * 16777216 + (data[9] << 16) + (data[10] << 8) + data[11]) * 1e3
    );
  else
    return /* @__PURE__ */ new Date("invalid");
};
function saveState(callback) {
  if (onSaveState)
    onSaveState();
  let savedSrcEnd = srcEnd;
  let savedPosition = position;
  let savedStringPosition = stringPosition;
  let savedSrcStringStart = srcStringStart;
  let savedSrcStringEnd = srcStringEnd;
  let savedSrcString = srcString;
  let savedStrings = strings;
  let savedReferenceMap = referenceMap;
  let savedBundledStrings = bundledStrings;
  let savedSrc = new Uint8Array(src.slice(0, srcEnd));
  let savedStructures = currentStructures;
  let savedStructuresContents = currentStructures.slice(0, currentStructures.length);
  let savedPackr = currentUnpackr;
  let savedSequentialMode = sequentialMode;
  let value = callback();
  srcEnd = savedSrcEnd;
  position = savedPosition;
  stringPosition = savedStringPosition;
  srcStringStart = savedSrcStringStart;
  srcStringEnd = savedSrcStringEnd;
  srcString = savedSrcString;
  strings = savedStrings;
  referenceMap = savedReferenceMap;
  bundledStrings = savedBundledStrings;
  src = savedSrc;
  sequentialMode = savedSequentialMode;
  currentStructures = savedStructures;
  currentStructures.splice(0, currentStructures.length, ...savedStructuresContents);
  currentUnpackr = savedPackr;
  dataView = new DataView(src.buffer, src.byteOffset, src.byteLength);
  return value;
}
function clearSource() {
  src = null;
  referenceMap = null;
  currentStructures = null;
}
var mult10 = new Array(147);
for (let i = 0; i < 256; i++) {
  mult10[i] = +("1e" + Math.floor(45.15 - i * 0.30103));
}
var defaultUnpackr = new Unpackr({ useRecords: false });
var unpack = defaultUnpackr.unpack;
var unpackMultiple = defaultUnpackr.unpackMultiple;
var decode = defaultUnpackr.unpack;
var FLOAT32_OPTIONS = {
  NEVER: 0,
  ALWAYS: 1,
  DECIMAL_ROUND: 3,
  DECIMAL_FIT: 4
};
var f32Array = new Float32Array(1);
var u8Array = new Uint8Array(f32Array.buffer, 0, 4);

// node_modules/msgpackr/pack.js
var textEncoder;
try {
  textEncoder = new TextEncoder();
} catch (error) {
}
var extensions;
var extensionClasses;
var hasNodeBuffer = typeof Buffer !== "undefined";
var ByteArrayAllocate = hasNodeBuffer ? function(length6) {
  return Buffer.allocUnsafeSlow(length6);
} : Uint8Array;
var ByteArray = hasNodeBuffer ? Buffer : Uint8Array;
var MAX_BUFFER_SIZE = hasNodeBuffer ? 4294967296 : 2144337920;
var target;
var keysTarget;
var targetView;
var position2 = 0;
var safeEnd;
var bundledStrings2 = null;
var writeStructSlots;
var MAX_BUNDLE_SIZE = 21760;
var hasNonLatin = /[\u0080-\uFFFF]/;
var RECORD_SYMBOL = Symbol("record-id");
var Packr = class extends Unpackr {
  constructor(options) {
    super(options);
    this.offset = 0;
    let typeBuffer;
    let start;
    let hasSharedUpdate;
    let structures;
    let referenceMap2;
    let encodeUtf8 = ByteArray.prototype.utf8Write ? function(string2, position3) {
      return target.utf8Write(string2, position3, target.byteLength - position3);
    } : textEncoder && textEncoder.encodeInto ? function(string2, position3) {
      return textEncoder.encodeInto(string2, target.subarray(position3)).written;
    } : false;
    let packr = this;
    if (!options)
      options = {};
    let isSequential = options && options.sequential;
    let hasSharedStructures = options.structures || options.saveStructures;
    let maxSharedStructures = options.maxSharedStructures;
    if (maxSharedStructures == null)
      maxSharedStructures = hasSharedStructures ? 32 : 0;
    if (maxSharedStructures > 8160)
      throw new Error("Maximum maxSharedStructure is 8160");
    if (options.structuredClone && options.moreTypes == void 0) {
      this.moreTypes = true;
    }
    let maxOwnStructures = options.maxOwnStructures;
    if (maxOwnStructures == null)
      maxOwnStructures = hasSharedStructures ? 32 : 64;
    if (!this.structures && options.useRecords != false)
      this.structures = [];
    let useTwoByteRecords = maxSharedStructures > 32 || maxOwnStructures + maxSharedStructures > 64;
    let sharedLimitId = maxSharedStructures + 64;
    let maxStructureId = maxSharedStructures + maxOwnStructures + 64;
    if (maxStructureId > 8256) {
      throw new Error("Maximum maxSharedStructure + maxOwnStructure is 8192");
    }
    let recordIdsToRemove = [];
    let transitionsCount = 0;
    let serializationsSinceTransitionRebuild = 0;
    this.pack = this.encode = function(value, encodeOptions) {
      if (!target) {
        target = new ByteArrayAllocate(8192);
        targetView = target.dataView || (target.dataView = new DataView(target.buffer, 0, 8192));
        position2 = 0;
      }
      safeEnd = target.length - 10;
      if (safeEnd - position2 < 2048) {
        target = new ByteArrayAllocate(target.length);
        targetView = target.dataView || (target.dataView = new DataView(target.buffer, 0, target.length));
        safeEnd = target.length - 10;
        position2 = 0;
      } else
        position2 = position2 + 7 & 2147483640;
      start = position2;
      if (encodeOptions & RESERVE_START_SPACE) position2 += encodeOptions & 255;
      referenceMap2 = packr.structuredClone ? /* @__PURE__ */ new Map() : null;
      if (packr.bundleStrings && typeof value !== "string") {
        bundledStrings2 = [];
        bundledStrings2.size = Infinity;
      } else
        bundledStrings2 = null;
      structures = packr.structures;
      if (structures) {
        if (structures.uninitialized)
          structures = packr._mergeStructures(packr.getStructures());
        let sharedLength = structures.sharedLength || 0;
        if (sharedLength > maxSharedStructures) {
          throw new Error("Shared structures is larger than maximum shared structures, try increasing maxSharedStructures to " + structures.sharedLength);
        }
        if (!structures.transitions) {
          structures.transitions = /* @__PURE__ */ Object.create(null);
          for (let i = 0; i < sharedLength; i++) {
            let keys = structures[i];
            if (!keys)
              continue;
            let nextTransition, transition = structures.transitions;
            for (let j = 0, l = keys.length; j < l; j++) {
              let key = keys[j];
              nextTransition = transition[key];
              if (!nextTransition) {
                nextTransition = transition[key] = /* @__PURE__ */ Object.create(null);
              }
              transition = nextTransition;
            }
            transition[RECORD_SYMBOL] = i + 64;
          }
          this.lastNamedStructuresLength = sharedLength;
        }
        if (!isSequential) {
          structures.nextId = sharedLength + 64;
        }
      }
      if (hasSharedUpdate)
        hasSharedUpdate = false;
      let encodingError;
      try {
        if (packr.randomAccessStructure && !packr.readOnlyStructures && value && typeof value === "object") {
          if (value.constructor === Object) writeStruct(value);
          else if (value.constructor !== Map && !Array.isArray(value) && !extensionClasses.some((extClass) => value instanceof extClass)) {
            writeStruct(value.toJSON ? value.toJSON() : value);
          } else pack2(value);
        } else
          pack2(value);
        let lastBundle = bundledStrings2;
        if (bundledStrings2)
          writeBundles(start, pack2, 0);
        if (referenceMap2 && referenceMap2.idsToInsert) {
          let idsToInsert = referenceMap2.idsToInsert.sort((a, b) => a.offset > b.offset ? 1 : -1);
          let i = idsToInsert.length;
          let incrementPosition = -1;
          while (lastBundle && i > 0) {
            let insertionPoint = idsToInsert[--i].offset + start;
            if (insertionPoint < lastBundle.stringsPosition + start && incrementPosition === -1)
              incrementPosition = 0;
            if (insertionPoint > lastBundle.position + start) {
              if (incrementPosition >= 0)
                incrementPosition += 6;
            } else {
              if (incrementPosition >= 0) {
                targetView.setUint32(
                  lastBundle.position + start,
                  targetView.getUint32(lastBundle.position + start) + incrementPosition
                );
                incrementPosition = -1;
              }
              lastBundle = lastBundle.previous;
              i++;
            }
          }
          if (incrementPosition >= 0 && lastBundle) {
            targetView.setUint32(
              lastBundle.position + start,
              targetView.getUint32(lastBundle.position + start) + incrementPosition
            );
          }
          position2 += idsToInsert.length * 6;
          if (position2 > safeEnd)
            makeRoom(position2);
          packr.offset = position2;
          let serialized = insertIds(target.subarray(start, position2), idsToInsert);
          referenceMap2 = null;
          return serialized;
        }
        packr.offset = position2;
        if (encodeOptions & REUSE_BUFFER_MODE) {
          target.start = start;
          target.end = position2;
          return target;
        }
        return target.subarray(start, position2);
      } catch (error) {
        encodingError = error;
        throw error;
      } finally {
        if (structures) {
          resetStructures();
          if (hasSharedUpdate && packr.saveStructures) {
            let sharedLength = structures.sharedLength || 0;
            let returnBuffer = target.subarray(start, position2);
            let newSharedData = prepareStructures(structures, packr);
            if (!encodingError) {
              if (packr.saveStructures(newSharedData, newSharedData.isCompatible) === false) {
                structures.uninitialized = true;
                return packr.pack(value, encodeOptions);
              }
              packr.lastNamedStructuresLength = sharedLength;
              if (target.length > 1073741824) target = null;
              return returnBuffer;
            }
          }
        }
        if (target.length > 1073741824) target = null;
        if (encodeOptions & RESET_BUFFER_MODE)
          position2 = start;
      }
    };
    const resetStructures = () => {
      if (serializationsSinceTransitionRebuild < 10)
        serializationsSinceTransitionRebuild++;
      let sharedLength = structures.sharedLength || 0;
      if (structures.length > sharedLength && !isSequential)
        structures.length = sharedLength;
      if (transitionsCount > 1e4) {
        structures.transitions = null;
        serializationsSinceTransitionRebuild = 0;
        transitionsCount = 0;
        if (recordIdsToRemove.length > 0)
          recordIdsToRemove = [];
      } else if (recordIdsToRemove.length > 0 && !isSequential) {
        for (let i = 0, l = recordIdsToRemove.length; i < l; i++) {
          recordIdsToRemove[i][RECORD_SYMBOL] = 0;
        }
        recordIdsToRemove = [];
      }
    };
    const packArray = (value) => {
      var length6 = value.length;
      if (length6 < 16) {
        target[position2++] = 144 | length6;
      } else if (length6 < 65536) {
        target[position2++] = 220;
        target[position2++] = length6 >> 8;
        target[position2++] = length6 & 255;
      } else {
        target[position2++] = 221;
        targetView.setUint32(position2, length6);
        position2 += 4;
      }
      for (let i = 0; i < length6; i++) {
        pack2(value[i]);
      }
    };
    const pack2 = (value) => {
      if (position2 > safeEnd)
        target = makeRoom(position2);
      var type = typeof value;
      var length6;
      if (type === "string") {
        let strLength = value.length;
        if (bundledStrings2 && strLength >= 4 && strLength < 4096) {
          if ((bundledStrings2.size += strLength) > MAX_BUNDLE_SIZE) {
            let extStart;
            let maxBytes2 = (bundledStrings2[0] ? bundledStrings2[0].length * 3 + bundledStrings2[1].length : 0) + 10;
            if (position2 + maxBytes2 > safeEnd)
              target = makeRoom(position2 + maxBytes2);
            let lastBundle;
            if (bundledStrings2.position) {
              lastBundle = bundledStrings2;
              target[position2] = 200;
              position2 += 3;
              target[position2++] = 98;
              extStart = position2 - start;
              position2 += 4;
              writeBundles(start, pack2, 0);
              targetView.setUint16(extStart + start - 3, position2 - start - extStart);
            } else {
              target[position2++] = 214;
              target[position2++] = 98;
              extStart = position2 - start;
              position2 += 4;
            }
            bundledStrings2 = ["", ""];
            bundledStrings2.previous = lastBundle;
            bundledStrings2.size = 0;
            bundledStrings2.position = extStart;
          }
          let twoByte = hasNonLatin.test(value);
          bundledStrings2[twoByte ? 0 : 1] += value;
          target[position2++] = 193;
          pack2(twoByte ? -strLength : strLength);
          return;
        }
        let headerSize;
        if (strLength < 32) {
          headerSize = 1;
        } else if (strLength < 256) {
          headerSize = 2;
        } else if (strLength < 65536) {
          headerSize = 3;
        } else {
          headerSize = 5;
        }
        let maxBytes = strLength * 3;
        if (position2 + maxBytes > safeEnd)
          target = makeRoom(position2 + maxBytes);
        if (strLength < 64 || !encodeUtf8) {
          let i, c1, c2, strPosition = position2 + headerSize;
          for (i = 0; i < strLength; i++) {
            c1 = value.charCodeAt(i);
            if (c1 < 128) {
              target[strPosition++] = c1;
            } else if (c1 < 2048) {
              target[strPosition++] = c1 >> 6 | 192;
              target[strPosition++] = c1 & 63 | 128;
            } else if ((c1 & 64512) === 55296 && ((c2 = value.charCodeAt(i + 1)) & 64512) === 56320) {
              c1 = 65536 + ((c1 & 1023) << 10) + (c2 & 1023);
              i++;
              target[strPosition++] = c1 >> 18 | 240;
              target[strPosition++] = c1 >> 12 & 63 | 128;
              target[strPosition++] = c1 >> 6 & 63 | 128;
              target[strPosition++] = c1 & 63 | 128;
            } else {
              target[strPosition++] = c1 >> 12 | 224;
              target[strPosition++] = c1 >> 6 & 63 | 128;
              target[strPosition++] = c1 & 63 | 128;
            }
          }
          length6 = strPosition - position2 - headerSize;
        } else {
          length6 = encodeUtf8(value, position2 + headerSize);
        }
        if (length6 < 32) {
          target[position2++] = 160 | length6;
        } else if (length6 < 256) {
          if (headerSize < 2) {
            target.copyWithin(position2 + 2, position2 + 1, position2 + 1 + length6);
          }
          target[position2++] = 217;
          target[position2++] = length6;
        } else if (length6 < 65536) {
          if (headerSize < 3) {
            target.copyWithin(position2 + 3, position2 + 2, position2 + 2 + length6);
          }
          target[position2++] = 218;
          target[position2++] = length6 >> 8;
          target[position2++] = length6 & 255;
        } else {
          if (headerSize < 5) {
            target.copyWithin(position2 + 5, position2 + 3, position2 + 3 + length6);
          }
          target[position2++] = 219;
          targetView.setUint32(position2, length6);
          position2 += 4;
        }
        position2 += length6;
      } else if (type === "number") {
        if (value >>> 0 === value) {
          if (value < 32 || value < 128 && this.useRecords === false || value < 64 && !this.randomAccessStructure) {
            target[position2++] = value;
          } else if (value < 256) {
            target[position2++] = 204;
            target[position2++] = value;
          } else if (value < 65536) {
            target[position2++] = 205;
            target[position2++] = value >> 8;
            target[position2++] = value & 255;
          } else {
            target[position2++] = 206;
            targetView.setUint32(position2, value);
            position2 += 4;
          }
        } else if (value >> 0 === value) {
          if (value >= -32) {
            target[position2++] = 256 + value;
          } else if (value >= -128) {
            target[position2++] = 208;
            target[position2++] = value + 256;
          } else if (value >= -32768) {
            target[position2++] = 209;
            targetView.setInt16(position2, value);
            position2 += 2;
          } else {
            target[position2++] = 210;
            targetView.setInt32(position2, value);
            position2 += 4;
          }
        } else {
          let useFloat32;
          if ((useFloat32 = this.useFloat32) > 0 && value < 4294967296 && value >= -2147483648) {
            target[position2++] = 202;
            targetView.setFloat32(position2, value);
            let xShifted;
            if (useFloat32 < 4 || // this checks for rounding of numbers that were encoded in 32-bit float to nearest significant decimal digit that could be preserved
            (xShifted = value * mult10[(target[position2] & 127) << 1 | target[position2 + 1] >> 7]) >> 0 === xShifted) {
              position2 += 4;
              return;
            } else
              position2--;
          }
          target[position2++] = 203;
          targetView.setFloat64(position2, value);
          position2 += 8;
        }
      } else if (type === "object" || type === "function") {
        if (!value)
          target[position2++] = 192;
        else {
          if (referenceMap2) {
            let referee = referenceMap2.get(value);
            if (referee) {
              if (!referee.id) {
                let idsToInsert = referenceMap2.idsToInsert || (referenceMap2.idsToInsert = []);
                referee.id = idsToInsert.push(referee);
              }
              target[position2++] = 214;
              target[position2++] = 112;
              targetView.setUint32(position2, referee.id);
              position2 += 4;
              return;
            } else
              referenceMap2.set(value, { offset: position2 - start });
          }
          let constructor = value.constructor;
          if (constructor === Object) {
            writeObject(value);
          } else if (constructor === Array) {
            packArray(value);
          } else if (constructor === Map) {
            if (this.mapAsEmptyObject) target[position2++] = 128;
            else {
              length6 = value.size;
              if (length6 < 16) {
                target[position2++] = 128 | length6;
              } else if (length6 < 65536) {
                target[position2++] = 222;
                target[position2++] = length6 >> 8;
                target[position2++] = length6 & 255;
              } else {
                target[position2++] = 223;
                targetView.setUint32(position2, length6);
                position2 += 4;
              }
              for (let [key, entryValue] of value) {
                pack2(key);
                pack2(entryValue);
              }
            }
          } else {
            for (let i = 0, l = extensions.length; i < l; i++) {
              let extensionClass = extensionClasses[i];
              if (value instanceof extensionClass) {
                let extension = extensions[i];
                if (extension.write) {
                  if (extension.type) {
                    target[position2++] = 212;
                    target[position2++] = extension.type;
                    target[position2++] = 0;
                  }
                  let writeResult = extension.write.call(this, value);
                  if (writeResult === value) {
                    if (Array.isArray(value)) {
                      packArray(value);
                    } else {
                      writeObject(value);
                    }
                  } else {
                    pack2(writeResult);
                  }
                  return;
                }
                let currentTarget = target;
                let currentTargetView = targetView;
                let currentPosition = position2;
                target = null;
                let result;
                try {
                  result = extension.pack.call(this, value, (size) => {
                    target = currentTarget;
                    currentTarget = null;
                    position2 += size;
                    if (position2 > safeEnd)
                      makeRoom(position2);
                    return {
                      target,
                      targetView,
                      position: position2 - size
                    };
                  }, pack2);
                } finally {
                  if (currentTarget) {
                    target = currentTarget;
                    targetView = currentTargetView;
                    position2 = currentPosition;
                    safeEnd = target.length - 10;
                  }
                }
                if (result) {
                  if (result.length + position2 > safeEnd)
                    makeRoom(result.length + position2);
                  position2 = writeExtensionData(result, target, position2, extension.type);
                }
                return;
              }
            }
            if (Array.isArray(value)) {
              packArray(value);
            } else {
              if (value.toJSON) {
                const json = value.toJSON();
                if (json !== value)
                  return pack2(json);
              }
              if (type === "function")
                return pack2(this.writeFunction && this.writeFunction(value));
              writeObject(value);
            }
          }
        }
      } else if (type === "boolean") {
        target[position2++] = value ? 195 : 194;
      } else if (type === "bigint") {
        if (value < 9223372036854776e3 && value >= -9223372036854776e3) {
          target[position2++] = 211;
          targetView.setBigInt64(position2, value);
        } else if (value < 18446744073709552e3 && value > 0) {
          target[position2++] = 207;
          targetView.setBigUint64(position2, value);
        } else {
          if (this.largeBigIntToFloat) {
            target[position2++] = 203;
            targetView.setFloat64(position2, Number(value));
          } else if (this.largeBigIntToString) {
            return pack2(value.toString());
          } else if (this.useBigIntExtension || this.moreTypes) {
            let empty = value < 0 ? BigInt(-1) : BigInt(0);
            let array2;
            if (value >> BigInt(65536) === empty) {
              let mask = BigInt(18446744073709552e3) - BigInt(1);
              let chunks = [];
              while (true) {
                chunks.push(value & mask);
                if (value >> BigInt(63) === empty) break;
                value >>= BigInt(64);
              }
              array2 = new Uint8Array(new BigUint64Array(chunks).buffer);
              array2.reverse();
            } else {
              let invert4 = value < 0;
              let string2 = (invert4 ? ~value : value).toString(16);
              if (string2.length % 2) {
                string2 = "0" + string2;
              } else if (parseInt(string2.charAt(0), 16) >= 8) {
                string2 = "00" + string2;
              }
              if (hasNodeBuffer) {
                array2 = Buffer.from(string2, "hex");
              } else {
                array2 = new Uint8Array(string2.length / 2);
                for (let i = 0; i < array2.length; i++) {
                  array2[i] = parseInt(string2.slice(i * 2, i * 2 + 2), 16);
                }
              }
              if (invert4) {
                for (let i = 0; i < array2.length; i++) array2[i] = ~array2[i];
              }
            }
            if (array2.length + position2 > safeEnd)
              makeRoom(array2.length + position2);
            position2 = writeExtensionData(array2, target, position2, 66);
            return;
          } else {
            throw new RangeError(value + " was too large to fit in MessagePack 64-bit integer format, use useBigIntExtension, or set largeBigIntToFloat to convert to float-64, or set largeBigIntToString to convert to string");
          }
        }
        position2 += 8;
      } else if (type === "undefined") {
        if (this.encodeUndefinedAsNil)
          target[position2++] = 192;
        else {
          target[position2++] = 212;
          target[position2++] = 0;
          target[position2++] = 0;
        }
      } else {
        throw new Error("Unknown type: " + type);
      }
    };
    const writePlainObject = this.variableMapSize || this.coercibleKeyAsNumber || this.skipValues ? (object) => {
      let keys;
      if (this.skipValues) {
        keys = [];
        for (let key2 in object) {
          if ((typeof object.hasOwnProperty !== "function" || object.hasOwnProperty(key2)) && !this.skipValues.includes(object[key2]))
            keys.push(key2);
        }
      } else {
        keys = Object.keys(object);
      }
      let length6 = keys.length;
      if (length6 < 16) {
        target[position2++] = 128 | length6;
      } else if (length6 < 65536) {
        target[position2++] = 222;
        target[position2++] = length6 >> 8;
        target[position2++] = length6 & 255;
      } else {
        target[position2++] = 223;
        targetView.setUint32(position2, length6);
        position2 += 4;
      }
      let key;
      if (this.coercibleKeyAsNumber) {
        for (let i = 0; i < length6; i++) {
          key = keys[i];
          let num = Number(key);
          pack2(isNaN(num) ? key : num);
          pack2(object[key]);
        }
      } else {
        for (let i = 0; i < length6; i++) {
          pack2(key = keys[i]);
          pack2(object[key]);
        }
      }
    } : (object) => {
      target[position2++] = 222;
      let objectOffset = position2 - start;
      position2 += 2;
      let size = 0;
      for (let key in object) {
        if (typeof object.hasOwnProperty !== "function" || object.hasOwnProperty(key)) {
          pack2(key);
          pack2(object[key]);
          size++;
        }
      }
      if (size > 65535) {
        throw new Error('Object is too large to serialize with fast 16-bit map size, use the "variableMapSize" option to serialize this object');
      }
      target[objectOffset++ + start] = size >> 8;
      target[objectOffset + start] = size & 255;
    };
    const writeRecord = this.useRecords === false ? writePlainObject : options.progressiveRecords && !useTwoByteRecords ? (
      // this is about 2% faster for highly stable structures, since it only requires one for-in loop (but much more expensive when new structure needs to be written)
      (object) => {
        let nextTransition, transition = structures.transitions || (structures.transitions = /* @__PURE__ */ Object.create(null));
        let objectOffset = position2++ - start;
        let wroteKeys;
        for (let key in object) {
          if (typeof object.hasOwnProperty !== "function" || object.hasOwnProperty(key)) {
            nextTransition = transition[key];
            if (nextTransition)
              transition = nextTransition;
            else {
              let keys = Object.keys(object);
              let lastTransition = transition;
              transition = structures.transitions;
              let newTransitions = 0;
              for (let i = 0, l = keys.length; i < l; i++) {
                let key2 = keys[i];
                nextTransition = transition[key2];
                if (!nextTransition) {
                  nextTransition = transition[key2] = /* @__PURE__ */ Object.create(null);
                  newTransitions++;
                }
                transition = nextTransition;
              }
              if (objectOffset + start + 1 == position2) {
                position2--;
                newRecord(transition, keys, newTransitions);
              } else
                insertNewRecord(transition, keys, objectOffset, newTransitions);
              wroteKeys = true;
              transition = lastTransition[key];
            }
            pack2(object[key]);
          }
        }
        if (!wroteKeys) {
          let recordId = transition[RECORD_SYMBOL];
          if (recordId)
            target[objectOffset + start] = recordId;
          else
            insertNewRecord(transition, Object.keys(object), objectOffset, 0);
        }
      }
    ) : (object) => {
      let nextTransition, transition = structures.transitions || (structures.transitions = /* @__PURE__ */ Object.create(null));
      let newTransitions = 0;
      for (let key in object) if (typeof object.hasOwnProperty !== "function" || object.hasOwnProperty(key)) {
        nextTransition = transition[key];
        if (!nextTransition) {
          nextTransition = transition[key] = /* @__PURE__ */ Object.create(null);
          newTransitions++;
        }
        transition = nextTransition;
      }
      let recordId = transition[RECORD_SYMBOL];
      if (recordId) {
        if (recordId >= 96 && useTwoByteRecords) {
          target[position2++] = ((recordId -= 96) & 31) + 96;
          target[position2++] = recordId >> 5;
        } else
          target[position2++] = recordId;
      } else {
        newRecord(transition, transition.__keys__ || Object.keys(object), newTransitions);
      }
      for (let key in object)
        if (typeof object.hasOwnProperty !== "function" || object.hasOwnProperty(key)) {
          pack2(object[key]);
        }
    };
    const checkUseRecords = typeof this.useRecords == "function" && this.useRecords;
    const writeObject = checkUseRecords ? (object) => {
      checkUseRecords(object) ? writeRecord(object) : writePlainObject(object);
    } : writeRecord;
    const makeRoom = (end) => {
      let newSize;
      if (end > 16777216) {
        if (end - start > MAX_BUFFER_SIZE)
          throw new Error("Packed buffer would be larger than maximum buffer size");
        newSize = Math.min(
          MAX_BUFFER_SIZE,
          Math.round(Math.max((end - start) * (end > 67108864 ? 1.25 : 2), 4194304) / 4096) * 4096
        );
      } else
        newSize = (Math.max(end - start << 2, target.length - 1) >> 12) + 1 << 12;
      let newBuffer = new ByteArrayAllocate(newSize);
      targetView = newBuffer.dataView || (newBuffer.dataView = new DataView(newBuffer.buffer, 0, newSize));
      end = Math.min(end, target.length);
      if (target.copy)
        target.copy(newBuffer, 0, start, end);
      else
        newBuffer.set(target.slice(start, end));
      position2 -= start;
      start = 0;
      safeEnd = newBuffer.length - 10;
      return target = newBuffer;
    };
    const newRecord = (transition, keys, newTransitions) => {
      let recordId = structures.nextId;
      if (!recordId)
        recordId = 64;
      if (recordId < sharedLimitId && this.shouldShareStructure && !this.shouldShareStructure(keys)) {
        recordId = structures.nextOwnId;
        if (!(recordId < maxStructureId))
          recordId = sharedLimitId;
        structures.nextOwnId = recordId + 1;
      } else {
        if (recordId >= maxStructureId)
          recordId = sharedLimitId;
        structures.nextId = recordId + 1;
      }
      let highByte = keys.highByte = recordId >= 96 && useTwoByteRecords ? recordId - 96 >> 5 : -1;
      transition[RECORD_SYMBOL] = recordId;
      transition.__keys__ = keys;
      structures[recordId - 64] = keys;
      if (recordId < sharedLimitId) {
        keys.isShared = true;
        structures.sharedLength = recordId - 63;
        hasSharedUpdate = true;
        if (highByte >= 0) {
          target[position2++] = (recordId & 31) + 96;
          target[position2++] = highByte;
        } else {
          target[position2++] = recordId;
        }
      } else {
        if (highByte >= 0) {
          target[position2++] = 213;
          target[position2++] = 114;
          target[position2++] = (recordId & 31) + 96;
          target[position2++] = highByte;
        } else {
          target[position2++] = 212;
          target[position2++] = 114;
          target[position2++] = recordId;
        }
        if (newTransitions)
          transitionsCount += serializationsSinceTransitionRebuild * newTransitions;
        if (recordIdsToRemove.length >= maxOwnStructures)
          recordIdsToRemove.shift()[RECORD_SYMBOL] = 0;
        recordIdsToRemove.push(transition);
        pack2(keys);
      }
    };
    const insertNewRecord = (transition, keys, insertionOffset, newTransitions) => {
      let mainTarget = target;
      let mainPosition = position2;
      let mainSafeEnd = safeEnd;
      let mainStart = start;
      target = keysTarget;
      position2 = 0;
      start = 0;
      if (!target)
        keysTarget = target = new ByteArrayAllocate(8192);
      safeEnd = target.length - 10;
      newRecord(transition, keys, newTransitions);
      keysTarget = target;
      let keysPosition = position2;
      target = mainTarget;
      position2 = mainPosition;
      safeEnd = mainSafeEnd;
      start = mainStart;
      if (keysPosition > 1) {
        let newEnd = position2 + keysPosition - 1;
        if (newEnd > safeEnd)
          makeRoom(newEnd);
        let insertionPosition = insertionOffset + start;
        target.copyWithin(insertionPosition + keysPosition, insertionPosition + 1, position2);
        target.set(keysTarget.slice(0, keysPosition), insertionPosition);
        position2 = newEnd;
      } else {
        target[insertionOffset + start] = keysTarget[0];
      }
    };
    const writeStruct = (object) => {
      let newPosition = writeStructSlots(object, target, start, position2, structures, makeRoom, (value, newPosition2, notifySharedUpdate) => {
        if (notifySharedUpdate)
          return hasSharedUpdate = true;
        position2 = newPosition2;
        let startTarget = target;
        pack2(value);
        resetStructures();
        if (startTarget !== target) {
          return { position: position2, targetView, target };
        }
        return position2;
      }, this);
      if (newPosition === 0)
        return writeObject(object);
      position2 = newPosition;
    };
  }
  useBuffer(buffer) {
    target = buffer;
    target.dataView || (target.dataView = new DataView(target.buffer, target.byteOffset, target.byteLength));
    targetView = target.dataView;
    position2 = 0;
  }
  set position(value) {
    position2 = value;
  }
  get position() {
    return position2;
  }
  clearSharedData() {
    if (this.structures)
      this.structures = [];
    if (this.typedStructs)
      this.typedStructs = [];
  }
};
extensionClasses = [Date, Set, Error, RegExp, ArrayBuffer, Object.getPrototypeOf(Uint8Array.prototype).constructor, DataView, C1Type];
extensions = [{
  pack(date, allocateForWrite, pack2) {
    let seconds = date.getTime() / 1e3;
    if ((this.useTimestamp32 || date.getMilliseconds() === 0) && seconds >= 0 && seconds < 4294967296) {
      let { target: target2, targetView: targetView2, position: position3 } = allocateForWrite(6);
      target2[position3++] = 214;
      target2[position3++] = 255;
      targetView2.setUint32(position3, seconds);
    } else if (seconds > 0 && seconds < 4294967296) {
      let { target: target2, targetView: targetView2, position: position3 } = allocateForWrite(10);
      target2[position3++] = 215;
      target2[position3++] = 255;
      targetView2.setUint32(position3, date.getMilliseconds() * 4e6 + (seconds / 1e3 / 4294967296 >> 0));
      targetView2.setUint32(position3 + 4, seconds);
    } else if (isNaN(seconds)) {
      if (this.onInvalidDate) {
        allocateForWrite(0);
        return pack2(this.onInvalidDate());
      }
      let { target: target2, targetView: targetView2, position: position3 } = allocateForWrite(3);
      target2[position3++] = 212;
      target2[position3++] = 255;
      target2[position3++] = 255;
    } else {
      let { target: target2, targetView: targetView2, position: position3 } = allocateForWrite(15);
      target2[position3++] = 199;
      target2[position3++] = 12;
      target2[position3++] = 255;
      targetView2.setUint32(position3, date.getMilliseconds() * 1e6);
      targetView2.setBigInt64(position3 + 4, BigInt(Math.floor(seconds)));
    }
  }
}, {
  pack(set6, allocateForWrite, pack2) {
    if (this.setAsEmptyObject) {
      allocateForWrite(0);
      return pack2({});
    }
    let array2 = Array.from(set6);
    let { target: target2, position: position3 } = allocateForWrite(this.moreTypes ? 3 : 0);
    if (this.moreTypes) {
      target2[position3++] = 212;
      target2[position3++] = 115;
      target2[position3++] = 0;
    }
    pack2(array2);
  }
}, {
  pack(error, allocateForWrite, pack2) {
    let { target: target2, position: position3 } = allocateForWrite(this.moreTypes ? 3 : 0);
    if (this.moreTypes) {
      target2[position3++] = 212;
      target2[position3++] = 101;
      target2[position3++] = 0;
    }
    pack2([error.name, error.message, error.cause]);
  }
}, {
  pack(regex, allocateForWrite, pack2) {
    let { target: target2, position: position3 } = allocateForWrite(this.moreTypes ? 3 : 0);
    if (this.moreTypes) {
      target2[position3++] = 212;
      target2[position3++] = 120;
      target2[position3++] = 0;
    }
    pack2([regex.source, regex.flags]);
  }
}, {
  pack(arrayBuffer, allocateForWrite) {
    if (this.moreTypes)
      writeExtBuffer(arrayBuffer, 16, allocateForWrite);
    else
      writeBuffer(hasNodeBuffer ? Buffer.from(arrayBuffer) : new Uint8Array(arrayBuffer), allocateForWrite);
  }
}, {
  pack(typedArray2, allocateForWrite) {
    let constructor = typedArray2.constructor;
    if (constructor !== ByteArray && this.moreTypes)
      writeExtBuffer(typedArray2, typedArrays.indexOf(constructor.name), allocateForWrite);
    else
      writeBuffer(typedArray2, allocateForWrite);
  }
}, {
  pack(arrayBuffer, allocateForWrite) {
    if (this.moreTypes)
      writeExtBuffer(arrayBuffer, 17, allocateForWrite);
    else
      writeBuffer(hasNodeBuffer ? Buffer.from(arrayBuffer) : new Uint8Array(arrayBuffer), allocateForWrite);
  }
}, {
  pack(c1, allocateForWrite) {
    let { target: target2, position: position3 } = allocateForWrite(1);
    target2[position3] = 193;
  }
}];
function writeExtBuffer(typedArray2, type, allocateForWrite, encode2) {
  let length6 = typedArray2.byteLength;
  if (length6 + 1 < 256) {
    var { target: target2, position: position3 } = allocateForWrite(4 + length6);
    target2[position3++] = 199;
    target2[position3++] = length6 + 1;
  } else if (length6 + 1 < 65536) {
    var { target: target2, position: position3 } = allocateForWrite(5 + length6);
    target2[position3++] = 200;
    target2[position3++] = length6 + 1 >> 8;
    target2[position3++] = length6 + 1 & 255;
  } else {
    var { target: target2, position: position3, targetView: targetView2 } = allocateForWrite(7 + length6);
    target2[position3++] = 201;
    targetView2.setUint32(position3, length6 + 1);
    position3 += 4;
  }
  target2[position3++] = 116;
  target2[position3++] = type;
  if (!typedArray2.buffer) typedArray2 = new Uint8Array(typedArray2);
  target2.set(new Uint8Array(typedArray2.buffer, typedArray2.byteOffset, typedArray2.byteLength), position3);
}
function writeBuffer(buffer, allocateForWrite) {
  let length6 = buffer.byteLength;
  var target2, position3;
  if (length6 < 256) {
    var { target: target2, position: position3 } = allocateForWrite(length6 + 2);
    target2[position3++] = 196;
    target2[position3++] = length6;
  } else if (length6 < 65536) {
    var { target: target2, position: position3 } = allocateForWrite(length6 + 3);
    target2[position3++] = 197;
    target2[position3++] = length6 >> 8;
    target2[position3++] = length6 & 255;
  } else {
    var { target: target2, position: position3, targetView: targetView2 } = allocateForWrite(length6 + 5);
    target2[position3++] = 198;
    targetView2.setUint32(position3, length6);
    position3 += 4;
  }
  target2.set(buffer, position3);
}
function writeExtensionData(result, target2, position3, type) {
  let length6 = result.length;
  switch (length6) {
    case 1:
      target2[position3++] = 212;
      break;
    case 2:
      target2[position3++] = 213;
      break;
    case 4:
      target2[position3++] = 214;
      break;
    case 8:
      target2[position3++] = 215;
      break;
    case 16:
      target2[position3++] = 216;
      break;
    default:
      if (length6 < 256) {
        target2[position3++] = 199;
        target2[position3++] = length6;
      } else if (length6 < 65536) {
        target2[position3++] = 200;
        target2[position3++] = length6 >> 8;
        target2[position3++] = length6 & 255;
      } else {
        target2[position3++] = 201;
        target2[position3++] = length6 >> 24;
        target2[position3++] = length6 >> 16 & 255;
        target2[position3++] = length6 >> 8 & 255;
        target2[position3++] = length6 & 255;
      }
  }
  target2[position3++] = type;
  target2.set(result, position3);
  position3 += length6;
  return position3;
}
function insertIds(serialized, idsToInsert) {
  let nextId;
  let distanceToMove = idsToInsert.length * 6;
  let lastEnd = serialized.length - distanceToMove;
  while (nextId = idsToInsert.pop()) {
    let offset = nextId.offset;
    let id = nextId.id;
    serialized.copyWithin(offset + distanceToMove, offset, lastEnd);
    distanceToMove -= 6;
    let position3 = offset + distanceToMove;
    serialized[position3++] = 214;
    serialized[position3++] = 105;
    serialized[position3++] = id >> 24;
    serialized[position3++] = id >> 16 & 255;
    serialized[position3++] = id >> 8 & 255;
    serialized[position3++] = id & 255;
    lastEnd = offset;
  }
  return serialized;
}
function writeBundles(start, pack2, incrementPosition) {
  if (bundledStrings2.length > 0) {
    targetView.setUint32(bundledStrings2.position + start, position2 + incrementPosition - bundledStrings2.position - start);
    bundledStrings2.stringsPosition = position2 - start;
    let writeStrings = bundledStrings2;
    bundledStrings2 = null;
    pack2(writeStrings[0]);
    pack2(writeStrings[1]);
  }
}
function prepareStructures(structures, packr) {
  structures.isCompatible = (existingStructures) => {
    let compatible = !existingStructures || (packr.lastNamedStructuresLength || 0) === existingStructures.length;
    if (!compatible)
      packr._mergeStructures(existingStructures);
    return compatible;
  };
  return structures;
}
var defaultPackr = new Packr({ useRecords: false });
var pack = defaultPackr.pack;
var encode = defaultPackr.pack;
var { NEVER, ALWAYS, DECIMAL_ROUND, DECIMAL_FIT } = FLOAT32_OPTIONS;
var REUSE_BUFFER_MODE = 512;
var RESET_BUFFER_MODE = 1024;
var RESERVE_START_SPACE = 2048;

// node_modules/msgpackr/iterators.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/icechunk/crockford_base32.js
init_legacy_browser();
var ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
function crockfordBase32Encode(input) {
  const numBytes = input.length;
  let value = 0;
  let output = "";
  let bits = 0;
  for (let i = 0; i < numBytes; ++i) {
    value = value << 8 | input[i];
    for (bits += 8; bits >= 5; bits -= 5) {
      output += ALPHABET[value >>> bits - 5 & 31];
    }
  }
  if (bits > 0) {
    output += ALPHABET[value << 5 - bits & 31];
  }
  return output;
}

// node_modules/neuroglancer/lib/kvstore/icechunk/decode_utils.js
var LATEST_KNOWN_SPEC_VERSION = 1;
var MAGIC = Uint8Array.of(
  73,
  67,
  69,
  240,
  159,
  167,
  138,
  67,
  72,
  85,
  78,
  75
);
var IMPLEMENTATION_NAME_LENGTH = 24;
var ENVELOPE_HEADER_SIZE = MAGIC.length + // magic
IMPLEMENTATION_NAME_LENGTH + // implementation name
1 + // spec_version
1 + // file type
1;
async function decodeEnvelope(buffer, maxVersion, fileType, signal) {
  if (buffer.byteLength < ENVELOPE_HEADER_SIZE) {
    throw new Error(
      `Expected icechunk header of ${ENVELOPE_HEADER_SIZE} bytes, but received: ${buffer.byteLength} bytes`
    );
  }
  const dv = new DataView(buffer);
  let offset = 0;
  for (let i = 0, n = MAGIC.length; i < n; ++i) {
    if (dv.getUint8(i) !== MAGIC[i]) {
      throw new Error(
        `Expected magic bytes of ${MAGIC.join()} but received: ${new Uint8Array(buffer, 0, n).join()}`
      );
    }
  }
  offset += MAGIC.length;
  offset += IMPLEMENTATION_NAME_LENGTH;
  const specVersion = dv.getUint8(offset++);
  if (specVersion > maxVersion) {
    throw new Error(
      `Expected version <= ${maxVersion} but received: ${specVersion}`
    );
  }
  const storedFileType = dv.getUint8(offset++);
  if (storedFileType !== fileType) {
    throw new Error(
      `Expected file type of ${fileType}, but received: ${storedFileType}`
    );
  }
  const compressionMethod = dv.getUint8(offset++);
  let content = new Uint8Array(buffer, offset);
  switch (compressionMethod) {
    case 0:
      break;
    case 1:
      content = await requestAsyncComputation(
        decodeZstd,
        signal,
        [buffer],
        content
      );
      content = new Uint8Array(
        content.buffer,
        content.byteOffset,
        content.byteLength
      );
      break;
    default:
      throw new Error(`Unknown compression method: ${compressionMethod}`);
  }
  return { content, specVersion };
}
async function decodeMsgpack(buffer, maxVersion, fileType, signal) {
  const { content, specVersion } = await decodeEnvelope(
    buffer,
    maxVersion,
    fileType,
    signal
  );
  return {
    content: new Unpackr({
      mapsAsObjects: false,
      int64AsType: "bigint"
    }).unpack(content),
    specVersion,
    estimatedSize: buffer.byteLength * 3
  };
}
var DataId = pipe(
  tuple([instance(Uint8Array)]),
  transform((obj) => obj[0])
);
var DataId12 = pipe(
  DataId,
  length5(12),
  transform(crockfordBase32Encode)
);
var DataId8 = pipe(
  DataId,
  length5(8),
  transform(crockfordBase32Encode)
);
var MIN_SAFE_INTEGER_BIGINT = BigInt(Number.MIN_SAFE_INTEGER);
var MAX_SAFE_INTEGER_BIGINT = BigInt(Number.MAX_SAFE_INTEGER);
var bigIntToSafeNumber = pipe(
  bigint(),
  check(
    (x) => x >= MIN_SAFE_INTEGER_BIGINT && x <= MAX_SAFE_INTEGER_BIGINT,
    `Number outside supported range: [${Number.MIN_SAFE_INTEGER}, ${Number.MAX_SAFE_INTEGER}]`
  ),
  transform(Number)
);
var Integer = union([
  bigIntToSafeNumber,
  pipe(number(), integer())
]);
function tupleToObject(entries) {
  const keys = Object.keys(entries);
  return pipe(
    array(any2()),
    length5(keys.length),
    transform(
      (x) => Object.fromEntries(keys.map((key, i) => [key, x[i]]))
    ),
    strictObject(entries)
  );
}
var ManifestId = DataId12;
var ChunkId = DataId12;
var NodeId = DataId8;
function parseDecodedMsgpack(schema, name, decoded) {
  try {
    return {
      ...parse3(schema, decoded.content),
      estimatedSize: decoded.estimatedSize
    };
  } catch (e) {
    if (isValiError(e)) {
      throw new Error(
        `Error parsing icechunk ${name}: ${JSON.stringify(flatten(e.issues))}`
      );
    }
    throw e;
  }
}

// node_modules/neuroglancer/lib/kvstore/icechunk/manifest.js
var MANIFEST_FILE_TYPE = 2;
var InlineChunkPayload = strictObject({
  Inline: instance(Uint8Array)
});
var Chunksum = any2();
var VirtualChunkLocation = string();
var VirtualChunkRef = tupleToObject({
  location: VirtualChunkLocation,
  offset: Integer,
  length: Integer,
  chunksum: Chunksum
});
var VirtualChunkRefPayload = strictObject({
  Virtual: VirtualChunkRef
});
var ChunkRef = tupleToObject({
  id: ChunkId,
  offset: Integer,
  length: Integer
});
var ChunkRefPayload = strictObject({
  Ref: ChunkRef
});
var ChunkPayload = pipe(
  map(string(), any2()),
  transform(Object.fromEntries),
  union([InlineChunkPayload, VirtualChunkRefPayload, ChunkRefPayload])
);
var Manifest = tupleToObject({
  id: ManifestId,
  chunks: map(
    NodeId,
    map(
      pipe(
        array(Integer),
        transform((chunk) => chunk.join())
      ),
      ChunkPayload
    )
  )
});
async function decodeManifest(buffer, signal) {
  const decoded = await decodeMsgpack(
    buffer,
    LATEST_KNOWN_SPEC_VERSION,
    MANIFEST_FILE_TYPE,
    signal
  );
  return parseDecodedMsgpack(Manifest, "chunk manifest", decoded);
}
function getManifestUrl(baseUrl, id) {
  return pipelineUrlJoin(baseUrl, `manifests/${id}`);
}

// node_modules/neuroglancer/lib/kvstore/icechunk/ref.js
init_legacy_browser();
function decodeRef(obj) {
  verifyObject(obj);
  if (Object.keys(obj).length !== 1) {
    throw new Error(
      `Expected object with only a "snapshot" property, but received: ${JSON.stringify(obj)}`
    );
  }
  const id = verifyObjectProperty(obj, "snapshot", verifyString);
  if (!isSnapshotId(id)) {
    throw new Error(
      `Expected icechunk snapshot id but received: ${JSON.stringify(id)}`
    );
  }
  return id;
}
function isSnapshotId(id) {
  return id.match(/^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{20}$/) !== null;
}
function isBranchRef(name) {
  return name.match(/^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{8}\.json$/) !== null;
}

// node_modules/neuroglancer/lib/kvstore/icechunk/snapshot.js
init_legacy_browser();
var SNAPSHOT_FILE_TYPE = 1;
var SnapshotId = DataId12;
var AttributesId = DataId12;
var ManifestFileInfo = tupleToObject({
  id: ManifestId,
  sizeBytes: Integer,
  numRows: Integer
});
var AttributeFileInfo = tupleToObject({
  id: AttributesId
});
var UserAttributesSnapshot = pipe(
  map(string(), any2()),
  transform(Object.fromEntries),
  union([
    strictObject({
      Inline: any2()
    })
  ])
  // v.map(v.picklist(["Ref"]), UserAttributesRef),
);
var ChunkKeyEncoding2 = picklist(["Slash", "Dot"]);
var Configuration = map(string(), any2());
var Codec = tupleToObject({
  name: string(),
  configuration: Configuration
});
var FillValue = pipe(
  map(string(), any2()),
  transform((obj) => {
    const values = Array.from(obj.values());
    if (values.length !== 1) {
      throw new Error(
        `Expected a single key, but received: ${JSON.stringify(Array.from(obj.keys()))}`
      );
    }
    return values[0];
  })
);
var StorageTransformer = tupleToObject({
  name: string(),
  configuration: Configuration
});
var DimensionNames = array(nullable(string()));
var ZarrArrayMetadata = tupleToObject({
  shape: array(Integer),
  dataType: string(),
  chunkShape: array(Integer),
  chunkKeyEncoding: ChunkKeyEncoding2,
  fillValue: FillValue,
  codecs: array(Codec),
  storageTransformers: array(StorageTransformer),
  dimensionNames: nullable(DimensionNames)
});
var ChunkIndices = array(Integer);
var ManifestExtents = strictTuple([ChunkIndices, ChunkIndices]);
var ManifestRef = tupleToObject({
  objectId: ManifestId,
  extents: ManifestExtents
});
var NodeDataGroup = picklist(["Group"]);
var NodeDataArray = strictObject({
  Array: tupleToObject({
    metadata: ZarrArrayMetadata,
    manifests: array(ManifestRef)
  })
});
var NodeData = union([
  NodeDataGroup,
  pipe(
    map(string(), any2()),
    transform(Object.fromEntries),
    NodeDataArray
  )
]);
var NodeSnapshot = tupleToObject({
  id: NodeId,
  path: pipe(
    string(),
    transform((s) => s === "/" ? "" : s.slice(1) + "/")
  ),
  userAttributes: UserAttributesSnapshot,
  nodeData: NodeData
});
var Nodes = pipe(
  map(string(), NodeSnapshot),
  transform(
    (obj) => Array.from(obj.values()).sort(
      (a, b) => defaultStringCompare(a.path, b.path)
    )
  )
);
var Snapshot = tupleToObject({
  id: SnapshotId,
  parentId: nullable(SnapshotId),
  flushedAt: string(),
  message: string(),
  metadata: record(string(), any2()),
  manifestFiles: pipe(
    array(ManifestFileInfo),
    transform((obj) => {
      const map2 = /* @__PURE__ */ new Map();
      for (const entry of obj) {
        map2.set(entry.id, entry);
      }
      return map2;
    })
  ),
  attributeFiles: array(AttributeFileInfo),
  nodes: Nodes
});
async function decodeSnapshot(buffer, signal) {
  const decoded = await decodeMsgpack(
    buffer,
    LATEST_KNOWN_SPEC_VERSION,
    SNAPSHOT_FILE_TYPE,
    signal
  );
  return parseDecodedMsgpack(Snapshot, "snapshot", decoded);
}
function encodeZarrJson(node) {
  const { userAttributes, nodeData } = node;
  let attributes;
  if (userAttributes === null) {
    attributes = /* @__PURE__ */ new Map();
  } else {
    attributes = userAttributes.Inline;
  }
  const obj = nodeData !== "Group" ? encodeArrayZarrJson(nodeData.Array.metadata, attributes) : { zarr_format: 3, node_type: "group", attributes };
  return JSON.stringify(obj, (_key, value) => {
    if (value instanceof Map) {
      return Object.fromEntries(value);
    }
    return value;
  });
}
function encodeArrayZarrJson(metadata, attributes) {
  const {
    shape,
    chunkShape,
    chunkKeyEncoding,
    dataType,
    fillValue,
    codecs,
    storageTransformers,
    dimensionNames
  } = metadata;
  return {
    zarr_format: 3,
    node_type: "array",
    shape,
    data_type: dataType,
    chunk_grid: { name: "regular", configuration: { chunk_shape: chunkShape } },
    chunk_key_encoding: {
      name: "default",
      configuration: { separator: chunkKeyEncoding === "Dot" ? "." : "/" }
    },
    fill_value: fillValue,
    codecs,
    storage_transformers: storageTransformers,
    dimension_names: dimensionNames ?? void 0,
    attributes
  };
}
function findNode(snapshot, path) {
  const { nodes } = snapshot;
  const index = binarySearch(
    nodes,
    path,
    (a, b) => defaultStringCompare(a, b.path)
  );
  if (index < 0) {
    throw new Error(`Node not found: ${JSON.stringify(path)}`);
  }
  return nodes[index];
}
function getSnapshotUrl(baseUrl, id) {
  return pipelineUrlJoin(baseUrl, `snapshots/${id}`);
}

// node_modules/neuroglancer/lib/kvstore/icechunk/metadata_cache.js
var __knownSymbol2 = (name, symbol) => (symbol = Symbol[name]) ? symbol : Symbol.for("Symbol." + name);
var __typeError2 = (msg) => {
  throw TypeError(msg);
};
var __using2 = (stack, value, async) => {
  if (value != null) {
    if (typeof value !== "object" && typeof value !== "function") __typeError2("Object expected");
    var dispose, inner;
    if (async) dispose = value[__knownSymbol2("asyncDispose")];
    if (dispose === void 0) {
      dispose = value[__knownSymbol2("dispose")];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") __typeError2("Object not disposable");
    if (inner) dispose = function() {
      try {
        inner.call(this);
      } catch (e) {
        return Promise.reject(e);
      }
    };
    stack.push([async, dispose, value]);
  } else if (async) {
    stack.push([async]);
  }
  return value;
};
var __callDispose2 = (stack, error, hasError) => {
  var E = typeof SuppressedError === "function" ? SuppressedError : function(e, s, m, _) {
    return _ = Error(m), _.name = "SuppressedError", _.error = e, _.suppressed = s, _;
  };
  var fail = (e) => error = hasError ? new E(e, error, "An error was suppressed during disposal") : (hasError = true, e);
  var next = (it) => {
    while (it = stack.pop()) {
      try {
        var result = it[1] && it[1].call(it[2]);
        if (it[0]) return Promise.resolve(result).then(next, (e) => (fail(e), next()));
      } catch (e) {
        fail(e);
      }
    }
    if (hasError) throw error;
  };
  return next();
};
function makeMetadataCache(sharedKvStoreContext, description, decode2) {
  const cache = new SimpleAsyncCache(
    sharedKvStoreContext.chunkManager.addRef(),
    {
      get: async (url, progressOptions) => {
        const readResponse = await sharedKvStoreContext.kvStoreContext.read(
          url,
          {
            ...progressOptions,
            throwIfMissing: true
          }
        );
        try {
          return await decode2(readResponse.response, progressOptions.signal);
        } catch (e) {
          throw new Error(`Error reading icechunk ${description} from ${url}`, {
            cause: e
          });
        }
      }
    }
  );
  cache.registerDisposer(sharedKvStoreContext.addRef());
  return cache;
}
function getSnapshot(sharedKvStoreContext, baseUrl, id, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "icechunk:snapshot",
    () => makeMetadataCache(
      sharedKvStoreContext,
      "snapshot",
      async (response, signal) => {
        const value = await decodeSnapshot(
          await response.arrayBuffer(),
          signal
        );
        return { data: value, size: value.estimatedSize };
      }
    )
  );
  return cache.get(getSnapshotUrl(baseUrl, id), options);
}
function getManifest(sharedKvStoreContext, baseUrl, id, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "icechunk:manifest",
    () => makeMetadataCache(
      sharedKvStoreContext,
      "manifest",
      async (response, signal) => {
        const value = await decodeManifest(
          await response.arrayBuffer(),
          signal
        );
        return { data: value, size: value.estimatedSize };
      }
    )
  );
  return cache.get(getManifestUrl(baseUrl, id), options);
}
function getRef(sharedKvStoreContext, url, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "icechunk:ref",
    () => makeMetadataCache(sharedKvStoreContext, "ref", async (response) => ({
      data: decodeRef(await response.json()),
      size: 0
    }))
  );
  return cache.get(url, options);
}
function getBranch(sharedKvStoreContext, url, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "icechunk:branch",
    () => {
      const cache2 = new SimpleAsyncCache(
        sharedKvStoreContext.chunkManager.addRef(),
        {
          get: async (url2, progressOptions) => {
            var _stack = [];
            try {
              const _span = __using2(_stack, new ProgressSpan(progressOptions.progressListener, {
                message: `Resolving icechunk branch at ${url2}`
              }));
              try {
                const listResponse = await sharedKvStoreContext.kvStoreContext.list(url2, {
                  ...progressOptions,
                  responseKeys: "suffix"
                });
                const headKey = listResponse.entries.find(
                  (entry) => isBranchRef(entry.key)
                );
                if (headKey === void 0) {
                  throw new Error(`Failed to find any refs`);
                }
                const snapshotId = await getRef(
                  sharedKvStoreContext,
                  pipelineUrlJoin(url2, headKey.key),
                  progressOptions
                );
                return { data: snapshotId, size: 0 };
              } catch (e) {
                throw new Error(`Error resolving icechunk branch at ${url2}`, {
                  cause: e
                });
              }
            } catch (_) {
              var _error = _, _hasError = true;
            } finally {
              __callDispose2(_stack, _error, _hasError);
            }
          }
        }
      );
      cache2.registerDisposer(sharedKvStoreContext.addRef());
      return cache2;
    }
  );
  return cache.get(url, options);
}
function getTag(sharedKvStoreContext, url, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "icechunk:tag",
    () => {
      const cache2 = new SimpleAsyncCache(
        sharedKvStoreContext.chunkManager.addRef(),
        {
          get: async (url2, progressOptions) => {
            var _stack = [];
            try {
              const _span = __using2(_stack, new ProgressSpan(progressOptions.progressListener, {
                message: `Resolving icechunk tag at ${url2}`
              }));
              try {
                const [tagResponse, deletedResponse] = await Promise.all([
                  getRef(
                    sharedKvStoreContext,
                    pipelineUrlJoin(url2, "ref.json"),
                    progressOptions
                  ),
                  sharedKvStoreContext.kvStoreContext.stat(
                    pipelineUrlJoin(url2, "ref.json.deleted"),
                    progressOptions
                  )
                ]);
                if (deletedResponse !== void 0) {
                  throw new Error(`Tag is marked as deleted`);
                }
                return { data: tagResponse, size: 0 };
              } catch (e) {
                throw new Error(`Error resolving icechunk tag at ${url2}`, {
                  cause: e
                });
              }
            } catch (_) {
              var _error = _, _hasError = true;
            } finally {
              __callDispose2(_stack, _error, _hasError);
            }
          }
        }
      );
      cache2.registerDisposer(sharedKvStoreContext.addRef());
      return cache2;
    }
  );
  return cache.get(url, options);
}
function resolveRefSpec(sharedKvStoreContext, url, refSpec, options) {
  if ("snapshot" in refSpec) {
    return Promise.resolve(refSpec.snapshot);
  }
  if ("branch" in refSpec) {
    return getBranch(
      sharedKvStoreContext,
      pipelineUrlJoin(url, `refs/branch.${refSpec.branch}/`),
      options
    );
  }
  return getTag(
    sharedKvStoreContext,
    pipelineUrlJoin(url, `refs/tag.${refSpec.tag}/`),
    options
  );
}

// node_modules/neuroglancer/lib/kvstore/icechunk/read.js
init_legacy_browser();
function resolveIcechunkPath(snapshot, path) {
  let nodePath;
  let chunk;
  const zarrJsonMatch = path.match(/(?:^|\/)(zarr\.json)$/);
  if (zarrJsonMatch !== null) {
    nodePath = path.slice(0, -zarrJsonMatch[1].length);
  } else {
    const chunkMatch = path.match(/c(?:[./][0-9]+)*$/);
    if (chunkMatch === null) {
      return void 0;
    }
    nodePath = path.slice(0, -chunkMatch[0].length);
    const parts = chunkMatch[0].split(/[./]/);
    const n = parts.length - 1;
    chunk = new Array(n);
    for (let i = 0; i < n; ++i) {
      chunk[i] = Number(parts[i + 1]);
    }
  }
  const node = findNode(snapshot, nodePath);
  if (chunk === void 0) {
    return { node };
  }
  if (node.nodeData === "Group") {
    return void 0;
  }
  const { shape, chunkShape } = node.nodeData.Array.metadata;
  const rank = shape.length;
  if (rank !== chunk.length) {
    return void 0;
  }
  for (let i = 0; i < rank; ++i) {
    if (chunk[i] * chunkShape[i] >= shape[i]) {
      return void 0;
    }
  }
  return { node, chunk };
}
function manifestExtentsContain([lower, upper], chunk) {
  for (let i = 0, n = chunk.length; i < n; ++i) {
    const c = chunk[i];
    if (c < lower[i] || c >= upper[i]) return false;
  }
  return true;
}
async function resolveChunkPayload(sharedKvStoreContext, baseUrl, node, chunk, options) {
  const { manifests } = node.nodeData.Array;
  const chunkKey = chunk.join();
  const nodeId = node.id;
  for (const manifestRef of manifests) {
    if (!manifestExtentsContain(manifestRef.extents, chunk)) continue;
    const manifest = await getManifest(
      sharedKvStoreContext,
      baseUrl,
      manifestRef.objectId,
      options
    );
    const chunks = manifest.chunks.get(nodeId);
    if (chunks === void 0) continue;
    const chunkPayload = chunks.get(chunkKey);
    if (chunkPayload !== void 0) return chunkPayload;
  }
  return void 0;
}
async function stat2(sharedKvStoreContext, baseUrl, snapshot, path, options) {
  const resolvedPath = resolveIcechunkPath(snapshot, path);
  if (resolvedPath === void 0) return void 0;
  const { node, chunk } = resolvedPath;
  if (chunk === void 0) {
    return { totalSize: void 0 };
  }
  const payload = await resolveChunkPayload(
    sharedKvStoreContext,
    baseUrl,
    node,
    chunk,
    options
  );
  if (payload === void 0) return void 0;
  let totalSize;
  if ("Inline" in payload) {
    totalSize = payload.Inline.length;
  } else if ("Virtual" in payload) {
    totalSize = payload.Virtual.length;
  } else {
    totalSize = payload.Ref.length;
  }
  return { totalSize };
}
async function readFromChunkPayload(sharedKvStoreContext, baseUrl, payload, options) {
  if ("Inline" in payload) {
    return handleByteRangeRequestFromUint8Array(
      payload.Inline,
      options.byteRange
    );
  }
  let offset;
  let length6;
  let url;
  if ("Virtual" in payload) {
    ({ location: url, offset, length: length6 } = payload.Virtual);
  } else {
    const { Ref: ref } = payload;
    ({ offset, length: length6 } = ref);
    url = getChunkUrl(baseUrl, ref.id);
  }
  return new FileByteRangeHandle(
    sharedKvStoreContext.kvStoreContext.getFileHandle(url),
    { offset, length: length6 }
  ).read(options);
}
function getChunkUrl(baseUrl, id) {
  return pipelineUrlJoin(baseUrl, `chunks/${id}`);
}
async function read3(sharedKvStoreContext, baseUrl, snapshot, path, options) {
  const resolvedPath = resolveIcechunkPath(snapshot, path);
  if (resolvedPath === void 0) return void 0;
  const { node, chunk } = resolvedPath;
  if (chunk === void 0) {
    const data = encodeZarrJson(node);
    const encoded = new TextEncoder().encode(data);
    return handleByteRangeRequestFromUint8Array(encoded, options.byteRange);
  }
  const payload = await resolveChunkPayload(
    sharedKvStoreContext,
    baseUrl,
    node,
    chunk,
    options
  );
  if (payload === void 0) return void 0;
  return readFromChunkPayload(sharedKvStoreContext, baseUrl, payload, options);
}

// node_modules/neuroglancer/lib/kvstore/icechunk/url.js
init_legacy_browser();
var BRANCH_PREFIX = "branch.";
var TAG_PREFIX = "tag.";
function getIcechunkUrl(options, key) {
  const { baseUrl, refSpec } = options;
  const versionString = refSpec === void 0 ? "" : `@${formatRefSpec(refSpec)}/`;
  return baseUrl + `|icechunk:${versionString}${encodePathForUrl(key)}`;
}
function formatRefSpec(refSpec) {
  if ("branch" in refSpec) {
    return BRANCH_PREFIX + encodePathForUrl(refSpec.branch);
  }
  if ("tag" in refSpec) {
    return TAG_PREFIX + encodePathForUrl(refSpec.tag);
  }
  return refSpec.snapshot;
}
function isValidBranchName(name) {
  return name.length > 0 && !name.includes("/");
}
function parseRefSpec(versionString) {
  if (versionString === void 0) return void 0;
  if (versionString.startsWith(BRANCH_PREFIX)) {
    const branch = versionString.substring(BRANCH_PREFIX.length);
    if (!isValidBranchName(branch)) {
      throw new Error(`Invalid branch name: ${JSON.stringify(branch)}`);
    }
    return { branch: decodeURIComponent(branch) };
  }
  if (versionString.startsWith(TAG_PREFIX)) {
    const tag = versionString.substring(TAG_PREFIX.length);
    if (!isValidBranchName(tag)) {
      throw new Error(`Invalid tag name: ${JSON.stringify(tag)}`);
    }
    return { tag: decodeURIComponent(tag) };
  }
  if (isSnapshotId(versionString)) {
    return { snapshot: versionString };
  }
  throw new Error(`Invalid ref spec: ${JSON.stringify(versionString)}`);
}
function parseIcechunkUrl(parsedUrl, base) {
  ensureNoQueryOrFragmentParameters(parsedUrl);
  try {
    const m = (parsedUrl.suffix ?? "").match(/^(?:@([^/]*)(?:\/|$))?(.*)$/);
    const [, refSpecString, path] = m;
    return {
      baseUrl: base.store.getUrl(ensurePathIsDirectory(base.path)),
      version: parseRefSpec(refSpecString),
      path: decodeURIComponent(path)
    };
  } catch (e) {
    throw new Error(`Invalid URL: ${parsedUrl.url}`, { cause: e });
  }
}

// node_modules/neuroglancer/lib/kvstore/icechunk/backend.js
var IcechunkKvStore = class {
  constructor(sharedKvStoreContext, baseUrl, refSpec) {
    this.sharedKvStoreContext = sharedKvStoreContext;
    this.baseUrl = baseUrl;
    this.refSpec = refSpec;
  }
  snapshot;
  async getSnapshot(options) {
    let { snapshot } = this;
    if (snapshot === void 0) {
      const snapshotId = await resolveRefSpec(
        this.sharedKvStoreContext,
        this.baseUrl,
        this.refSpec ?? { branch: "main" },
        options
      );
      snapshot = this.snapshot = await getSnapshot(
        this.sharedKvStoreContext,
        this.baseUrl,
        snapshotId,
        options
      );
    }
    return snapshot;
  }
  getUrl(key) {
    return getIcechunkUrl(this, key);
  }
  async stat(key, options) {
    const snapshot = await this.getSnapshot(options);
    return stat2(
      this.sharedKvStoreContext,
      this.baseUrl,
      snapshot,
      key,
      options
    );
  }
  async read(key, options) {
    const snapshot = await this.getSnapshot(options);
    return read3(
      this.sharedKvStoreContext,
      this.baseUrl,
      snapshot,
      key,
      options
    );
  }
  async list(prefix, options) {
    const snapshot = await this.getSnapshot(options);
    return getListResponseFromSnapshot(snapshot, prefix);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};

// node_modules/neuroglancer/lib/kvstore/icechunk/complete_url.js
init_legacy_browser();
async function completeIcechunkUrl(_sharedKvStoreContext, options) {
  const { url } = options;
  const suffix = url.suffix ?? "";
  if (suffix === "") {
    return {
      offset: 0,
      completions: [{ value: "@", description: "Ref specifier" }]
    };
  }
  const m = suffix.match(/^@([^/]*)((?:\/|$).*)/);
  if (m === null) return void 0;
  const [, version, rest] = m;
  if (rest !== "") {
    parseRefSpec(version);
    return void 0;
  }
  let refCompletionsPromise;
  if (version.match(
    /^(?:(?:(?:t|$)(?:a|$)(?:g|$)(?:\.|$))|(?:(?:b|$)(?:r|$)(?:a|$)(?:n|$)(?:c|$)(?:h|$)(?:\.|$)))/
  )) {
    const refsPath = joinPath(options.base.path, `refs/`);
    refCompletionsPromise = listKvStore(
      options.base.store,
      refsPath + decodeURIComponent(version),
      { signal: options.signal, progressListener: options.progressListener }
    ).then(
      ({ directories }) => directories.map((path) => {
        const ref = path.slice(refsPath.length);
        return {
          value: encodePathForUrl(ref) + "/",
          description: ref.startsWith("tag.") ? "Tag" : "Branch"
        };
      })
    );
  }
  let snapshotCompletionsPromise;
  if (version.match(/^[0-9ABCDEFGHJKMNPQRSTVWXYZ]{0,20}$/)) {
    const snapshotsPath = joinPath(options.base.path, `snapshots/`);
    snapshotCompletionsPromise = listKvStore(
      options.base.store,
      snapshotsPath + version,
      { signal: options.signal, progressListener: options.progressListener }
    ).then(({ entries }) => {
      const results = [];
      for (const { key } of entries) {
        const snapshotId = key.slice(snapshotsPath.length);
        if (!isSnapshotId(snapshotId)) continue;
        results.push({
          value: snapshotId + "/",
          description: "Snapshot"
        });
      }
      return results;
    });
  }
  return {
    offset: 1,
    completions: [
      ...await refCompletionsPromise ?? [],
      ...await snapshotCompletionsPromise ?? []
    ]
  };
}

// node_modules/neuroglancer/lib/kvstore/icechunk/register_backend.js
function icechunkProvider(sharedKvStoreContext) {
  return {
    scheme: "icechunk",
    description: "Icechunk repository",
    getKvStore(parsedUrl, base) {
      const { baseUrl, version, path } = parseIcechunkUrl(parsedUrl, base);
      return {
        store: new IcechunkKvStore(sharedKvStoreContext, baseUrl, version),
        path
      };
    },
    completeUrl(options) {
      return completeIcechunkUrl(sharedKvStoreContext, options);
    }
  };
}
backendOnlyKvStoreProviderRegistry.registerKvStoreAdapterProvider(
  icechunkProvider
);

// node_modules/neuroglancer/lib/kvstore/middleauth/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/middleauth/common.js
init_legacy_browser();
var SCHEME_PREFIX = "middleauth+";
function getMiddleAuthCredentialsProvider(credentialsManager, url) {
  return credentialsManager.getCredentialsProvider(
    "middleauthapp",
    new URL(url).origin
  );
}
function middleauthProvider(scheme, context, httpKvStoreClass) {
  return {
    scheme: SCHEME_PREFIX + scheme,
    description: `${scheme} with middleauth`,
    getKvStore(url) {
      const httpUrl = url.url.substring(SCHEME_PREFIX.length);
      const credentialsProvider = getMiddleAuthCredentialsProvider(
        context.credentialsManager,
        httpUrl
      );
      try {
        const { baseUrl, path } = getBaseHttpUrlAndPath(httpUrl);
        return {
          store: new httpKvStoreClass(
            context,
            baseUrl,
            SCHEME_PREFIX + baseUrl,
            fetchOkWithOAuth2CredentialsAdapter(credentialsProvider)
          ),
          path
        };
      } catch (e) {
        throw new Error(`Invalid URL ${JSON.stringify(url.url)}`, {
          cause: e
        });
      }
    }
  };
}
function registerProviders2(registry, httpKvStoreClass) {
  for (const httpScheme of ["https"]) {
    registry.registerBaseKvStoreProvider(
      (context) => middleauthProvider(httpScheme, context, httpKvStoreClass)
    );
  }
}

// node_modules/neuroglancer/lib/kvstore/middleauth/register_backend.js
registerProviders2(backendOnlyKvStoreProviderRegistry, HttpKvStore);

// node_modules/neuroglancer/lib/kvstore/ngauth/register.js
init_legacy_browser();
function getNgauthCredentialsProvider(credentialsManager, authServer, bucket) {
  return false_default ? credentialsManager.getCredentialsProvider("gcs", { bucket }) : credentialsManager.getCredentialsProvider("ngauth_gcs", {
    authServer,
    bucket
  });
}
var SCHEME_PREFIX2 = "gs+ngauth+";
function gcsNgauthProvider(scheme, context) {
  return {
    scheme,
    description: false_default ? "Google Cloud Storage" : "Google Cloud Storage (ngauth)",
    getKvStore(url) {
      const m = (url.suffix ?? "").match(/^\/\/([^/]+)\/([^/]+)(\/.*)?$/);
      if (m === null) {
        throw new Error(
          `Invalid URL, expected ${url.scheme}://<ngauth-server>/<bucket>/<path>`
        );
      }
      const [, authHost, bucket, path] = m;
      const authUrl = url.scheme.substring(SCHEME_PREFIX2.length) + "://" + authHost;
      const credentialsProvider = getNgauthCredentialsProvider(
        context.credentialsManager,
        authUrl,
        bucket
      );
      return {
        store: new GcsKvStore(
          bucket,
          `${url.scheme}://${authHost}/${bucket}/`,
          fetchOkWithOAuth2CredentialsAdapter(credentialsProvider)
        ),
        path: decodeURIComponent((path ?? "").substring(1))
      };
    }
  };
}
for (const scheme of ["http", "https"]) {
  frontendBackendIsomorphicKvStoreProviderRegistry.registerBaseKvStoreProvider(
    (context) => gcsNgauthProvider(`${SCHEME_PREFIX2}${scheme}`, context)
  );
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/list.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/btree.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/decode_utils.js
init_legacy_browser();
var import_crc32c = __toESM(require_crc32c(), 1);

// node_modules/neuroglancer/lib/util/leb128.js
init_legacy_browser();
function decodeLeb128(array2, offset) {
  let result = 0;
  let shift = 0;
  for (let i = offset, length6 = array2.byteLength; i < length6; ++i) {
    const byte = array2.getUint8(i);
    result += (byte & 127) << shift;
    if ((byte & 128) === 0) {
      if (result > Number.MAX_SAFE_INTEGER) {
        throw new Error(`Value exceeded ${Number.MAX_SAFE_INTEGER}`);
      }
      return { offset: i + 1, value: result };
    }
    shift += 7;
  }
  throw new Error("Unexpected EOF");
}
function decodeLeb128Bigint(array2, offset) {
  let result = 0n;
  let shift = 0n;
  for (let i = offset, length6 = array2.byteLength; i < length6; ++i) {
    const byte = array2.getUint8(i);
    result |= BigInt(byte & 127) << BigInt(shift);
    if ((byte & 128) === 0) {
      return { offset: i + 1, value: result };
    }
    shift += 7n;
  }
  throw new Error("Unexpected EOF");
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/decode_utils.js
var CompressionMethod = /* @__PURE__ */ ((CompressionMethod2) => {
  CompressionMethod2[CompressionMethod2["UNCOMPRESSED"] = 0] = "UNCOMPRESSED";
  CompressionMethod2[CompressionMethod2["ZSTD"] = 1] = "ZSTD";
  return CompressionMethod2;
})(CompressionMethod || {});
async function decodeEnvelope2(buffer, expectedMagic, maxVersion, signal) {
  if (buffer.byteLength < 4 + 8 + 4 + 2) {
    throw new Error("Unexpected EOF");
  }
  const dv = new DataView(buffer);
  const magic = dv.getUint32(
    0,
    /*littleEndian=*/
    false
  );
  if (magic !== expectedMagic) {
    throw new Error(
      `Expected magic value 0x${expectedMagic.toString(16)} but received 0x${magic.toString(16)}`
    );
  }
  const length6 = dv.getBigUint64(
    4,
    /*littleEndian=*/
    true
  );
  if (length6 != BigInt(buffer.byteLength)) {
    throw new Error(
      `Expected length ${buffer.byteLength} but received: ${length6}`
    );
  }
  const checksum = dv.getUint32(
    buffer.byteLength - 4,
    /*littleEndian=*/
    true
  );
  const actualChecksum = (0, import_crc32c.buf)(new Uint8Array(buffer, 0, buffer.byteLength - 4)) >>> 0;
  if (checksum != actualChecksum) {
    throw new Error(
      `Expected CRC32c checksum of ${checksum}, but received ${actualChecksum}`
    );
  }
  const version = dv.getUint8(12);
  if (version > maxVersion) {
    throw new Error(
      `Expected version to be <= ${maxVersion}, but received: ${version}`
    );
  }
  const compressionFormat = dv.getUint8(13);
  let content = new Uint8Array(buffer, 14, buffer.byteLength - 14 - 4);
  switch (compressionFormat) {
    case 0:
      break;
    case 1:
      content = await requestAsyncComputation(
        decodeZstd,
        signal,
        [buffer],
        content
      );
      break;
    default:
      throw new Error(`Unknown compression format ${compressionFormat}`);
  }
  return {
    reader: {
      offset: 0,
      data: new DataView(
        content.buffer,
        content.byteOffset,
        content.byteLength
      )
    },
    version
  };
}
function readBytes(reader, count) {
  const { offset, data } = reader;
  if (offset + count > data.byteLength) {
    throw new Error(`Unexpected EOF`);
  }
  reader.offset += count;
  return new Uint8Array(data.buffer, data.byteOffset + offset, count);
}
function readLeb128(reader) {
  const { value, offset } = decodeLeb128(reader.data, reader.offset);
  reader.offset = offset;
  return value;
}
function readLeb128Bigint(reader) {
  const { value, offset } = decodeLeb128Bigint(reader.data, reader.offset);
  reader.offset = offset;
  return value;
}
function readLeb128Bounded(reader, maxValue) {
  const value = readLeb128(reader);
  if (value > maxValue) {
    throw new Error(`Expected value <= ${maxValue}, but received: ${value}`);
  }
  return value;
}
function readUint8(reader) {
  const { offset, data } = reader;
  if (offset + 1 > data.byteLength) {
    throw new Error(`Unexpected EOF`);
  }
  reader.offset += 1;
  return data.getUint8(offset);
}
function readInt32le(reader) {
  const { offset, data } = reader;
  if (offset + 4 > data.byteLength) {
    throw new Error(`Unexpected EOF`);
  }
  reader.offset += 4;
  return data.getInt32(
    offset,
    /*littleEndian=*/
    true
  );
}
function readUint64le(reader) {
  const { offset, data } = reader;
  if (offset + 8 > data.byteLength) {
    throw new Error(`Unexpected EOF`);
  }
  reader.offset += 8;
  return data.getBigUint64(
    offset,
    /*littleEndian=*/
    true
  );
}
function ensureEof(reader) {
  if (reader.offset !== reader.data.byteLength) {
    throw new Error(`Expected EOF at byte ${reader.offset}`);
  }
}
function readArrayOf(readElement) {
  return (reader, count, options) => {
    const values = [];
    for (let i = 0; i < count; ++i) {
      values[i] = readElement(reader, options);
    }
    return values;
  };
}
function toArrayOfStructs(count, arrays) {
  const keys = Object.keys(arrays);
  const structs = [];
  for (let i = 0; i < count; ++i) {
    const value = Object.fromEntries(
      keys.map((key) => [key, arrays[key][i]])
    );
    structs[i] = value;
  }
  return structs;
}
function readStructOfArrays(members, validate) {
  return (reader, count, options) => {
    const arrays = Object.fromEntries(
      Object.entries(members).map(([key, read4]) => [
        key,
        read4(reader, count, options)
      ])
    );
    const structs = toArrayOfStructs(count, arrays);
    if (validate !== void 0) {
      for (let i = 0; i < count; ++i) {
        validate == null ? void 0 : validate(structs[i], options);
      }
    }
    return structs;
  };
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/indirect_data_reference.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/key.js
init_legacy_browser();
var EMPTY_KEY = new Uint8Array(0);
function compareArraysLexicographically(a, b) {
  const minLength = Math.min(a.length, b.length);
  for (let i = 0; i < minLength; ++i) {
    const d = a[i] - b[i];
    if (d !== 0) return d;
  }
  return a.length - b.length;
}
function findFirstMismatch(a, b) {
  const minLength = Math.min(a.length, b.length);
  for (let i = 0; i < minLength; ++i) {
    const d = a[i] - b[i];
    if (d !== 0) return { offset: i, difference: d };
  }
  return { offset: minLength, difference: a.length - b.length };
}
var EMPTY_KEY_RANGE = {
  inclusiveMin: EMPTY_KEY,
  exclusiveMax: Uint8Array.of(0)
};
function concatKeys(...keys) {
  let length6 = 0;
  for (const key of keys) {
    length6 += key.length;
  }
  const newKey = new Uint8Array(length6);
  let offset = 0;
  for (const key of keys) {
    newKey.set(key, offset);
    offset += key.length;
  }
  return newKey;
}
function keyStartsWith(key, prefix) {
  return key.length >= prefix.length && findFirstMismatch(key, prefix).offset === prefix.length;
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/indirect_data_reference.js
function readDataFileId(reader, options) {
  const { dataFileTable } = options;
  const index = readLeb128(reader);
  if (index >= dataFileTable.length) {
    throw new Error(
      `Invalid data file index ${index}, expected value <= ${dataFileTable.length}`
    );
  }
  return dataFileTable[index];
}
var readIndirectDataReferences = readStructOfArrays(
  {
    dataFile: readArrayOf(readDataFileId),
    offset: readArrayOf(readLeb128Bigint),
    length: readArrayOf(readLeb128Bigint)
  },
  (value, options) => {
    if (locationIsMissing(value)) {
      if (options.allowMissing !== true) {
        throw new Error(`Reference to missing value not allowed`);
      }
    } else {
      if (value.offset + value.length > BigInt(Number.MAX_SAFE_INTEGER)) {
        throw new Error(
          `Offset=${value.offset} + length=${value.length} exceeds maximum of ${Number.MAX_SAFE_INTEGER}`
        );
      }
    }
  }
);
function locationIsMissing(location2) {
  return location2.offset === 0xffffffffffffffffn && location2.length === 0xffffffffffffffffn;
}
var MAX_PATH_LENGTH = 65535;
function readDataFileTable(reader, transitiveBaseUrl) {
  const numFiles = readLeb128(reader);
  const pathLengthBuffer = new Uint16Array(numFiles * 3);
  for (let i = 1, count = numFiles * 3; i < count; ++i) {
    pathLengthBuffer[i] = readLeb128Bounded(reader, MAX_PATH_LENGTH);
  }
  const dataFileIds = [];
  let prevBasePath = EMPTY_KEY;
  let prevRelativePathEncoded = EMPTY_KEY;
  const textDecoder = new TextDecoder("utf-8", { fatal: true });
  for (let i = 0; i < numFiles; ++i) {
    let prefixLength = pathLengthBuffer[i];
    let suffixLength = pathLengthBuffer[i + numFiles];
    const basePathLength = pathLengthBuffer[i + 2 * numFiles];
    const pathLength = prefixLength + suffixLength;
    if (pathLength > MAX_PATH_LENGTH) {
      throw new Error(
        `path_length[${i} = prefix_length(${prefixLength}) + suffix_length(${suffixLength}) = ${pathLength} > ${MAX_PATH_LENGTH}`
      );
    }
    if (basePathLength > pathLength) {
      throw new Error(
        `base_path_length[${i}] = ${basePathLength} > path_length(${pathLength}) = prefix_length(${prefixLength}) + suffix_length(${suffixLength})`
      );
    }
    if (prefixLength > Math.min(prevBasePath.length, basePathLength) && basePathLength !== prevBasePath.length) {
      throw new Error(
        `path_prefix_length[${i - 1}] = ${prefixLength} > min(base_path_length[${i - 1}] = ${prevBasePath.length}, base_path_length[${i}] = ${basePathLength}) is not valid if base_path_length[${i - 1}] != base_path_length[${i}]`
      );
    }
    const relativePathLength = prefixLength + suffixLength - basePathLength;
    let baseUrl;
    let relativePath;
    if (basePathLength === 0) {
      baseUrl = transitiveBaseUrl;
      prevBasePath = EMPTY_KEY;
    } else if (prefixLength >= basePathLength) {
      baseUrl = dataFileIds[i - 1].baseUrl;
    } else {
      const basePath = new Uint8Array(basePathLength);
      let offset = 0;
      const baseSuffixLength = Math.max(basePathLength - prefixLength, 0);
      if (prefixLength > 0) {
        const basePrefixLength = Math.min(prefixLength, basePathLength);
        basePath.set(prevBasePath.subarray(0, basePrefixLength));
        offset = basePrefixLength;
        prefixLength -= basePrefixLength;
      }
      if (baseSuffixLength !== 0) {
        basePath.set(readBytes(reader, baseSuffixLength), offset);
        suffixLength -= baseSuffixLength;
      }
      baseUrl = pipelineUrlJoin(
        transitiveBaseUrl,
        textDecoder.decode(basePath)
      );
      prevBasePath = basePath;
    }
    if (relativePathLength === 0) {
      relativePath = "";
      prevRelativePathEncoded = EMPTY_KEY;
    } else if (suffixLength === 0 && relativePathLength === prevRelativePathEncoded.length) {
      relativePath = dataFileIds[i - 1].relativePath;
    } else {
      const relativePathEncoded = new Uint8Array(relativePathLength);
      let offset = 0;
      if (prefixLength !== 0) {
        relativePathEncoded.set(
          prevRelativePathEncoded.subarray(0, prefixLength),
          0
        );
        offset += prefixLength;
      }
      if (suffixLength > 0) {
        relativePathEncoded.set(readBytes(reader, suffixLength), offset);
      }
      relativePath = textDecoder.decode(relativePathEncoded);
      prevRelativePathEncoded = relativePathEncoded;
    }
    dataFileIds[i] = { baseUrl, relativePath };
  }
  return dataFileIds;
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/btree.js
var BTREE_NODE_MAGIC_VALUE = 215687390;
var BTREE_NODE_FORMAT_VERSION = 0;
var MAX_BTREE_NODE_ARITY = 1024 * 1024;
async function decodeBtreeNode(buffer, baseUrl, signal) {
  try {
    const { reader } = await decodeEnvelope2(
      buffer,
      BTREE_NODE_MAGIC_VALUE,
      BTREE_NODE_FORMAT_VERSION,
      signal
    );
    const height = readUint8(reader);
    const dataFileTable = readDataFileTable(reader, baseUrl);
    const numEntries = readLeb128(reader);
    if (numEntries === 0) {
      throw new Error(`Empty b+tree node`);
    }
    if (numEntries > MAX_BTREE_NODE_ARITY) {
      throw new Error(
        `B+tree node has arity ${numEntries}, which exceeds limit of ${MAX_BTREE_NODE_ARITY}`
      );
    }
    return {
      height,
      ...height === 0 ? readBtreeLeafNodeEntries(reader, dataFileTable, numEntries) : readBtreeInteriorNodeEntries(reader, dataFileTable, numEntries),
      estimatedSize: reader.data.byteLength * 3
    };
  } catch (e) {
    throw new Error(`Error decoding OCDBT b+tree node`, { cause: e });
  }
}
var MAX_KEY_LENGTH = 65535;
function readKeyLength(reader) {
  return readLeb128Bounded(reader, MAX_KEY_LENGTH);
}
function readKeys(reader, count, interiorNode) {
  const keyLengthBuffer = new Uint16Array(count * 2);
  for (let i = 1, n = keyLengthBuffer.length; i < n; ++i) {
    keyLengthBuffer[i] = readKeyLength(reader);
  }
  let commonPrefixLength = keyLengthBuffer[count];
  for (let i = 1; i < count; ++i) {
    commonPrefixLength = Math.min(commonPrefixLength, keyLengthBuffer[i]);
  }
  let subtreeCommonPrefixLengths;
  if (interiorNode) {
    subtreeCommonPrefixLengths = new Uint16Array(count);
    for (let i = 0; i < count; ++i) {
      const x = subtreeCommonPrefixLengths[i] = readKeyLength(reader);
      commonPrefixLength = Math.min(commonPrefixLength, x);
    }
  }
  commonPrefixLength = Math.min(keyLengthBuffer[count], commonPrefixLength);
  for (let i = 0, prevLength = 0; i < count; ++i) {
    const prefixLength = keyLengthBuffer[i];
    if (prefixLength > prevLength) {
      throw new Error(
        `Child ${i}: Prefix length of ${prefixLength} exceeds previous key length ${prevLength}`
      );
    }
    const suffixLength = keyLengthBuffer[i + count];
    const keyLength = prefixLength + suffixLength;
    if (keyLength > MAX_KEY_LENGTH) {
      throw new Error(
        `Child ${i}: Key length ${keyLength} exceeds limit of ${MAX_KEY_LENGTH}`
      );
    }
    if (interiorNode) {
      const subtreeCommonPrefixLength = subtreeCommonPrefixLengths[i];
      if (subtreeCommonPrefixLength > keyLength) {
        throw new Error(
          `Child ${i}: subtree common prefix length of ${subtreeCommonPrefixLength} exceeds key length of ${keyLength}`
        );
      }
      subtreeCommonPrefixLengths[i] -= commonPrefixLength;
    }
    prevLength = keyLength;
  }
  const keys = new Array(count);
  let commonPrefix;
  {
    const keyLength = keyLengthBuffer[count];
    const key = readBytes(reader, keyLength);
    commonPrefix = key.slice(0, commonPrefixLength);
    keys[0] = key.slice(commonPrefixLength);
  }
  for (let i = 1; i < count; ++i) {
    const prefixLength = keyLengthBuffer[i] - commonPrefixLength;
    const suffixLength = keyLengthBuffer[i + count];
    const suffix = readBytes(reader, suffixLength);
    const prevKey = keys[i - 1];
    if (compareArraysLexicographically(prevKey.subarray(prefixLength), suffix) >= 0) {
      throw new Error(`Invalid key order`);
    }
    const key = new Uint8Array(prefixLength + suffixLength);
    key.set(prevKey.subarray(0, prefixLength));
    key.set(suffix, prefixLength);
    keys[i] = key;
  }
  return {
    keys,
    subtreeCommonPrefixLengths,
    commonPrefix
  };
}
var MAX_INLINE_VALUE_LENGTH = 1024 * 1024;
function readLeafNodeValueReferences(reader, dataFileTable, numEntries) {
  const lengths = readArrayOf(readLeb128Bigint)(reader, numEntries, {});
  const valueKinds = readBytes(reader, numEntries);
  for (let i = 0; i < numEntries; ++i) {
    const valueKind = valueKinds[i];
    if (valueKind > 1) {
      throw new Error(
        `value_kind[${i}]=${valueKind} is outside valid range [0, ${1}]`
      );
    }
    if (valueKind === 0) {
      const length6 = lengths[i];
      if (length6 > BigInt(MAX_INLINE_VALUE_LENGTH)) {
        throw new Error(
          `value_length[${i}]=${length6} exceeds maximum of ${MAX_INLINE_VALUE_LENGTH} for an inline value`
        );
      }
    }
  }
  const values = new Array(numEntries);
  for (let i = 0; i < numEntries; ++i) {
    if (valueKinds[i] !== 1) continue;
    const dataFile = readDataFileId(reader, { dataFileTable });
    values[i] = {
      dataFile,
      offset: 0n,
      length: lengths[i]
    };
  }
  for (let i = 0; i < numEntries; ++i) {
    if (valueKinds[i] !== 1) continue;
    const offset = readLeb128Bigint(reader);
    values[i].offset = offset;
  }
  for (let i = 0; i < numEntries; ++i) {
    if (valueKinds[i] !== 0) continue;
    values[i] = readBytes(reader, Number(lengths[i]));
  }
  return values;
}
function readBtreeLeafNodeEntries(reader, dataFileTable, numEntries) {
  const { keys, commonPrefix } = readKeys(
    reader,
    numEntries,
    /*interiorNode=*/
    false
  );
  const values = readLeafNodeValueReferences(reader, dataFileTable, numEntries);
  return {
    keyPrefix: commonPrefix,
    entries: toArrayOfStructs(numEntries, {
      key: keys,
      value: values
    })
  };
}
function readBtreeInteriorNodeEntries(reader, dataFileTable, numEntries) {
  const { keys, commonPrefix, subtreeCommonPrefixLengths } = readKeys(
    reader,
    numEntries,
    /*interiorNode=*/
    true
  );
  const nodes = readBtreeNodeReferences(reader, numEntries, { dataFileTable });
  return {
    keyPrefix: commonPrefix,
    entries: toArrayOfStructs(numEntries, {
      key: keys,
      subtreeCommonPrefixLength: subtreeCommonPrefixLengths,
      node: nodes
    })
  };
}
var readBtreeNodeStatistics = readStructOfArrays({
  numKeys: readArrayOf(readLeb128Bigint),
  numTreeBytes: readArrayOf(readLeb128Bigint),
  numIndirectValueBytes: readArrayOf(readLeb128Bigint)
});
var readBtreeNodeReferences = readStructOfArrays({
  location: readIndirectDataReferences,
  statistics: readBtreeNodeStatistics
});
function validateBtreeNodeReference(node, height, inclusiveMinKey) {
  if (node.height !== height) {
    throw new Error(`Expected height of ${height} but received ${node.height}`);
  }
  const { keyPrefix } = node;
  if (inclusiveMinKey.length < keyPrefix.length) {
    if (compareArraysLexicographically(keyPrefix, inclusiveMinKey) >= 0) {
      return;
    }
  } else {
    const c = compareArraysLexicographically(
      keyPrefix,
      inclusiveMinKey.subarray(0, keyPrefix.length)
    );
    if (c >= 0) {
      if (compareArraysLexicographically(
        node.entries[0].key,
        inclusiveMinKey.subarray(keyPrefix.length)
      ) >= 0) {
        return;
      }
    }
  }
  throw new Error(
    `First key [${keyPrefix}]+[${node.entries[0].key}] < inclusive_min [${inclusiveMinKey}] specified by parent node`
  );
}
function findBtreeInteriorEntryLowerBound(entries, inclusiveMin) {
  const index = binarySearchLowerBound(
    0,
    entries.length,
    (i) => compareArraysLexicographically(entries[i].key, inclusiveMin) > 0
  );
  return Math.max(0, index - 1);
}
function findBtreeLeafEntryLowerBound(entries, inclusiveMin) {
  return binarySearchLowerBound(
    0,
    entries.length,
    (i) => compareArraysLexicographically(entries[i].key, inclusiveMin) >= 0
  );
}
function findBtreeInteriorEntryPrefixRange(entries, prefix) {
  const lower = findBtreeInteriorEntryLowerBound(entries, prefix);
  const upper = findBtreeEntryPrefixUpperBound(
    entries,
    lower,
    entries.length,
    prefix
  );
  return [lower, upper];
}
function findBtreeEntryPrefixUpperBound(entries, lower, upper, prefix) {
  if (lower === upper || prefix.length === 0) return upper;
  return binarySearchLowerBound(lower, upper, (i) => {
    const { offset, difference } = findFirstMismatch(prefix, entries[i].key);
    return difference < 0 && offset < prefix.length;
  });
}
function findBtreeLeafEntryPrefixRange(entries, prefix) {
  const lower = findBtreeLeafEntryLowerBound(entries, prefix);
  const upper = findBtreeEntryPrefixUpperBound(
    entries,
    lower,
    entries.length,
    prefix
  );
  return [lower, upper];
}
function findBtreeLeafEntry(entries, key) {
  const index = binarySearch(
    entries,
    key,
    (a, b) => compareArraysLexicographically(a, b.key)
  );
  if (index < 0) return void 0;
  return entries[index];
}
function findBtreeInteriorEntry(entries, key) {
  const index = binarySearchLowerBound(
    0,
    entries.length,
    (i) => compareArraysLexicographically(entries[i].key, key) > 0
  );
  if (index === 0) {
    return void 0;
  }
  const entry = entries[index - 1];
  const { subtreeCommonPrefixLength } = entry;
  if (subtreeCommonPrefixLength !== 0 && !keyStartsWith(key, entry.key.subarray(0, subtreeCommonPrefixLength))) {
    return void 0;
  }
  return entry;
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/metadata_cache.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/manifest.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/version_tree.js
init_legacy_browser();
var MAX_VERSION_TREE_ARITY_LOG2 = 16;
function readVersionTreeLeafNode(reader, versionTreeArityLog2, dataFileTable) {
  const maxNumEntries = 2 ** versionTreeArityLog2;
  const numEntries = readLeb128Bounded(reader, maxNumEntries);
  const entries = readVersionTreeLeafNodeEntries(reader, numEntries, {
    allowMissing: true,
    dataFileTable
  });
  validateVersionTreeLeafNodeEntries(entries, versionTreeArityLog2);
  return entries;
}
function readVersionTreeInteriorNode(reader, versionTreeArityLog2, dataFileTable, height) {
  const maxHeight = getMaxVersionTreeHeight(versionTreeArityLog2);
  if (height > maxHeight) {
    throw new Error(
      `height=${height} exceeds maximum of ${maxHeight} for version_tree_arity_log2=${versionTreeArityLog2}`
    );
  }
  const maxArity = 2 ** versionTreeArityLog2;
  const entries = readVersionTreeInteriorNodeEntries(
    reader,
    dataFileTable,
    maxArity,
    height - 1
  );
  validateVersionTreeInteriorNodeEntries(entries, versionTreeArityLog2, height);
  return entries;
}
function validateVersionTreeLeafNodeEntries(entries, versionTreeArityLog2) {
  const maxNumEntries = 2 ** versionTreeArityLog2;
  if (entries.length === 0 || entries.length > maxNumEntries) {
    throw new Error(
      `num_children=${entries.length} outside valid range [1, ${maxNumEntries}]`
    );
  }
  for (const [i, entry] of entries.entries()) {
    if (locationIsMissing(entry.root.location)) {
      if (entry.rootHeight !== 0) {
        throw new Error(
          `non-zero root_height=${entry.rootHeight} for empty generation ${entry.generationNumber}`
        );
      }
      const { statistics } = entry.root;
      if (statistics.numKeys !== 0n || statistics.numTreeBytes !== 0n || statistics.numIndirectValueBytes !== 0n) {
        throw new Error(
          `non-zero statistics for empty generation_number[${i}]=${entry.generationNumber}`
        );
      }
    }
    if (entry.generationNumber === 0n) {
      throw new Error(`generation_number[${i}] must be non-zero`);
    }
    if (i !== 0) {
      if (entry.generationNumber <= entries[i - 1].generationNumber) {
        throw new Error(
          `generation_number[${i}]=${entry.generationNumber} <= generation_number[${i - 1}]=${entries[i - 1].generationNumber}`
        );
      }
    }
  }
  const lastGenerationNumber = entries.at(-1).generationNumber;
  const firstGenerationNumber = entries[0].generationNumber;
  const minGenerationNumber = getMinVersionTreeNodeGenerationNumber(
    versionTreeArityLog2,
    0,
    lastGenerationNumber
  );
  if (firstGenerationNumber < minGenerationNumber) {
    throw new Error(
      `Generation range [${firstGenerationNumber}, ${lastGenerationNumber}] exceeds maximum of [${minGenerationNumber}, ${lastGenerationNumber}]`
    );
  }
}
function validateVersionTreeInteriorNodeEntries(entries, versionTreeArityLog2, height) {
  const maxNumEntries = 2 ** versionTreeArityLog2;
  if (entries.length === 0 || entries.length > maxNumEntries) {
    throw new Error(
      `num_children=${entries.length} outside valid range [1, ${maxNumEntries}]`
    );
  }
  const childGenerationNumberStride = 1n << BigInt(versionTreeArityLog2 * height);
  for (const [i, entry] of entries.entries()) {
    if (entry.generationNumber === 0n) {
      throw new Error(`generation_number[${i}] must be non-zero`);
    }
    if (i !== 0) {
      const prev = entries[i - 1];
      if (entry.generationNumber <= prev.generationNumber) {
        throw new Error(
          `generation_number[${i}]=${entry.generationNumber} >= generation_number[${i - 1}]=${prev.generationNumber}`
        );
      }
      if ((entry.generationNumber - 1n) / childGenerationNumberStride === (prev.generationNumber - 1n) / childGenerationNumberStride) {
        throw new Error(
          `generation_number[${i}]=${entry.generationNumber} should be in the same child node as generation_number[${i - 1}]=${prev.generationNumber}`
        );
      }
    }
    if (entry.generationNumber % childGenerationNumberStride !== 0n) {
      throw new Error(
        `generation_number[${i}]=${entry.generationNumber} is not a multiple of ${childGenerationNumberStride}`
      );
    }
    if (entry.numGenerations > childGenerationNumberStride) {
      throw new Error(
        `num_generations[${i}]=${entry.numGenerations} for generation_number=${entry.generationNumber} is greater than ${childGenerationNumberStride}`
      );
    }
  }
  const maxArity = 1n << BigInt(versionTreeArityLog2);
  const lastEntry = entries.at(-1);
  if ((lastEntry.generationNumber - 1n) / childGenerationNumberStride / maxArity !== (entries[0].generationNumber - 1n) / childGenerationNumberStride / maxArity) {
    throw new Error(
      `generation_number[0]=${entries[0].generationNumber} cannot be in the same node as generation_number[${entries.length - 1}]=${lastEntry.generationNumber}`
    );
  }
}
function getMinVersionTreeNodeGenerationNumber(versionTreeArityLog2, height, lastGenerationNumber) {
  return lastGenerationNumber - (lastGenerationNumber - 1n) % (1n << BigInt(versionTreeArityLog2 * (height + 1)));
}
function readVersionTreeArityLog2(reader) {
  const value = readUint8(reader);
  if (value === 0 || value > MAX_VERSION_TREE_ARITY_LOG2) {
    throw new Error(
      `Expected version_tree_arity_log2 in range [1, ${MAX_VERSION_TREE_ARITY_LOG2}] but received: ${value}`
    );
  }
  return value;
}
var VERSION_TREE_NODE_MAGIC_VALUE = 215683636;
var VERSION_TREE_NODE_FORMAT_VERSION = 0;
async function decodeVersionTreeNode(buffer, baseUrl, signal) {
  try {
    const { reader } = await decodeEnvelope2(
      buffer,
      VERSION_TREE_NODE_MAGIC_VALUE,
      VERSION_TREE_NODE_FORMAT_VERSION,
      signal
    );
    const versionTreeArityLog2 = readVersionTreeArityLog2(reader);
    const height = readUint8(reader);
    const dataFileTable = readDataFileTable(reader, baseUrl);
    return {
      versionTreeArityLog2,
      height,
      entries: height === 0 ? readVersionTreeLeafNode(reader, versionTreeArityLog2, dataFileTable) : readVersionTreeInteriorNode(
        reader,
        versionTreeArityLog2,
        dataFileTable,
        height
      ),
      estimatedSize: reader.data.byteLength * 3
    };
  } catch (e) {
    throw new Error(`Error decoding OCDBT version tree node`, { cause: e });
  }
}
var readVersionTreeNodeInteriorNodeEntriesWithKnownCount = readStructOfArrays({
  generationNumber: readArrayOf(readLeb128Bigint),
  location: readIndirectDataReferences,
  numGenerations: readArrayOf(readLeb128Bigint),
  commitTime: readArrayOf(readUint64le),
  height: readArrayOf(
    (reader, { height }) => height === void 0 ? readUint8(reader) : height
  ),
  cumulativeNumGenerations: readArrayOf(() => 0n)
});
function computeCumulativeNumGenerations(versionNodes) {
  let sum = 0n;
  for (const ref of versionNodes) {
    sum += ref.numGenerations;
    ref.cumulativeNumGenerations = sum;
  }
}
function readVersionTreeInteriorNodeEntries(reader, dataFileTable, maxNumEntries, height) {
  const numEntries = readLeb128Bounded(reader, maxNumEntries);
  const entries = readVersionTreeNodeInteriorNodeEntriesWithKnownCount(
    reader,
    numEntries,
    { dataFileTable, height }
  );
  computeCumulativeNumGenerations(entries);
  return entries;
}
function getMaxVersionTreeHeight(versionTreeArityLog2) {
  return Math.floor(63 / versionTreeArityLog2) - 1;
}
var readVersionTreeLeafNodeEntries = readStructOfArrays({
  generationNumber: readArrayOf(readLeb128Bigint),
  rootHeight: readArrayOf(readUint8),
  root: readBtreeNodeReferences,
  commitTime: readArrayOf(readUint64le)
});
function compareVersionSpecToVersion(versionSpec, ref) {
  return "generationNumber" in versionSpec ? bigintCompare(versionSpec.generationNumber, ref.generationNumber) : bigintCompare(versionSpec.commitTime, ref.commitTime);
}
function findLeafVersion(generationIndex, versions, version) {
  if ("generationNumber" in version) {
    return findLeafVersionByGenerationNumber(
      versions,
      version.generationNumber
    );
  } else if ("generationIndex" in version) {
    let { generationIndex: i } = version;
    i -= generationIndex;
    if (i < 0n) return -1;
    if (i >= BigInt(versions.length)) return versions.length;
    return Number(i);
  } else {
    return findLeafVersionByCommitTime(versions, version.commitTime);
  }
}
function findLeafVersionByGenerationNumber(versions, generationNumber) {
  const index = binarySearch(
    versions,
    generationNumber,
    (a, b) => bigintCompare(a, b.generationNumber)
  );
  if (index < 0) return versions.length;
  return index;
}
function findLeafVersionByCommitTime(versions, commitTime) {
  const index = binarySearchLowerBound(
    0,
    versions.length,
    (i) => versions[i].commitTime > commitTime
  );
  if (index === 0) return versions.length;
  return index - 1;
}
function findLeafVersionIndexByLowerBound(generationIndex, versions, version) {
  if ("generationIndex" in version) {
    const index = version.generationIndex - generationIndex;
    if (index < 0n) return 0;
    if (index > BigInt(versions.length)) return versions.length;
    return Number(index);
  }
  return binarySearchLowerBound(
    0,
    versions.length,
    (i) => compareVersionSpecToVersion(version, versions[i]) <= 0
  );
}
function findVersionNode(versionTreeArityLog2, generationIndex, versionNodes, version) {
  if ("generationIndex" in version) {
    return versionNodes[findVersionNodeIndexByGenerationIndex(
      versionNodes,
      version.generationIndex - generationIndex
    )];
  }
  return "generationNumber" in version ? findVersionNodeByGenerationNumber(
    versionTreeArityLog2,
    versionNodes,
    version.generationNumber
  ) : findVersionNodeByCommitTime(versionNodes, version.commitTime);
}
function findVersionNodeIndexByGenerationIndex(versionNodes, generationIndex) {
  return binarySearchLowerBound(
    0,
    versionNodes.length,
    (i) => versionNodes[i].cumulativeNumGenerations > generationIndex
  );
}
function findVersionNodeByGenerationNumber(versionTreeArityLog2, versionNodes, generationNumber) {
  const index = binarySearchLowerBound(
    0,
    versionNodes.length,
    (i) => versionNodes[i].generationNumber >= generationNumber
  );
  if (index === versionNodes.length) return void 0;
  const ref = versionNodes[index];
  if (getMinVersionTreeNodeGenerationNumber(
    versionTreeArityLog2,
    ref.height,
    ref.generationNumber
  ) > generationNumber) {
    return void 0;
  }
  return ref;
}
function findVersionNodeByCommitTime(versionNodes, commitTime) {
  const index = binarySearchLowerBound(
    0,
    versionNodes.length,
    (i) => versionNodes[i].commitTime > commitTime
  );
  if (index === 0) return void 0;
  return versionNodes[index - 1];
}
function findVersionNodeIndexByLowerBound(versionTreeArityLog2, generationIndex, versionNodes, version) {
  if ("generationIndex" in version) {
    return findVersionNodeIndexByGenerationIndex(
      versionNodes,
      version.generationIndex - generationIndex
    );
  }
  if ("generationNumber" in version) {
    return findVersionNodeIndexByGenerationNumberLowerBound(
      versionTreeArityLog2,
      versionNodes,
      version.generationNumber
    );
  }
  return findVersionNodeIndexByCommitTimeLowerBound(
    versionNodes,
    version.commitTime
  );
}
function findVersionNodeIndexByGenerationNumberLowerBound(versionTreeArityLog2, versionNodes, generationNumber) {
  return binarySearchLowerBound(0, versionNodes.length, (i) => {
    const ref = versionNodes[i];
    return getMinVersionTreeNodeGenerationNumber(
      versionTreeArityLog2,
      ref.height,
      ref.generationNumber
    ) >= generationNumber;
  });
}
function findVersionNodeIndexByCommitTimeLowerBound(versionNodes, commitTime) {
  const index = binarySearchLowerBound(
    0,
    versionNodes.length,
    (i) => versionNodes[i].commitTime > commitTime
  );
  return Math.max(0, index - 1);
}
function findVersionNodeIndexByUpperBound(generationIndex, versionNodes, version) {
  if ("generationIndex" in version) {
    return findVersionNodeIndexByGenerationIndexUpperBound(
      versionNodes,
      version.generationIndex - generationIndex
    );
  }
  if ("generationNumber" in version) {
    return findVersionNodeIndexByGenerationNumberUpperBound(
      versionNodes,
      version.generationNumber
    );
  }
  return findVersionNodeIndexByCommitTimeLowerBound(
    versionNodes,
    version.commitTime
  );
}
function findVersionNodeIndexByGenerationIndexUpperBound(versionNodes, generationIndex) {
  return binarySearchLowerBound(0, versionNodes.length, (i) => {
    const node = versionNodes[i];
    return node.cumulativeNumGenerations - node.numGenerations >= generationIndex;
  });
}
function findVersionNodeIndexByGenerationNumberUpperBound(versionNodes, generationNumber) {
  return binarySearchLowerBound(
    0,
    versionNodes.length,
    (i) => versionNodes[i].generationNumber >= generationNumber
  );
}
function validateVersionTreeNodeReference(node, config, lastGenerationNumber, height, numGenerations) {
  if (node.height !== height) {
    throw new Error(
      `Expected height of ${height} but received: ${node.height}`
    );
  }
  if (node.versionTreeArityLog2 !== config.versionTreeArityLog2) {
    throw new Error(
      `Expected version_tree_arity_log2=${config.versionTreeArityLog2} but received: ${node.versionTreeArityLog2}`
    );
  }
  const { generationNumber } = node.entries.at(-1);
  if (generationNumber !== lastGenerationNumber) {
    throw new Error(
      `Expected generation number ${lastGenerationNumber} but received: ${generationNumber}`
    );
  }
  const actualNumGenerations = node.height === 0 ? BigInt(node.entries.length) : node.entries.at(-1).cumulativeNumGenerations;
  if (actualNumGenerations !== numGenerations) {
    throw new Error(
      `Expected ${numGenerations}, but received: ${actualNumGenerations}`
    );
  }
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/manifest.js
function decodeConfig(reader) {
  const uuid = readBytes(reader, 16).slice();
  const manifestKind = readLeb128(reader);
  if (manifestKind > 1) {
    throw new Error(`Unknown manifest kind: ${manifestKind}`);
  }
  const maxInlineValueBytes = readLeb128(reader);
  const maxDecodedNodeBytes = readLeb128(reader);
  const versionTreeArityLog2 = readVersionTreeArityLog2(reader);
  const compressionMethod = readLeb128(reader);
  let zstdLevel;
  switch (compressionMethod) {
    case CompressionMethod.UNCOMPRESSED:
      break;
    case CompressionMethod.ZSTD:
      zstdLevel = readInt32le(reader);
      break;
    default:
      throw new Error(`Invalid compression method: ${compressionMethod}`);
  }
  return {
    uuid,
    manifestKind,
    maxInlineValueBytes,
    maxDecodedNodeBytes,
    versionTreeArityLog2,
    compressionMethod,
    zstdLevel
  };
}
function decodeManifestVersionTree(reader, config, baseUrl) {
  var _a;
  const dataFileTable = readDataFileTable(reader, baseUrl);
  const inlineVersions = readVersionTreeLeafNode(
    reader,
    config.versionTreeArityLog2,
    dataFileTable
  );
  const versionTreeNodes = readManifestVersionTreeNodes(
    reader,
    config.versionTreeArityLog2,
    dataFileTable,
    inlineVersions.at(-1).generationNumber
  );
  return {
    inlineVersions,
    versionTreeNodes,
    numGenerations: BigInt(inlineVersions.length) + (((_a = versionTreeNodes.at(-1)) == null ? void 0 : _a.cumulativeNumGenerations) ?? 0n)
  };
}
function readManifestVersionTreeNodes(reader, versionTreeArityLog2, dataFileTable, lastGenerationNumber) {
  const maxNumEntries = getMaxVersionTreeHeight(versionTreeArityLog2);
  const entries = readVersionTreeInteriorNodeEntries(
    reader,
    dataFileTable,
    maxNumEntries,
    /* height=*/
    void 0
  );
  validateManifestVersionTreeNodes(
    versionTreeArityLog2,
    lastGenerationNumber,
    entries
  );
  return entries;
}
function validateManifestVersionTreeNodes(versionTreeArityLog2, lastGenerationNumber, entries) {
  const maxHeight = getMaxVersionTreeHeight(versionTreeArityLog2);
  for (const [i2, entry] of entries.entries()) {
    if (entry.height === 0 || entry.height > maxHeight) {
      throw new Error(
        `entry_height[${i2}]=${entry.height} outside valid range [1, ${maxHeight}]`
      );
    }
    if (entry.generationNumber === 0n) {
      throw new Error(`generation_number[${i2}] must be non-zero`);
    }
    if (i2 > 0) {
      const prev = entries[i2 - 1];
      if (entry.generationNumber <= prev.generationNumber) {
        throw new Error(
          `generation_number[${i2}]=${entry.generationNumber} <= generation_number[${i2 - 1}]=${prev.generationNumber}`
        );
      }
      if (entry.height >= prev.height) {
        throw new Error(
          `entry_height[${i2}]=${entry.height} >= entry_height[${i2 - 1}]=${prev.height}`
        );
      }
    }
  }
  let i = entries.length;
  for (const {
    minGenerationNumber,
    maxGenerationNumber,
    height
  } of getPossibleManifestVersionTreeNodeReferences(
    lastGenerationNumber,
    versionTreeArityLog2
  )) {
    if (i === 0) {
      break;
    }
    const entry = entries[i - 1];
    if (entry.height !== height) {
      continue;
    }
    --i;
    const { generationNumber } = entry;
    if (generationNumber < minGenerationNumber || generationNumber > maxGenerationNumber) {
      throw new Error(
        `generation_number[${i}]=${generationNumber} is outside expected range [${minGenerationNumber}, ${maxGenerationNumber}] for height ${height}`
      );
    }
  }
  if (i !== 0) {
    throw new Error(
      `Unexpected child with generation_number[${i - 1}]=${entries[i - 1].generationNumber} and entry_height=${entries[i - 1].height} given last generation_number=${lastGenerationNumber}`
    );
  }
}
function getPossibleManifestVersionTreeNodeReferences(generationNumber, versionTreeArityLog2) {
  generationNumber = generationNumber - 1n >> BigInt(versionTreeArityLog2) << BigInt(versionTreeArityLog2);
  let height = 1;
  const results = [];
  while (generationNumber !== 0n) {
    const shift = BigInt((height + 1) * versionTreeArityLog2);
    const nextGenerationNumber = generationNumber - 1n >> shift << shift;
    const minGenerationNumber = nextGenerationNumber + 1n;
    results.push({
      minGenerationNumber,
      maxGenerationNumber: generationNumber,
      height
    });
    ++height;
    generationNumber = nextGenerationNumber;
  }
  return results;
}
var MANIFEST_MAGIC_VALUE = 215693866;
var MANIFEST_FORMAT_VERSION = 0;
async function decodeManifest2(buffer, baseUrl, signal) {
  try {
    const { reader } = await decodeEnvelope2(
      buffer,
      MANIFEST_MAGIC_VALUE,
      MANIFEST_FORMAT_VERSION,
      signal
    );
    const config = decodeConfig(reader);
    const versionTree = config.manifestKind === 0 ? decodeManifestVersionTree(reader, config, baseUrl) : void 0;
    ensureEof(reader);
    return { config, versionTree, estimatedSize: reader.data.byteLength * 3 };
  } catch (e) {
    throw new Error(`Error decoding OCDBT manifest`, { cause: e });
  }
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/metadata_cache.js
var __knownSymbol3 = (name, symbol) => (symbol = Symbol[name]) ? symbol : Symbol.for("Symbol." + name);
var __typeError3 = (msg) => {
  throw TypeError(msg);
};
var __using3 = (stack, value, async) => {
  if (value != null) {
    if (typeof value !== "object" && typeof value !== "function") __typeError3("Object expected");
    var dispose, inner;
    if (async) dispose = value[__knownSymbol3("asyncDispose")];
    if (dispose === void 0) {
      dispose = value[__knownSymbol3("dispose")];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") __typeError3("Object not disposable");
    if (inner) dispose = function() {
      try {
        inner.call(this);
      } catch (e) {
        return Promise.reject(e);
      }
    };
    stack.push([async, dispose, value]);
  } else if (async) {
    stack.push([async]);
  }
  return value;
};
var __callDispose3 = (stack, error, hasError) => {
  var E = typeof SuppressedError === "function" ? SuppressedError : function(e, s, m, _) {
    return _ = Error(m), _.name = "SuppressedError", _.error = e, _.suppressed = s, _;
  };
  var fail = (e) => error = hasError ? new E(e, error, "An error was suppressed during disposal") : (hasError = true, e);
  var next = (it) => {
    while (it = stack.pop()) {
      try {
        var result = it[1] && it[1].call(it[2]);
        if (it[0]) return Promise.resolve(result).then(next, (e) => (fail(e), next()));
      } catch (e) {
        fail(e);
      }
    }
    if (hasError) throw error;
  };
  return next();
};
function getManifest2(sharedKvStoreContext, dataFile, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "ocdbt:manifest",
    () => {
      const cache2 = new SimpleAsyncCache(
        sharedKvStoreContext.chunkManager.addRef(),
        {
          get: async (dataFile2, progressOptions) => {
            var _stack = [];
            try {
              const fullUrl = pipelineUrlJoin(
                dataFile2.baseUrl,
                dataFile2.relativePath
              );
              const _span = __using3(_stack, new ProgressSpan(progressOptions.progressListener, {
                message: `Reading OCDBT manifest from ${fullUrl}`
              }));
              const readResponse = await sharedKvStoreContext.kvStoreContext.read(
                fullUrl,
                {
                  ...progressOptions,
                  throwIfMissing: true
                }
              );
              try {
                const manifest = await decodeManifest2(
                  await readResponse.response.arrayBuffer(),
                  dataFile2.baseUrl,
                  progressOptions.signal
                );
                return { data: manifest, size: manifest.estimatedSize };
              } catch (e) {
                throw new Error(`Error reading OCDBT manifest from ${fullUrl}`, {
                  cause: e
                });
              }
            } catch (_) {
              var _error = _, _hasError = true;
            } finally {
              __callDispose3(_stack, _error, _hasError);
            }
          }
        }
      );
      cache2.registerDisposer(sharedKvStoreContext.addRef());
      return cache2;
    }
  );
  return cache.get(dataFile, options);
}
async function getResolvedManifest(sharedKvStoreContext, url, options) {
  const manifest = await getManifest2(
    sharedKvStoreContext,
    { baseUrl: url, relativePath: "manifest.ocdbt" },
    options
  );
  if (manifest.versionTree === void 0) {
    throw new Error("only manifest_kind=single is supported");
  }
  return manifest;
}
function makeIndirectDataReferenceCache(sharedKvStoreContext, description, decode2) {
  const cache = new SimpleAsyncCache(
    sharedKvStoreContext.chunkManager.addRef(),
    {
      get: async (location2, progressOptions) => {
        const { dataFile } = location2;
        const fullUrl = pipelineUrlJoin(
          dataFile.baseUrl,
          dataFile.relativePath
        );
        const readResponse = await sharedKvStoreContext.kvStoreContext.read(
          fullUrl,
          {
            ...progressOptions,
            throwIfMissing: true,
            byteRange: {
              offset: Number(location2.offset),
              length: Number(location2.length)
            }
          }
        );
        try {
          const node = await decode2(
            await readResponse.response.arrayBuffer(),
            dataFile.baseUrl,
            progressOptions.signal
          );
          return { data: node, size: node.estimatedSize };
        } catch (e) {
          throw new Error(
            `Error reading OCDBT ${description} from ${fullUrl}`,
            {
              cause: e
            }
          );
        }
      },
      encodeKey: ({ dataFile, offset, length: length6 }) => JSON.stringify([dataFile, `${offset}/${length6}`])
    }
  );
  cache.registerDisposer(sharedKvStoreContext.addRef());
  return cache;
}
function getBtreeNode(sharedKvStoreContext, location2, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "ocdbt:btree",
    () => makeIndirectDataReferenceCache(
      sharedKvStoreContext,
      "b+tree node",
      decodeBtreeNode
    )
  );
  return cache.get(location2, options);
}
function getVersionTreeNode(sharedKvStoreContext, location2, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "ocdbt:versionnode",
    () => makeIndirectDataReferenceCache(
      sharedKvStoreContext,
      "version tree node",
      decodeVersionTreeNode
    )
  );
  return cache.get(location2, options);
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/list.js
var DEBUG3 = false;
async function listRoot(sharedKvStoreContext, root2, prefix, options) {
  const entries = [];
  const directories = /* @__PURE__ */ new Set();
  if (!locationIsMissing(root2.root.location)) {
    await listSubtree(root2.root, root2.rootHeight, EMPTY_KEY, 0, {
      sharedKvStoreContext,
      prefix,
      entries,
      directories,
      signal: options.signal,
      progressListener: options.progressListener
    });
  }
  const response = normalizeListResponse({
    entries,
    directories: Array.from(directories)
  });
  if (DEBUG3) {
    console.log(JSON.stringify(response));
  }
  return response;
}
async function listSubtree(nodeReference, height, inclusiveMinKey, subtreeCommonPrefixLength, options) {
  var _a;
  (_a = options.signal) == null ? void 0 : _a.throwIfAborted();
  const node = await getBtreeNode(
    options.sharedKvStoreContext,
    nodeReference.location,
    options
  );
  validateBtreeNodeReference(
    node,
    height,
    inclusiveMinKey.subarray(subtreeCommonPrefixLength)
  );
  const subtreeKeyPrefix = concatKeys(
    inclusiveMinKey.subarray(0, subtreeCommonPrefixLength),
    node.keyPrefix
  );
  if (DEBUG3) {
    console.log("listSubtree", {
      nodeReference,
      height,
      inclusiveMinKey,
      subtreeCommonPrefixLength
    });
  }
  const addDirectoryIfValid = (key) => {
    try {
      options.directories.add(
        new TextDecoder("utf-8", { fatal: true }).decode(key)
      );
    } catch {
    }
  };
  const { prefix } = options;
  {
    const { offset, difference } = findFirstMismatch(prefix, subtreeKeyPrefix);
    if (difference !== 0 && offset < Math.min(prefix.length, subtreeKeyPrefix.length)) {
      return;
    }
  }
  if (prefix.length < subtreeKeyPrefix.length) {
    const separatorIndex = subtreeKeyPrefix.indexOf(47, prefix.length);
    if (separatorIndex !== -1) {
      addDirectoryIfValid(subtreeKeyPrefix.subarray(0, separatorIndex));
      return;
    }
  }
  const prefixForCurrentNode = prefix.subarray(subtreeKeyPrefix.length);
  if (node.height > 0) {
    const entries = node.entries;
    const [lower, upper] = findBtreeInteriorEntryPrefixRange(
      entries,
      prefixForCurrentNode
    );
    if (DEBUG3) {
      console.log(
        "Got entry range",
        lower,
        upper,
        entries.length,
        prefixForCurrentNode
      );
    }
    const promises = [];
    for (let entryIndex = lower; entryIndex < upper; ) {
      const entry = entries[entryIndex];
      ++entryIndex;
      const { key } = entry;
      const { subtreeCommonPrefixLength: subtreeCommonPrefixLength2 } = entry;
      if (subtreeCommonPrefixLength2 > prefixForCurrentNode.length) {
        const separatorIndex = key.indexOf(
          47,
          prefixForCurrentNode.length
        );
        if (separatorIndex !== -1) {
          const directoryPrefix = key.subarray(0, separatorIndex);
          addDirectoryIfValid(concatKeys(subtreeKeyPrefix, directoryPrefix));
          entryIndex = findBtreeEntryPrefixUpperBound(
            entries,
            entryIndex,
            upper,
            directoryPrefix
          );
          continue;
        }
      }
      promises.push(
        listSubtree(
          entry.node,
          height - 1,
          concatKeys(subtreeKeyPrefix, entry.key),
          subtreeKeyPrefix.length + entry.subtreeCommonPrefixLength,
          options
        )
      );
    }
    await Promise.all(promises);
  } else {
    const entries = node.entries;
    const [lower, upper] = findBtreeLeafEntryPrefixRange(
      entries,
      prefixForCurrentNode
    );
    for (let entryIndex = lower; entryIndex < upper; ) {
      const entry = entries[entryIndex];
      ++entryIndex;
      const { key } = entry;
      const separatorIndex = key.indexOf(
        47,
        prefixForCurrentNode.length
      );
      if (separatorIndex !== -1) {
        const directoryPrefix = key.subarray(0, separatorIndex);
        addDirectoryIfValid(concatKeys(subtreeKeyPrefix, directoryPrefix));
        entryIndex = findBtreeEntryPrefixUpperBound(
          entries,
          entryIndex,
          upper,
          key.subarray(0, separatorIndex + 1)
        );
        continue;
      }
      try {
        options.entries.push({
          key: new TextDecoder("utf-8", { fatal: true }).decode(
            concatKeys(subtreeKeyPrefix, key)
          )
        });
      } catch {
      }
    }
  }
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/read.js
init_legacy_browser();
var DEBUG4 = false;
async function findEntryInRoot(sharedKvStoreContext, root2, key, options) {
  if (locationIsMissing(root2.root.location)) {
    return void 0;
  }
  return await findEntryInSubtree(
    sharedKvStoreContext,
    root2.root,
    root2.rootHeight,
    EMPTY_KEY,
    key,
    options
  );
}
async function findEntryInSubtree(sharedKvStoreContext, nodeReference, nodeHeight, inclusiveMinKey, queryKey, options) {
  while (true) {
    const node = await getBtreeNode(
      sharedKvStoreContext,
      nodeReference.location,
      options
    );
    if (DEBUG4) {
      console.log(nodeReference, nodeHeight, node, inclusiveMinKey, queryKey);
    }
    validateBtreeNodeReference(node, nodeHeight, inclusiveMinKey);
    if (!keyStartsWith(queryKey, node.keyPrefix)) {
      if (DEBUG4) {
        console.log(
          "not found due to key prefix mismatch",
          queryKey,
          node.keyPrefix
        );
      }
      return void 0;
    }
    if (node.height === 0) {
      const entry2 = findBtreeLeafEntry(
        node.entries,
        queryKey
      );
      return entry2;
    }
    const entry = findBtreeInteriorEntry(
      node.entries,
      queryKey
    );
    if (entry === void 0) {
      return void 0;
    }
    const { subtreeCommonPrefixLength } = entry;
    queryKey = queryKey.subarray(subtreeCommonPrefixLength);
    nodeReference = entry.node;
    inclusiveMinKey = entry.key.subarray(subtreeCommonPrefixLength);
    --nodeHeight;
  }
}
async function readFromLeafNodeEntry(sharedKvStoreContext, entry, options) {
  const { value } = entry;
  if (value instanceof Uint8Array) {
    return handleByteRangeRequestFromUint8Array(value, options.byteRange);
  }
  const {
    offset,
    length: length6,
    dataFile: { baseUrl, relativePath }
  } = value;
  const { store, path } = sharedKvStoreContext.kvStoreContext.getKvStore(baseUrl);
  return await new FileByteRangeHandle(
    new KvStoreFileHandle(store, path + relativePath),
    { offset: Number(offset), length: Number(length6) }
  ).read(options);
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/read_version.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/version_specifier.js
init_legacy_browser();
function formatVersion(version) {
  if (version === void 0) return "HEAD";
  if ("generationNumber" in version) {
    return `v${version.generationNumber}`;
  }
  const { commitTime } = version;
  return formatCommitTime(commitTime);
}
function parseVersion(versionString) {
  if (versionString === void 0) return void 0;
  const m = versionString.match(
    /^(?:v([1-9]\d*)|(?:\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d*)?Z))$/
  );
  if (m === null) {
    throw new Error(
      `Invalid OCDBT version specifier: ${JSON.stringify(versionString)}`
    );
  }
  const [, generationString] = m;
  if (generationString !== void 0) {
    const generationNumber = BigInt(generationString);
    if (generationNumber > 0xffffffffffffffffn) {
      throw new Error(`Invalid generation number: ${generationNumber}`);
    }
    return { generationNumber };
  }
  return { commitTime: parseCommitTime(versionString) };
}
function parseCommitTime(versionString) {
  const m = versionString.match(
    /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:(\.\d*))?Z$/
  );
  if (m === null)
    throw new Error(
      `Invalid commit timestamp: ${JSON.stringify(versionString)}`
    );
  const [, commitTimeString, commitTimeFractionalSeconds] = m;
  return commitTimeFromSecondsAndSubseconds(
    Date.parse(commitTimeString + "Z"),
    commitTimeFractionalSeconds
  );
}
function commitTimeFromSecondsAndSubseconds(seconds, subseconds) {
  let commitTime = BigInt(seconds) * 1000000n;
  if (subseconds !== void 0 && subseconds.length > 1) {
    const fraction = Number(subseconds);
    commitTime += BigInt(Math.min(999999999, Math.round(fraction * 1e9)));
  }
  return commitTime;
}
function formatCommitTime(commitTime) {
  let fractionalSeconds = commitTime % 1000000000n;
  let seconds = commitTime / 1000000000n;
  if (fractionalSeconds < 0n) {
    fractionalSeconds += 1000000000n;
    seconds -= 1n;
  }
  let timestampString = new Date(Number(seconds) * 1e3).toISOString();
  if (timestampString.length !== 24) {
    throw new Error(`Invalid commit time: ${commitTime} -> ${timestampString}`);
  }
  timestampString = timestampString.slice(0, 19);
  if (fractionalSeconds !== 0n) {
    timestampString += "." + fractionalSeconds.toString().padStart(9, "0").replace(/0+$/, "");
  }
  timestampString += "Z";
  return timestampString;
}
var COMMIT_TIME_PREFIX_REGEXP = new RegExp(
  "^(\\d{0,4})(?:(?<=\\d{4})-(\\d{0,2})(?:(?<=\\d{2})-(\\d{0,2})(?:(?<=\\d{2})T(\\d{0,2})(?:(?<=\\d{2}):(\\d{0,2})(?:(?<=\\d{2}):(\\d{0,2})(?:(?<=\\d{2})(\\.\\d*)?(Z)?)?)?)?)?)?)?$"
);
function getMinMaxDateComponent(componentName, prefix, digits, inclusiveMinBound, inclusiveMaxBound) {
  prefix = prefix ?? "";
  const min4 = parseInt(prefix.padEnd(digits, "0"), 10);
  const max4 = parseInt(prefix.padEnd(digits, "9"), 10);
  if (min4 > inclusiveMaxBound) {
    throw new Error(`Invalid ${componentName} prefix: ${prefix}`);
  }
  return [Math.max(inclusiveMinBound, min4), Math.min(inclusiveMaxBound, max4)];
}
function getDaysInMonth(year, month) {
  const d = /* @__PURE__ */ new Date(0);
  d.setUTCFullYear(year);
  d.setUTCMonth(month);
  d.setUTCDate(0);
  return d.getUTCDate();
}
function parseCommitTimePrefix(versionString) {
  const m = versionString.match(COMMIT_TIME_PREFIX_REGEXP);
  if (m === null) {
    throw new Error(
      `Expected prefix of ISO-8601 "YYYY-MM-DDThh:mm:ss.sssssssssZ" format, but received: ${JSON.stringify(versionString)}`
    );
  }
  const year = getMinMaxDateComponent("year", m[1], 4, 0, 9999);
  const month = getMinMaxDateComponent("month", m[2], 2, 1, 12);
  const daysInMaxMonth = getDaysInMonth(year[1], month[1]);
  const day = getMinMaxDateComponent("day", m[3], 2, 1, daysInMaxMonth);
  const hour = getMinMaxDateComponent("hour", m[4], 2, 0, 23);
  const minute = getMinMaxDateComponent("minute", m[5], 2, 0, 59);
  const second = getMinMaxDateComponent("second", m[6], 2, 0, 59);
  const subsecondString = m[7] ?? ".";
  const z = m[8];
  const minSubseconds = subsecondString.padEnd(10, "0");
  const maxSubseconds = z === void 0 ? subsecondString.padEnd(10, "9") : minSubseconds;
  const subseconds = [minSubseconds, maxSubseconds];
  function getDate(i) {
    const date = /* @__PURE__ */ new Date(0);
    date.setUTCFullYear(year[i]);
    date.setUTCMonth(month[i] - 1);
    date.setUTCDate(day[i]);
    date.setUTCHours(hour[i]);
    date.setUTCMinutes(minute[i]);
    date.setUTCSeconds(second[i]);
    return commitTimeFromSecondsAndSubseconds(date.getTime(), subseconds[i]);
  }
  return [getDate(0), getDate(1)];
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/read_version.js
async function getRoot(sharedKvStoreContext, url, version, options) {
  const cache = sharedKvStoreContext.chunkManager.memoize.get(
    "ocdbt:version",
    () => {
      const cache2 = new SimpleAsyncCache(sharedKvStoreContext.chunkManager.addRef(), {
        get: async ({ url: url2, version: version2 }, progressOptions) => {
          const manifest = await getResolvedManifest(
            sharedKvStoreContext,
            url2,
            progressOptions
          );
          const root2 = await readVersion(
            sharedKvStoreContext,
            manifest,
            version2,
            options
          );
          if (root2 === void 0) {
            throw new Error(`Version ${formatVersion(version2)} not found`);
          }
          return {
            data: root2.ref,
            // BtreeGenerationReference is a tiny object, size may as well be 0
            size: 0
          };
        },
        encodeKey: ({ url: url2, version: version2 }) => {
          let versionString;
          if (version2 !== void 0) {
            versionString = formatVersion(version2);
          }
          return JSON.stringify([url2, versionString]);
        }
      });
      cache2.registerDisposer(sharedKvStoreContext.addRef());
      return cache2;
    }
  );
  return cache.get({ url, version }, options);
}
async function readVersion(sharedKvStoreContext, manifest, version, options) {
  var _a;
  const { versionTree } = manifest;
  if (version === void 0) {
    const { versionTreeNodes, inlineVersions } = versionTree;
    const index = inlineVersions.length - 1;
    return {
      ref: inlineVersions[index],
      generationIndex: (((_a = versionTreeNodes.at(-1)) == null ? void 0 : _a.cumulativeNumGenerations) ?? 0n) + BigInt(index)
    };
  }
  const { ref, generationIndex } = await findVersion(
    sharedKvStoreContext,
    manifest,
    version,
    options
  );
  if (ref === void 0) return void 0;
  return { ref, generationIndex };
}
async function findVersionIndexByLowerBound(sharedKvStoreContext, manifest, version, options) {
  const { generationIndex } = await findVersionLowerBoundImpl(
    sharedKvStoreContext,
    manifest,
    version,
    options
  );
  return generationIndex;
}
async function findVersionIndexByUpperBound(sharedKvStoreContext, manifest, version, options) {
  const { generationIndex } = await findVersionUpperBoundImpl(
    sharedKvStoreContext,
    manifest,
    version,
    options
  );
  return generationIndex;
}
function findVersionImpl(options) {
  const { isInline, findInLeaf, findInInterior } = options;
  async function findVersion2(sharedKvStoreContext, manifest, query, progressOptions) {
    var _a;
    const { config, versionTree } = manifest;
    const generationIndex = ((_a = versionTree.versionTreeNodes.at(-1)) == null ? void 0 : _a.cumulativeNumGenerations) ?? 0n;
    const { inlineVersions } = versionTree;
    if (isInline(config, generationIndex, inlineVersions, query)) {
      const index = findInLeaf(config, generationIndex, inlineVersions, query);
      return {
        ref: inlineVersions[index],
        generationIndex: generationIndex + BigInt(index)
      };
    }
    const { versionTreeNodes } = versionTree;
    if (versionTreeNodes.length === 0) {
      return { ref: void 0, generationIndex: 0n };
    }
    const ref = findInInterior(config, 0n, versionTreeNodes, query);
    if (ref === void 0) return { ref: void 0, generationIndex: 0n };
    return await findInSubtree(
      sharedKvStoreContext,
      manifest.config,
      0n + ref.cumulativeNumGenerations - ref.numGenerations,
      ref,
      query,
      progressOptions
    );
  }
  async function findInSubtree(sharedKvStoreContext, config, generationIndex, ref, query, progressOptions) {
    while (true) {
      const node = await getVersionTreeNode(
        sharedKvStoreContext,
        ref.location,
        progressOptions
      );
      validateVersionTreeNodeReference(
        node,
        config,
        ref.generationNumber,
        ref.height,
        ref.numGenerations
      );
      if (node.height === 0) {
        const entries = node.entries;
        const index = findInLeaf(config, generationIndex, entries, query);
        return {
          ref: entries[index],
          generationIndex: generationIndex + BigInt(index)
        };
      }
      const result = findInInterior(
        config,
        generationIndex,
        node.entries,
        query
      );
      if (result === void 0) return { ref: void 0, generationIndex };
      ref = result;
      generationIndex += ref.cumulativeNumGenerations - ref.numGenerations;
    }
  }
  return findVersion2;
}
function isVersionQueryInline(generationIndex, versions, version) {
  if ("generationIndex" in version) {
    return version.generationIndex >= generationIndex;
  }
  return compareVersionSpecToVersion(version, versions[0]) >= 0;
}
var findVersion = findVersionImpl({
  isInline(_config, generationIndex, versions, version) {
    return isVersionQueryInline(generationIndex, versions, version);
  },
  findInLeaf(_config, generationIndex, versions, version) {
    return findLeafVersion(generationIndex, versions, version);
  },
  findInInterior(config, generationIndex, versionNodes, version) {
    return findVersionNode(
      config.versionTreeArityLog2,
      generationIndex,
      versionNodes,
      version
    );
  }
});
var findVersionLowerBoundImpl = findVersionImpl({
  isInline(_config, generationIndex, versions, version) {
    return isVersionQueryInline(generationIndex, versions, version);
  },
  findInLeaf(_config, generationIndex, versions, version) {
    return findLeafVersionIndexByLowerBound(generationIndex, versions, version);
  },
  findInInterior(config, generationIndex, versionNodes, version) {
    const index = findVersionNodeIndexByLowerBound(
      config.versionTreeArityLog2,
      generationIndex,
      versionNodes,
      version
    );
    return versionNodes[index];
  }
});
var findVersionUpperBoundImpl = findVersionImpl({
  isInline(_config, generationIndex, versions, version) {
    return isVersionQueryInline(generationIndex, versions, version);
  },
  findInLeaf(_config, generationIndex, versions, version) {
    return findLeafVersionIndexByLowerBound(generationIndex, versions, version);
  },
  findInInterior(_config, generationIndex, versionNodes, version) {
    const index = findVersionNodeIndexByUpperBound(
      generationIndex,
      versionNodes,
      version
    );
    return versionNodes[index];
  }
});

// node_modules/neuroglancer/lib/kvstore/ocdbt/url.js
init_legacy_browser();
function getOcdbtUrl(options, key) {
  const { version, baseUrl } = options;
  const versionString = version === void 0 ? "" : `@${formatVersion(version)}/`;
  return baseUrl + `|ocdbt:${versionString}${encodePathForUrl(key)}`;
}
function parseOcdbtUrl(parsedUrl, base) {
  ensureNoQueryOrFragmentParameters(parsedUrl);
  try {
    const m = (parsedUrl.suffix ?? "").match(/^(?:@([^/]*)(?:\/|$))?(.*)$/);
    const [, versionString, path] = m;
    return {
      baseUrl: base.store.getUrl(ensurePathIsDirectory(base.path)),
      version: parseVersion(versionString),
      path: decodeURIComponent(path)
    };
  } catch (e) {
    throw new Error(`Invalid URL: ${parsedUrl.url}`, { cause: e });
  }
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/backend.js
var OcdbtKvStore = class {
  constructor(sharedKvStoreContext, baseUrl, version) {
    this.sharedKvStoreContext = sharedKvStoreContext;
    this.baseUrl = baseUrl;
    this.version = version;
  }
  root;
  async getRoot(options) {
    let { root: root2 } = this;
    if (root2 === void 0) {
      root2 = this.root = await getRoot(
        this.sharedKvStoreContext,
        this.baseUrl,
        this.version,
        options
      );
    }
    return root2;
  }
  getUrl(key) {
    return getOcdbtUrl(this, key);
  }
  async stat(key, options) {
    const root2 = await this.getRoot(options);
    const encodedKey = new TextEncoder().encode(key);
    const entry = await findEntryInRoot(
      this.sharedKvStoreContext,
      root2,
      encodedKey,
      options
    );
    if (entry === void 0) return void 0;
    const { value } = entry;
    const totalSize = Number(value.length);
    return { totalSize };
  }
  async read(key, options) {
    const root2 = await this.getRoot(options);
    const encodedKey = new TextEncoder().encode(key);
    const entry = await findEntryInRoot(
      this.sharedKvStoreContext,
      root2,
      encodedKey,
      options
    );
    if (entry === void 0) return void 0;
    return await readFromLeafNodeEntry(
      this.sharedKvStoreContext,
      entry,
      options
    );
  }
  async list(prefix, options) {
    const root2 = await this.getRoot(options);
    const encodedPrefix = new TextEncoder().encode(prefix);
    return await listRoot(
      this.sharedKvStoreContext,
      root2,
      encodedPrefix,
      options
    );
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};

// node_modules/neuroglancer/lib/kvstore/ocdbt/complete_url.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/ocdbt/list_versions.js
init_legacy_browser();
var DEBUG5 = false;
async function listVersions(sharedKvStoreContext, manifest, options) {
  var _a;
  const { inclusiveMin, exclusiveMax } = options;
  if (DEBUG5) {
    console.log("listVersions", inclusiveMin, exclusiveMax);
  }
  const resolvedInclusiveMin = inclusiveMin === void 0 ? { generationIndex: 0n } : inclusiveMin;
  const resolvedExclusiveMax = exclusiveMax === void 0 ? { generationIndex: manifest.versionTree.numGenerations } : exclusiveMax;
  const { config, versionTree } = manifest;
  const { versionTreeArityLog2 } = config;
  let minGenerationIndex;
  const results = [];
  {
    const generationIndex = ((_a = versionTree.versionTreeNodes.at(-1)) == null ? void 0 : _a.cumulativeNumGenerations) ?? 0n;
    visitLeafEntries(generationIndex, versionTree.inlineVersions);
    await visitInteriorEntries(0n, versionTree.versionTreeNodes);
  }
  function visitLeafEntries(generationIndex, versions) {
    const lower = findLeafVersionIndexByLowerBound(
      generationIndex,
      versions,
      resolvedInclusiveMin
    );
    const upper = findLeafVersionIndexByLowerBound(
      generationIndex,
      versions,
      resolvedExclusiveMax
    );
    const resultGenerationIndex = generationIndex + BigInt(lower);
    if (minGenerationIndex === void 0 || resultGenerationIndex < minGenerationIndex) {
      minGenerationIndex = resultGenerationIndex;
    }
    for (let i = lower; i < upper; ++i) {
      results.push(versions[i]);
    }
  }
  async function visitInteriorEntries(generationIndex, versionNodes) {
    var _a2;
    (_a2 = options.signal) == null ? void 0 : _a2.throwIfAborted();
    const lower = findVersionNodeIndexByLowerBound(
      versionTreeArityLog2,
      generationIndex,
      versionNodes,
      resolvedInclusiveMin
    );
    const upper = findVersionNodeIndexByUpperBound(
      generationIndex,
      versionNodes,
      resolvedExclusiveMax
    );
    if (DEBUG5) {
      console.log(
        "listVersions: visitInteriorEntries",
        resolvedInclusiveMin,
        resolvedExclusiveMax,
        `generationIndex=${generationIndex}`,
        `versionNodes.length=${versionNodes.length}`,
        lower,
        upper
      );
    }
    const promises = [];
    for (let i = lower; i < upper; ++i) {
      const ref = versionNodes[i];
      promises.push(
        visitNodeRef(
          generationIndex + ref.cumulativeNumGenerations - ref.numGenerations,
          ref
        )
      );
    }
    await Promise.all(promises);
  }
  async function visitNodeRef(generationIndex, ref) {
    const node = await getVersionTreeNode(
      sharedKvStoreContext,
      ref.location,
      options
    );
    validateVersionTreeNodeReference(
      node,
      config,
      ref.generationNumber,
      ref.height,
      ref.numGenerations
    );
    if (node.height === 0) {
      visitLeafEntries(
        generationIndex,
        node.entries
      );
    } else {
      await visitInteriorEntries(
        generationIndex,
        node.entries
      );
    }
  }
  results.sort((a, b) => bigintCompare(a.generationNumber, b.generationNumber));
  return { generationIndex: minGenerationIndex ?? 0n, versions: results };
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/complete_url.js
async function listVersionsLimited(sharedKvStoreContext, manifest, minGenerationIndex, maxGenerationIndex, limit, options) {
  if (maxGenerationIndex <= minGenerationIndex + limit) {
    const { versions } = await listVersions(sharedKvStoreContext, manifest, {
      inclusiveMin: { generationIndex: minGenerationIndex },
      exclusiveMax: { generationIndex: maxGenerationIndex },
      ...options
    });
    return versions;
  }
  const [{ versions: lowerVersions }, { versions: upperVersions }] = await Promise.all(
    [minGenerationIndex, maxGenerationIndex - limit / 2n].map(
      (generationIndex) => listVersions(sharedKvStoreContext, manifest, {
        inclusiveMin: { generationIndex },
        exclusiveMax: { generationIndex: generationIndex + limit / 2n },
        ...options
      })
    )
  );
  return [...lowerVersions, ...upperVersions];
}
async function completeOcdbtUrl(sharedKvStoreContext, options) {
  const { url } = options;
  const suffix = url.suffix ?? "";
  if (suffix === "") {
    return {
      offset: 0,
      completions: [{ value: "@", description: "Version specifier" }]
    };
  }
  const m = suffix.match(/^@([^/]*)((?:\/|$).*)/);
  if (m === null) return void 0;
  const [, version, rest] = m;
  if (rest !== "") {
    parseVersion(version);
    return void 0;
  }
  const { base } = options;
  const baseUrl = base.store.getUrl(ensurePathIsDirectory(base.path));
  if (!version.startsWith("v")) {
    const [inclusiveMin, inclusiveMax] = parseCommitTimePrefix(version);
    const progressOptions = {
      signal: options.signal,
      progressListener: options.progressListener
    };
    const manifest = await getResolvedManifest(
      sharedKvStoreContext,
      baseUrl,
      progressOptions
    );
    const [minVersion, maxVersion] = await Promise.all([
      findVersionIndexByLowerBound(
        sharedKvStoreContext,
        manifest,
        { commitTime: inclusiveMin },
        progressOptions
      ),
      findVersionIndexByUpperBound(
        sharedKvStoreContext,
        manifest,
        { commitTime: inclusiveMax + 1n },
        progressOptions
      )
    ]);
    const versions = await listVersionsLimited(
      sharedKvStoreContext,
      manifest,
      minVersion,
      maxVersion,
      100n,
      {
        signal: options.signal,
        progressListener: options.progressListener
      }
    );
    const completions = versions.map((version2) => ({
      value: `${formatCommitTime(version2.commitTime)}/`,
      description: `v${version2.generationNumber}`
    }));
    completions.reverse();
    return { offset: 1, completions };
  }
  if (version === "v") {
    const { base: base2 } = options;
    const manifest = await getResolvedManifest(
      sharedKvStoreContext,
      base2.store.getUrl(base2.path),
      options
    );
    const completions = manifest.versionTree.inlineVersions.map((ref) => ({
      value: `v${ref.generationNumber}/`,
      description: formatCommitTime(ref.commitTime)
    }));
    completions.reverse();
    return { offset: 1, completions };
  }
  return { offset: 1, completions: [{ value: `${version}/` }] };
}

// node_modules/neuroglancer/lib/kvstore/ocdbt/register_backend.js
function ocdbtProvider(sharedKvStoreContext) {
  return {
    scheme: "ocdbt",
    description: "OCDBT database",
    getKvStore(parsedUrl, base) {
      const { baseUrl, version, path } = parseOcdbtUrl(parsedUrl, base);
      return {
        store: new OcdbtKvStore(sharedKvStoreContext, baseUrl, version),
        path
      };
    },
    completeUrl(options) {
      return completeOcdbtUrl(sharedKvStoreContext, options);
    }
  };
}
backendOnlyKvStoreProviderRegistry.registerKvStoreAdapterProvider(
  ocdbtProvider
);

// node_modules/neuroglancer/lib/kvstore/s3/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/s3/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/s3/common.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/s3/list.js
init_legacy_browser();
var EXPECTED_XML_NAMESPACE_URIS = [
  "http://doc.s3.amazonaws.com/2006-03-01/",
  "http://s3.amazonaws.com/doc/2006-03-01/"
];
function isValidListObjectsResponse(documentElement) {
  return EXPECTED_XML_NAMESPACE_URIS.includes(documentElement.namespaceURI) && documentElement.tagName === "ListBucketResult";
}
async function getS3BucketListing(bucketUrl, prefix, fetchOkImpl, options) {
  const delimiter = "/";
  try {
    const response = await fetchOkImpl(
      `${bucketUrl}?list-type=2&prefix=${encodeURIComponent(prefix)}&delimiter=${encodeURIComponent(delimiter)}&encoding-type=url`,
      /*init=*/
      {
        headers: { accept: "application/xml,text/xml" },
        signal: options.signal,
        progressListener: options.progressListener
      }
    );
    const contentType = response.headers.get("content-type");
    if (contentType === null || /\b(application\/xml|text\/xml|text\/html)\b/i.exec(contentType) === null) {
      throw new Error(`Expected XML content-type but received: ${contentType}`);
    }
    const text = await response.text();
    const doc = new DOMParser().parseFromString(text, "application/xml");
    const { documentElement } = doc;
    if (!isValidListObjectsResponse(documentElement)) {
      throw new Error(
        `Received unexpected XML root element <${documentElement.tagName} xmlns="${documentElement.namespaceURI}">`
      );
    }
    const namespaceURI = documentElement.namespaceURI;
    const namespaceResolver = () => namespaceURI;
    const commonPrefixNodes = doc.evaluate(
      "//CommonPrefixes/Prefix",
      doc,
      namespaceResolver,
      XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE,
      null
    );
    const directories = [];
    for (let i = 0, n = commonPrefixNodes.snapshotLength; i < n; ++i) {
      let name = commonPrefixNodes.snapshotItem(i).textContent;
      if (name === null) continue;
      name = decodeURIComponent(name);
      directories.push(name.substring(0, name.length - delimiter.length));
    }
    const entries = [];
    const contents = doc.evaluate(
      "//Contents/Key",
      doc,
      namespaceResolver,
      XPathResult.UNORDERED_NODE_SNAPSHOT_TYPE,
      null
    );
    for (let i = 0, n = contents.snapshotLength; i < n; ++i) {
      const name = contents.snapshotItem(i).textContent;
      if (name === null) continue;
      entries.push({ key: decodeURIComponent(name) });
    }
    return { directories, entries };
  } catch (e) {
    throw new Error(`S3-compatible listing not supported`, { cause: e });
  }
}
function getVirtualHostedStyleListing(url, fetchOkImpl, options) {
  const { baseUrl, path } = getBaseHttpUrlAndPath(url);
  return getS3BucketListing(baseUrl, path, fetchOkImpl, options);
}
function parsePathStyleUrl(url) {
  const u = new URL(url);
  const m = u.pathname.match(/^\/([^/]+)(?:\/(.*))$/);
  if (m === null) {
    return void 0;
  }
  const [, bucket, path] = m;
  return {
    bucketUrl: `${u.origin}/${bucket}/${u.search}`,
    bucket: decodeURIComponent(bucket),
    prefix: decodeURIComponent(path)
  };
}
async function getPathStyleListing(url, fetchOkImpl, options) {
  const parsed = parsePathStyleUrl(url);
  if (parsed === void 0) {
    throw new Error(
      `Path-style S3 URL ${JSON.stringify(url)} must specify bucket`
    );
  }
  const { bucketUrl, bucket, prefix } = parsed;
  const response = await getS3BucketListing(
    bucketUrl,
    prefix,
    fetchOkImpl,
    options
  );
  const bucketPrefix = encodePathForUrl(bucket) + "/";
  return {
    entries: response.entries.map((entry) => ({
      key: bucketPrefix + entry.key
    })),
    directories: response.directories.map((name) => bucketPrefix + name)
  };
}
function getUrlKindCache(memoize) {
  return memoize.getUncounted(
    "s3:urlkind",
    () => /* @__PURE__ */ new Map()
  );
}
async function listS3CompatibleUrl(url, origin, memoize, fetchOkImpl, options) {
  var _a;
  const cache = getUrlKindCache(memoize);
  const urlKind = cache.get(origin);
  if (urlKind === "virtual") {
    return await getVirtualHostedStyleListing(url, fetchOkImpl, options);
  }
  if (urlKind === "path") {
    return await getPathStyleListing(url, fetchOkImpl, options);
  }
  if (urlKind !== null) {
    try {
      const { result, urlKind: urlKind2 } = await Promise.any([
        getVirtualHostedStyleListing(url, fetchOkImpl, options).then(
          (result2) => ({
            result: result2,
            urlKind: "virtual"
          })
        ),
        getPathStyleListing(url, fetchOkImpl, options).then((result2) => ({
          result: result2,
          urlKind: "path"
        }))
      ]);
      cache.set(origin, urlKind2);
      return result;
    } catch (e) {
      (_a = options.signal) == null ? void 0 : _a.throwIfAborted();
      cache.set(origin, null);
      throw new Error(
        `Neither virtual hosted nor path-style S3 listing supported`,
        { cause: e }
      );
    }
  }
  throw new Error(`Neither virtual hosted nor path-style S3 listing supported`);
}

// node_modules/neuroglancer/lib/kvstore/s3/common.js
var __knownSymbol4 = (name, symbol) => (symbol = Symbol[name]) ? symbol : Symbol.for("Symbol." + name);
var __typeError4 = (msg) => {
  throw TypeError(msg);
};
var __using4 = (stack, value, async) => {
  if (value != null) {
    if (typeof value !== "object" && typeof value !== "function") __typeError4("Object expected");
    var dispose, inner;
    if (async) dispose = value[__knownSymbol4("asyncDispose")];
    if (dispose === void 0) {
      dispose = value[__knownSymbol4("dispose")];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") __typeError4("Object not disposable");
    if (inner) dispose = function() {
      try {
        inner.call(this);
      } catch (e) {
        return Promise.reject(e);
      }
    };
    stack.push([async, dispose, value]);
  } else if (async) {
    stack.push([async]);
  }
  return value;
};
var __callDispose4 = (stack, error, hasError) => {
  var E = typeof SuppressedError === "function" ? SuppressedError : function(e, s, m, _) {
    return _ = Error(m), _.name = "SuppressedError", _.error = e, _.suppressed = s, _;
  };
  var fail = (e) => error = hasError ? new E(e, error, "An error was suppressed during disposal") : (hasError = true, e);
  var next = (it) => {
    while (it = stack.pop()) {
      try {
        var result = it[1] && it[1].call(it[2]);
        if (it[0]) return Promise.resolve(result).then(next, (e) => (fail(e), next()));
      } catch (e) {
        fail(e);
      }
    }
    if (hasError) throw error;
  };
  return next();
};
var ReadableS3KvStore = class {
  constructor(sharedKvStoreContext, baseUrl, baseUrlForDisplay, knownToBeVirtualHostedStyle, fetchOkImpl = fetchOk) {
    this.sharedKvStoreContext = sharedKvStoreContext;
    this.baseUrl = baseUrl;
    this.baseUrlForDisplay = baseUrlForDisplay;
    this.knownToBeVirtualHostedStyle = knownToBeVirtualHostedStyle;
    this.fetchOkImpl = fetchOkImpl;
  }
  stat(key, options) {
    const url = joinBaseUrlAndPath(this.baseUrl, key);
    return stat(this, key, url, options, this.fetchOkImpl);
  }
  read(key, options) {
    const url = joinBaseUrlAndPath(this.baseUrl, key);
    return read(this, key, url, options, this.fetchOkImpl);
  }
  list(prefix, options) {
    var _stack = [];
    try {
      const { progressListener } = options;
      const _span = __using4(_stack, progressListener === void 0 ? void 0 : new ProgressSpan(progressListener, {
        message: `Listing prefix ${this.getUrl(prefix)}`
      }));
      if (this.knownToBeVirtualHostedStyle) {
        return getS3BucketListing(
          this.baseUrl,
          prefix,
          this.fetchOkImpl,
          options
        );
      }
      return listS3CompatibleUrl(
        joinBaseUrlAndPath(this.baseUrl, prefix),
        this.baseUrlForDisplay,
        this.sharedKvStoreContext.chunkManager.memoize,
        this.fetchOkImpl,
        options
      );
    } catch (_) {
      var _error = _, _hasError = true;
    } finally {
      __callDispose4(_stack, _error, _hasError);
    }
  }
  getUrl(path) {
    return joinBaseUrlAndPath(this.baseUrlForDisplay, path);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};
function amazonS3Provider(sharedKvStoreContext, s3KvStoreClass) {
  return {
    scheme: "s3",
    description: "S3 (anonymous)",
    getKvStore(url) {
      const m = (url.suffix ?? "").match(/^\/\/([^/]+)(\/.*)?$/);
      if (m === null) {
        throw new Error("Invalid URL, expected `s3://<bucket>/<path>`");
      }
      const [, bucket, path] = m;
      return {
        store: new s3KvStoreClass(
          sharedKvStoreContext,
          `https://${bucket}.s3.amazonaws.com/`,
          `s3://${bucket}/`,
          /*knownToBeVirtualHostedStyle=*/
          true
        ),
        path: decodeURIComponent((path ?? "").substring(1))
      };
    }
  };
}
function s3Provider(sharedKvStoreContext, httpScheme, s3KvStoreClass) {
  return {
    scheme: `s3+${httpScheme}`,
    description: `S3-compatible ${httpScheme} server`,
    getKvStore(url) {
      const m = (url.suffix ?? "").match(/^\/\/([^/]+)(\/.*)?$/);
      if (m === null) {
        throw new Error(
          "Invalid URL, expected `s3+${httpScheme}://<host>/<path>`"
        );
      }
      const [, host, path] = m;
      return {
        store: new s3KvStoreClass(
          sharedKvStoreContext,
          `${httpScheme}://${host}/`,
          `s3+${httpScheme}://${host}/`,
          /*knownToBeVirtualHostedStyle=*/
          false
        ),
        path: decodeURIComponent((path ?? "").substring(1))
      };
    }
  };
}
function registerProviders3(registry, s3KvStoreClass) {
  registry.registerBaseKvStoreProvider(
    (context) => amazonS3Provider(context, s3KvStoreClass)
  );
  for (const httpScheme of ["http", "https"]) {
    registry.registerBaseKvStoreProvider(
      (context) => s3Provider(context, httpScheme, s3KvStoreClass)
    );
  }
}

// node_modules/neuroglancer/lib/kvstore/s3/backend.js
var S3KvStore = class extends ReadableS3KvStore {
  list(prefix, options) {
    return proxyList(this.sharedKvStoreContext, this.getUrl(prefix), options);
  }
};

// node_modules/neuroglancer/lib/kvstore/s3/register_backend.js
registerProviders3(backendOnlyKvStoreProviderRegistry, S3KvStore);

// node_modules/neuroglancer/lib/kvstore/zip/register_backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/zip/backend.js
init_legacy_browser();

// node_modules/neuroglancer/lib/kvstore/zip/metadata.js
init_legacy_browser();
var import_crc_32 = __toESM(require_crc32(), 1);
var EOCDR_WITHOUT_COMMENT_SIZE = 22;
var MAX_COMMENT_SIZE = 65535;
var EOCDR_SIGNATURE = 101010256;
var ZIP64_EOCDR_SIGNATURE = 101075792;
function lastReadCachingReader(base) {
  let lastReadOffset = 0;
  let lastReadBuffer;
  return async function lastReadCachingRead(offset, length6, progressOptions) {
    if (lastReadBuffer !== void 0) {
      if (offset > lastReadOffset && offset + length6 <= lastReadOffset + lastReadBuffer.length) {
        return lastReadBuffer.subarray(
          offset - lastReadOffset,
          offset + length6 - lastReadOffset
        );
      }
    }
    const newBuffer = await base(offset, length6, progressOptions);
    lastReadOffset = offset;
    lastReadBuffer = newBuffer;
    return newBuffer;
  };
}
function parseEndOfCentralDirectoryRecord(data) {
  const dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const size = data.length;
  for (let i = size - EOCDR_WITHOUT_COMMENT_SIZE; i >= 0; --i) {
    if (dv.getUint32(
      i,
      /*littleEndian=*/
      true
    ) !== EOCDR_SIGNATURE) {
      continue;
    }
    const commentLength = dv.getUint16(
      i + 20,
      /*littleEndian=*/
      true
    );
    const expectedCommentLength = size - i - EOCDR_WITHOUT_COMMENT_SIZE;
    if (commentLength !== expectedCommentLength) {
      continue;
    }
    const diskNumber = dv.getUint16(
      i + 4,
      /*littleEndian=*/
      true
    );
    const entryCount = dv.getUint16(
      i + 10,
      /*littleEndian=*/
      true
    );
    const centralDirectorySize = dv.getUint32(
      i + 12,
      /*littleEndian=*/
      true
    );
    const centralDirectoryOffset = dv.getUint32(
      i + 16,
      /*littleEndian=*/
      true
    );
    return {
      eocdrOffset: i,
      diskNumber,
      entryCount,
      centralDirectorySize,
      centralDirectoryOffset
    };
  }
  return void 0;
}
async function findEndOfCentralDirectory(reader, totalLength, options) {
  const size = Math.min(
    EOCDR_WITHOUT_COMMENT_SIZE + MAX_COMMENT_SIZE,
    totalLength
  );
  const readStart = totalLength - size;
  const data = await reader(readStart, size, options);
  const record2 = parseEndOfCentralDirectoryRecord(data);
  if (record2 === void 0) {
    throw new Error(
      "End of central directory record signature not found; either not a zip file or file is truncated."
    );
  }
  const {
    eocdrOffset,
    diskNumber,
    entryCount,
    centralDirectorySize,
    centralDirectoryOffset
  } = record2;
  if (diskNumber !== 0) {
    throw new Error(
      `Multi-volume zip files are not supported. This is volume: ${diskNumber}`
    );
  }
  const commentBytes = data.slice(eocdrOffset + 22, data.length);
  if (entryCount === 65535 || centralDirectoryOffset === 4294967295) {
    return await readZip64CentralDirectory(
      reader,
      eocdrOffset,
      commentBytes,
      options
    );
  } else {
    return await readEntries(
      reader,
      centralDirectoryOffset,
      centralDirectorySize,
      entryCount,
      commentBytes,
      options
    );
  }
}
var END_OF_CENTRAL_DIRECTORY_LOCATOR_SIGNATURE = 117853008;
async function readZip64CentralDirectory(reader, offset, commentBytes, progressOptions) {
  const zip64EocdlOffset = offset - 20;
  const eocdl = await reader(zip64EocdlOffset, 20, progressOptions);
  const eocdlDv = new DataView(
    eocdl.buffer,
    eocdl.byteOffset,
    eocdl.byteLength
  );
  if (eocdlDv.getUint32(
    0,
    /*littleEndian=*/
    true
  ) !== END_OF_CENTRAL_DIRECTORY_LOCATOR_SIGNATURE) {
    throw new Error("invalid zip64 end of central directory locator signature");
  }
  const zip64EocdrOffset = eocdlDv.getBigUint64(
    8,
    /*littleEndian=*/
    true
  );
  const zip64Eocdr = await reader(
    Number(zip64EocdrOffset),
    56,
    progressOptions
  );
  const zip64EocdrDv = new DataView(
    zip64Eocdr.buffer,
    zip64Eocdr.byteOffset,
    zip64Eocdr.byteLength
  );
  if (zip64EocdrDv.getUint32(
    0,
    /*littleEndian=*/
    true
  ) !== ZIP64_EOCDR_SIGNATURE) {
    throw new Error("invalid zip64 end of central directory record signature");
  }
  const entryCount = zip64EocdrDv.getBigUint64(
    32,
    /*littleEndian=*/
    true
  );
  const centralDirectorySize = zip64EocdrDv.getBigUint64(
    40,
    /*littleEndian=*/
    true
  );
  const centralDirectoryOffset = zip64EocdrDv.getBigUint64(
    48,
    /*littleEndian=*/
    true
  );
  return readEntries(
    reader,
    Number(centralDirectoryOffset),
    Number(centralDirectorySize),
    Number(entryCount),
    commentBytes,
    progressOptions
  );
}
var CENTRAL_DIRECTORY_FILE_HEADER_SIGNATURE = 33639248;
async function readEntries(reader, centralDirectoryOffset, centralDirectorySize, rawEntryCount, commentBytes, progressOptions) {
  let readEntryCursor = 0;
  const allEntriesBuffer = await reader(
    centralDirectoryOffset,
    centralDirectorySize,
    progressOptions
  );
  const rawEntries = [];
  const dv = new DataView(
    allEntriesBuffer.buffer,
    allEntriesBuffer.byteOffset,
    allEntriesBuffer.byteLength
  );
  const textDecoder = new TextDecoder();
  for (let e = 0; e < rawEntryCount; ++e) {
    const signature = dv.getUint32(
      readEntryCursor + 0,
      /*littleEndian=*/
      true
    );
    if (signature !== CENTRAL_DIRECTORY_FILE_HEADER_SIGNATURE) {
      throw new Error(
        `invalid central directory file header signature: 0x${signature.toString(16)}`
      );
    }
    const versionMadeBy = dv.getUint16(
      readEntryCursor + 4,
      /*littleEndian=*/
      true
    );
    const versionNeededToExtract = dv.getUint16(
      readEntryCursor + 6,
      /*littleEndian=*/
      true
    );
    const generalPurposeBitFlag = dv.getUint16(
      readEntryCursor + 8,
      /*littleEndian=*/
      true
    );
    const compressionMethod = dv.getUint16(
      readEntryCursor + 10,
      /*littleEndian=*/
      true
    );
    const lastModFileTime = dv.getUint16(
      readEntryCursor + 12,
      /*littleEndian=*/
      true
    );
    const lastModFileDate = dv.getUint16(
      readEntryCursor + 14,
      /*littleEndian=*/
      true
    );
    const crc32 = dv.getUint32(
      readEntryCursor + 16,
      /*littleEndian=*/
      true
    );
    let compressedSize = dv.getUint32(
      readEntryCursor + 20,
      /*littleEndian=*/
      true
    );
    let uncompressedSize = dv.getUint32(
      readEntryCursor + 24,
      /*littleEndian=*/
      true
    );
    const fileNameLength = dv.getUint16(
      readEntryCursor + 28,
      /*littleEndian=*/
      true
    );
    const extraFieldLength = dv.getUint16(
      readEntryCursor + 30,
      /*littleEndian=*/
      true
    );
    const fileCommentLength = dv.getUint16(
      readEntryCursor + 32,
      /*littleEndian=*/
      true
    );
    const internalFileAttributes = dv.getUint16(
      readEntryCursor + 36,
      /*littleEndian=*/
      true
    );
    const externalFileAttributes = dv.getUint32(
      readEntryCursor + 38,
      /*littleEndian=*/
      true
    );
    let relativeOffsetOfLocalHeader = dv.getUint32(
      readEntryCursor + 42,
      /*littleEndian=*/
      true
    );
    if (generalPurposeBitFlag & 64) {
      throw new Error("strong encryption is not supported");
    }
    readEntryCursor += 46;
    let nameBytes = allEntriesBuffer.subarray(
      readEntryCursor,
      readEntryCursor += fileNameLength
    );
    let isUTF8 = (generalPurposeBitFlag & 2048) !== 0;
    const extraFields = [];
    for (let i = 0; i < extraFieldLength - 3; ) {
      const headerId = dv.getUint16(
        readEntryCursor + i + 0,
        /*littleEndian=*/
        true
      );
      const dataSize = dv.getUint16(
        readEntryCursor + i + 2,
        /*littleEndian=*/
        true
      );
      const dataStart = i + 4;
      const dataEnd = dataStart + dataSize;
      if (dataEnd > extraFieldLength) {
        throw new Error("extra field length exceeds extra field buffer size");
      }
      extraFields.push({
        id: headerId,
        offset: readEntryCursor + dataStart,
        length: dataSize
      });
      i = dataEnd;
    }
    readEntryCursor += extraFieldLength;
    const commentBytes2 = allEntriesBuffer.slice(
      readEntryCursor,
      readEntryCursor += fileCommentLength
    );
    if (uncompressedSize === 4294967295 || compressedSize === 4294967295 || relativeOffsetOfLocalHeader === 4294967295) {
      const zip64ExtraField = extraFields.find((e2) => e2.id === 1);
      if (zip64ExtraField === void 0) {
        throw new Error("expected zip64 extended information extra field");
      }
      const { offset: zip64EiefBufferOffset, length: zip64EiefBufferLength } = zip64ExtraField;
      let index = 0;
      if (uncompressedSize === 4294967295) {
        if (index + 8 > zip64EiefBufferLength) {
          throw new Error(
            "zip64 extended information extra field does not include uncompressed size"
          );
        }
        uncompressedSize = Number(
          dv.getBigUint64(
            zip64EiefBufferOffset + index,
            /*littleEndian=*/
            true
          )
        );
        index += 8;
      }
      if (compressedSize === 4294967295) {
        if (index + 8 > zip64EiefBufferLength) {
          throw new Error(
            "zip64 extended information extra field does not include compressed size"
          );
        }
        compressedSize = Number(
          dv.getBigUint64(
            zip64EiefBufferOffset + index,
            /*littleEndian=*/
            true
          )
        );
        index += 8;
      }
      if (relativeOffsetOfLocalHeader === 4294967295) {
        if (index + 8 > zip64EiefBufferLength) {
          throw new Error(
            "zip64 extended information extra field does not include relative header offset"
          );
        }
        relativeOffsetOfLocalHeader = Number(
          dv.getBigUint64(
            zip64EiefBufferOffset + index,
            /*littleEndian=*/
            true
          )
        );
        index += 8;
      }
    }
    const nameField = extraFields.find(
      (e2) => e2.id === 28789 && e2.length >= 6 && // too short to be meaningful
      allEntriesBuffer[e2.offset] === 1 && // Version       1 byte      version of this extra field, currently 1
      dv.getInt32(
        e2.offset + 1,
        /*littleEndian=*/
        true
      ) === (0, import_crc_32.buf)(nameBytes)
    );
    if (nameField) {
      nameBytes = allEntriesBuffer.slice(
        nameField.offset + 5,
        nameField.offset + nameField.length
      );
      isUTF8 = true;
    }
    if (compressionMethod === 0) {
      let expectedCompressedSize = uncompressedSize;
      if ((generalPurposeBitFlag & 1) !== 0) {
        expectedCompressedSize += 12;
      }
      if (compressedSize !== expectedCompressedSize) {
        throw new Error(
          `compressed/uncompressed size mismatch for stored file: ${compressedSize} != ${expectedCompressedSize}`
        );
      }
    }
    let fileName = textDecoder.decode(nameBytes);
    fileName = fileName.replaceAll("\\", "/");
    isUTF8;
    const rawEntry = {
      versionMadeBy,
      versionNeededToExtract,
      generalPurposeBitFlag,
      compressionMethod,
      lastModFileTime,
      lastModFileDate,
      crc32,
      compressedSize,
      uncompressedSize,
      nameBytes,
      commentBytes: commentBytes2,
      internalFileAttributes,
      externalFileAttributes,
      relativeOffsetOfLocalHeader,
      fileName
    };
    rawEntries.push(rawEntry);
  }
  return {
    commentBytes,
    entries: rawEntries,
    // Estimate that the JavaScript representation consumes twice the memory of
    // the encoded representation.
    sizeEstimate: commentBytes.length + allEntriesBuffer.length * 2
  };
}
async function readEntryDataHeader(reader, rawEntry, options) {
  if (rawEntry.generalPurposeBitFlag & 1) {
    throw new Error("encrypted entries not supported");
  }
  const data = await reader(rawEntry.relativeOffsetOfLocalHeader, 30, options);
  const dv = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const signature = dv.getUint32(
    0,
    /*littleEndian=*/
    true
  );
  if (signature !== 67324752) {
    throw new Error(
      `invalid local file header signature: 0x${signature.toString(16)}`
    );
  }
  const fileNameLength = dv.getUint16(
    26,
    /*littleEndian=*/
    true
  );
  const extraFieldLength = dv.getUint16(
    28,
    /*littleEndian=*/
    true
  );
  const localFileHeaderEnd = rawEntry.relativeOffsetOfLocalHeader + data.length + fileNameLength + extraFieldLength;
  return localFileHeaderEnd;
}
async function readZipMetadata(reader, totalLength, options) {
  return await findEndOfCentralDirectory(
    lastReadCachingReader(reader),
    totalLength,
    options
  );
}
var ZipCompressionMethod = /* @__PURE__ */ ((ZipCompressionMethod2) => {
  ZipCompressionMethod2[ZipCompressionMethod2["STORE"] = 0] = "STORE";
  ZipCompressionMethod2[ZipCompressionMethod2["DEFLATE"] = 8] = "DEFLATE";
  return ZipCompressionMethod2;
})(ZipCompressionMethod || {});

// node_modules/neuroglancer/lib/kvstore/zip/backend.js
var __knownSymbol5 = (name, symbol) => (symbol = Symbol[name]) ? symbol : Symbol.for("Symbol." + name);
var __typeError5 = (msg) => {
  throw TypeError(msg);
};
var __using5 = (stack, value, async) => {
  if (value != null) {
    if (typeof value !== "object" && typeof value !== "function") __typeError5("Object expected");
    var dispose, inner;
    if (async) dispose = value[__knownSymbol5("asyncDispose")];
    if (dispose === void 0) {
      dispose = value[__knownSymbol5("dispose")];
      if (async) inner = dispose;
    }
    if (typeof dispose !== "function") __typeError5("Object not disposable");
    if (inner) dispose = function() {
      try {
        inner.call(this);
      } catch (e) {
        return Promise.reject(e);
      }
    };
    stack.push([async, dispose, value]);
  } else if (async) {
    stack.push([async]);
  }
  return value;
};
var __callDispose5 = (stack, error, hasError) => {
  var E = typeof SuppressedError === "function" ? SuppressedError : function(e, s, m, _) {
    return _ = Error(m), _.name = "SuppressedError", _.error = e, _.suppressed = s, _;
  };
  var fail = (e) => error = hasError ? new E(e, error, "An error was suppressed during disposal") : (hasError = true, e);
  var next = (it) => {
    while (it = stack.pop()) {
      try {
        var result = it[1] && it[1].call(it[2]);
        if (it[0]) return Promise.resolve(result).then(next, (e) => (fail(e), next()));
      } catch (e) {
        fail(e);
      }
    }
    if (hasError) throw error;
  };
  return next();
};
function makeZipReader(base) {
  return async (offset, length6, options) => {
    const readResponse = await readFileHandle(base, {
      throwIfMissing: true,
      byteRange: { offset, length: length6 },
      strictByteRange: true,
      signal: options.signal,
      progressListener: options.progressListener
    });
    return new Uint8Array(await readResponse.response.arrayBuffer());
  };
}
function getZipMetadataCache(chunkManager, base) {
  const url = base.getUrl();
  return makeSimpleAsyncCache(chunkManager, `zipMetadata:${url}`, {
    get: async (_unusedCacheKey, progressOptions) => {
      var _stack = [];
      try {
        const _span = __using5(_stack, new ProgressSpan(progressOptions.progressListener, {
          message: `Reading ZIP central directory from ${url}`
        }));
        const statResponse = await base.stat(progressOptions);
        if ((statResponse == null ? void 0 : statResponse.totalSize) === void 0) {
          throw new Error(`Failed to determine ZIP file size: ${url}`);
        }
        const metadata = await readZipMetadata(
          makeZipReader(base),
          statResponse.totalSize,
          progressOptions
        );
        filterArrayInplace(
          metadata.entries,
          (entry) => !entry.fileName.endsWith("/")
        );
        metadata.entries.sort(
          (a, b) => defaultStringCompare(a.fileName, b.fileName)
        );
        return { data: metadata, size: metadata.sizeEstimate };
      } catch (_) {
        var _error = _, _hasError = true;
      } finally {
        __callDispose5(_stack, _error, _hasError);
      }
    }
  });
}
async function getZipMetadata(chunkManager, base, options) {
  const cache = getZipMetadataCache(chunkManager, base);
  try {
    return await cache.get(void 0, options);
  } finally {
    cache.dispose();
  }
}
function findEntry(metadata, key) {
  const { entries } = metadata;
  const index = binarySearch(
    entries,
    key,
    (key2, entry) => defaultStringCompare(key2, entry.fileName)
  );
  if (index < 0) return void 0;
  return entries[index];
}
function list(metadata, prefix) {
  const { entries } = metadata;
  const startIndex = binarySearchLowerBound(
    0,
    entries.length,
    (index) => entries[index].fileName >= prefix
  );
  const endIndex = binarySearchLowerBound(
    Math.min(entries.length, startIndex + 1),
    entries.length,
    (index) => !entries[index].fileName.startsWith(prefix)
  );
  const listEntries = [];
  const directories = [];
  for (let index = startIndex; index < endIndex; ) {
    const entry = entries[index];
    const i = entry.fileName.indexOf("/", prefix.length);
    if (i === -1) {
      listEntries.push({ key: entry.fileName });
      ++index;
    } else {
      directories.push(entry.fileName.substring(0, i));
      const directoryPrefix = entry.fileName.substring(0, i + 1);
      index = binarySearchLowerBound(
        index + 1,
        endIndex,
        (index2) => !entries[index2].fileName.startsWith(directoryPrefix)
      );
    }
  }
  return { entries: listEntries, directories };
}
var ZipKvStore = class {
  constructor(chunkManager, base) {
    this.chunkManager = chunkManager;
    this.base = base;
  }
  metadata;
  async getMetadata(options) {
    let { metadata } = this;
    if (metadata === void 0) {
      metadata = this.metadata = await getZipMetadata(
        this.chunkManager,
        this.base,
        options
      );
    }
    return metadata;
  }
  getUrl(key) {
    return this.base.getUrl() + `|zip:${encodePathForUrl(key)}`;
  }
  async stat(key, options) {
    const entry = findEntry(await this.getMetadata(options), key);
    if (entry === void 0) return void 0;
    return { totalSize: entry.uncompressedSize };
  }
  async read(key, options) {
    const entry = findEntry(await this.getMetadata(options), key);
    if (entry === void 0) return void 0;
    let { fileDataStart } = entry;
    if (fileDataStart === void 0) {
      fileDataStart = entry.fileDataStart = await readEntryDataHeader(
        makeZipReader(this.base),
        entry,
        options
      );
    }
    let handle = new FileByteRangeHandle(this.base, {
      offset: fileDataStart,
      length: entry.compressedSize
    });
    switch (entry.compressionMethod) {
      case ZipCompressionMethod.STORE:
        break;
      case ZipCompressionMethod.DEFLATE:
        handle = new GzipFileHandle(handle, "deflate-raw");
        break;
      default:
        throw new Error(
          `Unsupported compression method: ${entry.compressionMethod}`
        );
    }
    return handle.read(options);
  }
  async list(prefix, options) {
    const metadata = await this.getMetadata(options);
    return list(metadata, prefix);
  }
  get supportsOffsetReads() {
    return true;
  }
  get supportsSuffixReads() {
    return true;
  }
};

// node_modules/neuroglancer/lib/kvstore/zip/register_backend.js
function zipProvider(sharedKvStoreContext) {
  return {
    scheme: "zip",
    description: "ZIP archive",
    getKvStore(parsedUrl, base) {
      ensureNoQueryOrFragmentParameters(parsedUrl);
      return {
        store: new ZipKvStore(
          sharedKvStoreContext.chunkManager,
          new KvStoreFileHandle(base.store, base.path)
        ),
        path: decodeURIComponent(parsedUrl.suffix ?? "")
      };
    }
  };
}
backendOnlyKvStoreProviderRegistry.registerKvStoreAdapterProvider(zipProvider);

// node_modules/neuroglancer/lib/worker_rpc_context.js
init_legacy_browser();
var rpc = new RPC(
  self,
  /*waitUntilReady=*/
  false
);
rpc.sendReady();
globalThis.rpc = rpc;
