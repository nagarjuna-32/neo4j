// DevGraph Sentinel — Frontend Application Logic
// Hackathon Build Sprint Bengaluru 2026

let cy = null;
let currentGraphData = { nodes: [], edges: [], stats: {} };
let selectedNodeData = null;

// Color palette mapping specified by Section 8
const NODE_COLORS = {
  Project: '#3b82f6',     // Blue
  Component: '#06b6d4',   // Cyan
  Decision: '#a855f7',    // Purple
  Bug: '#ef4444',         // Red
  Fix: '#10b981',         // Green
  Test: '#84cc16',        // Light green
  Dependency: '#f59e0b',  // Amber
  Reason: '#8b5cf6',      // Violet
  PullRequest: '#818cf8', // Indigo
  Developer: '#14b8a6',   // Teal
  Default: '#64748b'      // Slate
};

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  await checkHealth();
  await loadGraph();
  await loadActivity();
  switchTab('overview');
});

// Toast Notification System
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  const bg = type === 'success' ? 'bg-emerald-950 border-emerald-800 text-emerald-200'
           : type === 'error' ? 'bg-red-950 border-red-800 text-red-200'
           : 'bg-surface-800 border-surface-600 text-slate-200';

  toast.className = `p-3 rounded-xl border ${bg} text-xs shadow-xl flex items-center gap-2 transform transition-all duration-300 pointer-events-auto max-w-sm`;
  toast.innerHTML = `
    <i data-lucide="${type === 'success' ? 'check-circle' : type === 'error' ? 'alert-triangle' : 'info'}" class="w-4 h-4 shrink-0"></i>
    <span class="flex-1">${message}</span>
  `;
  container.appendChild(toast);
  if (window.lucide) lucide.createIcons();

  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tab Switching
function switchTab(tabName) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
  document.querySelectorAll('.tab-button').forEach(btn => {
    btn.classList.remove('bg-cyan-600', 'text-white');
    btn.classList.add('text-slate-400');
  });

  const targetContent = document.getElementById(`tabContent-${tabName}`);
  const targetBtn = document.getElementById(`tabBtn-${tabName}`);
  if (targetContent) {
    targetContent.classList.remove('hidden');
    targetContent.classList.add('flex');
  }
  if (targetBtn) {
    targetBtn.classList.remove('text-slate-400');
    targetBtn.classList.add('bg-cyan-600', 'text-white');
  }

  if (tabName === 'graph') {
    setTimeout(() => {
      if (cy) {
        cy.resize();
        cy.fit(undefined, 40);
      } else if (currentGraphData && currentGraphData.nodes) {
        initCytoscape(currentGraphData);
      }
    }, 120);
  }
  if (window.lucide) lucide.createIcons();
}

// Health & System Diagnostics
async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) throw new Error('Health check failed');
    const data = await res.json();

    // Update Pills in Header
    const neoBadge = document.getElementById('neo4jStatusBadge');
    const neoText = document.getElementById('neo4jStatusText');
    if (data.neo4j_connected) {
      neoBadge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-emerald-950/40 border-emerald-800/60 text-emerald-300 cursor-pointer';
      neoText.innerText = 'Neo4j: Connected (Live Cypher)';
    } else {
      neoBadge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-amber-950/40 border-amber-800/60 text-amber-300 cursor-pointer';
      neoText.innerText = 'Graph: In-Memory Engine';
    }

    const aiBadge = document.getElementById('aiStatusBadge');
    const aiText = document.getElementById('aiStatusText');
    if (data.ai_configured) {
      aiBadge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-purple-950/40 border-purple-800/60 text-purple-300 cursor-pointer';
      aiText.innerText = `AI: ${data.ai_model}`;
    } else {
      aiBadge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border bg-cyan-950/40 border-cyan-800/60 text-cyan-300 cursor-pointer';
      aiText.innerText = 'AI: Deterministic Engine';
    }

    // Modal details
    document.getElementById('diagNeo4jStatus').innerText = data.neo4j_status;
    document.getElementById('diagStorageBackend').innerText = `Engine: ${data.storage_backend}`;
    document.getElementById('diagAIStatus').innerText = data.ai_status;
    document.getElementById('diagAIModel').innerText = `Model: ${data.ai_model}`;

    // Overview Banner Diagnostics Ribbon
    const ovNeoStatus = document.getElementById('overviewNeoStatus');
    const ovNeoDot = document.getElementById('overviewNeoDot');
    if (ovNeoStatus) {
      ovNeoStatus.innerText = data.neo4j_connected ? 'Neo4j AuraDB (Live Cypher)' : 'In-Memory Engine';
    }
    if (ovNeoDot) {
      ovNeoDot.className = data.neo4j_connected ? 'w-2 h-2 rounded-full bg-emerald-400' : 'w-2 h-2 rounded-full bg-amber-400 animate-pulse';
    }
    const ovAIStatus = document.getElementById('overviewAIStatus');
    if (ovAIStatus) {
      ovAIStatus.innerText = data.ai_configured ? data.ai_model : 'Deterministic Grounded';
    }
    const ovStorage = document.getElementById('overviewStorageBackend');
    if (ovStorage) {
      ovStorage.innerText = data.storage_backend;
    }

    const diagList = document.getElementById('diagList');
    diagList.innerHTML = '';
    (data.diagnostics || []).forEach(diag => {
      const p = document.createElement('p');
      p.innerText = `• ${diag}`;
      diagList.appendChild(p);
    });

  } catch (err) {
    console.warn('Health check issue:', err);
  }
}

function openHealthModal() {
  document.getElementById('healthModal').classList.remove('hidden');
  document.getElementById('healthModal').classList.add('flex');
}

