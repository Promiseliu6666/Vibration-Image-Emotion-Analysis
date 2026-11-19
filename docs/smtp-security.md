# SMTP 凭据泄露处置

本次发现：`ruoyi-fastapi-backend/.env.dev` 中的 QQ 邮箱 SMTP 授权码已进入
Git 历史。`.env.prod` 也被跟踪。`.gitignore` 不会自动取消跟踪已提交文件。

## 必须撤销旧授权码

在 QQ 邮箱网页版「设置 → 账户 → POP3/IMAP/SMTP 服务」中撤销泄露的授权码，
必要时关闭后重新开启 SMTP 服务，并确认旧授权码已失效。检查近期发信记录。
删除文件或清理 Git 历史不能使授权码失效。

在本机私有配置或服务器环境变量中填入新授权码，设置 `MAIL_ENABLED=true`，
重启后端。新授权码不要发到聊天、Issue 或提交记录中。

## 私有配置与模板

- `.env.dev` / `.env.prod` 从 Git 索引移除，本机原文件保留。
- 新环境从 `.env.dev.example` / `.env.prod.example` 复制，填写数据库、JWT 等配置。
- 邮件默认关闭；缺少配置不影响模块导入。
- 邮件异常只记录异常类型，避免校验错误或 SMTP 错误将密钥写入日志。
- CI 运行 `python scripts/check_smtp_secrets.py` 检查当前受跟踪的配置及 Python 文件。
  这是针对 SMTP 的检查，不是全类型密钥扫描，也不代表旧历史已清理。

## 历史清理需要单独操作

修复提交保留旧历史。所有旧分支、标签、拉取请求缓存、克隆或分叉都可能仍有副本。
先撤销授权码，再协调协作者暂停推送，确认需要重写的远端分支和标签。

在单独的受控镜像副本中使用 `git-filter-repo` 移除这两个路径：

```text
git filter-repo --sensitive-data-removal --invert-paths --path ruoyi-fastapi-backend/.env.dev --path ruoyi-fastapi-backend/.env.prod
```

重写会改变提交 SHA。检查所有分支和标签，确认没有其他泄露副本后，使用明确的
远端旧 SHA 和 `--force-with-lease` 逐一更新相关引用。不要对未知的新提交强推，
也不要直接 `push --mirror`，避免删除不相关引用。协作者随后应重新克隆，
防止从旧克隆把敏感历史重新推回仓库。必要时联系 GitHub 支持清理缓存引用。

这两个私有文件还包含其他服务的配置；其中如使用真实密码或 API 密钥，也应逐项更换。
