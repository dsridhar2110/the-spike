/* ---------- VISUAL 1 · MAP ---------- */
// Two metrics: the two things an applicant actually asks. Muted red -> green,
// polarity flipped per metric so green always means "better for you".
const RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b'];

const METRICS = {
  approval: {
    label: 'Approval rate', unit: '%', lo: 72, hi: 93, flip: false,
    legend: ['72%', '93%'],
    note: 'Share of applications approved, 2018–2025.',
  },
  days: {
    label: 'Decision time', unit: ' days', lo: 44, hi: 64, flip: false,
    legend: ['45 days', '63 days'],
    note: 'Median days from submission to decision. Note how tightly they cluster — '
        + 'the next chart shows why.',
  },
};

function rampColor(t, m) {
  const u = (m && m.flip) ? 1 - t : t;
  const i = Math.round(Math.max(0, Math.min(1, u)) * (RAMP.length - 1));
  return RAMP[i];
}

function drawMap(MAP, metricKey, onPick, selected) {
  const s = document.querySelector('#c-map');
  const m = METRICS[metricKey];
  s.setAttribute('viewBox', `0 0 ${MAP.w} ${MAP.h}`);
  s.innerHTML = '';
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a) => { const e = document.createElementNS(NS, t);
    for (const k in a) e.setAttribute(k, a[k]); return e; };

  for (const f of MAP.features) {
    const v = f[metricKey];
    const has = f.in && v != null;
    const t = has ? (v - m.lo) / (m.hi - m.lo) : 0;
    const broken = !has && f.why && f.why.kind === 'broken';
    const p = mk('path', {
      d: f.d,
      fill: has ? rampColor(t, m) : (broken ? 'var(--flagfill)' : 'var(--nodata)'),
      stroke: broken ? 'var(--bad)' : 'var(--surface)',
      'stroke-width': broken ? 2.5 : 2,
      'stroke-dasharray': broken ? '6 3' : '',
      'stroke-linejoin': 'round',
      class: 'brg live' + (f.name === selected ? ' sel' : '') + (broken ? ' flag' : ''),
    });
    p.addEventListener('click', () => onPick(f.name));
    p.addEventListener('pointerenter', () => onPick(f.name, true));
    s.appendChild(p);
  }
  // label only the two extremes, so the map stays clean
  const live = MAP.features.filter(f => f.in && f[metricKey] != null);
  live.sort((a, b) => b[metricKey] - a[metricKey]);
  for (const f of [live[0], live[live.length - 1]]) {
    const g = mk('g', { class: 'maplab' });
    const tx = mk('text', { x: f.c[0], y: f.c[1] - 2, 'text-anchor': 'middle' });
    tx.textContent = f.name;
    const tv = mk('text', { x: f.c[0], y: f.c[1] + 15, 'text-anchor': 'middle', class: 'big' });
    tv.textContent = f[metricKey] + m.unit;
    g.appendChild(tx); g.appendChild(tv); s.appendChild(g);
  }
}

