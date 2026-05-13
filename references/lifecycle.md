# 生命周期：衰减、提升与冲突

## 三层衰减流

```
[Session Raw]         30 天         [Daily Memory]      30 天         [Monthly Summary]    1 年         [Yearly Snapshot]
原始会话摘要      ─────────────▶   每日浓缩            ─────────────▶  月度模式提取        ─────────────▶  年度高层轨迹
sessions/         压缩抽取         daily/              聚合           monthly/             浓缩            yearly/
↓ 删除原始                          ↓ 长期保留                          ↓ 长期保留                           ↓ 永久保留
```

**删除的不是信息，是低价值细节。** 抽象化的稳定信息一路向上保留。

## 每个阶段的处理

### Session（会话）

**何时写入**：每次对话结束（或长对话进行中的重要节点）

**何时删除**：`created_at + 30 天`

**TTL 处理**：
- 30 天到期前必须已被压缩进 daily
- 压缩后原文件可删除
- 删除前在 daily 文件的 `evidence` 列表里留一条 `<expired> sessions/2026/05/13/session_001.md` 标记

### Daily（每日）

**何时写入**：当天结束时；如果跨天没写，下次会话开始时回填昨天的

**何时压缩**：当月结束 + 1 个月后压缩进 monthly

**Daily 写入流程**：

```
1. 列出当天所有 session_NNN.md
2. 提取每个 session 的：
   - 重要事件
   - 新提取的偏好/事实/决策
   - 未解决问题
3. 去重合并
4. 写入 daily/YYYY/MM/DD.md
5. 检测与现有 entity/palace 的冲突 → 走冲突处理流程
6. 把高重要度的 facts 提升到 entity/palace
```

### Monthly（每月）

**何时写入**：每月第一天，处理上月

**内容**：
- 当月重要事件清单
- 当月新增/废弃的偏好与决策
- 当月活跃项目状态变化
- 当月未解决问题

### Yearly（每年）

**何时写入**：每年第一天

**内容**：
- 全年项目轨迹
- 长期偏好的形成 / 稳定 / 变化
- 重大决策档案

## 提升规则（一次出现 → 长期偏好）

| 出现次数 | 储存层 | confidence | status |
|---------|--------|-----------|--------|
| 1 次 | session | 0.3-0.5 | tentative |
| 2 次 | daily + entity 候选 | 0.5-0.7 | tentative |
| 3 次未被纠正 | palace 偏好 + entity 稳定 | 0.85+ | active |
| 5 次以上 + 跨多日 | reflection 模式 | 0.9+ | active |

**关键**：证据次数靠 `evidence` 数组长度判断。每次出现 append 一条路径，不替换。

## 降级与废弃

| 触发 | 操作 |
|------|------|
| 用户明确纠正 | 旧记忆立即 `status: superseded`，新记忆 `supersedes: <旧 name>` |
| 长期未被引用（>90 天）| 降级为 `status: archived`，不参与默认检索 |
| 与新事实冲突且无法调和 | 旧的 `superseded`，附 `reason` 字段说明 |
| 用户要求"忘记" | 改 `status: redacted`，内容置空，保留 frontmatter 用于审计 |

**永远不要直接 rm 一个长期记忆文件。** 用 status 标记 + 软删除。原因：审计、回溯、用户问"我之前说过 X 吗？"时还能查到。

## 冲突处理：保留链而非覆盖

旧记忆：

```yaml
---
name: pref-build-tool-2026-q1
description: 用户偏好 Vite 作为构建工具
type: entity
status: superseded
confidence: 0.85
created_at: 2026-02-10
updated_at: 2026-05-13
superseded_by: pref-build-tool-2026-q2
evidence:
  - daily/2026/02/10.md
  - daily/2026/03/15.md
---

用户在 Q1 一致表示偏好 Vite。
```

新记忆：

```yaml
---
name: pref-build-tool-2026-q2
description: 用户改为偏好 Bun 作为构建工具
type: entity
status: active
confidence: 0.9
created_at: 2026-05-13
supersedes: pref-build-tool-2026-q1
reason: >
  用户在 2026-05-13 明确表示由于性能原因改用 Bun。
evidence:
  - sessions/2026/05/13/session_002.md
---

用户改为偏好 Bun。
```

这样 agent 能回答：

> "你以前偏好 Vite（Q1 多次提及），但在 2026-05-13 因为性能改成了 Bun。如果你想回到 Vite 我也可以记录这次变化。"

## Conflict Detection 时机

每次写入 daily 时，跑一次：

```python
for new_fact in daily.extracted_facts:
    for existing in palace_and_entities:
        if existing.topic == new_fact.topic and existing.status == 'active':
            if existing.content != new_fact.content:
                flag_conflict(existing, new_fact)
```

发现冲突后**不要自动决策**：

1. 标记两条记忆 `status: conflict_pending`
2. 在 `palace/open_loops.md` 加一条："冲突待解决：X vs Y，evidence ..."
3. 下次相关对话中向用户确认
4. 用户确认后走 supersede 流程

## 索引一致性

每次记忆状态变化（active ↔ superseded ↔ archived），必须同步：

| 索引 | 是否更新 |
|------|---------|
| `MEMORY.md` | active → archived 时移除条目 |
| `index/keyword_index.md` | 关键词不变则不动 |
| `index/entity_index.md` | 实体重命名时更新 |
| 反链（其他文件 `evidence:` 引用本文件）| 不需要更新，保留历史链 |

## 例外：用户明确请求删除

```
用户："请把我说过的关于 X 的内容彻底删除。"
```

操作：

1. 找出所有 `topic == X` 或 `references X` 的文件
2. 一一改成 `status: redacted`，内容置空
3. **不要**真正 `rm`（除非用户明说"物理删除"）
4. 回复用户列出受影响的路径，请求确认是否物理删除
5. 如确认，再 `rm` 并在 `MEMORY.md` 加一条 "Redacted at YYYY-MM-DD per user request" 元记录

敏感信息（密钥、个人证件号）出现时直接走 redacted 流程，无需用户主动要求。
