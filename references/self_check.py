"""self_check.py —— requirement-to-path 机械自检（v1.21.0 新增；v1.27.0 修三处误报；v1.29.0 加 --skill 模式；v1.30.0 加重述检测并修同值检查的分组；v1.31.0 通用模式补欠账行自数 + 档位声明唯一；v1.32.0 该模式改为「禁止第二处出现」；v1.37.0 修两处"假绿"；v1.37.1 收窄来源列作用域 + 章节定位容错 + 行首版本对账；**v1.37.2 按实跑收紧步骤表判据／消重声明检查／收窄版本判据；v1.37.3 表格整体声明 + 未核项进退出码（2）+ 窄表改提示项（ℹ️）**；v1.37.4 锚点改「标题优先 + 最长窗口」+ 窗口非空才算数 + 声明线索词 + 括注来源 + §3 裸整数 + 反向边界误报（红队 8/8、探针 5/5 实跑确认））。 | v1.37.5（第五轮独立评审打回）：`REQUIRED_SKILL_ANCHORS` 补硬约束起始锚点——它原是编号连续性检查的切片起点却不自受检，删掉该行会让检查静默关闭而 `--skill` 照样 exit 0；去掉 `he = len(body)` 兜底（找不到结束锚点时会拿文末「已知限制」的 1./2./3. 当硬约束编号，报假阳性）。；v1.37.8：**声明词表比对前先剥离 Markdown 强调符**（加粗写「**层级：模块级**」曾被抓成取值「模块级**」→ 合规文档进 ⚠️ 未核；实跑本 skill 自己产出的计划文档命中 2 条）；v1.37.9：**新增第 6 项检查 `validate_negation_claims()`——状态否定的证据**（「无 X／没有 X／未实现 X」是对世界的断言，必须同一行能指出证据：来源标签／四类标记／本地 `文件:行`；判 ⚠️ 未核而非违规，因为机器分不清"选择不做"与"断言没有"。来历：本 skill 自己产出的计划文档跑出 0 violations / exit 0，而里面写着「无并发保护」——实际是「有原子替换写、无跨进程并发控制」。出口口径 5 项 → 6 项）

v1.37.0 修的是**检查器自己的假绿**，不是文档的措辞：
  ① `validate_numbers()` 原先两个分支都 `return []`，永久 0 violations —— 而 SKILL.md 把"数字标记"
     列为机械自检三项之一、把"0 violations"当放行条件。**最容易被声称全绿的那一项恰好恒真。**
  ② `extract_sources()` 对 `|` 开头的行整体 `continue`，而交付文档的施工步骤本来就常以表格承载
     —— 等于在最常见的承载形态上完全不核来源。现改为"认表头名为「来源」的那一列"。
  ③ `validate_skill_self()` 只查"正文有没有第二处"，而 v1.32.0 已把那些第二处全删了
     —— 正则永不命中 → 检查器永久放行，frontmatter 版本因此落后账本多个版本而无人发现。
     现补"第一处必须仍然正确且可达"：版本号与账本最末一行对账 + 权威位置哨兵必须存在。

v1.37.1 修的是 v1.37.0 那一轮**自己引入的假阳性与硬报**（独立复评打回，三条均经复核成立）：
  ④ `extract_sources()` 认"表头名为「来源」的列"时**不区分表的种类**，于是把交付文档里合法的裁决表／
     说明表也当施工作业表核（`examples/full-walkthrough.md` 的门禁 4 裁决表被判 5 条越界，而该文件
     正是 SKILL.md 钦定的示范交付物）。现要求该表**同时含「步骤／阶段／指令模板」类表头**才纳入核验；
     反过来，施工步骤表**缺「来源」列**必须报违规（旧行为是整表静默跳过，属漏报）。
     单元格里"反引号标签 + 中文说明"的写法也从"静默丢弃说明"改为报一条「标签外夹带文字」。
  ⑤ 估算章节定位只认 `#` 标题，而 SKILL.md 的文档结构表把 §3 写成 `3. 量级与估算`（无 `#`）
     —— 照结构表写的交付物会被硬报"找不到第 3 节"。现兼容 `#` 标题／编号列表／加粗三种形态；
     真的定位不到时输出 ⚠️「未核」提示并跳过数字检查，而不是把格式问题升级成内容违规。
  ⑥ `_ledger_max_version()` 名实不符：对外说"账本最末一行"，实现取全文 `max()`——末尾新增一行预告
     会对正确的 SKILL.md 误报，行内提及高版本号又会漏报。现只取**行首版本号**（账本条目行 `| vX.Y.Z |`）。

用法：python self_check.py <交付文档.md>        # 交付物：13 项机械检查全跑
     python self_check.py --skill <SKILL.md>   # SKILL.md 自身：声明唯一 + 权威位置可达 + 与账本同步
规则单一来源：白名单只定义在此处，SKILL.md 描述只指向这里（改域 = 改这里，检查与规则永远同步）。
"""
import os
import re
import sys

# v1.42.0：Windows 控制台默认 cp936(GBK)，而本脚本结尾会打印 ℹ️／⚠️／🛑 ——
# 这些字符在 GBK 下无法编码，`print` 抛 UnicodeEncodeError，于是**判完准备返回 0**
# 的过程被崩成 traceback、进程退出码 1。用户看到的是一次「崩溃」，实际检查早已通过；
# 更坏的情况是有人据此以为"必须设 PYTHONIOENCODING 才能跑"。默认编码由宿主决定，
# 脚本不能假设它是 UTF-8，所以这里强制 stdout/stderr 走 UTF-8 并对不可编码字符降级替换。
try:  # 非交互流（某些 IDE／重定向）可能没有 reconfigure
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ============ 第 1 层：封闭域白名单（唯一事实来源） ============
# 合法来源标签形态。注意：L0-P / L0-S 属**条件合法**（见 NEEDS_L0_ANCHOR）——仅当交付文档确实
# 存在 L0 编号产出物时才可用。（v1.37.0 修注释：原文写"已废弃、不在白名单内"，与下面第 9 条正则自相矛盾）
# v1.27.0 补记：`repo/` 前缀是**必须的**（白名单正则要求字面量 `repo/`）——SKILL.md 的
# `repo/path#符号名` 写法易被读成"仓库路径#符号名"，实测按后者写会全部越界。已在 SKILL.md ⑭ 矩阵第 9 对补明文。
ALLOWED_SOURCE_PATTERNS = [
    r"^R\d+$",                                 # 门禁4 天花板条目 R1/R2
    r"^D\d+$",                                 # 门禁4 打包默认 D1/D2
    r"^C\d+$",                                 # §4 契约 C1/C2
    r"^K\d+$",                                 # L2 坑 K1
    r"^H\d+$",                                 # 门禁1-4 的 [假设] H1（⑭ 矩阵第 9 对早已列为合法来源）
    r"^账本v\d+\.\d+(?:\.\d+)?$",              # 账本版本行（v1.37.0 换：旧 `V\d+` 形态在 verification-log.md 里没有任何 V 编号条目，是悬空标签）
    r"^repo/[A-Za-z0-9_\-./:]+#\w+$",          # repo/path#符号名（v1.27.0 修：字符类补 `:`，否则 `owner/name:path#sym` 形态全部越界）
    r"^repo/[A-Za-z0-9_\-./:]+:L\d+$",         # repo/path:L<行>（同上补 `:`）
    # v1.53.0：行**区间**。来历：eval 03 实跑时施工方写 `repo/…:L36-L68`（读一段实现的标准写法）
    #   被判「不在封闭域内」——封闭域规则的目的是「可核验」，区间比单行更可核，却因正则只认单行被挡。
    #   ⚠️ 只允许 `L<a>-L<b>` 或 `L<a>-<b>`：区间要有明确两端，才好核「a ≤ b 且 b ≤ 文件行数」。
    r"^repo/[A-Za-z0-9_\-./:]+:L\d+-L?\d+$",
    r"^L0-[PSCD]\d+$",                         # L0 门禁产出（仅当门禁 3 已编号时合法，见下）
    # v1.56.2：**本地文件行号**。来历（eval 01 子代理回报 k 条）：来源白名单只收 `repo/…`，
    #   而「门禁 1 之前先读本地代码」是 SKILL.md 明写的一步，它产出的证据必然是本地
    #   `文件:行`——白名单若不收，本地取证就只能挂到 `L0-C/L0-S` 上间接引用，
    #   等于**规则要求做这件事、却不给它的证据一个落点**。
    # 只认带行号或行区间、且扩展名在 `EVIDENCE_EXTENSIONS` 内（唯一权威，本节末尾有断言核对，两处手抄串若漂移会 import 即报错），
    # 裸文件名不放行（"出自某个文件"不可核，必须指到行）。
    r"^[A-Za-z0-9_\-./]+\.(?:py|md|json|toml|sql|yml|yaml|ini|cfg|txt|env|ts|tsx|js|jsx):L?\d+(?:-L?\d+)?$",
]


def table_cells(line: str) -> list:
    """按**未转义**的 `|` 切分 Markdown 表格行，并还原单元格里的 `\\|`。

    v1.56.22 修：此前三处都用 `s.strip("|").split("|")` —— 单元格里写合法的转义竖线
    （`读配置 a\\|b 表`）时，朴素切分把它当成了列分隔符，**整行后续列全部错位**。
    真反例（实测）：某行把来源写成 `L0-P2`、通过信号写成 `跑通`，检查器读成来源 `跑通`、
    通过信号 `b 表`，于是报「来源 跑通 不在封闭域内」——**报文指向的根本不是作者写的内容**，
    比漏报更难查：它会让人去改一个本来正确的地方。
    `\\|` 是**合法 Markdown**，所以这是解析层的错，不是产出物的错。
    """
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", body)]

# L0 标签需要门禁 3 实际编号存在才算合法——此处给出"是否需要复核"标记
# （v1.20 实测：门禁 3 是降级 [假设] 形式未编号时，L0-S 引用即越界）
NEEDS_L0_ANCHOR = [r"^L0-[PSCD]\d+$"]

# ============ --skill 模式：必须存在的哨兵 + 禁止出现的形态 ============
# 为什么要有"必须存在"的哨兵：只查"第二处有没有"的检查器，会在第二处被删掉之后永久失明。
# 权威位置必须**可达** —— 否则"值只存一处"会退化成"值哪儿都没有"（v1.37.0 的教训）。
REQUIRED_SKILL_ANCHORS = [
    ("账本指向句（正文版本行）", r"\*\*完整账本\*\*见"),
    ("正文版本行哨兵（`**版本**：见…`）", r"\*\*版本\*\*[ \t]*[：:][ \t]*见"),
    ("硬约束条数声明句（冻结机制段）", r"数量即本列表长度"),
    ("硬约束列表结束锚点（交付前逐条核对那行）", r"STOP[：:][ \t]*交付前逐条核对"),
    # v1.37.5（第五轮独立评审 🟡-4）：编号连续性检查的**切片起点**是
    #   `body.find("**叙事线硬约束**")`，但那串字不在哨兵表里 —— 把它删掉后
    #   `hb = -1`、`if hb >= 0` 为假，编号连续性检查**静默关闭**，而其余哨兵仍在、
    #   `--skill` 照样 exit 0。检查能力可以被一次纯文本删除悄悄关掉，正是本 skill
    #   一直在治的病：能关掉检查器的东西，必须自己也在受检名单里。
    ("硬约束列表起始锚点（叙事线硬约束那行）", r"\*\*叙事线硬约束\*\*"),
]
FORBIDDEN_IN_SKILL_BODY = [
    ("正文版本行（当前版本：vX）", r"当前版本：v[\d.]+"),
    ("账本区间端点（v1.2 " + chr(0x2192) + " vX）", r"v1\.2\s*" + chr(0x2192) + r"\s*v[\d.]+"),
    ("硬约束封顶数字（总数封顶 N 条）", r"总数封顶\s*\d+\s*条"),
    # v1.37.4（红队 R4-6 实跑确认）：旧 denylist 只列了 `当前版本：vX` 这一个**字面**形态，
    # 于是第二处版本声明改写成 `> **版本**：v1.30.0`（真实 SKILL.md 第 11 行的同族形态）
    # 就完全逃逸——检查器"禁止第二处"的对象是按形态枚举的，枚举不到就不算第二处。
    # 现改为**取值级**判据：任何"版本(号)："后面跟数字的写法都算声明式取值。
    ("正文版本重述（任何 `版本：vX` 形态）", r"版本(?:号)?[*` ]*[：:][ \t]*v?\d"),
]

# ============ 第 2 层：数字标记判据（v1.37.0 由空壳改为真判据） ============
# 估算类数字必须带四类标记之一，或括注"已定/依据编号"。
# 范围限定在第 3 节「量级与估算」（结构表规定的估算章节）——全文扫描会把"已定参数"
# 与正文举例一起报成假阳性（SKILL.md 明确说通用模式对本文件成片假阳性）。
ESTIMATE_UNIT = re.compile(
    r"\d+(?:\.\d+)?\s*(?:ms|毫秒|秒|分钟|小时|天|%|万|千|字|token|Token|MB|GB|KB|TB|字节|篇|块|条|次|qps|QPS|req/s)")
MARKER = re.compile(r"\[(?:实测|假设|外源|推导)\]")
# v1.37.4（红队 R4-8 实跑确认）：旧写法里 `已定` 是**裸词**，只要句中出现"已定"就放行——
# 等于发了一张免检牌。现在"已定"必须**当场括注依据**（`已定（依据 R1）`/`已定（见 C2）`）；
# 裸写"已定"由 validate_numbers 单独报违规（docstring 早就自述实现了这条，代码里其实没有）。
FIXED_HINT = re.compile(r"已定[ \t]*[（(][^)）]{1,40}[)）]|依据编号|`[RDCKH]\d+`|`L0-[PSCD]\d+`|`账本v[\d.]+`")
BARE_FIXED = re.compile(r"已定")
# v1.37.4（评分组 🔴-4 实跑确认）：SKILL.md 承诺扫"表格单元格里的裸整数"，而 ESTIMATE_UNIT
# 要求带单位词，`| 分块数 | 1200 |` 这类**纯数字格**从来不会被报。两处清单不同集 = 漏核。
# 现补这条：§3 表格里"独占一格的 3 位以上整数"必须有标记或已定依据（阈值与 SKILL.md 同步写死）。
BARE_INT_CELL = re.compile(r"[|｜][ \t]*(\d{3,})[ \t]*(?=[|｜])")
# v1.37.1：三种承载形态都认——`## 3. 量级与估算`（标题）、`3. 量级与估算`（编号列表，SKILL.md 的文档
# 结构表就是这种形态）、`**3. 量级与估算**`（加粗）。旧版只认 `#` 标题，照结构表写的交付物会被硬报
# "找不到第 3 节"（独立复评发现）。
# v1.37.4 重设计（红队 R4-1/R4-2 与我方 P5 探针**均由实跑确认**）：旧实现"取第一个命中 + 窗口非空即算数"
#   ——目录条目下多一条缩进续行、或 §3 正文里出现 `4. 峰值内存：32MB` 这种编号项，窗口就"非空却错位"，
#   于是 §3 数字标记**整节静默不核**（0 violations、无 ⚠️、exit 0）。现在分两级锚点：
#   ①**标题形态优先**（`## 3. xxx`）——正文标题不会被目录行/列表项冒充，这是唯一可靠形态；
#   ②只有全文没有标题形态时才退回"编号/加粗"形态，且**退回时打 ⚠️ 未核**（宁可说没核，不许假装核了）。
SEC_ESTIMATE_HEAD = re.compile(
    r"^[ \t]*(?:>[ \t]*)?#{1,6}[ \t]*(?:§[ \t]*)?3[ \t]*[\.、]?[ \t]*(?:\*\*)?[^\n]*(?:量级与估算|量级|估算)")
SEC_ESTIMATE_PLAIN = re.compile(
    r"^[ \t]*(?:>[ \t]*)?(?:\*\*)?[ \t]*(?:§[ \t]*)?3[ \t]*[\.、][ \t]*(?:\*\*)?[^\n]*(?:量级与估算|量级|估算)")
