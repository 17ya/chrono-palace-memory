---
name: entity-<type>-<slug>
description: 关于这个实体当前已知的状态
type: entity
entity_type: user | project | concept | tool | person
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
confidence: 0.85  # [0,1] —— 通常 0.85+ 才算稳定 entity
importance: 0.0-1.0
status: active
evidence:
  - daily/YYYY/MM/DD.md
  - sessions/YYYY/MM/DD/session_NNN.md
references:
  - palace/projects/xxx.md
  - palace/preferences.md
---

# <Entity Name>

## What
这个实体是什么。一句话定义。

## Current Status
当前状态（active / completed / paused / abandoned）。

## Core Properties / Ideas
- 核心属性 1
- 核心属性 2
- 核心属性 3

## History
- YYYY-MM-DD：实体被首次记录
- YYYY-MM-DD：状态变化
- YYYY-MM-DD：最近一次更新

## Relations
- 相关项目：[[other-entity-name]]
- 相关概念：[[concept-name]]
- 相关人物：[[person-name]]

## Sources
最近被提及的 session/daily：
- daily/YYYY/MM/DD.md
- sessions/YYYY/MM/DD/session_NNN.md
