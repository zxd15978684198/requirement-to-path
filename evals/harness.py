# -*- coding: utf-8 -*-
"""evals/harness.py —— 任务级评测的**可复核那一半**（v1.49.0）

它不是"自动评测 agent"：那需要起干净会话、把 query 交给真实 agent。
它做的是把 expected_behavior 里**能机械判的部分**变成谓词，对着一份真实产出物打分，
并**引用产出原文**当证据；判不了的条目标「人工」，不冒充通过。

用法：
    python evals/harness.py --case 02 --doc <产出物.md> [--root <项目根>]
"""
import argparse, json, os, re, sys

# 技能包根目录（本文件在 `<skill>/evals/harness.py`）。用来解析产出物里
# 「引用技能包自身」的那类 `文件:行`——见 `_skill_pkg_path()`。
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load(case):
    d = os.path.dirname(os.path.abspath(__file__))
    p = [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.startswith("%02d-" % int(case))]
    if not p:
        sys.exit("找不到用例 %s" % case)
    return json.load(open(p[0], encoding="utf-8"))

def line_of(text, pat, flags=0):
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(pat, ln, flags):
            return i, ln.strip()
    return None

def _index(root):
    idx = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "node_modules", "__pycache__", ".venv", "vector_store")]
        for f in fn:
            if f.endswith((".py", ".json", ".md", ".sql")):
                idx.setdefault(f, []).append(os.path.join(dp, f))
    return idx

def _skill_pkg_path(f):
    """`文件:行` 里的文件是否指向**技能包自身**（`SKILL.md`／`references/…`）。

    v1.56.19：盲跑 4 的产出物开头合法引用了 `SKILL.md:431`（它描述了本次遵循的落盘时序），
    而两个按 `root` 解析的判据都把它算成「核不到」——**判据射程错，不是产出物错**。
    取证对象本来就有两类：**被测项目**与**技能包自身**，两类都是真实的 `文件:行`。
    """
    if os.path.isabs(f):
        return None
    cand = os.path.join(SKILL_ROOT, f)
    return cand if os.path.exists(cand) else None


def check_file_line(text, root):
    """E1：引用真实 文件:行；文件在项目内能唯一定位到、且行号不越界。"""
    hits = re.findall(r"([\w./\\-]+\.(?:py|json|md|sql)):(\d+)", text)
    if not hits:
        return False, "没有任何 `文件:行` 形式的取证"
    idx = _index(root)
    ok, weak, bad, hard = 0, [], [], []
    for f, n in hits:
        base = os.path.basename(f)
        cand = f if os.path.isabs(f) else os.path.join(root, f)
        if not os.path.exists(cand):
            pkg = _skill_pkg_path(f)
            if pkg:
                cand = pkg          # 技能包自身的引用同样可核（它也在磁盘上、也有行号）
            else:
                found = idx.get(base, [])
                if len(found) == 1:
                    cand = found[0]
                    weak.append(base)
                else:
                    bad.append("%s %s" % (base, "在项目内有 %d 处同名" % len(found) if found else "不存在"))
                    continue
        total = 0
        target = None
        with open(cand, encoding="utf-8", errors="replace") as fh:
            for i, ln in enumerate(fh, 1):
                total = i
                if i == int(n):
                    target = ln
        if int(n) > total:
            hard.append("%s:%s 越界(共%d行)" % (base, n, total))
        elif not (target or "").strip():
            # v1.57.0：**行号在范围内 ≠ 那一行说了你引它说的话**。
            # 来历：盲跑 6 的交付物把 `multi_agent.py:236` 当 36.3 秒峰值的取证引了 6 次，
            # 而那一行是**空行**（36.3 只在该文件 :197 的注释里）；它照样拿了 9/9——
            # 因为旧判据只核「文件定位得到 + 行号不越界」。空行是这件事里唯一
            # 可以纯机械判定的形态，所以只判它；「引的是注释 / 引错符号」仍需人工。
            hard.append("%s:%s 指向空行" % (base, n))
        else:
            ok += 1
    if hard:
        # 空行/越界是**硬错**：不存在「这处引对了就算过」的读法。旧版把它们和
        # 「文件定位不到」混在一个 bad 列表里、且只要求 ok≥1，于是 8 对 7 错仍判 PASS。
        return False, "有 %d 处引用指错了地方（空行或越界）：%s —— 行号在范围内不等于那一行说了你引它说的话" % (
            len(hard), "；".join(hard[:3]))
    if not ok:
        return False, "全部取证核不到：" + "；".join(bad[:3])
    msg = "%d 处取证可核" % ok
    if weak:
        msg += "；其中 %d 处只写了文件名、需按唯一同名文件定位（应写全路径）" % len(set(weak))
    if bad:
        msg += "；仍有 %d 处核不到：%s" % (len(bad), "；".join(bad[:2]))
    return True, msg

def check_marker(text):
    n = len(re.findall(r"\[待确认\]", text))
    if n:
        return True, "出现 [待确认] %d 次" % n
    # 前置条件不成立时**判不适用**，而不是判失败：这条要核的是「把口头信息与代码实况对账，
    # 有疑虑标 [待确认] 而不是照抄」，而**降级路径下根本没有可对账的口头信息**——需求方不可达，
    # 门禁 1 没有外部裁决人，疑虑按 SKILL.md 的降级流程改由 §0 的 `[假设]` 清单与未解项承载。
    # 盲跑 8（用例 02）实测撞上：产出物在 L9／L13／L23／L45 逐处声明了不可达、H1–H7 全部
    # 标了「需求方可达后须复核」，却在词面上没有 `[待确认]` 三字，被判 FAIL——那是把
    # 「前置条件不存在」读成了「功能没做到」。
    # **不写成静默跳过**：记为 N/A、打印理由、在总结行显示计数，从分母里减去但不许消失
    # （静默跳过比误判更坏——误判会被看见，静默会让缺口永远不出现）。
    if re.search(r"需求方不可达|不可达声明|需求方[^\n]{0,10}不回应|无人应答", text[:4000]):
        return None, ("不适用：降级路径（需求方不可达）下没有可对账的口头信息，"
                      "疑虑由 §0 `[假设]` 清单与未解项承载——此条只在需求方可达时判")
    return False, "没有 [待确认] 标记（口头信息与代码实况不一致时该标出来）"

def check_security(text):
    # 必须真的点名「权限」并说到「绕过/边界/过滤」，泛泛谈安全不算
    for ln in text.splitlines():
        if "权限" in ln and re.search(r"绕|边界|过滤", ln):
            return True, "L%d：%s" % (text.splitlines().index(ln) + 1, ln.strip()[:70])
    return False, "全文没有一处同时提到「权限」与「绕过/边界/过滤」——原文未回答安全边界问题"

def check_upstream(text):
    # 必须是「查了上游目录/官方实现」的痕迹，不是候选表里出现某仓库名
    h = line_of(text, r"libs/|官方实现|上游仓库|官方套件")
    return bool(h), ("L%d：%s" % (h[0], h[1][:70]) if h else "候选里没有「上游有没有官方实现」这一层")

def check_structure(text, doc_path):
    have = set(re.findall(r"(?m)^#{1,3}\s*(?:§\s*)?([0-9])(?=[.、．:：\s]|$)", text))
    missing = [str(i) for i in range(10) if str(i) not in have]
    ran = re.search(r"self_check\.py[^\n]*", text)
    code = re.search(r"EXIT\s*=|退出码\s*[:：]?\s*[0-9]", text)
    if missing:
        return False, "缺第 %s 节" % "、".join(missing)
    if not ran:
        return False, "0–9 节齐，但没有真跑 self_check.py 的记录"
    if not code:
        return False, "跑了 self_check.py 但没贴退出码"
    return True, "0–9 节齐，且贴了 self_check 输出与退出码"

def check_readonly(text):
    h = line_of(text, r"只读|不动.*文件|新增文件")
    return bool(h), ("L%d：%s" % (h[0], h[1][:70]) if h else "没有声明只读/不改动需求方文件")

# ---------------- 用例 01：语义缓存（有界模糊需求） ----------------
# 这组谓词盯的是「有界但关键约束藏在一句话里」的需求最容易漏的七件事。
# 与 03 的差别：03 判的是流程骨架（先问再搜、降级坦诚），01 判的是**取证质量**
# ——候选是不是直搜来的、抄它会在什么条件下坏、出处是不是可查。

