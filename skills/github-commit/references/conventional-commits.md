# Conventional Commits 速查

标准格式：

`type(scope): subject`

其中：

- `type` 必填
- `scope` 选填，但在模块边界清楚时建议保留
- `subject` 使用动词原形，简短、具体、可读

## 常用类型

- `feat`: 新功能
- `fix`: 修复 bug 或异常行为
- `docs`: 文档改动
- `style`: 纯格式调整，不影响逻辑
- `refactor`: 重构，不改变外部行为
- `test`: 测试改动
- `build`: 构建、依赖、打包配置
- `ci`: 持续集成、自动化流程
- `chore`: 杂项维护

## 选择建议

- 有用户可感知的新能力，用 `feat`
- 修错误、补边界条件、修回归，用 `fix`
- README、注释文档、接口说明单独变更，用 `docs`
- 测试文件单独变更，用 `test`
- `go.mod`、`package.json`、`Dockerfile`、构建脚本等，用 `build`
- `.github/workflows/`、发布脚本、CI 配置，用 `ci`
- 只是代码整理且不改变行为，用 `refactor`
- 实在不能更准确归类时，再用 `chore`

## 示例

- `feat(auth): add token refresh endpoint`
- `fix(parser): handle empty input safely`
- `docs(readme): update local setup steps`
- `test(api): add coverage for retry middleware`
- `build(deps): bump gin to v1.10.0`
- `ci(release): run tags on version publish`
- `refactor(store): simplify transaction handling`
- `chore(repo): clean generated fixtures`

## 不推荐写法

- `update code`
- `fix bugs`
- `change stuff`
- `misc`

这些写法的问题是范围不清、行为不清、无法从日志快速理解改动意图。
