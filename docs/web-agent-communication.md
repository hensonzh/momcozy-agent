# Web 端与智能体通信方案

本文档梳理当前测试 Web 前端与 `momcozy-agent` 智能体服务之间的通信协议、请求字段、响应事件、前端消费方式，以及几个结构化 UI 的回传闭环。

相关代码入口：

- 主前端：`web/index.html`、`web/app.js`、`web/styles.css`
- IBCLC 在线咨询页：`web/ibclc-chat.html`
- HTTP 服务：`src/momcozy_agent/server.py`
- Agent loop：`src/momcozy_agent/agents.py`
- 类型定义：`src/momcozy_agent/types.py`

## 1. 总体链路

当前 Web 端和智能体之间有三类通信：

1. 主聊天流式接口：`POST /api/ag-ui`
   - 前端发送用户消息、图片、会话 id。
   - 后端转换成 `RuntimeInputs`，调用 Responses API agent loop。
   - 后端用 SSE 返回文本、工具调用状态、结构化工具结果和 run 状态。

2. 售后工单模拟提交：`POST /api/support-ticket-submit`
   - 前端提交售后工单表单。
   - 后端模拟生成工单编号。
   - 前端再把“工单已提交”作为用户消息发回 `/api/ag-ui`，让智能体做情绪承接。

3. 前端页面事件回传：`POST /api/client-event`
   - 当前用于 IBCLC 在线咨询结束事件。
   - IBCLC H5 页把 `ibclc_consult_completed` 写入后端 session。
   - 后续主聊天轮次会把该事件注入 `client_event_context`，智能体能感知用户已经完成过一次 IBCLC 在线咨询。

## 2. 主聊天接口：`POST /api/ag-ui`

### 2.1 请求方式

```http
POST /api/ag-ui
Content-Type: application/json
Accept: text/event-stream
```

响应类型：

```http
Content-Type: text/event-stream; charset=utf-8
```

前端发送位置：`web/app.js` 的 `streamChat()`。

### 2.2 前端请求体

请求体由 `buildAgUiPayload(text, images)` 生成。

```json
{
  "threadId": "thread_xxx",
  "userId": "user_xxx",
  "runId": "run_1710000000000_1",
  "state": {
    "user_id": "user_xxx",
    "locale": "zh-CN",
    "timezone": "Asia/Shanghai",
    "message_sent_at": "2026-05-13T15:30:12.123+08:00",
    "user_profile": {
      "user_id": "user_xxx",
      "language": "zh-CN"
    }
  },
  "messages": [
    {
      "id": "msg_1710000000000",
      "role": "user",
      "content": "用户输入文本"
    }
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {
    "user_id": "user_xxx",
    "locale": "zh-CN",
    "timezone": "Asia/Shanghai",
    "message_sent_at": "2026-05-13T15:30:12.123+08:00"
  }
}
```

有图片时，`messages[0].content` 会变成数组：

```json
[
  {
    "type": "text",
    "text": "请看这张图"
  },
  {
    "type": "image",
    "image_url": "data:image/png;base64,...",
    "mime_type": "image/png",
    "name": "photo.png",
    "size": 123456,
    "detail": "auto"
  }
]
```

字段说明：

| 字段 | 来源 | 当前用途 |
| --- | --- | --- |
| `threadId` | `localStorage.momcozy_conversation_id`；没有则前端生成 | 后端 session id，决定是否复用 `previous_response_id`、已加载 skill、上下文状态 |
| `userId` | `localStorage.momcozy_user_id`；没有则前端生成 | 客户端用户身份，后端同步到 `RuntimeInputs.user_id` 和 `user_profile.user_id` |
| `runId` | 前端按时间戳和 `runCount` 生成 | 本轮 run id，用于 SSE 事件关联 |
| `state.locale` | `navigator.language || "en-US"` | 后端转为 `RuntimeInputs.locale` |
| `state.timezone` | `Intl.DateTimeFormat().resolvedOptions().timeZone` | 后端转为 `RuntimeInputs.timezone`，首轮注入 request context |
| `state.message_sent_at` | 前端用本地时间生成，包含时区偏移 | 后端转为 `RuntimeInputs.message_sent_at`，每轮注入 request context |
| `state.user_profile.user_id` | 前端生成的 `userId` | 供 `profile_get` 等 runtime 工具读取 |
| `messages[].id` | 前端生成 | 当前后端不依赖该字段 |
| `messages[].role` | 固定为 `user` | 后端只从最新 user 消息提取内容 |
| `messages[].content` | 文本或图文数组 | 后端提取 `user_message` 和 `images` |
| `tools` | 当前传空数组 | 当前后端不读取 |
| `context` | 当前传空数组 | 当前后端不读取 |
| `forwardedProps` | 前端同步传关键客户端字段 | 后端兼容从这里读取 `user_id`、`locale`、`timezone`、`message_sent_at` 等扩展上下文 |

