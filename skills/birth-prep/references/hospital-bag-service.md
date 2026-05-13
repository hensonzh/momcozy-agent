# 待产包服务参考

当用户想要待产包、入院包、待产包卡片、入院准备或预产期临近准备计划时，使用本参考文件。

## 产品目标

生成一份个性化的待产包卡片，帮助用户减少临近生产时的混乱和焦虑。

即使用户信息不完整，也应该给出有用的结构化结果。优先使用分组、分阶段的清单，不要生成一长串没有层次的物品列表。

## 表单优先的信息采集策略

当用户请求待产包、入院包、待产包卡片或入院准备，且相关信息尚未确认时，优先创建前端可渲染表单，而不是在聊天里连续追问。

硬性规则：如果当前用户消息中没有 `confirmed_form_data`，不要生成最终待产包卡片。必须先创建表单。

在调用 `ui_form_create` 前，先输出一句简短引导，说明这些问题会帮助按孕周、分娩方式、住院背景和打包风格生成更贴合的待产包卡片。不要只展示表单。

使用：

- `form_id`: `hospital_bag_intake`
- `title`: `待产包卡片`
- `description`: `确认几个背景信息后，我会按你的孕周、分娩方式和打包风格生成个性化待产包卡片。`
- `submit_label`: `生成我的卡片`

表单字段必须使用以下稳定 schema。`ui_form_create.fields` 里的每个字段都需要表示为 JSON object string。

必填字段只覆盖生成有价值待产包卡片所需的最低信息；可选字段允许为空，并在 `card_json` 中标为 `"待确认"`、写入 `missing_fields`，或放入 `hospital_context.items_to_confirm_with_hospital`。

必填字段：

```json
[
  {
    "id": "due_date_or_week",
    "label": "预产期或当前孕周",
    "type": "text",
    "required": true,
    "placeholder": "例如：2026-06-12 或 37 周",
    "help_text": "用于判断打包优先级和准备时间线。"
  },
  {
    "id": "birth_path",
    "label": "当前分娩方式",
    "type": "select",
    "required": true,
    "options": ["顺产", "计划剖宫产", "未确定", "医生建议为准"],
    "help_text": "如果还没确定，可以选择“未确定”或“医生建议为准”。"
  },
  {
    "id": "packing_style",
    "label": "打包风格",
    "type": "select",
    "required": true,
    "options": ["极简", "标准", "完整", "预算优先"],
    "help_text": "用于控制清单长度和物品优先级。"
  },
  {
    "id": "first_birth",
    "label": "是否第一胎",
    "type": "select",
    "required": true,
    "options": ["是", "否", "不确定"],
    "help_text": "第一胎通常需要更多医院确认问题和支持人提示。"
  }
]
```

可选字段：

```json
[
  {
    "id": "birth_setting",
    "label": "医院、地区或生产地点",
    "type": "text",
    "required": false,
    "placeholder": "例如：某某医院、公立医院、私立医院、月子中心配套医院，或暂未确定"
  },
  {
    "id": "expected_stay",
    "label": "预计住院时长",
    "type": "select",
    "required": false,
    "options": ["不确定", "1 天", "2-3 天", "4 天或以上", "医生/医院建议为准"]
  },
  {
    "id": "support_person",
    "label": "陪产人或支持人情况",
    "type": "select",
    "required": false,
    "options": ["有，且需要准备物品", "有，但不需要准备物品", "暂时没有", "不确定"]
  },
  {
    "id": "feeding_intention",
    "label": "喂养意向",
    "type": "select",
    "required": false,
    "options": ["母乳", "配方", "混合", "未确定"]
  },
  {
    "id": "hospital_provided_items",
    "label": "已知医院会提供的物品",
    "type": "textarea",
    "required": false,
    "placeholder": "例如：产褥垫、纸尿裤、宝宝衣物、奶瓶、毛巾。不确定可留空。"
  },
  {
    "id": "hospital_rules_or_notes",
    "label": "已知医院规则或注意事项",
    "type": "textarea",
    "required": false,
    "placeholder": "例如：陪产限制、食物规则、拍照录像规则、入院材料要求。不确定可留空。"
  }
]
```

生成 `ui_form_create` 时，可以把必填字段和可选字段放在同一个 `fields` 数组中，但必须保持这些稳定 `id`、`type` 和 `required` 值。

如果用户已经临近预产期或明显焦虑，仍然先创建表单，除非用户报告紧急症状或明确要求跳过表单。

## 表单提交后

当用户提交或确认表单数据后，直接生成 `card_json` 并调用 `ui_card_create`。除非必填答案相互矛盾或存在不安全表达，否则不要重复询问同样的问题。

## 孕周阶段服务策略

生成待产包卡片前，必须先根据 `confirmed_form_data.due_date_or_week` 判断当前服务阶段。服务阶段会决定卡片覆盖范围、`packing_groups` 内容密度和 `timeline`。

如果用户只提供预产期，基于当前日期推断大致孕周或距离预产期的时间；如果 `due_date_or_week` 格式无法解析服务阶段，在 `timeline` 中保持保守建议，并在 `missing_fields` 中标记 `due_date_or_week`。

