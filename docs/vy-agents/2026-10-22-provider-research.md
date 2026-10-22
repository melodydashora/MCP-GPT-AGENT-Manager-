# Provider caching, token counting and context patterns (research notes)

Gathered 2026-10-22 by a research agent for the VY Agents tab design. Facts marked [search] came from search-engine summaries, because the page itself could not be fetched from the sandbox. Treat every price and model name here as something to confirm with the capability probe and with provider-reported usage. Do not hard-code any of it in the app.

## Prompt and context caching

ACCESS NOTE: Everything below was gathered on 2026-10-22. I read platform.claude.com, code.claude.com, anthropic.com, raw GitHub (the SDKs and cookbooks), and the Gemini API discovery document directly. ai.google.dev, developers.openai.com, openai.com and openrouter.ai could not be reached from this sandbox (DNS failure or egress policy). Facts from those sites come from WebSearch index summaries and are marked [search]. Source keys refer to the "sources" list.

=== ANTHROPIC (A1 prompt-caching page, A2 pricing, A6 structured outputs, A8 tool search, A12 SDK v2.1.0, fetched 2026-10-22) ===
- Two modes. (1) Automatic caching: a top-level "cache_control": {"type":"ephemeral"} puts the breakpoint on the last cacheable block and moves it forward as the conversation grows. It uses 1 of the 4 slots. (2) Explicit breakpoints: cache_control on individual content blocks. Maximum 4 breakpoints. Breakpoints cost nothing; you pay only for writes and reads. [A1]
- TTL is "5m" by default and is refreshed for free on each hit. "1h" is optional: {"type":"ephemeral","ttl":"1h"}. The lifetime counts from the START of the request that writes or reads, so generation time uses it up. With mixed TTLs, 1h entries must come before 5m entries. The page suggests the 1h TTL for gaps of 5 to 60 minutes between requests (for example, a user who may not reply within 5 minutes). It also says cache hits are not deducted from rate limits. [A1]
- Price multipliers on base input: 5m write 1.25x, 1h write 2x, read 0.1x. Exceptions: reads are 0.05x on Opus 5.5 and Sonnet 5.5, and 0.025x on Fable 5.1 and Mythos 5.1. Examples in $/MTok (base / 5m write / 1h write / read): Opus 5.5 4 / 5 / 8 / 0.20; Sonnet 5.5 2 / 2.50 / 4 / 0.10; Sonnet 4.6 3 / 3.75 / 6 / 0.30; Haiku 4.5 1 / 1.25 / 2 / 0.10; Haiku 5.5 (prompts of 100k tokens or less) 0.10 / 0.125 / 0.20 / 0.01. [A1, A2]
- Minimum cacheable length:
  - 512 tokens: Fable 5.1, Mythos 5.1, Opus 5.5, Opus 5, Sonnet 5.5, Fable 5, Mythos 5, Haiku 5.5.
  - 1,024: Opus 4.8, Sonnet 5, Sonnet 4.6, Sonnet 4.5, Opus 4.1, Opus 4, Sonnet 4.
  - 2,048: Mythos Preview, Opus 4.7, Haiku 3.5.
  - 4,096: Opus 4.6, Opus 4.5, Haiku 4.5.
  - Shorter prompts are silently not cached. No error is returned, and both cache usage fields are 0. [A1]
- Prefix order is tools -> system -> messages. A change at one level invalidates that level and everything after it.
  - Changing tool definitions invalidates everything.
  - Toggling web search, citations or speed invalidates system and messages.
  - Changing tool_choice, or adding or removing images, invalidates messages.
  - Changing thinking parameters or output_config.effort invalidates messages. [A1]
  - Changing output_config.format invalidates the prompt cache for that thread. [A6]
