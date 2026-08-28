# BigData Interview Lab — API v1.0

> 状态：已按最新产品逻辑修订
> 适用阶段：MVP
> 前置文档：PRD.md、ARCHITECTURE.md、DATABASE.md、REVIEW_ALGORITHM.md

---

# 1. API 设计目标

API 负责连接：

```text
Next.js
   ↓
FastAPI
   ↓
Service
   ↓
SQLite / LLM Service
```

MVP API 覆盖：

- 首页仪表盘
- 每日任务
- 知识点与知识卡片
- 题目浏览
- 选择题作答
- 问答题自评
- SQL AI 判题
- 错题本
- ReviewState
- 学习统计
- 设置

---

# 2. 基础规范

统一前缀：

```text
/api/v1
```

统一格式：

```text
Content-Type: application/json
```

DATETIME 使用 ISO 8601：

```json
"created_at": "2026-08-28T06:30:00Z"
```

DATE 使用：

```json
"next_review_date": "2026-08-30"
```

MVP 不做：

```text
JWT
OAuth
用户登录
权限系统
公开 API
```

---

# 3. 通用错误结构

```json
{
  "error": {
    "code": "QUESTION_NOT_FOUND",
    "message": "题目不存在",
    "details": null
  }
}
```

常用状态码：

| 状态码 | 场景 |
|---:|---|
| 200 | 查询或操作成功 |
| 201 | 创建成功 |
| 400 | 请求内容不合法 |
| 404 | 资源不存在 |
| 409 | 状态冲突 / 重复操作 |
| 422 | 参数校验失败 |
| 500 | 系统异常 |
| 502 | LLM 服务异常 |
| 504 | LLM 超时 |

---

# 4. Dashboard

```text
GET /api/v1/dashboard
```

返回：

```json
{
  "today": {
    "date": "2026-08-28",
    "task_id": 12,
    "status": "in_progress",
    "review_total": 8,
    "review_completed": 3,
    "new_total": 5,
    "new_completed": 2
  },
  "review": {
    "due_count": 8,
    "overdue_count": 3
  },
  "week": {
    "completed_attempts": 31,
    "study_days": 5,
    "choice_accuracy": 0.78
  },
  "weak_knowledge_points": [
    {
      "id": "spark.shuffle",
      "name": "Shuffle",
      "mastery_score": 42
    }
  ],
  "pending_sql_assessment_count": 1
}
```

首页使用聚合接口，避免前端自行拼装大量请求。

---

# 5. 知识点

## 5.1 获取知识点树

```text
GET /api/v1/knowledge-points
```

返回：

```json
[
  {
    "id": "spark",
    "name": "Spark",
    "level": 1,
    "mastery_score": 68,
    "children": [
      {
        "id": "spark.shuffle",
        "name": "Shuffle",
        "level": 2,
        "mastery_score": 42,
        "children": []
      }
    ]
  }
]
```

没有有效题目时：

```json
"mastery_score": null
```

---

## 5.2 获取单个知识点

```text
GET /api/v1/knowledge-points/{knowledge_point_id}
```

返回：

```json
{
  "id": "spark.shuffle",
  "name": "Shuffle",
  "description": "...",
  "mastery_score": 42,
  "question_count": 12,
  "completed_question_count": 5,
  "has_card": true
}
```

---

# 6. 知识卡片

## 6.1 获取知识卡片

```text
GET /api/v1/knowledge-points/{knowledge_point_id}/card
```

返回：

```json
{
  "id": "card.spark.shuffle",
  "knowledge_point_id": "spark.shuffle",
  "revision": 3,
  "content": {
    "one_line_definition": "...",
    "core_principle": ["..."],
    "interview_highlights": ["..."],
    "common_mistakes": ["..."]
  },
  "progress": {
    "status": "read",
    "view_count": 3,
    "last_viewed_at": "2026-08-28T05:00:00Z"
  },
  "related_questions": []
}
```

---

## 6.2 标记知识卡片已查看

```text
POST /api/v1/knowledge-cards/{card_id}/view
```

无需请求体。