### 2.2.1 客户端负责维护的信息

以下字段属于客户端或宿主 App，不应由智能体服务端自行生成业务含义：

| 字段 | 当前 Web Demo 实现 | 原因 |
| --- | --- | --- |
| `user_id` / `userId` | 首次打开时生成 `user_${crypto.randomUUID()}`，保存到 `localStorage.momcozy_user_id` | 用户身份应来自 App 登录态或客户端会话，不应由 agent 服务猜测 |
| `threadId` | 当前聊天会话 id，保存到 `localStorage.momcozy_conversation_id` | 决定后端 session 和 Responses API 多轮上下文 |
| `locale` | `navigator.language` | 属于用户设备/客户端环境 |
| `timezone` | `Intl.DateTimeFormat().resolvedOptions().timeZone` | 属于用户设备/客户端环境 |
| `message_sent_at` | 前端发送消息时生成，格式包含本地 UTC offset | 消息发生时间应在客户端发送动作发生时冻结 |
| `user_profile` / `baby_profile` / `service_state` | 当前 demo 只传最小 `user_profile.user_id`；真实 App 应从客户端状态或业务 API 注入 | 这些是应用侧用户状态，不应由模型生成 |

### 2.3 后端兼容读取字段

`server.py` 的 `_runtime_inputs_from_ag_ui()` 会读取这些字段：

| 字段 | 说明 |
| --- | --- |
| `messages` | 优先从最新 user message 中提取文本和图片 |
| `message` | 兜底文本字段 |
| `state` | 可包含 `user_id`、`locale`、`timezone`、`message_sent_at`、profile 等 |
| `forwardedProps` / `forwarded_props` | 可包含动态上下文和 profile |
| `user_id` / `userId` | 顶层、`state` 或 `forwardedProps` 都支持 |
| `locale` | 顶层兜底 |
| `timezone` | 顶层兜底 |
| `message_sent_at` | 顶层兜底 |
| `previous_response_id` | 可放在 `state` 或 `forwardedProps` 中 |
| `user_profile` | 可放在 `state` 或 `forwardedProps` 中 |
| `baby_profile` | 可放在 `state` 或 `forwardedProps` 中 |
| `service_state` | 可放在 `state` 或 `forwardedProps` 中 |
| `retrieved_records` | 可放在 `state` 或 `forwardedProps` 中 |
| `retrieved_knowledge` | 可放在 `state` 或 `forwardedProps` 中 |

`/api/ag-ui` 还读取这些 AG-UI 运行字段：

| 字段 | 说明 |
| --- | --- |
| `threadId` / `thread_id` | 后端 session id |
| `runId` / `run_id` | 本轮 run id |
| `parentRunId` / `parent_run_id` | 可选父 run id |
| `conversation_id` | `threadId` 缺失时的 fallback |

### 2.4 转换后的 `RuntimeInputs`

后端会把请求转为智能体内部输入：

```python
{
    "user_message": str,
    "user_id": str,
    "locale": str,
    "timezone": str,
    "message_sent_at": str,
    "previous_response_id": str,
    "user_profile": dict,
    "baby_profile": dict,
    "service_state": dict,
    "retrieved_records": list,
    "retrieved_knowledge": list,
    "images": [
        {
            "image_url": str,
            "detail": "auto" | "low" | "high",
            "mime_type": str,
            "name": str,
            "size": int
        }
    ]
}
```

