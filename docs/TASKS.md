# BigData Interview Lab — TASKS v1.0

> 状态：MVP 开发任务拆解
> 适用阶段：正式开发前
> 前置文档：
> - PRD.md
> - ARCHITECTURE.md
> - DATABASE.md
> - REVIEW_ALGORITHM.md
> - API.md
>
> 核心原则：
> - 小步开发
> - 每个任务单独审批
> - 每个任务必须有验收标准
> - 未完成当前阶段，不进入下一阶段
> - 不允许 Claude Code 自行扩大范围

---

# 1. 开发总原则

整个项目按照：

```text
需求确认
↓
方案设计
↓
用户审核
↓
实施开发
↓
自动测试
↓
用户验收
↓
Git 提交
```

执行。

Claude Code 每次准备修改文件前，必须先说明：

1. 本次目标
2. 为什么要改
3. 准备修改哪些文件
4. 每个文件改什么
5. 是否影响 API / 数据库 / 复习算法
6. 如何验证
7. 是否存在超出当前任务范围的修改

用户明确批准后才能实施。

---

# 2. MVP 开发阶段总览

```text
Phase 0   项目骨架与开发环境
Phase 1   SQLite + SQLAlchemy + Migration
Phase 2   Content 内容结构与导入
Phase 3   知识点与知识卡片
Phase 4   选择题完整闭环
Phase 5   问答题自评完整闭环
Phase 6   ReviewState + Wrong Book
Phase 7   DailyTask + Dashboard
Phase 8   SQL AI 判题
Phase 9   学习统计 + 设置
Phase 10  前端体验收尾
Phase 11  MVP 总体验收
```

开发顺序不能倒置。

---

# 3. Phase 0 — 项目骨架与开发环境

## 目标

建立最小可运行的：

```text
Next.js
+
FastAPI
```

开发骨架。

这一阶段不写业务功能。

---

## Task 0.1 — 检查仓库当前状态

### 只读检查

确认：

```text
CLAUDE.md
README.md
docs/
```

是否存在。

确认当前 Git 状态。

确认：

```text
Node
npm
Python
pip
```

可用。

### 不允许

```text
修改文件
安装依赖
初始化项目
```

### 验收

用户看到明确检查结果。

---

## Task 0.2 — 初始化 FastAPI 项目骨架

预计建立：

```text
backend/
├── app/
│   ├── __init__.py
│   └── main.py
└── tests/
```

只实现：

```text
GET /health
```

返回：

```json
{
  "status": "ok"
}
```

### 验收

FastAPI 可以本地启动。

Swagger 可以打开。

`/health` 返回 200。

---

## Task 0.3 — 初始化 Next.js 项目骨架

建立：

```text
frontend/
```

只保留最小首页。

首页显示：

```text
BigData Interview Lab
```

### 不做

```text
Dashboard
题目页面
样式系统
复杂组件
```

### 验收

Next.js 可以本地启动。

首页可访问。

---

## Task 0.4 — 前后端连通

前端调用：

```text
GET /health
```

页面展示：

```text
Backend Connected
```

或：

```text
Backend Offline
```

### 验收

Next.js → FastAPI HTTP 通信成功。

---

# 4. Phase 1 — SQLite + SQLAlchemy

## 目标

把数据库基础设施搭好。

暂时不实现业务页面。

---

## Task 1.1 — 后端配置管理

建立：

```text
backend/app/config.py
.env.example
```

配置：

```text
DATABASE_URL
APP_TIMEZONE
LLM_PROVIDER
LLM_MODEL
LLM_API_KEY
```

### 安全要求

真实 `.env` 不提交 Git。

API Key 不进入前端。

---

## Task 1.2 — SQLAlchemy Session

建立：

```text
backend/app/db/
```

实现：

```text
engine
session
foreign_keys = ON
WAL
```

### 验收

可连接：

```text
data/app.db
```

---

## Task 1.3 — 创建 ORM Models

按照 DATABASE.md 建立 MVP 数据模型。

必须覆盖：

