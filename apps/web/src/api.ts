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