返回：

```json
{
  "status": "read",
  "view_count": 4,
  "last_viewed_at": "2026-08-28T06:00:00Z"
}
```

知识卡片阅读不影响掌握率。

---

# 7. 题目列表

```text
GET /api/v1/questions
```

支持：

```text
knowledge_point_id
question_type
difficulty
status
page
page_size
```

示例：

```text
GET /api/v1/questions?knowledge_point_id=spark.shuffle&question_type=short_answer
```

返回：

```json
{
  "items": [
    {
      "id": "spark.shuffle.qa.001",
      "title": "...",
      "question_type": "short_answer",
      "difficulty": 2,
      "mastery_state": "vague",
      "is_due": true
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 12
}
```

---

# 8. 获取一道题

```text
GET /api/v1/questions/{question_id}
```

默认返回当前版本，但提交前不得泄露答案或评分标准。

---

## 8.1 选择题

```json
{
  "id": "spark.shuffle.choice.001",
  "revision": 2,
  "question_type": "single_choice",
  "content": "...",
  "options": [
    {"key": "A", "content": "..."},
    {"key": "B", "content": "..."}
  ],
  "difficulty": 2,
  "primary_knowledge_point": {
    "id": "spark.shuffle",
    "name": "Shuffle"
  }
}
```

提交前不返回：

```text
correct_answer
explanation
```

---

## 8.2 问答题

```json
{
  "id": "spark.shuffle.qa.001",
  "revision": 1,
  "question_type": "short_answer",
  "content": "请说明 Spark Shuffle 的作用和触发场景。",
  "difficulty": 3,
  "primary_knowledge_point": {
    "id": "spark.shuffle",
    "name": "Shuffle"
  }
}
```

提交前不返回：

```text
reference_answer
explanation
```

问答题 MVP 不包含：

```text
scoring_rubric
AI评分
总分
评分点
```

---

## 8.3 SQL 题

```json
{
  "id": "sql.window.row_number.001",
  "revision": 3,
  "question_type": "sql",
  "content": "...",
  "table_schema": "...",
  "field_description": "...",
  "business_requirement": "...",
  "difficulty": 3,
  "max_score": 10
}
```

提交前不返回：

```text
expected_sql
scoring_criteria
```

---

# 9. 创建 Attempt

统一入口：

```text
POST /api/v1/questions/{question_id}/attempts
```

所有提交都必须携带：

```text
question_revision
attempt_type
answer
client_request_id
```

如果来自每日任务，可附带：

```text
daily_task_item_id
```

---

# 10. 提交选择题

请求：

```json
{
  "question_revision": 2,
  "attempt_type": "new",
  "answer": {
    "selected_options": ["B"]
  },
  "daily_task_item_id": 102,
  "client_request_id": "uuid..."
}
```

后端立即：

```text
创建 Attempt
→ 自动判分
→ completed
→ 更新 ReviewState
→ 更新 DailyTaskItem
```

返回：

```json
{
  "attempt_id": 301,
  "status": "completed",
  "result": {
    "is_correct": false,
    "score": 0,
    "max_score": 1,
    "correct_answer": ["B"],
    "explanation": "...",
    "mastery_state": "unmastered",
    "next_review_date": "2026-08-29"
  }
}
```

---

# 11. 提交问答题

请求：

```json
{
  "question_revision": 1,
  "attempt_type": "new",
  "answer": {
    "text": "我的回答..."
  },
  "daily_task_item_id": 103,
  "client_request_id": "uuid..."
}
```

后端：

```text
创建 Attempt
status = awaiting_self_assessment
```

不调用 LLM。

返回：

```json
{
  "attempt_id": 302,
  "status": "awaiting_self_assessment",
  "user_answer": "我的回答...",
  "reference_answer": "参考答案...",
  "explanation": "解析...",
  "mastery_options": [
    {
      "value": "unmastered",
      "label": "不会"
    },
    {
      "value": "vague",
      "label": "模糊"
    },
    {
      "value": "familiar",
      "label": "基本掌握"
    },
    {
      "value": "mastered",
      "label": "熟练掌握"
    }
  ]
}
```

