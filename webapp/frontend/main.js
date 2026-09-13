// main.js — entry point: auth check, login flow, session bootstrap
// Imports are added in later plans (api.js, chat.js, sessions.js, citations.js don't exist yet)

const loginOverlay = document.getElementById('login-overlay');
const appShell     = document.getElementById('app');
const loginForm    = document.getElementById('login-form');
const passwordInput = document.getElementById('password-input');
const loginError   = document.getElementById('login-error');

async function checkAuth() {
    try {
        const resp = await fetch('/api/sessions', { credentials: 'include' });
        if (resp.ok) {
            showApp();
        } else {
            showLogin();
        }
    } catch {
        showLogin();
    }
}

function showLogin() {
    loginOverlay.hidden = false;
    appShell.hidden = true;
    passwordInput.focus();
}

function showApp() {
    loginOverlay.hidden = true;
    appShell.hidden = false;
    // Chat bootstrap will be called here once chat.js and sessions.js are imported
    if (typeof window.__bootApp === 'function') window.__bootApp();
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
            // Cookie is now set; reload to re-check auth
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

document.getElementById('modal-backdrop').addEventListener('click', () => {
    document.getElementById('citation-modal').hidden = true;
});
document.getElementById('modal-close-btn').addEventListener('click', () => {
    document.getElementById('citation-modal').hidden = true;
});
document.getElementById('new-session-btn').addEventListener('click', () => {
    if (typeof window.__newSession === 'function') window.__newSession();
});

// Boot
checkAuth();
