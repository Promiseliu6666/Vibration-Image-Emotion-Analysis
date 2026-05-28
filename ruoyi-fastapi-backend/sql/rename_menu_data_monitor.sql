-- Rename menu from 数据监控 to 实时分析
UPDATE sys_menu SET menu_name = '实时分析', remark = '实时分析菜单' WHERE path = 'druid';
