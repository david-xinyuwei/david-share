// Records every request the page sends to the Work IQ MCP endpoint, and the bytes that come back.
// It reads a copy of the response stream; the page's own request is not changed.
// The Authorization header is never read: only the request body (JSON-RPC, no secret) is kept.
(() => {
  const VERSION = 2;
  if (window.__mcpRecorder === VERSION) return 'already installed';
  const original = window.__mcpOriginalFetch || window.fetch;
  window.__mcpOriginalFetch = original;
  window.__mcpRecorder = VERSION;
  window.__mcpLog = window.__mcpLog || [];
  const MCP = 'https://workiq.svc.cloud.microsoft/mcp';
  const KEEP = ['content-type', 'request-id', 'client-request-id', 'retry-after', 'date'];
  window.fetch = async function (input, init) {
    const isRequest = typeof Request !== 'undefined' && input instanceof Request;
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (!url.startsWith(MCP)) return original.apply(this, arguments);
    let body = init && typeof init.body === 'string' ? init.body : null;
    if (body === null && isRequest) {
      try { body = await input.clone().text(); } catch (e) { body = null; }
    }
    const entry = {url, method: (init && init.method) || (isRequest ? input.method : 'GET'), sentUtc: new Date().toISOString(),
                   t0: performance.now(), body, chunks: [], done: false};
    window.__mcpLog.push(entry);
    let response;
    try {
      response = await original.apply(this, arguments);
    } catch (e) {
      entry.networkError = String(e);
      entry.done = true;
      throw e;
    }
    entry.status = response.status;
    entry.msToHeaders = Math.round(performance.now() - entry.t0);
    entry.headers = {};
    for (const k of KEEP) { const v = response.headers.get(k); if (v) entry.headers[k] = v; }
    try {
      const reader = response.clone().body.getReader();
      const decoder = new TextDecoder();
      (async () => {
        try {
          for (;;) {
            const {done, value} = await reader.read();
            if (done) break;
            entry.chunks.push(decoder.decode(value, {stream: true}));
            entry.msToLastByte = Math.round(performance.now() - entry.t0);
          }
        } catch (e) {
          entry.streamEnd = String(e);  // the page closes the event stream once it has its answer
        }
        entry.done = true;
      })();
    } catch (e) {
      entry.streamEnd = String(e);
      entry.done = true;
    }
    return response;
  };
  return 'installed';
})()
