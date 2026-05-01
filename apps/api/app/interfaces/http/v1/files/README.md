# files API

文件接口负责统一上传入口和文件元数据查询。

当前已开放：

- `POST /api/v1/files/upload-intents`：创建短期预签名上传 URL，并登记 `pending_upload` 文件元数据。

本接口不负责具体业务归属审核。项目材料、头像、资源附件等业务模块应引用返回的 `file_id`，
再按各自业务规则完成审核、绑定和后续状态流转。
