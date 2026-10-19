#!/usr/bin/env bash
# Rebuilds assets/react from the pinned npm lockfile. Needs Node.js 18+ and registry access.
# vy-react-runtime.js is hand-written source and is not touched.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cp "$KIT/scripts/asset-build/package.json" "$KIT/scripts/asset-build/package-lock.json" \
   "$KIT/scripts/asset-build/sucrase-entry.js" "$WORK/"
cd "$WORK"
npm ci --ignore-scripts --no-audit --no-fund
npx esbuild sucrase-entry.js --bundle --minify --format=iife --global-name=VySucrase \
  --target=es2017 --platform=browser --legal-comments=eof --outfile=vy-sucrase.min.js
OUT="$KIT/assets/react"
cp node_modules/react/umd/react.production.min.js node_modules/react/umd/react.development.js "$OUT/"
cp node_modules/react-dom/umd/react-dom.production.min.js node_modules/react-dom/umd/react-dom.development.js "$OUT/"
cp vy-sucrase.min.js "$OUT/"
cp node_modules/react/LICENSE "$OUT/licenses/react-LICENSE.txt"
cp node_modules/react-dom/LICENSE "$OUT/licenses/react-dom-LICENSE.txt"
cp node_modules/sucrase/LICENSE "$OUT/licenses/sucrase-LICENSE.txt"
(cd "$OUT" && sha256sum -c ../../SHA256SUMS.txt) && echo "Rebuilt assets match SHA256SUMS.txt"
