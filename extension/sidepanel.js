// ═══════════════════════════════════════════════════════════
// Configuration
// ═══════════════════════════════════════════════════════════

const API_BASE = 'http://127.0.0.1:5000';
const MAX_FOLLOW_UPS = 3;
const STORAGE_KEY = 'summarizer_state';

// ═══════════════════════════════════════════════════════════
// State
// ═══════════════════════════════════════════════════════════

let state = {
    currentAction: null, // 'page', 'url', 'youtube', 'text'
    length: 'M',
    fontSize: 16,
    followUpCount: 0,
    summary: null,
    heading: null,
    context: null,
    followUps: []
};

// ═══════════════════════════════════════════════════════════
// DOM Elements
// ═══════════════════════════════════════════════════════════

const elements = {
    // Actions
    btnPage: document.getElementById('btnPage'),
    btnUrl: document.getElementById('btnUrl'),
    btnYoutube: document.getElementById('btnYoutube'),
    btnText: document.getElementById('btnText'),

    // Controls
    clearBtn: document.getElementById('clearBtn'),
    exportBtn: document.getElementById('exportBtn'),
    fontDecrease: document.getElementById('fontDecrease'),
    fontIncrease: document.getElementById('fontIncrease'),

    // Content
    contentArea: document.getElementById('contentArea'),
    emptyState: document.getElementById('emptyState'),
    summarySection: document.getElementById('summarySection'),
    summaryHeading: document.getElementById('summaryHeading'),
    summaryMeta: document.getElementById('summaryMeta'),
    summaryBody: document.getElementById('summaryBody'),
    followupSection: document.getElementById('followupSection'),
    loadingIndicator: document.getElementById('loadingIndicator'),

    // Input
    userInput: document.getElementById('userInput'),
    sendBtn: document.getElementById('sendBtn'),
    followUpCounter: document.getElementById('followUpCounter'),
    jumpBtn: document.getElementById('jumpBtn'),

    // URL Modal
    urlOverlay: document.getElementById('urlOverlay'),
    urlInput: document.getElementById('urlInput'),
    urlCancel: document.getElementById('urlCancel'),
    urlSubmit: document.getElementById('urlSubmit')
};

// ═══════════════════════════════════════════════════════════
// Persistence
// ═══════════════════════════════════════════════════════════

async function saveState() {
    await chrome.storage.local.set({ [STORAGE_KEY]: state });
}

async function loadState() {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    if (result[STORAGE_KEY]) {
        state = { ...state, ...result[STORAGE_KEY] };
        restoreUI();
    }
}

function restoreUI() {
    // Restore length selection
    document.querySelectorAll('[data-length]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.length === state.length);
    });

    // Restore font size
    elements.summaryBody.style.fontSize = state.fontSize + 'px';

    // Restore summary if exists
    if (state.summary) {
        showSummary(state.heading, state.summary, false);

        // Restore follow-ups
        state.followUps.forEach(fu => {
            addFollowUpToUI(fu.question, fu.answer);
        });

        updateFollowUpCounter();
    }
}

// ═══════════════════════════════════════════════════════════
// UI Helpers
// ═══════════════════════════════════════════════════════════

function setActiveAction(action) {
    state.currentAction = action;
    document.querySelectorAll('.action-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.action === action);
    });
}

function showLoading(show) {
    elements.loadingIndicator.classList.toggle('visible', show);
    elements.emptyState.style.display = 'none';
    elements.sendBtn.disabled = show;
    elements.userInput.disabled = show;
}

function showSummary(heading, body, save = true) {
    elements.emptyState.style.display = 'none';
    elements.summarySection.classList.add('visible');

    elements.summaryHeading.textContent = heading;
    elements.summaryBody.innerHTML = formatSummaryBody(body);
    elements.summaryBody.style.fontSize = state.fontSize + 'px';

    // Reset follow-ups for new summary
    if (save) {
        state.heading = heading;
        state.summary = body;
        state.context = body;
        state.followUpCount = 0;
        state.followUps = [];
        elements.followupSection.innerHTML = '';
        saveState();
    }

    updateFollowUpCounter();
    scrollToBottom();
}

function formatSummaryBody(text) {
    // Convert markdown-style formatting
    let html = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    return '<p>' + html + '</p>';
}