此时：

```text
ReviewState 尚未更新
DailyTaskItem 尚未完成
```

---

# 12. 问答题自评

```text
POST /api/v1/attempts/{attempt_id}/self-assessment
```

请求：

```json
{
  "mastery_state": "familiar"
}
```

后端：

```text
保存 self_assessed_mastery_state
→ Attempt.status = completed
→ Review Policy 计算 review_stage
→ 更新 ReviewState
→ 更新 DailyTaskItem
```

返回：

```json
{
  "attempt_id": 302,
  "status": "completed",
  "self_assessed_mastery_state": "familiar",
  "review_state": {
    "mastery_state": "familiar",
    "next_review_date": "2026-09-04",
    "policy_version": "review_v1"
  }
}
```

问答题没有：

```text
final_score
raw_score
AI确认
regrade
dispute
```

---

# 13. 问答题页面交互

推荐：

```text
显示题目
↓
用户输入答案
↓
提交
↓
展示：
- 用户答案
- 参考答案
- 解析
↓
用户选择：

[不会]
[模糊]
[基本掌握]
[熟练掌握]

↓
完成 Attempt
↓
下一题
```

必须先提交答案，才能看到参考答案。

---

# 14. 提交 SQL 题

请求：

```json
{
  "question_revision": 3,
  "attempt_type": "practice",
  "answer": {
    "sql": "SELECT ..."
  },
  "daily_task_item_id": null,
  "client_request_id": "uuid..."
}
```

后端：

```text
创建 Attempt
status = grading
↓
调用 LLM
```

AI 判题主要依据：

```text
business_requirement
+
scoring_criteria
```

`expected_sql` 仅供理解题意。

不允许以 SQL 文本相似度或结构相似度判断正确性。

---

# 15. SQL 正常评分响应

AI 成功后：

```json
{
  "attempt_id": 303,
  "status": "awaiting_confirmation",
  "assessment": {
    "assessment_id": 501,
    "raw_score": 8,
    "max_score": 10,
    "criteria": [
      {
        "id": "c1",
        "status": "matched",
        "score": 2,
        "max_score": 2,
        "feedback": "..."
      }
    ],
    "knowledge_analysis": {
      "mastered": [],
      "weak": [],
      "missing": []
    },
    "errors": [],
    "suggestions": []
  },
  "expected_sql": "..."
}
```

---

# 16. SQL 默认接受逻辑

SQL 评分页面最常见流程：

```text
提交 SQL
↓
AI评分
↓
展示结果
↓
用户点击“下一题”
↓
默认接受 AI 原始评分
↓
形成 Final Assessment
↓
ReviewState 更新
```

因此前端点击“下一题”时调用：

```text
POST /api/v1/attempts/{attempt_id}/confirm
```

请求：

```json
{
  "action": "accept"
}
```

返回：

```json
{
  "attempt_id": 303,
  "status": "completed",
  "final_score": 8,
  "max_score": 10,
  "final_score_source": "ai_confirmed",
  "mastery_state": "familiar",
  "next_review_date": "2026-09-04"
}
```

---

# 17. SQL 调整评分

如果用户认为 AI 分数不合理：

```text
POST /api/v1/attempts/{attempt_id}/confirm
```

请求：

```json
{
  "action": "adjust",
  "final_score": 9
}
```

后端保留：

```text
AI raw_score = 8
Attempt.final_score = 9
final_score_source = user_adjusted
```

---

# 18. SQL 重新判题

```text
POST /api/v1/attempts/{attempt_id}/regrade
```

不创建新的 Attempt。

只创建新的：

```text
AIAssessment
```

适用于：

```text
LLM超时
返回格式错误
用户认为AI理解错误
```

---

# 19. SQL 标记争议

```text
POST /api/v1/attempts/{attempt_id}/dispute
```

请求：

```json
{
  "reason": "AI 对 JOIN 条件理解错误"
}
```

结果：

```json
{
  "attempt_id": 303,
  "status": "disputed"
}
```