function closeHealthModal() {
  document.getElementById('healthModal').classList.add('hidden');
  document.getElementById('healthModal').classList.remove('flex');
}

// Render Overview Workspace Cards
function renderOverviewCards(data) {
  const decList = document.getElementById('overviewDecisionsList');
  const bugsList = document.getElementById('overviewBugsList');
  if (!decList || !bugsList) return;

  decList.innerHTML = '';
  bugsList.innerHTML = '';

  const nodes = data.nodes || [];

  // Technical Decisions
  const decisions = nodes.filter(n => (n.labels && n.labels.includes('Decision')) || n.label === 'Decision');
  if (decisions.length === 0) {
    decList.innerHTML = '<p class="text-xs text-slate-500 italic p-3 bg-surface-800 rounded-lg">No technical decisions recorded yet.</p>';
  } else {
    decisions.forEach(d => {
      const p = d.properties || {};
      const card = document.createElement('div');
      card.className = 'p-3 rounded-xl border border-purple-900/40 bg-purple-950/20 text-xs space-y-1.5 hover:border-purple-700 transition';
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-mono font-bold text-purple-400">${d.id}</span>
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-900/80 text-purple-200">${p.author || 'Engineering'}</span>
        </div>
        <p class="font-semibold text-slate-100">${p.title || d.id}</p>
        <p class="text-[11px] text-slate-400 leading-relaxed"><strong class="text-purple-300">Rationale:</strong> ${p.reason || p.description || 'Architectural choice'}</p>
        <div class="pt-1 flex items-center justify-between border-t border-purple-900/30">
          <span class="text-[10px] text-slate-500">${p.timestamp ? new Date(p.timestamp).toLocaleDateString() : 'Active Baseline'}</span>
          <button onclick="setPrompt('What architectural trade-offs motivated decision ${d.id} (${p.title || ''})?', 'Authentication'); switchTab('debug');" class="text-xs text-purple-300 hover:text-purple-200 font-semibold flex items-center gap-1">
            <span>Debug with AI</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
          </button>
        </div>
      `;
      decList.appendChild(card);
    });
  }

  // Incidents & Regressions
  const bugs = nodes.filter(n => (n.labels && n.labels.includes('Bug')) || n.label === 'Bug');
  if (bugs.length === 0) {
    bugsList.innerHTML = '<p class="text-xs text-slate-500 italic p-3 bg-surface-800 rounded-lg">No historical incidents recorded yet.</p>';
  } else {
    bugs.forEach(b => {
      const p = b.properties || {};
      const card = document.createElement('div');
      card.className = 'p-3 rounded-xl border border-red-900/40 bg-red-950/20 text-xs space-y-1.5 hover:border-red-700 transition';
      card.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-mono font-bold text-red-400">${b.id}</span>
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-900/80 text-red-200 uppercase">${p.status || 'Remediated'}</span>
        </div>
        <p class="font-semibold text-slate-100">${p.title || b.id}</p>
        <p class="text-[11px] text-slate-400 leading-relaxed"><strong class="text-red-300">Root Cause:</strong> ${p.root_cause || p.symptom || 'Incident record'}</p>
        <div class="pt-1 flex items-center justify-between border-t border-red-900/30">
          <span class="text-[10px] text-slate-500">${p.component || 'Authentication'}</span>
          <button onclick="switchTab('impact');" class="text-xs text-red-300 hover:text-red-200 font-semibold flex items-center gap-1">
            <span>Analyze Impact</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
          </button>
        </div>
      `;
      bugsList.appendChild(card);
    });
  }

  if (window.lucide) lucide.createIcons();
}

// Load and Render Knowledge Graph
async function loadGraph(projectId = 'PRJ-SENTINEL') {
  try {
    const res = await fetch(`/api/graph?project_id=${encodeURIComponent(projectId)}`);
    if (!res.ok) throw new Error('Failed to retrieve knowledge graph');
    const data = await res.json();
    currentGraphData = data;

    // Update Header Summary Stats
    const stats = data.stats || {};
    const totalNodes = stats.total_nodes ?? data.nodes.length;
    const totalEdges = stats.total_edges ?? data.edges.length;
    const countComp = stats.components ?? (data.nodes || []).filter(n => n.label === 'Component' || (n.labels && n.labels.includes('Component'))).length;
    const countDec = stats.decisions ?? (data.nodes || []).filter(n => n.label === 'Decision' || (n.labels && n.labels.includes('Decision'))).length;
    const countBugs = stats.bugs ?? (data.nodes || []).filter(n => n.label === 'Bug' || (n.labels && n.labels.includes('Bug'))).length;
    const countTests = (data.nodes || []).filter(n => n.label === 'Test' || (n.labels && n.labels.includes('Test'))).length;

    document.getElementById('statNodes').innerText = totalNodes;
    document.getElementById('statEdges').innerText = totalEdges;
    document.getElementById('statComponents').innerText = countComp;
    document.getElementById('statBugs').innerText = countBugs;
    document.getElementById('statDecisions').innerText = countDec;

    // Update Overview Workspace Metric Cards
    const ovNodes = document.getElementById('statOverviewNodes');
    if (ovNodes) ovNodes.innerText = totalNodes;
    const ovEdges = document.getElementById('statOverviewEdges');
    if (ovEdges) ovEdges.innerText = totalEdges;
    const ovComps = document.getElementById('statOverviewComponents');
    if (ovComps) ovComps.innerText = countComp;
    const ovDecs = document.getElementById('statOverviewDecisions');
    if (ovDecs) ovDecs.innerText = countDec;
    const ovBugs = document.getElementById('statOverviewBugs');
    if (ovBugs) ovBugs.innerText = countBugs;
    const ovTests = document.getElementById('statOverviewTests');
    if (ovTests) ovTests.innerText = countTests || 1;

    renderOverviewCards(data);
    initCytoscape(data);
  } catch (err) {
    console.error('Error loading graph:', err);
    showToast('Failed to load graph data', 'error');
  }
}

