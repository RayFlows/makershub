import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  ConfigProvider,
  Descriptions,
  Form,
  Input,
  Layout,
  Menu,
  Space,
  Spin,
  Statistic,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { TabsProps } from "antd";
import {
  CalendarClock,
  ClipboardList,
  Coins,
  FolderKanban,
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
          colorPrimary: "#0f766e",
          borderRadius: 6,
          fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
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
  const tabItems: TabsProps["items"] = [
    {
      key: "password",
      label: "密码登录",
      children: <PasswordLoginForm onAuthenticated={onAuthenticated} />,
    },
    {
      key: "first-login",
      label: "首次登录",
      children: <FirstLoginForm onAuthenticated={onAuthenticated} />,
    },
  ];

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-heading">
          <div className="auth-mark">MH</div>
          <div>
            <Typography.Title level={1}>MakersHub 成员端</Typography.Title>
            <Typography.Text type="secondary">账号登录</Typography.Text>
          </div>
        </div>
        <Tabs defaultActiveKey="password" items={tabItems} />
      </section>
    </main>
  );
}

function PasswordLoginForm({
  onAuthenticated,
}: {
  onAuthenticated: (auth: AuthTokenData, required?: boolean) => void;
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
      <Button block type="primary" htmlType="submit" loading={submitting}>
        登录
      </Button>
    </Form>
  );
}

function FirstLoginForm({
  onAuthenticated,
}: {
  onAuthenticated: (auth: AuthTokenData, required?: boolean) => void;
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
          <Button loading={sending} onClick={handleSendCode}>
            发送
          </Button>
        </Space.Compact>
      </Form.Item>
      <Button block type="primary" htmlType="submit" loading={submitting}>
        继续
      </Button>
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
      <section className="auth-panel narrow">
        <div className="auth-heading">
          <div className="auth-mark">MH</div>
          <div>
            <Typography.Title level={1}>设置密码</Typography.Title>
            <Typography.Text type="secondary">首次登录</Typography.Text>
          </div>
        </div>
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
          <Button block type="primary" htmlType="submit" loading={submitting}>
            保存密码
          </Button>
        </Form>
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
  return (
    <Layout className="app-shell">
      <Layout.Sider width={232} className="side-nav">
        <div className="brand">MakersHub</div>
        <Menu mode="inline" defaultSelectedKeys={["profile"]} items={menuItems} />
      </Layout.Sider>
      <Layout>
        <Layout.Header className="top-bar">
          <Space size={12}>
            <CalendarClock size={18} />
            <span>成员网页端</span>
          </Space>
          <Space size={12}>
            <Tag color={channel === "password" ? "green" : "cyan"}>{channel || "active"}</Tag>
            <Button icon={<LogOut size={16} />} onClick={onLogout}>
              退出
            </Button>
          </Space>
        </Layout.Header>
        <Layout.Content className="content">
          <section className="profile-header">
            <Avatar size={64} src={user.avatar_url || undefined}>
              {user.display_name.slice(0, 1)}
            </Avatar>
            <div>
              <Typography.Title level={1}>{user.display_name}</Typography.Title>
              <Typography.Text type="secondary">{user.email || "未绑定邮箱"}</Typography.Text>
            </div>
          </section>

          <section className="status-grid">
            <div className="status-panel accent-green">
              <span>账号状态</span>
              <strong>{user.status}</strong>
            </div>
            <div className="status-panel accent-gold">
              <span>积分余额</span>
              <strong>--</strong>
            </div>
            <div className="status-panel accent-rose">
              <span>待处理申请</span>
              <strong>--</strong>
            </div>
          </section>

          <section className="detail-band">
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
            <div className="work-panel">
              <Statistic title="本周积分变动" value="--" />
            </div>
            <div className="work-panel">
              <Statistic title="借用记录" value="--" />
            </div>
            <div className="work-panel">
              <Statistic title="项目申请" value="--" />
            </div>
          </section>
        </Layout.Content>
      </Layout>
    </Layout>
  );
}

export default App;
