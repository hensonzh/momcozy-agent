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

## 信息采集评估结论

分娩计划卡不是完整问卷，采集目标是帮用户快速表达“我希望医护团队怎么和我沟通”。字段设计遵循：

- 必填只保留生成卡片不可缺少的轻量信息：时间背景、计划分娩方式、最重要的价值优先级。
- `top_priorities` 表达“我最在意什么”，`communication_preferences` 表达“希望医护怎么和我说”，两者不能放重复选项。
- 多选字段不要放“我还没想好”“未确定”“听医生安排”“无特别偏好”等排他选项；这些意思由用户不勾选该字段、填写补充文本或使用单选字段承接，避免同时勾选后产生歧义。
- 对用户最难临场组织语言的字段，优先使用 `multi_select` 或 `select`，不要一上来让用户写长段文字。
- 可选字段只用于增强个性化，不阻塞生成：生产地点、是否第一胎、支持人、沟通方式、生产过程偏好、需要提前沟通的操作、疼痛缓解/麻醉沟通、宝宝出生后偏好、计划变化和紧急情况沟通、医院确认问题、明确已知的医疗/安全信息。
- 医疗或安全信息只能来自用户明确填写，不根据其他字段推断。
- 如果用户不知道某些答案，可以继续生成草稿，不要为了低优先级字段反复追问。

## 表单字段

表单门控、短确认延续、预填规则和 `confirmed_form_data` 处理由主 `SKILL.md` 统一规定。本参考只定义分娩沟通卡专属字段、卡片 schema 和生成规则。

使用：

- `form_id`: `birth_plan_card_intake`
- `title`: `信息采集`
- `description`: 留空字符串
- `submit_label`: `生成我的沟通卡`

表单字段必须使用以下稳定 schema。`ui_form_create.fields` 里的每个字段都需要表示为 JSON object string 或 JSON object。

必填字段：

```json
[
  {
    "id": "due_date_or_week",
    "label": "基本信息｜现在怀孕多久/预产期",
    "type": "text",
    "required": true,
    "placeholder": "例如：2026-06-12 或 37 周"
  },
  {
    "id": "birth_path",
    "label": "基本信息｜医生目前建议的生产方式",
    "type": "select",
    "required": true,
    "options": ["顺产", "剖宫产", "还没确定"]
  },
  {
    "id": "top_priorities",
    "label": "支持与沟通｜最希望医护知道的事",
    "type": "multi_select",
    "required": true,
    "options": ["宝宝出生后，想尽早抱一抱/贴一贴", "想尽早试着喂母乳", "希望伴侣/支持人尽量陪在身边", "希望医护多鼓励我、告诉我进展", "一些非必要操作，希望先和我沟通"]
  }
]
```

可选字段：

