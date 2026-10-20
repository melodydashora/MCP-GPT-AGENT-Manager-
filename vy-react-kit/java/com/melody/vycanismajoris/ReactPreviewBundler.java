package com.melody.vycanismajoris;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Builds one self-contained HTML page that runs a React project in VY's offline preview.
 *
 * <p>Pure Java 8 with no Android dependencies, so host tests can run it. The caller reads the
 * four runtime assets from the APK (for example with AssetManager), passes the project's text
 * files keyed by project-relative path, and loads the returned HTML into the preview WebView.
 * The page inlines React, ReactDOM, the Sucrase transpiler and the VY runtime, so it makes no
 * network, fetch or XHR request. A Content-Security-Policy with a per-page nonce blocks
 * everything else.
 */
public final class ReactPreviewBundler {

    public static final int MAX_FILES = 300;
    public static final long MAX_SOURCE_BYTES = 4L * 1024L * 1024L;
    public static final String MODE_DEVELOPMENT = "development";
    public static final String MODE_PRODUCTION = "production";

    private static final String[] ENTRY_CANDIDATES = {
        "src/main.jsx", "src/main.tsx", "src/index.jsx", "src/index.tsx",
        "src/main.js", "src/index.js", "src/main.ts", "src/index.ts",
        "main.jsx", "main.tsx", "index.jsx", "index.tsx", "app.jsx", "App.jsx", "App.tsx",
        "main.js", "index.js"
    };
    private static final String[] SOURCE_EXTENSIONS = {
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".css"
    };
    private static final Pattern REACT_IMPORT = Pattern.compile(
        "(?:from\\s*['\"]react(?:-dom)?(?:/[A-Za-z-]+)?['\"])|(?:require\\(\\s*['\"]react(?:-dom)?(?:/[A-Za-z-]+)?['\"]\\s*\\))");
    private static final Pattern PACKAGE_REACT = Pattern.compile("\"react\"\\s*:");
    private static final Pattern MODULE_SCRIPT = Pattern.compile(
        "<script\\b[^>]*\\bsrc\\s*=\\s*[\"']([^\"']+)[\"'][^>]*>\\s*</script\\s*>",
        Pattern.CASE_INSENSITIVE);
    private static final Pattern INLINE_SCRIPT = Pattern.compile(
        "<script\\b(?![^>]*\\bsrc\\s*=)[^>]*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern HEAD_OPEN = Pattern.compile("<head\\b[^>]*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern BODY_CLOSE = Pattern.compile("</body\\s*>", Pattern.CASE_INSENSITIVE);
    private static final Pattern ROOT_ELEMENT = Pattern.compile(
        "\\bid\\s*=\\s*[\"']root[\"']", Pattern.CASE_INSENSITIVE);
    private static final Pattern NONCE = Pattern.compile("[A-Za-z0-9+/_=-]{16,128}");

    private ReactPreviewBundler() {
    }

    /** Runtime files shipped in the APK, read by the caller as UTF-8 text. */
    public static final class Assets {
        final String react;
        final String reactDom;
        final String sucrase;
        final String runtime;

        public Assets(String react, String reactDom, String sucrase, String runtime) {
            this.react = requireScript("react", react);
            this.reactDom = requireScript("react-dom", reactDom);
            this.sucrase = requireScript("sucrase", sucrase);
            this.runtime = requireScript("runtime", runtime);
        }
    }

    /** The finished page plus what was and was not included. */
    public static final class Result {
        public final String html;
        public final String entry;
        public final List<String> included;
        public final List<String> skipped;
        public final List<String> warnings;
        /**
         * The page's Content-Security-Policy. When the preview serves the page through
         * shouldInterceptRequest, send this exact value as the response's
         * Content-Security-Policy header. A different header policy is combined with the
         * page's own policy, and one without this nonce blocks the runtime.
         */
        public final String contentSecurityPolicy;

        Result(String html, String entry, List<String> included, List<String> skipped,
               List<String> warnings, String contentSecurityPolicy) {
            this.contentSecurityPolicy = contentSecurityPolicy;
            this.html = html;
            this.entry = entry;
            this.included = Collections.unmodifiableList(included);
            this.skipped = Collections.unmodifiableList(skipped);
            this.warnings = Collections.unmodifiableList(warnings);
        }
    }

    /** Thrown when the project cannot become a preview page. The message is user-facing. */
    public static final class BundleException extends Exception {
        private static final long serialVersionUID = 1L;

        public BundleException(String message) {
            super(message);
        }
    }

    /** Returns true when the path is a source file the preview runtime can load. */
    public static boolean isSourcePath(String path) {
        if (path == null || path.isEmpty()) {
            return false;
        }
        String normalized = path.replace('\\', '/');
        for (String part : normalized.split("/")) {
            if (part.equals("node_modules") || part.equals("..")
                    || (part.startsWith(".") && part.length() > 1)) {
                return false;
            }
        }
        String lower = normalized.toLowerCase(Locale.ROOT);
        for (String extension : SOURCE_EXTENSIONS) {
            if (lower.endsWith(extension)) {
                return true;
            }
        }
        return false;
    }

    /**
     * Returns the project's React entry file, or null when the project does not look like React.
     * An index.html module script wins; otherwise the usual Vite and Create React App names apply.
     */
    public static String findEntry(Map<String, String> files) {
        if (files == null || files.isEmpty() || !usesReact(files)) {
            return null;
        }
        String html = files.get("index.html");
        if (html != null) {
            Matcher matcher = MODULE_SCRIPT.matcher(html);
            while (matcher.find()) {
                String local = localPath(matcher.group(1));
                if (local != null && files.containsKey(local) && isSourcePath(local)) {
                    return local;
                }
            }
        }
        for (String candidate : ENTRY_CANDIDATES) {
            if (files.containsKey(candidate)) {
                return candidate;
            }
        }
        return null;
    }

    /** Returns true when a source file imports React or package.json depends on it. */
    public static boolean usesReact(Map<String, String> files) {
        String packageJson = files.get("package.json");
        if (packageJson != null && PACKAGE_REACT.matcher(packageJson).find()) {
            return true;
        }
        for (Map.Entry<String, String> file : files.entrySet()) {
            String lower = file.getKey().toLowerCase(Locale.ROOT);
            if (lower.endsWith(".jsx") || lower.endsWith(".tsx")) {
                return true;
            }
            if (isSourcePath(file.getKey()) && file.getValue() != null
                    && REACT_IMPORT.matcher(file.getValue()).find()) {
                return true;
            }
        }
        return false;
    }

    /**
     * Builds the preview page.
     *
     * @param files project text files keyed by project-relative path using '/' separators
     * @param assets runtime scripts from the APK
     * @param nonce a fresh random CSP nonce for this page load (16-128 base64 characters)
     * @param mode {@link #MODE_DEVELOPMENT} or {@link #MODE_PRODUCTION}
     */
    public static Result build(Map<String, String> files, Assets assets, String nonce, String mode)
            throws BundleException {
        if (files == null || assets == null) {
            throw new IllegalArgumentException("files and assets are required");
        }
        if (nonce == null || !NONCE.matcher(nonce).matches()) {
            throw new IllegalArgumentException("nonce must be 16-128 base64 or base64url characters");
        }
        String safeMode = MODE_PRODUCTION.equals(mode) ? MODE_PRODUCTION : MODE_DEVELOPMENT;
        String entry = findEntry(files);
        if (entry == null) {
            throw new BundleException("This project has no React entry file. Add src/main.jsx "
                + "or index.jsx that imports react.");
        }

        TreeMap<String, String> sources = new TreeMap<String, String>();
        List<String> skipped = new ArrayList<String>();
        long total = 0;
        for (Map.Entry<String, String> file : new TreeMap<String, String>(files).entrySet()) {
            String path = file.getKey().replace('\\', '/');
            while (path.startsWith("./")) {
                path = path.substring(2);
            }
            if (!isSourcePath(path) || file.getValue() == null) {
                if (!path.equals("index.html")) {
                    skipped.add(path);
                }
                continue;
            }
            total += file.getValue().getBytes(StandardCharsets.UTF_8).length;
            sources.put(path, file.getValue());
        }
        if (sources.size() > MAX_FILES) {
            throw new BundleException("The preview supports up to " + MAX_FILES
                + " source files; this project has " + sources.size() + ".");
        }
        if (total > MAX_SOURCE_BYTES) {
            throw new BundleException("The project's source files are larger than the "
                + (MAX_SOURCE_BYTES / (1024 * 1024)) + " MiB preview limit.");
        }

        List<String> warnings = new ArrayList<String>();
        String page = files.get("index.html");
        if (page == null) {
            page = "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
                + "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                + "<title>Preview</title>\n</head>\n<body>\n<div id=\"root\"></div>\n</body>\n</html>\n";
        } else {
            page = removeLocalModuleScripts(page, files);
            if (INLINE_SCRIPT.matcher(page).find()) {
                warnings.add("index.html has inline scripts. The preview blocks them; move that code "
                    + "into a module file.");
            }
            if (!ROOT_ELEMENT.matcher(page).find()) {
                warnings.add("index.html has no element with id=\"root\".");
            }
        }

        String csp = "default-src 'none'; script-src 'nonce-" + nonce + "'; "
            + "style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:";
        String head = "<meta http-equiv=\"Content-Security-Policy\" content=\"" + csp + "\">\n";
        Matcher headOpen = HEAD_OPEN.matcher(page);
        if (headOpen.find()) {
            page = page.substring(0, headOpen.end()) + "\n" + head + page.substring(headOpen.end());
        } else {
            page = head + page;
        }

        StringBuilder scripts = new StringBuilder();
        scripts.append(scriptTag(nonce, "vy-react", assets.react));
        scripts.append(scriptTag(nonce, "vy-react-dom", assets.reactDom));
        scripts.append(scriptTag(nonce, "vy-sucrase", assets.sucrase));
        scripts.append("<script type=\"application/json\" id=\"vy-react-modules\">")
            .append(manifestJson(entry, safeMode, sources))
            .append("</script>\n");
        scripts.append(scriptTag(nonce, "vy-react-runtime", assets.runtime));
        scripts.append("<script nonce=\"").append(nonce).append("\">window.VyReact.start();</script>\n");

        Matcher bodyClose = BODY_CLOSE.matcher(page);
        int insertAt = -1;
        while (bodyClose.find()) {
            insertAt = bodyClose.start();
        }
        if (insertAt >= 0) {
            page = page.substring(0, insertAt) + scripts + page.substring(insertAt);
        } else {
            page = page + "\n" + scripts;
        }
        return new Result(page, entry, new ArrayList<String>(sources.keySet()), skipped, warnings, csp);
    }

    private static String removeLocalModuleScripts(String html, Map<String, String> files) {
        Matcher matcher = MODULE_SCRIPT.matcher(html);
        StringBuffer out = new StringBuffer();
        while (matcher.find()) {
            String local = localPath(matcher.group(1));
            boolean projectFile = local != null && files.containsKey(local);
            matcher.appendReplacement(out, projectFile ? "" : Matcher.quoteReplacement(matcher.group()));
        }
        matcher.appendTail(out);
        return out.toString();
    }

    private static String localPath(String src) {
        String value = src.trim();
        if (value.contains("://") || value.startsWith("//") || value.startsWith("data:")) {
            return null;
        }
        int cut = value.indexOf('?');
        if (cut >= 0) {
            value = value.substring(0, cut);
        }
        cut = value.indexOf('#');
        if (cut >= 0) {
            value = value.substring(0, cut);
        }
        while (value.startsWith("./") || value.startsWith("/")) {
            value = value.substring(value.startsWith("./") ? 2 : 1);
        }
        return value.isEmpty() || value.contains("..") ? null : value;
    }

    private static String scriptTag(String nonce, String id, String body) {
        return "<script nonce=\"" + nonce + "\" data-vy=\"" + id + "\">\n" + body + "\n</script>\n";
    }

    static String requireScript(String name, String body) {
        if (body == null || body.isEmpty()) {
            throw new IllegalArgumentException(name + " asset is missing");
        }
        String lower = body.toLowerCase(Locale.ROOT);
        if (lower.contains("</script") || lower.contains("<!--")) {
            throw new IllegalArgumentException(name + " asset cannot be inlined safely");
        }
        return body;
    }

    static String manifestJson(String entry, String mode, Map<String, String> sources) {
        StringBuilder json = new StringBuilder();
        json.append("{\"entry\":").append(jsonString(entry))
            .append(",\"mode\":").append(jsonString(mode))
            .append(",\"files\":{");
        boolean first = true;
        for (Map.Entry<String, String> source : sources.entrySet()) {
            if (!first) {
                json.append(',');
            }
            first = false;
            json.append(jsonString(source.getKey())).append(':').append(jsonString(source.getValue()));
        }
        return json.append("}}").toString();
    }

    /** JSON string that is also safe inside an HTML script element. */
    static String jsonString(String value) {
        StringBuilder out = new StringBuilder(value.length() + 16);
        out.append('"');
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                case '<': out.append("\\u003c"); break;
                case '>': out.append("\\u003e"); break;
                case '&': out.append("\\u0026"); break;
                case '\u2028': out.append("\\u2028"); break;
                case '\u2029': out.append("\\u2029"); break;
                default:
                    if (c < 0x20) {
                        out.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
                    } else {
                        out.append(c);
                    }
            }
        }
        return out.append('"').toString();
    }
}