- Lookback: each breakpoint checks at most 20 block positions back. If a growing conversation pushes the breakpoint 20 or more blocks past the last write, you need an extra breakpoint. [A1]
- What a hit needs:
  - "Cache hits require 100 percent identical prompt segments." The cache key is a cryptographic hash of the prompt up to the breakpoint.
  - Keep key order in tool_use blocks stable, because "some languages (for example, Swift, Go) randomize key order during JSON conversion, breaking caches."
  - Put the breakpoint on the last block that stays identical across requests, not on a varying one such as a timestamp or the user's input.
  - For concurrent requests, an entry becomes available only after the first response starts.
  - Caches are isolated per workspace on the Claude API and never shared across organizations. [A1]
- Not cacheable directly: thinking blocks (they are cached along with prior assistant turns), sub-content blocks such as citations, and empty text blocks. [A1]
- Usage fields: cache_creation_input_tokens, cache_read_input_tokens, input_tokens (only the tokens after the last breakpoint), and cache_creation.{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}. Total input = read + creation + input_tokens. [A1]
- Pre-warming: max_tokens: 0 writes the cache without generating output. It is not allowed with stream, extended thinking, structured outputs, tool_choice of tool or any, or Batches. [A1]
- Tool search interaction: deferred tools (defer_loading: true) are kept out of the system-prompt prefix, so discovering a tool preserves the cache. A deferred tool cannot also carry cache_control (400 error). [A8]
- Context editing interaction: clear_tool_uses invalidates the cached prefix each time it clears. The docs say to use clear_at_least so each clear removes enough tokens to justify the new cache write. [A4]

=== OPENAI (O1/O3 openai-python v3.36.1 published 2026-10-22, generated from the OpenAPI spec; O6 Prompt Caching 201 cookbook; O9/O14 [search]) ===
- From the cookbook [O6]:
  - Caching is automatic for prompts of 1024 tokens or more, with hits in 128-token increments, and needs an exact repeated prefix match.
  - Requests are routed by a hash of the first ~256 tokens. prompt_cache_key is combined with that hash to make routing stickier.
  - About 15 RPM per prefix+key combination. Beyond that, traffic overflows to other machines, and each new machine is a one-time miss.
  - Claimed savings: input cost down "up to 90%" and time-to-first-token down "up to 80%".
  - Put static content first and volatile content last; even small early changes break the prefix match.
  - Codex CLI keeps system instructions, tool definitions, sandbox config and environment context identical and in the same order between requests.
- From the current API spec [O1]:
  - prompt_cache_key: "Used by OpenAI to cache responses for similar requests to optimize your cache hit rates. Replaces the `user` field."
  - prompt_cache_options, gpt-5.6 and later only:
    - One implicit breakpoint by default. Explicit breakpoints are added with prompt_cache_breakpoint {mode:"explicit"} on input_text, input_image or input_file blocks; the boundary is "not rounded to a token block".
    - Each request can write up to 4 breakpoints. Matching considers up to the latest 80 breakpoints in the conversation, with no content-block lookback limit.
    - mode "implicit" (the default) writes 1 implicit breakpoint plus up to the latest 3 explicit ones. mode "explicit" writes up to the latest 4 explicit ones; with none, the request is not cached.
    - ttl only allows "30m", described as a MINIMUM lifetime that the backend may extend.
    - Also: prewarm (bool) and comparison_response_id (cache diagnostics).
  - prompt_cache_retention ("in_memory" | "24h") is deprecated. Only "24h" is supported for gpt-5.5, gpt-5.5-pro and future models. On older models it defaults to 24h for non-ZDR orgs and in_memory for ZDR orgs.
- Usage fields [O3]: Responses has usage.input_tokens_details.cached_tokens and cache_write_tokens. Chat Completions has prompt_tokens_details.cached_tokens and cache_write_tokens. Admin usage reports have input_cache_write_30m_tokens and input_cache_write_12h_tokens.
- [search O9/O14] For GPT-5.6 and later:
  - The minimum cacheable prefix is 1,024 visible input tokens.
  - Writes cost 1.25x uncached input for 30m. There is reportedly a 12h option at 2.5x in the Responses API (see unverified).
  - Models before 5.6 had no write fee.
  - The 2026-09-22 announcement cites "up to 90%" off cached input.
  - On GPT-5.6 and later, prompt_cache_key is mainly for separate cache accounting.

