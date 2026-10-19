package com.melody.vycanismajoris;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Stream;

/** Host checks for ReactPreviewBundler. Usage: ReactPreviewBundlerCheck <kitDir> <outDir>. */
public final class ReactPreviewBundlerCheck {
    private static int passed;
    private static final String NONCE = "dGVzdE5vbmNlMTIzNDU2Nzg5MA";

    public static void main(String[] args) throws Exception {
        Path kit = Paths.get(args[0]);
        Path out = Paths.get(args[1]);
        Files.createDirectories(out);
        Path assetsDir = kit.resolve("assets/react");
        ReactPreviewBundler.Assets production = new ReactPreviewBundler.Assets(
            read(assetsDir.resolve("react.production.min.js")),
            read(assetsDir.resolve("react-dom.production.min.js")),
            read(assetsDir.resolve("vy-sucrase.min.js")),
            read(assetsDir.resolve("vy-react-runtime.js")));
        ReactPreviewBundler.Assets development = new ReactPreviewBundler.Assets(
            read(assetsDir.resolve("react.development.js")),
            read(assetsDir.resolve("react-dom.development.js")),
            read(assetsDir.resolve("vy-sucrase.min.js")),
            read(assetsDir.resolve("vy-react-runtime.js")));
        Path fixtures = kit.resolve("test/reactpreview/fixtures");

        // Detection.
        Map<String, String> vite = load(fixtures.resolve("vite-app"));
        check(ReactPreviewBundler.usesReact(vite), "vite app uses React");
        check("src/main.jsx".equals(ReactPreviewBundler.findEntry(vite)), "index.html module script picks entry");
        check(ReactPreviewBundler.findEntry(load(fixtures.resolve("not-react"))) == null, "plain JS is not React");
        check("index.jsx".equals(ReactPreviewBundler.findEntry(load(fixtures.resolve("single-file")))), "single-file entry");
        Map<String, String> noHtml = new HashMap<String, String>(vite);
        noHtml.remove("index.html");
        check("src/main.jsx".equals(ReactPreviewBundler.findEntry(noHtml)), "Vite name without index.html");
        Map<String, String> cra = new HashMap<String, String>();
        cra.put("src/index.js", "import React from 'react';\n");
        check("src/index.js".equals(ReactPreviewBundler.findEntry(cra)), "Create React App entry");

        // Source path filter.
        check(ReactPreviewBundler.isSourcePath("src/App.tsx"), "tsx is source");
        check(ReactPreviewBundler.isSourcePath("a/b/c.css"), "css is source");
        check(!ReactPreviewBundler.isSourcePath("node_modules/react/index.js"), "node_modules excluded");
        check(!ReactPreviewBundler.isSourcePath(".env.js"), "dotfiles excluded");
        check(!ReactPreviewBundler.isSourcePath("src/.secret/x.js"), "dot directories excluded");
        check(!ReactPreviewBundler.isSourcePath("../x.js"), "parent paths excluded");
        check(!ReactPreviewBundler.isSourcePath("logo.png"), "images are not inlined source");

        // JSON escaping keeps the manifest inert inside HTML.
        String json = ReactPreviewBundler.jsonString("</script><!--& \"\\\n\u0001");
        check(!json.contains("<") && !json.contains(">") && !json.contains("&"), "manifest escapes markup");
        check(json.contains("\\u2028") && json.contains("\\u0001") && json.contains("\\\""), "manifest escapes controls");

        // Unsafe assets and bad nonces are refused.
        check(throwsIae(() -> new ReactPreviewBundler.Assets("a</script>", "b", "c", "d")), "asset with </script refused");
        check(throwsIae(() -> new ReactPreviewBundler.Assets("a", "b<!--", "c", "d")), "asset with <!-- refused");
        check(throwsIae(() -> ReactPreviewBundler.build(vite, production, "short", null)), "short nonce refused");
        check(throwsIae(() -> ReactPreviewBundler.build(vite, production, "bad\"nonce\"1234567890", null)), "quoted nonce refused");

        // Vite page.
        ReactPreviewBundler.Result viteResult = ReactPreviewBundler.build(vite, development, NONCE, "development");
        check(viteResult.entry.equals("src/main.jsx"), "result entry");
        check(!viteResult.html.contains("src=\"/src/main.jsx\""), "local module script removed");
        check(viteResult.html.contains("Content-Security-Policy"), "CSP added");
        check(viteResult.html.contains("script-src 'nonce-" + NONCE + "'"), "CSP nonce");
        check(!viteResult.html.contains("unsafe-eval"), "no unsafe-eval");
        check(viteResult.html.indexOf("<title>VY Vite fixture</title>") > 0, "user head kept");
        check(viteResult.included.contains("src/components/Greeting.tsx"), "tsx included");
        check(viteResult.included.contains("src/data.json"), "json included");
        check(viteResult.skipped.isEmpty(), "nothing skipped: " + viteResult.skipped);
        check(viteResult.warnings.isEmpty(), "no warnings: " + viteResult.warnings);
        check(viteResult.html.indexOf("vy-react-runtime") < viteResult.html.indexOf("window.VyReact.start()"),
            "runtime before start");
        check(viteResult.html.indexOf("</body>") > viteResult.html.indexOf("window.VyReact.start()"),
            "scripts inside body");
        write(out.resolve("vite-app.dev.html"), viteResult.html);
        write(out.resolve("vite-app.prod.html"),
            ReactPreviewBundler.build(vite, production, NONCE, "production").html);

        // Warnings for inline scripts and a missing root.
        Map<String, String> warned = new HashMap<String, String>(vite);
        warned.put("index.html", "<html><head></head><body><script>alert(1)</script></body></html>");
        ReactPreviewBundler.Result warnedResult = ReactPreviewBundler.build(warned, production, NONCE, null);
        check(warnedResult.warnings.size() == 2, "inline script and missing root warnings");

        // Remote scripts in index.html are kept (CSP blocks them) and not mistaken for entries.
        Map<String, String> remote = new HashMap<String, String>(vite);
        remote.put("index.html", "<html><head></head><body><div id=\"root\"></div>"
            + "<script src=\"https://cdn.example/x.js\"></script>"
            + "<script type=\"module\" src=\"./src/main.jsx?v=1\"></script></body></html>");
        ReactPreviewBundler.Result remoteResult = ReactPreviewBundler.build(remote, production, NONCE, null);
        check(remoteResult.entry.equals("src/main.jsx"), "query string entry resolved");
        check(remoteResult.html.contains("https://cdn.example/x.js"), "remote script kept for CSP to block");
        check(!remoteResult.html.contains("./src/main.jsx?v=1"), "relative entry script removed");

        // Starter template shipped for New React project.
        Map<String, String> starter = load(kit.resolve("templates/react-starter"));
        check("src/main.jsx".equals(ReactPreviewBundler.findEntry(starter)), "starter entry");
        ReactPreviewBundler.Result starterResult = ReactPreviewBundler.build(starter, development, NONCE, null);
        check(starterResult.warnings.isEmpty() && starterResult.skipped.isEmpty(), "starter is clean");
        write(out.resolve("react-starter.dev.html"), starterResult.html);

        // Other fixtures as generated pages.
        String[] names = {"single-file", "syntax-error", "bad-package", "runtime-error", "injection"};
        for (String name : names) {
            ReactPreviewBundler.Result result = ReactPreviewBundler.build(
                load(fixtures.resolve(name)), development, NONCE, "development");
            check(result.html.contains("<div id=\"root\"></div>"), name + " generated root");
            write(out.resolve(name + ".dev.html"), result.html);
        }
        ReactPreviewBundler.Result injection = ReactPreviewBundler.build(
            load(fixtures.resolve("injection")), production, NONCE, "production");
        String manifest = injection.html.substring(injection.html.indexOf("id=\"vy-react-modules\">"));
        manifest = manifest.substring(0, manifest.indexOf("</script>"));
        check(!manifest.contains("</script") && !manifest.contains("<!--"), "user source cannot close the manifest");

        // Not React and size limits.
        check(throwsBundle(() -> ReactPreviewBundler.build(load(fixtures.resolve("not-react")), production, NONCE, null)),
            "plain JS project reports BundleException");
        Map<String, String> many = new TreeMap<String, String>();
        many.put("index.jsx", "import React from 'react';");
        for (int i = 0; i <= ReactPreviewBundler.MAX_FILES; i++) {
            many.put("src/f" + i + ".js", "export default " + i + ";");
        }
        check(throwsBundle(() -> ReactPreviewBundler.build(many, production, NONCE, null)), "file count limit");
        Map<String, String> big = new TreeMap<String, String>();
        StringBuilder huge = new StringBuilder();
        while (huge.length() <= ReactPreviewBundler.MAX_SOURCE_BYTES) {
            huge.append("// padding padding padding padding padding padding padding padding\n");
        }
        big.put("index.jsx", "import React from 'react';\n" + huge);
        check(throwsBundle(() -> ReactPreviewBundler.build(big, production, NONCE, null)), "byte size limit");

        System.out.println("ReactPreviewBundlerCheck: " + passed + " assertions passed");
    }

    interface Action {
        void run() throws Exception;
    }

    private static boolean throwsIae(Action action) {
        try {
            action.run();
            return false;
        } catch (IllegalArgumentException expected) {
            return true;
        } catch (Exception other) {
            return false;
        }
    }

    private static boolean throwsBundle(Action action) {
        try {
            action.run();
            return false;
        } catch (ReactPreviewBundler.BundleException expected) {
            return !expected.getMessage().isEmpty();
        } catch (Exception other) {
            return false;
        }
    }

    private static void check(boolean condition, String name) {
        if (!condition) {
            throw new AssertionError("FAILED: " + name);
        }
        passed++;
    }

    private static Map<String, String> load(Path dir) throws IOException {
        Map<String, String> files = new TreeMap<String, String>();
        try (Stream<Path> walk = Files.walk(dir)) {
            for (Path path : (Iterable<Path>) walk.filter(Files::isRegularFile)::iterator) {
                files.put(dir.relativize(path).toString().replace(File.separatorChar, '/'), read(path));
            }
        }
        return files;
    }

    private static String read(Path path) throws IOException {
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }

    private static void write(Path path, String text) throws IOException {
        Files.write(path, text.getBytes(StandardCharsets.UTF_8));
    }
}
