# S2 任务：ELN 数据缺口追踪更新（只读）

你是调查员（只读）。目标：更新 https://github.com/c12-ai/BIC-agent-service/issues/63#issuecomment-4921384223 的数据缺口现状（那是上一轮 recheck：CC/UV 图已解锁、余 5 缺口）。

## 任务
1. 读该 comment 的缺口清单，逐项对照当前 bench-verify 现状重新核定（今晚新增事实：CC 照片链全通 #112/#115/#119、化合物名 chem-service+草稿期补名 #95/#103、CC 峰判读真数据但 tubes/rt 空 #127、chem-service :8010 活）。DB talos_agent_db 可取真实数据佐证。
2. 每项：已解决（引 issue/sha）/ 部分（缺什么）/ 未动；剩余缺口给推荐解决顺序（对照 #127 路线 A 外部依赖）。
3. 以新 comment 落到 BIC-agent-service#63（中文，Facts/Interpretation 分节，格式对齐旧 comment）。

不改代码。收尾 dispatch done（FACTS/Judgment 分开）。
