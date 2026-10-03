import { readFile } from 'node:fs/promises'
import { checkTrialEvidence } from './trial-checks.mjs'

const record = JSON.parse(await readFile(new URL('../../docs/M6_TRIAL_RESULTS.json', import.meta.url), 'utf8'))
const report = checkTrialEvidence(record)
console.log(JSON.stringify({ milestone: 'M6', ...report }, null, 2))
if (!report.passed) process.exitCode = 1
