# L1 搜索配方

<!-- self_check: genre=reference -->

从需求规格出发，找到 GitHub 上**整块匹配**模块的操作手册。

> **铁律：GitHub 检索全部走 `github` 连接器（MCP 工具），不自研搜索脚本。**
> 自研直连 REST API 的问题实测：未认证时搜索限流 **10 次/分钟**，一次跑 3-5 组关键词并行必然被拦，
> 拿回来的数据不完整、不稳定；连接器的鉴权与额度由平台托管，没有这个天花板。
>
> **实测结论置信度标注**：**[实测-稳定]** = 多项目／多次复现，可放心依赖；
> **[实测-单次]** = 单次实测观察，样本不足，重要决策前建议复验；**[推断]** = 未实测。
> GitHub 工具行为可能随官方升级变化，标注只代表撰写时点。

---

## 零、工具链（顺序不能颠倒）

### 前置：加载连接器

接通 **GitHub 连接器**（`github`）：接通后其 GitHub MCP 工具即可调用。工具名在本运行环境里带前缀（`mcp__github__*`），**按后缀名识别**。

加载后**把本次将用到的每个工具各探活一次**（不要只测一个就假定全通）：

| 工具 | 最小探活调用 |
| --- | --- |
| `search_repositories` | `query: "stars:>100000"`、`perPage: 1` |
| `search_code` | `query: "\"content hash\" language:python"`、`perPage: 1` |
| `search_issues` | `query: "reranking"` + **`owner`／`repo` 限定**、`perPage: 1` |
| `get_file_contents`（**目录**） | 任取一个已知仓库的根目录（`path: "/"`）——这**只证明工具活着**，不证明正文能到手 |
| `get_file_contents`（**文件**） | 任取一个**已知存在的小文件**（如 `path: "README.md"`）——**必须看正文到没到手**，这是 L2 取证的真前置 |
| `list_commits` | 任取一个已知仓库的最近一条提交 |

> **v1.7 实测教训**：只探活 `search_repositories` 就开工，`search_issues` 连跑 3 次全 0——**不用 repo 限定，该工具对抽象表述（"feature request for hybrid search"）和具体现象描述（"search results are irrelevant for chinese queries"）都返回 0**。这不是词没选好，是没有被探活的工具把"用法错误"伪装成了"搜不到"。

**探活怎么算通过**（原文只写了"测什么"，没写"什么算过"——盲跑实测卡在这里）：判据只看**响应形态**，不看命中数。调用**正常返回了结构良好的响应**（无异常、无鉴权错误、结果里带 `total_count` 或结果数组）即 **通过**；**`total_count: 0` 也是通过**——"没搜到"不等于"工具坏"。以下三种才算**失败**：抛异常／鉴权或限流报错／工具名不存在。**把"0 条结果"读成"工具坏"，会让整条流程在一个没坏的地方停住。**

**正文通道探活（v1.56.21 补——只探"工具活着"会漏掉这一条）**：`get_file_contents` 读**目录**回 JSON，读**文件**却可能只回 `successfully downloaded text file (SHA: …)` 加一句 `[embedded resource unsupported; raw resource data remains available to programmatic callers]`——**工具是好的、sha 是对的，正文到不了模型**（v1.37.6 与盲跑 5 两次实测，同一现象）。所以"文件"那一行探活**必须确认正文到手**，并把判定写进产出物，因为它决定 L2 的取证形态：

- **正文到手** → L2 走连接器（首选，可给行号）；
- **只回 SHA** → 切 REST：用 **`fetch` MCP 工具**打 `api.github.com`（**不是**内建 `WebFetch`——后者在本机可能直接报 `multiple usable web providers are registered (deepseek-fetch-api, http); configure one explicitly`，**那不代表文件不存在**），拿到 base64 正文后本地解码数行号；再不行用 `search_code` 片段＋它自带的 blob `sha`。
  - **`fetch` 也打不通时的本机兜底（v1.56.23 补，盲跑 6 实测）**：`pwsh` 里 `Invoke-RestMethod`／`Invoke-WebRequest` 打 `api.github.com` 可用，返回体落盘到临时目录再本地 `grep` 取行号（长度克制，别整仓拉）。**注意域名分工**：只有 `api.github.com` 这条通；`raw.githubusercontent.com` 与 `cdn.jsdelivr.net` 在本机实测**都不可达**，别在这两个域名上耗轮次——要文件正文就老老实实走 `api.github.com/repos/<owner>/<repo>/contents/<path>`。
- **`read_mcp_resource` 不是通道**：本连接的资源清单只有四个 `ui://github-mcp-server/...`（`list_mcp_resources(server="github")` 实测），**没有** `repo://{owner}/{repo}/contents{/path*}` 这种模板，照那个形态调只会得到 `fetch failed`——**不要据它判断"正文读不到"。**

三条通道的完整形态与出处写法见 `references/l2-extraction-protocol.md`「拿到正文的三条通道」。

### 步 1：捞候选（两条路，**直搜为主**）

#### 1-A 直搜路径（主路径）—— `search_repositories`

