// CodeBrain AI — Frontend Application Logic
// Every Bug Has a History

// Backend Base URL Configuration:
// Automatically targets the production Render backend when deployed on Vercel or custom domains.
// Uses relative paths when served directly by the FastAPI backend or when on localhost.
const RENDER_BACKEND_URL = 'https://code-brain-ai-jta8.onrender.com';

function getApiBaseUrl() {
  if (typeof window !== 'undefined' && window.API_BASE_URL) {
    return window.API_BASE_URL.replace(/\/+$/, '');
  }
  if (typeof window !== 'undefined' && window.location) {
    const host = window.location.hostname;
    const port = window.location.port;

    // Local development
    if (host === 'localhost' || host === '127.0.0.1' || host === '0.0.0.0') {
      if (port && port !== '8000') {
        return 'http://localhost:8000';
      }
      return '';
    }

    // Direct Render backend deployment
    if (host.includes('onrender.com')) {
      return '';
    }
  }
  return RENDER_BACKEND_URL;
}

const API_BASE = getApiBaseUrl();

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

let currentProjectId = 'PRJ-SENTINEL';
let currentMemoryFilter = 'all';
let currentMemorySearch = '';

// Initialize Application on DOM Ready
document.addEventListener('DOMContentLoaded', async () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  
  // Restore sidebar collapse state
  const isCollapsed = localStorage.getItem('codebrain_sidebar_collapsed') === 'true';
  const sidebar = document.getElementById('leftSidebar');
  const collapseIcon = document.getElementById('sidebarCollapseIcon');
  if (isCollapsed && sidebar) {
    sidebar.classList.add('collapsed');
    if (collapseIcon) collapseIcon.setAttribute('data-lucide', 'panel-left-open');
  }

  // Close user menu on outside click
  window.addEventListener('click', (e) => {
    const userMenu = document.getElementById('userMenuDropdown');
    const userBtn = document.getElementById('btnUserMenu');
    if (userMenu && !userMenu.classList.contains('hidden')) {
      if (userBtn && !userBtn.contains(e.target) && !userMenu.contains(e.target)) {
        userMenu.classList.add('hidden');
      }
    }
  });

  await checkHealth();
  await populateProjectSelector();
  await loadGraph(currentProjectId);
  await loadActivity(currentProjectId);
  switchTab('overview');
});

// Dynamic Project Selector Population
async function populateProjectSelector() {
  const select = document.getElementById('projectSelector');
  if (!select) return;

  try {
    const res = await fetch(`${API_BASE}/api/projects`);
    if (!res.ok) return;
    const projects = await res.json();
    if (Array.isArray(projects) && projects.length > 0) {
      select.innerHTML = projects.map(p => `
        <option value="${p.id}" class="bg-surface-850 text-slate-100" ${p.id === currentProjectId ? 'selected' : ''}>
          ${p.name || p.id}
        </option>
      `).join('');
    }
  } catch (err) {
    console.warn('Could not populate projects list, using default:', err);
  }
}

async function handleProjectChange(projectId) {
  if (!projectId || projectId === currentProjectId) return;
  currentProjectId = projectId;
  showToast(`Switching to project: ${projectId}`, 'info');

  const headerProjectName = document.getElementById('headerProjectName');
  if (headerProjectName) headerProjectName.innerText = projectId;

  await loadGraph(projectId);
  await loadActivity(projectId);
}

// Sidebar Collapse / Expand Toggle
function toggleSidebarCollapse() {
  const sidebar = document.getElementById('leftSidebar');
  const collapseIcon = document.getElementById('sidebarCollapseIcon');
  if (!sidebar) return;

  sidebar.classList.toggle('collapsed');
  const isCollapsed = sidebar.classList.contains('collapsed');
  localStorage.setItem('codebrain_sidebar_collapsed', isCollapsed);

  if (collapseIcon) {
    collapseIcon.setAttribute('data-lucide', isCollapsed ? 'panel-left-open' : 'panel-left-close');
    if (window.lucide) lucide.createIcons();
  }

  // Resize graph canvas if visible
  setTimeout(() => {
    if (cy) {
      cy.resize();
      cy.fit(undefined, 40);
    }
  }, 240);
}

