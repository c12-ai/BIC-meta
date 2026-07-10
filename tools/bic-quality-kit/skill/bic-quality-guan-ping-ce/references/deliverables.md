# Deliverable Format

Current phase returns one report: `BIC Quality Brief`.

```text
BIC Quality Brief

Change Set
- 变更摘要：
- 变更仓库：
- 是否直接跨仓：

Module Mapping
- Repo / Module：
- 映射来源：
- 文件证据：

Test Correspondence
- 直接相关测试：
- 间接相关测试：
- 可能相关测试：
- 对应依据：

Missing Tests & Next Step
- 建议新增测试：
- 建议完善测试：
- 暂未发现明显缺口：
- 下一步建议：
```

Keep the brief concise. Cite the selected base/merge-base or warning, change
sources, concrete file paths and objects, module ids, test imports/references,
assertions, disabled state, and explicit relations. Do not emit confidence,
risk, priority, evidence-type, or coverage-percentage labels. State that tests
were not executed and static correspondence does not prove pass/fail.
