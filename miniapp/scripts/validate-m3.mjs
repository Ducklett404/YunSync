import { build } from 'esbuild'

const compiled = await build({
  entryPoints: ['scripts/m3-validation-entry.ts'],
  bundle: true,
  format: 'esm',
  platform: 'node',
  target: 'node18',
  write: false,
})

const source = compiled.outputFiles[0].text
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
const { runM3Validation } = await import(moduleUrl)
const report = runM3Validation()

console.log(JSON.stringify(report, null, 2))
if (!report.passed) process.exitCode = 1
