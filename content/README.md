# Content 基础规则

## 1. Content 与 SQLite 的关系

- `content/` 是 authoring source of truth（人工维护、Git 版本控制）
- SQLite 是 runtime representation（运行时数据库）
- 运行时不能每次请求直接读取 YAML / Markdown
- 后续通过 import/sync 脚本：content/ → 校验 → 导入 SQLite

## 2. Knowledge Point 目录结构

按技术域拆分 YAML 文件：

```
content/knowledge/
├── spark.yaml
├── hive.yaml
└── ...
```

每个文件包含一个顶级知识点及其子知识点。

## 3. Stable ID 规则

- 全小写
- 技术域层级使用 `.` 连接（如 `spark.shuffle`）
- 多单词使用 `_` 连接（如 `spark.data_skew`）
- ID 是稳定业务标识，一旦进入历史数据，不因显示名称（`name`）调整而改变
- `name` 可以修改，`id` 不可修改

示例：

```
spark
spark.rdd
spark.shuffle
spark.stage
hive
hive.partition
hive.table_type
```

## 4. YAML Knowledge Point 字段

### 必填

| 字段 | 说明 |
|------|------|
| `id` | 稳定知识点 ID |
| `name` | 显示名称 |
| `sort_order` | 同级排序，非负整数 |

### 可选

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `description` | null | 知识点简介 |
| `is_active` | true | 是否有效 |
| `children` | 无 | 子知识点列表（authoring-only 字段） |

### 数据库派生字段（不写在 YAML 中）

| 字段 | 派生规则 |
|------|---------|
| `parent_id` | 根据嵌套父节点的 `id` 推导，顶级为 null |
| `level` | 根据嵌套深度推导：顶级 = 1，每层 + 1 |

`created_at` / `updated_at` 由数据库负责。

## 5. children 派生规则

`children` 是 YAML authoring-only 字段，不直接对应数据库字段。

导入时 flatten：

```
children → parent_id + level
```

示例：

```yaml
- id: spark           # parent_id = null, level = 1
  children:
    - id: spark.rdd   # parent_id = "spark", level = 2
    - id: spark.shuffle  # parent_id = "spark", level = 2
```

## 6. sort_order 规则

- 必须为非负整数
- 同级知识点按 `sort_order` 升序排列
- 不要求连续（1, 2, 3 或 1, 5, 10 都可）
- 相同 `sort_order` 暂时允许，后续展示可再以 `id` 做稳定次序

## 7. is_active 规则

- 默认 `true`
- 设为 `false` 表示知识点退役
- import 时更新 DB 对应字段
- 不 hard delete，保留历史数据关联

## 8. 数据消失处理

YAML 中消失的数据不 hard delete。后续 import 结合 `is_active` 设计处理。

## 9. 后续计划

- Task 2.7：validator（校验 ID 唯一性、parent 存在性、level 一致性等）
- Task 2.8：importer（实际同步到 SQLite）
- 当前尚未定义 Question Schema

---

## 10. Knowledge Card 目录结构

```
content/cards/
├── spark.shuffle.md
├── hive.partition.md
└── ...
```

文件名 = knowledge_point_id + `.md`。

## 11. Card Stable ID 规则

- card id = `card.` + knowledge_point_id
- 示例：knowledge_point_id `spark.shuffle` → card id `card.spark.shuffle`
- 一个 knowledge_point 最多对应一张 card
- knowledge_point name 改变 → card id 不变
- knowledge_point stable id 不变 → card 继续绑定原知识点

## 12. Knowledge Card Front Matter

```yaml
---
knowledge_point_id: spark.shuffle
title: Shuffle
is_active: true
---
```

| 字段 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `knowledge_point_id` | ✅ | — | 对应知识点 ID |
| `title` | ✅ | — | 卡片标题 |
| `is_active` | ❌ | true | 是否启用 |

不包含 `id`、`revision`、`source_hash`、`imported_at`（由 importer/DB 管理）。

## 13. Knowledge Card Markdown 正文规则

正文从 `## 一句话定义` 开始，**不写 `#` 一级标题**（title 由 Front Matter 提供）。

固定 section：

```
## 一句话定义
## 核心原理
## 面试高频点
## 常见易错点
```

