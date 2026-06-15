import {
  createConfigFromPolicy,
  getPlatformSupport,
  ExperimentalBackends,
} from '@microsoft/mxc-sdk';

console.log('platformSupport');
console.log(JSON.stringify(getPlatformSupport(), null, 2));

console.log('experimentalBackends');
console.log(JSON.stringify(ExperimentalBackends));

const policy = {
  version: '0.6.0-alpha',
  timeoutMs: 30000,
  network: { allowOutbound: false },
};

console.log('processConfig');
console.log(JSON.stringify(createConfigFromPolicy(policy, 'process', 'mxc-sdk-process-smoke'), null, 2));

try {
  console.log('hyperlightConfig');
  console.log(JSON.stringify(createConfigFromPolicy(policy, 'hyperlight', 'mxc-sdk-hyperlight-smoke'), null, 2));
} catch (error) {
  console.log('hyperlightConfigError');
  console.log(error?.stack || String(error));
}