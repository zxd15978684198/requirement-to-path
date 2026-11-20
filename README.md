# requirement-to-path

> From one vague requirement → find a **whole, matching module** on GitHub → read the code, extract facts, rule on trade-offs → reverse-engineer a **step-by-step path you can actually build from**.

> 一句模糊需求 → 找到 GitHub 上**整块匹配**的成熟模块 → 读码提取事实、裁决优缺点 → 反推一条**能照着施工**的分步路径。

A **skill package** for coding agents: plain Markdown instructions plus two Python checkers. Not bound to any model or framework.
一个给 coding agent 用的 **skill 包**：纯 Markdown 指令 + 两个 Python 校验脚本，不绑定任何模型或框架。

---

## English

### Why it exists

It targets the three mistakes that show up in almost every "just find an open-source project for me" run:

1. **Searching before clarifying** — the requirement is still vague, so keyword hits have nothing to do with the real pain point.
2. **Copying whatever runs** — no code reading, no boundary checks, so someone else's constraints get adopted as your own.
3. **Passing `[inference]` off as `[measured]`** — facts and guesses share one table, and the deliverable only *looks* right.

Hence **four hard gates**: Gate 1 pain-point list → Gate 2 option decision table → Gate 3 requirement spec → Gate 4 benchmark adjudication. No gate, no next layer.

### What a run looks like

```
applicability check
  → Gate 1 (pain points, each tagged [assumption])
  → L1.0 connect the github connector
  → L1 half-run (find candidate approaches)
  → Gate 2 (approach A vs approach B — pick one)
  → Gate 3 (scope: what to build, what explicitly not, acceptance criteria)
  → L1 full run (find the final benchmark module)
  → L2 code reading (every fact carries file:line / test function / [inference]+how to verify)
  → Gate 4 (per-repo adjudication: why reference it, why not copy it wholesale)
  → L3 step-by-step path (three-part deliverable + copy-pasteable prompt templates)
  → pre-delivery self-check (must run self_check.py; paste output and exit code)
```

End-to-end output shape: [`examples/full-walkthrough.md`](examples/full-walkthrough.md).

### Install

A skill is just a directory; copy it into the agent's skills directory.

**DSH (DeepSeek Harness)**

```bash
git clone <this-repo> requirement-to-path
cp -r requirement-to-path ~/.dsh/skills/          # Windows: %USERPROFILE%\.dsh\skills\
```

**Claude Code / other agents that support skills**: copy into their skills directory (e.g. `~/.claude/skills/`), or reference `SKILL.md` as a project instruction file.

**Prerequisite**: the `github` connector (MCP tools). It still runs without it, but falls back to a degraded path — candidate coverage and ranking both drop, and the degradation must be stated explicitly in the deliverable.

### When to trigger it

Say something like:

> implement feature/module X ｜ is there an open-source project to reference ｜ how do others build this module ｜ the requirement is vague, I want a concrete plan

Not for: requirements already clear and you just want to start (`spec-development`), or you have a plan and want it stress-tested (`grill-me`).

### Pre-delivery self-check

```bash
python references/self_check.py <deliverable.md>    # 13 mechanical checks + 1 advisory
python references/self_check.py --skill SKILL.md     # the skill itself: single-source declarations, authoritative anchors reachable, in sync with the ledger
```

Exit code `0` **only** means "no mechanical violation found" — it is not proof the acceptance checklist was completed, and `--skill` is not proof of capability.

### Evaluations

`evals/` holds 6 task-level cases (semantic cache / state persistence / vague platform ask / timeout-retry / incremental rebuild / device dispatch), each as `skill + query + files + expected_behavior`.

```bash
python evals/harness.py --case 02 --doc <deliverable.md> --root <project-root>
```

`harness.py` does not evaluate an agent (that needs a clean session). It turns the mechanically checkable part of `expected_behavior` into predicates, scores one real deliverable, and quotes the deliverable as evidence; anything it cannot judge is marked "manual" rather than passed.

