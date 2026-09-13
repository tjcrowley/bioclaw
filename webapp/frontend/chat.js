// chat.js — Chat thread + live activity view (UI-01, UI-02)
// Imports api.js for askQuestion/openToolStream.
// Citation rendering hook: window.__renderAnswerWithCitations (set by citations.js, Plan 09-04).
// Session ID hook: window.__onNewSessionId (set by sessions.js, Plan 09-04).
// Upload hook: window.__onFilesSelected (set by sessions.js, Plan 09-04).

import { askQuestion, openToolStream } from './api.js';

const chatThread   = document.getElementById('chat-thread');
const activityView = document.getElementById('activity-view');
const composerForm = document.getElementById('composer-form');
const questionInput = document.getElementById('question-input');
const sendBtn      = document.getElementById('send-btn');
const fileInput    = document.getElementById('file-input');

function _scrollToBottom(el) {
    el.scrollTop = el.scrollHeight;
}

function _argsSummary(toolInput) {
    if (!toolInput || typeof toolInput !== 'object') return '';
    const keys = Object.keys(toolInput);
    if (!keys.length) return '';
    const first = keys[0];
    const val = String(toolInput[first]);
    const preview = val.length > 40 ? val.slice(0, 40) + '…' : val;
    return `${first}=${preview}`;
}

export function appendMessage({ role, content, citations }) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';

    if (role === 'assistant' && typeof window.__renderAnswerWithCitations === 'function') {
        bubble.innerHTML = window.__renderAnswerWithCitations(content, citations);
    } else {
        bubble.textContent = content;
    }

    div.appendChild(bubble);
    chatThread.appendChild(div);
    _scrollToBottom(chatThread);
    return div;
}

export function renderActivityEvent(event) {
    const div = document.createElement('div');
    div.className = `activity-event${event.is_error ? ' error' : ''}`;

    const namePart = document.createElement('span');
    namePart.className = 'tool-name';
    namePart.textContent = event.tool_name || 'unknown';

    const argsPart = document.createElement('span');
    argsPart.className = 'tool-args';
    argsPart.textContent = _argsSummary(event.tool_input);

    div.appendChild(namePart);
    if (argsPart.textContent) div.appendChild(document.createTextNode(' '));
    div.appendChild(argsPart);

    activityView.appendChild(div);
    _scrollToBottom(activityView);
}

export function openActivityView() {
    activityView.innerHTML = '';
    activityView.hidden = false;
}

export function closeActivityView() {
    activityView.hidden = true;
}

export function clearChatThread() {
    chatThread.innerHTML = '';
    closeActivityView();
}

export async function sendMessage(question, sessionId) {
    if (!question.trim()) return null;

    const streamId = (typeof crypto !== 'undefined' && crypto.randomUUID)
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2);

    // 1. Open WS BEFORE the POST so no early tool events are lost (09-RESEARCH.md Pitfall 1)
    const stream = openToolStream(streamId, {
        onEvent: renderActivityEvent,
        onClose: closeActivityView,
    });

    // 2. User bubble + activity view
    appendMessage({ role: 'user', content: question });
    openActivityView();
    sendBtn.disabled = true;
    questionInput.value = '';

    let newSessionId = sessionId;
    try {
        const resp = await askQuestion(question, sessionId, streamId);
        newSessionId = resp.session_id;
        appendMessage({ role: 'assistant', content: resp.answer, citations: resp.citations });
    } catch (err) {
        if (err.message !== 'unauthorized') {
            appendMessage({ role: 'system', content: `Error: ${err.message}` });
        }
    } finally {
        stream.close();
        closeActivityView();
        sendBtn.disabled = false;
    }

    return newSessionId;
}

// ─── Composer wiring ─────────────────────────────────────────────────────────

composerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const question = questionInput.value.trim();
    if (!question) return;
    const newSessionId = await sendMessage(question, window.__currentSessionId || null);
    if (newSessionId && typeof window.__onNewSessionId === 'function') {
        window.__onNewSessionId(newSessionId);
    }
});

fileInput.addEventListener('change', () => {
    const files = fileInput.files;
    if (!files || !files.length) return;
    const name = files[0].name.replace(/\.[^.]+$/, '');
    if (typeof window.__onFilesSelected === 'function') {
        window.__onFilesSelected(files, name);
    }
    fileInput.value = ''; // reset so same file can be re-selected
});

// ─── Drag-and-drop on the entire main panel ───────────────────────────────────

const mainPanel = document.getElementById('main-panel');
mainPanel.addEventListener('dragover', (e) => {
    e.preventDefault();
    mainPanel.style.outline = `2px dashed var(--accent-primary)`;
});
mainPanel.addEventListener('dragleave', () => {
    mainPanel.style.outline = '';
});
mainPanel.addEventListener('drop', (e) => {
    e.preventDefault();
    mainPanel.style.outline = '';
    const files = e.dataTransfer?.files;
    if (!files || !files.length) return;
    const name = files[0].name.replace(/\.[^.]+$/, '');
    if (typeof window.__onFilesSelected === 'function') {
        window.__onFilesSelected(files, name);
    }
});

// ─── Session-expired handler ──────────────────────────────────────────────────

window.addEventListener('bioclaw:unauthorized', () => {
    appendMessage({ role: 'system', content: 'Session expired — please refresh to log in again.' });
});
