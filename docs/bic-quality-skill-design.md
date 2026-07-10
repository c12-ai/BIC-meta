# BIC Quality Skill 设计说明

## 文档状态

- 状态：当前阶段已实现
- 适用版本：`bic-quality-guan-ping-ce` 只读分析版
- 最后更新：2026-07-10
- 产品背景：[`Production-PRD.md`](../Production-PRD.md)
- 源码位置：[`tools/bic-quality-kit/`](../tools/bic-quality-kit/)

本文档说明当前已经落地的 BIC Quality Skill。它沿用早期方案中“通过
Claude / Codex 对话触发项目级质量分析”的产品方向，但以当前代码和输出
契约为准，不再保留已经废弃的风险等级、Capability 标签、Verification
Scope 和覆盖率推断。

## 最终产品目标

长期来看，BIC Quality Test Agent 可以演进成一个项目级质量评测入口。
它可以在代码变化、PR、需求评审和上线前检查等场景中，识别影响范围、
建立需求与测试的对应关系、选择验证策略、执行必要测试、收集证据，并在
需要时移交给专项 E2E 能力完成真实链路验证。

长期产品最终需要帮助开发者回答：

1. 这次改动影响了哪些仓库和功能模块？
2. 当前项目里有哪些测试与这些改动真正相关？
3. 哪些新增或修改的行为缺少测试？
4. 实际验证结果是否可信，还剩下什么未验证内容？

上述目标属于长期演进方向。当前阶段只实现前三个问题中的只读静态分析
部分，不执行测试，也不对运行结果做结论。

## 当前阶段定位

当前交付物是安装在 Claude / Codex 项目环境中的 BIC Quality Skill。用户
通过自然语言触发，Skill 读取完整本地变更集，定位受影响仓库和功能模块，
检查当前仓库已有测试与改动对象的对应关系，并生成一份结构化
`BIC Quality Brief`。

当前 Skill 是质量分析器，不是测试执行平台。它回答：

- 当前分支相对本地基线有哪些变化？
- 变化位于哪个真实 Git 仓库？
- 每个仓库中的变化属于哪个功能模块？
- 是否直接涉及多个仓库？
- 哪些现有测试直接、间接或可能与改动相关？
- 哪些改动对象建议新增测试，哪些已有测试建议完善？

当前 Skill 不回答“测试是否通过”，也不通过 coverage 百分比、风险分数或
置信度标签代替真实测试证据。

## 相对早期方案的关键变化

早期方案将路径映射为 Repo Scope、Capability Scope、Risk Level 和
Verification Scope，再据此推荐测试。当前实现已经收敛为更直接、可验证的
模型：

```text
Git 变更
  → 真实仓库
  → 功能模块
  → 改动文件 / 改动对象
  → 现有测试对应关系
  → 新增测试 / 完善测试建议
```

主要变化如下：

- 删除 `high / medium / low` 风险等级和重复标签。
- 删除 `configured-coverage`、`repo-type-match`、`coverage_gaps` 和
  `coverage_unconfirmed` 等容易被误解为真实覆盖的字段。
- 仓库身份来自 Git 动态发现，不再维护硬编码仓库列表。
- 新仓库优先使用目录结构推导模块，不把 `api`、`models`、`events` 等通用
  目录词猜成业务能力。
- 测试判断从“测试目录是否存在”升级为“测试是否导入、调用或通过一层调用
  链进入改动对象，并且是否存在有效断言”。
- 将“测试与改动如何关联”和“是否需要补测试”拆成两个独立维度。

## 当前架构

当前架构分为四个层次。

### 1. 对话入口层

`SKILL.md` 是 Claude / Codex 的统一入口。它负责理解用户是否指定了基线
分支、调用只读脚本、按需读取规则，并把结构化分析结果整理成一份
`BIC Quality Brief`。

典型触发方式：

```text
用 BIC quality 看下当前 diff
```

