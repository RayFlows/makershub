import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  ConfigProvider,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Select,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import {
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  Coins,
  KeyRound,
  ListTodo,
  LogOut,
  Mail,
  Plus,
  RefreshCw,
  Send,
  ShieldCheck,
  UserRound,
  XCircle,
} from "lucide-react";

import {
  ApiRequestError,
  claimWorkbenchTask,
  createWorkbenchTask,
  firstLogin,
  getWorkbenchTaskStatusMeta,
  getMyPermissions,
  getMyPointAccount,
  getMyPointLedger,
  getMyMemberProfile,
  getMe,
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
  visibilityLabels,
  type AuthTokenData,
  type CreateWorkbenchTaskPayload,
  type CurrentUserPermissions,
  type EmailCodeResponse,
  type MyMemberProfileResponse,
  type PointAccount,
  type PointLedgerEntry,
  type PointRule,
  type UpdateMemberProfilePayload,
  type UserSummary,
  type WorkbenchTask,
} from "./api";
import {
  clearStoredAuth,
  isExpired,
  loadStoredAuth,
  saveStoredAuth,
  type StoredAuth,
} from "./auth-storage";
import "./styles.css";

type AuthStatus = "checking" | "anonymous" | "authenticated" | "passwordRequired";

interface PasswordLoginValues {
  email: string;
  password: string;
}

interface FirstLoginValues {
  email: string;
  code: string;
}

interface PasswordSetValues {
  password: string;
  confirm_password: string;
}

interface MemberProfileFormValues {
  real_name?: string;
  student_id?: string;
  phone?: string;
  email?: string;
  college?: string;
  major?: string;
  grade?: string;
  qq?: string;
  bio?: string;
}

type MemberSection = "dashboard" | "tasks" | "points" | "profile";

interface WorkbenchTaskFormValues {
  title: string;
  task_type: string;
  assignment_type: "assigned" | "bounty";
  visibility: "department" | "association" | "public";
  department_id?: string;
  content: string;
  point_rule_id: number;
  assignee_id?: string;
}

const menuItems = [
  { key: "dashboard", icon: <ClipboardList size={18} />, label: "工作台" },
  { key: "tasks", icon: <ListTodo size={18} />, label: "任务" },
  { key: "points", icon: <Coins size={18} />, label: "积分" },
  { key: "profile", icon: <UserRound size={18} />, label: "资料" },
] satisfies Array<{ key: MemberSection; icon: JSX.Element; label: string }>;

const authErrorMessage = (error: unknown) => {
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  return "网络异常，请稍后重试";
};

function App() {
  const [status, setStatus] = useState<AuthStatus>("checking");
  const [auth, setAuth] = useState<StoredAuth | null>(null);
  const [channel, setChannel] = useState<string>("");

  useEffect(() => {
    restoreSession();
  }, []);

  const user = auth?.user || null;

  async function restoreSession() {
    const stored = loadStoredAuth();
    if (!stored) {
      setStatus("anonymous");
      return;
    }

    try {
      let nextAuth = stored;
      if (isExpired(stored.expires_at)) {
        if (isExpired(stored.refresh_expires_at)) {
          throw new Error("refresh token expired");
        }
        nextAuth = await refreshToken(stored.refresh_token);
        saveStoredAuth({ ...nextAuth, password_required: stored.password_required });
      }

      const me = await getMe(nextAuth.access_token);
      const restored = {
        ...nextAuth,
        user: me.user,
        password_required: stored.password_required,
      };
      setAuth(restored);
      setChannel(me.claims.channel || "");
      setStatus(restored.password_required ? "passwordRequired" : "authenticated");
    } catch {
      clearStoredAuth();
      setAuth(null);
      setStatus("anonymous");
    }
  }

  function acceptAuth(nextAuth: AuthTokenData, passwordRequired = false) {
    const stored = { ...nextAuth, password_required: passwordRequired };
    saveStoredAuth(stored);
    setAuth(stored);
    setChannel(passwordRequired ? "email_code" : "password");
    setStatus(passwordRequired ? "passwordRequired" : "authenticated");
  }

  async function handleLogout() {
    const refresh = auth?.refresh_token;
    clearStoredAuth();
    setAuth(null);
    setChannel("");
    setStatus("anonymous");
    if (refresh) {
      try {
        await logout(refresh);
      } catch {
        // 本地退出优先完成，服务端会话撤销失败由后续 /auth/me 兜底。
      }
    }
  }

  function handlePasswordSet(userSummary: UserSummary) {
    if (!auth) return;
    const nextAuth = {
      ...auth,
      user: userSummary,
      password_required: false,
    };
    saveStoredAuth(nextAuth);
    setAuth(nextAuth);
    setChannel((currentChannel) => currentChannel || "email_code");
    setStatus("authenticated");
  }

  const appContent = useMemo(() => {
    if (status === "checking") return <LoadingScreen />;
    if (status === "anonymous") return <AuthScreen onAuthenticated={acceptAuth} />;
    if (status === "passwordRequired" && auth) {
      return <SetPasswordScreen token={auth.access_token} onPasswordSet={handlePasswordSet} />;
    }
    if (status === "authenticated" && auth && user) {
      return <MemberShell user={user} token={auth.access_token} channel={channel} onLogout={handleLogout} />;
    }
    return <LoadingScreen />;
  }, [auth, channel, status, user]);

  return (
    <ConfigProvider
      theme={{
        token: {
          colorBgBase: "#f8f8f8",
          colorBgContainer: "#FFFFFF",
          colorText: "#222831",
          colorTextSecondary: "#4E5969",
          colorTextTertiary: "#7D8592",
          colorBorder: "rgba(34, 40, 49, 0.16)",
          colorBorderSecondary: "rgba(34, 40, 49, 0.08)",
          colorPrimary: "#00ADB5",
          colorInfo: "#00ADB5",
          colorSuccess: "#00BAAD",
          colorWarning: "#FFE89E",
          colorError: "#E33C64",
          borderRadius: 10,
          borderRadiusLG: 20,
          borderRadiusSM: 6,
          controlHeight: 44,
          controlHeightSM: 36,
          fontSize: 14,
          fontSizeHeading1: 26,
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
        },
        components: {
          Button: {
            borderRadius: 12,
            controlHeight: 44,
            fontWeight: 500,
            primaryShadow: "none",
          },
          Input: {
            borderRadius: 12,
            controlHeight: 44,
          },
          Tabs: {
            horizontalItemPadding: "10px 0",
            titleFontSize: 14,
          },
        },
      }}
    >
      {appContent}
    </ConfigProvider>
  );
}

