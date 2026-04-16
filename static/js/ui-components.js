/**
 * UI Components for Hierarchical Agent Display
 * Displays main agent and sub-agents with reasoning traces and metrics
 */

class AgentHierarchyPanel {
    constructor(container) {
        this.container = typeof container === 'string' 
            ? document.getElementById(container) 
            : container;
        this.currentHierarchy = null;
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('AgentHierarchyPanel: Container not found');
            return;
        }

        // Create container structure
        this.container.innerHTML = `
            <div class="agent-hierarchy-panel">
                <div class="hierarchy-header">
                    <h3>🤖 Agent Hierarchy</h3>
                    <button class="clear-hierarchy-btn" title="Clear hierarchy">Clear</button>
                </div>
                <div class="hierarchy-content">
                    <div id="main-agent-container"></div>
                    <div id="sub-agents-container"></div>
                </div>
                <div class="hierarchy-stats">
                    <div class="stat-row">
                        <span class="stat-label">Total Agents:</span>
                        <span class="stat-value" id="total-agents">1</span>
                    </div>
                    <div class="stat-row">
                        <span class="stat-label">Active Sub-Agents:</span>
                        <span class="stat-value" id="active-subagents">0</span>
                    </div>
                </div>
            </div>
        `;

        // Setup event listeners
        this.setupEventListeners();

