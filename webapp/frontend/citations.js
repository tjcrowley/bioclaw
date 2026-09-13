// citations.js — Citation rendering for agent answers (UI-03)
// AskResponse.citations is a list of [tag_string, record_or_null] pairs.
// tag_string format: "[ref:TOOL_NAME:SHA_PREFIX_12]"

const CITATION_RE = /\[ref:([^:[\]]+):([a-f0-9]{12})\]/g;

function _escapeHtml(str) {
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function _buildCitationMap(citations) {
    const map = new Map();
    for (const entry of (citations || [])) {
        if (!Array.isArray(entry) || entry.length < 1) continue;
        const tag = entry[0];
        const record = entry[1] ?? null;
        const match = CITATION_RE.exec(tag);
        CITATION_RE.lastIndex = 0;
        if (match) map.set(match[2], { tag, record, toolName: match[1] });
    }
    return map;
}

export function renderAnswerWithCitations(answerText, citations) {
    const citationMap = _buildCitationMap(citations);
    // Store on window so delegated click handler can look up citations later
    window.__lastCitations = citations;

    let result = '';
    let lastIndex = 0;
    CITATION_RE.lastIndex = 0;

    let match;
    while ((match = CITATION_RE.exec(answerText)) !== null) {
        // Escape the text segment before this citation
        result += _escapeHtml(answerText.slice(lastIndex, match.index));
        const toolName = match[1];
        const sha = match[2];
        const hasRecord = citationMap.has(sha) && citationMap.get(sha).record !== null;
        result += `<button class="citation-ref${hasRecord ? '' : ' unresolved'}" ` +
                  `data-sha="${_escapeHtml(sha)}" data-tool="${_escapeHtml(toolName)}" ` +
                  `title="${_escapeHtml(toolName)}">[${_escapeHtml(toolName)}]</button>`;
        lastIndex = CITATION_RE.lastIndex;
    }
    result += _escapeHtml(answerText.slice(lastIndex));
    return result;
}

export function showCitationDetail(sha, citations) {
    const citationModal = document.getElementById('citation-modal');
    const citationDetail = document.getElementById('citation-detail');

    const found = (citations || []).find(
        (entry) => Array.isArray(entry) && typeof entry[0] === 'string' && entry[0].includes(sha)
    );

    if (!found || found[1] == null) {
        citationDetail.textContent = `Citation [${sha}] not found in audit log for this response.`;
    } else {
        citationDetail.textContent = JSON.stringify(found[1], null, 2);
    }
    citationModal.hidden = false;
}

// Delegated click handler for citation buttons rendered in the chat thread
document.getElementById('chat-thread').addEventListener('click', (e) => {
    const btn = e.target.closest('.citation-ref');
    if (!btn) return;
    const sha = btn.dataset.sha;
    showCitationDetail(sha, window.__lastCitations || []);
});
