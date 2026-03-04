<template>
   <div class="app-container config-management">
      <!-- 搜索区域 -->
      <el-card shadow="never" class="search-card mb20">
         <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
            <el-form-item label="参数名称" prop="configName">
               <el-input
                  v-model="queryParams.configName"
                  placeholder="请输入参数名称"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="参数键名" prop="configKey">
               <el-input
                  v-model="queryParams.configKey"
                  placeholder="请输入参数键名"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="系统内置" prop="configType">
               <el-select v-model="queryParams.configType" placeholder="系统内置" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_yes_no"
                     :key="dict.value"
                     :label="dict.label"
                     :value="dict.value"
                  />
               </el-select>
            </el-form-item>
            <el-form-item label="创建时间">
               <el-date-picker
                  v-model="dateRange"
                  value-format="YYYY-MM-DD"
                  type="daterange"
                  range-separator="-"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  style="width: 280px"
               />
            </el-form-item>
            <el-form-item>
               <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
               <el-button icon="Refresh" @click="resetQuery">重置</el-button>
            </el-form-item>
         </el-form>
      </el-card>

      <!-- 操作按钮栏 -->
      <div class="action-bar mb20">
         <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['system:config:add']">
            新增
         </el-button>
         <el-button type="success" icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['system:config:edit']">
            修改
         </el-button>
         <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['system:config:remove']">
            删除
         </el-button>
         <el-button type="warning" icon="Download" @click="handleExport" v-hasPermi="['system:config:export']">
            导出
         </el-button>
         <el-button type="danger" icon="Refresh" @click="handleRefreshCache" v-hasPermi="['system:config:remove']">
            刷新缓存
         </el-button>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </div>

      <!-- 参数配置表格 -->
      <el-card shadow="never" class="table-card">
         <el-table
            v-loading="loading"
            :data="configList"
            @selection-change="handleSelectionChange"
            style="width: 100%"
            :row-style="{ height: '60px' }"
         >
            <el-table-column type="selection" width="55" align="center" />
            <el-table-column label="参数主键" align="center" prop="configId" width="100" />
            <el-table-column label="参数名称" align="center" prop="configName" min-width="180" show-overflow-tooltip />
            <el-table-column label="参数键名" align="center" prop="configKey" min-width="200" show-overflow-tooltip />
            <el-table-column label="参数键值" align="center" prop="configValue" min-width="220" show-overflow-tooltip />
            <el-table-column label="系统内置" width="120" align="center">
               <template #default="scope">
                  <dict-tag :options="sys_yes_no" :value="scope.row.configType" />
               </template>
            </el-table-column>
            <el-table-column label="备注" align="center" min-width="200" prop="remark" show-overflow-tooltip />
            <el-table-column label="创建时间" width="180" align="center">
               <template #default="scope">
                  <span>{{ parseTime(scope.row.createTime) }}</span>
               </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="160" align="center">
               <template #default="scope">
                  <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:config:edit']">修改</el-button>
                  <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:config:remove']">删除</el-button>
               </template>
            </el-table-column>
         </el-table>

         <pagination
            v-show="total > 0"
            :total="total"
            v-model:page="queryParams.pageNum"
            v-model:limit="queryParams.pageSize"
            @pagination="getList"
            class="pagination-center"
         />
      </el-card>

      <!-- 添加或修改参数配置对话框 -->
      <el-dialog :title="title" v-model="open" width="680px" append-to-body destroy-on-close class="config-dialog">
         <el-form ref="configRef" :model="form" :rules="rules" label-width="100px">
            <el-row :gutter="30">
               <el-col :span="24">
                  <el-form-item label="参数名称" prop="configName">
                     <el-input v-model="form.configName" placeholder="请输入参数名称" />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="参数键名" prop="configKey">
                     <el-input v-model="form.configKey" placeholder="请输入参数键名" />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="参数键值" prop="configValue">
                     <el-input
                        v-model="form.configValue"
                        type="textarea"
                        :rows="4"
                        placeholder="请输入参数键值"
                     />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="系统内置" prop="configType">
                     <el-radio-group v-model="form.configType">
                        <el-radio
                           v-for="dict in sys_yes_no"
                           :key="dict.value"
                           :value="dict.value"
                        >{{ dict.label }}</el-radio>
                     </el-radio-group>
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="备注">
                     <el-input
                        v-model="form.remark"
                        type="textarea"
                        :rows="4"
                        placeholder="请输入内容"
                     />
                  </el-form-item>
               </el-col>
            </el-row>
         </el-form>
         <template #footer>
            <div class="dialog-footer">
               <el-button type="primary" @click="submitForm">确 定</el-button>
               <el-button @click="cancel">取 消</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="Config">