=== GOOGLE GEMINI (G1 discovery doc rev 20261020; G3 cookbook Caching.ipynb; G4-G6, G9 [search]) ===
- Implicit caching is on by default for Gemini 2.5 and newer. To get hits, put large shared content at the start and the varying question at the end. Check usageMetadata.cachedContentTokenCount. [G4 search]
- gemini-4-argon (GA 2026-10-13 per the changelog [search]) supports implicit caching only, for prompts of 4,096 tokens or more, at a 95% discount on cached input. Explicit caching (cachedContents / caches.create) is not supported and returns an error. Confirmed by the cookbook, fetched directly: "95% discount on repeated input prefixes of 4,096 tokens or more ... does not support explicit cache creation". [G3, G5] Cached-input price is $0.10/M through 2026-11-30 and $0.20 from 2026-12-01. [G5/G6 search]
- Explicit caching:
  - Supported on Gemini 3 and 2.5 models. [G3]
  - A cache "can be only used with model it was created for". contents, tools and systemInstruction are immutable; systemInstruction is text only; ttl is input-only; expireTime is always returned. Use it by setting generateContent cachedContent: "cachedContents/{id}". [G1]
  - The default TTL is 1 hour. [G3; G4 search adds that there is no minimum or maximum]
  - Storage is billed per token-hour. Example: Gemini 3 Flash Preview cached input costs $0.05/M (text, image, video) plus $1.00/M tokens per hour of storage. [G6 search]
- promptTokenCount includes the cached tokens when cached_content is set. [G1]
- Implicit minimums are inconsistent across sources (see unverified). The Interactions API supports implicit caching only. [search]

=== OPENROUTER (R1 [search]) ===
- Passes Anthropic cache_control through: top-level automatic, or up to 4 block breakpoints, with 5m or 1h TTL. OpenAI, DeepSeek and Gemini 2.5 use implicit caching.
- Sticky routing sends later requests to the same provider after a cached request, but only when cache reads are cheaper than normal input. A session_id makes routing sticky right away. A manual provider.order disables it. Stickiness expires after 10 minutes of inactivity (another OpenRouter page says 5).
- Usage fields: prompt_tokens_details.cached_tokens and cache_write_tokens.

## Token counting

ANTHROPIC (A3, fetched 2026-10-22)
- Endpoint: POST https://api.anthropic.com/v1/messages/count_tokens. It takes the same inputs as Messages (system, tools, images, PDFs, thinking) and returns {"input_tokens": N}.
- The count is "an estimate". It is free, with separate RPM limits by tier: Start 5,000, Build 10,000, Scale 20,000. These limits are independent of message-creation limits.
- It does not apply caching logic, even if cache_control is present.
- It returns invalid_request_error for server tools (except the advisor tool), the MCP connector, and image or document blocks with url or file sources. Send base64 instead.
- Claude 4.7 and later (and Mythos Preview) use a newer tokenizer that produces about 30% more tokens. The docs say to count against the model you will actually use.
- With context editing enabled, the response gives input_tokens after clearing and context_management.original_input_tokens before clearing. [A4]
- Tool overhead to add to an estimate, from the pricing page [A2]: the tool-use system prompt is 286 tokens on Opus 5.5 (tool_choice auto/none); 354 (auto/none) / 474 (any/tool) on Sonnet 5; 497/589 on Sonnet 4.6; 496/588 on Haiku 4.5. The text_editor_20250728 tool adds 974 tokens on Claude 4.7 and later, 745 on 4.6 and earlier.

OPENAI (O2, openai-python v3.36.1, 2026-10-22)
- Endpoint: POST /responses/input_tokens (SDK: client.responses.input_tokens.count).
- Accepts model, input, instructions, tools, tool_choice, text (structured output config), reasoning, conversation, previous_response_id, truncation and parallel_tool_calls.
- Returns {object: "response.input_tokens", input_tokens}.
- Guide: developers.openai.com/api/docs/guides/token-counting [search]. Price and rate limits for this endpoint are not verified.
- Related billing fact [O10 search]: with previous_response_id, prior input tokens in the chain are still billed as input. Server-side state saves upload bytes, not tokens.
- Also available: POST /responses/compact [O5], and context_management [{type:"compaction", compact_threshold}] on responses.create [O1].

