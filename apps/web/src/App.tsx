import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  ConfigProvider,
  Descriptions,
  Form,
  Input,
  Space,
  Spin,
  Statistic,
  Typography,
} from "antd";
import {
  Activity,
  ArrowRight,
  ClipboardList,
  Coins,
  FolderKanban,
  KeyRound,
  LogOut,
  Mail,
  PackageSearch,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import {
  ApiRequestError,
  firstLogin,
  getMe,
  logout,
  passwordLogin,
  refreshToken,
  sendEmailCode,
  setPassword,
  type AuthTokenData,
  type EmailCodeResponse,
  type UserSummary,
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

const menuItems = [
  { key: "profile", icon: <UserRound size={18} />, label: "个人资料" },
  { key: "points", icon: <Coins size={18} />, label: "积分账本" },
  { key: "resources", icon: <PackageSearch size={18} />, label: "资源借用" },
  { key: "projects", icon: <FolderKanban size={18} />, label: "项目申请" },
  { key: "records", icon: <ClipboardList size={18} />, label: "我的记录" },
];

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
    if (status === "authenticated" && user) {
      return <MemberShell user={user} channel={channel} onLogout={handleLogout} />;
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
  channel,
  onLogout,
}: {
  user: UserSummary;
  channel: string;
  onLogout: () => void;
}) {
  const avatarText = user.display_name.slice(0, 1);
  const navRef = useRef<HTMLElement | null>(null);

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
          <p className="eyebrow member-nav-title">导航</p>
          <div className="member-nav-list">
            {menuItems.map((item) => (
              <button
                aria-current={item.key === "profile" ? "page" : undefined}
                className={item.key === "profile" ? "member-nav-button is-active" : "member-nav-button"}
                key={item.key}
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
              <p className="eyebrow">Member Console</p>
              <h1 className="headline page-title">成员工作台</h1>
              <p className="muted page-summary">查看账号状态、积分账本、借用记录与项目申请。</p>
            </div>
            <div className="status-pill">
              <Activity size={18} />
              <span>{user.status}</span>
            </div>
          </section>

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
            <div className="hero-status">
              <Activity size={18} />
              <span>{user.status}</span>
            </div>
          </section>

          <section className="status-grid">
            <div className="surface panel status-panel accent-green">
              <span>账号状态</span>
              <strong>{user.status}</strong>
            </div>
            <div className="surface panel status-panel accent-gold">
              <span>积分余额</span>
              <strong>--</strong>
            </div>
            <div className="surface panel status-panel accent-rose">
              <span>待处理申请</span>
              <strong>--</strong>
            </div>
          </section>

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

          <section className="work-grid">
            <div className="surface panel work-panel">
              <Statistic title="本周积分变动" value="--" />
            </div>
            <div className="surface panel work-panel">
              <Statistic title="借用记录" value="--" />
            </div>
            <div className="surface panel work-panel">
              <Statistic title="项目申请" value="--" />
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
