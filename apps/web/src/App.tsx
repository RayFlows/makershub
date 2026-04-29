import { Button, ConfigProvider, Layout, Menu, Space, Tag, Typography } from "antd";
import {
  CalendarClock,
  ClipboardList,
  Coins,
  FolderKanban,
  PackageSearch,
  UserRound,
} from "lucide-react";

import "./styles.css";

const menuItems = [
  { key: "profile", icon: <UserRound size={18} />, label: "个人资料" },
  { key: "points", icon: <Coins size={18} />, label: "积分账本" },
  { key: "resources", icon: <PackageSearch size={18} />, label: "资源借用" },
  { key: "projects", icon: <FolderKanban size={18} />, label: "项目申请" },
  { key: "records", icon: <ClipboardList size={18} />, label: "我的记录" },
];

const quickEntries = [
  "完善资料",
  "查看积分",
  "申请借用",
  "提交项目",
];

function App() {
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
      <Layout className="app-shell">
        <Layout.Sider width={232} className="side-nav">
          <div className="brand">MakersHub</div>
          <Menu mode="inline" defaultSelectedKeys={["profile"]} items={menuItems} />
        </Layout.Sider>
        <Layout>
          <Layout.Header className="top-bar">
            <Space size={12}>
              <CalendarClock size={18} />
              <span>成员网页端验证环境</span>
            </Space>
            <Tag color="cyan">V2 骨架</Tag>
          </Layout.Header>
          <Layout.Content className="content">
            <section className="intro">
              <Typography.Title level={1}>成员网页端</Typography.Title>
              <Typography.Paragraph>
                第一阶段先用网页端验证登录、资料、积分、资源借用和项目申请流程。
              </Typography.Paragraph>
              <Space wrap>
                {quickEntries.map((entry) => (
                  <Button key={entry} type={entry === "申请借用" ? "primary" : "default"}>
                    {entry}
                  </Button>
                ))}
              </Space>
            </section>
            <section className="status-grid">
              <div className="status-panel accent-green">
                <span>身份状态</span>
                <strong>等待接入后端</strong>
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
          </Layout.Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}

export default App;
