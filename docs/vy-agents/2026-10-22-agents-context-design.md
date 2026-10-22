> Full version of the VY Agents tab design, written 2026-10-22 by a cloud Claude Code workflow: three independent designs, scored and merged. A short version for the phone builders is on the Melody Session Bridge at project.vy-canis-majoris / design.agents-context-window.20261022. Release gate: 2026-10-22-release-0.4.4-gate.md. Provider research: 2026-10-22-provider-research.md.

# VY Agents tab: context-efficient design (final spec)

**For:** the VY builders (Claude Code and Codex in VY's terminal on Melody's phone).
**Date:** 2026-10-22.
**Applies to:** release 0.4.5 and later. 0.4.4 (code 20) stays reserved for F (crash), E (HOME) and C (inventory). This spec adds nothing to 0.4.4 apart from the one recommendation in §5.1.
**Status:** design only. Nothing here has been checked against /root/projects/vy-canis-majoris. §3 lists what to read in the source before writing code. Where the source disagrees with this spec, the source wins, and the change is recorded in docs/ARCHITECTURE.md before coding.
**Base:** Design A ("one cached prefix, one project card, edits instead of whole files"), plus ideas from Design B ("lean context") and Design C ("one shared context"). §0.2 lists each one.

**Tags:**
- [Given]: stated by the coordinating session.
- [Reported]: from bridge notes quoted by the input designs; not re-checked.
- [A1], [O6], [G3]…: provider research keys (§19). [search]: a provider fact seen only in search summaries.
- [AS-n]: an assumption (§1.4).
- [Qn]: verify in the source first (§3).

---

## 0. Summary

### 0.1 The design in nine points

1. **One file filter.**
   - `ProjectFilePolicy` (pure Java) is the only place that decides what may be listed, sent, counted, written or exported.
   - Dependency, build-output, dot-config and credential files are never sent and never counted.
2. **One request layout for everything.**
   - Every request is built in the same order: STATIC → MEMORY → FILES → SUMMARY → HISTORY → TAIL. That covers chat, Build, compaction and reviews.
   - Everything above TAIL is byte-stable and cached by the provider. Only TAIL is new on each turn.
3. **A sticky working set.**
   - "Chosen files" become a per-conversation working set that lives in the cached FILES block.
   - Each file is sent once per version. It is never re-attached on every turn and never copied into history.
4. **Chat and Build share one prefix.**
   - The Build protocol is always in STATIC. The mode is one line in TAIL.
   - A change the model proposes in chat is applied later without asking the model again.
5. **Edits, not whole files.**
   - The existing strict JSON change-set protocol gets one new `edit` op: find/replace with a base hash.
   - Its result goes through the existing change-set, receipt and Undo path.
6. **One shared memory file.**
   - `AGENTS.md` at the project root holds the project card, the project memory and the current handoff.
   - The Agents tab sends it as its MEMORY block. Codex reads it directly. Claude Code and Gemini CLI load it through one-line pointers in `CLAUDE.md` and `GEMINI.md`.
   - One agent builds; the others review a small change set.
7. **Visible, rolling compaction.**
   - Long conversations fold into a summary that Melody can edit and must accept. The last 4 turns stay word for word, and nothing is deleted.
8. **Files on request.**
   - The model asks for a file with one text line (`VY-NEED-FILES:`), and one tap attaches it.
   - No provider needs a tool-calling loop.
9. **Everything visible, nothing cut silently.**
   - A footer meter shows the estimate before sending, and each reply gets a token receipt.
   - A Context sheet and a "What was sent" view show exactly what the model received.

### 0.2 Where each idea came from

| Idea | From | Note |
|---|---|---|
| ProjectFilePolicy shared by inventory, picker, card and export | A (B and C agree) | B/C's `.vyignore` subset added |
| Deterministic block order; Build protocol always in STATIC; mode only in TAIL | A | |
| Sticky working set in a cached FILES block; file text never in history | A | |
| Text protocol for file requests instead of a tool loop | A | Native tools are an optional Phase 6 |
| `edit` op inside the existing vy_build JSON; all-or-nothing; base hash | A | Closest-match error hints from B |
| MEMORY frozen per epoch; mid-epoch changes sent as TAIL deltas | B, C | Prefix stays stable when AGENTS.md or the file list changes |
| Anthropic breakpoints at the end of MEMORY and of FILES | B | The card stays cached when files change |
| Context note in TAIL (what the model holds, what changed, who changed it) | C | |
| AGENTS.md as the one shared memory + handoff file | C (pointer files from A) | Kept to one file. C's separate HANDOFF.md is folded in; its journal is deferred |
| Chat proposals applied without a second model call | C | Fixes the reported 0.3.1 double work |
| Undo never silently overwrites files changed outside VY | C | |
| Local git baseline plus an off-phone archive before refactoring | C (A: archive) | |
| Capability probe in "Profile test"; compaction thresholds set by measured cache class; cold-cache hint | B | |
| Per-block hash diagnostics; device parity self-test | B, C | |
| Redact credential-like text instead of refusing the whole file | B, C | A refused the whole file |
| Phone fixture script and per-phase phone tests | A | Extended |

**Not taken, and why:**
- **Native list/read/search/edit tool loop for all providers (B, C).** It is a large Java 8 change across three tool formats, Gemini thought signatures, schema limits and extra request rounds. Deferred to optional Phase 6, behind the capability probe.
- **Three provider-specific edit transports, including an OpenAI V4A `apply_patch` parser (C).** That triples the edit surface. One JSON `edit` op serves every provider.
- **Applying edits to a file that changed after the model read it ("re-anchoring", C).** An edit could land in the wrong place. A changed base is always rejected.
- **Re-sending only a diff of a changed file (C).** No source shows that models edit reliably from diffs of an earlier copy. FILES always holds the full current text.
- **journal.jsonl, `vy-journal`/`vy-snapshot` terminal commands and a snapshot blob store (C).** Useful, but not needed for the token goal. Backlog (Phase 6).
- **Dollar price tables (B).** Several prices are known only from search summaries [search]. The UI shows provider-reported tokens only.

---

## 1. Facts and assumptions

### 1.1 Given [Given]

**The app**
- VY Canis Majoris, package com.melody.vycanismajoris. First a modernized, better Termux; then an IDE with an Agents tab, offline preview, bridge/MCP, helper apps and packaging.
- The source exists only on Melody's phone, at /root/projects/vy-canis-majoris (Termux proot Ubuntu).
- Java 8, no Gradle on the phone; built with scripts/build-on-android.sh. The terminal is native (vyterm.c).
- Bundled runtimes: CPython 3.14.8, Node v24.18.0, npm 11.16.0.

**Releases**
- Google Play closed testing. Release 19 (0.4.3-browser) is in review.
- 0.4.4 (code 20) is planned with crash fix F, and ideally the HOME fix (E) and the inventory/limits fix (C).

**The Agents tab today**
- Model picker, for example "Gemini Argon · gemini-4-argon".
- "Project conversation · context kept", a "Context" button, "Profile test passed", "Report response".
- Toggle "Let the agent edit this project", with the text: "Build shares up to eight safe project text files with this model and saves its changes. Undo last build keeps a recovery copy. Shell commands are not run."
- Composer footer: "Brief + chosen files + recent chat".
- Editor quick actions: Preview, Run tests, Project memory, Activity journal, Last build, Undo last build.
- Build refused with "Project exceeds the 500-entry build inventory limit"; node_modules was 919 of 964 entries.
- Historical limits: 500-entry inventory, 8 files, 64 KiB context.

**Melody**
- Claude Code, Codex and Gemini all run in VY's terminal.
- Roadmap v13 priorities:
  - working pip;
  - working React in VY;
  - raised file/text limits with no silent truncation;
  - her standard Codex and Claude Code CLIs keep working in VY's terminal.

### 1.2 Reported in bridge notes [Reported]

These come from the input designs. Confirm them in §3.

**Code and protocol**
- Class names: ModelGateway, ProjectContext, ProjectConversation, ChatTurns, ChatRequestState, AgentDraftStore, ChatMarkdown, ChatCodeBlocks, SkillRepository, WorkspaceStore, ProjectChangeSet. ProjectChangeSet.validatePath refuses credential-like names.
- Build captures up to 8 complete allowed text files (64 KiB) on its own path.
  - It replies in a strict JSON whole-file protocol (host suite `projectbuildprotocol`, 184 assertions).
  - Apply uses optimistic checks against the originals, private copies of the originals, receipts and batch Undo.

**Tests**
- Host test runners: scripts/test-core.sh (JSON-java jar via VY_JSON_JAR) and scripts/compile-check.sh.
- The on-device app-process test runner aborts with code 134.

**Observed behaviour**
- Project "ocean" holds node_modules 919, .gemini 27, .vy 5, .cache 3 and .local 3 entries.
- Multi-agent work is manual: a brief per profile, files attached by hand, replies copied between agents.
- In the 0.3.1 phone test, a change Astra proposed with Build off had to be produced again with Build on.
- docs/ARCHITECTURE.md is the single architecture document (plan v12/v13).

**Known issues**
- FILE-LOCK: terminal writers bypass VY's Java file lock.
- PY-SANDBOX: the Python and Node runners share the app's UID.
- SOURCE-BACKUP: no Git; the newest off-phone archive predates 0.4.x.
- CLI-COMPAT: Codex exited 1 in VY's terminal in at least one configuration.
- A "60,000-character reply limit" exists somewhere; its scope is unknown.

### 1.3 Provider facts (details in §9)

- **Anthropic:**
  - up to 4 cache breakpoints, plus top-level automatic caching;
  - 5-minute default TTL, optional 1-hour TTL;
  - reads cost 0.1x (0.05x on Opus 5.5 and Sonnet 5.5); writes cost 1.25x (5m) or 2x (1h);
  - minimum cacheable length is 512–4,096 tokens depending on the model;
  - each breakpoint looks back at most 20 blocks [A1].
- **OpenAI:** automatic prefix caching from 1,024 tokens; `prompt_cache_key`; `prompt_cache_options` on gpt-5.6 and later (ttl "30m" only); `prompt_cache_retention` is deprecated [O1, O6].
- **Gemini:** gemini-4-argon has implicit caching only, from 4,096 tokens, at a 95% discount. Explicit `cachedContents` returns an error on Argon [G3, G5].

### 1.4 Assumptions [AS-n]

- **AS-1** Every Agents turn re-sends the brief, the chosen files and the recent chat, in an order that defeats caching. Phase 1 measures this.
- **AS-2** "Recent chat" is a sliding window of N turns [Q5].
- **AS-3** Build is a separate request with its own file capture, and it returns whole files [Q8].
- **AS-4** Project memory is a file inside the project; web-multifile-test's test.sh checks that it exists [Q12].
- **AS-5** CLIs started in VY's terminal run with the project folder as their working directory [Q20].
- **AS-6** Gemini CLI resolves `@AGENTS.md` imports in GEMINI.md, and Codex finds AGENTS.md in a folder that is not a git repository. Phase 0 checks both on the phone.
- **AS-7** A cold CLI session spends 10–40k tokens exploring before it does useful work.
- **AS-8** `git` can be installed and used in the proot Ubuntu.
- **AS-9** Conversations are stored per project and per profile [Q16].

---

## 2. What "triple work" is, and how each source is removed

Melody did not define it. Her message opens with "They all three run in the terminal" (Claude Code, Codex, Gemini), so the strongest reading is three agents redoing each other's work. The app also has two duplications of its own.