```text
knowledge_point
knowledge_card
knowledge_card_version
question
question_version
question_related_knowledge_point
attempt
ai_assessment
attempt_knowledge_result
review_state
question_preference
daily_task
daily_task_item
knowledge_card_progress
app_setting
```

注意：

问答题不使用 AI Assessment。

`ai_assessment` 只服务 SQL。

---

## Task 1.4 — Alembic

初始化 Migration。

生成第一版数据库 migration。

### 验收

可以：

```text
空数据库
→ migration
→ 完整表结构
```

不得依赖手工建表。

---

## Task 1.5 — 数据库模型测试

测试：

```text
外键
唯一约束
Attempt 重复 client_request_id
DailyTask task_date unique
QuestionVersion 联合主键
```

---

# 5. Phase 2 — Content 内容层

## 目标

实现：

```text
Content
↓
Validation
↓
Import
↓
SQLite
```

---

## Task 2.1 — 定义内容目录

建立：

```text
content/
├── topics/
├── knowledge/
└── questions/
    ├── choice/
    ├── short_answer/
    └── sql/
```

---

## Task 2.2 — 定义知识点 YAML Schema

支持：

```text
id
parent_id
name
level
description
sort_order
```

准备少量示例：

```text
Spark
Spark > Shuffle
SQL
SQL > Window Function
```

---

## Task 2.3 — 定义知识卡片 Markdown 规范

支持：

```text
一句话定义
核心原理
面试高频点
常见易错点
```

需要 stable card id。

---

## Task 2.4 — 定义选择题 YAML Schema

必须支持：

```text
id
question_type
knowledge_point
content
options
correct_answer
explanation
difficulty
tags
```

---

## Task 2.5 — 定义问答题 YAML Schema

问答题只保留：

```text
id
question_type
knowledge_point
content
reference_answer
explanation
difficulty
tags
related_knowledge_points
```

明确不包含：

```text
scoring_rubric
AI评分配置
```

---

## Task 2.6 — 定义 SQL 题 YAML Schema

支持：

```text
content
table_schema
field_description
business_requirement
expected_sql
scoring_criteria
knowledge_point
difficulty
tags
```

---

## Task 2.7 — 内容校验器

校验：

```text
ID重复
知识点不存在
题型非法
难度不在 1-5
Choice 正确答案不存在
SQL scoring_criteria 缺失
知识卡片知识点不存在
```

---

## Task 2.8 — Content Import

实现：

```text
scripts/import_content.py
```

逻辑：

```text
读取
↓
校验
↓
source_hash
↓
无变化 → 跳过
有变化 → revision + 1
↓
写 SQLite
```

---

## Task 2.9 — Content Import 测试

测试：

```text
首次导入
重复导入
内容修改
版本增加
内容删除 → is_active=0
非法内容阻止导入
```

---

# 6. Phase 3 — 知识点与知识卡片

## 目标

完成第一条真实产品链路：

```text
Content
↓
SQLite
↓
FastAPI
↓
Next.js
```

---

## Task 3.1 — Knowledge Repository / Service

实现：

```text
知识点树
知识点详情
知识卡片读取
```

---

## Task 3.2 — Knowledge API

实现：

```text
GET /api/v1/knowledge-points
GET /api/v1/knowledge-points/{id}
GET /api/v1/knowledge-points/{id}/card
POST /api/v1/knowledge-cards/{id}/view
```

---

## Task 3.3 — 知识点页面

前端实现：

```text
知识点树
知识点详情
知识卡片
```

MVP 只要求：

```text
清楚
可读
能跳转
```

暂不追求高级视觉效果。

---

## Task 3.4 — 验收

必须做到：

```text
点击 Spark
↓
进入 Shuffle
↓
查看知识卡片
↓
记录阅读次数
```

---

# 7. Phase 4 — 选择题完整闭环

## 目标

实现第一种完整做题体验。

---

## Task 4.1 — Question 查询服务

支持：

```text
按知识点
按题型
按难度
```

查询。

---

## Task 4.2 — Question API

实现：

```text
GET /api/v1/questions
GET /api/v1/questions/{id}
```

必须避免答案泄露。

---

## Task 4.3 — 选择题提交

实现：

```text
POST /api/v1/questions/{id}/attempts
```

