<template>
   <div class="app-container operlog-management">
      <!-- 搜索区域 -->
      <el-card shadow="never" class="search-card mb20">
         <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
            <el-form-item label="操作地址" prop="operIp">
               <el-input
                  v-model="queryParams.operIp"
                  placeholder="请输入操作地址"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="系统模块" prop="title">
               <el-input
                  v-model="queryParams.title"
                  placeholder="请输入系统模块"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="操作人员" prop="operName">
               <el-input
                  v-model="queryParams.operName"
                  placeholder="请输入操作人员"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="类型" prop="businessType">
               <el-select v-model="queryParams.businessType" placeholder="操作类型" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_oper_type"
                     :key="dict.value"
                     :label="dict.label"
                     :value="dict.value"
                  />
               </el-select>
            </el-form-item>
            <el-form-item label="状态" prop="status">
               <el-select v-model="queryParams.status" placeholder="操作状态" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_common_status"
                     :key="dict.value"
                     :label="dict.label"
                     :value="dict.value"
                  />
               </el-select>
            </el-form-item>
            <el-form-item label="操作时间">
               <el-date-picker
                  v-model="dateRange"
                  value-format="YYYY-MM-DD HH:mm:ss"
                  type="daterange"
                  range-separator="-"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  :default-time="[new Date(2000, 1, 1, 0, 0, 0), new Date(2000, 1, 1, 23, 59, 59)]"
                  style="width: 380px"
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
         <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['monitor:operlog:remove']">
            删除
         </el-button>
         <el-button type="danger" icon="Delete" @click="handleClean" v-hasPermi="['monitor:operlog:remove']">
            清空
         </el-button>
         <el-button type="warning" icon="Download" @click="handleExport" v-hasPermi="['monitor:operlog:export']">
            导出
         </el-button>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </div>

      <!-- 操作日志表格 -->
      <el-card shadow="never" class="table-card">
         <el-table
            ref="operlogRef"
            v-loading="loading"
            :data="operlogList"
            @selection-change="handleSelectionChange"
            :default-sort="defaultSort"
            @sort-change="handleSortChange"
            style="width: 100%"
            :row-style="{ height: '60px' }"
         >
            <el-table-column type="selection" width="55" align="center" />
            <el-table-column label="日志编号" align="center" prop="operId" width="100" />
            <el-table-column label="系统模块" align="center" prop="title" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作类型" align="center" width="120">
               <template #default="scope">
                  <dict-tag :options="sys_oper_type" :value="scope.row.businessType" />
               </template>
            </el-table-column>
            <el-table-column label="操作人员" align="center" width="120" prop="operName" show-overflow-tooltip sortable="custom" :sort-orders="['descending', 'ascending']" />
            <el-table-column label="操作地址" align="center" prop="operIp" width="140" show-overflow-tooltip />
            <el-table-column label="操作状态" align="center" width="120">
               <template #default="scope">
                  <dict-tag :options="sys_common_status" :value="scope.row.status" />
               </template>
            </el-table-column>
            <el-table-column label="操作日期" align="center" prop="operTime" width="180" sortable="custom" :sort-orders="['descending', 'ascending']">
               <template #default="scope">
                  <span>{{ parseTime(scope.row.operTime) }}</span>
               </template>
            </el-table-column>
            <el-table-column label="消耗时间" align="center" prop="costTime" width="120" show-overflow-tooltip sortable="custom" :sort-orders="['descending', 'ascending']">
               <template #default="scope">
                  <span>{{ scope.row.costTime }}毫秒</span>
               </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="100" align="center">
               <template #default="scope">
                  <el-button link type="primary" icon="View" @click="handleView(scope.row, scope.index)" v-hasPermi="['monitor:operlog:query']">详细</el-button>
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

      <!-- 操作日志详细对话框 -->
      <el-dialog title="操作日志详细" v-model="open" width="900px" append-to-body destroy-on-close class="operlog-dialog">
         <el-descriptions :column="2" border>
            <el-descriptions-item label="操作模块" :span="1">{{ form.title }} / {{ typeFormat(form) }}</el-descriptions-item>
            <el-descriptions-item label="请求方式" :span="1">{{ form.requestMethod }}</el-descriptions-item>
            <el-descriptions-item label="登录信息" :span="1">{{ form.operName }} / {{ form.operIp }} / {{ form.operLocation }}</el-descriptions-item>
            <el-descriptions-item label="请求地址" :span="1">{{ form.operUrl }}</el-descriptions-item>
            <el-descriptions-item label="操作方法" :span="2">{{ form.method }}</el-descriptions-item>
            <el-descriptions-item label="请求参数" :span="2">
               <pre class="param-pre">{{ form.operParam }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="返回参数" :span="2">
               <pre class="param-pre">{{ form.jsonResult }}</pre>
            </el-descriptions-item>
            <el-descriptions-item label="操作状态" :span="1">
               <div v-if="form.status === 0">正常</div>
               <div v-else-if="form.status === 1">失败</div>
            </el-descriptions-item>
            <el-descriptions-item label="消耗时间" :span="1">{{ form.costTime }}毫秒</el-descriptions-item>
            <el-descriptions-item label="操作时间" :span="2">{{ parseTime(form.operTime) }}</el-descriptions-item>
            <el-descriptions-item label="异常信息" :span="2" v-if="form.status === 1">
               <pre class="error-pre">{{ form.errorMsg }}</pre>
            </el-descriptions-item>
         </el-descriptions>
         <template #footer>
            <div class="dialog-footer">
               <el-button @click="open = false">关 闭</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>
<script setup name="Operlog">
import { list, delOperlog, cleanOperlog } from "@/api/monitor/operlog";

const { proxy } = getCurrentInstance();
const { sys_oper_type, sys_common_status } = proxy.useDict("sys_oper_type","sys_common_status");

const operlogList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);
const defaultSort = ref({ prop: "operTime", order: "descending" });

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    operIp: undefined,
    title: undefined,
    operName: undefined,
    businessType: undefined,
    status: undefined
  }
});