| 参数 | 值 | 说明 |
| --- | --- | --- |
| `query` | GitHub 搜索语法（见 §一） | **必填**；**≤3 个词的名词组合** + `stars:>=N` |
| `minimal_output` | **`false`** | 默认 `true` 只返回精简字段，拿不到 star／提交时间／archived → 成熟度判断直接失效 |
| `perPage` | 建议 30–100 | **必须逐条看完返回的候选表**——不许只取前 N 条。**判定式（P0-1，可机械核）**：①**取回条数 ≥ 命中数**（不够就分页看完）；②**命中数远超"你能逐条看完"的容量 ⇒ 该查询不可用于发现**，换更具体的机制词，或改走带 `repo:` 范围的精确通道（那是核实，见 1-B） |
| `sort` | `stars` | [实测-单次] 可用；不传则走 best match，会拿到低 star 噪音 |
| `order` | `desc` | 配合 `sort` 用 |
| `page` | 翻页 | |

> **「不许只取前 N 条」是硬要求**：实测一次真实的语义缓存需求，只看前 5 条就漏掉了 81★ 的
> `vcache-project/vCache`——它是**全表唯一**给出"误命中上界"的仓库，而排在它前面的都是高 star
> 但机制不匹配的项目（KV 缓存、提示压缩）。**star 排名 ≠ 机制匹配度。**

读回的仓库对象（`minimal_output: false`）含：`full_name`、`description`、`html_url`、
`stargazers_count`、`forks_count`、`language`、`pushed_at`、`created_at`、`archived`、`fork`、`license`、`open_issues_count`、`default_branch`。

#### 1-B 反查路径 —— **不是发现路径**，是"已有候选之后的精读"

`search_code` 是**精确**工具，只在**带仓库范围**时精确：

| 形态 | 实测结果 |
| --- | --- |
| `repo:zilliztech/GPTCache similarity_threshold` | **19 条**（精确命中原文件） |
| `repo:vcache-project/vCache VerifiedDecisionPolicy delta` | **11 条** |
| `"similarity_threshold" language:python`（**无范围**） | **148,992 条**，top-5 全是无关小仓库 |
| `"semantic_cache" language:python`（**无范围**） | **21,248 条**，同上 |

**所以**：无范围的机制短语**不能**用来捞候选——它把"这个词在代码里出现过"当成"这个仓库实现了这
机制"，而任何仓库的日志、测试数据、README 里都可能有这个词。反查的正确用法是**先有候选**，
再用 `repo:<owner>/<name> <符号名>` 去**定位与核实**它的实现（步 2 与 L2 取证都走这条）。

> 本文件曾把 `"<机制短语>" language:python` 当推荐主路径，理由是"搜码命中的仓库，是代码里真写了
> 这个机制的仓库"。这条推理的漏洞就是上表那 148,992 条：**命中 ≠ 实现**。而原文举的支持证据
> （`"content hash" repo:zilliztech/GPTCache`）其实是**带 `repo:` 的范围查询**——证据支持的是范围
> 形态，不是它推荐的无范围形态。**别把"验证一个已知仓库"的工具当成"发现未知仓库"的工具。**

> **两条路的关系（现行）**：1-A 直搜负责**发现**，1-B 反查负责**核实**；1-A 空、或命中的全是
> 框架／教程时，**换关键词组再跑 1-A**（见 §七），不要改用无范围反查硬凑候选。

### 步 2：核验候选 —— `list_commits` / `get_file_contents` / `search_code`

| 要什么 | 工具 | 参数 |
| --- | --- | --- |
| 最近提交（活跃度） | `list_commits` | `owner`、`repo`、`perPage: 1` |
| 文件树 | `get_file_contents` | `owner`、`repo`、`path: "/"` |
| 读某个文件 | `get_file_contents` | `owner`、`repo`、`path`、`ref`（默认分支未必是 main） |
| 在码里定位机制 | `search_code` | `query`，机制短语**加英文双引号**，如 `"content hash" repo:owner/name` |

**已知的候选**（不在搜索结果里，只有 `owner/repo`）想拿元信息：再跑一次
`search_repositories`，`query: "repo:owner/name"`、`minimal_output: false` —— 官方 MCP 的 repos 工具集
**没有** `get_repository`，用搜索语法回捞是正解。

> 备选（可选）：连接器还暴露了仓库内容资源模板 `repo://{owner}/{repo}/contents{/path*}`，
> 需要按资源方式整目录读取时可用 `ReadMcpResource`，但常规流程用 `get_file_contents` 就够。

### 为什么必须用 GitHub 仓库搜索，而不是通用网页搜索

**实测对比（同一需求）**：

| 方式 | 排序依据 | 结果 |
| --- | --- | --- |
| 通用网页搜索 | 网页的 **SEO 质量** | 命中的 5 个候选**全是 2-5 star** 的个人小项目 |
| `search_repositories`（GitHub 官方搜索 API） | 仓库的 **影响力指标**（star/fork/star 时间） | 第一条即命中 **8185 star** 的主流项目 |

**根因**：小项目的 README 关键词密度高、还有 npm / go 包页面，在网页搜索里反而排得靠前。

→ **网页搜索只用于"找术语线索"**（当你不知道该用什么行话描述某机制时），**不用于挑候选**。

### 排序怎么控制（[实测-单次]）

`sort` 与 `order` **都可用**：`sort: "stars"` + `order: "desc"` 实测返回严格按 star 降序
（`content hash stars:>=100` → 1535 → 590 → 420）。

