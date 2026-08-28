# BigData Interview Lab — ARCHITECTURE v0.2

> 状态：架构设计稿
> 适用阶段：MVP
> 核心原则：简单、稳定、可迭代，以秋招学习效率优先，不做过度设计。

---

## 1. 架构目标

BigData Interview Lab 采用：

**Next.js 前端 + FastAPI 后端 + SQLite 数据库 + Content 内容库 + LLM Service**

整体为单用户、本地优先的模块化单体应用。

MVP 中三类题型采用不同评估方式：

```text
选择题 → 后端自动判分
问答题 → 展示参考答案 + 用户自评掌握状态
SQL题  → LLM Service AI 判题
```

因此 LLM 不是所有题型的必经依赖，而只是 SQL 判题能力。即使 LLM 暂时不可用，知识卡片、选择题、问答题、错题本和复习系统仍可以正常工作。

架构目标：

1. 学习内容由 Git 管理并可持续维护。
2. Attempt、ReviewState 等运行数据长期保存在 SQLite。
3. 问答题保持简单高效，不依赖 AI。
4. SQL AI 模型可以替换，不影响核心业务代码。
5. 前端只负责交互，业务规则统一由 FastAPI 管理。
6. MVP 快速落地，同时保留后续扩展空间。

# 2. 总体架构

```text
                     Browser
                        │
                        ▼
               ┌────────────────┐
               │    Next.js     │
               │   TypeScript   │
               └───────┬────────┘
                       │ HTTP / JSON
                       ▼
               ┌────────────────┐
               │    FastAPI     │
               │     Python     │
               └───────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
 │   SQLite    │ │   Content   │ │ LLM Service  │
 │ 运行数据     │ │   Import    │ │ 仅 SQL 判题   │
 └─────────────┘ └──────┬──────┘ └──────┬───────┘
                         │               │
                         ▼               ▼
                    content/        LLM Provider
                   Git 内容源        具体模型 API
```

调用方向：

```text
Next.js
   ↓
FastAPI Router
   ↓
Service
   ↓
Repository / LLM Service
   ↓
SQLite / LLM API
```

三类题型：

```text
ChoiceQuestionService
→ 系统判分
→ ReviewService

ShortAnswerService
→ 保存答案
→ 返回参考答案
→ 用户自评
→ ReviewService

SQLGradingService
→ LLMService
→ LLMProvider
→ AI判题
→ ReviewService
```

前端永远不能直接调用 LLM API。

# 3. 架构原则

## 3.1 前端不保存业务真相

前端负责：

* 页面展示
* 表单输入
* 答题交互
* Loading
* 错误提示
* API 调用
* 图表展示

前端不负责：

* 判题
* ReviewState 计算
* 复习日期计算
* 每日任务生成
* 知识点掌握率计算
* 错题本判断
* AI Prompt 构造
* API Key

所有核心规则统一放后端。

---

## 3.2 FastAPI 是唯一业务入口

FastAPI 负责：

```text
题目
知识卡片
每日任务
Attempt
选择题自动判分
问答题参考答案返回与自评提交
SQL AI判题
ReviewState
错题本
复习调度
学习统计
内容导入
系统设置
```

前端不能自己计算：

- 复习日期
- 掌握率
- 错题本归属
- SQL 最终判题状态

问答题虽然由用户自评，但自评结果必须提交给 FastAPI，由后端统一更新 ReviewState。

# 4. 前端架构

使用：

```text
Next.js
TypeScript
App Router
```

MVP 不引入 Redux。

普通页面数据：

```text
Next.js
→ Backend API
→ JSON
→ 页面展示
```

答题页面使用组件自身状态保存尚未提交的答案。

建议页面结构：

```text
frontend/
└── src/
    ├── app/
    │   ├── page.tsx
    │   ├── today/
    │   ├── knowledge/
    │   ├── practice/
    │   ├── wrong-book/
    │   ├── statistics/
    │   └── settings/
    │
    ├── components/
    │   ├── question/
    │   ├── knowledge/
    │   ├── review/
    │   └── statistics/
    │
    ├── lib/
    │   ├── api/
    │   └── types/
    │
    └── styles/
```

第一阶段不创建大量 `hooks/store/providers/utils` 等空目录。

需要时再增加。

---

# 5. 后端架构

FastAPI 采用**模块化单体**。

建议目录：

