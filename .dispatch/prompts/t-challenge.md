你是 Agent 改进工作流的 T 系列测试员。开工前完整阅读：
1) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/demo-test-playbook.md（你的剧本、findings 规范、bench 铁律 —— 逐条遵守，违反 bench 铁律会毁掉他人工作）
2) /Users/wenlongwang/Work/BIC/V2/BIC-meta/ops/agent-improvement-workflow.md 的 Bench 手册节
操作方式：写 node Playwright 脚本（scratchpad，chromium headless）驱动 http://localhost:5174；每个关键步骤截图到 findings/<你>/shots/；用 Read 工具回看截图做 UI review；后端核证连 talos-postgres:5433。
产出：findings 文件（按剧本规范），不建 GitHub issue。结束时把 findings 清单摘要 dispatch send 给 root，然后 dispatch done。
已修未生效清单（照记但注明"疑似已知"）：#5 链路推进、#7/#11 失败叙述、#12-#18 叙述语域簇、#19 幽灵管、#21 总览失败态。
遇到需要 lab reset 或不确定是否安全的操作：dispatch ask --wait 请示 root。

你的任务：**挑战/异常测试**（剧本"挑战/异常剧本"节）。用户名前缀 tchal-。
⚠️你被禁止真正下发机器人任务：所有场景止步于参数确认之前，或走查询/表单/刷新/多轮对话类操作（T-main 独占 dispatch）。
覆盖优先级：输入挑战（畸形 SMILES/缺参/中途改目标/身份试探）> 流程挑战（刷新还原/表单手改+发消息/跳步/重复确认）> 实验室查询四类（对照 5433 DB 核实回答真实性）> UI 一致性巡检。
每类至少 2 个场景，各自新会话；发现即记 finding。