仍然建议叠一层门槛：`stars:>=100`（需放宽时降到 `stars:>=20`），因为**默认排序是 best match，不是 star** ——
不显式传 `sort` 就会拿到一堆低 star 噪音。

> 早先版本的本文件写过"`sort` 是否暴露不稳定"，**那是错的，已按实测修正**。

### 连接器 vs 自研直连（为什么铁律成立）

| 维度 | `github` 连接器（MCP） | 自研脚本直连 REST API |
| --- | --- | --- |
| 鉴权 | 连接器统一托管（服务端授权，已绑定账号） | 需自备 `GITHUB_TOKEN`，否则未认证 |
| 限流 | 按授权额度，可连续多轮搜索 | 未认证**搜索 10 次/分钟**，多组关键词并行必然被拦 |
| 维护 | 随连接器升级（工具集由 GitHub 官方 MCP server 提供） | 每次都要自己处理错误码／重试／字段解析 |

### 连接器不可用时的降级

处置链**以本节 §6.1 为准（原 SKILL.md「L1.0-fallback」，现为唯一处）**（用户确认 → WebFetch 直取 REST API → 产出物显式标注降级），此处不重复。两点补充：

- 未认证限流 10 次/分钟 [实测-单次]，多关键词并行必然被拦；
- WebFetch 拿到的候选完整性没有保证，产出物必须注明"降级路径，候选可能不全"。

---

## 一、关键词构造：机制描述，不用领域名

### 原理

**机制描述是独特指纹，领域名是高频词。** 用领域名会命中几千个通用框架；用机制描述能把范围收敛到几个仓库。

| ❌ 领域名（会命中框架） | ✅ 机制描述（精准） |
| --- | --- |
| `RAG system` | `re-embed only changed chunks` |
| `knowledge base sync` | `delete propagation stale documents` |
| `vector database update` | `patch metadata without re-embedding` |
| `data pipeline` | `chunk registry sqlite` |
| `LLM memory` | `incremental indexing content hash` |

### ⚠️ 机制描述词该喂给哪个工具（实测踩坑 [实测-稳定]，务必先看）

**机制短语不能直接丢给 `search_repositories`。** 它只搜仓库的 name / description / readme **元数据**，
GitHub 对多个词是 **AND** 语义，于是多词机制短语几乎必然 0 结果：

| 实测 query（`search_repositories`） | 命中 | 说明 |
| --- | --- | --- |
| `incremental index content hash stars:>=100 language:python archived:false` | **0** | 4 个词全 AND，必空 |
| `incremental index content hash stars:>=100` | **0** | 去掉语言过滤仍空 |
| `chunk registry stars:>=20` | **0** | 2 个词 + 门槛就空了 |
| `chunk registry` | 24 | 去掉门槛才有，但**全是噪音**（Minecraft 区块、假数据生成器…） |
| `content hash in:name stars:>=100` | 1 | `in:name` 更窄，命中的是 Terraform 教程仓库，无关 |

**正确分工**：

| 工具 | 搜什么 | 关键词形态 |
| --- | --- | --- |
| `search_repositories` | 仓库**元数据**（name/description/readme） | **≤3 个词的名词组合** + `stars:>=N`，如 `semantic cache`、`chunk registry`、`incremental indexing` |
| `search_code` | 代码**内容** | **机制短语的落点**——`"content hash" repo:owner/name`、`"dedup" path:src`；短语加**英文双引号**才做精确匹配，否则 `hash` 会命中 `pylint.conf` 这类噪音 |

**所以两件事分工**：**发现**用 `search_repositories`（直搜，见 §零 1-A），**核实**用 `search_code`——
但必须**带 `repo:` 范围**（无范围形态实测 148,992 条噪音，见 1-B）。机制描述指纹是"核实工具"，
不是"发现工具"。

#### 1-C 当 `search_repositories` 归零时的发现兜底（[实测-单次]）

`search_repositories` 连试两个查询都返回 0 时，**不要直接判"0 候选"**——退一步用**无 `repo:` 范围**的 `search_code` 打机制短语，命中数会很大（实测 213 / 177 条），但**前几条就能定位到主仓**（本次由 `refresh_ref_docs` 的片段一路顺藤到 `run-llama/llama_index` 的 `ingestion/pipeline.py`）。代价是要在噪音里挑，所以：

| 顺序 | 动作 | 判据 |
| --- | --- | --- |
| 1 | `search_repositories` ≤3 词名词组合 | 命中 > 0 → 走正常路径 |
| 2 | 仍为 0 → `search_code` **不加 `repo:`**、加英文双引号打机制短语 | 前 10 条里有 ≥1 个**真实主仓**（非 vendored 副本、非 fork 教程）→ 转入核实 |
| 3 | 前 10 条全是 vendored 副本（`venv/…`、`site-packages/…`、`api/Lib/…`） | 也在告诉你有价值：这些副本指向的**上游就是主仓**，按 `repository` 字段回查上游 |

**注意**：无范围结果里同一段代码会被几十个 `venv/Lib/site-packages/` 副本重复命中——**表里记"已换词"并说明走了兜底**，别把它当"取回条数 < 命中数"的形式缺陷（P0-1 的例外情形）。