SEC_CONTRACT_HEAD = re.compile(
    r"^[ \t]*(?:>[ \t]*)?#{1,6}[ \t]*(?:§[ \t]*)?4(?!\d)[ \t]*[\.、]?[ \t]*")
HEAD_ANY = re.compile(r"^#{1,6}\s")
SEC_CONTRACT_PLAIN = re.compile(
    r"^[ \t]*(?:>[ \t]*)?(?:\*\*)?[ \t]*(?:§[ \t]*)?4(?!\d)[ \t]*[\.、][ \t]*(?:\*\*)?[ \t]*\S")
# 兼容旧名（外部若有引用）：等价于"任意形态"
SEC_ESTIMATE = SEC_ESTIMATE_PLAIN
SEC_CONTRACT = SEC_CONTRACT_PLAIN
# 未核提示（**不是违规，也不是通过**）：定位不到章节、或识别不出声明取值时打出来，
# 避免把"跳过"读成"全绿"。**有未核项时 main 返回 2**——调用方不能只看"退出码 0"。
WARNINGS: list[str] = []
# 提示项（v1.37.3 单列）：**不影响退出码**。用于"适用范围出界"这类已定性的说明——
# 例如某张表有「来源」列、但表头表明它不是施工步骤表。它确实没被核，但误判概率与后果都有限；
# 若一律算未核，每份含门禁裁决表的交付物都拿不到退出码 0，门禁会退化成噪音。
ADVISORY: list[str] = []
# v1.37.4（红队建议）：把"0 ≠ 交付合格"写进**脚本自己的输出**——SKILL.md 那份约 30 项清单里
# 只有 5 项落在这个脚本的射程内，退出码 0 只代表这 5 项过了。
# v1.37.9（P0-3）：曾把射程从 5 项扩到 6 项（新增"状态否定的证据"）。
# v1.40.0（独立评审打回）：**退回 5 项**——那条判据实跑误报 37.5%、漏报 70%，
#   留在 ⚠️/退出码 2 里会教执行者"忽略 ⚠️"，而降级成 ℹ️ 提示项后它照样能让人去看。
#   射程的自述必须与实现同步：**多报一项"我核了什么"，比少报更危险。**
_CAVEAT = ("口径：0 violations ≠ 交付合格——本脚本只覆盖 13 项机械检查（来源封闭域／声明唯一／声明冲突／欠账行计数／估算数字标记／候选发现记录／标记与证据配套／L3 通过信号可判／引用完整性／章节骨架／账本版本引用／自检留痕／承诺落地）；另有 ℹ️ 提示项（状态否定的证据）"
           "**不进退出码、也不算通过**。SKILL.md 交付清单的其余项（章节完整性、"
           "对标取舍、决策意图链…）不在射程内，仍须人工逐条打勾。")
# v1.46.0：退出码语义是**契约**，不是帮助文本——旧版只在"用法错误"分支打印它，
#   于是正常通过时调用方只能靠猜（把 `2` 读成"红了"是最常见的误读）。
_EXIT_CODES = ("退出码：0 = 放行／1 = 有硬违规／2 = 无硬违规但有 ⚠️ 未核项（**未核 ≠ 通过**）"
               "／64 = 用法错误")


def _split_tags(body: str) -> list[str]:
    """标签切分：有反引号时只取反引号内容，否则按分隔符切。

    v1.27.0 的老规矩保留——避免把"；对标印证见 §5"这类中文说明切成假标签
    （v1.20 实测：一次报 30+ 条假阳性）。
    """
    raw = re.findall(r"`([^`]+)`", body) if "`" in body else re.split(r"[、,，/\s]+", body)
    out = []
    for tag in raw:
        tag = tag.strip("`").strip()
        if tag:
            out.append(tag)
    return out


# v1.37.1：只有**施工步骤表**的来源列才核——其它表（门禁 4 裁决表、映射表、说明表）写自然语言
#   出处是合法的，不在"每步带来源列"这条规则的射程内。
# v1.37.2 收紧判据（**实跑发现**）：旧判据把「阶段」也算作施工步骤表的标志，于是
#   `references/l3-mode-map.md:37` 的阶段映射表（表头 `阶段 / 模式 / 理由`）被判成施工步骤表，
#   报出"缺少来源列"——假阳性。**「阶段」单独出现不足以定性**：映射表、阶段汇总表都用它。
#   现在的判据：①表头含「步骤」即算；②否则必须含「指令模板／通过信号／翻车信号／提示词」之一
#   （这几个词只出现在逐步施工表里）。别把"参考表里没写来源"当成"施工步骤没来源"。
STEP_HEADER_CORE = re.compile(r"(?:^|\s|\|)步骤(?:\s|\||$)")
STEP_HEADER_SIGNAL = re.compile(r"(?:^|\s|\|)(?:指令模板|通过信号|翻车信号|提示词)(?:\s|\||$)")
SEP_ROW = re.compile(r"^:?-{2,}:?$")


def extract_sources(doc_text: str) -> tuple[list[tuple[str, int]], list[str]]:
    """提取来源标签 → (标签列表 [(标签, 行号)], 结构性违规文字列表)。两种承载形态：

    ①正文行：`来源：` / `**来源**：` / `来源:`；标签可能带反引号。
    ②**施工步骤表**：表头含「来源」列，且含「步骤」或「指令模板/通过信号/翻车信号/提示词」之一 → 逐行核该列。
      其它带「来源」列的表（裁决表／说明表）**不核**——它们写自然语言出处是合法的；
      但施工步骤表**缺「来源」列**要报违规（旧行为是整表静默跳过 = 漏报）。

    v1.27.0 的误报修复保留：只认"来源"这一列的单元格，不把 §5 对标表里的
    "领域知识来源："当成来源标注行。
    v1.37.0 修漏报：旧实现 `if line.lstrip().startswith("|"): continue` 把**所有**表格行跳过，
    而交付文档的施工步骤本来就常以表格承载（SKILL.md 文档结构 §7、examples 都是）。
    v1.37.1 修的是 v1.37.0 引入的**新假阳性**：只看"有没有来源列"、不看表的种类，把
    `examples/full-walkthrough.md` 的门禁 4 裁决表判出 5 条越界——那是 SKILL.md 钦定的示范交付物。
    规则要的是"施工步骤每步带来源"，不是"文档里任何一张表都不许写自然语言出处"。
    """
    tags: list[tuple[str, int]] = []
    notes: list[str] = []
    in_table = False
    src_col = None
    is_step_table = False
    warned_missing = False
    for lineno, line in enumerate(doc_text.splitlines(), 1):
        if line.strip().startswith("|"):
            cells = table_cells(line)
            if not in_table:                    # 本表首行 = 表头：定列、判表的种类
                in_table = True
                warned_missing = False
                is_step_table = (any(STEP_HEADER_CORE.search(c) for c in cells)
                                 or any(STEP_HEADER_SIGNAL.search(c) for c in cells))
                src_col = None
                for i, c in enumerate(cells):
                    if c.strip("*` \u3000") == "来源":
                        src_col = i
                        break
                if src_col is not None and not is_step_table:
                    # v1.56.3（eval 01 子代理回报 g 条）：**契约表不该收到这条提示**。
                    #   实测：§4 契约表（表头 `# / 契约 / 入库前断言 / 违约处置 / 来源`）触发
                    #   「会不会是表头写歪了的施工步骤表」提示；执行者为了消掉噪音，把列名改成
                    #   「依据」——于是**真的施工步骤表**写「依据」时反而认不出、静默漏核。
                    #   判据：表头含「契约／断言／违约处置／边界」= 契约表，身份已明确，跳过提示。
                    is_contract_table = any(
                        re.search(r"契约|断言|违约处置|边界", c) for c in cells)
                    if not is_contract_table:
                        ADVISORY.append(
                            "行 %d：这张表有「来源」列，但表头表明它不是施工步骤表（表头：%s）→ 该表的来源封闭域未核；"
                            "若它其实是施工步骤表，请把表头改写成含「步骤」或「指令模板/通过信号/翻车信号/提示词」的规范列名"
                            % (lineno, " / ".join(cells)))
                if is_step_table and src_col is None:
                    warned_missing = True
                    if _l3_toc_hits(doc_text) < 3:
                        continue    # 不是 L3 交付物（参考文档里的"步骤"是讲做法，不是施工步骤）
                    notes.append(
                        "行 %d：施工步骤表缺少名为「来源」的列（表头：%s）——每步必须能给出来源；"
                        "表头写成「来源说明」「依据」这类变体脚本认不出，会被当成没有来源列"
                        % (lineno, " / ".join(cells)))
                continue
            if not is_step_table or src_col is None or warned_missing:
                continue                        # 裁决表／说明表：不在射程内
            if len(cells) > src_col and not SEP_ROW.match(cells[src_col]):
                cell = cells[src_col]
                if not cell.strip(" `*\u3000") or cell.strip() in ("-", "—", "待补", "TBD", "todo", "TODO"):
                    # v1.37.3 修静默漏报（实跑 F2 表 2）：空来源格旧路径下 `_split_tags("")`
                    #   返回空列表 → 既不报"缺来源"也不报"未核"，整列空白的步骤表直接通过。
                    notes.append(
                        "行 %d：来源格为空——每步必须能给出来源；填不出来源就该**删掉该步骤**，不许留空格"
                        % lineno)
                    continue
                for tag in _split_tags(cell):
                    tags.append((tag, lineno))
                # v1.37.6（真跑一轮暴露的误报）：旧版只 `strip()` 空白，于是「`R1`、`repo/x#y`」
                # 这种**标签用顿号分隔**的合法写法，残留物是分隔符 `、` → 被判成"标签外夹带文字"。
                # 分隔符不是说明文字。把空白与常见分隔符一并抹掉再看还有什么——剩下中文/符号才算夹带。
                residue = re.sub(r"[\s\u3000、，,；;／/|]+", "", re.sub(r"`[^`]*`", "", cell))
                if "`" in cell and residue:
                    notes.append(
                        "行 %d：来源格在反引号标签外夹带了文字「%s」——来源格只放标签；夹带的说明"
                        "要么被读成标签、要么被悄悄丢掉，两种都不该发生" % (lineno, residue[:40]))
            continue
        in_table = False                        # 离开表格：列位置与表种类作废（下一张表可能不同）
        src_col = None
        is_step_table = False
        # v1.48.1 修假红：`来源` 是复合词的后半（实测来源／知识来源／数据来源）时不是标注。
        #   实测 SKILL.md 的标题「### 需求方不可达时的降级流程（实测来源：GitHub 公开 issue）」
        #   与 l1 的「**v1.7 实测来源**：测试需求是…」都被旧判据当成来源标注，
        #   把 GitHub／公开／issue）判成越界 → SKILL.md 自己拿 exit 1。负向后顾只认"词首的 来源"。
        m = re.search(r"(?<![\u4e00-\u9fa5])来源[*\s]*[：:]\s*(.+)$", line)
        if m:
            body = m.group(1).strip()
            # v1.48.1 修假红：`来源：` 后面接一整句话不是标注（实测 l3-mode-map 的笔记块
            #   「来源：一份"看着完整…"的 L3 文档，被交给…」被判成 3 个越界标签）。
            #   标签形态只可能是：有反引号的标签串，或不含句读的短串。其余算"这一行没核"，不报违规。
            if len(body) > 40 or re.search(r"[。，；]", body):
                ADVISORY.append("行 %d：`来源：` 后面是句子而不是标签 → 本行的来源封闭域未核" % lineno)
                continue
            for tag in _split_tags(body):
                tags.append((tag, lineno))
            continue
        # v1.37.4（红队 R4-4 实跑确认）：来源写成**行内括注、无冒号**——`- 第 3 步（来源 `XX9`）`——
        #   两条既有路径都够不着（正文行路径要冒号、表格路径要 `|` 开头且有「来源」表头），
        #   于是**整项不核且零提示**。这里补第三种形态，且只认"行尾是一串反引号标签"的写法，
        #   这样 v1.27.0 的误报（§5 对标表里「领域知识来源：见 §5」）不会被重新引入。
        # v1.37.4 二次修（红队 R4-4 复跑仍漏，父会话实跑定位）：收尾的右括号包在标签**外面**
        #   （`- P1 …（来源 `XX9`）`），而首版判据要求标签串**紧贴行尾** → 括号一在，整条不匹配。
        #   允许标签串后再跟一个右括号。**注意首版把 `[）)]?` 放在标签串之前，那是错的**——
        #   括号在左侧的形态（`来源（D1）`）本来就由 `来源[*\s]*` + 分隔符切分覆盖。
        m2 = re.search(r"(?<![\u4e00-\u9fa5])来源[*\s]*((?:`[^`]+`[ \t、，,/]*)+)[ \t]*[）)]?$", line)
        if m2:
            for tag in _split_tags(m2.group(1)):
                tags.append((tag, lineno))
    return tags, notes


def has_l0_anchor(doc_text: str) -> bool:
    """全文是否存在 L0 编号产出物（门禁1-3 的编号定义）。"""
    # v1.27.0 修：原判据只认"编号后紧跟冒号"，认不出表格首列的定义形态（如 `| \`L0-S1\` | 验收标准 | …`），
    # 导致 v1.26.0 实测中一个确实定义了 L0-S1~S5 的交付物被误判为"无 L0 编号产出物"
    # v1.37.6（真跑一轮暴露的漏判）：交付物正文写 L0 清单时习惯把标签写成 `` `L0-P1`：… ``，
    # 而旧判据要求"编号后**紧跟**冒号"，中间夹一个反引号就不认 → 文档明明有 L0 编号产出物，
    # 却被判"无 L0 编号产出物"，连带**所有 L0 来源标签全部越界**（一次假阳性雪崩）。
    if re.search(r"`?L0-[PSCD]\d+`?\s*[：:]\s*\S", doc_text):
        return True
    return bool(re.search(r"^\|\s*`?L0-[PSCD]\d+`?\s*\|", doc_text, re.M))


def validate_sources(doc_text: str) -> list[str]:
    """来源封闭域校验：越界即报行号；施工步骤表缺来源列、来源格夹带说明也在此报。"""
    violations = []
    l0_anchored = has_l0_anchor(doc_text)
    tags, notes = extract_sources(doc_text)
    violations.extend(notes)
    # v1.37.4：解析失败的**兜底提示**——文档里明写了「来源」标注，却一个标签都没解析出来，
    #   说明它用了脚本不认的形态（红队 R4-4 的"行内括注无冒号"就是这样静默通过的）。
    #   记入 WARNINGS（main 因此返回 2）：未核就是未核，不许与"核过了没问题"同形。
    if not tags and re.search(r"来源[*\s]*[（(：:]", doc_text):
        WARNINGS.append(
            "全文出现「来源」标注，但一个标签都没解析出来 → **来源封闭域这一项没有核验**"
            "（不等于通过；main 返回 2）。射程内的三种写法：正文行「来源：`R1`」、"
            "施工步骤表的「来源」列、行尾括注「（来源 `R1`）」")
    for tag, lineno in tags:
        if not any(re.fullmatch(p, tag) for p in ALLOWED_SOURCE_PATTERNS):
            violations.append(f"行 {lineno}: 来源 {tag} 不在封闭域内")
            continue
        if not l0_anchored and any(re.fullmatch(p, tag) for p in NEEDS_L0_ANCHOR):
            violations.append(
                f"行 {lineno}: 来源 {tag} 属于 L0 标签，但文档无 L0 编号产出物（降级 [假设] 未编号时禁止引用）")
    return violations


