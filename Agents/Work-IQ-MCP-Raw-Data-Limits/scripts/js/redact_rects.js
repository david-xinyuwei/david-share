// Where on the page are the strings that match the given patterns (IDs), and where does the answer end.
// Returns rectangles in CSS pixels; scripts/redact_shot.py paints boxes over them in a copy of the screenshot.
((patterns) => {
  const res = patterns.map(p => new RegExp(p, 'g'));
  const col = document.querySelector('[data-testid="workiq-remote-detail-column"]');
  if (!col) return {error: 'no detail column'};
  const rects = [];
  const each = (text, found) => {
    for (const re of res) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        if (!m[0]) { re.lastIndex++; continue; }
        found(m.index, m[0].length);
      }
    }
  };
  const walker = document.createTreeWalker(col, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    each(n.data, (start, length) => {
      const r = document.createRange();
      r.setStart(n, start);
      r.setEnd(n, start + length);
      for (const b of r.getClientRects()) rects.push({x: b.x, y: b.y, w: b.width, h: b.height, where: 'text'});
    });
  }
  // The request editor is a textarea: its text has no rectangles of its own, so compute them from the font metrics.
  const ta = col.querySelector('textarea[aria-label="Tool arguments as JSON"]');
  if (ta) {
    const cs = getComputedStyle(ta);
    const ctx = document.createElement('canvas').getContext('2d');
    ctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const cw = ctx.measureText('0'.repeat(100)).width / 100;
    let lh = parseFloat(cs.lineHeight);
    if (isNaN(lh)) lh = parseFloat(cs.fontSize) * 1.2;
    const box = ta.getBoundingClientRect();
    const x0 = box.x + parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft) - ta.scrollLeft;
    const y0 = box.y + parseFloat(cs.borderTopWidth) + parseFloat(cs.paddingTop) - ta.scrollTop;
    ta.value.split('\n').forEach((line, i) => {
      each(line, (start, length) => rects.push({x: x0 + start * cw, y: y0 + i * lh, w: length * cw, h: lh, where: 'textarea'}));
    });
  }
  let bottom = 0;
  for (const e of col.querySelectorAll('pre, textarea, button')) bottom = Math.max(bottom, e.getBoundingClientRect().bottom);
  return {rects, contentBottom: bottom, dpr: window.devicePixelRatio, innerWidth: window.innerWidth, innerHeight: window.innerHeight};
})(__ARG__)