```text
用 BIC quality 看当前分支相对 main 的改动
```

```text
帮我看看这次改动涉及哪些仓库和模块，现有测试还缺什么
```

### 2. 变更与模块分析层

`quality_context.py` 负责总流程编排，包括工作区发现、Git 变更收集、模块
映射、测试资产读取和最终结构化输出。

它动态发现 `BIC-meta` 根仓库和直接子目录中的独立 Git 仓库。每个仓库
独立解析分支、HEAD、本地基线和 merge base，避免一个仓库的基线判断污染
另一个仓库。

模块映射先使用 `scope-taxonomy.yaml` 中的显式 BIC 业务规则；没有命中时，
根据 `app`、`src`、`packages`、`services`、`lib` 等稳定源码根目录保留结构
模块；仍然无法判断的文件保留为 `unmapped`，不会凭空创造业务语义。

### 3. 测试对应性分析层

该层由三个确定性脚本组成：

- `symbol_extraction.py`：提取新增文件中的 Python、JavaScript、TypeScript
  声明、路由、事件和类型；对修改、重命名、删除或不支持的语言保留文件级
  改动对象。
- `test_assets.py`：发现真实测试文件、测试配置和命令入口，并解析每个测试
  用例的导入、引用标识符、场景名称、断言以及 skip、xfail、todo 状态。
- `test_relations.py`：以 `(repo, module_scope)` 为身份，将改动对象与现有
  测试建立直接、间接或可能相关关系，再生成补测建议。

所有分析都通过读取文件或 AST 完成，不导入项目模块，不执行测试。

### 4. 规则与交付层

`config/` 保存机器可读的模块规则和可选测试语义关系；`references/` 保存
仓库说明、模块映射规则、测试对应性规则和报告模板。

`test-inventory.yaml` 不再声明“测试已经覆盖模块”，而是补充静态代码无法
判断的语义关系，特别是跨仓 E2E 或业务流程测试。模块关系使用
`relates_modules`，明确对象关系可以使用 `relates_objects`；跨仓关系必须在
`relates_repository_modules` 中同时指定目标仓库和模块。

## 完整分析链路

```text
用户对话触发
        ↓
解析可选 base ref / worktree-only 意图
        ↓
动态发现 BIC-meta 与直接子 Git 仓库
        ↓
逐仓收集 committed / staged / worktree / untracked 变化
        ↓
按仓库映射 explicit / structural / unmapped 功能模块
        ↓
提取新增声明或文件级改动对象
        ↓
发现并解析当前仓库真实测试资产
        ↓
建立直接 / 安全一层调用 / 显式 / 可能相关关系
        ↓
生成建议新增 / 建议完善 / 暂未发现明显缺口
        ↓
输出一份 BIC Quality Brief
```

## Diff 收集设计

默认分析的是当前 checkout 的 `HEAD` 相对本地可用基线的完整变化，而不是
只看未提交文件。

每个仓库按以下顺序寻找本地基线：

1. 用户通过对话显式指定的 `--base-ref`。
2. CI 环境提供的目标分支。
3. `origin/main`、`main`、`origin/master`、`master`。

找到基线后读取 `merge-base(base, HEAD)..HEAD` 的已提交变化，再合并：

- unstaged worktree changes；
- staged changes；
- untracked files；
- rename、delete、copy 等变更类型。

显式基线不存在时只报告 warning，不静默替换成其他分支。Skill 不执行
`git fetch`、`git checkout` 或任何 Git 写操作。用户明确只想看未提交变化时，
可以使用 `--worktree-only`。

## 仓库与功能模块设计

公开的 scope 输出只保留三个核心事实：

```text
affected_repositories
modules_by_repository
direct_cross_repository
```

`affected_repositories` 使用真实发现到的 Git 仓库名；
`modules_by_repository` 在每个仓库下面列出功能模块和文件依据；
`direct_cross_repository` 仅表示本次变更是否直接修改了多个仓库。

