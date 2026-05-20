# 待产包服务参考

当用户想要待产包、入院包、住院包、待产包卡片、入院物品准备或去医院前要带什么时，使用本参考文件。

## 产品目标

生成一份个性化、可打包、可分享的待产清单卡片，帮助用户减少临近生产时的混乱和焦虑。

待产包不是单纯的科普列表。最终产物应该同时回答：

- 现在这个孕周最应该先准备什么。
- 哪些是通常必带，哪些只是建议或可选。
- 每类物品建议带多少。
- 哪些要先和医院确认，不要重复买或误带。

即使用户信息不完整，也应该给出有用的结构化结果。优先使用分组、数量、优先级和医院确认项，不要生成一长串没有层次的物品列表。

## 待产包表单字段

表单门控和提交后的通用流程由主 `SKILL.md` 统一规定：首次进入待产包服务时先做服务邀约，不直接创建表单；用户确认开始后，再创建 `hospital_bag_intake` 表单；用户提交后再生成结构化卡片。本参考只定义待产包服务专属的表单字段、预填规则和兼容规则。

使用：

- `form_id`: `hospital_bag_intake`
- `title`: `信息采集`
- `description`: 留空字符串，不在表单标题下展示说明文字。
- `submit_label`: `生成我的卡片`

表单字段必须使用以下稳定 schema。`ui_form_create.fields` 里的每个字段都需要表示为 JSON object string。

创建表单前的共享预填规则由主 `SKILL.md` 统一规定。本参考只补充待产包表单专属字段的预填映射；不要把已知信息只写在普通回复里，也不要让用户重复填写。

待产包专属预填映射：

- 已知母乳/配方/混合/未确定 -> `feeding_intention.default_value`
- 已知年龄 -> `age.default_value`
- 已知 BMI、身高体重或行动便利相关信息 -> `bmi_or_weight_context.default_value`
- 已知妊娠病史、过敏、医生提醒或特殊注意事项 -> `pregnancy_history_or_notes.default_value`
- 已知预计住院时长 -> `expected_stay.default_value`
- 已知医院提供物品 -> `hospital_provided_items.default_value`

只有用户明确提供、`profile_get` 返回，或当前上下文可以稳定继承的信息才可预填；如果只是模型推测、风险不确定或存在冲突，留空并用 `placeholder` 引导用户确认。

当前前端表单协议没有单独的 section/header 字段。为了实现分类呈现，`hospital_bag_intake` 字段必须按下方顺序排列，并在用户可见 `label` 前使用分组前缀：

- `基本信息｜...`
- `生产信息｜...`
- `医院信息｜...`
- `偏好信息｜...`

不要创建仅用于装饰的假字段；所有字段都应是可填写或可选择的信息。

不要再收集用于控制清单长短或购买策略的单独字段。清单密度由孕周、是否临近入院、分娩方式、住院时长、医院已提供物品、是否第一胎和喂养意向共同决定。

必填字段只覆盖生成有价值待产包卡片所需的最低信息，控制在 4 个；可选字段允许为空，并在 `card_json` 中标为 `"待确认"`、写入 `missing_fields`，或放入 `hospital_context.items_to_confirm_with_hospital`。

表单体验原则：

- 不要让表单像医疗问卷；文案应强调“少带错、少漏带、少重复买”。
- 不要为待产包表单字段生成字段解释或字段下方说明文案；字段只保留标题、输入控件、必要 placeholder 和选项。
- 年龄、BMI、妊娠病史或特殊注意事项都只能作为待产包个性化和医院确认项参考，不能用于诊断、风险分级或医疗建议。
- 如果用户已上传产检材料、医院清单或 B 超单图片，只能基于当前可见内容辅助提取待确认信息；不要因此新增表单字段，不要根据图片作医学判断，关键信息仍需要用户确认。

必填字段：

```json
[
	  {
	    "id": "due_date_or_week",
	    "label": "基本信息｜预产期或当前孕周",
	    "type": "text",
	    "required": true,
	    "placeholder": "例如：2026-06-12 或 37 周"
	  },
	  {
	    "id": "first_birth",
	    "label": "基本信息｜是否第一胎",
	    "type": "select",
	    "required": true,
	    "options": ["是", "否", "不确定"]
	  },
	  {
	    "id": "birth_path",
	    "label": "生产信息｜计划分娩方式",
	    "type": "select",
	    "required": true,
	    "options": ["顺产", "剖宫产", "未确定"]
	  },
	  {
	    "id": "feeding_intention",
	    "label": "偏好信息｜喂养意向",
	    "type": "select",
	    "required": true,
	    "options": ["母乳", "配方", "混合", "未确定"]
	  }
	]
	```

