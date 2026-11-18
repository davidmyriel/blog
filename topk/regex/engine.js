// Sparse-gram regex search, small enough to run in a browser.
// all() and covering() are copied from the TopK blog's SparseGramExplorer widget.
// The regex planner follows the rules described in the blog post; it is a sketch, not TopK's code.
(function (root) {
  const MIN = 3, MAX = 8;          // gram lengths kept in the index
  const MAX_EXACT = 16;            // cap on exact strings tracked per regex node

  // ---------- CRC32 bigram weights ----------
  const TABLE = Array.from({ length: 256 }, (_, v) => {
    let c = v;
    for (let b = 0; b < 8; b++) c = c & 1 ? (c >>> 1) ^ 0xedb88320 : c >>> 1;
    return c >>> 0;
  });
  const enc = new TextEncoder();
  const weightCache = new Map();
  function crc32(s) {
    let w = weightCache.get(s);
    if (w !== undefined) return w;
    let c = 0xffffffff;
    for (const byte of enc.encode(s)) c = (c >>> 8) ^ TABLE[(c ^ byte) & 0xff];
    w = ~c >>> 0;
    weightCache.set(s, w);
    return w;
  }
  function bigrams(s) {
    const chars = [...s];
    return chars.slice(0, -1).map((ch, index) => ({ index, text: ch + chars[index + 1], weight: crc32(ch + chars[index + 1]) }));
  }
  const slice = (chars, start, rightBigram) => ({ start, end: rightBigram + 2, text: chars.slice(start, rightBigram + 2).join('') });

  // ---------- SparseGram::all(): every gram stored at index time ----------
  function all(s, min = MIN, max = MAX) {
    const chars = [...s], bg = bigrams(s), out = [];
    const minD = min - 2, maxD = max - 2;
    for (let right = 1; right < bg.length; right++) {
      if (minD <= 1) out.push(slice(chars, right - 1, right));
      let interior = bg[right - 1].weight;
      const leftLimit = Math.max(0, right - maxD);
      for (let left = right - 2; left >= leftLimit; left--) {
        if (interior >= bg[right].weight) break;
        if (right - left >= minD && bg[left].weight >= interior) out.push(slice(chars, left, right));
        interior = Math.max(interior, bg[left].weight);
      }
    }
    return out.sort((a, b) => a.start - b.start || a.end - b.end);
  }

  // ---------- SparseGram::covering(): the smaller set used at query time ----------
  function covering(s, min = MIN, max = MAX) {
    const chars = [...s], bg = bigrams(s);
    if (!bg.length) return [];
    const out = [], stack = [bg[0]];
    const minD = min - 2, maxD = max - 2;
    for (const cur of bg.slice(1)) {
      while (stack.length > 1 && cur.index - stack[0].index > maxD) {
        const prev = stack.shift(), next = stack[0];
        if (next.index - prev.index >= minD) out.push(slice(chars, prev.index, next.index));
      }
      while (stack.length > 1 && stack[stack.length - 1].weight < cur.weight) stack.pop();
      const prev = stack[stack.length - 1];
      const emit = cur.weight > prev.weight;
      if (emit) stack.pop();
      stack.push(cur);
      if (emit && cur.index - prev.index >= minD) out.push(slice(chars, prev.index, cur.index));
    }
    while (stack.length > 1) {
      const cur = stack.pop(), prev = stack[stack.length - 1];
      if (cur.index - prev.index >= minD) out.push(slice(chars, prev.index, cur.index));
    }
    return out.sort((a, b) => a.start - b.start || a.end - b.end);
  }
  const trigrams = s => { const c = [...s], out = []; for (let i = 0; i + 3 <= c.length; i++) out.push({ start: i, end: i + 3, text: c.slice(i, i + 3).join('') }); return out; };

  // ---------- index ----------
  function buildIndex(docs) {
    const postings = new Map();
    docs.forEach((doc, id) => {
      for (const g of all(doc.toLowerCase())) {
        let p = postings.get(g.text);
        if (!p) postings.set(g.text, p = []);
        if (p[p.length - 1] !== id) p.push(id);
      }
    });
    return { docs, postings, size: docs.length };
  }

  // ---------- regex parser (a practical subset; anything else falls back to a scan) ----------
  function parse(src) {
    let i = 0, ignoreCase = false;
    if (src.startsWith('(?i)')) { ignoreCase = true; i = 4; }
    const peek = () => src[i], eof = () => i >= src.length;
    function alt() {
      const xs = [cat()];
      while (peek() === '|') { i++; xs.push(cat()); }
      return xs.length === 1 ? xs[0] : { t: 'alt', xs };
    }
    function cat() {
      const xs = [];
      while (!eof() && peek() !== '|' && peek() !== ')') xs.push(repeat());
      return { t: 'cat', xs };
    }
    function repeat() {
      let x = atom();
      for (;;) {
        const c = peek();
        let min, max;
        if (c === '?') { min = 0; max = 1; i++; }
        else if (c === '*') { min = 0; max = Infinity; i++; }
        else if (c === '+') { min = 1; max = Infinity; i++; }
        else if (c === '{' && /^\{\d+(,\d*)?\}/.test(src.slice(i))) {
          const m = src.slice(i).match(/^\{(\d+)(,(\d*))?\}/);
          i += m[0].length;
          min = +m[1]; max = m[2] ? (m[3] === '' ? Infinity : +m[3]) : min;
        } else return x;
        if (peek() === '?') i++; // lazy quantifier: same matches for our purposes
        x = { t: 'rep', x, min, max };
      }
    }
    function atom() {
      const c = src[i++];
      if (c === '(') {
        if (src.startsWith('?:', i)) i += 2;
        else if (src[i] === '?') throw new Error('unsupported group');
        const x = alt();
        if (src[i++] !== ')') throw new Error('unclosed group');
        return x;
      }
      if (c === '[') return cls();
      if (c === '.') return { t: 'any' };
      if (c === '^' || c === '$') return { t: 'empty' };
      if (c === '\\') {
        const e = src[i++];
        if (e === undefined) throw new Error('trailing backslash');
        if ('dwsDWS'.includes(e)) return { t: 'any' };
        if (e === 'b' || e === 'B') return { t: 'empty' };
        if (e === 'n') return { t: 'lit', c: '\n' };
        if (e === 't') return { t: 'lit', c: '\t' };
        if (/[a-zA-Z0-9]/.test(e)) throw new Error('unsupported escape');
        return { t: 'lit', c: e };
      }
      if (c === ')' || c === '*' || c === '+' || c === '?') throw new Error('unexpected ' + c);
      return { t: 'lit', c };
    }
    function cls() {
      let neg = false;
      if (src[i] === '^') { neg = true; i++; }
      const set = new Set();
      let first = true, broad = false;
      while (i < src.length && (src[i] !== ']' || first)) {
        first = false;
        let a = src[i++];
        if (a === '\\') { const e = src[i++]; if ('dwsDWS'.includes(e)) { broad = true; continue; } a = e; }
        if (src[i] === '-' && src[i + 1] && src[i + 1] !== ']') {
          i++;
          let b = src[i++];
          if (b === '\\') b = src[i++];
          const span = b.charCodeAt(0) - a.charCodeAt(0);
          if (span > 26) broad = true;
          else for (let k = 0; k <= span; k++) set.add(String.fromCharCode(a.charCodeAt(0) + k));
        } else set.add(a);
      }
      if (src[i++] !== ']') throw new Error('unclosed class');
      if (neg || broad) return { t: 'any' };
      return { t: 'cls', chars: set };
    }
    const ast = alt();
    if (!eof()) throw new Error('unexpected ' + peek());
    return { ast, ignoreCase };
  }

  // ---------- planner: what must every match contain? ----------
  const TRUE = { op: 'all' };
  const isTrue = e => e.op === 'all';
  function AND(xs) {
    const flat = [];
    for (const x of xs) { if (isTrue(x)) continue; if (x.op === 'and') flat.push(...x.xs); else flat.push(x); }
    const seen = new Set(), out = flat.filter(x => { const k = key(x); if (seen.has(k)) return false; seen.add(k); return true; });
    return out.length === 0 ? TRUE : out.length === 1 ? out[0] : { op: 'and', xs: out };
  }
  function OR(xs) {
    if (xs.some(isTrue) || !xs.length) return TRUE;
    const flat = [];
    for (const x of xs) { if (x.op === 'or') flat.push(...x.xs); else flat.push(x); }
    const seen = new Set(), out = flat.filter(x => { const k = key(x); if (seen.has(k)) return false; seen.add(k); return true; });
    return out.length === 1 ? out[0] : { op: 'or', xs: out };
  }
  const key = e => e.op === 'gram' ? 'g:' + e.g : e.op === 'all' ? '*' : e.op + '(' + e.xs.map(key).join(',') + ')';

  function plan(src, gramsOf = covering) {
    let parsed;
    try { parsed = parse(src); } catch (err) { return { expr: TRUE, error: err.message, ignoreCase: src.startsWith('(?i)') }; }
    const cross = (A, B) => { const out = new Set(); for (const a of A) for (const b of B) out.add(a + b); return out; };
    const toExpr = info => {
      if (!info.exact) return info.expr;
      return OR([...info.exact].map(s => [...s].length < MIN ? TRUE : AND(gramsOf(s).map(g => ({ op: 'gram', g: g.text })))));
    };
    function analyze(n) {
      switch (n.t) {
        case 'lit': return { exact: new Set([n.c.toLowerCase()]) };
        case 'cls': {
          const set = new Set([...n.chars].map(c => c.toLowerCase()));
          return set.size <= 4 ? { exact: set } : { exact: null, expr: TRUE };
        }
        case 'any': return { exact: null, expr: TRUE };
        case 'empty': return { exact: new Set(['']) };
        case 'cat': {
          let acc = new Set(['']);
          const exprs = [];
          for (const x of n.xs.map(analyze)) {
            if (x.exact) {
              if (acc && acc.size * x.exact.size <= MAX_EXACT) acc = cross(acc, x.exact);
              else { if (acc) exprs.push(toExpr({ exact: acc })); acc = x.exact; }
            } else {
              if (acc) exprs.push(toExpr({ exact: acc }));
              acc = null;
              exprs.push(x.expr);
            }
          }
          if (!exprs.length) return { exact: acc };
          if (acc) exprs.push(toExpr({ exact: acc }));
          return { exact: null, expr: AND(exprs) };
        }
        case 'alt': {
          const xs = n.xs.map(analyze);
          if (xs.every(x => x.exact)) {
            const u = new Set(xs.flatMap(x => [...x.exact]));
            if (u.size <= MAX_EXACT) return { exact: u };
          }
          return { exact: null, expr: OR(xs.map(toExpr)) };
        }
        case 'rep': {
          const x = analyze(n.x);
          if (n.min === 0) {
            if (n.max === 1 && x.exact && x.exact.size < MAX_EXACT) return { exact: new Set(['', ...x.exact]) };
            return { exact: null, expr: TRUE }; // may match nothing, so it cannot be required
          }
          if (n.max === n.min && n.min <= 3 && x.exact && Math.pow(x.exact.size, n.min) <= MAX_EXACT) {
            let acc = new Set(['']);
            for (let k = 0; k < n.min; k++) acc = cross(acc, x.exact);
            return { exact: acc };
          }
          return { exact: null, expr: toExpr(x) }; // at least one copy must appear
        }
      }
    }
    const info = analyze(parsed.ast);
    return { expr: toExpr(info), ignoreCase: parsed.ignoreCase };
  }

  // ---------- execution ----------
  function intersect(a, b) { const out = []; let i = 0, j = 0; while (i < a.length && j < b.length) { if (a[i] === b[j]) { out.push(a[i]); i++; j++; } else if (a[i] < b[j]) i++; else j++; } return out; }
  function union(a, b) { const out = []; let i = 0, j = 0; while (i < a.length || j < b.length) { if (j >= b.length || (i < a.length && a[i] < b[j])) out.push(a[i++]); else if (i >= a.length || b[j] < a[i]) out.push(b[j++]); else { out.push(a[i]); i++; j++; } } return out; }
  function evaluate(index, e) {
    if (isTrue(e)) return null; // null means "every document"
    if (e.op === 'gram') return index.postings.get(e.g) || [];
    const parts = e.xs.map(x => evaluate(index, x));
    if (e.op === 'and') {
      const lists = parts.filter(p => p !== null).sort((a, b) => a.length - b.length);
      return lists.length ? lists.reduce(intersect) : null;
    }
    return parts.some(p => p === null) ? null : parts.reduce(union);
  }
  function toRegExp(src, ignoreCase) {
    return new RegExp(src.startsWith('(?i)') ? src.slice(4) : src, ignoreCase ? 'i' : '');
  }
  function search(index, src, gramsOf = covering) {
    const p = plan(src, gramsOf);
    let re = null, reError = null;
    try { re = toRegExp(src, p.ignoreCase); } catch (err) { reError = err.message; }
    const cand = evaluate(index, p.expr);
    const ids = cand === null ? index.docs.map((_, i) => i) : cand;
    const matches = re ? ids.filter(i => re.test(index.docs[i])) : [];
    return { plan: p.expr, planError: p.error, regexError: reError, scan: cand === null, candidates: ids, matches };
  }
  function describe(e) {
    if (isTrue(e)) return 'scan everything';
    if (e.op === 'gram') return JSON.stringify(e.g);
    return e.xs.map(x => (x.op === 'gram' || x.op === 'all' ? describe(x) : '(' + describe(x) + ')')).join(e.op === 'and' ? ' AND ' : ' OR ');
  }

  const api = { MIN, MAX, crc32, bigrams, all, covering, trigrams, buildIndex, plan, search, describe };
  if (typeof module !== 'undefined') module.exports = api;
  else root.Engine = api;
})(typeof window !== 'undefined' ? window : globalThis);