此时不更新 ReviewState。

---

# 20. 查询 Attempt

```text
GET /api/v1/attempts/{attempt_id}
```

按题型返回对应状态。

---

## 20.1 问答题待自评

```json
{
  "id": 302,
  "question_id": "spark.shuffle.qa.001",
  "question_type": "short_answer",
  "status": "awaiting_self_assessment",
  "user_answer": "...",
  "reference_answer": "...",
  "explanation": "...",
  "self_assessed_mastery_state": null
}
```

---

## 20.2 SQL 待确认

```json
{
  "id": 303,
  "question_id": "sql.window.row_number.001",
  "question_type": "sql",
  "status": "awaiting_confirmation",
  "user_answer": "SELECT ...",
  "ai_assessment": {
    "raw_score": 8,
    "max_score": 10
  },
  "final_score": null
}
```

---

# 21. 待处理 Attempt

提供统一接口：

```text
GET /api/v1/attempts/pending
```

返回：

```json
{
  "short_answer_self_assessment": [
    {
      "attempt_id": 302,
      "question_id": "...",
      "created_at": "..."
    }
  ],
  "sql_confirmation": [
    {
      "attempt_id": 303,
      "question_id": "...",
      "raw_score": 8,
      "max_score": 10,
      "created_at": "..."
    }
  ]
}
```

用于用户关闭页面后恢复未完成流程。

---

# 22. 今日任务

```text
GET /api/v1/daily-tasks/today
```

如果当天任务不存在：

```text
后端自动生成并保存
```

如果已经存在：

```text
直接返回原快照
```

不得刷新重新抽题。

---

# 23. 今日任务响应

```json
{
  "id": 12,
  "task_date": "2026-08-28",
  "status": "in_progress",
  "summary": {
    "review_total": 8,
    "review_completed": 3,
    "new_total": 5,
    "new_completed": 2,
    "skipped": 0
  },
  "items": [
    {
      "id": 101,
      "item_type": "review",
      "status": "pending",
      "question": {
        "id": "spark.shuffle.qa.001",
        "revision": 1,
        "question_type": "short_answer",
        "difficulty": 2,
        "title": "..."
      },
      "due_date": "2026-08-27",
      "mastery_state": "vague"
    }
  ]
}
```

---

# 24. 获取历史任务

```text
GET /api/v1/daily-tasks/{date}
```

---

# 25. 跳过任务题

```text
POST /api/v1/daily-task-items/{item_id}/skip
```

复习题被跳过时：

```text
不创建 Attempt
不更新 ReviewState
不修改 next_review_date
```

---

# 26. 恢复 skipped

```text
POST /api/v1/daily-task-items/{item_id}/restore
```

只允许：

```text
skipped → pending
```

---

# 27. ReviewState

## 27.1 查看

```text
GET /api/v1/questions/{question_id}/review-state
```

---

## 27.2 手动修改

```text
PUT /api/v1/questions/{question_id}/review-state
```

请求：

```json
{
  "mastery_state": "familiar"
}
```

后端根据 review_v1 重新计算复习阶段和日期。

---

# 28. 错题本

```text
GET /api/v1/wrong-book
```

支持：

```text
knowledge_point_id
question_type
mastery_state
page
page_size
```

默认来源：

```text
mastery_state = unmastered / vague
```

再叠加：

```text
follow
ignore
```

用户偏好。

---

# 29. 错题本偏好

```text
PUT /api/v1/questions/{question_id}/wrong-book-preference
```

请求：

```json
{
  "mode": "follow"
}
```

或：

```json
{
  "mode": "ignore"
}
```

或：

```json
{
  "mode": "auto"
}
```

只影响 Wrong Book 展示，不影响 ReviewState 和复习调度。

---

# 30. 题目 Attempt 历史

```text
GET /api/v1/questions/{question_id}/attempts
```

问答题历史示例：

```json
[
  {
    "id": 101,
    "attempt_type": "new",
    "status": "completed",
    "self_assessed_mastery_state": "vague",
    "created_at": "..."
  },
  {
    "id": 205,
    "attempt_type": "review",
    "status": "completed",
    "self_assessed_mastery_state": "familiar",
    "created_at": "..."
  }
]
```

