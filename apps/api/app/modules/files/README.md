# 文件模块

文件模块负责对象存储文件的元数据、对象 key 生成和生命周期状态。

## 边界

- 本模块负责：文件元数据、用途、归属用户、bucket/object_key、大小、hash、状态；
- 本模块不负责：项目材料、头像、开源协议等具体业务含义；
- MinIO 客户端仍在 `infrastructure/minio`，本模块只在服务层协调使用。

## 当前已落地

- `files` ORM 模型；
- `build_object_key(...)` 统一对象 key 生成；
- `register_file_metadata(...)` 文件元数据登记；
- `FileRepository.mark_deleted(...)` 删除状态标记。

## 后续接入

- 统一上传接口；
- 预签名 URL；
- 临时文件清理任务；
- 文件删除补偿和审计；
- 项目材料、头像、资源附件等业务表统一引用 `file_id`。
