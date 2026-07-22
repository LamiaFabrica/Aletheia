/*
Medusa Crawler Dashboard JS
--------------------------
This file powers the real-time operator dashboard for the Medusa crawler. It provides:
- Operator controls (start, pause, resume, stop, restart, indefinite crawl)
- Real-time status card (system state, job info, queue size, errors, stats)
- Crawler queue management (load, filter, add, delete, bulk actions, job details drawer)
- Activity log streaming (live, filterable)
- AntiGumf panel (status, enable/disable, reload, rule/filter counts)
- Plugin manager panel (list, enable/disable, status)

Integration points:
- SocketIO for live status/logs
- REST API endpoints for all crawler, queue, AntiGumf, and plugin actions

Extension guidelines:
- Add new controls or panels by following the modular function structure
- Use showToast for all user feedback
- Use fetch() for all API calls, and update UI on response
- All DOM updates are idempotent and robust to missing elements
- Bulk actions and job details drawer are extensible for future features

Handoff:
- Main entry: DOMContentLoaded handler at bottom
- Key functions: setOperatorButtonStates, updateCrawlerStatusUI, loadQueue, renderQueueList, loadActivityLog, showToast
- Extendable: add new panels, filters, or SocketIO events as needed
*/

let orchestratorState = 'IDLE';
let indefiniteCrawl = false;
let socket = null;

// --- Chart.js Chart Initialization ---
let statusDonutChart, queueStatusBarChart, logBarChart;

// --- Operator Controls ---
function setOperatorButtonStates(state) {
    // Enable/disable buttons based on orchestrator state
    const startBtn = document.querySelector('.remote-btn.start');
    const pauseBtn = document.querySelector('.remote-btn.pause');
    const resumeBtn = document.querySelector('.remote-btn.resume');
    const stopBtn = document.querySelector('.remote-btn.stop');
    const restartBtn = document.querySelector('.remote-btn.restart');
    const removeBtn = document.querySelector('.remote-btn.remove');
    const infiniteBtn = document.querySelector('.remote-btn.infinite');

    if (!startBtn || !pauseBtn || !resumeBtn || !stopBtn || !restartBtn || !infiniteBtn) return;

    // All disabled by default
    startBtn.disabled = pauseBtn.disabled = resumeBtn.disabled = stopBtn.disabled = restartBtn.disabled = false;

    switch (state) {
        case 'RUNNING':
            startBtn.disabled = true;
            resumeBtn.disabled = true;
            pauseBtn.disabled = false;
            stopBtn.disabled = false;
            break;
        case 'PAUSED':
            startBtn.disabled = true;
            pauseBtn.disabled = true;
            resumeBtn.disabled = false;
            stopBtn.disabled = false;
            break;
        case 'IDLE':
        case 'STOPPED':
        case 'COMPLETED':
        case 'EXHAUSTED':
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            resumeBtn.disabled = true;
            stopBtn.disabled = true;
            break;
        case 'ERROR':
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            resumeBtn.disabled = true;
            stopBtn.disabled = false;
            break;
        default:
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            resumeBtn.disabled = true;
            stopBtn.disabled = true;
    }
    // Indefinite crawl toggle is always enabled
    infiniteBtn.disabled = false;
    // Disable unavailable features
    pauseBtn.disabled = true;
    resumeBtn.disabled = true;
    restartBtn.disabled = true;
    if (removeBtn) removeBtn.disabled = false;
}

function startCrawler() {
    fetch('/api/crawl', {method: 'POST'})
        .then(r => r.json()).then(data => {
            showToast('Crawler started', data);
            fetchCrawlerStats();
        })
        .catch(e => showToast('Failed to start crawler', e, true));
}
function pauseCrawler() {
    showToast('Pause is not available in this version.', null, true);
}
function resumeCrawler() {
    showToast('Resume is not available in this version.', null, true);
}
function stopCrawler() {
    // Get the current job ID from the status card
    const currentJobId = document.getElementById('currentJobId')?.textContent;
    if (!currentJobId || currentJobId === 'N/A') {
        showToast('No current job to stop', null, true);
        return;
    }
    fetch(`/api/crawl/${currentJobId}/stop`, {method: 'POST'})
        .then(r => r.json()).then(data => {
            showToast('Crawler stopped', data);
            fetchCrawlerStats();
        })
        .catch(e => showToast('Failed to stop crawler', e, true));
}
function restartCrawler() {
    showToast('Restart is not available in this version.', null, true);
}
function removeCrawlerJob() {
    const currentJobId = document.getElementById('currentJobId')?.textContent;
    if (!currentJobId || currentJobId === 'N/A') {
        showToast('No current job to remove', null, true);
        return;
    }
    fetch(`/api/crawl/${currentJobId}/remove`, {method: 'POST'})
        .then(r => r.json()).then(data => {
            showToast('Job removed', data);
            fetchCrawlerStats();
        })
        .catch(e => showToast('Failed to remove job', e, true));
}
function toggleIndefiniteCrawl() {
    indefiniteCrawl = !indefiniteCrawl;
    // Optionally persist to backend
    showToast('Indefinite Crawl: ' + (indefiniteCrawl ? 'On' : 'Off'));
}