SQL 历史可返回：

```text
final_score
max_score
```

---

# 31. 学习统计

## 31.1 总览

```text
GET /api/v1/statistics/overview
```

支持：

```text
period=today
period=week
period=all
```

返回：

```json
{
  "period": "week",
  "completed_attempts": 31,
  "study_days": 5,
  "choice": {
    "count": 18,
    "accuracy": 0.78
  },
  "short_answer": {
    "count": 7,
    "mastery_distribution": {
      "unmastered": 1,
      "vague": 2,
      "familiar": 3,
      "mastered": 1
    }
  },
  "sql": {
    "count": 6,
    "average_score_ratio": 0.71
  }
}
```

问答题不再统计平均分。

---

## 31.2 掌握状态分布

```text
GET /api/v1/statistics/mastery-distribution
```

返回：

```json
{
  "unmastered": 8,
  "vague": 15,
  "familiar": 34,
  "mastered": 32,
  "not_started": 67
}
```

---

## 31.3 知识点掌握率

```text
GET /api/v1/statistics/knowledge-mastery
```

---

## 31.4 薄弱知识点

```text
GET /api/v1/statistics/weak-points?limit=10
```

优先返回：

```text
已开始学习
且掌握率较低
```

的知识点。

---

# 32. 设置

## 32.1 获取设置

```text
GET /api/v1/settings
```

返回：

```json
{
  "daily": {
    "new_question_count": 5,
    "choice_count": 3,
    "short_answer_count": 1,
    "sql_count": 1,
    "max_review_count": 15
  },
  "timezone": "Asia/Shanghai"
}
```

---

## 32.2 修改设置

```text
PUT /api/v1/settings
```

请求：

```json
{
  "daily": {
    "new_question_count": 8,
    "choice_count": 5,
    "short_answer_count": 2,
    "sql_count": 1,
    "max_review_count": 20
  }
}
```

必须满足：

```text
choice_count
+
short_answer_count
+
sql_count
=
new_question_count
```

已生成的当日任务不受设置修改影响，从次日生效。

---

# 33. Content 管理

MVP 不提供题库 CRUD API：

```text
POST /questions
PUT /questions
DELETE /questions
```

题目、答案、知识卡片统一通过：

```text
content/
```

维护。

内容导入使用 CLI / script，不提供管理后台接口。

---

# 34. 题目版本规则

用户看到：

```text
revision = 3
```

提交时即使数据库当前已经：

```text
revision = 4
```

后端仍必须：

```text
按 revision 3 判题 / 展示答案
```

原则：

> 用户看到哪个版本，就按哪个版本完成本次 Attempt。

---

# 35. 幂等性

以下操作必须幂等：

```text
创建 Attempt
问答题 self-assessment
SQL confirm
ReviewState 更新
DailyTask 今日生成
```

Attempt 创建依赖：

```text
client_request_id
```

避免双击和网络重试产生重复记录。

---

# 36. LLM 相关 API 只服务 SQL

MVP 中 LLM 不再参与：

```text
问答题评分
问答题掌握判断
问答题知识点分析
```

LLM 仅用于：

```text
SQL AI 判题
```

后端仍保留：

```text
LLMService
LLMProvider
Prompt Version
结构化结果校验
```

用于 SQL 模块。

---

# 37. 页面与 API 映射

## 首页

```text
GET /dashboard
```

## 今日学习

```text
GET  /daily-tasks/today
GET  /questions/{id}
POST /questions/{id}/attempts

问答：
POST /attempts/{id}/self-assessment

SQL：
POST /attempts/{id}/confirm
POST /attempts/{id}/regrade
POST /attempts/{id}/dispute
```

## 知识点

```text
GET /knowledge-points
GET /knowledge-points/{id}
GET /knowledge-points/{id}/card
GET /questions?knowledge_point_id=...
```

## 错题本

```text
GET /wrong-book
GET /questions/{id}/attempts
PUT /questions/{id}/wrong-book-preference
```

