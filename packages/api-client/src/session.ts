import type { AuthTokenData } from "./types";

export interface StoredAuth extends AuthTokenData {
  password_required?: boolean;
}

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface AuthStorage {
  loadStoredAuth(): StoredAuth | null;
  saveStoredAuth(auth: StoredAuth): void;
  clearStoredAuth(): void;
}

export function createAuthStorage(storage: KeyValueStorage, storageKey: string): AuthStorage {
  return {
    loadStoredAuth() {
      const raw = storage.getItem(storageKey);
      if (!raw) return null;

      try {
        return JSON.parse(raw) as StoredAuth;
      } catch {
        storage.removeItem(storageKey);
        return null;
      }
    },
    saveStoredAuth(auth) {
      storage.setItem(storageKey, JSON.stringify(auth));
    },
    clearStoredAuth() {
      storage.removeItem(storageKey);
    },
  };
}

export function isExpired(expiresAt: string | undefined, skewMs = 30 * 1000): boolean {
  if (!expiresAt) return true;
  const expiresTime = new Date(expiresAt).getTime();
  if (!expiresTime) return true;
  return Date.now() >= expiresTime - skewMs;
}
