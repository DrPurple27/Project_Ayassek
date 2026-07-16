function showLoadingScreen(): void {
    const el = document.getElementById("loading-screen");
    if (el) el.classList.remove("hidden");
}

function hideLoadingScreen(): void {
    const el = document.getElementById("loading-screen");
    if (el) el.classList.add("hidden");
}

function renderLoadingSteps(steps: Array<{ name: string; label: string; status: string; detail: string }>): void {
    const container = document.getElementById("loading-steps");
    if (!container) return;
    container.innerHTML = "";
    for (const s of steps) {
        const div = document.createElement("div");
        div.className = "loading-step " + s.status;
        const icon = document.createElement("span");
        icon.className = "step-icon";
        if (s.status === "ok") icon.textContent = "\u2713";
        else icon.textContent = "";
        const label = document.createElement("span");
        label.className = "loading-label";
        label.textContent = s.label;
        const detail = document.createElement("span");
        detail.className = "loading-detail";
        detail.textContent = s.detail;
        div.appendChild(icon);
        div.appendChild(label);
        div.appendChild(detail);
        container.appendChild(div);
    }
}

async function pollReady(): Promise<void> {
    const cmdEl = document.getElementById("loading-cmd");
    for (let i = 0; i < 120; i++) {
        try {
            const resp = await fetch("/api/system/ready");
            const data = await resp.json();
            renderLoadingSteps(data.steps || []);
            const nrsStep = (data.steps || []).find((s: any) => s.name === "nrs_model");
            if (cmdEl && nrsStep && nrsStep.status === "warning" && nrsStep.detail.startsWith("Run:")) {
                cmdEl.classList.add("visible");
                cmdEl.textContent = nrsStep.detail;
            } else if (cmdEl) {
                cmdEl.classList.remove("visible");
            }
            if (data.ready) {
                setTimeout(hideLoadingScreen, 500);
                return;
            }
        } catch {}
        await new Promise(r => setTimeout(r, 1000));
    }
    hideLoadingScreen();
}

function parseMarkdown(text: string): string {
    let html = text
        .replace(/&/g, "&")
        .replace(/</g, "<")
        .replace(/>/g, ">");
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_: string, lang: string, code: string) => {
        return "<pre><code>" + code.replace(/\n$/, "") + "</code></pre>";
    });
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, "<strong><em>$1</em></strong>");
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    html = html.replace(/~(.+?)~/g, "<del>$1</del>");
    html = html.replace(/^### (.+?)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+?)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+?)$/gm, "<h1>$1</h1>");
    html = html.replace(/^> (.+?)$/gm, "<blockquote>$1</blockquote>");
    html = html.replace(/^[\-\*] (.+?)$/gm, "<li class='ul-item'>$1</li>");
    html = html.replace(/(<li class='ul-item'>.*<\/li>\n?)+/g, "<ul>$&</ul>");
    html = html.replace(/^\d+\. (.+?)$/gm, "<li class='ol-item'>$1</li>");
    html = html.replace(/(<li class='ol-item'>.*<\/li>\n?)+/g, "<ol>$&</ol>");
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    html = html.replace(/^\s*?\n/gm, "<br>");
    html = html.replace(/<\/h([123])><br>/g, "</h$1>");
    html = html.replace(/<\/blockquote><br>/g, "</blockquote>");
    html = html.replace(/<\/ul><br>/g, "</ul>");
    html = html.replace(/<\/ol><br>/g, "</ol>");
    html = html.replace(/<\/pre><br>/g, "</pre>");
    html = html.replace(/(?:<br>\s*)+$/g, "");
    return html;
}

class WebSocketClient {
    private ws: WebSocket | null = null;
    private reconnectTimer: number | null = null;
    private handlers: Map<string, Array<(data: any) => void>> = new Map();
    private _sessionId: string;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 20;
    private _connecting: boolean = false;

    constructor(sessionId: string = "default") {
        this._sessionId = sessionId;
    }

    get sessionId(): string { return this._sessionId; }

    setSessionId(sid: string): void {
        this._sessionId = sid;
        this.reconnectAttempts = 0;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.connect();
    }

    connect(): void {
        if (this._connecting) return;
        this._connecting = true;
        const protocol = window.location.protocol === "https:" ? "wss" : "ws";
        const url = protocol + "://" + window.location.host + "/ws/" + this._sessionId;
        this.setStatus("connecting");
        if (this.ws) {
            const oldWs = this.ws;
            oldWs.onclose = null;
            oldWs.onerror = null;
            oldWs.onmessage = null;
            if (oldWs.readyState === WebSocket.OPEN || oldWs.readyState === WebSocket.CONNECTING) {
                oldWs.close();
            }
        }
        this.ws = new WebSocket(url);
        this.ws.onopen = () => {
            this._connecting = false;
            this.reconnectAttempts = 0;
            this.setStatus("connected");
            this.addLog("WebSocket connected", "success");
        };
        this.ws.onclose = () => {
            this._connecting = false;
            this.setStatus("disconnected");
            this.addLog("Disconnected. Reconnecting...", "warn");
            this.scheduleReconnect();
        };
        this.ws.onerror = () => {
            this._connecting = false;
            this.setStatus("disconnected");
        };
        this.ws.onmessage = (event: MessageEvent) => {
            try {
                const msg = JSON.parse(event.data);
                this.dispatch(msg);
            } catch (e) { console.warn("WS parse error:", e); }
        };
    }

