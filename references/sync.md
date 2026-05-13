# 多机同步

## 模型

`~/.memory/` 本身是一个**私人 git repository**。同步 = `git pull --rebase`、`git commit`、`git push`。
没有自建服务器，没有 CRDT，没有 P2P。
git 已经解决了"多端 markdown 文件版本控制 + 合并"这件事，没必要重发明。

```
machine A ───┐                        ┌─── machine A
             ▼                        ▲
   ~/.memory/                  ~/.memory/
   (git repo) ─── private remote ─── (git repo)
             ▲                        ▼
machine B ───┘                        └─── machine B
```

## 配置

```bash
python3 ~/.claude/skills/chrono-palace-memory/tools/sync.py --init
git -C ~/.memory remote add origin <private-url>
git -C ~/.memory push -u origin main
```

`<private-url>` 可以是：
- GitHub / GitLab / Gitea **private** repo（推荐）
- 自架 `git daemon` / SSH 服务器
- Dropbox / iCloud Drive 路径下的 `--bare` repo（不推荐，git 对云盘不友好）

**绝对不要用 public 仓库。** 记忆含对话、用户身份、未公开偏好。

## 日常同步

```bash
python3 tools/sync.py            # pull-rebase + commit + push
python3 tools/sync.py --status   # 看本地相对 remote 状态
python3 tools/sync.py --dry-run  # 不动手只看会发生什么
```

`tools/sync.py` 在整个流程期间持有 `~/.memory/.lock`（同 forget/migrate/expire 用的同一把锁），所以同机其他工具不会半途插入写。

## 哪些文件**不**进 git

`--init` 自动写一份 `.gitignore` 排除以下机器本地状态（同机才有意义，跨机会引起 merge 冲突）：

- `.lock`（fcntl 锁文件）
- `.cache/`（embedding 缓存 —— 每台机器自己 build）
- `.audit-redactions.log`（机器本地审计追踪）
- `.status.log`（cron 日志）
- 系统/编辑器噪声（`.DS_Store`、`*.swp` 等）

`.migrations-applied` **进**仓库 —— 它代表 schema 状态，应该跨机器一致。

## 冲突处理

当两台机器同时写同一个 daily / session：

```
$ python3 tools/sync.py
Pulling (rebase)...
CONFLICT (content): Merge conflict in daily/2026/05/13.md
pull failed — resolve conflicts manually and re-run sync.
```

按以下方式手动解决：

1. `git -C ~/.memory status` 看冲突文件
2. 打开冲突文件，**保留两端视角**而不是二选一 —— 用本 skill 的 supersede 链模式：
   - 早写的标记 `status: superseded` + `superseded_by: <新条目>`
   - 新条目加 `supersedes: <旧条目>` + `reason: "conflict on multi-machine sync"`
   - 或者两条都保留，加 `evidence` 互相引用，因为同一天的不同会话本来就是可以并列的
3. `git add`、`git rebase --continue`
4. 重跑 `tools/sync.py`

不要简单 `git checkout --theirs` / `--ours`，那会丢信息 —— 本系统的核心承诺就是"不丢历史"。

## 一致性边界

- **同进程并发**：`file_lock` + `atomic_write` 保证（见 `_lib.py` 的 `file_lock()` / `atomic_write()` ）。
- **多机异步并发**：git 的合并模型。两机几乎同时各写一个 session，pull-rebase 时两个 commit 都保留，相安无事。同一文件被两机修改才会产生冲突，需要手动按上述流程处理。
- **不保证**：跨机 sub-second 实时同步。如果你想要"机 A 写完一秒后机 B 立刻能看见"，不应使用这个 skill —— 应该用 server-backed memory。

## 自动化（可选）

把 sync 加到 SessionStart hook（在 daily-status 之后）：

```jsonc
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {"type": "command", "command": "python3 ~/.claude/skills/chrono-palace-memory/tools/sync.py >/dev/null 2>&1 || true"},
          {"type": "command", "command": "python3 ~/.claude/skills/chrono-palace-memory/tools/daily-status.py"}
        ]
      }
    ]
  }
}
```

`|| true` 让网络失败/无 remote 不阻塞 session 启动。Status 仍会显示给 agent。
