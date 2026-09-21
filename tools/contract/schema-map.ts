/**
 * Bản đồ `operationId → schema FE` mà H1 dùng để giải response 2xx (B0-07 [2]).
 *
 * Mỗi dòng không phải v2 của BE-BIND §1 (kể cả S1, S2) và §2 có **đúng một** mục;
 * `check.py` hỏng khi thiếu hay thừa mục ("bản đồ đủ"). Hợp đồng cũ lấy theo cột
 * "Schema FE" của BE-BIND, hợp đồng mới theo cột Response của HOP-DONG-MOI §2–§8.
 * Module nhập thẳng file (`@/api/schemas/<file>`, HOP-DONG-MOI §9), không qua
 * `export *` của `index.ts`, trừ các schema cũ vốn khai **trong** `index.ts`.
 *
 * `shape`:
 * - `object` — thân là chính schema;
 * - `array` — thân là mảng của schema (danh sách cũ, W22);
 * - `empty` — thân rỗng (204, hay 2xx không thân); không có schema để giải.
 *
 * Mục chỉ mang **chuỗi** module/tên export, không nhập tĩnh: một export thiếu
 * phải thành một dòng hỏng của smoke, không làm sập cả runner lúc liên kết ESM.
 */

export type SchemaMapEntry =
  | { readonly module: string; readonly exportName: string; readonly shape: 'object' | 'array' }
  | { readonly shape: 'empty' };

const INDEX = '@/api/schemas/index';
const ADMIN_ML = '@/api/schemas/adminMl';
const USERS = '@/api/schemas/users';
const VERSIONS = '@/api/schemas/versions';

const EMPTY: SchemaMapEntry = { shape: 'empty' };

/** Mục thân là một object của `exportName` trong `module`. */
function object(module: string, exportName: string): SchemaMapEntry {
  return { exportName, module, shape: 'object' };
}

/** Mục thân là mảng các object của `exportName` trong `module`. */
function array(module: string, exportName: string): SchemaMapEntry {
  return { exportName, module, shape: 'array' };
}

