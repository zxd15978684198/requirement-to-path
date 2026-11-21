<a id="chinese"></a>

# requirement-to-path · 需求 → 对标 → 路径重构

> **从一句模糊需求，走到一条能照着施工的实现路径。**

**简体中文** ｜ [English ↓](#english)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/zxd15978684198/requirement-to-path?style=social)](https://github.com/zxd15978684198/requirement-to-path)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](references/self_check.py)
[![零依赖](https://img.shields.io/badge/dependencies-0-brightgreen)](references/self_check.py)
[![CI](https://github.com/zxd15978684198/requirement-to-path/actions/workflows/ci.yml/badge.svg)](https://github.com/zxd15978684198/requirement-to-path/actions/workflows/ci.yml)

一个给 AI coding agent 用的 **skill**（不是库，不是 CLI）。它把「帮我实现某个模块」这件事拆成五层，每层都有硬门禁，最后交付一份**每步都带通过信号**的施工路径。

---

## 它和「直接问 ChatGPT」差在哪

| 常见的做法 | 这个 skill |
| --- | --- |
| 你只说得出一句话，AI 立刻开始写代码 | **先问清**：3 道门禁产出痛点清单 → 方案决策表 → 需求规格 |
| 丢给你十个 GitHub 链接 | 匹配度矩阵 + **逐仓库**「为什么参考 / 为什么不全抄」 |
| 拿 README 当结论 | **读代码**：`get_file_contents` 看实现，`pull_request_read` 看是否真合并 |
| 「方案看起来是对的」 | 每步三件套：**指令模板 / 通过信号 / 翻车信号** |
| 分不清哪句是猜的 | 每条事实标 `[代码可读]` / `[测试可证]` / `[推断]`，推断必须给验证方法 |

一句话：**它不替你写代码，它给你一条别人已经踩过坑的路。**

---

## 什么时候**不该**用它

诚实地写在最前面，省得你用错：

| 情况 | 该用什么 |
| --- | --- |
| 需求已明确，只想立项开工 | `spec-development` |
| 已有方案，只想压测它站不站得住 | `grill-me` |
| 只想讨论方案，不需要找对标 | 直接聊，别套流程 |
| 需求是**某家公司内部的业务规则** | 开工前就会告诉你不会有开源对标，别耗满搜索轮次 |

---

## 流程

```
L0 澄清（门禁 1–3）→ L1 定位 → L2 提取（读码）→ 门禁 4 裁决 → L3 路径重构 → 交付自检
```

- **L0**：需求方语言提问（禁用方案术语），三道门禁各产出一份可审阅的文档，⚙ 硬阻断
- **L1**：动词短语 + 机制名词构造关键词 → 直搜捞候选 → 分类打标 → 匹配度矩阵 → 代码级验证
- **L2**：入口主流程 → 数据结构 → 接口契约 → 测试文件，四步都记「它没断言什么」
- **门禁 4**：优点照抄 / 能用但需改造 / 缺陷自己补，三分类后逐条裁决
- **L3**：分步路径，每步都要能追溯到「L0 的某条裁决」或「L2 的某段代码」

11 步执行序列见 [`references/pipeline.md`](references/pipeline.md)，主文件见 [`SKILL.md`](SKILL.md)。

---

## 安装

### 前置条件（硬性，不是可选项）

本 skill **强依赖 `github` 连接器**（MCP server）。所有检索与读码都走它的工具：

`search_repositories` · `search_code` · `get_file_contents` · `pull_request_read` · `search_issues`

不自研检索脚本——鉴权托管、限流额度高（未认证直连只有 10 次/分钟）、随官方 server 升级零维护。连接器不可用时会走降级路径，并在交付文档里**显式标注候选质量下降**。

### 把这个连接器配上

需要做到的事只有一件：让你的 agent 能调到上面那 5 个工具。两条路，任选其一。

**A. 用官方托管端点（最省事）**。GitHub 自己有托管的 MCP server，用 PAT 作为 Bearer 鉴权：

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": { "Authorization": "Bearer <你的 PAT>" }
    }
  }
}
```

把这段放进客户端的 MCP 配置即可：Claude Desktop / Cursor 各有自己的配置文件；DSH 走 MCP 连接器面板的「导入 JSON」。

**B. 本地跑官方 server**。

```bash
docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=<你的 PAT> \
  ghcr.io/github/github-mcp-server
```

在客户端里把这条命令注册成 `stdio` 类型的 server。不想用 Docker，也可以从 [`github/github-mcp-server`](https://github.com/github/github-mcp-server) 下二进制。

**PAT 权限按需最小化**。只读公开仓库时，fine-grained token 一个权限都不勾也能用；要读私有仓库，就给对应的那几个仓库 `Contents: Read`。本 skill 全程只读：不写、不开 PR、不发评论。

**接好之后怎么确认**。问一句「你现在能调到哪些 github 工具」，看有没有 `search_repositories`、`search_code`、`get_file_contents`、`pull_request_read`、`search_issues` 这 5 个。

**只暴露了一部分会怎样**。缺 `search_code`：定位阶段退化成只用仓库搜索，候选质量下降；缺 `get_file_contents`：读不到代码，「深读代码提取事实」这一整层失效。这两种情况都会在交付文档里显式标注为降级。

全程不需要 `gh` CLI，也不会调用任何 shell 命令。

### Claude Code

```bash
git clone https://github.com/zxd15978684198/requirement-to-path.git \
  ~/.claude/skills/requirement-to-path
```

之后在会话里说「**帮我实现 XXX**」或「**有没有开源项目可以参考**」即可触发。

### DeepSeek Harness (DSH)

把整个目录放进 `DSH_HOME/skills/requirement-to-path/`，确保 `SKILL.md` 位于该目录根。

### 其他工具（Cursor / Codex / Gemini CLI / 自建 agent）

本 skill **不绑定任何运行时**：全是 Markdown + 一个只依赖标准库的 Python 脚本。把 `SKILL.md` 作为指令文件喂给你的 agent、把 `references/` 放在它能读到的位置即可。

---

## 一次真实调用长什么样

需求方原话只有一句：

> 给内部问答机器人加一层语义缓存——重复或近似的问题别再调模型；但近似但不同的问题不能串答案。

产出物（10 节，约 4 万字符）：

```
0 定位与档位   1 业务叙事   2 决策表 + 依据   3 量级   4 契约
5 对标结论     6 模块全景   7 分步路径        8 验收   9 已知限制
```

完整的端到端样例见 [`examples/full-walkthrough.md`](examples/full-walkthrough.md)。

第 7 节每一行长这样：

| 步骤 | 来源 | 指令模板 | 通过信号 | 翻车信号 |
| --- | --- | --- | --- | --- |
| 加法缓存条目 | `src/cache.py:88` | … | 该测试能从 4 变 8 | 命中率不涨但延迟降 |

**来源格填不出来源的步骤，会被删除**——不允许补一个勉强的出处。

---

## 质量与成本

### 成本

| 项 | 量 |
| --- | --- |
| 首次加载 `SKILL.md` | ≈ 10,000 字符 |
| `references/` | **按层读**，不是一次性全读（L0 前只读题池的 4 节，L1 前只读配方的主链 7 节） |
| 运行时依赖 | 0（Python 标准库 + 你的 MCP 连接器） |

### 可复核的部分

```bash
# SKILL.md 自身一致性：版本对账 / 哨兵位置 / 禁用形态 / 自述项数
python references/self_check.py --skill SKILL.md     # → 0 violations

# 交付物自检：13 项机械检查（来源封闭域、声明唯一、标记与证据配套……）
python references/self_check.py <交付文档.md>       # 退出码 0/1/2/64

# 任务级评测：对真实产出物打分，只判「能机械判的那一半」
python evals/harness.py --case 02 --doc <产出物.md> --root <项目根>
```

| 证据 | 内容 |
| --- | --- |
| 13 项机械自检 | 来源封闭域、声明唯一性、估算数字标记、L3 通过信号可判、引用完整性…… |
| 6 道任务级评测 | [`evals/`](evals/)：语义缓存、状态持久化、模糊平台、超时重试、增量重建、设备派发 |
| 135 条版本账本 | [`references/verification-log.md`](references/verification-log.md)：每次实测的版本、验证方式、覆盖范围、**以及跑不通的分支** |
| CI | [`.github/workflows/ci.yml`](.github/workflows/ci.yml)：在 Python 3.10 与 3.13 上跑自洽检查 + 参考文档检查 + 引用完整性 + 用例校验 |

> **退出码 `0` 只等于「脚本没查到问题」**，不等于交付合格。脚本射程见 [`references/delivery-checklist.md`](references/delivery-checklist.md) §三、§四。这个 skill 对「假绿」有病态般的警惕——账本里记着它自己五次把检查器写成空转的事。

---

## 仓库结构

```
SKILL.md                        主文件：五层流程 + 门禁 + 硬约束（≈10K 字符）
README.md                       你正在读的这份（中文在上，English 在下）
CHANGELOG.md                    只记对外可见的变化
references/
  pipeline.md                   流程图、11 步执行序列
  l0-question-bank.md           L0 题池（按域、按门禁）
  l1-search-recipes.md          L1 检索配方（连接器映射、漏斗、降级）
  l2-extraction-protocol.md     L2 读码协议
  l3-mode-map.md                L3 路径规格（三件套、文档结构、叙事线）
  gate4-adjudication.md         门禁 4 裁决细则
  delivery-checklist.md         交付前自检清单与引用矩阵
  maintainer-notes.md           **改 SKILL.md 前必读**：声明唯一性表 + 维护纪律
  verification-log.md           135 条版本账本（诚实记录，含失败）
  self_check.py                 13 项机械自检（仅标准库）
examples/full-walkthrough.md    端到端产出样例
evals/                          6 道任务级评测 + harness.py
```

---

## 已知限制

1. **强依赖 `github` 连接器** — 未接通时只能走降级路径，候选完整性与排序质量都会下降，且降级结果会在交付文档里显式标注。
2. **搜索轮次硬上限 3 轮** — 满 3 轮必须把已有候选摆给需求方裁决，不允许自行死磕。
3. **「需求方答不出」的分支尚未实测** — 需求方就是项目 owner 时止损规则不会被触发；替不懂技术的别人做需求时要留意。
4. **本 skill 不做代码实现** — L3 产出交给 `spec-development` 之类的执行型 skill。

未验证的分支（🔴 会卡死流程 / 🟡 仅降低质量）逐条记在 [`references/verification-log.md`](references/verification-log.md)。

---

## 参与维护

改 `SKILL.md` 之前**必须**先读 [`references/maintainer-notes.md`](references/maintainer-notes.md)，它写着这个仓库最容易翻车的地方：

- **值只许出现在唯一权威处**——同一个数字写在两处、改一处漏另一处，是本 skill 历次翻车的唯一根因
- 正文不写会随改版变化的值（版本号、区间端点、条数）
- 改完立刻跑 `python references/self_check.py --skill SKILL.md`，并**贴出输出与退出码**
- 判据类改动不执行等于没改（账本里记着 5 次同类事故）

提交 PR 时请说明：改了什么、为什么、以及你**实际跑了哪条命令**。

---

## License

[MIT](LICENSE) © 2026 zxd15978684198

---

<a id="english"></a>

# English · requirement → analogue → reconstruct the path

> **Turn one vague sentence into an implementation path you can build against.**

[简体中文 ↑](#chinese) ｜ **English**

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
README.md                       You are reading this (Chinese on top, English below)
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
