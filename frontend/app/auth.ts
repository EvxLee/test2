const keycloakAuthUrl = import.meta.env.VITE_KEYCLOAK_AUTH_URL;
const clientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID
const redirectUri = import.meta.env.VITE_ATLAS_FRONTEND_URL
const postLogoutRedirectUri  = redirectUri + "/logout"


function base64UrlEncode(str) {
  return btoa(String.fromCharCode.apply(null, new Uint8Array(str)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function generateCodeChallenge(verifier) {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return base64UrlEncode(digest);
}

export async function login() {
  const verifier = base64UrlEncode(crypto.getRandomValues(new Uint8Array(32)));
  const challenge = await generateCodeChallenge(verifier);
  localStorage.setItem("pkce_verifier", verifier);

  const authUrl = `${keycloakAuthUrl}/auth?client_id=${clientId}` +
    `&redirect_uri=${encodeURIComponent(redirectUri)}` +
    `&response_type=code` +
    `&scope=openid profile email` +
    `&code_challenge=${challenge}` +
    `&code_challenge_method=S256`;

  window.location.href = authUrl;
}
export async function handleRedirectCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (!code) return;

  const verifier = localStorage.getItem("pkce_verifier");

  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    code,
    redirect_uri: redirectUri,
    code_verifier: verifier
  });

  const res = await fetch(`${keycloakAuthUrl}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });

  const tokens = await res.json();
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("id_token", tokens.id_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);
  localStorage.removeItem("pkce_verifier");
  window.history.replaceState({}, document.title, "/");
}

export async function refreshTokens() {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;

  const body = new URLSearchParams({
    grant_type: "refresh_token",
    client_id: clientId,
    refresh_token: refreshToken
  });

  const res = await fetch(`${keycloakAuthUrl}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });

  if (!res.ok) return false;

  const tokens = await res.json();
  localStorage.setItem("access_token", tokens.access_token);
  localStorage.setItem("id_token", tokens.id_token);
  localStorage.setItem("refresh_token", tokens.refresh_token);

  return true;
}

export function isLoggedIn(): boolean {
  const token = localStorage.getItem("access_token");
  if (!token) return false;

  try {
    const [, payloadBase64] = token.split(".");
    const payload = JSON.parse(atob(payloadBase64));
    const now = Math.floor(Date.now() / 1000);
    if (payload.exp > now) return true;
    return refreshTokens()
  } catch {
    return false;
  }
}

export function hasPartnerRole(): boolean {
  try {
    const token = localStorage.getItem("access_token");
    if (!token) return false;
    const [, payloadBase64] = token.split(".");
    const payload = JSON.parse(atob(payloadBase64));
    const roles: string[] = payload?.realm_access?.roles ?? [];
    return roles.includes("external-partner");
  } catch {
    return false;
  }
}

export function logout() {
  const logoutUrl = `${keycloakAuthUrl}/logout?client_id=${clientId}` +
    `&post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUri)}`;
  localStorage.clear();
  window.location.href = logoutUrl;
}

