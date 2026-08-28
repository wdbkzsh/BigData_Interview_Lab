# BigData Interview Lab — DATABASE v0.2

> 状态：数据库设计稿
> 数据库：SQLite
> 适用阶段：MVP
> 前置文档：PRD.md、ARCHITECTURE.md

---

# 1. 数据库设计目标

数据库同时处理两类数据。

## 1.1 内容数据

包括：

- 知识点
- 知识卡片
- 选择题
- 问答题及参考答案
- SQL 手写题及评分标准
- 题目与知识点关系

源头：

```text
content/
```

SQLite 保存运行副本。

## 1.2 用户运行数据

包括：

- 每一次答题 Attempt
- 问答题用户自评掌握状态
- SQL AI 原始判题记录
- SQL 最终采用的判题结果
- ReviewState
- 下次复习日期
- DailyTask
- Wrong Book 关注 / 忽略状态
- 知识卡片阅读记录
- 用户设置

这些运行数据以 SQLite 为事实来源。

# 2. 核心设计原则

## 2.1 内容 ID 使用稳定字符串

题目和知识点不使用数据库自增 ID 作为业务身份。

例如：

```text
spark
spark.shuffle
spark.shuffle.stage

spark.shuffle.choice.001
spark.shuffle.qa.001

sql.window.row_number.001
```

这样即使：

```text
删除数据库
→ 重新导入 content
```

题目的业务身份仍然不变。

---

## 2.2 运行记录使用数据库 ID

例如：

```text
Attempt
AI Assessment
Daily Task
```

使用 SQLite 自增整数主键。

---

## 2.3 历史数据不可覆盖

用户重新做一道题：

```text
第一次 Attempt
第二次 Attempt
第三次 Attempt
```

必须全部保留。

不能：

```text
UPDATE 第一次答案
```

替换历史。

---

## 2.4 当前状态和历史事件分离

```text
Attempt
=
历史

ReviewState
=
当前状态
```

同一道题：

```text
Attempt       1:N
ReviewState   1:1
```

---

## 2.5 评估方式按题型分离

```text
选择题
→ 系统自动判分

问答题
→ 用户提交答案
→ 查看参考答案
→ self_assessed_mastery_state

SQL题
→ AI Raw Assessment
→ 默认接受 / 用户调整 / 重判
→ Final Result
```

只有 SQL 题保存 AI Assessment。

问答题不保存 AI 分数，也不需要 scoring rubric。

## 2.6 不保存可以实时计算的统计值

例如：

```text
今日做题数
本周做题数
知识点掌握率
总正确率
```

MVP 不创建统计宽表。

统一从：

```text
Attempt
ReviewState
Question
KnowledgePoint
```

实时计算。

---

# 3. 核心实体关系

```text
KnowledgePoint
      │
      ├────────────── KnowledgeCard
      │
      └────────────── Question
                           │
                           ├── QuestionVersion
                           │
                           ├── Attempt
                           │      │
                           │      ├── 短答：self_assessed_mastery_state
                           │      ├── SQL：AIAssessment
                           │      └── SQL：AttemptKnowledgeResult
                           │
                           ├── ReviewState
                           └── QuestionPreference

DailyTask
   └── DailyTaskItem
            └── Question + QuestionVersion
```

知识点掌握率不单独存表，由 ReviewState 动态计算。

# 4. 表清单

MVP 使用以下 15 张表：

| 表 | 作用 |
|---|---|
| knowledge_point | 多级知识点树 |
| knowledge_card | 知识卡片当前状态 |
| knowledge_card_version | 知识卡片版本 |
| question | 题目稳定身份 |
| question_version | 题目具体版本 |
| question_related_knowledge_point | 题目关联知识点 |
| attempt | 每一次真实作答 |
| ai_assessment | SQL 题 AI 原始判题记录 |
| attempt_knowledge_result | SQL AI 返回的知识点分析 |
| review_state | 单题当前复习状态 |
| question_preference | 错题本手动关注 / 忽略 |
| daily_task | 每日任务快照 |
| daily_task_item | 每日任务题目 |
| knowledge_card_progress | 知识卡片阅读状态 |
| app_setting | 单用户设置 |