GEMINI (G1 discovery rev 20261020; G2 google-genai v2.32.0)
- Endpoint: POST v1beta/models/{model}:countTokens.
- The body takes either `contents` or `generateContentRequest`, never both. generateContentRequest includes systemInstruction, tools (function declarations) and cachedContent. [G1]
- Response: totalTokens, cachedContentTokenCount, promptTokensDetails, cacheTokensDetails. "Models may tokenize text differently, so each model may return a different token_count." [G1]
- SDK limitation: google-genai 2.32.0 raises ValueError in Gemini Developer API mode if CountTokensConfig sets system_instruction, tools or generation_config ("only supported in Gemini Enterprise Agent Platform mode"). To count system instructions and tools on the Developer API you have to use the REST generateContentRequest form. [G2]
- After a call, usageMetadata also reports promptTokenCount (includes cached tokens), cachedContentTokenCount, toolUsePromptTokenCount, thoughtsTokenCount and candidatesTokenCount. [G1]
- Whether countTokens is free, and its rate limits, are not verified.

OPENROUTER: no token-counting endpoint was verified.

## Context-management patterns for coding agents

PATTERNS FROM SOURCES (as reported, not recommendations)

1. Repository map instead of full file contents
- Aider sends a "concise map of your whole git repository" with every request: files plus key symbols and their definition lines. [P1 repomap.md]
  - The map is ranked with a graph-ranking algorithm over the file-dependency graph and trimmed to a token budget (--map-tokens, default 1k). It can grow "significantly" when no files are in the chat.
  - The model uses the map to ask for specific files.
- Anthropic's "just-in-time" approach: keep "lightweight identifiers (file paths, stored queries, web links, etc.)" and load data through tools when needed. [A10, published 2025-09-29]
- No authoritative source was found for a hash-based file manifest specifically (see unverified).

2. Tools that fetch files on demand
- Anthropic text editor tool: view supports view_range line ranges and max_characters truncation. Line numbers in view output are described as "essential" for view_range and insert_line. [A7]
- The memory tool's view truncates text over 16,000 characters and supports view_range. [A9]
- Tool search defers tool definitions themselves; the docs cite about 55k tokens of definitions reduced by more than 85%. [A8]

3. Edit formats that cut output tokens, and how reliable they are
- Aider formats [P1 edit-formats.md]:
  - "whole" is simple but "slow and costly" because the entire file is returned.
  - "diff" (SEARCH/REPLACE blocks) is efficient.
  - "diff-fenced" puts the path inside the fence, "primarily used with the Gemini family of models, which often fail to conform to the fencing approach".
  - "udiff" is a simplified unified diff.
  - editor-diff and editor-whole are for architect mode.
- Aider's unified-diff post (2023-12-21) [P1]:
  - On GPT-4 Turbo the laziness benchmark score rose from 20% with SEARCH/REPLACE to 61% with udiff, and lazy-comment tasks fell from 12 to 4.
  - No line numbers are used ("GPT is terrible at working with source code line numbers").
  - Without "high level diff" prompting, editing errors rose 30-50%. With flexible patching disabled, editing errors rose 9X.
- OpenAI GPT-4.1 prompting guide [O8]:
  - Recommends a V4A patch format.
  - "the SEARCH/REPLACE diff format used in Aider's polyglot benchmark, as well as a pseudo-XML format with no internal escaping, both had high success rates."
  - What the effective formats share: "(1) they do not use line numbers, and (2) they provide both the exact code to be replaced, and the exact code with which to replace it".
