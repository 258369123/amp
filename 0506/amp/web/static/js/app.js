/**
 * Main application logic for AMP Web UI
 */

// Global state
const state = {
    topology: null,
    status: null,
    selectedNode: null,
    selectedLink: null,
    updateInterval: null,
};

// Configuration
const config = {
    updateIntervalMs: 5000, // Poll every 5 seconds
    apiBaseUrl: '',
};

/**
 * Initialize the application
 */
async function init() {
    console.log('Initializing AMP Web UI...');

    // Setup event listeners
    setupEventListeners();

    // Initial data fetch
    await fetchData();

    // Start auto-refresh
    startAutoRefresh();

    console.log('AMP Web UI initialized');
}

/**
 * Setup event listeners for UI controls
 */
function setupEventListeners() {
    // Refresh button
    const refreshBtn = document.getElementById('refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', async () => {
            console.log('Manual refresh triggered');
            await fetchData();
        });
    }

    // Zoom controls
    const zoomInBtn = document.getElementById('zoom-in');
    const zoomOutBtn = document.getElementById('zoom-out');
    const resetViewBtn = document.getElementById('reset-view');

    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => {
            if (window.topologyViz) {
                window.topologyViz.zoomIn();
            }
        });
    }

    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => {
            if (window.topologyViz) {
                window.topologyViz.zoomOut();
            }
        });
    }

    if (resetViewBtn) {
        resetViewBtn.addEventListener('click', () => {
            if (window.topologyViz) {
                window.topologyViz.resetView();
            }
        });
    }
}

/**
 * Fetch all data from API
 */
async function fetchData() {
    try {
        // Fetch topology and status in parallel
        const [topologyResult, statusResult] = await Promise.all([
            fetchTopology(),
            fetchStatus(),
        ]);

        if (topologyResult) {
            state.topology = topologyResult;
            renderTopology(topologyResult);
        }

        if (statusResult) {
            state.status = statusResult;
            updateDashboard(statusResult);
            updateOperations(statusResult.recent_operations || []);
        }

        // Update last update time
        updateLastUpdateTime();

    } catch (error) {
        console.error('Error fetching data:', error);
        showError('Failed to fetch data from server');
    }
}

/**
 * Fetch topology data from API
 */
