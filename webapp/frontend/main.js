// main.js — Entry point: auth check, login flow, and module wiring.
// Imports all other modules and sets up the window.* hook protocol.

import { renderAnswerWithCitations, showCitationDetail } from './citations.js';
import { clearChatThread, appendMessage } from './chat.js';
import { loadSessionList, resumeSession, addOrRefreshSession } from './sessions.js';
import { uploadDataset, exportCsv, exportScript, getSession } from './api.js';

// ─── Window hooks (read by chat.js, citations.js, sessions.js) ───────────────
window.__renderAnswerWithCitations = renderAnswerWithCitations;

// Track currently active dataset for export button
window.__currentDatasetId = null;

function _showDownloadBtn() {
    document.getElementById('download-btn').removeAttribute('hidden');
    document.getElementById('export-script-btn').removeAttribute('hidden');
}
function _hideDownloadBtn() {
    document.getElementById('download-btn').setAttribute('hidden', '');
    document.getElementById('export-script-btn').setAttribute('hidden', '');
}

window.__onNewSessionId = (sessionId) => {
    addOrRefreshSession(sessionId);
};

window.__newSession = () => {
    window.__currentSessionId = null;
    window.__currentDatasetId = null;
    _hideDownloadBtn();
    clearChatThread();
    loadSessionList().catch(() => {});
    document.getElementById('question-input').focus();
};

window.__onFilesSelected = async (files, name) => {
    const formData = new FormData();
    formData.append('name', name || 'upload');
    for (const f of files) formData.append('files', f);

    appendMessage({ role: 'system', content: `Uploading "${name || files[0]?.name}"…` });
    try {
        const result = await uploadDataset(formData);
        if (result.status === 'success') {
            // Attach upload result to current session
            if (result.session_id) {
                window.__currentSessionId = result.session_id;
                addOrRefreshSession(result.session_id);
            }
            // Track dataset for export button
            if (result.dataset_id) {
                window.__currentDatasetId = result.dataset_id;
                _showDownloadBtn();
            }
            appendMessage({
                role: 'system',
                content: `Dataset "${name}" ingested as ${result.dataset_id}. ` +
                         `You can now ask questions about it.`,
            });
        } else {
            appendMessage({ role: 'system', content: `Upload failed: ${result.detail || 'unknown error'}` });
        }
    } catch {
        appendMessage({ role: 'system', content: 'Upload failed — see console for details.' });
    }
};

window.__bootApp = async () => {
    await loadSessionList();
    document.getElementById('question-input').focus();
};

// After a successful ask response, refresh the session's recent_datasets to pick
// up any dataset set during the conversation (e.g., analysis run on an uploaded file).
window.__onAskResponse = async (sessionId) => {
    if (!sessionId) return;
    try {
        const session = await getSession(sessionId);
        if (session && session.recent_datasets && session.recent_datasets.length > 0) {
            window.__currentDatasetId = session.recent_datasets[0];
            _showDownloadBtn();
        }
    } catch {
        // best-effort — don't surface errors from a secondary call
    }
};

// ─── Auth flow ────────────────────────────────────────────────────────────────
const loginOverlay  = document.getElementById('login-overlay');
const appShell      = document.getElementById('app');
const loginForm     = document.getElementById('login-form');
const passwordInput = document.getElementById('password-input');
const loginError    = document.getElementById('login-error');

function showLogin() {
    loginOverlay.hidden = false;
    appShell.hidden = true;
    passwordInput.focus();
}

function showApp() {
    loginOverlay.hidden = true;
    appShell.hidden = false;
    if (typeof window.__bootApp === 'function') window.__bootApp();
}

async function checkAuth() {
    try {
        const resp = await fetch('/api/sessions', { credentials: 'include' });
        resp.ok ? showApp() : showLogin();
    } catch {
        showLogin();
    }
}

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginError.hidden = true;
    const password = passwordInput.value;
    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ password }),
        });
        if (resp.ok) {
            location.reload();
        } else {
            loginError.hidden = false;
            passwordInput.value = '';
            passwordInput.focus();
        }
    } catch {
        loginError.hidden = false;
    }
});

window.addEventListener('bioclaw:unauthorized', showLogin);

// ─── Download button wiring ───────────────────────────────────────────────────
document.getElementById('download-btn').addEventListener('click', () => {
    if (window.__currentDatasetId) {
        exportCsv(window.__currentDatasetId);
    }
});
document.getElementById('export-script-btn').addEventListener('click', () => {
    if (window.__currentDatasetId) {
        exportScript(window.__currentDatasetId);
    }
});

// ─── Modal wiring ─────────────────────────────────────────────────────────────
document.getElementById('modal-backdrop').addEventListener('click', () => {
    document.getElementById('citation-modal').hidden = true;
});
document.getElementById('modal-close-btn').addEventListener('click', () => {
    document.getElementById('citation-modal').hidden = true;
});
document.getElementById('new-session-btn').addEventListener('click', () => {
    if (typeof window.__newSession === 'function') window.__newSession();
});

// ─── Boot ─────────────────────────────────────────────────────────────────────
checkAuth();
