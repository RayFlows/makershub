import { defineConfig } from "vitepress";

export default defineConfig({
  title: "MakersHub",
  description: "开源硬件协会平台文档",
  lang: "zh-CN",
  themeConfig: {
    nav: [{ text: "重构文档", link: "/rebuild/" }],
    sidebar: {
      "/rebuild/": [
        { text: "重构文档首页", link: "/rebuild/" },
        {
          text: "先读主线",
          items: [
            { text: "需求核对清单", link: "/rebuild/requirements-checklist" },
            { text: "第一阶段路线图", link: "/rebuild/phase-1-roadmap" },
            { text: "后端基础设施清单", link: "/rebuild/backend-foundation-checklist" }
          ]
        },
        {
          text: "设计细节",
          items: [
            { text: "API 契约草案", link: "/rebuild/api-contract" },
            { text: "数据库设计草案", link: "/rebuild/database-design" },
            { text: "业务域划分", link: "/rebuild/domain-division" },
            { text: "业务域内部架构", link: "/rebuild/backend-domain-architecture" },
            { text: "功能工作流", link: "/rebuild/workflows" }
          ]
        },
        {
          text: "工程与运维",
          items: [
            { text: "项目结构规划", link: "/rebuild/project-structure" },
            { text: "后端代码注释规范", link: "/rebuild/backend-code-style" },
            { text: "仓库与版本管理", link: "/rebuild/repository-versioning" },
            { text: "环境与发布周期", link: "/rebuild/environment-release-ops" }
          ]
        }
      ]
    }
  }
});