- OpenAI GPT-5.1 guide [O7]: apply_patch is a built-in tool type; "this implementation uses a freeform function call rather than a JSON format. In testing, the named function decreased apply_patch failure rates by 35%."
- V4A details [O12 search]: 3 lines of context above and below by default, @@ to name a class or function when context is ambiguous, no line numbers.
- Codex CLI grammar [O13, openai/codex at 2026-10-22, apply_patch.lark]: "*** Begin Patch" / "*** Add File:" / "*** Update File:" / "*** Delete File:" / "*** Move to:" / "@@" / lines starting with +, - or space / "*** End of File" / "*** End Patch". The tool description reads "This is a FREEFORM tool, so do not wrap the patch in JSON."
- Anthropic str_replace needs an exact, unique match. [A7]

4. Rolling summaries / compaction
- Anthropic [A4, A5, A12]:
  - Compaction on demand: beta header compact-2026-09-04 with a top-level `compaction` parameter.
  - Compaction at a token threshold: the context_management edit compact_20260112. The SDK default trigger is 150,000 input tokens, with optional `instructions` and `pause_after_compaction`.
  - Context editing (beta header context-management-2025-06-27):
    - clear_tool_uses_20250919 defaults: trigger 100,000 input tokens, keep 3 tool uses, clear_tool_inputs false, plus an optional exclude_tools list.
    - clear_thinking_20251015 must be listed first when both edits are used.
  - The client keeps the full history; the edits happen server-side.
- OpenAI: context_management [{type:"compaction", compact_threshold}] on requests, and POST /responses/compact. [O1, O5]
- Codex compaction prompt [O13]: "CONTEXT CHECKPOINT COMPACTION. Create a handoff summary for another LLM that will resume the task", covering progress and decisions, constraints and preferences, next steps, and critical data.
- Anthropic article [A10]: tool-result clearing is "One of the safest lightest touch forms of compaction". The article also lists structured note-taking and sub-agents with clean context windows.

5. Pinned project memory
- Claude Code [A11]:
  - CLAUDE.md is loaded every session; target is under 200 lines per file.
  - @path imports go at most four hops deep.
  - CLAUDE.md files in subdirectories, and path-scoped .claude/rules, load on demand.
  - Auto-memory MEMORY.md loads its first 200 lines or 25KB.
  - The project-root CLAUDE.md is re-injected after /compact.
- Anthropic memory tool memory_20250818 [A9]:
  - Runs client-side over a /memories directory, with commands view, create, str_replace, insert, delete and rename.
  - The API automatically adds "ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE".
  - It pairs with context editing: Claude gets a warning to save to memory before content is cleared. [A4]
  - Documented multi-session pattern: a progress log, a feature checklist and an end-of-session update.
- Aider's caching layout [P1 caching.md]: it orders the prompt so the system prompt, read-only files, repo map and editable files are cached. `--cache-keepalive-pings N` pings every 5 minutes to keep Anthropic's 5-minute cache warm.

6. Deduplicating repeated file contents / sending only what changed
- Cline replaces earlier reads of the same file with a notice and keeps only the latest version. Its blog says multiple stale copies make "certain LLM models having a harder time identifying correct chunks of the file for editing". [P2, search and secondary sources only]
- Anthropic clear_tool_uses replaces the oldest tool results with placeholder text. [A4]
- OpenAI previous_response_id avoids resending history, but the prior input is still billed. [O10 search]
- No provider-authoritative source was found for "send only files changed since the last turn" (see unverified).

## Tool-calling limits

ANTHROPIC
- Strict tool use / structured outputs [A6]:
  - At most 20 strict tools per request, 24 optional parameters across all strict schemas, and 16 union-type parameters (anyOf or type arrays). Past these, the API may return 400 "Schema is too complex for compilation". Compilation times out at 180 s.
  - Compiled grammars are cached for 24 hours from last use. Changing only a name or description does not invalidate the grammar cache.
  - Not supported: recursive schemas, external $ref, numeric constraints (minimum, maximum, multipleOf), minLength and maxLength, minItems other than 0 or 1, additionalProperties other than false, regex backreferences, lookaround and \b.
  - Behaviour: required properties are emitted first; enum and const casing may change; refusals or max_tokens stops can produce output that does not match the schema.
  - Use output_config.format; output_format is deprecated.