可选字段：

```json
	[
	  {
	    "id": "age",
	    "label": "基本信息｜妈妈年龄",
	    "type": "text",
	    "required": false,
	    "placeholder": "例如：32；不想填可以留空"
	  },
	  {
	    "id": "bmi_or_weight_context",
	    "label": "基本信息｜BMI 或身高体重情况",
	    "type": "text",
	    "required": false,
	    "placeholder": "例如：BMI 24，或身高体重；不确定可留空"
	  },
	  {
	    "id": "pregnancy_history_or_notes",
	    "label": "基本信息｜妊娠病史或特殊注意事项",
	    "type": "textarea",
	    "required": false,
	    "placeholder": "例如：妊娠糖尿病、过敏史、医生提醒、行动不便等；没有可留空。"
	  },
	  {
	    "id": "birth_setting",
	    "label": "医院信息｜医院、地区或生产地点",
	    "type": "text",
	    "required": false,
	    "placeholder": "例如：某某医院、公立医院、私立医院、月子中心配套医院，或暂未确定"
	  },
	  {
	    "id": "expected_stay",
	    "label": "生产信息｜预计住院时长",
	    "type": "select",
	    "required": false,
	    "options": ["不确定", "1 天", "2-3 天", "4 天或以上", "医生/医院建议为准"]
	  },
	  {
	    "id": "support_person",
	    "label": "生产信息｜陪产人或支持人情况",
	    "type": "select",
	    "required": false,
	    "options": ["有，且需要准备物品", "有，但不需要准备物品", "暂时没有", "不确定"]
	  },
	  {
	    "id": "hospital_provided_items",
	    "label": "医院信息｜已知医院会提供的物品",
	    "type": "textarea",
	    "required": false,
	    "placeholder": "例如：产褥垫、纸尿裤、宝宝衣物、奶瓶、毛巾。不确定可留空。"
	  }
	]
	```

生成 `ui_form_create` 时，可以把必填字段和可选字段放在同一个 `fields` 数组中，但必须保持这些稳定 `id`、`type` 和 `required` 值。已知信息必须通过 `default_value` 进入对应字段；未知信息不要编造默认值。

## 表单提交后

收到 `hospital_bag_intake` 的 `confirmed_form_data` 后，按下方规则生成 `card_json` 并调用 `ui_card_create`。兼容旧版本表单：如果缺少 `feeding_intention`，可以继续生成卡片，并把 `owner.feeding_intention` 写成 `"待确认"`；不要因此卡住流程。

## 孕周阶段服务策略

生成待产包卡片前，必须先根据 `confirmed_form_data.due_date_or_week` 判断当前服务阶段。服务阶段会决定卡片覆盖范围、`packing_groups` 内容密度和 `timeline`。

如果用户只提供预产期，基于当前日期推断大致孕周或距离预产期的时间；如果 `due_date_or_week` 格式无法解析服务阶段，在 `timeline` 中保持保守建议，并在 `missing_fields` 中标记 `due_date_or_week`。

阶段规则：

1. 32 周前：规划确认型
   - 重点是确认医院要求、分娩方式变化可能、大件缺口和预算。
   - `packing_groups` 保持中等密度，不要过早生成完整到每个消耗品数量的超长清单。
   - `hospital_context.items_to_confirm_with_hospital` 优先放医院确认事项。

2. 32-35 周：采购准备型
   - 重点是购买或集中准备必需品。
   - `packing_groups` 覆盖证件文件包、妈妈住院包、宝宝出院包、陪产人包、车上备用包、产后回家第一周用品。
   - 通过 `focus_items` 提醒优先准备项；不要默认生成单独的采购缺口模块。

3. 36 周左右：实际打包型
   - 重点是把主要包和证件资料实际打包完成。
   - `packing_groups` 应包含具体数量，例如产褥垫、产妇卫生巾、一次性内裤、宝宝出院衣物等；证件和通讯设备不强行写数量。
   - `timeline` 应偏短、可执行。