不创建：

```text
wrong_book
statistics
knowledge_mastery
user
role
permission
short_answer_assessment
```

问答题自评直接保存在 Attempt 中，不额外拆表。

# 5. knowledge_point

知识点树。

```text
Spark
├── RDD
├── Shuffle
│   ├── Shuffle Write
│   └── Shuffle Read
└── Spark SQL
```

字段：

| 字段          | 类型                | 说明       |
| ----------- | ----------------- | -------- |
| id          | TEXT PK           | 稳定知识点 ID |
| parent_id   | TEXT NULL FK      | 父知识点     |
| name        | TEXT NOT NULL     | 名称       |
| level       | INTEGER NOT NULL  | 层级       |
| description | TEXT NULL         | 简介       |
| sort_order  | INTEGER DEFAULT 0 | 排序       |
| is_active   | BOOLEAN DEFAULT 1 | 是否有效     |
| created_at  | DATETIME          | 创建时间     |
| updated_at  | DATETIME          | 更新时间     |

约束：

```text
parent_id → knowledge_point.id
```

顶级知识点：

```text
parent_id = NULL
```

删除原则：

**不物理删除已有知识点。**

内容移除后：

```text
is_active = 0
```

防止历史 Attempt 的知识关系失效。

---

# 6. knowledge_card

每个知识点最多对应一张当前知识卡片。

字段：

| 字段                 | 类型             | 说明      |
| ------------------ | -------------- | ------- |
| id                 | TEXT PK        | 卡片稳定 ID |
| knowledge_point_id | TEXT UNIQUE FK | 对应知识点   |
| current_revision   | INTEGER        | 当前版本    |
| is_active          | BOOLEAN        | 是否启用    |
| created_at         | DATETIME       | 创建时间    |
| updated_at         | DATETIME       | 更新时间    |

示例：

```text
card.spark.shuffle
```

---

# 7. knowledge_card_version

保存知识卡片版本。

字段：

| 字段           | 类型            | 说明           |
| ------------ | ------------- | ------------ |
| card_id      | TEXT FK       | 卡片 ID        |
| revision     | INTEGER       | 版本号          |
| content_json | TEXT NOT NULL | 卡片完整结构       |
| source_path  | TEXT          | content 文件路径 |
| source_hash  | TEXT          | 文件内容 hash    |
| imported_at  | DATETIME      | 导入时间         |

联合主键：

```text
(card_id, revision)
```

`content_json` 包含：

```text
one_line_definition
core_principle
interview_highlights
common_mistakes
```

不把这些拆成大量数据库列。

原因：

知识卡片的主要用途是：

```text
整体读取
→ 页面展示
```

不需要针对卡片内部字段做 SQL 查询。

---

# 8. question

Question 表只保存**题目的稳定身份和可查询元数据**。

字段：

| 字段                         | 类型                | 说明      |
| -------------------------- | ----------------- | ------- |
| id                         | TEXT PK           | 稳定题目 ID |
| question_type              | TEXT              | 题型      |
| primary_knowledge_point_id | TEXT FK           | 主知识点    |
| title                      | TEXT NULL         | 题目标题    |
| difficulty                 | INTEGER           | 1-5     |
| tags_json                  | TEXT              | 标签      |
| current_revision           | INTEGER           | 当前版本    |
| is_active                  | BOOLEAN DEFAULT 1 | 是否有效    |
| created_at                 | DATETIME          | 创建时间    |
| updated_at                 | DATETIME          | 更新时间    |

题型：

```text
single_choice
multiple_choice
short_answer
sql
```

虽然 MVP 可以先只实现单选，但数据库提前允许多选，不增加明显复杂度。

难度约束：

```text
1 <= difficulty <= 5
```

---

# 9. question_version

题目具体内容采用版本表保存。

字段：