/* ---------- VISUAL 3 · APPROVAL DROP (aligned bars, green -> red) ---------- */
function drawSlope(link, london, sel, RUSHRATE) {
  const s = document.querySelector('#c-slope');
  const rows = link.filter(d => d.approve_bunched != null && d.approve_not_bunched != null)
                   .slice().sort((a, b) => a.gap_pp - b.gap_pp);
  const W = 880, NAME = 138, RUSH = 196, V1 = 262, X0 = 300, R = 128, T = 62, rh = 34, B = 42;
  const H = T + rows.length * rh + B;
  s.setAttribute('viewBox', `0 0 ${W} ${H}`);
  s.innerHTML = '';
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a) => { const e = document.createElementNS(NS, t);
    for (const k in a) e.setAttribute(k, a[k]); return e; };

  const maxDrop = Math.max(...rows.map(d => Math.abs(d.gap_pp)));
  const pw = W - X0 - R;
  const len = g => (Math.abs(g) / maxDrop) * pw;          // 0 -> full width

  const defs = mk('defs', {});
  rows.forEach((d, i) => {
    // userSpaceOnUse is required: a horizontal line has a zero-height bounding box,
    // which makes the default objectBoundingBox gradient degenerate and render nothing.
    const gr = mk('linearGradient', { id: 'sg' + i, gradientUnits: 'userSpaceOnUse',
      x1: X0, y1: 0, x2: X0 + Math.max(len(d.gap_pp), 6), y2: 0 });
    const [c0, c1] = d.gap_pp < 0 ? ['var(--good)', 'var(--bad)']
                                  : ['var(--good-soft)', 'var(--good-deep)'];
    gr.appendChild(mk('stop', { offset: '0%', 'stop-color': c0 }));
    gr.appendChild(mk('stop', { offset: '100%', 'stop-color': c1 }));
    defs.appendChild(gr);
  });
  s.appendChild(defs);

  // column headers — two stacked lines each, so nothing collides
  [[RUSH, 'on the', 'deadline'], [V1, 'approved', 'normally']].forEach(([xx, l1, l2]) => {
    const a1 = mk('text', { x: xx, y: T - 40, 'text-anchor': 'end', class: 'colhead' });
    a1.textContent = l1; s.appendChild(a1);
    const a2 = mk('text', { x: xx, y: T - 27, 'text-anchor': 'end', class: 'colhead' });
    a2.textContent = l2; s.appendChild(a2);
  });
  const h2 = mk('g', {});
  h2.appendChild(mk('circle', { cx: W - R + 10, cy: T - 31, r: 5, fill: 'var(--bad)' }));
  const e2 = mk('text', { x: W - R + 22, y: T - 27, class: 'slopehead' });
  e2.textContent = 'in the rush'; h2.appendChild(e2);
  s.appendChild(h2);

  const ar = mk('text', { x: X0 + pw / 2, y: H - 12, 'text-anchor': 'middle', class: 'axlabel' });
  ar.textContent = 'length of bar = approval points lost'; s.appendChild(ar);

  rows.forEach((d, i) => {
    const yy = T + i * rh + rh / 2;
    const up = d.gap_pp > 0, isSel = d.borough === sel;
    const w = Math.max(len(d.gap_pp), 6);
    const g = mk('g', { class: 'slope' + (isSel ? ' selected' : '') });

    const nm = mk('text', { x: NAME, y: yy + 5, 'text-anchor': 'end',
      class: 'slopelab' + (isSel ? ' strong' : '') });
    nm.textContent = d.borough; g.appendChild(nm);

    const rr = mk('text', { x: RUSH, y: yy + 5, 'text-anchor': 'end', class: 'slopelab' });
    rr.setAttribute('fill', 'var(--series)');
    rr.setAttribute('font-weight', '640');
    rr.textContent = (RUSHRATE[d.borough] != null ? RUSHRATE[d.borough] + '%' : '—');
    g.appendChild(rr);

    const v1 = mk('text', { x: V1, y: yy + 5, 'text-anchor': 'end', class: 'slopelab strong' });
    v1.setAttribute('fill', up ? 'var(--good-soft)' : 'var(--good)');
    v1.textContent = d.approve_not_bunched.toFixed(0) + '%'; g.appendChild(v1);

    g.appendChild(mk('line', { x1: X0, y1: yy, x2: X0 + w, y2: yy,
      stroke: `url(#sg${i})`, 'stroke-width': 10, 'stroke-linecap': 'round' }));
    g.appendChild(mk('circle', { cx: X0, cy: yy, r: 6,
      fill: up ? 'var(--good-soft)' : 'var(--good)', stroke: 'var(--surface)', 'stroke-width': 2 }));
    g.appendChild(mk('circle', { cx: X0 + w, cy: yy, r: 6,
      fill: up ? 'var(--good-deep)' : 'var(--bad)', stroke: 'var(--surface)', 'stroke-width': 2 }));

    const v2 = mk('text', { x: X0 + w + 14, y: yy + 5, class: 'slopelab strong' });
    v2.setAttribute('fill', up ? 'var(--good-deep)' : 'var(--bad)');
    v2.textContent = `${d.approve_bunched.toFixed(0)}%  ${up ? '+' : ''}${d.gap_pp}`;
    g.appendChild(v2);

    const ti = mk('title', {});
    ti.textContent = `${d.borough}: ${d.approve_not_bunched}% approved normally → `
      + `${d.approve_bunched}% in the rush (${d.gap_pp} points)`;
    g.appendChild(ti);
    s.appendChild(g);
  });

  const ln = mk('text', { x: NAME, y: H - 12, 'text-anchor': 'end', class: 'slopehead' });
  ln.textContent = `London  ${london.approval_not_bunched}% → ${london.approval_bunched}%`;
  s.appendChild(ln);
}