    private scheduleReconnect(): void {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            this.addLog("Max reconnect attempts reached. Click a session to retry.", "error");
            return;
        }
        const delay = Math.min(3000 * Math.pow(1.5, this.reconnectAttempts), 30000);
        this.reconnectAttempts++;
        this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            this.connect();
        }, delay);
    }

    private dispatch(msg: { type: string; data: any; session_id?: string }): void {
        const listeners = this.handlers.get(msg.type) || [];
        for (const handler of listeners) {
            handler(msg.data);
        }
        const wild = this.handlers.get("*") || [];
        for (const handler of wild) {
            handler(msg);
        }
    }

    on(type: string, handler: (data: any) => void): void {
        if (!this.handlers.has(type)) {
            this.handlers.set(type, []);
        }
        this.handlers.get(type)!.push(handler);
    }

    setStatus(status: string): void {
        const el = document.getElementById("connection-status");
        const dot = document.getElementById("status-dot");
        if (el) { el.className = status; el.textContent = status.charAt(0).toUpperCase() + status.slice(1); }
        if (dot) { dot.className = "status-dot " + status; }
    }

    addLog(msg: string, cls: string = ""): void {
        const display = document.getElementById("logs-display");
        if (!display) return;
        const entry = document.createElement("div");
        entry.className = "log-entry " + cls;
        const time = new Date().toLocaleTimeString();
        entry.textContent = "[" + time + "] " + msg;
        display.appendChild(entry);
        display.scrollTop = display.scrollHeight;
        while (display.children.length > 200) {
            const first = display.firstChild;
            if (first) display.removeChild(first);
        }
    }
}

class ChatUI {
    private container: HTMLElement;
    private streamingMsg: HTMLElement | null = null;
    private pendingText: string = "";

    constructor() { this.container = document.getElementById("chat-messages")!; }

    addMessage(role: string, content: string, cls: string = ""): HTMLElement {
        const msg = document.createElement("div");
        msg.className = "message " + role + " " + cls;
        if (role === "assistant") {
            msg.innerHTML = parseMarkdown(content);
        } else {
            msg.textContent = content;
        }
        this.container.appendChild(msg);
        this.scrollDown();
        return msg;
    }

    startStreaming(): void {
        if (this.streamingMsg) this.finishStreaming();
        const el = document.createElement("div");
        el.className = "message assistant streaming";
        el.textContent = "Thinking...";
        this.container.appendChild(el);
        this.streamingMsg = el;
        this.pendingText = "";
        this.scrollDown();
    }

    appendToken(token: string): void {
        if (!this.streamingMsg) this.startStreaming();
        this.pendingText += token;
        this.streamingMsg!.innerHTML = parseMarkdown(this.pendingText);
        this.scrollDown();
    }

    finishStreaming(): void {
        if (this.streamingMsg) {
            this.streamingMsg.classList.remove("streaming");
            const text = this.pendingText;
            if (!text.trim() || text === "Thinking...") {
                this.streamingMsg.remove();
            }
            this.streamingMsg = null;
            this.pendingText = "";
        }
    }

    addSystemMsg(text: string): void {
        const msg = document.createElement("div");
        msg.className = "message system";
        msg.textContent = text;
        this.container.appendChild(msg);
        this.scrollDown();
    }

    scrollDown(): void { this.container.scrollTop = this.container.scrollHeight; }

    clear(): void {
        this.container.innerHTML = "";
        this.streamingMsg = null;
        this.pendingText = "";
    }

    renderHistory(messages: Array<{ role: string; content: string }>): void {
        this.clear();
        for (const msg of messages) {
            this.addMessage(msg.role, msg.content);
        }
    }
}

class ProviderUI {
    private pm: HTMLElement;
    private mm: HTMLElement;
    currentProviderId: string = "";
    currentModelId: string = "";
    private _loading: boolean = false;

    constructor() {
        this.pm = document.getElementById("provider-menu")!;
        this.mm = document.getElementById("model-menu")!;
        this.setupDropdowns();
    }

    private setupDropdowns(): void {
        document.getElementById("provider-btn")!.onclick = (e: MouseEvent) => {
            e.stopPropagation();
            this.pm.classList.toggle("hidden");
            this.mm.classList.add("hidden");
        };
        document.getElementById("model-btn")!.onclick = (e: MouseEvent) => {
            e.stopPropagation();
            this.mm.classList.toggle("hidden");
            this.pm.classList.add("hidden");
        };
        document.getElementById("provider-selector")!.onclick = (e: MouseEvent) => e.stopPropagation();
        document.getElementById("model-selector")!.onclick = (e: MouseEvent) => e.stopPropagation();
        document.addEventListener("click", () => {
            this.pm.classList.add("hidden");
            this.mm.classList.add("hidden");
        });
    }

    async refresh(): Promise<void> { await this.loadProviders(); }

    async loadProviders(): Promise<void> {
        if (this._loading) return;
        this._loading = true;
        try {
            const resp = await fetch("/api/providers");
            const data = await resp.json();
            this.renderProviderDropdown(data);
            this.renderModelDropdown(data);
            this.renderPanel(data);
        } catch (e) { console.error("Failed to load providers:", e); }
        finally { this._loading = false; }
    }