| 字段           | 类型            | 说明         |
| ------------ | ------------- | ---------- |
| question_id  | TEXT FK       | 题目 ID      |
| revision     | INTEGER       | 版本         |
| payload_json | TEXT NOT NULL | 当前版本完整题目结构 |
| source_path  | TEXT          | 内容文件位置     |
| source_hash  | TEXT          | 文件 hash    |
| imported_at  | DATETIME      | 导入时间       |

联合主键：

```text
(question_id, revision)
```

---

## 9.1 为什么 Question 和 QuestionVersion 分开

假设：

```text
2026-08-28
SQL题：
查询每个部门工资最高的员工
```

用户做了一次。

之后发现题目描述不清楚，于是修改。

如果直接：

```text
UPDATE question
```

历史 Attempt 会变成：

> 用户当时到底做的是哪个版本？

无法回答。

因此：

```text
Question
= 稳定身份

QuestionVersion
= 具体内容
```

Attempt 必须记录：

```text
question_id
question_revision
```

---

# 10. question_version payload

不同题型结构不同，因此不设计大量 NULL 字段。

统一放：

```text
payload_json
```

---

## 10.1 选择题

概念结构：

```json
{
  "content": "...",
  "options": [],
  "correct_answer": [],
  "explanation": "..."
}
```

---

## 10.2 问答题

```json
{
  "content": "...",
  "reference_answer": "...",
  "explanation": "..."
}
```

问答题 MVP 不保存：

```text
scoring_rubric
AI评分点
total_score
```

关联知识点继续由 `question.primary_knowledge_point_id` 和 `question_related_knowledge_point` 管理。

## 10.3 SQL 题

```json
{
  "content": "...",
  "table_schema": "...",
  "field_description": "...",
  "business_requirement": "...",
  "expected_sql": "...",
  "scoring_criteria": {
    "total_score": 10,
    "criteria": []
  }
}
```

判题规则仍然是：

```text
business_requirement
+
scoring_criteria
```

作为主要依据。

`expected_sql` 只是参考。

---

# 11. question_related_knowledge_point

一个问题可能涉及多个知识点。

例如：

```text
SQL综合题

主知识点：
SQL > 窗口函数

同时涉及：
SQL > GROUP BY
SQL > JOIN
```

字段：

| 字段                 | 类型             | 说明      |
| ------------------ | -------------- | ------- |
| question_id        | TEXT FK        | 题目      |
| knowledge_point_id | TEXT FK        | 关联知识点   |
| weight             | REAL DEFAULT 1 | 后续掌握率权重 |

联合主键：

```text
(question_id, knowledge_point_id)
```

主知识点仍然保存在：

```text
question.primary_knowledge_point_id
```

这里仅保存额外知识点。

---

# 12. attempt

Attempt 是系统最重要的历史表。

> 用户每提交一次答案，就立即产生一条 Attempt。

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | Attempt ID |
| question_id | TEXT FK | 题目 |
| question_revision | INTEGER | 作答时题目版本 |
| daily_task_item_id | INTEGER NULL FK | 来源每日任务 |
| attempt_type | TEXT | new / review / practice |
| user_answer | TEXT | 用户原始答案 |
| status | TEXT | 当前状态 |
| self_assessed_mastery_state | TEXT NULL | 问答题用户自评结果 |
| final_score | REAL NULL | 选择题 / SQL 最终分数 |
| max_score | REAL NULL | 选择题 / SQL 满分 |
| final_result_json | TEXT NULL | SQL 最终判题结果或其他完成结果 |
| final_score_source | TEXT NULL | system / ai_confirmed / user_adjusted |
| client_request_id | TEXT UNIQUE NULL | 幂等请求 ID |
| created_at | DATETIME | 提交时间 |
| finalized_at | DATETIME NULL | Attempt 完成时间 |
| review_applied_at | DATETIME NULL | ReviewState 是否已应用 |

## 12.1 attempt_type

```text
new
review
practice
```

## 12.2 status

**选择题**

```text
completed
```

**问答题**

```text
awaiting_self_assessment
completed
```