```text
backend/
└── app/
    ├── main.py
    ├── api/
    │   ├── questions.py
    │   ├── attempts.py
    │   ├── reviews.py
    │   ├── daily_tasks.py
    │   ├── knowledge.py
    │   ├── statistics.py
    │   └── settings.py
    │
    ├── services/
    │   ├── question_service.py
    │   ├── attempt_service.py
    │   ├── choice_grading_service.py
    │   ├── short_answer_service.py
    │   ├── sql_grading_service.py
    │   ├── review_service.py
    │   ├── daily_task_service.py
    │   ├── mastery_service.py
    │   └── statistics_service.py
    │
    ├── repositories/
    │   ├── question_repository.py
    │   ├── attempt_repository.py
    │   └── review_repository.py
    │
    ├── llm/
    │   ├── service.py
    │   ├── provider.py
    │   ├── schemas.py
    │   └── prompts/
    │       └── sql_grading.*
    │
    ├── db/
    │   ├── session.py
    │   └── models/
    │
    ├── schemas/
    ├── review/
    │   └── policy.py
    ├── config.py
    └── exceptions.py
```

职责：

```text
Router
→ 接收 / 校验 HTTP 请求

Service
→ 业务逻辑

Repository
→ 数据访问

Review Policy
→ 复习算法

LLM Service
→ 只负责 SQL AI 判题
```

问答题不经过 `LLMService`。

# 6. SQLite 的定位

SQLite 是系统运行数据库。

主要保存：

```text
题目和知识卡片运行副本
Attempt
问答题用户自评
SQL AI评分记录
SQL最终判题结果
ReviewState
DailyTask
用户设置
学习记录
```

数据库文件：

```text
data/app.db
```

不提交 Git。

# 7. Content 与 SQLite 的关系

这里采用：

## Content 是内容源，SQLite 是运行副本

不是：

```text
页面请求
→ 每次解析 Markdown/YAML
```

而是：

```text
content/
   ↓
内容校验
   ↓
Import
   ↓
SQLite
   ↓
FastAPI运行时查询
```

原因：

### Content 文件适合

* Git 管理
* 人工审核
* AI 辅助生成
* 查看 diff
* 批量修改
* 内容备份

### SQLite 适合

* 根据知识点查题
* 随机抽题
* 今日任务生成
* JOIN Attempt
* JOIN ReviewState
* 学习统计

因此：

**内容维护与系统运行分离。**

---

# 8. Content 目录

推荐：

```text
content/
├── topics/
├── knowledge/
│   ├── spark/
│   ├── hive/
│   ├── sql/
│   └── ...
│
└── questions/
    ├── choice/
    ├── short_answer/
    └── sql/
```

第一阶段推荐：

* 知识卡片使用 Markdown
* 题目使用 YAML；SQL 题的评分标准同样保存在 YAML 中
* 知识点结构使用 YAML

原因：

Markdown 更适合长文本学习内容。

YAML 更适合题目、评分点、字段等结构化数据，同时人工阅读体验比 JSON 更好。

例如每个内容必须存在稳定 ID，而不是依赖数据库自增 ID：

```text
spark.shuffle
spark.shuffle.choice.001
spark.shuffle.qa.001
sql.window.row_number.001
```

这样即使重新导入数据库，内容身份仍然稳定。

---

# 9. 内容导入机制

提供独立导入流程：

```text
Content File
   ↓
Schema Validation
   ↓
检查 ID
   ↓
检查知识点引用
   ↓
检查 SQL scoring criteria 总分
   ↓
Import / Update
   ↓
SQLite
```

不合法内容不得进入运行数据库。

例如必须检查：

* question_id 是否重复
* knowledge_point_id 是否存在
* SQL scoring criteria 分值是否正确
* SQL scoring criteria 是否存在
* Choice 正确答案是否属于选项
* 关联知识卡片是否存在

内容导入失败必须指出具体文件和错误。

---

# 10. 内容版本问题

题目以后可能修改。

但用户历史 Attempt 不能因为题目后来变化而失去意义。

因此架构要求：

**Attempt 必须能够知道当时作答对应的题目版本。**

内容导入时生成：

```text
content_revision
```

Attempt 至少关联：

```text
question_id
question_revision
```

具体数据库如何保存版本，在 DATABASE.md 中确定。

---

# 11. LLM Service

MVP 的 LLM Service **只负责 SQL 手写题判题**。

