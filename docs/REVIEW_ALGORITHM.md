# BigData Interview Lab — REVIEW_ALGORITHM v0.2

> 状态：复习算法设计稿  
> 适用阶段：MVP  
> 算法版本：`review_v2`  
> 前置文档：PRD.md、ARCHITECTURE.md、DATABASE.md

---

# 1. 设计目标

复习算法解决四个问题：

1. 一道题做完后，当前处于什么题目掌握状态？
2. 下一次什么时候重新出现？
3. 每天优先复习哪些题？
4. 如何从单题 ReviewState 计算 Spark / Hive / SQL 等知识点掌握率？

核心目标不是严格复刻某个数学遗忘模型，而是：

> **不会的高频重复，模糊的近期巩固，掌握的逐步拉长间隔。**

MVP 同时支持三种不同评估方式：

```text
选择题 → 系统自动判分
问答题 → 用户查看参考答案后自评掌握状态
SQL题  → AI辅助判题，最终采用结果转换为分数表现
```

---

# 2. 核心概念

## 2.1 Question Mastery State

单题当前掌握状态：

```text
unmastered    不会
vague         模糊
familiar      基本掌握
mastered      熟练掌握
```

保存在 `review_state.mastery_state`。

## 2.2 review_stage

`review_stage` 表示当前复习阶段，用于决定下次复习间隔。

| stage | 间隔 |
|---:|---:|
| 0 | 1 天 |
| 1 | 2 天 |
| 2 | 4 天 |
| 3 | 7 天 |
| 4 | 14 天 |
| 5 | 30 天 |

形成：

```text
1 → 2 → 4 → 7 → 14 → 30 天
```

## 2.3 为什么 Mastery State 与 Stage 分开

掌握状态回答：

> 现在会不会？

复习阶段回答：

> 已经经过多少次时间验证？

例如两个 `familiar`：

```text
刚进入基本掌握
和
已经稳定复习多次
```

下一次间隔可以不同。

---

# 3. 两条评估路径

MVP 不再强行把所有题型转换成同一种评分方式。

## 3.1 Score-Based Path

适用于：

```text
选择题
SQL题
```

输入：

```text
final_score / max_score
```

再转换为 `Performance`。

## 3.2 Self-Assessment Path

适用于：

```text
问答题
用户主动手工调整掌握状态
```

输入直接就是：

```text
unmastered
vague
familiar
mastered
```

不经过分数和 AI 阈值。

---

# 4. Score-Based Performance

只有 `Attempt.status = completed` 的最终结果可以进入算法。

```text
score_ratio = final_score / max_score
```

Performance：

| score_ratio | Performance | 含义 |
|---:|---|---|
| `< 0.60` | fail | 明显未掌握 |
| `0.60 ~ < 0.80` | partial | 知道部分但不完整 |
| `0.80 ~ < 0.95` | good | 基本正确 |
| `>= 0.95` | excellent | 完整准确 |

阈值属于 `review_v2`，以后调整需要升级算法版本。

---

# 5. 选择题

单选题：

```text
答错 → 0 / 1 → fail
答对 → 1 / 1 → excellent
```

未来多选题 MVP 默认：

```text
完全正确 → 1
否则 → 0
```

不做复杂部分得分。

---

# 6. SQL题

SQL 题使用最终采用的判题结果：

```text
Attempt.final_score
Attempt.max_score
```

例如：

```text
AI 原始：7 / 10
用户正常下一题 → 接受 7 / 10
```

则：

```text
score_ratio = 0.7
```

如果用户调整为：

```text
9 / 10
```

算法使用：

```text
0.9
```

AI 原始分不直接进入复习算法。

`grading_failed`、`disputed`、`awaiting_confirmation` 都不能更新 ReviewState。

---

# 7. 问答题：Self Assessment

问答题流程：

```text
用户独立回答
↓
提交答案
↓
查看参考答案 / 解析
↓
用户选择：
不会 / 模糊 / 基本掌握 / 熟练掌握
↓
Attempt completed
↓
应用 Self-Assessment Policy
```

问答题没有：

```text
final_score
max_score
score_ratio
AI评分
Performance阈值
```

用户自评就是该次问答题的最终复习输入。

---

# 8. 问答题自评到复习状态的映射

## 8.1 不会

用户选择：

```text
unmastered
```

结果：

```text
mastery_state = unmastered
review_stage = 0
next_review_date = 1天后
consecutive_successes = 0
```

## 8.2 模糊

