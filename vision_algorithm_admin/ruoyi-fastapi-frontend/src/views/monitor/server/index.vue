<template>
  <div class="app-container server-monitor">
    <el-row :gutter="24">
      <!-- CPU 卡片 -->
      <el-col :span="12">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><Cpu /></el-icon>
              <span>CPU</span>
            </div>
          </template>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="核心数">{{ server.cpu?.cpuNum ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="当前空闲率">{{ server.cpu?.free ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="用户使用率">{{ server.cpu?.used ?? '-' }}%</el-descriptions-item>
            <el-descriptions-item label="系统使用率">{{ server.cpu?.sys ?? '-' }}%</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 内存卡片 -->
      <el-col :span="12">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><Tickets /></el-icon>
              <span>内存</span>
            </div>
          </template>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="属性" label-align="center" align="center" />
            <el-descriptions-item label="系统内存" align="center">{{ server.mem?.total ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Python内存" align="center">{{ server.py?.total ?? '-' }}</el-descriptions-item>

            <el-descriptions-item label="已用内存">{{ server.mem?.used ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="已用内存">{{ server.py?.used ?? '-' }}</el-descriptions-item>

            <el-descriptions-item label="剩余内存">{{ server.mem?.free ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="剩余内存">{{ server.py?.free ?? '-' }}</el-descriptions-item>

            <el-descriptions-item label="使用率">
              <span :class="{ 'text-danger': server.mem?.usage > 80 }">{{ server.mem?.usage ?? '-' }}%</span>
            </el-descriptions-item>
            <el-descriptions-item label="使用率">
              <span :class="{ 'text-danger': server.py?.usage > 80 }">{{ server.py?.usage ?? '-' }}%</span>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 服务器信息 -->
      <el-col :span="24">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><Monitor /></el-icon>
              <span>服务器信息</span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="服务器名称">{{ server.sys?.computerName ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="服务器IP">{{ server.sys?.computerIp ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="操作系统">{{ server.sys?.osName ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="系统架构">{{ server.sys?.osArch ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- Python解释器信息 -->
      <el-col :span="24">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><CoffeeCup /></el-icon>
              <span>Python解释器信息</span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="Python名称">{{ server.py?.name ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Python版本">{{ server.py?.version ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="启动时间">{{ server.py?.startTime ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="运行时长">{{ server.py?.runTime ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="安装路径" :span="2">{{ server.py?.home ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="项目路径" :span="2">{{ server.sys?.userDir ?? '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 磁盘状态 -->
      <el-col :span="24">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><MessageBox /></el-icon>
              <span>磁盘状态</span>
            </div>
          </template>
          <el-table :data="server.sysFiles" style="width: 100%" :row-style="{ height: '60px' }">
            <el-table-column prop="dirName" label="盘符路径" min-width="120" show-overflow-tooltip />
            <el-table-column prop="sysTypeName" label="文件系统" width="120" />
            <el-table-column prop="typeName" label="盘符名称" width="140" show-overflow-tooltip />
            <el-table-column prop="total" label="总大小" width="140" />
            <el-table-column prop="free" label="可用大小" width="140" />
            <el-table-column prop="used" label="已用大小" width="140" />
            <el-table-column label="已用百分比" width="140" align="center">
              <template #default="scope">
                <span :class="{ 'text-danger': scope.row.usage > 80 }">{{ scope.row.usage }}%</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { getServer } from '@/api/monitor/server'

const server = ref([]);
const { proxy } = getCurrentInstance();

function getList() {
  proxy.$modal.loading("正在加载服务监控数据，请稍候！");
  getServer().then(response => {
    server.value = response.data;
    proxy.$modal.closeLoading();
  });
}

getList();
</script>
<style lang="scss" scoped>
  .server-monitor {
    padding: 20px;
    background: linear-gradient(to bottom, #f8fbff, #eef2f7);
    min-height: 100vh;
    background: var(--el-bg-color-page) !important;
  }
  
  .info-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    overflow: hidden;
    margin-bottom: 24px;
  
    :deep(.el-card__header) {
      background: linear-gradient(120deg, #667eea, #764ba2);
      color: #fff;
      padding: 18px 24px;
      font-size: 18px;
      font-weight: 600;
    }
  
    .card-header-title {
      display: flex;
      align-items: center;
      gap: 12px;
    }
  
    :deep(.el-descriptions__label) {
      background: rgba(102, 126, 234, 0.08);
      font-weight: 600;
      color: var(--el-text-color-primary); // 使用主题变量，自动适配亮/暗
      width: 140px;
    }
  
    // 删除这行！不要手动硬编码颜色
    // :deep(.el-descriptions__content) { color: #606266; }
  
    // 让 descriptions 内容也使用标准文字颜色（与表格一致）
    :deep(.el-descriptions__content) {
      color: var(--el-text-color-regular) !important; // 与 el-table 内容文字完全一致
    }
  
    .text-danger {
      color: #f56c6c;
      font-weight: 600;
    }
  }
  
  :deep(.el-table) {
    th.el-table__cell {
      background: #409eff;
      color: #fff;
      font-weight: 600;
      font-size: 15px;
      height: 56px;
    }
  
    td.el-table__cell {
      height: 60px;
      // 不设置 color，让它使用默认 var(--el-text-color-regular)
    }
  
    .el-table__row:hover {
      background: rgba(102, 126, 234, 0.06);
    }
  }
  
  // 可选：暗模式下稍微增强悬浮效果（更明显）
  html.dark {
    :deep(.el-table__row:hover) {
      background: rgba(102, 126, 234, 0.16) !important;
    }
  
    .info-card .text-danger {
      color: #ff6b6b !important; // 暗模式下红色更亮眼
    }
  }
  </style>