def _find(text, pat):
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(pat, ln):
            return i, ln.strip()
    return None, ""

def c1_applicability(text):
    """E1：先判适用性，不跳到直接给方案。

    动机：需求只有一句话（"别串答案"是藏在句子后半的硬约束），直接给方案
    最容易把「近似不同问题」这条丢掉——所以先问"这需求要不要走本流程"。

    实跑 01 时踩的坑：初版只认字面「适用性」三个字，而真实产出物写的是
    `## 0 定位与档位声明` + `层级：模块级。档位：设计文档。`——**档位声明就是
    适用性判断**（skill 自己的规格管它叫「层级／档位声明」）。判据只认一种措辞，
    等于逼产出物去迎合判据的用词，而不是去满足要求。
    """
    n, ln = _find(text, r"适用性|适用判断|是否走本流程|本流程适用|档位(声明)?|层级：|层级:")
    if not n:
        return False, "没有适用性／档位声明——看起来直接进了方案"
    pn, pln = _find(text, r"^\s*#{1,3}[^\n]*(实现方案如下|推荐方案|最终方案)|^\s*#{1,3}\s*(?:§\s*)?[6-9][^\n]*(实现|落地|路径|步骤)")
    if pn and pn < n:
        return False, "L%d 就先给实现路径（%s），早于 L%d 的档位判断" % (pn, pln[:40], n)
    return True, "L%d：%s" % (n, ln[:70])

def _table_cells(ln):
    # v1.56.22：与 `references/self_check.py` 的 `table_cells()` **同一份判据**（两处各一份是既成事实，
    #   改一处忘一处正是本 skill 反复在治的病；此处至少保证**行为一致**）。
    #   修的是：单元格里写合法的转义竖线时，朴素 `split("|")` 会把整行后续列错位，
    #   于是"来源列"读到的是别的列的内容 → 报出指向错误内容的错。
    body = ln.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", body)]

def c1_discovery(text):
    """E3：直搜（search_repositories + stars 下限），取回条数 ≥ 命中数。

    踩过的坑（2026-10-18 实跑 01）：初版要求「取回 N／命中 M 写在同一行」，
    而 skill 自己规定的形态是**候选发现记录表**（列：命中数｜取回条数），
    真实产出物照规格写了表，判据却判 FAIL——**判据没跟上规格**，这不是产出物的错。
    现在两种形态都认：先按表头找列、逐行比对；找不到表再退回同行写法。
    """
    # v1.56.19：**探活不是发现**。skill 的 L1.0 要求「本次将用到的每个工具各探活一次」，
    #   探活用的检索式天然是无范围试打（目的就是看工具通不通）。把它读成「拿无范围
    #   search_code 当发现路径」是射程错。盲跑 4 的产出物正撞在这里：表格首列写 `探活`、
    #   结论写着「无范围限定短语是噪音通道，**不能**用于发现」——豁免词表里两个词都差一个字
    #   （表里是 `不用于发现`／`探针`，产出物写的是 `不能用于发现`／`探活`）。
    #   这次**不再往词表里加同义词**（加同义词很快会变成「照着这份产出物写判据」，
    #   `solid` 已经因此错过三次），改判**结构**：`探活` 是技能包自己定义的活动名，
    #   出现在该行首个表格单元即豁免。真违规长的是「发现轮次行 + 无范围检索式」。
    PROBE_ACT = r"探活|探针|可用性检查"
    EXEMPT = (r"兜底|不.{0,2}用于发现|不是发现路径|非发现|已放弃|未用|没用|不用|未使用|"
              r"避免|禁止|不用作|噪音|"
              # v1.56.22：下面这几个**不是产出物的措辞变体，是技能包自己规定的表格列词汇**
              #   （候选发现表的列名就是「已换词？」，另有「取回条数」列）。按自家列词汇豁免，
              #   不构成「照着某份产出物写判据」；而且「未取回／同上」本身就自证这一行没被当发现路径用。
              #   盲跑 5 的产出物两行都写了「已换词：是（改用带 repo: 范围的机制短语反查）」，
              #   第二行还用「同上」承接第一行的理由 —— 它把「无范围」三个字自己标出来了（自证式诚实），
              #   判据却因为词表里没有「换词」「同上」而判它违规。
              r"换词|分页|逐页|未取回|同上")
    for i, ln in enumerate(text.splitlines(), 1):
        if "search_code" not in ln:
            continue
        cells = _table_cells(ln)
        if (cells and re.search(PROBE_ACT, cells[0])) or re.search(PROBE_ACT, ln):
            continue
        if re.search(r"无范围|没有范围|不限范围|不带\s*repo:", ln) and not re.search(EXEMPT, ln):
            return False, "L%d 拿无范围 search_code 当发现路径：%s" % (i, ln.strip()[:60])
    if not re.search(r"search_repositories", text):
        return False, "候选发现没有走 search_repositories 直搜"
    # v1.58.2：截断规则有**两种合法形态**——①显式 stars 下限（`stars:>N`）；
    #   ②在候选发现记录里写明「按 stars 排序、取回前 N 条」（表格自带命中/取回两列，
    #   读者能复核"有哪些被取回、按什么序截断"）。
    #   原判据只认 ①，于是把盲跑 9 的写法（`search_repositories（sort stars）`
    #   ＋「取回均为 30 条」＋「把候选收窄到 5 个仓库」）判成「没写 stars 下限」——
    #   **判据只认一种写法**，同族第九次。要求本身（必须写清怎么截断的）不变。
    if not re.search(r"stars\s*[:：>]|stars:>", text) and not re.search(
            r"sort\s*stars|按\s*stars|stars\s*(?:降序|排序|倒序)|"
            r"取回[^\n]{0,8}\d+\s*条|top\s*\d+|前\s*\d+\s*条", text):
        return False, ("候选集怎么截断的不可复核：既没有 stars 下限（`stars:>N`），"
                       "也没有写明按 stars 排序、取回前 N 条")

    # 形态一：候选发现记录表（命中数 / 取回条数 两列）
    lines = text.splitlines()
    head = None
    for i, ln in enumerate(lines):
        if "|" in ln and "命中" in ln and "取回" in ln:
            cells = _table_cells(ln)
            hi = next((k for k, c in enumerate(cells) if "命中" in c), None)
            gi = next((k for k, c in enumerate(cells) if "取回" in c), None)
            if hi is not None and gi is not None and hi != gi:
                head = (i, hi, gi)
                break
    if head:
        i0, hi, gi = head
        checked, bad, exempt = 0, [], []
        for ln in lines[i0 + 1:]:
            if not ln.lstrip().startswith("|"):
                break
            cells = _table_cells(ln)
            if len(cells) <= max(hi, gi):
                continue
            mh, mg = re.search(r"\d+", cells[hi]), re.search(r"\d+", cells[gi])
            if not (mh and mg):
                continue
            hit, got = int(mh.group()), int(mg.group())
            checked += 1
            if got >= hit:
                continue
            if re.search(r"换词|分页|逐页|探活|不用于发现|抽查|只看命中数", ln):
                exempt.append("%d/%d" % (hit, got))
                continue
            bad.append("%d/%d" % (hit, got))
        if bad:
            return False, "L%d 起的候选表里 %d 行取回 < 命中且没写换词/分页/探活：%s" % (
                i0 + 1, len(bad), "、".join(bad[:3]))
        if checked:
            return True, "候选发现表 %d 行已比对（命中/取回）%s" % (
                checked, "；豁免 %d 行（换词/分页/探活）" % len(exempt) if exempt else "")

    # 形态二：同一行写出「取回 N ≥ 命中 M」
    for i, ln in enumerate(text.splitlines(), 1):
        m1 = re.search(r"取回[^\d]{0,12}(\d+)", ln)
        m2 = re.search(r"命中[^\d]{0,10}(\d+)", ln)
        if m1 and m2:
            got, hit = int(m1.group(1)), int(m2.group(1))
            if got >= hit:
                return True, "L%d 取回 %d ≥ 命中 %d" % (i, got, hit)
            if re.search(r"已换词|分页看完|逐页翻完|全部翻完|探活", ln):
                return True, "L%d 取回 %d < 命中 %d，但写明了已换词／分页看完／探活" % (i, got, hit)
            return False, "L%d 取回 %d < 命中 %d，且没写换词或分页看完——候选集是截断的抽样" % (i, got, hit)
    return False, "既没有「命中数/取回条数」表，也没有同一行写出取回与命中——无法判断是否只看了第一页"

