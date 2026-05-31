import { createMakersHubApiClient } from "@makershub/api-client";

export * from "@makershub/api-client";

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

const apiClient = createMakersHubApiClient({ baseUrl: apiBaseUrl });

export const {
  claimWorkbenchTask,
  createWorkbenchTask,
  firstLogin,
  getMe,
  getMyMemberProfile,
  getMyPermissions,
  getMyPointAccount,
  getMyPointLedger,
  listPointRules,
  listWorkbenchTasks,
  logout,
  passwordLogin,
  refreshToken,
  reviewWorkbenchTask,
  sendEmailCode,
  setPassword,
  submitWorkbenchTask,
  updateMyMemberProfile,
} = apiClient;