```text
mastery_state = vague
review_stage = 1
next_review_date = 2天后
consecutive_successes = 0
```

## 8.3 基本掌握

```text
mastery_state = familiar
review_stage = 3
next_review_date = 7天后
consecutive_successes += 1
```

## 8.4 熟练掌握

第一次或当前 stage < 4：

```text
mastery_state = mastered
review_stage = 4
next_review_date = 14天后
```

如果该题已经处于 `mastered` 且再次自评为 `mastered`：

```text
review_stage = 5
next_review_date = 30天后
```

用于验证长期稳定掌握。

---

# 9. 为什么问答题允许第一次自评 mastered

选择题一次答对可能存在蒙对，因此 Score-Based Path 不会把第一次答对直接视为长期掌握。

问答题不同：

```text
先独立组织答案
↓
再与参考答案对照
↓
用户主动判断自己能否完整表达
```

因此用户明确选择 `mastered` 时，系统尊重用户判断。

这也是取消问答题 AI 强制评分后的核心产品原则：

> **问答题训练的是面试表达与自我检验，用户拥有最终判断权。**

---

# 10. Score-Based：首次做题

以下仅适用于选择题和 SQL 题。

如果不存在 ReviewState：

## fail

```text
mastery_state = unmastered
stage = 0
next = 1天后
consecutive_successes = 0
```

## partial

```text
mastery_state = vague
stage = 0
next = 1天后
consecutive_successes = 0
```

## good

```text
mastery_state = vague
stage = 1
next = 2天后
consecutive_successes = 1
```

## excellent

```text
mastery_state = vague
stage = 1
next = 2天后
consecutive_successes = 1
```

第一次高分不直接进入 `mastered`。

---

# 11. Score-Based：fail

```text
score_ratio < 0.60
```

无论原状态：

```text
stage = 0
mastery_state = unmastered
consecutive_successes = 0
next = 1天后
```

---

# 12. Score-Based：partial

```text
0.60 <= score_ratio < 0.80
```

结果：

```text
stage = max(0, current_stage - 1)
mastery_state = vague
consecutive_successes = 0
```

下次日期由新 stage 决定。

---

# 13. Score-Based：good

```text
0.80 <= score_ratio < 0.95
```

结果：

```text
stage = min(current_stage + 1, 5)
consecutive_successes += 1
mastery_state = mastery_from_stage(stage)
```

---

# 14. Score-Based：excellent

```text
score_ratio >= 0.95
```

默认：

```text
stage += 1
```

如果连续两次及以上 `excellent`：

```text
stage = min(current_stage + 2, 5)
```

用于快速拉长已经稳定的内容。

---

# 15. Score-Based 的 stage 到 mastery 映射

| stage | mastery_state |
|---:|---|
| 0 | vague |
| 1 | vague |
| 2 | familiar |
| 3 | familiar |
| 4 | mastered |
| 5 | mastered |

特殊优先规则：

```text
fail → unmastered
partial → vague
```

---

# 16. 用户主动手工调整掌握状态

除了问答题正常自评外，用户还可以在其他页面主动调整某道题当前状态。

统一使用 Self-Assessment Policy：

| 用户选择 | stage | 下次复习 |
|---|---:|---:|
| 不会 | 0 | 1 天 |
| 模糊 | 1 | 2 天 |
| 基本掌握 | 3 | 7 天 |
| 熟练掌握 | 4 | 14 天 |

如果已经是 `mastered` 并再次明确选择 `mastered`，可以进入 stage 5 / 30 天。

手工判断优先于系统自动状态。

---

# 17. consecutive_successes

`consecutive_successes` 表示连续稳定表现。

Score-Based：

```text
good / excellent → +1
partial / fail    → 0
```

Self-Assessment：

```text
familiar / mastered → +1
vague / unmastered  → 0
```

MVP 主要用于保留未来算法升级所需的信息。

---

# 18. review_count

只有：

```text
attempt_type = review
且
Attempt.status = completed
```

才：

```text
review_count += 1
```

`new` 和 `practice` 不增加 `review_count`。

但是所有 completed Attempt 都可以更新 ReviewState。

---

# 19. practice 如何影响复习状态

用户主动练习：

```text
attempt_type = practice
```

也属于新的有效学习证据。

因此：

- 选择题：根据自动判分更新。
- 问答题：根据本次自评更新。
- SQL题：根据最终采用的判题结果更新。

不能因为不是系统安排的 review 就忽略。

---

# 20. 未完成 Attempt

以下 Attempt 不更新 ReviewState：

