# scripts/security

安全检查脚本目录，用于放置可以在本地和 CI 中重复执行的轻量安全守卫。

当前能力：

- `check_tracked_secrets.py`：扫描 Git 已跟踪文件中的高置信度密钥。

本目录不负责生产密钥托管，也不替代 GitHub secret scanning、部署平台 secret、云厂商密钥管理或人工安全审计。
