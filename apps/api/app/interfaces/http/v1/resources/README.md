# 资源 V1 接口

负责暴露物资分类、物资台账和库存调整 HTTP 契约。

## 已落地接口

- `GET /api/v1/resources/material-categories`
- `POST /api/v1/resources/material-categories`
- `GET /api/v1/resources/materials`
- `POST /api/v1/resources/materials`
- `GET /api/v1/resources/materials/{material_id}`
- `PATCH /api/v1/resources/materials/{material_id}`
- `PATCH /api/v1/resources/materials/{material_id}/stock`

查询接口要求登录；写接口要求 `resources.material.manage` 权限点。

注意：成员端物资浏览只能看到 `available` 物资，非 `resources.material.manage` 用户即使手动
传入其他状态，也不能看到维修中、停用或下架台账数据。当前接口实现仍需补齐这一后端
兜底过滤，补齐前不能作为成员端物资浏览的安全完成口径。
