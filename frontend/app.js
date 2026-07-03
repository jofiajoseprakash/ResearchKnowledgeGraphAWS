const auth = { idToken: null, email: null, password: null };

const selectors = {
  apiUrl: document.querySelector("#apiUrl"),
  authPanel: document.querySelector("#authPanel"),
  authEmail: document.querySelector("#authEmail"),
  authPassword: document.querySelector("#authPassword"),
  signInButton: document.querySelector("#signInButton"),
  authError: document.querySelector("#authError"),
  question: document.querySelector("#question"),
  askButton: document.querySelector("#askButton"),
  askAiButton: document.querySelector("#askAiButton"),
  aiLabel: document.querySelector("#aiLabel"),
  status: document.querySelector("#status"),
  intentTitle: document.querySelector("#intentTitle"),
  intentDescription: document.querySelector("#intentDescription"),
  graphSummary: document.querySelector("#graphSummary"),
  graph: document.querySelector("#graph"),
  nodeDetails: document.querySelector("#nodeDetails"),
  resetGraph: document.querySelector("#resetGraph"),
  table: document.querySelector("#table"),
  sparql: document.querySelector("#sparql"),
  toggleSparql: document.querySelector("#toggleSparql"),
};

async function signIn(email, password) {
  const apiUrl = selectors.apiUrl.value.replace(/\/$/, "");
  const response = await fetch(`${apiUrl}/auth`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Sign-in failed");
  return data;
}

async function ensureToken() {
  if (auth.idToken) return auth.idToken;
  if (auth.email && auth.password) {
    const data = await signIn(auth.email, auth.password);
    auth.idToken = data.id_token;
    // auto-clear token just before it expires so next call re-auths
    setTimeout(() => { auth.idToken = null; }, (data.expires_in - 60) * 1000);
    return auth.idToken;
  }
  throw new Error("Not signed in");
}

selectors.signInButton.addEventListener("click", async () => {
  const email = selectors.authEmail.value.trim();
  const password = selectors.authPassword.value;
  selectors.authError.classList.add("hidden");
  selectors.signInButton.disabled = true;
  selectors.signInButton.textContent = "Signing in…";
  try {
    const data = await signIn(email, password);
    auth.idToken = data.id_token;
    auth.email = email;
    auth.password = password;
    setTimeout(() => { auth.idToken = null; }, (data.expires_in - 60) * 1000);
    selectors.authPanel.classList.add("signed-in");
    selectors.signInButton.textContent = `Signed in as ${email}`;
    setStatus("Signed in", "ok");
    handleAsk();
  } catch (err) {
    selectors.authError.textContent = err.message;
    selectors.authError.classList.remove("hidden");
    selectors.signInButton.disabled = false;
    selectors.signInButton.textContent = "Sign in";
  }
});

const PREFIXES = `
PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
`;

const intents = [
  {
    id: "citation",
    title: "Citation Graph",
    description: "Recent papers (top) citing foundational works (bottom). Arrows show who cites whom.",
    matches: ["citation", "cite", "cites", "cited"],
    mode: "graph",
    layout: "hierarchical",
    edgeLabel: "cites",
    sourceType: "recent",
    targetType: "foundational",
    sourceVar: "work",
    sourceLabelVar: "workTitle",
    targetVar: "citedWork",
    targetLabelVar: "citedTitle",
    query: `
${PREFIXES}
SELECT ?work ?workTitle ?citedWork ?citedTitle
WHERE {
  ?work a kg:Work ;
        rdfs:label ?workTitle ;
        kg:publicationYear ?year ;
        kg:cites ?citedWork .
  ?citedWork rdfs:label ?citedTitle .
  FILTER(?year >= 2025)
}
LIMIT 100
`,
  },
  {
    id: "authors",
    title: "Papers And Authors",
    description: "Shows which authors wrote each paper.",
    matches: ["author", "authors", "wrote", "paper authors"],
    mode: "graph",
    edgeLabel: "authored by",
    sourceType: "paper",
    targetType: "author",
    sourceVar: "source",
    sourceLabelVar: "sourceLabel",
    targetVar: "target",
    targetLabelVar: "targetLabel",
    query: `
${PREFIXES}
SELECT ?source ?sourceLabel ?target ?targetLabel
WHERE {
  ?source a kg:Work ;
          rdfs:label ?sourceLabel ;
          kg:authoredBy ?target .
  ?target rdfs:label ?targetLabel .
}
LIMIT 60
`,
  },
  {
    id: "topics",
    title: "Papers By Topic",
    description: "Shows how papers connect to research topics.",
    matches: ["topic", "topics", "field", "area"],
    mode: "graph",
    edgeLabel: "has topic",
    sourceType: "paper",
    targetType: "topic",
    sourceVar: "source",
    sourceLabelVar: "sourceLabel",
    targetVar: "target",
    targetLabelVar: "targetLabel",
    query: `
${PREFIXES}
SELECT ?source ?sourceLabel ?target ?targetLabel
WHERE {
  ?source a kg:Work ;
          rdfs:label ?sourceLabel ;
          kg:hasTopic ?target .
  ?target rdfs:label ?targetLabel .
}
LIMIT 60
`,
  },
  {
    id: "institutions",
    title: "Authors And Institutions",
    description: "Shows author affiliations and the institutions connected to the demo graph.",
    matches: ["institution", "institutions", "university", "affiliation", "lab"],
    mode: "graph",
    edgeLabel: "affiliated with",
    sourceType: "author",
    targetType: "institution",
    sourceVar: "source",
    sourceLabelVar: "sourceLabel",
    targetVar: "target",
    targetLabelVar: "targetLabel",
    query: `
${PREFIXES}
SELECT DISTINCT ?source ?sourceLabel ?target ?targetLabel
WHERE {
  ?work kg:authoredBy ?source .
  ?source rdfs:label ?sourceLabel ;
          kg:affiliatedWith ?target .
  ?target rdfs:label ?targetLabel .
}
LIMIT 60
`,
  },
  {
    id: "top-topics",
    title: "Top Topics",
    description: "Ranks topics by the number of papers connected to them.",
    matches: ["top topic", "top topics", "popular topic", "summary", "count"],
    mode: "table",
    query: `
${PREFIXES}
SELECT ?topicName (COUNT(?work) AS ?paperCount)
WHERE {
  ?work kg:hasTopic ?topic .
  ?topic rdfs:label ?topicName .
}
GROUP BY ?topicName
ORDER BY DESC(?paperCount)
`,
  },
  {
    id: "recent-papers",
    title: "Recent Papers",
    description: "Lists the newest papers in the graph with publication year.",
    matches: ["recent", "newest", "latest", "papers", "works"],
    mode: "table",
    query: `
${PREFIXES}
SELECT ?title ?year
WHERE {
  ?work a kg:Work ;
        rdfs:label ?title .
  OPTIONAL { ?work kg:publicationYear ?year . }
}
ORDER BY DESC(?year)
LIMIT 25
`,
  },
  {
    id: "prolific-authors",
    title: "Most Prolific Authors",
    description: "Authors ranked by number of papers in the graph.",
    matches: ["prolific", "top author", "most papers", "active author", "productive"],
    mode: "table",
    query: `
${PREFIXES}
SELECT ?authorName (COUNT(DISTINCT ?work) AS ?papers)
WHERE {
  ?work a kg:Work ;
        kg:authoredBy ?author .
  ?author rdfs:label ?authorName .
}
GROUP BY ?authorName
ORDER BY DESC(?papers)
LIMIT 20
`,
  },
  {
    id: "active-institutions",
    title: "Most Active Institutions",
    description: "Institutions ranked by number of papers their researchers contributed to.",
    matches: ["top institution", "leading university", "most active institution", "which university"],
    mode: "table",
    query: `
${PREFIXES}
SELECT ?instName (COUNT(DISTINCT ?work) AS ?papers)
WHERE {
  ?work a kg:Work ;
        kg:authoredBy ?author .
  ?author kg:affiliatedWith ?inst .
  ?inst rdfs:label ?instName .
}
GROUP BY ?instName
ORDER BY DESC(?papers)
LIMIT 20
`,
  },
  {
    id: "most-cited",
    title: "Most Cited Papers",
    description: "Papers with the most citations from other papers in the graph.",
    matches: ["most cited", "highly cited", "influential", "impact", "cited by"],
    mode: "table",
    query: `
${PREFIXES}
SELECT ?title ?year (COUNT(?citing) AS ?citations)
WHERE {
  ?citing kg:cites ?work .
  ?work rdfs:label ?title .
  OPTIONAL { ?work kg:publicationYear ?year . }
}
GROUP BY ?title ?year
ORDER BY DESC(?citations)
LIMIT 20
`,
  },
  {
    id: "coauthors",
    title: "Co-author Network",
    description: "Researchers who have co-authored papers together.",
    matches: ["collaborat", "co-author", "coauthor", "colleague", "worked together"],
    mode: "graph",
    edgeLabel: "co-authored",
    sourceType: "author",
    targetType: "author",
    sourceVar: "source",
    sourceLabelVar: "sourceLabel",
    targetVar: "target",
    targetLabelVar: "targetLabel",
    query: `
${PREFIXES}
SELECT DISTINCT ?source ?sourceLabel ?target ?targetLabel
WHERE {
  ?work kg:authoredBy ?source ;
        kg:authoredBy ?target .
  ?source rdfs:label ?sourceLabel .
  ?target rdfs:label ?targetLabel .
  FILTER(STR(?source) < STR(?target))
}
LIMIT 80
`,
  },
];

function matchIntent(question) {
  const normalized = question.toLowerCase();
  return (
    intents.find((intent) => intent.matches.some((word) => normalized.includes(word))) ||
    intents[0]
  );
}

function setStatus(text, state = "") {
  selectors.status.textContent = text;
  selectors.status.className = `status ${state}`.trim();
}

function bindingValue(binding, key) {
  return binding[key]?.value || "";
}

function parseBindings(result) {
  return result?.results?.bindings || [];
}

async function runSparql(query, retry = true) {
  const apiUrl = selectors.apiUrl.value.replace(/\/$/, "");
  if (!apiUrl) throw new Error("API URL is required");

  const token = await ensureToken();
  const response = await fetch(`${apiUrl}/query/sparql`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({ query }),
  });

  if (response.status === 401 && retry) {
    // token expired — clear it and retry once with a fresh one
    auth.idToken = null;
    return runSparql(query, false);
  }

  const responseText = await response.text();
  let payload;
  try {
    payload = JSON.parse(responseText);
  } catch {
    payload = { message: responseText || `HTTP ${response.status}` };
  }
  if (!response.ok) {
    throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
  }
  if (payload.error) {
    throw new Error(payload.detail || payload.error);
  }
  return payload.result;
}