注意：

- 前端现在显式传 `user_id`、`locale`、`timezone` 和 `message_sent_at`。
- `timezone` 仍保留后端默认值 `America/Los_Angeles` 作为兼容兜底，但正常 Web Demo 不依赖这个兜底。
- `message_sent_at` 如果前端不传，后端仍会按 timezone 实时生成；但正式客户端应在发送时生成并传入。
- 如果前端只传 `user_id`，没有传 `user_profile`，后端会自动补成 `user_profile: {"user_id": ...}`。
- `previous_response_id` 前端不需要传；后端 session 会自动保存上一轮 Responses API 的 response id 并在下一轮补上。

## 3. 后端 session 状态

每个 `threadId` 对应一个 `ChatSession`：

```python
{
    "conversation_id": str,
    "previous_response_id": str | None,
    "loaded_skill_ids": list[str],
    "context_state": {
        "environment_sent": bool,
        "loaded_references": list[str],
        "client_events": list[str]
    }
}
```

状态用途：

- `previous_response_id`：用于 Responses API 多轮上下文延续。
- `loaded_skill_ids`：记录当前 session 已加载的 skill，避免重复加载。
- `environment_sent`：控制 `locale`、`timezone` 只在首轮注入。
- `loaded_references`：记录已加载过的参考资料，例如设备说明书。
- `client_events`：记录前端页面事件，例如 IBCLC 在线咨询已结束。

后续每轮都会注入：

- `message_sent_at`
- 已加载参考资料：`loaded_reference_context`
- 前端事件：`client_event_context`

## 4. Responses API 请求结构

Agent loop 最终调用 Responses API 的请求结构：

```python
{
    "model": "gpt-5.5",
    "instructions": STATIC_AGENT_INSTRUCTIONS,
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "request_context:\n..."},
                {"type": "input_text", "text": "user_message:\n..."},
                {"type": "input_image", "image_url": "...", "detail": "auto"}
            ]
        }
    ],
    "tools": [...],
    "tool_choice": "auto",
    "reasoning": {"effort": "medium"},
    "text": {
        "format": {"type": "text"},
        "verbosity": "medium"
    },
    "store": true,
    "prompt_cache_key": "momcozy-agent-v2",
    "previous_response_id": "resp_xxx"
}
```

其中 `previous_response_id` 只有在 session 已存在上一轮 response id 时才会带上。

## 5. `/api/ag-ui` SSE 响应事件

SSE 格式：

```text
data: {"type":"RUN_STARTED", "...":"..."}

data: {"type":"TEXT_MESSAGE_CONTENT", "delta":"..."}
```

前端解析方式：

- `response.body.getReader()` 逐块读取。
- 用 `TextDecoder` 解码。
- 按 `\n\n` 分割 SSE event。
- 提取每行 `data:` 后面的 JSON。
- 进入 `streamChat()` 的事件分支消费。

### 5.1 Run 事件

#### `RUN_STARTED`

```json
{
  "type": "RUN_STARTED",
  "timestamp": 1710000000000,
  "thread_id": "thread_xxx",
  "run_id": "run_xxx",
  "parent_run_id": "run_parent"
}
```

前端行为：

- 调用 `updateMeta(event)`。
- 更新 conversation label。

#### `RUN_FINISHED`

```json
{
  "type": "RUN_FINISHED",
  "timestamp": 1710000000000,
  "thread_id": "thread_xxx",
  "run_id": "run_xxx",
  "result": {
    "response_id": "resp_xxx"
  }
}
```

前端行为：

- 结束 thinking / preparing 状态。
- 如果没有文本、表单、卡片，则展示 `(No text response)`。
- 调用 `finishWorkPanel()` 收起 work panel。

注意：后端会暂存 `RUN_FINISHED`，等文本流结束和 assistant followup 处理完后再发送。

### 5.2 Assistant 文本事件

#### `TEXT_MESSAGE_START`