**SQL题**

```text
grading
awaiting_confirmation
completed
grading_failed
disputed
```

## 12.3 final_score_source

只适用于选择题 / SQL：

```text
system
ai_confirmed
user_adjusted
```

问答题：

```text
final_score = NULL
max_score = NULL
final_score_source = NULL
```

最终复习输入来自：

```text
self_assessed_mastery_state
```

# 13. 为什么所有题型都先创建 Attempt

用户点击提交时应先保存原始作答。

**选择题**

```text
提交
→ INSERT Attempt
→ 系统判分
```

**问答题**

```text
提交
→ INSERT Attempt
→ 返回参考答案
→ 等待用户自评
```

**SQL题**

```text
提交
→ INSERT Attempt
→ 调用 AI
```

这样无论用户关闭页面还是 AI 失败，用户原始答案都不会丢失。

# 14. ai_assessment

`ai_assessment` **仅用于 SQL 手写题**。

一个 SQL Attempt 可以存在多个 AI Assessment，用于：

- 首次判题
- 超时后的重试
- 用户主动重新判题

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | AI Assessment ID |
| attempt_id | INTEGER FK | SQL Attempt |
| provider | TEXT NULL | 模型供应商 |
| model | TEXT NULL | 模型名称 |
| prompt_version | TEXT | SQL Prompt 版本 |
| status | TEXT | success / failed / invalid_response / timeout |
| raw_score | REAL NULL | AI 原始分 |
| max_score | REAL NULL | 满分 |
| result_json | TEXT NULL | 结构化判题结果 |
| error_message | TEXT NULL | 失败原因 |
| input_tokens | INTEGER NULL | 输入 Token |
| output_tokens | INTEGER NULL | 输出 Token |
| latency_ms | INTEGER NULL | 耗时 |
| created_at | DATETIME | 请求时间 |

问答题不会写入本表。

# 15. SQL AI Assessment 和 Attempt 的关系

例如：

```text
SQL Attempt #100
用户 SQL
     │
     ├── AI Assessment #201 → timeout
     └── AI Assessment #202 → success，7/10

用户正常下一题
→ final_score = 7
→ final_score_source = ai_confirmed

或用户调整
→ final_score = 9
→ final_score_source = user_adjusted
```

`ai_assessment.raw_score` 永远表示 AI 原始结果。

`attempt.final_score` 表示最终采用的 SQL 判题结果。

问答题没有这层关系。

# 16. attempt_knowledge_result

本表仅保存 **SQL AI 判题**产生的知识点分析，例如：

```text
mastered
weak
missing
```

字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | ID |
| attempt_id | INTEGER FK | SQL Attempt |
| knowledge_point_id | TEXT FK | 知识点 |
| evidence_type | TEXT | mastered / weak / missing |
| earned_score | REAL NULL | 对应知识点得分 |
| max_score | REAL NULL | 对应知识点满分 |
| detail_json | TEXT NULL | 依据和反馈 |

问答题不生成 `attempt_knowledge_result`。

MVP 的 Knowledge Point Mastery Score 仍以 ReviewState 为主要依据，本表只用于 SQL 薄弱点展示，避免重复加权。

# 17. review_state

ReviewState 表示：

> 用户当前对某一道题的掌握情况。

每道题最多一条。

字段：

| 字段                    | 类型                | 说明           |
| --------------------- | ----------------- | ------------ |
| question_id           | TEXT PK FK        | 题目           |
| mastery_state         | TEXT              | 当前掌握状态       |
| last_attempt_id       | INTEGER NULL FK   | 最近有效 Attempt |
| last_review_at        | DATETIME NULL     | 最近复习         |
| next_review_date      | DATE NULL         | 下次复习日期       |
| review_count          | INTEGER DEFAULT 0 | 已复习次数        |
| consecutive_successes | INTEGER DEFAULT 0 | 连续成功次数       |
| policy_version        | TEXT              | 使用的复习算法版本    |
| algorithm_state_json  | TEXT NULL         | 算法内部状态       |
| updated_at            | DATETIME          | 更新时间         |