```text
问答题 awaiting_self_assessment
SQL grading
SQL grading_failed
SQL awaiting_confirmation
SQL disputed
```

只有真正完成后才应用复习策略。

---

# 21. next_review_date

复习按业务日期计算：

```text
APP_TIMEZONE
```

例如：

```text
today = 2026-08-28
stage = 2
interval = 4
```

则：

```text
next_review_date = 2026-09-01
```

不使用精确的 `+96小时`。

---

# 22. 复习逾期

如果题目已经逾期：

```text
next_review_date < today
```

系统只计算：

```text
overdue_days
```

用于任务优先级。

逾期本身：

- 不自动降低 mastery_state
- 不自动改变 stage

只有再次作答才能改变 ReviewState。

---

# 23. Due Review Pool

每日任务生成时查询：

```text
ReviewState.next_review_date <= today
AND Question.is_active = 1
```

得到待复习池。

---

# 24. 复习优先级

排序：

```text
① overdue_days 越大越优先
② mastery_state 越低越优先
③ next_review_date 越早越优先
④ last_review_at 越早越优先
```

掌握状态优先级：

```text
unmastered
>
vague
>
familiar
>
mastered
```

---

# 25. 每日最大复习量

默认：

```text
daily.max_review_count = 15
```

可配置。

如果今天 32 道到期，只安排前 15 道。

剩余题目仍保持逾期状态，第二天继续优先出现。

---

# 26. 每日新题

默认：

```text
3 选择
1 问答
1 SQL
```

共：

```text
5 道
```

复习题不占新题数量。

---

# 27. DailyTask 生成

当天第一次访问：

```text
检查 DailyTask(today)
↓
不存在
↓
选到期复习题
↓
选固定数量新题
↓
保存 DailyTask + DailyTaskItem
```

当天再次刷新：

```text
直接返回同一任务
```

不重新随机。

---

# 28. 新题定义

题目没有任何 `completed Attempt` 才是新题。

特殊情况：

**问答题**

已经提交但：

```text
awaiting_self_assessment
```

不能再次作为新题出现，应先继续完成该 Attempt。

**SQL题**

存在：

```text
grading_failed
awaiting_confirmation
```

也不能重新作为新题随机出现，应先处理原 Attempt。

---

# 29. 新题随机规则

MVP：

```text
active Question
+
不存在 completed Attempt
+
不存在待完成 Attempt
```

按题型简单随机。

暂时不做：

- 薄弱知识点推荐
- 难度自适应
- 知识点轮转

---

# 30. Question Mastery State 数值映射

用于 Knowledge Point Mastery Score：

| 状态 | 数值 |
|---|---:|
| 未做 | 0 |
| unmastered | 20 |
| vague | 45 |
| familiar | 75 |
| mastered | 100 |

`未做 = 0` 用于同时体现：

```text
学习覆盖度
+
掌握质量
```

---

# 31. 叶子知识点掌握率

例如一个知识点有：

```text
Question A → mastered = 100
Question B → familiar = 75
Question C → vague = 45
Question D → 未做 = 0
```

则：

```text
(100 + 75 + 45 + 0) / 4
= 55%
```

---

# 32. 关联知识点权重

主知识点默认：

```text
weight = 1.0
```

关联知识点默认：

```text
weight = 0.5
```

如果内容文件显式配置，则使用配置值。

---

# 33. SQL AI Knowledge Evidence

只有 SQL AI 判题会产生：

```text
mastered
weak
missing
```

并写入 `attempt_knowledge_result`。

MVP 用途：

```text
SQL 判题反馈
薄弱点展示
```

**暂时不直接再次影响 Knowledge Point Mastery Score。**

因为 SQL Question 的 ReviewState 已经参与掌握率计算，再叠加 AI Evidence 会产生重复加权。

问答题没有 AI Knowledge Evidence。

---

# 34. 父知识点掌握率

父节点使用直接有效子节点的等权平均。

例如：

```text
RDD        80%
Shuffle    55%
Stage      70%
Spark SQL  75%
```

则：

```text
Spark = 70%
```

不按题量加权，避免题库数量大的模块支配整个大类。

---

# 35. 没有题目的知识点

叶子知识点没有有效题目：

```text
Mastery Score = NULL
```

而不是 `0%`。

父级汇总时忽略 NULL。

---

# 36. 知识卡片阅读

阅读知识卡片：

```text
不直接提高 Mastery Score
```

知识卡片只提供学习输入。

真正的掌握证据来自做题后的 ReviewState。