    private renderProviderDropdown(data: any): void {
        this.pm.innerHTML = "";
        for (const p of data.providers) {
            const item = document.createElement("div");
            item.className = "dropdown-item" + (p.active ? " active" : "");
            const count = p.status && p.status.model_count ? p.status.model_count : (p.models ? p.models.length : 0);
            item.textContent = p.name + " (" + count + " models)";
            item.onclick = async () => {
                this.pm.classList.add("hidden");
                const firstModel = p.models && p.models.length > 0 ? p.models[0].id : "";
                try {
                    await fetch("/api/providers/select", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ provider_id: p.id, model: firstModel }),
                    });
                } catch (err) { console.error("Failed to select provider:", err); }
                await this.loadProviders();
            };
            this.pm.appendChild(item);
        }
        const activeP = data.providers.find((p: any) => p.id === data.active_provider);
        const btn = document.getElementById("provider-btn")!;
        btn.textContent = (activeP && activeP.name) || data.active_provider || "Provider";
        this.currentProviderId = data.active_provider || "";
        this.currentModelId = data.active_model || "";
    }

    private renderModelDropdown(data: any): void {
        this.mm.innerHTML = "";
        const activeProvider = data.providers.find((p: any) => p.active);
        if (!activeProvider || !activeProvider.models || activeProvider.models.length === 0) {
            const item = document.createElement("div");
            item.className = "dropdown-item disabled";
            item.textContent = "No models available";
            this.mm.appendChild(item);
        } else {
            for (const m of activeProvider.models) {
                const item = document.createElement("div");
                item.className = "dropdown-item" + (m.id === data.active_model ? " active" : "");
                item.textContent = m.name || m.id;
                item.onclick = async () => {
                    this.mm.classList.add("hidden");
                    try {
                        await fetch("/api/providers/select", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ provider_id: this.currentProviderId, model: m.id }),
                        });
                    } catch (err) { console.error("Failed to select model:", err); }
                    await this.loadProviders();
                };
                this.mm.appendChild(item);
            }
        }
        const btn = document.getElementById("model-btn")!;
        btn.textContent = data.active_model || "Model";
    }

    private renderPanel(data: any): void {
        const list = document.getElementById("providers-list");
        if (!list) return;
        list.innerHTML = "";
        for (const p of data.providers) {
            const card = document.createElement("div");
            card.className = "provider-card" + (p.active ? " active" : "");
            const connected = p.status && p.status.connected ? "Connected" : "Not connected";
            const title = document.createElement("h4");
            title.textContent = p.name + " ";
            const statusSpan = document.createElement("span");
            statusSpan.style.color = (p.status && p.status.connected) ? "var(--success)" : "var(--danger)";
            statusSpan.textContent = "(" + connected + ")";
            title.appendChild(statusSpan);
            card.appendChild(title);
            const desc = document.createElement("p");
            desc.textContent = p.description || "";
            card.appendChild(desc);
            if (p.status) {
                const meta = document.createElement("div");
                meta.className = "meta";
                meta.textContent = "Streaming: " + (p.status.streaming ? "Yes" : "No") +
                    " | Tools: " + (p.status.tools ? "Yes" : "No") +
                    " | Vision: " + (p.status.vision ? "Yes" : "No");
                card.appendChild(meta);
            }
            const tags = document.createElement("div");
            tags.className = "models-tags";
            for (const m of p.models || []) {
                const tag = document.createElement("span");
                tag.className = "model-tag" + (m.id === data.active_model ? " selected" : "");
                tag.dataset.provider = p.id;
                tag.dataset.model = m.id;
                tag.textContent = m.id;
                tag.addEventListener("click", async () => {
                    try {
                        const r = await fetch("/api/providers/select", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ provider_id: p.id, model: m.id }),
                        });
                        if (!r.ok) console.error("Failed to select model:", r.status);
                    } catch (err) { console.error("Failed to select model:", err); }
                    await this.loadProviders();
                });
                tags.appendChild(tag);
            }
            card.appendChild(tags);
            list.appendChild(card);
        }
    }
}

interface NeuralNode { id: string; title: string; content: string; x: number; y: number; created_at: number; updated_at: number; }
interface NeuralEdge { id: string; source_node_id: string; target_node_id: string; strength: number; is_manual: boolean; created_at: number; }

class NeuralGraphUI {
    private canvas: HTMLElement;
    private svg: SVGSVGElement;
    private nodesContainer: HTMLElement;
    private statsEl: HTMLElement;
    private zoomLevelEl: HTMLElement;
    private nodes: NeuralNode[] = [];
    private edges: NeuralEdge[] = [];
    private panX: number = 0;
    private panY: number = 0;
    private zoom: number = 1;
    private isPanning: boolean = false;
    private panStartX: number = 0;
    private panStartY: number = 0;
    private panStartPanX: number = 0;
    private panStartPanY: number = 0;
    private dragNode: NeuralNode | null = null;
    private dragNodeEl: HTMLElement | null = null;
    private dragOffsetX: number = 0;
    private dragOffsetY: number = 0;
    private connecting: { sourceNode: NeuralNode; tempLine: SVGPathElement } | null = null;
    private selectedEdgeId: string | null = null;
    private editNodeId: string | null = null;
    private updateDebounce: number | null = null;

    constructor() {
        this.canvas = document.getElementById("neural-canvas")!;
        this.svg = document.getElementById("neural-svg") as SVGSVGElement;
        this.nodesContainer = document.getElementById("neural-nodes")!;
        this.statsEl = document.getElementById("neural-stats")!;
        this.zoomLevelEl = document.getElementById("neural-zoom-level")!;
        this.setupEvents();
        this.setupModal();
    }

    async load(): Promise<void> {
        await Promise.all([this.loadNodes(), this.loadEdges()]);
        this.render();
    }

    async loadNodes(): Promise<void> {
        try {
            const resp = await fetch("/api/memory/nodes");
            const data = await resp.json();
            this.nodes = data.nodes || [];
        } catch { this.nodes = []; }
    }