阶段规则：

1. 32 周前：规划确认型
   - 重点是确认医院要求、分娩方式变化可能、大件缺口和预算。
   - `packing_groups` 保持简洁，避免过早生成过长清单。
   - `hospital_context.items_to_confirm_with_hospital` 优先放医院确认事项。

2. 32-35 周：采购准备型
   - 重点是购买或集中准备必需品。
   - `packing_groups` 覆盖 Documents、Labor、Postpartum、Baby、Partner/Support。
   - `missing_or_to_buy` 应突出还需要购买或补齐的物品类型。

3. 36 周左右：实际打包型
   - 重点是把主要包和证件资料实际打包完成。
   - `packing_groups` 优先覆盖证件资料、妈妈入院必需品、宝宝出院物品、手机充电器、医院确认项。
   - `timeline` 应偏短、可执行。

4. 37 周以后或用户说“快生了”：即时可拿取型
   - 重点是马上能拿走的入院包。
   - 优先处理证件、生产必需品、宝宝出院物品、陪产人安排、交通和医院联系信息。
   - 减少非必需的 nice-to-have，避免增加用户负担。

`timeline` 是卡片里的准备时间线，不等于已经创建提醒。当前没有 reminder 工具；如需提醒，只能建议用户在 App 或日历中手动设置。

## 卡片 JSON 契约

最终产物必须通过 `ui_card_create` 创建结构化卡片产物。前端会把 `ui_card_create.card.card_json` 当作唯一数据源，并据此渲染移动端待产包卡片。

不要把很长的 markdown 清单当作卡片数据源。可以附一段简短说明，但卡片本身必须通过 `ui_card_create` 传递结构化 JSON。

默认生成移动端简化版卡片。目标是在用户一屏到两屏内看懂“背景摘要、精简清单、还要向医院确认什么”，不要把同一信息在多个分区中重复表达。

简化规则：

- `packing_groups` 是主清单，最多 3 个分组；每组最多 4 个 items；全卡片主清单总量优先控制在 10-12 个 items。
- `hospital_context.items_to_confirm_with_hospital` 最多 3 条，只放必须向医院确认的问题。
- `missing_or_to_buy` 最多 3 条，只放用户可能真的需要补齐/购买的类别；不要复制 `packing_groups` 已有完整条目。
- `timeline` 最多 2 条，偏行动导向，不要展开成详细计划。
- `personalized_notes` 最多 2 条，只放真正个性化且没有在其他分区出现过的提醒。
- 不要同时在 `packing_groups`、`missing_or_to_buy`、`personalized_notes` 中重复同一句话或同一物品说明。
- 对未知信息，不要为了填满卡片而反复显示 `"待确认"`；只有影响下一步行动的未知项才写入 `missing_fields` 或 `items_to_confirm_with_hospital`。

使用以下 schema：

```json
{
  "card_type": "hospital_bag_card",
  "schema_version": "1.0",
  "title": "待产包卡片",
  "subtitle": "个性化入院打包计划",
  "owner": {
    "due_date_or_week": "待确认",
    "birth_setting": "待确认",
    "birth_path": "待确认",
    "packing_style": "standard",
    "first_birth": "待确认",
    "support_person": "待确认"
  },
  "hospital_context": {
    "expected_stay": "待确认",
    "hospital_provided_items": [],
    "hospital_rules_or_notes": [],
    "items_to_confirm_with_hospital": []
  },
  "packing_groups": [
    {
      "group_id": "documents",
      "title": "证件资料包",
      "items": [
        {
          "label": "身份证件和医保/保险或支付资料",
          "priority": "must",
          "note": "提前确认医院入院登记要求。"
        }
      ]
    }
  ],
  "missing_or_to_buy": [],
  "timeline": [],
  "personalized_notes": [],
  "missing_fields": [],
  "disclaimer": "请优先遵循医院要求和医生/助产士的具体指导。"
}
```

规则：

- 必须使用 schema 中稳定的 snake_case key。
- `packing_groups` 是卡片的主清单内容。
- 每个物品 item 应包含 `label`、`priority`，可选 `note`。
- 每个物品标签保持简洁，便于移动端卡片扫读。
- App 端根据 `card_json` 的分区 key 自行决定渲染分区；模型不要输出 markdown 版待产包卡片。

priority 取值：

- `must`：通常应准备的入院关键物品，例如证件资料、支付材料、手机充电器、宝宝出院基础物品。
- `recommended`：多数用户有帮助，但不是所有医院或所有用户都必须准备。
- `nice_to_have`：舒适或备用物品；预算优先或临近生产时可以减少。
- `confirm_first`：不要直接当作必带物品；应先向医院确认是否允许、是否需要或是否由医院提供。

字段缺失规则：

