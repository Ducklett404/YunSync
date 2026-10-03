import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { checkProductionData } from './release-checks.mjs'
import { checkTrialEvidence } from './trial-checks.mjs'

// Synthetic fixtures verify the gate only; they are never product content or sign-off evidence.
const env = {
  VITE_DATA_MODE: 'real', YUNSYNC_MINIAPP_APPID: 'wx1234567890abcdef',
  YUNSYNC_LEGAL_ENTITY: '合成门禁单位', YUNSYNC_PRIVACY_CONTACT: 'fixture-contact',
  YUNSYNC_WEATHER_PROVIDER: 'fixture-provider', YUNSYNC_CONTENT_SIGNOFF_VERSION: 'signed-v1',
}
const fixture = {
  env, weatherReady: true, manifest: { 'mp-weixin': { appid: env.YUNSYNC_MINIAPP_APPID, setting: { urlCheck: true } } },
  content: {
    recipes: Object.entries({ '粥': 12, '汤': 12, '菜': 16, '节庆食品': 8 }).flatMap(([category, count]) => Array.from({ length: count }, (_, index) => ({
      id: `${category}-${index}`, name: '合成食谱', category, minutes: 20, servings: 2,
      ingredients: [{ name: '合成食材', amount: '100克', isKey: true, allergenTags: [] }],
      tools: ['锅'], steps: [{ order: 1, action: '合成步骤' }], allergens: [], exclusions: [], substitutions: [],
      source: 'fixture-source', sourceNote: 'fixture-authorization', reviewer: '合成审核者',
      version: 'signed-v1', isDemo: false, reviewStatus: 'approved', updatedAt: '2026-10-04T00:00:00Z',
    }))),
    bundles: Array.from({ length: 8 }, (_, index) => ({
      id: `bundle-${index}`, recipeIds: ['粥-0'], source: 'fixture-source', version: 'signed-v1',
      isDemo: false, reviewStatus: 'approved', updatedAt: '2026-10-04T00:00:00Z',
    })),
  },
}
let checksPassed = 0
const currentContent = JSON.parse(await readFile(new URL('../src/data/m2-content.json', import.meta.url), 'utf8'))
function check(name, change, expected) {
  const input = structuredClone(fixture)
  change(input)
  const report = checkProductionData(input)
  assert.equal(report.passed, expected, `${name}: ${report.errors.join('; ')}`)
  checksPassed++
  console.log(`PASS ${name}`)
}
check('complete synthetic gate fixture', () => {}, true)
check('current DEMO library cannot release even with filled configuration', input => { input.content = currentContent }, false)
check('missing legal entity', input => { input.env.YUNSYNC_LEGAL_ENTITY = '' }, false)
check('placeholder sign-off', input => { input.env.YUNSYNC_CONTENT_SIGNOFF_VERSION = 'demo-signoff' }, false)
check('demo mode', input => { input.env.VITE_DATA_MODE = 'demo' }, false)
check('AppID mismatch', input => { input.manifest['mp-weixin'].appid = 'wx0000000000000000' }, false)
check('domain validation disabled', input => { input.manifest['mp-weixin'].setting.urlCheck = false }, false)
check('weather adapter unavailable', input => { input.weatherReady = false }, false)
check('approved flag cannot hide DEMO content', input => { input.content.recipes[0].isDemo = true }, false)
check('unsigned recipe', input => { input.content.recipes[0].reviewer = '' }, false)
check('recipe quota incomplete', input => { input.content.recipes.pop() }, false)
check('incomplete recipe ingredient', input => { delete input.content.recipes[0].ingredients[0].isKey }, false)
check('disabled recipe referenced by a bundle', input => { input.content.recipes[0].reviewStatus = 'disabled' }, false)
check('draft festival bundle', input => { input.content.bundles[0].reviewStatus = 'draft' }, false)
check('duplicate recipe ID', input => { input.content.recipes[1].id = input.content.recipes[0].id }, false)
const emptyTrial = JSON.parse(await readFile(new URL('../../docs/M6_TRIAL_RESULTS.json', import.meta.url), 'utf8'))
assert.equal(checkTrialEvidence(emptyTrial).passed, false, 'Unexecuted trials must never pass')
checksPassed++
const participants = count => Array.from({ length: count }, (_, index) => ({
  id: `P${String(index + 1).padStart(2, '0')}`, medicalMisunderstanding: false, allergenExclusionConfirmed: true,
  tasks: { today: { completed: true, seconds: 20 }, pantry: { completed: true, seconds: 25 } },
}))
const trialFixture = {
  buildCommit: 'a'.repeat(40), walkthrough: { status: 'completed', date: '2026-10-04', participants: participants(3) },
  closedTrial: { status: 'completed', date: '2026-10-04', participants: participants(10) },
  defectAuditCompleted: true, defects: [],
  deviceChecks: ['weixin-devtools', 'android', 'ios', 'weak-network', 'permissions'].map(id => ({ id, status: 'passed', evidence: 'synthetic-fixture' })),
  signoffs: ['professional-content', 'safety', 'privacy', 'real-users', 'release-owner'].map(role => ({ role, status: 'approved', name: '合成测试人', date: '2026-10-04', evidence: 'synthetic-fixture' })),
}
for (const [name, mutate, expected] of [
  ['complete synthetic trial evidence', () => {}, true],
  ['90% completion boundary', input => { input.closedTrial.participants[0].tasks.today.completed = false; input.closedTrial.participants[0].tasks.pantry.completed = false }, true],
  ['completion below 90%', input => { for (const person of input.closedTrial.participants.slice(0, 2)) { person.tasks.today.completed = false; person.tasks.pantry.completed = false } }, false],
  ['unresolved P1 defect', input => { input.defects.push({ id: 'D1', priority: 'P1', status: 'open' }) }, false],
  ['missing privacy approval', input => { input.signoffs = input.signoffs.filter(item => item.role !== 'privacy') }, false],
  ['safety misunderstanding', input => { input.closedTrial.participants[0].medicalMisunderstanding = true }, false],
]) {
  const input = structuredClone(trialFixture)
  mutate(input)
  assert.equal(checkTrialEvidence(input).passed, expected, name)
  checksPassed++
  console.log(`PASS ${name}`)
}
console.log(JSON.stringify({ milestone: 'M6-preparation', checksPassed, passed: true, releaseApproved: false }))