4. 37 周以后或用户说“快生了”：即时可拿取型
   - 重点是马上能拿走的入院包。
   - 优先处理证件、生产必需品、宝宝出院物品、陪产人安排、交通和医院联系信息。
   - 减少非必需的 nice-to-have，避免增加用户负担。

`timeline` 是卡片里的准备时间线，不等于已经创建提醒。当前没有 reminder 工具；如需提醒，只能建议用户在 App 或日历中手动设置。

## 卡片 JSON 契约

最终产物必须通过 `ui_card_create` 创建结构化卡片产物。前端会把 `ui_card_create.card.card_json` 当作唯一数据源，并据此渲染移动端待产包卡片。

不要把很长的 markdown 清单当作卡片数据源。可以附一段简短说明，但卡片本身必须通过 `ui_card_create` 传递结构化 JSON。

默认生成“个性化说明 + 完整分组清单”的移动端卡片。前端会把分组渲染为可折叠清单，因此可以比旧版更具体，但仍要避免机械堆砌和重复。

待产包卡片必须体现“个性化”，不能只是把参考清单原样搬运。个性化体现在：

- `owner`：展示用户已确认的孕周/预产期、计划分娩方式、喂养意向、是否第一胎、医院或地区等。
- `packing_groups`：根据用户情况裁剪、保留或降级物品；不是每次都全量输出参考清单。
- `priority`：用 `must`、`recommended`、`nice_to_have`、`confirm_first` 区分必带物品、建议物品、可选物品和需要先和医院确认的物品。
- `quantity`：只用于消耗品、衣物、护理用品、宝宝用品等数量会影响准备的物品；证件资料和通讯随身设备通常不要写数量。
- `copy_requirement`：用于证件资料，表达是否需要复印件，例如 `"原件"`、`"原件+复印件"`；`confirm_first` 物品不要写 `copy_requirement`。
- `personalized_notes`：明确说明这张清单为什么这样调整，例如“你选择母乳，因此保留哺乳用品和吸奶器备用项”。
- `focus_items`：兼容字段，可留空；仅在旧版回退展示或工具 handler 需要摘要时生成，最多保留最需要先打包、忘带影响最大的 5-7 项，不要依赖它传达核心内容。
- `hospital_questions`：兼容字段，可留空；仅在旧版回退展示或工具 handler 需要摘要时生成，每条仍使用“物品/规则：一句话解释”的结构。
- `hospital_context.items_to_confirm_with_hospital`：明确写出“哪些物品/规则需要问医院”，不要只写泛泛的“按医院要求”。

清单密度规则：

- `packing_groups` 是主清单，按场景分包，最多 6 个分组。
- 每组最多 8 个 items；全卡片主清单通常控制在 24-48 个 items。
- 临近入院或用户明显紧张时，优先压缩到最容易执行的必带和医院确认项，避免增加负担。
- 用户孕周较早且时间充裕时，可以覆盖更完整的分组，但仍应避免机械堆砌。
- 医院已明确提供的物品应降级或移出主清单，不要为了凑数量保留重复物品。
- `hospital_context.items_to_confirm_with_hospital` 最多 5 条，只放必须向医院确认的问题。
- `focus_items` 是兼容摘要字段，可以留空；若生成，最多 7 条，优先放“入院马上需要、忘带影响最大”的物品，不要机械复制所有必带项。
- `hospital_questions` 是兼容摘要字段，可以留空；若生成，最多 8 条，必须是明确可问医院的问题，并统一写成“物品/规则：一句话解释”。
- `timeline` 最多 3 条，偏行动导向，不要展开成详细计划。
- `personalized_notes` 最多 3 条，只放真正个性化且没有在其他分区出现过的提醒。
- 不要同时在 `packing_groups`、`focus_items`、`hospital_questions`、`personalized_notes` 中重复同一句话或同一物品说明。
- 对未知信息，不要为了填满卡片而反复显示 `"待确认"`；只有影响下一步行动的未知项才写入 `missing_fields` 或 `items_to_confirm_with_hospital`。

使用以下 schema。`focus_items` 和 `hospital_questions` 是兼容摘要字段，默认保留空数组；只有 handler 明确需要旧版回退摘要时才裁剪填入：