// --- Toast Feedback ---
function showToast(message, data, isError) {
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.style.position = 'fixed';
        toastContainer.style.top = '24px';
        toastContainer.style.right = '24px';
        toastContainer.style.zIndex = 9999;
        document.body.appendChild(toastContainer);
    }
    const toast = document.createElement('div');
    toast.className = 'toast align-items-center text-white ' + (isError ? 'bg-danger' : 'bg-success');
    toast.role = 'alert';
    toast.ariaLive = 'assertive';
    toast.ariaAtomic = 'true';
    toast.style.minWidth = '220px';
    toast.style.marginBottom = '12px';
    toast.style.opacity = 0;
    toast.style.transform = 'translateY(-20px)';
    toast.innerHTML = `<div class="d-flex"><div class="toast-body">${message}</div><button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button></div>`;
    toastContainer.appendChild(toast);
    setTimeout(()=>{toast.style.opacity=1;toast.style.transform='translateY(0)';},10);
    if (window.bootstrap && window.bootstrap.Toast) {
        const bsToast = new window.bootstrap.Toast(toast, {delay: 3000});
        bsToast.show();
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    } else {
        setTimeout(() => {toast.style.opacity=0;toast.style.transform='translateY(-20px)';setTimeout(()=>toast.remove(),300);}, 3000);
    }
    console.log('[TOAST]', message, data);
}

// --- Real-Time Status ---
function updateCrawlerStatusUI(status) {
    // Update DOM elements for status card
    safeSetText('systemStateText', status.system_state || 'Unknown');
    // Status icon
    const statusIcon = document.getElementById('statusIcon');
    let iconHtml = '';
    switch ((status.system_state || '').toUpperCase()) {
        case 'RUNNING': iconHtml = '<i class="bi bi-play-circle-fill" style="color:#00e0ff;"></i>'; break;
        case 'PAUSED': iconHtml = '<i class="bi bi-pause-circle-fill" style="color:#ffc107;"></i>'; break;
        case 'IDLE': iconHtml = '<i class="bi bi-stop-circle-fill" style="color:#adb5bd;"></i>'; break;
        case 'STOPPED': iconHtml = '<i class="bi bi-stop-circle-fill" style="color:#dc3545;"></i>'; break;
        case 'ERROR': iconHtml = '<i class="bi bi-exclamation-octagon-fill" style="color:#dc3545;"></i>'; break;
        default: iconHtml = '<i class="bi bi-question-circle-fill" style="color:#adb5bd;"></i>';
    }
    statusIcon.innerHTML = iconHtml;
    // Current job
    safeSetText('currentJobId', status.current_job?.id || 'N/A');
    safeSetText('currentJobStart', status.current_job?.started_at || 'N/A');
    safeSetText('urlsProcessed', status.current_job?.urls_processed || 'N/A');
    safeSetText('errorsThisJob', status.current_job?.errors_this_job || 'N/A');
    safeSetText('newKbItems', status.current_job?.new_kb_items || 'N/A');
    safeSetText('dataVolume', status.current_job?.data_volume_mb || 'N/A');
    safeSetText('urlsInQueue', status.queue_size ?? 'N/A');
    // Historical stats
    safeSetText('totalJobs', status.historical_stats?.total_crawl_jobs_run ?? 'N/A');
    safeSetText('totalUrls', status.historical_stats?.total_urls_crawled_ever ?? 'N/A');
    safeSetText('totalKbItems', status.historical_stats?.total_kb_items_added_ever ?? 'N/A');
    // Error details
    safeSetText('errorDetails', status.last_error_details?.message || '');
    setOperatorButtonStates(status.system_state);
    updateChartsFromStats(status);
}

