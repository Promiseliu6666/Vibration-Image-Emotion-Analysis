<template>
  <div class="app-container dashboard-monitor">
    <!-- 数据总览统计卡片组 -->
    <div class="stats-grid">
      <div class="stat-card">
        <el-image :src="home1Image" class="stat-icon" />
        <div class="stat-info">
          <div class="stat-number">{{ statistics.alg_count }}</div>
          <div class="stat-label">算法数量</div>
        </div>
      </div>
      <div class="stat-card">
        <el-image :src="home2Image" class="stat-icon" />
        <div class="stat-info">
          <div class="stat-number">{{ statistics.scene_count }}</div>
          <div class="stat-label">应用场景</div>
        </div>
      </div>
      <div class="stat-card">
        <el-image :src="home3Image" class="stat-icon" />
        <div class="stat-info">
          <div class="stat-number">{{ statistics.video_count }}</div>
          <div class="stat-label">视频数量</div>
        </div>
      </div>
      <div class="stat-card">
        <el-image :src="home4Image" class="stat-icon" />
        <div class="stat-info">
          <div class="stat-number">{{ statistics.video_stream_count }}</div>
          <div class="stat-label">累计使用数量</div>
        </div>
      </div>
    </div>

    <!-- 算法调用统计 TOP10 -->
    <el-card shadow="never" class="chart-card mb20">
      <template #header>
        <div class="card-header-title">
          <el-icon><PieChart /></el-icon>
          <span>算法调用统计 TOP10</span>
        </div>
      </template>
      <div ref="chartRef1" class="chart-container" />
    </el-card>

    <!-- 场景调用统计 TOP10 -->
    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header-title">
          <el-icon><Odometer /></el-icon>
          <span>场景调用统计 TOP10</span>
        </div>
      </template>
      <div ref="chartRef2" class="chart-container" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { getStatistics, getCharts } from '@/api/xuzhou/algorithm'
import home1Image from '@/assets/images/home1.png'
import home2Image from '@/assets/images/home2.png'
import home3Image from '@/assets/images/home3.png'
import home4Image from '@/assets/images/home4.png'

const chartRef1 = ref(null)
const chartRef2 = ref(null)

// 统计数据
const statistics = ref({
  alg_count: 0,
  scene_count: 0,
  video_count: 0,
  video_stream_count: 0
})

// 图表数据
const charts = ref({
  top10_scene: [],
  top10_alg: []
})

const initChart1 = () => {
  const chart = echarts.init(chartRef1.value)
  const algNames = charts.value.top10_alg.map(item => item[0])
  const algCounts = charts.value.top10_alg.map(item => item[1])
  
  const option = {
    title: {
      left: 'center',
      textStyle: {
        fontSize: 14,
        color: '#141414'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: algNames.length > 0 ? algNames : ['暂无数据'],
      axisLabel: {
        rotate: 30,
        fontSize: 12
      }
    },
    yAxis: {
      type: 'value',
      name: '调用次数'
    },
    series: [{
      name: '调用次数',
      type: 'bar',
      data: algCounts.length > 0 ? algCounts : [0],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#83bff6' },
          { offset: 0.5, color: '#188df0' },
          { offset: 1, color: '#188df0' }
        ])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#2378f7' },
            { offset: 0.7, color: '#2378f7' },
            { offset: 1, color: '#83bff6' }
          ])
        }
      }
    }]
  }
  chart.setOption(option)
  
  // 响应式处理
  window.addEventListener('resize', () => {
    chart.resize()
  })
}

const initChart2 = () => {
  const chart = echarts.init(chartRef2.value)
  const sceneNames = charts.value.top10_scene.map(item => item[0])
  const sceneCounts = charts.value.top10_scene.map(item => item[1])
  
  const option = {
    title: {
      left: 'center',
      textStyle: {
        fontSize: 14,
        color: '#141414'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: sceneNames.length > 0 ? sceneNames : ['暂无数据'],
      axisLabel: {
        rotate: 0,
        fontSize: 10
      }
    },
    yAxis: {
      type: 'value',
      name: '调用次数'
    },
    series: [{
      name: '调用次数',
      type: 'line',
      data: sceneCounts.length > 0 ? sceneCounts : [0],
      smooth: true,
      lineStyle: {
        width: 3,
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(128, 255, 165)' },
          { offset: 1, color: 'rgba(1, 191, 236)' }
        ])
      },
      areaStyle: {
        opacity: 0.8,
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(128, 255, 165)' },
          { offset: 1, color: 'rgba(1, 191, 236)' }
        ])
      },
      symbol: 'circle',
      symbolSize: 6,
      emphasis: {
        focus: 'series'
      }
    }]
  }
  chart.setOption(option)
  
  // 响应式处理
  window.addEventListener('resize', () => {
    chart.resize()
  })
}

// 获取统计数据
const fetchStatistics = async () => {
  try {
    const response = await getStatistics()
    if (response.code === 200) {
      statistics.value = response.data
    }
  } catch (error) {
    console.error('获取统计数据失败:', error)
  }
  
  try {
    const response = await getCharts()
    if (response.code === 200) {
      charts.value = response.data
      // 数据获取成功后重新初始化图表
      initChart1()
      initChart2()
    }
  } catch (error) {
    console.error('获取图表数据失败:', error)
  }
}

onMounted(() => {
  fetchStatistics()
  initChart1()
  initChart2()
})
</script>

<style lang="scss" scoped>
  .dashboard-monitor {
    padding: 20px;
    background: linear-gradient(to bottom, #f8fbff, #eef2f7);
    min-height: 100vh;
    background: var(--el-bg-color-page) !important;
  }
  
  /* 统计卡片网格 */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    margin-bottom: 24px;
  }
  
  .stat-card {
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    padding: 24px;
    display: flex;
    align-items: center;
    transition: all 0.3s;
    background: var(--el-bg-color-page) !important;
  
    &:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
    }
  
    .stat-icon {
      width: 60px;
      height: 60px;
      margin-right: 24px;
    }
  
    .stat-info {
      .stat-number {
        font-size: 32px;
        font-weight: 600;
        color: #303133;
        line-height: 1.2;
      }
  
      .stat-label {
        font-size: 15px;
        color: #909399;
        margin-top: 8px;
      }
    }
  }
  
  /* 图表卡片 */
  .chart-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    overflow: hidden;
  
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
  
    .chart-container {
      width: 100%;
      height: 460px;
      padding: 20px 0;
    }
  }
  </style>