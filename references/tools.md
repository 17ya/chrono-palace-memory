# Tools 手册

`tools/` 下的 Python 脚本是 agent 在记忆操作时按场景调用的辅助。**优先用工具，不要纯靠 grep 或目测。**

所有脚本：
- Python 3，仅依赖标准库
- 默认操作 `~/.memory/`，用 `--root` 覆盖
- 退出码：0 成功 / 1 失败或有候选 / 2 调用错误
- 都有 `--help`

## validate.py

**何时用**：每次批量写入完成后、commit 前、CI 中、用户报告"记忆好像不一致"时。

```bash
python3 tools/validate.py
python3 tools/validate.py --json     # 机器可读
python3 tools/validate.py --root /tmp/test-mem  # 指定根目录
```

检查项：必需 frontmatter 字段、`evidence:` 路径存在、`[[name]]` 解析得到、reflection ≥3 evidence、session TTL 与 created_at 一致、confidence/importance 在 [0,1]、MEMORY.md 非空且 ≤200 行、entity_index/keyword_index 覆盖。

退出码 1 = 有错误必须修；warnings 可暂忽略但应该收敛。

## search.py

**何时用**：检索流程的"语义层"实际执行者。任何回答前需要参考过去事实时调用。

```bash
python3 tools/search.py "memory architecture"
python3 tools/search.py --type palace "preferences"
python3 tools/search.py --top 3 --include-superseded "old plan"
```

评分公式（见 [retrieval.md](retrieval.md)）：
```
0.40 * semantic + 0.20 * recency + 0.20 * importance + 0.10 * entity + 0.10 * confidence
```

**已知局限**：当前 semantic 用 query-side recall（命中查询词比例），数据集小时分数容易并列。后续可换 Jaccard 或加 IDF；接口稳定，替换 `score_semantic()` 即可。

## aggregate-daily.py

**何时用**：会话开始时检查昨日 daily 是否缺失；用户问"昨天/前天做了什么"；定期 ledger。

```bash
python3 tools/aggregate-daily.py             # 今天
python3 tools/aggregate-daily.py 2026-05-13  # 指定日期
```

**只产出草稿到 stdout，不自动写文件。** Agent 必须人工复核（dedupe / 分类 / 冲突检测）后再写 `daily/YYYY/MM/DD.md`。原因见 [lifecycle.md](lifecycle.md) 的"daily 写入流程"。

## expire-sessions.py

**何时用**：每日开始时检查；validate 报告有 expired 但未删除文件时。

```bash
python3 tools/expire-sessions.py          # dry-run，只报告
python3 tools/expire-sessions.py --apply  # 真的移动到 sessions/_expired/
```

**铁律**：未填 `promoted_to:` 的 session 即使 expires_at 已过也不会被清理 —— 工具会列为 BLOCKED 并返回退出码 1。先 promote，再清理。

## find-conflicts.py

**何时用**：写入新记忆前；daily 聚合时；用户说"我之前是不是说过 X"。

```bash
python3 tools/find-conflicts.py --topic memory-skill
python3 tools/find-conflicts.py --against /tmp/draft.md
python3 tools/find-conflicts.py --topic preferences --threshold 0.5
```

候选判定：name 完全相同、topic 出现在 `topics:` 列表、出现在 description、或同类型记忆描述 token 重叠 ≥ 阈值。

**不自动决策**。Agent 看 candidate 列表，按 [lifecycle.md](lifecycle.md) 的 supersede 链处理。

## daily-status.py

**何时用**：会话开始时（通过 SessionStart hook 或手工 `/memory-status`）；cron 夜间巡检；任何时候想快速判断"记忆是否健康"。

```bash
python3 tools/daily-status.py             # 人读
python3 tools/daily-status.py --format json   # 机器读
```

报告项：
- MEMORY.md 是否存在
- 昨日 daily 是否已写、是否已 promote
- 今日 session 数
- 跨日未 promote 的 session 列表
- 过期但被 BLOCK 的 session 列表

**零副作用**。退出码 1 表示有 actionable issue，可被 cron 用作告警。