- Tool search [A8]:
  - Up to 10,000 deferred tools per request. Each search returns 5 tools by default (limit 1 to 10,000).
  - Regex patterns are capped at 200 characters and BM25 queries at 500.
  - At least one tool must stay non-deferred.
  - The docs say selection accuracy "degrades once you exceed 30-50 available tools", and recommend tool search when there are 10 or more tools or the definitions exceed 10k tokens.
- Text editor tool [A7]: name str_replace_based_edit_tool, type text_editor_20250728. Commands are view (with view_range [start, end], 1-indexed, -1 for end of file, and an optional max_characters truncation), str_replace (old_str must match exactly, including whitespace), create and insert (insert_line, 0 for start of file). The app should reply with an error when there are 0 or more than 1 matches.
- Thinking: changing thinking parameters invalidates the cache [A1]. On Fable 5.1, Opus 5.5, Sonnet 5.5 and Haiku 5.5, server-side context management never invalidates thinking blocks, but client-side edits to earlier turns can. For new accounts created on or after 2026-08-31, replaying an invalidated block is rejected unless you opt in to dropping it. [A4]

OPENAI (O4/O1 SDK 2026-10-22; O11 [search])
- Function names: a-z, A-Z, 0-9, _ and -, at most 64 characters. strict: true enables a subset of JSON Schema.
- Tool definitions are injected into the system message and billed as input tokens. The docs' mitigations are to load fewer functions up front, shorten descriptions, or use tool search with deferred tools. [O11 search]
- The SDK has defer_loading on function and custom tools, and a tool_search tool (execution: server or client). [O4]
- Custom (freeform) tools accept a grammar format with syntax "lark" or "regex", so input is not JSON-escaped. [O4]
- Built-in apply_patch tool: operations create_file, update_file and delete_file, each with path and diff. Your harness applies the V4A diff and reports failure so the model can recover. [O4, O12 search]
- Strict mode requires all properties to be required plus additionalProperties: false [search, partly verified]. The numeric structured-output limits (property counts, nesting depth, enum sizes) are NOT verified.

GEMINI (G1 discovery rev 20261020; G7, G8 [search])
- FunctionDeclaration.name: a-z, A-Z, 0-9, _, :, . and -, at most 128 characters.
- Parameters are given either as `parameters` (an OpenAPI 3.0.3 subset) or as `parametersJsonSchema` (mutually exclusive).
- FunctionCallingConfig.mode is AUTO (default), ANY, NONE or VALIDATED. allowedFunctionNames applies only with ANY or VALIDATED. [G1]
- responseJsonSchema supports only: $id, $defs, $ref, $anchor, type, format, title, description, enum, items, prefixItems, minItems, maxItems, minimum, maximum, anyOf, oneOf (treated as anyOf), properties, additionalProperties, required, and propertyOrdering. Cyclic refs are unrolled only to a limited degree. responseSchema is marked deprecated in favour of response_format. [G1]
- Guidance [G7 search]: keep the active set at about 10 to 20 tools. Function declarations count toward input tokens. In ANY mode, very large or deeply nested schemas may be rejected.
- Gemini 3 thought signatures [G8 search]: the first functionCall part in each step of the current turn must be sent back with its thoughtSignature, or the request fails with 400. With parallel calls only the first part carries a signature, and parts must come back in exact order (FC1+sig, FC2, FR1, FR2). Keep whole Part objects in history.

## Unverified or conflicting

