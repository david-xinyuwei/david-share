/**
 * AOAI Proxy — Bridge between NemoClaw (OpenAI-compatible) and Azure OpenAI
 *
 * NemoClaw sends: Authorization: Bearer <key> + /v1/chat/completions
 * Azure OpenAI expects: api-key: <key> + /openai/deployments/{model}/chat/completions?api-version=...
 *
 * This proxy performs header and path translation so NemoClaw can use Azure OpenAI
 * as its inference backend without any modification to NemoClaw itself.
 *
 * Usage:
 *   # Edit the configuration below, then:
 *   node aoai-proxy.js
 *
 * Author: Xinyu Wei (魏新宇)
 */

const http = require('http');
const https = require('https');
const { URL } = require('url');

// ============================================================
// Configuration — Edit these values for your environment
// ============================================================
const AOAI_BASE = process.env.AOAI_BASE || 'https://<your-aoai-resource>.openai.azure.com';
const AOAI_PATH_PREFIX = process.env.AOAI_PATH_PREFIX || '/openai';
const API_VERSION = process.env.AOAI_API_VERSION || '2025-04-01-preview';
const DEFAULT_MODEL = process.env.AOAI_MODEL || 'gpt-5.4';
const PORT = parseInt(process.env.PROXY_PORT || '9100', 10);
// ============================================================

const server = http.createServer((req, res) => {
  const auth = req.headers['authorization'] || '';
  const apiKey = auth.startsWith('Bearer ') ? auth.slice(7) : auth;

  let targetPath = req.url;
  const urlObj = new URL(req.url, 'http://localhost');

  // Convert OpenAI /v1/chat/completions → AOAI /openai/deployments/{model}/chat/completions
  if (urlObj.pathname === '/v1/chat/completions' || urlObj.pathname === '/chat/completions') {
    targetPath = AOAI_PATH_PREFIX + '/deployments/' + DEFAULT_MODEL + '/chat/completions?api-version=' + API_VERSION;
  }
  // Convert /v1/responses → AOAI /openai/responses
  else if (urlObj.pathname === '/v1/responses' || urlObj.pathname === '/responses') {
    targetPath = AOAI_PATH_PREFIX + '/responses?api-version=' + API_VERSION;
  }
  // Convert /v1/models → AOAI /openai/models
  else if (urlObj.pathname === '/v1/models' || urlObj.pathname === '/models') {
    targetPath = AOAI_PATH_PREFIX + '/models?api-version=' + API_VERSION;
  }
  else {
    const cleanPath = urlObj.pathname.replace(/^\/v1/, '');
    targetPath = AOAI_PATH_PREFIX + cleanPath;
    if (!targetPath.includes('api-version')) {
      targetPath += (targetPath.includes('?') ? '&' : '?') + 'api-version=' + API_VERSION;
    }
  }

  const targetUrl = new URL(targetPath, AOAI_BASE);
  console.log(new Date().toISOString(), req.method, req.url, '->', targetUrl.pathname + targetUrl.search);

  const options = {
    hostname: targetUrl.hostname,
    port: 443,
    path: targetUrl.pathname + targetUrl.search,
    method: req.method,
    headers: { ...req.headers, host: targetUrl.hostname, 'api-key': apiKey }
  };
  delete options.headers['authorization'];
  delete options.headers['connection'];

  const proxyReq = https.request(options, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });
  proxyReq.on('error', (e) => {
    console.error('Proxy error:', e.message);
    res.writeHead(502);
    res.end('Proxy error: ' + e.message);
  });
  req.pipe(proxyReq);
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`AOAI proxy on http://0.0.0.0:${PORT}`);
  console.log(`Target: ${AOAI_BASE}${AOAI_PATH_PREFIX} (model: ${DEFAULT_MODEL})`);
  console.log('Authorization: Bearer → api-key | OpenAI paths → AOAI paths');
});