```json
{
  "type": "TEXT_MESSAGE_START",
  "message_id": "run_xxx:assistant",
  "role": "assistant"
}
```

当前前端没有单独处理这个事件。

#### `TEXT_MESSAGE_CONTENT`

```json
{
  "type": "TEXT_MESSAGE_CONTENT",
  "message_id": "run_xxx:assistant",
  "delta": "流式文本片段"
}
```

前端行为：

- 创建或复用 assistant bubble。
- 将 `delta` 追加到 Markdown 内容。
- 使用 `marked + DOMPurify` 渲染。
- 如果后续发生工具调用，当前这段 provisional assistant text 会被移动进 work panel，作为中间过程 narration。

#### `TEXT_MESSAGE_END`

```json
{
  "type": "TEXT_MESSAGE_END",
  "message_id": "run_xxx:assistant"
}
```

前端行为：

- 清理文本 idle thinking timer。
- 视为本段 assistant text 输出结束。

### 5.3 Thinking 事件

Thinking 通过 `CUSTOM` 事件返回：

```json
{
  "type": "CUSTOM",
  "timestamp": 1710000000000,
  "name": "momcozy.agent.thinking",
  "value": {
    "type": "agent.thinking",
    "status": "started",
    "metadata": {}
  }
}
```

`status` 可能值：

- `started`
- `running`
- `completed`
- `failed`

前端行为：

- `started` / `running`：展示 `Thinking`。
- 如果 `metadata.after_output_text === true`：展示 `Preparing next step`。
- 目前前端不会在 completed 时立刻移除 Thinking，而是等下一条可见事件替换，以减少空白延迟感。
- 如果模型没有立刻发送 reasoning 事件，前端会在 `RUN_STARTED` 或 `agent.status` 进入 `requesting_model` 时先展示 `Thinking` 作为兜底。

### 5.4 Agent 状态事件

Agent 状态会以两种事件形式发送：

#### `ACTIVITY_SNAPSHOT`

```json
{
  "type": "ACTIVITY_SNAPSHOT",
  "message_id": "run_xxx:status",
  "activity_type": "MOMCOZY_AGENT_STATUS",
  "content": {
    "type": "agent.status",
    "phase": "requesting_model",
    "message": "Requesting model response.",
    "metadata": {
      "round": 0
    }
  },
  "replace": true
}
```

#### `CUSTOM` / `momcozy.agent.status`

```json
{
  "type": "CUSTOM",
  "name": "momcozy.agent.status",
  "value": {
    "type": "agent.status",
    "phase": "tool_completed",
    "message": "Tool completed.",
    "metadata": {}
  }
}
```

前端主要用它们更新 meta。`requesting_model` 也会触发首轮 `Thinking` 兜底，真正可见的 work panel 主要来自 tool call 事件。

### 5.5 Tool call 事件

#### `TOOL_CALL_START`

```json
{
  "type": "TOOL_CALL_START",
  "timestamp": 1710000000000,
  "tool_call_id": "call_xxx",
  "tool_call_name": "ui_form_create",
  "parent_message_id": "run_xxx:tool-results",
  "response_id": "resp_xxx",
  "output_index": 1,
  "item_id": "fc_xxx"
}
```

前端行为：

- 记录当前 tool name。
- 将 provisional assistant text 移入 work panel。
- 调用 `addWorkToolStart()`，显示工具开始状态。

#### `TOOL_CALL_ARGS`

```json
{
  "type": "TOOL_CALL_ARGS",
  "tool_call_id": "call_xxx",
  "delta": "{\"argument_keys\":[\"title\",\"fields\"]}"
}
```

前端行为：

- 根据 tool name 展示“参数已准备好”的状态。
- 出于安全和 UI 简洁，后端不会把完整工具参数都透给前端，`safe_tool_arguments()` 会做摘要。

#### `TOOL_CALL_END`

```json
{
  "type": "TOOL_CALL_END",
  "tool_call_id": "call_xxx"
}
```

前端行为：

- 展示工具正在执行或生成中的状态。

#### `TOOL_CALL_RESULT`