### 构造步骤

1. 从需求规格的「做什么」里提取**动词短语**：`同步变化` → `incremental sync`、`删除过期` → `delete stale`
2. 提取**机制名词**：`台账` → `registry / manifest / state table`、`指纹` → `hash fingerprint`
3. 组合成 3-5 组关键词，写成 GitHub 搜索语法，交给 `search_repositories` **并行跑**
4. **返回结果为空或全是噪音 → 是关键词的问题**（太窄／太宽／行话不对），回到第 1 步重新组合，不要带着错误关键词往下走

### GitHub 搜索语法速用（写在 `query` 里）

| 语法 | 作用 | 例子 |
| --- | --- | --- |
| `stars:>=N` | 影响力门槛（**必用**，挡掉个人小项目） | `stars:>=100` |
| `language:` | 限定语言 | `language:python` |
| `in:name` / `in:readme` / `in:description` | 限定匹配字段 | `registry in:name` |
| `topic:` | 按主题标签 | `topic:rag` |
| `archived:false` | 排除已归档 | `archived:false` |
| `fork:false` | 排除 fork | `fork:false` |
| `pushed:>2025-01-01` | 近一年有提交 | 用来跳过停滞项目 |
| `size:<2000` | 排除超大仓库（单位 KB） | 避免命中 monorepo／平台 |

组合示例：`incremental index content hash stars:>=100 language:python archived:false pushed:>2025-01-01`

### 中文需求的英文化

| 中文需求词 | 建议英文关键词 |
| --- | --- |
| 增量更新 | incremental update / delta sync |
| 去重 | deduplication / duplicate detection |
| 删除传播 | delete propagation / orphaned chunks |
| 断点续跑 | resumable / checkpoint |
| 幂等 | idempotent |
| 变更检测 | change detection / content hash |
| 状态机与非法迁移 | state machine / transition guard / illegal transition |
| 并发控制与行锁 | row lock / SELECT FOR UPDATE / optimistic concurrency |
| 数据库迁移与向后兼容 | migration / backfill / nullable column |
| 权限过滤（检索期） | permission filtering / row-level security / access control |
| 超时与重试 | timeout / retry / watchdog / circuit breaker |
| 语义缓存与误命中 | semantic cache / embedding threshold / false hit |
| 审计留痕 | audit log / who-did-what / asset tag |

---

## 二、结果分类：先分类再筛选

搜到的结果混着框架、教程、平台，**先按类型分流**：

| 类型 | 识别特征 | 处理 |
| --- | --- | --- |
| **完整模块 / 项目** | 独立仓库、**只做一件事**、核心目录清晰 | 🎯 目标 |
| **参考实现库**（v1.7 新增） | 单一机制的**独立库／统一 API**（如把各家重排模型收口成一个接口的 `rerankers`）；覆盖面**窄于**需求，但接口设计成熟、可整读 | 📐 **读设计、抄模式**（接口形状／数据结构／错误处理约定），**不作依赖**——尤其活跃度停滞时 |
| 框架 | 通用库、可 pip/npm 装、什么都做（LangChain／LlamaIndex 类） | ❌ 排除 |
| 教程 / 示例 | notebook、单文件 demo、`_tutorial` 后缀 | 📎 参考，不作对标 |
| 平台 / 产品 | 有 UI、多服务、docker-compose | ❌ 排除 |

### 硬判据

> **README 第一句能否用"它做 X"一句话概括？**
> 能 → 模块；不能 → 大概率是框架。
> **能概括、但覆盖面窄于需求** → 参考实现库：学它怎么设计，而不是拿它交差。

> **v1.7 实测来源**：测试需求是"给 R2R 的检索链加 reranking"，真正需要的是**学 `AnswerDotAI/rerankers` 的接口设计**（工厂+注册表、语言相关默认模型表、`Result` 不变式），而不是找一个"带头部重排的完整 RAG 系统"。按原四分类，这个库会因"不是完整方案"差点被误排——新增本档后它成了第一优选。

**类型判断的数据从哪来**（不用 clone）：
`get_file_contents(owner, repo, path: "/")` 看顶层目录结构（有没有 `src/`、`examples/`、`docker-compose.yml`），
`get_file_contents(owner, repo, path: "README.md")` 读第一句。

（实测教训：前两轮搜索全部命中框架，被用户连续纠正两次"不要框架要模块"——这一步不能省。）

---

## 三、匹配度矩阵

把需求规格拆成 N 个**可核对的功能点**，逐候选打勾：

```
需求点                        候选A   候选B
块级增量重嵌                    ✅      ?
metadata 变化不重算             ✅      ?
删除传播（含部分块删除）          ✅      ?
本地台账                       ✅      ?
目标存储兼容                    ❌      ?
先预览再删                     ❌      ?
─────────────────────────────────────
设计匹配度                     5/9
```

**缺口清单比匹配分数重要**——分数决定选谁，缺口决定要补多少活。

---

## 四、元信息 + 成熟度（分开报）

**数据全部来自连接器，不需要 curl、不需要 clone**（字段位置已实测）：