        // Subscribe to state changes
        if (window.StateHooks) {
            this.unsubscribe = window.StateHooks.useState('debug.agentHierarchy', (hierarchy) => {
                this.updateHierarchy(hierarchy);
            });
        }
    }

    setupEventListeners() {
        const clearBtn = this.container.querySelector('.clear-hierarchy-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (window.StateManagerInstance) {
                    window.StateManagerInstance.dispatch('clearAgentHierarchy');
                }
            });
        }
    }

    updateHierarchy(hierarchy) {
        if (!hierarchy) return;
        
        this.currentHierarchy = hierarchy;
        this.renderMainAgent(hierarchy.mainAgent);
        this.renderSubAgents(hierarchy.subAgents || []);
        this.updateStats(hierarchy);
    }

    renderMainAgent(mainAgent) {
        const container = this.container.querySelector('#main-agent-container');
        if (!container) return;

        const expanded = this.currentHierarchy?.expandedAgents?.['main'] ?? true;
        const statusClass = mainAgent.status === 'running' ? 'status-running' : 'status-idle';

        let html = `
            <div class="agent-card main-agent ${statusClass}">
                <div class="agent-header">
                    <button class="expand-btn" data-agent-id="main" title="Expand/Collapse">
                        ${expanded ? '▼' : '▶'}
                    </button>
                    <div class="agent-type-badge agent-type-main">Main Agent</div>
                    <div class="agent-status">${mainAgent.status.toUpperCase()}</div>
                </div>
                ${expanded ? this.renderAgentContent(mainAgent) : ''}
            </div>
        `;

        container.innerHTML = html;

        // Setup expand button
        const expandBtn = container.querySelector('.expand-btn');
        if (expandBtn) {
            expandBtn.addEventListener('click', () => {
                if (window.StateManagerInstance) {
                    window.StateManagerInstance.dispatch('toggleAgentExpanded', { agentId: 'main' });
                }
            });
        }
    }

    renderSubAgents(subAgents) {
        const container = this.container.querySelector('#sub-agents-container');
        if (!container) return;

        if (subAgents.length === 0) {
            container.innerHTML = '<p class="empty-state">No sub-agents spawned yet</p>';
            return;
        }

        let html = '<div class="sub-agents-list">';
        
        subAgents.forEach((agent, index) => {
            html += this.renderSubAgentCard(agent, index);
        });

        html += '</div>';
        container.innerHTML = html;

        // Setup expand buttons for sub-agents
        container.querySelectorAll('.expand-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const agentId = e.target.dataset.agentId;
                if (window.StateManagerInstance) {
                    window.StateManagerInstance.dispatch('toggleAgentExpanded', { agentId });
                }
            });
        });
    }

    renderSubAgentCard(agent, index) {
        const expanded = this.currentHierarchy?.expandedAgents?.[agent.id] ?? true;
        const statusClass = agent.status === 'completed' ? 'status-completed' : 'status-running';
        const typeClass = this.getAgentTypeBadgeClass(agent.type);

        let html = `
            <div class="agent-card sub-agent ${statusClass}">
                <div class="agent-header">
                    <span class="agent-indent">├─</span>
                    <button class="expand-btn" data-agent-id="${agent.id}" title="Expand/Collapse">
                        ${expanded ? '▼' : '▶'}
                    </button>
                    <div class="agent-type-badge ${typeClass}">${agent.type}</div>
                    <div class="agent-status">${agent.status.toUpperCase()}</div>
                </div>
                ${expanded ? this.renderAgentContent(agent) : ''}
            </div>
        `;

        return html;
    }

    renderAgentContent(agent) {
        let html = '<div class="agent-content">';

        // Reasoning trace
        if (agent.reasoning && agent.reasoning.length > 0) {
            html += '<div class="reasoning-section">';
            html += '<h4>Reasoning Trace:</h4>';
            html += '<div class="reasoning-list">';
            agent.reasoning.forEach((step, idx) => {
                const stepText = typeof step === 'string' ? step : JSON.stringify(step);
                html += `<div class="reasoning-item"><strong>Step ${idx + 1}:</strong> ${this.escapeHtml(stepText)}</div>`;
            });
            html += '</div>';
            html += '</div>';
        }

        // Result
        if (agent.result) {
            html += '<div class="result-section">';
            html += '<h4>Result:</h4>';
            html += `<div class="result-text">${this.escapeHtml(agent.result)}</div>`;
            html += '</div>';
        }

        // Metrics
        if (agent.metrics) {
            html += this.renderMetricsPanel(agent.metrics);
        }

        html += '</div>';
        return html;
    }

    renderMetricsPanel(metrics) {
        let html = '<div class="metrics-panel">';
        html += '<h4>Metrics:</h4>';
        html += '<div class="metrics-grid">';

        if (metrics.duration !== undefined && metrics.duration !== null) {
            html += `<div class="metric-item"><span>Duration:</span> <span class="metric-value">${metrics.duration.toFixed(2)}s</span></div>`;
        }

        if (metrics.retrievedDocuments !== undefined) {
            html += `<div class="metric-item"><span>Documents:</span> <span class="metric-value">${metrics.retrievedDocuments}</span></div>`;
        }

        if (metrics.iterations !== undefined) {
            html += `<div class="metric-item"><span>Iterations:</span> <span class="metric-value">${metrics.iterations}</span></div>`;
        }

        if (metrics.confidence !== undefined && metrics.confidence !== null) {
            const confPercent = (metrics.confidence * 100).toFixed(1);
            const confClass = metrics.confidence >= 0.7 ? 'high-confidence' : 'low-confidence';
            html += `<div class="metric-item"><span>Confidence:</span> <span class="metric-value ${confClass}">${confPercent}%</span></div>`;
        }

        html += '</div>';
        html += '</div>';
        return html;
    }

    getAgentTypeBadgeClass(type) {
        if (!type) {
            return 'agent-type-default';
        }

        const normalized = String(type).trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-');
        const allowed = new Set(['full_document', 'comparison', 'extraction', 'search']);
        return allowed.has(normalized) ? `agent-type-${normalized}` : 'agent-type-default';
    }

    updateStats(hierarchy) {
        const totalAgentsEl = this.container.querySelector('#total-agents');
        const activeSubAgentsEl = this.container.querySelector('#active-subagents');

        if (totalAgentsEl) {
            const total = 1 + (hierarchy.subAgents?.length || 0);
            totalAgentsEl.textContent = total;
        }

        if (activeSubAgentsEl) {
            const active = (hierarchy.subAgents || []).filter(a => a.status === 'running').length;
            activeSubAgentsEl.textContent = active;
        }
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    destroy() {
        if (this.unsubscribe) {
            this.unsubscribe();
        }
    }
}