def validate_declarations(doc_text: str, doc_path: str = "") -> list[str]:
    """声明型内容全文只许出现一次：层级/档位/版本号。

    注意作用域：本函数只查"多种取值"（不一致），**事实上的"重述"由 --skill 模式查**
    ——SKILL.md 维护纪律②说的"相同也算违规"只对 `--skill` 成立，不要混用。
    """
    # v1.56.5（合并 pattern 后当场暴露）：账本正文在**讲述历史**——它逐条记着
    #   「…把正文引用的 `v1.30.0`/`v1.32.0` 判成冲突…」这类对旧版本的引用。
    #   合并前这个坑看不出来（每个 pattern 各自判，命中不了这种跨形态的一对）；
    #   合并后它立刻变成「账本自己声明了两个版本号」的假红，audit 第 4 组因此 exit 1。
    #   与 v1.56.1 给 `validate_declarations_unique` 加的那条守卫同源：**引用不是声明**。
    if doc_path:
        _lp, _ = _find_ledger(doc_path)
        if _lp and os.path.abspath(_lp) == os.path.abspath(doc_path):
            return []
    violations = []
    # v1.37.2 两处收紧（均由**实跑**暴露，不是推理出来的）：
    # ①层级/档位从此表移除——`validate_declarations_unique()` 已完整覆盖（且带否定后顾 `(?<!非)`，
    #   能力更强），两个检查器都报会让同一处缺陷产出两行（实跑 negative.md：12 行里 2 行同源）。
    # ②版本号只认**声明形态**（`version:` / `版本：vX` / `当前版本：vX`），不再抓裸 `v\d+\.\d+`：
    #   实跑 `examples/full-walkthrough.md` 时，它把正文引用的 `v1.3/v1.5/v1.26` 判成"版本号冲突"——
    #   那些是**证据标识**（回账本查证的入口），不是本文档的版本声明。约束的是"文档自己的版本号
    #   只许写一处"，不是"文中出现过的版本号只许一个"。
    # v1.37.3 收紧：版本声明**必须带冒号**。旧判据的分隔符含 `\s`，于是散文里的
    #   「langchain version 0.3.7」「对标版本 v1.0.0」被判成本文档的版本号声明 → 假阳性
    #   （实跑 F4）。SKILL.md 承诺的"实测账目/样例出处的版本号是证据标识、不在清理范围"
    #   靠这条收紧落地：声明形态有冒号，引用形态没有。
    # v1.56.5（正控实测发现）：旧写法**每个 pattern 各自判断**"是否出现多种取值"，
    #   于是跨 pattern 的冲突永远查不出——实测 `version: 1.0.0` + `当前版本：v2.0.0`
    #   两个声明互相矛盾，函数返回 []。而并排放两个 pattern 的目的**正是**覆盖两种写法；
    #   它们指向同一个声明位（本文档的版本号），就必须合并后统一判"取值是否唯一"。
    #   合并前实测：同 pattern 内两值 → 报；跨 pattern 两值 → 静默。合并后两者都报。
    found: set[str] = set()
    for pattern in (
        r"(?<![A-Za-z])version[：:][ \t]*v?(\d+\.\d+(?:\.\d+)?)",
        r"版本[：:][ \t]*v?(\d+\.\d+(?:\.\d+)?)",
    ):
        found.update(re.findall(pattern, doc_text, re.I))
    if len(found) > 1:
        violations.append(f"声明冲突: 版本号声明 出现多种值 {sorted(found)}")
    return violations


def validate_ledger_line(doc_text: str) -> list[str]:
    """欠账行**不得出现计数**（v1.31.0 新增自数对账；**v1.36.0 改为禁止计数**）。

    思路变更：v1.31.0 做的是"自述数与实际数对账"，但那只查"行内自洽"，
    查不出"自述数与全节实际标注数不符"——实测交付物因此扣分。
    v1.36.0 改为**消灭对象**：欠账行不许写任何计数（与版本号同类），
    没有计数就没有对不上的可能。回填清单同样不写"共 N 项"。
    """
    violations = []
    # v1.37.4（红队 R4-3 实跑确认）：后缀写死成 `个数字`，一句"本表 12 个估算数字"就绕过去了；
    # 换量词（`本表 12 个估算数`）同样绕过。现改为"本表 + 数字 + 量词 + 估算类名词"。
    # 已知边界：不跟名词的裸写法（"本表 12 个"）不在此判据内——宁可窄，也不误伤"本表 3 个字段"这类正常句。
    pat = r"本表\s*[0-9一二三四五六七八九十]+\s*(?:个|项|条)[ \t]*(?:数字|估算|数|标注|量)"
    for m in re.finditer(pat, doc_text):
        violations.append(
            "欠账行出现计数「%s」——v1.36.0 起禁止（手写的计数就是第二处可矛盾的值；删掉计数，改为「本表数字均带四类标记」）"
            % m.group(0))
    pat2 = r"须回填\s*[0-9一二三四五六七八九十]+\s*(?:个|项|条)"
    for m in re.finditer(pat2, doc_text):
        violations.append(
            "回填说明出现计数「%s」——改为「须回填者见 §9.1」，逐条列出不写项数" % m.group(0))
    # v1.37.4（评分组 🔴-2 实跑确认）：SKILL.md 明文"回填清单本身也不写「共 m 项」"，可脚本里
    #   从来没有判据落地 → 一条硬规则零机械落点（"共 7 项"静默通过）。现补上，且只在
    #   回填/清单语境内判，避免误伤文档别处的"共 N 项"。
    for i, line in enumerate(doc_text.splitlines(), 1):
        if not re.search(r"回填|清单|§9\.1|9\.1", line):
            continue
        m3 = re.search(r"(?:共|合计)\s*[0-9一二三四五六七八九十]+\s*(?:个|项|条)", line)
        if m3:
            violations.append(
                "行 %d：回填清单出现项数「%s」——SKILL.md 明文不写「共 m 项」（手写的计数就是第二处"
                "可矛盾的值）→ %s" % (i, m3.group(0), line.strip()[:70]))
    return violations


def validate_declarations_unique(doc_text: str, doc_path: str = "") -> list[str]:
    """层级/档位声明在交付物里只许出现一次（v1.31.0 新增）。

    来历：v1.18.1 实测——文档头部写"参考档 ≤600 行"、§0 写"设计档"，两处矛盾，
    被评审判为"首稿不自洽"。旧检查只扫 `层级[：:]` 形式，抓不到这种夹在句子里的声明。

    v1.56.1（记账当场暴露的假红）：账本正文会**逐字引用**被验文档的档位声明——
    v1.56.0 那行里同时出现「`层级：模块级。档位：设计文档。`」（引用 01 的产出物）
    与「设计档」（另一处引用），于是扫账本时报「档位声明冲突 ['设计文档','设计档']」。
    这和 v1.48.3 那条「账本引用自己历史里的探针版本号」是同一个病根：**引用不是声明**。
    文档就是账本时直接返回 []（其余检查照跑）。
    """
    if doc_path:
        _lp, _ = _find_ledger(doc_path)
        if _lp and os.path.abspath(_lp) == os.path.abspath(doc_path):
            return []
    violations = []
    # v1.31.0 修误报：交付物常以否定形式列举其他档位（如「非系统级、非参考档、非施工规范」），
    # 会被当成第二种取值 —— 加否定后顾 (?<!非) 排除。
    # v1.37.4（红队 R4-5 实跑确认的**误报**）：裸词集合把合规的反向边界句判成冲突——
    # §9 写「本设计**不适用于**系统级改造」，旧判据命中 `系统级` → 报"出现多种取值
    # ['模块级','系统级']"；`(?<!非)` 只挡得住"非系统级"，挡不住"不适用于…"。
    # 现要求**声明语气线索**（层级/档位/定位/属于/为/按/采用）紧邻取值才算声明。
    # 已知收窄：不带线索词的隐式声明不再被抓——宁可漏报一条，也不能把合规交付物判死。
    # v1.37.4 二次修（**我方 p1 探针实跑抓出**）：线索词不能进捕获组——否则"为模块级"与
    # "按模块级"会被算成**两种取值**，合规文档反而被判冲突（正是这条判据要防的误报）。
    # 捕获组只包取值，线索词用非捕获组。
    _CUE = r"(?:层级|档位|定位|属于|即为|为|按|采用)[ \t]*[：:]?[ \t]*"
    for name, pat in (
        ("层级声明", _CUE + r"(?<![非不无])(模块级|系统级)"),
        ("档位声明", _CUE + r"(?<![非不无])(参考文档|设计文档|施工规范|参考档|设计档|施工档)"),
    ):
        hits = re.findall(pat, doc_text)
        if len(set(hits)) > 1:
            violations.append("声明冲突（%s）：出现多种取值 %s" % (name, sorted(set(hits))))
    # v1.37.3：词表外的取值进 ⚠️ 未核——旧判据只认已知词，写"组件级""子系统级"时既报不出来、
    #   也不进未核（与"目录锚点塌陷"同性质：**识别失败被当成没问题**）。
    for label, pat, known in (
        ("层级", r"(?<!非)层级[：:]\s*([^\s，。；、（）()]+)", ("模块级", "系统级")),
        ("档位", r"(?<!非)档位[：:]\s*([^\s，。；、（）()]+)", ("参考文档", "设计文档", "施工规范", "参考档", "设计档", "施工档")),
    ):
        for raw in sorted(set(re.findall(pat, doc_text))):
            # v1.37.8：先剥掉 Markdown 强调符/反引号再比词表——`**层级：模块级**` 会被捕获成
            #   「模块级**」，于是**把声明加粗写反而进未核**（实跑本 skill 自己产出的计划文档
            #   即命中 2 条：层级与档位各一条）。强调符是排版，不是取值的一部分。
            v = raw.strip("*`_ \t\u3000")
            if v not in known:
                WARNINGS.append(
                    "%s声明取值「%s」不在已知词表 %s 内 → **该声明未核**（机器不认识这个取值，"
                    "不代表它没问题）" % (label, v, list(known)))
    return violations


# v1.37.3：SKILL.md 明文允许「表格可整体声明」（如"上表除标注 [假设] 的两行外，其余为 [推导]"），
#   而数字判据是逐行的 → 合规写法被判违规（实跑 F3 报 3 条）。声明行带标记时，其**紧随的那张表**
#   整表豁免；遇到非表格行即失效（声明只覆盖它紧邻的那张表，不无限外扩）。
BLANKET_DECL = re.compile(
    r"(?:上表|下表|本表|表中|表内)[^\n]{0,40}?(?:均为|一律|视为|全部为|其余为|除[^\n]{0,24}?外)")


def _blanket_covered(lines, lo, hi) -> set:
    """整体声明覆盖的行号集合（v1.37.3）。

    声明行带标记、且用了「上表/下表/本表…均为/一律/除…外」这类措辞时，它**紧邻的那张表**
    整表豁免——**上下两个方向都算**：SKILL.md 举的例子是"上表除…外，其余为 `[推导]`"
    （即声明在表**下方**），而实跑夹具 F3 把同样措辞放在了表**上方**。
    空行不打断相邻关系：F3 首版失败的原因就是空行把标记重置掉了（声明行与表头之间有空行）。
    """
    covered = set()
    for n in range(lo, hi):
        if not (BLANKET_DECL.search(lines[n]) and MARKER.search(lines[n])):
            continue
        k = n + 1                                    # 向下：空行后的紧邻表格
        while k < hi and not lines[k].strip():
            k += 1
        while k < hi and lines[k].strip().startswith("|"):
            covered.add(k)
            k += 1
        k = n - 1                                    # 向上：空行前的紧邻表格
        while k >= lo and not lines[k].strip():
            k -= 1
        while k >= lo and lines[k].strip().startswith("|"):
            covered.add(k)
            k -= 1
    return covered


def _estimate_section(doc_text: str):
    """定位第 3 节「量级与估算」的 (起行, 止行)；找不到返回 None。

    靠结构表规定的章节名定位（§3 = 量级与估算），章节边界用 §4 的起始行。
    v1.37.1：三种承载形态都认（`#` 标题／编号列表／加粗）——旧版只认 `#` 标题，而 SKILL.md 的
    文档结构表把 §3 写成 `3. 量级与估算`，照它写的交付物会被硬报"找不到第 3 节"。
    找不到**不报违规也不静默**：由调用方打 ⚠️「未核」提示（**跳过 ≠ 通过**）。
    """
    lines = doc_text.splitlines()
    # v1.37.3：候选逐个试、窗口非空才算数（旧实现取第一个命中就定锚点；目录行会抢占锚点 →
    #   窗口塌成 0 行 → §3 全部数字既不报、也不进 ⚠️。实跑 `audit_r3/F1-toc-window-miss.md` 确认：
    #   `0 violations` + 无 ⚠️ + exit 0，而 §3 里 120ms／45分钟／32MB 一个标记都没有。
    #   **"看齐了"和"看错地方"在输出上完全同形。**）
    # v1.37.4：但"窗口非空"只是个弱条件，两种**非空却错位**立刻绕过它（均由**实跑**确认）：
    #   ①目录条目下多一条缩进续行 → 假窗口变成 2 行（红队 R4-1）；
    #   ②§3 正文里出现 `4. 峰值内存：32MB` 这类编号项 → 命中 §4 起点，窗口在中间截断（红队 R4-2）；
    #   ③目录的 §3 行与 §4 行之间隔着别的行 → 窗口非空但整段是目录（我方 P5 探针）。
    #   现按可靠性分三级：
    #   ①**标题形态优先**（`## 3. xxx`）且取**最后一个**候选（目录在前、正文在后）——正文标题
    #     不会被目录行/列表项冒充，这是唯一能自动采信的形态；
    #   ②退而用"编号/加粗"形态时**打 ⚠️ 未核**（如实说没核，不许假装核了）；
    #   ③§4 终点同样先标题后编号；落在编号形态时**打 ⚠️ 未核**（R4-2 只能靠这条兜住）。
    for cands, head_form in (
        ([i for i, l in enumerate(lines) if SEC_ESTIMATE_HEAD.match(l)], True),
        ([i for i, l in enumerate(lines) if SEC_ESTIMATE_PLAIN.match(l)], False),
    ):
        for lo in reversed(cands):
            hi = len(lines)
            tail_note = None
            for j in range(lo + 1, len(lines)):
                if SEC_CONTRACT_HEAD.match(lines[j]):
                    hi = j
                    break
            if hi == len(lines):
                for j in range(lo + 1, len(lines)):
                    if SEC_CONTRACT_PLAIN.match(lines[j]):
                        hi = j
                        tail_note = (
                            "第 3 节的终点落在**编号形态**的行上（第 %d 行：「%s」）→ 该行若是 §3 正文里的"
                            "有序列表项，窗口会被从中间截断、后半段的估算数字不核；请把第 4 节写成 markdown 标题"
                            % (j + 1, lines[j].strip()[:40]))
                        break
            if hi == len(lines):
                # v1.40.0：找不到 §4 时**不能一路吃到文末**——实跑 chk_cand.md 确认：
                #   §5 对标表里的「命中数 8903」被当成 §3 的估算数字报违规。
                #   退而用「下一个 markdown 标题」收口，并如实打 ⚠️（不说"已核"）。
                for j in range(lo + 1, len(lines)):
                    if HEAD_ANY.match(lines[j]):
                        hi = j
                        tail_note = ("找不到第 4 节的起点 → 第 3 节的核验范围只能收到下一个标题"
                                     "（第 %d 行：「%s」）；若 §3 实际更长，请把第 4 节写成 markdown 标题"
                                     % (j + 1, lines[j].strip()[:40]))
                        break
            if hi - lo <= 1:
                continue
            if not head_form:
                WARNINGS.append(
                    "第 3 节**不是 markdown 标题形态**（命中第 %d 行：「%s」）→ 锚点可能被目录行/列表项"
                    "冒充，本节的数字标记核验**不作数**；请把 §3 写成 `## 3. 量级与估算`"
                    % (lo + 1, lines[lo].strip()[:40]))
            if tail_note:
                WARNINGS.append(tail_note)
            return (lo, hi)
    return None