// Mobile Slide-Out Drawer Navigation
function toggleMobileNav() {
  const sidebar = document.getElementById('leftSidebar');
  const overlay = document.getElementById('mobileNavOverlay');
  if (!sidebar || !overlay) return;

  const isClosed = sidebar.classList.contains('-translate-x-full');
  if (isClosed) {
    sidebar.classList.remove('-translate-x-full');
    sidebar.classList.add('translate-x-0');
    overlay.classList.remove('hidden');
  } else {
    closeMobileNav();
  }
}

function closeMobileNav() {
  const sidebar = document.getElementById('leftSidebar');
  const overlay = document.getElementById('mobileNavOverlay');
  if (sidebar) {
    sidebar.classList.add('-translate-x-full');
    sidebar.classList.remove('translate-x-0');
  }
  if (overlay) {
    overlay.classList.add('hidden');
  }
}

// User Profile / Settings Menu Toggle
function toggleUserMenu() {
  const dropdown = document.getElementById('userMenuDropdown');
  if (dropdown) dropdown.classList.toggle('hidden');
}

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

// Enhanced Workspace Tab Switching
function switchTab(tabName) {
  // Hide all workspace content containers
  document.querySelectorAll('.tab-content').forEach(el => {
    el.classList.add('hidden');
    el.classList.remove('flex');
  });

  // Reset all sidebar navigation item styles
  document.querySelectorAll('.sidebar-nav-item').forEach(btn => {
    btn.classList.remove('bg-cyan-950/70', 'border-cyan-800/80', 'text-cyan-300', 'shadow-sm', 'font-semibold');
    btn.classList.add('text-slate-400', 'font-medium', 'border-transparent');
    const icon = btn.querySelector('i');
    if (icon) {
      icon.classList.remove('text-cyan-400', 'text-blue-400', 'text-amber-400', 'text-purple-400', 'text-emerald-400');
      icon.classList.add('text-slate-400');
    }
  });

  // Activate target content
  const targetContent = document.getElementById(`tabContent-${tabName}`);
  if (targetContent) {
    targetContent.classList.remove('hidden');
    targetContent.classList.add('flex');
  }

  // Activate target sidebar button
  const targetSidebarBtn = document.getElementById(`sidebarBtn-${tabName}`);
  if (targetSidebarBtn) {
    targetSidebarBtn.classList.remove('text-slate-400', 'font-medium', 'border-transparent');
    targetSidebarBtn.classList.add('bg-cyan-950/70', 'border-cyan-800/80', 'text-cyan-300', 'shadow-sm', 'font-semibold');
    const icon = targetSidebarBtn.querySelector('i');
    if (icon) {
      icon.classList.remove('text-slate-400');
      const activeColor = tabName === 'debug' ? 'text-blue-400'
                        : tabName === 'impact' ? 'text-amber-400'
                        : tabName === 'memory' ? 'text-purple-400'
                        : tabName === 'chat' ? 'text-emerald-400'
                        : 'text-cyan-400';
      icon.classList.add(activeColor);
    }
  }

  // Floating Chat Launcher visibility
  const floatingLauncher = document.getElementById('floatingChatLauncher');
  if (floatingLauncher) {
    if (tabName === 'chat') {
      floatingLauncher.classList.add('hidden');
    } else {
      floatingLauncher.classList.remove('hidden');
    }
  }

  // Workspace-specific initializations
  if (tabName === 'graph') {
    setTimeout(() => {
      if (cy) {
        cy.resize();
        cy.fit(undefined, 40);
      } else if (currentGraphData && currentGraphData.nodes) {
        initCytoscape(currentGraphData);
      }
    }, 120);
  } else if (tabName === 'memory') {
    renderMemoryWorkspace(currentGraphData);
  } else if (tabName === 'chat') {
    const projLabel = document.getElementById('chatActiveProjectLabel');
    if (projLabel) {
      const projSelect = document.getElementById('projectSelector');
      projLabel.textContent = projSelect && projSelect.selectedOptions[0] ? projSelect.selectedOptions[0].text : currentProjectId;
    }
    setTimeout(() => {
      const input = document.getElementById('chatInputText');
      if (input) input.focus();
    }, 100);
  }

  closeMobileNav();
  if (window.lucide) lucide.createIcons();
}