class ReasoningTimeline {
    constructor(container) {
        this.container = typeof container === 'string'
            ? document.getElementById(container)
            : container;
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('ReasoningTimeline: Container not found');
            return;
        }

        this.container.innerHTML = `
            <div class="reasoning-timeline">
                <h3>📋 Reasoning Timeline</h3>
                <div id="timeline-content" class="timeline-content"></div>
            </div>
        `;

        if (window.StateHooks) {
            this.unsubscribe = window.StateHooks.useState('debug.traceData', (traceData) => {
                this.renderTimeline(traceData);
            });
        }
    }

    renderTimeline(traceData) {
        const content = this.container.querySelector('#timeline-content');
        if (!content || !traceData) return;

        if (traceData.length === 0) {
            content.innerHTML = '<p class="empty-state">No reasoning steps yet</p>';
            return;
        }

        let html = '<div class="timeline-steps">';
        traceData.forEach((step, idx) => {
            const stepText = typeof step === 'string' ? step : JSON.stringify(step);
            const icon = this.getStepIcon(stepText);
            html += `
                <div class="timeline-step">
                    <div class="step-marker">${icon}</div>
                    <div class="step-content">
                        <div class="step-number">Step ${idx + 1}</div>
                        <div class="step-text">${this.escapeHtml(stepText)}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';

        content.innerHTML = html;
    }

    getStepIcon(text) {
        if (text.includes('retrieved') || text.includes('search')) return '🔍';
        if (text.includes('decompos') || text.includes('split')) return '🔀';
        if (text.includes('spawn') || text.includes('delegate')) return '🚀';
        if (text.includes('answer') || text.includes('result')) return '✅';
        if (text.includes('error') || text.includes('fail')) return '❌';
        return '•';
    }

    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    destroy() {
        if (this.unsubscribe) {
            this.unsubscribe();
        }
    }
}

class MetricsPanel {
    constructor(container) {
        this.container = typeof container === 'string'
            ? document.getElementById(container)
            : container;
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('MetricsPanel: Container not found');
            return;
        }

        this.container.innerHTML = `
            <div class="metrics-dashboard">
                <h3>📊 Performance Metrics</h3>
                <div class="metrics-summary">
                    <div class="metric-card">
                        <div class="metric-title">Total Duration</div>
                        <div class="metric-display" id="total-duration">0.00s</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Documents Retrieved</div>
                        <div class="metric-display" id="docs-retrieved">0</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Agent Count</div>
                        <div class="metric-display" id="agent-count">1</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-title">Confidence Score</div>
                        <div class="metric-display" id="confidence-score">N/A</div>
                    </div>
                </div>
            </div>
        `;

        if (window.StateHooks) {
            this.unsubscribe = window.StateHooks.useState('debug.agentHierarchy', (hierarchy) => {
                this.updateMetrics(hierarchy);
            });
        }
    }

    updateMetrics(hierarchy) {
        if (!hierarchy) return;

        const mainMetrics = hierarchy.mainAgent?.metrics || {};
        const subAgents = hierarchy.subAgents || [];

        // Total duration
        let totalDuration = mainMetrics.duration || 0;
        subAgents.forEach(agent => {
            totalDuration += (agent.metrics?.duration || 0);
        });

        const durationEl = this.container.querySelector('#total-duration');
        if (durationEl) {
            durationEl.textContent = `${totalDuration.toFixed(2)}s`;
        }

        // Documents retrieved
        const docsRetrieved = mainMetrics.retrievedDocuments || 0;
        const docsEl = this.container.querySelector('#docs-retrieved');
        if (docsEl) {
            docsEl.textContent = docsRetrieved;
        }

        // Agent count
        const agentCount = 1 + subAgents.length;
        const agentCountEl = this.container.querySelector('#agent-count');
        if (agentCountEl) {
            agentCountEl.textContent = agentCount;
        }

        // Confidence
        const confidence = mainMetrics.confidence;
        const confidenceEl = this.container.querySelector('#confidence-score');
        if (confidenceEl) {
            if (confidence !== undefined && confidence !== null) {
                const confPercent = (confidence * 100).toFixed(1);
                confidenceEl.textContent = `${confPercent}%`;
                confidenceEl.className = 'metric-display ' + (confidence >= 0.7 ? 'high-confidence' : 'low-confidence');
            } else {
                confidenceEl.textContent = 'N/A';
            }
        }
    }

    destroy() {
        if (this.unsubscribe) {
            this.unsubscribe();
        }
    }
}

// CSS Styles
const HierarchyStyles = `
<style id="hierarchy-styles">
    /* Agent Hierarchy Panel */
    .agent-hierarchy-panel {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    .hierarchy-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 2px solid #334155;
    }

    .hierarchy-header h3 {
        color: #a78bfa;
        margin: 0;
        font-size: 1.2em;
    }

    .clear-hierarchy-btn {
        padding: 8px 16px;
        background: #ef4444;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        transition: background 0.2s;
    }

    .clear-hierarchy-btn:hover {
        background: #dc2626;
    }

    .hierarchy-content {
        margin-bottom: 15px;
    }

    /* Agent Cards */
    .agent-card {
        background: #0f172a;
        border-left: 4px solid #667eea;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 12px;
        transition: all 0.2s;
    }

    .agent-card.main-agent {
        border-left: 4px solid #667eea;
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
    }

    .agent-card.sub-agent {
        margin-left: 20px;
        border-left: 3px solid #6b7280;
    }

    .agent-card.status-running {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(34, 197, 94, 0.05) 100%);
        border-left-color: #22c55e;
    }

    .agent-card.status-completed {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
        border-left-color: #3b82f6;
    }

    .agent-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }

    .expand-btn {
        background: none;
        border: none;
        color: #a78bfa;
        cursor: pointer;
        font-size: 14px;
        padding: 0;
        width: 20px;
        text-align: center;
        transition: transform 0.2s;
    }

    .expand-btn:hover {
        transform: scale(1.2);
    }

    .agent-indent {
        color: #64748b;
        font-size: 12px;
    }

    .agent-type-badge {
        padding: 4px 12px;
        border-radius: 20px;
        color: white;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
    }

    .agent-status {
        margin-left: auto;
        padding: 4px 10px;
        background: #334155;
        color: #cbd5e1;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
    }

    .agent-status.running {
        background: #22c55e;
        color: white;
    }

    /* Agent Content */
    .agent-content {
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #334155;
    }

    .reasoning-section,
    .result-section,
    .metrics-panel {
        margin-bottom: 12px;
    }

    .agent-content h4 {
        color: #cbd5e1;
        font-size: 0.9em;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .reasoning-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .reasoning-item {
        padding: 8px 12px;
        background: #1e293b;
        border-left: 2px solid #667eea;
        border-radius: 4px;
        font-size: 12px;
        line-height: 1.5;
        color: #cbd5e1;
    }

    .reasoning-item strong {
        color: #a78bfa;
    }

    .result-text {
        padding: 12px;
        background: #1e293b;
        border-radius: 4px;
        font-size: 12px;
        line-height: 1.6;
        color: #cbd5e1;
        max-height: 150px;
        overflow-y: auto;
        word-wrap: break-word;
    }

    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
    }

    .metric-item {
        display: flex;
        justify-content: space-between;
        padding: 8px 12px;
        background: #1e293b;
        border-radius: 4px;
        font-size: 12px;
        color: #cbd5e1;
    }

    .metric-value {
        color: #a78bfa;
        font-weight: 600;
    }

    .metric-value.high-confidence {
        color: #22c55e;
    }

    .metric-value.low-confidence {
        color: #fb923c;
    }

    .hierarchy-stats {
        padding: 12px;
        background: #0f172a;
        border-radius: 8px;
        border-top: 1px solid #334155;
    }

    .stat-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        font-size: 12px;
        color: #cbd5e1;
    }

    .stat-label {
        color: #94a3b8;
    }

    .stat-value {
        color: #a78bfa;
        font-weight: 600;
    }

    /* Reasoning Timeline */
    .reasoning-timeline {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    .reasoning-timeline h3 {
        color: #a78bfa;
        margin-bottom: 15px;
        font-size: 1.2em;
    }

    .timeline-content {
        max-height: 400px;
        overflow-y: auto;
    }

    .timeline-steps {
        display: flex;
        flex-direction: column;
        gap: 12px;
        position: relative;
    }

    .timeline-steps::before {
        content: '';
        position: absolute;
        left: 20px;
        top: 30px;
        bottom: 0;
        width: 2px;
        background: #334155;
    }

    .timeline-step {
        display: flex;
        gap: 15px;
        position: relative;
    }

    .step-marker {
        width: 40px;
        height: 40px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #0f172a;
        border: 2px solid #667eea;
        border-radius: 50%;
        font-size: 18px;
        flex-shrink: 0;
        z-index: 1;
    }

    .step-content {
        flex: 1;
        padding: 12px;
        background: #0f172a;
        border-radius: 8px;
        border-left: 2px solid #667eea;
    }

    .step-number {
        color: #a78bfa;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 4px;
    }

    .step-text {
        color: #cbd5e1;
        font-size: 12px;
        line-height: 1.5;
        word-wrap: break-word;
    }

    /* Metrics Dashboard */
    .metrics-dashboard {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    .metrics-dashboard h3 {
        color: #a78bfa;
        margin-bottom: 15px;
        font-size: 1.2em;
    }

    .metrics-summary {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
    }

    @media (max-width: 768px) {
        .metrics-summary {
            grid-template-columns: 1fr;
        }
    }

    .metric-card {
        background: #0f172a;
        border: 2px solid #334155;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
    }

    .metric-card:hover {
        border-color: #667eea;
        box-shadow: 0 0 12px rgba(102, 126, 234, 0.2);
    }

    .metric-title {
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
        font-weight: 600;
    }

    .metric-display {
        color: #a78bfa;
        font-size: 1.8em;
        font-weight: 700;
        font-family: 'Courier New', monospace;
    }

    .metric-display.high-confidence {
        color: #22c55e;
    }

    .metric-display.low-confidence {
        color: #fb923c;
    }

    .empty-state {
        text-align: center;
        color: #64748b;
        padding: 20px;
        font-style: italic;
    }

    /* Responsive */
    @media (max-width: 1024px) {
        .agent-card.sub-agent {
            margin-left: 15px;
        }

        .metrics-grid {
            grid-template-columns: 1fr;
        }
    }

    /* Scrollbar Styling */
    .timeline-content::-webkit-scrollbar,
    .result-text::-webkit-scrollbar {
        width: 6px;
    }

    .timeline-content::-webkit-scrollbar-track,
    .result-text::-webkit-scrollbar-track {
        background: #0f172a;
    }

    .timeline-content::-webkit-scrollbar-thumb,
    .result-text::-webkit-scrollbar-thumb {
        background: #667eea;
        border-radius: 3px;
    }

    .timeline-content::-webkit-scrollbar-thumb:hover,
    .result-text::-webkit-scrollbar-thumb:hover {
        background: #764ba2;
    }
</style>
`;

// Export components
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AgentHierarchyPanel, ReasoningTimeline, MetricsPanel, HierarchyStyles };
}