def validate_numbers(doc_text: str) -> list[str]:
    """估算类数字必须带四类标记，或括注已定依据（v1.37.0 由空壳改为真判据）。

    判据按 SKILL.md 正文写死的清单实现：扫 `\\d+ms`／`\\d+%`／`\\d+ 万`／`\\d+ 字`／
    带单位的量（MB|GB|字节|token|篇|块…），逐个判定归属——是估算就补标记、
    是已定参数就括注依据、两者都不是就删掉。
    旧实现（v1.31.0~v1.36.0）只做了一次 findall 就 `return []`，两个分支都返回空列表，
    **永久 0 violations**，而 SKILL.md 把"数字标记"列为三项机械自检之一。
    """
    sec = _estimate_section(doc_text)
    lines = doc_text.splitlines()
    if sec is None:
        # v1.37.3：定位失败**既不当成"没违章"、也不退回全文扫描**——全文扫描会把用户原话里的
        #   时间描述（"一次几十分钟"）和"12 条测试"这类计数一并报成假阳性：实跑
        #   `examples/full-walkthrough.md` 被打回 2 处，两处都不是估算数字。
        #   **范围不可知就如实标未核**：main 因 WARNINGS 返回 2——既不静默，也不乱报。
        WARNINGS.append(
            "未能定位第 3 节「量级与估算」→ **数字标记这一项没有核验**（不等于通过；main 返回 2）；"
            "章节缺失、标题与结构表不一致，或**目录行抢占了章节锚点**时会发生。请人工确认该节是否存在")
        return []
    else:
        lo, hi = sec
    violations = []
    covered = _blanket_covered(lines, lo, hi)    # 整体声明覆盖的那张表：整表豁免
    for n in range(lo, hi):
        line = lines[n]
        if n in covered:
            continue
        ok = bool(MARKER.search(line) or FIXED_HINT.search(line))
        # v1.37.4（红队 R4-8 实跑确认）：`已定` 曾是**免检牌**——句中出现这两个字就放行，于是
        #   "已定参数须括注依据编号"这条规则在脚本里没有任何判据（docstring 却自述实现了它）。
        #   现在：裸写"已定"且该行带数字 = 违规；必须当场括注（`已定（依据 R1）`）。
        if BARE_FIXED.search(line) and not FIXED_HINT.search(line) and re.search(r"\d", line):
            violations.append(
                "行 %d：写了「已定」但**没当场括注依据**——「已定」不是免检牌，须写成「已定（依据 R1）」"
                "或「依据编号 …」；否则等于用两个字跳过整个标注要求 → %s" % (n + 1, line.strip()[:70]))
            continue
        # v1.37.4（评分组 🔴-4 实跑确认）：SKILL.md 的清单承诺扫「表格单元格里的裸整数」，而
        #   ESTIMATE_UNIT 要求带单位词 → `| 分块数 | 1200 |` 这类纯数字格从来不报。
        #   **文档承诺 > 脚本能力**正是这轮要清的东西，现按"独占一格的 3 位以上整数"补上。
        m_int = BARE_INT_CELL.search(line)
        if m_int and not ok:
            violations.append(
                "行 %d：表格里的纯数字格「%s」既没标记、也没括注已定依据——结构表要求「每个量都带单位」，"
                "这类独占一格的整数是最容易漏标的估算值；补单位+标记，或写清已定依据 → %s"
                % (n + 1, m_int.group(1), line.strip()[:70]))
            continue
        if not ESTIMATE_UNIT.search(line):
            continue
        if ok:
            continue
        if re.search(r"\[实测[-－]", line):
            violations.append(
                "行 %d：用了 `[实测-稳定]`／`[实测-单次]`——这两个是 **references 内专用**标注"
                "（见统一标注表），交付文档的估算数字只认四类 `[实测]`/`[假设]`/`[外源]`/`[推导]`"
                "或括注已定依据 → %s" % (n + 1, line.strip()[:70]))
            continue
        violations.append(
            "行 %d：估算类数字无四类标记、也未括注已定依据 → %s" % (n + 1, line.strip()[:70]))
    # 自述范围越界：写了"全文／所有数字"却全文一个标记都没有
    if re.search(r"(?:全文|所有)(?:的)?(?:数字|量)", doc_text) and not MARKER.search(doc_text):
        violations.append("自述「全文／所有数字」带四类标记，但全文没有任何 [实测]/[假设]/[外源]/[推导]")
    return violations


# v1.37.3 容错加粗/反引号（实跑 fake-skill 暴露）：旧正则要求版本号紧跟 `|` 或行首，
#   账本行写成 `| **v1.40.0** | …` 时匹配不到 → 取值回落到更早的行，
#   frontmatter 落后一条仍打印"已对账"、exit 0。
ROW_LEADING_VERSION = re.compile(r"^[ \t]*(?:#{1,6}[ \t]*|[-*+][ \t]*)?\|?[ \t]*(?:\*\*|`)?[ \t]*v(\d+)\.(\d+)(?:\.(\d+))?")


def _ledger_max_version(skill_path: str):
    """读 `references/verification-log.md`，取**行首版本号**的最大值 → (版本, 账本路径, 识别到的版本行数)。

    v1.37.1 改名实相符（独立复评打回）：旧实现对全文 `findall` + `max()`，而 docstring 与
    SKILL.md 都写"等于账本最末一行"——两者只在"最高版本恰好是最后一行"时等价，两头都会错：
    末尾新增一行预告（如 v1.38.0）会对正确的 SKILL.md 误报；正文行内提到更高版本号时，
    真正的落后反而漏报。现只认**行首版本号**（账本条目行 `| vX.Y.Z | …` 或 `vX.Y.Z …`），
    行内提及（历史叙述、举例）一律不计。

    v1.51.0：**解析规则与第 7 项「可核性」统一**。此前这里只拼 `文档目录/references/…` 一层，
    而证据可核性走的 `_find_ledger()` 是「文档目录 → 逐级祖先 → CWD」。
    同一份账本两套找法，后果是：SKILL.md 一旦不在 skill 根目录（比如改版时另存一份去对比），
    `--skill` 会报"读不到账本"并打印一个**另一个检查明明能找到的路径**——
    那读起来像"文件缺失"，其实是本脚本内部两套规则打架。**同一事实只许有一处解析规则。**
    """
    found, text = _find_ledger(skill_path)
    shown = os.path.join(os.path.dirname(os.path.abspath(skill_path)),
                         "references", "verification-log.md")
    if text is None:
        return None, shown, 0
    vs = [m.groups() for m in (ROW_LEADING_VERSION.match(l) for l in text.splitlines()) if m]
    if not vs:
        return None, found, 0
    best = max((int(a), int(b), int(c or 0)) for a, b, c in vs)
    return "%d.%d.%d" % best, found, len(vs)


