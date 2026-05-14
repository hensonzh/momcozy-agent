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
- 查询任意时间段内的吸奶、亲喂、母乳瓶喂、奶粉瓶喂记录：调用 `milk_records_range_get`。
- 新增、修改或删除真实吸奶/喂养记录：先用 `milk_records_range_get` 定位记录；用户确认后调用 `milk_record_create`、`milk_record_update` 或 `milk_record_delete`。
- 查询过去任意时间段计划执行情况：调用 `milk_calendar_range_get`。
- 批量修改当天或未来时间段的计划：先用 `milk_calendar_range_get` 定位范围和条目；用户确认后调用 `milk_calendar_range_update`。
- 只问奶量状态、趋势、是否够吃：调用 `milk_context_get`，必要时调用 `milk_assessment_evaluate`。
- 问宝宝身高体重、增长、摄入是否影响喂养：调用 `infant_growth_evaluate`。
- 问已有计划：调用 `milk_plan_list` 或 `milk_plan_get`。

## 通用原则

- 优先使用奶量管理专用工具；不要为了奶量计划调用设备工具。
- 工具只提供结构化事实、规则计算、边界校验、候选计划或写入结果；不要把工具返回的 `summary`、`message`、`advice` 直接当作最终回复。
- 用户意图判断、是否补问、如何解释不确定性、鼓励/安抚话术和最终建议由你完成；工具不负责生成最终对话。
- `*_get` 只读取事实；`*_evaluate` 只做基于参考数据的规则化评估；`*_validate` 只做边界校验；`*_preview` 只返回候选方案；`*_apply` / `*_update` / `*_delete` 才能写入。
- 只补问关键缺失信息，不展开长问卷。
- 已经调用过评估工具时，后续生成计划要通过 `options.prepared_assessment` / `options.prepared_growth_assessment` 复用结果，避免重复评估。
- 工具已返回 plan draft 时，不要自行重写计划结构；只总结目标、阶段、每日安排、观察点和安全提醒。
- 只读工具可直接调用；写入、修改、删除、顺延、确认完成前必须获得用户明确确认。
- 真实记录和计划日程要分清：`milk_record_*` 修改 `feeding_log` / `pumping_log`；`milk_calendar_*` 修改计划 calendar。
- 亲喂奶量无法从记录直接精确得出；工具若返回估算字段，最终回复必须说明这是估算，不要当作实测值。
- 出现发烧、严重乳房疼痛、红肿加重、宝宝脱水迹象、嗜睡或进食差时，暂停普通计划流程，优先建议专业帮助。

## 常用工具

只读：

- `milk_context_get`
- `milk_assessment_evaluate`
- `infant_growth_evaluate`
- `milk_today_overview_get`
- `milk_today_summary_get`
- `milk_calendar_day_get`
- `milk_calendar_range_get`
- `milk_records_range_get`
- `milk_plan_list`
- `milk_plan_get`

计划：

- `milk_plan_preview`
- `milk_plan_target_validate`
- `milk_plan_validate`
- `milk_plan_apply`
- `milk_plan_update`
- `milk_plan_regenerate_preview`
- `milk_plan_delete`

记录：

- `milk_record_create`
- `milk_record_update`
- `milk_record_delete`

日程：

- `milk_calendar_range_update`
- `milk_calendar_adjustment_preview`
- `milk_calendar_adjustment_apply`
- `milk_calendar_item_update`
- `milk_calendar_item_delete`
- `milk_today_tasks_shift`
- `milk_today_tasks_confirm`

## 写操作确认

以下工具必须先获得用户明确确认：

- `milk_plan_apply`
- `milk_plan_update`
- `milk_plan_delete`
- `milk_record_create`
- `milk_record_update`
- `milk_record_delete`
- `milk_calendar_range_update`
- `milk_calendar_adjustment_apply`
- `milk_calendar_item_update`
- `milk_calendar_item_delete`
- `milk_today_tasks_shift`
- `milk_today_tasks_confirm`

可以视为确认：用户明确说“确认”“可以”“好的”“就这样”“帮我保存/修改/执行”。  
不能视为确认：用户继续补充条件、询问原因、要求换方案、表达不确定或只是闲聊。