---

## 17.1 mastery_state

只能是：

```text
unmastered
vague
familiar
mastered
```

对应：

```text
不会
模糊
基本掌握
熟练掌握
```

---

## 17.2 algorithm_state_json

现在不提前写死：

```text
ease_factor
interval
repetition
```

等具体算法确定后，可以放入：

```text
algorithm_state_json
```

例如未来：

```json
{
  "interval": 7,
  "ease_factor": 2.4,
  "repetitions": 3
}
```

这样以后更换复习算法不会立刻要求数据库加很多字段。

---

# 18. ReviewState 更新规则

ReviewState 的更新入口按题型区分。

### 选择题

```text
Attempt completed
+
系统判分结果
```

### 问答题

必须满足：

```text
Attempt.status = awaiting_self_assessment
+
self_assessed_mastery_state 已选择
```

事务：

```text
BEGIN

UPDATE Attempt
SET self_assessed_mastery_state = ?
   ,status = completed
   ,finalized_at = now()

UPSERT ReviewState
    使用用户自评状态和 review policy

SET review_applied_at = now()

UPDATE DailyTaskItem

COMMIT
```

### SQL题

必须已有最终采用的 AI 判题结果。

所有题型都要求：

```text
review_applied_at IS NULL
```

防止重复更新 ReviewState。

# 19. question_preference

Wrong Book 本身不是表。

但用户需要：

```text
手动关注
手动忽略
```

所以单独保存用户偏好。

字段：

| 字段              | 类型         | 说明    |
| --------------- | ---------- | ----- |
| question_id     | TEXT PK FK | 题目    |
| wrong_book_mode | TEXT       | 错题本模式 |
| updated_at      | DATETIME   | 更新时间  |

模式：

```text
auto
follow
ignore
```

默认：

```text
auto
```

---

# 20. Wrong Book 查询规则

概念上：

```text
IF wrong_book_mode = follow
    显示

ELSE IF wrong_book_mode = ignore
    不显示

ELSE
    根据 ReviewState 自动判断
```

MVP 自动显示：

```text
unmastered
vague
```

手动忽略：

**只影响 Wrong Book。**

不修改：

```text
ReviewState
next_review_date
每日复习任务
```

---

# 21. daily_task

每日任务必须保存快照。

字段：

| 字段                  | 类型            | 说明      |
| ------------------- | ------------- | ------- |
| id                  | INTEGER PK    | 每日任务 ID |
| task_date           | DATE UNIQUE   | 日期      |
| status              | TEXT          | 状态      |
| new_question_target | INTEGER       | 新题目标数   |
| generated_at        | DATETIME      | 生成时间    |
| completed_at        | DATETIME NULL | 完成时间    |

状态：

```text
not_started
in_progress
completed
skipped
```

---

# 22. daily_task_item

保存当天实际安排的题。

字段：

| 字段                   | 类型              | 说明           |
| -------------------- | --------------- | ------------ |
| id                   | INTEGER PK      | Item ID      |
| daily_task_id        | INTEGER FK      | 每日任务         |
| question_id          | TEXT FK         | 题目           |
| question_revision    | INTEGER         | 当天使用版本       |
| item_type            | TEXT            | 题目来源         |
| sort_order           | INTEGER         | 顺序           |
| status               | TEXT            | 完成状态         |
| due_date_snapshot    | DATE NULL       | 复习题原到期日期     |
| completed_attempt_id | INTEGER NULL FK | 完成它的 Attempt |
| created_at           | DATETIME        | 创建时间         |

`item_type`：

```text
review
new
```

约束：

同一天不能重复加入同一道题：

```text
UNIQUE(daily_task_id, question_id)
```

---

# 23. 为什么 DailyTaskItem 保存 question_revision

假设今天早晨生成：

```text
Question Revision 3
```

下午你修改题库，变成：

```text
Revision 4
```

今天任务不能突然变题。

因此：

```text
DailyTaskItem
```

保存生成任务时对应的版本。