| 输出项 | 取自 | 字段位置 |
| --- | --- | --- |
| star / fork / archived / 默认分支 | `search_repositories(minimal_output: false)` | `stargazers_count`、`forks_count`、`archived`、`default_branch` |
| 最后提交时间（push）/ 创建时间 | 同上 | `pushed_at`、`created_at` |
| license | 同上 | `license.spdx_id` —— **仓库没声明 license 时该字段整体缺失**，按"未知"记 |
| 最近一条提交（更细的活跃度） | `list_commits(owner, repo, perPage: 1)` | 时间在 **`[0].commit.author.date`**（不是 `pushed_at`，长度 1 的数组） |
| 文件树与规模 | `get_file_contents(owner, repo, path: "/")` | 每项含 `type`（dir/file）、`size`、`name`、`path` |

> **实测 [实测-单次]：`minimal_output` 默认 `true` 时只回 15 个字段**——有 `stargazers_count`、`forks_count`、
> `created_at`、`updated_at`、`archived`、`language`，**但没有 `pushed_at`、没有 `license`**。
> 想判断"最后提交距今多久"就必须显式传 `minimal_output: false`，否则只能退而用 `updated_at`
> （仓库被 star 也会刷新，会把停滞项目误判成活跃）。

### 输出格式（必须分开报）

| 输出 | 示例 |
| --- | --- |
| **设计匹配度** | 高（9 个核对点命中 5 个） |
| **成熟度** | ⚠️ 低——2 star、0 fork、近 3 个月未提交 |

成熟度**内部还要再分两个维度**，不许压成一个等级：

| 维度 | 判据 | 档位 |
| --- | --- | --- |
| **社区规模** | `stargazers_count` | 高 ≥1000／中 ≥100／低 <100 |
| **活跃度** | `pushed_at` 距今 | 活跃 ≤30 天／放缓 ≤180／停滞 ≤365／长期未更新 >365 |

### 判断原则

- **不设 star 硬阈值**——存在"设计精准但没人用"的项目（实测命中的项目只有 2 star，但设计匹配度最高）；
- **两个维度分开报**，让用户自己判断；
- 组合结论要避免误判：
  - 高 star + 活跃/放缓 → ✅ 成熟活跃，可读设计也可作依赖
  - 高 star + 停滞 → ⚠️ 社区规模大、设计经过验证，**适合读设计，不建议作生产依赖**
  - 低/中 star + 活跃 → 🌱 新兴项目，**结论形态是「参考其设计、自己补生产化」**
- `archived: true` 或 `fork: true` 要显式标出（fork 的 star 与活跃度不代表原项目）。

---

## 五、代码级验证

**只读 README 不算数**（[实测-单次]：只读 README 得出的两条结论在读码后被推翻）。

| 步骤 | 做法 |
| --- | --- |
| 1 | `get_file_contents` 读 README 快速判定**类型**（模块/框架/教程/平台） |
| 2 | `get_file_contents(path: "/")` 看目录，定位**入口主流程**（`engine.py` / `sync.py` / `main.py`） |
| 3 | 读**数据结构**（台账表结构 / 数据模型） |
| 4 | 读**接口契约**（适配器 / 抽象基类） |
| 5 | 读**测试文件**（断言即验收清单） |

先用 `search_code` 定位命中文件，再 `get_file_contents` 读原文——比逐个猜路径快得多，也避免把整个仓库拉下来。

`search_code` 返回项的可用字段（[实测-单次]）：`path`（命中文件路径）、`repository`（`owner/repo`）、
`text_matches[].fragment`（命中片段，可直接看上下文判断是不是真实现）。
**短语一定加引号**（`"content hash"`），否则 `hash` 这种通用词会命中 `pylint.conf`、`.ipynb` 里的
编辑器配置等噪音——实测 `hash repo:zilliztech/GPTCache` 的 6 条命中里就有 3 条是噪音。

**但不要把多段引号短语用 `OR` 串进同一个查询**（[实测-单次]，v1.10.1）：跑
`"trajectory diff" OR "trajectory comparison" OR "trace diff"` 得 `total_count: 0`，
而紧接着单独跑 `"trajectory diff"` 得 6368——**引号短语一旦用 `OR` 串联就整体失效**。
需要多组短语时逐条分开跑（会占轮次预算，所以第 1 轮就把最关键的 2–3 组排好序），不要压进一个查询。

小仓库（<30KB）可整读；大仓库严格按上述顺序，不读全仓。

---

## 六、网络受限时的补充处置

**以下两条是补充**（主处置链见 §6.1）：

### 6.1 主处置链：半通 / 全断（原在 SKILL.md「L1.0-fallback」，现为唯一处）

**第 0 步：先判「半通」还是「全断」**（实测来源：工具面未注册但资源面可用）

现象（实测）：连接器状态显示 connected，`search_repositories` / `search_code` 等**工具在 ToolSearch 索引里不存在**，直接调用报 `not found in the deferred tools index`——但 `ListMcpResources` 能列出该 server 的资源，且 `ReadMcpResource` 能真的读到文件。

处置：**这属于「半通」，先不要降级**。按顺序：

