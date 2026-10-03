import { readFile } from 'node:fs/promises'
import { parse } from 'jsonc-parser'
import { checkProductionData } from './release-checks.mjs'

const content = JSON.parse(await readFile(new URL('../src/data/m2-content.json', import.meta.url), 'utf8'))
const manifest = parse(await readFile(new URL('../src/manifest.json', import.meta.url), 'utf8'))
const report = checkProductionData({ env: process.env, content, manifest })
if (!report.passed) {
  console.error('Release blocked:\n' + report.errors.map(error => `- ${error}`).join('\n'))
  process.exitCode = 1
} else {
  console.log('Real-data configuration and signed content checks passed.')
}
