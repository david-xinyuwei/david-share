// Retest official-style MXC Python sample using schema 0.4.0-alpha.
// This checks whether the AppContainer fallback path can run Python when
// getAvailableToolsPolicy/readwritePaths are included.

import {
  createConfigFromPolicy,
  getAvailableToolsPolicy,
  getTemporaryFilesPolicy,
  spawnSandboxFromConfig,
} from '@microsoft/mxc-sdk';

const tools = getAvailableToolsPolicy(process.env);
const temp = getTemporaryFilesPolicy();

const config = createConfigFromPolicy(
  {
    version: '0.4.0-alpha',
    filesystem: {
      readonlyPaths: tools.readonlyPaths,
      readwritePaths: temp.readwritePaths,
    },
    network: { allowOutbound: false },
    timeoutMs: 30000,
  },
  'process',
  'official-python-sample-04'
);

config.process.commandLine = 'python -c "import sys; print(\'OFFICIAL_MXC_PYTHON_04_OK\'); print(sys.version)"';

console.log('=== Generated config ===');
console.log(JSON.stringify(config, null, 2));

const child = spawnSandboxFromConfig(config, { usePty: false });
let stdout = '';
let stderr = '';

child.stdout?.on('data', (data) => {
  stdout += data.toString();
  process.stdout.write(data);
});
child.stderr?.on('data', (data) => {
  stderr += data.toString();
  process.stderr.write(data);
});
child.on('close', (code) => {
  console.log('\n=== Final result ===');
  console.log(JSON.stringify({ code, stdout, stderr }, null, 2));
  process.exitCode = code ?? 1;
});