1. `ListMcpResources({ server: "<server>" })` 探活**资源面**——能列出资源说明 server 活着；
2. 用资源通道直读源码（**connector-native，不算降级**）：`ReadMcpResource({ server: "github", uri: "repo://{owner}/{repo}/contents{/path}" })` 可读任意仓库任意文件全文；`repo://…/refs/heads/{branch}/contents{/path}` 可指定分支；
3. **限制要如实标注**：资源通道只能「读已知路径的文件」，**不支持搜索发现、不支持目录列举**（传目录返回 404）、**拿不到 star/license/活跃度**。因此产出物须写「**候选集来自领域已知集 + 逐文件核验，非搜索路径；候选集不完整**」；
4. **先判「这个需求能不能在半通下跑」**——资源通道**只能读已知路径、不能搜索发现**，所以：
   - **候选集来自领域已知集**（你已经知道具体 owner/repo）→ 可以继续，按第 2 步直读；
   - **候选集需要靠搜索发现**（不知道有哪些仓库）→ **漏斗的候选发现能力已丧失，不要在此时硬跑**。正确动作是**明确告知用户「当前连接器半通、无法做候选发现，请重连后重跑」并停下**——硬跑出来的产出物只能标「候选集不完整」，对需要发现的需求等于没有产出。
5. 告知用户重启应用／重连连接器以让工具面重新注册；用户处理完立即重探**四个工具各一次**（`search_repositories`／`search_code`／`get_file_contents`／`list_commits`），全通即回到主路径。

**两个补充规则**（同一实测得出）：

- `search_code` 带 `repo:` 限定交 0 且 `incomplete_results: true` 时**不要断定「没有实现」**——改用机制短语反查；`search_repositories` 带 `repo:` 报 `Validation Failed`（如改名仓库）时**元数据不可得就如实标注缺口、禁止编造 star／license**。

**全断时的降级链**：

1. 告知用户连接器未就绪，请其在**连接器管理页**确认 `GitHub` 已连接／已授权；
2. 用户暂时无法处理时，才改用通用 `WebFetch` 直取 GitHub REST API，**并显式标注这是降级结果**：
   `https://api.github.com/search/repositories?q=<query>&sort=stars&order=desc`
   注意：未认证限流严苛（搜索 10 次/分钟），结果会被截断或不完整；
3. **候选发现降级且仍有候选时**（**指连接器／网络这条检索通道降级——不是「需求方不可达」那条 L0 降级轴**），必须在产出物**§5 首行**写明「**本次结果来自降级路径，候选集不完整**」（固定句式，别自拟近义句）；**三条通道全断时以第 4 条为准**——§5 首行改写 `N/A：无网络与连接器，未执行候选发现`：两句**互斥而非并列**，别同时写；
4. **三条通道同时不可用时的终止分支**（连接器不可用 + 网络不可达 + 命令不可执行）：**允许继续产出，但产出物必须降级为「纯推导方案」**，且四条写死：①§0 声明「本次无候选发现与代码核验输入，§5 对标章节为空，全部结论为 `[推断]`／`[假设]`，须在有网环境重跑 §5 与 §6」；②§5 不写「未找到」这类**会被读成结论**的措辞，改写 `N/A：无网络与连接器，未执行候选发现`；③自检清单里**来源封闭域**与**代码级验证**两项**由人工判「未核」**，并当场写明「**人工核验，未经脚本**」+ 逐项结论——**不得引用 `self_check.py` 的退出码或 ⚠️ 行来证明这两项已核**：纯推导方案里来源列合法填 `H<n>`／`L0-S<n>`，脚本对「来源封闭域」不会报 ⚠️，但**候选发现记录表缺失会报 ⚠️**（纯推导方案本来就没有这张表）→ 退出码通常是 **2**，不是 0；而「代码级验证」根本不在脚本射程内 → 拿退出码当证据，就是把「没核」读成「已核」，正是本 skill 反复治理的那种失明；④交付时显式告知用户**该产出物不能当作对标结论使用**。**为什么必须写死**：没有这一支时执行者只能自拟声明，而「未找到」与「没搜」在读者眼里是同一句话——前者是结论，后者是缺口。

1. **确实需要本地整仓时**（跑测试／跨文件 grep）才 `git clone --depth 1 <url>`；企业网络常拦（实测 `CONNECT tunnel failed, 502`）→ 被拦就退回连接器逐文件读（`get_file_contents` + `search_code`，多数场景够用）。本流程正常**不需要** clone——连接器走 HTTPS 到 MCP 服务端，不受本地 `git` 协议阻断影响；
2. **走 WebFetch 降级路径时**，三个可直接用的端点：
   - `https://api.github.com/repos/{owner}/{repo}` ← 元信息
   - `https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1` ← 完整文件树
   - `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}` ← 逐文件读
   注意：默认分支未必是 main（实测是 master）→ 先确认 `default_branch`。

---

## 七、搜索轮次策略

| 轮次 | 动作 |
| --- | --- |
| 第 1 轮 | 走**直搜**：`search_repositories` 跑 3-5 组 **≤3 词的名词组合**（`semantic cache`、`incremental indexing`），`minimal_output: false` + `sort: stars` + `perPage: 30-100`，**逐条看完候选表**；同时对已知候选用 `repo:<owner>/<name> <符号>` 做精读核实 |
| 第 2 轮 | 命中全是框架／平台／无关噪音 → **换关键词组**，换成更具体的机制词（`registry`、`content hash`、`sqlite`）；或把 `search_code` 收窄到 `language:`／`path:` |
| 第 3 轮 | 仍不合意 → **放宽门槛**（`stars:>=20`）或去掉 `language:`，看是否有跨语言的设计参考 |
| 上限 | **见 SKILL.md「已知限制」第 2 条（本行不复述数值）**；超过则把已有候选摆给用户裁决，不要自行死磕 |