```json
{
  "type": "TOOL_CALL_RESULT",
  "message_id": "run_xxx:tool-results",
  "tool_call_id": "call_xxx",
  "content": "{\"ok\":true,\"tool_name\":\"ui_form_create\",\"form\":{...}}",
  "role": "tool"
}
```

前端行为：

- `content` 是 JSON 字符串，需要 `parseJson(event.content)`。
- 更新 work panel 工具结果状态。
- 根据 `tool_name` 分发到结构化 UI 渲染器。

### 5.6 Stream Timing 调试

本地测试时可以设置 `MOMCOZY_DEBUG_STREAM_TIMING=1` 启动服务端。后端会在 stderr 输出本轮 run 的关键 Responses stream 事件和 SSE 发送时间，例如首个 `response.output_text.delta`、`response.output_item.done`、`response.completed`、`TEXT_MESSAGE_CONTENT`、`RUN_FINISHED`。

这些日志不包含文本内容或工具参数，只包含事件名、delta 长度和少量 item 元数据。用法：

- 如果 `responses:response.output_text.delta` 本身很晚，慢点主要在 Responses API 首包/模型侧。
- 如果 `sse:TEXT_MESSAGE_CONTENT` 很早但浏览器很晚才显示，再排查浏览器、代理或本地网络。
- 如果文本 delta 很早、`response.output_item.done` 后到 `response.completed` 很晚，前端较久显示 `Preparing next step` 是 stream 尾部完成事件较晚，不代表文本没有到达。

## 6. Tool result 安全响应体

后端不会直接把工具原始结果完整透给前端，而是通过 `safe_tool_result()` 输出安全子集。

通用字段：

```json
{
  "ok": true,
  "tool_name": "ui_form_create",
  "id": "...",
  "skill_id": "...",
  "status": "...",
  "resource_id": "...",
  "side_effect_performed": false,
  "error": {
    "type": "...",
    "message": "..."
  }
}
```

按工具附加字段：

| 工具 | 附加字段 | 前端消费 |
| --- | --- | --- |
| `ui_form_create` | `form` | `addFormCard(result.form)` |
| `ui_card_create` | `card`、可选 `assistant_followup` | `addCard(result.card)` |
| `ibclc_consult_card_create` | `card` | `addIbclcConsultCard(result.card)` |
| `support_ticket_draft_create` | `ticket`、`submit_label` | `addSupportTicketDraft(result)` |

## 7. 前端渲染和消费逻辑

### 7.1 普通文本

`TEXT_MESSAGE_CONTENT` 会进入 assistant bubble：

- 原始 Markdown 存在 `node._rawMarkdown`
- 用 `marked.parse()` 转 HTML
- 用 `DOMPurify.sanitize()` 清洗
- 图片会绑定点击放大 viewer

### 7.2 中间 assistant text

如果模型在 loop 中先输出了一段 assistant text，随后又发生工具调用：

1. 前端先临时显示 assistant bubble。
2. 收到 `TOOL_CALL_START` / `ARGS` / `END` / `RESULT` 时调用 `moveProvisionalTextToWorkPanel()`。
3. 这段文本会被移入 work panel，作为本轮中间 narration。
4. 最后一轮 assistant text 才保留在最终 assistant bubble。

这个设计用于区分“loop 中间过程”和“最终回答”。

### 7.3 Work panel

work panel 由前端根据工具事件生成，不是后端直接返回 HTML。

核心状态来源：

- `TOOL_CALL_START`
- `TOOL_CALL_ARGS`
- `TOOL_CALL_END`
- `TOOL_CALL_RESULT`
- loop 中间 assistant text
- thinking / preparing 状态

work item 文案由前端根据 `tool_name` 映射：

- `load_skill`：Loading service workflow
- `read_skill_file`：Reading service reference
- `ui_form_create`：Preparing form / Form ready
- `ui_card_create`：Creating card / Card ready
- `ibclc_consult_card_create`：Preparing IBCLC consult / IBCLC consult ready
- `device_manual_search`：Checking device manual / Device manual checked
- `support_ticket_draft_create`：Preparing support ticket / Support ticket ready

### 7.4 表单 UI

