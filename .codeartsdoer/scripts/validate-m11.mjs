import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = process.cwd()
const expectedSkills = ['yunsync-cloud-plan', 'yunsync-deploy', 'yunsync-validate']
const checks = []

function check(name, condition, detail = '') {
  checks.push({ name, ok: Boolean(condition), detail })
}

function read(relative) {
  return readFileSync(resolve(root, relative), 'utf8')
}

const agentPath = '.codeartsdoer/agents/yunsync-cloud-agent.md'
const agent = read(agentPath)
check('agent name matches file', /^name:\s*yunsync-cloud-agent\s*$/m.test(agent))
check('agent supports primary and subagent use', /^mode:\s*all\s*$/m.test(agent))
check('agent protects secrets', /不读取、打印、提交或记录 AK\/SK/.test(agent))
check('agent requires confirmation before cloud mutation', /明确确认前，只允许生成计划/.test(agent))

const status = read('.codeartsdoer/skills/ProjectSkillStatus.txt')
for (const skill of expectedSkills) {
  const path = `.codeartsdoer/skills/${skill}/SKILL.md`
  const content = read(path)
  check(`${skill} name matches directory`, new RegExp(`^name:\\s*${skill}\\s*$`, 'm').test(content))
  check(`${skill} has description`, /^description:\s*\S.+$/m.test(content))
  check(`${skill} enabled for IDE`, new RegExp(`^${skill}=true$`, 'm').test(status))
}

check('cloud plan generator exists', read('.codeartsdoer/skills/yunsync-cloud-plan/scripts/generate-cloud-plan.mjs').includes('仅规划，不创建或购买资源'))
check('validation runner redacts credentials', read('.codeartsdoer/skills/yunsync-validate/scripts/run-validation.mjs').includes('[REDACTED]'))
check('deployment planner is plan only', read('.codeartsdoer/skills/yunsync-deploy/scripts/create-deployment-plan.mjs').includes('plan-only，不创建云资源'))
check('codebase ignore excludes secrets', read('.codeartsdoer/.codebaseignore').includes('credentials.csv'))

for (const item of checks) console.log(`${item.ok ? 'PASS' : 'FAIL'} ${item.name}${item.detail ? ` — ${item.detail}` : ''}`)
const failures = checks.filter(item => !item.ok)
console.log(`\nM11 checks: ${checks.length - failures.length}/${checks.length} passed`)
if (failures.length) process.exit(1)