- 字段在 schema 中有固定位置但用户未提供时，使用 `"待确认"`。
- 缺失信息会影响个性化、打包优先级或住院准备判断时，写入 `missing_fields`。
- 医院政策、医院是否提供物品或入院规则未知时，优先写入 `hospital_context.items_to_confirm_with_hospital`，不要编造。
- `hospital_provided_items` 保存用户已确认医院会提供的物品；`hospital_rules_or_notes` 保存用户已知规则；`items_to_confirm_with_hospital` 保存仍需要用户向医院确认的问题。

数组关系：

- `packing_groups` 是完整卡片清单，按使用场景分组。
- `missing_or_to_buy` 只放用户可能还没准备、需要购买或补齐的物品类型。
- `missing_or_to_buy` 必须用更短的类别化表达，不能机械重复 `packing_groups` 的完整条目。

商品链接规则：

- 如果推荐的 `card_json` 物品中包含吸奶器，在 `ui_card_create` 外部的普通回复文本中附带购买链接。
- 生成待产包卡片后，只要 `ui_card_create` 的工具结果里包含 `assistant_followup`，最终普通回复必须包含其中的资源提示；可以按用户语言轻微改写，但必须保留短链接 `[sea.momcozy.com](https://sea.momcozy.com/collections/weekly-deals/products/momcozy-mobile-style-hands-free-breast-pump?variant=46306441625789)`。
- 不要把购买链接写入 `card_json`。
- 链接固定为：https://sea.momcozy.com/collections/weekly-deals/products/momcozy-mobile-style-hands-free-breast-pump?variant=46306441625789
- 普通回复文本中不要裸露完整长链接，使用 Markdown 短链接格式：`[sea.momcozy.com](https://sea.momcozy.com/collections/weekly-deals/products/momcozy-mobile-style-hands-free-breast-pump?variant=46306441625789)`。
- 推荐语气必须弱化推销意味：只作为“如果你还没有准备、可以先了解/作为可选备用”的资源提示，不要暗示用户必须购买，也不要制造焦虑。
- 如果用户明确表示不打算母乳、医院已提供完整泌乳支持或不想看商品推荐，可以不附购买链接。

## 打包架构

按真实使用场景分组：

1. 证件资料包
   - 身份证件、医保/保险或支付资料、医院建档/预约信息、产检资料、分娩沟通卡、重要联系人。

2. 待产随身包
   - 舒适衣物、袜子、拖鞋、润唇膏、吸管水杯、允许情况下的零食、手机充电器、充电宝、安抚物。

3. 妈妈入院基础包
   - 哺乳或前开扣衣物、宽松出院衣物、如果医院不提供则准备产褥垫/一次性内裤、洗漱用品、必要时毛巾、防溢乳垫、如计划母乳可准备乳头膏。
   - 加入吸奶器或便携式吸奶器，priority 使用 `recommended`；note 保持温和，例如“如果计划母乳、混合喂养，或想为初期涨奶/追奶留一个备用选择，可带上；具体使用以医院和哺乳顾问建议为准。”

4. 宝宝出院包
   - 出院衣物、如果医院不提供则准备纸尿裤、湿巾或棉柔巾、包被、帽子、袜子、需要时准备安全座椅。

5. 陪产人/支持人包
   - 身份证件、手机充电器、零食、水、换洗衣物、洗漱用品、常用药、停车/支付用品。

6. 先向医院确认
   - 取决于医院政策或医院是否提供的物品，例如配方奶、奶瓶、纸尿裤、毛巾、分娩球、TENS、拍照录像、额外陪护人员、食物规则等。

## 个性化规则

- 极简：证件、生产必需品、产后基础物品、宝宝出院基础物品。
- 标准：覆盖常见住院需求，并加入舒适物品和陪产包。
- 完整：增加备用物品、舒适偏好、额外衣物和场景补充。
- 预算优先：优先关键必需品，标注舒适备用项，避免和医院提供物品重复。
- 第一胎：加入更多医院确认问题和支持人角色提示。
- 非第一胎：询问上次缺什么/什么没用上，并据此调整。

## 计划剖宫产适配规则

如果 `confirmed_form_data.birth_path` 是 `计划剖宫产`，仍然使用同一个 `hospital_bag_card` schema，不新增字段或分区。

生成时：

- 减少顺产待产过程中特有的物品重点，例如长时间走动、分娩球、自然镇痛辅助物等，除非用户明确需要。
- 把重点放入已有字段：
  - `packing_groups`：宽松出院衣物、方便拿取的洗漱用品、长充电线、产后基础物品、宝宝出院物品、陪产人包。
  - `hospital_context.items_to_confirm_with_hospital`：住院时长、陪同规则、术后宝宝接触、喂养支持、医院提供物品。
  - `personalized_notes`：更长住院假设、物品方便拿取、支持人安排。
  - `timeline`：按计划日期倒推准备节奏。
- 不提供手术指导，不替代医生说明。

## 安全与政策边界

- 不编造医院政策。
- 不建议用户自行携带药物或医疗设备，除非提醒其遵循医生/医院指导。
- 如果用户报告已经临产、大出血、严重疼痛、胎动减少或其他紧急症状，停止打包建议，优先建议联系医生、医院或急救服务。
