-- Migration: add box_serial column to binhua_analysis table
-- Enables the server to proxy analysis video from the correct box

-- MySQL
ALTER TABLE binhua_analysis ADD COLUMN box_serial VARCHAR(100) NULL DEFAULT NULL COMMENT '所属盒子序列号' AFTER video_path;

-- PostgreSQL (uncomment if using PostgreSQL)
-- ALTER TABLE binhua_analysis ADD COLUMN box_serial VARCHAR(100) DEFAULT NULL;
-- COMMENT ON COLUMN binhua_analysis.box_serial IS '所属盒子序列号';