`ui_form_create` 返回的是 form schema，不是 HTML。

前端渲染：

- `addFormCard(formSpec)`
- 每个字段走 `createFormField()` 或 `createCheckboxGroup()`
- 支持 text、date、textarea、select、multi_select / checkbox_group
- 必填字段在 label 前显示红色 `*`

用户提交表单后：

1. 前端收集表单值。
2. 构造一条用户消息：
   ```text
   我已确认 xxx 信息，请基于这些信息生成对应卡片。
   form_id: ...
   confirmed_form_data:
   {...}
   ```
3. 调用 `sendUserText()` 再次进入 `/api/ag-ui`。
4. 智能体基于表单数据生成卡片或下一步回复。

### 7.5 卡片 UI

`ui_card_create` 返回 card schema。

前端渲染：

- `birth_plan_card`：`renderBirthPlanCardV1()`
- `hospital_bag_card`：`renderHospitalBagCardV1()`
- 未识别卡片：`renderUnsupportedCard()`

卡片支持下载：

- 使用 `html-to-image` 导出 PNG。
- 移动端如果支持 Web Share API，会优先系统分享。

### 7.6 IBCLC 咨询卡

`ibclc_consult_card_create` 返回 IBCLC card schema。

前端渲染：

- `addIbclcConsultCard(card)`
- 生成一张 IBCLC 咨询卡。
- 前端为每张卡生成独立 `consult_id`。
- “在线咨询”链接会携带：
  - `thread_id`
  - `consult_id`

链接示例：

```text
/ibclc-chat.html?thread_id=thread_xxx&consult_id=ibclc_xxx
```

当 IBCLC 页结束咨询后，主聊天页只会把匹配同一个 `consult_id` 的卡片改为：

- 按钮文案：`咨询结束`
- 按钮置灰
- 移除 `href`、`target`、`rel`

这样同一会话后续再生成新的 IBCLC 卡片时，不会继承上一张卡片的结束状态。

### 7.7 售后工单

`support_ticket_draft_create` 返回工单草稿。

前端渲染：

- `addSupportTicketDraft(result)`
- 展示可确认的售后工单表单

用户点击“确认并提交”：

1. 前端调用 `POST /api/support-ticket-submit`
2. 后端模拟返回工单编号
3. 前端把提交结果整理成一条用户消息，再调用 `/api/ag-ui`
4. 智能体收到后输出简短情绪支持和 24 小时人工客服承诺

## 8. 售后工单接口：`POST /api/support-ticket-submit`

请求体：

```json
{
  "ticket": {
    "issue_type": "使用帮助",
    "issue_summary": "用户描述的问题",
    "product_model": "Air1",
    "urgency": "普通"
  },
  "thread_id": "thread_xxx",
  "user_id": "user_xxx",
  "locale": "zh-CN",
  "timezone": "Asia/Shanghai",
  "message_sent_at": "2026-05-12T11:00:00.000+08:00",
  "idempotency_key": "uuid"
}
```

后端当前只强校验 `ticket` 必须是 object，其余字段用于模拟请求语义和后续真实客服 API 对接。`user_id`、`thread_id`、`locale`、`timezone`、`message_sent_at` 都由客户端提供。

响应体：

```json
{
  "status": "mock_submitted",
  "ticket_id": "mock_ticket_xxxxxxxx",
  "side_effect_performed": false,
  "mock": true,
  "message": "工单已提交，人工客服会在 24 小时内联系你解决问题。",
  "ticket": {
    "issue_type": "...",
    "issue_summary": "...",
    "product_model": "...",
    "urgency": "..."
  }
}
```

## 9. 客户端事件接口：`POST /api/client-event`

当前用于 IBCLC 在线咨询结束事件。

请求体：

```json
{
  "thread_id": "thread_xxx",
  "user_id": "user_xxx",
  "event_type": "ibclc_consult_completed",
  "label": "用户已完成一次 IBCLC 在线咨询",
  "occurred_at": "2026-05-12T11:00:00.000+08:00",
  "locale": "zh-CN",
  "timezone": "Asia/Shanghai",
  "metadata": {
    "user_id": "user_xxx",
    "consultant_name": "Emily Chen",
    "consultant_credentials": "IBCLC",
    "source": "ibclc-chat",
    "consult_id": "ibclc_xxx"
  }
}
```

