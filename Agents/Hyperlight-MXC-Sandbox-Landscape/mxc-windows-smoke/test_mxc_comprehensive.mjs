// MXC processcontainer + hyperlight comprehensive Windows tests.
// Run with: node test_mxc_comprehensive.mjs

import {
  getPlatformSupport,
  createConfigFromPolicy,
  spawnSandboxFromConfig,
  ExperimentalBackends,
} from '@microsoft/mxc-sdk';
import { execFileSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const wxcExe = path.join(__dirname, 'node_modules', '@microsoft', 'mxc-sdk', 'bin', 'x64', 'wxc-exec.exe');

function log(msg) { console.log(`[${new Date().toISOString()}] ${msg}`); }

// === Test 1: Platform probe ===
log('=== TEST 1: Platform Probe ===');
const support = getPlatformSupport();
log(`isSupported: ${support.isSupported}`);
log(`availableMethods: ${JSON.stringify(support.availableMethods)}`);
log(`isolationTier: ${support.isolationTier || 'N/A'}`);
log(`isolationWarnings: ${JSON.stringify(support.isolationWarnings || [])}`);

// === Test 2: wxc-exec --probe ===
log('\n=== TEST 2: wxc-exec --probe ===');
try {
  const probe = JSON.parse(execFileSync(wxcExe, ['--probe'], { encoding: 'utf-8', timeout: 10000 }));
  log(`tier: ${probe.tier}`);
  log(`probes: ${JSON.stringify(probe.probes)}`);
  log(`warnings: ${JSON.stringify(probe.warnings)}`);
} catch (e) {
  log(`FAIL: ${e.message}`);
}

// === Test 3: processcontainer echo (schema 0.4.0, no filesystem) ===
log('\n=== TEST 3: processcontainer echo (0.4.0 AppContainer) ===');
try {
  const stdout = execFileSync(wxcExe, [
    path.join(__dirname, 'processcontainer_hello_0_4_echo_only.json')
  ], { encoding: 'utf-8', timeout: 30000 });
  log(`output: ${stdout.trim()}`);
  log('PASS');
} catch (e) {
  log(`exit code: ${e.status}`);
  log(`stdout: ${(e.stdout || '').trim()}`);
  log(`stderr: ${(e.stderr || '').trim().slice(0, 500)}`);
}

// === Test 4: processcontainer Python (schema 0.4.0) ===
log('\n=== TEST 4: processcontainer Python (0.4.0) ===');
const pythonConfig = {
  version: '0.4.0-alpha',
  containment: 'processcontainer',
  containerId: 'mxc-python-smoke',
  process: {
    commandLine: 'python -c "import sys; print(f\'MXC_PYTHON_OK Python {sys.version}\')"',
    timeout: 30000
  },
  network: { defaultPolicy: 'block' },
  processContainer: {
    name: 'mxc-python-smoke',
    leastPrivilege: false,
    capabilities: [],
    ui: { isolation: 'container', desktopSystemControl: false, systemSettings: 'none', ime: false }
  }
};
try {
  const configB64 = Buffer.from(JSON.stringify(pythonConfig)).toString('base64');
  const stdout = execFileSync(wxcExe, ['--config-base64', configB64], { encoding: 'utf-8', timeout: 30000 });
  log(`output: ${stdout.trim()}`);
  log('PASS');
} catch (e) {
  log(`exit code: ${e.status}`);
  log(`stdout: ${(e.stdout || '').trim()}`);
  log(`stderr: ${(e.stderr || '').trim().slice(0, 500)}`);
}

// === Test 5: processcontainer Node.js ===
log('\n=== TEST 5: processcontainer Node.js (0.4.0) ===');
const nodeConfig = {
  version: '0.4.0-alpha',
  containment: 'processcontainer',
  containerId: 'mxc-node-smoke',
  process: {
    commandLine: 'node -e "console.log(\'MXC_NODE_OK\', process.version, process.arch)"',
    timeout: 30000
  },
  network: { defaultPolicy: 'block' },
  processContainer: {
    name: 'mxc-node-smoke',
    leastPrivilege: false,
    capabilities: [],
    ui: { isolation: 'container', desktopSystemControl: false, systemSettings: 'none', ime: false }
  }
};
try {
  const configB64 = Buffer.from(JSON.stringify(nodeConfig)).toString('base64');
  const stdout = execFileSync(wxcExe, ['--config-base64', configB64], { encoding: 'utf-8', timeout: 30000 });
  log(`output: ${stdout.trim()}`);
  log('PASS');
} catch (e) {
  log(`exit code: ${e.status}`);
  log(`stdout: ${(e.stdout || '').trim()}`);
  log(`stderr: ${(e.stderr || '').trim().slice(0, 500)}`);
}

// === Test 6: hyperlight backend (experimental, post-setup) ===
log('\n=== TEST 6: hyperlight backend (experimental micro-VM) ===');
try {
  const hlConfig = {
    version: '0.7.0-dev',
    containment: 'hyperlight',
    containerId: 'mxc-hyperlight-comprehensive',
    process: {
      commandLine: "import sys, platform; print(f'MXC_HYPERLIGHT_COMPREHENSIVE_OK Python {sys.version.split()[0]} on {platform.system()}')",
      timeout: 30000
    }
  };
  const configB64 = Buffer.from(JSON.stringify(hlConfig)).toString('base64');
  const stdout = execFileSync(wxcExe, ['--experimental', '--config-base64', configB64], {
    encoding: 'utf-8', timeout: 60000,
  });
  log(`output: ${stdout.trim()}`);
  log('PASS');
} catch (e) {
  log(`exit code: ${e.status}`);
  log(`stdout: ${(e.stdout || '').trim()}`);
  log(`stderr: ${(e.stderr || '').trim().slice(0, 500)}`);
}

// === Test 7: hyperlight numpy/pandas ===
log('\n=== TEST 7: hyperlight numpy+pandas (experimental) ===');
try {
  const hlMathConfig = {
    version: '0.7.0-dev',
    containment: 'hyperlight',
    containerId: 'mxc-hyperlight-math',
    process: {
      commandLine: "import numpy as np, pandas as pd; df = pd.DataFrame({'x': np.arange(5), 'y': np.arange(5)**2}); print(df.sum().to_dict())",
      timeout: 60000
    }
  };
  const configB64 = Buffer.from(JSON.stringify(hlMathConfig)).toString('base64');
  const stdout = execFileSync(wxcExe, ['--experimental', '--config-base64', configB64], {
    encoding: 'utf-8', timeout: 60000,
  });
  log(`output: ${stdout.trim()}`);
  log('PASS');
} catch (e) {
  log(`exit code: ${e.status}`);
  log(`stdout: ${(e.stdout || '').trim()}`);
  log(`stderr: ${(e.stderr || '').trim().slice(0, 500)}`);
}

log('\n=== ALL TESTS DONE ===');
