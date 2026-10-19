/*
 * VY React preview runtime. Version 1.
 * Runs a multi-file React project inside VY's offline preview WebView.
 * Needs no network, fetch, XHR or eval. Each transpiled module is added as an
 * inline <script> that carries this script's CSP nonce.
 * Requires globals: React, ReactDOM (UMD 18.x) and VySucrase (Sucrase bundle).
 */
(function (global) {
  'use strict';

  var VERSION = '1';
  var self = document.currentScript;
  var nonce = (self && (self.nonce || self.getAttribute('nonce'))) || '';
  var factories = Object.create(null);
  var cache = Object.create(null);
  var files = Object.create(null);
  var EXTENSIONS = ['', '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', '.json', '.css'];
  var INDEXES = ['/index.js', '/index.jsx', '/index.ts', '/index.tsx'];
  var processShim = { env: { NODE_ENV: 'development' } };

  function VyModuleError(message, path) {
    var e = new Error(message);
    e.name = 'VyModuleError';
    e.vyPath = path || null;
    return e;
  }

  function normalize(path) {
    var out = [];
    String(path).split('/').forEach(function (part) {
      if (!part || part === '.') return;
      if (part === '..') {
        if (!out.length) throw VyModuleError('Import leaves the project folder: ' + path);
        out.pop();
      } else {
        out.push(part);
      }
    });
    return out.join('/');
  }

  function dirname(path) {
    var i = path.lastIndexOf('/');
    return i < 0 ? '' : path.slice(0, i);
  }

  function jsxShim(type, config, maybeKey) {
    var props = {};
    var key;
    for (var name in config) {
      if (Object.prototype.hasOwnProperty.call(config, name)) props[name] = config[name];
    }
    if (maybeKey !== undefined) key = maybeKey;
    if (key !== undefined) props.key = key;
    return global.React.createElement(type, props);
  }

  function externals() {
    var React = global.React;
    var ReactDOM = global.ReactDOM;
    var runtime = { Fragment: React.Fragment, jsx: jsxShim, jsxs: jsxShim, jsxDEV: jsxShim };
    return {
      'react': React,
      'react-dom': ReactDOM,
      'react-dom/client': ReactDOM,
      'react/jsx-runtime': runtime,
      'react/jsx-dev-runtime': runtime
    };
  }

  function resolve(fromPath, spec) {
    var ext = externals();
    if (Object.prototype.hasOwnProperty.call(ext, spec)) return { external: spec };
    var isRelative = spec.charAt(0) === '.' || spec.charAt(0) === '/';
    if (!isRelative) {
      throw VyModuleError('Package "' + spec + '" is not available in the offline preview. ' +
        'Bundled packages: react, react-dom. Copy small helpers into the project instead.', fromPath);
    }
    var base = spec.charAt(0) === '/' ? normalize(spec) : normalize(dirname(fromPath) + '/' + spec);
    var i;
    for (i = 0; i < EXTENSIONS.length; i++) {
      if (files[base + EXTENSIONS[i]] !== undefined) return { path: base + EXTENSIONS[i] };
    }
    for (i = 0; i < INDEXES.length; i++) {
      if (files[base + INDEXES[i]] !== undefined) return { path: base + INDEXES[i] };
    }
    throw VyModuleError('Cannot find "' + spec + '" imported from ' + fromPath + '.', fromPath);
  }

  function extensionOf(path) {
    var i = path.lastIndexOf('.');
    return i < 0 ? '' : path.slice(i + 1).toLowerCase();
  }

  function define(path, factory) {
    factories[path] = factory;
  }

  function injectScript(code, path) {
    var script = document.createElement('script');
    if (nonce) script.nonce = nonce;
    script.textContent = code;
    var failed = null;
    function onError(event) {
      failed = event.error || new Error(event.message);
    }
    global.addEventListener('error', onError);
    try {
      document.head.appendChild(script);
    } finally {
      global.removeEventListener('error', onError);
      script.parentNode && script.parentNode.removeChild(script);
    }
    if (failed) throw failed;
    if (!factories[path]) {
      throw VyModuleError('The preview blocked the code for ' + path +
        '. The preview page must give the runtime a CSP nonce.', path);
    }
  }

  function compile(path) {
    var source = files[path];
    var ext = extensionOf(path);
    if (ext === 'json') {
      var data;
      try {
        data = JSON.parse(source);
      } catch (e) {
        throw VyModuleError(path + ' is not valid JSON: ' + e.message, path);
      }
      factories[path] = function (require, module) { module.exports = data; };
      return;
    }
    if (ext === 'css') {
      factories[path] = function () {
        var style = document.createElement('style');
        if (nonce) style.nonce = nonce;
        style.setAttribute('data-vy-path', path);
        style.textContent = source;
        document.head.appendChild(style);
      };
      return;
    }
    var transforms = ['jsx', 'imports'];
    if (ext === 'ts' || ext === 'tsx') transforms.push('typescript');
    var output;
    try {
      output = global.VySucrase.transform(source, {
        transforms: transforms,
        filePath: path,
        jsxRuntime: 'automatic',
        production: true,
        keepUnusedImports: false
      }).code;
    } catch (e) {
      var where = e.loc ? ' (line ' + e.loc.line + ', column ' + (e.loc.column + 1) + ')' : '';
      throw VyModuleError('Syntax error in ' + path + where + ': ' + e.message, path);
    }
    // The wrapper stays on line 1 so browser line numbers match the source file.
    var code = 'window.VyReact.__define(' + JSON.stringify(path) +
      ', function (require, module, exports, process) {' + output +
      '\n});\n//# sourceURL=vy-project:///' + encodeURI(path);
    injectScript(code, path);
  }

  function load(path) {
    if (cache[path]) return cache[path].exports;
    if (!factories[path]) compile(path);
    var module = { exports: {} };
    cache[path] = module;
    var localRequire = function (spec) {
      var target = resolve(path, spec);
      return target.external ? externals()[target.external] : load(target.path);
    };
    try {
      factories[path](localRequire, module, module.exports, processShim);
    } catch (e) {
      delete cache[path];
      if (e && !e.vyPath) e.vyPath = path;
      throw e;
    }
    return module.exports;
  }

  function escapeText(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function showError(error) {
    var box = document.getElementById('vy-react-error');
    if (!box) {
      box = document.createElement('pre');
      box.id = 'vy-react-error';
      box.setAttribute('role', 'alert');
      box.style.cssText = 'position:fixed;left:0;right:0;bottom:0;max-height:60%;overflow:auto;' +
        'margin:0;padding:12px;background:#2b0b0e;color:#ffd7d7;font:13px/1.4 monospace;' +
        'white-space:pre-wrap;z-index:2147483647;border-top:3px solid #ff5c5c';
      (document.body || document.documentElement).appendChild(box);
    }
    var message = (error && error.message) || String(error);
    var stack = (error && error.stack) || '';
    box.innerHTML = '<b>Preview error</b>\n' + escapeText(message) +
      (stack && stack.indexOf(message) < 0 ? '\n\n' + escapeText(stack) : '') +
      (stack && stack.indexOf(message) >= 0 ? '\n\n' + escapeText(stack.split('\n').slice(1, 8).join('\n')) : '');
    global.VyReact.lastError = message;
  }

  function readManifest() {
    var node = document.getElementById('vy-react-modules');
    if (!node) throw VyModuleError('The preview page has no vy-react-modules manifest.');
    var manifest = JSON.parse(node.textContent);
    if (!manifest || typeof manifest.entry !== 'string' || !manifest.files) {
      throw VyModuleError('The vy-react-modules manifest is incomplete.');
    }
    return manifest;
  }

  function start() {
    try {
      if (!global.React || !global.ReactDOM || !global.VySucrase) {
        throw VyModuleError('React, ReactDOM or the transpiler did not load in the preview.');
      }
      var manifest = readManifest();
      Object.keys(manifest.files).forEach(function (path) {
        files[normalize(path)] = manifest.files[path];
      });
      if (manifest.mode === 'production') processShim.env.NODE_ENV = 'production';
      load(normalize(manifest.entry));
      global.VyReact.started = true;
    } catch (e) {
      showError(e);
    }
  }

  global.addEventListener('error', function (event) {
    showError(event.error || event.message);
  });
  global.addEventListener('unhandledrejection', function (event) {
    showError(event.reason);
  });

  global.VyReact = {
    version: VERSION,
    started: false,
    lastError: null,
    start: start,
    __define: define
  };
})(window);
