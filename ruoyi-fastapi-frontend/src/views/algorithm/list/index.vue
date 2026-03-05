<template>
  <div class="app-container">
    <!-- 搜索表单 -->
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="算法名称" prop="algorithmName">
        <el-input
          v-model="queryParams.algorithmName"
          placeholder="请输入算法名称"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <!-- <el-form-item label="算法版本" prop="algorithmVersion">
        <el-input
          v-model="queryParams.algorithmVersion"
          placeholder="请输入算法版本"
          clearable
          style="width: 240px"
          @keyup.enter="handleQuery"
        />
      </el-form-item> -->
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
      :data="algorithmList"
      @selection-change="handleSelectionChange"
    >
      <!-- <el-table-column type="selection" width="55" align="center" /> -->
      <el-table-column label="序号" type="index" width="80" align="center">
        <template #default="scope">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + scope.$index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column label="算法名称" align="center" prop="algName" :show-overflow-tooltip="true" />
      <el-table-column label="算法编号" align="center" prop="algSerial" :show-overflow-tooltip="true" />
      <el-table-column label="算法版本" align="center" prop="algVersion" :show-overflow-tooltip="true" />
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-button link type="primary" icon="View" @click="showSceneDetail(scope.row)">详情</el-button>
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

<script setup name="Algorithm">
import { ref, reactive, toRefs, getCurrentInstance } from 'vue'
import { listAlgorithm } from '@/api/xuzhou/algorithm'

const { proxy } = getCurrentInstance();

const algorithmList = ref([]);
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
    algorithmName: undefined,
    algorithmVersion: undefined
  },
  rules: {
    algorithmName: [{ required: true, message: "算法名称不能为空", trigger: "blur" }],
    algorithmVersion: [{ required: true, message: "算法版本不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询算法列表 */
function getList() {
  loading.value = true;
  listAlgorithm(queryParams.value).then(response => {
    algorithmList.value = response.rows;
    total.value = response.total;
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
  ids.value = selection.map(item => item.id);
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

function showSceneDetail(row) {
  
}

/** 删除按钮操作 */
function handleDelete(row) {
  const algorithmIds = row.id || ids.value;
  proxy.$modal.confirm('是否确认删除算法编号为"' + algorithmIds + '"的数据项？').then(function() {
    // 实际实现中这里会调用删除API
    proxy.$modal.msgSuccess("删除成功");
    getList();
  }).catch(() => {});
}

// 初始化数据
getList();
</script>
