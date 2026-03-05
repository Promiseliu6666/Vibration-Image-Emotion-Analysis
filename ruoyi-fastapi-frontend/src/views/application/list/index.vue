<template>
  <div class="app-container">
    <!-- 搜索表单 -->
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="场景名称" prop="sceneName">
        <el-input
          v-model="queryParams.sceneName"
          placeholder="请输入场景名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="场景编号" prop="sceneSerial">
        <el-input
          v-model="queryParams.sceneSerial"
          placeholder="请输入场景编号"
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
      <!-- <el-col :span="1.5">
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
      </el-col> -->
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <!-- 数据表格 -->
    <el-table
      v-loading="loading"
      :data="sceneList"
      @selection-change="handleSelectionChange"
    >
      <!-- <el-table-column type="selection" width="55" align="center" /> -->
      <el-table-column label="序号" type="index" width="80" align="center">
        <template #default="scope">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + scope.$index + 1 }}</span>
        </template>
      </el-table-column>
<el-table-column label="场景名称" align="center" prop="sceneName" :show-overflow-tooltip="true" />
      <el-table-column label="场景编号" align="center" prop="sceneSerial" :show-overflow-tooltip="true" />
      <el-table-column label="更新时间" align="center" prop="sceneUpdateTime" :show-overflow-tooltip="true" />
      <el-table-column label="算法数量" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <!-- <el-tag v-for="value in scope.row.sceneAlgorithmData" style="margin-right: 5px; margin-bottom: 5px; ">{{ value }}</el-tag> -->
           <div>{{ scope.row.sceneAlgorithm.length }} 个</div>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="showSceneDetail(scope.row)">详情</el-button>
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

    <!-- 场景详细信息弹框 -->
    <el-dialog
      v-model="sceneDetailOpen"
      title="场景详细信息"
      width="800px"
      :before-close="() => { sceneDetailOpen = false }"
    >
      <el-form :model="sceneDetail" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="场景名称:">
              <span>{{ sceneDetail.scene_name }}</span>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="场景编号:">
              <span>{{ sceneDetail.scene_serial }}</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="更新时间:">
              <span>{{ sceneDetail.scene_update_time }}</span>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="算法列表:">
              <el-table :data="sceneDetail.alg_details" style="width: 100%" max-height="300">
                <el-table-column prop="algName" label="算法名称" width="150" />
                <el-table-column prop="algVersion" label="算法版本" width="150" />
                <el-table-column prop="algSerial" label="算法编号" />
              </el-table>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="sceneDetailOpen = false">关闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="Scene">
import { ref, reactive, toRefs, getCurrentInstance } from 'vue'
import { listScene, addScene, updateScene, delScene, getScene } from '@/api/xuzhou/scene'

const { proxy } = getCurrentInstance();

const sceneList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");

// 场景详细信息相关
const sceneDetail = ref({});
const sceneDetailOpen = ref(false);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    sceneName: undefined,
    sceneSerial: undefined
  },
  rules: {
    sceneName: [{ required: true, message: "场景名称不能为空", trigger: "blur" }],
    sceneSerial: [{ required: true, message: "场景编号不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询场景列表 */
function getList() {
  loading.value = true;
  // 调用场景API获取数据
  listScene(queryParams.value).then(response => {
    sceneList.value = response.rows;
    total.value = response.total;
    loading.value = false;
    sceneList.value.forEach((e) => {
      try {
        e.sceneAlgorithmData = JSON.parse(e.sceneAlgorithmName);
      } catch (error) {
        console.error("解析算法名称失败:", error);
        e.sceneAlgorithmData = [];
      }
    });
    console.log(sceneList.value);
    
  }).catch(error => {
    proxy.$modal.notifyError("获取场景列表失败");
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
  ids.value = selection.map(item => item.sceneId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  // 实际实现中这里会打开新增对话框
  proxy.$modal.msgSuccess("新增按钮功能待实现");
}

/** 修改按钮操作 */
function handleUpdate(row) {
  // 实际实现中这里会打开修改对话框
  proxy.$modal.msgSuccess("修改按钮功能待实现");
}

/** 删除按钮操作 */
function handleDelete(row) {
  const sceneIds = row.sceneId || ids.value.join(",");
  proxy.$modal.confirm('是否确认删除场景编号为"' + sceneIds + '"的数据项？').then(function() {
    // 调用删除API
    return delScene(sceneIds);
  }).then(() => {
    proxy.$modal.msgSuccess("删除成功");
    getList();
  }).catch(() => {});
}

/** 获取场景详细信息 */
function getSceneDetail(sceneId) {
  getScene(sceneId).then(response => {
    sceneDetail.value = response.data;
    sceneDetailOpen.value = true;
  }).catch(error => {
    proxy.$modal.notifyError("获取场景详细信息失败");
  });
}

/** 显示场景详细信息弹框 */
function showSceneDetail(row) {
  getSceneDetail(row.sceneId);
}

// 初始化数据
getList();
</script>
