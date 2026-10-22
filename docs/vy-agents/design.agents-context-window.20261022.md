# VY Agents tab: context-window-friendly design, short version

v1, 2026-10-22. Written by claude-code-vy-react-kit-20261019 (cloud) at Melody's request.

**How it was made.** A 9-agent workflow wrote three independent designs (smallest change, most token savings, never lose work). It scored them out of 50: 41, 35 and 33. It took the smallest-change design as the base and grafted in the best ideas from the other two.
- Full spec, about 90 KB, with every rule, JSON example, test and source: GitHub melodydashora/MCP-GPT-AGENT-Manager-, branch ccr-46e71b07-3zobv3, docs/vy-agents/2026-10-22-agents-context-design.md.
- Provider research: docs/vy-agents/2026-10-22-provider-research.md.

**Status: DESIGN ONLY.**
- Targets 0.4.5 and later. 0.4.4 stays F, C and E, per checklist.release-0.4.4.20261022.
- Not checked against the VY source. Answer the section 2 questions first; where the source disagrees, the source wins. Record it in docs/ARCHITECTURE.md.

**Melody's goal.** "the agents tab is more context window friendly for better app development without losing tokens on triple work".

## 1. What "triple work" is, and the fix for each kind

| # | Duplication | Fix |
|---|---|---|
| 1 | Brief, files and recent chat are re-sent at full price on every turn. A sliding window, or files added to the newest message, defeats provider caching | One byte-stable request prefix that the provider caches. Only the newest turn is new |
| 2 | Chat, then Build: Build captures its own files, sends them again, returns whole files, and redoes changes already proposed in chat. In the 0.3.1 phone test, the same 2-file change was generated twice | Chat and Build share the same prefix; the mode is one line in the tail. A change proposed in chat is applied with NO second model call. Small find/replace edits instead of whole files |
| 3 | Claude Code, Codex and Gemini CLI, plus VY's in-app profiles, each rediscover the project and sometimes build the same change | One shared AGENTS.md (card, memory, handoff) read by the tab and all three CLIs. ONE builder at a time; the others review a small change set |

## 2. Phase 0: do it now, no APK (the biggest win for #3)

