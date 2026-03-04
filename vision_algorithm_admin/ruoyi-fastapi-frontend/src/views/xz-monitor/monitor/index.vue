<template>
  <div class="app-container">
    <!-- 统计信息卡片 -->
    <el-row :gutter="20" class="mb4">
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoCamera /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">总视频数</div>
              <div class="stat-value">{{ total }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoPlay /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">运行中</div>
              <div class="stat-value">{{ runningCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon">
              <el-icon><VideoPause /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-title">未运行</div>
              <div class="stat-value">{{ stoppedCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 搜索表单 -->
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="视频名称" prop="vidName">
        <el-input
          v-model="queryParams.vidName"
          placeholder="请输入视频名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="视频编码" prop="vidSerial">
        <el-input
          v-model="queryParams.vidSerial"
          placeholder="请输入视频编码"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="视频类型" prop="vidType">
        <el-input
          v-model="queryParams.vidType"
          placeholder="请输入视频类型"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="场景名称" prop="vidSceneName">
        <el-input
          v-model="queryParams.vidSceneName"
          placeholder="请输入场景名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 工具栏 -->
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="info"
          plain
          icon="Search"
          size="mini"
          @click="toggleSearch"
        >搜索</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="View"
          :disabled="selectedVideos.length === 0 || openedWindows.length >= 4"
          @click="handleBatchView"
        >批量查看 ({{ selectedVideos.length }}/4)</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <!-- 表格数据 -->
    <el-table ref="multipleTableRef" v-loading="loading" :data="videoList" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="55" align="center" />
          <el-table-column label="视频ID" align="center" prop="vidId" />
      <el-table-column label="视频名称" align="center" prop="vidName" :show-overflow-tooltip="true" />
      <el-table-column label="视频序列号" align="center" prop="vidSerial" :show-overflow-tooltip="true" />
      <el-table-column label="视频类型" align="center" prop="vidType" :show-overflow-tooltip="true" />
      <el-table-column label="场景名称" align="center" prop="vidSceneName" :show-overflow-tooltip="true" />
      <el-table-column label="算法名称" align="center" prop="vidAlgorithmName" :show-overflow-tooltip="true" />
      <el-table-column label="运行状态" align="center" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.isRunning ? 'success' : 'info'">
            {{ scope.row.isRunning ? '运行中' : '未运行' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="vidUpdateTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.vidUpdateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="handleView(scope.row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页组件 -->
    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 查看弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      :title="`监控详情 - ${currentVideo.vidName}`"
      width="90%"
      top="5vh"
      @close="closeViewDialog"
      :close-on-press-escape="false"
    >
      <div class="monitor-detail">
        <!-- 视频区域 -->
        <div class="video-section">
          <h3>视频监控</h3>
          <div 
            class="video-grid"
            :class="{
              'single': videoStreams.length === 1,
              'double': videoStreams.length === 2,
              'triple': videoStreams.length === 3,
              'quad': videoStreams.length === 4
            }"
          >
            <div 
              v-for="(stream, index) in videoStreams" 
              :key="stream.id"
              class="video-item"
            >
              <div class="video-header">
                <span class="video-title">{{ stream.name }}</span>
                <span class="video-status online">在线</span>
              </div>
              <div class="video-container single-video">
                 <!-- 推流视频元素 -->
                 <video 
                   :ref="el => { if (el) liveVideoRefs[index] = el }"
                   class="video-player"
                   controls
                   muted
                   style="display: block;"
                 >
                   您的浏览器不支持视频播放
                 </video>
                 <div class="video-placeholder" v-show="videoLoading[index]">
                   <el-icon size="48"><VideoCamera /></el-icon>
                   <p>视频加载中...</p>
                 </div>
               </div>
            </div>
          </div>
        </div>

        <!-- 消息记录区域 -->
        <div class="message-section">
          <h3>消息记录</h3>
          <div class="message-list">
            <div 
              v-for="message in cacheMessages" 
              :key="message.track_id"
              class="message-item"
            >
              <div class="message-content">
                <div class="message-image">
                  <el-image 
                    :src="'data:image/jpeg;base64,' + message.image"
                    fit="cover"
                    style="width: 120px; height: 80px;"
                    :preview-src-list="['data:image/jpeg;base64,' + message.image]"
                  >
                    <template #error>
                      <div class="image-slot">
                        <el-icon><Picture /></el-icon>
                      </div>
                    </template>
                  </el-image>
                </div>
                <div class="message-info">
                  <div class="message-time">
                    <el-icon><Clock /></el-icon>
                    {{ message.timeStr }}
                  </div>
                  <div>{{ '预警编码：' + message.code }}<span v-if="algorithmDict[message.code]">（{{ getAlgorithmName(message.code) }}）</span></div>
                  <div v-if="message.plate">{{ '预警车牌：' + message.plate }}</div>
                  <div >{{ 'ID: ' + message.track_id }}</div>
                  <div v-if="message.human_attributes" class="attributes">
                    <el-tag v-for="value in message.human_attributes" :key="value">{{ filter_attributes(value) }}</el-tag>
                  </div>
                  <div v-if="message.vehicle_attributes" class="attributes">
                    <el-tag v-for="(value, index) in message.vehicle_attributes" :key="index">{{ filter_attributes(value) }}</el-tag>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <!-- 预警消息分页 -->
          <pagination
            v-show="alarmTotal > 0"
            :total="alarmTotal"
            v-model:page="alarmQueryParams.pageNum"
            v-model:limit="alarmQueryParams.pageSize"
            layout="total, prev, pager, next"
            @pagination="loadVideoAlarms"
          />
        </div>
      </div>
    </el-dialog>

    <!-- 批量查看弹窗 -->
    <el-dialog
      v-for="windowData in batchViewDialogs"
      class="batch-view-dialog"
      :key="windowData.id"
      v-model="windowData.visible"
      :title="`批量监控查看 - ${windowData.videoStreams.length}路视频`"
      width="90%"
      top="5vh"
      :data-window-id="windowData.id"
      @close="closeBatchViewDialog(windowData.id)"
      :close-on-press-escape="false"
    >
      <div class="batch-monitor-detail">
        <!-- 视频区域 -->
        <div class="video-section">
          <div class="dashboard-chart-title">实时监控 - {{ windowData.videoStreams.length }}路视频</div>
          <div 
            class="video-grid"
            :class="{
              'single': windowData.videoStreams.length === 1,
              'double': windowData.videoStreams.length === 2,
              'triple': windowData.videoStreams.length === 3,
              'quad': windowData.videoStreams.length === 4
            }"
          >
            <div 
              v-for="(stream, index) in windowData.videoStreams" 
              :key="stream.id"
              class="video-item"
            >
              <div class="video-header">
                <span class="video-title">{{ stream.name }}</span>
                <span class="video-status online">在线</span>
              </div>
              <div class="video-container">
                <video 
                  :id="`batchVideo-${windowData.id}-${index}`"
                  class="video-player live-video"
                  controls
                  muted
                  style="display: block;"
                >
                  您的浏览器不支持视频播放
                </video>
                <div class="video-placeholder" v-show="windowData.videoLoading[index]">
                  <el-icon size="48"><VideoCamera /></el-icon>
                  <p>视频加载中...</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup name="Monitor">
import { ref, reactive, toRefs, getCurrentInstance, nextTick, watch, onUnmounted, onMounted } from 'vue'
import { listVideo, pushVideoConfig } from '@/api/xuzhou/video'
import { getCacheMessages } from '@/api/xuzhou/monitor'
import { getAlarmList } from '@/api/xuzhou/alarm'
import { listAlgorithm } from '@/api/xuzhou/algorithm'
import { parseTime } from '@/utils/ruoyi'
import { VideoCamera, VideoPlay, VideoPause, Clock, Picture, View } from '@element-plus/icons-vue'
import flvjs from 'flv.js'

const { proxy } = getCurrentInstance();

// 算法字典：key为算法编号(algSerial)，value为算法名称(algName)
const algorithmDict = ref({});
async function loadAlgorithmDict() {
  try {
    const params = { pageNum: 1, pageSize: 9999 };
    const response = await listAlgorithm(params);
    const dict = {};
    (response.rows || []).forEach(item => {
      const key = item.algSerial ?? item.alg_serial ?? item.serial ?? item.algCode ?? item.code;
      const name = item.algName ?? item.alg_name ?? item.name;
      if (key != null && name != null) {
        dict[key] = name;
      }
    });
    algorithmDict.value = dict;
  } catch (e) {
    console.warn('加载算法字典失败', e);
  }
}
function getAlgorithmName(code) {
  return algorithmDict.value[code] || code;
}

const videoList = ref([]);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const runningCount = ref(0);
const stoppedCount = ref(0);

// 定时器相关
const publish_path = ref('default_publish_path'); // 可以根据实际需要设置
const cacheTimer = ref(null);
const cacheMessages = ref([]);
const alarmTimer = ref(null);

// 预警消息分页参数
const alarmQueryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  vidId: null
});
const alarmTotal = ref(0);

const data = reactive({
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    vidName: undefined,
    vidSerial: undefined,
    vidType: undefined,
    vidSceneName: undefined
  }
});

const { queryParams } = toRefs(data);

/** 查询视频列表 */
function getList() {
  loading.value = true;
  listVideo(queryParams.value).then(response => {
    videoList.value = response.rows;
    total.value = response.total;
    runningCount.value = response.runningCount || 0;
    stoppedCount.value = response.stoppedCount || 0;
    loading.value = false;
  }).catch(() => {
    loading.value = false;
  });
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}

function filter_attributes(message) {
  const match = message.match(/\(([^)]+)\)/);
  if (match) {
    return match[1];
  }
  return '';
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 切换搜索显示 */
function toggleSearch() {
  showSearch.value = !showSearch.value;
}

/** 选择条数  */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.vidId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
  selectedVideos.value = selection;
}

/** 加载视频预警列表 */
async function loadVideoAlarms(vidId) {
  if (vidId && typeof vidId !== 'object') {
    alarmQueryParams.vidId = vidId;
    alarmQueryParams.pageNum = 1;
  }

  try {
    const res = await getAlarmList({
      vid_id: alarmQueryParams.vidId,
      page_num: alarmQueryParams.pageNum,
      page_size: alarmQueryParams.pageSize
    });
    
    if (res.code === 200) {
      alarmTotal.value = res.total;
      cacheMessages.value = res.rows.map(item => {
        let image = '';
        try {
            const imgStr = item.alarm_image || item.alarmImage
            const processImage = (img) => {
                if (img && !img.startsWith('http') && !img.startsWith('/') && !img.startsWith('data:image')) {
                    return img.replace(/[\r\n\s]+/g, '')
                }
                return img
            }

            if (imgStr) {
                try {
                    const parsed = JSON.parse(imgStr)
                    if (Array.isArray(parsed)) {
                        image = parsed.length > 0 ? processImage(parsed[0]) : ''
                    } else if (typeof parsed === 'string') {
                        image = processImage(parsed)
                    }
                } catch (jsonError) {
                    image = processImage(imgStr)
                }
            }
        } catch (e) {
            console.error('解析图片流程异常', e)
        }
        
        let content = {};
        try {
            const contentStr = item.alarm_content || item.alarmContent
            if (contentStr) {
                content = JSON.parse(contentStr)
            }
        } catch (e) {
             console.error('解析内容失败', e)
        }

        return {
          track_id: item.alarm_id || item.alarmId,
          timeStr: item.alarm_time || item.alarmTime,
          code: item.alarm_code || item.alarmCode,
          image: image,
          plate: content.plate || content.plate_number,
          human_attributes: content.human_attributes,
          vehicle_attributes: content.vehicle_attributes
        };
      });
    }
  } catch (error) {
    console.error('获取视频预警列表失败', error);
  }
}

/** 查看按钮操作 */
function handleView(row) {
  currentVideo.value = row;
  cacheMessages.value = [];
  
  // 调用推送视频配置接口获取视频流地址
  pushVideoConfig(row.vidId).then(response => {
    console.log('视频配置推送成功:', response);
    proxy.$modal.msgSuccess('视频配置推送成功');

    publish_path.value = response.data.publish_path;
    
    // 使用接口返回的srs_flv_url作为视频播放地址
    const streamUrl = response.data?.srs_flv_url?.trim() || `http://localhost:8080/live/${row.vidId}.flv`;
    videoStreams.value = [
      { id: 1, name: row.vidName, url: streamUrl }
    ];
    
    // 初始化加载状态
    videoLoading.value = [true];
    
    // 接口调用成功后再打开弹窗
    viewDialogVisible.value = true;
    
    // 等待弹窗渲染完成后初始化视频播放器
    nextTick(() => {
      initVideoPlayers();
      // startCacheTimer();
      loadVideoAlarms(row.vidId);
      startAlarmTimer();
    });
  }).catch(error => {
    console.error('视频配置推送失败:', error);
    proxy.$modal.msgError('视频配置推送失败');
    
    // 失败时使用默认地址并打开弹窗
    videoStreams.value = [
      { id: 1, name: row.vidName, url: `http://localhost:8080/live/${row.vidId}.flv` }
    ];
    
    // 初始化加载状态
    videoLoading.value = [true];
    
    viewDialogVisible.value = true;
    
    // 等待弹窗渲染完成后初始化视频播放器
    nextTick(() => {
      initVideoPlayers();
      loadVideoAlarms(row.vidId);
      startAlarmTimer();
    });
  });
  
  // 模拟消息记录数据
  messageRecords.value = [];
}

// 查看弹窗相关
const viewDialogVisible = ref(false);
const currentVideo = ref({});
const videoStreams = ref([]);
const messageRecords = ref([]);
const flvPlayers = ref([]);
const liveVideoRefs = ref([]);    // 推流视频元素引用
const videoLoading = ref([]); // 控制视频加载状态

// 批量查看相关
const selectedVideos = ref([]);
const openedWindows = ref([]);
const batchViewDialogs = ref([]);

/** 初始化视频播放器 */
function initVideoPlayers() {
  if (!flvjs.isSupported()) {
    proxy.$modal.msgError('当前浏览器不支持FLV播放');
    return;
  }
  
  // 清理现有播放器
  flvPlayers.value.forEach(player => {
    if (player) {
      player.destroy();
    }
  });
  flvPlayers.value = [];
  
  // 为每个视频流创建播放器
  videoStreams.value.forEach((stream, index) => {
    const liveVideoElement = liveVideoRefs.value[index];
    
    if (liveVideoElement && stream.url) {
      videoLoading.value[index] = true;
      try {
        // 创建FLV播放器用于播放真实流，禁用自动重连
        // 检查是否已存在播放器实例，避免重复创建
        if (flvPlayers.value[index]) {
          console.log(`主视频播放器已存在 [${stream.name}]，先销毁旧播放器`);
          try {
            flvPlayers.value[index].pause();
            flvPlayers.value[index].destroy();
            flvPlayers.value[index] = null;
          } catch (e) {
            console.warn('销毁旧主播放器时出错:', e);
          }
        }
        
        // 清空视频元素的内容，避免残留
        liveVideoElement.src = '';
        liveVideoElement.load && liveVideoElement.load();
        
        const player = flvjs.createPlayer({
          type: 'flv',
          url: stream.url
        }, {
          enableWorker: false,
          enableStashBuffer: false,
          stashInitialSize: 128,
          lazyLoad: false,
          lazyLoadMaxDuration: 0,
          deferLoadAfterSourceOpen: false,
          autoCleanupSourceBuffer: true,
          autoCleanupMaxBackwardDuration: 30,
          autoCleanupMinBackwardDuration: 10,
          // 禁用自动重连
          isLive: true,
          liveBufferLatencyChasing: false,
          liveBufferLatencyMaxLatency: 0,
          liveBufferLatencyMinRemain: 0
        });
        
        player.attachMediaElement(liveVideoElement);
        player.load();
        
        // 添加错误处理 - 禁用自动重连
        player.on(flvjs.Events.ERROR, (errorType, errorDetail) => {
          console.error('FLV播放器错误:', errorType, errorDetail);
          proxy.$modal.msgError(`视频播放失败: ${stream.name}`);
          // 出错时隐藏加载提示
          videoLoading.value[index] = false;
          
          // 禁用自动重连，直接销毁播放器
          try {
            player.pause();
            player.destroy();
          } catch (e) {
            console.warn('销毁播放器时出错:', e);
          }
          
          // 从数组中移除该播放器
          flvPlayers.value[index] = null;
        });
        
        // 监听视频加载完成事件
        player.on(flvjs.Events.METADATA_ARRIVED, () => {
          console.log(`视频加载完成: ${stream.name}`);
          videoLoading.value[index] = false;
        });
        
        // 尝试播放推流视频
        player.play().catch(error => {
          console.warn('推流视频播放失败:', error);
        });
        
        flvPlayers.value[index] = player;
        console.log(`视频播放器初始化成功: ${stream.name}, URL: ${stream.url}`);
        
        // 添加超时处理，30秒后如果视频还没加载完成，则停止加载
        setTimeout(() => {
          if (videoLoading.value[index]) {
            console.log(`主视频加载超时 [${stream.name}]，停止加载`);
            videoLoading.value[index] = false;
            
            // 销毁对应的播放器
            if (flvPlayers.value[index]) {
              try {
                flvPlayers.value[index].pause();
                flvPlayers.value[index].destroy();
                flvPlayers.value[index] = null;
              } catch (error) {
                console.warn('超时销毁主播放器时出错:', error);
              }
            }
          }
        }, 30000);
        
      } catch (error) {
        console.error('创建FLV播放器失败:', error);
        proxy.$modal.msgError(`创建视频播放器失败: ${stream.name}`);
        // 出错时隐藏加载提示
        videoLoading.value[index] = false;
      }
    }
  });
}

/** 关闭查看弹窗 */
function closeViewDialog() {
  viewDialogVisible.value = false;
  stopCacheTimer();
  stopAlarmTimer();
  // 清理视频播放器
  flvPlayers.value.forEach(player => {
    if (player) {
      try {
        player.pause();
        player.destroy();
      } catch (error) {
        console.warn('清理播放器时出错:', error);
      }
    }
  });
  
  flvPlayers.value = [];
  liveVideoRefs.value = [];
  videoLoading.value = []; // 重置加载状态
}

/** 批量查看按钮操作 */
function handleBatchView() {
  if (selectedVideos.value.length === 0) {
    proxy.$modal.msgWarning('请选择要查看的监控点');
    return;
  }
  
  // 计算可以打开的视频数量（最多4个）
  const maxVideos = 4;
  const currentWindows = openedWindows.value.length;
  
  if (currentWindows >= maxVideos) {
    proxy.$modal.msgWarning('最多只能同时播放4路视频');
    return;
  }
  
  const remainingSlots = maxVideos - currentWindows;
  const videosToOpen = selectedVideos.value.slice(0, remainingSlots);
  
  if (videosToOpen.length === 0) {
    return;
  }
  
  // 创建新的批量查看弹窗，支持2x2布局
  const windowId = 'batch_' + Date.now() + '_' + Math.floor(Math.random() * 1000);
  
  // 为每个选中的视频获取流地址
  const videoStreamPromises = videosToOpen.map(async (video) => {
    try {
      const response = await pushVideoConfig(video.vidId);
      const streamUrl = response.data?.srs_flv_url?.trim() || `http://localhost:8080/live/${video.vidId}.flv`;
      return {
        id: video.vidId,
        name: video.vidName,
        url: streamUrl,
        video: video
      };
    } catch (error) {
      console.error('获取视频流地址失败:', error);
      return {
        id: video.vidId,
        name: video.vidName,
        url: `http://localhost:8080/live/${video.vidId}.flv`,
        video: video
      };
    }
  });
  
  // 等待所有视频流地址获取完成
  Promise.all(videoStreamPromises).then(videoStreams => {
    const windowData = {
      id: windowId,
      visible: true,
      videoStreams: videoStreams,
      messageRecords: [],
      flvPlayers: [],
      videoLoading: new Array(videoStreams.length).fill(true)
    };
    
    openedWindows.value.push(windowData);
    batchViewDialogs.value.push(windowData);
    
    // 等待弹窗渲染完成后初始化视频播放器
    nextTick(() => {
      initBatchVideoPlayers(windowData);
    });
  });
  
  // 清空选择
  selectedVideos.value = [];
  if (proxy.$refs.multipleTableRef) {
    proxy.$refs.multipleTableRef.clearSelection();
  }
}

/** 初始化批量查看视频播放器 */
function initBatchVideoPlayers(windowData) {
  if (!flvjs.isSupported()) {
    proxy.$modal.msgError('当前浏览器不支持FLV播放');
    return;
  }
  
  // 确保flvPlayers数组已初始化
  if (!windowData.flvPlayers) {
    windowData.flvPlayers = [];
  }
  
  // 为每个视频流创建播放器
  windowData.videoStreams.forEach((stream, index) => {
    const element = document.querySelector(`#batchVideo-${windowData.id}-${index}`);
    if (element && stream.url) {
      // 检查是否已存在播放器实例，避免重复创建
      if (windowData.flvPlayers[index]) {
        console.log(`跳过已存在的播放器 [${windowData.id}-${index}]`);
        return;
      }
      initBatchVideoElement(element, windowData.id, index, stream.url, 'flv');
    }
  });
  
  // 添加超时处理，30秒后如果视频还没加载完成，则停止加载
  setTimeout(() => {
    const currentWindowData = batchViewDialogs.value.find(w => w.id === windowData.id);
    if (currentWindowData && currentWindowData.videoLoading) {
      currentWindowData.videoLoading.forEach((isLoading, index) => {
        if (isLoading) {
          console.log(`视频加载超时 [${windowData.id}-${index}]，停止加载`);
          currentWindowData.videoLoading[index] = false;
          
          // 销毁对应的播放器
          if (currentWindowData.flvPlayers && currentWindowData.flvPlayers[index]) {
            try {
              currentWindowData.flvPlayers[index].pause();
              currentWindowData.flvPlayers[index].destroy();
              currentWindowData.flvPlayers[index] = null;
            } catch (error) {
              console.warn('超时销毁播放器时出错:', error);
            }
          }
        }
      });
    }
  }, 30000);
}

/** 初始化批量查看视频元素 */
function initBatchVideoElement(element, windowId, index, streamUrl, type) {
  if (!element || !streamUrl) return;
  
  // 获取窗口数据
  const windowData = batchViewDialogs.value.find(w => w.id === windowId);
  if (!windowData) return;
  
  // 严格检查：如果已经存在播放器实例，直接返回，不允许重复创建
  if (windowData.flvPlayers && windowData.flvPlayers[index]) {
    console.warn(`禁止重复创建播放器实例 [${windowId}-${index}]`);
    return;
  }
  
  // 清空视频元素的内容，避免残留
  element.src = '';
  element.load && element.load();
  
  // 直接创建FLV播放器并播放，不显示前置动画
  try {
    const player = flvjs.createPlayer({
      type: 'flv',
      url: streamUrl
    }, {
      enableWorker: false,
      enableStashBuffer: false,
      stashInitialSize: 128,
      lazyLoad: false,
      lazyLoadMaxDuration: 0,
      deferLoadAfterSourceOpen: false,
      autoCleanupSourceBuffer: true,
      autoCleanupMaxBackwardDuration: 30,
      autoCleanupMinBackwardDuration: 10,
      // 禁用自动重连
      isLive: true,
      liveBufferLatencyChasing: false,
      liveBufferLatencyMaxLatency: 0,
      liveBufferLatencyMinRemain: 0
    });
    
    player.attachMediaElement(element);
    player.load();
    
    // 添加错误处理 - 禁用自动重连
    player.on(flvjs.Events.ERROR, (errorType, errorDetail) => {
      console.error(`视频播放失败 [${windowId}-${index}]:`, errorType, errorDetail);
      
      // 更新加载状态
      if (windowData.videoLoading) {
        windowData.videoLoading[index] = false;
      }
      
      // 禁用自动重连，直接销毁播放器
      try {
        player.pause();
        player.destroy();
      } catch (e) {
        console.warn('销毁播放器时出错:', e);
      }
      
      // 从数组中移除该播放器
      if (windowData.flvPlayers) {
        windowData.flvPlayers[index] = null;
      }
    });
    
    // 监听视频加载完成事件
    player.on(flvjs.Events.METADATA_ARRIVED, () => {
      console.log(`视频元数据加载完成 [${windowId}-${index}]`);
      
      // 更新加载状态
      if (windowData.videoLoading) {
        windowData.videoLoading[index] = false;
      }
    });
    
    // 直接播放视频
    player.play().catch(error => {
      console.warn(`视频播放失败 [${windowId}-${index}]:`, error);
    });
    
    // 存储播放器实例
    if (!windowData.flvPlayers) {
      windowData.flvPlayers = [];
    }
    windowData.flvPlayers[index] = player;
    
    console.log(`批量查看视频播放器初始化成功 [${windowId}-${index}]: ${streamUrl}`);
    
  } catch (error) {
    console.error(`创建FLV播放器失败 [${windowId}-${index}]:`, error);
    
    // 更新加载状态
    if (windowData.videoLoading) {
      windowData.videoLoading[index] = false;
    }
  }
}

/** 关闭批量查看窗口 */
function closeBatchViewDialog(windowId) {
  const windowIndex = openedWindows.value.findIndex(w => w.id === windowId);
  if (windowIndex > -1) {
    const window = openedWindows.value[windowIndex];
    // 清理视频播放器
    if (window.flvPlayers && window.flvPlayers.length > 0) {
      window.flvPlayers.forEach((player, index) => {
        if (player) {
          try {
            console.log(`清理批量查看播放器 [${windowId}-${index}]`);
            player.pause();
            player.destroy();
          } catch (error) {
            console.warn(`清理批量查看播放器时出错 [${windowId}-${index}]:`, error);
          }
        }
      });
    }
    
    // 清理视频元素
    if (window.videoStreams && window.videoStreams.length > 0) {
      window.videoStreams.forEach((stream, index) => {
        const element = document.querySelector(`#batchVideo-${windowId}-${index}`);
        if (element) {
          try {
            element.src = '';
            element.load && element.load();
          } catch (error) {
            console.warn(`清理视频元素时出错 [${windowId}-${index}]:`, error);
          }
        }
      });
    }
    
    openedWindows.value.splice(windowIndex, 1);
    
    const dialogIndex = batchViewDialogs.value.findIndex(d => d.id === windowId);
    if (dialogIndex > -1) {
      batchViewDialogs.value.splice(dialogIndex, 1);
    }
  }
}

/** 生成模拟视频流数据 */
function generateMockStreams(video) {
  const streamCount = Math.min(4, Math.floor(Math.random() * 4) + 1);
  const streams = [];
  for (let i = 1; i <= streamCount; i++) {
    streams.push({
      id: i,
      name: `${video.vidName}-摄像头${i}`,
      url: `http://localhost:8080/live/${video.vidId}_stream${i}.flv`
    });
  }
  return streams;
}

/** 生成模拟消息数据 */
function generateMockMessages(video) {
  const messages = [
    {
      id: 1,
      time: new Date().toLocaleString(),
      image: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=',
      text: `${video.vidName} 监控点正常运行中，当前状态良好。`
    },
    {
      id: 2,
      time: new Date(Date.now() - 300000).toLocaleString(),
      image: 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=',
      text: `检测到 ${video.vidName} 区域有异常活动，请注意查看。`
    }
  ];
  return messages;
}

// 组件卸载时清理资源
/** 获取缓存消息 */
function fetchCacheMessages() {
  if (publish_path.value) {
    getCacheMessages(publish_path.value).then(response => {
      if (response.code === 200 && response.data) {
        cacheMessages.value = [...response.data, ...cacheMessages.value];
        if (response.data.length > 0) {
          console.log('获取缓存消息成功:', response.data);
        }
      }
    }).catch(error => {
      console.error('获取缓存消息失败:', error);
    });
  }
}

/** 启动定时器 */
function startCacheTimer() {
  // 立即执行一次
  fetchCacheMessages();
  
  // 每3秒执行一次
  cacheTimer.value = setInterval(() => {
    fetchCacheMessages();
  }, 3000);
}

/** 停止定时器 */
function stopCacheTimer() {
  if (cacheTimer.value) {
    clearInterval(cacheTimer.value);
    cacheTimer.value = null;
  }
}

/** 启动预警定时器 */
function startAlarmTimer() {
  stopAlarmTimer();
  alarmTimer.value = setInterval(() => {
    loadVideoAlarms();
  }, 5000);
}

/** 停止预警定时器 */
function stopAlarmTimer() {
  if (alarmTimer.value) {
    clearInterval(alarmTimer.value);
    alarmTimer.value = null;
  }
}

// 组件挂载时启动定时器
onMounted(() => {
  // startCacheTimer();
  loadAlgorithmDict();
});

onUnmounted(() => {
  // 清理定时器
  stopCacheTimer();
  stopAlarmTimer();
  
  // 清理主视频播放器
  flvPlayers.value.forEach(player => {
    if (player) {
      try {
        player.pause();
        player.destroy();
      } catch (error) {
        console.warn('清理主播放器时出错:', error);
      }
    }
  });
  
  // 清理批量查看播放器
  openedWindows.value.forEach(window => {
    if (window.flvPlayers && window.flvPlayers.length > 0) {
      window.flvPlayers.forEach(player => {
        if (player) {
          try {
            player.pause();
            player.destroy();
          } catch (error) {
            console.warn('清理批量查看播放器时出错:', error);
          }
        }
      });
    }
  });
});

// 初始化数据
getList();
</script>

<style scoped>
.stat-card {
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  margin-bottom: 20px;
}

.stat-content {
  display: flex;
  align-items: center;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-icon .el-icon {
  font-size: 24px;
  color: white;
}

.stat-info {
  flex: 1;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .stat-card {
    margin-bottom: 10px;
  }
}

.monitor-detail {
  display: flex;
  gap: 20px;
  height: 70vh;
}

.video-section {
  flex: 2;
  display: flex;
  flex-direction: column;
}

.video-section h3 {
  margin: 0 0 15px 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.video-grid {
  display: grid;
  gap: 10px;
  flex: 1;
}

.video-grid.single {
  grid-template-columns: 1fr;
}

.video-grid.double {
  grid-template-columns: 1fr 1fr;
}

.video-grid.triple {
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
}

.video-grid.triple .video-item:first-child {
  grid-column: 1 / -1;
}

.video-grid.quad {
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
}

.video-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.video-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.video-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 12px;
}

.video-status.online {
  background: #f0f9ff;
  color: #409eff;
}

.video-container {
  position: relative;
  height: calc(100% - 37px);
  background: #000;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}

.video-container.single-video {
  /* height: 400px; */
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
}

.video-player:first-child {
  z-index: 1;
}

.video-player.live-video {
  z-index: 2;
}

.video-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: rgba(0, 0, 0, 0.8);
  color: #fff;
  z-index: 3;
}

.video-placeholder p {
  margin: 8px 0 0 0;
  font-size: 14px;
}

.message-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e4e7ed;
  padding-left: 20px;
}

.message-section h3 {
  margin: 0 0 15px 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.message-item {
  margin-bottom: 20px;
  padding: 15px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.message-content {
  display: flex;
  gap: 12px;
}

.message-image {
  flex-shrink: 0;
}

.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 120px;
  height: 80px;
  background: #f5f7fa;
  color: #c0c4cc;
}

.message-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-time {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}

.attributes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.message-text {
  flex: 1;
}

.message-text p {
  margin: 0;
  line-height: 1.6;
  color: #606266;
  font-size: 14px;
  word-break: break-word;
}

/* 滚动条样式 */
.message-list::-webkit-scrollbar {
  width: 6px;
}

.message-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.message-list::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.message-list::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

.batch-view-dialog {
  background-color: #3E7BFA !important;
  .el-dialog__body {
    padding: 0;
  }
}

.dashboard-chart-title {
  color: #1D211F;
  font-size: 14px;
}

:deep(.el-dialog) {
  background: linear-gradient( 180deg, #c2d6ff 0%, rgba(62,123,250,0) 100%), #FFFFFF !important;
  border-radius: 4px;
}

:deep(.el-dialog__header .el-dialog__title) {
  color: #1D211F !important;
  font-size: 16px;
  font-weight: 600;
}

/* 批量监控查看样式 */
.batch-monitor-detail {
  display: flex;
  flex-direction: column;
  height: 80vh;
  padding: 20px;
}

.batch-monitor-detail .video-section {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.batch-monitor-detail .video-grid {
  flex: 1;
  min-height: 0;
}

.batch-monitor-detail .video-item {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.batch-monitor-detail .video-container {
  flex: 1;
  position: relative;
  min-height: 200px;
}
</style>