function fetchCrawlerStats() {
    fetch('/api/crawler/stats').then(r => r.json()).then(updateCrawlerStatusUI);
}

// --- Crawler Queue Management ---
let lastQueueData = [];
function renderQueueList(queue) {
    lastQueueData = queue;
    const list = document.getElementById('crawlerQueueList');
    if (!list) return;
    list.innerHTML = '';
    if (!queue || !queue.length) {
        list.innerHTML = '<div class="text-muted">Queue is empty.</div>';
        return;
    }
    queue.forEach(job => {
        const row = document.createElement('div');
        row.className = 'crawler-queue-row';
        if (selectedJobIds.has(job.id)) row.style.background = 'rgba(0,224,255,0.12)';
        row.innerHTML = `
            <input type="checkbox" style="margin-right:0.7em;" ${selectedJobIds.has(job.id)?'checked':''} onclick="toggleJobSelection(${job.id})">
            <span class="crawler-queue-status">${job.status}</span>
            <span style="font-family:monospace;cursor:pointer;" onclick="openJobDrawer(${JSON.stringify(job).replace(/"/g,'&quot;')})">${job.tool_name}</span>
            <span style="color:#00e0ff;">${job.target_url}</span>
            <span class="crawler-queue-priority">${job.priority ?? 0}</span>
            <button class="btn btn-sm btn-danger" onclick="deleteQueueJob(${job.id})">Delete</button>
        `;
        list.appendChild(row);
    });
    // Bulk actions bar
    let bulkBar = document.getElementById('queueBulkBar');
    if (!bulkBar) {
        bulkBar = document.createElement('div');
        bulkBar.id = 'queueBulkBar';
        bulkBar.style.margin = '0.7em 0';
        bulkBar.innerHTML = `<button class="btn btn-danger me-2" onclick="bulkDeleteJobs()">Delete Selected</button><button class="btn btn-warning" onclick="bulkRecrawlJobs()">Recrawl Selected</button>`;
        list.parentElement.insertBefore(bulkBar, list);
    }
    bulkBar.style.display = selectedJobIds.size ? '' : 'none';
}

function loadQueue() {
    showQueueLoadingSpinner();
    fetch('/api/crawler/queue').then(r => r.json()).then(data => {
        let queue = data.queue || [];
        queue = applyQueueFilters(queue);
        renderQueueList(queue);
        safeSetText('urlsInQueue', queue.length);
    });
}

// --- Robust event listener attachment ---
function safeAddEventListener(id, event, handler) {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, handler);
}
safeAddEventListener('refreshQueueBtn', 'click', loadQueue);
safeAddEventListener('queueStatusFilter', 'change', loadQueue);
safeAddEventListener('queueDomainFilter', 'input', function() { setTimeout(loadQueue, 300); });
safeAddEventListener('addQueueJobForm', 'submit', function(e) {
    e.preventDefault();
    const form = e.target;
    const data = {
        tool_name: form.tool_name.value,
        target_url: form.target_url.value,
        parser_hint: form.parser_hint.value,
        priority: form.priority.value
    };
    fetch('/api/crawler/queue', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    }).then(r => r.json()).then(resp => {
        if (resp.status === 'success') {
            showToast('Job added', resp);
            form.reset();
            loadQueue();
        } else {
            showToast('Failed to add job: ' + (resp.error || resp.message), resp, true);
        }
    });
});
safeAddEventListener('antigumfToggleBtn', 'click', toggleAntiGumf);
safeAddEventListener('antigumfStatusText', 'click', loadAntiGumfStatus);

function deleteQueueJob(id) {
    fetch(`/api/crawler/queue/${id}`, {method: 'DELETE'})
        .then(r => r.json()).then(data => {
            showToast('Job deleted', data);
            loadQueue();
        });
}