**Working definition:** any token or human step that re-sends, re-reads, re-asks or re-records project context that an agent already has and that has not changed.

| # | Duplication | Evidence | Status | How it is removed |
|---|---|---|---|---|
| 1 | The same context is paid for on every turn. Brief, files and recent chat are re-sent at full price; a sliding window, or files added to the newest message, defeats caching | Footer "Brief + chosen files + recent chat" | AS-1, AS-2, unverified; Phase 1 measures | Byte-stable cached prefix (§4). Working set inside the cached block (§5.3). Append-only history and compaction (§7) |
| 2 | Chat, then Build. Build captures and sends files again, regenerates whole files, and redoes changes already proposed in chat | Build's own 8-file capture [Reported]; the 0.3.1 test [Reported] | AS-3 | Build reuses the chat's prefix and working set, which is a cache read. Mode only in TAIL. Chat proposals applied without a second call. `edit` op instead of whole files (§6) |
| 3 | Three agents, plus VY's in-app profiles, each rediscover the project, re-read the same files and sometimes all build the same change | Melody's words [Given]; the manual multi-agent workflow [Reported] | Strongest reading | One AGENTS.md (card, memory, handoff) read by the tab and all three CLIs. One builder; the others review a small change set (§8) |

Ask Melody, in one line, which of the three costs her most (§18). Either way, the Phase 1 receipts show how the in-app tokens split.

---

## 3. Verify in the source first (Phase 0, no code change)

Record each answer with file:line in docs/ARCHITECTURE.md, under a dated heading "Agents request layout (as of 0.4.4)". Do not start a new doc.

```sh
cd /root/projects/vy-canis-majoris
grep -rln 'ModelGateway\|ProjectContext\|ProjectConversation\|ChatTurns\|ChatRequestState\|AgentDraftStore\|ProjectChangeSet\|WorkspaceStore' --include='*.java' .
grep -rn 'Let the agent edit this project\|Brief + chosen files\|500-entry' --include='*.java' --include='*.xml' .
grep -rn 'chat/completions\|/v1/responses\|/v1/messages\|anthropic-version\|generateContent' --include='*.java' .
grep -rn 'usage\|input_tokens\|prompt_tokens\|usageMetadata\|stop_reason\|finish_reason\|finishReason' --include='*.java' .
grep -rn '65536\|64 \* 1024\|substring(0\|truncat\|60000\|60_000' --include='*.java' .
grep -rn 'currentTimeMillis\|new Date\|SimpleDateFormat\|UUID\|String.format(' --include='*.java' .
```

| Q | Question | What the answer decides |
|---|---|---|
| Q1 | Which endpoint does each provider use: OpenAI Responses or Chat Completions, Anthropic Messages, Gemini generateContent or streamGenerateContent? | Adapter shapes (§4.6) |
| Q2 | Are replies streamed? Where do the usage fields arrive? | Usage parsing (§9.6) |
| Q3 | Where do the brief, Project memory, skills and the Activity journal go (system or user message)? Are they sent on every turn? | Move into STATIC/MEMORY |
| Q4 | Where are chosen files placed? Do they stay chosen, or are they picked again each turn? | If they are appended to the newest user message every turn, that is the largest re-billing; move them to FILES |
| Q5 | How many turns does "recent chat" keep? Is it a sliding window? Are dropped turns announced? | Append-only history and compaction; stepped window in the meantime (§7.3) |
| Q6 | Is anything that varies (time, dates, UUIDs, counters, locale-formatted numbers) placed above the user's message? | Move it into TAIL or remove it |
| Q7 | Do stored turns contain file contents inline? | Legacy handling (§14) |
| Q8 | How does Build pick its files? Is it a separate request? Does it send chat history? Where are 8, 64 KiB and 500 defined, and is 64 KiB per file or per request? Is anything truncated silently? | Build shares the prefix; truncation becomes a visible refusal |
| Q9 | What is the max output tokens per mode? Is the stop reason checked? | Cut-off detection (§6.6) |
| Q10 | Are provider usage fields parsed anywhere? | Phase 1 |
| Q11 | What do the Context button, Activity journal and Last build show, and where are they stored? Does turning the toggle on make every send a Build? | UI mapping; mode mapping (§6.2) |
| Q12 | Where do the brief and Project memory live (path, format)? What is inside .vy/? | AGENTS.md migration (§8.4) |
| Q13 | OpenAI: is `store` set? Is `previous_response_id` used? | §9.2 |
| Q14 | Does build-on-android.sh glob the source tree or list files one by one? | New classes must get compiled |
| Q15 | Which JSON library builds request bodies on the device? Android org.json keeps insertion order; the host JSON-java jar uses a HashMap | Host tests compare parsed structures; device parity self-test (§4.5) |
| Q16 | How are conversations stored: per profile? Are raw provider parts kept (for example Gemini thoughtSignature)? | §7.2, §7.5 |
| Q17 | Is change-set apply all-or-nothing today? Does Undo check a file's current content before restoring it? Do delete/rename ops exist? | §6.3, §6.4 |
| Q18 | What did 0.4.4's fix C implement: a reusable filter class, or inline checks? | Phase 1 reuses it or refactors it |
| Q19 | Where is the 60,000-character limit enforced: on model replies, or only on Report response? | Visible handling (§5.6) |
| Q20 | How does the terminal set the working directory and HOME after fix E? | Where the CLIs look for AGENTS.md, CLAUDE.md and GEMINI.md |
| Q21 | What does "Profile test" send and record? | Capability probe (§9.7) |

**Decision rules:**
- Brief or memory sent as a user message → move it into MEMORY (Phase 2).
- Files appended to the newest user message → move them into FILES (Phase 2).
- A sliding window → stepped window in Phase 2, compaction in Phase 4.
- Any silent truncation → a visible refusal in Phase 1.
- No usage parsing → add it in Phase 1. Every later acceptance test depends on it.
- An answer that contradicts this spec → update the matching spec section in ARCHITECTURE.md before coding.

---

## 4. Request layout per turn

### 4.1 Blocks, most stable first

| # | Block | Content | Changes when | Cache |
|---|---|---|---|---|
| 1 | STATIC | VY agent rules `vy-rules vN`: role, reply rules, safety rules, the full change-set protocol (also in chat mode), the VY-NEED-FILES rule, selected skills sorted by name | App update; skill selection changed | cached |
| 2 | MEMORY | Project card (generated: kind, run/test commands, file map with line counts, counts of never-shared folders), then AGENTS.md. Both as of the start of the epoch | Only when an epoch is rebuilt (§4.2) | Anthropic BP1, 1h |
| 3 | FILES | Working-set files, complete and current, in working-set order, each with path, sha8 and bytes. Plus `not sent` lines with reasons | A working-set file's content changes, or the set changes | Anthropic BP2, 1h |
| 4 | SUMMARY | Rolling summary of folded turns (only after the first compaction) | When a compaction is accepted | Anthropic BP3, 1h (when present) |
| 5 | HISTORY | Turns since the last compaction, exactly as sent and received. Never contains file contents | Each turn appends to it | Anthropic automatic 5m breakpoint |
| 6 | TAIL | Turn header and mode, context note, changes since the epoch started, last-build line, Melody's message | Every turn | New this turn; it becomes part of the next turn's cached HISTORY |

**Rules**
- **Nothing that varies goes above TAIL.**
  - Not allowed above TAIL: the clock, dates, UUIDs, battery, device state, absolute device paths, locale-formatted numbers.
- **File contents appear only in FILES.**
  - A file is either in FILES with its current text, or not sent at all.
  - So one list answers "what does the model see".
- **History is stored exactly as sent.**
  - The stored user turn is the full rendered TAIL; the stored assistant turn is the raw reply text.
  - ChatMarkdown may change the display, never the stored text.
  - A retry re-sends identical bytes.
- **The mode lives in TAIL.**
  - Chat and Build share every byte above TAIL, so the first Build after a discussion is a cache read.
- **Agent files are never in FILES.**
  - AGENTS.md is in MEMORY. CLAUDE.md and GEMINI.md are only pointers.
  - None of them can be added to the working set; the picker shows "already in MEMORY" or "pointer file".

### 4.2 Epochs