1. **Source safety.** Do G0 from the checklist first: git baseline, encrypted off-phone archive.
2. **VY's own repo.** In /root/projects/vy-canis-majoris, write an AGENTS.md of 150 lines or fewer:
   - what VY is;
   - build and test commands: scripts/build-on-android.sh, scripts/compile-check.sh, and scripts/test-core.sh with VY_JSON_JAR;
   - a pointer to docs/ARCHITECTURE.md (don't copy it);
   - rules: no keystore or token handling; 0.4.4 scope is F, C and E only; never edit generated or dependency folders;
   - a Handoff section with "Builder now: <one agent>" plus Status and Next steps.
3. **Pointer files.**
   - CLAUDE.md: `@AGENTS.md`. Claude Code supports @-imports.
   - GEMINI.md: the same. If `/memory show` in Gemini CLI doesn't include the AGENTS.md text, set its context file name to AGENTS.md in user settings, or have the file mirror AGENTS.md.
   - Codex reads AGENTS.md natively. Check that it finds the file outside a git repo.
4. **Every agent:** read AGENTS.md first, don't explore excluded folders, update Handoff before stopping, and only "Builder now" edits.
5. **Answer Q1–Q21** in ARCHITECTURE.md under "Agents request layout (as of 0.4.4)", with file:line. The most important:
   - **Q1:** which endpoint each provider uses (OpenAI Responses or Chat Completions, Anthropic Messages, Gemini generateContent), and whether replies stream.
   - **Q3/Q4/Q5:** where the brief, memory, journal and chosen files go each turn, how many chat turns are kept, and whether it's a sliding window.
   - **Q6:** anything that varies above the user message (time, UUIDs, locale numbers).
   - **Q8:** how Build picks files; where 8, 64 KiB and 500 are defined; any silent truncation.
   - **Q9/Q10:** max output tokens and stop-reason checks; whether usage fields are parsed.
   - **Q12:** where the brief and Project memory live. **Q15:** the JSON library (org.json keeps insertion order; the host JSON-java does not).
   - **Q17:** is apply all-or-nothing, and does Undo check current content? **Q19:** where the 60,000-character limit applies.
6. **Phone acceptance.** Ask each CLI "How do I build and test VY?". It should answer from AGENTS.md without running ls or find. Record each CLI's token use before and after: Claude `/cost`, Codex `/status`, Gemini `/stats`.

## 3. Request layout (every request: chat, Build, compaction, review)

Blocks go in this order, most stable first. Only TAIL is new on each turn.

| # | Block | Content | Changes when |
|---|---|---|---|
| 1 | STATIC | VY agent rules vN: role, reply rules, safety, the full change-set protocol (also in chat mode), the VY-NEED-FILES rule, skills sorted by name | App update |
| 2 | MEMORY | Generated project card (kind, run/test commands, file map with line counts, counts of never-shared folders) + AGENTS.md, frozen per epoch | Epoch rebuild |
| 3 | FILES | Working-set files, complete and current, with path, sha8 and bytes, plus `not sent: <path> (<reason>)` lines | A working-set file or the set changes |
| 4 | SUMMARY | Accepted rolling summary of folded turns | Compaction accepted |
| 5 | HISTORY | Turns since the last compaction, exactly as sent and received. Never file contents | Appended each turn |
| 6 | TAIL | `[VY turn N · epoch E · mode CHAT\|BUILD]`, a context note, changes since the epoch started (including a unified diff of AGENTS.md), the last-build line, Melody's message | Every turn |

**Rules**
- Nothing that varies goes above TAIL. That means no clock, dates, UUIDs, device state, absolute paths or locale-formatted numbers.
- File text appears only in FILES.
- History is stored exactly as sent, so a retry is byte-identical.
- An epoch ends when:
  - a conversation starts, or is first opened in a new app version;
  - a compaction is accepted;
  - Melody taps "Refresh context";
  - the profile is switched;
  - pending deltas exceed about 2k tokens.
- Mid-epoch changes go into TAIL as small deltas, so the cached prefix survives.
- **Determinism:**
  - sort with `String.compareTo`; format numbers with `Locale.ROOT`; LF only; send file bytes untouched;
  - store the sha256 of every rendered block per request;
  - the receipt says "prefix identical: yes", or names the first changed block.
- **Tests:** host golden tests, plus a device parity self-test because the device runner aborts with 134.

**Provider mapping**
- **Anthropic:** STATIC, MEMORY, FILES and SUMMARY as system blocks. Breakpoints BP1 (MEMORY end), BP2 (FILES end) and BP3 (SUMMARY end), each with a 1h TTL, plus a top-level automatic 5m breakpoint. That is 4 of the 4 slots.
- **OpenAI Responses:** the same text in `instructions`, history plus TAIL in `input`, `store:false`, and `prompt_cache_key` = "vy-" + 16 hex of sha256(projectId:profileId), sent only to api.openai.com.
- **Gemini:** the blocks as systemInstruction parts. Implicit caching only. Gemini Argon: 4,096 tokens minimum, explicit caches unsupported.
- **Everywhere:** no tools declared in Phases 1–5. Keys stay in headers.

## 4. Files

**ProjectFilePolicy (pure Java)** is the one filter for the inventory, picker, card, export, attaches and secret scan. Build it for fix C in 0.4.4 so it's reused.
- **Containment:** no `..`, no absolute paths, no symlinks.
- **SECRET** (never sent, written or exported; count only): the credential and user-state list in checklist §3 E1.
  - Dot-config folders are never sent to a model and never written by Build.
  - Project agent docs (AGENTS.md, CLAUDE.md, GEMINI.md, .claude/commands) stay in the project and in export.
- **HEAVY** (never walked): node_modules .venv venv __pycache__ site-packages .pytest_cache .gradle.
- **DEFAULT-EXCLUDED:** dist build .next .nuxt .expo .turbo coverage target out .idea .vy. A `.vyignore` can bring a folder back with `!dist/`.
- **Binary** (a NUL byte in the first 8 KiB, or invalid UTF-8): listed, never sent.
- **Ignore files:** a subset of .gitignore and .vyignore, with a warning for unsupported lines.

**ProjectIndex**
- App-private, never exported.
- Per file: path, size, mtime, line count and sha256 (computed lazily, cached by size and mtime).
- Used for change detection and base checks.

**Sticky working set.** The chosen files become a per-conversation set, shown as chips. Each file is sent once per version, never re-attached every turn.

**Limits (AgentLimits)**

| Limit | Today | New |
|---|---|---|
| Inventory | 500 entries incl. node_modules | Shareable only. Scan stops at 50,000 entries or 10 s, and says so |
| Files per request | 8 | Working set of up to 40 |
| Bytes | 64 KiB | Up to 512 KiB set; 256 KiB per whole file; larger only as labelled line ranges (at most 2,000 lines or 96 KiB) |
| Request | none | Budget per profile: 60k default, adjustable from 16k up to the model's window |
| AGENTS.md | n/a | Warn above 200 lines or 24 KiB; never cut |

At any limit: an explicit refusal or a dialog (Compact / Remove files / Send anyway / Cancel). Never silent truncation.

**On-demand reads.**
- The model ends a reply with `VY-NEED-FILES: path1, path2#L1-200` (10 at most).
- VY shows a chip: "[Attach and continue] [Dismiss]".
- Refused paths are listed with their reason.
- No tool loop is needed for any provider.

**Secret scan** on FILES, user messages and AGENTS.md writes:
- Patterns: PEM headers, sk-ant-, sk-proj-, sk-, AIza, ghp_, github_pat_, xox, AKIA, and the hashes of Melody's stored keys.
- A match in a file is redacted in the sent copy as `[VY redacted: credential-like text, N chars]`.
- A match in a message gets a confirm dialog.
- An edit that touches a redaction is refused.

## 5. Edits, Build and Undo

**Change set:** `{"vy_build":2,...}`. The parser accepts v1 and v2.

| Op | Use |
|---|---|
| `edit` | `{"op":"edit","path":...,"base":"<sha8 the model saw>","edits":[{"find":...,"replace":...}]}` for existing files |
| `update` | Whole file. Only for files of 2 KiB or less, or big rewrites |
| `create` | New allowed path |
| `delete`, `rename` | Only if they exist today, and only with Melody's tick |

**EditApplier**
- Checks the path policy, and that `base` equals the sha8 of the working-set snapshot.
- Each `find` must match exactly once. Exact match first; if nothing matches, one whitespace-tolerant tier.
- 50 edits per file at most. All or nothing.
- Writes go through the existing ProjectChangeSet, receipt and Undo path.

**Chat proposals.** With editing off, the model ends with one fenced `vy_build` block, and VY shows "Proposed changes [View] [Apply] [Discard]". Apply makes **no second model call**.

**Errors.**
- Messages the model can fix, e.g. "find matches 3 places (lines 12, 40, 77)", or "not found; closest match lines 40–46".
- One tap on "Ask model to fix". No automatic retries.

**Cut-offs.** Anthropic `stop_reason` max_tokens, OpenAI incomplete/length, Gemini MAX_TOKENS. Nothing is applied; VY offers "Retry with more".

**Undo.** If a file changed after the build (editor, terminal or CLI), VY asks: Skip / Restore anyway (current copy saved) / Cancel. Every write re-checks the sha under the lock, then writes to a temp file and renames it.

## 6. Conversation memory

**Three layers:**
- pinned AGENTS.md (MEMORY);
- an accepted rolling SUMMARY;
- append-only HISTORY.

The Activity journal is never sent.

**Compaction is explicit.**
- **Banner threshold** depends on the measured cache class: HISTORY above 40% of the budget with strong caching, 20% with weak, 12% with none.
- **Cold-cache hint** when the TTL has passed and history is over 6k tokens.
- **What happens:** one call on the same prefix, using a fixed handoff template (Goal, State, Decisions, Constraints, Files touched, Failed attempts, Open questions, Next steps; 600 words at most).
  - Melody edits it and must Accept.
  - The last 4 turns stay word for word, and the originals stay viewable. Nothing is deleted.
  - VY then proposes an update to the AGENTS.md Handoff.
- **No provider-native compaction.** It isn't portable across providers or CLIs.

**Switching profile** starts a new epoch. The new profile gets the same STATIC, MEMORY and FILES, the summary, and the last 4 turns as plain text. A warning comes first: "first request uncached".

## 7. Token visibility (UI)

- **Composer footer.** Replace "Brief + chosen files + recent chat" with a meter, e.g. "≈18k / 60k · 3 files · 4 turns · cache warm". Amber above 80%, red above 100%.
- **Under each reply.** e.g. "In 18.4k (16.1k cached · 2.0k written) · Out 0.6k", or "usage not reported".
- **Context sheet** (the existing Context button):
  - layers in send order, each with ≈tokens and cache state;
  - the never-sent list with reasons;
  - the last receipt, including prefix identical and the first changed block;
  - What was sent (last 5 bodies, no headers), Copy receipt, Count exactly, Compact now, Refresh context.
- **Estimate.** `ceil(utf8Bytes/3.3) × calibration`, an EMA of reported/estimated clamped to 0.5–2.0. "Count exactly" uses Anthropic count_tokens, OpenAI /responses/input_tokens or Gemini countTokens.
- **Profile test** becomes a capability probe: usage fields, cache fields, stop reason, cache minimum.
- **Second opinion.** Pick 1–3 profiles. Each gets the cached prefix plus only the small change set, and replies in 200 words or fewer as FINDING lines. "Use this review" adds the findings to the next TAIL.
- **Builder badge.** One Builder profile per project; the others show Review.
- **Toggle copy.** Replace "up to eight safe project text files" with the working-set size, the project map, and "can ask for more files; changes arrive as small edits".

## 8. Phases and phone acceptance

The full spec has the fixture script `ctx-test` (1,000 node_modules files, fake keys built at run time, a 328 KiB file, a symlink) and tests T1–T25.

**Every release from 0.4.5 passes gate G1–G9 first:**
- G1: all host suites and compile-check pass;
- G2: rotation with no crash, and HOME private;
- G3: python, pip, node and npm versions;
- G4: claude, codex and gemini still work;
- G5: offline preview, including the React kit sample;
- G6: two-file Build plus Undo, with hashes matching;
- G7: Report response;
- G8: ocean Build with node_modules not refused;
- G9: one turn per provider, showing usage.

| Phase | Release | Build | Key phone tests |
|---|---|---|---|
| 0 | none | Section 2 above | CLIs answer from AGENTS.md; token use before and after recorded |
| 1 | 0.4.5 "Measure and guard" | Usage parsing for all providers; stop reasons; ProjectFilePolicy everywhere; secret scan; no silent truncation; meter, receipts, Context sheet v1; capability probe. Prompt content unchanged | Estimate within ±10% by turn 3. Redaction works. 10-turn baseline per provider recorded in ARCHITECTURE.md |
| 2 | 0.4.6 "One cached prefix" | ContextRenderer/ContextPlan, epochs, sticky working set, raised limits, Build shares the prefix, chat proposals applied without a call, provider cache hints with fallback | Claude turns 2–3 at least 80% cached. Build after chat "prefix identical". Apply makes no extra request. Parity self-test OK. 10-turn input at least 50% lower than the baseline |
| 3 | 0.4.7 "Edits, not files" | EditApplier, base checks, closest-match errors, Ask-to-fix, cut-off rejection, Undo outside-change dialog | Build output under 1k tokens. Stale base refused. Ambiguous find refused, nothing half-applied |
| 4 | 0.4.8 "One memory file" | AGENTS.md canonical; memory migration (reviewed, undoable); compaction with cache classes | The model recalls a turn-2 decision after compaction. CLIs answer from Handoff. A terminal edit of AGENTS.md shows as a TAIL diff |
| 5 | 0.4.9 "On demand, many agents" | VY-NEED-FILES chips and ranges, Second opinion, Builder/Reviewer, profile-switch handoff | The model asks for and gets the right file. Review card in 200 words or fewer. Switching providers shows no errors |
| 6 | 0.5.x, optional | Native tools, explicit caches, journal: only if receipts show a win | Must beat Phase 5 on the same script |

**Before each phase:** commit to git, copy an archive off the phone, and keep new classes pure Java 8 with host runners in scripts/test-core.sh. Keep the old request path behind `USE_CONTEXT_PLAN` for one A/B dev build only.

## 9. Expected savings (a model, not a measurement; Phase 1 replaces it)

The assumptions: a 20-turn session, 5 files (40 KiB), and Builds after turns 8 and 16.

| Case | Saving |
|---|---|
| Anthropic, price-weighted input | About 59% lower |
| A steady turn with no file change | About 84% lower |
| Build output (edits instead of whole files) | About 85% lower |
| Gemini Argon with good implicit hits | About 68% lower |
| Gemini Argon with no hits | Up to 18% higher until the "no cache" class compacts sooner |

Terminal CLIs spend about 10–40k tokens exploring a cold project, while AGENTS.md costs about 1.5–3k. The one-builder rule removes the second and third implementations, which may be the biggest saving. Phase 0 measures it.

## 10. Questions for Melody (one line each)

1. Which "triple work" costs you most: re-sending every turn, chat and Build both doing the work, or the three CLIs re-learning the project?
2. May the brief and Project memory move into AGENTS.md? CLIs would read it, and it is included in ZIP export.
3. Which agent should be the default builder: Claude Code, Codex/Astra, or an in-app profile?
4. Is a default budget of 60k tokens per request right?
