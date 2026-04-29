import type { AuthTokenData } from "./api";

const AUTH_STORAGE_KEY = "makershub.web.auth";

export interface StoredAuth extends AuthTokenData {
  password_required?: boolean;
}

export function loadStoredAuth(): StoredAuth | null {
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) return null;

  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    clearStoredAuth();
    return null;
  }
}

export function saveStoredAuth(auth: StoredAuth): void {
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
}

export function clearStoredAuth(): void {
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
}

export function isExpired(expiresAt: string | undefined): boolean {
  if (!expiresAt) return true;
  const expiresTime = new Date(expiresAt).getTime();
  if (!expiresTime) return true;
  return Date.now() >= expiresTime - 30 * 1000;
}