    async loadEdges(): Promise<void> {
        try {
            const resp = await fetch("/api/memory/edges");
            const data = await resp.json();
            this.edges = data.edges || [];
        } catch { this.edges = []; }
    }

    render(): void {
        this.renderEdges();
        this.renderNodes();
        this.updateStats();
    }

    private updateStats(): void {
        this.statsEl.textContent = this.nodes.length + " neurons, " + this.edges.length + " synapses";
    }

    private getViewportBounds(): { left: number; top: number; right: number; bottom: number } {
        const rect = this.canvas.getBoundingClientRect();
        const left = (-this.panX) / this.zoom;
        const top = (-this.panY) / this.zoom;
        const right = (rect.width - this.panX) / this.zoom;
        const bottom = (rect.height - this.panY) / this.zoom;
        return { left, top, right, bottom };
    }

    private isNodeVisible(n: NeuralNode, bounds: { left: number; top: number; right: number; bottom: number }): boolean {
        return n.x + 180 > bounds.left && n.x - 180 < bounds.right &&
               n.y + 80 > bounds.top && n.y - 80 < bounds.bottom;
    }

    private renderNodes(): void {
        this.nodesContainer.innerHTML = "";
        const bounds = this.getViewportBounds();
        const fragment = document.createDocumentFragment();

        for (const n of this.nodes) {
            if (!this.isNodeVisible(n, bounds)) continue;
            const el = document.createElement("div");
            el.className = "neural-node";
            el.dataset.nodeId = n.id;
            el.style.left = n.x + "px";
            el.style.top = n.y + "px";
            el.style.width = "180px";

            const header = document.createElement("div");
            header.className = "node-header";
            const title = document.createElement("span");
            title.className = "node-title";
            title.textContent = n.title || "untitled";
            const editBtn = document.createElement("button");
            editBtn.className = "node-edit-btn";
            editBtn.textContent = "\u270E";
            editBtn.onclick = (e) => { e.stopPropagation(); this.openEditModal(n.id); };
            header.appendChild(title);
            header.appendChild(editBtn);

            const content = document.createElement("div");
            content.className = "node-content";
            content.textContent = n.content || "";

            const ports = document.createElement("div");
            ports.className = "node-ports";
            const portIn = document.createElement("div");
            portIn.className = "port port-in";
            portIn.title = "Connect to this neuron";
            const portOut = document.createElement("div");
            portOut.className = "port port-out";
            portOut.title = "Connect from this neuron";

            portOut.onmousedown = (e) => this.startConnection(e, n, el);
            portIn.onmouseup = () => this.finishConnection(n);

            ports.appendChild(portIn);
            ports.appendChild(portOut);

            el.appendChild(header);
            el.appendChild(content);
            el.appendChild(ports);

            el.onmousedown = (e) => this.startDrag(e, n, el);
            fragment.appendChild(el);
        }
        this.nodesContainer.appendChild(fragment);
    }

    private renderEdges(): void {
        const ns = new Map<string, NeuralNode>();
        for (const n of this.nodes) ns.set(n.id, n);
        const bounds = this.getViewportBounds();
        let html = "";

        for (const e of this.edges) {
            const src = ns.get(e.source_node_id);
            const tgt = ns.get(e.target_node_id);
            if (!src || !tgt) continue;
            if (!this.isNodeVisible(src, bounds) && !this.isNodeVisible(tgt, bounds)) continue;

            const p0x = src.x + 180;
            const p0y = src.y + 40;
            const p3x = tgt.x;
            const p3y = tgt.y + 40;
            const offset = Math.abs(p3x - p0x) * 0.4;
            const p1x = p0x + offset;
            const p1y = p0y;
            const p2x = p3x - offset;
            const p2y = p3y;

            const color = e.is_manual ? "var(--edge-manual)" : "var(--edge-auto)";
            const selected = e.id === this.selectedEdgeId;
            const strokeWidth = selected ? 3 : 1.5;

            html += `<path d="M ${p0x} ${p0y} C ${p1x} ${p1y} ${p2x} ${p2y} ${p3x} ${p3y}" 
                      stroke="${color}" stroke-width="${strokeWidth}" fill="none"
                      data-edge-id="${e.id}" class="neural-edge" 
                      style="cursor:pointer;transition:stroke-width 0.15s;"/>
                     <polygon points="0,-4 10,0 0,4" fill="${color}" 
                      transform="translate(${p3x},${p3y}) rotate(${Math.atan2(p3y - p1y, p3x - p1x) * 180 / Math.PI})"
                      style="pointer-events:none;"/>`;
        }

        this.svg.innerHTML = html;
        this.svg.querySelectorAll(".neural-edge").forEach(path => {
            path.addEventListener("click", (ev) => {
                ev.stopPropagation();
                const edgeId = (path as SVGElement).dataset.edgeId || null;
                if (this.selectedEdgeId === edgeId) {
                    this.selectedEdgeId = null;
                    if (confirm("Delete this connection?")) {
                        fetch("/api/memory/edges/" + edgeId, { method: "DELETE" }).then(r => {
                            if (r.ok) this.load();
                        });
                    }
                } else {
                    this.selectedEdgeId = edgeId;
                    this.renderEdges();
                }
            });
        });
    }

    private startConnection(e: MouseEvent, src: NeuralNode, el: HTMLElement): void {
        e.stopPropagation();
        if (this.connecting) return;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
        line.id = "neural-temp-line";
        const x1 = src.x + 180;
        const y1 = src.y + 40;
        line.setAttribute("d", `M ${x1} ${y1} L ${x1} ${y1}`);
        line.style.stroke = "var(--warning)";
        line.style.strokeWidth = "2";
        line.style.fill = "none";
        line.style.strokeDasharray = "5,5";
        line.style.pointerEvents = "none";
        this.svg.appendChild(line);
        this.connecting = { sourceNode: src, tempLine: line };
        el.querySelector(".port-out")?.classList.add("port-connecting");
    }

