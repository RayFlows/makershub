import { Button, ConfigProvider, Layout, Menu, Space, Table, Tag, Typography } from "antd";
import {
  Activity,
  Building2,
  ClipboardCheck,
  Coins,
  ShieldCheck,
  UsersRound,
} from "lucide-react";

import "./styles.css";

const menuItems = [
  { key: "members", icon: <UsersRound size={18} />, label: "成员管理" },
  { key: "permissions", icon: <ShieldCheck size={18} />, label: "权限配置" },
  { key: "resources", icon: <Building2 size={18} />, label: "资源管理" },
  { key: "approvals", icon: <ClipboardCheck size={18} />, label: "审核工作台" },
  { key: "points", icon: <Coins size={18} />, label: "积分与审计" },
];

const columns = [
  { title: "事项", dataIndex: "name", key: "name" },
  { title: "业务域", dataIndex: "domain", key: "domain" },
  { title: "状态", dataIndex: "status", key: "status" },
];

const data = [
  { key: "1", name: "成员资料审核", domain: "组织与成员", status: "待接入" },
  { key: "2", name: "资源借用审批", domain: "借用", status: "待接入" },
  { key: "3", name: "项目立项审核", domain: "项目", status: "待接入" },
];

function App() {
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: "#14532d",
          borderRadius: 6,
          fontFamily:
            "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        },
      }}
    >
      <Layout className="admin-shell">
        <Layout.Sider width={248} className="admin-side">
          <div className="admin-brand">MakersHub Admin</div>
          <Menu mode="inline" defaultSelectedKeys={["approvals"]} items={menuItems} />
        </Layout.Sider>
        <Layout>
          <Layout.Header className="admin-top">
            <Space size={12}>
              <Activity size={18} />
              <span>后台管理重写基线</span>
            </Space>
            <Tag color="green">权限优先</Tag>
          </Layout.Header>
          <Layout.Content className="admin-content">
            <section className="admin-heading">
              <Typography.Title level={1}>审核工作台</Typography.Title>
              <Space wrap>
                <Button type="primary">处理审核</Button>
                <Button>查看审计</Button>
              </Space>
            </section>
            <Table
              columns={columns}
              dataSource={data}
              pagination={false}
              rowClassName="admin-table-row"
            />
          </Layout.Content>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}

export default App;