export const SCHEMA_MAP: Readonly<Record<string, SchemaMapEntry>> = {
  /* -- BE-BIND §1, hợp đồng cũ -------------------------------------------- */

  // #1. Response đăng nhập không có thân: FE bỏ qua thân (`src/api/client.ts:590-597`,
  // `postWithoutBody` ở `:695-704`) và lấy phiên bằng refresh (`src/lib/auth/session.ts`
  // chỉ gọi `bootstrapSession` → `refreshPath`). Vì vậy 204, không giải bằng schema refresh.
  auth_login: EMPTY,
  // #3. Schema FE là `.passthrough()` (K04): giải bằng bản strict riêng của harness (W16).
  auth_refresh: object('./strict/refresh', 'RefreshResponseSchema'),
  auth_logout: EMPTY, // #4
  drawings_init_upload: object(INDEX, 'ProgressSchema'), // #5
  drawings_upload_chunk: object(INDEX, 'ProgressSchema'), // #6
  drawings_complete_upload: object(INDEX, 'ProgressSchema'), // #7
  drawings_read_progress: object(INDEX, 'ProgressSchema'), // #8
  telemetry_read_feature_flags: object('@/api/schemas/featureFlags', 'FeatureFlagsSchema'), // #9
  floors_create_floor: object(INDEX, 'FloorSchema'), // #10
  floors_delete_floor: object(INDEX, 'FloorSchema'), // #11
  floors_list_floors: array(INDEX, 'FloorSchema'), // #12
  floors_reorder_floors: array(INDEX, 'FloorSchema'), // #13
  library_list_items: array('@/api/schemas/library', 'LibraryItemSchema'), // #14
  library_read_item: object('@/api/schemas/library', 'LibraryItemSchema'), // #15
  measurements_list_records: array('@/api/schemas/measurements', 'MeasurementRecordSchema'), // #16
  measurements_create_record: object('@/api/schemas/measurements', 'MeasurementRecordSchema'), // #17
  measurements_delete_record: EMPTY, // #18 (204)
  notifications_list: array('@/api/schemas/notifications', 'NotificationSchema'), // #19
  notifications_mark_read: EMPTY, // #20
  notifications_mark_all_read: EMPTY, // #21
  notifications_accept_invite: object('@/api/schemas/notifications', 'NotificationSchema'), // #22
  projects_list_projects: array(INDEX, 'ProjectSchema'), // #23
  projects_read_project: object(INDEX, 'ProjectSchema'), // #24
  projects_create_project: object(INDEX, 'ProjectSchema'), // #25
  projects_update_project: object(INDEX, 'ProjectSchema'), // #26
  projects_delete_project: object(INDEX, 'ProjectSchema'), // #27
  templates_list_templates: array('@/api/schemas/propertyTemplates', 'PropertyTemplateSchema'), // #28
  templates_create_template: object('@/api/schemas/propertyTemplates', 'PropertyTemplateSchema'), // #29
  quality_read_assessment: object('@/api/schemas/quality', 'ImageQualityAssessmentSchema'), // #30
  quality_set_corners: object('@/api/schemas/quality', 'ImageQualityAssessmentSchema'), // #31
  quality_straighten: object('@/api/schemas/quality', 'ImageQualityAssessmentSchema'), // #32
  spatial_read_floor: object(INDEX, 'FloorSchema'), // #33
  floors_patch_spatial_floor: object(INDEX, 'FloorSchema'), // #34
  spatial_write_layer: object('@/api/schemas/spatialLayer', 'FloorLayerWriteResultSchema'), // #35
  versions_read_version: object(INDEX, 'VersionSchema'), // #36
  telemetry_ingest_batch: EMPTY, // #37 (204)
  users_list_users: object(USERS, 'AdminUserListSchema'), // #38 `{total, users}`
  users_list_memberships: array(USERS, 'UserMembershipSchema'), // #39
  users_list_activity: array(USERS, 'UserActivitySchema'), // #40
  users_change_role: object(USERS, 'AdminUserSchema'), // #41
  users_disable_user: object(USERS, 'AdminUserSchema'), // #42
  users_enable_user: object(USERS, 'AdminUserSchema'), // #43
  users_invite_users: array(USERS, 'AdminUserSchema'), // #44
  users_resend_invitation: object(USERS, 'AdminUserSchema'), // #45
  users_delete_user: object(USERS, 'AdminUserSchema'), // #46
  // S1, S2: thân là `data:` của mỗi khung SSE (H5), không phải response HTTP.
  streams_open_progress: object(INDEX, 'ProgressSchema'), // S1
  streams_open_notifications: object('@/api/schemas/notifications', 'NotificationSchema'), // S2

  /* -- BE-BIND §2, hợp đồng mới (HOP-DONG-MOI §2–§8) ----------------------- */

  projects_list_summaries: object('@/api/schemas/projectSummaries', 'ProjectSummaryPageSchema'), // N1
  members_add_member: object(INDEX, 'UserSchema'), // N3 (response `UserSchema` cũ)
  members_remove_member: object(INDEX, 'UserSchema'), // N4
  settings_read_settings: object('@/api/schemas/projectSettings', 'ProjectSettingsSchema'), // N5
  settings_replace_settings: object('@/api/schemas/projectSettings', 'ProjectSettingsSchema'), // N6
  drawings_list_latest_uploads: object('@/api/schemas/uploads', 'LatestFloorUploadPageSchema'), // N7
  auth_request_password_reset: EMPTY, // N8 (luôn 204)
  auth_confirm_password_reset: EMPTY, // N9 (204)
  auth_accept_invitation: EMPTY, // N10 (204 + cookie)
  me_read_profile: object('@/api/schemas/me', 'MeSchema'), // N11
  me_update_profile: object('@/api/schemas/me', 'MeSchema'), // N12
  me_change_password: EMPTY, // N13 (204)
  me_replace_avatar: object('@/api/schemas/me', 'MeSchema'), // N14
  spatial_read_graph: object('@/api/schemas/spatialGraph', 'SpatialGraphDocumentSchema'), // N15
  spatial_read_layer: object('@/api/schemas/spatialLayer', 'FloorLayerDocumentSchema'), // N16
  versions_list_versions: object(VERSIONS, 'FloorVersionPageSchema'), // N17
  versions_read_snapshot: object(VERSIONS, 'FloorVersionSnapshotSchema'), // N18
  versions_restore_version: object(VERSIONS, 'FloorVersionSummarySchema'), // N19 (201)
  versions_label_version: object(VERSIONS, 'FloorVersionSummarySchema'), // N20
  rules_read_config: object('@/api/schemas/ruleConfig', 'ProjectRuleConfigSchema'), // N21
  rules_replace_config: object('@/api/schemas/ruleConfig', 'ProjectRuleConfigSchema'), // N22
  ml_list_families: object(ADMIN_ML, 'ModelFamilyPageSchema'), // N23
  ml_activate_version: object(ADMIN_ML, 'ModelFamilySchema'), // N24
  ml_list_versions: object(ADMIN_ML, 'ModelVersionPageSchema'), // N25
  ml_upload_version: object(ADMIN_ML, 'ModelVersionSchema'), // N26
  ml_read_version: object(ADMIN_ML, 'ModelVersionSchema'), // N27
  ml_list_datasets: object(ADMIN_ML, 'DatasetPageSchema'), // N28
  ml_create_dataset: object(ADMIN_ML, 'DatasetSchema'), // N29
  ml_list_dataset_versions: object(ADMIN_ML, 'DatasetVersionPageSchema'), // N30
  ml_build_dataset_version: object(ADMIN_ML, 'DatasetVersionSchema'), // N31 (202)
  ml_list_jobs: object(ADMIN_ML, 'TrainingJobPageSchema'), // N32
  ml_create_job: object(ADMIN_ML, 'TrainingJobSchema'), // N33 (202)
  ml_read_job: object(ADMIN_ML, 'TrainingJobSchema'), // N34
  ml_cancel_job: object(ADMIN_ML, 'TrainingJobSchema'), // N35
  ml_list_job_metrics: object(ADMIN_ML, 'TrainingMetricPageSchema'), // N36
  ml_list_job_logs: object(ADMIN_ML, 'TrainingLogPageSchema'), // N37
};