    private finishConnection(tgt: NeuralNode): void {
        if (!this.connecting || this.connecting.sourceNode.id === tgt.id) return;
        const src = this.connecting.sourceNode;
        fetch("/api/memory/edges", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source_id: src.id, target_id: tgt.id, strength: 1.0 }),
        }).then(r => { if (r.ok) this.load(); });
        this.cancelConnection();
    }

    private cancelConnection(): void {
        if (this.connecting) {
            this.connecting.tempLine.remove();
            this.canvas.querySelector(".port-connecting")?.classList.remove("port-connecting");
            this.connecting = null;
        }
    }

    private startDrag(e: MouseEvent, n: NeuralNode, el: HTMLElement): void {
        if ((e.target as HTMLElement).closest(".port, .node-edit-btn")) return;
        this.dragNode = n;
        this.dragNodeEl = el;
        const rect = el.getBoundingClientRect();
        this.dragOffsetX = e.clientX - rect.left;
        this.dragOffsetY = e.clientY - rect.top;
        el.style.cursor = "grabbing";
        e.preventDefault();
    }

    private startPan(e: MouseEvent): void {
        this.isPanning = true;
        this.panStartX = e.clientX;
        this.panStartY = e.clientY;
        this.panStartPanX = this.panX;
        this.panStartPanY = this.panY;
        this.canvas.style.cursor = "grabbing";
    }

    private applyZoom(delta: number): void {
        const oldZoom = this.zoom;
        this.zoom = Math.max(0.3, Math.min(3, this.zoom + delta));
        this.panX = this.panX * (this.zoom / oldZoom);
        this.panY = this.panY * (this.zoom / oldZoom);
        this.updateTransform();
    }

    private updateTransform(): void {
        this.nodesContainer.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
        this.svg.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
        this.svg.style.transformOrigin = "0 0";
        this.zoomLevelEl.textContent = Math.round(this.zoom * 100) + "%";
    }

    private setupModal(): void {
        document.getElementById("modal-close-btn")!.onclick = () => this.closeModal();
        document.getElementById("modal-save-btn")!.onclick = () => this.saveModal();
        document.getElementById("modal-delete-btn")!.onclick = () => this.deleteModal();
        document.getElementById("node-edit-modal")!.onclick = (e) => {
            if (e.target === e.currentTarget) this.closeModal();
        };
    }

    private openEditModal(nodeId: string): void {
        this.editNodeId = nodeId;
        const n = this.nodes.find(x => x.id === nodeId);
        if (!n) return;
        const titleInput = document.getElementById("modal-title-input") as HTMLInputElement | null;
        const contentInput = document.getElementById("modal-content-input") as HTMLTextAreaElement | null;
        if (titleInput) titleInput.value = n.title || "";
        if (contentInput) contentInput.value = n.content || "";
        const idEl = document.getElementById("modal-node-id");
        if (idEl) idEl.textContent = "ID: " + nodeId;
        const conns = this.edges.filter(e => e.source_node_id === nodeId || e.target_node_id === nodeId);
        const connEl = document.getElementById("modal-node-connections");
        if (connEl) connEl.textContent = conns.length + " connections";
        document.getElementById("node-edit-modal")!.classList.remove("hidden");
    }

    private closeModal(): void {
        document.getElementById("node-edit-modal")!.classList.add("hidden");
        this.editNodeId = null;
    }

    private async saveModal(): Promise<void> {
        const id = this.editNodeId;
        if (!id) return;
        const titleInput = document.getElementById("modal-title-input") as HTMLInputElement | null;
        const contentInput = document.getElementById("modal-content-input") as HTMLTextAreaElement | null;
        const title = titleInput ? titleInput.value.trim() : "";
        const content = contentInput ? contentInput.value.trim() : "";
        try {
            const resp = await fetch("/api/memory/nodes/" + id, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title, content }),
            });
            if (!resp.ok) console.error("Failed to save node:", resp.status);
        } catch (e) { console.error("Failed to save node:", e); }
        this.closeModal();
        await this.load();
    }

    private async deleteModal(): Promise<void> {
        const id = this.editNodeId;
        if (!id) return;
        if (!confirm("Delete this neuron and all its connections?")) return;
        try {
            const resp = await fetch("/api/memory/nodes/" + id, { method: "DELETE" });
            if (!resp.ok) console.error("Failed to delete node:", resp.status);
        } catch (e) { console.error("Failed to delete node:", e); }
        this.closeModal();
        await this.load();
    }

    private setupEvents(): void {
        this.canvas.onmousedown = (e: MouseEvent) => {
            if (e.target === this.canvas || (e.target as HTMLElement).id === "neural-grid") {
                this.startPan(e);
            }
        };

        document.onmousemove = (e: MouseEvent) => {
            if (this.dragNode && this.dragNodeEl) {
                const canvasRect = this.canvas.getBoundingClientRect();
                const newX = (e.clientX - canvasRect.left - this.panX - this.dragOffsetX) / this.zoom;
                const newY = (e.clientY - canvasRect.top - this.panY - this.dragOffsetY) / this.zoom;
                this.dragNode.x = Math.round(newX);
                this.dragNode.y = Math.round(newY);
                this.dragNodeEl.style.left = this.dragNode.x + "px";
                this.dragNodeEl.style.top = this.dragNode.y + "px";
                this.renderEdges();
                if (this.updateDebounce) clearTimeout(this.updateDebounce);
                const dn = this.dragNode;
                this.updateDebounce = window.setTimeout(() => {
                    fetch("/api/memory/nodes/" + dn.id, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ x: dn.x, y: dn.y }),
                    });
                }, 300);
                if (this.connecting) {
                    const mx = (e.clientX - canvasRect.left - this.panX) / this.zoom;
                    const my = (e.clientY - canvasRect.top - this.panY) / this.zoom;
                    const sx = this.connecting.sourceNode.x + 180;
                    const sy = this.connecting.sourceNode.y + 40;
                    const off = Math.abs(mx - sx) * 0.4;
                    const d = `M ${sx} ${sy} C ${sx + off} ${sy} ${mx - off} ${my} ${mx} ${my}`;
                    this.connecting.tempLine.setAttribute("d", d);
                }
            } else if (this.isPanning) {
                this.panX = this.panStartPanX + (e.clientX - this.panStartX);
                this.panY = this.panStartPanY + (e.clientY - this.panStartY);
                this.updateTransform();
                this.renderEdges();
                this.renderNodes();
            }
        };

        document.onmouseup = () => {
            if (this.dragNodeEl) {
                this.dragNodeEl.style.cursor = "grab";
            }
            this.dragNode = null;
            this.dragNodeEl = null;
            this.isPanning = false;
            this.canvas.style.cursor = "grab";
        };

        this.canvas.onwheel = (e: WheelEvent) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            this.applyZoom(delta);
            this.render();
        };

        document.getElementById("neural-new-btn")!.onclick = async () => {
            const canvasRect = this.canvas.getBoundingClientRect();
            const cx = Math.round((canvasRect.width / 2 - this.panX) / this.zoom);
            const cy = Math.round((canvasRect.height / 2 - this.panY) / this.zoom);
            const title = prompt("Neuron title:") || "New Neuron";
            try {
                const resp = await fetch("/api/memory/nodes", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title, content: "", x: cx, y: cy }),
                });
                if (!resp.ok) console.error("Failed to create neuron:", resp.status);
            } catch (e) { console.error("Failed to create neuron:", e); }
            await this.load();
        };

        document.getElementById("neural-zoom-in")!.onclick = () => { this.applyZoom(0.2); this.render(); };
        document.getElementById("neural-zoom-out")!.onclick = () => { this.applyZoom(-0.2); this.render(); };
        document.getElementById("neural-zoom-reset")!.onclick = () => {
            this.panX = 0; this.panY = 0; this.zoom = 1;
            this.updateTransform();
            this.render();
        };

        this.canvas.onclick = (e) => {
            if (e.target === this.canvas || (e.target as HTMLElement).id === "neural-grid") {
                if (this.connecting) this.cancelConnection();
                if (this.selectedEdgeId) { this.selectedEdgeId = null; this.renderEdges(); }
            }
        };
    }
}

