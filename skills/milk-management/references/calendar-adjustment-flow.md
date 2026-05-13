# 日程调整流程

适用于用户查询、新增、修改或删除奶量管理 calendar 内容，包括时间、条目内容、类型和完成状态。

## 原则

- calendar 可以独立使用，不依赖 milk plan。
- 只读查询可以直接调用工具；写操作必须先确认。
- 新增事项首轮只能 preview，不能直接 apply。
- 用户新增的事情必须写入 calendar；不能只调整吸奶/亲喂任务。
- preview / apply 的 payload 必须包含用户插入事件本身，以及由此产生的排奶调整。
- 涉及完成状态 `finish` 的更新暂时强制走主界面日历；直接温柔回复“好的，这个需要您回到主界面的日历中操作完成，并记录具体时间和奶量哦。这样可以帮助我们更准确地评估您的泌乳状态。”，不要调用工具。
- 只解释用户需要知道的变更，不暴露数据库字段或内部规则。

## 入口判断

1. 用户查询某天安排：走“查询日程”。
2. 用户新增一个会占用时间的事项：走“新增事项并调整”。
3. 用户修改已有条目的时间、内容、类型或完成状态：走“修改已有条目”。
4. 用户删除已有条目：走“删除条目”。

## 查询日程

1. 明确日期；如果用户没说日期，默认今天。
2. 调用 `milk_calendar_day_get`：
   - `user_id`
   - `target_date`
   - 如用户限定计划或类型，再传 `plan_id` / `item_type`
3. 用简洁语言展示当天条目、时间、类型和完成状态。
4. 不调用写工具。

## 新增事项并调整

适用于“下午要去吃饭”“9 点接孩子”“今天外出两小时”“临时加一次吸奶”等。

1. 如果事项时间不明确，先补问关键时间，不调用工具：
   - 事项日期。
   - 开始时间。
   - 结束时间或预计持续多久。
2. 识别插入事项类型：
   - 明确是吸奶/排奶/泵奶：`item_type="吸奶"`。
   - 明确是亲喂：`item_type="亲喂"`。
   - 吃饭、外出、开会、接孩子、上课、睡觉、通勤等：`item_type="自定义"`。
3. 时间确认后，调用 `milk_calendar_adjustment_preview`：
   - `user_id`
   - `target_date`
   - `event_start_time`
   - `event_end_time` 或 `duration_minutes`
   - `content`
   - `item_type`
   - 如只调整某个计划，再传 `plan_id`
4. 向用户展示 preview 结果：
   - 将加入 calendar 的事项、日期、时间和类型。
   - 是否冲突。
   - 哪个吸奶/亲喂任务会调整。
   - 调整前后时间。
5. 询问用户是否确认。
6. 用户明确确认后，调用 `milk_calendar_adjustment_apply`：
   - `user_id`
   - `target_date`
   - `proposal`：必须传入 preview 返回的完整 `proposal` 或 `proposal_json`，不要自行丢弃 `insert_event` / `updates`
   - `idempotency_key`
7. 返回更新后的日程摘要，说明新增事项和被调整的吸奶/亲喂任务。
8. 如果 preview 显示没有冲突，仍然需要用户确认后再调用 `milk_calendar_adjustment_apply`，因为新增事项本身也需要写入 calendar。

## 修改已有条目

适用于用户修改某个 calendar 条目的时间、内容、类型或完成状态。

1. 如果用户没有明确目标条目，先调用 `milk_calendar_day_get`：
   - `user_id`
   - `target_date`
   - 必要时传 `item_type`
2. 让用户确认要修改哪一条；不要凭模糊描述直接写。
3. 根据用户想改的字段构造 `patch`：
   - 改时间：`start_time`，必要时 `end_time`
   - 改内容：`content`
   - 改类型：`type` 或 `item_type`，值只能是 `吸奶`、`亲喂`、`自定义`
   - 改完成状态：`finish`
4. 用户确认后，调用 `milk_calendar_item_update`：
   - `user_id`
   - `item_id`
   - `patch`
   - `idempotency_key`
5. 如需展示最新日程，再调用 `milk_calendar_day_get`。

## 完成状态同步

暂时关闭 LLM 侧完成状态写入。

1. 用户要把条目标记为完成、取消完成、确认全部完成，或修改任何 `finish` 状态时，不调用任何工具。
2. 不先调用 `milk_calendar_day_get`、`milk_today_overview_get` 或 `milk_today_summary_get` 来核对当前日程。
3. 直接温柔回复：“好的，这个需要您回到主界面的日历中操作完成，并记录具体时间和奶量哦。这样可以帮助我们更准确地评估您的泌乳状态。”
4. 不说“系统不允许”“工具失败”“我无法直接修改”等内部原因。
5. 不调用 `milk_calendar_item_update`。
6. 不调用 `milk_today_tasks_confirm`。
7. 服务层保留未来同步逻辑；当前对话入口不启用。

## 删除条目

1. 如果用户没有明确目标条目，先调用 `milk_calendar_day_get`：
   - `user_id`
   - `target_date`
   - 必要时传 `item_type`
2. 让用户确认要删除哪一条。
3. 用户明确确认后，调用 `milk_calendar_item_delete`：
   - `user_id`
   - `item_id`
   - `idempotency_key`
4. 如需展示最新日程，再调用 `milk_calendar_day_get`。

## 确认规则

可以视为确认：

- “确认”
- “可以”
- “好的”
- “就这样”
- “帮我改吧”

不能视为确认：

- 用户继续补充新时间。
- 用户问为什么。
- 用户要求换一个方案。
- 用户只是在闲聊或表达不确定。

## 重要限制

- 用户只说“下午要去吃饭”“晚点外出”时，不能直接 preview；必须先确认具体时间或持续时长。
- 用户确认前，不能调用 `milk_calendar_adjustment_apply`、`milk_calendar_item_update` 或 `milk_calendar_item_delete`。
- 涉及 `finish` 的请求，即使用户确认，也暂时不能调用任何工具，尤其不能调用 `milk_calendar_item_update` 或 `milk_today_tasks_confirm`。
- 如果用户新增的是吃饭/外出等生活事项，必须作为 `自定义` 事项写入 calendar。
- 如果用户新增的是吸奶或亲喂，必须按对应类型写入 calendar。
