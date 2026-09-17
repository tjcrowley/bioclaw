// api.js — BioClaw API client module
// All functions use credentials:'include' to send the session cookie automatically.
// On 401, a 'bioclaw:unauthorized' CustomEvent is dispatched on window.

function _handle401() {
    window.dispatchEvent(new CustomEvent('bioclaw:unauthorized'));
}

async function _fetch(url, opts = {}) {
    const resp = await fetch(url, { credentials: 'include', ...opts });
    if (resp.status === 401) {
        _handle401();
        throw new Error('unauthorized');
    }
    return resp;
}

export async function login(password) {
    const resp = await fetch('/api/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
    });
    if (!resp.ok) throw new Error('unauthorized');
    return resp.json();
}

export async function askQuestion(question, sessionId, streamId) {
    const resp = await _fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            question,
            session_id: sessionId || null,
            stream_id: streamId || null,
        }),
    });
    if (!resp.ok) throw new Error(`ask failed: ${resp.status}`);
    return resp.json();
}

export function openToolStream(streamId, { onEvent, onClose } = {}) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Browser sends session cookie on WS upgrade automatically — no ?session= needed.
    const ws = new WebSocket(`${protocol}//${location.host}/ws/${streamId}`);

    ws.addEventListener('message', (e) => {
        try {
            const event = JSON.parse(e.data);
            if (typeof onEvent === 'function') onEvent(event);
        } catch { /* ignore parse errors */ }
    });

    ws.addEventListener('close', () => {
        if (typeof onClose === 'function') onClose();
    });

    ws.addEventListener('error', () => {
        // WS errors often precede the close event; onClose handles cleanup
    });

    return {
        close() { ws.close(); },
    };
}

export async function listSessions() {
    const resp = await _fetch('/api/sessions');
    if (!resp.ok) throw new Error(`list sessions failed: ${resp.status}`);
    return resp.json();
}

export async function getSession(sessionId) {
    const resp = await _fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
    if (resp.status === 404) return null;
    if (!resp.ok) throw new Error(`get session failed: ${resp.status}`);
    return resp.json();
}

export async function uploadDataset(formData) {
    // formData is a FormData object — do NOT set Content-Type header (browser sets multipart boundary)
    const resp = await _fetch('/api/upload', {
        method: 'POST',
        body: formData,
    });
    if (!resp.ok) throw new Error(`upload failed: ${resp.status}`);
    return resp.json();
}

export function exportCsv(datasetId) {
    // Use anchor-click pattern for browser-native file download (RESEARCH.md Pitfall 5).
    // Session cookie is sent automatically on navigation — do NOT use fetch() here.
    const url = `/api/export/csv?dataset_id=${encodeURIComponent(datasetId)}`;
    const a = document.createElement('a');
    a.href = url;
    a.download = '';  // filename comes from Content-Disposition header
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}
