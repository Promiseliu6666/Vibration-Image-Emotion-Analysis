-- Migration: create local_algorithm_run_log table for local algorithm run history

-- MySQL
CREATE TABLE IF NOT EXISTS local_algorithm_run_log (
    id              INT AUTO_INCREMENT PRIMARY KEY     COMMENT '主键',
    vid_id          INT          NOT NULL              COMMENT '摄像头ID',
    algorithm_code  VARCHAR(64)  NOT NULL              COMMENT '算法编码',
    algorithm_name  VARCHAR(128) DEFAULT ''            COMMENT '算法名称',
    status          VARCHAR(32)  NOT NULL DEFAULT 'running' COMMENT 'running/completed/failed/stopped',
    start_time      DATETIME     NOT NULL              COMMENT '启动时间',
    end_time        DATETIME     NULL                  COMMENT '结束时间',
    error_message   VARCHAR(500) NULL                  COMMENT '错误信息',
    create_time     DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_vid_id (vid_id),
    INDEX idx_status (status),
    INDEX idx_start_time (start_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='本地算法运行记录';

-- PostgreSQL (uncomment if using PostgreSQL)
-- CREATE TABLE IF NOT EXISTS local_algorithm_run_log (
--     id              SERIAL PRIMARY KEY,
--     vid_id          INTEGER       NOT NULL,
--     algorithm_code  VARCHAR(64)   NOT NULL,
--     algorithm_name  VARCHAR(128)  DEFAULT '',
--     status          VARCHAR(32)   NOT NULL DEFAULT 'running',
--     start_time      TIMESTAMP     NOT NULL,
--     end_time        TIMESTAMP     NULL,
--     error_message   VARCHAR(500)  NULL,
--     create_time     TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
-- );
-- CREATE INDEX IF NOT EXISTS idx_local_run_vid_id ON local_algorithm_run_log(vid_id);
-- CREATE INDEX IF NOT EXISTS idx_local_run_status ON local_algorithm_run_log(status);
-- CREATE INDEX IF NOT EXISTS idx_local_run_start_time ON local_algorithm_run_log(start_time);
