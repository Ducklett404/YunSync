import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const rootDir = dirname(scriptDir)
const registryPath = join(rootDir, 'config', 'official-sources.json')
const outputDir = join(rootDir, 'official-source-sync')
const snapshotDir = join(outputDir, 'attachments', 'external', 'web')
const reportPath = join(outputDir, 'latest-report.json')
const strict = process.argv.includes('--strict')
const dryRun = process.argv.includes('--dry-run')

const registry = JSON.parse(await readFile(registryPath, 'utf8'))

function shanghaiDate() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function requestUrlFor(source, today) {
  if (source.checkUrlTemplate) {
    return source.checkUrlTemplate.replace('{today}', today)
  }
  return source.checkUrl || source.officialUrl
}

function markdownSnapshot(source, result, fetchedAt) {
  const facts = source.verifiedFacts.map((fact) => `- ${fact}`).join('\n')
  const indicators = (result.indicatorChecks || [])
    .map((item) => `- ${item.indicator}: ${item.matched ? 'matched' : 'missing'}`)
    .join('\n')
  const jsonSample = result.sampleData
    ? `\n## 官方接口样例结果\n\n\`\`\`json\n${JSON.stringify(result.sampleData, null, 2)}\n\`\`\`\n`
    : ''

  return `<!-- source: ${source.authority} -->
<!-- fetched_at: ${fetchedAt} -->
<!-- url: ${source.officialUrl} -->

# ${source.id}

- 官方来源：${source.officialUrl}
- 本次校验地址：${result.requestUrl}
- HTTP 状态：${result.httpStatus ?? 'unavailable'}
- 最终地址：${result.finalUrl || 'unavailable'}
- 同步模式：${source.syncMode}
- 内容 SHA-256：${result.contentHash || 'unavailable'}
- 结果：${result.ok ? 'verified' : 'failed'}

## 已核验事实

${facts}

## 自动指标校验

${indicators || '- 无文本指标；使用JSON键校验或仅校验可用性。'}
${jsonSample}
## 使用边界

${source.usageBoundary}
`
}

async function verifySource(source, today) {
  const requestUrl = requestUrlFor(source, today)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 12000)

  try {
    const response = await fetch(requestUrl, {
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'User-Agent': 'YunSync-Official-Source-Checker/1.0 (+documentation verification)',
        Accept: source.responseType === 'json' ? 'application/json' : 'text/html,application/pdf;q=0.9,*/*;q=0.8',
      },
    })
    const body = await response.text()
    const indicatorChecks = (source.expectedIndicators || []).map((indicator) => ({
      indicator,
      matched: body.includes(indicator),
    }))

    let sampleData
    let jsonKeysOk = true
    if (source.responseType === 'json') {
      sampleData = JSON.parse(body)
      jsonKeysOk = (source.expectedJsonKeys || []).every((key) => Object.hasOwn(sampleData, key))
    }

    const indicatorsOk = indicatorChecks.every((item) => item.matched)
    return {
      id: source.id,
      requestUrl,
      finalUrl: response.url,
      httpStatus: response.status,
      contentType: response.headers.get('content-type'),
      contentLength: body.length,
      contentHash: sha256(body),
      indicatorChecks,
      sampleData,
      ok: response.ok && indicatorsOk && jsonKeysOk,
      error: null,
    }
  } catch (error) {
    return {
      id: source.id,
      requestUrl,
      finalUrl: null,
      httpStatus: null,
      contentType: null,
      contentLength: 0,
      contentHash: null,
      indicatorChecks: [],
      sampleData: null,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    }
  } finally {
    clearTimeout(timer)
  }
}

const startedAt = new Date().toISOString()
const today = shanghaiDate()
const results = []

for (const [index, source] of registry.sources.entries()) {
  if (index > 0) await sleep(1100)
  results.push(await verifySource(source, today))
}

const fetchedAt = new Date().toISOString()
const okCount = results.filter((result) => result.ok).length
const report = {
  schemaVersion: registry.schemaVersion,
  startedAt,
  completedAt: fetchedAt,
  sampleDate: today,
  overallStatus: okCount === results.length ? 'verified' : okCount === 0 ? 'failed' : 'partial',
  summary: {
    total: results.length,
    verified: okCount,
    failed: results.length - okCount,
  },
  results,
  humanOnlyReleaseInputs: registry.humanOnlyReleaseInputs,
}

if (!dryRun) {
  await mkdir(snapshotDir, { recursive: true })
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')

  for (const source of registry.sources) {
    const result = results.find((item) => item.id === source.id)
    const filename = `${sha256(source.officialUrl).slice(0, 8)}.md`
    await writeFile(join(snapshotDir, filename), markdownSnapshot(source, result, fetchedAt), 'utf8')
  }
}

console.log(JSON.stringify(report.summary))
console.log(`overallStatus=${report.overallStatus}`)
console.log(`report=${reportPath}`)

if (strict && report.overallStatus !== 'verified') {
  process.exitCode = 1
}