---

# 24. knowledge_card_progress

用于记录知识卡片使用情况。

字段：

| 字段              | 类型                | 说明   |
| --------------- | ----------------- | ---- |
| card_id         | TEXT PK FK        | 卡片   |
| first_viewed_at | DATETIME NULL     | 首次阅读 |
| last_viewed_at  | DATETIME NULL     | 最近阅读 |
| view_count      | INTEGER DEFAULT 0 | 阅读次数 |
| status          | TEXT              | 阅读状态 |

状态：

```text
unread
read
```

MVP 不做：

```text
知识卡片完成度 37%
阅读时长
滚动进度
```

避免无意义复杂度。

---

# 25. app_setting

单用户系统无需 User 表。

用户配置统一保存在：

```text
app_setting
```

字段：

| 字段         | 类型       | 说明   |
| ---------- | -------- | ---- |
| key        | TEXT PK  | 设置项  |
| value_json | TEXT     | 设置值  |
| updated_at | DATETIME | 更新时间 |

例如：

```text
daily.new_question_count

daily.choice_count
daily.short_answer_count
daily.sql_count

app.timezone
```

---

# 26. 不创建 User 表

MVP 是：

```text
单用户
本地个人使用
```

因此不创建：

```text
user
account
role
permission
login_session
```

以后如果进入：

```text
v2 多用户
```

再统一引入：

```text
user_id
```

当前不要提前污染全部表。

---

# 27. Knowledge Point Mastery Score

不创建 `knowledge_mastery` 表。

掌握率由 MasteryService 根据：

```text
ReviewState
Question
QuestionRelatedKnowledgePoint
```

动态计算。

其中：

- 选择题 ReviewState 来自系统判分。
- 问答题 ReviewState 来自用户自评。
- SQL ReviewState 来自最终 AI 判题结果。

`attempt_knowledge_result` 只用于 SQL 薄弱点展示，MVP 不重复参与掌握率加减。

具体权重由 REVIEW_ALGORITHM.md 定义。

# 28. Statistics

MVP 不创建统计宽表。

实时计算：

**选择题**

```text
题量
正确率
```

**问答题**

```text
题量
self_assessed_mastery_state 分布
```

**SQL题**

```text
题量
final_score / max_score
```

以及：

```text
今日 / 本周 / 累计学习量
ReviewState 分布
知识点掌握率
待复习数量
```

问答题不计算平均分或 AI 正确率。

# 29. Content Import

内容文件导入数据库时遵循：

```text
读取 content
↓
Schema Validation
↓
业务校验
↓
计算 source_hash
↓
判断内容是否改变
```

如果没有改变：

```text
不生成新版本
```

如果改变：

```text
revision + 1
↓
INSERT QuestionVersion
↓
UPDATE Question.current_revision
```

---

# 30. 内容删除规则

如果 Git 中删除：

```text
spark.shuffle.choice.001
```

已经存在历史 Attempt。

数据库不能：

```text
DELETE question
```

必须：

```text
question.is_active = 0
```

以后：

* 不再进入新题
* 不再主动推荐
* 历史 Attempt 仍然可查看

---

# 31. 内容版本和 Git 的关系

每个版本记录：

```text
source_path
source_hash
```

以后如果需要，还可以增加：

```text
git_commit
```

MVP 暂时不是必须。

---

# 32. 主键策略

## 内容实体

使用稳定字符串：

```text
knowledge_point.id
knowledge_card.id
question.id
```

---

## 运行实体

使用：

```text
INTEGER PRIMARY KEY
```

例如：

```text
attempt.id
ai_assessment.id
daily_task.id
```

SQLite 对此支持最好。

---

# 33. 时间字段

时间字段统一分两类。

## DATETIME

例如：

```text
created_at
updated_at
finalized_at
```

数据库统一保存 UTC 时间。

---

## DATE

例如：

```text
task_date
next_review_date
```

是根据：

```text
APP_TIMEZONE
```

计算出的业务日期。

不能直接依赖电脑当前时区。

