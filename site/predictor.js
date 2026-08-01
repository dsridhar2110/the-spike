/* Browser-side re-implementation of sklearn's TfidfVectorizer + LogisticRegression.
   Must match: lowercase, token_pattern \b\w\w+\b, ngram_range (1,2),
   sublinear_tf (1+log tf), tf*idf, then L2 normalisation. */

function tokens(text) {
  const t = (text || "").toLowerCase().match(/\b\w\w+\b/g) || [];
  const out = t.slice();
  for (let i = 0; i < t.length - 1; i++) out.push(t[i] + " " + t[i + 1]);
  return out;
}

/** TF-IDF vector for one document, restricted to the shipped vocabulary. */
function vectorise(text, words) {
  const counts = new Map();
  for (const g of tokens(text)) if (words[g]) counts.set(g, (counts.get(g) || 0) + 1);
  const vec = new Map();
  let norm = 0;
  for (const [g, c] of counts) {
    const v = (1 + Math.log(c)) * words[g][0];     // sublinear tf x idf
    vec.set(g, v); norm += v * v;
  }
  norm = Math.sqrt(norm) || 1;
  for (const [g, v] of vec) vec.set(g, v / norm);
  return vec;
}

/** Predict P(approved) and return the terms that moved it most. */
function predict(text, borough, type, MODEL) {
  const vec = vectorise(text, MODEL.words);
  let z = MODEL.intercept;
  const contrib = [];
  for (const [g, v] of vec) {
    const c = v * MODEL.words[g][1];
    z += c;
    if (Math.abs(c) > 1e-4) contrib.push([g, c]);
  }
  const bKey = "area_name_" + borough, tKey = "app_type_" + type;
  const bc = MODEL.cats[bKey] || 0, tc = MODEL.cats[tKey] || 0;
  z += bc + tc;
  contrib.sort((a, b) => b[1] - a[1]);
  return {
    p: 1 / (1 + Math.exp(-z)),
    helped: contrib.filter(c => c[1] > 0).slice(0, 6),
    hurt: contrib.filter(c => c[1] < 0).slice(-6).reverse(),
    boroughEffect: bc, typeEffect: tc,
    matched: vec.size,
  };
}

/** Cosine similarity against the shipped corpus of real applications. */
function similar(text, MODEL, borough, k) {
  const q = vectorise(text, MODEL.words);
  if (!q.size) return [];
  const scored = [];
  for (const row of MODEL.corpus) {
    const v = vectorise(row.d, MODEL.words);
    let dot = 0;
    for (const [g, val] of q) { const w = v.get(g); if (w) dot += val * w; }
    if (dot > 0.05) scored.push([dot + (row.b === borough ? 0.03 : 0), dot, row]);
  }
  scored.sort((a, b) => b[0] - a[0]);
  return scored.slice(0, k).map(([, sim, row]) => ({ ...row, sim }));
}
