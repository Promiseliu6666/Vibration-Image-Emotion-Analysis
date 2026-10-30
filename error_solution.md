# 问题总结

## 问题一：PowerShell 中执行带引号路径的 MySQL 命令报错

**错误现象：**

```
表达式或语句中包含意外的标记“-h”
表达式或语句中包含意外的标记“127.0.0.1”
...
```

**原因：** PowerShell 中用双引号包裹可执行文件路径时，会把它当成一个字符串，而不是要执行的命令，后面的参数（`-h`、`-P` 等）被解析为意外标记。

**解决：** 在路径前加调用运算符 `&`，告诉 PowerShell 把该字符串当作命令执行：

```powershell
& "D:\AA_install\mysql-8.0.44-winx64\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u root -p ...
```

**衍生问题：** 命令换行输入（出现 `>>` 续行符）导致 `-u` 与用户名 `root` 被拆成两行，报 `option '-u' requires an argument`。**解决：整条命令必须写在一行内**，`-u` 后紧跟用户名。

---

## 问题二：导入 SQL 文件时的两个错误

### 2.1 数据超长错误

**错误现象：**

```
ERROR 1406 (22001) at line 26 in file: '...ruoyi-fastapi.sql':
Data too long for column 'dept_name' at row 1
```

**原因：** SQL 文件中的数据长度超过了表结构 `dept_name` 字段定义的长度，MySQL 严格模式拒绝截断数据而中断导入。

**解决：** 临时关闭严格模式，让 MySQL 自动截断超长数据后继续导入：

```sql
SET SESSION sql_mode='';
```

（可选）后续如需保留完整数据，可手动加宽字段：

```sql
ALTER TABLE sys_dept MODIFY COLUMN dept_name VARCHAR(100);
```

### 2.2 `source` 命令语法错误

**错误现象：**

```
ERROR 1064 (42000) at line 1: You have an error in your SQL syntax ...
near 'source E:/.../ruoyi-fastapi.sql' at line 1
```

**原因：** `source` 是 MySQL **客户端内部命令**，不是标准 SQL 语句，不能与 `-e` 参数混用。`-e` 后只能跟标准 SQL，客户端无法识别 `source`。

**解决：**

- **方法一（推荐）：用管道重定向导入，同时关闭严格模式：**

```powershell
(Get-Content "E:\...\ruoyi-fastapi.sql" -Raw) | & "D:\...\mysql.exe" -h 127.0.0.1 -P 3306 -u root -p ruoyi_fastapi --init-command="SET SESSION sql_mode=''"
```

- **方法二：先登录 mysql，再在 `mysql>` 提示符下执行 `source`：**

```sql
SET SESSION sql_mode='';
source E:/.../ruoyi-fastapi.sql
```

---

## 核心要点速记

| 问题              | 关键点            | 解决方式                      |
| --------------- | -------------- | ------------------------- |
| PowerShell 路径执行 | 引号路径被当字符串      | 加 `&` 调用运算符               |
| 参数被拆行           | `-u` 与用户名分离    | 整条命令写一行                   |
| Data too long   | 严格模式拒绝截断       | `SET SESSION sql_mode=''` |
| `source` 语法错误   | 客户端命令不能用于 `-e` | 用管道重定向或登录后执行              |

**最终可用的导入命令（一行版）：**

```powershell
(Get-Content "E:\Learning\Binhua\Vibration-Image-Emotion-Analysis-main\ruoyi-fastapi-backend\sql\ruoyi-fastapi.sql" -Raw) | & "D:\AA_install\mysql-8.0.44-winx64\bin\mysql.exe" -h 127.0.0.1 -P 3306 -u root -p ruoyi_fastapi --init-command="SET SESSION sql_mode=''"
```

- 在全新环境中，你原来的创建数据库命令是对的。                                                                                                                 

- 你之前导入时缺少 --default-character-set=utf8mb4，这是乱码的直接原因。                                           

- 既然不需要备份，就要先删除数据库，再重新创建和导入。                                                             
  
                                                               请到 QQ 邮箱网页版：                                                                                               
  
  设置 → 账号 → 开启 POP3/IMAP/SMTP 服务 → 生成授权码                                                                
  
  然后把新生成的 QQ 授权码填入：                                                                                     
  
  MAIL_PASSWORD=新的QQ邮箱授权码         

![](C:\Users\15826\AppData\Roaming\marktext\images\2026-10-29-13-20-17-image.png)

vhitjxlslgddecdd





原因是“本机摄像头”默认选中了索引 1，而电脑上的索引 1 是 vivo办公套件摄像头，不是笔记本的 HP Wide  
Vision HD Camera。因此虽然接口返回 200，画面却不正常。

已修改：

- Vibration-Image-Emotion-Analysis-main/ruoyi-fastapi-backend/hik_vision/hik_vision.py:31 将本机摄像
  头默认索引从 1 改为 0。

- Vibration-Image-Emotion-Analysis-main/ruoyi-fastapi-frontend/src/views/monitor/druid/index.vue:299
  切换到本机摄像头时，不再携带小智设备 ID。

- 后端已重启，前端构建通过。
  
  已验证索引 0 能输出 640×480 画面，单帧为非黑图片。现在回到监控页按 Ctrl + F5，重新选择“本机摄像头”即
  可。若仍无画面，请关闭 vivo 办公套件或其他正在占用摄像头的应用后再试。