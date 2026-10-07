import { execFileSync, spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '../../../..')
const miniapp = resolve(root, 'miniapp')
const reportPath = resolve(root, 'docs/competition/generated/M11_VALIDATION_REPORT.md')
const requested = process.argv.find(value => /^--(quick|full|ui)$/.test(value)) || '--quick'
const mode = requested.slice(2)

const commands = [
  ['type-check'],
  ['validate:m2'],
  ['validate:m3'],
  ['validate:m4'],
  ['validate:m5'],
  ['validate:m6'],
]

if (mode === 'full' || mode === 'ui') commands.push(['build:h5'], ['build:mp-weixin'])
if (mode === 'ui') commands.push(['validate:h5'])

function redact(value) {
  return value
    .replace(/(CODEARTS_CLI_(?:AK|SK)|HW_(?:ACCESS|SECRET)_KEY|MAAS_API_KEY|DATABASE_URL|REDIS_URL)\s*[=:]\s*[^\s]+/gi, '$1=[REDACTED]')
    .replace(/Bearer\s+[A-Za-z0-9._~+\/-]+/gi, 'Bearer [REDACTED]')
    .replace(/postgres(?:ql)?:\/\/[^\s]+/gi, 'postgresql://[REDACTED]')
    .replace(/redis:\/\/[^\s]+/gi, 'redis://[REDACTED]')
}

function tail(value, max = 1200) {
  const clean = redact(value || '').trim()
  return clean.length <= max ? clean : `…${clean.slice(-max)}`
}

const results = []
for (const [script] of commands) {
  const started = Date.now()
  const executable = process.platform === 'win32' ? (process.env.ComSpec || 'cmd.exe') : 'npm'
  const args = process.platform === 'win32' ? ['/d', '/s', '/c', 'npm', 'run', script] : ['run', script]
  const result = spawnSync(executable, args, {
    cwd: miniapp,
    encoding: 'utf8',
    env: { ...process.env, CI: '1' },
    maxBuffer: 20 * 1024 * 1024,
    windowsHide: true,
  })
  results.push({
    script,
    status: result.status ?? 1,
    durationMs: Date.now() - started,
    output: tail(`${result.stdout || ''}\n${result.stderr || ''}\n${result.error?.message || ''}`),
  })
  console.log(`${result.status === 0 ? 'PASS' : 'FAIL'} npm run ${script}`)
  if (result.status !== 0) break
}

let commit = 'unknown'
let dirty = true
try {
  commit = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim()
  dirty = execFileSync('git', ['status', '--porcelain', '--untracked-files=normal'], { cwd: root, encoding: 'utf8' }).trim().length > 0
} catch {}

const passed = results.every(result => result.status === 0) && results.length === commands.length
const rows = results.map(result => `| \`npm run ${result.script}\` | ${result.status === 0 ? '通过' : '失败'} | ${(result.durationMs / 1000).toFixed(1)} s |`).join('\n')
const failures = results.filter(result => result.status !== 0)
  .map(result => `### npm run ${result.script}\n\n\`\`\`text\n${result.output || '(无输出)'}\n\`\`\``)
  .join('\n\n')

const report = `# M11 CodeArts 验证报告

- 生成时间：${new Date().toISOString()}
- Git 提交：\`${commit}\`
- 工作树包含未提交变更：${dirty ? '是' : '否'}
- 模式：\`${mode}\`
- 结论：**${passed ? '通过' : '失败'}**

| 命令 | 结果 | 用时 |
|---|---|---:|
${rows}

## 失败摘要

${failures || '无。'}

> 报告不记录环境变量值、访问密钥或连接密码。
`

mkdirSync(dirname(reportPath), { recursive: true })
writeFileSync(reportPath, report, 'utf8')
console.log(`报告: ${reportPath}`)
process.exit(passed ? 0 : 1)
