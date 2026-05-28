-- Existing MySQL database upgrade for algorithm version management.
-- Run this against the current development database if /xuzhou/algorithm/list reports missing columns.

ALTER TABLE xuzhou_alg
  ADD COLUMN alg_weight_path varchar(500) DEFAULT NULL COMMENT '算法权重文件路径';

ALTER TABLE xuzhou_alg
  ADD COLUMN alg_runtime_type varchar(50) NOT NULL DEFAULT 'external_box' COMMENT '运行位置: local/external_box';

ALTER TABLE xuzhou_alg
  ADD COLUMN alg_enabled tinyint(1) NOT NULL DEFAULT 1 COMMENT '是否启用';

ALTER TABLE xuzhou_alg
  ADD UNIQUE KEY uk_xuzhou_alg_serial_version (alg_serial, alg_version);

INSERT INTO xuzhou_alg (
  alg_name,
  alg_version,
  alg_serial,
  alg_common,
  alg_default_conf,
  alg_weight_path,
  alg_runtime_type,
  alg_enabled,
  alg_update_time
) VALUES
  ('人脸检测', 'v1', 'face_detection', NULL, '{"proto_path":"algorithm/model/face_detection/v1/deploy.prototxt","confidence":0.55}', 'algorithm/model/face_detection/v1/res10_300x300_ssd_iter_140000.caffemodel', 'external_box', 1, sysdate()),
  ('人脸特征识别', 'v1', 'arcface_recognition', NULL, '{}', 'algorithm/model/arcface_recognition/v1/w600k_r50.onnx', 'external_box', 1, sysdate()),
  ('实时人脸幸福指数分析', 'v1', 'realtime_face_analysis', NULL, '{"face_detection":"face_detection:v1","face_recognition":"arcface_recognition:v1"}', NULL, 'external_box', 1, sysdate())
ON DUPLICATE KEY UPDATE
  alg_name = VALUES(alg_name),
  alg_common = VALUES(alg_common),
  alg_default_conf = VALUES(alg_default_conf),
  alg_weight_path = VALUES(alg_weight_path),
  alg_runtime_type = VALUES(alg_runtime_type),
  alg_enabled = VALUES(alg_enabled),
  alg_update_time = VALUES(alg_update_time);
