/**
 * Topology visualization using D3.js force-directed graph
 */

class TopologyVisualization {
    constructor(containerId, data) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.data = data;

        // Dimensions
        this.width = this.container.clientWidth;
        this.height = this.container.clientHeight;

        // Callbacks
        this.onNodeClick = null;
        this.onLinkClick = null;

        // D3 elements
        this.svg = null;
        this.g = null;
        this.simulation = null;
        this.zoom = null;

        // Selected elements
        this.selectedNode = null;
        this.selectedLink = null;

        // Initialize
        this.init();
    }

    /**
     * Initialize the visualization
     */
    init() {
        // Clear container
        this.container.innerHTML = '';

        // Create SVG
        this.svg = d3.select(`#${this.containerId}`)
            .append('svg')
            .attr('width', this.width)
            .attr('height', this.height);

        // Create zoom behavior
        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        // Create main group
        this.g = this.svg.append('g');

        // Create force simulation
        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(150))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(40));

        // Render initial data
        this.render();

        console.log('Topology visualization initialized');
    }

    /**
     * Render the graph
     */
    render() {
        if (!this.data || !this.data.nodes || !this.data.links) {
            console.warn('No data to render');
            return;
        }

        // Clear existing elements
        this.g.selectAll('*').remove();

        // Create arrow markers for directed edges
        const defs = this.g.append('defs');

        // Active arrow
        defs.append('marker')
            .attr('id', 'arrow-active')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#3fb950');

        // Inactive arrow
        defs.append('marker')
            .attr('id', 'arrow-inactive')
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#f85149');

        // Create links
        const link = this.g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(this.data.links)
            .enter()
            .append('line')
            .attr('class', 'link')
            .attr('stroke', d => this.getLinkColor(d.status))
            .attr('stroke-width', 2)
            .attr('marker-end', d => `url(#arrow-${d.status})`)
            .on('click', (event, d) => {
                event.stopPropagation();
                this.handleLinkClick(d);
            });

        // Create nodes
        const node = this.g.append('g')
            .attr('class', 'nodes')
            .selectAll('circle')
            .data(this.data.nodes)
            .enter()
            .append('circle')
            .attr('class', 'node')
            .attr('r', 20)
            .attr('fill', d => this.getNodeColor(d.type))
            .attr('stroke', '#30363d')
            .attr('stroke-width', 2)
            .on('click', (event, d) => {
                event.stopPropagation();
                this.handleNodeClick(d);
            })
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d))
            );

        // Add node labels
        const nodeLabel = this.g.append('g')
            .attr('class', 'node-labels')
            .selectAll('text')
            .data(this.data.nodes)
            .enter()
            .append('text')
            .attr('class', 'node-label')
            .attr('dy', 35)
            .text(d => d.name || d.id);

        // Update simulation
        this.simulation
            .nodes(this.data.nodes)
            .on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);

                nodeLabel
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
            });

        this.simulation.force('link')
            .links(this.data.links);

        // Store references
        this.linkElements = link;
        this.nodeElements = node;

        console.log(`Rendered ${this.data.nodes.length} nodes and ${this.data.links.length} links`);
    }

    /**
     * Update the visualization with new data
     */
    update(data) {
        this.data = data;
        this.render();
    }

    /**
     * Get node color based on segment type
     */
    getNodeColor(type) {
        const colors = {
            'external': '#58a6ff',
            'dmz': '#f78166',
            'internal': '#a371f7',
            'domain': '#ffa657',
        };
        return colors[type] || '#8b949e';
    }

    /**
     * Get link color based on status
     */
    getLinkColor(status) {
        const colors = {
            'active': '#3fb950',
            'disconnected': '#f85149',
            'stopped': '#6e7681',
        };
        return colors[status] || '#6e7681';
    }

    /**
     * Handle node click
     */
    handleNodeClick(node) {
        // Clear previous selection
        if (this.nodeElements) {
            this.nodeElements.classed('selected', false);
        }
        if (this.linkElements) {
            this.linkElements.classed('selected', false);
        }

        // Select clicked node
        this.selectedNode = node;
        this.selectedLink = null;

        if (this.nodeElements) {
            this.nodeElements
                .filter(d => d.id === node.id)
                .classed('selected', true);
        }

        // Call callback
        if (this.onNodeClick) {
            this.onNodeClick(node);
        }
    }

    /**
     * Handle link click
     */
    handleLinkClick(link) {
        // Clear previous selection
        if (this.nodeElements) {
            this.nodeElements.classed('selected', false);
        }
        if (this.linkElements) {
            this.linkElements.classed('selected', false);
        }

        // Select clicked link
        this.selectedLink = link;
        this.selectedNode = null;

        if (this.linkElements) {
            this.linkElements
                .filter(d => d.id === link.id)
                .classed('selected', true);
        }

        // Call callback
        if (this.onLinkClick) {
            this.onLinkClick(link);
        }
    }

    /**
     * Drag handlers
     */
    dragStarted(event, d) {
        if (!event.active) {
            this.simulation.alphaTarget(0.3).restart();
        }
        d.fx = d.x;
        d.fy = d.y;
    }

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    dragEnded(event, d) {
        if (!event.active) {
            this.simulation.alphaTarget(0);
        }
        d.fx = null;
        d.fy = null;
    }

    /**
     * Zoom controls
     */
    zoomIn() {
        this.svg.transition()
            .duration(300)
            .call(this.zoom.scaleBy, 1.3);
    }

    zoomOut() {
        this.svg.transition()
            .duration(300)
            .call(this.zoom.scaleBy, 0.7);
    }

    resetView() {
        this.svg.transition()
            .duration(500)
            .call(
                this.zoom.transform,
                d3.zoomIdentity.translate(0, 0).scale(1)
            );
    }
}

// Export for use in app.js
window.TopologyVisualization = TopologyVisualization;
