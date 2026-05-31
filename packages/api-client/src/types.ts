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