function shortLabel(label, max = 46) {
  if (!label) return "Unknown";
  return label.length > max ? `${label.slice(0, max - 1)}...` : label;
}

function nodeGradient(type) {
  const map = {
    paper: "url(#gPaper)",
    author: "url(#gAuthor)",
    topic: "url(#gTopic)",
    institution: "url(#gInstitution)",
    recent: "url(#gRecent)",
    foundational: "url(#gFoundational)",
  };
  return map[type] || "url(#gPaper)";
}

function nodeRadius(type) {
  if (type === "recent") return 22;
  if (type === "foundational") return 16;
  if (type === "paper") return 20;
  return 16;
}

function nodeTypeFromUri(uri) {
  if (uri.includes("/author/")) return "author";
  if (uri.includes("/topic/")) return "topic";
  if (uri.includes("/institution/")) return "institution";
  return "paper";
}

function edgeLabelForType(targetType) {
  if (targetType === "author") return "by";
  if (targetType === "topic") return "about";
  if (targetType === "institution") return "at";
  return "cites";
}

function buildGraphRows(bindings, intent) {
  const nodes = new Map();
  const edges = [];
  const sourceVar = intent.sourceVar || "source";
  const sourceLabelVar = intent.sourceLabelVar || "sourceLabel";
  const targetVar = intent.targetVar || "target";
  const targetLabelVar = intent.targetLabelVar || "targetLabel";

  const autoTypes = intent.sourceType === "auto";

  for (const row of bindings) {
    const source = bindingValue(row, sourceVar);
    const target = bindingValue(row, targetVar);
    if (!source || !target) continue;

    const srcType = autoTypes ? nodeTypeFromUri(source) : intent.sourceType;
    const tgtType = autoTypes ? nodeTypeFromUri(target) : intent.targetType;

    nodes.set(source, {
      id: source,
      label: bindingValue(row, sourceLabelVar),
      type: srcType,
    });
    nodes.set(target, {
      id: target,
      label: bindingValue(row, targetLabelVar),
      type: tgtType,
    });
    edges.push({ source, target, label: autoTypes ? edgeLabelForType(tgtType) : intent.edgeLabel });
  }

  return { nodes: Array.from(nodes.values()), edges };
}