```json
{
  "card_type": "hospital_bag_card",
  "schema_version": "1.0",
  "title": "待产包",
  "subtitle": "个性化入院物品清单",
  "owner": {
    "due_date_or_week": "待确认",
    "birth_setting": "待确认",
    "birth_path": "待确认",
    "first_birth": "待确认",
    "feeding_intention": "待确认",
    "support_person": "待确认"
  },
  "hospital_context": {
    "expected_stay": "待确认",
    "hospital_provided_items": [],
    "items_to_confirm_with_hospital": [
      "胎监带：确认医院是否要求自带，以及需要几条。",
      "宝宝纸尿裤和衣物：确认医院是否提供，避免重复携带。"
    ]
  },
  "focus_items": [],
  "hospital_questions": [],
  "packing_groups": [
    {
      "group_id": "documents",
      "title": "证件文件包",
      "items": [
        {
          "label": "夫妻双方身份证",
          "copy_requirement": "原件+复印件",
          "priority": "must",
          "note": "以医院入院登记要求为准。",
          "confirm_question": ""
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
- 每个物品 item 应包含 `label`、`priority`，可选 `quantity`、`copy_requirement`、`note`、`confirm_question`。
- `quantity` 必须是面向用户的中文短文本，例如 `"10-20片"`、`"1套"`、`"若干"`、`"按住院天数"`。
- 不要为了格式整齐给所有物品都写数量：
  - 证件资料优先使用 `copy_requirement`，不要写 `"1套"`、`"2份"` 这类数量。
  - 手机、充电器、充电宝、耳机等通讯随身设备通常不写数量；用户默认只带自己的常用设备。
  - 消耗品和多件物品才写数量，例如产褥垫、卫生巾、一次性内裤、纸巾、宝宝衣物、包被。
- `copy_requirement` 只用于证件资料，取值示例：`"原件"`、`"原件+复印件"`。
- 当 `priority` 是 `confirm_first` 时，不要写 `quantity` 或 `copy_requirement`；待产清单里只需要物品名和“和医院确认”标签，解释放到 `confirm_question`、`hospital_questions` 或 `hospital_context.items_to_confirm_with_hospital`。
- 每个物品标签保持简洁，便于移动端卡片扫读。
- 当 `priority` 是 `confirm_first` 时，必须写清楚原因：
  - 优先在 `confirm_question` 中写一句可直接问医院的问题，例如 `"确认医院是否提供脸盆；如果提供，可以不带。"`。
  - 不要在 `note`、`quantity` 或 `copy_requirement` 里写 `"按医院要求确认"`、`"按医院要求"`、`"按需要"` 这类泛化补充信息。
  - 相关问题必须同步写入 `hospital_context.items_to_confirm_with_hospital`，并带上物品名。
- App 端根据 `card_json` 的分区 key 自行决定渲染分区；模型不要输出 markdown 版待产包卡片。
- `focus_items` 和 `hospital_questions` 是可选兼容数据源，不是前端默认独立展示区；可以留空。核心清单内容必须体现在 `packing_groups`，个性化原因必须体现在 `personalized_notes`。

priority 取值：

- `must`：通常应准备的入院关键物品，例如证件资料、支付材料、手机充电器、宝宝出院基础物品。
- `recommended`：多数用户有帮助，但不是所有医院或所有用户都必须准备。
- `nice_to_have`：舒适或备用物品；临近生产或客观条件不需要时可以减少。
- `confirm_first`：不要直接当作必带物品；应先向医院确认是否允许、是否需要或是否由医院提供。

字段缺失规则：

- 字段在 schema 中有固定位置但用户未提供时，使用 `"待确认"`。
- 缺失信息会影响个性化、清单优先级或住院准备判断时，写入 `missing_fields`。
- 医院政策、医院是否提供物品或入院规则未知时，优先写入 `hospital_context.items_to_confirm_with_hospital`，不要编造。
- `hospital_provided_items` 保存用户已确认医院会提供的物品；`items_to_confirm_with_hospital` 保存仍需要用户向医院确认的问题、医院政策或入院规则，不再单独收集医院规则说明字段。

数组关系：

- `packing_groups` 是完整卡片清单，必须按使用场景分组，不按物品品类分组。
- 固定场景分组优先使用以下 `group_id/title`，按顺序输出；没有相关物品的分组可以省略，不要为了凑齐 6 组硬塞物品：
  1. `documents` / `证件文件包`
  2. `mom_hospital_bag` / `妈妈住院包`
  3. `baby_discharge_bag` / `宝宝出院包`
  4. `support_person_bag` / `陪产人包`
  5. `car_backup_bag` / `车上备用包`
  6. `postpartum_home_first_week` / `产后回家第一周用品`
- 不再按“通讯工具、妈妈清洁护理、妈妈衣物、哺乳用品、饮食相关、宝宝用品”等品类创建独立分组；这些物品要归入对应场景包。
- `focus_items` 是可选兼容摘要字段，来源于固定规则和用户阶段；可以留空，不要等同于完整清单中的全部 `must` 项，也不要依赖它作为默认展示模块。
- `hospital_questions` 是可选兼容摘要字段，来源于固定问题库和用户情况；可以留空。若生成，可同步写入 `hospital_context.items_to_confirm_with_hospital` 保持兼容。每条必须写成“物品/规则：一句话解释”，不要写成一个没有对象的长问题，也不要依赖它作为默认展示模块。
- `missing_or_to_buy` 是兼容字段，不参与默认卡片主展示；除非用户明确要购买缺口或购物清单，否则保持空数组；明确需要时最多输出 5 条。
- `hospital_context.items_to_confirm_with_hospital` 必须是明确问题，不要是笼统提醒。推荐格式：`物品/规则：一句话解释。`

## 基础物品库与个性化裁剪

图片清单中的物品是待产包基础物品库，不等于每个用户都要完整携带。生成卡片时按以下顺序处理：

1. 先以参考清单作为候选物品库，保留证件文件包、妈妈住院包、宝宝出院包、陪产人包、车上备用包、产后回家第一周用品等基础场景。
2. 再根据用户情况裁剪：
   - 计划分娩方式：剖宫产减少顺产待产过程舒适物，增加“住院时长、方便拿取、宽松出院衣物”等提示。
   - 喂养意向：母乳/混合保留哺乳用品和吸奶器；配方喂养减少哺乳用品，把奶瓶/配方奶放入医院确认项。
   - 预计住院时长：调整消耗品数量，例如产褥垫、一次性内裤、宝宝纸尿裤。
   - 医院已提供物品：主清单中降级或不再重复列为必带；不要为了填充字段生成购买缺口。
   - 是否第一胎：第一胎增加医院确认问题和支持人提示。
3. 最后输出：
   - 物品清单：写入 `packing_groups`，按场景分组呈现。
   - 和医院确认的物品：在 `packing_groups` 中标记 `priority: "confirm_first"`，必要时同步到 `hospital_questions` 或 `hospital_context.items_to_confirm_with_hospital` 保持兼容。
   - 个性化理由：写入 `personalized_notes`。

## `focus_items` 兼容摘要规则

`focus_items` 只是旧版兼容摘要，可以留空。确实需要生成时，应相对稳定，不要每次临时发挥；先从以下固定基线挑选，再按用户情况裁剪到 5-7 条：

1. 37 周以后或用户说“快生了”：优先保留“马上拿走”物品。
   - 身份证、医保卡、产检资料
   - 手机和充电线
   - 产褥垫/产妇卫生巾
   - 一次性内裤
   - 妈妈宽松出院衣物
   - 宝宝出院衣物和包被
   - 吸管杯
2. 32-36 周：优先保留“要尽快买齐/打包”的物品。
   - 证件资料
   - 产褥垫/产妇卫生巾
   - 一次性内裤
   - 宝宝出院衣物和包被
   - 手机充电线
   - 哺乳用品基础项（仅母乳/混合喂养）
3. 剖宫产：关键摘要中更优先放宽松出院衣物、方便拿取的洗漱用品、长充电线；不要突出顺产待产过程舒适物。
4. 配方喂养：不要把吸奶器、乳盾、初乳收集器放入关键摘要。
5. 医院已明确提供的物品，不要放入 `focus_items`。

`focus_items` 可以是字符串数组，也可以是对象数组；为了移动端稳定，优先使用短字符串。

## 医院确认兼容问题库

`hospital_questions` 只是旧版兼容摘要，可以留空。确实需要生成时，必须来自以下固定问题库，再按用户情况裁剪排序。不要输出笼统的“按医院要求确认”，也不要写成没有对象的长句。每条使用“物品/规则：一句话解释”。

固定问题库：

- 准生证/户口本：确认医院是否要求携带原件和复印件，以及复印件份数。
- 产褥垫/纸尿裤/宝宝衣物：确认医院是否提供，避免重复携带。
- 胎监带/收腹带：确认是否需要自带；剖宫产先问医生是否建议使用收腹带。
- 陪产/探视：确认是否允许陪产或探视，以及陪产人是否可以过夜。
- 水/零食/吸管杯：确认产房和病区是否允许携带。
- 奶瓶/配方奶/吸奶器：确认医院是否允许携带或是否由医院提供。
- 住院时长/出院要求：确认预计住院几天，以及宝宝出院衣物是否有要求。
- 安全座椅/安全提篮：确认出院交通是否需要，以及医院或当地是否有规则要求。

裁剪规则：

- 母乳/混合喂养：保留“喂养支持”问题。
- 配方喂养：保留“奶瓶、配方奶是否允许或是否由医院提供”的问题。
- 剖宫产：保留“住院安排”和“收腹带/术后用品是否建议”的问题。
- 第一胎：优先保留入院证件、医院提供物品、陪产/探视、住院安排。
- 如果用户已填写医院会提供某类物品，不要再重复问同一问题。

## 参考清单内容

以下是生成 `packing_groups` 时的内容基线。要根据用户的孕周、分娩方式、住院时长、喂养意向、医院提供物品、是否第一胎和临近程度裁剪，不要每次机械全量输出。

1. 证件文件包
   - 夫妻双方身份证：`must`，`copy_requirement`: `原件+复印件`
   - 准生证：`confirm_first`，确认问题：医院是否要求准生证及复印件。
   - 户口本：`confirm_first`，确认问题：医院是否要求户口本及复印件。
   - 医保本/医保卡：`must`，`copy_requirement`: `原件`
   - 产检本/产检资料：`must`，`copy_requirement`: `原件`
   - 银行卡/现金/移动支付：`must`

2. 妈妈住院包
   - 手机：`must`
   - 充电线及充电器：`must`，note：建议带长充电线，方便病床旁使用。
   - 充电宝：`recommended`
   - 耳机：`nice_to_have`
   - 夜用卫生巾/产妇卫生巾：15片，`must`
   - 产褥垫：10-20片，`must`
   - 一次性内裤：若干条，`recommended`
   - 一次性马桶垫：30-50片，`recommended`
   - 牙刷牙膏：各1支，`must`
   - 毛巾/棉柔巾：4条/2包，`recommended`
   - 脸盆：`confirm_first`，确认问题：医院是否提供脸盆或是否允许自带。
   - 洗发水、沐浴露、洗面奶、护肤品：旅行装各1份，`nice_to_have`
   - 纸巾：5包，`recommended`
   - 出院外套/宽松出院衣物：1套，`must`
   - 拖鞋：1双，`must`
   - 胎监带：`confirm_first`，确认问题：医院是否要求自带胎监带，以及需要几条。
   - 收腹带：`confirm_first`，确认问题：医生/医院是否建议产后使用，剖宫产尤其先问医生。
   - 哺乳衣/前开扣睡衣：1-2件，`recommended`
   - 吸管杯：1个，`must`
   - 餐具：1套，`recommended`
   - 助产食品/能量补给：`confirm_first`，确认问题：产房是否允许进食、允许带哪些食物。
   - 允许情况下的零食和水：`confirm_first`，确认问题：住院区/产房是否允许自带食物。

3. 宝宝出院包
   - 纸尿裤：`confirm_first`，确认问题：医院是否提供纸尿裤；如果不提供，问建议数量。
   - 湿巾/棉柔巾：1-2包，`recommended`
   - 包被：1条，`must`
   - 出院衣物：1套，`must`
   - 帽子/袜子：各1-2件，`recommended`
   - 安全座椅：`confirm_first`，确认问题：出院交通是否需要安全座椅或安全提篮。

4. 陪产人包
   - 身份证件：`must`，`copy_requirement`: `原件`
   - 手机充电器：`must`
   - 水和零食：按住院天数，`recommended`
   - 换洗衣物和洗漱用品：1套，`recommended`
   - 常用药、停车/支付用品：按个人情况，`recommended`

5. 车上备用包
   - 备用产褥垫/产妇卫生巾：少量，`recommended`
   - 纸巾/湿巾：少量，`recommended`
   - 水：少量，`recommended`
   - 备用衣物：1套，`nice_to_have`
   - 手机充电线：`recommended`
   - 医院路线、停车和支付用品：`recommended`

6. 产后回家第一周用品
   - 一次性防溢乳垫：5-10片，`recommended`
   - 哺乳文胸/哺乳背心：2-3件，`recommended`
   - 吸奶器：1台，`recommended`
   - 储奶瓶/初乳收集器：1个，`recommended`
   - 乳盾：`confirm_first`，确认问题：是否需要乳盾应先听哺乳顾问或医院建议。
   - 乳头霜：1支，`recommended`

## 个性化规则

- 临近入院或用户说“马上要生/快生了”：优先证件、通讯、妈妈产后基础护理、宝宝出院基础物品和医院确认项；减少舒适备用项。
- 孕周较早且用户有时间准备：覆盖常见住院需求，并加入产后回家第一周用品、宝宝出院包、陪产人包和需要提前向医院确认的项目。
- 用户提到已有物品、医院可能提供物品或担心重复准备时：优先把相关内容放入医院确认项，避免重复列为必带。
- 第一胎：加入更多医院确认问题、数量提示和支持人角色提示。
- 非第一胎：询问或参考上次缺什么/什么没用上，并据此调整。
- 母乳或混合喂养：保留哺乳用品和吸奶器；吸奶器用 `recommended`，不要表达成必须购买。
- 配方喂养：减少哺乳用品；奶瓶、配方奶相关内容优先进入医院确认项，不要擅自建议带入医院。
- 医院已提供某物品：不要再把它作为 `must` 重复放入主清单，可放入 `hospital_provided_items`。

## 剖宫产适配规则

如果 `confirmed_form_data.birth_path` 是 `剖宫产` 或同义表达，仍然使用同一个 `hospital_bag_card` schema，不新增字段或分区。

生成时：

- 减少顺产待产过程中特有的物品重点，例如长时间走动、分娩球、自然镇痛辅助物等，除非用户明确需要。
- 把重点放入已有字段：
  - `packing_groups`：证件文件包、妈妈住院包、宝宝出院包、陪产人包、车上备用包、产后回家第一周用品。
  - `hospital_context.items_to_confirm_with_hospital`：住院时长、陪同规则、术后宝宝接触、喂养支持、医院提供物品。
  - `personalized_notes`：更长住院假设、物品方便拿取、支持人安排。
  - `timeline`：按计划日期倒推准备节奏。
- 不提供手术指导，不替代医生说明。

## 购物车链接规则

- 生成待产包卡片后，只要 `ui_card_create` 的工具结果里包含 `assistant_followup`，最终普通回复必须包含其中的购物车资源提示。
- 生成完成后的第一句要像真人把成果递给用户，而不是系统播报。推荐语气类似：“你的待产包已经生成好了哦～我也顺手把适合直接购买的妈妈/宝宝用品整理成了购物车，方便你慢慢核对、删减。”
- 不要把购物车链接写入 `card_json`；链接只出现在 `ui_card_create` 外部的普通回复文本中。
- 链接固定为：`/hospital-bag-cart`。
- 普通回复文本中使用显眼的 Markdown 短链接格式：`**[打开待产包一键打包下单页](/hospital-bag-cart)**`。
- 购物车只打包适合直接购买的妈妈和宝宝母婴用品，例如产褥垫、一次性内裤、宝宝纸尿裤、湿巾、棉柔巾、包被、防溢乳垫、储奶袋、吸奶器等。
- 证件资料、医院规则、医院确认项、药物、医疗处置相关内容不要打包为商品。
- 推荐语气必须弱化推销意味：强调“可以先打开购物车核对和删减”，不要暗示用户必须购买，也不要制造焦虑。

## 安全与政策边界

- 不编造医院政策。
- 不建议用户自行携带药物或医疗设备，除非提醒其遵循医生/医院指导。
- 如果用户报告已经临产、大出血、严重疼痛、胎动减少或其他紧急症状，停止打包建议，优先建议联系医生、医院或急救服务。
