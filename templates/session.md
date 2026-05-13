---
name: session-YYYYMMDD-NNN
description: 一句话总结本次会话发生了什么
type: session
created_at: YYYY-MM-DD
expires_at: YYYY-MM-DD  # created_at + 30 天
confidence: 0.7
importance: 0.0-1.0
status: active
evidence: []  # session 是底层证据，自身无 evidence
promoted_to: []  # 提升到 daily/palace 后回填
topics:
  - topic1
  - topic2
entities_mentioned:
  - entity1
  - entity2
---

# Session Summary

## Topics
本次会话讨论了什么主题。

## Key Decisions
做出的关键决策。

## New Facts Learned
- 事实 1
- 事实 2

## User Preferences Observed
- 观察到的偏好（一次出现 = 临时，不直接进 palace）

## Tasks / Open Loops
- 未完成任务 1
- 未解决问题 1

## Conflicts Detected
- 如果发现与已有记忆冲突，列出来：旧 vs 新

## Verbatim Quotes (optional, only if critical)
> 用户原话，仅当措辞重要时保留

## Promotion Notes
本次会话哪些内容值得提升到 daily/palace/entity，由 daily 流程处理。