function initialLayout(nodes, width, height, hierarchical = false) {
  if (hierarchical) {
    const recent = nodes.filter((n) => n.type === "recent");
    const foundational = nodes.filter((n) => n.type === "foundational");
    const placed = [];
    recent.forEach((node, i) => {
      placed.push({ ...node,
        x: (width / (Math.max(recent.length, 1) + 1)) * (i + 1),
        y: height * 0.20,
        vx: 0, vy: 0,
      });
    });
    // Grid layout so foundational papers don't all crowd one row
    const perRow = Math.max(Math.ceil(Math.sqrt(foundational.length * (width / height))), 4);
    foundational.forEach((node, i) => {
      const row = Math.floor(i / perRow);
      const col = i % perRow;
      const itemsInRow = Math.min(perRow, foundational.length - row * perRow);
      placed.push({ ...node,
        x: (width / (itemsInRow + 1)) * (col + 1),
        y: height * 0.58 + row * 72,
        vx: 0, vy: 0,
      });
    });
    return placed;
  }

  const centerX = width / 2;
  const centerY = height / 2;
  // Seed on a large ring so physics starts with nodes already spread out
  const baseR = Math.min(width, height) * 0.36;

  return nodes.map((node, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(nodes.length, 1);
    const r = baseR + (index % 6) * 28;
    return {
      ...node,
      x: centerX + Math.cos(angle) * r,
      y: centerY + Math.sin(angle) * r,
      vx: 0,
      vy: 0,
    };
  });
}