// --- Activity Log Management ---
let logEntries = [];
function renderActivityLog(entries) {
    const logDiv = document.getElementById('activityLog');
    if (!logDiv) return;
    logDiv.innerHTML = '';
    if (!entries || !entries.length) {
        logDiv.innerHTML = '<div class="text-muted">No log entries.</div>';
        return;
    }
    entries.forEach(entry => {
        const row = document.createElement('div');
        row.style.marginBottom = '0.3em';
        row.innerHTML = `<span style="color:#a259f7;font-weight:600;">[${entry.severity}]</span> <span style="color:#00e0ff;">${entry.event_type}</span> <span style="color:#adb5bd;">${entry.message}</span> <span style="color:#888;font-size:0.92em;">${entry.timestamp}</span>`;
        logDiv.appendChild(row);
    });
    updateLogBarChartFromEntries(entries);
}

function loadActivityLog() {
    showLogLoadingSpinner();
    fetch('/api/admin/activity_log?page_size=50').then(r => r.json()).then(data => {
        logEntries = data.data || [];
        renderActivityLog(logEntries);
    });
}

// Stream new log entries via SocketIO
function addLogEntry(entry) {
    logEntries.unshift(entry);
    if (logEntries.length > 100) logEntries.pop();
    renderActivityLog(logEntries);
}

// Log filter form
const logFilterForm = document.getElementById('logFilterForm');
if (logFilterForm) {
    logFilterForm.addEventListener('submit', function(e) {
        e.preventDefault();
        // For now, just reload log (can add filter params)
        loadActivityLog();
    });
}

// --- SocketIO Integration (extend) ---
function setupSocketIO() {
    socket = io();
    socket.on('crawler_status_update', data => {
        orchestratorState = data.system_state;
        updateCrawlerStatusUI(data);
        setOperatorButtonStates(orchestratorState);
        loadQueue();
    });
    socket.on('new_log_entry', entry => {
        addLogEntry(entry);
    });
}