class MemoryUI {
    private neuralUI: NeuralGraphUI;

    constructor() {
        this.neuralUI = new NeuralGraphUI();
    }

    async load(): Promise<void> {
        await this.neuralUI.load();
    }
}

class ToolsUI {
    async load(): Promise<void> {
        try {
            const resp = await fetch("/api/system/tools");
            const data = await resp.json();
            const list = document.getElementById("tools-list")!;
            list.innerHTML = "";
            for (const t of data.tools) {
                const card = document.createElement("div");
                card.className = "tool-card";
                const h4 = document.createElement("h4");
                h4.textContent = t.name;
                card.appendChild(h4);
                const p = document.createElement("p");
                p.textContent = t.description;
                card.appendChild(p);
                const meta = document.createElement("p");
                meta.style.cssText = "font-size:11px;color:var(--text-muted);margin-top:4px";
                const params = t.spec && t.spec.parameters ? Object.keys(t.spec.parameters) : [];
                meta.textContent = "Params: " + (params.join(", ") || "none");
                card.appendChild(meta);
                list.appendChild(card);
            }
        } catch (e) { console.error(e); }
    }
}

class SystemUI {
    async loadStatus(): Promise<void> {
        try {
            const resp = await fetch("/api/system/status");
            const data = await resp.json();
            const info = document.getElementById("status-info")!;
            info.innerHTML = "";
            const addRow = (label: string, value: string) => {
                const div = document.createElement("div");
                const lbl = document.createElement("span");
                lbl.className = "label";
                lbl.textContent = label + " ";
                div.appendChild(lbl);
                div.appendChild(document.createTextNode(value));
                info.appendChild(div);
            };
            addRow("Uptime:", Math.round(data.uptime) + "s");
            addRow("OS:", data.system.os + " " + data.system.release);
            addRow("Python:", data.system.python);
            addRow("CPU:", data.resources.cpu_percent + "%");
            addRow("Memory:", data.resources.memory_used_gb + "GB / " + data.resources.memory_total_gb + "GB (" + data.resources.memory_percent + "%)");
            addRow("Disk:", data.resources.disk_used_gb + "GB / " + data.resources.disk_total_gb + "GB");
            addRow("Provider:", data.ayassek.active_provider + " / " + data.ayassek.active_model);
            addRow("Memory Messages:", String(data.ayassek.memory_messages));
            const tel = document.getElementById("telemetry")!;
            tel.textContent = "CPU: " + data.resources.cpu_percent + "% | Mem: " + data.resources.process_memory_mb + "MB | Up: " + Math.round(data.uptime) + "s";
        } catch (e) { console.error(e); }
    }
}