```json
[
  {
    "id": "birth_setting",
    "label": "基本信息｜准备在哪家医院/哪里生",
    "type": "text",
    "required": false,
    "placeholder": "例如：某某医院、助产中心，或暂未确定"
  },
  {
    "id": "first_birth",
    "label": "基本信息｜是不是第一胎",
    "type": "select",
    "required": false,
    "options": ["是", "否", "还没确定"]
  },
  {
    "id": "support_person",
    "label": "支持与沟通｜谁陪你、希望 TA 帮什么",
    "type": "text",
    "required": false,
    "placeholder": "例如：伴侣陪产并参与重要决定；妈妈在产后帮忙照顾"
  },
  {
    "id": "communication_preferences",
    "label": "支持与沟通｜希望医护怎么和你沟通",
    "type": "multi_select",
    "required": false,
    "options": ["做操作前，先告诉我为什么需要", "做重要决定前，先问问我的想法", "重要决定也请同步伴侣/支持人", "请用简单清楚的话说明", "计划有变化时，请先说原因和选择", "需要翻译或语言支持"]
  },
  {
    "id": "priority_notes",
    "label": "支持与沟通｜还有什么想补充告诉医护",
    "type": "textarea",
    "required": false,
    "placeholder": "如果上面的选项没覆盖，可以简单写一句；不确定可留空。"
  },
  {
    "id": "labor_preferences",
    "label": "生产过程｜生宝宝时希望怎么被照顾",
    "type": "multi_select",
    "required": false,
    "options": ["医生允许时，希望可以走动或换姿势", "宝宝心跳监护怎么做，希望先说明一下", "希望可以用分娩球、热敷或按摩让自己舒服一点", "想提前确认生产时能不能喝水或吃点东西", "希望环境安静一点、灯光柔和一点"]
  },
  {
    "id": "intervention_preferences",
    "label": "生产过程｜需要先说清楚的操作",
    "type": "multi_select",
    "required": false,
    "options": ["如果需要侧切，请先说明原因再和我沟通", "如果需要产钳或吸引，请先解释为什么需要", "如果需要人工破水，请先和我说明", "灌肠或剃毛前，希望先告诉我是否必须"]
  },
  {
    "id": "pain_relief_preferences",
    "label": "疼痛和舒适｜生产时怎么帮你舒服一点",
    "type": "multi_select",
    "required": false,
    "options": ["想提前了解有哪些减痛/麻醉选择", "如果安全允许，先试试呼吸、姿势、按摩来缓解", "我倾向使用无痛/硬膜外，想提前沟通安排", "有点担心副作用或恢复，想先了解清楚再决定", "如果剖宫产，希望手术麻醉前充分说明"]
  },
  {
    "id": "pain_relief_notes",
    "label": "疼痛和舒适｜其他关于疼痛缓解/麻醉的想法",
    "type": "textarea",
    "required": false,
    "placeholder": "如果上面的选项没覆盖，可以简单写一句；不确定可留空。"
  },
  {
    "id": "feeding_intention",
    "label": "宝宝出生后｜准备怎么喂宝宝",
    "type": "select",
    "required": false,
    "options": ["母乳喂养", "母乳和配方奶都可能", "配方奶", "还没想好"]
  },
  {
    "id": "baby_after_birth_preferences",
    "label": "宝宝出生后｜宝宝出生后希望怎么安排",
    "type": "multi_select",
    "required": false,
    "options": ["宝宝出生后，想尽早抱一抱/贴一贴", "想尽早试着亲喂/喂母乳", "如果医院允许，希望晚一点剪脐带", "希望宝宝尽量和我在一起", "给宝宝做检查或护理前，希望先告诉我", "打针、疫苗或新生儿检查前，希望先说明", "如果医院允许，希望伴侣/家人剪脐带", "如果医院允许，第一次洗澡晚一点", "如果宝宝需要离开我身边，请说明原因和大概多久", "给宝宝用配方奶或奶瓶前，请先和我沟通"]
  },
  {
    "id": "if_plans_change",
    "label": "临时变化｜如果现场安排变了，希望怎么沟通",
    "type": "textarea",
    "required": false,
    "placeholder": "例如：请尽量解释原因；请让伴侣参与决定；请用简单语言说明选择。"
  },
  {
    "id": "emergency_authorization",
    "label": "临时变化｜如果来不及慢慢沟通，希望怎么处理",
    "type": "select",
    "required": false,
    "options": ["来不及细说时，优先按医生团队判断处理", "希望先联系我的伴侣/支持人", "希望尽量先直接告诉我", "还没确定"]
  },
  {
    "id": "hospital_questions_focus",
    "label": "提前问医院｜想提前问医院的问题",
    "type": "multi_select",
    "required": false,
    "options": ["陪产和探视怎么安排", "能不能拍照或录像", "生产时能不能喝水或吃点东西", "无痛或麻醉什么时候可以沟通", "宝宝出生后的护理流程", "产后有没有母乳喂养支持", "大概住几天、怎么出院", "紧急情况会怎么沟通和决定"]
  },
  {
    "id": "medical_notes",
    "label": "提前问医院｜过敏、医生提醒或其他安全信息",
    "type": "textarea",
    "required": false,
    "placeholder": "只填写你明确知道的信息，例如：过敏、医生已说明的限制、医院要求。不确定可留空。"
  }
]
```

生成 `ui_form_create` 时，可以把必填字段和可选字段放在同一个 `fields` 数组中，但必须保持这些稳定 `id`、`type` 和 `required` 值。字段顺序必须按分类排列：`基本信息`、`支持与沟通`、`生产过程`、`疼痛和舒适`、`宝宝出生后`、`临时变化`、`提前问医院`。同一分类下的字段必须连续出现，不要被其他分类打断。

支持人字段统一使用 `support_person`。如果历史上下文或旧表单里出现 `support_people`，只作为兼容输入读取，不要再创建新的 `support_people` 表单字段。

`medical_notes` 默认不预填。即使历史上下文或 `hospital_bag_intake` 的 `pregnancy_history_or_notes` 里已经有妊娠病史、过敏史或医生提醒，也不要自动写入 `medical_notes.default_value`；只有用户在本服务里明确表达"希望医护团队知道"时才写入。