const { queryParams, form } = toRefs(data);

/** 查询登录日志 */
function getList() {
  loading.value = true;
  list(proxy.addDateRange(queryParams.value, dateRange.value)).then(response => {
    operlogList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}
/** 操作日志类型字典翻译 */
function typeFormat(row, column) {
  return proxy.selectDictLabel(sys_oper_type.value, row.businessType);
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
  queryParams.value.pageNum = 1;
  proxy.$refs["operlogRef"].sort(defaultSort.value.prop, defaultSort.value.order);
}
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.operId);
  multiple.value = !selection.length;
}
/** 排序触发事件 */
function handleSortChange(column, prop, order) {
  queryParams.value.orderByColumn = column.prop;
  queryParams.value.isAsc = column.order;
  getList();
}
/** 详细按钮操作 */
function handleView(row) {
  open.value = true;
  form.value = row;
}
/** 删除按钮操作 */
function handleDelete(row) {
  const operIds = row.operId || ids.value;
  proxy.$modal.confirm('是否确认删除日志编号为"' + operIds + '"的数据项?').then(function () {
    return delOperlog(operIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 清空按钮操作 */
function handleClean() {
  proxy.$modal.confirm("是否确认清空所有操作日志数据项?").then(function () {
    return cleanOperlog();
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("清空成功");
  }).catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download("monitor/operlog/export",{
    ...queryParams.value,
  }, `config_${new Date().getTime()}.xlsx`);
}

getList();
</script>
<style lang="scss" scoped>
   .operlog-management {
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
         color: #fff !important;
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
   
   /* 详细对话框 */
   .operlog-dialog {
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
   
     :deep(.el-descriptions__label) {
       background: rgba(102, 126, 234, 0.08);
       font-weight: 600;
       color: #303133;
     }
   
     .param-pre,
     .error-pre {
       margin: 0;
       padding: 12px;
       background: #f8f9fa;
       border-radius: 8px;
       white-space: pre-wrap;
       word-break: break-all;
       font-size: 13px;
       max-height: 300px;
       overflow-y: auto;
     }
   
     .error-pre {
       background: rgba(245, 108, 108, 0.1);
       color: #f56c6c;
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