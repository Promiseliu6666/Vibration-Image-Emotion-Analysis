-- Migration: add vid_box_serial column to xuzhou_video table
-- For existing databases that already have xuzhou_video table

-- MySQL
ALTER TABLE xuzhou_video ADD COLUMN vid_box_serial VARCHAR(100) NULL DEFAULT NULL COMMENT '所属盒子序列号' AFTER vid_uri;

-- PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE xuzhou_video ADD COLUMN vid_box_serial VARCHAR(100) DEFAULT NULL;
-- COMMENT ON COLUMN xuzhou_video.vid_box_serial IS '所属盒子序列号';