---

# 34. 外键

SQLite 必须开启：

```text
PRAGMA foreign_keys = ON
```

所有业务外键都需要真实约束。

禁止仅在 Python 层“默认关联存在”。

---

# 35. SQLite WAL

建议启用：

```text
PRAGMA journal_mode = WAL
```

原因：

虽然是单用户应用，但 FastAPI 可能存在：

```text
页面查询
SQL AI判题写入
问答题自评
Attempt提交
统计查询
```

同时发生。

WAL 可以降低：

```text
database is locked
```

概率。

---

# 36. 推荐数据库访问方式

后端推荐：

```text
SQLAlchemy 2.x
```

负责：

* Model
* Session
* Transaction
* Query

数据库结构变化建议使用：

```text
Alembic
```

管理 migration。

不要：

```text
手工打开 SQLite
ALTER TABLE
```

作为正式开发流程。

---

# 37. 索引设计

MVP 至少建立：

### Attempt

```text
INDEX(question_id)
INDEX(created_at)
INDEX(status)
INDEX(finalized_at)
```

---

### ReviewState

```text
INDEX(next_review_date)
INDEX(mastery_state)
```

---

### Question

```text
INDEX(primary_knowledge_point_id)
INDEX(question_type)
INDEX(is_active)
```

---

### DailyTask

```text
UNIQUE(task_date)
```

---

### DailyTaskItem

```text
INDEX(daily_task_id)
INDEX(question_id)
```

---

### AttemptKnowledgeResult

```text
INDEX(knowledge_point_id)
INDEX(attempt_id)
```

---

# 38. 防止重复提交

前端提交答案时生成：

```text
client_request_id
```

例如 UUID。

Attempt：

```text
UNIQUE(client_request_id)
```

如果：

```text
用户双击提交
网络重试
```

FastAPI 收到相同 ID：

返回已有 Attempt。

不能重复插入。

---

# 39. 选择题事务

```text
BEGIN

INSERT Attempt
↓
系统判分
↓
Attempt.status = completed
↓
UPSERT ReviewState
↓
SET review_applied_at
↓
UPDATE DailyTaskItem

COMMIT
```

# 40. 问答题 / SQL 事务

## 40.1 问答题

第一次提交：

```text
BEGIN

INSERT Attempt
status = awaiting_self_assessment

COMMIT
```

随后后端返回该 QuestionVersion 的：

```text
reference_answer
explanation
```

用户选择掌握状态后：

```text
BEGIN

UPDATE Attempt
SET self_assessed_mastery_state = ?
   ,status = completed
   ,finalized_at = now()

UPSERT ReviewState

SET review_applied_at

UPDATE DailyTaskItem

COMMIT
```

问答题整个流程不调用 AI。

## 40.2 SQL题

第一次提交：

```text
INSERT Attempt
status = grading
```

AI 成功：

```text
INSERT AIAssessment
UPDATE Attempt
status = awaiting_confirmation
```

用户点击“下一题”默认接受：

```text
BEGIN

UPDATE Attempt
SET final_score = AI raw_score
   ,final_result_json = AI result
   ,final_score_source = ai_confirmed
   ,status = completed

INSERT AttemptKnowledgeResult
UPSERT ReviewState
UPDATE DailyTaskItem
SET review_applied_at

COMMIT
```

如果用户调整，则 `final_score_source = user_adjusted`。

# 41. SQL AI失败

仅适用于 SQL题。

AI 超时或结果不可解析：

```text
Attempt.status = grading_failed
```

同时记录失败的 `AIAssessment`。

此时：

```text
ReviewState 不更新
DailyTaskItem 不完成
用户 SQL 不删除
```

重新判题：

```text
同一 Attempt
+
新的 AIAssessment
```

不创建第二个 Attempt。

# 42. SQL AI有争议

仅适用于 SQL题。

如果用户认为 AI 判题错误：

- 可直接调整最终结果；
- 可重新判题；
- 也可以暂时标记 `disputed`。

`disputed` 状态不更新 ReviewState。

