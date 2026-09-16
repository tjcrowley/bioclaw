// citations.js — Citation rendering for agent answers (UI-03)
// AskResponse.citations is a list of [tool_name, sha_prefix, record_or_null] 3-tuples.
// (qa/citations.py::verify_answer_citations returns (tool_name, sha_prefix, record_or_None))

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
        if (!Array.isArray(entry) || entry.length < 2) continue;
        // entry = [tool_name, sha_prefix, record_or_null]
        const toolName = entry[0];
        const sha = entry[1];
        const record = entry[2] ?? null;
        map.set(sha, { toolName, record });
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

    // citations is [[tool_name, sha_prefix, record_or_null], ...] — search by sha_prefix (entry[1])
    const found = (citations || []).find(
        (entry) => Array.isArray(entry) && entry.length >= 2 && entry[1] === sha
    );

    if (!found || found[2] == null) {
        citationDetail.textContent = `Citation [${sha}] not found in audit log for this response.`;
    } else {
        const header = `# ${found[0]}  sha:${found[1]}\n\n`;
        citationDetail.textContent = header + JSON.stringify(found[2], null, 2);
    }
    citationModal.hidden = false;
}

// Delegated click handler — read citations from the containing bubble (not a global)
// so that old messages stay correct after new messages arrive.
const _chatThread = document.getElementById('chat-thread');
if (!_chatThread) {
    console.error('[citations] #chat-thread not found — click handler not registered');
} else {
    _chatThread.addEventListener('click', (e) => {
        const btn = e.target.closest('.citation-ref');
        if (!btn) return;
        console.log('[citations] click on sha:', btn.dataset.sha);
        const sha = btn.dataset.sha;
        const bubble = btn.closest('.message-bubble');
        const cits = (bubble && bubble._bioclawCitations) || window.__lastCitations || [];
        console.log('[citations] cits length:', cits.length, 'bubble has prop:', !!(bubble && bubble._bioclawCitations));
        try {
            showCitationDetail(sha, cits);
        } catch (err) {
            console.error('[citations] showCitationDetail threw:', err);
        }
    });
}