function simulateLayout(nodes, edges, width, height) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const centerX = width / 2;
  const centerY = height / 2;
  const desired = 210;

  for (let tick = 0; tick < 420; tick += 1) {
    for (let i = 0; i < nodes.length; i += 1) {
      for (let j = i + 1; j < nodes.length; j += 1) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x || 0.01;
        const dy = b.y - a.y || 0.01;
        const distanceSq = dx * dx + dy * dy;
        const force = Math.min(16000 / distanceSq, 5.0);
        const distance = Math.sqrt(distanceSq);
        const fx = (dx / distance) * force;
        const fy = (dy / distance) * force;
        a.vx -= fx;
        a.vy -= fy;
        b.vx += fx;
        b.vy += fy;
      }
    }

    for (const edge of edges) {
      const source = byId.get(edge.source);
      const target = byId.get(edge.target);
      if (!source || !target) continue;
      const dx = target.x - source.x || 0.01;
      const dy = target.y - source.y || 0.01;
      const distance = Math.sqrt(dx * dx + dy * dy);
      const force = (distance - desired) * 0.014;
      const fx = (dx / distance) * force;
      const fy = (dy / distance) * force;
      source.vx += fx;
      source.vy += fy;
      target.vx -= fx;
      target.vy -= fy;
    }

    for (const node of nodes) {
      node.vx += (centerX - node.x) * 0.0008;
      node.vy += (centerY - node.y) * 0.0008;
      node.vx *= 0.78;
      node.vy *= 0.78;
      node.x += node.vx;
      node.y += node.vy;
    }
  }

  return nodes;
}

function simulateHierarchical(nodes, edges, width, height) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const desired = 200;

  for (let tick = 0; tick < 420; tick++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = (b.x - a.x) || 0.01;
        const dy = (b.y - a.y) || 0.01;
        const distSq = dx * dx + dy * dy;
        const force = Math.min(16000 / distSq, 5.0);
        const dist = Math.sqrt(distSq);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx -= fx; a.vy -= fy;
        b.vx += fx; b.vy += fy;
      }
    }
    for (const edge of edges) {
      const s = byId.get(edge.source), t = byId.get(edge.target);
      if (!s || !t) continue;
      const dx = (t.x - s.x) || 0.01;
      const dy = (t.y - s.y) || 0.01;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const force = (dist - desired) * 0.010;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      s.vx += fx; s.vy += fy;
      t.vx -= fx; t.vy -= fy;
    }
    for (const node of nodes) {
      const tierCenter = node.type === "recent" ? height * 0.20 : height * 0.72;
      node.vy += (tierCenter - node.y) * 0.018;
      node.vx += (width / 2 - node.x) * 0.0008;
      node.vx *= 0.78;
      node.vy *= 0.78;
      node.x += node.vx;
      node.y += node.vy;
      if (node.type === "recent") {
        node.y = Math.max(height * 0.05, Math.min(height * 0.42, node.y));
      } else {
        node.y = Math.max(height * 0.48, Math.min(height * 0.96, node.y));
      }
    }
  }
  return nodes;
}

