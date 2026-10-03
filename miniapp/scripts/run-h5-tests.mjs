import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const cwd = fileURLToPath(new URL('../', import.meta.url))
const server = spawn(process.execPath, ['scripts/serve-h5.mjs'], { cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
server.stderr.pipe(process.stderr)
try {
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('H5 test server did not start')), 20000)
    server.once('error', error => { clearTimeout(timer); reject(error) })
    server.once('exit', code => { clearTimeout(timer); reject(new Error(`H5 test server exited: ${code}`)) })
    server.stdout.on('data', chunk => {
      if (chunk.toString().includes('H5 test server:')) { clearTimeout(timer); resolve() }
    })
  })
  const runner = spawn(process.execPath, ['node_modules/@playwright/test/cli.js', 'test'], { cwd, windowsHide: true, stdio: 'inherit' })
  process.exitCode = await new Promise((resolve, reject) => {
    runner.once('error', reject)
    runner.once('exit', code => resolve(code ?? 1))
  })
} finally {
  server.kill()
}
