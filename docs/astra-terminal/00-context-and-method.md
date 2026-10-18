# 0. Context and method

This document set is a design specification for **Astra Terminal**, an Android terminal for Melody's Samsung Galaxy S26 Ultra that is meant to be measurably better than Termux for one job: building software and learning with AI agents (OpenAI Codex, Anthropic Claude Code, Google Gemini CLI) from a phone, without switching apps, with the Melody Session Bridge as the continuity and coordination layer.

It was produced on 2026-10-18 by a Claude Code cloud session on request of the owner. It is a specification, not code, and nothing in it has been run on Samsung hardware by its authors.

## 0.1 The request

> "Help Astra build an amazing terminal for android - can you tell me everything that goes into a terminal required for android that is way better than termux that can access libraries, connect to models, like using melody session bridge and multicollaborate in the same workspace and help people build and handle learning skills via their phone without switching apps? First everything that goes into a multimedia continuity terminal built with keyboard actions that can do everything needed on a normal keyboard connected to a desktop."

Two clarifications arrived while the work was in progress:

1. **Astra is an OpenAI model.** Astra is Melody's assistant persona running on OpenAI Codex / ChatGPT, is the phone coordinator on the bridge (session id `melody-phone`), and built Astra Terminal 0.1.1 in a Codex cloud workspace. Codex CLI is therefore Astra's own CLI. The spec treats the three vendor CLIs as equals; none is privileged.
2. **"Make sure it can open Claude and Gemini and dot is not needed to open yet."** Adopted reading: one-tap actions that open Claude Code and Gemini CLI, at parity with the existing "Codex" action in 0.1.1, are a P0 requirement; opening is on demand, and auto-opening any agent at app launch is not required yet. The word "dot" is ambiguous (likely voice-to-text) and is carried as an open question in sections 3 and 5 rather than guessed at.

## 0.2 Who is who

| Name | Role in this project | Notes |
|---|---|---|
| Melody | Owner; expert user | Sets rules: never Replit Agent; label unverified claims; one writer per branch; handoffs via the bridge; code via PRs. |
| Astra (OpenAI) | Builder and phone coordinator | Has the Android toolchain and emulator in a Codex cloud workspace. "You" in this spec means Astra. |
| Claude (Anthropic) | Specs, protocol tests, SSH and security review via PRs | Authored this spec. |
| Gemini (Google) | Independent second review | |

## 0.3 What already exists

**Astra Terminal 0.1.1** (built and emulator-verified by Astra on 2026-10-18; recorded on the bridge as `project.workspace/handoff.astra-terminal-samsung.20261018` v1 and context `codex-astra-terminal-samsung-20261018` v1):

- Package `dev.astra.terminal`, versionCode 2, debug-signed development APK; source exists only as a zip in the Codex workspace.
- Native Android `/system/bin/sh` PTY in app storage; SSH terminal (JSch 2.28.8 + BouncyCastle 1.86, Ed25519) with explicit SHA256 host-key approval, persisted endpoint pins, refusal of changed keys, no saved password; session tabs; extra-keys row; foreground session service; explicit "Ubuntu" and "Codex" actions in SSH sessions.
- Architecture: connects to the existing Termux `sshd` on phone loopback (127.0.0.1:8022) to reuse the already-installed proot Ubuntu. No bundled Termux bootstrap, no second Ubuntu, no root.
- Build: JDK 21, Gradle 8.9, AGP 8.7.3, compileSdk 35, targetSdk 28, minSdk 26, NDK 27.2, arm64-v8a + x86_64.
- Verified: 153 unit tests, 13 transport checks, live JVM SSH, lint, APK v2 signature, 16 KiB zip alignment, 3 Android 9/API 28 instrumentation tests. Not tested on Samsung hardware; phone SSH connection unverified.

**Claude's earlier suggestions** (`project.workspace/handoff.astra-terminal-suggestions.20261018` v1, suggestions only, nothing adopted) covered reliability (wake locks, phantom process killer, tmux, sshd hardening, signing key), agent-first features (compose bar, OSC 9 notifications, agent tabs, protocol checklist, text-to-bridge, share-sheet intake), later engine options (libghostty-vt, Termux-plugin rebuild) and a three-builder workflow. This spec goes deeper, corrects that note where the research found it wrong, and labels anything taken from it as SUGGESTED-PRIOR.

**Phone evidence** (Melody's Termux screenshots, 2026-10-18): Termux installed; proot-distro installed; Ubuntu container present; `codex` and `astra` not found in the outer Termux shell (unknown inside Ubuntu).

**This repository** (`MCP-GPT-AGENT-Manager-`) is a Python MCP server exposing git and file tools through a proxy with origin allowlist, per-caller rate limit and audit log (Vecto) to a gated agent (Eidolon: path boundary, operation allowlist, denied secret patterns, size limit, hashed bearer token). The spec reuses that gate-proxy-audit pattern as the model for how agents get mediated access to the phone's workspace.

## 0.4 Method

Ten design dimensions were researched in parallel by independent agents, each with web access and a scope brief. For each dimension, the researcher's load-bearing claims were handed to two independent verifiers with different lenses (an adversarial fact-checker working from primary sources, and a practitioner working from issue trackers and real-device reports). Section writers then applied the verdicts: a claim is stated as fact only when no verifier refuted it and at least one confirmed it with a primary source. A final pass checked the sections against each other for contradictions and gaps and produced the roadmap.

## 0.5 Confidence labels used throughout

| Label | Meaning |
|---|---|
| VERIFIED-WEB | Checked against a source on 2026-10-18; URL given. |
| KNOWLEDGE | From the authors' training, not re-checked today. Treat as a lead, not a fact. |
| INFERRED | The authors' reasoning; untested. |
| EXISTING-0.1.1 | Already built per Astra's 0.1.1 handoff; not independently verified on Samsung hardware. |
| SUGGESTED-PRIOR | Appears in Claude's 2026-10-18 suggestions note. |

Priorities: **P0** needed before anything works reliably on the phone; **P1** what makes it better than Termux; **P2** later.

## 0.6 How to read this set

Section 1 (keyboard and input) answers the owner's first-named priority and ends with the complete key map. Sections 2 to 4 are the terminal itself and its Linux backend. Sections 5 to 7 are the agent, collaboration and learning layers. Sections 8 to 10 cover security and distribution, the competitive landscape and the Android app architecture. Section 11 is the roadmap and the gap list against 0.1.1. Each section ends with a test checklist, open questions and the sources that were actually opened.
