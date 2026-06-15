// Retest the official MXC SDK Python sample pattern.
// Source: https://github.com/microsoft/mxc/blob/main/sdk/README.md
// Pattern: getAvailableToolsPolicy + getTemporaryFilesPolicy + createConfigFromPolicy + spawnSandboxFromConfig.

import {
  createConfigFromPolicy,
  getAvailableToolsPolicy,
  getTemporaryFilesPolicy,
  getPlatformSupport,
  spawnSandboxFromConfig,
} from '@microsoft/mxc-sdk';

function print(title, value) {
  console.log(`\n=== ${title} ===`);
  if (typeof value === 'string') console.log(value);
  else console.log(JSON.stringify(value, null, 2));
}

print('Platform support', getPlatformSupport());

const tools = getAvailableToolsPolicy(process.env);
const temp = getTemporaryFilesPolicy();
print('tools.readonlyPaths', tools.readonlyPaths);
print('temp.readwritePaths', temp.readwritePaths);

const config = createConfigFromPolicy(
  {
    version: '0.5.0-alpha',
    filesystem: {
      readonlyPaths: tools.readonlyPaths,
      readwritePaths: temp.readwritePaths,
    },
    network: { allowOutbound: false },
    timeoutMs: 30000,
  },
  'process',
  'official-python-sample'
);

config.process.commandLine = 'python -c "import sys; print(\'OFFICIAL_MXC_PYTHON_SAMPLE_OK\'); print(sys.version)"';

print('Generated config', config);

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
  print('Final result', { code, stdout, stderr });
  process.exitCode = code ?? 1;
});