架构：

```text
SQLGradingService
      ↓
LLMService
      ↓
LLMProvider
      ↓
具体模型 API
```

问答题：

```text
ShortAnswerService
→ 不调用 LLM
→ 返回 reference_answer
→ 接收用户 self_assessed_mastery_state
```

业务层不得直接依赖具体 OpenAI / Claude / 其他厂商 SDK。

统一能力只需要：

```text
grade_sql(...)
```

未来如果增加“问答题 AI 点评”按钮，也应作为可选能力新增，不改变 MVP 问答题主流程。

# 12. Prompt 管理

MVP 只维护 SQL 判题 Prompt：

```text
backend/app/llm/prompts/sql_grading.*
```

Prompt 必须版本化。

输入至少包含：

```text
题目
table_schema
field_description
business_requirement
scoring_criteria
expected_sql
user_sql
相关知识点
```

主要判题依据：

```text
business_requirement
+
scoring_criteria
```

`expected_sql` 只帮助理解题意和提供参考，不允许按文本相似度判定正确性。

# 13. AI 返回结构

本节仅适用于 SQL 题。

LLM 必须返回结构化业务结果，例如：

```text
score
max_score
criteria_results
mastered_points
weak_points
missing_points
errors
suggestions
reasoning_summary
```

FastAPI 使用 Schema 校验。

解析失败：

```text
第一次失败
→ 请求模型重新输出结构化结果一次
→ 再失败
→ SQL Attempt 标记 grading_failed
```

此时不得更新 ReviewState。

问答题没有 AI 返回结构。

# 14. 不同题型的评估结果

## 14.1 选择题

```text
提交
→ 系统判分
→ Attempt completed
→ ReviewState
```

## 14.2 问答题

```text
提交文字答案
→ Attempt = awaiting_self_assessment
→ 返回参考答案 / 解析
→ 用户选择：
  不会 / 模糊 / 基本掌握 / 熟练掌握
→ Attempt completed
→ ReviewState
```

问答题不产生 AI Assessment，也没有 final_score。

## 14.3 SQL题

```text
提交 SQL
→ Attempt = grading
→ AI Raw Assessment
→ 页面展示结果
→ 用户点击下一题 = 默认接受
   或调整 / 重新判题
→ Final Result
→ Attempt completed
→ ReviewState
```

只有 SQL 需要区分 AI Raw Assessment 与 Final Result。

# 15. Attempt 生命周期

## 15.1 选择题

```text
提交
→ completed
→ ReviewState 更新
```

## 15.2 问答题

```text
提交
→ awaiting_self_assessment
→ 展示参考答案
→ 用户选择掌握状态
→ completed
→ ReviewState 更新
```

如果用户提交答案后关闭页面：

```text
Attempt 仍保留为 awaiting_self_assessment
```

下次可以继续完成自评。

## 15.3 SQL题

```text
提交
→ grading
→ awaiting_confirmation
→ 用户正常下一题默认接受
   / 调整
   / 重新判题
→ completed
```

AI失败：

```text
grading_failed
```

重新判题仍使用原 Attempt。

任何题型重新作答都创建新的 Attempt，不覆盖历史。

# 16. ReviewState

ReviewState 表示：

> 用户现在对这道题掌握得怎么样。

每道题只有一个当前 ReviewState。

它负责：

```text
Question Mastery State
last_review_at
next_review_date
review_count
相关复习状态
```

复习算法集中在：

```text
review/policy.py
```

Route 和 QuestionService 不写复习天数。

以后改变遗忘曲线算法，只修改 Review Policy。

---

# 17. Wrong Book

Wrong Book 不建立独立业务实体。

它本质是：

```text
Question
+
ReviewState
+
用户关注/忽略状态
```

组成的查询视图。

例如：

```text
题目掌握状态较低
→ 自动显示

手动关注
→ 显示

手动忽略
→ 不显示
```

手动忽略只改变 Wrong Book 的展示。

**不修改 ReviewState，也不取消间隔复习。**

---

# 18. 每日任务

MVP：

```text
今日任务
=
今日到期复习题
+
固定数量未做新题
```

默认：

```text
3 选择
1 问答
1 SQL
```

新题数量以后可以设置。

## 每日任务必须生成快照

不要每次刷新首页重新随机。

当天第一次打开：

