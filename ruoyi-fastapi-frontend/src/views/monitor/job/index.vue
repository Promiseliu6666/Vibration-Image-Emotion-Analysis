<template>
   <div class="app-container job-management">
      <!-- 搜索区域 -->
      <el-card shadow="never" class="search-card mb20">
         <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
            <el-form-item label="任务名称" prop="jobName">
               <el-input
                  v-model="queryParams.jobName"
                  placeholder="请输入任务名称"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="任务组名" prop="jobGroup">
               <el-select v-model="queryParams.jobGroup" placeholder="请选择任务组名" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_job_group"
                     :key="dict.value"
                     :label="dict.label"
                     :value="dict.value"
                  />
               </el-select>
            </el-form-item>
            <el-form-item label="任务状态" prop="status">
               <el-select v-model="queryParams.status" placeholder="请选择任务状态" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_job_status"
                     :key="dict.value"
                     :label="dict.label"
                     :value="dict.value"
                  />
               </el-select>
            </el-form-item>
            <el-form-item>
               <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
               <el-button icon="Refresh" @click="resetQuery">重置</el-button>
            </el-form-item>
         </el-form>
      </el-card>

      <!-- 操作按钮栏 -->
      <div class="action-bar mb20">
         <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['monitor:job:add']">
            新增
         </el-button>
         <el-button type="success" icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['monitor:job:edit']">
            修改
         </el-button>
         <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['monitor:job:remove']">
            删除
         </el-button>
         <el-button type="warning" icon="Download" @click="handleExport" v-hasPermi="['monitor:job:export']">
            导出
         </el-button>
         <el-button type="info" icon="Operation" @click="handleJobLog" v-hasPermi="['monitor:job:query']">
            日志
         </el-button>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </div>

      <!-- 定时任务表格 -->
      <el-card shadow="never" class="table-card">
         <el-table
            v-loading="loading"
            :data="jobList"
            @selection-change="handleSelectionChange"
            style="width: 100%"
            :row-style="{ height: '60px' }"
         >
            <el-table-column type="selection" width="55" align="center" />
            <el-table-column label="任务编号" width="100" align="center" prop="jobId" />
            <el-table-column label="任务名称" align="center" prop="jobName" min-width="180" show-overflow-tooltip />
            <el-table-column label="任务组名" align="center" width="140">
               <template #default="scope">
                  <dict-tag :options="sys_job_group" :value="scope.row.jobGroup" />
               </template>
            </el-table-column>
            <el-table-column label="调用目标字符串" align="center" prop="invokeTarget" min-width="280" show-overflow-tooltip />
            <el-table-column label="cron执行表达式" align="center" prop="cronExpression" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="120" align="center">
               <template #default="scope">
                  <el-switch
                     v-model="scope.row.status"
                     active-value="0"
                     inactive-value="1"
                     @change="handleStatusChange(scope.row)"
                  />
               </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="260" align="center">
               <template #default="scope">
                  <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['monitor:job:edit']">修改</el-button>
                  <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['monitor:job:remove']">删除</el-button>
                  <el-button link type="primary" icon="CaretRight" @click="handleRun(scope.row)" v-hasPermi="['monitor:job:changeStatus']">执行一次</el-button>
                  <el-button link type="primary" icon="View" @click="handleView(scope.row)" v-hasPermi="['monitor:job:query']">详细</el-button>
                  <el-button link type="primary" icon="Operation" @click="handleJobLog(scope.row)" v-hasPermi="['monitor:job:query']">日志</el-button>
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

      <!-- 添加或修改定时任务对话框 -->
      <el-dialog :title="title" v-model="open" width="900px" append-to-body destroy-on-close class="job-dialog">
         <el-form ref="jobRef" :model="form" :rules="rules" label-width="120px">
            <el-row :gutter="30">
               <el-col :span="24">
                  <el-form-item label="任务名称" prop="jobName">
                     <el-input v-model="form.jobName" placeholder="请输入任务名称" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="任务分组" prop="jobGroup">
                     <el-select v-model="form.jobGroup" placeholder="请选择" style="width: 100%">
                        <el-option
                           v-for="dict in sys_job_group"
                           :key="dict.value"
                           :label="dict.label"
                           :value="dict.value"
                        />
                     </el-select>
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item prop="jobGroup">
                     <template #label>
                        <span>
                           任务执行器
                           <el-tooltip placement="top">
                              <template #content>
                                 <div>调用方法为异步函数时此选项无效</div>
                              </template>
                              <el-icon><question-filled /></el-icon>
                           </el-tooltip>
                        </span>
                     </template>
                     <el-select v-model="form.jobExecutor" placeholder="请选择任务执行器" style="width: 100%">
                        <el-option
                           v-for="dict in sys_job_executor"
                           :key="dict.value"
                           :label="dict.label"
                           :value="dict.value"
                        />
                     </el-select>
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item prop="invokeTarget">
                     <template #label>
                        <span>
                           调用方法
                           <el-tooltip placement="top">
                              <template #content>
                                 <div>调用示例：module_task.scheduler_test.job</div>
                              </template>
                              <el-icon><question-filled /></el-icon>
                           </el-tooltip>
                        </span>
                     </template>
                     <el-input v-model="form.invokeTarget" placeholder="请输入调用目标字符串" />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="位置参数" prop="jobArgs">
                     <el-input v-model="form.jobArgs" placeholder="请输入位置参数" />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="关键字参数" prop="jobKwargs">
                     <el-input v-model="form.jobKwargs" placeholder="请输入关键字参数" />
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="cron表达式" prop="cronExpression">
                     <el-input v-model="form.cronExpression" placeholder="请输入cron执行表达式">
                        <template #append>
                           <el-button type="primary" @click="handleShowCron">
                              生成表达式
                           </el-button>
                        </template>
                     </el-input>
                  </el-form-item>
               </el-col>
               <el-col :span="24" v-if="form.jobId !== undefined">
                  <el-form-item label="状态">
                     <el-radio-group v-model="form.status">
                        <el-radio
                           v-for="dict in sys_job_status"
                           :key="dict.value"
                           :value="dict.value"
                        >{{ dict.label }}</el-radio>
                     </el-radio-group>
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="执行策略" prop="misfirePolicy">
                     <el-radio-group v-model="form.misfirePolicy">
                        <el-radio-button value="1">立即执行</el-radio-button>
                        <el-radio-button value="2">执行一次</el-radio-button>
                        <el-radio-button value="3">放弃执行</el-radio-button>
                     </el-radio-group>
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="是否并发" prop="concurrent">
                     <el-radio-group v-model="form.concurrent">
                        <el-radio-button value="0">允许</el-radio-button>
                        <el-radio-button value="1">禁止</el-radio-button>
                     </el-radio-group>
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

      <!-- Cron表达式生成器 -->
      <el-dialog title="Cron表达式生成器" v-model="openCron" width="800px" append-to-body destroy-on-close class="cron-dialog">
         <crontab ref="crontabRef" @hide="openCron=false" @fill="crontabFill" :expression="expression" />
      </el-dialog>

      <!-- 任务详细对话框 -->
      <el-dialog title="任务详细" v-model="openView" width="800px" append-to-body destroy-on-close class="view-dialog">
         <el-descriptions :column="2" border>
            <el-descriptions-item label="任务编号">{{ form.jobId }}</el-descriptions-item>
            <el-descriptions-item label="任务分组">{{ jobGroupFormat(form) }}</el-descriptions-item>
            <el-descriptions-item label="任务名称">{{ form.jobName }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ parseTime(form.createTime) }}</el-descriptions-item>
            <el-descriptions-item label="cron表达式">{{ form.cronExpression }}</el-descriptions-item>
            <el-descriptions-item label="下次执行时间">{{ parseTime(form.nextValidTime) }}</el-descriptions-item>
            <el-descriptions-item label="任务执行器">{{ jobExecutorFormat(form) }}</el-descriptions-item>
            <el-descriptions-item label="调用目标方法" :span="2">{{ form.invokeTarget }}</el-descriptions-item>
            <el-descriptions-item label="位置参数" :span="2">{{ form.jobArgs }}</el-descriptions-item>
            <el-descriptions-item label="关键字参数" :span="2">{{ form.jobKwargs }}</el-descriptions-item>
            <el-descriptions-item label="任务状态">
               <div v-if="form.status == 0">正常</div>
               <div v-else-if="form.status == 1">暂停</div>
            </el-descriptions-item>
            <el-descriptions-item label="是否并发">
               <div v-if="form.concurrent == 0">允许</div>
               <div v-else-if="form.concurrent == 1">禁止</div>
            </el-descriptions-item>
            <el-descriptions-item label="执行策略">
               <div v-if="form.misfirePolicy == '0'">默认策略</div>
               <div v-else-if="form.misfirePolicy == '1'">立即执行</div>
               <div v-else-if="form.misfirePolicy == '2'">执行一次</div>
               <div v-else-if="form.misfirePolicy == '3'">放弃执行</div>
            </el-descriptions-item>
         </el-descriptions>
         <template #footer>
            <div class="dialog-footer">
               <el-button @click="openView = false">关 闭</el-button>
            </div>
         </template>
      </el-dialog>
   </div>
