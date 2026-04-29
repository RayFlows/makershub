# 脚本

本目录放置开发、初始化和运维脚本。

例如初始化唯一超级管理员、生成权限点、导入初始部门等。

## 小程序同步

微信开发者工具运行在 Windows 宿主机上，直接打开 WSL 的 `\\wsl.localhost\...`
路径时，新增文件和目录的监听可能延迟或失效。

小程序开发时建议仍以 WSL 仓库为源码来源，然后把 `apps/miniapp` 同步到
Windows 本地镜像目录：

```bash
scripts/dev/sync-miniapp-to-windows.sh
```

默认镜像目录：

```text
C:\Users\Ray\Documents\New project\makershub-miniapp
```

微信开发者工具打开这个 Windows 本地目录即可。该目录是镜像目录，默认不要在里面改代码。