function addFollowUpToUI(question, answer) {
    const item = document.createElement('div');
    item.className = 'followup-item';
    item.innerHTML = `
        <div class="followup-question">${escapeHtml(question)}</div>
        <div class="followup-answer">${formatSummaryBody(answer)}</div>
    `;
    elements.followupSection.appendChild(item);
    scrollToBottom();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function updateFollowUpCounter() {
    const remaining = MAX_FOLLOW_UPS - state.followUpCount;

    if (!state.summary) {
        elements.followUpCounter.textContent = '';
        elements.followUpCounter.className = 'followup-counter';
        elements.userInput.disabled = true;
        elements.userInput.placeholder = 'Summarize something first...';
        return;
    }

    elements.userInput.disabled = false;
    elements.userInput.placeholder = 'Ask about this summary...';

    if (remaining > 0) {
        elements.followUpCounter.textContent = `${remaining} question${remaining !== 1 ? 's' : ''} remaining`;
        elements.followUpCounter.className = remaining === 1 ? 'followup-counter warning' : 'followup-counter';
    } else {
        elements.followUpCounter.textContent = 'Question limit reached for this summary';
        elements.followUpCounter.className = 'followup-counter limit';
        elements.userInput.disabled = true;
        elements.userInput.placeholder = 'Limit reached. Start a new summary.';
    }
}

function scrollToBottom() {
    setTimeout(() => {
        elements.contentArea.scrollTop = elements.contentArea.scrollHeight;
    }, 100);
}

function clearAll() {
    state = {
        currentAction: null,
        length: 'M',
        fontSize: 16,
        followUpCount: 0,
        summary: null,
        heading: null,
        context: null,
        followUps: []
    };

    elements.summarySection.classList.remove('visible');
    elements.emptyState.style.display = 'flex';
    elements.followupSection.innerHTML = '';
    elements.summaryHeading.textContent = '';
    elements.summaryBody.innerHTML = '';

    document.querySelectorAll('.action-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('[data-length]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.length === 'M');
    });

    updateFollowUpCounter();
    saveState();
}

// ═══════════════════════════════════════════════════════════
// API Calls
// ═══════════════════════════════════════════════════════════

async function getCurrentUrl() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0]?.url || '';
}

async function getCurrentPageTitle() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0]?.title || 'Current Page';
}

async function callAPI(endpoint, payload) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...payload, length: state.length })
    });

    if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || `HTTP ${res.status}`);
    }

    return await res.json();
}

async function summarizePage() {
    setActiveAction('page');
    showLoading(true);

    try {
        const url = await getCurrentUrl();
        const title = await getCurrentPageTitle();

        if (!url) throw new Error('Could not get current page URL');

        const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
        const endpoint = isYouTube ? '/summarize-youtube' : '/summarize-url';

        const data = await callAPI(endpoint, { url });

        showLoading(false);
        showSummary(data.heading || title, data.summary);

    } catch (error) {
        showLoading(false);
        showError(error.message);
    }
}

async function summarizeUrl(url) {
    setActiveAction('url');
    showLoading(true);

    try {
        const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
        const endpoint = isYouTube ? '/summarize-youtube' : '/summarize-url';

        const data = await callAPI(endpoint, { url });

        showLoading(false);
        showSummary(data.heading || 'Summary', data.summary);

    } catch (error) {
        showLoading(false);
        showError(error.message);
    }
}

async function summarizeYouTube() {
    setActiveAction('youtube');

    const url = await getCurrentUrl();
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        showError('Please navigate to a YouTube video first');
        return;
    }

    showLoading(true);

    try {
        const title = await getCurrentPageTitle();
        const data = await callAPI('/summarize-youtube', { url });

        showLoading(false);
        showSummary(data.heading || title, data.summary);

    } catch (error) {
        showLoading(false);
        showError(error.message);
    }
}

async function summarizeText(text) {
    setActiveAction('text');
    showLoading(true);

    try {
        const data = await callAPI('/summarize', { text });

        showLoading(false);
        showSummary(data.heading || 'Custom Text Summary', data.summary);

    } catch (error) {
        showLoading(false);
        showError(error.message);
    }
}

