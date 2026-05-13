# 今日安排与日结流程

适用于用户查看“今日计划、今日安排、今日日结、完成情况、顺延任务”。

## 今日安排

调用 `milk_today_overview_get` 读取当天 calendar，返回任务总数、已完成数、未完成数和任务列表。

## 今日日结

调用 `milk_today_summary_get` 汇总当天 calendar 完成情况。

面向用户展示时只保留以下内容，不展开任务列表、吸奶记录、喂养记录、数据库字段或工具返回的完整 JSON：

```markdown
### 今日完成情况
- **总任务**：{total_count}项
- **已完成**：{completed_count}项
- **待完成**：{pending_count}项
- **完成率**：{completion_rate}%
- **吸奶计划任务**：{pump_task_count}项

{encouragement}
```

字段来源：

- `total_count`：`calendar_summary.total_count`
- `completed_count`：`calendar_summary.completed_count`
- `pending_count`：`calendar_summary.pending_count`
- `completion_rate`：`calendar_summary.completion_rate`
- `pump_task_count`：`calendar_summary.pump_task_count`
- `encouragement`：工具返回的 `encouragement`

## 今日任务操作

- 标记完成：调用 `milk_calendar_item_update`
- 删除任务：调用 `milk_calendar_item_delete`
- 新增事项并调整冲突：先 `milk_calendar_adjustment_preview`，确认后 `milk_calendar_adjustment_apply`
- 顺延后续任务：调用 `milk_today_tasks_shift`
- 确认全部完成：调用 `milk_today_tasks_confirm`

## 原则

- calendar 可独立使用，不依赖 milk_plan。
- 只读类工具可直接调用。
- 修改、删除、顺延、确认全部完成前必须取得用户明确确认。