```text
没有今日任务
   ↓
DailyTaskService
   ↓
查到期 ReviewState
   +
取新题
   ↓
生成 Today Task
   ↓
保存
```

当天之后：

```text
刷新页面
→ 返回同一份任务
```

否则刷新一次题目就变化，学习体验会很差。

---

# 19. 后台任务

MVP 不使用：

```text
Cron
Celery
Redis Queue
定时任务服务
```

所谓"每天检查待复习题"采用：

```text
用户打开首页
   ↓
系统取得当前业务日期
   ↓
检查 next_review_date
```

即按需计算。

单用户平台没有必要为此运行常驻调度系统。

---

# 20. 学习统计

MVP 不创建统计宽表。

主要从：

```text
Attempt
ReviewState
Question
KnowledgePoint
```

实时计算。

统计口径：

**选择题**

```text
做题量
正确率
```

**问答题**

```text
做题量
self_assessed_mastery_state 分布
掌握状态变化
```

问答题不计算平均 AI 分。

**SQL题**

```text
做题量
最终评分平均值
掌握状态
```

以及：

```text
今日 / 本周 / 累计做题数
各知识点掌握率
待复习数量
```

# 21. 知识点掌握率

必须区分：

```text
Question Mastery State
```

单题四级：

```text
不会
模糊
基本掌握
熟练掌握
```

和：

```text
Knowledge Point Mastery Score
```

知识点百分比：

```text
Spark                  68%
└── Shuffle            42%
```

知识点掌握率由后端 `MasteryService` 计算。

具体权重算法在复习算法阶段确定。

---

# 22. API 分组

ARCHITECTURE 只定义 API 范围，不在这里确定最终 URL。

预计包含：

```text
Knowledge
Questions
Attempts
SQL Assessments
Reviews
Daily Tasks
Wrong Book
Statistics
Settings
```

具体接口、请求体、返回体统一在：

```text
docs/API.md
```

设计。

---

# 23. 配置管理

根目录提供：

```text
.env.example
```

但不提交真实：

```text
.env
```

后端配置至少包括：

```text
DATABASE_URL
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
APP_TIMEZONE
```

前端仅保存：

```text
BACKEND_API_BASE_URL
```

API Key 永远不能出现在：

```text
frontend/
浏览器代码
Git
README 示例真实值
```

---

# 24. 时间处理

数据库时间统一使用标准时间保存。

每日任务和复习日期根据：

```text
APP_TIMEZONE
```

计算业务日期。

不在代码中写死机器时区。

这样未来更换电脑或部署不会导致复习日期错乱。

---

# 25. 本地开发

未来本地开发采用两个进程：

```text
Terminal A
FastAPI
localhost:8000
```

```text
Terminal B
Next.js
localhost:3000
```

请求：

```text
Browser
→ localhost:3000
→ localhost:8000/api/...
```

FastAPI 开发环境 CORS 只允许前端开发地址。

---

# 26. 错误处理

## FastAPI 请求失败

前端显示明确错误并允许重试，不白屏。

## SQLite 异常

事务失败必须 rollback。

## 问答题自评未完成

用户提交问答答案后关闭页面：

```text
Attempt.status = awaiting_self_assessment
```

下次进入可恢复参考答案页面并继续自评。

## LLM 超时 / 返回格式错误

仅影响 SQL题。

SQL Attempt 保留用户 SQL：

```text
status = grading_failed
```

允许重新判题，不创建新的 Attempt。

## 用户重复提交

前端请求中禁用提交按钮，后端同时通过 `client_request_id` 保证幂等。

## SQL AI 结果展示后关闭页面

保留：

```text
awaiting_confirmation
```

用户下次可以继续处理。

# 27. 数据一致性原则

需要事务保证：

### 选择题

```text
Attempt completed
+
ReviewState update
```

### 问答题自评

```text
Attempt.self_assessed_mastery_state
+
Attempt completed
+
ReviewState update
```

### SQL最终结果

```text
Final SQL Assessment
+
Attempt completed
+
ReviewState update
```

都必须做到要么全部成功，要么全部失败。

# 28. 测试原则

MVP 至少覆盖：

```text
选择题自动判分
Attempt 创建
问答题提交后进入 awaiting_self_assessment
问答题参考答案只在提交后返回
问答题自评更新 ReviewState
ReviewState 更新
每日任务生成
今日任务重复访问一致
Wrong Book 筛选
内容导入校验
SQL AI结构化结果解析
SQL AI失败不更新 ReviewState
SQL默认接受 / 调整 / 重判流程
```

