# 0. Context and method

> **Status, 2026-11-23.** This page is the only part of the planned document set that exists. The research behind it ran on 2026-10-18. Verification was only partly completed and none of the planned sections was written, because the run hit an account usage limit. The research agents' full findings were then lost when the cloud workspace was recycled; only their summaries survived. Those summaries were handed to the owner's session bridge for the builder and are not in this repository. The app has also changed a great deal since this page was written, so section 0.3 describes the state on 18 October 2026 only.

This page was written as the opening of a planned design specification for the terminal inside **VY Canis Majoris**, Astra's Android workspace app for Melody's Samsung Galaxy S26 Ultra. The aim was a terminal measurably better than Termux for one job: building software and learning with AI agents (OpenAI Codex, Anthropic Claude Code, Google Gemini CLI) from a phone, without switching apps, with the Melody Session Bridge as the continuity and coordination layer.

It was written on 2026-10-18 by a Claude Code cloud session at the owner's request. Nothing in it was run on Samsung hardware by its author.

## 0.1 The request

> "Help Astra build an amazing terminal for android - can you tell me everything that goes into a terminal required for android that is way better than termux that can access libraries, connect to models, like using melody session bridge and multicollaborate in the same workspace and help people build and handle learning skills via their phone without switching apps? First everything that goes into a multimedia continuity terminal built with keyboard actions that can do everything needed on a normal keyboard connected to a desktop."

Two clarifications arrived while the work was in progress:

1. **Astra is an OpenAI model.** Astra is Melody's assistant persona running on OpenAI Codex / ChatGPT, is the phone coordinator on the bridge (session id `melody-phone`), and built Astra Terminal 0.1.1 in a Codex cloud workspace. Codex CLI is therefore Astra's own CLI. The spec treats the three vendor CLIs as equals; none is privileged.
2. **"Make sure it can open Claude and Gemini and dot is not needed to open yet."** Read against the screenshots of the build (0.3 below): "dot" is the app's own **Your OpenAI dot** card in Setup, which hands off to the ChatGPT app. So: Anthropic and Gemini must open, both as model profiles in the Agents tab and as Claude Code and Gemini CLI processes in the Terminal, at parity with Codex (P0); the OpenAI dot handoff is deferred (P2) and the spec does not design around it.

## 0.2 Who is who

| Name | Role in this project | Notes |
|---|---|---|
| Melody | Owner; expert user | Sets rules: never Replit Agent; label unverified claims; one writer per branch; handoffs via the bridge; code via PRs. |
| Astra (OpenAI) | Builder and phone coordinator | Has the Android toolchain and emulator in a Codex cloud workspace. "You" in this spec means Astra. |
| Claude (Anthropic) | Specs, protocol tests, SSH and security review via PRs | Authored this spec. |
| Gemini (Google) | Independent second review | |

## 0.3 What already exists

**VY Canis Majoris 0.1.0** ("first-light / development preview"), seen in eight screenshots Melody sent on 2026-10-18 from the S26 Ultra. Bottom tabs: Project, Terminal, Agents, Tools, Setup.

| Tab | What is there today (SEEN) |
|---|---|
| Terminal | "Local terminal, Android shell". Five extra keys (Ctrl C, Esc, Tab, up, down). A one-line "Enter a shell command" field with Send, plus Start / attach and Stop. Footer: bundled system shell and Android utilities only; no compilers or package management yet. |
| Agents | Model profiles (OpenAI, Anthropic, Gemini or a compatible HTTPS API; bring your own key) each with its own conversation per project, plus project memory. One profile exists: "Builder, openai / Astra". A failed request shows the toast "Model request failed. Check endpoint, key, model access, and connectivity." and the user turn appears twice. Footer discloses what is sent: memory, up to 5,000 of a chosen skill, recent conversation, the prompt. |
| Tools | MCP connections (Streamable HTTP over HTTPS, tokens in the encrypted vault; Configure server, Connect / inspect). Skills library (3 skills; Import SKILL.md; imports never execute code). Screen studio (share screen, snapshot, view latest; captures stay local). App preview and tests (sandboxed HTML/CSS/JS preview with network blocked; Run test.sh). |
| Setup | Workspace health checks (storage writable; profiles 0; notifications not granted; screen access needs fresh consent; MCP not connected this session; models verified only on a successful request). Verify encrypted storage. Export project and settings. "Your OpenAI dot" card (Open ChatGPT, Dot setup guide). Version card 0.1.0: store release, broader toolchains, automated agent editing and independent security review in progress. |
| Project | Project "first-light": files and project memory saved on device, editor autosave, Switch / new project, Export ZIP, New file, Import, Memory. No git visible. |