let activePanel: string = "chat";

function switchPanel(name: string, memUI: MemoryUI, toolsUI: ToolsUI, providerUI: ProviderUI, sysUI: SystemUI): void {
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    document.querySelectorAll(".sidebar-tab").forEach(t => t.classList.remove("active"));
    const panel = document.getElementById("panel-" + name);
    if (panel) panel.classList.add("active");
    const tab = document.querySelector('.sidebar-tab[data-panel="' + name + '"]');
    if (tab) tab.classList.add("active");
    activePanel = name;
    if (name === "memory") memUI.load();
    if (name === "tools") toolsUI.load();
    if (name === "providers") providerUI.refresh();
    if (name === "settings") sysUI.loadStatus();
}

function init(): void {
    const wsClient = new WebSocketClient("default");
    const chatUI = new ChatUI();
    const providerUI = new ProviderUI();
    const memUI = new MemoryUI();
    const toolsUI = new ToolsUI();
    const sysUI = new SystemUI();

    (window as any).wsClient = wsClient;
    (window as any).chatUI = chatUI;

    showLoadingScreen();
    pollReady().then(() => {

    let sessions: Array<{ id: string; name: string; messages: Array<{ role: string; content: string }>; createdAt: number }> = [];
    let activeSessionId: string | null = null;
    let switchLock: Promise<void> | null = null;

    function getLocalSessions(): Array<{ id: string; name: string; messages: Array<{ role: string; content: string }>; createdAt: number }> {
        try {
            const raw = localStorage.getItem("ayassek_sessions");
            return raw ? JSON.parse(raw) : [];
        } catch { return []; }
    }

    function saveLocalSessions(ss: any[]): void {
        localStorage.setItem("ayassek_sessions", JSON.stringify(ss));
    }

    function renderSessions(): void {
        const list = document.getElementById("sessions-list")!;
        list.innerHTML = "";
        sessions.sort((a, b) => b.createdAt - a.createdAt);
        for (const sess of sessions) {
            const item = document.createElement("div");
            item.className = "session-item" + (sess.id === activeSessionId ? " active" : "");
            item.textContent = sess.name;
            const delBtn = document.createElement("button");
            delBtn.className = "session-del";
            delBtn.textContent = "\u00d7";
            delBtn.onclick = (e: MouseEvent) => {
                e.stopPropagation();
                fetch("/api/chat/sessions/" + sess.id, { method: "DELETE" }).catch(() => {});
                sessions = sessions.filter(s => s.id !== sess.id);
                saveLocalSessions(sessions);
                if (activeSessionId === sess.id) {
                    if (sessions.length > 0) { switchToSession(sessions[0].id); }
                    else {
                        createNewSession("Chat 1");
                    }
                } else { renderSessions(); }
            };
            item.appendChild(delBtn);
            item.onclick = () => switchToSession(sess.id);
            list.appendChild(item);
        }
    }

    async function serverSessions(): Promise<Array<{ id: string; name: string }>> {
        try {
            const resp = await fetch("/api/chat/sessions");
            const data = await resp.json();
            return data.sessions || [];
        } catch { return []; }
    }

    async function loadSessionMessages(sessionId: string): Promise<Array<{ role: string; content: string }>> {
        try {
            const resp = await fetch("/api/chat/sessions/" + sessionId + "/messages");
            if (!resp.ok) return [];
            const data = await resp.json();
            return data.messages || [];
        } catch { return []; }
    }

    async function createNewSession(name: string): Promise<string> {
        try {
            const resp = await fetch("/api/chat/sessions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
            });
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            const data = await resp.json();
            const sid = data.session_id;
            const locSess = { id: sid, name, messages: [], createdAt: Date.now() };
            sessions.push(locSess);
            saveLocalSessions(sessions);
            renderSessions();
            return sid;
        } catch {
            const sid = "sess_" + Date.now().toString(36) + "_" + Math.random().toString(36).slice(2, 8);
            const locSess = { id: sid, name, messages: [], createdAt: Date.now() };
            sessions.push(locSess);
            saveLocalSessions(sessions);
            renderSessions();
            return sid;
        }
    }

    async function switchToSession(sessionId: string): Promise<void> {
        if (switchLock) { await switchLock; }
        let resolveLock: () => void = () => {};
        switchLock = new Promise<void>(r => { resolveLock = r; });
        try {
            activeSessionId = sessionId;
            wsClient.setSessionId(sessionId);
            const msgs = await loadSessionMessages(sessionId);
            if (msgs.length > 0) {
                chatUI.renderHistory(msgs);
                const locSess = sessions.find(s => s.id === sessionId);
                if (locSess) { locSess.messages = msgs; saveLocalSessions(sessions); }
            } else {
                const locSess = sessions.find(s => s.id === sessionId);
                if (locSess && locSess.messages.length > 0) chatUI.renderHistory(locSess.messages);
                else chatUI.clear();
            }
            renderSessions();
            switchPanel("chat", memUI, toolsUI, providerUI, sysUI);
        } finally { resolveLock(); switchLock = null; }
    }

    function addMessageToSession(role: string, content: string): void {
        if (!activeSessionId) return;
        const sess = sessions.find(s => s.id === activeSessionId);
        if (sess) {
            sess.messages.push({ role, content });
            saveLocalSessions(sessions);
        }
    }

    (async () => {
        const ss = await serverSessions();
        if (ss.length > 0) {
            const localMap = new Map(getLocalSessions().map(s => [s.id, s]));
            sessions = ss.map(s => {
                const local = localMap.get(s.id);
                return {
                    id: s.id,
                    name: s.name,
                    messages: local ? local.messages : [],
                    createdAt: typeof (s as any).created_at === 'number' ? (s as any).created_at * 1000 : Date.now(),
                };
            });
            saveLocalSessions(sessions);
        } else {
            const localSessions = getLocalSessions();
            if (localSessions.length > 0) {
                for (const ls of localSessions) {
                    try {
                        const resp = await fetch("/api/chat/sessions", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ name: ls.name }),
                        });
                        if (resp.ok) {
                            const data = await resp.json();
                            (ls as any).serverId = data.session_id;
                        }
                    } catch {}
                }
                sessions = localSessions;
            } else {
                const sid = await createNewSession("Chat 1");
                sessions = getLocalSessions();
                activeSessionId = sid;
                renderSessions();
                return;
            }
        }

        const first = sessions.find((s: any) => s.id === activeSessionId) || sessions[0];
        activeSessionId = first.id;
        renderSessions();
        const msgs = await loadSessionMessages(first.id);
        if (msgs.length > 0) chatUI.renderHistory(msgs);
        else if ((first as any).messages && (first as any).messages.length > 0) chatUI.renderHistory((first as any).messages);
    })();

    document.getElementById("new-session-btn")!.onclick = async () => {
        const name = "Chat " + (sessions.length + 1);
        const sid = await createNewSession(name);
        activeSessionId = sid;
        renderSessions();
        chatUI.clear();
        switchPanel("chat", memUI, toolsUI, providerUI, sysUI);
    };

    wsClient.connect();

    wsClient.on("brain.token", (data: any) => {
        chatUI.appendToken(data.token);
    });

    wsClient.on("brain.tool_call", (data: any) => {
        const indicator = document.getElementById("tool-indicator")!;
        indicator.classList.remove("hidden");
        indicator.textContent = "Running tool: " + data.tool + "...";
        wsClient.addLog("Tool call: " + data.tool + "(" + JSON.stringify(data.args) + ")", "tool");
    });

    wsClient.on("brain.tool_result", (data: any) => {
        const indicator = document.getElementById("tool-indicator")!;
        indicator.classList.add("hidden");
        wsClient.addLog("Tool result: " + data.tool + " \u2192 " + ((data.result || "").substring(0, 100)), "success");
    });

    wsClient.on("brain.response", (data: any) => {
        chatUI.finishStreaming();
        const text = (data && data.text) || "";
        if (text) addMessageToSession("assistant", text);
        setSendingState(false);
    });

    wsClient.on("brain.error", (data: any) => {
        chatUI.finishStreaming();
        const indicator = document.getElementById("tool-indicator")!;
        indicator.classList.add("hidden");
        chatUI.addSystemMsg("Error: " + data.error);
        setSendingState(false);
    });

    wsClient.on("brain.thinking", () => { chatUI.startStreaming(); });
    wsClient.on("brain.done", () => { chatUI.finishStreaming(); });
    wsClient.on("provider.changed", () => { providerUI.refresh(); });
    wsClient.on("memory.updated", () => { if (activePanel === "memory") memUI.load(); });

    let isSending: boolean = false;

    const setSendingState = (sending: boolean): void => {
        isSending = sending;
        const sendBtn = document.getElementById("send-btn") as HTMLButtonElement | null;
        const input = document.getElementById("chat-input") as HTMLTextAreaElement | null;
        if (sendBtn) { sendBtn.disabled = sending; sendBtn.textContent = sending ? "Sending..." : "Send"; }
        if (input) input.disabled = sending;
    };

    function autoResizeTextarea(): void {
        const input = document.getElementById("chat-input") as HTMLTextAreaElement | null;
        if (!input) return;
        input.style.height = "auto";
        input.style.height = Math.min(input.scrollHeight, 150) + "px";
    }

    const sendMessage = async (): Promise<void> => {
        if (isSending) return;
        const input = document.getElementById("chat-input") as HTMLTextAreaElement | null;
        if (!input) return;
        const text = input.value.trim();
        if (!text) return;
        setSendingState(true);
        input.value = "";
        autoResizeTextarea();
        chatUI.addMessage("user", text);
        addMessageToSession("user", text);
        try {
            await fetch("/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, session_id: activeSessionId || "default" }),
            });
        } catch (e) {
            chatUI.addSystemMsg("Failed to send: " + e);
            chatUI.finishStreaming();
            setSendingState(false);
        }
    };

    document.getElementById("send-btn")!.onclick = sendMessage;

    const chatInput = document.getElementById("chat-input") as HTMLTextAreaElement;
    chatInput.onkeydown = (e: KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    };
    chatInput.oninput = autoResizeTextarea;

    document.querySelectorAll(".sidebar-tab").forEach(tab => {
        tab.addEventListener("click", () => {
            switchPanel((tab as HTMLElement).dataset.panel!, memUI, toolsUI, providerUI, sysUI);
        });
    });

    document.getElementById("refresh-tools-btn")?.addEventListener("click", () => toolsUI.load());
    document.getElementById("refresh-providers-btn")?.addEventListener("click", () => providerUI.refresh());
    document.getElementById("clear-logs-btn")?.addEventListener("click", () => {
        const d = document.getElementById("logs-display");
        if (d) d.innerHTML = '<div class="log-entry">Cleared.</div>';
    });

    providerUI.refresh();

    setInterval(() => {
        if (activePanel === "settings") sysUI.loadStatus();
    }, 5000);
    });
}

document.addEventListener("DOMContentLoaded", init);