function renderGraph(bindings, intent) {
  const svg = selectors.graph;
  const width = svg.clientWidth || 900;
  const height = svg.clientHeight || 580;
  const graph = buildGraphRows(bindings, intent);
  const hierarchical = intent.layout === "hierarchical";
  const nodes = hierarchical
    ? simulateHierarchical(initialLayout(graph.nodes, width, height, true), graph.edges, width, height)
    : simulateLayout(initialLayout(graph.nodes, width, height, false), graph.edges, width, height);
  const byId = new Map(nodes.map((node) => [node.id, node]));

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = `
    <defs>
      <radialGradient id="gPaper" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#93c5fd"/><stop offset="100%" stop-color="#1e40af"/>
      </radialGradient>
      <radialGradient id="gAuthor" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#6ee7b7"/><stop offset="100%" stop-color="#065f46"/>
      </radialGradient>
      <radialGradient id="gTopic" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#fde68a"/><stop offset="100%" stop-color="#b45309"/>
      </radialGradient>
      <radialGradient id="gInstitution" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#f9a8d4"/><stop offset="100%" stop-color="#9d174d"/>
      </radialGradient>
      <radialGradient id="gRecent" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#a5b4fc"/><stop offset="100%" stop-color="#3730a3"/>
      </radialGradient>
      <radialGradient id="gFoundational" cx="38%" cy="32%" r="68%">
        <stop offset="0%" stop-color="#d8b4fe"/><stop offset="100%" stop-color="#6b21a8"/>
      </radialGradient>
      <filter id="nodeShadow" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="2" stdDeviation="3.5" flood-color="rgba(0,0,0,0.22)"/>
      </filter>
      <marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto">
        <path d="M0,0.5 L0,5.5 L7,3 z" fill="#94a3b8"/>
      </marker>
    </defs>
  `;

  // Row labels for hierarchical layout
  if (hierarchical) {
    const viewport0 = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.appendChild(viewport0);
    for (const [label, y, color] of [["RECENT PAPERS (2026)", height * 0.05, "var(--recent)"], ["FOUNDATIONAL WORKS", height * 0.47, "var(--foundational)"]]) {
      const t = document.createElementNS("http://www.w3.org/2000/svg", "text");
      t.setAttribute("x", width / 2);
      t.setAttribute("y", y);
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("fill", color);
      t.setAttribute("font-size", "11");
      t.setAttribute("font-weight", "600");
      t.setAttribute("letter-spacing", "1");
      t.textContent = label;
      viewport0.appendChild(t);
    }
  }

  const viewport = document.createElementNS("http://www.w3.org/2000/svg", "g");
  viewport.setAttribute("id", "viewport");
  svg.appendChild(viewport);

  for (const edge of graph.edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) continue;

    const edgeGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    edgeGroup.setAttribute("class", "edge-group");
    edgeGroup.setAttribute("data-source", edge.source);
    edgeGroup.setAttribute("data-target", edge.target);

    const el = document.createElementNS("http://www.w3.org/2000/svg", "path");
    el.setAttribute("class", "edge");
    el.setAttribute("fill", "none");
    el.setAttribute("marker-end", "url(#arrow)");
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const offset = Math.min(len * 0.18, 38);
    const cx = (source.x + target.x) / 2 - (dy / len) * offset;
    const cy = (source.y + target.y) / 2 + (dx / len) * offset;
    el.setAttribute("d", `M ${source.x},${source.y} Q ${cx},${cy} ${target.x},${target.y}`);
    edgeGroup.appendChild(el);

    if (edge.label) {
      const lx = (source.x + target.x) / 2 - (dy / len) * offset * 0.5;
      const ly = (source.y + target.y) / 2 + (dx / len) * offset * 0.5;
      const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      const labelW = edge.label.length * 6 + 8;
      bg.setAttribute("x", lx - labelW / 2);
      bg.setAttribute("y", ly - 8);
      bg.setAttribute("width", labelW);
      bg.setAttribute("height", 13);
      bg.setAttribute("rx", 3);
      bg.setAttribute("class", "edge-label-bg");
      bg.setAttribute("fill", "white");
      bg.setAttribute("fill-opacity", "0.82");
      bg.setAttribute("pointer-events", "none");
      const lt = document.createElementNS("http://www.w3.org/2000/svg", "text");
      lt.setAttribute("class", "edge-label");
      lt.setAttribute("x", lx);
      lt.setAttribute("y", ly + 1);
      lt.setAttribute("text-anchor", "middle");
      lt.setAttribute("pointer-events", "none");
      lt.textContent = edge.label;
      edgeGroup.appendChild(bg);
      edgeGroup.appendChild(lt);
    }

    viewport.appendChild(edgeGroup);
  }

  for (const node of nodes) {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", "node");
    group.setAttribute("transform", `translate(${node.x}, ${node.y})`);

    const r = nodeRadius(node.type);
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("r", r);
    circle.setAttribute("fill", nodeGradient(node.type));
    circle.setAttribute("filter", "url(#nodeShadow)");

    const label = shortLabel(node.label, 22);
    const labelW = Math.min(label.length * 6.2 + 16, 158);
    const labelBg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    labelBg.setAttribute("x", -labelW / 2);
    labelBg.setAttribute("y", r + 5);
    labelBg.setAttribute("width", labelW);
    labelBg.setAttribute("height", 16);
    labelBg.setAttribute("rx", 4);
    labelBg.setAttribute("fill", "white");
    labelBg.setAttribute("fill-opacity", "0.88");
    labelBg.setAttribute("pointer-events", "none");

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("y", r + 15);
    text.setAttribute("pointer-events", "none");
    text.textContent = label;

    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = node.label;

    group.dataset.nodeId = node.id;
    group.appendChild(circle);
    group.appendChild(labelBg);
    group.appendChild(text);
    group.appendChild(title);
    enableNodeDrag(svg, group, node, byId, graph.edges);
    viewport.appendChild(group);
  }

  selectors.graphSummary.textContent = `${nodes.length} nodes, ${graph.edges.length} relationships`;
  selectors.nodeDetails.classList.add("hidden");
  enablePanZoom(svg, viewport);
}