async function askFollowUp(question) {
    if (state.followUpCount >= MAX_FOLLOW_UPS) {
        showError('Follow-up limit reached');
        return;
    }

    if (!state.context) {
        showError('Please summarize something first');
        return;
    }

    showLoading(true);

    try {
        const history = state.followUps.map(fu => [
            { role: 'user', content: fu.question },
            { role: 'assistant', content: fu.answer }
        ]).flat();

        const data = await callAPI('/follow-up', {
            question,
            context: state.context,
            history
        });

        showLoading(false);

        state.followUpCount++;
        state.followUps.push({ question, answer: data.answer });

        addFollowUpToUI(question, data.answer);
        updateFollowUpCounter();
        saveState();

    } catch (error) {
        showLoading(false);
        showError(error.message);
    }
}

function showError(message) {
    elements.emptyState.style.display = 'none';
    elements.summarySection.classList.add('visible');
    elements.summaryHeading.textContent = 'Error';
    elements.summaryBody.innerHTML = `<p style="color: #c92a2a;">${escapeHtml(message)}</p>`;
}

// ═══════════════════════════════════════════════════════════
// Event Handlers
// ═══════════════════════════════════════════════════════════

// Action buttons
elements.btnPage.addEventListener('click', summarizePage);

elements.btnUrl.addEventListener('click', () => {
    elements.urlOverlay.classList.add('visible');
    elements.urlInput.focus();
});

elements.btnYoutube.addEventListener('click', summarizeYouTube);

elements.btnText.addEventListener('click', () => {
    setActiveAction('text');
    elements.userInput.placeholder = 'Paste text to summarize...';
    elements.userInput.disabled = false;
    elements.userInput.focus();
});

// URL Modal
elements.urlCancel.addEventListener('click', () => {
    elements.urlOverlay.classList.remove('visible');
    elements.urlInput.value = '';
});

elements.urlSubmit.addEventListener('click', () => {
    const url = elements.urlInput.value.trim();
    if (url) {
        elements.urlOverlay.classList.remove('visible');
        elements.urlInput.value = '';
        summarizeUrl(url);
    }
});

elements.urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        elements.urlSubmit.click();
    } else if (e.key === 'Escape') {
        elements.urlCancel.click();
    }
});

// Length selector
document.querySelectorAll('[data-length]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('[data-length]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.length = btn.dataset.length;
        saveState();
    });
});

// Font size controls
elements.fontDecrease.addEventListener('click', () => {
    if (state.fontSize > 12) {
        state.fontSize -= 2;
        elements.summaryBody.style.fontSize = state.fontSize + 'px';
        saveState();
    }
});

elements.fontIncrease.addEventListener('click', () => {
    if (state.fontSize < 24) {
        state.fontSize += 2;
        elements.summaryBody.style.fontSize = state.fontSize + 'px';
        saveState();
    }
});

// Send button
elements.sendBtn.addEventListener('click', async () => {
    const input = elements.userInput.value.trim();
    if (!input) return;

    elements.userInput.value = '';

    // If no summary yet and text action selected, summarize the text
    if (!state.summary && state.currentAction === 'text') {
        await summarizeText(input);
    } else if (!state.summary) {
        // Treat as text to summarize
        await summarizeText(input);
    } else {
        // Treat as follow-up question
        await askFollowUp(input);
    }
});

elements.userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        elements.sendBtn.click();
    }
});

// Auto-resize textarea
elements.userInput.addEventListener('input', () => {
    elements.userInput.style.height = '44px';
    elements.userInput.style.height = Math.min(120, elements.userInput.scrollHeight) + 'px';
});

// Clear button
elements.clearBtn.addEventListener('click', () => {
    if (confirm('Clear everything and start fresh?')) {
        clearAll();
    }
});

// Export button
elements.exportBtn.addEventListener('click', () => {
    const exportData = {
        timestamp: new Date().toISOString(),
        heading: state.heading,
        summary: state.summary,
        followUps: state.followUps
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

// Jump to latest button
elements.contentArea.addEventListener('scroll', () => {
    const { scrollTop, scrollHeight, clientHeight } = elements.contentArea;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    elements.jumpBtn.classList.toggle('visible', !isNearBottom && state.summary);
});

elements.jumpBtn.addEventListener('click', scrollToBottom);

// ═══════════════════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════════════════

loadState();
updateFollowUpCounter();