def c1_l0_artifacts(text):
    """E2：门禁 1 的澄清结果必须落成带编号的 L0-P/C/S 产出物。

    为什么不是"有澄清问题清单就行"：清单在对话里会随上下文蒸发，交付文档里
    必须留下「痛点／约束／成功信号」三类带编号的东西，后面取证才能引用它们。
    """
    need = {"L0-P": r"L0-P\d", "L0-C": r"L0-C\d", "L0-S": r"L0-S\d"}
    miss = [k for k, p in need.items() if not re.search(p, text)]
    if miss:
        return False, "缺带编号的 %s 产出物" % "／".join(miss)
    gate = _find(text, r"门禁\s*1|弹窗澄清|澄清")
    if gate[0]:
        return True, "L%d 门禁 1；L0-P/C/S 三类编号齐" % gate[0]
    # 降级路径（需求方不可达）下，`SKILL.md` 规定的 §0 顺序是「不可达声明 → `[假设]` 清单
    # → …」，正文里**根本不会出现「门禁 1」三个字**：三类产出物就长在 `[假设]` 清单里，
    # 靠「编号 + 类别」两列表明身份（盲跑 6 的 §0.1 就是这样，2026-10-19；这是「只认一种
    # 措辞」的同族复发）。判据若坚持要那个词，等于要求产出物迎合判据用词。
    # 改判**结构事实**：L0-P/C/S 三类编号各自与自己的类别名同行。
    pairs = set()
    for ln in text.splitlines():
        m = re.search(r"L0-([PCS])\d", ln)
        if not m:
            continue
        for key, word in (("P", "痛点"), ("C", "约束"), ("S", "规格")):
            if m.group(1) == key and word in ln:
                pairs.add(key)
    if len(pairs) == 3:
        return True, "L0-P/C/S 三类编号齐，且各自与类别名（痛点／约束／规格）同行（降级路径未写「门禁 1」字样）"
    return False, "有 L0 编号产出物，但没说它们是门禁 1 澄清出来的（三类也没有各自与类别名同行）"

def c1_candidates(text):
    """E4：候选集须含 GPTCache 之外至少一个，且每个写出「抄它会在什么条件下坏」。

    这条是 01 与 03 最大的区别：03 允许"0 候选降级"，01 的需求是有界的、
    必然有可对标物——所以"只找到 GPTCache 一个"等于没做候选发现。
    "会在什么条件下坏"必须落在候选附近（±3 行），否则就是贴在文章末尾的
    通用免责声明，不是对这个候选的判断。
    """
    repos = set()
    for owner, name in re.findall(r"\brepo/([\w.-]+)/([\w.-]+)", text):
        repos.add("%s/%s" % (owner, name))
    for owner, name in re.findall(r"`([\w.-]+)/([\w.-]+)`", text):
        repos.add("%s/%s" % (owner, name))
    gpt = [r for r in repos if "gptcache" in r.lower()]
    others = [r for r in repos if "gptcache" not in r.lower()]
    if not gpt:
        return False, "候选集里没有 GPTCache（本例的标杆实现）"
    if not others:
        return False, "除 GPTCache 外没有第二个候选——只认一个标杆，谈不上候选发现"
    lines = text.splitlines()
    judged = []
    for r in sorted(repos):
        idx = [i for i, ln in enumerate(lines) if r in ln]
        near = False
        for i in idx:
            for j in range(max(0, i - 3), min(len(lines), i + 4)):
                if re.search(r"会在.{0,12}(坏|失效|崩|不成立)|失效(条件|点)|一旦.{0,12}(坏|失效|不成立)"
                             # v1.60.8：规则的原文是「为什么参考＋**为什么不全抄**」（SKILL.md:160、
                             #   l3-mode-map.md:454/:379），而这里原先只认「会坏／失效条件」一种说法。
                             #   盲跑 14 写的是「它没有角色/租户概念…要自己补」——合规的取舍，被判红。
                             #   补齐规则自己的说法；「会坏条件」仍是更强的形态，不是被替换。
                             r"|为什么不全抄|不全抄|不直接抄|自己的?补|要自己|需要自己|自己实现|不能直接用|缺口", lines[j]):
                    near = True
                    break
            if near:
                break
        if near:
            judged.append(r)
    if len(judged) < 2:
        return False, "写了 %d 个候选，但只有 %d 个在附近给出「会在什么条件下坏」" % (len(repos), len(judged))
    return True, "候选 %d 个（含 GPTCache）；%d 个写出了失效条件" % (len(repos), len(judged))

def c1_evidence(text):
    """E5：取证须带 repo/<owner>/<name>:<path>#符号 或 :L行；不许裸行号、不许引 README 当结论。

    为什么禁裸行号：`依据：adapter.py:88` 在需求方仓库里核不到（同名文件多、
    行号随分支漂），而 `repo/x/y:path#sym` 能被第三方独立复核。
    README 当结论是另一类：README 说的是"设计意图"，代码才是"实际行为"。
    """
    # v1.56.22：**标点风格不是判据**。原正则把定位形态写死成 `repo/<owner>/<name>:<path>`，
    #   但 `repo/<owner>/<name>/<path>` 同样唯一（owner、name 就是头两段），
    #   而「路径 + blob sha」和「路径 + #符号名」一样能把引用钉到具体内容上（甚至更硬：
    #   钉的是内容本身，不是会随分支漂的行号）。盲跑 5 的产出物通篇用斜杠分隔
    #   ＋「（blob sha `…`）」括注，**12 处真引用被算成 0 处** → 「判据只认一种写法」这一族第六次复发。
    #   现在按**可复核性**判，不按标点判。
    cites = []
    for i, ln in enumerate(text.splitlines(), 1):
        if "repo/" not in ln:
            continue
        for m in re.finditer(r"repo/[\w.-]+/[\w.-]+[:/][^\s`）)，,；;]*", ln):
            seg = m.group(0)
            if re.search(r"#[\w.-]+|L\d+", seg) or re.search(
                    r"(?:blob\s*sha|sha)`?\s*[:：]?\s*`?[0-9a-f]{7,40}", ln, re.I):
                cites.append((i, seg[:70]))
                break
    if len(cites) < 3:
        return False, ("只有 %d 处可复核的仓库取证（至少要 3 处才算真读过）；接受两种写法："
                       "`repo/<owner>/<name>[:/]<path>` 后跟 `#符号名`／`:L行`，"
                       "或同行给出 `blob sha <hex>`" % len(cites))
    # v1.60.7：**代码切片不是引用**。原正则把 `hexdigest()[:32]` 里的 `:32` 当成裸行号，
    #   盲跑 14 因此被扣一分（该分与本谓词声称要测的东西无关）。现在排除
    #   「前一个字符是 [ { ( 」与「后一个字符是 ] 」两种形态；`（`:13`）` 这类缩写仍照抓。
    _BARE = r"(?<![L\w/\[({]):\d{1,4}(?![\w\-\]])"
    if re.search(_BARE, text):
        bad = re.search(_BARE, text).group(0)
        return False, "出现裸行号「%s」——repo/…:path#符号 或 :L行 才可被独立复核" % bad
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(r"README", ln) and re.search(r"依据|结论|说明它|证明|据此", ln) and not re.search(
                r"不能|不足以|不算|不引用|不作为|只是设计意图|不拿|不用|不当|不作|而非|不看|别信|不计入", ln):
            return False, "L%d 把 README 当结论：%s" % (i, ln.strip()[:60])
    return True, "%d 处可复核取证，无裸行号，未把 README 当结论" % len(cites)

# ---------------- 用例 03：极模糊的平台级需求 ----------------
# 这一组谓词判的是「四条最容易同时失效的判据」有没有守住，不是"方案好不好"。

def _nth_line(text, pat):
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(pat, ln):
            return i
    return None

