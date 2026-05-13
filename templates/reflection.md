---
name: reflection-<slug>
description: agent 从长期交互中抽象出的一条模式
type: reflection
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
confidence: 0.5  # 反思记忆必须 0.5 起步，谨慎升高至 ≥0.85
importance: 0.0-1.0
status: active
evidence:  # 反思记忆必须有至少 3 条证据
  - daily/YYYY/MM/DD.md
  - daily/YYYY/MM/DD.md
  - daily/YYYY/MM/DD.md
evidence_count: 3
related_entities:
  - entities/user.md
---

# Pattern: <一句话描述模式>

## Pattern
agent 观察到的稳定模式。注意：这是 agent 推断的，不是用户直接陈述的。

## Evidence
- YYYY-MM-DD（daily/xxx）：用户表现 / 用户说...
- YYYY-MM-DD：再次观察到...
- YYYY-MM-DD：再次...

## Confidence Trajectory
- 第 1 次观察：confidence 0.3（孤证）
- 第 2 次观察：confidence 0.5（候选模式）
- 第 3 次观察：confidence 0.7（当前）
- 5 次以上：confidence 0.85（稳定模式）

## How to Apply
当 agent 在未来对话中遇到 <某类情况> 时，应该 <如何调整行为>。

## Disconfirming Evidence
如果未来出现以下情况，应**降低**此模式置信度：
- 用户明确否定
- 出现 ≥2 次反例
- 用户行为长期偏离

## Last Reviewed
YYYY-MM-DD：上次复审此模式时的判断