# v1.51.0：**自述项数**也必须对账。
#   来历：v1.48.0 才把 SKILL.md 的「七项」改成「十一项」——脚本早已是 11 项，
#   而 SKILL.md 资源清单行还写着七项，靠人记得同步。两种漂移都坏：
#   **多报一项"我核了什么"比少报更危险**（_CAVEAT 旁边那条注释），
#   而少报会让使用者以为某处核过了、其实没核。这里把四个人工同步点并成一次机检：
#   ①`_CAVEAT` 自称的项数 ②它括注里枚举的清单条数 ③SKILL.md 资源行的自述项数
#   ④脚本 `main()` 交付分支里**实际调用**的 validator 个数（AST 数出来）。
_CN_NUM = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
           "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s: str) -> int:
    """把「十一／十二／9」这类自述数字转 int；认不出返回 -1。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if len(s) == 2 and s[0] == "十" and s[1] in _CN_NUM:
        return 10 + _CN_NUM[s[1]]
    return _CN_NUM.get(s, -1)


def _impl_validator_counts() -> tuple[int, int]:
    """AST 数出 `main()` 交付分支里实际调用的 validator，返回 (机械项数, 提示项数)。

    为什么不维护"项名 → 函数名"映射表：**那张表本身会漂移，而漂移正是要查的东西**
    （写死映射等于把结论抄一遍，重构函数名时两边一起改成错的）。
    归属按调用点判：进 `ADVISORY.*` 的算提示项；进 `WARNINGS.*` 的不计项
    （`audit_evidence_resolvability` 是第 7 项"可核性"的第二层，不是独立一项）。
    """
    import ast
    with open(os.path.abspath(__file__), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    main_fn = next((n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    if main_fn is None:
        return -1, -1
    branch = None
    for node in main_fn.body:
        if isinstance(node, ast.If) and "--skill" in ast.unparse(node.test):
            branch = node.orelse
            break
    if branch is None:
        return -1, -1
    allc, advisory, warned = set(), set(), set()
    for node in ast.walk(ast.Module(body=branch, type_ignores=[])):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            bucket = {"ADVISORY": advisory, "WARNINGS": warned}.get(node.func.value.id)
            if bucket is not None:
                for sub in ast.walk(node):
                    if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                            and sub.func.id.startswith("validate_")):
                        bucket.add(sub.func.id)
        if isinstance(node.func, ast.Name) and node.func.id.startswith("validate_"):
            allc.add(node.func.id)
    return len(allc - advisory - warned), len(advisory)


def validate_skill_self(doc_text: str, doc_path: str = "") -> list[str]:
    """SKILL.md 自身检查（v1.29.0 新增；v1.30.0 加分组；v1.32.0 改为「禁止第二处出现」；**v1.37.0 加"第一处必须仍然正确且可达"**）。

    为什么 v1.37.0 又要加：v1.32.0 的思路（正文不写这些值 → 正文里出现即违规）是对的，
    但它把检查器的作用面**绑在了被删掉的那处文本上**——第二处一删，三条正则永不命中，
    检查器就永久放行：frontmatter 的 version 因此落后账本多个版本而无人发现。
    **"消灭产生条件"必须同时补一条"确认残留的那个值仍然正确"，否则消灭的是检查能力本身。**
    所以现在查四件事：①version 唯一 ②正文禁止出现声明式取值 ③权威位置哨兵必须存在
    ④version 必须等于账本最新一条版本行（行首版本号的最大值）。
    """
    violations = []
    # 1) frontmatter 的 version 必须存在且唯一，且与账本同步
    fm = re.findall(r"^version:\s*([\d.]+)[ \t]*$", doc_text, re.M)
    if len(fm) != 1:
        violations.append("frontmatter `version:` 应恰好 1 处，实际 %d 处：%s" % (len(fm), fm))
    elif doc_path:
        ledger_ver, ledger_path, ledger_rows = _ledger_max_version(doc_path)
        if ledger_ver is None:
            violations.append(
                "在「文档目录／逐级祖先／CWD」下都找不到账本 `references/verification-log.md`"
                "（按文档同目录算应为 `%s`）→ 版本无从对账；确认账本存在且含 `| vX.Y.Z | …` 形态的行首版本号"
                % ledger_path)
        elif fm[0] != ledger_ver:
            violations.append(
                "frontmatter `version: %s` 与账本最新版本行 `v%s` 不一致——唯一的权威值必须与内容同步，"
                "否则它只是唯一的错值（旧版 --skill 只查「正文有没有第二处」，第二处删掉后这类落后再也查不出来）"
                % (fm[0], ledger_ver))
    # 2) frontmatter 之后的正文里，禁止出现"声明式"的版本/区间/条数
    parts = doc_text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else doc_text
    for name, pat in FORBIDDEN_IN_SKILL_BODY:
        hits = re.findall(pat, body)
        if hits:
            violations.append(
                "%s 不应出现在正文（值只许在唯一权威处，正文只留指向）—— 出现即产生不一致的条件：%s"
                % (name, sorted(set(hits))))
    # 3) 权威位置必须可达（存在性）：声明指向的文本必须真的在文件里
    for name, pat in REQUIRED_SKILL_ANCHORS:
        if not re.search(pat, body):
            violations.append(
                "找不到「%s」（哨兵 `%s`）——「声明唯一性」表指向的权威位置不存在，值就没有落点" % (name, pat))
    # 4) 硬约束列表的编号必须从 1 连续，无跳号重号；且条数 = 列表长度（不写数字）
    hb = body.find("**叙事线硬约束**")
    he = body.find(chr(0x1F6D1) + " STOP：交付前逐条核对")
    # v1.37.5（第五轮独立评审 🟡-5）：旧写法找不到结束锚点时 `he = len(body)`，
    #   于是文末「已知限制」小节的 `1. **`/`2. **`/`3. **` 会被并进 nums →
    #   报出"硬约束编号不连续"的**假阳性**。锚点缺失本身已由第 3 步
    #   （REQUIRED_SKILL_ANCHORS）报违规，这里不再拿 len(body) 兜底：
    #   宁可说"这段核不了"，也不要用错区间去报假缺陷。
    if hb >= 0 and he > hb:
        nums = [int(x) for x in re.findall(r"^(\d+)\. \*\*", body[hb:he], re.M)]
        if nums and nums != list(range(1, len(nums) + 1)):
            violations.append("硬约束编号不连续：%s" % nums)
    # 5) 自述项数必须与实现对账（v1.51.0）
    #    锚点缺失也算违规，且措辞要指向"对账"，不指向内容——理由同本函数开头 v1.32.0 的教训：
    #    **正则永不命中 = 检查器永久放行**，那比报错更接近故障。
    impl_mech, impl_adv = _impl_validator_counts()
    caveat = re.search(r"只覆盖\s*(\d+)\s*项机械检查（([^）]*)）", _CAVEAT)
    if caveat is None:
        violations.append(
            "`_CAVEAT` 里找不到「只覆盖 N 项机械检查（…枚举…）」这一句 → 自述项数无从对账；"
            "改这句措辞时请同步本检查的正则（它查的就是「自述与实现是否一致」）")
    else:
        claimed = int(caveat.group(1))
        enumerated = len([x for x in caveat.group(2).split("／") if x.strip()])
        if claimed != enumerated:
            violations.append(
                "`_CAVEAT` 自称 %d 项，括注里只枚举了 %d 条（%s）——**自述的总数与自己的清单不符**"
                % (claimed, enumerated, caveat.group(2)))
        m2s = re.findall(
            r"\*\*(十[一二三四五六七八九]?|[零一二三四五六七八九]|\d+)\s*项机械自检"
            r"\s*\+\s*(十[一二三四五六七八九]?|[零一二三四五六七八九]|\d+)\s*项提示项", body)
        if not m2s:
            violations.append(
                "SKILL.md 资源清单行里找不到「**N 项机械自检 + M 项提示项**」这一句 → 无从与实现对账；"
                "这句话是使用者判断「脚本替我核了多少」的唯一入口，不要改掉它的形态")
        else:
            # 声明唯一性同样适用于**自述能力**：本 skill 的纪律是"别处只准写『见 X』，不准重述取值"，
            #   两处都写项数时，改一处漏一处就会让读者读到两个不同的"N"——而这里正是那个"N"的家。
            if len(m2s) > 1:
                violations.append(
                    "「**N 项机械自检 + M 项提示项**」这句话在 SKILL.md 里出现 %d 处——"
                    "**自述能力也必须唯一**（只保留资源清单行那一处，别处写「见资源清单」）" % len(m2s))
            g1, g2 = m2s[0]
            doc_mech, doc_adv = _cn_to_int(g1), _cn_to_int(g2)
            if doc_mech != impl_mech:
                violations.append(
                    "SKILL.md 自称「%s项机械自检」，而 `main()` 交付分支实际调用 %d 个 validator —— "
                    "**自述能力与实际能力已漂移**（v1.48.0 的「七项」就是这样落后了四个版本）"
                    % (g1, impl_mech))
            if doc_adv != impl_adv:
                violations.append(
                    "SKILL.md 自称「%s项提示项」，实际 %d 项（只进 `ADVISORY`、不影响退出码）"
                    % (g2, impl_adv))
            if claimed != doc_mech:
                violations.append(
                    "两处自述不一致：`self_check.py` 的 `_CAVEAT` 说 %d 项，SKILL.md 说 %s项"
                    % (claimed, g1))
    return violations


# ============ 第 6 项：状态否定的证据（v1.37.9 / P0-3） ============
# **本脚本第一条内容级判据**：前 5 项核的都是"引用得对不对"，这一项核"说的对不对"。
# 来历（它存在的唯一理由，别删）：本 skill 自己产出的计划文档跑出 `0 violations / exit 0`，
#   而里面写着「无并发保护」——事实上是「有原子替换写、无跨进程并发控制」。
#   **「没有 X」和「有 X」是同一种论断**，都该有证据。
# 判定为 ⚠️ 未核而不是违规：否定句在决策语境里合法（"不做 X"是选择，不是断言），
#   机器分不清"选择不做"和"断言没有"，所以只要求**同行能指出证据**，不直接判错。
NEGATION_CLAIM = re.compile(
    # v1.40.0 扩词（独立评审实跑：13 句非法只抓到 3 句 = 70% 漏报）：
    #   ①`无` 后面允许跟空格/拉丁词（"无 Redis 依赖"）；②补 `缺少|暂无|不具备`（原只有"缺失"）
    #   ③**尾部可为零**——但只在该否定词后面紧跟标点/空白/行尾时才算（"审计轨道不存在。"、"该能力缺失。"）
    #     否则 `无` 会把每个"无X"都捞进来（"无效"这类）。这是"抓得到句尾否定"与"不炸"之间的折中。
    r"(?:无|没有|不存在|缺失|缺少|暂无|不具备)"
    r"(?:[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9_\- ]{0,13}|(?=[，。；、,.;:！？!?\s]|$))"
    r"|未(?:实现|接入|覆盖|涉及|纳入|包含|提及|跑过|测过|验证|使用|提供|支持|定义|编号|落点|记录|给出|发现|处理|接通|跑|测|出现|生效|落地)")
# 豁免三类：①规则/选择句（"禁止 X"是要求，不是论断）②模态词（"无需/无法"不是对世界的断言）
#          ③同行已带证据或标记
NEGATION_EXEMPT = re.compile(
    r"禁止|不得|不要|不许|不准|不做|不引入|不写|不采用|不修改|不碰|不重述|别[用把改]"
    r"|无法|无需|无论|无关|不限|不宜|不必|不适用|不参与|不构成|不影响"
    r"|\[(?:实测|假设|外源|推导|待确认|未核|推断)\]"
    r"|依据编号|账本v[\d.]|`[RDCKH]\d+`|`L0-[PSCD]\d+`|repo/"
    # 本地代码引用也算证据（`business_tools.py:141-147`）：来源封闭域是**交付文档来源列**的规则，
    # 这里只问"这句话有没有指向可查的东西"——指到本地某文件的某一行，就是可查的。
    r"|[\w./\\-]+\.(?:py|md|json|toml|sql|yml|yaml|ini|cfg|txt|env|ts|tsx|js|jsx):\d+"
    # v1.40.0 补（独立评审实跑抓到的两处，都是"正文许诺了、脚本没实现"）：
    #   ④**正文许诺的出路必须真的生效**：SKILL.md 写「改成『本次未核：…』是合法出路」，
    #     而旧豁免只认 `[未核]` 方括号形态 → 按正文改完照样挨警告。**假出路比没出路更坏**。
    r"|本次未核[：:]"
    #   ⑤正当术语白名单（"无侵入/无状态/无锁"是设计属性，不是对世界的断言——实跑 8 句正当表述里 3 句被误报）
    r"|无(?:侵入|状态|锁|副作用|歧义|损|限|环|差别|感知|感)"
    #   ⑥范围声明（"本文未覆盖灰度发布"说的是文档边界，不是功能缺失）
    r"|未(?:覆盖|涉及|纳入|包含|提及)"
    #   ⑦**章节不可用声明**（v1.56.4）：骨架检查规定的合法出路是 `§N N/A：<具体原因>`，
    #     但原因句最自然的措辞就是「本需求无未解项」「没有接入外部仓库」——于是**按正文
    #     写的形态去改，改完照样被本项提示**（实测 4 种写法 4 种全中）。这与 ④ 同源：
    #     正文许诺的出路必须真的生效，否则是假出路。作用域只到**声明式**（`N/A：` 带冒号），
    #     真实论断「本方案没有并发保护。」不含该形态，仍会被抓。
    r"|N/A\s*[：:]"
    #   ⑧**纯占位行**（v1.56.4）：整行只有一个否定词 + 标点（「无。」「暂无。」）时，
    #     它说的是"本节没有内容"，不是"世界上没有某物"——没有可被证据支持或反驳的命题。
    #     只在**整行就是它**时豁免，句中出现的「无 X」不受影响。
    r"|^\s*(?:无|暂无|没有|不适用|待补|N/A)[。.；;，,]?\s*$")


def validate_negation_claims(doc_text: str) -> list[str]:
    """状态否定（无 X／没有 X／未实现 X）也是论断，必须能指出证据 → 返回 ⚠️ 未核项列表。

    只扫**正文**：跳过代码块、标题、表格分隔行。限量输出（超过 8 处只列前 8 处 + 总数），
    避免一次报几十条把真缺陷淹掉——这条判据的价值在"让人去看"，不在"报得多"。
    """
    hits: list[tuple[int, str]] = []
    in_code = False
    for n, line in enumerate(doc_text.splitlines(), 1):
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not s or s.startswith("#"):
            continue
        if SEP_ROW.match(s.strip("| \t")):
            continue
        if NEGATION_EXEMPT.search(line):
            continue
        m = NEGATION_CLAIM.search(line)
        if m:
            hits.append((n, m.group(0)))
    if not hits:
        return []
    shown = hits[:8]
    out = [
        "行 %d：出现状态否定「%s」，但同行没有来源标签或标记 → **该否定是论断，不是事实**"
        "（「没有 X」和「有 X」一样需要证据：补来源标签、或改成「本次未核：…」、或删掉这个否定）"
        % (n, claim) for n, claim in shown]
    if len(hits) > len(shown):
        out.append("（另有 %d 处同类未列出——先修上面这些，别一次改几十处）" % (len(hits) - len(shown)))
    return out


# ============ 第 6 项：候选发现记录（v1.40.0） ============
# 来历：v1.38.0 把「取回条数 ≥ 命中数」写进正文并自称**可机械核**，而脚本一行都没碰它
#   （独立评审实跑 + grep 证明：`total_count|perPage|命中数|取回条数` 在本脚本 0 命中）——
#   那是空头承诺：后来的维护者会信这四个字，以为漏检已被机器看住。
# 这一项把它做实：只认**候选发现记录表**（表头同时含「命中数」与「取回条数」）。
# 判据：标了「发现」的行，`取回条数 < 命中数` 且未标「已换词」→ 违规。
#   **不设魔法阈值**：容量不够就换词并把换词记下来，而不是拿一个未校准的数字当豁免线
#   （v1.38.0 曾把阈值 30 写在"运行时不加载"的账本里，执行者根本读不到——已撤销）。
# 表不存在不算违规、但进 ⚠️ 未核（由调用方判）：**「没这张表」与「这张表全对」必须看得出区别。**
CAND_HEADER_HITS = re.compile(r"(?:^|\s|\|)命中数(?:\s|\||$)")
CAND_HEADER_FETCHED = re.compile(r"(?:^|\s|\|)取回条数(?:\s|\||$)")
CAND_HEADER_CHANNEL = re.compile(r"(?:^|\s|\|)通道(?:\s|\||$)")
CAND_SWITCHED = re.compile(r"已换词|换词后|已分页|分页看完")


def _cand_switched(row: str) -> bool:
    """「已换词／已分页」豁免必须看**肯定**用法。

    来历（v1.53.0，eval 03 实跑）：一份真实产出物写的是「**未**完成：既**未分页看完**、
    也未再换词」，而 `CAND_SWITCHED` 匹配到被否定的「分页看完」→ 把它当豁免，
    「取回 20 < 命中 54」这个**唯一真正失败的形式缺陷被静默放过，exit 0**。
    这与本脚本反复治理的「假绿」同源：判据能匹配词语，却读不懂否定。
    """
    for m in re.finditer(r"已换词|换词后|已分页|分页看完", row):
        if not re.search(r"未|没|不再|尚未|不曾|从未", row[max(0, m.start() - 10):m.start()]):
            return True
    return False


def _first_int(cell: str):
    m = re.search(r"\d[\d,]*", cell)
    return int(m.group(0).replace(",", "")) if m else None


def validate_candidate_discovery(doc_text: str) -> tuple[list[str], bool]:
    """返回 (违规列表, 是否见到候选发现记录表)。"""
    violations: list[str] = []
    seen_table = False
    in_table = False
    col: dict[str, int] = {}
    for n, line in enumerate(doc_text.splitlines(), 1):
        s = line.strip()
        if not s.startswith("|"):
            in_table, col = False, {}
            continue
        cells = table_cells(s)
        if not in_table:
            in_table = True
            col = {}
            for i, c in enumerate(cells):
                if CAND_HEADER_HITS.search(c):
                    col["hits"] = i
                elif CAND_HEADER_FETCHED.search(c):
                    col["fetched"] = i
                elif CAND_HEADER_CHANNEL.search(c):
                    col["chan"] = i
            if "hits" in col and "fetched" in col:
                seen_table = True
            continue
        if "hits" not in col or "fetched" not in col or max(col.values()) >= len(cells):
            continue
        if SEP_ROW.match(cells[col["hits"]]):
            continue
        if "chan" in col and "核实" in cells[col["chan"]] and "发现" not in cells[col["chan"]]:
            continue
        if _cand_switched(s):
            continue
        hits = _first_int(cells[col["hits"]])
        fetched = _first_int(cells[col["fetched"]])
        if hits is None or fetched is None:
            continue
        if fetched < hits:
            violations.append(
                "行 %d：候选发现记录「取回条数 %d < 命中数 %d」且未标「已换词」→ **这就是「只取前 N 条」"
                "的形式缺陷**（实测它漏掉过 81★ 的仓库）：要么把 perPage 调大／分页看完，要么换更具体的"
                "机制词并在表里记下换词" % (n, fetched, hits))
    return violations, seen_table


# v1.41.0 新增（第 7 项机械检查）：标记与证据必须配套。
# 为什么：在 v1.41.0 之前，`MARKER` 那一项只问"这个数字有没有带标记"——**带了就过**。
#   于是 `[实测]` 退化成一张免检通行证：把数字统一打上 `[实测]`，六项检查全部放行。
# 实测教训（可复核）：本 skill 自己产出的「可观测性方案」里，
#   `约 12 条 span`（4 次模型调用 + 2 个工具 + HTTP 层的**加法推算**）
#   与 `排障演练可回答的问题数 3 个`（**将来**才验收的 `V7`）都标了 `[实测]`，
#   而当时六项检查一处都没抓到 —— 正文写了"标记要有依据"，机器不查，就等于靠自觉。
# 判据：`[实测]`／`[外源]` 是**对世界的断言**，必须同行能指出证据在哪；
#   `[假设]`／`[推导]` 不要求（它们本来就承认自己不是事实）。
# 证据形态：`文件:行`／`文件`／`repo/...`／`账本 vX.Y`／`H<n>`（探活编号）／URL。
#   **只指向本文档内部的小节号不算证据**——那是"我在别处也说过"，不是测量。
# v1.56.23：扩展名清单**只定义这一次**。此前它同时写在 `EVIDENCE_FOR_MARKER`（本处）与
#   `_LOCAL_EVIDENCE`（下方）两个正则里，两份拷贝必然漂移——盲跑 6 就撞上了：`.env` 只加到
#   一处，于是「⚠️ 未核项」通道放行、而「❌ 标记与证据配套」通道照样报违规，同一个路径
#   在同一个脚本里有两个结论。（另：`SKILL.md:401` 是**第三处**，由
#   `.eval/probe_evidence_ext.py` 的 [3] 断言它与这里逐项一致。）
EVIDENCE_EXTENSIONS = ("py", "md", "json", "toml", "sql", "yml", "yaml", "ini", "cfg",
                       "txt", "env", "ts", "tsx", "js", "jsx")
# v1.56.24：扩展名后面必须**不是词字符**（`(?![\w])`）。没有它，`chroma.sqlite3` 会先匹配到
#   扩展名 `sql`、被截成 `chroma.sql`，于是报「`chroma.sql` 不存在」→ 假 ⚠️（盲跑 7 实测）。
_EVIDENCE_EXT_ALT = "|".join(EVIDENCE_EXTENSIONS)
EVIDENCE_FOR_MARKER = re.compile(
    r"(?:[\w./\\-]+\.(?:%s)(?![\w])(?::\d+)?" % _EVIDENCE_EXT_ALT +
    r"|repo/"
    r"|账本\s*v?\d"
    r"|`?H\d+`?"
    r"|https?://)"
)
# v1.60.2 缺陷 e：同一份「本地证据扩展名」清单曾四处承载、两个取值
#   （`EVIDENCE_EXTENSIONS` 15 个 / `ALLOWED_SOURCE_PATTERNS` 12 个 / `NEGATION_EXEMPT` 12 个
#   / `SKILL.md` 15 个）。后果是**照 SKILL.md 写 `来源：config.txt:3` 会被判「不在封闭域内」**
#   —— 正文让执行者这么写、脚本判这么写非法，比"少报未核"更硬。
#   这里把两处手抄串钉回权威常量：以后再改 `EVIDENCE_EXTENSIONS` 而忘改它们，import 就失败。
_EXT_GROUP = re.compile(r"\(\?:([a-z|]+)\)")


def _ext_set_of(pattern: str):
    m = _EXT_GROUP.search(pattern)
    return set(m.group(1).split("|")) if m else set()


_LOCAL_SRC_RE = [p for p in ALLOWED_SOURCE_PATTERNS if p.startswith("^[A-Za-z0-9_")]
assert len(_LOCAL_SRC_RE) == 1, "来源白名单里本地文件正则应恰 1 条，实为 %d" % len(_LOCAL_SRC_RE)
if _ext_set_of(_LOCAL_SRC_RE[0]) != set(EVIDENCE_EXTENSIONS):
    raise SystemExit("扩展名漂移：来源白名单 %s ≠ EVIDENCE_EXTENSIONS %s"
                     % (sorted(_ext_set_of(_LOCAL_SRC_RE[0])), sorted(EVIDENCE_EXTENSIONS)))
if _ext_set_of(NEGATION_EXEMPT.pattern) != set(EVIDENCE_EXTENSIONS):
    raise SystemExit("扩展名漂移：否定豁免 %s ≠ EVIDENCE_EXTENSIONS %s"
                     % (sorted(_ext_set_of(NEGATION_EXEMPT.pattern)), sorted(EVIDENCE_EXTENSIONS)))

STRONG_MARKER = re.compile(r"\[(?:实测|外源)\]")


def validate_marker_evidence(doc_text: str) -> list[str]:
    """`[实测]`／`[外源]` 必须同行指出证据（v1.41.0 新增的第 7 项）。

    只查这两种标记：`[假设]`／`[推导]` 自认不是事实，不要求外部证据。
    查**整行**而不是"紧跟在标记之后"，是为了避免"证据写在同一表格行的另一列"被误报。
    """
    violations = []
    in_code = False
    for lineno, line in enumerate(doc_text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        hit = STRONG_MARKER.search(line)
        if not hit:
            continue
        # 豁免：讲"标记体系"本身的行（欠账行固定格式、回填要求、标注说明）。
        #   本 skill 规定的欠账行就长这样：`本表数字均带四类标记（[实测]／…）`；
        #   交付物里也常写「…需在 P1/P9 跑完后**回填为** `[实测]`」这类要求句。
        #   它们是在**谈论标记**，不是在给某个数字下断言。实跑发现：漏掉这条豁免时，
        #   本 skill 自己规定的欠账行格式、以及旧交付物里的回填要求句都会被判违规
        #   （首轮 8 条里 1 条、旧交付物 4 条里 1 条属此类假阳性）。
        if re.search(r"四类标记|三类标记|标记口径|回填为|回填清单|标注为|改标|未标记即视为", line):
            continue
        # v1.48.3：账本行（`| v1.x.y | … |`）里的 `[实测]` 是**记录某次实测发生过的标签**，
        #   不是在给本表的数字下断言。自扫账本时它被判"没有同行证据"——一条假红。
        if re.match(r"^\|\s*\*{0,2}v\d+\.\d+", line):
            continue
        # v1.48.1 修假红：**反引号里的标记是在谈论标记，不是在用它**。
        #   实测 SKILL.md 的自述行「②`[实测]`／`[外源]` 引用的本地证据必须真的能核」被判违规——
        #   那句话说的事正是这条判据自己，却因为"标记同行没证据"挨了一次。
        if not STRONG_MARKER.search(re.sub(r"`[^`]*`", "", line)):
            continue
        if EVIDENCE_FOR_MARKER.search(line):
            continue
        violations.append(
            "行 %d：`%s` 同行没有可定位的证据（`文件:行`／`repo/...`／`账本 vX.Y`／`H<n>`／URL）"
            "——**标记是对世界的断言，不是免检通行证**；给不出证据就改标 `[假设]`／`[推导]`，"
            "或写「本次未核：…」→ %s" % (lineno, hit.group(0), line.strip()[:70]))
    return violations


# v1.46.0（机制修补：证据可以被伪造）——第 7 项只验"长相"，不验真假。
#   实测（可复核，5 个伪造用例全部通过 validate_marker_evidence）：
#     `[实测] 结论（见 infra/gateway.py:88）`      文件不存在、行号编造 → 放行
#     `[实测] 结论（见 totally/fake/path.py:1）`  路径纯编造        → 放行
#     `[实测] 结论（见 notes.md）`                连行号都没有      → 放行
#     `[实测] 结论（账本 v9.9.9）`                版本不存在        → 放行
#     `[外源] 结论（repo/nonexistent/proj#L1-L2）` 仓库不存在        → 放行
#   于是"标记不是免检通行证"这句被实现成了"多写一个像路径的字符串即可通行"。
# 判据：**本地可核的证据必须真的能核**——本地文件按「文档目录 → 逐级祖先 → CWD」解析；
#   账本版本按账本行首版本号查表。核不到 → ⚠️ 未核（不是违规，也不是通过，退出码 2）。
#   外部证据（`repo/…`／URL）**天然不可机核**，本函数不判——所以这轮修补只堵住"伪造本地证据"这一半，
#   剩下那一半只能靠人工，别把"未核项为 0"读成"证据全真"。
_LOCAL_EVIDENCE = re.compile(
    r"(?<![\w./\\-])([\w./\\-]+\.(?:%s)(?![\w]))(?::(\d+))?" % _EVIDENCE_EXT_ALT)
# v1.56.23：扩展名清单改用上面那个常量（此前是第二份拷贝，两份必然漂移），并补 `env`。
# 来历：盲跑 6 要引 `STREAM_TIMEOUT_SECONDS` 的**实测取值**，而那个值只在 `.env` 里，
# 白名单没有 `env` → 一条 `[实测]` 无合法出处，**首跑直接报硬违规**。取证形态是 `路径:行号`
# 而不是值本身，所以接受 `.env`；但**配置项优先引提交进仓库的 `.env.example`**
# （`.env` 常被 gitignore，且可能含密钥）。
_LEDGER_EVIDENCE = re.compile(r"账本\s*v?(\d+\.\d+(?:\.\d+)?)")
# 证据根声明（v1.56.19）：交付物可以自己声明"我的本地证据相对哪个根解析"。
#   来历：盲跑 4 的终版产出物**从项目目录里跑**是 exit 0、零证据告警，**从别处跑**同一份文档
#   5 条 `[实测]` 本地证据**全部核不到**（`src/personal_assistant/models.py` 等）。
#   差别只在 CWD —— 也就是说这个判别器的结论**取决于你在哪运行它**。
#   一个判别器不能这样：同一份文档必须只有一个结论。形态（放在文件前 4000 字符内）：
#   `<!-- self_check: evidence_root=E:\projects\某项目 -->`
#   声明了根就**不再看 CWD**（否则"声明"只是又一个候选，结论仍随环境漂移）。
_ROOT_DECL = re.compile(r"<!--\s*self_check[\s:]+evidence_root\s*=\s*([^>]+?)\s*-->")
_MAX_ANCESTOR = 4
_LINECOUNT_CACHE: dict[str, int | None] = {}


def _line_count(path: str):
    """行数（用于核"行号是否越界"）；读不了返回 None（不因此报未核）。"""
    if path in _LINECOUNT_CACHE:
        return _LINECOUNT_CACHE[path]
    try:
        n = sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
    except OSError:
        n = None
    _LINECOUNT_CACHE[path] = n
    return n


def _evidence_roots(doc_path: str) -> list[str]:
    roots, here = [], os.path.dirname(os.path.abspath(doc_path))
    for _ in range(_MAX_ANCESTOR + 1):
        roots.append(here)
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    cwd = os.getcwd()
    if cwd not in roots:
        roots.append(cwd)
    return roots


def _find_ledger(doc_path: str):
    """按文档目录向上找 `references/verification-log.md` → (路径, 文本)；找不到返回 (None, None)。"""
    for root in _evidence_roots(doc_path):
        cand = os.path.join(root, "references", "verification-log.md")
        if os.path.exists(cand):
            try:
                return cand, open(cand, encoding="utf-8").read()
            except OSError:
                return None, None
    return None, None


def _ledger_versions(doc_path: str):
    """返回账本的行首版本号集合；找不到返回 None。"""
    _, text = _find_ledger(doc_path)
    if text is None:
        return None
    return set(re.findall(r"(?m)^\|\s*\*{0,2}v(\d+\.\d+(?:\.\d+)?)", text))


def audit_evidence_resolvability(doc_text: str, doc_path: str) -> list[str]:
    """第 7 项补强（v1.46.0）：`[实测]`／`[外源]` 引用的**本地**证据必须真实存在。"""
    warnings = []
    declared = [m.group(1).strip() for m in _ROOT_DECL.finditer(doc_text[:4000])]
    declared = [d for d in declared if os.path.isdir(d)]
    anchor = _evidence_roots(doc_path)
    if declared:
        # 声明了证据根就**不再看 CWD**（见 `_ROOT_DECL` 的来历）：否则"声明"只是又添一个
        # 候选根，同一份文档的结论照样随"你在哪个目录跑脚本"而变。
        anchor = [r for r in anchor if r != os.getcwd()]
    roots = declared + anchor
    ledger = _ledger_versions(doc_path)
    in_code = False
    for lineno, line in enumerate(doc_text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code or not STRONG_MARKER.search(line):
            continue
        if re.search(r"四类标记|三类标记|标记口径|回填为|回填清单|标注为|改标|未标记即视为", line):
            continue
        bad = ""
        # `repo/owner/name:path.py` 与 URL 是**外部**证据（本机核不了，口径见 `_CAVEAT`）。
        # 但 `_LOCAL_EVIDENCE` 会从那个冒号之后开始匹配到 `path.py`——那个 match 的前缀不是
        # `repo/`，于是被当本地路径去核 → 假 ⚠️（盲跑 7 实测；而来源封闭域**恰恰规定**
        # 外部路径要写成 `repo/owner/name:path` 形态，两条规则互斥）。修法：**先把外源 token
        # 抹掉再扫**——在循环里判断前缀永远晚一步，抹掉才是从根上不让它进来。
        scan = re.sub(r"(?:repo/|https?://)[^\s`）)】]*", " ", line)
        for mm in _LOCAL_EVIDENCE.finditer(scan):
            name = mm.group(1)
            if name.startswith(("repo/", "http")):
                continue
            hit = next((os.path.join(r, name) for r in roots
                        if os.path.exists(os.path.join(r, name))), None)
            if hit is None:
                bad = ("`%s` 在解析根下都不存在（试过：%s）"
                       % (name, "；".join(roots)))
                break
            num = mm.group(2)
            if num:
                total = _line_count(hit)
                if total is not None and int(num) > total:
                    bad = ("`%s:%s` 行号越界（该文件只有 %d 行）" % (name, num, total))
                    break
        if bad:
            warnings.append(
                "行 %d：`[实测]`／`[外源]` 引用的本地证据 %s → **无法核实**"
                "（不是违规，但也不是通过）；确认路径与行号，或改标 `[假设]`／写「本次未核：…」。"
                "若这些路径本来就相对**目标项目**而不是相对本文档，请在文件头声明证据根："
                "`<!-- self_check: evidence_root=<项目根绝对路径> -->`"
                "——声明后结论由文档决定，不再取决于你从哪个目录运行脚本"
                % (lineno, bad))
            continue
        for ver in _LEDGER_EVIDENCE.findall(line):
            if ledger is not None and ver not in ledger:
                warnings.append(
                    "行 %d：引用 `账本 v%s`，但账本里没有对应的行首版本号 → **无法核实**" % (lineno, ver))
                break
    return warnings


# v1.44.0 新增（第 8 项机械检查）：L3 施工路径的「通过信号」必须可判。
# 为什么加：一份 0 violations 的 L3 交付物交给**拿不到仓库的外部施工方**按字面实现，
#   结果四步里一步整层缺失、一条契约与另一步直接互斥。问题不是信息不足，是判据不是谓词：
#     · 通过信号写「只增减该 doc 的**块数量级**」——3→4 算过吗？3→40 呢？（判不了真假）
#     · 契约断言 `ledger 总块数 == collection.count()`，而没有任何步骤负责写 ledger（断链）
#     · 指令模板写「取消注释全量路径」——拿不到仓库的人无法执行（空指令）
#     · 「先删旧块再写新块」与「失败后旧块仍可召回」同时要求（Chroma 上不可兼得）
#     · 删除过滤用 `where={"doc_id": …}`，而写块 metadata 用 document_id（同一操作两套键名）
# 范围守卫：只当文档里存在「含『通过信号』列的步骤表」时才跑——无守卫的判据会在无关表格上
#   成片误报（v1.27.0 的教训）。不是 L3 交付物（需求、计划、复盘）一律不查。
L3_STEP_COL_SIGNAL = re.compile(r"通过信号")
L3_STEP_COL_TPL = re.compile(r"指令模板|步骤指令|提示词")
L3_NON_PREDICATE = re.compile(r"数量级|明显改善|大致|差不多|基本一致")
L3_PREDICATE_HINT = re.compile(
    r"\d|==|!=|>=|<=|≥|≤|不变|相等|一致|为\s*0|为0|非\s*0|非0"
    r"|断言|通过|报错|抛|命中|收敛|不通过|失败"
)
L3_FORBID_COMMENT_IN = re.compile(r"取消注释")
L3_DELETE_FIRST = re.compile(r"先删[^。；\n]{0,12}(?:再|后)写|先删旧块|先按[^。；\n]{0,20}删旧块")
L3_FAIL_KEEPS_OLD = re.compile(r"旧块(?:仍|必须仍|依然)[^。；\n]{0,10}(?:可召回|在|完整|保留)")
L3_WHERE_KEY = re.compile(r"where\s*=\s*\{\s*[\"'](\w+)[\"']")
# 谈论这条互斥本身的行（文档在解释"二者不可兼得"、或模板里写"不要先删后写"）不算违规。
L3_MUTEX_EXEMPT = re.compile(r"不可兼得|互斥|二选一|做不到|违约|不要先删|禁止先删")
# 「不要用取消注释来交付」是在**禁止**这种形态——引用禁令的行不算违规（实跑踩到：修好的文档
#   把禁令原文写进指令模板的"明确不要做"，被判成自己违规）。
L3_CANCEL_EXEMPT = re.compile(r"(?:不要|禁止|不得|别用|勿|不能)[^。；\n|]{0,30}取消注释")
# 两套删除顺序并存（v1.47.0）。**引号里的不算**：原文有「说明"先删后写"与"失败后旧块仍在"
#   不可兼得」这种句子，它是在引用一条规则、不是在下指令；不排除引号就会把正例判死。
#   同理排除「不要/禁止」开头的禁令句。
L3_DEL_FIRST_PRES = re.compile(r'(?<!["“「])先删[^。；\n]{0,12}(?:再|后)写')
L3_WRITE_FIRST_PRES = re.compile(
    r'(?<!["“「])先写[^。；\n]{0,40}?(?:再|后|成功后|全部成功)[^。；\n]{0,25}?(?:删|delete)')
L3_ORDER_EXEMPT = re.compile(r"(?:不要|禁止|不得|别用|勿|不可)[^。；\n|]{0,10}先(?:删|写)")
# 章节骨架检查的射程守卫用：出现 3 个以上才认为"这是一份 L3 交付物"（否则整项不适用）。
_L3_TOC_HINTS = ("需求与假设", "业务叙事", "决策依据", "量级与估算", "契约",
                 "对标", "模块全景", "施工路径", "验收", "已知限制")


def _l3_toc_hits(doc_text):
    """射程守卫（v1.48.1）：**按标题行**数 L3 章节名，而不是按全文出现。
    旧写法的漏洞：参考文档（如 l2-extraction-protocol）正文里本来就会**列举**这些章节名，
    于是被当成"这是 L3 交付物"→ 章节骨架检查开跑 → 每份参考文档都拿到 1 个假红。
    真实交付物的章节名长在标题行上（`## 1. 业务叙事…`／`**§2 决策依据**`），列举文本不长在。"""
    hits = set()
    for ln in doc_text.splitlines():
        s = ln.strip()
        if not (s.startswith("#") or s.startswith("**§") or s.startswith("**" + s[:0] + "§")):
            if not (s.startswith("**") and "§" in s[:6]):
                continue
        for h in _L3_TOC_HINTS:
            if h in s:
                hits.add(h)
    return len(hits)


def _order_hits(pat, lines, require_imperative=False):
    """真正在**下指令**的行号。两重豁免：
    ① 命中处前 14 字内有引号或禁令词 → 那是在引用/禁止这条规则，不是在要求它；
    ② require_imperative 时，命中处前面必须是「→」「：」「**」「|」或行首——
       原文的翻车信号列会写「③ 失败后旧块消失 → 用了先删后写」，那是在**列举错法**，
       位置判据（紧跟在「用了」后面）能把它和「→ 先删旧块再写新块」区分开。"""
    out = []
    for n, ln in enumerate(lines, 1):
        for m in pat.finditer(ln):
            pre = ln[max(0, m.start() - 14):m.start()]
            if re.search(r'["“「\']', pre) or re.search(r"(?:不要|禁止|不得|别用|勿|不可)", pre):
                continue
            if require_imperative and pre.strip() and not re.search(r"(?:→|[:：]|\*\*|\|)\s*$", pre):
                continue
            out.append(n)
            break
    return out


def _l3_key_defined(key: str, doc_text: str) -> bool:
    """键 K 有没有被定义：`K = …` 一行，或与 `metadata` 同行的反引号包裹。"""
    if re.search(r"(?m)^\s*%s\s*=" % re.escape(key), doc_text):
        return True
    if re.search(r"metadata[^\n]{0,120}`%s`|`%s`[^\n]{0,80}metadata"
                 % (re.escape(key), re.escape(key)), doc_text):
        return True
    return False


def validate_l3_signals(doc_text: str) -> list[str]:
    """L3 步骤表的「通过信号」必须可判 + 四条结构性断言（v1.44.0 新增的第 8 项）。"""
    lines = doc_text.splitlines()
    seen_step_table = False
    in_table = False
    col: dict[str, int] = {}
    rows: list[tuple[int, str, str]] = []   # (行号, 通过信号, 指令模板)

    for n, line in enumerate(lines, 1):
        s = line.strip()
        if not s.startswith("|"):
            in_table, col = False, {}
            continue
        cells = table_cells(s)
        if not in_table:
            in_table = True
            col = {}
            for i, c in enumerate(cells):
                if L3_STEP_COL_SIGNAL.search(c):
                    col["signal"] = i
                elif L3_STEP_COL_TPL.search(c):
                    col["tpl"] = i
            if "signal" in col:
                seen_step_table = True
            continue
        if "signal" not in col or col["signal"] >= len(cells):
            continue
        if SEP_ROW.match(cells[col["signal"]]):
            continue
        sig = cells[col["signal"]]
        tpl = cells[col["tpl"]] if "tpl" in col and col["tpl"] < len(cells) else ""
        rows.append((n, sig, tpl))

    if not seen_step_table:
        return []   # 不是 L3 交付物 → 本项不适用（不是"通过"）

    violations: list[str] = []

    # ① 通过信号必须是可判谓词
    for n, sig, tpl in rows:
        bad = L3_NON_PREDICATE.search(sig)
        if bad:
            violations.append(
                "行 %d：通过信号含非谓词措辞「%s」→ **判不了真假**；改成「量什么 + 阈值 + 方向」，"
                "例：「其余 doc 块数不变，且 Δcount == len(chunks_new)」" % (n, bad.group(0)))
        elif not L3_PREDICATE_HINT.search(sig):
            violations.append(
                "行 %d：通过信号里没有任何可判形态（数字／比较符／不变／断言／通过／报错）"
                "→ 换成谓词；「能跑通」不算信号 → %s" % (n, sig[:40]))
        # ② 禁止「取消注释某段现存代码」式指令
        if tpl and L3_FORBID_COMMENT_IN.search(tpl) and not L3_CANCEL_EXEMPT.search(tpl):
            violations.append(
                "行 %d：指令模板用「取消注释…」交付 → 对拿不到仓库的施工方是**空指令**，"
                "要把那段代码写进模板本身" % n)

    # ③ 互斥约束：先删后写 × 失败后旧块仍在（只在非豁免行之间判）
    del_first = [n for n, ln in enumerate(lines, 1)
                 if L3_DELETE_FIRST.search(ln) and not L3_MUTEX_EXEMPT.search(ln)]
    fail_old = [n for n, ln in enumerate(lines, 1)
                if L3_FAIL_KEEPS_OLD.search(ln) and not L3_MUTEX_EXEMPT.search(ln)]
    if del_first and fail_old:
        violations.append(
            "行 %d 与行 %d：文档同时要求「先删旧块再写新块」与「失败后旧块仍可召回」→ **二者不可兼得**"
            "（无多语句事务／原子 swap 时必然违约）；必须二选一并写明为何做不到另一条"
            % (del_first[0], fail_old[0]))

    # ④ 删除过滤用的键必须被定义（否则写块与删块各用一套键名 → 命中 0 块或 DuplicateIdError）
    for k in sorted(set(L3_WHERE_KEY.findall(doc_text))):
        if not _l3_key_defined(k, doc_text):
            violations.append(
                "删除过滤用 `where={\"%s\": …}`，但全文没有任何地方定义这个键（写块 metadata 用哪个键？）"
                "→ 施工方会用另一个键名写入，删除命中 0 块或抛 DuplicateIdError" % k)

    # ③-b 两套删除顺序并存（v1.47.0）：同一操作既写"先删后写"又写"先写后删" → 施工方各取一句，
    #   实现出来的原子性完全相反。**引号内的表述不算**——那是在讨论/引用某条规则（原正例里
    #   「说明"先删后写"与"失败后旧块仍在"不可兼得」正是引号内引用），一并把"不要/禁止"排除。
    #   为什么单列而不是并进 ③：③ 判的是"要求本身互斥"，这一条判的是"两处写法互相矛盾"——
    #   后者在文档里根本没有任何一处说"互斥"，读者两处都信。
    del_pres = _order_hits(L3_DEL_FIRST_PRES, lines, require_imperative=True)
    write_pres = _order_hits(L3_WRITE_FIRST_PRES, lines)
    if del_pres and write_pres:
        violations.append(
            "行 %d 写「先删旧块再写新块」、行 %d 写「先写新块再删旧块」→ **同一操作给了两套顺序**；"
            "施工方各取一句就会做出原子性相反的实现（先删的版本一失败就丢旧数据）。"
            "必须只留一套，另一处改成指回它" % (del_pres[0], write_pres[0]))

    return violations
#   来历：变异台架把「依据：D1」改成 D9（全文根本没有 D9）后，脚本 exit 0。
#   交付物一半的信誉建立在编号交叉引用上（来源列／依据列／⑭ 矩阵），而"编号指向不存在的条目"
#   恰恰是审阅者最难手工发现的一类——他得把每个编号都回查一遍，通常不会做。
#   定义处 = 以该编号为首格的表行（`| D1 | …`）或 `D1：…` 形态的行内定义；其余出现一律算引用。
_ID_ROW_DEF = re.compile(r"^\s*\|([^|\n]*)\|", re.M)
_ID_INLINE_DEF = re.compile(r"(?:\*\*|`)([DRCKH]\d{1,2})(?:\*\*|`)\s*[：:](?!\s*$)|\*\*([DRCKH]\d{1,2})\*\*\s*[：:]")
_ID_ANY = re.compile(r"(?<![\w\-])([DRCKH]\d{1,2})(?![\w\-])")


def _strip_fences(text: str) -> str:
    """剔掉 ``` 围栏块，但**只剔成对的**。

    v1.48.0 先用一条 `(?ms)^```.*?^```` 正则剔，实测未闭合围栏会被 `.*?` 一路吞到**下一处围栏**
    （不止本块），中间真实存在的编号引用因此不被检查——"该报的没报"比误报更难发现。
    改成状态机：遇到围栏就吞，遇到配对围栏才真正丢弃；扫到文件尾仍处于围栏内，
    说明这条围栏没闭合，把吞掉的内容原样还回去（宁可多查，不可少查）。
    """
    out, buf, in_fence = [], [], False
    for ln in text.splitlines(True):
        if re.match(r"[ \t]*```", ln):
            if in_fence:
                in_fence = False
                buf = []
            else:
                in_fence = True
            continue
        if in_fence:
            buf.append(ln)
        else:
            out.append(ln)
    if in_fence:
        out.extend(buf)
    return "".join(out)


