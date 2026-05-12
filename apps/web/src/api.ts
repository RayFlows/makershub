export type EmailCodePurpose = "bind_email" | "first_login";

export interface UserSummary {
  id: number;
  display_name: string;
  avatar_url: string | null;
  status: string;
  email: string | null;
}

export interface AuthTokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  expires_at: string;
  refresh_expires_at: string;
  user: UserSummary;
}

export interface EmailCodeResponse {
  email: string;
  purpose: EmailCodePurpose;
  expires_at: string;
  delivery_mode: string;
  dev_code: string | null;
}

export interface FirstLoginResponse extends AuthTokenData {
  password_required: boolean;
}

export interface SetPasswordResponse {
  password_set: boolean;
  user: UserSummary;
}

export interface MeResponse {
  user: UserSummary;
  claims: {
    channel?: string;
  };
}

export interface DepartmentSummary {
  id: number;
  code: string;
  name: string;
  status: string;
  sort_order: number;
}

export interface MemberProfile {
  id: number;
  user_id: number;
  real_name: string | null;
  student_id: string | null;
  phone: string | null;
  email: string | null;
  college: string | null;
  major: string | null;
  grade: string | null;
  qq: string | null;
  bio: string | null;
  created_at: string;
  updated_at: string;
}

export interface DepartmentMembership {
  id: number;
  department: DepartmentSummary;
  status: string;
  joined_at: string;
  left_at: string | null;
}

export interface MyMemberProfileResponse {
  profile: MemberProfile;
  departments: DepartmentSummary[];
  memberships: DepartmentMembership[];
}

export interface UpdateMemberProfilePayload {
  real_name?: string | null;
  student_id?: string | null;
  phone?: string | null;
  email?: string | null;
  college?: string | null;
  major?: string | null;
  grade?: string | null;
  qq?: string | null;
  bio?: string | null;
}

export interface CurrentUserPermissions {
  user_id: number;
  permissions: string[];
  is_super_admin: boolean;
  is_system_operator: boolean;
}

export interface PointAccount {
  user_id: number;
  balance: number;
  available_balance: number;
  frozen_balance: number;
  status: string;
  updated_at: string;
}

export interface PointLedgerEntry {
  id: number;
  user_id: number;
  direction: string;
  amount: number;
  balance_after: number;
  available_balance_after: number;
  frozen_balance_after: number;
  business_type: string;
  business_id: string | null;
  idempotency_key: string | null;
  related_hold_id: number | null;
  reason: string | null;
  operator_id: number | null;
  created_at: string;
}

export interface PointLedgerPage {
  items: PointLedgerEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface PointRule {
  id: number;
  code: string;
  name: string;
  rule_type: string;
  status: string;
  version: number;
  amount: number;
  description: string | null;
  effective_from: string | null;
  effective_to: string | null;
  created_by: number | null;
  updated_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkbenchTask {
  id: number;
  title: string;
  task_type: string;
  assignment_type: "assigned" | "bounty";
  visibility: "department" | "association" | "public";
  department_id: number | null;
  content: string;
  deadline: string | null;
  status: string;
  publisher_id: number;
  assignee_id: number | null;
  claimed_at: string | null;
  point_rule_id: number;
  point_rule_amount: number;
  submission_content: string | null;
  submitted_at: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_comment: string | null;
  completed_at: string | null;
  point_ledger_entry_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface WorkbenchTaskPage {
  items: WorkbenchTask[];
  page: number;
  page_size: number;
  total: number;
}

export interface CreateWorkbenchTaskPayload {
  title: string;
  task_type: string;
  assignment_type: "assigned" | "bounty";
  visibility: "department" | "association" | "public";
  department_id?: number | null;
  content: string;
  deadline?: string | null;
  point_rule_id: number;
  assignee_id?: number | null;
}

interface ApiEnvelope<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  message?: string;
  request_id?: string;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  token?: string;
}

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
  }
}

const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/$/, "");

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  const payload = (await response.json()) as ApiEnvelope<T>;

  if (!response.ok || payload.success === false) {
    const error = payload.error;
    throw new ApiRequestError(
      error?.message || "请求失败",
      error?.code || "HTTP_ERROR",
      response.status,
    );
  }
  if (payload.data === undefined) {
    throw new ApiRequestError("响应缺少数据", "EMPTY_RESPONSE", response.status);
  }
  return payload.data;
}

export function sendEmailCode(email: string, purpose: EmailCodePurpose) {
  return apiRequest<EmailCodeResponse>("/auth/email/send-code", {
    method: "POST",
    body: { email, purpose },
  });
}

export function firstLogin(email: string, code: string) {
  return apiRequest<FirstLoginResponse>("/auth/email/first-login", {
    method: "POST",
    body: { email, code },
  });
}

export function setPassword(token: string, password: string) {
  return apiRequest<SetPasswordResponse>("/auth/password/set", {
    method: "POST",
    token,
    body: { password },
  });
}

export function passwordLogin(email: string, password: string) {
  return apiRequest<AuthTokenData>("/auth/password/login", {
    method: "POST",
    body: { email, password },
  });
}

export function refreshToken(refresh_token: string) {
  return apiRequest<AuthTokenData>("/auth/refresh", {
    method: "POST",
    body: { refresh_token },
  });
}

export function logout(refresh_token: string) {
  return apiRequest<{ revoked: boolean }>("/auth/logout", {
    method: "POST",
    body: { refresh_token },
  });
}

export function getMe(token: string) {
  return apiRequest<MeResponse>("/auth/me", {
    method: "GET",
    token,
  });
}

export function getMyMemberProfile(token: string) {
  return apiRequest<MyMemberProfileResponse>("/me/profile", {
    method: "GET",
    token,
  });
}

export function updateMyMemberProfile(token: string, body: UpdateMemberProfilePayload) {
  return apiRequest<MyMemberProfileResponse>("/me/profile", {
    method: "PATCH",
    token,
    body,
  });
}

export function getMyPermissions(token: string) {
  return apiRequest<CurrentUserPermissions>("/permissions/me", {
    method: "GET",
    token,
  });
}

export function getMyPointAccount(token: string) {
  return apiRequest<PointAccount>("/me/points/account", {
    method: "GET",
    token,
  });
}

export function getMyPointLedger(token: string, page = 1, pageSize = 10) {
  return apiRequest<PointLedgerPage>(`/me/points/ledger?page=${page}&page_size=${pageSize}`, {
    method: "GET",
    token,
  });
}

export function listPointRules(token: string) {
  return apiRequest<PointRule[]>("/points/rules", {
    method: "GET",
    token,
  });
}

export function listWorkbenchTasks(
  token: string,
  params: { mine?: boolean; available_to_claim?: boolean; status?: string } = {},
) {
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
}

export function createWorkbenchTask(token: string, body: CreateWorkbenchTaskPayload) {
  return apiRequest<WorkbenchTask>("/workbench/tasks", {
    method: "POST",
    token,
    body,
  });
}

export function claimWorkbenchTask(token: string, taskId: number) {
  return apiRequest<WorkbenchTask>(`/workbench/tasks/${taskId}/claim`, {
    method: "POST",
    token,
  });
}

export function submitWorkbenchTask(token: string, taskId: number, submissionContent: string) {
  return apiRequest<WorkbenchTask>(`/workbench/tasks/${taskId}/submit`, {
    method: "POST",
    token,
    body: { submission_content: submissionContent },
  });
}

export function reviewWorkbenchTask(
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
}
