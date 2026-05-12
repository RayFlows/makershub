import { defineConfig } from "vitepress";

export default defineConfig({
  title: "MakersHub",
  description: "开源硬件协会平台文档",
  lang: "zh-CN",
  themeConfig: {
    nav: [
      { text: "文档首页", link: "/" },
      { text: "重构主线", link: "/rebuild/" }
    ],
    sidebar: {
      "/rebuild/": [
        { text: "总览", link: "/rebuild/" },
        {
          text: "01 先读",
          items: [
            { text: "需求核对清单", link: "/rebuild/01-先读/01-需求核对清单" },
            { text: "第一阶段路线图", link: "/rebuild/01-先读/02-第一阶段路线图" },
            { text: "后端基础设施清单", link: "/rebuild/01-先读/03-后端基础设施清单" }
          ]
        },
        {
          text: "02 架构设计",
          items: [
            { text: "API 契约", link: "/rebuild/02-架构设计/01-API契约" },
            { text: "数据库设计", link: "/rebuild/02-架构设计/02-数据库设计" },
            { text: "业务域划分", link: "/rebuild/02-架构设计/03-业务域划分" },
            { text: "后端业务域内部架构", link: "/rebuild/02-架构设计/04-后端业务域内部架构" },
            { text: "功能工作流", link: "/rebuild/02-架构设计/05-功能工作流" }
          ]
        },
        {
          text: "03 工程运维",
          items: [
            { text: "项目结构规划", link: "/rebuild/03-工程运维/01-项目结构规划" },
            { text: "后端代码规范", link: "/rebuild/03-工程运维/02-后端代码规范" },
            { text: "仓库与版本管理", link: "/rebuild/03-工程运维/03-仓库与版本管理" },
            { text: "环境部署与发布", link: "/rebuild/03-工程运维/04-环境部署与发布" }
          ]
        }
      ]
    }
  }
});
