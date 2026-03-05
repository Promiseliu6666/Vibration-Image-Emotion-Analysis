-- 修改系统对接日志表字段类型脚本
-- 将 request_params、response_data 和 error_msg 字段改为 LONGTEXT 以支持更长的数据

USE your_database_name; -- 请替换为实际的数据库名

-- 修改请求参数字段类型
ALTER TABLE `xuzhou_integration_log` 
MODIFY COLUMN `request_params` LONGTEXT COMMENT '请求参数';

-- 修改响应数据字段类型
ALTER TABLE `xuzhou_integration_log` 
MODIFY COLUMN `response_data` LONGTEXT COMMENT '响应数据';

-- 修改错误信息字段类型
ALTER TABLE `xuzhou_integration_log` 
MODIFY COLUMN `error_msg` LONGTEXT COMMENT '错误信息';

-- 验证修改结果
DESC `xuzhou_integration_log`;

-- 或者使用以下命令查看表结构
-- SHOW CREATE TABLE `xuzhou_integration_log`;