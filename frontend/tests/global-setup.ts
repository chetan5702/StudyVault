import type { ChildProcess } from 'node:child_process'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { existsSync } from 'node:fs'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const backendUrl = 'http://127.0.0.1:8011'
const frontendUrl = 'http://127.0.0.1:5174'

const delay = (milliseconds: number) => new Promise(resolve => setTimeout(resolve, milliseconds))

async function available(url: string) {
  try {
    const response = await fetch(url)
    return response.ok
  } catch {
    return false
  }
}

async function waitFor(url: string, process: ChildProcess, label: string) {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    if (process.exitCode !== null) throw new Error(`${label} exited during startup with code ${process.exitCode}.`)
    if (await available(url)) return
    await delay(100)
  }
  throw new Error(`Timed out waiting for ${label} at ${url}.`)
}

async function stop(process: ChildProcess) {
  if (process.exitCode !== null) return
  const exited = new Promise<void>(resolve => process.once('exit', () => resolve()))
  process.kill()
  await Promise.race([exited, delay(5_000)])
  if (process.exitCode === null) {
    process.kill('SIGKILL')
    await Promise.race([exited, delay(5_000)])
  }
}

async function waitForExit(process: ChildProcess, milliseconds: number) {
  if (process.exitCode !== null) return
  await Promise.race([
    new Promise<void>(resolve => process.once('exit', () => resolve())),
    delay(milliseconds),
  ])
}

export default async function globalSetup() {
  if (await available(`${backendUrl}/health`) || await available(frontendUrl)) {
    throw new Error('Browser-test ports 8011 or 5174 are already in use. Stop those processes and retry.')
  }

  const root = path.resolve(frontendRoot, '..')
  const candidates = [
    process.env.STUDYVAULT_TEST_PYTHON,
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    path.join(root, '.venv', 'bin', 'python'),
  ]
  const python = candidates.find(p => p && existsSync(p)) || (process.platform === 'win32' ? 'python' : 'python3')
  const backend = spawn(python, [path.resolve(frontendRoot, '..', 'backend', 'tools', 'e2e_server.py')], {
    cwd: frontendRoot,
    env: process.env,
    stdio: 'inherit',
  })
  let vite: ChildProcess | undefined
  try {
    await waitFor(`${backendUrl}/health`, backend, 'disposable backend')
    vite = spawn(process.execPath, [path.resolve(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', '5174', '--strictPort'], {
      cwd: frontendRoot,
      env: { ...process.env, STUDYVAULT_PROXY_TARGET: backendUrl },
      stdio: 'inherit',
    })
    await waitFor(frontendUrl, vite, 'Vite frontend')
  } catch (error) {
    if (vite) await stop(vite)
    await stop(backend)
    throw error
  }
  const frontend = vite

  return async () => {
    try {
      await fetch(`${backendUrl}/__test__/shutdown`, { method: 'POST' })
    } catch {
      // The process may already have stopped after a setup or test failure.
    }
    await waitForExit(backend, 5_000)
    await Promise.all([stop(frontend), stop(backend)])
  }
}
