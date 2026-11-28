// How long does a 300 ms timer take in this page right now (a hidden or sleeping tab delays or freezes timers).
(async () => {
  const t0 = performance.now();
  await new Promise(r => setTimeout(r, 300));
  const t1 = performance.now();
  await new Promise(r => setTimeout(r, 300));
  return {
    visibilityState: document.visibilityState,
    hasFocus: document.hasFocus(),
    firstTimerMs: Math.round(t1 - t0),
    secondTimerMs: Math.round(performance.now() - t1),
    logEntries: (window.__mcpLog || []).length,
    account: (document.querySelector('[data-testid="workiq-account-name"]') || {}).innerText || ''
  };
})()
