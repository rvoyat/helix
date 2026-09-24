const TOKEN_KEY = 'helix_token';
const USER_KEY  = 'helix_user';
const API_BASE  = 'http://localhost:8092';

function getToken() { return localStorage.getItem(TOKEN_KEY); }

function getUser() {
    const u = localStorage.getItem(USER_KEY);
    return u ? JSON.parse(u) : null;
}

function authHeaders() {
    const t = getToken();
    return t ? { 'Authorization': `Bearer ${t}` } : {};
}

async function checkAuth(requireAdmin = false) {
    const token = getToken();
    if (!token) { redirectLogin(); return null; }
    try {
        const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
        if (!res.ok) { redirectLogin(); return null; }
        const user = await res.json();
        localStorage.setItem(USER_KEY, JSON.stringify(user));
        if (requireAdmin && user.role !== 'admin') {
            alert('Accesso riservato agli amministratori.');
            window.location.href = 'index.html';
            return null;
        }
        return user;
    } catch { redirectLogin(); return null; }
}

function redirectLogin() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = 'login.html';
}

async function helixLogout() {
    try {
        await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: authHeaders() });
    } catch {}
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    window.location.href = 'login.html';
}