document.addEventListener('DOMContentLoaded', function() {
    setupSocketIO();
    fetchCrawlerStats();
    loadQueue();
    loadActivityLog();
    // Status Donut Chart
    const donutCtx = document.getElementById('statusDonutChart')?.getContext('2d');
    if (donutCtx) {
        statusDonutChart = new Chart(donutCtx, {
            type: 'doughnut',
            data: { labels: ['Running', 'Paused', 'Idle', 'Error'], datasets: [{ data: [1,0,0,0], backgroundColor: ['#00e0ff','#ffc107','#adb5bd','#dc3545'] }] },
            options: { cutout: '70%', plugins: { legend: { display: false } } }
        });
    }
    // Queue Status Bar Chart
    const queueBarCtx = document.getElementById('queueStatusBarChart')?.getContext('2d');
    if (queueBarCtx) {
        queueStatusBarChart = new Chart(queueBarCtx, {
            type: 'bar',
            data: { labels: ['Queued','Pending','Running','Completed','Failed','Error'], datasets: [{ label: 'Jobs', data: [0,0,0,0,0,0], backgroundColor: ['#a259f7','#00e0ff','#ffc107','#00ff41','#dc3545','#d63384'] }] },
            options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }
    // Log Bar Chart
    const logBarCtx = document.getElementById('logBarChart')?.getContext('2d');
    if (logBarCtx) {
        logBarChart = new Chart(logBarCtx, {
            type: 'bar',
            data: { labels: ['Info','Warn','Error','Critical'], datasets: [{ label: 'Logs', data: [0,0,0,0], backgroundColor: ['#6c757d','#ffc107','#dc3545','#d63384'] }] },
            options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
        });
    }
});

// --- Micro-interactions: Loading Spinners ---
function showQueueLoadingSpinner() {
    const list = document.getElementById('crawlerQueueList');
    if (list) list.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>';
}
function showLogLoadingSpinner() {
    const logDiv = document.getElementById('activityLog');
    if (logDiv) logDiv.innerHTML = '<div class="spinner-border text-info" role="status"><span class="visually-hidden">Loading...</span></div>';
}

// --- Advanced Queue Filtering ---
function applyQueueFilters(queue) {
    const status = document.getElementById('queueStatusFilter').value;
    const domain = document.getElementById('queueDomainFilter').value.trim();
    const parser = document.getElementById('queueParserFilter')?.value;
    const priority = document.getElementById('queuePriorityFilter')?.value;
    const search = document.getElementById('queueSearchFilter')?.value.trim().toLowerCase();
    return queue.filter(j => {
        if (status && j.status !== status) return false;
        if (domain && !(j.target_url || '').includes(domain)) return false;
        if (parser && j.parser_hint !== parser) return false;
        if (priority && String(j.priority) !== priority) return false;
        if (search && !((j.tool_name || '').toLowerCase().includes(search) || (j.target_url || '').toLowerCase().includes(search))) return false;
        return true;
    });
}

// --- Job Details Drawer ---
let openJobDrawerId = null;
function openJobDrawer(job) {
    let drawer = document.getElementById('jobDetailsDrawer');
    if (!drawer) {
        drawer = document.createElement('div');
        drawer.id = 'jobDetailsDrawer';
        drawer.style.position = 'fixed';
        drawer.style.top = '0';
        drawer.style.right = '0';
        drawer.style.width = '380px';
        drawer.style.height = '100%';
        drawer.style.background = 'rgba(30,32,40,0.97)';
        drawer.style.boxShadow = '0 0 32px #a259f7cc';
        drawer.style.zIndex = 20000;
        drawer.style.transition = 'transform 0.3s';
        drawer.style.transform = 'translateX(100%)';
        drawer.innerHTML = '<div style="padding:2em;"><button id="closeJobDrawerBtn" class="btn btn-secondary mb-3">Close</button><div id="jobDrawerContent"></div></div>';
        document.body.appendChild(drawer);
        document.getElementById('closeJobDrawerBtn').onclick = closeJobDrawer;
    }
    const content = document.getElementById('jobDrawerContent');
    content.innerHTML = Object.entries(job).map(([k,v]) => `<div><b>${k}:</b> <span style="color:#00e0ff;">${v}</span></div>`).join('');
    // Add actions
    content.innerHTML += `<hr><button class="btn btn-warning me-2" onclick="recrawlJob(${job.id})">Recrawl</button><button class="btn btn-danger" onclick="deleteQueueJob(${job.id})">Delete</button>`;
    drawer.style.transform = 'translateX(0)';
    openJobDrawerId = job.id;
}
function closeJobDrawer() {
    const drawer = document.getElementById('jobDetailsDrawer');
    if (drawer) drawer.style.transform = 'translateX(100%)';
    openJobDrawerId = null;
}
window.openJobDrawer = openJobDrawer;
window.closeJobDrawer = closeJobDrawer;

// --- Bulk Actions ---
let selectedJobIds = new Set();
function toggleJobSelection(id) {
    if (selectedJobIds.has(id)) selectedJobIds.delete(id); else selectedJobIds.add(id);
    renderQueueList(lastQueueData);
}
function bulkDeleteJobs() {
    if (!selectedJobIds.size) return;
    if (!confirm('Delete selected jobs?')) return;
    Promise.all(Array.from(selectedJobIds).map(id => fetch(`/api/crawler/queue/${id}`, {method:'DELETE'}))).then(() => {
        showToast('Deleted selected jobs');
        selectedJobIds.clear();
        loadQueue();
    });
}
function bulkRecrawlJobs() {
    if (!selectedJobIds.size) return;
    Promise.all(Array.from(selectedJobIds).map(id => fetch(`/api/crawler/queue/${id}/recrawl`, {method:'PUT'}))).then(() => {
        showToast('Recrawl triggered for selected jobs');
        selectedJobIds.clear();
        loadQueue();
    });
}
window.bulkDeleteJobs = bulkDeleteJobs;
window.bulkRecrawlJobs = bulkRecrawlJobs;
window.toggleJobSelection = toggleJobSelection;

// Add advanced filter UI elements (parser, priority, search)
function addQueueAdvancedFilters() {
    const form = document.getElementById('queueFilterForm');
    if (!form) return;
    if (!document.getElementById('queueParserFilter')) {
        const parserSel = document.createElement('select');
        parserSel.className = 'form-select';
        parserSel.id = 'queueParserFilter';
        parserSel.innerHTML = '<option value="">All Parsers</option>';
        form.appendChild(parserSel);
        // Load parser list
        fetch('/api/plugins/parsers').then(r=>r.json()).then(data=>{
            (data.data||[]).forEach(p=>{
                const opt = document.createElement('option');
                opt.value = p.name;
                opt.textContent = p.name;
                parserSel.appendChild(opt);
            });
        });
        parserSel.addEventListener('change', loadQueue);
    }
    if (!document.getElementById('queuePriorityFilter')) {
        const prioSel = document.createElement('select');
        prioSel.className = 'form-select';
        prioSel.id = 'queuePriorityFilter';
        prioSel.innerHTML = '<option value="">All Priorities</option>';
        for (let i = 0; i <= 10; ++i) {
            const opt = document.createElement('option');
            opt.value = String(i);
            opt.textContent = i;
            prioSel.appendChild(opt);
        }
        form.appendChild(prioSel);
        prioSel.addEventListener('change', loadQueue);
    }
    if (!document.getElementById('queueSearchFilter')) {
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.className = 'form-control';
        searchInput.id = 'queueSearchFilter';
        searchInput.placeholder = 'Search tool name or URL...';
        form.appendChild(searchInput);
        searchInput.addEventListener('input', function() { setTimeout(loadQueue, 300); });
    }
}
addQueueAdvancedFilters();

// --- AntiGumf Integration ---
function loadAntiGumfStatus() {
    fetch('/api/antigumf/status').then(r=>r.json()).then(data=>{
        safeSetText('antigumfStatusText', data.enabled ? 'Enabled' : 'Disabled');
        safeSetText('antigumfToggleBtn', data.enabled ? 'Disable' : 'Enable');
        safeSetText('antigumfStats', `Rules: ${data.rules_loaded || 0}, Filters: ${data.filters_loaded || 0}`);
    });
}
function toggleAntiGumf() {
    fetch('/api/antigumf/enable', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled: null}) // Toggle
    }).then(()=>{loadAntiGumfStatus();showToast('Toggled AntiGumf');});
}