function LoadingScreen() {
  return (
    <div className="loading-screen">
      <Spin size="large" />
    </div>
  );
}

function AuthScreen({ onAuthenticated }: { onAuthenticated: (auth: AuthTokenData, required?: boolean) => void }) {
  const [mode, setMode] = useState<"password" | "first-login">("password");

  return (
    <main className="auth-page">
      <section className="auth-card auth-card-login">
        <section className="auth-panel">
          <div className="auth-form-shell">
            <div className="login-brand" aria-label="开源硬件协会">
              <div className="auth-mark">SC</div>
              <div>
                <strong>开源硬件协会</strong>
                <span>SCUMAKER</span>
              </div>
            </div>
            {mode === "password" ? (
              <>
                <AuthPanelTitle title="登录成员端" subtitle="使用已绑定邮箱继续" />
                <PasswordLoginForm onAuthenticated={onAuthenticated} onFirstLogin={() => setMode("first-login")} />
              </>
            ) : (
              <>
                <AuthPanelTitle title="首次登录" subtitle="仅用于已在小程序绑定邮箱的账号" />
                <FirstLoginForm onAuthenticated={onAuthenticated} onBack={() => setMode("password")} />
              </>
            )}
          </div>
        </section>
      </section>
    </main>
  );
}

function AuthPanelTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="auth-heading compact">
      <Typography.Title level={1}>{title}</Typography.Title>
      <Typography.Text type="secondary">{subtitle}</Typography.Text>
    </div>
  );
}