选择题流程：

```text
提交
↓
Attempt
↓
系统判分
↓
ReviewState
↓
结果返回
```

---

## Task 4.4 — client_request_id 幂等

测试：

```text
相同 UUID 连续提交两次
```

只能产生一个 Attempt。

---

## Task 4.5 — 选择题前端

页面需要：

```text
题目
选项
提交
正确/错误
正确答案
解析
关联知识卡片
下一题
```

---

## Task 4.6 — 选择题算法测试

覆盖：

```text
首次答对
首次答错
再次答对
mastered 后答错
立即重做
```

---

# 8. Phase 5 — 问答题自评闭环

## 目标

实现最新确定的问答题流程。

---

## Task 5.1 — 问答题提交

用户提交答案：

```text
POST /questions/{id}/attempts
```

后端：

```text
Attempt.status = awaiting_self_assessment
```

返回：

```text
用户答案
参考答案
解析
```

不调用 AI。

---

## Task 5.2 — 问答题自评接口

实现：

```text
POST /api/v1/attempts/{id}/self-assessment
```

允许：

```text
unmastered
vague
familiar
mastered
```

---

## Task 5.3 — Self Assessment → ReviewState

根据 REVIEW_ALGORITHM.md：

```text
不会 → 短间隔
模糊 → 短间隔
基本掌握 → 中间隔
熟练掌握 → 长间隔
```

更新：

```text
ReviewState
DailyTaskItem
Attempt
```

---

## Task 5.4 — 问答题前端

流程必须严格：

```text
显示问题
↓
用户回答
↓
提交
↓
才显示标准答案
↓
用户自评
↓
下一题
```

不得提前显示参考答案。

---

## Task 5.5 — 未完成自评恢复

如果用户提交后关闭页面：

```text
Attempt = awaiting_self_assessment
```

重新进入时必须能继续自评。

---

## Task 5.6 — 验收

需要完整测试：

```text
第一次：不会
第二次：模糊
第三次：基本掌握
第四次：熟练掌握
```

历史 Attempt 不覆盖。

---

# 9. Phase 6 — ReviewState + Wrong Book

## 目标

完成真正的复习体系。

---

## Task 6.1 — Review Service

统一负责：

```text
复习阶段
掌握状态
next_review_date
manual mastery
review_count
```

Route 不允许写算法。

---

## Task 6.2 — ReviewState API

实现：

```text
GET /questions/{id}/review-state
PUT /questions/{id}/review-state
```

---

## Task 6.3 — Wrong Book Service

实现：

```text
auto
follow
ignore
```

规则。

不建立独立 wrong_book 表。

---

## Task 6.4 — Wrong Book API

实现：

```text
GET /wrong-book
PUT /questions/{id}/wrong-book-preference
```

---

## Task 6.5 — Wrong Book 页面

支持：

```text
知识点筛选
题型筛选
掌握状态筛选
查看
重做
关注
忽略
```

---

## Task 6.6 — 验收

必须验证：

```text
不会 → 自动出现
基本掌握 → 自动离开
follow → 强制出现
ignore → 隐藏
ignore 不影响 next_review_date
```

---

# 10. Phase 7 — DailyTask + Dashboard

## 目标

形成每天真正可以使用的学习入口。

---

## Task 7.1 — DailyTaskService

当天首次访问：

```text
到期 ReviewState
+
固定新题
↓
生成快照
```

---

## Task 7.2 — 到期题排序

按：

```text
overdue_days
↓
mastery_state
↓
next_review_date
↓
last_review_at
```

排序。

---

## Task 7.3 — 每日新题

默认：

```text
3 Choice
1 Short Answer
1 SQL
```

只从：

```text
从未完成的 active Question
```

中选择。

---

## Task 7.4 — DailyTask API

实现：

```text
GET /daily-tasks/today
GET /daily-tasks/{date}
POST /daily-task-items/{id}/skip
POST /daily-task-items/{id}/restore
```

---

## Task 7.5 — Dashboard API

实现：

```text
GET /dashboard
```

返回：

```text
今日任务
待复习
本周概览
薄弱知识点
待处理 Attempt
```