**A mechanical score is necessary, not sufficient** — always record the score together with the command; the same score may not reproduce under a different `--root`.

### Layout

```
SKILL.md                       # main file: flow, four gates, hard constraints, resources
references/
  l0-question-bank.md          # how to ask at gates 1–3
  l1-search-recipes.md         # GitHub search recipes, fallbacks, round cap
  l2-extraction-protocol.md    # labeling protocol for facts extracted from code
  l3-mode-map.md               # deliverable mode rules, three-part spec
  gate4-adjudication.md        # Gate 4 adjudication, unreachable-requester forms
  delivery-checklist.md        # pre-delivery checklist, cross-reference matrix
  pipeline.md                  # flow chart and the 11-step execution order
  self_check.py                # mechanical self-check
  verification-log.md          # per-version measured ledger (honest: which rule came from which run)
  maintainer-notes.md          # read before editing SKILL.md
evals/                         # 6 task-level cases + harness.py
examples/full-walkthrough.md   # end-to-end sample deliverable
```

### Known limits

- **Hard dependency on the `github` connector**; without it only the degraded path runs.
- **Search rounds are capped at 3**; at 3 you must hand the candidates to the user, not keep digging.
- **The "user can't answer" branch is untested**; when the requester is unreachable, follow the degraded form and say so.
- **This skill does not write code**: L3 output goes to an implementation skill.
- The development harness (`.eval/` blind runs, `blind/` records, private fixtures) is **not published**; references to it in `references/verification-log.md` are for provenance only.

Full untested branches and measured coverage live in [`references/verification-log.md`](references/verification-log.md) — **design ≠ verification**.

### Contributing

Read [`references/maintainer-notes.md`](references/maintainer-notes.md) before editing `SKILL.md` (declaration-uniqueness table + two maintenance rules), then run `python references/self_check.py --skill SKILL.md`. The version number appears exactly once, in the frontmatter, and must match the last row of the ledger.

### License

MIT — see [LICENSE](LICENSE).

---

## 中文

### 为什么有它

它针对"帮我找个开源项目"这类任务里几乎必然出现的三个错：

1. **没澄清就开搜** —— 需求还模糊，直接去 GitHub 找关键词，找到的东西和真实痛点没关系。
2. **找到能跑的就照抄** —— 不读代码、不判边界，把别人项目的约束当成自己的。
3. **把 `[推断]` 写成 `[实测]`** —— 事实与猜测混在一张表里，交付时"看起来对"。

对应地它有**四道硬门禁**：门禁 1 痛点清单 → 门禁 2 方案决策表 → 门禁 3 需求规格 → 门禁 4 对标裁决。未放行不得进入下一层。

### 它跑一遍是什么样

```
适用性判断
  → 门禁 1（痛点清单，每条带 [假设]）
  → L1.0 接通 github 连接器
  → L1 半程（找候选做法）
  → 门禁 2（A 做法 vs B 做法，选哪个）
  → 门禁 3（需求规格：做什么、明确不做什么、验收标准）
  → L1 全程（找最终对标模块）
  → L2 读码提取（每条事实带 文件:行 / 测试函数 / [推断]+验证方法）
  → 门禁 4（逐仓库裁决：为什么参考、为什么不全抄）
  → L3 分步路径（三件套 + 可复制的提示词模板）
  → 交付前自检（必跑 self_check.py，贴输出与退出码）
```

端到端产出形态见 [`examples/full-walkthrough.md`](examples/full-walkthrough.md)。

### 安装

skill 就是一个目录，整个拷进 agent 的 skills 目录即可。

**DSH（DeepSeek Harness）**

```bash
git clone <this-repo> requirement-to-path
cp -r requirement-to-path ~/.dsh/skills/          # Windows: %USERPROFILE%\.dsh\skills\
```

**Claude Code / 其他支持 skills 的 agent**：拷进各自的 skills 目录（如 `~/.claude/skills/`），或把 `SKILL.md` 作为项目指令文件引用。