允许：普通段落、列表、行内代码、fenced code block、Markdown table、加粗/斜体。

禁止：图片、HTML、正文一级标题（#）、复杂嵌入内容。

外链可以使用，但卡片核心知识不应依赖外链才能理解。

正文目标：3-5 分钟快速复习。

## 14. Revision / Source Hash 规则

- source_hash 使用 SHA-256 对规范化后的 `title + Markdown body` 计算
- title 变化 → source_hash 变化 → revision + 1
- 正文变化 → source_hash 变化 → revision + 1
- 仅文件 mtime 变化，hash 不变 → 不产生 revision
- 首次导入：revision = 1
- is_active 变化 → 不产生新 revision，直接更新 knowledge_card.is_active

## 15. knowledge_point_id 绑定变更规则

- knowledge_point_id 属于稳定绑定关系，不参与正文 revision
- 同一 card 已进入历史数据后，不允许普通内容修改顺手更换 knowledge_point_id
- 未来 importer 遇到绑定变化应报错，而不是静默迁移

---

## 16. Choice 目录结构

```
content/questions/choice/
├── spark.shuffle.choice.001.yaml
├── hive.partition.choice.001.yaml
└── ...
```

每个文件一个选择题，纯 YAML 格式。

## 17. Choice Stable ID 规则

格式：`{primary_knowledge_point_id}.choice.{3位序号}`

示例：

```text
spark.shuffle.choice.001
spark.shuffle.choice.002
hive.partition.choice.001
```

规则：

- ID 全项目唯一
- 一旦进入历史 Attempt 后，不因题干、答案、标题修改而改变
- 序号固定三位数字，从 001 起步

## 18. Choice YAML Schema

```yaml
id: spark.shuffle.choice.001
question_type: choice
primary_knowledge_point_id: spark.shuffle
title: "Shuffle 触发条件"
difficulty: 2
tags:
  - spark
  - shuffle
related_knowledge_points: []
is_active: true

content: 题目正文？

options:
  - key: A
    text: 选项内容
  - key: B
    text: 选项内容
  - key: C
    text: 选项内容
  - key: D
    text: 选项内容

correct_answer: C

explanation: 答案解析。
```

### 必填字段

id, question_type, primary_knowledge_point_id, content, options, correct_answer, explanation, difficulty

### 可选字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| title | null | 题目标题 |
| tags | [] | 字符串列表，不创建 Tag 实体 |
| related_knowledge_points | [] | 知识点 stable id 列表 |
| is_active | true | 是否有效 |

### difficulty

整数 1-5，数据库 CHECK 约束。

### related_knowledge_points 规则

- 知识点 stable id 列表
- 可为空
- 不允许重复
- `primary_knowledge_point_id` 不允许再次出现在 related 中
- 导入时使用数据库默认 weight（1.0）

## 19. Choice options 格式

```yaml
options:
  - key: A
    text: 选项内容
  - key: B
    text: 选项内容
```

规则：

- key 必须唯一
- 当前使用 A/B/C/D
- 顺序按照 YAML 列表顺序
- text 非空
- 不使用 YAML Map（`A: ...`）或 Markdown（`- A. ...`）

## 20. Choice correct_answer

当前 MVP 为单选，使用单个 option key 字符串：

```yaml
correct_answer: C
```

判题规则：完全正确 → 1，错误 → 0

## 21. Choice Question / QuestionVersion 映射

**Question 表字段映射**：

| YAML 字段 | Question 字段 |
|-----------|--------------|
| id | id |
| question_type | question_type |
| primary_knowledge_point_id | primary_knowledge_point_id |
| title | title |
| difficulty | difficulty |
| tags | tags_json |
| is_active | is_active |

**QuestionVersion.payload_json** 保存完整题目内容：

```json
{
  "content": "...",
  "options": [{"key": "A", "text": "..."}],
  "correct_answer": "C",
  "explanation": "..."
}
```

### revision 规则

- 首次导入：revision = 1
- content / options / correct_answer / explanation 任一变化 → source_hash 变化 → revision + 1
- source_hash 对上述四部分规范化后的内容计算 SHA-256
- difficulty / tags / is_active / title 变化不产生新 revision

