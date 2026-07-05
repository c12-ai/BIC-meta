# 配置表 correction draft — TLC sample-tube shelf model (for Drake to submit to Feishu)

Target document: 实验室信息维护配置表 (wiki `AKmcweV5iiorPWkQTY1cBdWOnxc`).

> Revised 2026-07-05 under parent decision D4: the earlier draft proposed adding a "bench
> dispatch box" row — superseded. The bench 2ml slots are robot-internal parking (the robot
> carries the selected shelf box there itself, first round only), so they do NOT belong in the
> chemist-facing material configuration. What needs correcting instead:

## 1. Confirm the sample-tube shelf rows are the chemist surface (no table change)

The existing TLC Rack rows stand as the authority — 样品管盒 on L2 RIGHT and L1 RIGHT
(5 box slots per layer, 5×4 cells, 有特殊性). The implemented lab state now matches them
exactly: location ids `tlc_supply_shelf_l{1,2}_right_c{1..5}`, per the same coordinate codec the
robot protocol uses (`layer_from_bottom` / `side` / `column_from_left`).

## 2. Corrections to make while in the document (root PRD rules 8–9)

- 任务物料准备清单 TLC 样品管 数量 `1 or 2` → `2–4`（同盒、同行、从第 1 列起连续）。
- 人工指定-分配槽位 "只能点击空位" → 选择已维护的物料（空位仅在维护模式下填充）。
- 建议补充一句说明（任务物料准备清单 TLC 行备注）：样品管盒由机器人在首轮自动从备料架搬运至工作台；
  取料坐标由系统按所选盒子的实际货架位置解析，非固定坐标。

## 3. No new rows needed

The robot Workspace parking slots (2ml/50ml/tip 台面槽位) are robot-internal execution
addresses, owned by the robot protocol and lab-service seed — keeping them out of the reviewed
chemist-facing 配置表 is deliberate (the PRD records this split in rule 7).