LLM 自动测试使用 Mock Provider，只覆盖 SQL 判题，不实际消耗模型 API。

# 29. 项目最终目录建议

```text
BigData_Interview_Lab/
│
├── CLAUDE.md
├── README.md
├── .gitignore
├── .env.example
│
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── API.md
│   ├── REVIEW_ALGORITHM.md
│   └── TASKS.md
│
├── frontend/
│
├── backend/
│
├── content/
│   ├── topics/
│   ├── knowledge/
│   └── questions/
│       ├── choice/
│       ├── short_answer/
│       └── sql/
│
├── scripts/
│
└── data/
```

其中：

```text
Git提交：
docs/
frontend/
backend/
content/
scripts/
.env.example

Git忽略：
data/
.env
缓存
日志
依赖
构建产物
```

---

# 30. MVP 明确不采用的架构

当前不使用：

| 技术            | 原因                  |
| ------------- | ------------------- |
| 微服务           | 单用户项目没有拆分收益         |
| Redis         | 当前没有缓存和分布式锁需求       |
| Kafka         | 不存在消息流场景            |
| Celery        | 没有必须后台执行的任务         |
| Docker        | 本地开发阶段增加复杂度         |
| PostgreSQL    | SQLite 足够           |
| WebSocket     | 不存在实时双向通讯需求         |
| Elasticsearch | 数据规模不需要             |
| 独立管理后台        | 内容通过文件维护            |
| 前端直接调用 LLM    | API Key 与业务规则必须留在后端 |

---

# 31. 架构决策记录

| 决策         | 当前方案                       | 原因               | 何时重新考虑     |
| ---------- | -------------------------- | ---------------- | ---------- |
| 应用架构       | 模块化单体                      | MVP 简单，边界仍清晰     | 多用户、规模明显扩大 |
| 前端         | Next.js + TypeScript       | UI 和开发生态成熟       | 暂无必要       |
| 后端         | FastAPI + Python           | AI、数据处理生态方便      | 暂无必要       |
| 数据库        | SQLite                     | 单用户、本地优先         | 多用户或云部署    |
| 内容管理       | Git 内容文件 → Import → SQLite | 可审核、可版本管理、运行查询方便 | 建管理后台时     |
| 知识卡片       | Markdown                   | 长文本易维护           | 有特殊编辑需求    |
| 题目         | YAML                       | 人工和 AI 都容易维护     | 大规模题库出现后   |
| AI         | LLM Service + Provider（仅 SQL 判题） | 避免绑定厂商且不让问答题依赖 AI | 保持长期 |
| SQL判题      | AI逻辑评分                     | 不依赖真实执行引擎        | 以后需要结果级判题  |
| Wrong Book | 查询视图                       | 避免重复状态           | 保持         |
| 每日任务       | 当日快照                       | 页面刷新不能换题         | 智能任务算法上线   |
| 复习调度       | Policy 单独封装                | 算法尚会调整           | 保持         |
| 用户         | 单用户无登录                     | 当前只服务本人          | 对外开放       |
| UI         | PC 优先                      | 秋招学习主要电脑使用       | v1.3 移动适配  |

---

# 32. 后续设计顺序

架构冻结后按以下顺序继续：

```text
ARCHITECTURE.md
        ↓
DATABASE.md
        ↓
REVIEW_ALGORITHM.md
        ↓
API.md
        ↓
TASKS.md
        ↓
项目初始化
        ↓
开始开发
```

在 DATABASE.md 完成之前，不开始创建业务表。

在 API.md 完成之前，不同时开发前后端业务功能。

---

# 33. MVP 最核心的数据流

平台的核心不是 AI，而是：

```text
Content
   ↓
Question
   ↓
Attempt
   ↓
题型评估
   ├── 选择题：System Grade
   ├── 问答题：Self Assessment
   └── SQL题：AI Assessment
   ↓
ReviewState
   ↓
Daily Task
   ↓
再次 Attempt
   ↓
Knowledge Mastery
```

AI 只存在于：

```text
SQL Assessment
```

因此即使暂时关闭 LLM：

```text
知识卡片
选择题
问答题
学习记录
错题本
复习体系
```

仍然可以正常使用。

这也是 MVP 最重要的架构边界。
