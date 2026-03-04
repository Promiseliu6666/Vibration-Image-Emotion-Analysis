<template>
   <div class="app-container notice-management">
      <!-- 搜索区域 -->
      <el-card shadow="never" class="search-card mb20">
         <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
            <el-form-item label="公告标题" prop="noticeTitle">
               <el-input
                  v-model="queryParams.noticeTitle"
                  placeholder="请输入公告标题"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="操作人员" prop="createBy">
               <el-input
                  v-model="queryParams.createBy"
                  placeholder="请输入操作人员"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="类型" prop="noticeType">
               <el-select v-model="queryParams.noticeType" placeholder="公告类型" clearable style="width: 240px">
                  <el-option
                     v-for="dict in sys_notice_type"
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
         <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['system:notice:add']">
            新增
         </el-button>
         <el-button type="success" icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['system:notice:edit']">
            修改
         </el-button>
         <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['system:notice:remove']">
            删除
         </el-button>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
      </div>

      <!-- 公告表格 -->
      <el-card shadow="never" class="table-card">
         <el-table
            v-loading="loading"
            :data="noticeList"
            @selection-change="handleSelectionChange"
            style="width: 100%"
            :row-style="{ height: '60px' }"
         >
            <el-table-column type="selection" width="55" align="center" />
            <el-table-column label="序号" align="center" prop="noticeId" width="100" />
            <el-table-column label="公告标题" align="center" prop="noticeTitle" min-width="260" show-overflow-tooltip />
            <el-table-column label="公告类型" align="center" width="120">
               <template #default="scope">
                  <dict-tag :options="sys_notice_type" :value="scope.row.noticeType" />
               </template>
            </el-table-column>
            <el-table-column label="状态" align="center" width="120">
               <template #default="scope">
                  <dict-tag :options="sys_notice_status" :value="scope.row.status" />
               </template>
            </el-table-column>
            <el-table-column label="创建者" align="center" prop="createBy" width="120" />
            <el-table-column label="创建时间" align="center" width="140">
               <template #default="scope">
                  <span>{{ parseTime(scope.row.createTime, '{y}-{m}-{d}') }}</span>
               </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="160" align="center">
               <template #default="scope">
                  <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:notice:edit']">修改</el-button>
                  <el-button link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:notice:remove']">删除</el-button>
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

      <!-- 添加或修改公告对话框 -->
      <el-dialog :title="title" v-model="open" width="800px" append-to-body destroy-on-close class="notice-dialog">
         <el-form ref="noticeRef" :model="form" :rules="rules" label-width="100px">
            <el-row :gutter="30">
               <el-col :span="12">
                  <el-form-item label="公告标题" prop="noticeTitle">
                     <el-input v-model="form.noticeTitle" placeholder="请输入公告标题" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="公告类型" prop="noticeType">
                     <el-select v-model="form.noticeType" placeholder="请选择" style="width: 100%">
                        <el-option
                           v-for="dict in sys_notice_type"
                           :key="dict.value"
                           :label="dict.label"
                           :value="dict.value"
                        />
                     </el-select>
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="状态">
                     <el-radio-group v-model="form.status">
                        <el-radio
                           v-for="dict in sys_notice_status"
                           :key="dict.value"
                           :value="dict.value"
                        >{{ dict.label }}</el-radio>
                     </el-radio-group>
                  </el-form-item>
               </el-col>
               <el-col :span="24">
                  <el-form-item label="内容">
                     <editor v-model="form.noticeContent" :min-height="300" />
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

<script setup name="Notice">
import { listNotice, getNotice, delNotice, addNotice, updateNotice } from "@/api/system/notice";

const { proxy } = getCurrentInstance();
const { sys_notice_status, sys_notice_type } = proxy.useDict("sys_notice_status", "sys_notice_type");

const noticeList = ref([]);
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
    noticeTitle: undefined,
    createBy: undefined,
    status: undefined
  },
  rules: {
    noticeTitle: [{ required: true, message: "公告标题不能为空", trigger: "blur" }],
    noticeType: [{ required: true, message: "公告类型不能为空", trigger: "change" }]
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 查询公告列表 */
function getList() {
  loading.value = true;
  listNotice(queryParams.value).then(response => {
    noticeList.value = response.rows;
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
    noticeId: undefined,
    noticeTitle: undefined,
    noticeType: undefined,
    noticeContent: undefined,
    status: "0"
  };
  proxy.resetForm("noticeRef");
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
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.noticeId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加公告";
}
/**修改按钮操作 */
function handleUpdate(row) {
  reset();
  const noticeId = row.noticeId || ids.value;
  getNotice(noticeId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改公告";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["noticeRef"].validate(valid => {
    if (valid) {
      if (form.value.noticeId != undefined) {
        updateNotice(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addNotice(form.value).then(response => {
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
  const noticeIds = row.noticeId || ids.value
  proxy.$modal.confirm('是否确认删除公告编号为"' + noticeIds + '"的数据项？').then(function() {
    return delNotice(noticeIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>
<style lang="scss" scoped>
   .notice-management {
     padding: 20px;
     background: linear-gradient(to bottom, #f8fbff, #eef2f7);
     min-height: 100vh;
      background:var(--el-bg-color-page) !important;
   }
   
   /* 搜索卡片 */
   .search-card {
     border-radius: 16px;
     box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
     padding: 4px 0;
     background: var(--el-bg-color-page) !important;
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
   
   /* 对话框 */
   .notice-dialog {
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