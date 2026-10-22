# VY 0.4.4 (versionCode 20) deploy-gate checklist

v1, 2026-10-22. Written by claude-code-vy-react-kit-20261019 (cloud) at Melody's request.

**Sources.** A 9-agent workflow read the bridge notes (roadmap v13 and earlier), Melody's Drive (read-only) and current Play documentation. An independent critic then reviewed it.
- Full version: GitHub melodydashora/MCP-GPT-AGENT-Manager-, branch ccr-46e71b07-3zobv3, docs/vy-agents/2026-10-22-release-0.4.4-gate.md.

**Status: PLAN.** Nothing here was checked against /root/projects/vy-canis-majoris.
- Bug status comes from owner-published bridge notes.
- Where the source disagrees, the source wins. Record the difference in docs/ARCHITECTURE.md.

**Rules.**
- Every write, script run and Console action needs Melody's approval.
- Never send credentials to models, the bridge, logs or exports.
- Report only tests actually run, as pass, fail or not run, with exact error text.
- Never Replit Agent.

## 1. Lanes (one writer at a time)

**Claude Code on the phone (claude-code-vy-arch-guide-20261022)**
- Owns source edits and the build.
- Publishes project.vy-canis-majoris / claim.vy-source.20261022 while it holds the tree.

**Astra (melody-phone)**
- Read-only verification and QA.
- Saves CLI launch evidence to verification.vy-cli-launch.20261022.
- Runs section 6 on the built APK.

**General**
- Nobody else edits the tree while the claim says "held".
- At about 95% of your context or usage limit, bundle: buildable tree, source backup, checkpoint, handoff note, status message to claude-code-vy-react-kit-20261019.
- No Play Console submissions while Melody is asleep.

## 2. G0: before any E or C edit (blocker)

1. **Local git baseline.**
   - In /root/projects/vy-canis-majoris, run `git init`.
   - Its .gitignore covers build outputs, *.jks, *.p12, *.keystore, local.properties, artifacts/, .env* and files/ocean-parked.
   - Run `find . -size +50M`. libvynode.so is 93 MB, and GitHub rejects files over 100 MB. Keep prebuilts out of git and record them in a sha256 manifest.
   - Commit, tag v0.4.3-baseline, then commit F.
2. **Off-phone copy.**
   - Make an ENCRYPTED tarball (age or gpg) of the source.
   - Record its sha256 before and after the copy.
   - Never put plaintext keys or tokens on /sdcard, Drive or the bridge.
3. **Keystores (Melody does this).**
   - Two keys: the Play upload key, and the dev signing key (cert a15b6b30…).
   - Losing the dev key means Melody's own install can never be updated without uninstalling, which deletes all her projects.
   - Encrypt both, and keep each passphrase apart from its file.
4. **VY app-private data.**
   - Termux cannot read /data/data/com.melody.vycanismajoris, and 0.4.4 migrates every workspace.
   - Export every project in-app before installing 0.4.4. Treat those ZIPs as secret, because 0.4.3 exports can contain CLI tokens.
   - Leave files/ocean-parked/ alone.
5. **Termux backup.** The 11 GB backup probably contains tokens and keystores. Encrypt it before it leaves the phone.

## 3. 0.4.4 scope (revised: F must not wait on the risky part of E)

Release 19, which has the F crash, could be approved and go live to testers at any time.

**F: crash.** Already fixed in source.
- Also check every `terminal.*` call on lifecycle paths: onDestroy, onStop, the Stop handler, onSaveInstanceState.
- Add a host stub test with terminal == null.

**C: Build inventory.**
- Never walk into, and never count:
  - node_modules .git __pycache__ .venv venv site-packages .gradle;
  - dist build .next out coverage, when they are generated;
  - .cache .vy;
  - the E denylist.
- Honor a basic .gitignore subset.
- Count only files that could actually be shared.
- At the limit, refuse explicitly and name the five largest folders. No silent truncation.
- Host fixtures:
  - shaped like ocean (964 entries, node_modules 919): must pass;
  - more than 500 real source files: must refuse, naming folders.
- Implement it as ONE reusable pure-Java filter class, ProjectFilePolicy, so the 0.4.5 Agents work reuses it. See design.agents-context-window.20261022.

**E part 1 (low risk, ship in 0.4.4): one shared denylist.**

Applied in Project ZIP export, ProjectContext, the Build inventory and Build capture.
- **Credential and user-state names:**
  - .claude/.credentials.json, .claude.json, .claude/projects, .claude/todos, .claude/shell-snapshots, .claude/statsig;
  - .codex/auth.json, .codex/sessions;
  - .gemini/oauth_creds.json, .gemini/google_accounts.json, .gemini/.env;
  - .config/gh, .git-credentials, .netrc, .ssh, .gitconfig, .npmrc, .pypirc;
  - .env*, *.pem, *.key, *.p12, *.pfx, *.jks, *.keystore, id_rsa*, id_ed25519*;
  - shell and REPL histories: .bash_history, .python_history, .node_repl_history, .lesshst. These often hold pasted keys.