An epoch is a stretch of conversation during which MEMORY (card plus AGENTS.md) does not change. A new epoch starts when:
- a conversation starts, or is first opened in a new app version (the STATIC version changed);
- a compaction is accepted;
- Melody taps "Refresh context";
- the profile is switched (the new provider's cache is cold anyway);
- the changes waiting in TAIL (AGENTS.md diff plus file-list changes) add up to more than 2,000 estimated tokens.

Between rebuilds, changes are sent as small deltas in TAIL, and so become part of HISTORY:
- **AGENTS.md edited** (by Melody, a CLI or VY):
  - a unified diff against the epoch snapshot, with the old and new sha8;
  - if the diff is over 2,000 tokens, the delta says "AGENTS.md changed a lot; refresh suggested" and the Refresh banner appears.
- **Files added, removed or renamed:** one line each.
- **Working-set files** are never sent as deltas. FILES always carries their current text.

### 4.3 Text formats

**STATIC (excerpt, illustrative):**
```
VY agent rules v2
You are the coding agent inside VY, an Android IDE. The user is Melody.
Modes: the last message starts with [VY turn N · epoch E · mode CHAT|BUILD].
BUILD: reply with exactly one JSON object {"vy_build":2,...} and nothing else.
CHAT: answer in prose. If you propose file changes, end with ONE fenced block tagged vy_build holding the same JSON.
Ops: edit (find/replace; base = the sha shown for that file in FILES), create, update (whole file; small files only), delete/rename (need Melody's tick).
Never use line numbers in find. Include 1-3 unchanged lines so each find matches exactly once.
FILES holds the complete current text of every file you can edit. If you need another file, end your reply with one line:
VY-NEED-FILES: path1, path2   (max 10; path#L1-200 for part of a large file). Never guess file contents.
AGENTS.md is shared with other agents. To change it, propose an edit to AGENTS.md; Melody reviews it.
Never ask for, print or copy keys. A value shown as [VY redacted: ...] must never appear in a change.
```

**MEMORY (target 3,000 tokens or less):**
- The card's file map is capped at 300 paths. After that, folders are listed with counts, and the card says so.
```
# VY project card: ocean (epoch 3)
Kind: web project (index.html). React entry: none. Preview: offline, network blocked.
Run/test: ./test.sh
Shareable files (18; line counts as of epoch 3):
  index.html 88L
  src/App.jsx 132L
  src/styles.css 61L
  src/components/ (9 files, 640L)
Never shared (VY policy): node_modules/ (919), .gemini/ (27), .vy/ (5), .cache/ (3), .local/ (3); 2 credential-like files hidden
=== AGENTS.md sha=4c1d09ae (as of epoch 3; VY card block omitted, rendered above) ===
...AGENTS.md text...
=== end AGENTS.md ===
```

**FILES:**
- The markers carry the sha, so a file that happens to contain a marker cannot end the block early.
```
=== VY FILES: 3 files, complete, nothing truncated ===
=== file src/App.jsx sha=9f3a12bc bytes=4210 ===
...exact UTF-8 content (credential-like values redacted, see 5.5)...
=== end src/App.jsx sha=9f3a12bc ===
=== file data/log.txt lines 1-200 of 10,000 sha=77aa0c19 (partial, requested range) ===
...
=== end data/log.txt sha=77aa0c19 ===
=== not sent: data/big.json (328 KiB is over the 256 KiB whole-file limit; ask for a line range) ===
```

**TAIL:**
```
[VY turn 15 · epoch 3 · mode CHAT]
Context note: FILES holds src/App.jsx, src/styles.css, index.html (all current). SUMMARY covers turns 1-10.
Changed since your last reply: src/styles.css 0b7e1f20 -> 5d9c4a11 (outside VY: terminal).
Since epoch start: added src/Nav.jsx (40L, not in FILES). AGENTS.md 4c1d09ae -> 7e2a51c0 (diff below).
--- AGENTS.md diff ---
@@ Handoff @@
-Status: header colour pending
+Status: header colour done (Build 2); nav bar next
---
Last build: Build 2 changed 2 files; Undo available.
---
<Melody's message>
```
In Build mode the header reads: `[VY turn 16 · epoch 3 · mode BUILD: reply with one vy_build JSON object only]`.

### 4.4 Example: turn 15 on Anthropic

```json
{
  "model": "<profile model>",
  "max_tokens": 8192,
  "cache_control": {"type": "ephemeral"},
  "system": [
    {"type": "text", "text": "<STATIC: vy-rules v2, ~1.5k tokens>"},
    {"type": "text", "text": "<MEMORY: card + AGENTS.md, epoch 3, ~2.5k tokens>",
     "cache_control": {"type": "ephemeral", "ttl": "1h"}},
    {"type": "text", "text": "<FILES: 3 files, ~10k tokens>",
     "cache_control": {"type": "ephemeral", "ttl": "1h"}},
    {"type": "text", "text": "<SUMMARY: turns 1-10, ~0.7k tokens>",
     "cache_control": {"type": "ephemeral", "ttl": "1h"}}
  ],
  "messages": [
    {"role": "user", "content": "<TAIL of turn 11, as sent>"},
    {"role": "assistant", "content": "<reply 11, as received>"},
    {"role": "user", "content": "<TAIL of turn 12>"},
    {"role": "assistant", "content": "<reply 12>"},
    {"role": "user", "content": "<TAIL of turn 13>"},
    {"role": "assistant", "content": "<reply 13>"},
    {"role": "user", "content": "<TAIL of turn 14>"},
    {"role": "assistant", "content": "<reply 14>"},
    {"role": "user", "content": "<TAIL of turn 15>"}
  ]
}
```

What the provider reads from cache and what it writes:

| Segment | Turn 15 (no file changed) | Turn 16 (after a Build changed src/App.jsx) |
|---|---|---|
| STATIC + MEMORY | read (BP1) | read (BP1) |
| FILES | read (BP2) | written again (1h, 2x), one time |
| SUMMARY | read (BP3) | written again |
| HISTORY turns 11–14 | read (automatic) | written again (5m, 1.25x) |
| TAIL | written (5m) | written (5m) |

Every Build or file attach costs one rewrite of FILES, SUMMARY and HISTORY. That is why the working set is sticky and history is compacted.

### 4.5 Determinism rules and tests

**Rendering rules**
- Sort with `String.compareTo`, never Collator. Format numbers with `Locale.ROOT`.
- VY-generated text uses LF only.
- File text goes byte for byte: no CRLF normalisation, no trimming. A file that is not valid UTF-8 counts as binary and is not sent.
- sha8 = the first 8 hex characters of the SHA-256 of the raw bytes.
- `ContextRenderer` is a pure function. Its inputs are the rules version, skills, card inputs, AGENTS.md snapshot, working-set snapshot, summary, stored turns and tail inputs. It does no I/O.

**Block hashes**
- Each request stores the sha256 of every rendered block.
- The receipt then says "prefix identical: yes", or "no, first changed block: FILES (src/App.jsx, by Build 2)".

**Host golden tests**
- Shuffled input maps give identical bytes.
- A change to Melody's message alone leaves every byte identical through HISTORY.
- A change to one working-set file leaves every byte identical through MEMORY.
- CHAT vs BUILD mode leaves every byte identical through HISTORY.

**Request JSON**
- Caching depends on the content of blocks and messages, not on the order of the top-level request fields. Still build bodies in a fixed order.
- Host tests compare parsed structures, because JSON-java reorders keys [Q15].

**Device parity self-test**
- A hidden debug action renders the golden fixture on the phone and compares each block's sha256 with the host golden values.
- This is needed because the device test runner aborts with code 134 [Reported].

### 4.6 Provider mapping

Keep each profile's current max-token values [Q9]; the numbers here are placeholders.

**Anthropic Messages:** as in §4.4. Empty blocks are dropped (for example SUMMARY before the first compaction), and their breakpoint goes with them.

**OpenAI Responses:**
```json
{
  "model": "<profile model>",
  "instructions": "<STATIC>\n\n<MEMORY>\n\n<FILES>\n\n<SUMMARY>",
  "input": [
    {"role": "user", "content": "<TAIL of turn 11>"},
    {"role": "assistant", "content": "<reply 11>"},
    {"role": "user", "content": "<TAIL of turn 15>"}
  ],
  "max_output_tokens": 8192,
  "store": false,
  "prompt_cache_key": "vy-3f9a0c4b7e21d855"
}
```
**OpenAI Chat Completions:** the same text goes in one first `system` message, then the history messages, then TAIL.

**Gemini generateContent:**
```json
{
  "systemInstruction": {"parts": [
    {"text": "<STATIC>"}, {"text": "<MEMORY>"}, {"text": "<FILES>"}, {"text": "<SUMMARY>"}]},
  "contents": [
    {"role": "user", "parts": [{"text": "<TAIL of turn 11>"}]},
    {"role": "model", "parts": ["<stored raw parts of reply 11>"]},
    {"role": "user", "parts": [{"text": "<TAIL of turn 15>"}]}
  ],
  "generationConfig": {"maxOutputTokens": 8192}
}
```

API keys stay in headers, as today. No tools are declared in Phases 1–5.

---

## 5. File access

### 5.1 ProjectFilePolicy (the only place these rules live)

**For 0.4.4 only:** implement fix C with this class and this exclusion list, so 0.4.5 can reuse it. If C shipped in another form [Q18], Phase 1 refactors it into this class. Never keep two filters.

Rules, in order:

1. **Containment.**
   - The canonical path must be inside the project root.
   - Refuse `..`, absolute paths, and a symlink at any path component. Symlinks are never followed.
2. **SECRET.** Never opened for content, sent, written by an agent or exported. Only counted by name.
   - Folders at any depth: `.git .gemini .claude .codex .cache .local .config .npm .ssh`.
   - File names: the list ProjectChangeSet.validatePath already refuses. Move that rule into the policy and have validatePath call it.
   - More file names, case-insensitive: `.env .env.* *.pem *.key *.p12 *.pfx *.jks *.keystore id_rsa* id_ed25519* .npmrc .pypirc .netrc *credentials* secret.* secrets.* service-account*.json google-services.json *api-key* *api_key*`.
   - The model sees only a count ("2 credential-like files hidden"). Melody sees the names.
3. **HEAVY.** Never sent, counted or walked into.
   - `node_modules .venv venv __pycache__ site-packages .pytest_cache .gradle`.
   - Excluded from ZIP export unless "Include dependencies and build output" is ticked.
4. **DEFAULT-EXCLUDED.** Treated like HEAVY, but a `.vyignore` line such as `!dist/` can bring a folder back in.
   - `dist build .next .nuxt .expo .turbo .parcel-cache coverage target out .idea .vy`. The `.vy` entry is pending Q12.
5. **Ignore files.**
   - Root `.gitignore` and `.vyignore`, in a documented subset: names, `*`, `?`, trailing `/`, leading `/`, `!`.
   - A line VY cannot parse shows a warning ("line 7 ignored: unsupported pattern"). It is never skipped silently.
   - Ignore files can only bring back DEFAULT-EXCLUDED folders, never SECRET or HEAVY ones.
6. **Binary.** A NUL byte in the first 8 KiB, or invalid UTF-8: listed as `[binary 24K]`, never sent.
7. **Size.**
   - Text files over 256 KiB are listed, but sent only as explicit line ranges (§5.4).
   - Over 8 MiB, content is refused; the file stays listed.

**The walk**
- Excluded folders are never entered.
- For each excluded top-level folder, an entry count is kept, capped at 2,000 (shown as "2,000+"). Details uses it to name the largest folders.
- The scan stops at 50,000 shareable entries or 10 seconds. The card and the Context sheet then say "map incomplete: scan stopped at N".

**Used by:** the Build inventory (C), the working-set picker, the card and map, the AGENTS.md managed block, ZIP export, VY-NEED-FILES attaches and the secret scan.

**Not used by:** the preview snapshot. A plain preview may legitimately reference files under node_modules. Leave the preview unchanged until a phone test shows the policy does not break it.

### 5.2 Manifest with hashes (ProjectIndex)

- **Storage:** app-private (`files/agents/<projectId>/index.json`); never in the project folder, never exported.
- **Per shareable file:** path, size, mtime, line count, kind (text, binary or large), and the full sha256. The hash is computed lazily and cached by path + size + mtime.
- **Rescans:** incremental, before each send and when the Agents tab resumes. A file is rehashed only when its size or mtime changed.
- **Used for:**
  - change detection ("changed outside VY");
  - base checks for edits;
  - card generation;
  - block hashes;
  - the "not sent" list.
- **What the model sees:**
  - the map with line counts (MEMORY, as of the epoch start);
  - sha8 only for files in FILES and for AGENTS.md.
  - Full hashes cost tokens the model does not need, so they are never sent.

### 5.3 Sticky working set

- **What it is:** a per-conversation list, kept in the order files were added and stored with the conversation. It shows as chips above the composer.
- **How it changes:** only through explicit actions.
  - the picker "+";
  - long-press to remove;
  - "Attach" on a model request;
  - the Build fallback below.
- **Snapshot at send:** VY captures an immutable snapshot of each file (path, bytes, sha8). Build checks `base` against that snapshot.
- **Build with an empty set:** Build uses its current auto-capture, filtered by the policy. The captured files are listed in the receipt and become the working set.
- **Limits** (in `AgentLimits`):
  - whole files up to 256 KiB each;
  - at most 40 files and 512 KiB per set;
  - the whole request must fit the profile budget: default 60k estimated tokens, adjustable from 16k up to the model's context window.
  - Every refusal names the file and the number.

### 5.4 On-demand reads (VY-NEED-FILES)

- **Parsing.** VY reads only the last line of a reply. It shows a chip: "Model asks for: src/api.js (≈1.1k), src/util.js (≈0.4k) [Attach and continue] [Dismiss]".
- **Attach.**
  - The files join the working set; the policy and the budget still apply.
  - VY sends a short TAIL: "Attached: …; continue."
- **Refused or unknown paths.** They are listed with their reasons, both in the chip and in the next TAIL, for example "not attached: .env, credential file, never shared".
- **Line ranges** (`path#L9001-9100`, at most 2,000 lines or 96 KiB per range).
  - They go into FILES with an explicit "partial, requested range" label.
  - The full file never goes in silently.
- **Setting "Auto-attach small requests"** (off by default). When on, VY attaches automatically if the total is 8k estimated tokens or less and every path is allowed. The chip still shows.
- **Cost.** An attach changes FILES, so FILES, SUMMARY and HISTORY are rewritten once (§4.4).

### 5.5 Secret scan

**Runs on:** every file going into FILES, every user message, every AGENTS.md write by VY, Copy receipt, and review packets.

**Patterns** (high confidence only):
- a PEM private-key header;
- `sk-ant-[A-Za-z0-9_-]{20,}`, `sk-proj-[A-Za-z0-9_-]{20,}`, `sk-[A-Za-z0-9]{32,}`;
- `AIza[0-9A-Za-z_-]{35}`;
- `ghp_[A-Za-z0-9]{36}`, `github_pat_[A-Za-z0-9_]{22,}`;
- `xox[abprs]-[A-Za-z0-9-]{10,}`;
- `AKIA[0-9A-Z]{16}`;
- an exact match against hashes of the keys stored in Melody's profiles.

**In files**
- The match is replaced in the copy that is sent with `[VY redacted: credential-like text, 39 chars]`.
- Melody and the model both see it: "1 value redacted in src/config.js line 1".
- A change set whose `find`, `replace` or `content` contains a redaction marker is refused: "edit touches a redacted value; edit that line yourself".

**In user messages:** a dialog before sending: "Your message looks like it contains a key. [Edit] [Send anyway]".

**Never kept:** matched text is never shown, logged, stored in receipts or copied.

The name rules in §5.1 stay the main defence. The scan is a second net.

### 5.6 Limits: old and new; nothing is cut silently

| Limit | Today | New | At the limit |
|---|---|---|---|
| Build inventory | 500 entries, including node_modules [Given] | Shareable files only; excluded folders are not walked; the scan stops at 50,000 shareable entries or 10 s | "map incomplete: scan stopped at N"; Details names the largest excluded folders |
| Files per request | 8 (Build) [Given] | Working set of up to 40 | Refuse to add, with the reason |
| Bytes per request | 64 KiB [Given] | Working set up to 512 KiB; the whole request must fit the profile budget | Refusal, or the over-budget dialog |
| Whole file | not documented | 256 KiB whole; larger only as labelled line ranges; over 8 MiB, no content | `not sent` line to the model and the reason in the chip |
| Line range | n/a | 2,000 lines or 96 KiB | "partial: lines a–b of N" |
| Request budget | none | Default 60k estimated tokens; per profile from 16k up to the model's window | Dialog: Compact / Remove files / Send anyway / Cancel |
| AGENTS.md | n/a | Warning above 200 lines or 24 KiB; confirmation above 64 KiB | Never cut |
| Card map | n/a | 300 paths, then folders with counts | Stated in the card |
| Compaction banner | n/a | HISTORY above 40%, 20% or 12% of the budget, depending on the cache class | Banner |
| Edits per file | n/a | 50 | Change set rejected |
| File requests per reply | n/a | 10 | The rest are listed as not attached |
| Model output | Profile value [Q9]; 60,000-character limit with unknown scope [Q19] | Values unchanged; cut-offs detected (§6.6) | "Cut off" caption; no change set applied |
| Display of a long reply | 60,000 characters? [Q19] | If this is a display cap, the full reply is saved and linked | Never silently shortened |

---

## 6. Edits, Build and Undo

### 6.1 Change-set shape

Adapt the field names to the existing protocol [Q8]. `vy_build` goes from 1 to 2; the parser accepts both.

```json
{
  "vy_build": 2,
  "summary": "Make the header blue",
  "changes": [
    {"op": "edit", "path": "src/styles.css", "base": "9f3a12bc",
     "edits": [{"find": "h1 { color: red; }", "replace": "h1 { color: #1e5bd8; }"}]},
    {"op": "create", "path": "src/Banner.jsx", "content": "..."},
    {"op": "update", "path": "index.html", "base": "77aa0c19", "content": "...whole file..."}
  ]
}
```

| Op | Use |
|---|---|
| `edit` | Existing files |
| `update` (whole file) | Only for files of 2 KiB or less, or when more than half the file changes. Needs `base` |
| `create` | The path must not exist and must be allowed by the policy |
| `delete`, `rename` | Only if the existing protocol has them [Q17]. Never applied without a tick for each file |

### 6.2 Where change sets come from

- **Toggle on** ("Let the agent edit this project"): the mode is BUILD. The reply is one vy_build object, read by the existing strict parser.
- **Toggle off:** the mode is CHAT and the reply is prose.
  - If the model proposes file changes, it ends with one fenced block tagged `vy_build` holding the same JSON.
  - VY parses it into a draft (AgentDraftStore) and shows a card: "Proposed changes: 2 files [View] [Apply] [Discard]".
  - Apply asks Melody to turn on editing, or applies once after a confirmation. It goes through EditApplier, with **no second model call**. This removes the reported 0.3.1 double work.
- If turning the toggle on does not mean "every send is a Build" today [Q11], map BUILD mode to whatever currently triggers a Build.

### 6.3 EditApplier (pure Java)

1. **Path and base checks.**
   - The path must pass the policy and validatePath.
   - For `edit` and `update`, the path must be in the working-set snapshot the model saw (or be AGENTS.md, §8.3), and `base` must equal that file's sha8.
   - Otherwise: "src/a.js changed since the model saw it".
2. **Matching.** Edits apply in order to the text as it evolves. Each `find` must be non-empty and match exactly once.
   - Tier 1: exact match.
   - Tier 2, only when tier 1 finds nothing: CRLF→LF and trailing spaces on each line ignored. It must still match exactly once, and the receipt notes "whitespace-tolerant match".
   - There are no looser tiers. Aider found that disabling flexible patching multiplied editing errors about 9 times [P1]; one safe tier keeps most of that benefit.
3. **Limits.** At most 50 edits per file, and the result must differ from the original.
4. **Writing.**
   - The result is the complete new content. It goes through the existing ProjectChangeSet path: validatePath, the optimistic check against originals on disk under the Java lock, private originals, receipts and batch Undo.
   - The Undo format is unchanged.
5. **All or nothing.** If any change fails, nothing is written. Q17 confirms whether this is today's behaviour; if it is not, make it so.
6. **Rules given to the model in STATIC:**
   - use `edit` for existing files;
   - never use line numbers [O8, P1];
   - include 1–3 unchanged lines in each `find` so it is unique;
   - use whole-file `update` only for small files or large rewrites.

### 6.4 Undo and writers outside VY

- **Before Undo restores a file,** it checks that the file's current sha equals the after-sha that Build recorded [Q17].
- **If the file has changed since** (in the editor, the terminal or a CLI), Undo shows a dialog: "src/App.jsx changed after this build (outside VY). [Skip this file] [Restore anyway: the current copy is saved to recovery] [Cancel]".
- **A multi-file Undo stays atomic,** unless Melody chooses per file.
- **Writing a change set:**
  - re-check each sha under the lock immediately before writing;
  - write through a temp file and rename (check what the current code does).
  - This narrows the race with terminal writers (FILE-LOCK [Reported]) but cannot remove it.

### 6.5 Errors and "Ask model to fix"

- **Per-edit errors** are written so the model can fix them in one try. Examples:
  - `edit 2 in src/styles.css: find text matches 3 places (lines 12, 40, 77); add surrounding lines`
  - `edit 1 in src/App.jsx: find text not found; closest match lines 40-46 (82% similar): <those lines>`
- **"Ask model to fix"** (one tap) sends a BUILD-mode TAIL containing only the error list. The prefix is cached, so it is cheap.
- **No automatic retries.**
- **Receipts track the edit failure rate per profile.**

### 6.6 Replies cut off at the output limit

- **How a cut-off is detected:**
  - Anthropic `stop_reason: max_tokens`;
  - OpenAI Responses `status: incomplete` with reason `max_output_tokens`;
  - Chat Completions `finish_reason: length`;
  - Gemini `finishReason: MAX_TOKENS`.
- **What VY does:** it parses no change set and applies nothing.
- **Message:** "Reply stopped at the 8,192-token output limit before the change set was complete. Nothing was changed. [Retry with 16,384] [Continue]". Continue applies to prose only.

---

## 7. Conversation memory

### 7.1 Three layers

| Layer | What | Where in the request | Lifetime |
|---|---|---|---|
| Pinned memory | AGENTS.md: card, brief, project memory, handoff | MEMORY | Across conversations and agents |
| Rolling summary | Summary of folded turns | SUMMARY | Per conversation; replaced by each compaction |
| Recent turns | Turns since the last compaction | HISTORY | Until the next compaction |

- The Activity journal is never sent; it is Melody's own log.
- "Last build" adds one line to TAIL after a Build or an Undo.

### 7.2 What is stored per turn

- The rendered TAIL (user side) and the raw reply text, word for word.
- Mode, profile id and model.
- For Gemini, the raw `parts` of each model turn [Q16]:
  - replayed only to the same model;
  - flattened to plain text for any other provider.
- The working-set manifest that was sent (path, sha8, bytes).
- The estimate, the provider's usage (input, cache read, cache write, output) and the stop reason.
- The block hashes (§4.5).

**Receipts** hold counts, paths and hashes only.

**Request bodies:** the last 5 per conversation are kept in app-private storage for "What was sent".
- They contain project text but no headers, and therefore no keys.
- They are deleted with the conversation.

### 7.3 Append-only history

- Every turn since the last compaction is sent.
- There is no sliding window: a window changes the first history message on every turn, which breaks caching.
- **Interim, from Phase 2 until Phase 4, only if Q5 finds a sliding window:**
  - use a stepped window: the first sent turn moves forward 10 turns at a time;
  - TAIL and the Context sheet say "turns 1–10 not sent".

### 7.4 Compaction (explicit, visible and rolling)

**Cache class per profile**

The class is measured over the last 5 eligible requests (requests whose prefix is above the model's cache minimum):

| Class | Rule |
|---|---|
| Strong | Average cache read is at least 70% of input (typical for Anthropic and OpenAI) |
| Weak | Some hits but under 70%, or Gemini implicit caching |
| None | 0 hits on 3 eligible requests in a row, or the provider reports no cache fields |

**Banner threshold** (HISTORY estimate as a share of the profile budget):
- Strong 40%, Weak 20%, None 12%.
- With the default 60k budget, that is about 24k, 12k and 7k.
- Reason (from Design B's model): with strong caching, compacting early costs more than reading cached history; with no caching, history must stay short.

**Cold-cache hint**
- When it shows: the last request was longer ago than the cache TTL, and HISTORY is over 6k tokens.
  - Anthropic history TTL: 5 minutes.
  - OpenAI gpt-5.6 and later: 30 minutes [O1].
  - Unknown: 5 minutes.
- Text: "Cache has gone cold; compacting now costs less than re-sending the history. [Compact] [Send as is]".

**Hard limit**
- If the request would exceed the model's context window: "Too much context for <model> (≈N tokens). [Compact] [Remove files] [Cancel]".
- VY never trims automatically.

**Procedure**
1. One call on the same profile: the same prefix (a cache read) plus a COMPACT tail using the template below. File contents are never in history, so the input is small.
2. Melody sees the summary in a card. She can edit it, then Accept or Reject.
3. Accept does four things:
   - SUMMARY becomes the new summary, covering turns 1..b;
   - the last 4 turns stay word for word;
   - a new epoch starts;
   - the original turns are kept and viewable ("Turns 1–18 summarized · Show"). They are never deleted.
4. VY proposes an update to the AGENTS.md Handoff section, built from the summary's status and next steps. It is a reviewed card (§8.3).
5. Reject, or a failed call: nothing changes.

**Summary template** (adapted from Codex's compaction prompt [O13]):
> "Write a handoff summary for another model that will resume this project conversation. Headings: Goal; Current state; Decisions (with file paths and turn numbers); Melody's constraints and preferences; Files touched (path: what changed); What was tried and failed; Open questions; Next steps. At most 600 words. No code longer than 3 lines."

**Provider-native compaction is not used.** That means Anthropic compaction and context editing, and OpenAI `/responses/compact`.
- Server-side summaries cannot be carried to another provider or to the CLIs.
- clear_tool_uses invalidates the cached prefix [A4].

### 7.5 Switching profile

- Switching profile inside a project starts a new epoch for the target profile. That profile gets:
  - STATIC, MEMORY and FILES (the same working set);
  - SUMMARY, if there is one;
  - the last 4 turns flattened to plain text, for example "[Build 2 applied: src/App.jsx, src/styles.css]".
- Provider-specific parts are never carried across: no Gemini signatures, no Anthropic thinking blocks.
- The meter warns before sending: "Switching to Gemini Argon: ≈14k tokens, first request uncached".

---

## 8. One shared memory file for the Agents tab and the terminal CLIs

### 8.1 The file

`AGENTS.md` at the project root.
- Target: 200 lines or fewer [A11].
- A warning above 200 lines or 24 KiB; a confirmation above 64 KiB. It is never cut.

```markdown
# <project> - shared agent memory
<!-- Read by: VY Agents tab, Codex (AGENTS.md), Claude Code (via CLAUDE.md), Gemini CLI (via GEMINI.md).
     Never put keys, tokens or passwords in this file. -->

<!-- vy:card:start (generated by VY; edit outside the markers) -->
Kind: web project (index.html) · Preview: VY offline preview
Run/test: ./test.sh
Folders: src/ (12 files), public/ (4), data/ (2)
Never read or edit: node_modules/, .git/, .gemini/, .claude/, .codex/, .cache/, .local/, dist/, build/, credential files
<!-- vy:card:end -->

## Brief
<what this project is, for whom, what "done" looks like>

## Project memory
- Conventions: ...
- Decisions (newest first): 2026-10-22 · claude-code · Use CSS variables for the theme · because ...

## Handoff
Goal: ...
Status: ...
Builder now: <one agent> (others review)
Next steps: 1. ... 2. ...
Open questions for Melody: ...
Recent changes (newest first, max 10): 2026-10-22 · codex · src/Nav.jsx · added nav bar

## Working agreement (every agent)
1. Read this file first. Do not explore the folders under "Never read or edit".
2. Only the agent named in "Builder now" edits files; the others review and write findings.
3. Before you stop, update Handoff (Status, Next steps, Recent changes). Keep it short.
4. Record lasting decisions under Project memory. Link long docs; do not copy them.
5. Never write keys or tokens anywhere in the project.
```

**What VY writes in the managed card block:** kind, commands, a folder summary and the never-read list, in 40 lines or fewer. It has no per-file line counts, so it changes only when folders change. The full map with line counts lives only in the in-app MEMORY card.

### 8.2 Pointer files

**`CLAUDE.md`:**
```
<!-- vy:pointer:start -->
@AGENTS.md
<!-- vy:pointer:end -->
```
- Claude Code supports `@path` imports [A11].

**`GEMINI.md`:** the same block [AS-6]. If Gemini CLI's `/memory show` does not include the AGENTS.md text:
1. Set Gemini CLI's context file name to AGENTS.md in its user settings. After fix E those settings live outside the project. Check the exact setting name on the installed version.
2. Otherwise, VY writes a mirror of AGENTS.md between the markers, with a header line `<!-- mirror of AGENTS.md sha=... -->`, and refreshes it whenever AGENTS.md changes.

**Codex** reads AGENTS.md natively. AS-6 still needs confirming: does Codex find it outside a git repository?

**General rules**
- Text outside VY's markers is never touched.
- If CLAUDE.md or GEMINI.md already exist, the block is inserted at the top after Melody confirms.

### 8.3 Who writes what

| Part | Written by | How |
|---|---|---|
| vy:card block | VY only | The "Agent guide" quick action, or an epoch rebuild when folders changed; only between the markers |
| Brief, Project memory | Melody; in-app agents by proposal | An in-app model proposes an `edit` on AGENTS.md (base = the sha in the MEMORY header or in the latest TAIL diff). It is **always** a reviewed card, even when edits are set to apply automatically. CLIs edit the file directly under the working agreement |
| Handoff | Whichever agent stops; VY proposes one after a compaction | Same as above |

**Write rules for VY**
- VY writes AGENTS.md through a temp file and a rename, after checking the sha it last read.
  - If the file changed in the meantime, VY re-reads it and re-applies only its own block.
  - If its block was changed or the markers are broken, VY shows the conflict, or appends a fresh block with a warning.
- Every VY write is a normal journaled change with Undo, and is secret-scanned first.

**Edits made by CLIs mid-conversation** reach the in-app model as a TAIL diff (§4.2). They do not break the cached prefix.

### 8.4 Moving today's brief and Project memory (Phase 4)

- **If they live elsewhere [Q12]:**
  - VY copies them into the "## Brief" and "## Project memory" sections as a reviewed, undoable change;
  - the old store is kept, read-only;
  - the Editor's "Project memory" quick action then opens AGENTS.md;
  - web-multifile-test's test.sh is updated to check AGENTS.md.
- **ZIP export** includes AGENTS.md, CLAUDE.md and GEMINI.md by default, because they are project docs. The export dialog has an "Agent files" checkbox.
- **Any future web publish or deploy flow** leaves these files out by default. A deployed static site would otherwise serve AGENTS.md publicly.

### 8.5 One builder, many reviewers

- **In the app:**
  - a project has one Builder profile at a time, shown as a "Builder" badge on the model chip;
  - Build and Apply are offered only on that profile; the other profiles get "Review";
  - changing the builder takes one tap and proposes an update to "Builder now" in AGENTS.md.
- **In the terminal:** the working agreement and the "Builder now" line. VY cannot enforce them on the CLIs. The external-change notes and base checks catch collisions.

### 8.6 Second opinion (review packet)

- **How to start:** the reply or change-set menu → "Second opinion…" → pick 1–3 profiles.
- **What each reviewer gets:**
  - STATIC + MEMORY + FILES. These are identical bytes, so they are cached on that provider if it was used recently.
  - A REVIEW tail: the summary (or the last 2 turns), the change-set JSON (small, thanks to edits) and Melody's question.
  - The instruction: "Review in at most 200 words: agree or disagree, concrete problems, concrete fixes. Do not rewrite files. Write each finding as `FINDING [high|med|low] path: text`."
- **Where results go:**
  - collapsed review cards in the source conversation;
  - they enter the builder's context only when Melody taps "Use this review", which adds the selected findings to the next TAIL;
  - each review is stored as a turn in the reviewer profile's conversation.

### 8.7 VY's own source repo (Phase 0, written by hand)

In /root/projects/vy-canis-majoris, write an AGENTS.md of 150 lines or fewer. It contains:
- what VY is;
- the build and test commands: scripts/build-on-android.sh, scripts/compile-check.sh, and scripts/test-core.sh with VY_JSON_JAR;
- a pointer to docs/ARCHITECTURE.md (do not copy it);
- the rules:
  - no keystore or token handling;
  - 0.4.4 scope is F, E and C only;
  - never edit generated or dependency folders;
  - one builder at a time;
- a Handoff section with "Builder now" and claims.

Add CLAUDE.md and GEMINI.md pointer blocks.

### 8.8 Bridge (optional; outside the app)

- **For the coordinating sessions:** one short bridge note for VY that points to AGENTS.md's Handoff section, instead of long multi-revision plan notes.
- **Never** copy keys into bridge notes.

---

## 9. Provider caching and token counting

### 9.1 Anthropic Messages [A1, A2, A3]

**Breakpoints**

| Slot | Placement | TTL |
|---|---|---|
| BP1 | End of MEMORY | 1h |
| BP2 | End of FILES | 1h |
| BP3 | End of SUMMARY, only when it exists | 1h |
| Top-level automatic `cache_control: {"type":"ephemeral"}` | Moves with the conversation | 5m |

- That is 4 of the 4 slots. When SUMMARY is empty, 3 are used.
- The 1h entries come before the 5m entry, as A1 requires.

**Why 1h for the system blocks**
- Phone sessions have 5–60 minute pauses while Melody types or tests the preview. A1 recommends 1h for gaps like that.
- A 1h write costs 2x instead of 1.25x; one reuse after a pause of more than 5 minutes pays for it.
- Keep the TTL in a constant, `ANTHROPIC_SYSTEM_TTL`. Switch to 5m if receipts show mostly back-to-back turns.

**Lookback.** Each turn adds 2 blocks, and the automatic breakpoint writes on every request, so the 20-block lookback is never exceeded.

**Minimum cacheable length**
- 512–4,096 tokens, depending on the model. A shorter segment is silently not cached, and both usage fields read 0.
- The receipt says "below this model's minimum" instead of reporting an error. VY never pads a prompt.

**Things that reset the cache.** Changing tools (VY sends none), thinking settings, or `output_config` effort or format. These are profile settings; changing one starts a new epoch, and the receipt says "settings changed: cache restarts".

**Usage**
- Total input = input_tokens + cache_read_input_tokens + cache_creation_input_tokens.
- When streaming, `message_start` carries the input and cache usage and `message_delta` carries output_tokens.

**Other notes**
- Cache hits are not counted against Anthropic rate limits [A1].
- Pre-warming (max_tokens 0) is not used.

### 9.2 OpenAI [O1, O3, O6; O9, O10, O14 search]

**Caching**
- Prefix caching is automatic from 1,024 tokens. The fixed block order does the work.

**`prompt_cache_key`**
- Value: `"vy-"` + the first 16 hex characters of sha256(projectId + ":" + profileId).
- Send it only when the endpoint host is api.openai.com. Compatible third-party endpoints may reject unknown fields.

**What not to send**
- `prompt_cache_retention`: deprecated.
- `prompt_cache_options` (gpt-5.6 and later): not in Phases 1–5. Phase 6 may add explicit breakpoints at the ends of MEMORY and FILES, if receipts show misses.

**State**
- `store: false`, unless the code relies on `previous_response_id` [Q13].
- Do not adopt `previous_response_id`: earlier input is still billed [O10], and it ties history to one provider.

**Usage**
- Responses: `input_tokens` (includes cached), `input_tokens_details.cached_tokens`, `cache_write_tokens` where present (check its exact location in a recorded response), `output_tokens`.
- Chat Completions: `prompt_tokens`, `prompt_tokens_details.cached_tokens`, `completion_tokens`. When streaming, usage arrives only with `stream_options: {"include_usage": true}`.

**Unverified [search]:** a 1.25x cache-write fee on gpt-5.6 and later, and no fee before 5.6.

### 9.3 Gemini [G1, G3, G5; G6, G8 search]

**gemini-4-argon**
- Implicit caching only, for prompts of 4,096 tokens or more, at a 95% discount on cached input.
- Never call caches.create: explicit caching returns an error on Argon.

**Other Gemini models**
- Implicit caching only in Phases 1–5.
- Explicit caches bill storage per token-hour and work only with the model they were created for [G1, G6 search]. They are an optional Phase 6 item.

**Usage**
- `promptTokenCount` (includes cached tokens), `cachedContentTokenCount`, `candidatesTokenCount`, `thoughtsTokenCount`.

**When there are no hits**
- Implicit caching is best effort.
- No hits on 3 eligible turns puts the profile in cache class None (§7.4): compaction comes earlier, and the meter hints "This model isn't reusing context; compact sooner".

**Thought signatures**
- They matter for function calling [G8 search], and VY sends no tools.
- VY still stores raw model parts and replays them to the same model only.

### 9.4 Compatible endpoints and OpenRouter

- **Default:** the same layout, with no cache fields.
- **OpenRouter with an Anthropic model:** OpenRouter passes Anthropic-style `cache_control` through [R1 search]. Turn it on only when the endpoint host is openrouter.ai and the model id starts with `anthropic/`.
- **Unknown endpoints** start in cache class None until usage shows cached tokens.

### 9.5 Graceful fallback

**Cache hints rejected**
- Applies to a 400 whose error body names `cache_control`, `ttl`, `prompt_cache_key` or `prompt_cache_options`.
- VY retries once without the hints, with the rest of the body unchanged, and saves `cacheHints=off` on the profile.
- The receipt and the Context sheet say so. The profile has a "Retry hints" button.

**No usage fields**
- The caption reads "usage not reported"; the meter keeps the estimate.
- Calibration is skipped, and the profile goes into cache class None.

**Context too long**
- Covers Anthropic "prompt is too long", OpenAI `context_length_exceeded` and Gemini's 400 token-limit error.
- VY shows the over-window dialog and keeps the draft.

### 9.6 Token counting

**Before sending**
- `TokenEstimate = ceil(utf8Bytes / 3.3) × calibration[profile]`.
- Calibration is an exponential moving average (α 0.3) of reported total input divided by the raw estimate, clamped to 0.5–2.0.
- It is stored with the profile metadata, never with keys. It absorbs tokenizer differences, such as the roughly 30% more tokens on Claude 4.7 and later [A3].
- It is always shown with "≈".

**After the reply:** provider-reported values.

| Provider | Total input | Cache read | Cache write | Output | Cut-off |
|---|---|---|---|---|---|
| Anthropic | input + cache read + cache creation | `cache_read_input_tokens` | `cache_creation_input_tokens` (5m/1h split) | `output_tokens` | `stop_reason` max_tokens |
| OpenAI Responses | `input_tokens` | `input_tokens_details.cached_tokens` | `cache_write_tokens` if present | `output_tokens` | status incomplete / max_output_tokens |
| OpenAI Chat | `prompt_tokens` | `prompt_tokens_details.cached_tokens` | `cache_write_tokens` if present | `completion_tokens` | `finish_reason` length |
| Gemini | `promptTokenCount` | `cachedContentTokenCount` | n/a | `candidatesTokenCount` (+ `thoughtsTokenCount`) | `finishReason` MAX_TOKENS |

**"Count exactly"** (Context sheet; on tap only):
- Anthropic `POST /v1/messages/count_tokens`: free, separate rate limits, an estimate, ignores caching [A3].
- OpenAI `POST /responses/input_tokens` [O2].
- Gemini `countTokens` in the REST `generateContentRequest` form, so that systemInstruction is counted [G1, G2].

**Predicted cache state per block:** "warm" when the block is within its TTL and its hash is unchanged. Shown as a dot on each layer.

### 9.7 Capability probe (extends "Profile test")

- The test still must not create a conversation or a working set.
- It records:
  - the endpoint kind;
  - whether usage fields and cache fields appear in the response;
  - the stop-reason field;
  - the model's cache minimum, from a table shipped with the app and marked "verify".
- It shows, for example: "Usage ✓ · Cache fields ✓ · Cache min 4,096".

---

## 10. UI (phone-first: bottom sheets, 48dp touch targets, no horizontal scroll, state survives rotation)

**Header and footer**
- **Header:** "Project conversation · context kept" becomes "Project conversation · epoch 3 · 14 turns (10 summarized)". Tap → Context sheet.
- **Composer footer:** "Brief + chosen files + recent chat" becomes the meter, for example "≈18k / 60k · 3 files · 4 turns · cache warm (41 min)".
  - Amber above 80% of the budget; red above 100%.
  - Tap → Context sheet.

**Working set**
- Chips above the composer: name and KiB. Long-press removes; "+" opens the picker.
- In the picker, refused files are greyed out with the reason: credential, binary, too large, excluded folder or agent file.

**Under each reply**
- One line, for example "In 18.4k (16.1k cached · 2.0k written) · Out 0.6k".
- Variants: "usage not reported"; "cut off at output limit · Retry with more"; "below cache minimum".
- Tap → receipt.

**Cards and dialogs:** Proposed changes (View/Apply/Discard), file-request chip, compaction banner, summary card (Edit/Accept/Reject), over-budget dialog, review cards, AGENTS.md proposal card, Undo outside-change dialog.

**Context sheet** (the existing Context button opens it)
1. Capability line.
2. Layers, in send order, each with ≈tokens, cache state and View/Edit:
   - VY rules vN;
   - Project memory (AGENTS.md sha, epoch) [Open];
   - Project map (n files, collapsed folders);
   - Working set [Manage];
   - Summary [View/Edit];
   - Conversation (turns sent / summarized) [Show];
   - This turn.
3. Never sent: every item with its reason.
4. Last request receipt:
   - provider, endpoint, model;
   - estimate vs reported;
   - cached, written and output tokens;
   - prefix identical yes/no, with the first changed block and the reason (for example "idle 7 min > 5 min TTL", "below minimum", "FILES changed by Build 2");
   - cache hints on/off;
   - stop reason.
5. Buttons: What was sent · Copy receipt · Count exactly · Compact now · Refresh context.

**"What was sent":** the last 5 request bodies, rendered block by block with cache markers. Long blocks are collapsed. Headers are never stored or shown.

**Copy receipt:** counts, paths and hashes only.

**Edit toggle:** keep the label "Let the agent edit this project". Its description, replacing "up to eight", becomes: "The agent sees your working set (5 files, 38 KiB) and the project map, and can ask for more files. Changes arrive as small edits; Undo last build keeps a recovery copy. Shell commands are not run. Never shared: dependency, build-output, dot-config and credential files."

**Menus and settings**
- **Reply menu:** Report response (unchanged), Second opinion…, Compact up to here, Copy.
- **Model chip:** a "Builder" badge on the builder profile; the others show "Reviewer".
- **Editor quick actions:** add "Agent guide" (Phase 2). "Project memory" opens AGENTS.md (Phase 4).
- **Profile settings:**
  - Context budget (default 60k);
  - Max output;
  - Compaction (Ask / Off);
  - Auto-attach small file requests (off);
  - Cache hints status (read-only, with Retry).

---

## 11. Failure handling

| Situation | What VY does |
|---|---|
| Estimate over the budget | Dialog: Compact / Remove files / Send anyway / Cancel. Nothing is trimmed |
| Provider says the context is too long | "Too much context for <model> (≈N tokens). Compact or remove files." The draft is kept |
| 400 naming a cache field | One retry without hints; profile set to `cacheHints=off`; the receipt says so |
| 0 cached tokens | Not an error. The receipt gives the likely reason: first request, below the minimum, TTL passed, or the first changed block. After 3 in a row: cache class None |
| Reply cut off at the output limit | Caption with Retry/Continue. No change set is parsed or applied |
| `find` not found, or matches several places | Nothing written. Per-edit error with match count or closest match; "Ask model to fix" |
| `base` mismatch (file changed in the editor, terminal or by a CLI) | Nothing written. "src/a.js changed since the model saw it. [Refresh working set]" |
| Change to a path outside the working set, or refused by the policy | That change set is rejected with the reason. Creating a new allowed path works |
| Change touches a redacted value | Refused; "edit that line yourself" |
| Undo target changed outside VY | Per-file dialog (§6.4); a recovery copy is kept |
| Compaction call fails, or the summary is rejected | Nothing changes |
| Requested file refused or missing | The chip lists the reason; the next TAIL tells the model |
| AGENTS.md markers damaged | A fresh managed block is appended with a warning. Melody's text is never overwritten |
| AGENTS.md changed by a CLI while a proposal is open | The proposal's base no longer matches; VY shows the conflict side by side |
| Activity recreated, or the app killed mid-request | Existing draft and retry machinery. Stored bodies make the retry byte-identical; the receipt shows "prefix identical: yes" |
| Network loss or 429 | The existing redacted, status-specific errors. At most one retry with backoff for 429/5xx; the draft is kept |
| Provider reports no usage | "usage not reported"; the meter keeps the estimate; calibration skipped |
| Second-opinion profile fails | The error appears in the review card; the source conversation is untouched |

---

## 12. Security and privacy rules

- **Keys** stay in the AndroidKeystore and in HTTPS headers only. They never appear in:
  - prompts, AGENTS.md, receipts or logs;
  - stored bodies, exports or Copy receipt;
  - Report response.
- **`prompt_cache_key`** is a hash of ids. It contains no names or emails.
- **SECRET folders** are never opened for content.
- **Nothing in this design** passes keys into the terminal or runtime environment (PY-SANDBOX).
- **App-private stores** (index, receipts, last-5 bodies, summaries) can be read by code running under the app's UID (PY-SANDBOX). They hold project text, never credentials.

---

## 13. Phased plan (0.4.5 and later)

### 13.0 Rules for every phase

- **Releases:** a phase may share a release with the next phase only if the release gate passes. A phase is never split across releases. No Agents-tab work goes into 0.4.4.
- **Before each phase starts:** commit to the local git repo and copy a source archive off the phone, recording its sha256.
- **New classes:**
  - pure Java 8, with no Android imports where possible;
  - a host runner in scripts/test-core.sh;
  - added to the build script if it lists files [Q14].
- **Old request path:** `USE_CONTEXT_PLAN` keeps it alive for exactly one A/B dev build in Phase 2. Delete it before the release build.
- **End of each phase:** record measured numbers and the new limits in docs/ARCHITECTURE.md.

### 13.1 Release gate (every release from 0.4.5)

| # | Check | Pass |
|---|---|---|
| G1 | scripts/test-core.sh (all suites), scripts/compile-check.sh, APK built with scripts/build-on-android.sh | All pass |
| G2 | Rotate 3 times with the terminal attached and detached; `echo $HOME` | No crash (F); HOME is outside workspaces (E) |
| G3 | `python3 --version`, `python3 -m pip --version`, `node -v`, `npm -v` | 3.14.8, pip prints its version, v24.18.0, 11.16.0; no regression from the previous release |
| G4 | `claude --version`, `codex --version`, `gemini --version` in VY's terminal | Outcomes recorded. A CLI that worked in the previous release still works (CLI-COMPAT) |
| G5 | Preview an HTML project and the React kit sample | Both render offline |
| G6 | Two-file Build, then Undo | Undo restores the baseline sha256 values |
| G7 | Report response | Reaches the worker |
| G8 | Build in ocean with node_modules present | Not refused (C) |
| G9 | One Agents turn on each provider profile | Receipt shows usage, or "usage not reported" |

Any failure blocks the release. Release notes list only behaviour that was tested.

### 13.2 Phone fixture `ctx-test`

In VY, create the project ctx-test and open VY's terminal on it. `pwd` must end in /workspaces/ctx-test.

```sh
mkdir -p src node_modules/pkg .gemini .claude data
i=0; while [ $i -lt 1000 ]; do echo "module.exports=$i" > node_modules/pkg/f$i.js; i=$((i+1)); done
echo '{}' > .gemini/settings.json; echo '{}' > .claude/settings.json
# Fake keys, assembled at run time so this document never contains a literal key pattern.
p1='sk-ant-''api03-'; echo "ANTHROPIC_API_KEY=${p1}TESTTESTTESTTESTTESTTESTTESTTEST" > .env
p2='AI''za'; printf 'export const firebase = { apiKey: "%sSyTESTTESTTESTTESTTESTTESTTESTTEST1" };\n' "$p2" > src/config.js
for f in a b c d e f; do yes "// $f: lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod" | head -n 150 > src/$f.js; done
echo 'export function e(){ return "found-e"; }' >> src/e.js
yes '{"k":"0123456789abcdef0123456789abcdef"},' | head -n 8000 > data/big.json
seq 1 10000 | sed 's/^/log line /' > data/log.txt
printf '<!doctype html><h1 style="color:red">ctx</h1>\n' > index.html
ln -s /root src/link-to-root
sha256sum src/*.js index.html | tee ~/ctx-baseline.sha
ls -l data/big.json
```

- Each src file is about 12 KiB, so three of them come to about 10k tokens. That is above every cache minimum, including Argon's 4,096.
- data/big.json is about 328 KiB, which is over the 256 KiB whole-file limit.
- All keys are fake.

### 13.3 Phases

#### Phase 0: now, no APK (builders in VY's terminal)

**Steps**
1. **Source safety.**
   - Make a tarball of /root/projects/vy-canis-majoris, copy it off the phone, and check its sha256 after the copy.
   - Run `git init` and make a local baseline commit [AS-8]. Its `.gitignore` excludes keystores, `*.jks`, `*.keystore`, `local.properties` and build output.
   - Keys never go into git.
2. **Answer Q1–Q21** in docs/ARCHITECTURE.md, with file:line references.
3. **Hand-write the agent files.** In the VY repo, write AGENTS.md (§8.7) plus the CLAUDE.md and GEMINI.md pointers.
4. **Adopt the one-builder rule** through "Builder now" in AGENTS.md.
5. **Optional bridge note.** A short one pointing to AGENTS.md (§8.8).

**Phone acceptance**
- P0-1: the ARCHITECTURE.md section answers Q1–Q21 with file:line. The archive sha256 matches after the copy. `git log` shows the baseline commit, or the notes record that git is unavailable.
- P0-2: in the VY repo, `claude` then `/memory` lists AGENTS.md through CLAUDE.md.
- P0-3: `gemini` then `/memory show` includes the AGENTS.md text, or the fallback used is recorded.
- P0-4: Codex loads AGENTS.md, or the check is recorded as blocked by CLI-COMPAT.
- P0-5: asked "How do I build and test VY?", each CLI that runs answers from AGENTS.md without running `ls` or `find`. Where available, record each CLI's token use for that question before and after AGENTS.md: Claude Code `/cost`, Codex `/status`, Gemini `/stats`.

#### Phase 1: 0.4.5 "Measure and guard" (the prompt content is unchanged, so the baseline stays honest)

**Build**
- **New classes:** `UsageRecord`, `TokenEstimate`, `AgentLimits`, `SecretScan`, `ProjectIndex`.
- **Usage and errors:**
  - parse usage for Anthropic, OpenAI (Responses or Chat, including the streaming variants) and Gemini;
  - detect stop reasons and map context-length errors.
- **ProjectFilePolicy everywhere:** used by the chosen-files picker, ZIP export and the Build inventory. Reuse or refactor C [Q18].
- **Secret scan:** on outgoing files (redaction) and on user messages (dialog).
- **No silent truncation:** every silent truncation found in Q8/Q19 becomes a visible refusal.
- **UI:**
  - the footer meter, sized by the parts of today's request;
  - the per-reply caption;
  - Context sheet v1 with the receipt, What was sent (last 5 bodies) and Copy receipt;
  - the over-budget dialog.
- **Profile test:** the capability probe.
- **Baseline:** run the 10-turn baseline script on a Claude, an OpenAI and a Gemini profile. Keep the script in ARCHITECTURE.md and record per-turn input, cached, written and output tokens there.

**Host tests:** filepolicy, secretscan, usageparse (recorded fixtures), tokenbudget; all existing suites pass.

**Phone acceptance**

| # | Steps | Pass |
|---|---|---|
| T1 | Build/inventory in ctx-test, and in ocean with node_modules and .gemini restored | No 500-entry refusal. Details shows "node_modules 1,000, .gemini 1, .claude 1 not shared", ".env hidden (1 credential-like)" and "src/link-to-root refused (symlink)". `unzip -l` on the export shows no node_modules, .gemini, .claude or .env |
| T2 | Add src/config.js to the working set and send; try to add .env; type a message containing `sk-ant-api03-TEST…` | What was sent shows `[VY redacted: credential-like text, 39 chars]`. The receipt says "1 value redacted". .env is greyed out (credential name). The message dialog appears. Copy receipt pasted into a file: `grep TESTTEST` finds nothing |
| T3 | Working set a.js, b.js, c.js; send "Say OK." three times | Estimate within ±25% of reported input on turn 1, and within ±10% by turn 3 |
| T4 | Add data/big.json. Then set the budget to 16k with a–c in the set and send | big.json refused, showing its real size against the 256 KiB limit. The over-budget dialog appears. Send anyway gives a reply or a mapped context error. Nothing is trimmed |
| T5 | Baseline script on the 3 providers | Numbers recorded in ARCHITECTURE.md; AS-1..AS-3 confirmed or refuted |

#### Phase 2: 0.4.6 "One cached prefix"

**Build**
- **Layout:**
  - `ContextRenderer` and `ContextPlan` (STATIC, MEMORY, FILES, SUMMARY empty, HISTORY, TAIL);
  - epochs and the TAIL context note and deltas;
  - history stored as sent.
- **Card and agent files:**
  - the `ProjectCard` generator;
  - MEMORY = card + brief + Project memory as stored today + AGENTS.md if it exists;
  - the "Agent guide" quick action writes the AGENTS.md managed block and the CLAUDE.md/GEMINI.md pointers.
- **Working set:**
  - sticky, captured as a snapshot with sha8;
  - raised limits (§5.6).
- **Build and chat share one prefix:**
  - Build uses the working set and the shared prefix; the mode lives only in TAIL;
  - CHAT-mode `vy_build` proposal blocks become drafts that Apply without a second call. Apply uses the existing whole-file path until Phase 3.
- **Provider adapters:**
  - cache hints per provider (§9);
  - automatic fallback when a provider rejects them.
- **History interim:** the stepped window, if Q5 found a sliding window.
- **Checks:** block-hash diagnostics and the device parity self-test.
- **Copy:** the new toggle text.
- **A/B:** `USE_CONTEXT_PLAN` A/B dev build, then delete the old path.

**Host tests:** contextrender golden tests (§4.5); changeproposal (fenced-block parsing); agentsmd (managed block inserted, replaced and preserved; damaged markers).

**Phone acceptance**

| # | Steps | Pass |
|---|---|---|
| T6 | Claude profile, set a–c. Three messages within 3 minutes; wait 10 minutes; send a fourth | Turn 1 writes 9k or more. On turns 2–3, cached is at least 80% of input. Turn 4 has at least the STATIC+MEMORY+FILES size cached (1h), and history is written again |
| T7 | The same on an OpenAI profile and a Gemini Argon profile | OpenAI: cached > 0 on turns 2–3. Gemini: cached > 0 on any of turns 2–4, or cache class None with the hint shown (recorded; not a VY failure) |
| T8 | After T6, add index.html in chat; on the next turn, turn editing on: "make the h1 blue" | The Build receipt says "prefix identical through HISTORY: yes" and cached is at least 80% |
| T9 | Editing off: "Propose making the h1 green" → proposal card → Apply (confirm) | File changed with no extra model request (the receipt count is unchanged). Undo restores the baseline sha |
| T10 | Agent guide quick action, run twice; then `claude` /memory and `gemini` /memory show | Markers present. Text Melody added outside the markers survives the second run. The pointer blocks exist. Both CLIs load AGENTS.md (or the fallback is recorded) |
| T11 | Rotate during a pending reply; kill from Recents mid-request; reopen | No crash; draft and receipt intact; the retry shows "prefix identical: yes" |
| T12 | Debug parity self-test | "parity OK": device block hashes equal the host golden values |
| T13 | The same 10-turn script as T5, on Claude | Price-weighted input at least 50% lower than the Phase 1 baseline, or the actual figure recorded with its reason |

#### Phase 3: 0.4.7 "Edits, not files"

**Build**
- `EditApplier`: the `edit` op, 2-tier matching, base sha8, the 50-edit cap, all-or-nothing.
- Closest-match errors and "Ask model to fix".
- Cut-off rejection.
- The Undo outside-change dialog; a sha re-check under the lock right before writing.
- STATIC version bump: one expected cache miss.

**Host tests:** the editapply suite; extended projectbuildprotocol and projectbuildflow suites (build, edit, preview, Undo, ZIP).

**Phone acceptance**

| # | Steps | Pass |
|---|---|---|
| T14 | Undo T9. Build: "make the h1 blue" | The change set uses `op: edit`, with output under 1,000 tokens. The preview updates. After Undo, `sha256sum` matches ~/ctx-baseline.sha |
| T15 | Editing off: the model proposes a change to a.js. Then run `echo '// x' >> src/a.js` in the terminal and tap Apply | "src/a.js changed since the model saw it"; nothing written; Undo history unchanged |
| T16 | Apply a Build that changes a.js; append to a.js in the terminal; tap Undo last build | The dialog names src/a.js. Skip keeps the terminal edit. Restore anyway keeps a recovery copy |
| T17 | "In src/b.js change lorem to LOREM on one line only" (b.js has 150 identical lines) | A precise "matches 150 places" error; nothing written. "Ask model to fix" gives a valid change set or an explanation; nothing is half-applied |
| T18 | Set max output to 300; BUILD: "create a 200-line file" | "Nothing was changed" message with Retry |

#### Phase 4: 0.4.8 "One memory file, long sessions"

**Build**
- **AGENTS.md becomes the canonical memory:**
  - migration of the brief and Project memory (§8.4);
  - "Project memory" opens AGENTS.md;
  - MEMORY = card + AGENTS.md;
  - in-app AGENTS.md proposals always go to review.
- **Compaction:**
  - cache classes, adaptive thresholds, the cold-cache hint;
  - an editable summary card; Accept starts a new epoch;
  - a Handoff update proposal.
- **History:** remove the stepped window.
- **Tests:** update test.sh.

**Host tests:** projectconversation (stored as sent, epochs, summary ranges, legacy turns); tokenbudget (cache classes and thresholds).

**Phone acceptance**

| # | Steps | Pass |
|---|---|---|
| T19 | Lower the budget until the banner shows (or send 24 short turns) → Compact → edit → Accept | The receipt says "turns 1–N summarized, 4 verbatim". Show reveals the originals. The next request is smaller. A Handoff proposal card appears. The model correctly answers a question about a decision from turn 2 |
| T20 | Migrate memory; then in the terminal ask `claude` "What is the current task and who is the builder?"; repeat with `codex` and `gemini` | Each CLI that runs answers from the Handoff without `ls` or `find`; CLI-COMPAT failures recorded |
| T21 | Mid-conversation, append a decision to AGENTS.md in the terminal; send the next Agents turn; then tap Refresh context | TAIL shows the AGENTS.md diff, and the prefix is identical through HISTORY. After Refresh, MEMORY contains the decision |

#### Phase 5: 0.4.9 "On demand, many agents"

**Build**
- VY-NEED-FILES parsing, the chip, line ranges and the auto-attach setting.
- Second opinion (review packet, review cards, "Use this review").
- Builder and Reviewer roles.
- The profile-switch handoff (§7.5).

**Host tests:** changeproposal (VY-NEED-FILES last-line parsing, ranges, refusals); review packet assembly and FINDING parsing.

**Phone acceptance**

| # | Steps | Pass |
|---|---|---|
| T22 | Working set {a.js}: "Which file defines function e? Ask for it if needed." Then ask for `data/log.txt#L9001-9100` and for `.env` | A chip offers src/e.js; after "Attach and continue", the answer mentions found-e. The range is attached and labelled partial. .env is refused with its reason |
| T23 | On the T14 Build reply, choose Second opinion → Gemini Argon | A review card of 200 words or fewer with FINDING lines. The Gemini receipt shows the change-set JSON in the tail and no extra files. "Use this review" adds the findings to the next TAIL only |
| T24 | Switch Claude → Gemini → Claude mid-task | No API errors. The first request after each switch is uncached and the meter warned about it. The model recalls an earlier decision |
| T25 | Make Claude the builder; open the Gemini profile | Build/Apply replaced by Review. "Builder now" update proposed in AGENTS.md |

#### Phase 6: 0.5.x, optional; each item only if receipts justify it

**Candidate items**
- Native list/read/search tools behind the capability probe.
- OpenAI explicit breakpoints (gpt-5.6 and later).
- Explicit Gemini caches for models other than Argon.
- journal.jsonl with `vy-journal`, and safety snapshots before CLI runs.
- Spend alerts.

**Acceptance:** on the same 10-turn script, each item beats Phase 5's receipts, or it is not shipped.

---

## 14. Migration from the current Agents tab

1. **0.4.4 is untouched,** apart from the recommendation in §5.1.
2. **Existing conversations open unchanged.** The first send in the new version starts epoch 1.
   - The working set is made from the files attached on the last turn that had files (otherwise it is empty).
   - Stored turns that contain inline file contents [Q7] are sent as stored ("legacy"), and a one-time banner suggests Compact.
   - Nothing is deleted.
3. **Build protocol.** The parser accepts `vy_build` 1 and 2. Each STATIC version bump causes one expected cache miss.
4. **Copy.** Remove "up to eight" everywhere. Check that the Play listing does not promise 8 files or 64 KiB.
5. **Memory migration (Phase 4)** is reviewed and undoable; the old store is kept.

---

## 15. Host test suites (scripts/test-core.sh)

| Suite | Covers |
|---|---|
| filepolicy | Containment, symlinks, SECRET/HEAVY/DEFAULT-EXCLUDED, `.vyignore`/`.gitignore` subset and warnings, binary, invalid UTF-8, size limits, the 2,000 count cap, the 50,000/10 s scan stop, validatePath delegation (all current projectchanges assertions still pass) |
| secretscan | Positive and negative cases per pattern; the profile-key hash match; no matched text in any message; the redaction-marker guard |
| contextrender | Golden tests from §4.5; block order; `not sent` lines; card capped at 300 paths; breakpoint placement per provider; empty-block handling; TAIL deltas |
| usageparse | Recorded real responses: Anthropic plain and streaming, OpenAI Responses and Chat (streaming with include_usage), Gemini; stop-reason and context-error mapping |
| tokenbudget | Estimate, calibration and clamping; the over-budget decision; cache classes; compaction thresholds; the cold-cache hint |
| editapply | Single and multiple edits, 0 matches, more than 1 match, the whitespace tier, base mismatch, the 50-edit cap, unchanged result, all-or-nothing, the redaction guard |
| changeproposal | Fenced `vy_build` in CHAT replies; VY-NEED-FILES last-line parsing, ranges and refusals |
| projectconversation | Stored as sent, epochs, summary ranges, legacy turns, manifest per turn, block hashes |
| agentsmd | Managed block insert, replace and preserve; damaged markers append with a warning; secret scan on write; pointer files |

Existing suites must still pass: projectbuildprotocol, projectbuildflow, modelgateway, projectcontext, projectchanges, workspace, storage.

---

## 16. Estimated token savings (model only; Phase 1 replaces it with measurements)

**Assumptions** (from Design A's model; the baseline is unverified)

| Item | Value |
|---|---|
| STATIC | 1,500 tokens |
| MEMORY | 1,000 tokens |
| Working set | 5 files, 40 KiB ≈ 11,000 tokens; cached prefix P ≈ 13,500 |
| Turn | 100 tokens of user text + 600 of reply |
| Session | 20 chat turns, plus Builds after turns 8 and 16, each changing 2 of the 5 files |
| Baseline | Every turn sends brief, files and the last 10 turns, uncached. Each Build re-sends everything and returns 2 whole files (≈4,600 output tokens) |
| Anthropic prices | Read 0.1x (conservative; 0.05x on Opus/Sonnet 5.5), 5m write 1.25x, 1h write 2x [A1] |

**Results**

| Case | Baseline | This design | Change |
|---|---|---|---|
| 20-turn session, Anthropic, price-weighted input | ≈379k | ≈157k | ≈59% lower. Slightly conservative here, because BP1 keeps STATIC+MEMORY cached through file changes |
| A steady turn with no file change | 19,600 | ≈3,135 | ≈84% lower |
| Build output | ≈4,600 (whole files) | ≈400–800 (edits) | ≈85% fewer output tokens per Build |
| OpenAI | | | Probably 55–70% lower, depending on the write fee [search] and the cached-input discount ("up to 90%" [O6]) |
| Gemini Argon, ~80% hits | ≈379k | ≈121k | ≈68% lower |
| Gemini Argon, no hits | | | ≈18% higher than a 10-turn window until cache class None tightens compaction. That is why the class exists |

**Sensitivity**
- A Build every 3 turns: about 35% lower, because each file change rewrites FILES and HISTORY.
- One Build per 10 or more turns: about 75% lower.

**Raw context size goes up** (about 27k at turn 20 instead of 19.6k). The savings come from caching and edits. Compaction bounds the growth. Anthropic does not count cache hits against rate limits [A1].

**Terminal CLIs** (AS-7, not measured)
- A cold session spends 10–40k tokens exploring; AGENTS.md costs about 1.5–3k at start.
- The one-builder rule removes the second and third implementations of the same change. This may be the largest saving, but it depends on behaviour. P0-5 and T20 measure it.

---

## 17. Risks, and what to verify first

1. **The baseline is unknown (AS-1..3).** If VY already sends files once or already caches, the savings are smaller.
   - Mitigation: Phase 1 measures before Phase 2 claims anything.
2. **Silent cache misses from rendering that is not deterministic** (timestamps, Collator ordering, locale-formatted numbers, ChatMarkdown re-normalising history, skill order).
   - Mitigation: golden tests, block hashes, the "prefix identical" line, the device parity self-test.
3. **Full history raises raw tokens where caching does not hit** (Gemini implicit caching, unknown endpoints).
   - Mitigation: cache class None and earlier compaction; the stepped window in the meantime.
4. **Every Build or attach rewrites FILES, SUMMARY and HISTORY.** Frequent tiny Builds cut the saving.
   - Mitigation: the MEMORY breakpoint, the sticky working set, compaction.
5. **The 1h Anthropic writes are wasted if Melody rarely comes back within the hour.**
   - Mitigation: one constant; switch to 5m based on receipts.
6. **Edits will sometimes fail** (non-unique find, JSON escaping, more often with Gemini).
   - Mitigation: precise errors, one-tap fix on a cached prefix, whole-file update for small files, the failure rate in receipts.
7. **Compaction can drop details.**
   - Mitigation: the summary is editable and must be accepted; originals are kept; the last 4 turns stay word for word; decisions go into AGENTS.md.
8. **AGENTS.md risks.** CLIs may ignore the working agreement, break the markers or write secrets; the file can be exported or deployed publicly.
   - Mitigation: append-and-warn on damaged markers, secret scan on VY's writes, an export checkbox, deploy flows excluding it by default.
9. **Unverified CLI behaviour:** Gemini CLI `@` imports, Codex discovery outside git (AS-6), CLI-COMPAT.
   - Mitigation: the Phase 0 checks, the fallbacks in §8.2, the G4 gate.
10. **The FILE-LOCK race with terminal writers.**
    - Mitigation: base checks, a re-check under the lock, Undo's outside-change dialog. It cannot be removed entirely.
11. **The secret scan can miss real secrets or over-redact.** Name rules stay the main defence. There is no override; the fix is to move the key out of the file.
12. **Wrong usage parsing would make every meter and test misleading.**
    - Mitigation: fixtures recorded from real responses on Melody's keys.
13. **Some provider facts are known only from search results, and model names may not be available to Melody's keys.**
    - Mitigation: no prices in the UI; rely on reported usage; the capability probe.
14. **Scope creep:** tool loops, explicit caches, two request paths, Agents work slipping into 0.4.4.
    - Mitigation: phase gates; `USE_CONTEXT_PLAN` deleted after one A/B build; 0.4.4 untouched.
15. **Source safety:** the source is only on the phone, with no git (SOURCE-BACKUP).
    - Mitigation: Phase 0 archive and git before any Phase 1 code; an archive before every phase.
16. **Phone resources:** hashing, walking, the stored bodies and recovery copies cost time, battery and storage.
    - Mitigation: incremental hashing, scan caps, the last-5 body limit, bounded Undo retention.
17. **Test gaps:** the device runner aborts with code 134, so phone tests are manual.
    - Mitigation: host suites for all the logic, the parity self-test, the fixture script.

**Verify in the source before coding:** Q1–Q21 (§3). The most important are:
- Q4/Q5: where files and history go today;
- Q8: Build's capture and truncation;
- Q10: usage parsing;
- Q12: where memory lives;
- Q15: the JSON library;
- Q17: atomic apply and Undo checks;
- Q18: what C shipped.

---

## 18. Questions for Melody (one line each)

1. Which "triple work" costs you most: re-sending every turn, chat and Build both doing the work, or the three CLIs re-learning the project?
2. May the brief and Project memory move into AGENTS.md? CLIs would then read it, and it is included in ZIP export by default.
3. Which agent should be the default builder: Claude Code, Codex/Astra, or an in-app profile?
4. Is a default budget of 60k tokens per request right?

---

## 19. Source keys

- **Anthropic:**
  - A1 prompt caching; A2 pricing; A3 token counting; A4 context editing; A5 compaction; A6 structured outputs; A7 text editor tool; A8 tool search; A9 memory tool;
  - A10 "Effective context engineering" (2025-09-29); A11 Claude Code memory (CLAUDE.md, @imports, under 200 lines); A12 anthropic-sdk-python v2.1.0.
- **OpenAI:**
  - O1–O5 openai-python v3.36.1 (prompt_cache_key/options/retention, input_tokens, usage fields, apply_patch, compact);
  - O6 Prompt Caching 201 cookbook; O7 GPT-5.1 guide; O8 GPT-4.1 guide;
  - O9–O12, O14 developers.openai.com and openai.com [search]; O13 openai/codex (apply_patch.lark, compaction prompt).
- **Gemini:** G1 v1beta discovery (rev 20261020); G2 google-genai v2.32.0; G3 caching cookbook; G4–G10 ai.google.dev / Vertex [search].
- **Other:** R1 OpenRouter prompt caching [search]; P1 Aider docs (edit formats, repo map, caching, unified diffs); P2 Cline context blog [search].