// Cytoscape.js Rendering & Interactions
function initCytoscape(graphData) {
  const container = document.getElementById('cy');
  if (!container) return;

  const elements = [];

  // Add Nodes
  (graphData.nodes || []).forEach(node => {
    const label = node.label || (node.labels && node.labels[0]) || 'Node';
    const color = NODE_COLORS[label] || NODE_COLORS.Default;
    const props = node.properties || {};
    const displayName = props.name || props.title || node.id;

    elements.push({
      group: 'nodes',
      data: {
        id: node.id,
        label: displayName.length > 24 ? displayName.substring(0, 22) + '...' : displayName,
        fullLabel: displayName,
        category: label,
        color: color,
        properties: props,
      }
    });
  });

  // Add Edges
  (graphData.edges || []).forEach(edge => {
    elements.push({
      group: 'edges',
      data: {
        id: edge.id || `${edge.source}_${edge.type}_${edge.target}`,
        source: edge.source,
        target: edge.target,
        label: edge.type,
      }
    });
  });

  if (cy) {
    cy.destroy();
  }

  cy = cytoscape({
    container: container,
    elements: elements,
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'data(color)',
          'label': 'data(label)',
          'color': '#f8fafc',
          'font-size': '11px',
          'font-weight': '600',
          'font-family': 'Inter, sans-serif',
          'text-valign': 'bottom',
          'text-margin-y': 6,
          'width': 44,
          'height': 44,
          'border-width': 2,
          'border-color': '#ffffff',
          'border-opacity': 0.8,
          'text-background-color': '#0b0f19',
          'text-background-opacity': 0.85,
          'text-background-padding': 3,
          'text-background-shape': 'roundrectangle',
          'overlay-padding': 6,
        }
      },
      {
        selector: 'node[category = "Project"]',
        style: {
          'width': 56,
          'height': 56,
          'font-size': '12px',
          'border-width': 3,
        }
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#475569',
          'target-arrow-color': '#94a3b8',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 1.1,
          'label': 'data(label)',
          'font-size': '9px',
          'font-family': 'JetBrains Mono, monospace',
          'color': '#94a3b8',
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
          'text-background-color': '#0b0f19',
          'text-background-opacity': 0.75,
          'text-background-padding': 2,
        }
      },
      {
        selector: 'node:selected',
        style: {
          'border-color': '#22d3ee',
          'border-width': 4,
          'shadow-blur': 25,
          'shadow-color': '#06b6d4',
          'shadow-opacity': 0.9,
        }
      },
      {
        selector: '.highlighted',
        style: {
          'border-color': '#f59e0b',
          'border-width': 4,
          'shadow-blur': 20,
          'shadow-color': '#f59e0b',
          'line-color': '#f59e0b',
          'target-arrow-color': '#f59e0b',
          'width': 3.5,
        }
      },
      {
        selector: '.dimmed',
        style: {
          'opacity': 0.25,
        }
      }
    ],
    layout: {
      name: 'cose',
      idealEdgeLength: 100,
      nodeOverlap: 20,
      refresh: 20,
      fit: true,
      padding: 40,
      randomize: false,
      componentSpacing: 100,
      nodeRepulsion: 400000,
      edgeElasticity: 100,
      nestingFactor: 5,
      gravity: 80,
      numIter: 1000,
      initialTemp: 200,
      coolingFactor: 0.95,
      minTemp: 1.0,
    }
  });

  // Node selection event
  cy.on('tap', 'node', function (evt) {
    const node = evt.target;
    displayNodeDetails(node.data());
  });

  // Background tap deselects
  cy.on('tap', function (evt) {
    if (evt.target === cy) {
      clearNodeDetails();
    }
  });
}

// Display Node Inspector Details in Sidebar
function displayNodeDetails(data) {
  selectedNodeData = data;
  document.getElementById('detailEmptyState').classList.add('hidden');
  document.getElementById('detailContent').classList.remove('hidden');
  document.getElementById('btnAskNode').classList.remove('hidden');

  const badge = document.getElementById('detailBadge');
  badge.innerText = data.category;
  badge.style.backgroundColor = data.color + '33';
  badge.style.color = data.color;
  badge.style.borderColor = data.color;

  document.getElementById('detailId').innerText = data.id;
  document.getElementById('detailTitle').innerText = data.fullLabel;

  const props = data.properties || {};
  document.getElementById('detailDesc').innerText =
    props.description || props.reason || props.symptom || 'No description recorded.';

  // Build properties table
  const table = document.getElementById('detailPropsTable');
  table.innerHTML = '';
  Object.entries(props).forEach(([k, v]) => {
    if (['id', 'name', 'title', 'description'].includes(k)) return;
    const row = document.createElement('div');
    row.className = 'flex justify-between items-center text-[11px] py-0.5 border-b border-surface-700/50';
    row.innerHTML = `
      <span class="text-slate-400 font-mono">${k}</span>
      <span class="text-slate-200 font-medium truncate max-w-[150px] text-right" title="${String(v)}">${String(v)}</span>
    `;
    table.appendChild(row);
  });

  // Find Neighbors
  const cyNode = cy.getElementById(data.id);
  const neighborsList = document.getElementById('detailNeighborsList');
  neighborsList.innerHTML = '';

  if (cyNode) {
    const connectedEdges = cyNode.connectedEdges();
    document.getElementById('detailNeighborCount').innerText = connectedEdges.length;

    connectedEdges.forEach(edge => {
      const isOutgoing = edge.source().id() === data.id;
      const otherNode = isOutgoing ? edge.target() : edge.source();
      const edgeLabel = edge.data('label');

      const item = document.createElement('div');
      item.className = 'p-1.5 rounded bg-surface-750 flex items-center justify-between hover:bg-surface-700 cursor-pointer transition';
      item.onclick = () => {
        cy.nodes().unselect();
        otherNode.select();
        cy.center(otherNode);
        displayNodeDetails(otherNode.data());
      };

      item.innerHTML = `
        <div class="flex items-center gap-1.5 truncate">
          <span class="w-2 h-2 rounded-full shrink-0" style="background-color: ${otherNode.data('color')}"></span>
          <span class="text-slate-200 font-medium truncate">${otherNode.data('fullLabel')}</span>
        </div>
        <span class="text-[10px] font-mono text-cyan-400 shrink-0 ml-1">${isOutgoing ? '-> ' : '<- '}${edgeLabel}</span>
      `;
      neighborsList.appendChild(item);
    });
  }
}

