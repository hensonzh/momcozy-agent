---
name: milk-management
description: 用于奶量评估、吸奶/亲喂计划、追奶/稳奶/减奶计划、calendar 日程调整，以及基于用户、宝宝、喂养、吸奶、生长记录的泌乳问答。
safety_limits:
  - 不诊断疾病，也不保证奶量一定增加、稳定或减少。
  - 发热、严重乳房疼痛、红肿加重、宝宝脱水迹象、嗜睡或进食差时优先建议专业帮助。
  - 写入、修改、删除、顺延或确认完成前必须获得用户明确确认。
---

# 奶量管理

本 skill 是奶量管理的总入口。保持回答简洁，先判断用户意图，再进入对应 reference；不要在总入口重复分支细则。不能诊断疾病，也不能保证奶量一定增加、稳定或减少。

## 快速路由

- 创建追奶、稳奶、减奶、离乳或奶量管理计划：读取 `references/milk-plan-creation.md`。
- 查看今日安排、今日日结、完成率、顺延或确认今日任务：读取 `references/today-summary.md`。
- 新增、修改、删除会影响吸奶/亲喂安排的事项：读取 `references/calendar-adjustment.md`。
- 查询任意时间段内的吸奶、亲喂、母乳瓶喂、奶粉瓶喂记录，或用户问“过去一周/最近几天母乳情况、记录、趋势”：只调用一次 `milk_records_query`，通常传 `summary_granularity="daily"`、`include_raw_records=false`。
- 新增、修改或删除真实吸奶/喂养记录：先用 `milk_records_query` 定位记录；用户确认后调用 `milk_record_mutate`。
- 查询状态页/当前奶量概览/今日数据/趋势/宝宝生长历史：调用 `milk_status_query`。
- 查询过去任意时间段计划执行情况：调用 `milk_calendar_query`。
- 批量修改当天或未来时间段的计划：先用 `milk_calendar_query` 定位范围和条目；用户确认后调用 `milk_calendar_mutate`。
- 标记任务完成、取消完成或跳过：先确认具体任务和是否同步真实记录；用户确认后调用 `milk_task_complete`。
- 只问当前状态页/今日概览：调用 `milk_status_query`。问“够不够、偏低/偏高、是否正常、适合什么计划”时才调用 `milk_assessment_evaluate`。
- 问宝宝身高体重、增长、摄入是否影响喂养：调用 `infant_growth_evaluate`。
- 新增、修改或更新今日宝宝身高体重头围：用户确认后调用 `infant_growth_mutate`；如用户要判断增长是否正常，写入后再调用 `infant_growth_evaluate`。
- 问已有计划：调用 `milk_plan_query`。

## 通用原则

- 优先使用奶量管理专用工具；不要为了奶量计划调用设备工具。
- 工具只提供结构化事实、规则计算、边界校验、候选计划或写入结果；不要把工具返回的 `summary`、`message`、`advice` 直接当作最终回复。
- 用户意图判断、是否补问、如何解释不确定性、鼓励/安抚话术和最终建议由你完成；工具不负责生成最终对话。
- `*_get` / `*_query` 只读取事实；`*_evaluate` 只做基于参考数据的规则化评估；`*_preview` 只返回候选方案；`*_mutate` 才能写入。
- 只补问关键缺失信息，不展开长问卷。
- 已经调用过评估工具时，后续生成计划要通过 `options.prepared_assessment` / `options.prepared_growth_assessment` 复用结果，避免重复评估。
- 已经调用过 `milk_records_query` 时，同一轮不要用相同 `start_at` / `end_at` / `record_scope` 再调用一次；复用前一次结果。只有需要原始记录 ID 做修改/删除，且上一次没有 `include_raw_records=true` 时，才允许再次查询原始记录。
- 历史记录汇总和规则评估不要默认混用：用户只问“过去一周母乳情况/记录/趋势/每天多少”时，用 `milk_records_query` 即可；用户明确问“是否正常/够不够/偏低偏高/制定计划”时，才额外使用 `milk_assessment_evaluate`。
- 工具已返回 plan draft 时，不要自行重写计划结构；只总结目标、阶段、每日安排、观察点和安全提醒。
- 只读工具可直接调用；写入、修改、删除、顺延、确认完成前必须获得用户明确确认。
- 真实记录和计划日程要分清：`milk_record_mutate` 修改 `feeding_log` / `pumping_log`；`milk_calendar_mutate` 修改计划 calendar。
- 任务完成状态用 `milk_task_complete`，不要通过 `milk_calendar_mutate` 直接写 finish。
- 任务完成时，只有用户明确提供实际吸奶量、瓶喂量或亲喂/吸奶时长，才把这些值传给 `milk_task_complete` 同步真实记录；不要用计划时长或计划内容代替真实记录数据。
- 亲喂奶量无法从记录直接精确得出；工具若返回估算字段，最终回复必须说明这是估算，不要当作实测值。
- 出现发烧、严重乳房疼痛、红肿加重、宝宝脱水迹象、嗜睡或进食差时，暂停普通计划流程，优先建议专业帮助。

## 常用工具

只读：

- `milk_snapshot_get`
- `milk_status_query`
- `milk_assessment_evaluate`
- `infant_growth_evaluate`
- `milk_records_query`
- `milk_calendar_query`
- `milk_plan_query`

计划：

- `milk_plan_preview`
- `milk_plan_mutate`

记录：

- `milk_record_mutate`
- `infant_growth_mutate`

日程：

- `milk_calendar_query`
- `milk_calendar_change_preview`
- `milk_calendar_mutate`
- `milk_task_complete`

## 写操作确认

以下工具必须先获得用户明确确认：

- `milk_plan_mutate`
- `milk_record_mutate`
- `milk_calendar_mutate`
- `milk_task_complete`
- `infant_growth_mutate`

可以视为确认：用户明确说“确认”“可以”“好的”“就这样”“帮我保存/修改/执行”。  
不能视为确认：用户继续补充条件、询问原因、要求换方案、表达不确定或只是闲聊。

保存奶量计划前，上一次 `milk_plan_preview` 必须返回 `plan_preview_ready` 且 `data.validation.valid=true`。如果 preview 返回需要修改或校验未通过，不展示“确认保存”，先重新生成或调整草稿。