What the screenshots show about the gap: the terminal is command-at-a-time with no raw key path, no physical-keyboard parity, no Linux backend; the MCP connection does not survive the session; notifications are not yet granted; a failed model call duplicates the user's turn and reports a generic cause. Section 11 turns these into the gap list.

**Astra Terminal 0.1.1**, a separate and earlier app, an SSH terminal onto an existing Termux install (built and emulator-verified by Astra on 2026-10-18; recorded on the bridge as `project.workspace/handoff.astra-terminal-samsung.20261018` v1 and context `codex-astra-terminal-samsung-20261018` v1):

- Package `dev.astra.terminal`, versionCode 2, debug-signed development APK; source exists only as a zip in the Codex workspace.
- Native Android `/system/bin/sh` PTY in app storage; SSH terminal (JSch 2.28.8 + BouncyCastle 1.86, Ed25519) with explicit SHA256 host-key approval, persisted endpoint pins, refusal of changed keys, no saved password; session tabs; extra-keys row; foreground session service; explicit "Ubuntu" and "Codex" actions in SSH sessions.
- Architecture: connects to the existing Termux `sshd` on phone loopback (127.0.0.1:8022) to reuse the already-installed proot Ubuntu. No bundled Termux bootstrap, no second Ubuntu, no root.
- Build: JDK 21, Gradle 8.9, AGP 8.7.3, compileSdk 35, targetSdk 28, minSdk 26, NDK 27.2, arm64-v8a + x86_64.
- Verified: 153 unit tests, 13 transport checks, live JVM SSH, lint, APK v2 signature, 16 KiB zip alignment, 3 Android 9/API 28 instrumentation tests. Not tested on Samsung hardware; phone SSH connection unverified.

**Claude's earlier suggestions** (`project.workspace/handoff.astra-terminal-suggestions.20261018` v1, suggestions only, nothing adopted) covered reliability (wake locks, phantom process killer, tmux, sshd hardening, signing key), agent-first features (compose bar, OSC 9 notifications, agent tabs, protocol checklist, text-to-bridge, share-sheet intake), later engine options (libghostty-vt, Termux-plugin rebuild) and a three-builder workflow. This spec goes deeper, corrects that note where the research found it wrong, and labels anything taken from it as SUGGESTED-PRIOR.

**Phone evidence** (Melody's Termux screenshots, 2026-10-18): Termux installed; proot-distro installed; Ubuntu container present; `codex` and `astra` not found in the outer Termux shell (unknown inside Ubuntu).

**This repository** (`MCP-GPT-AGENT-Manager-`) is a Python MCP server exposing git and file tools through a proxy with origin allowlist, per-caller rate limit and audit log (Vecto) to a gated agent (Eidolon: path boundary, operation allowlist, denied secret patterns, size limit, hashed bearer token). The spec reuses that gate-proxy-audit pattern as the model for how agents get mediated access to the phone's workspace.

## 0.4 Method: what was planned and what happened

Planned: research each design dimension in parallel with independent agents, each with web access and a scope brief; hand each researcher's load-bearing claims to two independent verifiers with different lenses (an adversarial fact-checker working from primary sources, and a practitioner working from issue trackers and real-device reports); have section writers apply the verdicts, stating a claim as fact only when no verifier refuted it and at least one confirmed it; then check the sections against each other and write the roadmap.

What happened: eleven dimensions were researched (the ten listed in 0.6 plus UI and visual design, added at the owner's request). Of the twenty-two verification passes, twelve completed and ten failed on the usage limit. No section writer completed, so no section, cross-check or roadmap exists.

## 0.5 Confidence labels the sections were to use

| Label | Meaning |
|---|---|
| SEEN-VY-0.1.0 | Read from Melody's screenshots of the VY Canis Majoris 0.1.0 build on 2026-10-18. |
| VERIFIED-WEB | Checked against a source on 2026-10-18; URL given. |
| KNOWLEDGE | From the authors' training, not re-checked today. Treat as a lead, not a fact. |
| INFERRED | The authors' reasoning; untested. |
| EXISTING-0.1.1 | Already built per Astra's 0.1.1 handoff; not independently verified on Samsung hardware. |
| SUGGESTED-PRIOR | Appears in Claude's 2026-10-18 suggestions note. |

Priorities: **P0** needed before anything works reliably on the phone; **P1** what makes it better than Termux; **P2** later.

## 0.6 The sections that were planned

None of these was written. Section 1, keyboard and input, was to answer the owner's first-named priority and end with the complete key map. Sections 2 to 4 were the terminal engine, multimedia and continuity, and the Linux backend. Sections 5 to 7 were the agent, collaboration and learning layers. Sections 8 to 10 were security and distribution, the competitive landscape and the Android app architecture. A UI and visual design section and a closing roadmap with a gap list were to follow.