async function fetchTopology() {
    try {
        const response = await fetch(`${config.apiBaseUrl}/api/topology`);
        const data = await response.json();

        if (data.success) {
            console.log('Topology fetched:', data.data);
            return data.data;
        } else {
            console.error('Topology fetch failed:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Error fetching topology:', error);
        return null;
    }
}

/**
 * Fetch status data from API
 */
async function fetchStatus() {
    try {
        const response = await fetch(`${config.apiBaseUrl}/api/status`);
        const data = await response.json();

        if (data.success) {
            console.log('Status fetched:', data.data);
            return data.data;
        } else {
            console.error('Status fetch failed:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Error fetching status:', error);
        return null;
    }
}

/**
 * Fetch segment details from API
 */
async function fetchSegmentDetails(segmentId) {
    try {
        const response = await fetch(`${config.apiBaseUrl}/api/segment/${segmentId}`);
        const data = await response.json();

        if (data.success) {
            return data.data;
        } else {
            console.error('Segment fetch failed:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Error fetching segment details:', error);
        return null;
    }
}

/**
 * Fetch tunnel details from API
 */
async function fetchTunnelDetails(tunnelId) {
    try {
        const response = await fetch(`${config.apiBaseUrl}/api/tunnel/${tunnelId}`);
        const data = await response.json();

        if (data.success) {
            return data.data;
        } else {
            console.error('Tunnel fetch failed:', data.error);
            return null;
        }
    } catch (error) {
        console.error('Error fetching tunnel details:', error);
        return null;
    }
}

/**
 * Update dashboard statistics
 */
function updateDashboard(status) {
    // Update tunnels
    const tunnelsTotal = document.getElementById('tunnels-total');
    const tunnelsActive = document.getElementById('tunnels-active');
    if (tunnelsTotal) tunnelsTotal.textContent = status.tunnels.total;
    if (tunnelsActive) tunnelsActive.textContent = status.tunnels.active;

    // Update shells
    const shellsTotal = document.getElementById('shells-total');
    const shellsActive = document.getElementById('shells-active');
    if (shellsTotal) shellsTotal.textContent = status.shells.total;
    if (shellsActive) shellsActive.textContent = status.shells.active;

    // Update segments
    const segmentsTotal = document.getElementById('segments-total');
    if (segmentsTotal) segmentsTotal.textContent = status.segments.total;
}

/**
 * Update last update time
 */
function updateLastUpdateTime() {
    const lastUpdate = document.getElementById('last-update');
    if (lastUpdate) {
        const now = new Date();
        lastUpdate.textContent = `Updated ${now.toLocaleTimeString()}`;
    }
}

/**
 * Update recent operations list
 */
function updateOperations(operations) {
    const operationsList = document.getElementById('operations-list');
    if (!operationsList) return;

    if (operations.length === 0) {
        operationsList.innerHTML = '<p class="placeholder">No recent operations</p>';
        return;
    }

    operationsList.innerHTML = operations.map(op => {
        const statusClass = op.status === 'completed' ? 'active' :
                           op.status === 'failed' ? 'inactive' : 'stopped';
        const time = new Date(op.created_at).toLocaleTimeString();

        return `
            <div class="operation-item">
                <div class="operation-header">
                    <span class="operation-type">${op.operation_type}</span>
                    <span class="operation-time">${time}</span>
                </div>
                <div class="operation-status">
                    <span class="badge ${statusClass}">${op.status}</span>
                    ${op.error_message ? `<span style="color: #f85149; font-size: 0.8rem;"> - ${op.error_message}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render topology visualization
 */
function renderTopology(topology) {
    if (window.topologyViz) {
        window.topologyViz.update(topology);
    } else {
        // Initialize topology visualization
        window.topologyViz = new TopologyVisualization('topology', topology);

        // Setup callbacks
        window.topologyViz.onNodeClick = async (node) => {
            console.log('Node clicked:', node);
            state.selectedNode = node;
            state.selectedLink = null;
            await showNodeDetails(node);
        };

        window.topologyViz.onLinkClick = async (link) => {
            console.log('Link clicked:', link);
            state.selectedLink = link;
            state.selectedNode = null;
            await showLinkDetails(link);
        };
    }
}

/**
 * Show node details in details panel
 */
async function showNodeDetails(node) {
    const detailsContent = document.getElementById('details-content');
    if (!detailsContent) return;

    // Show loading state
    detailsContent.innerHTML = '<p class="placeholder loading">Loading details...</p>';

    // Fetch detailed information
    const details = await fetchSegmentDetails(node.id);

    if (!details) {
        detailsContent.innerHTML = '<p class="placeholder">Failed to load details</p>';
        return;
    }

    const segment = details.segment;
    const tunnels = details.connected_tunnels || [];
    const shells = details.shells || [];

    detailsContent.innerHTML = `
        <div class="detail-section">
            <h3>Segment Information</h3>
            <div class="detail-row">
                <span class="detail-label">ID:</span>
                <span class="detail-value">${segment.id}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Name:</span>
                <span class="detail-value">${segment.name}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">CIDR:</span>
                <span class="detail-value">${segment.cidr}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">${segment.type}</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Connected Tunnels (${tunnels.length})</h3>
            ${tunnels.length > 0 ? tunnels.map(t => `
                <div class="detail-row">
                    <span class="detail-label">${t.source} → ${t.target}</span>
                    <span class="badge ${t.status === 'active' ? 'active' : 'inactive'}">${t.status}</span>
                </div>
            `).join('') : '<p class="placeholder">No tunnels</p>'}
        </div>

        <div class="detail-section">
            <h3>Shells (${shells.length})</h3>
            ${shells.length > 0 ? shells.map(s => `
                <div class="detail-row">
                    <span class="detail-label">${s.target_host}</span>
                    <span class="badge ${s.is_active ? 'active' : 'inactive'}">${s.shell_type}</span>
                </div>
            `).join('') : '<p class="placeholder">No shells</p>'}
        </div>
    `;
}

/**
 * Show link details in details panel
 */
async function showLinkDetails(link) {
    const detailsContent = document.getElementById('details-content');
    if (!detailsContent) return;

    // Show loading state
    detailsContent.innerHTML = '<p class="placeholder loading">Loading details...</p>';

    // Fetch detailed information
    const details = await fetchTunnelDetails(link.id);

    if (!details) {
        detailsContent.innerHTML = '<p class="placeholder">Failed to load details</p>';
        return;
    }

    const tunnel = details.tunnel;
    const createdAt = new Date(tunnel.created_at).toLocaleString();
    const lastCheck = tunnel.last_health_check ?
        new Date(tunnel.last_health_check).toLocaleString() : 'Never';

    detailsContent.innerHTML = `
        <div class="detail-section">
            <h3>Tunnel Information</h3>
            <div class="detail-row">
                <span class="detail-label">ID:</span>
                <span class="detail-value">${tunnel.id}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">${tunnel.tunnel_type}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Status:</span>
                <span class="badge ${tunnel.status === 'active' ? 'active' : 'inactive'}">${tunnel.status}</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Connection Details</h3>
            <div class="detail-row">
                <span class="detail-label">Local:</span>
                <span class="detail-value">${tunnel.local_host}:${tunnel.local_port}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Remote:</span>
                <span class="detail-value">${tunnel.remote_host}:${tunnel.remote_port}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Source Segment:</span>
                <span class="detail-value">${tunnel.source_segment}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Target Segment:</span>
                <span class="detail-value">${tunnel.target_segment}</span>
            </div>
        </div>

        <div class="detail-section">
            <h3>Timestamps</h3>
            <div class="detail-row">
                <span class="detail-label">Created:</span>
                <span class="detail-value">${createdAt}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Last Health Check:</span>
                <span class="detail-value">${lastCheck}</span>
            </div>
        </div>
    `;
}

/**
 * Show error message
 */
function showError(message) {
    console.error(message);
    const systemStatus = document.getElementById('system-status');
    if (systemStatus) {
        systemStatus.innerHTML = '<span class="status-dot inactive"></span> Error';
    }
}

/**
 * Start auto-refresh interval
 */
function startAutoRefresh() {
    if (state.updateInterval) {
        clearInterval(state.updateInterval);
    }

    state.updateInterval = setInterval(async () => {
        console.log('Auto-refresh triggered');
        await fetchData();
    }, config.updateIntervalMs);

    console.log(`Auto-refresh started (every ${config.updateIntervalMs}ms)`);
}

/**
 * Stop auto-refresh interval
 */
function stopAutoRefresh() {
    if (state.updateInterval) {
        clearInterval(state.updateInterval);
        state.updateInterval = null;
        console.log('Auto-refresh stopped');
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});
