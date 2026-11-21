# requirement-to-path · requirement → analogue → reconstruct the path

> **Turn one vague sentence into an implementation path you can build against.**

[English](README.md) ｜ [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/zxd15978684198/requirement-to-path?style=social)](https://github.com/zxd15978684198/requirement-to-path)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](references/self_check.py)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen)](references/self_check.py)
[![CI](https://github.com/zxd15978684198/requirement-to-path/actions/workflows/ci.yml/badge.svg)](https://github.com/zxd15978684198/requirement-to-path/actions/workflows/ci.yml)

A **skill** for AI coding agents — not a library, not a CLI. It splits "build me this module" into five layers, each behind a hard gate, and ends with an implementation path where **every step carries a pass signal**.

> **Language note.** The skill's own instructions — [`SKILL.md`](SKILL.md) and everything under [`references/`](references/) — are written in Chinese, and so are its trigger phrases. This English README exists so you can judge whether the project is worth reading before you open those files.

---

## How it differs from "just ask a model"

| The usual thing | This skill |
| --- | --- |
| You can manage one sentence, the model starts writing code | **It asks first**: three gates produce a pain-point list → a decision table → a requirement spec |
| It dumps ten GitHub links on you | A match matrix plus, per repo, "why reference it / why not copy it wholesale" |
| It treats a README as evidence | **It reads the code**: `get_file_contents` for the real implementation, `pull_request_read` to check a claim was actually merged |
| "The plan looks right" | Every step ships as a triple: **instruction template / pass signal / failure signal** |
| Guesswork is indistinguishable from fact | Each fact is tagged `[code-readable]` / `[test-provable]` / `[inference]`, and an inference must come with a way to verify it |

In one line: **it doesn't write the code for you — it hands you a path someone else already walked, potholes included.**

---

## When **not** to use it

Written up front so you don't reach for the wrong tool:

| Situation | Use instead |
| --- | --- |
| Requirements are settled; you just want to start building | `spec-development` |
| You have a plan; you want it stress-tested | `grill-me` |
| You only want to discuss a plan; no analogue needed | Just talk — don't run the pipeline |
| The requirement is **one company's internal business rule** | It will tell you there's no open-source analogue before you burn search rounds |

(The two alternatives named above are separate skills in the author's own setup — substitute whatever plays that role in yours.)

---

## Pipeline

```
L0 clarify (gates 1–3) → L1 locate → L2 extract (read the code) → gate 4 adjudicate → L3 reconstruct the path → self-check before delivery
```

- **L0** — questions phrased in the requester's language (solution jargon banned); each of three gates emits a reviewable document, and ⚙ blocks hard
- **L1** — verb phrase + mechanism noun build the keywords → direct search harvests candidates → classify and tag → match matrix → code-level verification
- **L2** — entry point and main flow → data structures → interface contracts → test files; at every step it records "what this does *not* assert"
- **Gate 4** — copy the strength / usable but needs rework / defect you must fix yourself: three buckets, adjudicated line by line
- **L3** — a step-by-step path where every step traces back to "a decision from L0" or "a piece of code from L2"

The 11-step execution sequence lives in [`references/pipeline.md`](references/pipeline.md); the main file is [`SKILL.md`](SKILL.md).

---

## Install

### Prerequisite (hard, not optional)

This skill **hard-depends on the `github` connector** (an MCP server). All discovery and code reading go through its tools:

`search_repositories` · `search_code` · `get_file_contents` · `pull_request_read` · `search_issues`

It does not roll its own search script — auth is managed for you, the rate-limit budget is far higher (unauthenticated direct calls get 10 requests a minute), and it costs nothing to maintain as the official server evolves. If the connector is unavailable the skill falls back to a degraded path and **flags the drop in candidate quality** in the delivered document.

### Wiring up the `github` connector

All the skill needs is for your agent to reach those five tools. Two ways, pick either.

**A. Hosted endpoint — least setup.** GitHub runs a hosted MCP server; authenticate with a PAT:

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer <your PAT>" }
    }
  }
}
```

Paste that into your client's MCP configuration: Claude Desktop and Cursor use their own config file, and DSH accepts it through the connectors panel's "import JSON".

**B. Run the official server locally.**

```bash
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=<your PAT> \
  ghcr.io/github/github-mcp-server
```

Register that as a `stdio` server in your client. No Docker? Take a binary from [`github/github-mcp-server`](https://github.com/github/github-mcp-server).

**Token scope — keep it minimal.** For public repositories only, a fine-grained token needs no permissions at all. To read private repositories, grant `Contents: Read` on just those repositories. This skill never writes, never opens pull requests, never comments.

**Verify it took.** Ask your agent which `github` tools it can reach. You should see `search_repositories`, `search_code`, `get_file_contents`, `pull_request_read`, `search_issues`.

**If only some of the tools are exposed:** without `search_code` the discovery stage falls back to repository search and candidate quality drops; without `get_file_contents` the code-reading stage cannot run at all. Both cases are flagged as degraded inside the delivered document.

No `gh` CLI and no shell commands are involved at any point.

### Claude Code

```bash
git clone https://github.com/zxd15978684198/requirement-to-path.git \
  ~/.claude/skills/requirement-to-path
```

Then say "**help me build XXX**" or "**is there an open-source project I can reference?**" in a session to trigger it.

### DeepSeek Harness (DSH)

Drop the whole directory at `DSH_HOME/skills/requirement-to-path/`, keeping `SKILL.md` at the root of that directory.

### Any other tool (Cursor / Codex / Gemini CLI / your own agent)

This skill **is not tied to any runtime**: it is Markdown plus one Python script that uses only the standard library. Feed `SKILL.md` to your agent as an instruction file and put `references/` somewhere it can read.

---

## What a real run looks like

The requester's entire brief was one sentence:

> Add a semantic cache layer to our internal QA bot — stop calling the model for repeated or near-duplicate questions; but near-duplicates that mean different things must not cross answers.

The deliverable (10 sections, roughly 40,000 characters):

```
0 framing and mode   1 business narrative   2 decision table + rationale   3 scale
4 contracts          5 analogue verdict     6 module landscape             7 step-by-step path
8 acceptance         9 known limitations
```

A full end-to-end sample is in [`examples/full-walkthrough.md`](examples/full-walkthrough.md).

Each row of section 7 looks like this:

| Step | Source | Instruction template | Pass signal | Failure signal |
| --- | --- | --- | --- | --- |
| Add the cache entry | `src/cache.py:88` | … | that test goes from 4 to 8 | hit rate flat but latency drops |

**A step whose Source cell cannot be filled in gets deleted** — no padding it with a plausible-looking citation.

---

## Quality and cost

### Cost

| Item | Amount |
| --- | --- |
| First load of `SKILL.md` | ≈ 10,000 characters |
| `references/` | **Read layer by layer**, never all at once (before L0 only 4 sections of the question bank; before L1 only the 7-section main chain of the recipes) |
| Runtime dependencies | 0 (Python standard library + your MCP connector) |

### What you can re-run yourself

```bash
# SKILL.md internal consistency: version reconciliation / sentinel positions / banned shapes / self-declared item count
python references/self_check.py --skill SKILL.md     # → 0 violations

# Deliverable self-check: 13 mechanical checks (closed source domain, claim uniqueness, tag/evidence pairing, …)
python references/self_check.py <deliverable.md>     # exit 0/1/2/64

# Task-level evaluation: scores a real deliverable, judging only the half a machine can judge
python evals/harness.py --case 02 --doc <deliverable.md> --root <project root>
```

| Evidence | What it is |
| --- | --- |
| 13 mechanical self-checks | Closed source domain, claim uniqueness, estimates marked as estimates, L3 pass signals must be decidable, reference integrity… |
| 6 task-level evaluations | [`evals/`](evals/): semantic caching, state persistence, vague platform, timeout-retry, incremental rebuild, device dispatch |
| A 135-row version ledger | [`references/verification-log.md`](references/verification-log.md): every measured run's version, how it was verified, what it covered — **and which branches still fail** |
| CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml): on every push, self-consistency + reference-doc checks + reference integrity + eval-case validation |

> **Exit code `0` only means "the script found nothing wrong"** — it does not mean the deliverable is good. The script's actual reach is documented in [`references/delivery-checklist.md`](references/delivery-checklist.md) §3–§4. This skill is pathologically wary of false green: the ledger records five separate occasions where it wrote a checker that silently checked nothing.

---

## Repository layout

```
SKILL.md                        Main file: five-layer pipeline + gates + hard constraints (≈10K characters)
README.md                       You are reading this (English)
README.zh-CN.md                 Chinese version
CHANGELOG.md                    User-visible changes only
references/
  pipeline.md                   Flow diagram, 11-step execution sequence
  l0-question-bank.md           L0 question bank (by domain, by gate)
  l1-search-recipes.md          L1 search recipes (connector mapping, funnel, degradation)
  l2-extraction-protocol.md     L2 code-reading protocol
  l3-mode-map.md                L3 path spec (the triple, document structure, narrative line)
  gate4-adjudication.md         Gate-4 adjudication rules
  delivery-checklist.md         Pre-delivery checklist and reference matrix
  maintainer-notes.md           **Read before editing SKILL.md**: claim-uniqueness table + maintenance discipline
  verification-log.md           135-row version ledger (honest, failures included)
  self_check.py                 13 mechanical self-checks (stdlib only)
examples/full-walkthrough.md    End-to-end sample deliverable
evals/                          6 task-level evaluations + harness.py
```

---

## Known limitations

1. **Hard dependency on the `github` connector** — without it only the degraded path runs; candidate coverage and ranking both drop, and the delivered document says so explicitly.
2. **Hard cap of 3 search rounds** — at three rounds it must put the candidates it has in front of the requester, not keep grinding on its own.
3. **The "requester can't answer" branch is untested** — the stop-loss rules never fire when the requester owns the project; be careful when running requirements for a non-technical third party.
4. **This skill does not implement code** — L3 output is handed to an execution-oriented skill such as `spec-development`.

Unverified branches (🔴 blocks the flow / 🟡 degrades quality only) are listed one by one in [`references/verification-log.md`](references/verification-log.md).

---

## Contributing

Before editing `SKILL.md` you **must** read [`references/maintainer-notes.md`](references/maintainer-notes.md). It documents the places this repository fails most often:

- **A value may live in exactly one authoritative place** — the same number written twice and one copy updated is the single root cause behind every past regression here
- Don't put values that move between releases (version numbers, interval endpoints, counts) in the body text
- After any change, run `python references/self_check.py --skill SKILL.md` right away and **paste the output and exit code**
- A change to a predicate that is never executed is not a change (the ledger records five incidents of exactly this)

In a PR, say what you changed, why, and **which command you actually ran**.

---

## License

[MIT](LICENSE) © 2026 zxd15978684198