---

## Task 7.6 — Dashboard 页面

目标：

```text
打开页面 3 秒内知道今天做什么
```

---

## Task 7.7 — 验收

测试：

```text
当天第一次生成任务
刷新后任务不变化
设置修改不影响今天任务
跳过复习题后 next_review_date 不改变
第二天仍然可重新出现
```

---

# 11. Phase 8 — SQL AI 判题

## 目标

这是 MVP 唯一必须使用 LLM 的核心功能。

---

## Task 8.1 — LLM Provider Interface

建立：

```text
LLMService
LLMProvider
```

业务层不得直接依赖某厂商 SDK。

---

## Task 8.2 — Mock Provider

先实现：

```text
MockLLMProvider
```

用于测试。

正式 API Key 尚未配置时，也可以完成完整业务链路。

---

## Task 8.3 — SQL Prompt

Prompt 输入：

```text
question
table_schema
field_description
business_requirement
scoring_criteria
expected_sql
user_sql
```

明确：

```text
business_requirement
+
scoring_criteria
```

为主要判题依据。

---

## Task 8.4 — Structured Output Schema

至少：

```text
score
criteria
mastered
weak
missing
errors
suggestions
reasoning_summary
```

---

## Task 8.5 — SQL Attempt

流程：

```text
提交
↓
Attempt = grading
↓
LLM
↓
AIAssessment
↓
awaiting_confirmation
```

---

## Task 8.6 — 默认接受

前端：

```text
下一题
```

默认触发：

```text
confirm action=accept
```

无需额外显示“确认评分”按钮作为主流程。

---

## Task 8.7 — 调整 / 重判 / 争议

实现：

```text
confirm adjust
regrade
dispute
```

---

## Task 8.8 — LLM 异常

覆盖：

```text
timeout
provider error
invalid response
retry
```

失败时不得更新 ReviewState。

---

## Task 8.9 — 正式 Provider

最后再接真实模型。

具体模型在此任务开始前单独确认。

不要提前绑定厂商。

---

# 12. Phase 9 — 学习统计 + 设置

## Task 9.1 — MasteryService

计算：

```text
Question Mastery State → 分值
↓
叶子 Knowledge Point
↓
父 Knowledge Point
```

---

## Task 9.2 — Statistics API

实现：

```text
GET /statistics/overview
GET /statistics/mastery-distribution
GET /statistics/knowledge-mastery
GET /statistics/weak-points
```

---

## Task 9.3 — 问答题统计

问答题不计算平均分。

统计：

```text
完成数
不会数
模糊数
基本掌握数
熟练掌握数
```

---

## Task 9.4 — Settings API

实现：

```text
GET /settings
PUT /settings
```

校验：

```text
choice
+
short_answer
+
sql
=
new_question_count
```

---

## Task 9.5 — Statistics 页面

MVP 只做：

```text
今日
本周
累计

题量
选择题正确率
SQL平均分
掌握状态分布
知识点掌握率
```

不提前开发：

```text
雷达图
月报
学习日历
复杂趋势图
```

---

# 13. Phase 10 — 前端体验收尾

## 目标

功能已经完整后，再统一处理体验。

---

## Task 10.1 — 全局导航

固定入口：

```text
首页
今日学习
知识点
错题本
统计
设置
```

---

## Task 10.2 — Loading / Empty / Error

每个页面必须有：

```text
Loading
空状态
错误状态
重试
```

---

## Task 10.3 — 题目页统一体验

三类题共用：

```text
顶部信息
题目区
答题区
反馈区
下一题
知识卡片入口
```

但不能为了复用强行把三类业务逻辑塞进一个巨型组件。

---

## Task 10.4 — 键盘体验

PC 优先。

建议：

```text
Ctrl/Cmd + Enter 提交
数字键选择选项
下一题快捷键
```

是否实现由实际开发成本决定。

---

## Task 10.5 — 样式收尾

目标：

```text
干净
易读
低干扰
适合长时间刷题
```

不是：

```text
炫酷动画
复杂渐变
过度设计
```

---

# 14. Phase 11 — MVP 总体验收

必须按完整用户旅程测试。