// Health & System Diagnostics
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
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
    const res = await fetch(`${API_BASE}/api/graph?project_id=${encodeURIComponent(projectId)}`);
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
    const res = await fetch(`${API_BASE}/api/analyze`, {
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

    const res = await fetch(`${API_BASE}/api/impact`, {
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
    const res = await fetch(`${API_BASE}/api/memory`, {
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
async function loadActivity(projectId = currentProjectId) {
  try {
    const res = await fetch(`${API_BASE}/api/activity?project_id=${encodeURIComponent(projectId)}`);
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
  if (btn) {
    btn.disabled = true;
    btn.classList.add('opacity-50');
  }

  try {
    const res = await fetch(`${API_BASE}/api/seed`, { method: 'POST' });
    if (!res.ok) throw new Error('Demo seeding failed');
    const data = await res.json();

    showToast(`Seeded demo graph baseline (${data.database})`, 'success');
    await checkHealth();
    await loadGraph(currentProjectId);
    await loadActivity(currentProjectId);
  } catch (err) {
    console.error('Seeding error:', err);
    showToast(`Seed failed: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.classList.remove('opacity-50');
    }
  }
}

// ================= PROJECT MEMORY WORKSPACE =================
function filterMemoryWorkspace(category) {
  currentMemoryFilter = category;
  document.querySelectorAll('.memory-filter-btn').forEach(btn => {
    if (btn.getAttribute('data-filter') === category) {
      btn.classList.remove('bg-surface-800', 'text-slate-400');
      btn.classList.add('bg-cyan-600', 'text-white', 'font-semibold');
    } else {
      btn.classList.remove('bg-cyan-600', 'text-white', 'font-semibold');
      btn.classList.add('bg-surface-800', 'text-slate-400');
    }
  });
  renderMemoryWorkspace(currentGraphData);
}

function handleMemorySearch(query) {
  currentMemorySearch = (query || '').trim().toLowerCase();
  renderMemoryWorkspace(currentGraphData);
}

function renderMemoryWorkspace(data = currentGraphData) {
  const grid = document.getElementById('memoryCardsGrid');
  if (!grid) return;

  const nodes = (data && data.nodes) ? data.nodes : [];
  
  const items = nodes.filter(n => {
    const label = n.label || (n.labels && n.labels[0]) || '';
    if (label === 'Project' || label === 'Developer') return false;
    if (currentMemoryFilter !== 'all' && label !== currentMemoryFilter) return false;
    if (currentMemorySearch) {
      const idMatch = (n.id || '').toLowerCase().includes(currentMemorySearch);
      const titleMatch = (n.properties?.title || n.properties?.name || '').toLowerCase().includes(currentMemorySearch);
      const descMatch = (n.properties?.description || n.properties?.symptom || n.properties?.root_cause || n.properties?.reason || '').toLowerCase().includes(currentMemorySearch);
      return idMatch || titleMatch || descMatch;
    }
    return true;
  });

  if (items.length === 0) {
    grid.innerHTML = `
      <div class="col-span-full py-12 text-center bg-surface-850 rounded-2xl border border-surface-700 p-8">
        <i data-lucide="inbox" class="w-8 h-8 text-slate-500 mx-auto mb-2"></i>
        <p class="font-bold text-slate-300 text-sm">No memory records found</p>
        <p class="text-xs text-slate-500 mt-1">Try clearing filters or search query, or capture a new architectural memory.</p>
        <button onclick="openMemoryModal()" class="mt-4 px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg">
          + Capture Project Memory
        </button>
      </div>
    `;
    if (window.lucide) lucide.createIcons();
    return;
  }

  grid.innerHTML = items.map(n => {
    const label = n.label || (n.labels && n.labels[0]) || 'Memory';
    const p = n.properties || {};
    const color = NODE_COLORS[label] || '#06b6d4';
    const border = label === 'Decision' ? 'border-purple-800/60 bg-purple-950/15'
                 : label === 'Bug' ? 'border-red-800/60 bg-red-950/15'
                 : label === 'Fix' ? 'border-emerald-800/60 bg-emerald-950/15'
                 : label === 'Dependency' ? 'border-amber-800/60 bg-amber-950/15'
                 : label === 'Test' ? 'border-lime-800/60 bg-lime-950/15'
                 : 'border-cyan-800/60 bg-cyan-950/15';

    const title = p.title || p.name || n.id;
    const desc = p.reason || p.root_cause || p.description || p.symptom || 'Linked graph entity in project memory mesh';
    const badge = p.author || p.status || p.test_type || (p.version ? `v${p.version}` : 'Verified');

    return `
      <div class="glass-card p-4 rounded-xl border ${border} flex flex-col justify-between hover:border-cyan-500/60 transition group">
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="font-mono text-xs font-bold" style="color: ${color}">${n.id}</span>
            <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-surface-800 border border-surface-600 text-slate-300">${label}</span>
          </div>
          <h4 class="font-bold text-sm text-slate-100 group-hover:text-cyan-300 transition leading-snug">${title}</h4>
          <p class="text-xs text-slate-400 mt-2 line-clamp-3 leading-relaxed">${desc}</p>
        </div>
        <div class="mt-4 pt-3 border-t border-surface-700/60 flex items-center justify-between text-xs">
          <span class="text-[10px] text-slate-500 font-mono">${badge}</span>
          <button onclick="inspectEntityFromMemory('${n.id}')" class="text-cyan-400 hover:text-cyan-300 font-semibold text-[11px] flex items-center gap-1">
            <span>Inspect in Graph</span>
            <i data-lucide="arrow-right" class="w-3 h-3"></i>
          </button>
        </div>
      </div>
    `;
  }).join('');

  if (window.lucide) lucide.createIcons();
}

function inspectEntityFromMemory(nodeId) {
  switchTab('graph');
  setTimeout(() => {
    if (cy) {
      const node = cy.getElementById(nodeId);
      if (node && node.length > 0) {
        cy.nodes().removeClass('selected');
        node.addClass('selected');
        cy.animate({ center: { eles: node }, zoom: 1.4, duration: 400 });
        selectNode(node.data());
      }
    }
  }, 200);
}

// ================= CONTEXT-AWARE AI CHAT ASSISTANT =================
let chatConversationId = 'conv-' + Math.random().toString(36).substring(2, 10);
let chatHistory = [];
let isChatSending = false;
let lastFailedMessage = null;

function startNewChat() {
  chatConversationId = 'conv-' + Math.random().toString(36).substring(2, 10);
  chatHistory = [];
  lastFailedMessage = null;

  const thread = document.getElementById('chatThread');
  if (thread) thread.innerHTML = '';

  const welcome = document.getElementById('chatWelcomeState');
  if (welcome) welcome.classList.remove('hidden');

  const input = document.getElementById('chatInputText');
  if (input) {
    input.value = '';
    input.style.height = 'auto';
    input.focus();
  }

  showToast('Started new chat conversation', 'info');
  if (window.lucide) lucide.createIcons();
}

function sendSuggestedQuestion(question) {
  const input = document.getElementById('chatInputText');
  if (!input) return;
  input.value = question;
  handleChatSend();
}

function handleChatKeydown(event) {
  const input = event.target;
  // Auto-resize textarea height
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 128) + 'px';

  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    handleChatSend();
  }
}

async function handleChatSend() {
  if (isChatSending) return;

  const input = document.getElementById('chatInputText');
  if (!input) return;
  const message = input.value.trim();
  if (!message) return;

  // Clear input & reset height
  input.value = '';
  input.style.height = 'auto';

  // Hide welcome state
  const welcome = document.getElementById('chatWelcomeState');
  if (welcome) welcome.classList.add('hidden');

  // Render User Message
  appendUserMessage(message);

  // Keep history updated (bounded to last 10 messages)
  chatHistory.push({ role: 'user', content: message });
  if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);

  // Show loading indicator
  setChatLoading(true);
  scrollToChatBottom();

  try {
    const payload = {
      message: message,
      conversation_id: chatConversationId,
      project_id: currentProjectId,
      history: chatHistory.slice(0, -1), // previous turns
    };

    const res = await fetch(`${API_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Chat request failed (HTTP ${res.status})`);
    }

    const data = await res.json();
    setChatLoading(false);

    // Save assistant response to history
    chatHistory.push({ role: 'assistant', content: data.answer });
    if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);

    // Update conversation ID if returned
    if (data.conversation_id) chatConversationId = data.conversation_id;

    // Update provider pill
    const providerPill = document.getElementById('chatProviderPillText');
    if (providerPill) {
      providerPill.textContent = data.ai_provider === 'OpenAI' ? `OpenAI ${data.model_used || ''}`.trim() : 'Grounded Neo4j Engine';
    }

    // Append Assistant Message
    appendAssistantMessage(data);
    scrollToChatBottom();
  } catch (err) {
    console.error('Chat Assistant Error:', err);
    setChatLoading(false);
    lastFailedMessage = message;
    appendErrorMessage(err.message);
    scrollToChatBottom();
    showToast(`Assistant Error: ${err.message}`, 'error');
  }
}

function setChatLoading(isLoading) {
  isChatSending = isLoading;
  const loading = document.getElementById('chatLoadingIndicator');
  const btn = document.getElementById('btnChatSend');
  if (loading) {
    if (isLoading) loading.classList.remove('hidden');
    else loading.classList.add('hidden');
  }
  if (btn) {
    btn.disabled = isLoading;
  }
  if (window.lucide) lucide.createIcons();
}

function scrollToChatBottom() {
  const container = document.getElementById('chatMessagesContainer');
  if (container) {
    setTimeout(() => {
      container.scrollTop = container.scrollHeight;
    }, 50);
  }
}

function appendUserMessage(text) {
  const thread = document.getElementById('chatThread');
  if (!thread) return;

  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const msgDiv = document.createElement('div');
  msgDiv.className = 'flex justify-end';
  msgDiv.innerHTML = `
    <div class="max-w-[85%] sm:max-w-[75%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-cyan-900/60 to-blue-900/60 border border-cyan-700/50 p-4 text-xs sm:text-sm text-slate-100 shadow-lg">
      <div class="flex items-center justify-between gap-4 mb-1 text-[10px] text-cyan-300/80 font-mono">
        <span class="font-bold">You</span>
        <span>${now}</span>
      </div>
      <p class="whitespace-pre-wrap leading-relaxed">${escapeHtml(text)}</p>
    </div>
  `;
  thread.appendChild(msgDiv);
}

function appendAssistantMessage(data) {
  const thread = document.getElementById('chatThread');
  if (!thread) return;

  const msgId = 'msg-' + Math.random().toString(36).substring(2, 9);
  const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // Render Markdown safely
  let rawHtml = '';
  if (window.marked && typeof marked.parse === 'function') {
    rawHtml = marked.parse(data.answer || '');
  } else {
    rawHtml = `<p class="whitespace-pre-wrap">${escapeHtml(data.answer || '')}</p>`;
  }

  // Build evidence section if present
  let evidenceHtml = '';
  if (data.evidence && data.evidence.length > 0) {
    const evidenceCards = data.evidence.map(ev => {
      const typeColor = ev.type === 'Bug' ? 'border-red-800/80 bg-red-950/20 text-red-300'
                      : ev.type === 'Decision' ? 'border-purple-800/80 bg-purple-950/20 text-purple-300'
                      : ev.type === 'Component' ? 'border-cyan-800/80 bg-cyan-950/20 text-cyan-300'
                      : ev.type === 'Fix' ? 'border-emerald-800/80 bg-emerald-950/20 text-emerald-300'
                      : ev.type === 'Test' ? 'border-lime-800/80 bg-lime-950/20 text-lime-300'
                      : 'border-amber-800/80 bg-amber-950/20 text-amber-300';

      const sourceBadge = ev.source === 'Project Memory'
        ? '<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-800">Project Memory</span>'
        : ev.source === 'Hypothesis'
        ? '<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-amber-950 text-amber-300 border border-amber-800">Hypothesis</span>'
        : '<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-slate-800 text-slate-300 border border-slate-700">General Guidance</span>';

      return `
        <div class="glass-card p-3 rounded-xl border ${typeColor} text-xs flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <span class="font-mono font-bold text-xs">${ev.id}</span>
              <div class="flex items-center gap-1">
                <span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-surface-800 border border-surface-700 text-slate-300">${ev.type}</span>
                ${sourceBadge}
              </div>
            </div>
            <h5 class="font-bold text-slate-100 text-xs">${escapeHtml(ev.title)}</h5>
            <p class="text-[11px] text-slate-400 mt-1 leading-snug line-clamp-3">${escapeHtml(ev.description || '')}</p>
          </div>
          <div class="mt-2.5 pt-2 border-t border-surface-700/60 flex items-center justify-between text-[11px]">
            <span class="text-slate-500 font-mono text-[10px] truncate max-w-[150px]">${escapeHtml(ev.related_to || '')}</span>
            <button onclick="inspectEntityFromMemory('${ev.id}')" class="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 text-[11px]" title="Center in Cytoscape graph">
              <span>Inspect</span>
              <i data-lucide="arrow-up-right" class="w-3 h-3"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    evidenceHtml = `
      <div class="mt-4 pt-3 border-t border-surface-700/70">
        <details class="group/evidence" open>
          <summary class="cursor-pointer flex items-center justify-between text-xs font-bold text-cyan-300 select-none hover:text-cyan-200 transition">
            <div class="flex items-center gap-1.5">
              <i data-lucide="database" class="w-3.5 h-3.5 text-cyan-400"></i>
              <span>Project Evidence (${data.evidence.length} Recorded Knowledge Records)</span>
            </div>
            <i data-lucide="chevron-down" class="w-3.5 h-3.5 text-slate-400 group-open/evidence:rotate-180 transition-transform"></i>
          </summary>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 mt-3">
            ${evidenceCards}
          </div>
        </details>
      </div>
    `;
  }

  // Suggested Actions section
  let actionsHtml = '';
  if (data.suggested_actions && data.suggested_actions.length > 0) {
    const actionList = data.suggested_actions.map(act => `
      <li class="flex items-start gap-2 text-xs text-slate-300">
        <i data-lucide="check-circle-2" class="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0"></i>
        <span>${escapeHtml(act)}</span>
      </li>
    `).join('');
    actionsHtml = `
      <div class="mt-3.5 pt-3 border-t border-surface-700/70">
        <h5 class="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
          <i data-lucide="list-checks" class="w-3.5 h-3.5 text-cyan-400"></i>
          <span>Suggested Next Steps</span>
        </h5>
        <ul class="space-y-1.5">
          ${actionList}
        </ul>
      </div>
    `;
  }

  // Follow-up question chips
  let followUpHtml = '';
  if (data.follow_up_questions && data.follow_up_questions.length > 0) {
    const chips = data.follow_up_questions.map(q => `
      <button onclick="sendSuggestedQuestion('${escapeJsString(q)}')" class="px-3 py-1.5 rounded-xl bg-surface-800 hover:bg-surface-750 hover:border-cyan-500/60 border border-surface-700 text-xs text-cyan-300 hover:text-white transition flex items-center gap-1.5 text-left group">
        <i data-lucide="arrow-right-circle" class="w-3 h-3 text-cyan-400 group-hover:translate-x-0.5 transition-transform"></i>
        <span>${escapeHtml(q)}</span>
      </button>
    `).join('');
    followUpHtml = `
      <div class="mt-3.5 pt-3 border-t border-surface-700/70">
        <div class="flex items-center gap-1.5 mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-400">
          <i data-lucide="help-circle" class="w-3.5 h-3.5 text-cyan-400"></i>
          <span>Suggested Follow-Ups</span>
        </div>
        <div class="flex flex-wrap gap-2">
          ${chips}
        </div>
      </div>
    `;
  }

  const msgDiv = document.createElement('div');
  msgDiv.className = 'flex items-start gap-3';
  msgDiv.id = msgId;
  msgDiv.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 flex items-center justify-center text-white shrink-0 shadow-md shadow-cyan-900/40 mt-1">
      <i data-lucide="bot" class="w-4 h-4 text-white"></i>
    </div>
    <div class="flex-1 max-w-[90%] sm:max-w-[85%] rounded-2xl rounded-tl-sm bg-surface-850 border border-cyan-800/40 p-4 sm:p-5 shadow-xl">
      <div class="flex items-center justify-between border-b border-surface-700/60 pb-2 mb-3 text-[11px] font-mono text-slate-400">
        <div class="flex items-center gap-2">
          <span class="font-bold text-white">CodeBrain AI</span>
          <span class="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-300 border border-cyan-800">${escapeHtml(data.intent || 'analysis')}</span>
        </div>
        <div class="flex items-center gap-2 text-[10px]">
          <span class="text-slate-500">${data.ai_provider || 'Grounded Engine'}</span>
          <span>&bull;</span>
          <span>${now}</span>
        </div>
      </div>

      <div class="markdown-content text-xs sm:text-sm text-slate-200 leading-relaxed space-y-2">
        ${rawHtml}
      </div>

      ${evidenceHtml}
      ${actionsHtml}
      ${followUpHtml}
    </div>
  `;

  thread.appendChild(msgDiv);

  // Style code blocks with copy buttons and syntax highlighting
  enhanceCodeBlocks(msgDiv);
  if (window.lucide) lucide.createIcons();
}

function appendErrorMessage(errText) {
  const thread = document.getElementById('chatThread');
  if (!thread) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = 'flex items-start gap-3';
  msgDiv.innerHTML = `
    <div class="w-8 h-8 rounded-xl bg-red-950 border border-red-800 flex items-center justify-center text-red-400 shrink-0 mt-1">
      <i data-lucide="alert-octagon" class="w-4 h-4"></i>
    </div>
    <div class="flex-1 max-w-[85%] rounded-2xl bg-red-950/20 border border-red-800/60 p-4 text-xs text-red-200">
      <p class="font-bold mb-1">Failed to get response</p>
      <p class="text-slate-400 mb-3">${escapeHtml(errText)}</p>
      <button onclick="retryLastChatMessage()" class="px-3 py-1.5 rounded-lg bg-red-900/60 hover:bg-red-900 border border-red-700 text-white font-semibold flex items-center gap-1.5 transition">
        <i data-lucide="refresh-cw" class="w-3 h-3"></i>
        <span>Retry Request</span>
      </button>
    </div>
  `;
  thread.appendChild(msgDiv);
  if (window.lucide) lucide.createIcons();
}

function retryLastChatMessage() {
  if (lastFailedMessage) {
    const input = document.getElementById('chatInputText');
    if (input) input.value = lastFailedMessage;
    handleChatSend();
  }
}

function enhanceCodeBlocks(container) {
  const preElements = container.querySelectorAll('pre');
  preElements.forEach(pre => {
    const code = pre.querySelector('code');
    if (!code) return;

    // Syntax highlight with highlight.js if available
    if (window.hljs) {
      try {
        hljs.highlightElement(code);
      } catch (e) {}
    }

    // Extract language class (e.g. language-python)
    let lang = 'CODE';
    code.classList.forEach(cls => {
      if (cls.startsWith('language-')) lang = cls.replace('language-', '').toUpperCase();
    });

    const wrapper = document.createElement('div');
    wrapper.className = 'relative my-3 rounded-xl overflow-hidden border border-surface-700 bg-surface-900';

    const header = document.createElement('div');
    header.className = 'flex items-center justify-between px-3 py-1.5 bg-surface-800/80 border-b border-surface-700/60 text-[11px] font-mono text-slate-400 select-none';
    header.innerHTML = `
      <span class="text-cyan-400 font-bold">${lang}</span>
      <button class="copy-code-btn flex items-center gap-1 px-2 py-0.5 rounded text-[10px] hover:text-white hover:bg-surface-700 text-slate-300 transition" title="Copy code snippet">
        <i data-lucide="copy" class="w-3 h-3"></i>
        <span>Copy</span>
      </button>
    `;

    pre.parentNode.insertBefore(wrapper, pre);
    wrapper.appendChild(header);
    wrapper.appendChild(pre);

    pre.className = 'p-3 text-xs font-mono overflow-x-auto custom-scrollbar bg-transparent m-0 text-slate-200';

    const copyBtn = header.querySelector('.copy-code-btn');
    copyBtn.addEventListener('click', () => {
      const textToCopy = code.innerText;
      navigator.clipboard.writeText(textToCopy).then(() => {
        copyBtn.innerHTML = `
          <i data-lucide="check" class="w-3 h-3 text-emerald-400"></i>
          <span class="text-emerald-400 font-bold">Copied!</span>
        `;
        if (window.lucide) lucide.createIcons();
        setTimeout(() => {
          copyBtn.innerHTML = `
            <i data-lucide="copy" class="w-3 h-3"></i>
            <span>Copy</span>
          `;
          if (window.lucide) lucide.createIcons();
        }, 2000);
      });
    });
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeJsString(str) {
  if (!str) return '';
  return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