/* ---------- VISUAL 4 · DEVELOPMENT TYPES ---------- */
function drawTypes(rows, base, who) {
  const s = document.querySelector('#c-types');
  const W = 880, L = 210, R = 58, T = 26, rh = 30;
  const d = rows.slice().sort((a, b) => b.approval - a.approval);
  const H = T + d.length * rh + 34;
  s.setAttribute('viewBox', `0 0 ${W} ${H}`);
  s.innerHTML = '';
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a) => { const e = document.createElementNS(NS, t);
    for (const k in a) e.setAttribute(k, a[k]); return e; };
  const lo = 60, hi = 90, pw = W - L - R;
  const x = v => L + ((v - lo) / (hi - lo)) * pw;

  s.appendChild(mk('line', { x1: x(base), x2: x(base), y1: T - 10, y2: H - 30,
    stroke: 'var(--ink-2)', 'stroke-width': 1.5 }));
  const bl = mk('text', { x: x(base), y: T - 16, 'text-anchor': 'middle', class: 'slopehead' });
  bl.textContent = `${who} average ${base}%`; s.appendChild(bl);

  d.forEach((r, i) => {
    const yy = T + i * rh, good = r.approval >= base;
    const nm = mk('text', { x: L - 12, y: yy + 15, 'text-anchor': 'end', class: 'typelab' });
    nm.textContent = r.type; s.appendChild(nm);
    const x0 = Math.min(x(base), x(r.approval)), w = Math.abs(x(r.approval) - x(base));
    s.appendChild(mk('rect', { x: x0, y: yy + 5, width: Math.max(w, 1.5), height: rh - 14, rx: 3,
      fill: good ? 'var(--good)' : 'var(--bad)', 'fill-opacity': .82 }));
    const v = mk('text', { x: x(r.approval) + (good ? 9 : -9), y: yy + 16,
      'text-anchor': good ? 'start' : 'end', class: 'typeval' });
    v.textContent = r.approval + '%'; s.appendChild(v);
    const n = mk('title', {}); n.textContent = `${r.type}: ${r.approval}% approved, ${r.n.toLocaleString('en-GB')} applications`;
    s.appendChild(n);
  });
}


/* ---------- VISUAL 2 · BUNCHING (per borough) ---------- */
function drawBunch(offsets, rec) {
  const s = document.querySelector('#c-bunch');
  const W = 760, H = 250, L = 54, R = 12, T = 30, B = 46;
  s.setAttribute('viewBox', `0 0 ${W} ${H}`);
  s.innerHTML = '';
  const NS = 'http://www.w3.org/2000/svg';
  const mk = (t, a) => { const e = document.createElementNS(NS, t);
    for (const k in a) e.setAttribute(k, a[k]); return e; };
  const c = rec.counts, max = Math.max(...c);
  const pw = W - L - R, ph = H - T - B, bw = pw / c.length;
  const y = v => T + ph - (v / max) * ph;
  const step = Math.pow(10, Math.floor(Math.log10(max))) / 2 || 1;
  for (let v = 0; v <= max; v += step) {
    s.appendChild(mk('line', { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: 'var(--grid)' }));
    const tk = mk('text', { x: L - 8, y: y(v) + 4, 'text-anchor': 'end', class: 'tick' });
    tk.textContent = v >= 1000 ? (v / 1000) + 'k' : v; s.appendChild(tk);
  }
  offsets.forEach((o, i) => {
    const zero = o === 0, x = L + i * bw + 1;
    const r = mk('rect', { x, y: y(c[i]), width: Math.max(bw - 2, 1),
      height: Math.max(ph - (y(c[i]) - T), 1), rx: 2,
      fill: zero ? 'var(--bad)' : 'var(--recede)' });
    const ti = mk('title', {});
    ti.textContent = `${o === 0 ? 'On the deadline' : (o > 0 ? '+' + o : o) + ' days'}: ${c[i].toLocaleString('en-GB')}`;
    r.appendChild(ti); s.appendChild(r);
    if ([-14, 0, 14].includes(o)) {
      const tk = mk('text', { x: x + bw / 2, y: H - B + 18, 'text-anchor': 'middle', class: 'tick' });
      tk.textContent = o === 0 ? 'deadline' : (o > 0 ? '+' + o : o); s.appendChild(tk);
    }
    if (zero) {
      const lb = mk('text', { x: x + bw / 2, y: y(c[i]) - 9, 'text-anchor': 'middle', class: 'dlabel' });
      lb.setAttribute('fill', 'var(--bad)');
      lb.textContent = c[i].toLocaleString('en-GB'); s.appendChild(lb);
    }
  });
  s.appendChild(mk('line', { x1: L, x2: W - R, y1: T + ph, y2: T + ph, stroke: 'var(--axis)' }));
  const ax = mk('text', { x: L + pw / 2, y: H - 10, 'text-anchor': 'middle', class: 'axlabel' });
  ax.textContent = 'days from the deadline the council set itself'; s.appendChild(ax);
  const hd = mk('text', { x: L, y: 16, class: 'slopehead' });
  const n1 = mk('tspan', { fill: 'var(--bad)', 'font-weight': '700' });
  n1.textContent = `${rec.excess}×`;
  hd.appendChild(n1);
  const n2 = mk('tspan', {});
  n2.textContent = ' more than expected on the deadline day';
  hd.appendChild(n2); s.appendChild(hd);
}
