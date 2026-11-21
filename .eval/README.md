# 内部实测证据

这个目录**在本仓库里是空的**，这是刻意的。

仓库里原来放着作者本机的实验脚手架：单条探针脚本、变异夹具、跑批产物、门禁审计器，约 2.2 MB。它们依赖作者本机的目录布局，对使用者没有价值，且部分是中途废弃的尝试，所以不随仓库发布。

**可复现的结论不在这里，在 [`../references/verification-log.md`](../references/verification-log.md)。** 那份账本记录了每一次实测的版本、验证方式、覆盖范围与结论（含跑不通的分支），共 130 余条版本行。

## 想自己验证这个 skill？

不需要这些脚手架，跑这两条就够：

```bash
# 1. SKILL.md 自身一致性（版本对账／哨兵位置／禁用形态／自述项数）
python references/self_check.py --skill SKILL.md

# 2. 任务级评测的可机械判定那一半
python evals/harness.py --case 02 --doc <一份真实产出物.md> --root <需求方项目根>
```

判据说明见 [`../evals/README.md`](../evals/README.md)，脚本射程见 [`../references/delivery-checklist.md`](../references/delivery-checklist.md) §三。