import { listConfig, getConfig, delConfig, addConfig, updateConfig, refreshCache } from "@/api/system/config";

const { proxy } = getCurrentInstance();
const { sys_yes_no } = proxy.useDict("sys_yes_no");

const configList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    configName: undefined,
    configKey: undefined,
    configType: undefined
  },
  rules: {
    configName: [{ required: true, message: "参数名称不能为空", trigger: "blur" }],
    configKey: [{ required: true, message: "参数键名不能为空", trigger: "blur" }],
    configValue: [{ required: true, message: "参数键值不能为空", trigger: "blur" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询参数列表 */
function getList() {
  loading.value = true;
  listConfig(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    configList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}
/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}
/** 表单重置 */
function reset() {
  form.value = {
    configId: undefined,
    configName: undefined,
    configKey: undefined,
    configValue: undefined,
    configType: "Y",
    remark: undefined
  };
  proxy.resetForm("configRef");
}
/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1;
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  dateRange.value = [];
  proxy.resetForm("queryRef");
  handleQuery();
}
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.configId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加参数";
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const configId = row.configId || ids.value;
  getConfig(configId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改参数";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["configRef"].validate(valid => {
    if (valid) {
      if (form.value.configId != undefined) {
        updateConfig(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addConfig(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}
/** 删除按钮操作 */
function handleDelete(row) {
  const configIds = row.configId || ids.value;
  proxy.$modal.confirm('是否确认删除参数编号为"' + configIds + '"的数据项？').then(function () {
    return delConfig(configIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download("system/config/export", {
    ...queryParams.value
  }, `config_${new Date().getTime()}.xlsx`);
}
/** 刷新缓存按钮操作 */
function handleRefreshCache() {
  refreshCache().then(() => {
    proxy.$modal.msgSuccess("刷新缓存成功");
  });
}

getList();
</script>
<style lang="scss" scoped>
   .config-management {
     padding: 20px;
     background: linear-gradient(to bottom, #f8fbff, #eef2f7);
     min-height: 100vh;
     background: var(--el-bg-color-page) !important;
   }
   
   /* 搜索卡片 */
   .search-card {
     border-radius: 16px;
     box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
     padding: 4px 0;
   }
   
   /* 操作栏 */
   .action-bar {
     background: #fff;
     padding: 16px 24px;
     border-radius: 16px;
     box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
     display: flex;
     align-items: center;
     gap: 12px;
     flex-wrap: wrap;
     background: var(--el-bg-color-page) !important;
   }
   
   /* 表格卡片 */
   .table-card {
     border-radius: 16px;
     overflow: hidden;
     box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
   }
     :deep(.el-table) {
       border-radius: 16px;
   
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
   
       .el-table__row {
         transition: all 0.3s;
   
         &:hover {
           background: rgba(102, 126, 234, 0.06);
         }
       }
     }
   
   .pagination-center {
     margin: 24px 0;
     text-align: center;
   }
   
   /* 输入框统一美化 */
   :deep(.el-input__wrapper) {
     height: 48px;
     border-radius: 12px;
     box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
   
     &:hover,
     &.is-focus {
       box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
     }
   }
   
   :deep(.el-select .el-input__wrapper) {
     height: 48px;
   }
   
   :deep(.el-date-editor) {
     height: 48px;
     border-radius: 12px;
   
     .el-range-input {
       height: 38px;
     }
   }
   
   /* 对话框 */
   .config-dialog {
     :deep(.el-dialog__header) {
       background: linear-gradient(120deg, #667eea, #764ba2);
       color: #fff;
       padding: 20px 24px;
       margin: 0;
       font-size: 18px;
       font-weight: 600;
       border-radius: 16px 16px 0 0;
     }
   
     :deep(.el-dialog__body) {
       padding: 30px 24px;
     }
   }
   
   /* 表单项间距 */
   :deep(.el-form-item) {
     margin-bottom: 24px;
   }
   
   /* 按钮美化 */
   :deep(.el-button) {
     border-radius: 12px;
     height: 44px;
     padding: 0 24px;
     font-weight: 500;
   }
   
   .dialog-footer {
     text-align: right;
     padding-top: 10px;
   }
   </style>