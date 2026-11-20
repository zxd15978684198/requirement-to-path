# Changelog

Only user-visible changes are listed here. For the per-version measured ledger — which rule came from which run, and which branches remain unverified — see
[`references/verification-log.md`](references/verification-log.md).

The version number appears exactly once, in the frontmatter of [`SKILL.md`](SKILL.md), and must match the last row of the ledger.

只记**对外可见**的变化。逐版实测账本（每条规则是哪次实测换来的、哪些分支还没验）在
[`references/verification-log.md`](references/verification-log.md)。

版本号只在 [`SKILL.md`](SKILL.md) 的 frontmatter 出现一次，并与账本末行对账。

---

## v1.60.8 — 2026-10-19

**EN.** Fixed an evaluation predicate that was *narrower than the rule it encodes*: `c1_candidates` required wording like "under what condition does it break" near each candidate row, while the rule only asks for "why you referenced it". A predicate stricter than the rule fails compliant output — corrected under the standard "is the predicate narrower than the rule?".
Ledger rows: `v1.60.8`, unverified item `v1.60.8·未验`.

**中文.** 修正一条**判据窄于规则**的评测谓词：`c1_candidates` 原本要求候选行附近同时出现"会在什么条件下坏"的措辞，而规则原文只要求写清"为什么参考"。判据比规则严，会把合规产出判成失败——按"判据是否窄于规则"这条标准改回。
账本对应条目 `v1.60.8`、未验证项 `v1.60.8·未验`。

## Earlier versions / 更早版本

**EN.** See [`references/verification-log.md`](references/verification-log.md) — one row per version: what changed, how it was verified, and where the verification stops.

**中文.** 见 [`references/verification-log.md`](references/verification-log.md)。账本按版本逐行记录：改了什么、怎么验的、验证边界在哪。