function clearNodeDetails() {
  selectedNodeData = null;
  document.getElementById('detailEmptyState').classList.remove('hidden');
  document.getElementById('detailContent').classList.add('hidden');
  document.getElementById('btnAskNode').classList.add('hidden');
  document.getElementById('detailBadge').innerText = 'Select a node';
  document.getElementById('detailBadge').style.backgroundColor = '';
  document.getElementById('detailBadge').style.color = '';
  if (cy) {
    cy.elements().removeClass('highlighted dimmed');
  }
}

function askAboutSelectedNode() {
  if (!selectedNodeData) return;
  const name = selectedNodeData.fullLabel || selectedNodeData.id;
  setPrompt(`What historical technical decisions and previous bugs are connected to ${name}?`, name);
  switchTab('debug');
}

// Graph Canvas Controls
function fitGraph() {
  if (cy) cy.fit(undefined, 40);
}
function zoomIn() {
  if (cy) cy.zoom(cy.zoom() * 1.25);
}
function zoomOut() {
  if (cy) cy.zoom(cy.zoom() * 0.8);
}
function resetGraphLayout() {
  if (cy) {
    cy.layout({
      name: 'cose',
      idealEdgeLength: 100,
      fit: true,
      padding: 40,
      randomize: true,
    }).run();
  }
}

// Filter Graph by Node Category
function filterGraph(category) {
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.classList.remove('bg-cyan-600', 'text-white');
    btn.classList.add('bg-surface-700');
  });
  const activeBtn = document.getElementById(`filterBtn-${category}`);
  if (activeBtn) {
    activeBtn.classList.remove('bg-surface-700');
    activeBtn.classList.add('bg-cyan-600', 'text-white');
  }

  if (!cy) return;
  if (category === 'ALL') {
    cy.elements().removeClass('dimmed');
  } else {
    cy.batch(() => {
      cy.nodes().forEach(node => {
        if (node.data('category') === category) {
          node.removeClass('dimmed');
        } else {
          node.addClass('dimmed');
        }
      });
      cy.edges().forEach(edge => {
        const srcCat = edge.source().data('category');
        const tgtCat = edge.target().data('category');
        if (srcCat === category || tgtCat === category) {
          edge.removeClass('dimmed');
        } else {
          edge.addClass('dimmed');
        }
      });
    });
  }
}

// ================= FEATURE B: CONTEXTUAL DEBUGGING ASSISTANT =================
function setPrompt(text, component = '') {
  document.getElementById('debugQuestionInput').value = text;
  if (component) {
    const sel = document.getElementById('debugComponentSelect');
    for (let i = 0; i < sel.options.length; i++) {
      if (sel.options[i].value === component || sel.options[i].text.includes(component)) {
        sel.selectedIndex = i;
        break;
      }
    }
  }
}

async function handleRunAnalysis() {
  const question = document.getElementById('debugQuestionInput').value.trim();
  const component = document.getElementById('debugComponentSelect').value;

  if (!question || question.length < 5) {
    showToast('Please enter an engineering question (at least 5 characters)', 'error');
    return;
  }

  const placeholder = document.getElementById('debugResultPlaceholder');
  const loading = document.getElementById('debugLoadingState');
  const container = document.getElementById('debugResultContainer');
  const btn = document.getElementById('btnRunAnalysis');

  placeholder.classList.add('hidden');
  container.classList.add('hidden');
  loading.classList.remove('hidden');
  loading.classList.add('flex');
  btn.disabled = true;

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: 'PRJ-SENTINEL',
        question: question,
        component: component || null,
      }),
    });

    if (!res.ok) throw new Error('Analysis request failed');
    const data = await res.json();
    renderAnalysisResult(data);
    showToast('Neo4j graph evidence retrieved and analyzed successfully', 'success');
  } catch (err) {
    console.error('Analysis error:', err);
    showToast(`Analysis failed: ${err.message}`, 'error');
    placeholder.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
    loading.classList.remove('flex');
    btn.disabled = false;
  }
}

