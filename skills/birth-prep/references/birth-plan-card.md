# 分娩沟通卡参考

当用户想要分娩计划、生产偏好、分娩偏好、产房沟通卡或可分享计划卡片时，使用本参考文件。

## 服务定位

分娩沟通卡的核心不是完整偏好记录，也不是医疗指令清单，而是一张适合在产检、入院或产房交接时给医生/护士看的“产房沟通优先级卡片”。

它应该帮助用户把最重要的沟通诉求表达清楚：

- 我最希望医护团队知道什么。
- 我希望如何被解释、被征求同意、被支持。
- 如果计划变化，我希望团队如何和我沟通。
- 哪些问题需要提前向医院确认。

弱化详细背景档案、低优先级背景信息和大段偏好记录。卡片要短、可扫读、适合手机保存或分享。

## 表单优先的信息采集策略

当用户请求分娩沟通卡且关键信息尚未确认时，优先创建前端可渲染表单，而不是在聊天里连续追问。

硬性规则：如果当前用户消息中没有 `confirmed_form_data`，不要生成最终分娩沟通卡。必须先创建表单。

创建 `ui_form_create` 后，最终回复里输出一句简短引导：

> 我会把这些整理成一张适合给医护团队看的沟通卡。

不要只展示表单，也不要把这句引导只放在工具调用前的中间态。

使用：

- `form_id`: `birth_plan_card_intake`
- `title`: `信息采集`
- `description`: `确认几个关键信息后，我会把这些整理成一张适合给医护团队看的沟通卡。`
- `submit_label`: `生成我的沟通卡`

表单字段必须使用以下稳定 schema。`ui_form_create.fields` 里的每个字段都需要表示为 JSON object string 或 JSON object。

必填字段：

```json
[
  {
    "id": "due_date_or_week",
    "label": "预产期或当前孕周",
    "type": "text",
    "required": true,
    "placeholder": "例如：2026-06-12 或 37 周",
    "help_text": "用于判断沟通卡的时间背景。"
  },
  {
    "id": "birth_path",
    "label": "计划分娩方式",
    "type": "select",
    "required": true,
    "options": ["顺产", "刨腹产", "未确定"],
    "help_text": "如果还没确定，可以选择“未确定”。"
  },
  {
    "id": "top_priorities",
    "label": "最希望医护团队知道的 1-2 件事",
    "type": "textarea",
    "required": true,
    "placeholder": "例如：希望每一步先解释；希望伴侣参与重要决定。",
    "help_text": "这些会成为卡片最醒目的沟通重点。"
  },
  {
    "id": "communication_preferences",
    "label": "沟通偏好",
    "type": "multi_select",
    "required": true,
    "options": ["操作/干预前先解释原因", "做决定前先征求同意", "重要沟通请同步伴侣/支持人", "请用简单清楚的语言说明", "需要翻译或语言支持", "计划变化时请先说明原因和选择"],
    "help_text": "这些偏好会被写成沟通请求，而不是医疗命令。"
  }
]
```

可选字段：

```json
[
  {
    "id": "birth_setting",
    "label": "生产地点或医院",
    "type": "text",
    "required": false,
    "placeholder": "例如：某某医院、助产中心，或暂未确定"
  },
  {
    "id": "support_people",
    "label": "主要支持人",
    "type": "text",
    "required": false,
    "placeholder": "例如：伴侣、妈妈、doula；以及希望谁参与决策"
  },
  {
    "id": "pain_relief_preferences",
    "label": "疼痛管理偏好",
    "type": "select",
    "required": false,
    "options": ["未确定", "希望先解释选项", "若安全则尽量无药物", "希望了解无痛/硬膜外", "计划麻醉沟通", "其他"]
  },
  {
    "id": "baby_after_birth_preferences",
    "label": "宝宝出生后和喂养偏好",
    "type": "multi_select",
    "required": false,
    "options": ["出生后尽早肌肤接触", "尽早尝试母乳", "宝宝护理/检查前先说明", "如需和宝宝分开，请说明原因和预计时间", "使用配方奶或奶瓶前请先沟通", "未确定"]
  },
  {
    "id": "if_plans_change",
    "label": "如果计划变化，什么最重要",
    "type": "textarea",
    "required": false,
    "placeholder": "例如：请尽量解释原因；请让伴侣参与决定；请用简单语言说明选择。"
  },
  {
    "id": "medical_notes",
    "label": "需要医护团队知道的医疗或安全信息",
    "type": "textarea",
    "required": false,
    "placeholder": "只填写你明确知道的信息，例如：过敏、医生已说明的限制、医院要求。不确定可留空。"
  }
]
```

生成 `ui_form_create` 时，可以把必填字段和可选字段放在同一个 `fields` 数组中，但必须保持这些稳定 `id`、`type` 和 `required` 值。

如果用户不知道某些答案，可以继续生成草稿，不要为了低优先级字段反复追问。

