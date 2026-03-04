<template>
  <div class="app-container">
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
        <el-select v-model="queryParams.vidType" placeholder="请选择视频类型" clearable filterable style="width: 240px">
          <el-option label="hik" value="hik"/>
          <el-option label="rtsp" value="rtsp"/>
          <el-option label="rtmp" value="rtmp"/>
          <el-option label="file" value="file"/>
        </el-select>
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
          type="primary"
          plain
          icon="Plus"
          @click="handleAdd"
        >新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <!-- 数据表格 -->
    <el-table
      v-loading="loading"
      :data="videoList"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="序号" type="index" width="80" align="center">
        <template #default="scope">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + scope.$index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="视频名称" align="center" prop="vidName" :show-overflow-tooltip="true" />
      <el-table-column label="视频序列号" align="center" prop="vidSerial" :show-overflow-tooltip="true" />
      <el-table-column label="视频类型" align="center" prop="vidType" :show-overflow-tooltip="true" />
      <el-table-column label="场景名称" align="center" prop="vidSceneName" :show-overflow-tooltip="true" />
      <el-table-column label="算法名称" align="center" prop="vidAlgorithmName" :show-overflow-tooltip="true" />
      <el-table-column label="更新时间" align="center" prop="vidUpdateTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.vidUpdateTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)">修改</el-button>
          <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)">删除</el-button>
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
  </div>
</template>

<script setup name="Video">
import { ref, reactive, toRefs, getCurrentInstance } from 'vue'
import { listVideo, delVideo } from '@/api/xuzhou/video'
import { parseTime } from '@/utils/ruoyi'

const { proxy } = getCurrentInstance();

const videoList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    vidName: undefined,
    vidSerial: undefined,
    vidType: undefined,
    vidSceneName: undefined
  },
  rules: {
    vidName: [{ required: true, message: "视频名称不能为空", trigger: "blur" }],
    vidSerial: [{ required: true, message: "视频序列号不能为空", trigger: "blur" }],
    vidType: [{ required: true, message: "视频类型不能为空", trigger: "blur" }],
    vidSceneName: [{ required: true, message: "场景名称不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询视频列表 */
function getList() {
  loading.value = true;
  listVideo(queryParams.value).then(response => {
    videoList.value = response.rows;
    total.value = response.total;
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

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}

/** 选择条数  */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.vidId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  proxy.$router.push({
    path: '/VideoStream/VideoEdit',
    query: {}
  });
}

/** 修改按钮操作 */
function handleUpdate(row) {
  const vidId = row.vidId || ids.value[0];
  // 使用sessionStorage存储整行数据，避免URL长度限制
  const rowData = row.vidId ? row : videoList.value.find(item => item.vidId === vidId);
  const storageKey = `video_row_data_${vidId}_${Date.now()}`;
  sessionStorage.setItem(storageKey, JSON.stringify(rowData));
  
  proxy.$router.push({
    path: '/VideoStream/VideoEdit',
    query: { 
      vidId,
      storageKey
    }
  });
}

/** 删除按钮操作 */
function handleDelete(row) {
  const videoIds = row.vidId || ids.value;
  proxy.$modal.confirm('是否确认删除视频ID为"' + videoIds + '"的数据项？').then(function() {
    return delVideo(videoIds);
  }).then(() => {
    proxy.$modal.msgSuccess("删除成功");
    getList();
  }).catch(() => {});
}

// 初始化数据
getList();
</script>