### primary_knowledge_point_id 变更规则

已有历史 Attempt 时，importer 应报错等待确认，不静默 UPDATE。

## 22. Choice 答案泄露规则

Content YAML 中保存 correct_answer 和 explanation，但未来 GET Question API 在提交前必须剔除这两个字段。当前只记录规则，不实现 API。

---

## 23. Short Answer 目录结构

```
content/questions/short_answer/
├── spark.shuffle.qa.001.yaml
├── hive.partition.qa.001.yaml
└── ...
```

每个文件一个问答题，纯 YAML 格式。

## 24. Short Answer Stable ID 规则

格式：`{primary_knowledge_point_id}.qa.{3位序号}`

示例：

```text
spark.shuffle.qa.001
spark.shuffle.qa.002
hive.partition.qa.001
```

规则：

- `.qa.` 是 stable ID 中的短类型标识，不是 question_type
- ID 全项目唯一
- 一旦进入历史 Attempt 后，不因题干修改而变化
- 序号固定三位数字，从 001 起步

## 25. Short Answer YAML Schema

```yaml
id: spark.shuffle.qa.001
question_type: short_answer
primary_knowledge_point_id: spark.shuffle
title: "Shuffle 本质与性能瓶颈"
difficulty: 3
tags:
  - spark
  - shuffle
related_knowledge_points: []
is_active: true

content: 题目正文？

reference_answer: |
  参考答案内容。
  支持多段、列表、行内代码。

explanation: |
  解析内容。
```

### 必填字段

id, question_type, primary_knowledge_point_id, content, reference_answer, explanation, difficulty

### 可选字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| title | null | 题目标题 |
| tags | [] | 字符串列表 |
| related_knowledge_points | [] | 知识点 stable id 列表 |
| is_active | true | 是否有效 |

### difficulty

整数 1-5，数据库 CHECK 约束。

### related_knowledge_points 规则

- 知识点 stable id 列表
- 可为空
- 不允许重复
- `primary_knowledge_point_id` 不允许出现在 related 中
- 只能引用 `content/knowledge/` 中已存在的 stable ID
- 导入时使用数据库默认 weight（1.0）

## 26. Short Answer reference_answer 格式

使用 YAML block scalar（`|`），允许 Markdown 风格：

```yaml
reference_answer: |
  第一段内容。

  - 列表项 1
  - 列表项 2

  `代码示例`
```

- 单个字符串字段，不是结构化对象
- 允许多段、列表、行内代码
- 面试问答通常需要多段内容，block scalar 可读性最佳

## 27. Short Answer Question / QuestionVersion 映射

**Question 表字段映射**：

| YAML 字段 | Question 字段 |
|-----------|--------------|
| id | id |
| question_type | question_type |
| primary_knowledge_point_id | primary_knowledge_point_id |
| title | title |
| difficulty | difficulty |
| tags | tags_json |
| is_active | is_active |

**QuestionVersion.payload_json** 保存完整题目内容：

```json
{
  "content": "...",
  "reference_answer": "...",
  "explanation": "..."
}
```

### revision 规则

- 首次导入：revision = 1
- content / reference_answer / explanation 任一变化 → source_hash 变化 → revision + 1
- source_hash 对上述三部分规范化后的内容计算 SHA-256
- title / difficulty / tags / is_active 变化不产生新 revision

### primary_knowledge_point_id 变更规则

已有历史 Attempt 时，importer 应报错等待确认，不静默 UPDATE。

## 28. Short Answer 答案泄露与自评规则

### 答案泄露

- 提交前 GET Question：不得返回 reference_answer 和 explanation
- 提交后：返回 user_answer + reference_answer + explanation + mastery_options
- 当前只记录规则，不实现 API

### 自评掌握状态

Content YAML 不包含自评状态。用户提交后选择：

| 用户选择 | mastery_state | review_stage | next_review_date |
|---------|---------------|--------------|------------------|
| 不会 | unmastered | 0 | 1天后 |
| 模糊 | vague | 1 | 2天后 |
| 基本掌握 | familiar | 3 | 7天后 |
| 熟练掌握 | mastered | 4 | 14天后 |

Short Answer 没有 final_score / max_score / score_ratio / AI 评分。