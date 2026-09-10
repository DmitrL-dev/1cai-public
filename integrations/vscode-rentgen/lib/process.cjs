'use strict';
const { spawn } = require('node:child_process');
const { join } = require('node:path');
const { MAX_OUTPUT } = require('./core.cjs');

// No shell; only processes created by this runner can be terminated.
function createRunner({ timeout = 30000, maxOutput = MAX_OUTPUT } = {}) {
  const active = new Set();
  let disposed = false;
  function execute(command, args) {
    if (disposed) return Promise.reject(new Error('CLI_DISPOSED'));
    return new Promise((resolve, reject) => {
      const child = spawn(command, args, { windowsHide: true, shell: false, stdio: ['ignore', 'pipe', 'pipe'] });
      let failure = null, size = 0, chunks = [], stderrSize = 0, stopping = null;
      const stop = code => {
        failure ??= new Error(code);
        if (stopping || child.exitCode !== null || child.signalCode !== null || !child.pid) return;
        stopping = new Promise(done => {
          if (process.platform === 'win32') {
            const killer = spawn(join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'),
              ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, shell: false, stdio: 'ignore' });
            killer.once('error', () => { child.kill(); done(); });
            killer.once('close', () => done());
          } else { child.kill('SIGKILL'); done(); }
        });
      };
      const cancel = () => stop('CLI_DISPOSED');
      active.add(cancel);
      const timer = setTimeout(() => stop('CLI_TIMEOUT'), timeout);
      child.stdout.on('data', chunk => {
        size += chunk.length;
        if (size > maxOutput) { chunks = []; stop('CLI_OUTPUT_LIMIT'); }
        else if (!failure) chunks.push(chunk);
      });
      child.stderr.on('data', chunk => { stderrSize += chunk.length; if (stderrSize > 65536) stop('CLI_STDERR_LIMIT'); });
      child.once('error', () => { failure ??= new Error('CLI_START_FAILED'); });
      child.once('close', async code => {
        clearTimeout(timer); active.delete(cancel);
        if (stopping) await stopping;
        if (failure) reject(failure);
        else resolve({ code, stdout: Buffer.concat(chunks) });
      });
    });
  }
  return { execute, dispose() { disposed = true; for (const cancel of active) cancel(); } };
}
module.exports = { createRunner };
