<template>
  <div class="app-container cache-monitor">
    <el-row :gutter="24">
      <!-- 基本信息 -->
      <el-col :span="24">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><Monitor /></el-icon>
              <span>基本信息</span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="Redis版本">{{ cache.info?.redis_version ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="运行模式">{{ cache.info?.redis_mode === 'standalone' ? '单机' : '集群' }}</el-descriptions-item>
            <el-descriptions-item label="端口">{{ cache.info?.tcp_port ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="客户端数">{{ cache.info?.connected_clients ?? '-' }}</el-descriptions-item>

            <el-descriptions-item label="运行时间(天)">{{ cache.info?.uptime_in_days ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="使用内存">{{ cache.info?.used_memory_human ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="使用CPU">{{ cache.info ? parseFloat(cache.info.used_cpu_user_children).toFixed(2) : '-' }}</el-descriptions-item>
            <el-descriptions-item label="内存配置">{{ cache.info?.maxmemory_human ?? '-' }}</el-descriptions-item>

            <el-descriptions-item label="AOF是否开启">{{ cache.info?.aof_enabled === '0' ? '否' : '是' }}</el-descriptions-item>
            <el-descriptions-item label="RDB是否成功">{{ cache.info?.rdb_last_bgsave_status ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="Key数量">{{ cache.dbSize ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="网络入口/出口">{{ cache.info ? `${cache.info.instantaneous_input_kbps}kps / ${cache.info.instantaneous_output_kbps}kps` : '-' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <!-- 命令统计 -->
      <el-col :span="12">
        <el-card shadow="never" class="info-card chart-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><PieChart /></el-icon>
              <span>命令统计</span>
            </div>
          </template>
          <div ref="commandstats" class="chart-container" />
        </el-card>
      </el-col>

      <!-- 内存信息 -->
      <el-col :span="12">
        <el-card shadow="never" class="info-card chart-card">
          <template #header>
            <div class="card-header-title">
              <el-icon><Odometer /></el-icon>
              <span>内存信息</span>
            </div>
          </template>
          <div ref="usedmemory" class="chart-container" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="Cache">
import { getCache } from '@/api/monitor/cache';
import * as echarts from 'echarts';

const cache = ref([]);
const commandstats = ref(null);
const usedmemory = ref(null);
const { proxy } = getCurrentInstance();

function getList() {
  proxy.$modal.loading("正在加载缓存监控数据，请稍候！");
  getCache().then(response => {
    proxy.$modal.closeLoading();
    cache.value = response.data;

    const commandstatsIntance = echarts.init(commandstats.value, "macarons");
    commandstatsIntance.setOption({
      tooltip: {
        trigger: "item",
        formatter: "{a} <br/>{b} : {c} ({d}%)"
      },
      series: [
        {
          name: "命令",
          type: "pie",
          roseType: "radius",
          radius: [15, 95],
          center: ["50%", "38%"],
          data: response.data.commandStats,
          animationEasing: "cubicInOut",
          animationDuration: 1000
        }
      ]
    });
    const usedmemoryInstance = echarts.init(usedmemory.value, "macarons");
    usedmemoryInstance.setOption({
      tooltip: {
        formatter: "{b} <br/>{a} : " + cache.value.info.used_memory_human
      },
      series: [
        {
          name: "峰值",
          type: "gauge",
          min: 0,
          max: 1000,
          detail: {
            formatter: cache.value.info.used_memory_human
          },
          data: [
            {
              value: parseFloat(cache.value.info.used_memory_human),
              name: "内存消耗"
            }
          ]
        }
      ]
    })
    window.addEventListener("resize", () => {
      commandstatsIntance.resize();
      usedmemoryInstance.resize();
    });
  })
}

getList();
</script>
<style lang="scss" scoped>
  .cache-monitor {
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
  
    /* 标签列：稍深的颜色，突出层次 */
    :deep(.el-descriptions__label) {
      background: rgba(102, 126, 234, 0.08);
      font-weight: 600;
      color: var(--el-text-color-primary);
      width: 140px;
    }
  
    /* 内容文字：与表格、其他组件完全一致，使用标准正文颜色变量 */
    :deep(.el-descriptions__content) {
      color: var(--el-text-color-regular) !important;
    }
  }
  
  .chart-card {
    .chart-container {
      width: 100%;
      height: 420px;
    }
  }
  
  /* 可选增强：暗模式下让 ECharts 图表文字也更清晰（如果使用 macarons 主题不够亮） */
  html.dark {
    /* 如果发现图表文字在暗模式下偏暗，可以强制提亮（大多数情况下 macarons 主题已适配好） */
    // 可根据实际效果决定是否保留下面这行
    // :deep(.echarts-text) {
    //   color: #e5e7eb !important;
    // }
  }
  </style>