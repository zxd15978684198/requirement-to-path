# requirement-to-path · 需求 → 对标 → 路径重构

> **从一句模糊需求，走到一条能照着施工的实现路径。**

[简体中文](README.zh-CN.md) ｜ [English](README.md)

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
README.md                       英文版（English）
README.zh-CN.md                 你正在读的这份
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