**前置条件**：`github` 连接器（MCP 工具）。没有它也能跑，但会走降级路径，候选完整性与排序都会下降，且降级结果必须在交付文档里显式标注。

### 怎么触发

说出下面这类话即可：

> 帮我实现某个功能/模块 ｜ 有没有开源项目可以参考 ｜ 别人是怎么做这个模块的 ｜ 需求很模糊想落地成方案

反面：需求已经很明确只想开工（用 `spec-development`）、已有方案只想压测（用 `grill-me`）—— 这两种**不该**用它。

### 交付前自检

```bash
python references/self_check.py <交付文档.md>      # 十三项机械检查 + 一项提示项
python references/self_check.py --skill SKILL.md    # skill 自身：声明唯一、权威位置可达、与账本同步
```

退出码 `0` **只等于「机械项没查出问题」**，不等于验收清单打勾完毕。`--skill` 也不是能力证明。

Windows／PowerShell 两个坑：控制台默认 GBK，先 `$env:PYTHONIOENCODING="utf-8"`；别用内联 `python -c "多行代码"`（反引号会被当转义符）。

### 评测

`evals/` 有 6 条任务级用例（语义缓存 / 状态持久化 / 模糊平台需求 / 超时重试 / 增量重建 / 设备调度），格式为 `skill + query + files + expected_behavior`。

```bash
python evals/harness.py --case 02 --doc <产出物.md> --root <项目根>
```

`harness.py` 不评测 agent（那需要起干净会话），它把 `expected_behavior` 里**能机械判的部分**变成谓词，对一份真实产出物打分，并引用产出原文当证据；判不了的条目标「人工」，不冒充通过。

**机械分是必要条件，不是充分条件**，分数必须连命令一起记 —— 同一个分数换 `--root` 就可能复现不出来。

### 目录结构

```
SKILL.md                       # 主文件：流程、四道门禁、硬约束、资源清单
references/
  l0-question-bank.md          # 门禁 1–3 的提问方式与选项设计
  l1-search-recipes.md         # GitHub 检索配方、降级路径、轮次上限
  l2-extraction-protocol.md    # 读码取事实的标注协议
  l3-mode-map.md               # 交付物模式判据、三件套规格
  gate4-adjudication.md        # 门禁 4 裁决、不可达形态、冲突处置
  delivery-checklist.md        # 交付前清单、引用关系矩阵、脚本射程
  pipeline.md                  # 流程图与 11 步执行序列表
  self_check.py                # 机械自检脚本
  verification-log.md          # 逐版实测账本（诚实账本：哪条规则是哪次实测换来的）
  maintainer-notes.md          # 改 SKILL.md 前必读
evals/                         # 6 条任务级用例 + harness.py
examples/full-walkthrough.md   # 端到端产出示例
```

### 已知限制

- **强依赖 `github` 连接器**；未授权只能走降级路径。
- **搜索轮次硬上限 3 轮**，满 3 轮必须把已有候选交用户裁决，不得自行死磕。
- **「用户答不出」的分支未实测**；需求方不可达时按降级形态处理并如实标注。
- **不做代码实现**：L3 产出交给实现类 skill 执行。
- 开发期台架（`.eval/` 盲跑、`blind/` 记录、私有夹具）**未随仓库发布**；`references/verification-log.md` 里对它们的引用只作溯源。

完整未验证分支与实测覆盖情况见 [`references/verification-log.md`](references/verification-log.md) —— **设计 ≠ 验证**，按卡点对待。

### 贡献

改 `SKILL.md` 前先读 [`references/maintainer-notes.md`](references/maintainer-notes.md)（声明唯一性表 + 两条维护纪律），改完必须跑 `python references/self_check.py --skill SKILL.md`。版本号只在 frontmatter 出现一次，并与账本末行对账。

### License

MIT，见 [LICENSE](LICENSE)。
