---
name: yunsync-validate
description: 运行 YunSync 的 TypeScript、M2 至 M6、H5 与微信构建验证并生成脱敏报告。用户要求测试、构建、回归、验收、发布前检查或定位构建失败时使用。
---

# YunSync Validate

## 模式

- quick：类型检查和 M2—M6 工程验证。
- full：quick 加 H5 与微信小程序构建。
- ui：full 加 H5 Playwright 页面回归。

## 命令

```powershell
node .codeartsdoer/skills/yunsync-validate/scripts/run-validation.mjs --quick
node .codeartsdoer/skills/yunsync-validate/scripts/run-validation.mjs --full
node .codeartsdoer/skills/yunsync-validate/scripts/run-validation.mjs --ui
```

报告写入 `docs/competition/generated/M11_VALIDATION_REPORT.md`。

## 处理失败

1. 先读取报告中的首个失败命令和日志摘要。
2. 只修复能由证据定位的问题。
3. 重新运行最小相关验证；通过后再运行原模式。
4. 不得把发布门禁的预期失败改成通过，不得删除安全校验。

## 数据保护

- 报告会对常见凭据格式和环境变量值做遮盖。
- 不在命令中传入真实密钥。
- 不把 `node_modules`、构建产物、Playwright 录像或本机缓存提交到仓库。
