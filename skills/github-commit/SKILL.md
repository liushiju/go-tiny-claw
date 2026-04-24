---
name: github-commit
description: 当用户要你检查 git 变更、整理提交边界、按 Conventional Commits 规范生成提交信息、执行 git commit，或在确认后推送到 GitHub 时使用这个 skill。它适用于需要审查 diff、只暂存相关文件、运行必要验证、使用非交互式 git 命令，并可借助脚本自动生成 commit message 草稿的提交流程。
---

# GitHub 提交

当任务涉及提交代码、编写提交信息、准备提交、拆分提交，或把当前分支推送到 GitHub 时，使用这个 skill。

## 目标

产出一个边界清晰、可审查、提交信息准确的 git 提交。提交信息默认采用 Conventional Commits 风格，并且必须和暂存区 diff 一致。

## 基本流程

1. 先检查仓库状态，再决定是否提交。
   - 运行 `git status --short`
   - 按需运行 `git diff --stat`、`git diff -- <path>`、`git diff --cached`
   - 如果不确定仓库风格，运行 `git log --oneline -5`

2. 明确这次提交的边界。
   - 区分本次任务相关改动和仓库里原本就存在的无关改动
   - 不要为了“让工作区干净”而顺手提交无关文件
   - 如果改动混在一起，只暂存与当前任务直接相关的文件

3. 提交前先验证。
   - 运行与改动最接近的检查：测试、lint、构建或定向验证
   - 如果无法运行验证，在最终回复里明确说明
   - 没看过 diff，不要声称提交已经准备好

4. 精确暂存。
   - 优先使用显式路径：`git add path/to/file`
   - 只有在用户明确要求提交当前所有改动时，才考虑整体暂存
   - 暂存后再次检查：`git diff --cached --stat` 或 `git diff --cached`

5. 用 Conventional Commits 生成提交信息。
   - 优先遵循仓库已有风格；如果没有明显风格，使用 Conventional Commits
   - 推荐格式：`type(scope): subject`
   - `subject` 描述行为变化，不写空泛词，不写实现流水账
   - 如果变更较大，可以补充正文说明 `what`、`why`、影响范围

6. 需要时先用脚本起草提交信息，再人工复核。
   - 运行 `python3 skills/github-commit/scripts/generate_commit_message.py`
   - 如果已经明确类型，可传 `--type feat`、`--type fix` 等参数
   - 如果你已经知道更精确的摘要，可传 `--summary "..."` 提升结果质量
   - 脚本输出是草稿，不是免审结果；必须结合暂存 diff 复核

7. 需要时直接用脚本执行非交互式提交。
   - 运行 `python3 skills/github-commit/scripts/commit_staged_changes.py`
   - 预览但不提交时，用 `--dry-run`
   - 需要自动正文时，用 `--with-body`
   - 需要手工正文时，用 `--body "..."` 覆盖自动正文
   - 除非用户明确要求，否则不要进入交互式 git 流程

8. 按需推送。
   - 只有用户明确要求 push、提交到远端、同步 GitHub 时才推送
   - 先确认当前分支：`git branch --show-current`
   - 默认使用 `git push origin HEAD`
   - 如果 push 需要网络或提权，走正常审批流程

## Conventional Commits 规则

不确定类型时，先看暂存 diff，再参考 [conventional-commits.md](./references/conventional-commits.md)。

- `feat`: 新功能或新增能力
- `fix`: 缺陷修复、错误处理修复、回归修复
- `docs`: 纯文档改动
- `test`: 测试新增或测试调整
- `refactor`: 不改变外部行为的重构
- `build`: 构建系统、依赖、包管理配置
- `ci`: CI/CD、GitHub Actions、发布流水线
- `chore`: 其他不属于以上类别的维护性改动

选择规则：

- 改动主要影响用户能力或行为时，优先 `feat` / `fix`
- 只有文档变更时，用 `docs`
- 只有测试变更时，用 `test`
- 依赖文件、构建脚本、打包配置变更时，用 `build`
- 工作流和自动化脚本变更时，用 `ci`
- 无法准确归入行为类改动时，再考虑 `chore`

## 自动生成脚本

生成脚本路径：

`skills/github-commit/scripts/generate_commit_message.py`

默认行为：

- 读取当前暂存区文件和变更统计
- 自动推断一个 `type`
- 自动推断一个可选 `scope`
- 生成一个 Conventional Commits 风格标题
- 可选附带正文草稿

常用示例：

```bash
python3 skills/github-commit/scripts/generate_commit_message.py
python3 skills/github-commit/scripts/generate_commit_message.py --type fix
python3 skills/github-commit/scripts/generate_commit_message.py --summary "add retry handling for webhook delivery"
python3 skills/github-commit/scripts/generate_commit_message.py --with-body
```

执行提交流程脚本：

`skills/github-commit/scripts/commit_staged_changes.py`

常用示例：

```bash
python3 skills/github-commit/scripts/commit_staged_changes.py --dry-run
python3 skills/github-commit/scripts/commit_staged_changes.py
python3 skills/github-commit/scripts/commit_staged_changes.py --type fix --with-body
python3 skills/github-commit/scripts/commit_staged_changes.py --summary "handle empty input safely"
```

## 安全边界

- 不要提交密钥、凭据、生成噪音或无关文件
- 不要改历史，不要 `amend`，不要 `force-push`，除非用户明确要求
- 如果与当前任务相关的文件里出现未预期改动，先读懂，再决定如何并存
- 如果提交边界不清晰，采用最窄的安全假设，并在最终回复说明

## 快速命令模板

检查并暂存：

```bash
git status --short
git diff --stat
git add path/to/file
git diff --cached --stat
```

生成提交信息草稿：

```bash
python3 skills/github-commit/scripts/generate_commit_message.py --with-body
```

预览自动提交命令：

```bash
python3 skills/github-commit/scripts/commit_staged_changes.py --dry-run --with-body
```

提交：

```bash
python3 skills/github-commit/scripts/commit_staged_changes.py
```

带正文提交：

```bash
python3 skills/github-commit/scripts/commit_staged_changes.py \
  --type fix \
  --body "Avoid panics on empty payloads and return a typed error instead."
```

推送：

```bash
git branch --show-current
git push origin HEAD
```

## 最终回复

任务完成后，最终回复应包含：

- 本次实际提交了什么，或已经准备好什么
- 如果创建了 commit，给出提交哈希
- 是否运行了验证
- 是否已推送到远端
- 是否有跳过的检查、未纳入提交的文件，或已知风险