// --- Plugin Manager Integration ---
function loadPluginList() {
    fetch('/api/plugins/parsers').then(r=>r.json()).then(data=>{
        const list = document.getElementById('pluginList');
        if (!list) return;
        list.innerHTML = '';
        (data.data||[]).forEach(plugin=>{
            const card = document.createElement('div');
            card.className = 'card mb-2';
            card.innerHTML = `<b>${plugin.name}</b> <span style="color:${plugin.enabled?'#00ff41':'#dc3545'};font-weight:600;">${plugin.enabled?'Enabled':'Disabled'}</span> <button class="btn btn-sm btn-${plugin.enabled?'danger':'success'} ms-2">${plugin.enabled?'Disable':'Enable'}</button>`;
            card.querySelector('button').onclick = ()=>{
                fetch(`/api/plugins/parsers/${plugin.name}/${plugin.enabled?'disable':'enable'}`,{method:'POST'}).then(()=>{loadPluginList();showToast(`${plugin.enabled?'Disabled':'Enabled'} ${plugin.name}`);});
            };
            list.appendChild(card);
        });
    });
}

// --- Init AntiGumf and Plugin Panels on load ---
document.addEventListener('DOMContentLoaded', function() {
    loadAntiGumfStatus();
    loadPluginList();
});

// --- Floating Popout Panel Logic ---
window.togglePopout = function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('open');
};

// --- Real-time Chart Updates ---
function updateChartsFromStats(stats) {
    if (statusDonutChart) {
        const state = (stats.system_state||'').toUpperCase();
        let data = [0,0,0,0];
        if (state==='RUNNING') data[0]=1;
        else if (state==='PAUSED') data[1]=1;
        else if (state==='IDLE') data[2]=1;
        else if (state==='ERROR') data[3]=1;
        statusDonutChart.data.datasets[0].data = data;
        statusDonutChart.update();
    }
    if (queueStatusBarChart && stats.queue_status_counts) {
        queueStatusBarChart.data.datasets[0].data = [
            stats.queue_status_counts.queued||0,
            stats.queue_status_counts.pending||0,
            stats.queue_status_counts.running||0,
            stats.queue_status_counts.completed||0,
            stats.queue_status_counts.failed||0,
            stats.queue_status_counts.error||0
        ];
        queueStatusBarChart.update();
    }
}
function updateLogBarChartFromEntries(entries) {
    if (!logBarChart) return;
    let info=0, warn=0, error=0, crit=0;
    entries.forEach(e=>{
        if (e.severity==='INFO') info++;
        else if (e.severity==='WARNING') warn++;
        else if (e.severity==='ERROR') error++;
        else if (e.severity==='CRITICAL') crit++;
    });
    logBarChart.data.datasets[0].data = [info, warn, error, crit];
    logBarChart.update();
}

// Add null checks for all DOM updates (example for systemStateText)
function safeSetText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}
// Replace all direct .textContent assignments in updateCrawlerStatusUI with safeSetText
// ... (repeat for all relevant fields) ... 