## 统计

```text
GET /statistics/overview
GET /statistics/mastery-distribution
GET /statistics/knowledge-mastery
GET /statistics/weak-points
```

## 设置

```text
GET /settings
PUT /settings
```

---

# 38. MVP API 汇总

## Dashboard

```text
GET /api/v1/dashboard
```

## Knowledge

```text
GET  /api/v1/knowledge-points
GET  /api/v1/knowledge-points/{id}
GET  /api/v1/knowledge-points/{id}/card
POST /api/v1/knowledge-cards/{id}/view
```

## Questions

```text
GET  /api/v1/questions
GET  /api/v1/questions/{id}
POST /api/v1/questions/{id}/attempts
GET  /api/v1/questions/{id}/attempts
```

## Attempts

```text
GET  /api/v1/attempts/{id}
GET  /api/v1/attempts/pending

POST /api/v1/attempts/{id}/self-assessment
POST /api/v1/attempts/{id}/confirm
POST /api/v1/attempts/{id}/regrade
POST /api/v1/attempts/{id}/dispute
```

## Reviews

```text
GET /api/v1/questions/{id}/review-state
PUT /api/v1/questions/{id}/review-state
```

## Daily Tasks

```text
GET  /api/v1/daily-tasks/today
GET  /api/v1/daily-tasks/{date}
POST /api/v1/daily-task-items/{id}/skip
POST /api/v1/daily-task-items/{id}/restore
```

## Wrong Book

```text
GET /api/v1/wrong-book
PUT /api/v1/questions/{id}/wrong-book-preference
```

## Statistics

```text
GET /api/v1/statistics/overview
GET /api/v1/statistics/mastery-distribution
GET /api/v1/statistics/knowledge-mastery
GET /api/v1/statistics/weak-points
```

## Settings

```text
GET /api/v1/settings
PUT /api/v1/settings
```

---

# 39. MVP 暂不提供

```text
登录 / 注册
题目 CRUD
知识卡片 CRUD
题库管理后台
WebSocket
AI自由问答
AI自动生成题目
AI自动生成知识卡片
问答题 AI评分
问答题 AI点评
公开 API
第三方 OAuth
```

未来如果需要，可把：

```text
“AI点评我的问答答案”
```

设计成一个可选增强功能，但不进入当前主流程。

---

# 40. API 开发优先级

## Phase 1：内容链路

```text
GET /knowledge-points
GET /knowledge-points/{id}/card
```

验证：

```text
Content → SQLite → FastAPI
```

---

## Phase 2：选择题

```text
GET /questions
GET /questions/{id}
POST /questions/{id}/attempts
```

先完成自动判分闭环。

---

## Phase 3：问答题

```text
POST /questions/{id}/attempts
POST /attempts/{id}/self-assessment
```

完成：

```text
作答 → 看答案 → 自评 → ReviewState
```

---

## Phase 4：Review / Wrong Book

```text
ReviewState
Wrong Book
```

---

## Phase 5：Daily Task / Dashboard

```text
DailyTask
Dashboard
```

---

## Phase 6：SQL AI 判题

```text
SQL Attempt
AIAssessment
confirm
regrade
dispute
```

---

## Phase 7：Statistics / Settings

```text
Statistics
Settings
```

---

# 41. API v1.0 最终业务边界

三类题最终接口流程：

```text
选择题
GET Question
↓
POST Attempt
↓
系统自动判分
↓
ReviewState
```

```text
问答题
GET Question
↓
POST Attempt
↓
展示参考答案
↓
POST Self Assessment
↓
ReviewState
```

```text
SQL题
GET Question
↓
POST Attempt
↓
LLM Assessment
↓
默认接受 / 调整 / 重判
↓
Final Score
↓
ReviewState
```

最重要的原则：

> 前端只提交用户行为和用户选择。

前端不能决定：

```text
next_review_date
知识点掌握率
错题本自动状态
每日任务生成逻辑
SQL最终复习阶段
```

这些必须统一由后端根据 Review Policy 和业务规则计算。
