# binhua_box

盒子端服务，负责摄像头拉流、算法推理、结果回传。

## 启动

```bash
cd ~/binhua_box
set -a
source box.env
set +a
python3 main.py
```

> `set -a` 确保 `box.env` 中的变量自动导出为环境变量，供 Python 进程读取。
