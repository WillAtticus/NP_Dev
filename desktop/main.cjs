const { app, BrowserWindow, dialog, protocol } = require('electron')
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

protocol.registerSchemesAsPrivileged([
  { scheme: 'neuropulse', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } },
])

const projectRoot = path.resolve(__dirname, '..')
const uiRoot = path.join(__dirname, 'ui')
const apiOrigin = 'http://127.0.0.1:8000'
const appOrigin = 'neuropulse://app'
// Keep the unpackaged prototype's Chromium cache/logs under its local project data
// directory. A previous elevated launch can leave the default Roaming cache ACLs
// owned by another token and make the desktop shell exit at startup.
if (!app.isPackaged) {
  app.setPath('userData', path.join(projectRoot, 'data', 'electron-user-data'))
}
let backendProcess = null
let backendLaunchError = null
let ownsBackend = false
let backendLogs = []
let mainWindow = null

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.woff2': 'font/woff2',
  '.json': 'application/json; charset=utf-8',
}

function registerLocalUiProtocol() {
  protocol.handle('neuropulse', async (request) => {
    const url = new URL(request.url)
    if (url.host !== 'app') return new Response('Not found', { status: 404 })

    let requestedPath
    try {
      requestedPath = decodeURIComponent(url.pathname).replace(/^\/+/, '')
    } catch {
      return new Response('Bad path', { status: 400 })
    }
    let filePath = path.resolve(uiRoot, requestedPath || 'index.html')
    if (!filePath.startsWith(`${uiRoot}${path.sep}`) && filePath !== path.join(uiRoot, 'index.html')) {
      return new Response('Forbidden', { status: 403 })
    }
    if (!fs.existsSync(filePath) && !path.extname(filePath)) filePath = path.join(uiRoot, 'index.html')
    try {
      const body = await fs.promises.readFile(filePath)
      return new Response(body, {
        headers: {
          'Content-Type': contentTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
          'Content-Security-Policy': "default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' http://127.0.0.1:8000 ws://127.0.0.1:8000; font-src 'self' data:; worker-src 'self' blob:",
          'X-Content-Type-Options': 'nosniff',
        },
      })
    } catch {
      return new Response('Application files are missing. Rebuild the desktop UI.', { status: 404 })
    }
  })
}

function startBackend() {
  const dataDir = app.isPackaged
    ? path.join(app.getPath('userData'), 'data')
    : path.join(projectRoot, 'data')
  fs.mkdirSync(dataDir, { recursive: true })
  const env = { ...process.env, DATA_DIR: dataDir, NEUROPULSE_BACKEND_URL: apiOrigin }

  if (app.isPackaged) {
    throw new Error('The Windows desktop package does not yet include a bundled Python backend.')
  }

  const venvPython = path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
  const python = process.env.NEUROPULSE_PYTHON || (fs.existsSync(venvPython) ? venvPython : 'python')
  const stdoutPath = path.join(app.getPath('userData'), 'backend.stdout.log')
  const stderrPath = path.join(app.getPath('userData'), 'backend.stderr.log')
  backendLogs = [fs.createWriteStream(stdoutPath, { flags: 'a' }), fs.createWriteStream(stderrPath, { flags: 'a' })]
  backendProcess = spawn(python, [
    '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000', '--log-level', 'info',
  ], { cwd: projectRoot, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  ownsBackend = true
  backendProcess.stdout.pipe(backendLogs[0])
  backendProcess.stderr.pipe(backendLogs[1])
  backendProcess.on('error', (error) => {
    backendLaunchError = error
    fs.appendFile(stderrPath, `\nBackend launch error: ${error.message}\n`, () => {})
  })
}

async function waitForBackend() {
  const deadline = Date.now() + 45000
  while (Date.now() < deadline) {
    if (backendLaunchError) throw new Error(`Could not launch Python backend: ${backendLaunchError.message}`)
    if (backendProcess?.exitCode !== null && backendProcess?.exitCode !== undefined) {
      throw new Error(`Backend process exited with code ${backendProcess.exitCode}.`)
    }
    try {
      const response = await fetch(`${apiOrigin}/api/v1/health`, { signal: AbortSignal.timeout(1200) })
      if (response.ok) return
    } catch { /* Backend is still starting. */ }
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  throw new Error('Backend startup timed out. Check the local Python environment and backend logs.')
}

async function hasBackendAlreadyRunning() {
  try {
    const response = await fetch(`${apiOrigin}/api/v1/health`, { signal: AbortSignal.timeout(900) })
    return response.ok
  } catch {
    return false
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 1100,
    minHeight: 720,
    title: 'NeuroPulse',
    backgroundColor: '#0b1220',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  })
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  mainWindow.webContents.on('will-navigate', (event, target) => {
    try {
      if (new URL(target).origin !== appOrigin) event.preventDefault()
    } catch {
      event.preventDefault()
    }
  })
  mainWindow.on('closed', () => { mainWindow = null })
  mainWindow.loadURL(`${appOrigin}/index.html`)
}

async function launch() {
  registerLocalUiProtocol()
  try {
    if (!fs.existsSync(path.join(uiRoot, 'index.html'))) {
      throw new Error('Desktop UI build is missing. Run npm run build:ui from the desktop folder.')
    }
    if (!await hasBackendAlreadyRunning()) startBackend()
    await waitForBackend()
    createWindow()
  } catch (error) {
    await dialog.showMessageBox({
      type: 'error',
      title: 'Không thể khởi động NeuroPulse',
      message: error.message,
      detail: 'Cài đặt backend theo README rồi chạy lại ứng dụng. Nhật ký backend nằm trong thư mục dữ liệu NeuroPulse của Windows.',
    })
    app.quit()
  }
}

app.whenReady().then(launch)

app.on('window-all-closed', () => app.quit())
app.on('before-quit', () => {
  if (ownsBackend && backendProcess && backendProcess.exitCode === null) backendProcess.kill()
  for (const stream of backendLogs) stream.end()
})

process.on('uncaughtException', (error) => {
  fs.appendFile(path.join(app.getPath('userData'), 'desktop.log'), `${error.stack || error}\n`, () => {})
})