function renderAnalysisResult(data) {
  const container = document.getElementById('debugResultContainer');
  container.classList.remove('hidden');

  // Assessment Banner
  document.getElementById('debugAssessmentText').innerText = data.assessment || 'Analysis complete.';
  document.getElementById('debugSourcePill').innerText = `Source: ${data.source}`;

  // Evidence Cards Grid
  const cardsGrid = document.getElementById('evidenceCardsGrid');
  cardsGrid.innerHTML = '';

  (data.relevant_evidence || []).forEach(record => {
    const card = document.createElement('div');
    const borderCol = record.type === 'Bug' ? 'border-red-800/60 bg-red-950/20'
                    : record.type === 'Decision' ? 'border-purple-800/60 bg-purple-950/20'
                    : record.type === 'Test' ? 'border-lime-800/60 bg-lime-950/20'
                    : 'border-surface-700 bg-surface-800';

    card.className = `p-3 rounded-xl border ${borderCol} text-xs space-y-1.5 cursor-pointer hover:border-cyan-500 transition group`;
    card.onclick = () => {
      if (cy) {
        switchTab('graph');
        const target = cy.getElementById(record.id);
        if (target && target.length > 0) {
          cy.nodes().unselect();
          target.select();
          cy.center(target);
          displayNodeDetails(target.data());
          showToast(`Selected evidence entity: ${record.id} in Knowledge Graph`, 'info');
        }
      }
    };

    const statusBadge = record.type === 'Test' ? '<span class="text-[9px] uppercase font-bold px-1.5 py-0.2 rounded bg-lime-950 text-lime-300 border border-lime-800">Verified Outcome</span>'
                      : record.type === 'Decision' ? '<span class="text-[9px] uppercase font-bold px-1.5 py-0.2 rounded bg-purple-950 text-purple-300 border border-purple-800">Documented Fact</span>'
                      : '<span class="text-[9px] uppercase font-bold px-1.5 py-0.2 rounded bg-red-950 text-red-300 border border-red-800">Analogous Incident</span>';

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="font-mono font-bold text-cyan-300">${record.id}</span>
        <div class="flex items-center gap-1.5">
          <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-surface-700 text-slate-300">${record.type}</span>
          ${statusBadge}
        </div>
      </div>
      <p class="font-semibold text-slate-100 group-hover:text-cyan-200 transition">${record.title}</p>
      <div class="text-[11px] text-slate-400">
        ${record.details.root_cause ? `<span class="text-red-300">Root Cause:</span> ${record.details.root_cause}` : ''}
        ${record.details.reason ? `<span class="text-purple-300">Reason:</span> ${record.details.reason}` : ''}
        ${record.details.verification_status ? `<span class="text-lime-300">Verification:</span> ${record.details.verification_status}` : ''}
      </div>
      <div class="text-[10px] text-slate-500 flex items-center gap-1 pt-1 border-t border-surface-700/40">
        <i data-lucide="eye" class="w-3 h-3 text-cyan-400"></i>
        <span>Click to inspect in Knowledge Graph</span>
      </div>
    `;
    cardsGrid.appendChild(card);
  });

  // Markdown Answer
  const markdownBox = document.getElementById('debugMarkdownAnswer');
  if (window.marked) {
    markdownBox.innerHTML = marked.parse(data.answer);
  } else {
    markdownBox.innerText = data.answer;
  }

  // Paths List
  const pathsList = document.getElementById('debugPathsList');
  pathsList.innerHTML = '';
  (data.evidence_paths || []).forEach(pathStr => {
    const p = document.createElement('div');
    p.className = 'p-2 rounded bg-surface-800 border border-surface-700 text-slate-300 break-all';
    p.innerHTML = `<span class="text-cyan-400">PATH:</span> ${pathStr}`;
    pathsList.appendChild(p);
  });

  // Potential Root Causes (Hypotheses)
  const hypSec = document.getElementById('debugHypothesesSection');
  const hypList = document.getElementById('debugHypothesesList');
  if (hypSec && hypList) {
    const causes = data.potential_root_causes || [];
    if (causes.length > 0) {
      hypSec.classList.remove('hidden');
      hypList.innerHTML = '';
      causes.forEach((cause, idx) => {
        const item = document.createElement('div');
        item.className = 'p-3 rounded-xl border border-amber-900/40 bg-amber-950/20 text-xs flex items-start gap-2.5';
        item.innerHTML = `
          <div class="w-5 h-5 rounded-full bg-amber-900/60 text-amber-300 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">${idx + 1}</div>
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-[10px] font-bold uppercase px-1.5 py-0.2 rounded bg-amber-900/60 text-amber-200 border border-amber-800">Hypothesis</span>
              <span class="text-[10px] text-slate-400">Requires live verification</span>
            </div>
            <p class="text-slate-200 leading-relaxed">${cause}</p>
          </div>
        `;
        hypList.appendChild(item);
      });
    } else {
      hypSec.classList.add('hidden');
    }
  }

  // Suggested Checks Checklist
  const checksSec = document.getElementById('debugChecksSection');
  const checksList = document.getElementById('debugChecksList');
  if (checksSec && checksList) {
    const checks = data.suggested_checks || [];
    if (checks.length > 0) {
      checksSec.classList.remove('hidden');
      checksList.innerHTML = '';
      checks.forEach(check => {
        const row = document.createElement('label');
        row.className = 'flex items-start gap-2.5 p-2 rounded-lg hover:bg-surface-800 cursor-pointer text-xs transition';
        row.innerHTML = `
          <input type="checkbox" class="mt-0.5 rounded border-slate-700 text-cyan-600 focus:ring-0">
          <span class="text-slate-300 leading-normal">${check}</span>
        `;
        checksList.appendChild(row);
      });
    } else {
      checksSec.classList.add('hidden');
    }
  }

  // Suggested Tests
  const testsSec = document.getElementById('debugTestsSection');
  const testsList = document.getElementById('debugTestsList');
  if (testsSec && testsList) {
    const tests = data.suggested_tests || [];
    if (tests.length > 0) {
      testsSec.classList.remove('hidden');
      testsList.innerHTML = '';
      tests.forEach(testName => {
        const item = document.createElement('div');
        item.className = 'p-2.5 rounded-xl border border-lime-900/40 bg-lime-950/20 text-xs flex items-center justify-between';
        item.innerHTML = `
          <div class="flex items-center gap-2">
            <i data-lucide="check-circle-2" class="w-4 h-4 text-lime-400 shrink-0"></i>
            <span class="font-mono text-lime-300 font-semibold">${testName}</span>
          </div>
          <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-lime-900/80 text-lime-200">Recommended Suite</span>
        `;
        testsList.appendChild(item);
      });
    } else {
      testsSec.classList.add('hidden');
    }
  }

  // Limitations & Missing Context
  const limBox = document.getElementById('debugLimitationsBox');
  const limText = document.getElementById('debugLimitationsText');
  if (limBox && limText) {
    if (data.evidence_limitations) {
      limBox.classList.remove('hidden');
      limText.innerText = data.evidence_limitations;
    } else {
      limBox.classList.add('hidden');
    }
  }

  if (window.lucide) lucide.createIcons();
}

function copyMarkdownAnswer() {
  const content = document.getElementById('debugMarkdownAnswer').innerText;
  navigator.clipboard.writeText(content).then(() => {
    showToast('Synthesis markdown copied to clipboard', 'info');
  });
}

// ================= FEATURE C: CHANGE IMPACT ANALYSIS =================
let lastImpactResult = null;

async function handleRunImpact() {
  const checkboxes = document.querySelectorAll('input[name="impactComp"]:checked');
  const changedComps = Array.from(checkboxes).map(cb => cb.value);

  const filesInput = document.getElementById('impactFilesInput');
  const filesVal = filesInput ? filesInput.value.trim() : '';
  const changedFiles = filesVal ? filesVal.split(',').map(s => s.trim()).filter(Boolean) : [];

  if (changedComps.length === 0 && changedFiles.length === 0) {
    showToast('Please select at least one component or enter changed file paths', 'error');
    return;
  }

  const btn = document.getElementById('btnRunImpact');
  btn.disabled = true;

  try {
    const payload = {
      project_id: 'PRJ-SENTINEL',
      changed_components: changedComps,
    };
    if (changedFiles.length > 0) {
      payload.changed_files = changedFiles;
    }

    const res = await fetch('/api/impact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || 'Impact analysis failed');
    }
    const data = await res.json();
    lastImpactResult = data;
    renderImpactResult(data);
    showToast('Change impact graph traversal calculated', 'success');
  } catch (err) {
    console.error('Impact analysis error:', err);
    showToast(`Impact calculation failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
}

function renderImpactResult(data) {
  document.getElementById('impactPlaceholder').classList.add('hidden');
  const report = document.getElementById('impactReportContainer');
  report.classList.remove('hidden');

  // Priority Banner
  const banner = document.getElementById('impactPriorityBanner');
  const icon = document.getElementById('impactPriorityIcon');
  const badge = document.getElementById('impactPriorityBadge');

  if (data.heuristic_priority === 'HIGH') {
    banner.className = 'p-4 rounded-xl border border-red-800/80 bg-red-950/30 flex items-center justify-between';
    icon.className = 'w-10 h-10 rounded-lg bg-red-900/60 text-red-400 flex items-center justify-center font-black';
    badge.className = 'text-xs font-extrabold px-2.5 py-0.5 rounded-full uppercase bg-red-900 text-red-200 border border-red-700';
    badge.innerText = 'HIGH RISK';
  } else if (data.heuristic_priority === 'MEDIUM') {
    banner.className = 'p-4 rounded-xl border border-amber-800/80 bg-amber-950/30 flex items-center justify-between';
    icon.className = 'w-10 h-10 rounded-lg bg-amber-900/60 text-amber-400 flex items-center justify-center font-black';
    badge.className = 'text-xs font-extrabold px-2.5 py-0.5 rounded-full uppercase bg-amber-900 text-amber-200 border border-amber-700';
    badge.innerText = 'MEDIUM RISK';
  } else {
    banner.className = 'p-4 rounded-xl border border-emerald-800/80 bg-emerald-950/30 flex items-center justify-between';
    icon.className = 'w-10 h-10 rounded-lg bg-emerald-900/60 text-emerald-400 flex items-center justify-center font-black';
    badge.className = 'text-xs font-extrabold px-2.5 py-0.5 rounded-full uppercase bg-emerald-900 text-emerald-200 border border-emerald-700';
    badge.innerText = 'LOW RISK';
  }

  document.getElementById('impactPriorityReason').innerText =
    (data.priority_reasons || []).join(' | ') || 'Heuristic evaluation complete.';

  // Affected Components List
  const affList = document.getElementById('affectedComponentsList');
  affList.innerHTML = '';
  (data.affected_components || []).forEach(aff => {
    const item = document.createElement('div');
    const isDirect = aff.tier === 'direct';
    item.className = `p-3 rounded-xl border ${isDirect ? 'border-cyan-800/60 bg-cyan-950/20' : 'border-surface-700 bg-surface-800'} text-xs flex items-center justify-between`;
    item.innerHTML = `
      <div>
        <div class="flex items-center gap-2">
          <span class="font-bold text-slate-100">${aff.name}</span>
          <span class="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${isDirect ? 'bg-cyan-900 text-cyan-300' : 'bg-surface-700 text-slate-400'}">${aff.tier}</span>
        </div>
        <p class="text-[11px] text-slate-400 mt-0.5">${aff.reason}</p>
      </div>
      <div class="font-mono text-[10px] text-slate-500">${(aff.path || []).join(' ➔ ')}</div>
    `;
    affList.appendChild(item);
  });

  // Historical Risks
  const risksList = document.getElementById('impactHistoricalRisksList');
  risksList.innerHTML = '';
  if ((data.historical_risks || []).length === 0) {
    risksList.innerHTML = '<p class="text-xs text-slate-500 italic p-3 bg-surface-800 rounded-lg">No historical bugs recorded on the affected component paths.</p>';
  } else {
    data.historical_risks.forEach(risk => {
      const item = document.createElement('div');
      item.className = 'p-3 rounded-xl border border-red-900/40 bg-red-950/20 text-xs space-y-1';
      item.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-mono font-bold text-red-400">${risk.bug_id}</span>
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-900/80 text-red-200">${risk.component}</span>
        </div>
        <p class="font-semibold text-slate-200">${risk.title}</p>
        <p class="text-[11px] text-slate-400"><strong class="text-red-300">Root Cause:</strong> ${risk.root_cause || 'Documented in incident record'}</p>
      `;
      risksList.appendChild(item);
    });
  }

  // Pre-merge Test Suite
  const testsList = document.getElementById('impactTestsList');
  testsList.innerHTML = '';
  if ((data.suggested_tests || []).length === 0) {
    testsList.innerHTML = '<p class="text-xs text-slate-500 italic p-3 bg-surface-800 rounded-lg">Run standard component unit test suites.</p>';
  } else {
    data.suggested_tests.forEach(test => {
      const item = document.createElement('div');
      item.className = 'p-3 rounded-xl border border-emerald-900/40 bg-emerald-950/20 text-xs space-y-1';
      item.innerHTML = `
        <div class="flex items-center justify-between">
          <span class="font-mono font-bold text-emerald-400">${test.test_id}</span>
          <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-900/80 text-emerald-200">${test.target_component}</span>
        </div>
        <p class="font-semibold text-slate-200">${test.title}</p>
        <p class="text-[11px] text-slate-400">${test.description || 'Validates critical regression flow'}</p>
      `;
      testsList.appendChild(item);
    });
  }

  // Technical Decisions
  const decList = document.getElementById('impactDecisionsList');
  if (decList) {
    decList.innerHTML = '';
    if ((data.technical_decisions || []).length === 0) {
      decList.innerHTML = '<p class="text-xs text-slate-500 italic p-3 bg-surface-800 rounded-lg">No architectural decisions recorded on the affected component paths.</p>';
    } else {
      data.technical_decisions.forEach(dec => {
        const item = document.createElement('div');
        item.className = 'p-3 rounded-xl border border-purple-900/40 bg-purple-950/20 text-xs space-y-1';
        item.innerHTML = `
          <div class="flex items-center justify-between">
            <span class="font-mono font-bold text-purple-400">${dec.decision_id}</span>
            <span class="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-900/80 text-purple-200">${dec.component}</span>
          </div>
          <p class="font-semibold text-slate-200">${dec.title}</p>
          <p class="text-[11px] text-slate-400"><strong class="text-purple-300">Rationale:</strong> ${dec.reason || 'Documented architectural choice'}</p>
        `;
        decList.appendChild(item);
      });
    }
  }

  // Disclaimer text
  const disc = document.getElementById('impactDisclaimerText');
  if (disc && data.disclaimer) {
    disc.innerText = data.disclaimer;
  }

  if (window.lucide) lucide.createIcons();
}

function visualizeImpactOnGraph() {
  switchTab('graph');
  if (!cy) return;

  // Build target set from lastImpactResult if available
  const targetNamesAndIds = new Set();
  const directNames = new Set();

  if (lastImpactResult) {
    (lastImpactResult.affected_components || []).forEach(aff => {
      targetNamesAndIds.add(aff.name);
      if (aff.component_id) targetNamesAndIds.add(aff.component_id);
      if (aff.tier === 'direct') directNames.add(aff.name);
    });
    (lastImpactResult.historical_risks || []).forEach(r => {
      targetNamesAndIds.add(r.bug_id);
      if (r.component) targetNamesAndIds.add(r.component);
    });
    (lastImpactResult.technical_decisions || []).forEach(d => {
      targetNamesAndIds.add(d.decision_id);
      if (d.component) targetNamesAndIds.add(d.component);
    });
    (lastImpactResult.suggested_tests || []).forEach(t => {
      targetNamesAndIds.add(t.test_id);
      if (t.target_component) targetNamesAndIds.add(t.target_component);
    });
  } else {
    const checkboxes = document.querySelectorAll('input[name="impactComp"]:checked');
    checkboxes.forEach(cb => targetNamesAndIds.add(cb.value));
  }

  cy.elements().removeClass('highlighted dimmed');

  cy.batch(() => {
    cy.nodes().forEach(node => {
      const name = node.data('fullLabel');
      const id = node.id();
      if (targetNamesAndIds.has(name) || targetNamesAndIds.has(id)) {
        node.addClass('highlighted');
      } else {
        node.addClass('dimmed');
      }
    });

    cy.edges().forEach(edge => {
      const src = edge.source();
      const tgt = edge.target();
      const srcName = src.data('fullLabel');
      const tgtName = tgt.data('fullLabel');
      const srcId = src.id();
      const tgtId = tgt.id();

      if ((targetNamesAndIds.has(srcName) || targetNamesAndIds.has(srcId)) &&
          (targetNamesAndIds.has(tgtName) || targetNamesAndIds.has(tgtId))) {
        edge.addClass('highlighted');
      } else {
        edge.addClass('dimmed');
      }
    });
  });

  const highlightedNodes = cy.elements('node.highlighted');
  if (highlightedNodes.length > 0) {
    cy.animate({
      fit: {
        eles: highlightedNodes,
        padding: 50,
      },
      duration: 500,
    });
  }

  showToast('Highlighting downstream impact path in Knowledge Graph', 'info');
}

// ================= FEATURE A: PROJECT MEMORY CAPTURE =================
function openMemoryModal() {
  document.getElementById('memoryModal').classList.remove('hidden');
  document.getElementById('memoryModal').classList.add('flex');
}

function closeMemoryModal() {
  document.getElementById('memoryModal').classList.add('hidden');
  document.getElementById('memoryModal').classList.remove('flex');
}

function switchMemoryType(type) {
  document.getElementById('memTypeInput').value = type;
  const decBtn = document.getElementById('memTypeBtn-decision');
  const bugBtn = document.getElementById('memTypeBtn-bug');
  const decFields = document.getElementById('memDecisionFields');
  const bugFields = document.getElementById('memBugFields');

  if (type === 'decision') {
    decBtn.className = 'flex-1 py-1.5 text-xs font-semibold rounded bg-purple-600 text-white transition';
    bugBtn.className = 'flex-1 py-1.5 text-xs font-semibold rounded text-slate-400 hover:text-white transition';
    decFields.classList.remove('hidden');
    bugFields.classList.add('hidden');
  } else {
    bugBtn.className = 'flex-1 py-1.5 text-xs font-semibold rounded bg-red-600 text-white transition';
    decBtn.className = 'flex-1 py-1.5 text-xs font-semibold rounded text-slate-400 hover:text-white transition';
    bugFields.classList.remove('hidden');
    decFields.classList.add('hidden');
  }
}

async function handleSaveMemory(evt) {
  evt.preventDefault();
  const memoryType = document.getElementById('memTypeInput').value;
  const title = document.getElementById('memTitle').value.trim();
  const component = document.getElementById('memComponent').value;

  const payload = {
    memory_type: memoryType,
    project_id: 'PRJ-SENTINEL',
    title: title,
    affected_component: component,
    source: 'Manual Dashboard Input',
  };

  if (memoryType === 'decision') {
    payload.reason = document.getElementById('memReason').value.trim();
    payload.description = document.getElementById('memDescription').value.trim();
    payload.dependency = document.getElementById('memDependency').value.trim() || null;
    payload.author = document.getElementById('memAuthor').value.trim() || 'Engineering Team';
  } else {
    payload.symptom = document.getElementById('memSymptom').value.trim();
    payload.root_cause = document.getElementById('memRootCause').value.trim() || null;
    payload.resolution = document.getElementById('memResolution').value.trim() || null;
    payload.verification = document.getElementById('memVerification').value.trim() || null;
  }

  const btn = document.getElementById('btnSubmitMemory');
  btn.disabled = true;

  try {
    const res = await fetch('/api/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || 'Failed to save memory');
    }

    const data = await res.json();
    showToast(`Memory saved: ${data.entity_id} (${data.entity_type})`, 'success');
    closeMemoryModal();
    document.getElementById('memoryForm').reset();

    // Reload graph and activity immediately
    await loadGraph();
    await loadActivity();
  } catch (err) {
    console.error('Error saving memory:', err);
    showToast(`Error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
}

// ================= ACTIVITY TIMELINE =================
async function loadActivity() {
  try {
    const res = await fetch('/api/activity?project_id=PRJ-SENTINEL');
    if (!res.ok) return;
    const activities = await res.json();

    const timeline = document.getElementById('activityTimeline');
    if (!timeline) return;
    timeline.innerHTML = '';

    activities.forEach(item => {
      const entry = document.createElement('div');
      const isBug = item.event_type.includes('BUG') || item.event_type.includes('INCIDENT');
      const isDec = item.event_type.includes('DECISION');
      const isSeed = item.event_type.includes('SEED');

      const color = isBug ? 'text-red-400 bg-red-950 border-red-800'
                  : isDec ? 'text-purple-400 bg-purple-950 border-purple-800'
                  : isSeed ? 'text-cyan-400 bg-cyan-950 border-cyan-800'
                  : 'text-emerald-400 bg-emerald-950 border-emerald-800';

      const timeFormatted = new Date(item.timestamp).toLocaleString();

      entry.className = 'glass-card p-4 rounded-xl flex items-start gap-3 text-xs';
      entry.innerHTML = `
        <div class="p-2 rounded-lg border ${color} shrink-0 mt-0.5">
          <i data-lucide="${isBug ? 'alert-triangle' : isDec ? 'git-commit' : isSeed ? 'database' : 'check'}" class="w-4 h-4"></i>
        </div>
        <div class="flex-1 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-slate-100">${item.title}</span>
            <span class="text-[10px] text-slate-500 font-mono">${timeFormatted}</span>
          </div>
          <div class="flex items-center gap-2">
            <span class="font-mono text-cyan-400 font-semibold">${item.entity_id}</span>
            <span class="text-slate-500">•</span>
            <span class="text-slate-400">Component: <strong class="text-slate-300">${item.component}</strong></span>
          </div>
          <p class="text-slate-400 text-[11px] leading-relaxed">${item.summary}</p>
        </div>
      `;
      timeline.appendChild(entry);
    });

    if (window.lucide) lucide.createIcons();
  } catch (err) {
    console.warn('Failed to load activity log:', err);
  }
}

// ================= SEED DEMO GRAPH =================
async function handleSeedDemo() {
  const btn = document.getElementById('btnSeedDemo');
  btn.disabled = true;
  btn.classList.add('opacity-50');

  try {
    const res = await fetch('/api/seed', { method: 'POST' });
    if (!res.ok) throw new Error('Demo seeding failed');
    const data = await res.json();

    showToast(`Seeded demo graph baseline (${data.database})`, 'success');
    await checkHealth();
    await loadGraph();
    await loadActivity();
  } catch (err) {
    console.error('Seeding error:', err);
    showToast(`Seed failed: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.classList.remove('opacity-50');
  }
}
