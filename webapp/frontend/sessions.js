// sessions.js — Session sidebar component (UI-04)
// Lists past sessions from GET /api/sessions; handles session resume.

import { listSessions, getSession } from './api.js';
import { clearChatThread, appendMessage } from './chat.js';

const sessionList = document.getElementById('session-list');

function _shortLabel(session) {
    const shortId = session.session_id.slice(0, 8);
    const dataset = session.recent_datasets && session.recent_datasets.length > 0
        ? session.recent_datasets[0]
        : null;
    return dataset ? `${shortId} · ${dataset}` : shortId;
}

function _clearActive() {
    sessionList.querySelectorAll('.session-item.active').forEach(el => el.classList.remove('active'));
}

function _createSessionItem(session) {
    const li = document.createElement('li');
    li.className = 'session-item';
    li.dataset.sessionId = session.session_id;
    li.textContent = _shortLabel(session);
    li.title = session.session_id;
    li.addEventListener('click', () => resumeSession(session.session_id));
    return li;
}

export async function loadSessionList() {
    try {
        const { sessions } = await listSessions();
        sessionList.innerHTML = '';
        for (const session of sessions) {
            sessionList.appendChild(_createSessionItem(session));
        }
        // Mark active if a session is already open
        if (window.__currentSessionId) {
            const active = sessionList.querySelector(
                `[data-session-id="${CSS.escape(window.__currentSessionId)}"]`
            );
            if (active) active.classList.add('active');
        }
    } catch {
        // 401 handled by api.js → bioclaw:unauthorized event
    }
}

export function resumeSession(sessionId) {
    window.__currentSessionId = sessionId;
    _clearActive();
    const item = sessionList.querySelector(`[data-session-id="${CSS.escape(sessionId)}"]`);
    if (item) item.classList.add('active');

    clearChatThread();

    // Replay full message history (HIST-01); fall back to dataset hint for pre-HIST-01 sessions
    getSession(sessionId).then((summary) => {
        if (!summary) return;
        const msgs = summary.messages || [];
        if (msgs.length === 0) {
            // No stored turns yet: fall back to dataset context hint
            const datasets = summary.recent_datasets || [];
            const ctx = datasets.length > 0
                ? `Resuming session — last used: ${datasets.join(', ')}`
                : `Resuming session ${sessionId.slice(0, 8)}…`;
            appendMessage({ role: 'system', content: ctx });
        } else {
            for (const msg of msgs) {
                appendMessage({ role: msg.role, content: msg.content, citations: msg.citations || undefined });
                // Render tool activity inline after assistant bubbles that had tool calls
                if (msg.role === 'assistant' && Array.isArray(msg.tool_events) && msg.tool_events.length > 0) {
                    const toolNames = msg.tool_events.map(e => e.tool_name.replace(/^mcp__bioclaw__/, '')).join(', ');
                    appendMessage({ role: 'system', content: `[Tools used: ${toolNames}]` });
                }
            }
        }
    }).catch(() => {});
}

export function addOrRefreshSession(sessionId) {
    const existing = sessionList.querySelector(`[data-session-id="${CSS.escape(sessionId)}"]`);
    if (existing) {
        _clearActive();
        existing.classList.add('active');
        // Move to top
        sessionList.prepend(existing);
    } else {
        _clearActive();
        const li = _createSessionItem({ session_id: sessionId, recent_datasets: [] });
        li.classList.add('active');
        sessionList.prepend(li);
    }
    window.__currentSessionId = sessionId;
}
