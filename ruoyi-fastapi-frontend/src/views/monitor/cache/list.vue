<template>
  <div class="app-container cache-list">
    <el-row :gutter="24">
      <!-- 缓存列表 -->
      <el-col :span="8">
        <el-card shadow="never" class="info-card" style="height: calc(100vh - 140px)">
          <template #header>
            <div class="card-header-title">
              <el-icon><Collection /></el-icon>
              <span>缓存列表</span>
              <el-button link type="primary" icon="Refresh" @click="refreshCacheNames()" style="margin-left: auto" class="white-link-button"/>
            </div>
          </template>
          <el-table
            v-loading="loading"
            :data="cacheNames"
            height="100%"
            highlight-current-row
            @row-click="getCacheKeys"
            style="width: 100%"
          >
            <el-table-column label="序号" width="80" type="index" align="center" />
            <el-table-column label="缓存名称" prop="cacheName" min-width="160" show-overflow-tooltip :formatter="nameFormatter" />
            <el-table-column label="备注" prop="remark" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click.stop="handleClearCacheName(scope.row)" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 键名列表 -->
      <el-col :span="8">
        <el-card shadow="never" class="info-card" style="height: calc(100vh - 140px)">
          <template #header>
            <div class="card-header-title">
              <el-icon><Key /></el-icon>
              <span>键名列表</span>
              <el-button link type="primary" icon="Refresh" @click="refreshCacheKeys()" style="margin-left: auto" />
            </div>
          </template>
          <el-table
            v-loading="subLoading"
            :data="cacheKeys"
            height="100%"
            highlight-current-row
            @row-click="handleCacheValue"
            style="width: 100%"
          >
            <el-table-column label="序号" width="80" type="index" align="center" />
            <el-table-column label="缓存键名" min-width="300" show-overflow-tooltip :formatter="keyFormatter" />
            <el-table-column label="操作" width="80" align="center">
              <template #default="scope">
                <el-button link type="danger" icon="Delete" @click.stop="handleClearCacheKey(scope.row)" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 缓存内容 -->
      <el-col :span="8">
        <el-card shadow="never" class="info-card" style="height: calc(100vh - 140px)">
          <template #header>
            <div class="card-header-title">
              <el-icon><Document /></el-icon>
              <span>缓存内容</span>
              <el-button link type="primary" @click="handleClearCacheAll()" style="margin-left: auto">
                清理全部
              </el-button>
            </div>
          </template>
          <el-form :model="cacheForm" label-width="100px" class="content-form">
            <el-form-item label="缓存名称">
              <el-input v-model="cacheForm.cacheName" readonly />
            </el-form-item>
            <el-form-item label="缓存键名">
              <el-input v-model="cacheForm.cacheKey" readonly />
            </el-form-item>
            <el-form-item label="缓存内容">
              <el-input
                v-model="cacheForm.cacheValue"
                type="textarea"
                :rows="12"
                readonly
                placeholder="请选择左侧键名查看内容"
              />
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="CacheList">
import { listCacheName, listCacheKey, getCacheValue, clearCacheName, clearCacheKey, clearCacheAll } from "@/api/monitor/cache";

const { proxy } = getCurrentInstance();

const cacheNames = ref([]);
const cacheKeys = ref([]);
const cacheForm = ref({});
const loading = ref(true);
const subLoading = ref(false);
const nowCacheName = ref("");
const tableHeight = ref(window.innerHeight - 200);

/** 查询缓存名称列表 */
function getCacheNames() {
  loading.value = true;
  listCacheName().then(response => {
    cacheNames.value = response.data;
    loading.value = false;
  });
}

/** 刷新缓存名称列表 */
function refreshCacheNames() {
  getCacheNames();
  proxy.$modal.msgSuccess("刷新缓存列表成功");
}

/** 清理指定名称缓存 */
function handleClearCacheName(row) {
  clearCacheName(row.cacheName).then(response => {
    proxy.$modal.msgSuccess("清理缓存名称[" + row.cacheName + "]成功");
    getCacheKeys();
  });
}

/** 查询缓存键名列表 */
function getCacheKeys(row) {
  const cacheName = row !== undefined ? row.cacheName : nowCacheName.value;
  if (cacheName === "") {
    return;
  }
  subLoading.value = true;
  listCacheKey(cacheName).then(response => {
    cacheKeys.value = response.data;
    subLoading.value = false;
    nowCacheName.value = cacheName;
  });
}

/** 刷新缓存键名列表 */
function refreshCacheKeys() {
  getCacheKeys();
  proxy.$modal.msgSuccess("刷新键名列表成功");
}

/** 清理指定键名缓存 */
function handleClearCacheKey(cacheKey) {
  clearCacheKey(cacheKey).then(response => {
    proxy.$modal.msgSuccess("清理缓存键名[" + cacheKey + "]成功");
    getCacheKeys();
  });
}

/** 列表前缀去除 */
function nameFormatter(row) {
  return row.cacheName.replace(":", "");
}

/** 键名前缀去除 */
function keyFormatter(cacheKey) {
  return cacheKey.replace(nowCacheName.value, "");
}

/** 查询缓存内容详细 */
function handleCacheValue(cacheKey) {
  getCacheValue(nowCacheName.value, cacheKey).then(response => {
    cacheForm.value = response.data;
  });
}

/** 清理全部缓存 */
function handleClearCacheAll() {
  clearCacheAll().then(response => {
    proxy.$modal.msgSuccess("清理全部缓存成功");
  });
}

getCacheNames();
</script>
<style lang="scss" scoped>
  .cache-list {
    padding: 20px;
    background: linear-gradient(to bottom, #f8fbff, #eef2f7);
    min-height: 100vh;
    background: var(--el-bg-color-page) !important;
  }
  
  .info-card {
    border-radius: 16px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
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
      width: 100%;
    }
  
    :deep(.el-table) {
      flex: 1;
  
      th.el-table__cell {
        background: #409eff !important;
        color: #fff;
        font-weight: 600;
        font-size: 15px;
        height: 56px;
      }
  
      td.el-table__cell {
        height: 60px;
      }
  
      .el-table__row:hover {
        background: rgba(102, 126, 234, 0.06);
      }
    }

  
  .content-form {
    padding: 20px 24px 0;
    height: 100%;
    display: flex;
    flex-direction: column;
  
    :deep(.el-form-item) {
      margin-bottom: 24px;
    }
  
    :deep(.el-textarea__inner) {
    font-family: 'Courier New', Courier, monospace;
    background: var(--el-input-bg-color, var(--el-bg-color)) !important;
    color: var(--el-text-color-primary) !important;
  }
  }
  </style>