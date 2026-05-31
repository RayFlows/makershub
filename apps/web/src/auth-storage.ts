import { createAuthStorage, isExpired } from "@makershub/api-client";

export { isExpired };
export type { StoredAuth } from "@makershub/api-client";

const authStorage = createAuthStorage(window.localStorage, "makershub.web.auth");

export const { clearStoredAuth, loadStoredAuth, saveStoredAuth } = authStorage;