---

# 37. Wrong Book

默认显示：

```text
mastery_state IN (
  unmastered,
  vague
)
```

偏好规则：

```text
follow → 强制显示
ignore → 不显示
auto   → 系统判断
```

`ignore` 不影响：

```text
ReviewState
next_review_date
DailyTask
```

---

# 38. familiar 退出错题本但继续复习

达到：

```text
familiar
```

后自动退出 Wrong Book。

但仍然有：

```text
next_review_date
```

因此：

```text
退出错题本 ≠ 停止复习
```

---

# 39. mastered 也继续复习

`mastered` 只是间隔更长：

```text
14天
→ 再次稳定
→ 30天
```

不是永远不出现。

---

# 40. skipped DailyTaskItem

用户跳过：

```text
DailyTaskItem.status = skipped
```

则：

```text
不创建 Attempt
不更新 ReviewState
```

如果是复习题，原 `next_review_date` 不变，因此后续仍属于 Due Review Pool。

---

# 41. 立即重做

立即重做产生：

```text
attempt_type = practice
```

新的 Attempt。

新 Attempt 完成后可以重新更新 ReviewState。

---

# 42. 连续学习天数

某个业务日期至少存在一条：

```text
completed Attempt
```

则该日算学习日。

只查看知识卡片暂不计入连续做题学习天数。

---

# 43. ReviewState 算法状态

`algorithm_state_json` 在 `review_v2` 中可保存：

```json
{
  "review_stage": 3,
  "last_evaluation_mode": "self",
  "last_performance": null,
  "consecutive_excellent": 0
}
```

Score-Based 时：

```json
{
  "review_stage": 2,
  "last_evaluation_mode": "score",
  "last_performance": "good",
  "consecutive_excellent": 0
}
```

同时：

```text
policy_version = "review_v2"
```

---

# 44. policy_version

`review_v2` 明确代表：

```text
选择题 / SQL → score-based
问答题 → self-assessment
```

未来更换 FSRS 或调整间隔时升级版本，不重写历史 Attempt。

---

# 45. 核心伪代码

```text
function apply_review(attempt, review_state):

    require attempt.status == completed

    if question_type == short_answer:
        selected = attempt.self_assessed_mastery_state
        return apply_self_assessment(selected, review_state)

    if question_type in [single_choice, multiple_choice, sql]:
        ratio = attempt.final_score / attempt.max_score
        performance = classify_score(ratio)
        return apply_score_based(performance, review_state)
```

Self Assessment：

```text
unmastered → stage 0 → 1天
vague      → stage 1 → 2天
familiar   → stage 3 → 7天
mastered   → stage 4 → 14天
再次稳定 mastered → stage 5 → 30天
```

---

# 46. 必须测试的场景

## 选择题

- 首次答错 → unmastered / stage 0 / 1天
- 首次答对不能直接 mastered
- mastered 后答错 → 快速降级

## 问答题

- 提交答案后不能立即更新 ReviewState
- `awaiting_self_assessment` 能恢复
- 自评不会 → 1天
- 自评模糊 → 2天
- 自评基本掌握 → 7天
- 自评熟练掌握 → 14天
- 再次稳定熟练 → 30天
- 问答题不需要 final_score / AI Assessment

## SQL题

- AI 未完成不能更新 ReviewState
- grading_failed 不更新
- disputed 不更新
- 默认接受后进入 completed
- 用户调整后使用调整后的最终分

## 通用

- 重复应用同一个 Attempt 只能更新 ReviewState 一次
- 超期不自动降级
- skip 不修改复习日期
- Wrong Book ignore 不影响复习
- 无题知识点 Mastery Score = NULL
- 未做题按 0 参与有题知识点的覆盖度计算

---

# 47. REVIEW_ALGORITHM v0.2 最终原则

三类题型最终汇入同一个 ReviewState：

```text
选择题
System Grade
     │
     ▼

问答题
Self Assessment
     │
     ▼

SQL题
AI Final Result
     │
     ▼

Review Policy
     ↓
Question Mastery State
     ↓
review_stage
     ↓
next_review_date
```

核心原则：

> **选择题用客观对错验证。**

> **问答题用“先独立回答、再看参考答案、自评掌握状态”验证。**

> **SQL题用 AI 辅助判题，但用户仍可调整最终结果。**

> **不会的高频出现，稳定掌握的逐步拉长间隔。**

> **问答题不为了“智能化”强行加入 AI，优先保证每天学习足够简单、高效。**
