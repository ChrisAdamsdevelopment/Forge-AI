const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const ROOT_DIR = path.resolve(__dirname, '..', '..');
const LOG_DIR = path.join(os.homedir(), '.forge', 'logs');
const isWindows = process.platform === 'win32';

let ollamaProcess = null;
let backendProcess = null;

fs.mkdirSync(LOG_DIR, { recursive: true });

function spawnWithLogs(name, command, args, options = {}) {
  const outLog = fs.createWriteStream(path.join(LOG_DIR, `${name}.out.log`), { flags: 'a' });
  const errLog = fs.createWriteStream(path.join(LOG_DIR, `${name}.err.log`), { flags: 'a' });

  const child = spawn(command, args, {
    cwd: ROOT_DIR,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: isWindows,
    windowsHide: isWindows,
    ...options,
  });

  child.stdout.on('data', (data) => outLog.write(data));
  child.stderr.on('data', (data) => errLog.write(data));
  child.on('close', (code) => {
    outLog.write(`\n[${new Date().toISOString()}] exited with code ${code}\n`);
    errLog.write(`\n[${new Date().toISOString()}] exited with code ${code}\n`);
  });

  return child;
}

async function isOllamaRunning() {
  try {
    const res = await fetch('http://localhost:11434/api/tags');
    return res.ok;
  } catch {
    return false;
  }
}

async function startOllama() {
  if (await isOllamaRunning()) return;
  if (ollamaProcess && !ollamaProcess.killed) return;
  ollamaProcess = spawnWithLogs('ollama', 'ollama', ['serve']);
}

async function startBackend() {
  if (backendProcess && !backendProcess.killed) return;

  const pythonCmd = isWindows
    ? path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe')
    : path.join(ROOT_DIR, '.venv', 'bin', 'python');

  const command = fs.existsSync(pythonCmd) ? pythonCmd : 'python';
  backendProcess = spawnWithLogs('backend', command, ['implementation/backend/forge/main.py']);
}

function getStatus() {
  return {
    ollama: ollamaProcess && !ollamaProcess.killed ? 'running' : 'stopped',
    backend: backendProcess && !backendProcess.killed ? 'running' : 'stopped',
    backendPort: 9147,
  };
}

function stopAll() {
  for (const proc of [backendProcess, ollamaProcess]) {
    if (proc && !proc.killed) {
      try {
        proc.kill('SIGTERM');
      } catch {
        // no-op
      }
    }
  }
}

module.exports = { startOllama, startBackend, stopAll, getStatus };
