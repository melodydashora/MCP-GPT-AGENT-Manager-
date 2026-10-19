#!/usr/bin/env bash
# Host checks for the VY React preview kit. Needs a JDK (javac 8+) and, for the browser
# stage, Node.js with Playwright and a Chromium build. Set VY_SKIP_BROWSER=1 to skip it.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/classes" "$WORK/pages"
javac --release 8 -Xlint:all,-options -Werror -d "$WORK/classes" \
  "$KIT/java/com/melody/vycanismajoris/ReactPreviewBundler.java"
javac --release 8 -cp "$WORK/classes" -d "$WORK/classes" \
  "$KIT/test/reactpreview/ReactPreviewBundlerCheck.java"
java -cp "$WORK/classes" com.melody.vycanismajoris.ReactPreviewBundlerCheck "$KIT" "$WORK/pages"
(cd "$KIT/assets/react" && sha256sum -c ../../SHA256SUMS.txt --quiet) && echo "asset hashes: OK"
if [ "${VY_SKIP_BROWSER:-0}" != "1" ]; then
  node "$KIT/test/reactpreview/browser-check.cjs" "$WORK/pages"
fi