def validate_reference_integrity(doc_text: str) -> list[str]:
    # 射程守卫（同 validate_section_skeleton）：只对 L3 交付物成立。任意文档里 `R3`／`D1` 可能只是
    #   普通代号（实测 CLI_使用与实现流程.md 因 "R3" 被判悬空 → 假红），故非交付物整项不适用。
    if _l3_toc_hits(doc_text) < 3:
        return []
    # 围栏代码块里出现的 `D1`／`C3` 不是引用（可能是二极管、电容、变量名）——先剔掉再扫。
    #   只剔 ``` 围栏，**不剔行内反引号**：来源列本来就把编号写成 `` `D1` ``，剔了等于把检查关掉。
    scan = _strip_fences(doc_text)
    # 定义处 = 表行**首格**里出现的编号（首格常写成 `[假设] H1`、`D1`、`` `C2` `` 等形态）+ 行内 `编号：…`
    defined = set()
    for m in _ID_ROW_DEF.finditer(scan):
        defined.update(_ID_ANY.findall(m.group(1)))
    for m in _ID_INLINE_DEF.finditer(scan):
        defined.add(m.group(1) or m.group(2))
    cited = set(_ID_ANY.findall(scan))
    missing = sorted(cited - defined, key=lambda s: (s[0], int(s[1:])))
    if missing:
        return ["引用了**不存在的编号** %s ——全文没有以它为首格的表行，也没有 `编号：…` 的定义行。"
                "来源列／依据列全靠这些编号指回条目，编号悬空等于**出处根本不存在**"
                "（比\"没写出处\"更难发现：读者会以为那一条已经被核过了）"
                % "、".join(missing[:8])]
    return []