**四条判据**（前两条是实测新增）：

| 观察 | 结论 | 动作 |
| --- | --- | --- |
| `total_count` 为 **0** | 词太多（AND 语义）或门槛太高 | **立刻减词**（砍到 ≤3 个）或去掉 `stars:`，不要继续加词 |
| `total_count` 为 **0**，但把同一个查询拆开单独跑就有结果 | **查询形态问题，不是生态里真的没有**：多段引号短语用 `OR` 串联会失效；多词叠加 `stars:` 门槛也会归零（两条均 v1.10.1 实测） | 拆成单短语逐条跑；或去掉门槛看量级。**先怀疑查询形态，再下"没有对标"的结论** |
| 命中数高但描述全是 JS 构建工具／Minecraft 这类**同名词汇** | 词有歧义 | 换更具体的复合词；已知候选仓库则用 `repo:` 收窄后精读 |
| 前 10 条里 `stargazers_count` > 100 的有 0 条 | 门槛或关键词有问题 | **不要往下走**，换词或放宽 |
| 前 10 条全是框架／平台 | 关键词太宽 | 加机制词收窄 |
| **返回体超大（数十 KB 起）或被截断／落盘** | 全量拉回会吃掉 token 预算；被落盘的结果可能不可回读（[实测-单次] v1.19：174646 字符结果落盘后不可回读，该轮候选集报废） | **减 `perPage`（≤10）+ 用 `fields` 裁剪字段**（只要 `path`／`repository`），或缩窄 query 分页拉取；被截断的轮次记为「候选集不完整」，**不许当作已枚举** |

**不许凑合用**——类型不对的结果不能进入匹配矩阵。

---

## 八、模型型组件的第二搜索面（HuggingFace）

> 置信度：**[实测-单次]**（v1.26.0）——规则级新增于 v1.9，首次端到端实测通过：触发判定正确、镜像抓取成功、三组机制词均返回、结论可驱动设计决策。

**背景**：v1.5 实测发现——模型型组件（如古籍标点模型 guwen-punc）在 GitHub 搜码里搜不到本体，最后是**借道引用它的下游代码**才发现的。GitHub 漏斗对「本体是模型」的子机制天然半盲，补一面 HuggingFace。

**触发**：子机制关键词里出现「模型／识别／检测／标注／打标／分类器／预训练」类实体时。**补充而非替代**：GitHub 漏斗照跑，本面只对疑似模型型子机制加搜，且不占 GitHub 的搜索轮次上限（数值见 SKILL.md「已知限制」第 2 条）。

**配方**：

```
WebFetch: https://huggingface.co/api/models?search=<机制词>&sort=downloads&direction=-1&limit=10
   ↓ 读返回项：id（org/model）、downloads（社区规模）、lastModified（活跃度）、pipeline_tag（任务类型）
   ↓ 需要深读时：WebFetch https://huggingface.co/<org>/<model>（模型卡：输入输出约定、用法、license）
```

**⚠ 官方域名不可达时的镜像降级（v1.26.0 实测，务必先看）**：`huggingface.co` 在本地网络**整体不可达**（`WebFetch` 直接 `fetch failed`，本次连试两组机制词均失败）。改走镜像：
```
WebFetch: https://hf-mirror.com/api/models?search=<机制词>&sort=downloads&direction=-1&limit=10
```
镜像实测可用（v1.26.0：三组机制词全部返回满 10 条）。**字段差异**：镜像返回 `likes` 与 `createdAt`，但**没有 `lastModified`**——活跃度改读 `createdAt`（并说明这是创建时间不是最后修改），社区规模可同时读 `downloads` 与 `likes`。

**交叉印证的价值（v1.26.0 实测新增）**：本面与 GitHub 漏斗**跑同一子机制**，两面结论若一致，可以下比单面更硬的结论。实测：`event extraction` 在 HF 最高仅 **276** 次下载（其余 6–30），GitHub 同机制最高 **60★**（其余 1–4★，多停滞在 2021–2022）→ 两面一致指向「**该子机制在开源生态无工业级实现，只有学术方案与数据集**」。这条结论直接改变了设计决策（不再找专用模型，改用通用 LLM + 规则）。**单看任一面都会以为是"自己没搜到"**。

**注意**：
- HF 元数据**没有 star 同构物**：`downloads` 当社区规模、`lastModified` 当活跃度，照 §四 两维度**分开报**（走镜像时活跃度读 `createdAt`，并注明口径不同）；
- 词形：`search=` 对长短语命中率低（[推断]），用 **≤2 词名词**（如 `punctuation`、`ner chinese`），不塞机制长句；
- 命中的模型按 §二「参考实现库」（📐 档）用法处理：读模型卡学输入输出约定，**不自动当依赖**；
- 标注纪律：只读元数据 → `[推断]`；读了模型卡内容后按内容升级。



## 九、工具映射表（L1、L2 全程只用这张表里的工具）

唯一例外：模型型组件的第二搜索面用 `WebFetch` 查 HuggingFace API（见 §八）。