- **NEW blocker, Build must refuse to WRITE files that later run code.** "Shell commands are not run" is otherwise false.
  - .bashrc, .profile, .mkshrc, the $ENV file;
  - .claude/settings*.json (hooks), .gemini/settings.json, .codex/config.toml;
  - .npmrc, .git/ and .git/hooks/*, .vy/.
  - Flag changes to package.json scripts (pre/postinstall/prepare) and to Makefiles in review.
  - Host test for each case. QA row 30.
- **CORRECTION: do not blanket-exclude project-level agent config from export.** CLAUDE.md, AGENTS.md, GEMINI.md, .claude/commands, .claude/agents and a project .gemini/settings.json are legitimate project files.
  - Exclude only credentials and user state from export.
  - Never send any dot-config file to a model.
  - Never let Build write one.

**E part 2 (higher risk): private HOME.**
- Ships in 0.4.4 ONLY if QA rows 5 to 7 pass on the phone. Otherwise it moves to 0.4.5.
- **Before you change anything,** record on the phone:
  - `npm config get prefix`;
  - `command -v claude codex gemini`;
  - `readlink -f` of each one;
  - `echo $PATH`.
- **The PATH risk.** If the npm global prefix or ~/.local/bin is inside the project, moving HOME turns the CLIs into "command not found". Carry the prefix over, or fix PATH.
- **In vyterm.c:**
  - HOME = <filesDir>/home, outside files/workspaces;
  - XDG_CONFIG_HOME, XDG_CACHE_HOME, the npm cache and TMPDIR all private;
  - the working directory stays the project.
- **The migration:**
  - Move ONLY user-level and credential state, using the E1 names.
  - Use rename() on the same filesystem. Run it off the UI thread, journal it, make it idempotent and resumable.
  - Never delete anything.
  - .claude.json holds a "projects" map keyed by absolute path. Merge those keys and rewrite the paths; don't use keep-newest.
  - Keep quarantine copies for at least two releases, because Play has no rollback.
- **Acceptance:**
  - `echo $HOME` is outside workspaces and `pwd` is the project;
  - claude, codex and gemini still resolve, and stay signed in (or need one re-login that persists);
  - an export ZIP contains no credentials.

**Not in 0.4.4:** Agents-tab context work (0.4.5+), pip, React integration, launchers. Do not claim them in the listing.

## 4. CLI evidence (Astra, read-only, now)

Melody says Claude Code, Codex and Gemini CLI all run in VY's terminal. Record it; do not reinstall, pin or fork. For each of claude, codex and gemini:

```
c=claude   # then codex, then gemini
p=$(readlink -f "$(command -v $c)"); echo "$c -> $p"; file "$p" 2>/dev/null; head -c4 "$p" | od -c | head -1
$c --version; echo "exit=$?"
```

Record:
- whether each one is JavaScript run by the bundled node, or a native ELF;
- its version, launch command and exit code.

**Why the file type matters for Play.** Play's Device and Network Abuse policy forbids downloading executable native code from outside Play. Interpreted code is exempt.
- A CLI that runs only as a downloaded native ELF, through linker64, is a listing and policy risk.
- The store copy should then say "runs in the terminal with your own account" only for what is reproduced.

Save the results to verification.vy-cli-launch.20261022, with no tokens or account details.

## 5. Build, sign, upload (Stage 1 to 3)

1. Set versionCode 20 and versionName 0.4.4. Re-confirm targetSdk 36 (required for updates since 2026-08-31) and minSdk 26.
2. Run scripts/compile-check.sh, scripts/test-core.sh (with VY_JSON_JAR) and the new E and C host tests. Build with scripts/build-on-android.sh.
3. **16 KB pages.** Treat them as enforced now.
   - Run the alignment verifier on every .so.
   - Check zip alignment of uncompressed .so files (zipalign -P 16 or bundletool).
   - grep vyterm.c and the JNI code for a hard-coded 4096 or PAGE_SIZE.
4. Run section 6 on the dev APK, installed over dev 0.4.3. Every Block row must pass.
5. Build the signed AAB with the upload key and check it with bundletool. Record:
   - its sha256;
   - **whether base/lib/arm64-v8a/libvynode.so is inside.** Release 16 installs at 48.8 MB, against a 93 MB library. If Node is missing, every CLI and npm promise fails for testers.
   - **the manifest:** debuggable=false; cleartext setting; restricted permissions (REQUEST_INSTALL_PACKAGES, MANAGE_EXTERNAL_STORAGE, QUERY_ALL_PACKAGES, SYSTEM_ALERT_WINDOW); FGS types; no exported component that runs commands or opens paths for other apps.
   - Also produce native-debug-symbols.zip.
6. In Play Console (with Melody):
   - turn on Managed publishing;
   - upload to INTERNAL first, with symbols;
   - read the pre-launch report: any crash or ANR blocks;
   - promote to closed "Alpha" to replace 19. If 19 is still in review, check in Console how Play handles that.
   - Then test Report response from the Play-installed build against the live worker.
7. **App access (blocker for review).** Reviewers cannot use chat, Build or Report response without an API key.
   - Fill in App content > App access with steps.
   - Consider a temporary key with a spend cap, rotated afterwards.
   - The listing must say that users bring their own OpenAI, Anthropic or Google key, and their own CLI accounts.
8. **Data safety (before production).** Re-walk it for:
   - user-initiated transfers to AI providers;
   - Report response content;
   - crash data;
   - MCP/bridge traffic;
   - screenshots, if screen-review captures can go to a provider. That needs a prominent disclosure, and FLAG_SECURE on key-entry screens.
9. **Never install a Play-signed build over Melody's dev build.** The signatures differ, so it would force an uninstall that deletes her projects. Use a second device or an emulator with a Play image for the Play path.

## 6. Phone QA matrix (B = blocks upload, S = record and fix in 0.4.5)

| # | Area | Steps | Pass | Gate |
|---|---|---|---|---|
| 1 | Upgrade, dev | Install dev 0.4.4 over dev 0.4.3 | No uninstall prompt. Projects, profiles, keys (fresh-process readback), chat, memory and journal intact. About says 0.4.4 (20) | B |
| 2 | Upgrade, Play | Second device or emulator: 16→20 AND 19→20 from Play | Update offered, data kept, terminal, Python and Node start | B |
| 3 | Fresh install | Clean install, new project, terminal | No crash. HOME private from the first launch (if E2 shipped) | B |
| 4 | F crash | Don't keep activities ON, then OFF: rotate before the terminal starts; Back right after launch; Stop with no terminal; rotate 10 times with a terminal; switch apps 5 times; split screen | No crash and no NPE. Check logs with wireless adb from Termux (adb pair/connect), since Termux can't read VY's logcat | B |
| 5 | Claude Code | `claude --version`; `claude`; sign in via the browser hand-off; one prompt that makes Claude run a Grep/Glob search AND one Bash command; quit; force-stop VY; `claude` again | Works and stays signed in. Credentials not in the project | B |
| 6 | Codex | `codex --version`; sign in; one prompt; `echo $?` | Exit 0, no silent exit 1. Auth outside the project | B |
| 7 | Gemini CLI | `gemini --version`; authenticate the way that works today; one prompt | Works. Config outside the project | B |
| 8 | Terminal basics | Ctrl-C, Stop, long wrapped line, `xdg-open https://example.com`. Then a Claude/npm session with many children kept in the background for more than 10 minutes | No dropped characters. URL opens. No "[Process completed (signal 9)]"; if it appears, write tester guidance: battery Unrestricted, disable child-process restrictions, no app sleeping | B |
| 9 | E isolation | In ocean: `echo $HOME; pwd; ls -la; ls -la $HOME`; Build Details; Context | (E2) HOME outside workspaces. (E1) No credential files in Context, Build or export | B |
| 10 | C inventory | Move node_modules back from files/ocean-parked; Build on with Gemini Argon, then Astra; 1-file edit. Separately, a project with more than 500 real files | Ocean: no refusal, excluded folders named, edit applied. Over 500: explicit refusal naming folders | B |
| 11 | Build failures | Reject; terminal edit of a pending target then apply; oversized file; write .env.json; swipe away during apply | No change / conflict shown / explicit "left out" message / refused / recovered with no half-written file | B |
| 12 | Undo | Two-file Build then Undo, compare hashes. Then Build, CLI edit of the same file, Undo | Hashes match (B). Undo must not silently destroy the CLI edit (S) | B/S |
| 13 | Preview | web-multifile-test: Preview, edit, Preview. Remote fetch. Exfil page with img/CSS url()/sendBeacon/WebSocket/form/window.open/file:// iframe | Renders offline. Blocked requests visibly blocked. No exfil path; no addJavascriptInterface; file access flags false | B |
| 14 | React | A self-contained dist build renders; a CDN script fails visibly | No React claim in 0.4.4 | S |
| 15 | Python | Hello; stdin (13); Stop an infinite loop; HTTPS urllib; rotate during a run | Correct. Stop within a few seconds. No re-run on recreation | B/S |
| 16 | pip | `python -m pip --version` | 0.4.4: a clear "not available", no crash or hang | B |
| 17 | Node/npm | `node -v` v24.18.0; `npm -v` 11.16.0; `npm i lodash` and require it; `npm i better-sqlite3` | Pure JS works. The native add-on gives an npm error, not a crash | B/S |
| 18 | Export ZIP | Export ocean after using all three CLIs; `unzip -l` | No credential or user-state files (E1 list). Project agent docs present | B |
| 19 | Offline | Airplane mode: launch, terminal, Python, Node, Preview, chat, Build, Report, npm i | Local features work. Network features show specific errors; drafts kept | B |
| 20 | Agents regression | Each profile (OpenAI, Gemini Argon, Claude, Astra): profile test, one turn, Context, Report response, wrong key | Status-specific errors. Key redacted everywhere. Report reaches /report with matching responseChars | B |
| 21 | Single send | Rotate and background VY during a chat request and during Build apply | Exactly one provider call (check usage page or ledger). No automatic full-context re-sends | B |
| 22 | Pre-launch report | Internal track upload | 0 crashes, 0 ANRs. Symbols resolve. Screenshots hold no personal data | B |
| 23 | 16 KB | Verifier on all .so (B); terminal, Python and Node on a 16 KB device or emulator (S) | Pass, or "not run" recorded | B/S |
| 24 | Android 16 (targetSdk 36) | Predictive back: Back in the terminal, in the Editor with unsaved edits, in the composer with a draft. Edge-to-edge: keyboard and nav bar vs composer and terminal input. Foldable or tablet emulator (orientation locks ignored at 600 dp and up) | Nothing lost. Nothing hidden. No crash on resize | B |
| 25 | API 26–27 Node | `llvm-nm -D libvynode.so \| grep aligned_alloc`; `node -v` on API 26/27 emulators | Loads, or minSdk raised to 28 / Node disabled below 28 | B |
| 26 | Terminal can't read secrets | `env \| grep -iE 'key\|token\|secret'`; grep shared_prefs, databases and files for sk-, sk-ant-, AIza, Bearer, refresh_token | Nothing in plaintext; Keystore ciphertext only | B |
| 27 | xdg-open lockdown | `xdg-open 'intent:#Intent;component=x/y;end'`, file:, content:, javascript:, market: | Refused. Only http/https (mailto optional) | B |
| 28 | Editor vs Build | Unsaved edit in the Editor, Build changes the same file, save the Editor | Conflict prompt, no silent overwrite | S |
| 29 | Low storage | Under 50 MB free: Build apply, E2 migration, Export | Explicit error; no empty or half-written files (temp file + rename) | B |
| 30 | Write refusals | Ask Build to create .bashrc and .claude/settings.json | Both refused | B |
| 31 | Endpoint HTTPS | Point a profile at http://example.com | Refused (localhost excepted at most) | S |
| 32 | Zip-slip | If import exists: ZIP with ../, absolute paths, symlinks, .env, .claude/.credentials.json | Each refused; nothing written outside the project | B (if import exists) |
| 33 | Accessibility | TalkBack through the tabs, the edit toggle, Build, Undo, Preview, Stop, Report. Max font and display size, light and dark | Labels, roles, toggle state announced. No clipping. 48dp targets | S (B if a core control is unlabeled) |

## 7. Melody's actions (her call; nothing done for her)

- **Backups (G0).** Encrypted source, both keystores with their passphrases stored separately, and an encrypted Termux backup off the phone.
- **Tokens and keys.**
  - Replace the full-account Cloudflare token with one scoped to the vy-support worker.
  - Rotate the Session Bridge owner key and move it into a password manager. Drive has "Session Bridge - PRIVATE connection details.txt" in plaintext. It is shared with no one, but it is readable by any Drive connector.
- **ZIP exports.** Until E1 ships, don't share ZIPs of projects where a CLI signed in. If one was shared, sign those CLIs out and rotate the keys.
- **Testers.**
  - Recruit 15 to 20 now. The 14-day clock is the longest step.
  - VY is paid, and Google's help says closed testers must buy it. Decide between paying and promo codes; whether promo codes cover closed-track installs is unverified.
  - Never switch the app to free to work around this: a free app can't go back to paid.
  - Testers who sideloaded the old Drive APKs (dev key) must export their projects and uninstall before installing from Play. Then remove the Drive links.
- **Report response.** Read incoming reports. The AI-content policy expects reports to feed moderation.

## 8. Open questions

- Do bundles 16 and 19 contain Node?
- What is the outcome of the release-19 review?
- How does Play handle code 20 while 19 is in review?
- Was the Dashora Labs account created after November 2023, which brings the 12-tester rule?
- Does the Data safety answer "collected, not shared" cover AI-provider transfers?
- Is a second Android device or emulator available for Play-path testing?
- Why does the device test runner abort with exit 134?
- Is each CLI JavaScript or native (section 4)?