function clearNodeFocus() {
  document.querySelectorAll(".node").forEach((n) => {
    n.classList.remove("selected", "connected", "dimmed");
  });
  document.querySelectorAll(".edge-group").forEach((e) => {
    e.classList.remove("edge-active", "edge-dimmed");
  });
}

function selectNode(group, node) {
  clearNodeFocus();

  // Find all edges touching this node; collect neighbour IDs
  const connectedIds = new Set();
  document.querySelectorAll(".edge-group").forEach((el) => {
    const src = el.getAttribute("data-source");
    const tgt = el.getAttribute("data-target");
    if (src === node.id || tgt === node.id) {
      connectedIds.add(src === node.id ? tgt : src);
      el.classList.add("edge-active");
    } else {
      el.classList.add("edge-dimmed");
    }
  });

  // Highlight selected + connected, dim everything else
  document.querySelectorAll(".node").forEach((n) => {
    if (n === group) {
      n.classList.add("selected");
    } else if (connectedIds.has(n.dataset.nodeId)) {
      n.classList.add("connected");
    } else {
      n.classList.add("dimmed");
    }
  });

  const url = openAlexUrl(node.id);
  const linkHtml = url
    ? `<a href="${url}" target="_blank" rel="noopener">View on OpenAlex ↗</a>`
    : escapeHtml(node.id);
  selectors.nodeDetails.innerHTML = `
    <h3>${escapeHtml(node.label)}</h3>
    <p class="node-type">${escapeHtml(node.type)}</p>
    <p>${linkHtml}</p>
  `;
  selectors.nodeDetails.classList.remove("hidden");
}

function svgPoint(svg, event) {
  const point = svg.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  return point.matrixTransform(svg.getScreenCTM().inverse());
}

function updateConnectedEdges(edges, byId) {
  document.querySelectorAll(".edge").forEach((el, index) => {
    const edge = edges[index];
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) return;
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const len = Math.sqrt(dx * dx + dy * dy) || 1;
    const offset = Math.min(len * 0.18, 38);
    const cx = (source.x + target.x) / 2 - (dy / len) * offset;
    const cy = (source.y + target.y) / 2 + (dx / len) * offset;
    el.setAttribute("d", `M ${source.x},${source.y} Q ${cx},${cy} ${target.x},${target.y}`);
  });
}

function enableNodeDrag(svg, group, node, byId, edges) {
  let startX, startY;

  group.addEventListener("pointerdown", (event) => {
    event.stopPropagation(); // prevent SVG pan from starting
    startX = event.clientX;
    startY = event.clientY;
    group.setPointerCapture(event.pointerId);
  });
  group.addEventListener("pointermove", (event) => {
    if (!group.hasPointerCapture(event.pointerId)) return;
    const point = svgPoint(svg, event);
    node.x = point.x;
    node.y = point.y;
    group.setAttribute("transform", `translate(${node.x}, ${node.y})`);
    updateConnectedEdges(edges, byId);
  });
  group.addEventListener("pointerup", (event) => {
    event.stopPropagation(); // prevent SVG onpointerup from clearing focus immediately after
    const moved = Math.abs(event.clientX - startX) + Math.abs(event.clientY - startY);
    if (moved < 5) selectNode(group, node); // click, not drag
    group.releasePointerCapture(event.pointerId);
  });
  group.addEventListener("pointercancel", (event) => {
    group.releasePointerCapture(event.pointerId);
  });
}