function PasswordLoginForm({
  onAuthenticated,
  onFirstLogin,
}: {
  onAuthenticated: (auth: AuthTokenData, required?: boolean) => void;
  onFirstLogin: () => void;
}) {
  const [form] = Form.useForm<PasswordLoginValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(values: PasswordLoginValues) {
    setSubmitting(true);
    setError("");
    try {
      const auth = await passwordLogin(values.email, values.password);
      onAuthenticated(auth, false);
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Form form={form} layout="vertical" requiredMark={false} onFinish={handleSubmit}>
      {error && <Alert className="form-alert" type="error" showIcon message={error} />}
      <Form.Item
        label="邮箱"
        name="email"
        rules={[
          { required: true, message: "请输入邮箱" },
          { type: "email", message: "邮箱格式不正确" },
        ]}
      >
        <Input autoComplete="email" prefix={<Mail size={16} />} placeholder="name@example.com" />
      </Form.Item>
      <Form.Item label="密码" name="password" rules={[{ required: true, message: "请输入密码" }]}>
        <Input.Password autoComplete="current-password" placeholder="请输入密码" />
      </Form.Item>
      <Button block type="primary" htmlType="submit" loading={submitting} icon={<ArrowRight size={16} />}>
        登录
      </Button>
      <div className="auth-secondary-actions">
        <button type="button" onClick={onFirstLogin}>
          首次登录
        </button>
      </div>
    </Form>
  );
}

function FirstLoginForm({
  onAuthenticated,
  onBack,
}: {
  onAuthenticated: (auth: AuthTokenData, required?: boolean) => void;
  onBack: () => void;
}) {
  const [form] = Form.useForm<FirstLoginValues>();
  const [submitting, setSubmitting] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [emailCode, setEmailCode] = useState<EmailCodeResponse | null>(null);

  async function handleSendCode() {
    const values = await form.validateFields(["email"]).catch(() => null);
    if (!values) return;
    const email = values.email as string;
    setSending(true);
    setError("");
    try {
      const result = await sendEmailCode(email, "first_login");
      setEmailCode(result);
      if (result.dev_code) {
        form.setFieldsValue({ code: result.dev_code });
      }
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  async function handleSubmit(values: FirstLoginValues) {
    setSubmitting(true);
    setError("");
    try {
      const auth = await firstLogin(values.email, values.code);
      onAuthenticated(auth, auth.password_required);
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Form form={form} layout="vertical" requiredMark={false} onFinish={handleSubmit}>
      {error && <Alert className="form-alert" type="error" showIcon message={error} />}
      {emailCode?.dev_code && (
        <Alert
          className="form-alert"
          type="info"
          showIcon
          message={`本地验证码：${emailCode.dev_code}`}
        />
      )}
      <Form.Item
        label="邮箱"
        name="email"
        rules={[
          { required: true, message: "请输入邮箱" },
          { type: "email", message: "邮箱格式不正确" },
        ]}
      >
        <Input autoComplete="email" prefix={<Mail size={16} />} placeholder="name@example.com" />
      </Form.Item>
      <Form.Item label="验证码" required>
        <Space.Compact block>
          <Form.Item
            name="code"
            noStyle
            rules={[
              { required: true, message: "请输入验证码" },
              { len: 6, message: "验证码为6位" },
            ]}
          >
            <Input inputMode="numeric" maxLength={6} placeholder="6位验证码" />
          </Form.Item>
          <Button loading={sending} onClick={handleSendCode} icon={<Mail size={15} />}>
            发送
          </Button>
        </Space.Compact>
      </Form.Item>
      <Button block type="primary" htmlType="submit" loading={submitting} icon={<ArrowRight size={16} />}>
        继续
      </Button>
      <div className="auth-secondary-actions">
        <button type="button" onClick={onBack}>
          返回密码登录
        </button>
      </div>
    </Form>
  );
}

function SetPasswordScreen({
  token,
  onPasswordSet,
}: {
  token: string;
  onPasswordSet: (user: UserSummary) => void;
}) {
  const [form] = Form.useForm<PasswordSetValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(values: PasswordSetValues) {
    setSubmitting(true);
    setError("");
    try {
      const result = await setPassword(token, values.password);
      onPasswordSet(result.user);
    } catch (err) {
      setError(authErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card single">
        <section className="auth-panel">
          <div className="auth-form-shell">
            <AuthPanelTitle title="设置密码" subtitle="首次登录" />
            <Form form={form} layout="vertical" requiredMark={false} onFinish={handleSubmit}>
              {error && <Alert className="form-alert" type="error" showIcon message={error} />}
              <Form.Item
                label="新密码"
                name="password"
                rules={[
                  { required: true, message: "请输入新密码" },
                  { min: 8, message: "密码至少8位" },
                ]}
              >
                <Input.Password autoComplete="new-password" placeholder="至少8位" />
              </Form.Item>
              <Form.Item
                label="确认密码"
                name="confirm_password"
                dependencies={["password"]}
                rules={[
                  { required: true, message: "请再次输入密码" },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue("password") === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error("两次密码不一致"));
                    },
                  }),
                ]}
              >
                <Input.Password autoComplete="new-password" placeholder="再次输入" />
              </Form.Item>
              <Button block type="primary" htmlType="submit" loading={submitting} icon={<KeyRound size={16} />}>
                保存密码
              </Button>
            </Form>
          </div>
        </section>
      </section>
    </main>
  );
}

function MemberShell({
  user,
  token,
  channel,
  onLogout,
}: {
  user: UserSummary;
  token: string;
  channel: string;
  onLogout: () => void;
}) {
  const avatarText = user.display_name.slice(0, 1);
  const navRef = useRef<HTMLElement | null>(null);
  const [activeSection, setActiveSection] = useState<MemberSection>("dashboard");
  const [permissions, setPermissions] = useState<CurrentUserPermissions | null>(null);
  const [pointAccount, setPointAccount] = useState<PointAccount | null>(null);
  const [taskSummary, setTaskSummary] = useState({
    mine: 0,
    available: 0,
    pendingReview: 0,
  });
  const [shellLoading, setShellLoading] = useState(true);
  const [shellMessage, setShellMessage] = useState<{ type: "error"; text: string } | null>(null);

  useEffect(() => {
    function syncNavRailPosition() {
      const navRail = navRef.current;
      if (!navRail) return;

      const safeInset = 18;
      const viewportHeight = window.innerHeight;
      const railHeight = navRail.offsetHeight;
      const centeredOffset = Math.max(safeInset, Math.floor((viewportHeight - railHeight) / 2));

      navRail.style.setProperty("--nav-rail-top", `${centeredOffset}px`);
      navRail.style.setProperty("--nav-rail-max-height", `${Math.max(220, viewportHeight - safeInset * 2)}px`);
    }

    syncNavRailPosition();
    window.addEventListener("resize", syncNavRailPosition);
    return () => window.removeEventListener("resize", syncNavRailPosition);
  }, []);

  async function refreshShellData() {
    setShellLoading(true);
    setShellMessage(null);
    try {
      const [permissionData, accountData, myTasks, availableTasks] = await Promise.all([
        getMyPermissions(token),
        getMyPointAccount(token),
        listWorkbenchTasks(token, { mine: true }),
        listWorkbenchTasks(token, { available_to_claim: true }),
      ]);
      setPermissions(permissionData);
      setPointAccount(accountData);
      setTaskSummary({
        mine: myTasks.total,
        available: availableTasks.total,
        pendingReview: myTasks.items.filter((item) => item.publisher_id === user.id && item.status === "pending_review")
          .length,
      });
    } catch (err) {
      setShellMessage({ type: "error", text: authErrorMessage(err) });
    } finally {
      setShellLoading(false);
    }
  }

  useEffect(() => {
    refreshShellData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, user.id]);

  const permissionCodes = permissions?.permissions || [];
  const canPublishTask = permissionCodes.includes("workbench.task.publish");
  const canViewPointRules = permissionCodes.includes("points.rule.view");

  return (
    <div className="member-shell">
      <header className="member-topbar">
        <div className="topbar-brand" aria-label="开源硬件协会">
          <img className="brand-logo" src="/brand/scumaker-logo.png" alt="" />
          <div className="brand-copy">
            <strong>开源硬件协会</strong>
            <span>SCUMAKER 成员端</span>
          </div>
        </div>

        <div className="topbar-actions">
          <div className="account-chip" title={user.email || user.display_name}>
            <Avatar size={30} src={user.avatar_url || undefined} className="account-avatar">
              {avatarText}
            </Avatar>
            <span>{user.display_name}</span>
          </div>
          <Button className="logout-top-button" icon={<LogOut size={16} />} onClick={onLogout}>
            退出
          </Button>
        </div>
      </header>

      <div className="member-layout">
        <nav className="surface panel member-nav" aria-label="成员端导航" ref={navRef}>
          <p className="eyebrow member-nav-title">Console</p>
          <div className="member-nav-list">
            {menuItems.map((item) => (
              <button
                aria-current={item.key === activeSection ? "page" : undefined}
                className={item.key === activeSection ? "member-nav-button is-active" : "member-nav-button"}
                key={item.key}
                onClick={() => setActiveSection(item.key)}
                type="button"
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </div>
        </nav>

        <main className="member-main">
          <section className="page-intro">
            <div>
              <p className="eyebrow">SCUMAKER</p>
              <h1 className="headline page-title">成员工作台</h1>
              <p className="muted page-summary">把任务、积分和资料放在一个入口里，先跑通真实业务闭环。</p>
            </div>
            <Button icon={<RefreshCw size={16} />} loading={shellLoading} onClick={refreshShellData}>
              刷新
            </Button>
          </section>

          {shellMessage && <Alert type={shellMessage.type} showIcon message={shellMessage.text} />}

          {activeSection === "dashboard" && (
            <DashboardPanel
              user={user}
              channel={channel}
              avatarText={avatarText}
              pointAccount={pointAccount}
              taskSummary={taskSummary}
              canPublishTask={canPublishTask}
              onOpenTasks={() => setActiveSection("tasks")}
            />
          )}
          {activeSection === "tasks" && (
            <WorkbenchTaskPanel
              token={token}
              user={user}
              canPublishTask={canPublishTask}
              canViewPointRules={canViewPointRules}
              onDataChanged={refreshShellData}
            />
          )}
          {activeSection === "points" && <PointsPanel token={token} account={pointAccount} />}
          {activeSection === "profile" && (
            <>
              <section className="surface panel detail-band">
                <div className="section-title">
                  <ShieldCheck size={18} />
                  <span>当前账号</span>
                </div>
                <Descriptions column={1} size="middle">
                  <Descriptions.Item label="用户 ID">{user.id}</Descriptions.Item>
                  <Descriptions.Item label="邮箱">{user.email || "--"}</Descriptions.Item>
                  <Descriptions.Item label="登录渠道">{channel || "--"}</Descriptions.Item>
                </Descriptions>
              </section>
              <MemberProfilePanel token={token} fallbackEmail={user.email} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}

function DashboardPanel({
  user,
  channel,
  avatarText,
  pointAccount,
  taskSummary,
  canPublishTask,
  onOpenTasks,
}: {
  user: UserSummary;
  channel: string;
  avatarText: string;
  pointAccount: PointAccount | null;
  taskSummary: { mine: number; available: number; pendingReview: number };
  canPublishTask: boolean;
  onOpenTasks: () => void;
}) {
  return (
    <>
      <section className="surface panel profile-hero">
        <div className="profile-header">
          <Avatar size={64} src={user.avatar_url || undefined} className="profile-avatar">
            {avatarText}
          </Avatar>
          <div>
            <Typography.Title level={1}>{user.display_name}</Typography.Title>
            <Typography.Text type="secondary">{user.email || "未绑定邮箱"}</Typography.Text>
          </div>
        </div>
        <Tag color={canPublishTask ? "cyan" : "default"}>{canPublishTask ? "可发布任务" : "成员账号"}</Tag>
      </section>

      <section className="status-grid">
        <div className="surface panel status-panel accent-green">
          <span>积分余额</span>
          <strong>{pointAccount?.balance ?? "--"}</strong>
        </div>
        <div className="surface panel status-panel accent-gold">
          <span>我的任务</span>
          <strong>{taskSummary.mine}</strong>
        </div>
        <div className="surface panel status-panel accent-rose">
          <span>可领取任务</span>
          <strong>{taskSummary.available}</strong>
        </div>
      </section>

      <section className="surface panel detail-band dashboard-actions">
        <div>
          <div className="section-title">
            <ShieldCheck size={18} />
            <span>当前入口</span>
          </div>
          <Descriptions column={1} size="middle">
            <Descriptions.Item label="账号状态">{user.status}</Descriptions.Item>
            <Descriptions.Item label="登录渠道">{channel || "--"}</Descriptions.Item>
            <Descriptions.Item label="待审核任务">{taskSummary.pendingReview}</Descriptions.Item>
          </Descriptions>
        </div>
        <Button type="primary" icon={<ListTodo size={16} />} onClick={onOpenTasks}>
          进入任务
        </Button>
      </section>
    </>
  );
}

function WorkbenchTaskPanel({
  token,
  user,
  canPublishTask,
  canViewPointRules,
  onDataChanged,
}: {
  token: string;
  user: UserSummary;
  canPublishTask: boolean;
  canViewPointRules: boolean;
  onDataChanged: () => Promise<void>;
}) {
  const [publishForm] = Form.useForm<WorkbenchTaskFormValues>();
  const assignmentType = Form.useWatch("assignment_type", publishForm);
  const visibility = Form.useWatch("visibility", publishForm);
  const [myTasks, setMyTasks] = useState<WorkbenchTask[]>([]);
  const [availableTasks, setAvailableTasks] = useState<WorkbenchTask[]>([]);
  const [pointRules, setPointRules] = useState<PointRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishing, setPublishing] = useState(false);
  const [actingTaskId, setActingTaskId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);
  const [submitTaskId, setSubmitTaskId] = useState<number | null>(null);
  const [submitContent, setSubmitContent] = useState("");
  const [reviewTaskId, setReviewTaskId] = useState<number | null>(null);
  const [reviewComment, setReviewComment] = useState("");

  async function loadTasks() {
    setLoading(true);
    setMessage(null);
    try {
      const requests: [
        Promise<{ items: WorkbenchTask[] }>,
        Promise<{ items: WorkbenchTask[] }>,
        Promise<PointRule[]> | null,
      ] = [
        listWorkbenchTasks(token, { mine: true }),
        listWorkbenchTasks(token, { available_to_claim: true }),
        canViewPointRules ? listPointRules(token) : null,
      ];
      const [mine, available, rules] = await Promise.all(requests);
      setMyTasks(mine.items);
      setAvailableTasks(available.items);
      if (rules) {
        setPointRules(rules.filter((item) => item.status === "active"));
      }
    } catch (err) {
      setMessage({ type: "error", text: authErrorMessage(err) });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, canViewPointRules]);

  async function handlePublish(values: WorkbenchTaskFormValues) {
    setPublishing(true);
    setMessage(null);
    try {
      const payload: CreateWorkbenchTaskPayload = {
        title: values.title,
        task_type: values.task_type,
        assignment_type: values.assignment_type,
        visibility: values.visibility,
        content: values.content,
        point_rule_id: Number(values.point_rule_id),
        assignee_id: values.assignment_type === "assigned" ? numberOrNull(values.assignee_id) : null,
        department_id: values.visibility === "department" ? numberOrNull(values.department_id) : null,
      };
      await createWorkbenchTask(token, payload);
      publishForm.resetFields();
      publishForm.setFieldsValue({ assignment_type: "bounty", visibility: "association", task_type: "daily" });
      setMessage({ type: "success", text: "任务已发布" });
      await loadTasks();
      await onDataChanged();
    } catch (err) {
      setMessage({ type: "error", text: authErrorMessage(err) });
    } finally {
      setPublishing(false);
    }
  }

  async function handleClaim(taskId: number) {
    await runTaskAction(taskId, async () => {
      await claimWorkbenchTask(token, taskId);
      setMessage({ type: "success", text: "任务已领取" });
    });
  }

  async function handleSubmit(taskId: number) {
    if (!submitContent.trim()) {
      setMessage({ type: "error", text: "请填写完成材料" });
      return;
    }
    await runTaskAction(taskId, async () => {
      await submitWorkbenchTask(token, taskId, submitContent.trim());
      setSubmitTaskId(null);
      setSubmitContent("");
      setMessage({ type: "success", text: "完成材料已提交" });
    });
  }

  async function handleReview(taskId: number, action: "approve" | "reject") {
    const fallback = action === "approve" ? "完成质量合格" : "材料需要补充";
    await runTaskAction(taskId, async () => {
      await reviewWorkbenchTask(token, taskId, action, reviewComment.trim() || fallback);
      setReviewTaskId(null);
      setReviewComment("");
      setMessage({ type: "success", text: action === "approve" ? "任务已通过并发放积分" : "任务已打回" });
    });
  }

  async function runTaskAction(taskId: number, action: () => Promise<void>) {
    setActingTaskId(taskId);
    setMessage(null);
    try {
      await action();
      await loadTasks();
      await onDataChanged();
    } catch (err) {
      setMessage({ type: "error", text: authErrorMessage(err) });
    } finally {
      setActingTaskId(null);
    }
  }

  function renderTask(task: WorkbenchTask) {
    const status = getWorkbenchTaskStatusMeta(task.status);
    const canClaim = task.status === "pending_claim" && task.assignment_type === "bounty";
    const canSubmit =
      task.assignee_id === user.id && (task.status === "pending_completion" || task.status === "rejected");
    const canReview = task.publisher_id === user.id && task.status === "pending_review";

    return (
      <List.Item className="task-list-item">
        <div className="task-row">
          <div className="task-row-main">
            <Space size={8} wrap>
              <Tag color={status.color}>{status.label}</Tag>
              <Tag>{visibilityLabels[task.visibility] || task.visibility}</Tag>
              <Tag>{task.assignment_type === "bounty" ? "悬赏" : "指定"}</Tag>
              <Tag color="cyan">+{task.point_rule_amount}</Tag>
            </Space>
            <h3>{task.title}</h3>
            <p>{task.content}</p>
            {task.submission_content && <p className="task-submission">提交：{task.submission_content}</p>}
          </div>
          <div className="task-row-actions">
            {canClaim && (
              <Button loading={actingTaskId === task.id} onClick={() => handleClaim(task.id)}>
                领取
              </Button>
            )}
            {canSubmit && (
              <Button type="primary" icon={<Send size={15} />} onClick={() => setSubmitTaskId(task.id)}>
                提交
              </Button>
            )}
            {canReview && (
              <Button icon={<CheckCircle2 size={15} />} onClick={() => setReviewTaskId(task.id)}>
                审核
              </Button>
            )}
          </div>
          {submitTaskId === task.id && (
            <div className="task-inline-form">
              <Input.TextArea
                rows={3}
                value={submitContent}
                onChange={(event) => setSubmitContent(event.target.value)}
                placeholder="说明完成情况、材料链接或交付内容"
              />
              <Space>
                <Button onClick={() => setSubmitTaskId(null)}>取消</Button>
                <Button type="primary" loading={actingTaskId === task.id} onClick={() => handleSubmit(task.id)}>
                  提交完成材料
                </Button>
              </Space>
            </div>
          )}
          {reviewTaskId === task.id && (
            <div className="task-inline-form">
              <Input.TextArea
                rows={3}
                value={reviewComment}
                onChange={(event) => setReviewComment(event.target.value)}
                placeholder="填写审核意见"
              />
              <Space wrap>
                <Button onClick={() => setReviewTaskId(null)}>取消</Button>
                <Button
                  danger
                  icon={<XCircle size={15} />}
                  loading={actingTaskId === task.id}
                  onClick={() => handleReview(task.id, "reject")}
                >
                  打回
                </Button>
                <Button
                  type="primary"
                  icon={<CheckCircle2 size={15} />}
                  loading={actingTaskId === task.id}
                  onClick={() => handleReview(task.id, "approve")}
                >
                  通过并发分
                </Button>
              </Space>
            </div>
          )}
        </div>
      </List.Item>
    );
  }

  return (
    <section className="task-workspace">
      {message && <Alert className="form-alert" type={message.type} showIcon message={message.text} />}

      {canPublishTask ? (
        <section className="surface panel publish-panel">
          <div className="section-title">
            <Plus size={18} />
            <span>发布任务</span>
          </div>
          <Form
            form={publishForm}
            layout="vertical"
            requiredMark={false}
            initialValues={{ assignment_type: "bounty", visibility: "association", task_type: "daily" }}
            onFinish={handlePublish}
          >
            <div className="task-form-grid">
              <Form.Item label="标题" name="title" rules={[{ required: true, message: "请输入任务标题" }]}>
                <Input placeholder="例如：完成展台海报" />
              </Form.Item>
              <Form.Item label="任务类型" name="task_type" rules={[{ required: true, message: "请输入任务类型" }]}>
                <Input placeholder="daily / poster / event" />
              </Form.Item>
              <Form.Item label="分配方式" name="assignment_type">
                <Select
                  options={[
                    { label: "悬赏任务", value: "bounty" },
                    { label: "指定任务", value: "assigned" },
                  ]}
                />
              </Form.Item>
              <Form.Item label="可见范围" name="visibility">
                <Select
                  options={[
                    { label: "协会内", value: "association" },
                    { label: "公开", value: "public" },
                    { label: "部门内", value: "department" },
                  ]}
                />
              </Form.Item>
              {assignmentType === "assigned" && (
                <Form.Item label="执行人用户 ID" name="assignee_id" rules={[{ required: true, message: "请输入执行人 ID" }]}>
                  <Input inputMode="numeric" placeholder="目标用户 ID" />
                </Form.Item>
              )}
              {visibility === "department" && (
                <Form.Item label="部门 ID" name="department_id" rules={[{ required: true, message: "请输入部门 ID" }]}>
                  <Input inputMode="numeric" placeholder="部门 ID" />
                </Form.Item>
              )}
              <Form.Item label="积分规则" name="point_rule_id" rules={[{ required: true, message: "请选择积分规则" }]}>
                {canViewPointRules ? (
                  <Select
                    placeholder="选择已启用积分规则"
                    options={pointRules.map((rule) => ({
                      label: `${rule.name}（+${rule.amount}）`,
                      value: rule.id,
                    }))}
                  />
                ) : (
                  <Input inputMode="numeric" placeholder="积分规则 ID" />
                )}
              </Form.Item>
            </div>
            <Form.Item label="任务内容" name="content" rules={[{ required: true, message: "请输入任务内容" }]}>
              <Input.TextArea rows={4} maxLength={2000} showCount placeholder="写清楚交付内容和验收方式" />
            </Form.Item>
            <div className="profile-form-footer">
              <span>{canViewPointRules ? `可选规则 ${pointRules.length} 条` : "当前角色不能查看规则列表"}</span>
              <Button type="primary" htmlType="submit" loading={publishing} icon={<Plus size={16} />}>
                发布任务
              </Button>
            </div>
          </Form>
        </section>
      ) : (
        <Alert className="form-alert" type="info" showIcon message="当前账号没有任务发布权限，可以领取公开悬赏或查看自己的任务。" />
      )}

      <Spin spinning={loading}>
        <section className="task-columns">
          <section className="surface panel task-list-panel">
            <div className="section-title">
              <ClipboardList size={18} />
              <span>我的任务</span>
            </div>
            {myTasks.length ? (
              <List dataSource={myTasks} renderItem={renderTask} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无我的任务" />
            )}
          </section>
          <section className="surface panel task-list-panel">
            <div className="section-title">
              <ListTodo size={18} />
              <span>可领取任务</span>
            </div>
            {availableTasks.length ? (
              <List dataSource={availableTasks} renderItem={renderTask} />
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可领取任务" />
            )}
          </section>
        </section>
      </Spin>
    </section>
  );
}

function PointsPanel({ token, account }: { token: string; account: PointAccount | null }) {
  const [pointAccount, setPointAccount] = useState<PointAccount | null>(account);
  const [ledger, setLedger] = useState<PointLedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: "error"; text: string } | null>(null);

  useEffect(() => {
    setPointAccount(account);
  }, [account]);

  useEffect(() => {
    let alive = true;

    async function loadPoints() {
      setLoading(true);
      setMessage(null);
      try {
        const [accountData, ledgerData] = await Promise.all([
          getMyPointAccount(token),
          getMyPointLedger(token),
        ]);
        if (!alive) return;
        setPointAccount(accountData);
        setLedger(ledgerData.items);
      } catch (err) {
        if (alive) setMessage({ type: "error", text: authErrorMessage(err) });
      } finally {
        if (alive) setLoading(false);
      }
    }

    loadPoints();
    return () => {
      alive = false;
    };
  }, [token]);

  return (
    <Spin spinning={loading}>
      {message && <Alert className="form-alert" type={message.type} showIcon message={message.text} />}
      <section className="status-grid">
        <div className="surface panel status-panel accent-green">
          <span>余额</span>
          <strong>{pointAccount?.balance ?? "--"}</strong>
        </div>
        <div className="surface panel status-panel accent-gold">
          <span>可用</span>
          <strong>{pointAccount?.available_balance ?? "--"}</strong>
        </div>
        <div className="surface panel status-panel accent-rose">
          <span>冻结</span>
          <strong>{pointAccount?.frozen_balance ?? "--"}</strong>
        </div>
      </section>
      <section className="surface panel task-list-panel">
        <div className="section-title">
          <Coins size={18} />
          <span>最近流水</span>
        </div>
        {ledger.length ? (
          <List
            dataSource={ledger}
            renderItem={(item) => (
              <List.Item>
                <div className="ledger-row">
                  <div>
                    <strong>{item.reason || item.business_type}</strong>
                    <span>{formatDateTime(item.created_at)}</span>
                  </div>
                  <Tag color={item.direction === "income" ? "green" : "red"}>
                    {item.direction === "income" ? "+" : "-"}
                    {item.amount}
                  </Tag>
                </div>
              </List.Item>
            )}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无积分流水" />
        )}
      </section>
    </Spin>
  );
}

function MemberProfilePanel({ token, fallbackEmail }: { token: string; fallbackEmail: string | null }) {
  const [form] = Form.useForm<MemberProfileFormValues>();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [profileData, setProfileData] = useState<MyMemberProfileResponse | null>(null);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    let alive = true;

    async function loadProfile() {
      setLoading(true);
      setMessage(null);
      try {
        const result = await getMyMemberProfile(token);
        if (!alive) return;
        setProfileData(result);
        form.setFieldsValue(profileToFormValues(result, fallbackEmail));
      } catch (err) {
        if (!alive) return;
        setMessage({ type: "error", text: authErrorMessage(err) });
      } finally {
        if (alive) setLoading(false);
      }
    }

    loadProfile();
    return () => {
      alive = false;
    };
  }, [fallbackEmail, form, token]);

  async function handleSubmit(values: MemberProfileFormValues) {
    setSaving(true);
    setMessage(null);
    try {
      const result = await updateMyMemberProfile(token, compactProfilePayload(values));
      setProfileData(result);
      form.setFieldsValue(profileToFormValues(result, fallbackEmail));
      setMessage({ type: "success", text: "资料已保存" });
    } catch (err) {
      setMessage({ type: "error", text: authErrorMessage(err) });
    } finally {
      setSaving(false);
    }
  }

  const departmentText =
    profileData?.memberships.map((item) => item.department.name).join("、") ||
    (profileData?.departments.length ? "暂未分配" : "--");

  return (
    <section className="surface panel profile-form-panel">
      <div className="section-title profile-form-title">
        <UserRound size={18} />
        <span>个人资料</span>
      </div>
      {message && (
        <Alert
          className="form-alert"
          type={message.type}
          showIcon
          message={message.text}
        />
      )}
      <Spin spinning={loading}>
        <Form form={form} layout="vertical" requiredMark={false} onFinish={handleSubmit}>
          <div className="profile-form-grid">
            <Form.Item label="真实姓名" name="real_name">
              <Input placeholder="填写真实姓名" />
            </Form.Item>
            <Form.Item
              label="手机号"
              name="phone"
              rules={[{ pattern: /^1[3-9]\d{9}$/, message: "请输入 11 位手机号" }]}
            >
              <Input inputMode="tel" maxLength={11} placeholder="用于借用和项目联系" />
            </Form.Item>
            <Form.Item label="学号" name="student_id">
              <Input inputMode="numeric" placeholder="填写学号" />
            </Form.Item>
            <Form.Item label="QQ" name="qq">
              <Input inputMode="numeric" placeholder="填写 QQ 号" />
            </Form.Item>
            <Form.Item label="学院" name="college">
              <Input placeholder="例如：计算机学院" />
            </Form.Item>
            <Form.Item label="专业" name="major">
              <Input placeholder="例如：计算机科学与技术" />
            </Form.Item>
            <Form.Item label="年级" name="grade">
              <Input inputMode="numeric" placeholder="例如：2026" />
            </Form.Item>
            <Form.Item label="联系邮箱" name="email">
              <Input autoComplete="email" placeholder="用于资料联系，不影响登录邮箱" />
            </Form.Item>
          </div>
          <Form.Item label="个人简介" name="bio">
            <Input.TextArea rows={4} maxLength={500} showCount placeholder="写一点项目方向或兴趣" />
          </Form.Item>
          <div className="profile-form-footer">
            <span>当前部门：{departmentText}</span>
            <Button type="primary" htmlType="submit" loading={saving}>
              保存资料
            </Button>
          </div>
        </Form>
      </Spin>
    </section>
  );
}

function profileToFormValues(
  data: MyMemberProfileResponse,
  fallbackEmail: string | null,
): MemberProfileFormValues {
  const { profile } = data;
  return {
    real_name: profile.real_name || "",
    student_id: profile.student_id || "",
    phone: profile.phone || "",
    email: profile.email || fallbackEmail || "",
    college: profile.college || "",
    major: profile.major || "",
    grade: profile.grade || "",
    qq: profile.qq || "",
    bio: profile.bio || "",
  };
}

function compactProfilePayload(values: MemberProfileFormValues): UpdateMemberProfilePayload {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [
      key,
      typeof value === "string" && value.trim() === "" ? null : value,
    ]),
  ) as UpdateMemberProfilePayload;
}

function numberOrNull(value: string | number | undefined): number | null {
  if (value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default App;