## aggregate-monthly.py / aggregate-yearly.py

**何时用**：每月初聚合上月、每年初聚合上年。模式与 `aggregate-daily.py` 一致，只产生草稿，由 agent 复核后写入 `monthly/YYYY/MM.md` 或 `yearly/YYYY.md`。

```bash
python3 tools/aggregate-monthly.py 2026-05   # 指定月
python3 tools/aggregate-yearly.py 2026       # 指定年
```

Monthly 是**模式提升**的关键时机：跨多日重复出现的模式才能晋升到 `palace/learned_patterns.md`。Yearly 高度浓缩，只保留项目轨迹、稳定偏好、关键决策。

## forget.py

**何时用**：用户明确说"忘掉/删除关于 X 的内容"；或检测到敏感信息泄入需要清理。

```bash
python3 tools/forget.py --topic <term>            # dry-run
python3 tools/forget.py --name <slug> --apply --reason "user requested 2026-05-13"
```

**软删除**：状态改为 `redacted`，body 置空，frontmatter 保留 + 追加 `redacted_at` / `redacted_reason`。审计日志 `~/.memory/.audit-redactions.log`。

`search.py` 自动跳过 redacted。物理删除（`rm`）只在用户**明确**要求"physical delete"时才考虑，且应当二次确认。

## migrate.py

**何时用**：升级 skill 后；CI 验证发现 schema drift；CONTRIBUTING 要求 schema 改动须有 migration 时。

```bash
python3 tools/migrate.py --list           # 看 applied / pending
python3 tools/migrate.py                  # dry-run all pending
python3 tools/migrate.py --apply          # actually run
python3 tools/migrate.py --only <slug>    # 单独跑一条
```

Migration 文件在 `tools/migrations/<YYYY-MM-DD>-<slug>.py`，必须 idempotent。已应用记录在 `~/.memory/.migrations-applied`。

## embed.py

**何时用**：首次安装可选 neural backend 时；大量记忆改动后重建缓存时。

```bash
python3 tools/embed.py --check    # 看依赖是否装好
python3 tools/embed.py            # 增量构建（基于 mtime）
python3 tools/embed.py --full     # 全量重建
python3 tools/embed.py --stats    # 缓存大小 / 覆盖
```

缓存：`~/.memory/.cache/embeddings.sqlite`。模型：`paraphrase-multilingual-MiniLM-L12-v2`（CPM_EMBEDDING_MODEL 可覆盖）。**全程本地，无网络**。

无 cache 或无依赖时 `search.py` 自动 fallback 到 TF-IDF —— 不会破坏 zero-config。

## sync.py

**何时用**：用户在多台机器使用本 skill 想要状态同步。详见 [sync.md](sync.md)。

```bash
python3 tools/sync.py --init      # 一次性：~/.memory 变成 git repo
python3 tools/sync.py --status    # 看本地 vs remote
python3 tools/sync.py             # pull-rebase + commit + push
```

依赖 `git` 命令行 + 用户配置的 **private** remote。整个流程持 `~/.memory/.lock`，与其他写工具互斥。

## 共享库 `_lib.py`

不要直接调用 `_lib.py`。它给所有工具提供：
- 极简 YAML-subset frontmatter 解析（无 PyYAML 依赖）
- `walk(root)` 遍历记忆树（跳过 MEMORY.md / README.md / index/）
- `MemoryFile` 数据类，按属性访问 confidence/importance/evidence/status 等
- `tokenize(text)` —— 拉丁 + CJK 混合分词
- `build_idf(docs)` / `tfidf_vector(tokens, idf)` / `cosine(a, b)` —— TF-IDF 语义评分基础组件
- `file_lock(root)` 上下文管理器 —— 跨进程互斥锁（fcntl on POSIX / msvcrt on Windows）
- `atomic_write(path, content)` —— 写入临时文件后 rename，crash-safe
- `LockTimeout` 异常类型 —— 多机/多进程争锁超时

**任何写工具必须 `with lib.file_lock(root): lib.atomic_write(...)` 组合使用**。新增工具时复用这些原语，不要重复实现 frontmatter 解析、评分、并发控制。