兼容字段：

- `thread_id` / `threadId`
- `conversation_id`
- `user_id` / `userId`
- `consult_id` / `consultId`

响应体：

```json
{
  "status": "recorded",
  "conversation_id": "thread_xxx",
  "consult_id": "ibclc_xxx",
  "event": "2026-05-12T11:00:00.000Z: 用户已完成一次 IBCLC 在线咨询 [event_type: ibclc_consult_completed] (...)",
  "session_state": {
    "conversation_id": "thread_xxx",
    "previous_response_id": "resp_xxx",
    "loaded_skill_ids": ["device-guidance"],
    "context_state": {
      "environment_sent": true,
      "loaded_references": [],
      "client_events": [
        "2026-05-12T11:00:00.000Z: 用户已完成一次 IBCLC 在线咨询 ..."
      ]
    }
  }
}
```

IBCLC 页还会把结果通过两条前端通道通知主页面：

1. `localStorage.momcozy_ibclc_consult_completed`
2. `window.opener.postMessage(payload, window.location.origin)`

主页面监听：

- `storage`
- `message`
- `focus`
- `pageshow`
- `visibilitychange`

收到事件后：

- 校验 `conversation_id`
- 更新 meta
- 找到匹配 `consult_id` 的 IBCLC 卡片
- 将按钮切换成“咨询结束”

## 10. 本地持久化字段

前端使用以下 `localStorage` key：

| Key | 说明 |
| --- | --- |
| `momcozy_user_id` | 当前客户端用户 id；demo 中首次打开自动生成，Reset 不清空 |
| `momcozy_conversation_id` | 当前主聊天会话 id |
| `momcozy_run_count` | 当前会话 run 计数，用于生成 runId |
| `momcozy_ibclc_consult_completed` | 最近一次 IBCLC 在线咨询完成事件 |

点击 Reset 时会清空：

- `momcozy_conversation_id`
- `momcozy_ibclc_consult_completed`

Reset 不清空 `momcozy_user_id`，因为用户身份应独立于单次聊天会话。真实 App 中该值应来自登录态、匿名用户 id 或设备侧用户映射。

## 11. 错误处理

### `/api/ag-ui`

请求解析失败时：

```json
{
  "error": "AG-UI input requires a user message."
}
```

HTTP status：`400`

agent loop 运行中失败时，后端通过 SSE 返回：

```json
{
  "type": "RUN_ERROR",
  "timestamp": 1710000000000,
  "message": "错误信息",
  "code": "错误类型"
}
```

前端行为：

- 结束 work panel。
- 添加 error bubble。
- 恢复输入区。

### `/api/support-ticket-submit`

失败响应：

```json
{
  "error": "support ticket submit requires a ticket object."
}
```

### `/api/client-event`

失败响应：

```json
{
  "error": "client event requires thread_id."
}
```

IBCLC 页面中，事件提交失败不会阻止用户结束咨询；它会走本地 fallback，只保证页面能返回。

## 12. 当前设计要点

1. 前端只负责渲染结构化 UI，不直接生成业务内容。
2. 表单、卡片、工单、IBCLC 咨询卡都由工具结果驱动。
3. 工具原始结果不会完整暴露给前端，后端会做 `safe_tool_result()` 裁剪。
4. loop 中间文本和工具状态进入 work panel，最终 assistant text 保留为普通 assistant bubble。
5. 会话连续性由后端 session + Responses API `previous_response_id` 维护，前端需要稳定传 `threadId`。
6. 外部 H5 页面事件通过 `/api/client-event` 回写 session，再通过 `client_event_context` 进入后续智能体上下文。
7. IBCLC 咨询完成状态按 `consult_id` 绑定单张卡片，避免同一会话中新卡片误继承旧状态。
8. 用户身份、locale、timezone 和每条消息的发送时间由客户端负责，后端只做兼容兜底和 runtime 转换。