- Access limitation: ai.google.dev, developers.openai.com, openai.com, openrouter.ai, aider.chat and cline.bot could not be reached from this sandbox. Every fact attributed to them came through WebSearch summaries and has not been read on the page itself.
- OpenAI 12-hour cache TTL: search snippets of the OpenAI guide describe a '12h' option in the Responses API with writes at 2.5x, and admin usage reports have an input_cache_write_12h_tokens field. However, the request parameter prompt_cache_options.ttl in the 2026-10-22 SDK only allows '30m' ('currently the only supported value'). These conflict and are unresolved.
- OpenAI cache-write price of 1.25x (GPT-5.6+, 30m) and 'no write fee before 5.6': search only. Per-model read discounts (for example 0.05x on 'GPT-6.1 Sol') come only from secondary sites.
- OpenAI routing details (hash of the first ~256 tokens, ~15 RPM per prefix+key, 128-token increments) come from the cookbook; search snippets say the current guide calls the hashed length 'varies by model'. For GPT-5.6 and later, prompt_cache_key reportedly matters mainly for cache accounting (search only).
- OpenAI structured-output schema limits (total properties, nesting depth, enum counts) were not found or verified.
- Price and rate limits for OpenAI POST /responses/input_tokens were not verified.
- Gemini implicit-caching minimum tokens per model conflict between sources: 1,024 (older docs), 2,048 (2.5 Flash/Pro), 4,096 (Gemini 3.x and Argon), and 6,144 for some 3.x models in the Vertex/Agent Platform doc. Forum users report the first hits at about 4,192 tokens. Not verified against the live page.
- Gemini implicit-cache discount for models other than Argon: Google's May 2025 blog said 75%; the Vertex doc and the pricing math (for example $0.05 vs $0.50 for Gemini 3 Flash Preview) suggest 90%. Not verified for the Developer API today. Argon's 95% is confirmed by the cookbook fetched directly.
- Gemini explicit-cache minimum token count was not verified (forum reports a 1,024 error; a third party cites 32,768). The default TTL of 1 hour is confirmed by the cookbook; 'no min/max TTL bounds' is search only.
- Whether Gemini countTokens is free, its rate limits, and whether computeTokens is available on the Developer API were not verified.
- Gemini 4 Argon cached-input price ($0.10/M until 2026-11-30, $0.20/M from 2026-12-01) and its GA date of 2026-10-13: search only.
- Gemini implicit caching failing when tools are defined (vercel/ai issue #11513, Gemini 3 Flash) was not checked.
- OpenRouter: all facts are search only, and sticky-routing expiry conflicts (10 minutes vs 5 minutes across OpenRouter pages). No OpenRouter token-counting endpoint was found.
- Cline's duplicate-file-read replacement: secondary sources only (search summaries of the blog, DeepWiki, Medium); exact notice text and trigger not verified in source code.
- 'File manifest with content hashes' and 'send only files changed since the last turn': no provider-authoritative or benchmark source was found. Aider's repo map and Anthropic's just-in-time retrieval are the closest documented patterns.
- Anthropic pricing table leaves the 'any, tool' tool-use overhead blank for Opus 5.5 and Sonnet 5.5; what the blank means was not verified.
- Model names (for example gemini-4-argon, gemini-3.8-flash, gpt-5.6, GPT-6, Claude Opus 5.5) are as they appear in 2026 sources. I could not confirm which of them a particular user's API key can access.

## Sources

- A1 https://platform.claude.com/docs/en/build-with-claude/prompt-caching (fetched 2026-10-22)
- A2 https://platform.claude.com/docs/en/about-claude/pricing (fetched 2026-10-22)
- A3 https://platform.claude.com/docs/en/build-with-claude/token-counting (fetched 2026-10-22)
- A4 https://platform.claude.com/docs/en/build-with-claude/context-editing (fetched 2026-10-22)
- A5 https://platform.claude.com/docs/en/build-with-claude/compaction (fetched 2026-10-22)
- A6 https://platform.claude.com/docs/en/build-with-claude/structured-outputs (fetched 2026-10-22)
- A7 https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool (fetched 2026-10-22)
- A8 https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool (fetched 2026-10-22)
- A9 https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool (fetched 2026-10-22)
- A10 https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents (published 2025-09-29, fetched 2026-10-22)
- A11 https://code.claude.com/docs/en/memory (fetched 2026-10-22)
- A12 https://github.com/anthropics/anthropic-sdk-python commit 9313f13 (2026-10-21), v2.1.0: src/anthropic/types/cache_control_ephemeral_param.py, types/beta/beta_compact_20260112_edit_param.py, types/beta/beta_clear_tool_uses_20250919_edit_param.py
- O1 https://github.com/openai/openai-python commit 7db9d88 (2026-10-22), v3.36.1: src/openai/types/responses/response_create_params.py and src/openai/types/chat/completion_create_params.py (prompt_cache_key, prompt_cache_options, prompt_cache_retention, context_management)
- O2 same repo: src/openai/resources/responses/input_tokens.py (POST /responses/input_tokens)
- O3 same repo: src/openai/types/responses/response_usage.py, src/openai/types/completion_usage.py, src/openai/types/admin/organization/usage_costs_response.py
- O4 same repo: types/responses/apply_patch_tool_param.py, response_apply_patch_tool_call.py, custom_tool_param.py, tool_search_tool_param.py, function_tool_param.py, types/shared_params/function_definition.py
- O5 same repo: src/openai/resources/responses/responses.py compact() -> POST /responses/compact
- O6 https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/Prompt_Caching_201.ipynb (fetched 2026-10-22)
- O7 https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/gpt-5/gpt-5-1_prompting_guide.ipynb (fetched 2026-10-22)
- O8 https://raw.githubusercontent.com/openai/openai-cookbook/main/examples/gpt4-1_prompting_guide.ipynb (fetched 2026-10-22)
- O9 https://developers.openai.com/api/docs/guides/prompt-caching (not fetchable from sandbox; WebSearch index 2026-10-22)
- O10 https://developers.openai.com/api/docs/guides/conversation-state (WebSearch index 2026-10-22)
- O11 https://developers.openai.com/api/docs/guides/function-calling (WebSearch index 2026-10-22)
- O12 https://developers.openai.com/api/docs/guides/tools-apply-patch (WebSearch index 2026-10-22)
- O13 https://github.com/openai/codex (HEAD 2026-10-22): codex-rs/core/assets/tools/apply_patch.lark, codex-rs/core/src/tools/handlers/apply_patch_spec.rs, codex-rs/prompts/templates/compact/prompt.md
- O14 https://openai.com/index/better-prompt-caching-for-gpt-6/ (WebSearch index; secondary coverage dated 2026-09-22/23)
- G1 https://generativelanguage.googleapis.com/$discovery/rest?version=v1beta (revision 20261020, fetched 2026-10-22)
- G2 https://github.com/googleapis/python-genai commit c97ae02 (2026-10-21), v2.32.0: google/genai/types.py, google/genai/models.py (_CountTokensConfig_to_mldev)
- G3 https://raw.githubusercontent.com/google-gemini/cookbook/main/quickstarts/Caching.ipynb (fetched 2026-10-22)
- G4 https://ai.google.dev/gemini-api/docs/caching (WebSearch index 2026-10-22; not directly fetchable)
- G5 https://ai.google.dev/gemini-api/docs/models/gemini-4-argon and https://ai.google.dev/gemini-api/docs/latest-model (WebSearch index 2026-10-22)
- G6 https://ai.google.dev/gemini-api/docs/pricing (WebSearch index 2026-10-22)
- G7 https://ai.google.dev/gemini-api/docs/function-calling (WebSearch index 2026-10-22)
- G8 https://ai.google.dev/gemini-api/docs/generate-content/thought-signatures (WebSearch index 2026-10-22)
- G9 https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/context-cache/context-cache-overview (WebSearch index 2026-10-22)
- G10 https://ai.google.dev/gemini-api/docs/tokens (WebSearch index 2026-10-22)
- R1 https://openrouter.ai/docs/guides/best-practices/prompt-caching (WebSearch index 2026-10-22)
- P1 https://github.com/Aider-AI/aider (HEAD 2026-05-22): aider/website/docs/more/edit-formats.md, docs/repomap.md, docs/usage/caching.md, _posts/2023-12-21-unified-diffs.md
- P2 https://cline.bot/blog/inside-clines-framework-for-optimizing-context-maintaining-narrative-integrity-and-enabling-smarter-ai (WebSearch index only; plus secondary DeepWiki/Medium summaries)