</template>

<script setup name="Job">
import { listJob, getJob, delJob, addJob, updateJob, runJob, changeJobStatus } from "@/api/monitor/job";
import Crontab from '@/components/Crontab'
const router = useRouter();
const { proxy } = getCurrentInstance();
const { sys_job_group, sys_job_status, sys_job_executor } = proxy.useDict("sys_job_group", "sys_job_status", "sys_job_executor");

const jobList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const openView = ref(false);
const openCron = ref(false);
const expression = ref("");

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    jobName: undefined,
    jobGroup: undefined,
    status: undefined
  },
  rules: {
    jobName: [{ required: true, message: "任务名称不能为空", trigger: "blur" }],
    invokeTarget: [{ required: true, message: "调用目标字符串不能为空", trigger: "blur" }],
    cronExpression: [{ required: true, message: "cron执行表达式不能为空", trigger: "change" }]
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询定时任务列表 */
function getList() {
  loading.value = true;
  listJob(queryParams.value).then(response => {
    jobList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}
/** 任务组名字典翻译 */
function jobGroupFormat(row, column) {
  return proxy.selectDictLabel(sys_job_group.value, row.jobGroup);
}
/** 任务执行器名字典翻译 */
function jobExecutorFormat(row, column) {
  return proxy.selectDictLabel(sys_job_executor.value, row.jobExecutor);
}
/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}
/** 表单重置 */
function reset() {
  form.value = {
    jobId: undefined,
    jobName: undefined,
    jobGroup: undefined,
    invokeTarget: undefined,
    cronExpression: undefined,
    misfirePolicy: "1",
    concurrent: "1",
    status: "1"
  };
  proxy.resetForm("jobRef");
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
// 多选框选中数据
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.jobId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
// 更多操作触发
function handleCommand(command, row) {
  switch (command) {
    case "handleRun":
      handleRun(row);
      break;
    case "handleView":
      handleView(row);
      break;
    case "handleJobLog":
      handleJobLog(row);
      break;
    default:
      break;
  }
}
// 任务状态修改
function handleStatusChange(row) {
  let text = row.status === "0" ? "启用" : "停用";
  proxy.$modal.confirm('确认要"' + text + '""' + row.jobName + '"任务吗?').then(function () {
    return changeJobStatus(row.jobId, row.status);
  }).then(() => {
    proxy.$modal.msgSuccess(text + "成功");
  }).catch(function () {
    row.status = row.status === "0" ? "1" : "0";
  });
}
/* 立即执行一次 */
function handleRun(row) {
  proxy.$modal.confirm('确认要立即执行一次"' + row.jobName + '"任务吗?').then(function () {
    return runJob(row.jobId, row.jobGroup);
  }).then(() => {
    proxy.$modal.msgSuccess("执行成功");})
  .catch(() => {});
}
/** 任务详细信息 */
function handleView(row) {
  getJob(row.jobId).then(response => {
    form.value = response.data;
    openView.value = true;
  });
}
/** cron表达式按钮操作 */
function handleShowCron() {
  expression.value = form.value.cronExpression;
  openCron.value = true;
}
/** 确定后回传值 */
function crontabFill(value) {
  form.value.cronExpression = value;
}
/** 任务日志列表查询 */
function handleJobLog(row) {
  const jobId = row.jobId || 0;
  router.push('/monitor/job-log/index/' + jobId)
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加任务";
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const jobId = row.jobId || ids.value;
  getJob(jobId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改任务";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["jobRef"].validate(valid => {
    if (valid) {
      if (form.value.jobId != undefined) {
        updateJob(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addJob(form.value).then(response => {
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
  const jobIds = row.jobId || ids.value;
  proxy.$modal.confirm('是否确认删除定时任务编号为"' + jobIds + '"的数据项?').then(function () {
    return delJob(jobIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download("monitor/job/export", {
    ...queryParams.value,
  }, `job_${new Date().getTime()}.xlsx`);
}

getList();
</script>
<style lang="scss" scoped>
   .job-management {
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
   
   /* 对话框通用 */
   .job-dialog,
   .cron-dialog,
   .view-dialog {
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
   
   /* 详细视图描述表格 */
   :deep(.el-descriptions__label) {
     background: rgba(102, 126, 234, 0.08);
     font-weight: 600;
     color: #303133;
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