def c3_gate1(text):
    """E1：先澄清、再搜。**两条合法路径**——需求方不可达→明说并降级；需求方可达→把问答留在案上。"""
    ask = _nth_line(text, r"门禁\s*1|先澄清|澄清(问题|清单)|待澄清")
    if not ask:
        return False, "没有澄清问题清单——门禁 1 没露面"
    # v1.60.3：原先用「候选」这个**名词**判断"已经搜索过"，于是假设表的依据列里
    #   写「候选池最大」就算检索动作，盲跑 10 与盲跑 11 双双被判「先搜后问」
    #   （实际两份都把不可达声明放在首行、把"若可达先问什么"放在假设表）。
    #   改成只认**动作证据**：调用检索工具 / 记下命中数或取回条数 / 给出 repo 链接。
    #   名词（候选、候选池、候选集）不再触发——讨论候选不等于搜过。
    first_cand = _nth_line(text, r"search_repositories\s*\(|search_issues\s*\(|"
                                 r"search_code\s*\(|命中数|取回条数|检出\s*\d+|"
                                 r"repo/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
    if first_cand and first_cand < ask:
        return False, "L%d 就出现检索动作/结果计数，早于 L%d 的澄清清单——先搜后问" % (first_cand, ask)
    gone = _nth_line(text, r"不可达|无法(追问|确认)|降级")
    if gone:
        return True, "L%d 澄清清单、L%d 声明不可达并降级；候选出现在其后" % (ask, gone)
    # v1.58.1：**需求方可达**也是一条合法路径。此前这段硬要求「不可达声明」，
    #   于是把一次合规的可达路径判成「有澄清清单，但没说需求方不可达（默认它答过了？）」
    #   ——**判据只认一条路径**，与本轮反复修的「只认一种写法」是同一病根。
    #   可达路径该留下的是**答案**（答复记录／门禁 2 决策表），不是「不可达」声明。
    answered = _nth_line(text, r"需求方(的)?(答复|回答|回复|确认)|答复[:：]|回答[:：]|"
                               r"问答记录|澄清(已)?闭环|门禁\s*2[^\n]{0,24}(决策表|逐机制|方案选项)")
    if answered:
        return True, ("L%d 澄清清单、L%d 留下需求方答复——**需求方可达路径**，"
                      "未声明不可达（正确）" % (ask, answered))
    return False, ("有澄清清单，但既没有「需求方不可达」声明、也没有任何答复记录／门禁 2 决策表"
                   "——**问题问出来了却没留下答案**")

def c3_framework(text):
    """E2：框架类候选要标「排除」，不能把编排框架当可抄模块交付。"""
    # v1.60.3：原先要求同一行同时出现「排除」与「框架」——**判的是措辞不是行为**。
    #   盲跑 10/11 都写作 `平台（❌ 不作目标形态）`、`不要引入第三方 agent 框架`，
    #   语义上框架已被挡在交付之外，两份却都判红。改成「框架 + 任一排除标记」。
    _EXCL = (r"排除|❌|✗|×|不作目标|不作为目标形态|不引入|不要引入|不考虑|不采用|不抄|"
             r"不要用|不选|不要选|禁用|禁止|拒绝|挡在.{0,6}之外|不用它|不当作候选")
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(r"框架", ln) and re.search(_EXCL, ln):
            return True, "L%d：%s" % (i, ln.strip()[:70])
    return False, ("没有一行同时出现「框架」与排除标记"
                   "（排除/❌/不作目标形态/不引入…）——框架没被挡在交付之外")

def c3_split(text):
    """E3：要么单候选覆盖，要么按组合型拆子机制并说明依据。"""
    h = line_of(text, r"拆分依据|组合型|拆成|子机制")
    return bool(h), ("L%d：%s" % (h[0], h[1][:70]) if h
                     else "既没声明单候选覆盖，也没给组合型拆分与依据")

def c3_discovery(text):
    """E4：发现路径不能是「无范围 search_code」；命中数要记录。

    踩过的坑：初版一见「search_code + 无范围」就判负，把**主动披露、并说明"不用于发现"**
    的真实产出物也打红了（假阴性，2026-10-18 实跑 03 时发现）。而 skill 的
    `l1-search-recipes.md` 1-C 恰恰允许它当兜底探针，前提是三件事写明：
    不作发现路径、记下命中数、说清为什么放弃。所以判据分两档：
    披露 + 兜底声明 → PASS（记「自查披露」）；无声明 → FAIL。
    """
    for i, ln in enumerate(text.splitlines(), 1):
        if "search_code" not in ln:
            continue
        if not re.search(r"无范围|没有范围|不限范围|不带\s*repo:|无\s*`repo:`", ln):
            continue
        if re.search(r"兜底|不用于发现|不是发现路径|非发现|探针|已放弃", ln):
            return True, "L%d 披露无范围 search_code 且声明不作发现路径：%s" % (i, ln.strip()[:60])
        return False, "L%d 用了无范围 search_code 却没声明它不作发现路径：%s" % (i, ln.strip()[:60])
    # 命中数的写法很杂（`检索命中数：…返回 **47** 条`／`命中 213`），只要求
    # 「同一行既谈到命中/返回、又给出数字」，不强求紧邻——初版要求紧邻，把
    # 正例夹具判了 FAIL（假阴性），是造正例才发现的。
    # 判「记录了命中数」踩过三次假阳性，结论：关键词+数字这条路不成立。
    #   ① `重建结果逐字段一致` —— 关键词太泛
    #   ② `:113 返回结构不变` —— 「返回」+任意数字 ≠ 计数
    #   ③ `命中且 status='active'` —— **「命中」在本 skill 的领域里也指数据库/缓存命中**
    # 所以必须把数字绑回检索语境：计数词与量词「条」在近距内同时出现。
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(r"(命中|检出|取回|返回|共)[^\n]{0,12}?\d+\s*\*{0,2}\s*条", ln):
            return True, "L%d：%s" % (i, ln.strip()[:70])
    return False, "没有记录命中数（无法判断是否超出容量阈值）"

def c3_downgrade(text):
    """E5：没有可对标时要明示降级级别，不编造对标。

    判据踩过的坑：初版只认 ③/④，可 skill 的降级链有四档（①找不到整块对标的子机制
    ／②部分匹配／③退回 spec-development／④无先例），文档走 ①② 时会被错判成
    「没写级别」。反过来，只写「降级路径」也不够——读的人不知道是"有子机制可抄"
    还是"一无所有"。所以要求：降级 与 级别/降级链 同现，且带 ①–④ 的编号，
    或直接写 spec-development／无先例。
    """
    for i, ln in enumerate(text.splitlines(), 1):
        if not re.search(r"降级", ln):
            continue
        if re.search(r"(级别|降级链)[^\n]{0,8}[①②③④]", ln) or re.search(r"spec-development|无先例", ln):
            return True, "L%d：%s" % (i, ln.strip()[:70])
        # v1.60.2：声明「没走降级链」也算明示（skill 正文允许这种写法）。
        #   要求同一行里出现「未/不/没有/无需」+ 降级，或「候选充足」，避免空口过关。
        if re.search(r"未走[^\n]{0,12}降级|未降级|无需降级|不降级", ln) or "候选充足" in ln:
            return True, "L%d（声明未降级）：%s" % (i, ln.strip()[:70])
    return False, ("没有明示降级级别（①子机制／②部分匹配／③退回 spec-development／④无先例）"
                   "——只写「降级路径」看不出是哪一级")

def c3_tail(text):
    """E6：结尾给未解项与下一步，且真跑自检并贴退出码。

    新增：抓「公告将来会贴、但眼下留占位符」。实跑 03 时该产出物 §9.4 只贴了
    命令、§9.5 写着「（本节由收口前的最后一次执行回填）」+ `【待回填】`——
    **这比完全不贴更危险**：它看起来像有证据。
    """
    a = _nth_line(text, r"未解项|待解|未解决")
    b = _nth_line(text, r"下一步|后续步骤|接下来")
    if not a or not b:
        return False, "缺「未解项」(%s) 或「下一步」(%s)" % ("有" if a else "无", "有" if b else "无")
    if not re.search(r"self_check\.py", text):
        return False, "有收尾，但没跑 self_check.py"
    # v1.60.2：占位符只扫**自检那一段**。原先是全文扫，于是 §3 的
    #   「实测标定均待回填（[假设]）；实测回填清单见 §9.1」——技能自己要求的写法——
    #   被判成「自检输出是占位符」（盲跑 11 实测）。意图是抓「命令贴了、输出留着待填」。
    _sl = _nth_line(text, r"self_check\.py")
    ph = None
    if _sl:
        for _i, _line in enumerate(text.split("\n"), 1):
            if _sl - 3 <= _i <= _sl + 20 and re.search(r"待回填|【待填】|待补充|TODO", _line):
                ph = _i
                break
    if ph:
        return False, "L%d 自检输出是占位符（待回填）——「公告将来会贴」不等于贴了" % ph
    if not re.search(r"EXIT\s*=|退出码\s*[:：]?\s*[0-9]", text):
        return False, "跑了 self_check.py 但没有退出码"
    return True, "未解项 L%d、下一步 L%d，且贴了自检退出码" % (a, b)

# ---------------- 用例 04：工具调用超时与重试（现象型需求 + 本地项目） ----------------
# 与 01/03 的差别：需求给的是**现象**（"卡住"／"会话废了"），不是机制名。
# 所以这组盯的是「现象→机制归因」与「对照本项目真实代码」两件事，
# 而不是只判取证格式。13 条里 3 条属语义判断，其余可机判。

def c4_pain_split(text):
    """把「卡住」与「会话废了」拆成两条独立痛点，不许合成「要稳定」。

    动机：这两件事的修法完全不同——前者是超时/看门狗，后者是错误处理与
    会话恢复。合成一条「要稳定」会让实现路径只做重试，而重试治不了"卡住"。
    """
    lines = text.splitlines()
    stall, crash = [], []
    for ln in lines:
        if not re.search(r"L0-P\d", ln):
            continue
        if re.search(r"卡|挂|不动|超时|hang|无响应|假死", ln):
            stall.append(ln)
        if re.search(r"会话|崩溃|废|断|恢复|重来|异常|报错", ln):
            crash.append(ln)
    if not stall:
        return False, "没有把「卡住／无响应」落成一条 L0-P 痛点"
    if not crash:
        return False, "没有把「报错后整个会话作废」落成一条独立的 L0-P 痛点"
    ids = set(re.findall(r"L0-P(\d+)", "".join(stall))) | set(re.findall(r"L0-P(\d+)", "".join(crash)))
    if len(ids) < 2:
        return False, "两条现象写进了同一个痛点编号（L0-P%s）——修法不同，必须拆开" % "".join(ids)
    return True, "卡住与崩溃分成 %d 条痛点" % len(ids)

def c4_constraints(text):
    """重试类需求最容易漏的三条约束：幂等性、退避、超时上限。"""
    miss = []
    if not re.search(r"幂等|重复执行|写操作.{0,8}(重|再)放|副作用", text):
        miss.append("重试是否幂等（写操作被重复执行）")
    if not re.search(r"退避|backoff|指数|抖动|jitter", text):
        miss.append("退避策略")
    if not re.search(r"上限|最大(次数|重试)|不超过|阈值|预算|budget", text):
        miss.append("重试上限／超时上限")
    if miss:
        return False, "缺 %d 条关键约束：%s" % (len(miss), "；".join(miss))
    return True, "幂等／退避／上限三条约束都在"

def c4_attribution(text):
    """现象必须归因到机制：卡住→超时/看门狗，崩溃→会话恢复/错误边界。

    只看「有没有写超时和重试」不够——那样写出来的东西对"卡住"无效
    （重试只在失败时发生，而卡住根本没有失败事件）。
    """
    lines = text.splitlines()
    a = b = False
    for i, ln in enumerate(lines):
        w = "\n".join(lines[max(0, i - 2):i + 3])
        if re.search(r"卡|挂|不动|hang|无响应|假死", w) and re.search(r"看门狗|watchdog|超时|timeout|心跳", w):
            a = True
        if re.search(r"会话|崩溃|废|恢复|重来", w) and re.search(r"checkpoint|恢复|resume|错误边界|异常处理|持久化|事务", w):
            b = True
    if not a:
        return False, "「卡住」没有归因到超时/看门狗——重试治不了「没有失败事件的卡住」"
    if not b:
        return False, "「会话废了」没有归因到会话恢复/错误边界"
    return True, "两类现象各自归因到不同机制"

def c4_local_code(text, root):
    """必须对照本项目真实代码，而不是只谈通用方案。

    v1.56.19：**射程有意不扩到技能包自身**。产出物引用 `SKILL.md:431`（自己遵循的流程）
    是合法的，但那是「技能包」不是「本项目」——若让它计入 `okf`，一份只抄技能包行号、
    完全没看项目代码的产出物就能通过「对照真实代码」，那是**假绿**。
    所以这类引用在此**静默跳过**：不记 ok、也不记 bad（记 bad 会让报错信息误导人）。
    """
    hits = re.findall(r"([\w./\\-]+\.(?:py|json|md|sql)):(\d+)", text)
    if not hits:
        return False, "没有任何 `文件:行` 形式的本地取证"
    idx = _index(root)
    okf, bad, hard = set(), [], []
    for f, n in hits:
        base = os.path.basename(f)
        cand = f if os.path.isabs(f) else os.path.join(root, f)
        if not os.path.exists(cand):
            if _skill_pkg_path(f):
                continue            # 技能包自身的引用，不在本检查射程内
            found = idx.get(base, [])
            if len(found) != 1:
                bad.append("%s 核不到" % base)
                continue
            cand = found[0]
        total, target = 0, None
        with open(cand, encoding="utf-8", errors="replace") as fh:
            for i, ln in enumerate(fh, 1):
                total = i
                if i == int(n):
                    target = ln
        if int(n) > total:
            hard.append("%s:%s 越界(共%d行)" % (base, n, total))
        elif not (target or "").strip():
            hard.append("%s:%s 指向空行" % (base, n))
        else:
            okf.add(base)
    if hard:
        # v1.57.0：与 `check_file_line` 同一条理——空行/越界是硬错，不参与「凑够几个文件就行」。
        return False, "有 %d 处引用指错了地方（空行或越界）：%s" % (len(hard), "；".join(hard[:3]))
    if len(okf) < 2:
        return False, "可核的本地文件只有 %d 个%s——本需求有现成项目，必须对照真实代码" % (
            len(okf), ("（%d 处核不到：%s）" % (len(bad), "；".join(bad[:2]))) if bad else "")
    return True, "%d 个文件的引用可核%s" % (len(okf), ("；%d 处核不到" % len(bad)) if bad else "")

def c4_predicates(text):
    """每步的「通过信号」必须是可判谓词，不能是「更稳了」这类无判据措辞。

    踩过的坑（2026-10-19 首次跑本用例）：初版 `solid` 只接受 `= < > 返回 不超过`
    这几种形式，把「调用在 30s±1s 时抛出 TimeoutError，日志行数为 1」
    和「`snapshot.next` 非空且 `interrupts` 为空」判成不可判——**这两条都可判**，
    只是用了另一种措辞。判据只认一种写法，等于逼产出物迎合判据的用词
    （与 v1.55.0 `c1_applicability` 同一病根）。
    现在的判据是：**必须含一个具体的可观测锚点**——比较运算符／带单位的数字／
    对具名字段的状态判断（非空、为空、仍为 NULL、长度从 1 变 0、不含某值、
    返回某个具名错误码）。只有形容词的一律不过。

    第二次踩同一个坑（2026-10-19，case 06 正例 10/11）：`仍为 NULL`、`返回
    invalid_asset_no`、`不含任何 dispatched 行` 三条全被判成不可判。病根一样，
    但这次不再靠加词表硬凑（越加越像「照着夹具写判据」），改成**结构判据**：
    要么有比较运算符，要么有「数字+单位／位」，要么有「状态词 + 具名 token」。
    """
    vague = r"更稳|更好|更可靠|生效|正常|合理|顺畅|数量级|明显改善|基本可用|成功即可"
    # 锚点一：比较运算符；锚点二：数字+单位/位；锚点三：状态词（含 NULL 与非空判定）；
    # 锚点四：返回/抛出 + 具名标识符（错误码、字段名），只认带下划线或驼峰的名字。
    solid = (r"[=<>≥≤±≠]|等于|相等|相同|一致|不等于|不超过|不低于|非空|为空|零|"
             r"为\s*(?:NULL|null|空|True|False|[0-9])|不含|包含|含有|"
             # 判定字面量：`脚本输出为 PASS`／`结果为 FAIL`。PASS/FAIL 与 True/False 同类，
             # 都是**判决结果**（跑了某东西、得到一个二值结论），是可判的。旧锚点表列了
             # True/False 却漏了 PASS/FAIL——盲跑 9 的 §8 那条
             # 「§8 全部条目的脚本输出为 `PASS`，且每条都附了运行前后块数与报告原文」
             # 被判成不可判（2026-10-19）。**判据只认一种写法**，同族第十次。
             r"为\s*`?(?:PASS|FAIL)`?|"
             r"\bNULL\b|\bnull\b|长度|行数|计数|次数|耗时|退出码|毫秒|\bms\b|"
             r"(?:返回|抛出|raise|return)\s*`?[A-Za-z_][A-Za-z0-9_]{2,}|"
             r"从\s*\d+\s*(?:变|到|降|增)|\d+\s*(?:s|秒|ms|毫秒|次|条|行|个|位)|"
             # 否定式：`报无结构漂移`／`无遗留`／`无重复`。这类写法给的是**可观测的
             # 缺席**（跑某命令 → 它的输出里没有某东西），是可判的。盲跑 4 的 L622
             # 「`alembic check` 报无结构漂移」被旧锚点表判成不可判（2026-10-19）。
             r"无[\u4e00-\u9fa5]{0,8}(?:漂移|报错|遗留|变化|重复|冲突)|"
             # 字面量键值：`{"ok": false, "error": "permission_denied"}`。这是**最可判**
             # 的一种（原文照贴的载荷），旧锚点表因为只认 `为 false` 而漏掉它
             # （盲跑 4 的 L647，2026-10-19）。
             r"\"[A-Za-z_][A-Za-z0-9_]*\"\s*:\s*(?:true|false|null|\"[^\"]*\"|-?\d+)|"
             # 闭集声明：`…要么 A，要么 B（两种状态之外不得有第三种）`。这类句子给的是
             # **穷尽性**——所有允许的状态被枚举完了，逐项对照即可判定，是可判的。
             # 旧锚点表只认「数字+单位/比较运算符」，把它判成不可判（盲跑 6 的 L490
             # `P9` 通过信号，2026-10-19）。不写「要么…要么…」那种半截形式，因为
             # 「要么快要么慢」并不可判；**只有加上穷尽性从句才是判据**。
             r"(?:之外|以外)(?:不得|不能)有|不得有第[二三]种|不允许有第[二三]种")
    # 第三次踩同一个坑（2026-10-19，盲跑 4 的真实产出物 9/11）：这次是**形态**不是措辞。
    # 产出物把每步的三件套写成「小标题 + `- **通过信号**：…`」条目（L601/618/643/658/
    # 672/686/698，条条可判：退出码 0／`{"ok": false, …}`／`scope == "own"`／工具集
    # 包含与不包含），而判据只扫表格，撞上一张 4 行的**汇总表**就报「只有 1/4 行含可判
    # 形式」。技能包从未规定通过信号必须写成表格——**形态不是判据**，同一份文档用表还是
    # 用列表，与「信号能不能判」无关。现在两种形态都收：表格里带「通过信号」列的每一行，
    # 以及 `- **通过信号**：…` 这类条目。
    lines = text.splitlines()

    def _is_sep(ln):
        cs = _table_cells(ln)
        return bool(cs) and all(re.fullmatch(r":?-{2,}:?", c) or not c for c in cs)

    signals = []
    head = None
    for i, ln in enumerate(lines):
        # **必须是表头行**（紧邻下一行是 `| --- |` 分隔行）。只按「这行有 `|` 又提到
        # 通过信号」去找，会撞上正文里**提到**「通过信号」四个字的数据行：盲跑 4 的
        # §9.1 欠账表有一格写着「按 §6 各步的"通过信号"补测试」，判据把它当表头，
        # 接着把「怎么补」那一列读成了信号列——3 条补救动作（`SHOW CREATE TABLE …`／
        # 重试 issue 反查／重填 `total_count`）被报成「不含可判形式」（2026-10-19）。
        # 表头是**结构**（后面必跟分隔行），不是「出现了某个词」。
        if "|" not in ln or "通过信号" not in ln:
            continue
        if i + 1 < len(lines) and _is_sep(lines[i + 1]):
            head = i
            break
    if head is not None:
        cells = _table_cells(lines[head])
        ci = next((k for k, c in enumerate(cells) if "通过信号" in c), None)
        if ci is not None:
            for j in range(head + 1, len(lines)):
                ln = lines[j]
                if not ln.lstrip().startswith("|"):
                    break
                cs = _table_cells(ln)
                # 分隔行不是数据行。不剔掉会被计入却永不含可判形式，结果是
                # **行数永远少一分**、任何文档都过不了（2026-10-19 首次跑就是栽在这里）。
                if _is_sep(ln):
                    continue
                if len(cs) > ci:
                    signals.append(("表格", cs[ci]))
    bullet = re.compile(r"\s*(?:[-*+]\s*)?(?:\*\*|__)?\s*通过信号\s*(?:\*\*|__)?\s*[：:]\s*(.+?)\s*$")
    for i, ln in enumerate(lines):
        m = bullet.match(ln)
        if m:
            signals.append(("条目", m.group(1)))
    # 纯交叉引用（「见 §6.3」）本身不含判据，但它的正文在别处出现、会另行收进来；
    # 若目标根本不存在，那是**引用完整性**的事，归 self_check 的引用检查，不在这里重复判。
    pointer = re.compile(r"^(?:见|详见|参见|同|如上|同上|↑+)\s*§?\s*[\w\-\.§]*$")
    judged = [(w, s) for w, s in signals if not pointer.match(s.strip().strip("`*_ |"))]
    if not signals:
        return False, "没有「通过信号」列或条目——验收不可判"
    if not judged:
        return False, "通过信号共 %d 处，但全是交叉引用，没有一处写出可判内容" % len(signals)
    # 行内格式不是判据的一部分：`从 `4` 变 `8`` 与 `从 4 变 8` 是同一句话。判据若不先抹掉
    # 反引号与加粗星号，就会把**被正确加码/加粗的数字**判成「不含可判形式」——盲跑 7 的
    # §6 通过信号有三条栽在这里（`失败集里有且只有它 `1` 条`、`块数从 `4` 变 `8` 再回到 `4``），
    # 而同族复发此前已多次。只抹 `` ` `` 与 `*`，**不抹下划线**：下划线是标识符的一部分
    # （`applicant_user_id`），抹掉会把名字切成两截。
    def _plain(x):
        return x.replace("`", "").replace("*", "")

    bad = [s[:40] for _, s in judged
           if re.search(vague, _plain(s)) and not re.search(solid, _plain(s))]
    loose = [s[:40] for _, s in judged if not re.search(solid, _plain(s))]
    if bad:
        return False, "%d/%d 处通过信号不可判（无判据措辞）：%s" % (len(bad), len(judged), "；".join(bad[:2]))
    if loose:
        return False, "%d/%d 处通过信号不含可判形式：%s" % (len(loose), len(judged), "；".join(loose[:2]))
    kinds = "、".join(sorted({w for w, _ in judged}))
    return True, "%d 处通过信号全部可判（来源：%s）" % (len(judged), kinds)

# ---------------- 用例 05：知识库增量重建（改造自有模块，对标非必选） ----------------
# 本组判据在**看到盲跑产出物之前**写定（2026-10-19）。事后照着答案出题不算测试。
# 与 01/03/04 的差别：这是「改造自己项目里已有模块」，GitHub 对标不是必选项，
# 所以判据给「显式声明不做对标」一条出路——测的是能不能识别边界，不是会不会硬套流程。
# 五个「这类需求一定会漏的点」：什么算改动／删除与改名／模型换代导致旧向量失效／
# 单点失败不许中断整批／失败项下次能重试。

def c5_two_pains(text):
    """「全量重建慢」与「单失败拖垮整批」必须是两个编号——修法完全不同。"""
    slow, fail = [], []
    for ln in text.splitlines():
        if not re.search(r"L0-P\d", ln):
            continue
        if re.search(r"全量|重建|二十分钟|20\s*分|慢|每次改", ln):
            slow.append(ln)
        if re.search(r"解析失败|失败|拖垮|整批|白跑|中断", ln):
            fail.append(ln)
    if not slow:
        return False, "没有把「全量重建慢」落成一条 L0-P"
    if not fail:
        return False, "没有把「单份解析失败拖垮整批」落成一条独立的 L0-P"
    ids = (set(re.findall(r"L0-P(\d+)", "".join(slow)))
           | set(re.findall(r"L0-P(\d+)", "".join(fail))))
    if len(ids) < 2:
        return False, "两类痛点写进同一个编号（L0-P%s）——增量与故障隔离是两套改法" % "".join(ids)
    return True, "慢与失败分成 %d 条痛点" % len(ids)

def c5_change_criterion(text):
    """「什么算改动过」必须给判据：mtime／内容 hash／依赖版本。

    只写「检测文件变化」是空话——变化怎么检测直接决定了三种行为：
    mtime 会被 checkout/拷贝重置、hash 要多读一遍全文、依赖版本变了旧向量全都不能用。
    """
    seen = []
    if re.search(r"mtime|修改时间|时间戳", text):
        seen.append("mtime")
    if re.search(r"\bhash\b|哈希|摘要|sha256|md5|checksum", text, re.I):
        seen.append("hash")
    if re.search(r"依赖版本|模型(版本|换代|升级)|embedding.{0,10}(版本|模型)|dimension|维度", text):
        seen.append("依赖版本")
    if not seen:
        return False, "没说「什么算改动过」——只写「检测变化」无法实现也无法验收"
    if len(seen) == 1 and seen[0] == "mtime":
        return False, "只用了 mtime——文件被 checkout/拷贝后 mtime 会变，会触发无意义重建"
    return True, "改动判据用了 %s" % "／".join(seen)

def c5_delete_rename(text):
    """删除与改名必须处理，否则索引里留下孤儿块，且这种脏是累积的。"""
    if not re.search(r"删除|删掉|移除|deleted", text):
        return False, "没处理「文档被删除」——索引里会留下孤儿块，且每轮都在累积"
    if not re.search(r"改名|重命名|rename|移动", text):
        return False, "没处理「文档改名/移动」——同一份文档会被当成「删一份+加一份」"
    return True, "删除与改名都有处置"

def c5_model_swap(text):
    """embedding 模型换代时旧向量全部失效——增量必须能识别这条失效。"""
    for i, ln in enumerate(text.splitlines(), 1):
        if re.search(r"模型(换代|升级|更换|变了)|换(模型|embedding)|embedding.{0,12}(版本|模型)|维度(变化|变)", ln):
            if re.search(r"全部|全量|失效|重建|作废|invalidat|不(能|可)复用", ln):
                return True, "L%d：模型换代导致旧向量失效已有处置" % i
    return False, "没提「embedding 模型换代后旧向量全部失效」——增量会把错误的向量当有效复用"

def c5_failure_isolated(text):
    """单份解析失败必须收敛成状态，不许 raise 出去中断整批；且失败项能重试。"""
    lines = text.splitlines()
    iso = retry = False
    for i, ln in enumerate(lines):
        w = "\n".join(lines[max(0, i - 2):i + 3])
        if re.search(r"解析失败|失败|异常", w) and re.search(
                r"continue|跳过|不中断|记录.{0,8}(状态|failed|失败)|failed|隔离|收敛", w):
            iso = True
        if re.search(r"重试|retry|下次(再|重建)|重新(解析|建)", w):
            retry = True
    if not iso:
        return False, "解析失败没被收敛成状态（跳过/记录 failed），会中断整批"
    if not retry:
        return False, "失败项没有「下次重建能重试」的路径——失败一次就永久漏掉"
    return True, "失败隔离 + 可重试两条都在"

def c5_alignment_choice(text):
    """对标是二选一：真走 search_repositories 且取回≥命中，或显式声明不做对标**并给理由**。

    踩过的坑（写本用例的第一版，2026-10-19）：初版只要匹配到「不做对标」四个字就 PASS，
    而它的通过文案是「显式声明不做对标，理由：不做对标」——**把声明原句当成理由念了一遍**。
    这是「用通过文案制造安全感」：听起来核了理由，实际一个字都没核。
    现在要求：声明句附近（±2 行）必须出现理由连词（因为/理由是/原因/因此/而不是），
    否则「不做对标」会变成万能的免责句，任何跳过对标的产出物都能过。
    """
    DECL = r"不做对标|无需对标|不适用.{0,6}对标|内部改造.{0,12}(不|无需)|没有对标的必要"
    REASON = r"因为|理由|原因|因此|而不是|需要的是|不是.{0,8}(找|抄|借用)"
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not re.search(DECL, ln):
            continue
        window = "\n".join(lines[max(0, i - 2):i + 3])
        if re.search(REASON, window):
            return True, "L%d 声明不做对标，且附近给了理由" % (i + 1)
        return False, ("L%d 声明不做对标，但附近（±2 行）没有任何理由连词——"
                       "「不做对标」不能当免责句用" % (i + 1))
    ok, msg = c1_discovery(text)
    if ok:
        return True, "走了候选发现：" + msg
    return False, "既没做候选发现（%s），也没显式声明不做对标——这是静默跳过" % msg

# ---------------- 用例 06：设备发放（需求文档完整 + 状态机/迁移/权限） ----------------
# 本组判据在**看到盲跑产出物之前**写定（2026-10-19）。事后照着答案出题不算测试。
# 与前五个的差别：这是**需求文档完整**的场景，不是一句话模糊需求。它测的是
# 「需求写得清楚时，会不会因为没事可澄清就跳过该做的裁决」——迁移回填语义、
# 旧数据是否追溯、并发怎么写，这三件需求单里都没写，但都必须裁决；
# 缺了它们文档照样能写得很好看，甚至自检全绿。

def c6_state_machine(text):
    """状态迁移必须显式写出「哪些合法、哪些必须被拒」，不能只写「加一个状态列」。

    需求单自己点了两条拒绝（重复发放、pending 直接发放），文档必须给出**判定位置**
    而不只是复述验收标准。判据看的是「拒绝条件 + 触发条件」是否成对出现。
    """
    lines = text.splitlines()
    has_state = any(re.search(r"已发放|dispatched|发放.{0,4}状态|状态.{0,4}发放", ln) for ln in lines)
    if not has_state:
        return False, "没有把「已发放」写成一个显式状态——只可能变成「审批通过后再记一笔」"
    rejects = 0
    for i, ln in enumerate(lines):
        if not re.search(r"拒绝|不许|禁止|不得|返回.{0,10}(错误|permission|拒绝)|reject", ln):
            continue
        w = "\n".join(lines[max(0, i - 2):i + 3])
        if re.search(r"重复|再次|已发放.{0,10}(再|重复)", w) or re.search(
                r"pending|待审批|未批准|未审批", w):
            rejects += 1
    if rejects < 2:
        return False, ("只写了 %d 条非法迁移的拒绝条件——需求单点了两条"
                       "（重复发放、pending 直接发放），少一条就说明状态机没写完" % rejects)
    return True, "%d 处非法迁移有明确拒绝条件" % rejects

def c6_migration(text):
    """数据库变更必须给默认值／可空性／回填，并裁决**旧行语义**。

    「表结构可以改，历史数据不能丢」这句话最容易的误读是「加个可空列就完了」——
    那样旧行是 NULL，而 NULL 在新语义里既不是「待发放」也不是「不追溯」，
    是第三个没人定义的状态。
    """
    got = []
    if re.search(r"默认值|default\s*=|server_default|可空|nullable|NOT\s+NULL", text, re.I):
        got.append("默认/可空性")
    if re.search(r"回填|backfill|迁移脚本|ALTER\s+TABLE|alembic|revision", text, re.I):
        got.append("迁移/回填")
    if re.search(r"历史数据|存量|旧(数据|行)|已有(申请|记录).{0,12}(怎么|如何|语义)", text):
        got.append("旧行语义")
    if len(got) < 3:
        return False, ("只给了 %s——「表结构可改但历史数据不能丢」必须交代默认值、回填、"
                       "以及回填后旧行是什么语义（待发放？不追溯？）" % "／".join(got or ["无"]))
    return True, "迁移三件齐：%s" % "／".join(got)

def c6_permission_layer(text):
    """发放权限必须落在业务工具内部，而不是只靠 Agent Tool 可见性。"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if not re.search(r"role|角色|权限|permission", ln):
            continue
        w = "\n".join(lines[max(0, i - 2):i + 3])
        if re.search(r"工具(内部|内|层)|业务(工具|层)|重新(读|取|检查)|再次(读|校验)|二次(校验|检查)", w):
            return True, "L%d：权限在业务工具层复查，不只靠 Agent Tool 可见性" % (i + 1)
    return False, ("没写「业务工具内部重新读 role」——只靠 Agent Tool 可见性不是权限，"
                   "是路由；员工绕过路由就能发放")

def c6_audit_triple(text):
    """发放必须记齐三件：谁发的、何时、资产编号；资产编号要有来源或校验。"""
    who = re.search(r"谁(发|操作)|发放人|操作人|dispatched_by|operator|reviewer_user_id|发放者", text)
    when = re.search(r"何时|时间|timestamp|dispatched_at|发放时间|datetime", text)
    what = re.search(r"资产编号|asset|序列号|serial|sn", text, re.I)
    missing = [n for n, m in (("谁发的", who), ("何时", when), ("资产编号", what)) if not m]
    if missing:
        return False, "发放审计缺 %s——需求单点了这三件" % "、".join(missing)
    if not re.search(r"校验|格式|来源|资产表|assets?\b|正则|非空|长度", text, re.I):
        return False, "记了资产编号但没说它从哪来／怎么校验——那就只是个自由文本字段"
    return True, "三件审计信息齐，且资产编号有来源或校验"

def c6_interrupt(text):
    """必须保住 interrupt() 人工确认，且不得用宽泛 try/except 包住 Agent Tool。"""
    if not re.search(r"interrupt\s*\(|Command\s*\(\s*resume", text):
        return False, "没有提到 interrupt()/Command(resume)——发放是写操作，必须走原有人工确认"
    if not re.search(r"不(得|要|能|许).{0,12}(try|except|捕获)|宽泛.{0,8}except|吞.{0,6}(中断|信号)", text):
        return False, ("没有写「不得用宽泛 try/except 包住 Agent Tool」——"
                       "包住就会吞掉 LangGraph 的中断信号，人工确认直接失效")
    return True, "保住 interrupt()，并写明不许宽泛 except 吞中断"

def c6_concurrency(text):
    """重复发放/并发必须用机制保证，不能只写「先查状态再更新」。"""
    mech = re.search(r"条件更新|UPDATE\s+.{0,26}WHERE|唯一(约束|索引)|unique|行锁|SELECT\s+.{0,12}FOR\s+UPDATE|"
                     r"幂等键|idempot|乐观锁|版本号|CAS\b", text, re.I)
    if not mech:
        return False, ("没给并发机制（条件更新／唯一约束／行锁／幂等键）——"
                       "「先查状态再更新」中间有窗口，两个请求都能通过检查")
    # 反方向：不能一边写「用条件更新」一边又只描述 check-then-write 而不给 writer
    if not re.search(r"WHERE|where", text) and not re.search(r"唯一(约束|索引)|unique", text, re.I):
        return False, "提到了并发但没给出具体的判定式（WHERE 条件或唯一约束）——那是口号"
    return True, "并发用机制保证，且给了具体判定式"


CASES = {
    "01": (["① 先判适用性", "② L0-P/C/S 编号产出物", "③ 直搜且取回≥命中",
            "④ 第二候选 + 失效条件", "⑤ 可复核取证（禁裸行号/README 当结论）",
            "⑥ 0–9 节 + 真跑自检", "⑦ 只读声明"],
           lambda t, a: [c1_applicability(t), c1_l0_artifacts(t), c1_discovery(t),
                         c1_candidates(t), c1_evidence(t),
                         check_structure(t, a.doc), check_readonly(t)]),
    "02": (["① 引真实 文件:行", "② [待确认] 对账", "③ 安全边界",
            "④ 上游官方实现", "⑤ 0–9 节 + 真跑自检", "⑥ 只读声明"],
           lambda t, a: [check_file_line(t, a.root), check_marker(t), check_security(t),
                         check_upstream(t), check_structure(t, a.doc), check_readonly(t)]),
    "03": (["① 先澄清再搜／降级", "② 框架排除", "③ 组合型拆分依据",
            "④ 发现路径无范围禁忌", "⑤ 0 候选降级级别", "⑥ 未解项+下一步+自检退出码"],
           lambda t, a: [c3_gate1(t), c3_framework(t), c3_split(t),
                         c3_discovery(t), c3_downgrade(t), c3_tail(t)]),
    "04": (["① 两类现象拆成独立痛点", "② 幂等/退避/上限三条约束",
            "③ 现象归因到不同机制", "④ 对照本项目真实代码",
            "⑤ 通过信号全是可判谓词", "⑥ L0-P/C/S 编号产出物",
            "⑦ 直搜且取回≥命中", "⑧ 0–9 节 + 真跑自检", "⑨ 只读声明"],
           lambda t, a: [c4_pain_split(t), c4_constraints(t), c4_attribution(t),
                         c4_local_code(t, a.root), c4_predicates(t),
                         c1_l0_artifacts(t), c1_discovery(t),
                         check_structure(t, a.doc), check_readonly(t)]),
    "05": (["① 慢与失败拆成独立痛点", "② 改动判据不是只有 mtime",
            "③ 删除与改名有处置", "④ 模型换代致旧向量失效",
            "⑤ 失败隔离且可重试", "⑥ 对标二选一（做 或 显式不做）",
            "⑦ 通过信号全是可判谓词", "⑧ L0-P/C/S 编号产出物",
            "⑨ 0–9 节 + 真跑自检", "⑩ 只读声明"],
           lambda t, a: [c5_two_pains(t), c5_change_criterion(t), c5_delete_rename(t),
                         c5_model_swap(t), c5_failure_isolated(t),
                         c5_alignment_choice(t), c4_predicates(t),
                         c1_l0_artifacts(t),
                         check_structure(t, a.doc), check_readonly(t)]),
    "06": (["① 状态机含非法迁移的拒绝条件", "② 迁移/回填/旧行语义三件齐",
            "③ 权限落在业务工具层", "④ 发放审计三件 + 资产编号可校验",
            "⑤ 保住 interrupt() 且不吞中断", "⑥ 并发用机制而非 check-then-write",
            "⑦ 对照本项目真实代码", "⑧ 对标二选一（做 或 显式不做）",
            "⑨ 通过信号可判 + L0 编号", "⑩ 0–9 节 + 真跑自检", "⑪ 只读声明"],
           lambda t, a: [c6_state_machine(t), c6_migration(t), c6_permission_layer(t),
                         c6_audit_triple(t), c6_interrupt(t), c6_concurrency(t),
                         c4_local_code(t, a.root), c5_alignment_choice(t),
                         c4_predicates(t), c1_l0_artifacts(t),
                         check_structure(t, a.doc), check_readonly(t)]),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    # 先判「这个用例有没有谓词」，再去读用例文件：否则 `--case 09` 会先报
    # "找不到用例文件"（exit 1），把「未实现」伪装成「跑失败」——而这两件事
    # 对读分数的人是相反的结论。未实现必须是 64 并明说。
    key = "%02d" % int(a.case)
    if key not in CASES:
        print("用例 %s 还没有谓词（只有 %s 有）——不是通过，是未实现" % (key, "/".join(sorted(CASES))))
        return 64
    case = load(a.case)
    if not os.path.exists(a.doc):
        print("读不到产出物：%s\n（用例未跑或产出物未入库 → **没有分数**，不等于通过）" % a.doc)
        return 64
    text = open(a.doc, encoding="utf-8", errors="replace").read()
    names, mk = CASES[key]
    print("用例 %s：%s" % (key, case["query"][:60]))
    print("产出物：%s（%d 字符）\n" % (a.doc, len(text)))
    passed = 0
    na = 0
    for name, (ok, why) in zip(names, mk(text, a)):
        # 谓词可以返回 `None`＝**前置条件不成立（不适用）**。三态而不是两态，是因为
        # 「这条不适用」与「这条没做到」是相反结论；把前者记成 FAIL 会制造系统性假红
        # （盲跑 8 用例 02 的 ② 就是这样），而**静默跳过**又会让缺口永远不出现。
        # 所以：打印 `N/A ` + 理由、计进 na、从分母减掉，并在总结行显示 na。
        tag = "N/A " if ok is None else ("PASS" if ok else "FAIL")
        print("%s %-20s %s" % (tag, name, why))
        if ok is None:
            na += 1
        else:
            passed += ok
    total = len(names)
    denom = total - na
    line = "\n机械可判 %d/%d" % (passed, denom)
    if na:
        line += ("（另有 %d 条前置条件不成立、判 N/A：分母已减去，未静默跳过；"
                 "逐条理由见上方 `N/A` 行）" % na)
    line += "；判不了的只有「语义相关性／证据是否真支持结论」，需人工"
    print(line)
    # 容差一条：判据里总有「语义相关性」这类机器判不动的东西，满分的验收目标定在
    # 「至多一条不过」。分母是**减去 N/A 后**的（否则全 N/A 会变成 0/0 而通过）。
    if denom == 0:
        return 64
    return 0 if passed >= denom - 1 else 1

if __name__ == "__main__":
    sys.exit(main())
