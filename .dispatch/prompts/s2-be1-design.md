# S2 任务：#128 BE-1 设计笔记（只读，先出一页 design note 再动码）

你是 S2（设计，只读）。#128 交付物 5 对 BE-1（L 级：三层落库）明确建议"issue 内先出一页 design note 再动码"，本单就是它。仓：BIC-agent-service origin/main（1d9fb7a）+ #128 五份交付物。

## 交付
一页 design note 评论到 #128：①trials.execution_status 新列 + jobs.outcome/review 两轴的 schema migration 方案（alembic 序、默认值回填策略——历史行怎么补）；②事件回放兼容分析（announced_transitions/快照重建路径逐一核对，列出会被新语义影响的 apply）；③#37 时序与 #5 游标推进在新模型下的等价性证明；④experiments.stage 值域扩展选项表（牵 #80 词表与页头文案）；⑤实施切片建议（能否拆 2-3 个可独立合并的 PR）。写完转述一句到 dispatch done。不改码。
