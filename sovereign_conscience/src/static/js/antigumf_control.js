document.addEventListener('DOMContentLoaded', () => {
    const statusCard = document.getElementById('status-card');
    const globalEnable = document.getElementById('global-enable-toggle');
    const dedupToggle = document.getElementById('dedup-toggle');
    const fuzzyToggle = document.getElementById('fuzzy-toggle');
    const relevanceToggle = document.getElementById('relevance-toggle');
    const consistencyToggle = document.getElementById('consistency-toggle');
    const fuzzyThreshold = document.getElementById('fuzzy-threshold');
    const fuzzyThresholdValue = document.getElementById('fuzzy-threshold-value');
    const relevanceThreshold = document.getElementById('relevance-threshold');
    const relevanceThresholdValue = document.getElementById('relevance-threshold-value');
    const reloadBtn = document.getElementById('reload-btn');
    const auditLog = document.getElementById('audit-log');
    const toast = document.getElementById('antigumf-toast');
    const reprocessForm = document.getElementById('reprocess-form');
    const reprocessId = document.getElementById('reprocess-id');
    const reprocessResult = document.getElementById('reprocess-result');

    // --- Bulk Config Import ---
    const bulkImportForm = document.getElementById('bulk-import-form');
    const bulkImportJson = document.getElementById('bulk-import-json');
    const bulkImportResult = document.getElementById('bulk-import-result');

    async function fetchStatus() {
        const resp = await fetch('/api/antigumf/status');
        if (!resp.ok) return showToast('Failed to fetch status', true);
        const data = await resp.json();
        renderStatus(data);
        setToggles(data);
        setSliders(data);
    }

    function renderStatus(data) {
        statusCard.innerHTML = `
            <div class="status-main">
                <span class="status-label">AntiGumf:</span>
                <span class="status-value ${data.enabled ? 'on' : 'off'}">${data.enabled ? 'ENABLED' : 'DISABLED'}</span>
            </div>
            <div class="status-details">
                <span>Rules: <b>${data.rules_loaded}</b></span>
                <span>Filters: <b>${data.filters_loaded}</b></span>
                <span>Tags: <b>${data.tags_loaded}</b></span>
                <span>Categories: <b>${data.categories_loaded}</b></span>
            </div>
        `;
    }

    function setToggles(data) {
        globalEnable.checked = !!data.enabled;
        dedupToggle.checked = !(data.paused && data.paused.deduplication === true);
        fuzzyToggle.checked = !(data.paused && data.paused.fuzzy === true);
        relevanceToggle.checked = !(data.paused && data.paused.relevance === true);
        consistencyToggle.checked = !(data.paused && data.paused.consistency === true);
    }

    function setSliders(data) {
        if (data.thresholds) {
            if (data.thresholds.fuzzy) {
                fuzzyThreshold.value = data.thresholds.fuzzy;
                fuzzyThresholdValue.textContent = Number(data.thresholds.fuzzy).toFixed(2);
            }
            if (data.thresholds.relevance) {
                relevanceThreshold.value = data.thresholds.relevance;
                relevanceThresholdValue.textContent = Number(data.thresholds.relevance).toFixed(2);
            }
        }
    }

    function showToast(msg, error = false) {
        toast.textContent = msg;
        toast.className = 'antigumf-toast' + (error ? ' error' : '');
        toast.style.display = 'block';
        setTimeout(() => { toast.style.display = 'none'; }, 2500);
    }

    async function postAPI(url, body) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!resp.ok) {
            showToast(`API error: ${url}`, true);
            return null;
        }
        return await resp.json();
    }

    globalEnable.addEventListener('change', async () => {
        await postAPI('/api/antigumf/enable', { enabled: globalEnable.checked });
        fetchStatus();
        showToast('AntiGumf ' + (globalEnable.checked ? 'enabled' : 'disabled'));
    });
    dedupToggle.addEventListener('change', async () => {
        await postAPI('/api/antigumf/pause', { stage: 'deduplication', paused: !dedupToggle.checked });
        fetchStatus();
        showToast('Deduplication ' + (dedupToggle.checked ? 'enabled' : 'paused'));
    });
    fuzzyToggle.addEventListener('change', async () => {
        await postAPI('/api/antigumf/pause', { stage: 'fuzzy', paused: !fuzzyToggle.checked });
        fetchStatus();
        showToast('Fuzzy matching ' + (fuzzyToggle.checked ? 'enabled' : 'paused'));
    });
    relevanceToggle.addEventListener('change', async () => {
        await postAPI('/api/antigumf/pause', { stage: 'relevance', paused: !relevanceToggle.checked });
        fetchStatus();
        showToast('Relevance scoring ' + (relevanceToggle.checked ? 'enabled' : 'paused'));
    });
    consistencyToggle.addEventListener('change', async () => {
        await postAPI('/api/antigumf/pause', { stage: 'consistency', paused: !consistencyToggle.checked });
        fetchStatus();
        showToast('Consistency check ' + (consistencyToggle.checked ? 'enabled' : 'paused'));
    });
    fuzzyThreshold.addEventListener('input', () => {
        fuzzyThresholdValue.textContent = Number(fuzzyThreshold.value).toFixed(2);
    });
    fuzzyThreshold.addEventListener('change', async () => {
        await postAPI('/api/antigumf/threshold', { stage: 'fuzzy', threshold: Number(fuzzyThreshold.value) });
        fetchStatus();
        showToast('Fuzzy threshold updated');
    });
    relevanceThreshold.addEventListener('input', () => {
        relevanceThresholdValue.textContent = Number(relevanceThreshold.value).toFixed(2);
    });
    relevanceThreshold.addEventListener('change', async () => {
        await postAPI('/api/antigumf/threshold', { stage: 'relevance', threshold: Number(relevanceThreshold.value) });
        fetchStatus();
        showToast('Relevance threshold updated');
    });
    reloadBtn.addEventListener('click', async () => {
        await postAPI('/api/antigumf/reload', {});
        fetchStatus();
        showToast('Rules/filters reloaded');
    });
    reprocessForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = Number(reprocessId.value);
        if (!id) return showToast('Enter a valid item ID', true);
        const resp = await postAPI('/api/antigumf/reprocess', { item_id: id });
        if (resp && resp.result) {
            reprocessResult.textContent = JSON.stringify(resp.result, null, 2);
            showToast('Reprocess complete');
        } else {
            reprocessResult.textContent = 'Not found or error.';
            showToast('Reprocess failed', true);
        }
    });

    async function loadAuditLog() {
        const resp = await fetch('/api/antigumf/audit');
        if (!resp.ok) return showToast('Failed to load audit log', true);
        const data = await resp.json();
        if (!data.audit_log) return;
        auditLog.innerHTML = '';
        data.audit_log.forEach(entry => {
            const div = document.createElement('div');
            div.className = 'audit-entry';
            div.innerHTML = `
                <span class="audit-type">${entry.event_type || ''}</span>
                <span class="audit-msg">${entry.reason || entry.message || ''}</span>
                <span class="audit-time">${entry.timestamp ? new Date(entry.timestamp).toLocaleString() : ''}</span>
            `;
            auditLog.appendChild(div);
        });
    }

    // Initial load
    fetchStatus();
    loadAuditLog();
    setInterval(fetchStatus, 10000);
    setInterval(loadAuditLog, 20000);

    if (bulkImportForm) {
        bulkImportForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            let config;
            try {
                config = JSON.parse(bulkImportJson.value);
            } catch (err) {
                bulkImportResult.textContent = 'Invalid JSON: ' + err.message;
                showToast('Invalid JSON', true);
                return;
            }
            bulkImportResult.textContent = 'Importing...';
            const resp = await postAPI('/api/antigumf/config/import', config);
            if (resp && !resp.error) {
                bulkImportResult.textContent = 'Import successful!\n' + JSON.stringify(resp, null, 2);
                showToast('Bulk config import successful');
                fetchStatus();
            } else {
                bulkImportResult.textContent = 'Import failed: ' + (resp && resp.error ? resp.error : 'Unknown error');
                showToast('Bulk config import failed', true);
            }
        });
    }
}); 