问答题不存在 AI 争议流程，因为掌握状态由用户自己决定。

# 43. Wrong Book 不建立数据库 VIEW

虽然产品上叫“视图”，MVP 暂时不创建 SQLite：

```text
CREATE VIEW wrong_book
```

统一由：

```text
WrongBookService
```

查询：

```text
Question
+
ReviewState
+
QuestionPreference
```

原因：

业务规则以后可能调整。

保持 Service 层更灵活。

---

# 44. 数据备份

SQLite 数据全部集中：

```text
data/app.db
```

Content 已经由 Git 管理。

因此真正需要备份的是：

```text
app.db
```

MVP 可以先手动复制。

后续增加：

```text
导出 / 自动备份
```

---

# 45. Git 管理规则

提交：

```text
content/
docs/
backend/
frontend/
migrations/
```

不提交：

```text
data/app.db
.env
*.db
*.sqlite
```

---

# 46. 数据库关系总图

```text
knowledge_point
      │
      ├── 1:1 knowledge_card
      │          └── 1:N knowledge_card_version
      │
      └── 1:N question
                 │
                 ├── 1:N question_version
                 ├── N:M related knowledge_point
                 ├── 1:N attempt
                 │       │
                 │       ├── 问答题：self_assessed_mastery_state
                 │       ├── SQL：1:N ai_assessment
                 │       └── SQL：1:N attempt_knowledge_result
                 │
                 ├── 1:1 review_state
                 └── 1:1 question_preference

daily_task
     └── 1:N daily_task_item
                    └── question + revision
```

# 47. 明确不存储的数据

以下内容不作为数据库事实字段保存：

```text
Spark 掌握率 68%
Hive 掌握率 72%
今日正确率
本周正确率
错题数量
今日待复习数量
连续学习天数
```

全部属于：

```text
查询结果 / 派生指标
```

避免缓存值和真实数据不一致。

---

# 48. REVIEW_ALGORITHM.md 负责的规则

DATABASE.md 只提供存储结构。

REVIEW_ALGORITHM.md 决定：

```text
选择题正确 / 错误如何推进复习阶段
问答题四档自评如何映射 review_stage 和 next_review_date
SQL 得分如何映射 Performance
连续成功如何拉长间隔
知识点掌握率如何计算
父知识点如何汇总
```

问答题不再需要“高分 / 低分阈值”。

# 49. 核心数据流最终确认

## 选择题

```text
QuestionVersion
      ↓
Attempt
      ↓
系统判分
      ↓
ReviewState
```

## 问答题

```text
QuestionVersion
      ↓
Attempt
status = awaiting_self_assessment
      ↓
展示 reference_answer
      ↓
用户选择 mastery_state
      ↓
Attempt completed
      ↓
ReviewState
```

## SQL

```text
QuestionVersion
      ↓
Attempt
      ↓
LLM
business_requirement + scoring_criteria
      ↓
AIAssessment
      ↓
默认接受 / 用户调整 / 重判
      ↓
Final Result
      ↓
AttemptKnowledgeResult
      ↓
ReviewState
```

## 每日学习

```text
ReviewState 到期
+
未做 Question
↓
DailyTask
↓
DailyTaskItem
↓
Attempt
```

# 50. DATABASE v0.2 最终核心模型

统一数据主线：

```text
Content
   ↓
Question + QuestionVersion
   ↓
Attempt
   ↓
题型评估
   ├── Choice：System Grade
   ├── Short Answer：Self Assessment
   └── SQL：AI Assessment
   ↓
ReviewState
   ↓
DailyTask
```

核心边界：

- **Attempt 保存历史真实作答。**
- **ReviewState 保存当前掌握状态。**
- **问答题的 `self_assessed_mastery_state` 保存用户当次自评。**
- **AIAssessment 只保存 SQL AI 原始判断。**
- **QuestionVersion 保证历史作答与当时题目版本一致。**

问答题不需要 AI、分数或评分点，这也是 v0.2 相较 v0.1 最重要的简化。