# ── 第 10 项（v1.47.0）：章节骨架——0–9 十节不许整节消失 ──
#   来历：变异台架删掉整节 §0／§6／§9 后三次 exit 0。整节缺失比某节写错更难被发现：
#   评审者只读"有字的地方"，空白处不会引起注意——而 §0（档位声明）与 §9（已知限制）
#   恰恰是"读的人需要知道"的两节。
# ── 体裁声明（v1.48.2）：非交付物的文档可以自己说清楚"我不是交付物" ──
#   来历（目标第 3 轮）：拿脚本扫 skill 自己的 5 份 references，它们一律 exit 2（未核项），
#   输出里没有任何一个字说明"这些文件本来就不是交付物，别把 2 当门禁"。歧义就是缺陷：
#   下次有人把它们接进 CI，exit 2 会被读成"内容不达标"。
#   声明形态（放在文件前 2000 字符内即可）：`<!-- self_check: genre=reference -->`
_GENRE_REF = re.compile(r"<!--\s*self_check[\s:]+genre\s*=\s*(?:reference|参考文档|非交付物)\s*-->")
_SEC_HEAD = re.compile(r"^(#{1,3})[ \t]*(?:§[ \t]*)?([0-9]{1,2})(?=[.、．:：\s]|$)", re.M)


def validate_section_skeleton(doc_text: str) -> list[str]:
    # 射程守卫（v1.47.0 实跑回归踩到）：本检查只对**L3 交付物**成立。拿它对任意 Markdown 跑，
    #   一份正常文档会被判「缺少第 0–9 节」（实测 CLAUDE.md exit 1）。判据：正文里出现 3 个以上
    #   L3 章节名才认为这是交付物；否则整项不适用（返回空，不产生违规也不产生提示）。
    #
    # v1.56.19 两处修（来历：复核盲跑 4 回报的 F1——它说 `## 10. 交付状态` 被截成 `## 1`
    #   致第 9 节误判为空。**实测它说错了**：`([0-9])` 匹配 `1` 后前瞻遇 `0` 直接失败，
    #   整行不产生任何匹配。但顺着它查出了两个真问题——）
    #   ① 两位数节号**完全不可见**：`## 10.` 匹配不上，该标题下的内容被静默并入上一节
    #      （**静默误解析**比明确拒绝更坏：不报错，只是把内容算到别人头上）。改 `{1,2}`。
    #   ② 「只剩标题」**不区分「真空白」与「正文全在子节」**：`## 9.` 紧接 `### 9.1`
    #      时，`heads[i+1]` 就是那条子节标题，于是第 9 节的"正文"为空 → 报「只剩标题」，
    #      而内容明明都在 9.1–9.5 里。**这是假红**（实测：合成文档里节号序列 012345678999，
    #      内容全在子节时一样报红）。修法：下一个标题若是**本节的子节**（层级更深且节号相同），
    #      正文在子节里，不算空节。
    hits = _l3_toc_hits(doc_text)
    if hits < 3:
        return []
    have = set(m.group(2) for m in _SEC_HEAD.finditer(doc_text))
    missing = [n for n in "0123456789" if n not in have]
    out = []
    if missing:
        out.append("缺少第 %s 节（SKILL.md「文档结构」表定义 0–9 十节，章节编号以该表为唯一来源）"
                   "——整节缺失的形态是\"这里什么都没有\"，评审时最容易被读过去；"
                   "若该节本不适用，写 `§N N/A：<具体原因>` 保留标题，不要整节消失"
                   % "、".join(missing))
    # 只剩标题的空节：标题在、内容被清空。这种形态比"整节消失"更隐蔽——目录里看得见，
    #   读者以为有东西，实际翻过去是空白。判据：到下一个标题之间没有非空、非分隔线的内容，
    #   **且下一个标题不是本节的子节**（子节里的正文属于本节，见上方 ②）。
    heads = list(_SEC_HEAD.finditer(doc_text))
    empty = []
    for i, m in enumerate(heads):
        nl = doc_text.find("\n", m.start())
        body_start = len(doc_text) if nl < 0 else nl + 1
        end = heads[i + 1].start() if i + 1 < len(heads) else len(doc_text)
        body = doc_text[body_start:end]
        stripped = "\n".join(ln for ln in body.splitlines()
                             if ln.strip() and not re.fullmatch(r"[-*_\s|]+", ln.strip()))
        if stripped.strip():
            continue
        if i + 1 < len(heads):
            nxt = heads[i + 1]
            if len(nxt.group(1)) > len(m.group(1)) and nxt.group(2) == m.group(2):
                continue          # 正文在子节里（`## 9.` 紧跟 `### 9.1`），不是空节
        empty.append(m.group(2))
    if empty:
        out.append("第 %s 节**只剩标题、正文是空的**——目录里看得见、翻过去是空白，比整节删掉更难察觉。"
                   "补齐内容，或写 `§N N/A：<具体原因>`" % "、".join(empty))
    return out


# ── 第 11 项（v1.47.0）：账本版本引用必须存在 ──
#   来历：台架在**来源格**里写 `账本v9.9.9`，仍 exit 0——来源封闭域只查"像不像标签"，
#   不查"这个版本号在账本里有没有对应行"（第 7 项的可核性只管 `[实测]`／`[外源]` 行）。
def validate_ledger_citations(doc_text: str, doc_path: str) -> list[str]:
    ledger_path, _ = _find_ledger(doc_path)
    # v1.48.3（自扫暴露）：账本扫自己时必然报假红——它记录着"版本号编错一位"这个探针，
    #   正文里就写着 `账本v9.9.9`。自己引用自己的历史条目不是"外部引用悬空"。
    if ledger_path and os.path.abspath(ledger_path) == os.path.abspath(doc_path):
        return []
    ledger = _ledger_versions(doc_path)
    if ledger is None:
        return []
    bad = sorted({v for v in _LEDGER_EVIDENCE.findall(doc_text) if v not in ledger})
    if bad:
        return ["引用了账本里**不存在的版本** %s（`references/verification-log.md` 没有这些行首版本号）。"
                "`账本vX.Y` 作为来源标签的含金量全部来自「那一行真的存在」——版本号编错一位，"
                "引用就从「可追溯」变成「看起来可追溯」" % ("v" + "、v".join(bad[:8]))]
    return []


# 第 12 项（v1.53.0）：宣称贴了自检输出，就必须真有退出码——**占位符不是证据**。
#   来历：用本 skill 实跑 eval 03，真实产出物 §9.4 只贴了命令，§9.5 写着
#   「（本节由收口前的最后一次执行回填）」+ `【待回填】`，全文没有 `EXIT=`。
#   这比完全不贴更危险：读者看到"原样粘贴"四个字就默认证据在，实际是空头承诺。
#   射程守卫（老教训，v1.27.0）：只在**出现占位符或"原样粘贴"类声明**时才生效。
#   否则每份文档都被要求带退出码，等于把交付清单的一行变成人人必填，成片误报。
_PLACEHOLDER_RE = re.compile(r"【待回填】|待回填|【待贴】|【待填】|待补充输出|（待贴）")
_SELFCHECK_EXIT_RE = re.compile(r"EXIT\s*=\s*\d|退出码\s*[:：]?\s*[0-9]")
_SELFCHECK_CLAIM_RE = re.compile(r"原样粘|原样贴|附上自检|自检输出见|原样抄")
# 占位符必须落在**自检语境**里才算数（v1.53.0 实跑教训）：基线交付物里有一句
# 「此条已记入本节，**待回填到** `references/l1-search-recipes.md`」——那是对正文内容的欠账，
# 与"自检输出稍后贴"完全无关，却被无条件占位符规则判成硬违规。判据的作用域要能说出为什么。
_SELFCHECK_CTX_RE = re.compile(r"自检|self_check|EXIT|退出码")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")


def _section_head(lines: list[str], i: int) -> int:
    """从第 i 行往上找最近的标题行；返回该标题的索引（找不到则 0）。"""
    for j in range(i, -1, -1):
        if _HEADING_RE.match(lines[j]):
            return j
    return 0


def validate_selfcheck_trace(doc_text: str) -> list[str]:
    """第 12 项：自检留痕必须是**真输出**，不是"稍后回填"的公告。"""
    if _SELFCHECK_EXIT_RE.search(doc_text):
        return []
    lines = doc_text.splitlines()
    for i, ln in enumerate(lines):
        if _PLACEHOLDER_RE.search(ln):
            head = _section_head(lines, i)
            window = "\n".join(lines[head:i + 2])
            if not _SELFCHECK_CTX_RE.search(window):
                continue
            return ["行 %d：`%s` —— 这里是占位符，而全文没有 `EXIT=<n>`／`退出码：<n>`。"
                    "「稍后回填」的自检证据读作**没有证据**：当场跑一次、把末行与退出码粘上，"
                    "或把这段公告删掉" % (i + 1, ln.strip()[:60])]
    for i, ln in enumerate(lines):
        if _SELFCHECK_CLAIM_RE.search(ln) and re.search(r"self_check|自检", ln):
            return ["行 %d：`%s` —— 宣称贴了自检输出，但全文没有 `EXIT=<n>`／`退出码：<n>`。"
                    "要么当场贴，要么把这句删掉：**公告 ≠ 证据**" % (i + 1, ln.strip()[:60])]
    return []


