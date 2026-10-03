import { build } from 'esbuild'

const compiled = await build({
  entryPoints: ['scripts/m4-validation-entry.ts'], bundle: true, format: 'esm', platform: 'node', target: 'node18', write: false,
})
const moduleUrl = `data:text/javascript;base64,${Buffer.from(compiled.outputFiles[0].text).toString('base64')}`
const { runM4Validation } = await import(moduleUrl)
const report = runM4Validation()
console.log(JSON.stringify(report, null, 2))
if (!report.passed) process.exitCode = 1