模块来源分为：

- `explicit`：命中已维护的 BIC 业务模块规则；
- `structural`：根据仓库内稳定源码目录推导；
- `unmapped`：当前没有足够依据，但文件仍保留在报告中。

这三个值说明“模块是怎么得到的”，不是风险或置信度标签。

## 测试资产发现设计

Skill 自动发现：

- Python：`test_*.py`、`*_test.py`；
- JavaScript / TypeScript：`*.test.*`、`*.spec.*`；
- Pytest、Vitest、Jest、Playwright 配置；
- `pyproject.toml` 和 `package.json` 中的测试入口。

测试配置和命令只说明项目存在测试基础设施，不能当作测试证据。空测试目录
也不算测试资产。只有具体测试文件才会进入测试对应性分析。

测试文件按用例解析，避免把同一文件中的不同测试混在一起。例如：一个被
skip 的相关测试，不能因为文件中另一个无关测试有断言就被判定为有效。
当前解析支持 Python 和 JavaScript / TypeScript 的相对导入、命名别名、
unittest/pytest 断言、`expect`/`assert`、skip、xfail、todo 和禁用 suite。

## 测试对应关系设计

测试对应关系描述的是事实来源，不使用高、中、低评分。

### 直接相关

测试位于同一仓库，并且导入改动文件、引用改动对象或调用相关导出。单纯
同名标识符、相同目录或仓库名不会形成直接关系。

### 间接相关

测试导入一个本地入口，该入口再导入或引用改动对象，形成安全的一层调用
关系；或者 `test-inventory.yaml` 明确声明了模块或对象关系。跨仓间接关系
只有显式指定目标仓库后才成立。

### 可能相关

测试名称、文件名或路径与功能模块存在语义线索，但没有找到代码级关系。
它用于帮助开发者继续查找，不能单独证明改动对象已有测试。

## 补测试判断设计

测试对应关系与补测动作分开计算。

### 建议新增测试

改动对象没有找到对象级直接关系、安全一层调用关系或显式对象映射。宽泛
的模块配置或场景名称不能替所有改动对象清除缺口。

### 建议完善测试

找到了对象级关系，但测试被 skip、xfail、todo，缺少有效断言，或者只有
同文件候选关系。对于修改文件，如果当前只能定位到文件级改动对象，也会
保守地建议确认或完善测试，而不是声称具体函数已经覆盖。

### 暂未发现明显缺口

存在启用中的直接测试、安全一层调用测试或显式对象映射，并且对应测试用例
包含有效断言。该结论仍然只表示“静态检查未发现明显缺口”，不表示测试已
执行或一定通过。

## 输出交付物

当前阶段只输出一份固定结构的 `BIC Quality Brief`：

```text
BIC Quality Brief

Change Set
- 变更摘要：
- 变更仓库：
- 是否直接跨仓：
- 本地基线与 warning：

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

报告中的结论必须引用具体文件、改动对象、测试路径、导入/引用、测试名称、
断言、禁用状态或显式配置关系。

## Skill Kit 目录结构

```text
tools/bic-quality-kit/
├── README.md
├── install.sh
├── verify-install.sh
├── tests/
│   └── test_quality_context.py
└── skill/
    └── bic-quality-guan-ping-ce/
        ├── SKILL.md
        ├── config/
        │   ├── scope-taxonomy.yaml
        │   └── test-inventory.yaml
        ├── references/
        │   ├── workspace-map.md
        │   ├── scope-taxonomy.md
        │   ├── test-analysis-rules.md
        │   └── deliverables.md
        └── scripts/
            ├── collect-quality-context.sh
            ├── detect-impact-scope.sh
            ├── inspect-test-inventory.sh
            ├── suggest-test-scope.sh
            ├── quality_context.py
            ├── symbol_extraction.py
            ├── test_assets.py
            └── test_relations.py