function enablePanZoom(svg, viewport) {
  let transform = { x: 0, y: 0, scale: 1 };
  let panning = false;
  let last = null;
  let didPan = false;

  function apply() {
    viewport.setAttribute(
      "transform",
      `translate(${transform.x}, ${transform.y}) scale(${transform.scale})`
    );
  }

  selectors.resetGraph.onclick = () => {
    transform = { x: 0, y: 0, scale: 1 };
    apply();
  };

  svg.onwheel = (event) => {
    event.preventDefault();
    const factor = event.deltaY > 0 ? 0.9 : 1.1;
    transform.scale = Math.max(0.35, Math.min(2.8, transform.scale * factor));
    apply();
  };

  svg.onpointerdown = (event) => {
    if (event.target.closest(".node")) return;
    panning = true;
    didPan = false;
    last = { x: event.clientX, y: event.clientY };
    svg.setPointerCapture(event.pointerId);
  };
  svg.onpointermove = (event) => {
    if (!panning || !last) return;
    const dx = event.clientX - last.x;
    const dy = event.clientY - last.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) didPan = true;
    transform.x += dx;
    transform.y += dy;
    last = { x: event.clientX, y: event.clientY };
    apply();
  };
  svg.onpointerup = (event) => {
    if (!didPan) {
      clearNodeFocus();
      selectors.nodeDetails.classList.add("hidden");
    }
    panning = false;
    didPan = false;
    last = null;
    svg.releasePointerCapture(event.pointerId);
  };
}

const COLUMN_LABELS = {
  w: "Paper", work: "Paper", source: "Paper", citedWork: "Cited Paper",
  t: "Topic", topic: "Topic",
  title: "Title", workTitle: "Title", sourceLabel: "Title", citedTitle: "Cited Paper",
  tname: "Topic", topicName: "Topic", targetLabel: "Topic / Author / Institution",
  target: "Related",
  year: "Year", publicationYear: "Year",
  authorName: "Author", name: "Author",
  instName: "Institution", inst: "Institution",
  papers: "Papers", paperCount: "Papers",
  citations: "Citations",
};

function friendlyColumn(col) {
  return COLUMN_LABELS[col] || col.replace(/([A-Z])/g, " $1").replace(/^./, (c) => c.toUpperCase());
}

function renderTable(bindings) {
  if (!bindings.length) {
    selectors.table.innerHTML = "<p class=\"empty\">No results.</p>";
    return;
  }
  const columns = Object.keys(bindings[0]);
  const rows = bindings
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => `<td>${renderCell(bindingValue(row, column))}</td>`)
          .join("")}</tr>`
    )
    .join("");
  selectors.table.innerHTML = `
    <table>
      <thead><tr>${columns.map((column) => `<th>${escapeHtml(friendlyColumn(column))}</th>`).join("")}</tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function openAlexUrl(uri) {
  // Convert internal example.org URI → real OpenAlex link
  // e.g. https://example.org/research-kg/resource/work/W123 → https://openalex.org/W123
  const match = uri.match(/\/resource\/(?:work|author|topic|institution|source)\/([^/]+)$/);
  return match ? `https://openalex.org/${match[1]}` : null;
}

