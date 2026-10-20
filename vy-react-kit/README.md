# VY React preview kit

This kit lets VY Canis Majoris (`com.melody.vycanismajoris`) run React projects in its
existing offline preview. A user opens a project with `src/main.jsx` (or `index.jsx`) and the
preview renders it. No npm install, no network, no external terminal.

Status on 2026-10-19: built and tested on a Linux host only. It has **not** been copied into
the VY source tree, built into an APK or run on the Samsung phone. The VY source lives only on
the phone, so the VY builder has to do the integration steps below.

## How it works

1. VY captures the project's text files, as the preview already does.
2. `ReactPreviewBundler.findEntry` decides whether the project is React and finds the entry file.
3. `ReactPreviewBundler.build` returns one HTML page. It inlines React 18.3.1, ReactDOM 18.3.1,
   a Sucrase 3.35.0 transpiler bundle, the VY runtime, and a JSON manifest of the project files.
4. In the WebView, the runtime transpiles each JSX/TSX/JS file when it is first imported. It
   resolves relative imports, CSS imports and JSON imports. It maps `react`, `react-dom`,
   `react-dom/client` and `react/jsx-runtime` to the bundled copies.
5. Each module runs as an inline `<script>` carrying the page's CSP nonce. The page needs no
   `unsafe-eval`, makes no requests, and its CSP is `default-src 'none'`.
6. Errors appear in a red panel at the bottom of the preview with the file, line and column.

## Files

| Path | Purpose |
|---|---|
| `java/com/melody/vycanismajoris/ReactPreviewBundler.java` | Pure Java 8 class. No Android imports. |
| `assets/react/react.development.js`, `react-dom.development.js` | React 18.3.1 UMD, readable errors. Recommended for the preview. |
| `assets/react/react.production.min.js`, `react-dom.production.min.js` | Smaller React 18.3.1 UMD builds. |
| `assets/react/vy-sucrase.min.js` | Sucrase 3.35.0 bundled by esbuild 0.24.2 as the global `VySucrase`. |
| `assets/react/vy-react-runtime.js` | Hand-written loader, module system and error panel. |
| `assets/react/licenses/` | MIT licenses for React, ReactDOM and Sucrase. |
| `templates/react-starter/` | Starter project for a "New React project" button. |
| `test/reactpreview/` | Host checks: Java assertions plus offline headless Chromium. |
| `scripts/build-react-assets.sh` | Rebuilds the vendor files from the pinned lockfile and checks hashes. |
| `SHA256SUMS.txt` | Hashes of every asset file. |

Size added to the APK is about 1.6 MB for all six scripts. Shipping only the development
React pair plus Sucrase and the runtime is about 1.4 MB.

## Integration steps for the VY builder

1. Copy `assets/react/*.js` to `app/src/main/assets/preview/react/` and the three license
   files to `app/src/main/assets/licenses/`. Run `sha256sum -c` against `SHA256SUMS.txt` first.
2. Copy `ReactPreviewBundler.java` to `app/src/main/java/com/melody/vycanismajoris/`.
3. Hook into the preview's request handler. Per the VY builder's 2026-10-19 source notes,
   `PreviewActivity.java` gives each preview a fresh private HTTPS-style `.vy.invalid` origin,
   and its `shouldInterceptRequest` serves files from the immutable `ProjectPreviewSnapshot`
   while blocking network, file and content access. Keep all of that. Only change what is
   returned for the preview's main page when the snapshot is a React project:

```java
// Once per preview load, after the snapshot is captured:
Map<String, String> files = /* snapshot text files, project-relative path -> UTF-8 text */;
ReactPreviewBundler.Result reactPage = null;
String reactError = null;
if (ReactPreviewBundler.findEntry(files) != null) {
    byte[] raw = new byte[18];
    new SecureRandom().nextBytes(raw);
    String nonce = Base64.encodeToString(raw, Base64.NO_WRAP | Base64.URL_SAFE | Base64.NO_PADDING);
    try {
        reactPage = ReactPreviewBundler.build(files, cachedAssets(context), nonce,
            ReactPreviewBundler.MODE_DEVELOPMENT);
    } catch (ReactPreviewBundler.BundleException e) {
        reactError = e.getMessage();   // Show this in the preview screen; it is user-facing.
    }
}

// In the existing shouldInterceptRequest, for the preview's main page URL only:
if (reactPage != null && isMainPage(request.getUrl())) {
    Map<String, String> headers = new HashMap<>();
    headers.put("Content-Security-Policy", reactPage.contentSecurityPolicy);
    headers.put("Cache-Control", "no-store");
    return new WebResourceResponse("text/html", "UTF-8", 200, "OK", headers,
        new ByteArrayInputStream(reactPage.html.getBytes(StandardCharsets.UTF_8)));
}
// Everything else keeps the existing snapshot handling and blocking.
```

   `cachedAssets` reads the four files once with `AssetManager` and keeps them; they total
   about 1.4 MB. Make a fresh nonce for every preview load. If the handler already adds its
   own `Content-Security-Policy` header, replace it with `reactPage.contentSecurityPolicy`
   for the React page. A header without this nonce blocks the runtime. Show
   `reactPage.warnings` to the user when it is not empty. Non-React projects must take the
   unchanged path. If the preview instead loads one HTML string, `loadDataWithBaseURL` with
   the existing base URL and `reactPage.html` also works.
4. Copy `test/reactpreview/` into the VY repository and add `bash test/reactpreview/run.sh` to
   `scripts/test-core.sh`. Set `VY_SKIP_BROWSER=1` where Playwright is not installed; the Java
   stage still runs.
5. Optionally add a "New React project" action that copies `templates/react-starter/`.
6. Update the in-app guide: React projects preview offline with `react` and `react-dom` only.

## Limits to state honestly in the app

- Only `react` and `react-dom` are available. Any other npm import shows a clear error.
- No npm install, bundler, dev server or hot reload. Reopen the preview to see changes.
- TypeScript types are stripped, not checked.
- Image imports, `url()` references to project files and fonts from files do not load.
  `data:` URLs work.
- Inline `<script>` blocks and remote scripts in `index.html` are blocked by the CSP.
  The bundler returns a warning for inline scripts.
- Limits: 300 source files and 4 MiB of source per preview.

## Checks run on 2026-10-19 (Linux host)

```
$ NODE_PATH=/opt/node22/lib/node_modules bash test/reactpreview/run.sh
ReactPreviewBundlerCheck: 48 assertions passed
asset hashes: OK
browser-check: 38 assertions passed (Chromium 141.0.7390.37)
$ bash scripts/build-react-assets.sh
Rebuilt assets match SHA256SUMS.txt
```

The Java class compiles with `javac --release 8 -Xlint:all -Werror`. The browser stage runs
with the network offline and every request aborted. It covers a Vite-style multi-file app
(JSX, TSX, JSON, CSS, `useState`, `StrictMode`), the starter template, a single-file app,
syntax errors with line and column, a missing npm package, a render error, and source text
that tries to close the script tag. A probe inside the app confirms the page blocks `eval`.
It also serves the page from a private `https://….vy.invalid` origin through a request handler
with the policy sent as a header, which is how VY's preview loads pages.

## Device acceptance still required

1. Fresh install, phone offline: the starter template renders and the button counts.
2. Edit `src/App.jsx`, reopen the preview, and see the change.
3. A syntax error shows the red panel with file and line; fixing it clears the panel.
4. Importing an unsupported package shows the package error and the app stays usable.
5. The preview makes no network request, checked with the existing interceptor log.
6. Existing HTML previews behave exactly as before.
7. Rotation, back navigation and reopening the preview do not leak old pages.
