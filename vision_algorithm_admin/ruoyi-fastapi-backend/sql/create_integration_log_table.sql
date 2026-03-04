-- 系统对接日志表创建脚本
-- 用于记录系统间接口调用的详细日志信息

CREATE TABLE IF NOT EXISTS `xuzhou_integration_log` (
  `log_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '日志主键',
  `system_name` varchar(100) DEFAULT '' COMMENT '系统名称',
  `interface_name` varchar(100) DEFAULT '' COMMENT '接口名称',
  `interface_url` varchar(500) DEFAULT '' COMMENT '接口地址',
  `request_method` varchar(10) DEFAULT '' COMMENT '请求方式',
  `request_params` varchar(4000) DEFAULT '' COMMENT '请求参数',
  `response_data` varchar(4000) DEFAULT '' COMMENT '响应数据',
  `status` int(1) DEFAULT 0 COMMENT '请求状态（0成功 1失败）',
  `error_msg` varchar(2000) DEFAULT '' COMMENT '错误信息',
  `request_time` datetime DEFAULT NULL COMMENT '请求时间',
  `response_time` datetime DEFAULT NULL COMMENT '响应时间',
  `cost_time` bigint(20) DEFAULT 0 COMMENT '耗时（毫秒）',
  `request_ip` varchar(128) DEFAULT '' COMMENT '请求IP',
  `user_agent` varchar(500) DEFAULT '' COMMENT '用户代理',
  `trace_id` varchar(64) DEFAULT '' COMMENT '链路追踪ID',
  `remark` varchar(500) DEFAULT '' COMMENT '备注',
  PRIMARY KEY (`log_id`),
  KEY `idx_sys_integration_log_sn` (`system_name`),
  KEY `idx_sys_integration_log_s` (`status`),
  KEY `idx_sys_integration_log_rt` (`request_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='徐州系统对接日志表';

-- 创建分区表（按月分区，提高查询性能）
-- 注意：如果需要分区表，请先删除上面的表，然后执行下面的分区表创建语句
/*
DROP TABLE IF EXISTS `sys_integration_log`;

CREATE TABLE `xuzhou_integration_log` (
  `log_id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '日志主键',
  `title` varchar(50) DEFAULT '' COMMENT '模块标题',
  `system_name` varchar(100) DEFAULT '' COMMENT '系统名称',
  `business_type` int(2) DEFAULT 0 COMMENT '业务类型（0其它 1新增 2修改 3删除）',
  `method` varchar(100) DEFAULT '' COMMENT '方法名称',
  `request_method` varchar(10) DEFAULT '' COMMENT '请求方式',
  `operator_type` int(1) DEFAULT 0 COMMENT '操作类别（0其它 1后台用户 2手机端用户）',
  `operator_name` varchar(50) DEFAULT '' COMMENT '操作人员',
  `dept_name` varchar(50) DEFAULT '' COMMENT '部门名称',
  `operator_url` varchar(255) DEFAULT '' COMMENT '请求URL',
  `operator_ip` varchar(128) DEFAULT '' COMMENT '主机地址',
  `operator_location` varchar(255) DEFAULT '' COMMENT '操作地点',
  `operator_param` varchar(2000) DEFAULT '' COMMENT '请求参数',
  `json_result` varchar(2000) DEFAULT '' COMMENT '返回参数',
  `status` int(1) DEFAULT 0 COMMENT '操作状态（0正常 1异常）',
  `error_msg` varchar(2000) DEFAULT NULL COMMENT '错误消息',
  `cost_time` bigint(20) DEFAULT 0 COMMENT '耗时（毫秒）',
  `oper_time` datetime DEFAULT NULL COMMENT '操作时间',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`log_id`, `create_time`),
  KEY `idx_system_name` (`system_name`),
  KEY `idx_business_type` (`business_type`),
  KEY `idx_status` (`status`),
  KEY `idx_oper_time` (`oper_time`),
  KEY `idx_operator_name` (`operator_name`),
  KEY `idx_title` (`title`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='徐州系统对接日志表'
PARTITION BY RANGE (YEAR(create_time)*100 + MONTH(create_time)) (
    PARTITION p202401 VALUES LESS THAN (202402),
    PARTITION p202402 VALUES LESS THAN (202403),
    PARTITION p202403 VALUES LESS THAN (202404),
    PARTITION p202404 VALUES LESS THAN (202405),
    PARTITION p202405 VALUES LESS THAN (202406),
    PARTITION p202406 VALUES LESS THAN (202407),
    PARTITION p202407 VALUES LESS THAN (202408),
    PARTITION p202408 VALUES LESS THAN (202409),
    PARTITION p202409 VALUES LESS THAN (202410),
    PARTITION p202410 VALUES LESS THAN (202411),
    PARTITION p202411 VALUES LESS THAN (202412),
    PARTITION p202412 VALUES LESS THAN (202501),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
*/

-- 创建定时清理任务（可选）
-- 清理30天前的日志数据
/*
DELIMITER //
CREATE EVENT IF NOT EXISTS `clean_integration_log`
ON SCHEDULE EVERY 1 DAY
STARTS '2024-01-01 02:00:00'
DO
BEGIN
    DELETE FROM xuzhou_integration_log WHERE create_time < DATE_SUB(NOW(), INTERVAL 30 DAY);
END //
DELIMITER ;

-- 启用事件调度器
SET GLOBAL event_scheduler = ON;
*/

-- 插入测试数据（可选）
/*
INSERT INTO `xuzhou_integration_log` (
    `title`, `system_name`, `business_type`, `method`, `request_method`,
    `operator_type`, `operator_name`, `dept_name`, `operator_url`,
    `operator_ip`, `operator_location`, `operator_param`, `json_result`,
    `status`, `error_msg`, `cost_time`, `oper_time`
) VALUES 
(
    '用户信息查询', '用户管理系统', 1, 'get_user_info', 'GET',
    1, 'admin', '系统管理部', '/api/user/123',
    '192.168.1.100', '内网IP', '{"user_id": 123}', '{"code": 200, "data": {"username": "test"}}',
    0, NULL, 150, NOW()
),
(
    '数据同步', '第三方系统', 2, 'sync_data', 'POST',
    0, 'system', '系统', '/api/sync/data',
    '10.0.0.1', '内网IP', '{"data_type": "user", "count": 100}', '{"code": 200, "message": "同步成功"}',
    0, NULL, 2500, NOW()
),
(
    '算法调用失败', 'AI算法系统', 0, 'face_recognition', 'POST',
    1, 'operator', '算法部', '/api/algorithm/face',
    '172.16.0.10', '内网IP', '{"image_id": "img_001"}', NULL,
    1, '算法服务不可用', 5000, NOW()
);
*/

-- 查询统计信息
/*
-- 按系统名称统计调用次数
SELECT system_name, COUNT(*) as call_count, 
       AVG(cost_time) as avg_cost_time,
       SUM(CASE WHEN status = 0 THEN 1 ELSE 0 END) as success_count,
       SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as error_count
FROM xuzhou_integration_log 
WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY system_name
ORDER BY call_count DESC;

-- 按日期统计调用趋势
SELECT DATE(create_time) as call_date, 
       COUNT(*) as total_calls,
       AVG(cost_time) as avg_response_time,
       SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) as error_count
FROM sys_integration_log 
WHERE create_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(create_time)
ORDER BY call_date DESC;

-- 查询耗时最长的接口调用
SELECT title, system_name, method, cost_time, oper_time, operator_url
FROM sys_integration_log 
WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
ORDER BY cost_time DESC
LIMIT 10;
*/