import { createServer } from 'node:http'
import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import { resolve, extname, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../dist/build/h5/', import.meta.url))
const port = Number(process.env.H5_TEST_PORT || 5186)
const types = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' }
createServer(async (request, response) => {
  try {
    const pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname)
    const path = resolve(root, `.${pathname === '/' ? '/index.html' : pathname}`)
    if (!path.startsWith(resolve(root) + sep)) { response.writeHead(403).end(); return }
    const file = await stat(path)
    if (!file.isFile()) { response.writeHead(404).end(); return }
    response.writeHead(200, { 'Content-Type': types[extname(path)] || 'application/octet-stream', 'Cache-Control': 'no-store' })
    createReadStream(path).pipe(response)
  } catch { response.writeHead(404).end() }
}).listen(port, '127.0.0.1', () => console.log(`H5 test server: http://127.0.0.1:${port}`))