## 表单提交后

当用户提交或确认表单数据后，直接生成 `card_json` 并调用 `ui_card_create`。除非必填答案相互矛盾或存在不安全表达，否则不要重复询问同样的问题。

卡片生成后，普通 final response 必须简短提醒：

> 你可以在产检或入院前把这张卡给医生/护士看，用它快速沟通你的重点偏好和需要讨论的问题。

## 卡片 JSON 契约

最终产物必须通过 `ui_card_create` 创建结构化卡片产物。前端会把 `ui_card_create.card.card_json` 当作唯一数据源，并据此渲染移动端卡片。

不要把自由格式 markdown 当作卡片数据源。可以附一段简短说明，但卡片本身必须通过 `ui_card_create` 传递结构化 JSON。

使用移动端 v1 紧凑 schema：

```json
{
  "card_type": "birth_plan_card",
  "schema_version": "1.0",
  "title": "分娩沟通卡",
  "subtitle": "产房沟通优先级卡片",
  "overview": {
    "due_date_or_week": "待确认",
    "birth_path": "待确认",
    "birth_setting": "",
    "support_people": "待确认"
  },
  "personalized_notes": [],
  "top_priorities": [],
  "communication": [],
  "pain_relief": [],
  "baby_after_birth": [],
  "if_plans_change": [],
  "questions_for_hospital": [],
  "medical_notes": [],
  "disclaimer": "这张卡只用于沟通，请优先遵循医生、助产士和医院的具体指导，尤其是出于安全原因需要调整计划时。"
}
```

字段规则：

- `top_priorities` 是卡片最重要的信息，必须来自用户明确提供的 `top_priorities` 或同义表达，最多 3 条。
- `overview` 只放孕周/预产期、计划分娩方式、生产地点/医院、支持人这类能帮助沟通的短信息，不要扩展成详细背景档案。
- `personalized_notes` 最多 3 条，用短句说明这张卡是基于哪些已确认信息整理的，例如孕周、分娩方式、医院、支持人；不要新增用户没确认的隐私或医学判断。
- `communication`、`pain_relief`、`baby_after_birth`、`if_plans_change` 都使用短句数组，每组最多 3 条。
- `questions_for_hospital` 最多 3 条，只放需要和医院/医护团队沟通的问题，不要编造医院政策；前端会把它作为普通沟通分组展示，不要把它写成独立“先确认”卡片。
- `medical_notes` 只允许放用户明确提供的过敏、医生说明或医院限制；不要推断诊断，不要新增医学建议。
- 不知道的内容不要强行写入 `"待确认"` 密集分区；空分区可以省略或留空数组。
- 不要写入用户没有提供或确认的隐私背景档案原始数据。

## 医疗安全与表达降级

这张卡不提供医学建议，不替代医生、助产士、麻醉师或医院流程。

医疗风险相关信息只允许：

- 用户明确提供的过敏。
- 用户明确提供的医生说明。
- 用户明确提供的医院限制或流程要求。

不允许：

- 根据症状推断诊断。
- 新增医学建议。
- 把偏好写成必须执行的医疗指令。
- 承诺某项干预一定能避免或一定会发生。

强诉求统一降级为沟通请求：

- 使用“在……前，请先和我沟通。”
- 使用“我希望先了解……”
- 使用“如果安全允许，我更希望……”

避免“拒绝”“绝对不要”“不允许”“必须”“一定要”这类强硬或绝对表达。用户明确写出强诉求时，也要包装成“需要和医生讨论的议题”。

## 刨腹产适配规则

如果 `confirmed_form_data.birth_path` 是 `刨腹产`、`剖腹产` 或 `计划剖宫产`，仍然使用同一个 `birth_plan_card` schema，不新增字段或分区。

生成时：

- 减少关于产程体位、自由活动、自然镇痛等顺产导向内容。
- 把重点放入已有字段：
  - `communication`：术前沟通、谁参与决策、如何解释变化。
  - `pain_relief`：麻醉相关沟通和希望提前解释的选项。
  - `baby_after_birth`：出生后肌肤接触时间、喂养偏好、宝宝护理沟通。
  - `medical_notes`：仅放用户明确提供的过敏、医生说明或医院限制。
  - `questions_for_hospital`：陪同、拍照、术后接触宝宝、喂养和住院流程等需要和医院/医护团队沟通的问题。
- 不提供手术指导，不替代医生说明。

## 输出规则

- 卡片要简洁、可分享、适合手机保存。
- 需要较长解释时，放在 `ui_card_create` 外部的普通回复中。
- 不确定内容放入 `questions_for_hospital`，作为普通沟通问题呈现，不要编造医院政策。
- 即使用户想要可打印或可复制版本，也仍然通过 `ui_card_create` 提供 `card_json`；前端可以把它渲染/导出成 HTML、PNG 或 PDF。
- 如果已经有表单数据，视为用户已确认该草稿所需信息。