```

`tools/bic-quality-kit/skill/` 是唯一源码。`.agents/skills/` 和
`.claude/skills/` 是安装副本。安装时旧版本备份会移到
`.trellis/.runtime/skill-backups/`，避免 Codex 或 Claude 同时发现多个同名
Skill。

## 脚本边界

当前脚本允许：

- 读取 Git 分支、ref、merge base、diff 和 status；
- 动态发现本地 Git 仓库；
- 扫描源码和测试文件；
- 读取 Pytest、Vitest、Jest、Playwright、package 和 pyproject 配置；
- 读取 Skill 配置和项目文档；
- 输出 JSON 和最终质量报告。

当前脚本禁止：

- 执行项目测试；
- 启动或重启服务；
- reset 数据库或 MQ；
- kill 端口或进程；
- 修改业务代码；
- fetch、checkout 或修改 Git 状态；
- 调用 live bench、Playwright 或专项 E2E runner。

如果用户要求运行测试，当前 Skill 只能给出建议命令或说明需要切换到后续
测试执行能力。

## 部署方式

在 `BIC-meta` 根目录执行：

```bash
./tools/bic-quality-kit/install.sh
./tools/bic-quality-kit/verify-install.sh
```

安装目标：

```text
.agents/skills/bic-quality-guan-ping-ce
.claude/skills/bic-quality-guan-ping-ce
```

`verify-install.sh` 会验证配置格式、Skill 必需文件、行为夹具、脚本工作区
解析以及源码与两份安装副本的一致性。

## 当前验收结果

当前版本已经满足：

1. Claude / Codex 可以发现并调用 Skill。
2. 默认 diff 同时包含本地分支已提交变化和 worktree 变化。
3. 用户可以通过对话显式指定本地基线分支。
4. 新增直接子 Git 仓库不需要修改硬编码仓库列表。
5. 报告保留仓库、模块和是否直接跨仓三个核心事实。
6. 新路径可以使用结构模块，不会被通用目录词错误映射成业务标签。
7. 测试发现基于具体文件，空目录和配置文件不会被当作已有测试。
8. 测试判断支持直接关系、安全一层调用、显式跨仓关系和可能相关候选。
9. 补测建议区分新增、完善和暂未发现明显缺口。
10. Skill 全程不执行被分析仓库的测试或运行环境操作。
11. 自动化行为夹具和完整安装验证均通过。

## 当前限制

- 只分析 checkout 的本地 `HEAD`，不主动查询远程 PR，也不 fetch 远程分支。
- 仓库自动发现范围是 `BIC-meta` 根仓库和直接子 Git 仓库。
- 新增或未跟踪的 Python、JavaScript、TypeScript 文件可以提取声明；修改、
  重命名或删除文件目前采用文件级对象，因为还没有实现 diff hunk 到函数体的
  精确归属。
- 自动间接关系只追踪一层本地源码调用，不构建完整调用图。
- 其他语言保留文件级改动对象，不解析内部声明。
- 静态分析无法证明测试可以运行、已经通过或覆盖所有业务行为。

## 后续演进方向

下一阶段可以在不破坏当前只读入口的基础上逐步增加：

1. 将 PRD、验收条件和 PR 描述中的行为映射到测试，形成需求级
   traceability。
2. 增加 diff hunk 到函数、方法和分支的精确归属。
3. 生成更精确的候选测试命令，但仍由用户或后续执行层决定是否运行。
4. 接入 CI 已产生的测试证据，区分“存在测试”和“测试实际通过”。
5. 增加独立的测试执行、失败诊断和专项 E2E 移交层。

这些能力应作为后续层次增加，不应让当前只读 Skill 在默认情况下启动环境
或执行测试。

## Change Log

- 2026-07-10：根据已实现 Skill 重写设计文档；移除风险等级和覆盖率推断，
  补充动态多仓 diff、功能模块映射、改动对象提取、测试对应性和补测建议
  的当前契约。
