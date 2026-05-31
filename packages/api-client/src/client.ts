import { createApiRequester, type ApiRequestOptions, type ApiTransport } from "./http";
import type {
  AuthTokenData,
  CreateWorkbenchTaskPayload,
  CurrentUserPermissions,
  EmailCodePurpose,
  EmailCodeResponse,
  FirstLoginResponse,
  MeResponse,
  MyMemberProfileResponse,
  PointAccount,
  PointLedgerPage,
  PointRule,
  SetPasswordResponse,
  UpdateMemberProfilePayload,
  WorkbenchTask,
  WorkbenchTaskPage,
} from "./types";

export interface MakersHubApiClientOptions {
  baseUrl: string;
  transport?: ApiTransport;
}

export interface ListWorkbenchTasksParams {
  mine?: boolean;
  available_to_claim?: boolean;
  status?: string;
}

export function createMakersHubApiClient(options: MakersHubApiClientOptions) {
  const apiRequest = createApiRequester(options);

  return {
    request<T>(path: string, requestOptions: ApiRequestOptions = {}) {
      return apiRequest<T>(path, requestOptions);
    },

    sendEmailCode(email: string, purpose: EmailCodePurpose) {
      return apiRequest<EmailCodeResponse>("/auth/email/send-code", {
        method: "POST",
        body: { email, purpose },
      });
    },

    firstLogin(email: string, code: string) {
      return apiRequest<FirstLoginResponse>("/auth/email/first-login", {
        method: "POST",
        body: { email, code },
      });
    },

    setPassword(token: string, password: string) {
      return apiRequest<SetPasswordResponse>("/auth/password/set", {
        method: "POST",
        token,
        body: { password },
      });
    },

    passwordLogin(email: string, password: string) {
      return apiRequest<AuthTokenData>("/auth/password/login", {
        method: "POST",
        body: { email, password },
      });
    },

    refreshToken(refresh_token: string) {
      return apiRequest<AuthTokenData>("/auth/refresh", {
        method: "POST",
        body: { refresh_token },
      });
    },

    logout(refresh_token: string) {
      return apiRequest<{ revoked: boolean }>("/auth/logout", {
        method: "POST",
        body: { refresh_token },
      });
    },

    getMe(token: string) {
      return apiRequest<MeResponse>("/auth/me", {
        method: "GET",
        token,
      });
    },

    getMyMemberProfile(token: string) {
      return apiRequest<MyMemberProfileResponse>("/me/profile", {
        method: "GET",
        token,
      });
    },

    updateMyMemberProfile(token: string, body: UpdateMemberProfilePayload) {
      return apiRequest<MyMemberProfileResponse>("/me/profile", {
        method: "PATCH",
        token,
        body,
      });
    },

    getMyPermissions(token: string) {
      return apiRequest<CurrentUserPermissions>("/permissions/me", {
        method: "GET",
        token,
      });
    },

    getMyPointAccount(token: string) {
      return apiRequest<PointAccount>("/me/points/account", {
        method: "GET",
        token,
      });
    },

    getMyPointLedger(token: string, page = 1, pageSize = 10) {
      return apiRequest<PointLedgerPage>(`/me/points/ledger?page=${page}&page_size=${pageSize}`, {
        method: "GET",
        token,
      });
    },

    listPointRules(token: string) {
      return apiRequest<PointRule[]>("/points/rules", {
        method: "GET",
        token,
      });
    },

    listWorkbenchTasks(token: string, params: ListWorkbenchTasksParams = {}) {
      const query = new URLSearchParams({ page: "1", page_size: "20" });
      if (params.mine !== undefined) query.set("mine", String(params.mine));
      if (params.available_to_claim !== undefined) {
        query.set("available_to_claim", String(params.available_to_claim));
      }
      if (params.status) query.set("status", params.status);
      return apiRequest<WorkbenchTaskPage>(`/workbench/tasks?${query.toString()}`, {
        method: "GET",
        token,
      });
    },

    createWorkbenchTask(token: string, body: CreateWorkbenchTaskPayload) {
      return apiRequest<WorkbenchTask>("/workbench/tasks", {
        method: "POST",
        token,
        body,
      });
    },

    claimWorkbenchTask(token: string, taskId: number) {
      return apiRequest<WorkbenchTask>(`/workbench/tasks/${taskId}/claim`, {
        method: "POST",
        token,
      });
    },

    submitWorkbenchTask(token: string, taskId: number, submissionContent: string) {
      return apiRequest<WorkbenchTask>(`/workbench/tasks/${taskId}/submit`, {
        method: "POST",
        token,
        body: { submission_content: submissionContent },
      });
    },

    reviewWorkbenchTask(
      token: string,
      taskId: number,
      action: "approve" | "reject",
      reviewComment: string,
    ) {
      return apiRequest<WorkbenchTask>(`/workbench/tasks/${taskId}/review`, {
        method: "POST",
        token,
        body: { action, review_comment: reviewComment },
      });
    },
  };
}

export type MakersHubApiClient = ReturnType<typeof createMakersHubApiClient>;