| 要做什么 | GitHub MCP 工具 | 关键参数 |
| --- | --- | --- |
| **反查候选（主路径）** | `search_code` | `query` = **加引号的机制短语**（`"content hash"`）+ `repo:`／`language:`／`path:`；读返回的 `repository`、`path` |
| 直搜候选（兜底） | `search_repositories` | `query` = **≤3 词名词组合** + `stars:>=N`／`language:`；**必须配 `minimal_output: false`**（默认 `true` 拿不到 `pushed_at`／`license`，停滞项目会被误判成活跃，见 l1-search-recipes §四）、`sort: "stars"`、`order: "desc"` |
| 取仓库元信息与成熟度 | `search_repositories` | `query: "repo:owner/name"`（已知仓库回捞；官方 repos 工具集**没有** `get_repository`）；读 `stargazers_count`／`pushed_at`／`archived`／`license.spdx_id` |
| 看最近提交（活跃度） | `list_commits` | `owner`、`repo`、`perPage: 1`；时间在 **`[0].commit.author.date`** |
| 看文件树／读文件 | `get_file_contents` | `owner`、`repo`、`path`（目录传 `/`）、`ref` 可选 |
| 搜提交历史 | `search_commits` | `query` |
| **核验"已实现"声称** | `pull_request_read` | `method: "get"` + `owner`／`repo`／`pullNumber`；**关键看 `merged` 字段**（`false` = 从未进主干）与 `mergeable_state`。实测：issue 标记 completed 但 PR `merged: false` 的情形**真实存在**——见漏斗第 6 步 |
| **找真实需求（可选场景）** | `search_issues` | **必须带 `owner` + `repo`**；`query` 用短关键词。**实测**：不带 repo 限定时，无论抽象表述还是具体现象描述**都返回 0 结果**——这不是搜索词的问题，是用法的问题 |

## 十、漏斗第 0 步：形状判据与深挖配额

> **形状判据（别凭感觉判）**：把需求拆成「必需能力集合」（缺任一条方案就不成立），再看**是否存在单一候选能同时覆盖全部必需能力**——能 → 整块匹配型；不能 → 组合型（**哪怕每一条子能力都已经有成熟对标**）。**第 0 步只能"初判"**：此时还没有候选集，只能按"必需能力是否明显同源"先定方向；**第 2 步捞出候选后必须复核一次**——若确有单一仓库同时覆盖全部必需能力就回退为整块匹配型。**判错的代价不对称**：组合型误判成整块型 → 白烧一轮；整块型误判成组合型 → 只多拆一次子机制。**拿不准时按组合型走。**接口面重合度只作参考、不作判据。

**组合型的深挖配额**（实测教训——子机制**不是平均用力**）：

| 深度 | 分配 | 怎么挑 |
| --- | --- | --- |
| **深挖到 L2 读码**（读实现 + 抓问题 + 抄模式） | **2–3 个子机制** | 挑"需求正文里争议最大／细节最多"的（如 mem0 #5850：合并 vs 淘汰是核心，聚类算法不是），以及"你完全没做过"的那个 |
| 只到 L1 定位（找到候选 + 一句结论） | 其余子机制 | 有对标即可，不读码 |
| 走 0 候选降级链级别①② | 找不到整块对标的子机制 | 见「找不到对标时怎么办」 |

> **为什么限定 2–3 个**：v1.7.1 实测拆出 5 个子机制后全部深挖，工具调用量达单机制需求的 1.5–2 倍且边际收益递减（独立评审指明为扣分项）。**深挖紧跟需求争议点，不搞平均用力**——组合型按"整块匹配"搜必然 0 命中，拆解后每个子机制都能找到对标；**整块匹配是目标，不是唯一入口**。

## 十一、0 候选降级链的级别定义与动作表

> **级别的触发条件**（逐级按"能不能"问下来，不许跳级）：① 有候选覆盖**部分**子机制 → ①；② 无整块候选，但**跨语言／跨栈**存在机制同构的实现 → ②；③ **连机制同构都没有**，设计只能从第一性原理推 → ③；④ **连"这属于哪个已知机制"都说不清**、或生态里确实没有 → ④（🛑 STOP 交用户裁决）。**①–④ 的唯一定义处就是本节的级别表 + 这句触发条件**，别处只许引用编号、不许复述含义。

| 级别 | 动作 | 产出要求 |
| --- | --- | --- |
| ① 部分匹配 | 把规格拆成子机制，逐个子机制单独搜，只参考命中的部分（**即退回第 0 步的组合型走法**） | 缺口清单标明"哪些子机制无对标" |
| ② 跨语言/跨栈设计参考 | 不要求技术栈一致，只看机制设计（表结构／流程／取舍） | 标注"仅设计参考，实现不可直接照抄" |
| ③ 退回 `spec-development` | 无任何可参考实现时，基于第一性原理设计 | 产出物首页标注"**无对标，风险更高**"，验收清单从严 |
| ④ 明示无先例 | 连部分匹配都没有 → 告知用户"该需求在开源生态无成熟先例" | 🛑 STOP：由用户决定自研、收缩需求还是搁置 |

①②拿到的结果**仍要过门禁 4 裁决**，不许因为"找了很久"就降低核验标准。