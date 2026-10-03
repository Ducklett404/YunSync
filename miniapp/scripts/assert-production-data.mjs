const required = [
  'YUNSYNC_MINIAPP_APPID',
  'YUNSYNC_LEGAL_ENTITY',
  'YUNSYNC_PRIVACY_CONTACT',
  'YUNSYNC_WEATHER_PROVIDER',
  'YUNSYNC_CONTENT_SIGNOFF_VERSION',
]

const missing = required.filter((name) => !process.env[name])
if (process.env.VITE_DATA_MODE !== 'real') missing.push('VITE_DATA_MODE=real')

if (missing.length) {
  console.error(`Release blocked: missing real-data configuration: ${missing.join(', ')}`)
  process.exit(1)
}

console.log('Real-data release configuration present.')