---

## 场景 A — 第一天使用

```text
打开首页
↓
生成今日任务
↓
看知识卡片
↓
做选择题
↓
做问答题并自评
↓
做 SQL
↓
看统计
```

---

## 场景 B — 第二天复习

```text
打开首页
↓
看到昨天到期复习题
↓
重做
↓
ReviewState 变化
↓
错题本变化
```

---

## 场景 C — 问答题恢复

```text
提交问答答案
↓
看到参考答案
↓
关闭页面
↓
重新打开
↓
继续自评
```

---

## 场景 D — SQL AI失败

```text
提交 SQL
↓
LLM timeout
↓
答案保留
↓
重新判题
↓
成功
↓
下一题默认接受
```

---

## 场景 E — 重复请求

```text
双击提交
网络重复请求
刷新页面
```

不得：

```text
重复 Attempt
重复 Review 更新
重复 DailyTask
```

---

# 15. 自动测试最低要求

后端至少覆盖：

```text
Content Import
Question Version
Choice grading
Short Answer self assessment
Review Policy
Wrong Book
DailyTask snapshot
Attempt idempotency
SQL Mock AI grading
SQL confirm
AI failure
Statistics
Settings
```

前端至少覆盖关键交互：

```text
选择题提交
问答题提交 → 自评
SQL结果 → 下一题
DailyTask 展示
错误状态
```

---

# 16. Git 提交建议

不要：

```text
一次提交整个 MVP
```

建议每个可验收任务或小阶段一个提交。

例如：

```text
feat: initialize FastAPI backend
feat: add SQLite models and migrations
feat: add content importer
feat: implement knowledge cards
feat: implement choice practice
feat: implement short-answer self assessment
feat: add review state and wrong book
feat: add daily task workflow
feat: add SQL AI grading
feat: add learning statistics
```

---

# 17. Claude Code 每次任务模板

后续每次开发，都使用类似模板：

```text
当前只执行 TASKS.md 中的 Task X.X。

请先阅读：
- CLAUDE.md
- 对应 docs 文档
- TASKS.md

先不要修改任何文件。

先输出：

1. 当前任务理解
2. 实现方案
3. 预计修改/新增文件
4. 每个文件的具体作用
5. 是否涉及数据库/API/算法
6. 测试方案
7. 验收方式

不得：
- 扩大任务范围
- 顺手重构其他模块
- 提前实现后续 Phase
- 修改未批准文件

等待我批准后再实施。
```

---

# 18. 第一批正式开发任务

现在只启动：

```text
Phase 0
```

不要一次让 Claude Code 初始化前后端、数据库、内容导入全部内容。

正确顺序：

```text
Task 0.1
↓
Task 0.2
↓
Task 0.3
↓
Task 0.4
```

完成 Phase 0 后再进入 Phase 1。

---

# 19. MVP Definition of Done

只有以下条件全部满足，才算 MVP 完成：

```text
知识点可以浏览
知识卡片可以查看

选择题：
能做 → 判分 → 复习

问答题：
能答 → 看参考答案 → 自评 → 复习

SQL题：
能写 → AI判题 → 默认接受/调整 → 复习

错题本：
能自动进入/离开
能关注/忽略

每日任务：
每天稳定生成
刷新不换题

统计：
能看今日/本周/累计
能看细粒度知识点掌握率

学习记录：
关闭程序重新打开后仍然存在
```

---

# 20. 最终开发路线

```text
设计阶段
PRD
↓
ARCHITECTURE
↓
DATABASE
↓
REVIEW_ALGORITHM
↓
API
↓
TASKS
✅

开发阶段
Phase 0
↓
Phase 1
↓
Phase 2
↓
Phase 3
↓
Phase 4
↓
Phase 5
↓
Phase 6
↓
Phase 7
↓
Phase 8
↓
Phase 9
↓
Phase 10
↓
Phase 11
↓
MVP
```

从现在开始，产品和系统设计阶段结束。

后续任何新增需求，如果不属于当前 Task：

```text
记录
↓
不立即开发
↓
放入后续版本
```

避免在 MVP 开发过程中不断扩大范围。