# 第 13 项：承诺是否落地（v1.58.0）。
# 来历：施工方回访（用例 04 的超时重试交付物）实测——文档 §3.3 算出"保留的硬上限**必须大于** 363.5 秒"，
#   并在决策表给出目标值 480；而 `P1` 的指令是"不要改动 `.env` 与 `.env.example` 里的既有键"，
#   **全文没有任何一步落地这个 480**。原项目 `.env` 实为 300 → "3 次尝试跑满"会被流层先杀掉，
#   整条最坏路径形同虚设。**写进文档的承诺，与写进文档的步骤，是两份东西。**
# 判据形态（不靠"承诺"这个词——那是措辞）：只认**可核对的事实**——
#   ①该行同时有**要求语**（必须大于／不低于／应设为／建议…）**且**有**维度词**（上限／超时／阈值／间隔…）
#     或一个反引号标识符（配置键名）；②该数字**在全文只出现这一次**。
#   两条同时成立 = 这个取值在文档里没有任何落点。三重条件让射程很窄：只出现一次的普通数字
#   （行号、版本、次数）不会被卷进来，因为它们所在的行没有要求语。
_LAND_VERB = re.compile(
    r"必须大于|必须不低于|应大于|应不低于|不低于|不小于|应设为|应设置为|应改为|应调为|"
    r"建议(?:设为|设置为|改为|取|调为)?|至少\s*(?:为|设)")
_LAND_DIM = re.compile(r"上限|下限|超时|阈值|间隔|并发|重试|容量|批量|块数|条数|大小|时长")
_LAND_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")
# 施工路径章的标题行——**只扫它之前**的章节。
# 为什么必须截断：第一版没有截断，结果在盲跑 6 的 `P4` 行上误报一次——那一行自己就带通过信号
#   「在 60 秒至 **75** 秒之间发出 `error` 事件」，75 只出现一次是**因为它就是这条步骤的验收窗口**，
#   并不是"没有落点"。**判据必须知道自己在哪一段里说话**：承诺在分析章（§0–§6），落点在施工章（§7）。
# 第二版仍报同一条：标题写成 `## §7 分步实现路径`（`7` 与 `分步` 之间**没有点号**），
#   而正则硬要求 `[.、．:：]` → 截断点没找到、cut 停在文件尾，等于没截断。
#   **"正则要求了一种写法"这条老病根，这次犯在我自己刚写的截断正则上。** 现改为点号可选。
_LAND_STEPS_HEAD = re.compile(
    r"^[ \t]*(?:>[ \t]*)?(?:#{1,6}[ \t]*|\*\*[ \t]*§[ \t]*)(?:§[ \t]*)?\d*[ \t]*[\.、．:：]?[ \t]*"
    r"(?:分步实现路径|施工路径|分步实现|实现路径|施工步骤)")


def validate_promise_landing(doc_text: str) -> list[str]:
    """第 13 项：分析章里给出的**建议取值**，文档里必须有落点。"""
    if _l3_toc_hits(doc_text) < 3:
        return []                 # 非交付物不适用（与章节骨架／引用完整性同一射程守卫）
    lines = _strip_fences(doc_text).splitlines()
    cut = len(lines)
    for i, ln in enumerate(lines):
        if _LAND_STEPS_HEAD.search(ln):
            cut = i
            break
    counts: dict = {}
    for ln in lines:
        for m in _LAND_NUM.finditer(ln):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    hits = []
    for i, ln in enumerate(lines[:cut]):
        if not _LAND_VERB.search(ln):
            continue
        if not (_LAND_DIM.search(ln) or "`" in ln):
            continue
        for m in _LAND_NUM.finditer(ln):
            n = m.group(1)
            if counts.get(n, 0) > 1:
                continue          # 别处（含施工章）出现过 —— 有落点
            hits.append(
                "行 %d：`%s` —— **这个取值全文只出现这一次**。建议值必须在施工路径里有落点"
                "（写进某一步的指令模板，或写成改 `.env`／配置的那一步）；"
                "只在分析章给出目标值而不落到任何步骤，施工方无从知道该在哪一步改它 —— "
                "**写下的承诺与写下的步骤是两份东西**" % (i + 1, ln.strip()[:70]))
            break
    return hits


def _read_doc(doc_path: str) -> str | None:
    """读文档；**任何"读不到"都必须是用法错误 64，不能是 traceback + 1**（v1.48.0）。

    为什么单列一个函数：`_EXIT_CODES` 与 SKILL.md 都把 64 写成"用法错误（没给路径或路径不存在）"，
    但旧实现只守了**空参数**这一种；路径不存在／传了目录／文件不是 UTF-8 三种全部裸 `open()`
    抛异常 → 栈回溯 + 退出码 1 —— 与"文档有硬违规"同码。这个脚本的全部纪律建立在退出码语义上，
    一次拼错文件名就会被读成"这份交付物有 7 条违规"，并在人工复核里被当成真红去改。
    实测（v1.48.0 加固前）：`no_such_file_xyz.md`／一个目录／含 0xFF 字节的文件，三者 exit=1。
    """
    try:
        with open(doc_path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        print("用法错误：找不到文件 %s" % doc_path)
    except IsADirectoryError:
        print("用法错误：%s 是目录，不是文件" % doc_path)
    except UnicodeDecodeError as e:
        print("用法错误：%s 不是 UTF-8 文本（%s）。本脚本只读 UTF-8；"
              "扫描件／OCR 产物请先存成 UTF-8 再检查" % (doc_path, e.reason))
    except OSError as e:
        print("用法错误：读不到 %s（%s）" % (doc_path, e))
    print(_EXIT_CODES)
    return None


def main(doc_path: str) -> int:
    """v1.56.2：**结果行必须是 stdout 的最后一行**。

    来历（eval 01 实跑，子代理回报 b 条）：交付清单要求「把自检结果与末行原样贴进文档」，
    而旧实现把**固定不变的退出码图例**打在最后——照抄末行会抄到一句与本次无关的常量，
    等于要求执行者贴一句永远相同的话。**「末行」是给人引用的接口**，接口的最后一格
    不该是常量。改为：图例走 stderr，stdout 末行永远是本次结论（通过／未核／失败）。
    """
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not doc_path:
        # v1.40.0（独立评审实跑：`--skill` 不给路径 → 裸 `FileNotFoundError: ''` + 退出码 1，
        #   与"有违规"同码）——维护者一次误用就会把"命令用错"读成"文档有问题"，
        #   而这个 skill 极度依赖退出码语义。用法错误单开 64（EX_USAGE）。
        print("用法：python self_check.py <交付文档.md>")
        print("     python self_check.py --skill <SKILL.md>")
        print("退出码：0 = 放行／1 = 有违规／2 = 0 违规但有 ⚠️ 未核项／64 = 用法错误")
        return 64
    text = _read_doc(doc_path)
    if text is None:
        return 64
    if "--skill" in sys.argv:
        # 窄范围模式：只查 SKILL.md 自身的声明唯一性 + 权威位置可达性（v1.29.0；v1.37.0 扩）
        # v1.46.0：**两种绿灯必须分开叫**。此前 --skill 与交付物检查打同一个横幅
        #   `=== self_check 通过 ===`，于是"SKILL.md 自洽"这个弱得多的结论，
        #   读起来与"这份交付物过了 8 项检查"一样——绿灯的含金量被自己的措辞抬高了。
        print("[文档自洽检查] 本模式只查 SKILL.md 自身一致（版本对账／哨兵位置／禁用形态／自述项数）——"
              "**绿灯不证明它跑需求有效**；能力只能由「真实需求 → 交付物 → 施工方回访」证明（见验证记录）。")
        violations = validate_skill_self(text, doc_path)
    else:
        is_ref = bool(_GENRE_REF.search(text[:2000]))
        violations = (
            validate_sources(text)
            + validate_declarations(text, doc_path)
            + validate_numbers(text)
            + validate_ledger_line(text)
            + validate_declarations_unique(text, doc_path)
            # 第 7 项（v1.41.0）：标记与证据配套——`[实测]`／`[外源]` 必须同行指得出证据。
            #   为什么必须是**违规**而不是提示项：这一条判的是"有没有给出处"，机械可判、
            #   无歧义（不像状态否定要理解语义）；而 `[实测]` 一旦能免检通行，整个标注体系就失效。
            + validate_marker_evidence(text)
            # 第 8 项（v1.44.0）：L3 施工路径的「通过信号」必须可判 + 四条结构性断言。
            #   来历：一份 0 violations 的 L3 交付物，交给拿不到仓库的外部施工方按字面实现，
            #   四步里一步整层缺失、一条契约与另一步直接互斥——而本脚本当时一条都查不出来。
            #   **判据不是谓词，等于没有约束**；"通过信号"恰恰是最该机械核的那一列。
            + ([] if is_ref else validate_l3_signals(text))
            # 第 9–11 项（v1.47.0）：19 条变异探针里有 3 类全数漏报，补在此处。
            #   ①引用完整性（编号悬空）②章节骨架（整节消失）③账本版本引用（版本号编错）。
            + ([] if is_ref else validate_reference_integrity(text))
            + ([] if is_ref else validate_section_skeleton(text))
            + validate_ledger_citations(text, doc_path)
            # 第 12 项（v1.53.0）：自检留痕必须是真的——占位符／"原样粘贴"的空头承诺不算。
            + validate_selfcheck_trace(text)
            # 第 13 项（v1.58.0）：**写下的承诺必须有落点**。来历是施工方回访：
            #   用例 04 的交付物在 §3.3 给出了目标值（保留的硬上限 480 秒）并论证了"必须大于 363.5"，
            #   而它的 `P1` 明令"不要改动 `.env`"——全文没有任何一步去改它。施工方照着做完，
            #   生产配置仍是 300 秒，那条"3 次尝试跑满"的最坏路径**形同虚设**。
            #   判据不问"作者有没有承诺"（那是措辞），只问"这个只出现一次的取值有没有落点"（那是事实）。
            + ([] if is_ref else validate_promise_landing(text))
        )
        # 第 7 项补强（v1.46.0）：证据必须**能核**，不能只是"长得像证据"——本地文件／账本版本查不到 → ⚠️ 未核。
        #   单列一条而不是塞回第 7 项：第 7 项判"有没有写处"，这里判"写的处能不能核"，两者失败信号不同
        #   （前者是硬违规 1，后者是未核 2）——混在一起会让"多写一个假路径"看起来像修好了。
        WARNINGS.extend(audit_evidence_resolvability(text, doc_path))
        # 提示项（v1.37.9 新增；**v1.40.0 降级为 ℹ️ 提示项**）：状态否定的证据。
        #   降级理由（独立评审实跑）：误报 37.5%（"无侵入/无状态"这类正当表述）、漏报 70%
        #   （换词即过），而 exit 2 与 ⚠️ 的**全部纪律**建立在"⚠️ = 真未核"之上——
        #   一条半可靠的判据混进 ⚠️，教出来的是"忽略 ⚠️"。提示项同样让人去看，但不污染那个信号。
        ADVISORY.extend(validate_negation_claims(text))
        # 第 6 项（v1.40.0）：候选发现记录——把 v1.38.0 自称"可机械核"的判定式做实。
        cand_violations, cand_seen = (([], True) if is_ref else validate_candidate_discovery(text))
        violations.extend(cand_violations)
        if not is_ref and not cand_seen and re.search(r"候选", text):
            WARNINGS.append(
                "未见到「候选发现记录表」（表头须含「命中数」与「取回条数」）→ **候选发现这一项没有核验**"
                "（不等于通过）；产出物里只要有候选/对标内容，就该有这张表（见 SKILL.md 文档结构 §5）")
        # 射程守卫必须**可见**（v1.48.0）。守卫本身是对的（拿 L3 检查跑普通 Markdown 会误报），
        #   但"静默跳过"与它要防的病同源：一份根本不是交付物的文件拿到 exit 0／2，而输出里
        #   没有一个字说明"章节骨架与引用完整性这两项压根没跑"。跳过要说出来。
        if is_ref:
            # 跳过要说出来，并且要进 ⚠️（退出码 2），不能静默放行——否则"不是交付物"会变成
            #   一种绕过五项检查的合法后门。
            WARNINGS.append(
                "本文件已声明 `genre=reference`（非交付物）：**L3 通过信号／引用完整性／章节骨架／"
                "承诺落地／候选发现记录五项未核**。这些检查依赖交付物形态；参考文档里的编号（如 `R1`／`C2`）"
                "常指向交付物而不在本文件内定义，机械核会成片误判。退出码 2 的含义是\"这五项没跑\"，"
                "不是\"内容不合格\"")
        elif _l3_toc_hits(text) < 3:
            WARNINGS.append(
                "本文件**不像 L3 交付物**（正文里没有出现 ≥3 个 L3 章节名：需求与假设／业务叙事／决策依据／"
                "量级与估算／契约／对标／模块全景／施工路径／验收／已知限制）→ **章节骨架、引用完整性、承诺落地三项未启用**，"
                "其余检查照跑。这不是通过：若这确实是要交付的 L3 文档，先补回 §0–§9 的标题")
    if ADVISORY:
        print("ℹ️ 提示项（**不影响退出码，但也不是「通过」**——请人工确认）：")
        print("\n".join(ADVISORY))
    if WARNINGS:
        print("⚠️ 未核项（不是违规，但也**不是通过**）：")
        print("\n".join(WARNINGS))
    if violations:
        # v1.51.0：**红灯也要分开叫**。v1.46.0 只把两种绿灯分了名，红灯仍是同一个横幅——
        #   于是 --skill 模式下"SKILL.md 自述与实现对不上"会显示成 `self_check 失败`，
        #   读起来像"某份交付物被查出问题"，而它连交付物都不是。绿灯防"抬高含金量"，
        #   红灯防"张冠李戴"，两者是同一条纪律的两面。
        if "--skill" in sys.argv:
            print("=== 文档自洽检查失败（**非能力验证**）：SKILL.md 自身不一致，"
                  "不代表它跑需求无效 ===")
        else:
            print("=== self_check 失败 ===")
        print("\n".join(violations))
        print(_EXIT_CODES, file=sys.stderr)
        return 1
    if WARNINGS:
        # v1.37.3：未核不再返回 0。旧行为下调用方只看退出码或"输出里有没有 violations"，
        #   会把"未核"与"通过"一视同仁——正是 SKILL.md 自述要防的失明模式换了个位置复发。
        print("=== self_check 无违规，但有 ⚠️ 未核项（退出码 2）——**未核 ≠ 通过** ===")
        print(_EXIT_CODES, file=sys.stderr)
        return 2
    if "--skill" in sys.argv:
        # 把"查了什么"打出来，证明它不是空转（v1.37.0：假绿比红更难发现）
        ver, ledger, rows = _ledger_max_version(doc_path)
        _im, _ia = _impl_validator_counts()
        print("=== 文档自洽检查通过（**非能力验证**）：0 violations ===")
        print("[--skill] frontmatter version 与账本最新版本行已对账：%s ｜ 哨兵 %d 处均存在 ｜ 禁用形态 0 处"
              " ｜ 账本识别到 %d 条行首版本行 ｜ 自述项数 %d+%d 与 `main()` 实际调用一致"
              % (ver, len(REQUIRED_SKILL_ANCHORS), rows, _im, _ia))
        print(_CAVEAT)
        print("=== 文档自洽检查通过（**非能力验证**）：0 violations ===")
        print(_EXIT_CODES, file=sys.stderr)
        return 0
    # ⚠️ 顺序是有意的：口径在前、**结论在最后一行**。交付清单要求「原样抄末行」，
    #   若末行是常量（图例或口径），抄下来等于什么都没证明。v1.56.2。
    print(_CAVEAT)
    print("=== self_check 通过：0 violations ===")
    print(_EXIT_CODES, file=sys.stderr)
    return 0


if __name__ == "__main__":
    # v1.29.0 修：入口原先直接把 sys.argv[1] 当路径传给 main，加了 --skill 开关后
    # 会变成 open("--skill") → FileNotFoundError。改为先滤掉开关再取路径。
    _paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    # v1.48.0：多给路径时旧实现**静默只用第一个**——调用方以为两份都查了。凡是"静默丢输入"
    #   都属于同一类病（看不见的假绿），一律按用法错误挡回。
    if len(_paths) > 1:
        print("用法错误：一次只查一份文档，收到 %d 个路径：%s" % (len(_paths), "、".join(_paths)))
        print(_EXIT_CODES)
        sys.exit(64)
    sys.exit(main(_paths[0] if _paths else ""))