不要给字段添加 `help_text`。字段说明应尽量体现在 label、placeholder 或选项文案里，避免表单看起来像密集问卷。

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
  "labor_preferences": [],
  "intervention_preferences": [],
  "pain_relief": [],
  "baby_after_birth": [],
  "if_plans_change": [],
  "emergency_authorization": [],
  "questions_for_hospital": [],
  "medical_notes": [],
  "disclaimer": "这张卡只用于沟通，请优先遵循医生、助产士和医院的具体指导，尤其是出于安全原因需要调整计划时。"
}
```

字段规则：

- `top_priorities` 是表单输入和兼容数据源，不作为前端独立展示模块。生成时必须把其中可展示的重点转入 `communication`、`baby_after_birth`、`intervention_preferences` 等对应分组，避免“摘要 + 正文”重复，也避免移除独立模块后丢失用户重点。
- `overview` 只放孕周/预产期、生产方式、生产地点/医院、支持人这类能帮助沟通的短信息，不要扩展成详细背景档案。
- `overview.support_people` 是卡片展示兼容字段，来源优先使用表单字段 `support_person`；旧数据里的 `support_people` 只作为兼容输入。
- `personalized_notes` 最多 3 条，用短句说明这张卡是基于哪些已确认信息整理的，例如孕周、分娩方式、医院、支持人、是否第一胎；不要新增用户没确认的隐私或医学判断。
- `communication`、`labor_preferences`、`intervention_preferences`、`pain_relief`、`baby_after_birth`、`if_plans_change`、`emergency_authorization` 都使用短句数组，每组最多 3 条。
- 若 `top_priorities` 含有暗示沟通方式的选项，应转化为 1-2 条短句写入 `communication`，避免该分区空缺。映射示例：
  - "希望伴侣/支持人尽量陪在身边" → "重要决定请同步伴侣/支持人"
  - "希望医护多鼓励我、告诉我进展" → "希望团队主动给我反馈和鼓励"
  - "一些非必要操作，希望先和我沟通" → "干预前请先和我沟通必要性"
  - 其余 `top_priorities` 项不属于沟通方式，不要勉强转化。
- 若 `top_priorities` 含有宝宝出生后偏好，也应写入 `baby_after_birth`，例如“宝宝出生后，想尽早抱一抱/贴一贴”转为“出生后希望尽早肌肤接触”，“想尽早试着喂母乳”转为“希望尽早尝试母乳”。
- 若 `top_priorities` 含有侧切、产钳、真空吸引、人工破水等需要提前说明的操作，应写入 `intervention_preferences`。如果用户填写了无法归入既有分组的重点，转成 `communication` 里的温和短句，例如“希望医护团队知道：……”，不要因为前端不再独立展示 `top_priorities` 而丢失用户重点。
- `feeding_intention` 不单独成为卡片分区；如果用户填写，转化为 `baby_after_birth` 中的一条短句，例如“喂养意向：母乳喂养”。
- `questions_for_hospital` 最多 3 条，只放用户选择的 `hospital_questions_focus`、用户明确提出的问题，或根据分娩方式生成的通用确认问题；不要编造医院政策，不要放待产包物品问题。前端会把它作为普通沟通分组展示，不要把它写成独立“先确认”卡片。
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

## 剖宫产适配规则

如果 `confirmed_form_data.birth_path` 是 `剖宫产` 或同义表达，仍然使用同一个 `birth_plan_card` schema，不新增字段或分区。

生成时：

- 减少关于生产时换姿势、自由活动、自然缓解疼痛等顺产导向内容。
- 把重点放入已有字段：
  - `communication`：术前沟通、谁参与决策、如何解释变化。
  - `labor_preferences`：剖宫产用户通常可留空，除非用户明确仍需要相关沟通。
  - `intervention_preferences`：剖宫产用户通常可留空，除非用户明确仍需要相关沟通。
  - `pain_relief`：麻醉相关沟通和希望提前解释的选项。
  - `baby_after_birth`：出生后肌肤接触时间、喂养偏好、宝宝护理沟通。
  - `emergency_authorization`：紧急情况下希望优先如何沟通或决策。
  - `medical_notes`：仅放用户明确提供的过敏、医生说明或医院限制。
  - `questions_for_hospital`：陪同、拍照、术后接触宝宝、喂养和住院流程等需要和医院/医护团队沟通的问题。
- 不提供手术指导，不替代医生说明。

## 输出规则

- 卡片要简洁、可分享、适合手机保存。
- 需要较长解释时，放在 `ui_card_create` 外部的普通回复中。
- 不确定内容放入 `questions_for_hospital`，作为普通沟通问题呈现，不要编造医院政策。
- 即使用户想要可打印或可复制版本，也仍然通过 `ui_card_create` 提供 `card_json`；前端可以把它渲染/导出成 HTML、PNG 或 PDF。
- 如果已经有表单数据，视为用户已确认该草稿所需信息。