function renderCell(value) {
  const url = openAlexUrl(value);
  if (url) {
    return `<a href="${url}" target="_blank" rel="noopener">${escapeHtml(value.split("/").pop())}</a>`;
  }
  return escapeHtml(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function handleAsk() {
  const intent = matchIntent(selectors.question.value);
  selectors.intentTitle.textContent = intent.title;
  selectors.intentDescription.textContent = intent.description;
  selectors.sparql.textContent = intent.query.trim();
  selectors.aiLabel.classList.add("hidden");
  selectors.graphSummary.textContent = "Running query...";
  selectors.graph.innerHTML = "";
  selectors.table.innerHTML = "";
  setStatus("Querying", "");

  try {
    const result = await runSparql(intent.query);
    const bindings = parseBindings(result);
    if (intent.mode === "graph") {
      renderGraph(bindings, intent);
    } else {
      selectors.graphSummary.textContent = `${bindings.length} rows`;
      renderGraph([], { sourceType: "paper", targetType: "topic", edgeLabel: "" });
    }
    renderTable(bindings);
    setStatus("Connected", "ok");
  } catch (error) {
    selectors.graphSummary.textContent = "Query failed";
    selectors.table.innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
    setStatus("Error", "error");
  }
}

async function handleAskAi() {
  const question = selectors.question.value.trim();
  if (!question) return;

  const apiUrl = selectors.apiUrl.value.replace(/\/$/, "");
  selectors.aiLabel.classList.add("hidden");
  selectors.graphSummary.textContent = "Asking AI…";
  selectors.graph.innerHTML = "";
  selectors.table.innerHTML = "";
  selectors.askAiButton.disabled = true;
  selectors.askAiButton.textContent = "Thinking…";
  setStatus("Querying AI", "");

  async function fetchNl(retry = true) {
    const token = await ensureToken();
    const response = await fetch(`${apiUrl}/query/nl`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (response.status === 401 && retry) {
      auth.idToken = null;
      return fetchNl(false);
    }
    return response;
  }

  try {
    const response = await fetchNl();
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);

    const generatedSparql = payload.sparql || "";
    selectors.sparql.textContent = generatedSparql;
    selectors.aiLabel.classList.remove("hidden");
    selectors.intentTitle.textContent = "AI Answer";
    selectors.intentDescription.textContent = `Question: "${question}"`;

    if (payload.sparql_error) {
      selectors.graphSummary.textContent = "AI query failed";
      selectors.table.innerHTML = `<p class="empty">AI generated SPARQL but it failed: ${escapeHtml(payload.sparql_error)}</p>`;
      setStatus("AI error", "error");
      return;
    }

    const bindings = parseBindings(payload.result);
    // Use head.vars for canonical SELECT-clause order — Object.keys order is not guaranteed
    const vars = payload.result?.head?.vars || Object.keys(bindings[0] || {});
    // Detect graph: 4 columns where columns 0 and 2 look like URIs
    const looksLikeUri = (v) => (bindings[0]?.[v]?.value || "").includes("://");
    const isGraphResult = vars.length === 4 && (
      vars.some((v) => v.toLowerCase().includes("label")) ||
      (looksLikeUri(vars[0]) && looksLikeUri(vars[2]))
    );
    if (isGraphResult) {
      const [sv, slv, tv, tlv] = vars;

      // Enrich: fetch authors for the same papers and merge into the same binding set
      let allBindings = [...bindings];
      const paperUris = [...new Set(bindings.map((b) => b[sv]?.value).filter(Boolean))];
      if (paperUris.length > 0) {
        try {
          const valuesList = paperUris.slice(0, 40).map((u) => `<${u}>`).join(" ");
          const authorQuery = `PREFIX kg: <https://example.org/research-kg/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?${sv} ?${slv} ?${tv} ?${tlv}
WHERE {
  VALUES ?${sv} { ${valuesList} }
  ?${sv} rdfs:label ?${slv} ;
         kg:authoredBy ?${tv} .
  ?${tv} rdfs:label ?${tlv} .
} LIMIT 120`;
          const authorResult = await runSparql(authorQuery);
          allBindings = [...bindings, ...parseBindings(authorResult)];
        } catch { /* enrichment optional — proceed with original bindings */ }
      }

      const fakeIntent = {
        sourceType: "auto", targetType: "auto", edgeLabel: "auto",
        sourceVar: sv, sourceLabelVar: slv,
        targetVar: tv, targetLabelVar: tlv,
      };
      renderGraph(allBindings, fakeIntent);
    } else {
      selectors.graphSummary.textContent = `${bindings.length} rows`;
      renderGraph([], { sourceType: "paper", targetType: "topic", edgeLabel: "" });
    }
    renderTable(bindings);
    setStatus("Connected", "ok");
  } catch (err) {
    selectors.graphSummary.textContent = "Failed";
    selectors.table.innerHTML = `<p class="empty">${escapeHtml(err.message)}</p>`;
    setStatus("Error", "error");
  } finally {
    selectors.askAiButton.disabled = false;
    selectors.askAiButton.textContent = "✦ Ask AI";
  }
}

selectors.askButton.addEventListener("click", handleAsk);
selectors.askAiButton.addEventListener("click", handleAskAi);
selectors.toggleSparql.addEventListener("click", () => {
  selectors.sparql.classList.toggle("hidden");
  selectors.toggleSparql.textContent = selectors.sparql.classList.contains("hidden")
    ? "Show SPARQL"
    : "Hide SPARQL";
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => {
    selectors.question.value = button.dataset.question;
    handleAsk();
  });
});
