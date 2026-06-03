<template>
  <div class="camera-list-container">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="mb4">
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon total"><el-icon><VideoCamera /></el-icon></div>
            <div class="stat-info">
              <div class="stat-title">摄像头总数</div>
              <div class="stat-value">{{ total }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon running"><el-icon><VideoPlay /></el-icon></div>
            <div class="stat-info">
              <div class="stat-title">运行中</div>
              <div class="stat-value">{{ runningCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon stopped"><el-icon><VideoPause /></el-icon></div>
            <div class="stat-info">
              <div class="stat-title">已停止</div>
              <div class="stat-value">{{ stoppedCount }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-content">
            <div class="stat-icon selected"><el-icon><Select /></el-icon></div>
            <div class="stat-info">
              <div class="stat-title">已选中</div>
              <div class="stat-value">{{ selectedCameras.length }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 摄像头位置 & 视频流类型筛选 -->
    <el-row :gutter="16" class="mb8">
      <el-col :span="4">
        <el-select v-model="queryParams.vidBoxSerial" placeholder="摄像头位置" clearable style="width:100%" @change="handleQuery">
          <el-option label="全部位置" value="" />
          <el-option label="本地服务器" value="__server__" />
          <el-option
            v-for="box in boxOptions"
            :key="box.serial"
            :label="`盒子-${box.serial} (${box.box_name || ''})`"
            :value="box.serial"
          />
        </el-select>
      </el-col>
      <el-col :span="4">
        <el-select v-model="queryParams.vidType" placeholder="视频流类型" clearable style="width:100%" @change="handleQuery">
          <el-option label="全部类型" value="" />
          <el-option label="USB摄像头" value="local" />
          <el-option label="RTSP流" value="rtsp" />
          <el-option label="RTMP流" value="rtmp" />
          <el-option label="HTTP流" value="http" />
          <el-option label="HTTPS流" value="https" />
          <el-option label="文件" value="file" />
        </el-select>
      </el-col>
    </el-row>

    <!-- 搜索栏 -->
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" class="mb8">
      <el-form-item label="名称" prop="vidName">
        <el-input v-model="queryParams.vidName" placeholder="请输入摄像头名称" clearable style="width: 180px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="序列号" prop="vidSerial">
        <el-input v-model="queryParams.vidSerial" placeholder="请输入序列号" clearable style="width: 180px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item label="场景" prop="vidSceneName">
        <el-input v-model="queryParams.vidSceneName" placeholder="请输入场景名称" clearable style="width: 180px" @keyup.enter="handleQuery" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 工具栏 -->
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button type="primary" plain icon="Plus" @click="handleAdd">新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="success" plain icon="Edit" :disabled="!single" @click="handleUpdate(selectedCameras[0])">修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button type="danger" plain icon="Delete" :disabled="!multiple" @click="handleDelete(null)">删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-divider direction="vertical" />
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="primary"
          icon="VideoPlay"
          :disabled="selectedCameras.length === 0 || openedWindows.length >= 4"
          @click="handleBatchView"
        >
          批量查看 ({{ selectedCameras.length }}/4)
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          icon="VideoPlay"
          :disabled="selectedCameras.length === 0"
          @click="handleBatchStart"
        >
          批量启动推理
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          icon="VideoPause"
          :disabled="selectedCameras.length === 0"
          @click="handleBatchStop"
        >
          批量停止推理
        </el-button>
      </el-col>
      <el-col :span="1.5">
        <el-switch
          v-model="autoRefresh"
          active-text="自动刷新"
          inactive-text="手动"
          style="margin-left: 20px"
        />
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
    </el-row>

    <!-- 摄像头表格 -->
    <el-table
      ref="cameraTableRef"
      v-loading="loading"
      :data="cameraList"
      @selection-change="handleSelectionChange"
      border
      stripe
      style="width: 100%"
    >
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="序号" type="index" width="70" align="center">
        <template #default="{ $index }">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + $index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="vidName" label="摄像头名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="vidSerial" label="序列号" min-width="120" show-overflow-tooltip />
      <el-table-column label="视频流类型" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.vidType)" size="small">{{ typeLabel(row.vidType) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="摄像头位置" width="120" align="center">
        <template #default="{ row }">
          <template v-if="row.vidBoxSerial">
            <el-tag type="warning" size="small">盒子-{{ row.vidBoxSerial }}</el-tag>
          </template>
          <el-tag v-else type="success" size="small">本地服务器</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="vidSceneName" label="场景名称" min-width="120" show-overflow-tooltip />
      <el-table-column label="算法" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <el-tag
            v-for="alg in (row.vidAlgorithmName || [])"
            :key="alg"
            size="small"
            type="info"
            style="margin-right: 4px"
          >
            {{ alg }}
          </el-tag>
          <span v-if="!row.vidAlgorithmName || row.vidAlgorithmName.length === 0">-</span>
        </template>
      </el-table-column>
      <el-table-column label="流地址" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          <span v-if="row.vidType === 'local'">USB设备: /dev/video{{ row.vidUri }}</span>
          <span v-else>{{ row.vidUri || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="分析模式" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="row.vidAnalysisMode === 'clip' ? 'warning' : 'success'" size="small">
            {{ row.vidAnalysisMode === 'clip' ? '截取分析' : '实时分析' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="运行状态" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip
            v-if="row.deviceErrorMessage"
            :content="row.deviceErrorMessage"
            placement="top"
            :show-after="300"
          >
            <el-tag :type="statusTagType(row.deviceStatus)">
              <span class="status-dot" :class="statusDotClass(row.deviceStatus)" />
              {{ statusLabel(row.deviceStatus) }}
            </el-tag>
          </el-tooltip>
          <el-tag v-else :type="statusTagType(row.deviceStatus)">
            <span class="status-dot" :class="statusDotClass(row.deviceStatus)" />
            {{ statusLabel(row.deviceStatus) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="vidUpdateTime" label="更新时间" width="180" align="center">
        <template #default="{ row }">
          <span v-if="row.vidUpdateTime">{{ parseTime(row.vidUpdateTime) }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="310" fixed="right" align="center">
        <template #default="{ row }">
          <!-- 本地摄像头：查看时自动拉流，无需手动启停 -->
          <template v-if="isLocalCamera(row)">
            <el-button type="primary" link icon="View" @click="handleView(row)">查看</el-button>
            <el-button type="primary" link icon="List" @click="handleRunHistory(row)">运行记录</el-button>
            <el-button type="primary" link icon="Setting" @click="showAlgorithmDialog(row)">配置算法</el-button>
            <el-button type="primary" link icon="Edit" @click="handleUpdate(row)">修改</el-button>
            <el-button type="danger" link icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
          <!-- 盒子摄像头：保持手动启停逻辑 -->
          <template v-else>
            <el-button
              v-if="row.deviceStatus === 'running'"
              type="primary" link icon="View" @click="handleView(row)">查看</el-button>
            <el-tooltip
              v-else-if="row.deviceStatus === 'error'"
              :content="row.deviceErrorMessage || '视频流错误'"
              placement="top"
            >
              <el-button type="warning" link icon="Warning" @click="handleRestartOne(row)">重试</el-button>
            </el-tooltip>
            <el-tooltip
              v-else-if="row.deviceStatus === 'offline'"
              :content="row.deviceErrorMessage || '盒子离线，无法操作'"
              placement="top"
            >
              <el-button type="info" link icon="VideoPlay" disabled>启动</el-button>
            </el-tooltip>

            <el-button
              v-if="row.deviceStatus === 'running'"
              type="danger" link icon="VideoPause" @click="handleStopOne(row)">停止</el-button>
            <el-button
              v-else-if="row.deviceStatus === 'error'"
              type="warning" link icon="RefreshRight" @click="handleRestartOne(row)">重试</el-button>
            <el-button
              v-else-if="row.deviceStatus !== 'offline'"
              type="success" link icon="VideoPlay" @click="handleStartOne(row)">启动</el-button>

            <el-button type="primary" link icon="Setting" @click="showAlgorithmDialog(row)">配置算法</el-button>
            <el-button type="primary" link icon="Edit" @click="handleUpdate(row)">修改</el-button>
            <el-button type="danger" link icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 新增/编辑弹窗 -->
    <el-dialog :title="dialogTitle" v-model="dialogOpen" width="580px" append-to-body>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="名称" prop="vidName">
              <el-input v-model="form.vidName" placeholder="请输入摄像头名称" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="序列号" prop="vidSerial">
              <el-input v-model="form.vidSerial" placeholder="请输入序列号" maxlength="100" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="摄像头位置" prop="vidBoxSerial">
              <el-select v-model="form.vidBoxSerial" placeholder="选择摄像头位置" clearable style="width: 100%">
                <el-option label="本地服务器" value="" />
                <el-option
                  v-for="box in boxOptions"
                  :key="box.serial"
                  :label="`盒子-${box.serial} (${box.box_name || ''})`"
                  :value="box.serial"
                >
                  <span>{{ box.box_name || '盒子' }}</span>
                  <el-tag size="small" style="margin-left:8px">{{ box.serial }}</el-tag>
                  <el-tag v-if="box.host" size="small" type="info" style="margin-left:4px">{{ box.host }}</el-tag>
                  <el-tag v-if="box.status === 'online'" size="small" type="success" style="margin-left:4px">在线</el-tag>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="视频流类型" prop="vidType">
              <el-select v-model="form.vidType" placeholder="请选择视频流类型" style="width: 100%">
                <el-option label="USB摄像头" value="local" />
                <el-option label="RTSP流" value="rtsp" />
                <el-option label="RTMP流" value="rtmp" />
                <el-option label="HTTP流" value="http" />
                <el-option label="HTTPS流" value="https" />
                <el-option label="文件" value="file" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="场景名称" prop="vidSceneName">
              <el-input v-model="form.vidSceneName" placeholder="请输入场景名称" maxlength="100" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分析模式" prop="vidAnalysisMode">
              <el-select v-model="form.vidAnalysisMode" placeholder="请选择分析模式" style="width: 100%">
                <el-option label="实时分析" value="realtime" />
                <el-option label="截取视频分析" value="clip" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="流地址" prop="vidUri">
          <el-input v-model="form.vidUri" :placeholder="uriPlaceholder" maxlength="1000" />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="submitLoading" @click="submitForm">确 定</el-button>
          <el-button @click="cancel">取 消</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 配置算法弹窗 -->
    <el-dialog
      v-model="algorithmDialogVisible"
      :title="`配置算法 - ${algorithmCamera?.vidName || ''}`"
      width="720px"
      append-to-body
      destroy-on-close
    >
      <div v-loading="algorithmLoading">
        <el-alert
          :title="`当前摄像头位置: ${algorithmCamera?.vidBoxSerial ? `盒子-${algorithmCamera.vidBoxSerial}` : '本地服务器'}，仅显示${algorithmCamera?.vidBoxSerial ? '盒子端' : '本地'}算法`"
          type="info"
          :closable="false"
          class="mb8"
        />
        <el-checkbox-group v-model="selectedAlgorithmIds" class="algorithm-check-list">
          <el-checkbox
            v-for="algorithm in enabledAlgorithmOptions"
            :key="algorithm.algId"
            :label="algorithm.algId"
            border
            class="algorithm-check-item"
          >
            <div class="algorithm-option-content">
              <span class="algorithm-option-title">{{ algorithmDisplayName(algorithm) }}</span>
              <el-tag size="small" :type="algorithm.algRuntimeType === 'local' ? 'success' : 'warning'">
                {{ runtimeTypeLabel(algorithm.algRuntimeType) }}
              </el-tag>
            </div>
          </el-checkbox>
        </el-checkbox-group>
        <el-empty v-if="!enabledAlgorithmOptions.length" description="暂无启用算法" />
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="algorithmDialogVisible = false">取 消</el-button>
          <el-button type="primary" :loading="algorithmSaving" @click="saveAlgorithmBinding">保 存</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 单个查看弹窗 -->
    <el-dialog
      v-model="viewDialogVisible"
      :title="`实时监控 - ${currentCamera.vidName || ''}`"
      width="70%"
      top="5vh"
      @close="closeViewDialog"
      :close-on-press-escape="false"
    >
      <div class="view-content">
        <div class="video-section">
          <div class="video-container single-view">
            <!-- 本地服务器摄像头 或 盒子摄像头 FLV 失败回退到 MJPEG -->
            <template v-if="isServerCamera(currentCamera) || useMJPEGFallback">
              <img v-if="boxStreamSrc" :src="boxStreamSrc" class="video-player" style="object-fit: contain" @load="singleVideoLoading = false" @error="handleDirectStreamError" />
              <img v-else-if="snapshotSrc" :src="snapshotSrc" class="video-player" style="object-fit: contain" />
              <div v-else-if="snapshotError" class="video-error">
                <el-icon size="42"><Warning /></el-icon>
                <div class="error-title">{{ snapshotError.title }}</div>
                <div class="error-message">{{ snapshotError.message }}</div>
                <div v-if="snapshotError.triedUrls?.length" class="error-detail">
                  <div>已尝试地址：</div>
                  <div v-for="url in snapshotError.triedUrls" :key="url">{{ url }}</div>
                </div>
                <div v-else-if="snapshotError.detail" class="error-detail">{{ snapshotError.detail }}</div>
                <el-button type="primary" size="small" @click="retryLoadStream(currentCamera)">重试</el-button>
              </div>
            </template>
            <!-- 盒子摄像头及其他：使用 SRS FLV 流（低延迟、硬件加速） -->
            <video v-else ref="liveVideoRef" class="video-player" controls muted />
            <div class="video-placeholder" v-show="singleVideoLoading">
              <el-icon size="48"><VideoCamera /></el-icon>
              <p>{{ isServerCamera(currentCamera) ? '本地摄像头加载中...' : '视频加载中...' }}</p>
            </div>
          </div>
        </div>
        <div class="info-section">
          <el-descriptions :column="1" border size="small" title="摄像头信息">
            <el-descriptions-item label="名称">{{ currentCamera.vidName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="序列号">{{ currentCamera.vidSerial || '-' }}</el-descriptions-item>
            <el-descriptions-item label="视频流类型">{{ typeLabel(currentCamera.vidType) }}</el-descriptions-item>
            <el-descriptions-item label="摄像头位置">
              <template v-if="currentCamera.vidBoxSerial">盒子-{{ currentCamera.vidBoxSerial }}</template>
              <template v-else>本地服务器</template>
            </el-descriptions-item>
            <el-descriptions-item label="场景">{{ currentCamera.vidSceneName || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="currentCamera.deviceStatus === 'running' ? 'success' : 'info'">
                {{ currentCamera.deviceStatus === 'running' ? '运行中' : '已停止' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="FLV地址">{{ currentCamera.srsFlvUrl || '-' }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>

    <!-- 批量查看弹窗 -->
    <el-dialog
      v-for="windowData in batchViewDialogs"
      :key="windowData.id"
      v-model="windowData.visible"
      :title="`批量监控 - ${windowData.videoStreams.length}路视频`"
      width="90%"
      top="5vh"
      @close="closeBatchViewDialog(windowData.id)"
      :close-on-press-escape="false"
    >
      <div class="video-grid" :class="gridClass(windowData.videoStreams.length)">
        <div v-for="(stream, index) in windowData.videoStreams" :key="stream.id" class="video-item">
          <div class="video-header">
            <span class="video-title">{{ stream.name }}</span>
            <el-tag size="small" type="success">在线</el-tag>
          </div>
          <div class="video-container">
            <video :id="`batchVideo-${windowData.id}-${index}`" class="video-player" controls muted />
            <div class="video-placeholder" v-show="windowData.videoLoading[index]">
              <el-icon size="40"><VideoCamera /></el-icon>
              <p>加载中...</p>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 本地算法运行记录弹窗 -->
    <el-dialog
      v-model="runHistoryVisible"
      :title="`运行记录 - ${runHistoryCamera?.vidName || ''}`"
      width="700px"
      append-to-body
      destroy-on-close
    >
      <div v-loading="runHistoryLoading">
        <el-empty v-if="!runHistoryLoading && runHistoryList.length === 0" description="暂无运行记录" />
        <el-table v-else :data="runHistoryList" border stripe size="small">
          <el-table-column label="算法" prop="algorithmName" min-width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="{ running: 'success', completed: '', failed: 'danger', stopped: 'info' }[row.status]" size="small">
                {{ runStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启动时间" width="160" align="center">
            <template #default="{ row }">{{ row.startTime ? parseTime(row.startTime) : '-' }}</template>
          </el-table-column>
          <el-table-column label="结束时间" width="160" align="center">
            <template #default="{ row }">{{ row.endTime ? parseTime(row.endTime) : '-' }}</template>
          </el-table-column>
          <el-table-column label="耗时" width="90" align="center">
            <template #default="{ row }">
              <span v-if="row.startTime && row.endTime">{{ ((new Date(row.endTime) - new Date(row.startTime)) / 1000).toFixed(0) }}s</span>
              <span v-else-if="row.status === 'running'">-</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.errorMessage || '-' }}</template>
          </el-table-column>
        </el-table>
        <pagination
          v-show="runHistoryTotal > 0"
          :total="runHistoryTotal"
          v-model:page="runHistoryPage.pageNum"
          v-model:limit="runHistoryPage.pageSize"
          @pagination="loadRunHistory"
          layout="prev, pager, next"
        />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { VideoCamera, VideoPlay, VideoPause, Select, Warning, RefreshRight, List } from '@element-plus/icons-vue'
import { listVideo, addVideo, updateVideo, delVideo, getVideo } from '@/api/xuzhou/video'
import { listAlgorithm } from '@/api/xuzhou/algorithm'
import { startCamera, stopCamera, listBoxes, getCameraStreamUrl, getCameraSnapshot, startLocalCamera, stopLocalCamera, getLocalCameraStreamUrl, getLocalCameraSnapshot, getLocalCameraRuns } from '@/api/xuzhou/camera'
import { parseTime } from '@/utils/ruoyi'
import flvjs from 'flv.js'

const loading = ref(false)
const total = ref(0)
const cameraList = ref([])
const selectedCameras = ref([])
const autoRefresh = ref(false)
const showSearch = ref(true)
const single = ref(true)
const multiple = ref(true)
const cameraTableRef = ref(null)
const queryRef = ref(null)
const formRef = ref(null)
const dialogOpen = ref(false)
const dialogTitle = ref('')
const submitLoading = ref(false)
const algorithmDialogVisible = ref(false)
const algorithmLoading = ref(false)
const algorithmSaving = ref(false)
const algorithmCamera = ref(null)
const algorithmOptions = ref([])
const selectedAlgorithmIds = ref([])
const boxOptions = ref([])

// 本地算法运行记录
const runHistoryVisible = ref(false)
const runHistoryCamera = ref(null)
const runHistoryLoading = ref(false)
const runHistoryList = ref([])
const runHistoryTotal = ref(0)
const runHistoryPage = reactive({ pageNum: 1, pageSize: 20 })

async function fetchBoxes() {
  try {
    const res = await listBoxes()
    if (res.code === 200 && res.data) {
      boxOptions.value = (res.data.online || []).map(b => ({ ...b, status: 'online' }))
    }
  } catch { /* ignore */ }
}

const queryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  vidName: '',
  vidSerial: '',
  vidType: '',
  vidBoxSerial: '',
  vidSceneName: ''
})

const form = reactive({
  vidId: undefined,
  vidName: '',
  vidSerial: '',
  vidBoxSerial: '',
  vidType: 'local',
  vidSceneName: '',
  vidUri: '',
  vidAnalysisMode: 'realtime'
})

const rules = computed(() => ({
  vidName: [{ required: true, message: '请输入摄像头名称', trigger: 'blur' }],
  vidType: [{ required: true, message: '请选择类型', trigger: 'change' }],
  vidUri: [{ required: true, message: '请输入流地址', trigger: 'blur' }]
}))

const uriPlaceholder = computed(() => {
  const tips = {
    local: 'USB摄像头设备索引，如: 0, 1, 2 (对应 /dev/video0)',
    rtsp: 'rtsp://username:password@ip:port/stream',
    rtmp: 'rtmp://ip:port/live/stream',
    http: 'http://ip:port/path/stream',
    https: 'https://ip:port/path/stream',
    file: '文件路径，如: /videos/test.mp4'
  }
  return tips[form.vidType] || '请输入流地址'
})

const enabledAlgorithmOptions = computed(() => {
  const isBoxCamera = algorithmCamera.value?.vidBoxSerial
  const runtimeType = isBoxCamera ? 'external_box' : 'local'
  return algorithmOptions.value.filter(item =>
    item.algEnabled !== false && item.algRuntimeType === runtimeType
  )
})

function parseJson(value) {
  if (!value) return {}
  if (typeof value === 'object') return value
  if (typeof value === 'string') {
    try {
      return JSON.parse(value)
    } catch {
      return {}
    }
  }
  return {}
}

function normalizeAlgorithmList(value) {
  if (!value) return []
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

function normalizeAlgorithmItem(item) {
  return {
    algId: item.algId,
    algName: item.algName || '',
    algVersion: item.algVersion || '',
    algSerial: item.algSerial || '',
    algWeightPath: item.algWeightPath || '',
    runtimeType: item.runtimeType || item.algRuntimeType || 'external_box',
    algRuntimeType: item.algRuntimeType || item.runtimeType || 'external_box',
    algEnabled: item.algEnabled !== false,
    algDefaultConf: parseJson(item.algDefaultConf),
  }
}

function runtimeTypeLabel(runtimeType) {
  return runtimeType === 'local' ? '本地' : '盒子'
}

function algorithmDisplayName(algorithm) {
  const version = algorithm.algVersion ? `(${algorithm.algVersion})` : ''
  return `${algorithm.algName || algorithm.algSerial || '未命名算法'}${version}`
}

function selectedAlgorithmItems() {
  const selectedIds = selectedAlgorithmIds.value.map(id => Number(id))
  return enabledAlgorithmOptions.value
    .filter(item => selectedIds.includes(Number(item.algId)))
    .map(normalizeAlgorithmItem)
}

async function showAlgorithmDialog(row) {
  algorithmCamera.value = row
  algorithmDialogVisible.value = true
  algorithmLoading.value = true
  try {
    const response = await listAlgorithm({ pageNum: 1, pageSize: 1000 })
    algorithmOptions.value = response.rows || []
    // 根据摄像头位置过滤已有算法，只保留匹配运行时类型的
    const isBoxCamera = !!row.vidBoxSerial
    const expectedType = isBoxCamera ? 'external_box' : 'local'
    const validOptionIds = new Set(
      algorithmOptions.value
        .filter(item => item.algEnabled !== false && item.algRuntimeType === expectedType)
        .map(item => item.algId)
    )
    selectedAlgorithmIds.value = normalizeAlgorithmList(row.vidAlgorithm)
      .map(item => item.algId)
      .filter(id => validOptionIds.has(id))
  } catch (error) {
    ElMessage.error('获取算法列表失败')
  } finally {
    algorithmLoading.value = false
  }
}

async function saveAlgorithmBinding() {
  if (!algorithmCamera.value) return
  algorithmSaving.value = true
  try {
    const detailResponse = await getVideo(algorithmCamera.value.vidId)
    const video = detailResponse.data || { ...algorithmCamera.value }
    const algorithms = selectedAlgorithmItems()
    video.vidAlgorithm = algorithms
    video.vidAlgorithmName = algorithms.map(item => algorithmDisplayName(item))
    await updateVideo(video)
    ElMessage.success('算法配置已保存')
    algorithmDialogVisible.value = false
    await getList()
  } catch (error) {
    ElMessage.error('算法配置保存失败')
  } finally {
    algorithmSaving.value = false
  }
}


const runningCount = ref(0)
const stoppedCount = ref(0)

// FLV 相关
const viewDialogVisible = ref(false)
const currentCamera = ref({})
const liveVideoRef = ref(null)
const singleVideoLoading = ref(true)
const useMJPEGFallback = ref(false)  // 盒子摄像头 FLV 失败后回退到 MJPEG 流
const boxStreamSrc = ref('')
const snapshotSrc = ref('')
const snapshotError = ref(null)
let snapshotObjectUrl = ''
let singleFlvPlayer = null
let snapshotTimer = null

let refreshTimer = null

// 批量查看
const openedWindows = ref([])
const batchViewDialogs = ref([])

// 类型标签
function typeTagType(vidType) {
  const map = { local: '', rtsp: 'warning', rtmp: 'danger', http: 'info', https: 'info', file: '' }
  return map[vidType] || 'info'
}

function typeLabel(vidType) {
  const map = { local: 'USB摄像头', rtsp: 'RTSP', rtmp: 'RTMP', http: 'HTTP', https: 'HTTPS', file: '文件' }
  return map[vidType] || vidType || '-'
}

function statusTagType(status) {
  const map = { running: 'success', stopped: 'info', error: 'danger', offline: 'warning', unknown: 'info' }
  return map[status] || 'info'
}

function statusLabel(status) {
  const map = { running: '运行中', stopped: '已停止', error: '错误', offline: '盒子离线', unknown: '未知' }
  return map[status] || status || '未知'
}

function statusDotClass(status) {
  return status || 'unknown'
}

function getSrsFlvUrl(vidId) {
  return `http://192.168.0.246:8080/live/publish_${vidId}.flv`
}

function isBoxCamera(camera) {
  return !!camera?.vidBoxSerial
}

function isLocalCamera(camera) {
  // 纯本地（无盒子），用于判断是否需要隐藏启动/停止按钮
  return !camera?.vidBoxSerial
}

function isLocalUsbCamera(camera) {
  // 本地 USB 摄像头 → MJPEG 播放
  return !camera?.vidBoxSerial && camera?.vidType === 'local'
}

function isLocalRtspCamera(camera) {
  // 本地网络流摄像头（RTSP/RTMP/HTTP）→ ffmpeg MJPEG 播放
  return !camera?.vidBoxSerial && camera?.vidType !== 'local'
}

function isServerCamera(camera) {
  // 所有本地摄像头（USB + RTSP）统一走 MJPEG 路径（无需 SRS）
  return !camera?.vidBoxSerial
}


// ==================== 数据获取 ====================
async function getList() {
  loading.value = true
  try {
    const params = { ...queryParams }
    if (!params.vidName) delete params.vidName
    if (!params.vidSerial) delete params.vidSerial
    if (!params.vidType) delete params.vidType
    if (!params.vidBoxSerial) delete params.vidBoxSerial
    if (!params.vidSceneName) delete params.vidSceneName

    const res = await listVideo(params)
    if (res.code === 200) {
      cameraList.value = res.rows || res.data?.rows || res.data?.records || []
      total.value = res.total || res.data?.total || 0
      runningCount.value = res.runningCount || res.data?.runningCount || res.data?.running_count || 0
      stoppedCount.value = res.stoppedCount || res.data?.stoppedCount || res.data?.stopped_count || 0
      // 补充 FLV URL
      cameraList.value.forEach(camera => {
        camera.srsFlvUrl = getSrsFlvUrl(camera.vidId)
      })
    }
  } catch (err) {
    console.error('获取摄像头列表失败', err)
  } finally {
    loading.value = false
  }
}

function handleQuery() {
  queryParams.pageNum = 1
  getList()
}

function resetQuery() {
  queryParams.vidName = ''
  queryParams.vidSerial = ''
  queryParams.vidType = ''
  queryParams.vidBoxSerial = ''
  queryParams.vidSceneName = ''
  handleQuery()
}

function handleSelectionChange(val) {
  selectedCameras.value = val
  single.value = val.length !== 1
  multiple.value = !val.length
}

// ==================== CRUD ====================
function handleAdd() {
  resetForm()
  dialogTitle.value = '新增摄像头'
  dialogOpen.value = true
}

function handleUpdate(row) {
  resetForm()
  const cam = row || selectedCameras.value[0]
  if (!cam) return
  form.vidId = cam.vidId
  form.vidName = cam.vidName
  form.vidSerial = cam.vidSerial
  form.vidBoxSerial = cam.vidBoxSerial || ''
  form.vidType = cam.vidType || 'local'
  form.vidSceneName = cam.vidSceneName || ''
  form.vidUri = cam.vidUri || ''
  form.vidAnalysisMode = cam.vidAnalysisMode || 'realtime'
  dialogTitle.value = '修改摄像头'
  dialogOpen.value = true
}

function handleDelete(row) {
  const delIds = row ? [row.vidId] : selectedCameras.value.map(c => c.vidId)
  if (!delIds.length) return

  const names = row
    ? row.vidName
    : selectedCameras.value.map(c => c.vidName).join('、')

  ElMessageBox.confirm(`确定删除摄像头 "${names}" 吗？`, '提示', { type: 'warning' }).then(async () => {
    const results = await Promise.allSettled(delIds.map(id => delVideo(id)))
    const succeeded = results.filter(r => r.status === 'fulfilled').length
    const failed = results.filter(r => r.status === 'rejected').length
    if (failed === 0) {
      ElMessage.success(`删除 ${succeeded} 个摄像头成功`)
    } else {
      ElMessage.warning(`${succeeded} 个删除成功，${failed} 个失败`)
    }
    getList()
  }).catch(() => {})
}

function submitForm() {
  formRef.value?.validate(async (valid) => {
    if (!valid) return
    submitLoading.value = true
    try {
      const payload = {
        vidName: form.vidName,
        vidSerial: form.vidSerial,
        vidBoxSerial: form.vidBoxSerial,
        vidType: form.vidType,
        vidSceneName: form.vidSceneName,
        vidUri: form.vidUri,
        vidAnalysisMode: form.vidAnalysisMode
      }
      if (form.vidId) {
        payload.vidId = form.vidId
        await updateVideo(payload)
        ElMessage.success('修改成功')
      } else {
        await addVideo(payload)
        ElMessage.success('新增成功')
      }
      dialogOpen.value = false
      getList()
    } catch (err) {
      ElMessage.error(err.message || '操作失败')
    } finally {
      submitLoading.value = false
    }
  })
}

function cancel() {
  dialogOpen.value = false
}

function resetForm() {
  form.vidId = undefined
  form.vidName = ''
  form.vidSerial = ''
  form.vidBoxSerial = ''
  form.vidType = 'local'
  form.vidSceneName = ''
  form.vidUri = ''
  form.vidAnalysisMode = 'realtime'
  formRef.value?.clearValidate()
}

// ==================== 单个查看 ====================
async function handleView(row) {
  currentCamera.value = row
  viewDialogVisible.value = true
  singleVideoLoading.value = true
  useMJPEGFallback.value = false
  boxStreamSrc.value = ''
  snapshotSrc.value = ''

  if (row.deviceStatus !== 'running') {
    singleVideoLoading.value = false
    const msg = row.deviceErrorMessage || '该摄像头未运行，无法查看实时视频'
    if (row.deviceStatus === 'error') {
      ElMessage.error(msg)
    } else if (row.deviceStatus === 'offline') {
      ElMessage.warning(msg)
    } else {
      ElMessage.warning(msg)
    }
    return
  }

  // 本地摄像头（USB + RTSP）→ MJPEG 路径（无需 SRS）
  if (isServerCamera(row)) {
    console.log('[camera-list] 走本地MJPEG路径 vidId=', row.vidId, 'vidType=', row.vidType)
    destroySinglePlayer()
    await startServerCameraStream(row)
    return
  }

  // 盒子摄像头 → FLV 播放
  console.log('[camera-list] 走盒子路径 vidId=', row.vidId, 'vidBoxSerial=', row.vidBoxSerial)
  await nextTick()
  initSinglePlayer(row)
}

async function startBoxStreamPreview(vidId) {
  stopSnapshotPreview()
  useMJPEGFallback.value = true
  snapshotSrc.value = ''
  snapshotError.value = null
  try {
    const res = await getCameraStreamUrl(vidId)
    const streamUrl = res.data?.streamUrl
    if (!streamUrl) {
      throw new Error(res.msg || '盒子未返回视频流地址')
    }
    boxStreamSrc.value = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
    singleVideoLoading.value = false
  } catch (error) {
    boxStreamSrc.value = ''
    await loadSnapshot(vidId)
  }
}

async function startServerCameraStream(row) {
  stopSnapshotPreview()
  snapshotSrc.value = ''
  snapshotError.value = null
  try {
    // 异步启动（后端非阻塞，立即返回）
    await startLocalCamera(row.vidId)

    // 轮询等待摄像头连接就绪，最多等 10 秒
    let streamUrl = null
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 500))
      try {
        const res = await getLocalCameraStreamUrl(row.vidId)
        streamUrl = res.data?.streamUrl
        if (streamUrl) break
      } catch { /* 还没就绪，继续等 */ }
    }

    if (!streamUrl) {
      throw new Error('本地摄像头启动超时，请检查视频源是否可达')
    }
    boxStreamSrc.value = `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${Date.now()}`
    singleVideoLoading.value = false
  } catch (error) {
    boxStreamSrc.value = ''
    // 启动失败，尝试用快照兜底
    await loadLocalSnapshot(row.vidId)
  }
}

async function loadLocalSnapshot(vidId) {
  try {
    const data = await getLocalCameraSnapshot(vidId)
    if (!data || !data.type?.startsWith('image/')) {
      throw await readBlobError(data)
    }
    const nextUrl = URL.createObjectURL(data)
    if (snapshotObjectUrl) {
      URL.revokeObjectURL(snapshotObjectUrl)
    }
    snapshotObjectUrl = nextUrl
    snapshotSrc.value = nextUrl
    snapshotError.value = null
    singleVideoLoading.value = false
  } catch (error) {
    snapshotError.value = formatSnapshotError(error)
    singleVideoLoading.value = false
  }
}

function handleDirectStreamError() {
  const camera = currentCamera.value
  boxStreamSrc.value = ''
  if (!camera?.vidId) return
  if (isLocalUsbCamera(camera)) {
    loadLocalSnapshot(camera.vidId)
  } else if (isBoxCamera(camera)) {
    loadSnapshot(camera.vidId)
  }
  // 本地 RTSP 无 MJPEG 回退，保持错误状态
}

function retryLoadStream(camera) {
  if (!camera?.vidId) return
  if (isLocalUsbCamera(camera)) {
    startServerCameraStream(camera)
  } else {
    // 本地 RTSP 或盒子摄像头：重试 FLV
    useMJPEGFallback.value = false
    boxStreamSrc.value = ''
    snapshotSrc.value = ''
    snapshotError.value = null
    singleVideoLoading.value = true
    // 本地 RTSP 需要先触发 ffmpeg→SRS 推流
    if (isLocalRtspCamera(camera)) {
      startLocalCamera(camera.vidId).catch(() => {})
    }
    nextTick(() => initSinglePlayer(camera))
  }
}

function startSnapshotPreview(vidId) {
  stopSnapshotPreview()
  loadSnapshot(vidId)
  snapshotTimer = setInterval(() => {
    loadSnapshot(vidId)
  }, 2000)
}

function formatSnapshotError(error) {
  const rawMessage = error?.message || '获取摄像头快照失败'
  const responseData = error?.data || {}
  const triedUrls = responseData.triedUrls || []
  const detail = responseData.detail || rawMessage
  const isConnectionError = rawMessage.includes('无法连接盒子本地服务') || detail.includes('All connection attempts failed')

  if (isConnectionError) {
    return {
      title: '无法连接盒子本地服务',
      message: '请确认盒子服务已启动、网络可达，并且端口已放行。',
      detail,
      triedUrls,
    }
  }

  return {
    title: '摄像头画面暂不可用',
    message: '请稍后重试，或检查摄像头是否正在运行。',
    detail,
    triedUrls,
  }
}

async function readBlobError(data) {
  try {
    const text = await data.text()
    const parsed = JSON.parse(text)
    const error = new Error(parsed.msg || parsed.detail || '快照接口未返回图片')
    error.data = parsed.data || {}
    throw error
  } catch (error) {
    if (error?.data) throw error
    throw new Error('快照接口未返回图片')
  }
}

async function loadSnapshot(vidId) {
  try {
    const data = await getCameraSnapshot(vidId)
    if (!data || !data.type?.startsWith('image/')) {
      throw await readBlobError(data)
    }
    const nextUrl = URL.createObjectURL(data)
    if (snapshotObjectUrl) {
      URL.revokeObjectURL(snapshotObjectUrl)
    }
    snapshotObjectUrl = nextUrl
    snapshotSrc.value = nextUrl
    snapshotError.value = null
    singleVideoLoading.value = false
  } catch (error) {
    snapshotError.value = formatSnapshotError(error)
    singleVideoLoading.value = false
  }
}

function stopSnapshotPreview() {
  if (snapshotTimer) {
    clearInterval(snapshotTimer)
    snapshotTimer = null
  }
  if (snapshotObjectUrl) {
    URL.revokeObjectURL(snapshotObjectUrl)
    snapshotObjectUrl = ''
  }
  boxStreamSrc.value = ''
  snapshotError.value = ''
}

function initSinglePlayer(row) {
  if (!flvjs.isSupported()) {
    // 浏览器不支持 FLV → 盒子摄像头回退到 MJPEG 流
    if (isBoxCamera(row)) {
      startBoxStreamPreview(row.vidId)
      return
    }
    ElMessage.error('当前浏览器不支持FLV播放')
    singleVideoLoading.value = false
    return
  }

  destroySinglePlayer()

  const element = liveVideoRef.value
  if (!element) return

  const streamUrl = row.srsFlvUrl || getSrsFlvUrl(row.vidId)

  const player = flvjs.createPlayer(
    { type: 'flv', url: streamUrl },
    {
      enableWorker: false,
      enableStashBuffer: false,
      stashInitialSize: 128,
      isLive: true,
      autoCleanupSourceBuffer: true,
    }
  )

  player.attachMediaElement(element)
  player.load()

  let flvFailed = false
  player.on(flvjs.Events.ERROR, () => {
    flvFailed = true
    singleVideoLoading.value = false
    try { player.destroy() } catch (e) { /* ignore */ }
    singleFlvPlayer = null
    // 盒子摄像头：FLV 失败时回退到盒子本地 MJPEG 流
    if (isBoxCamera(row)) {
      startBoxStreamPreview(row.vidId)
    }
  })

  player.on(flvjs.Events.METADATA_ARRIVED, () => {
    singleVideoLoading.value = false
  })

  player.play().catch(() => {})
  singleFlvPlayer = player

  setTimeout(() => {
    if (singleVideoLoading.value && !flvFailed) {
      singleVideoLoading.value = false
      destroySinglePlayer()
      // 15 秒超时 → 盒子摄像头回退到 MJPEG
      if (isBoxCamera(row)) {
        startBoxStreamPreview(row.vidId)
      }
    }
  }, 15000)
}

function destroySinglePlayer() {
  if (singleFlvPlayer) {
    try { singleFlvPlayer.pause(); singleFlvPlayer.destroy() } catch (e) { /* ignore */ }
    singleFlvPlayer = null
  }
}

function closeViewDialog() {
  viewDialogVisible.value = false
  destroySinglePlayer()
  stopSnapshotPreview()
  useMJPEGFallback.value = false
  singleVideoLoading.value = true
}

// ==================== 启停 ====================
async function handleStartOne(row) {
  try {
    if (isLocalCamera(row)) {
      await startLocalCamera(row.vidId)
      ElMessage.success(`本地摄像头 ${row.vidName} 采集已启动`)
    } else {
      await startCamera(row.vidId)
      ElMessage.success(`摄像头 ${row.vidName} 启动指令已发送`)
    }
    setTimeout(() => getList(), 2000)
  } catch (err) {
    ElMessage.error('启动失败')
  }
}

async function handleStopOne(row) {
  try {
    await ElMessageBox.confirm(`确定停止摄像头 ${row.vidName} 吗？`, '提示', { type: 'warning' })
    if (isLocalCamera(row)) {
      await stopLocalCamera(row.vidId)
    } else {
      await stopCamera(row.vidId)
    }
    ElMessage.success(`摄像头 ${row.vidName} 停止指令已发送`)
    setTimeout(() => getList(), 2000)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('停止失败')
  }
}

async function handleRestartOne(row) {
  try {
    if (isLocalCamera(row)) {
      await startLocalCamera(row.vidId)
    } else {
      await startCamera(row.vidId)
    }
    ElMessage.success(`摄像头 ${row.vidName} 重试指令已发送`)
    setTimeout(() => getList(), 2000)
  } catch (err) {
    ElMessage.error('重试失败')
  }
}

async function handleBatchStart() {
  const localCams = selectedCameras.value.filter(c => isLocalCamera(c))
  const boxCams = selectedCameras.value.filter(c => isBoxCamera(c) && c.deviceStatus !== 'running')
  if (localCams.length > 0 && boxCams.length === 0) {
    ElMessage.info('所选均为本地摄像头，无需手动启动')
    return
  }
  if (boxCams.length === 0) {
    ElMessage.info('所选盒子摄像头均已运行')
    return
  }
  const results = await Promise.allSettled(boxCams.map(c => startCamera(c.vidId)))
  const succeeded = results.filter(r => r.status === 'fulfilled').length
  const failed = results.filter(r => r.status === 'rejected').length
  const skippedMsg = localCams.length > 0 ? `（已跳过 ${localCams.length} 个本地摄像头）` : ''
  ElMessage[failed === 0 ? 'success' : 'warning'](
    failed === 0 ? `已向 ${succeeded} 个摄像头发送启动指令${skippedMsg}` : `${succeeded} 个启动成功，${failed} 个失败${skippedMsg}`
  )
  setTimeout(() => getList(), 3000)
}

async function handleBatchStop() {
  const localCams = selectedCameras.value.filter(c => isLocalCamera(c))
  const boxCams = selectedCameras.value.filter(c => isBoxCamera(c) && c.deviceStatus === 'running')
  if (localCams.length > 0 && boxCams.length === 0) {
    ElMessage.info('所选均为本地摄像头，无需手动停止')
    return
  }
  if (boxCams.length === 0) {
    ElMessage.info('所选盒子摄像头均已停止')
    return
  }
  const names = boxCams.map(c => c.vidName).join('、')
  try {
    const skipNote = localCams.length > 0 ? `\n（本地摄像头无需停止，共 ${localCams.length} 个）` : ''
    await ElMessageBox.confirm(`确定停止以下摄像头吗？\n${names}${skipNote}`, '批量停止', { type: 'warning' })
    const results = await Promise.allSettled(boxCams.map(c => stopCamera(c.vidId)))
    const succeeded = results.filter(r => r.status === 'fulfilled').length
    const failed = results.filter(r => r.status === 'rejected').length
    ElMessage[failed === 0 ? 'success' : 'warning'](
      failed === 0 ? `已向 ${succeeded} 个摄像头发送停止指令` : `${succeeded} 个停止成功，${failed} 个失败`
    )
    setTimeout(() => getList(), 3000)
  } catch (err) {
    if (err !== 'cancel') ElMessage.error('停止失败')
  }
}

// ==================== 批量查看 ====================
function gridClass(count) {
  return { single: count === 1, double: count === 2, quad: count >= 3 }
}

async function handleBatchView() {
  const maxVideos = 4
  const currentWindows = openedWindows.value.length
  if (currentWindows >= maxVideos) {
    ElMessage.warning('最多同时播放4路视频')
    return
  }

  const runningCams = selectedCameras.value.filter(c => c.deviceStatus === 'running')
  if (runningCams.length === 0) {
    ElMessage.warning('所选摄像头均未运行，无法查看实时视频')
    return
  }

  const stoppedCount = selectedCameras.value.length - runningCams.length
  if (stoppedCount > 0) {
    ElMessage.warning(`已跳过 ${stoppedCount} 个未运行的摄像头`)
  }

  const remainingSlots = maxVideos - currentWindows
  const videosToOpen = runningCams.slice(0, remainingSlots)

  const windowId = 'batch_' + Date.now() + '_' + Math.floor(Math.random() * 1000)
  const videoStreams = videosToOpen.map(v => ({
    id: v.vidId,
    name: v.vidName,
    url: v.srsFlvUrl || getSrsFlvUrl(v.vidId),
  }))

  const windowData = reactive({
    id: windowId,
    visible: true,
    videoStreams,
    flvPlayers: [],
    videoLoading: new Array(videoStreams.length).fill(true),
  })

  openedWindows.value.push(windowData)
  batchViewDialogs.value.push(windowData)

  await nextTick()
  initBatchPlayers(windowData)
}

function initBatchPlayers(windowData) {
  if (!flvjs.isSupported()) {
    ElMessage.error('当前浏览器不支持FLV播放')
    return
  }

  windowData.videoStreams.forEach((stream, index) => {
    const element = document.querySelector(`#batchVideo-${windowData.id}-${index}`)
    if (!element || !stream.url) return

    const player = flvjs.createPlayer(
      { type: 'flv', url: stream.url },
      {
        enableWorker: false,
        enableStashBuffer: false,
        stashInitialSize: 128,
        isLive: true,
        autoCleanupSourceBuffer: true,
      }
    )

    player.attachMediaElement(element)
    player.load()

    player.on(flvjs.Events.ERROR, () => {
      windowData.videoLoading[index] = false
      try { player.destroy() } catch (e) { /* ignore */ }
    })

    player.on(flvjs.Events.METADATA_ARRIVED, () => {
      windowData.videoLoading[index] = false
    })

    player.play().catch(() => {})
    windowData.flvPlayers[index] = player
  })

  setTimeout(() => {
    windowData.videoLoading.forEach((loading, i) => {
      if (loading) {
        windowData.videoLoading[i] = false
        if (windowData.flvPlayers[i]) {
          try { windowData.flvPlayers[i].destroy() } catch (e) { /* ignore */ }
          windowData.flvPlayers[i] = null
        }
      }
    })
  }, 30000)
}

function closeBatchViewDialog(windowId) {
  const idx = openedWindows.value.findIndex(w => w.id === windowId)
  if (idx > -1) {
    const w = openedWindows.value[idx]
    if (w.flvPlayers) {
      w.flvPlayers.forEach(p => {
        if (p) try { p.pause(); p.destroy() } catch (e) { /* ignore */ }
      })
    }
    openedWindows.value.splice(idx, 1)
  }

  const dIdx = batchViewDialogs.value.findIndex(d => d.id === windowId)
  if (dIdx > -1) batchViewDialogs.value.splice(dIdx, 1)
}

// ==================== 本地算法运行记录 ====================
async function handleRunHistory(row) {
  runHistoryCamera.value = row
  runHistoryVisible.value = true
  runHistoryPage.pageNum = 1
  await loadRunHistory()
}

async function loadRunHistory() {
  if (!runHistoryCamera.value) return
  runHistoryLoading.value = true
  try {
    const res = await getLocalCameraRuns(runHistoryCamera.value.vidId, runHistoryPage.pageNum, runHistoryPage.pageSize)
    if (res.code === 200 && res.data) {
      runHistoryList.value = res.data.rows || []
      runHistoryTotal.value = res.data.total || 0
    }
  } catch { /* ignore */ }
  finally { runHistoryLoading.value = false }
}

function runStatusLabel(s) {
  return { running: '运行中', completed: '已完成', failed: '失败', stopped: '已停止' }[s] || s
}

// ==================== 自动刷新 ====================
watch(autoRefresh, (val) => {
  if (val) {
    refreshTimer = setInterval(getList, 5000)
  } else {
    if (refreshTimer) clearInterval(refreshTimer)
  }
})

onMounted(() => {
  getList()
  fetchBoxes()
  if (autoRefresh.value) {
    refreshTimer = setInterval(getList, 5000)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  stopSnapshotPreview()
  destroySinglePlayer()
  openedWindows.value.forEach(w => {
    if (w.flvPlayers) {
      w.flvPlayers.forEach(p => {
        if (p) try { p.destroy() } catch (e) { /* ignore */ }
      })
    }
  })
})
</script>

<style scoped>
.camera-list-container {
  padding: 20px;
}

.stat-card {
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.stat-content {
  display: flex;
  align-items: center;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 12px;
}

.stat-icon.total { background: linear-gradient(135deg, #667eea, #764ba2); }
.stat-icon.running { background: linear-gradient(135deg, #67C23A, #85CE61); }
.stat-icon.stopped { background: linear-gradient(135deg, #909399, #B4B4B8); }
.stat-icon.selected { background: linear-gradient(135deg, #409EFF, #66B1FF); }

.stat-icon .el-icon {
  font-size: 22px;
  color: #fff;
}

.stat-title {
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.mb4 { margin-bottom: 20px; }
.mb8 { margin-bottom: 10px; }

.status-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 4px;
}

.status-dot.running {
  background: #67C23A;
  box-shadow: 0 0 4px #67C23A;
}

.status-dot.stopped,
.status-dot.unknown {
  background: #C0C4CC;
}

.status-dot.error {
  background: #F56C6C;
  box-shadow: 0 0 4px #F56C6C;
}

.status-dot.offline {
  background: #E6A23C;
  box-shadow: 0 0 4px #E6A23C;
}

.view-content {
  display: flex;
  gap: 20px;
  height: 50vh;
}

.video-section {
  flex: 2;
}

.video-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #000;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}

.single-view { min-height: 300px; }

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
  z-index: 1;
}

.video-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  z-index: 2;
}

.video-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 24px;
  color: #fff;
  text-align: center;
  z-index: 2;
}

.error-title {
  font-size: 18px;
  font-weight: 600;
}

.error-message {
  font-size: 14px;
  color: #dcdfe6;
}

.error-detail {
  max-width: 100%;
  padding: 8px 10px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.12);
  color: #c0c4cc;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}

.video-placeholder p {
  margin-top: 8px;
  font-size: 14px;
}

.info-section {
  flex: 1;
}

.video-grid {
  display: grid;
  gap: 10px;
  height: 60vh;
}

.video-grid.single { grid-template-columns: 1fr; }
.video-grid.double { grid-template-columns: 1fr 1fr; }
.video-grid.quad { grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; }

.video-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.video-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.video-title {
  font-size: 13px;
  font-weight: 500;
}

.dialog-footer {
  text-align: right;
}

:deep(.el-tag) {
  font-size: 12px;
}
</style>
