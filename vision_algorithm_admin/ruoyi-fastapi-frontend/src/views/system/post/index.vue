<template>
   <div class="app-container post-management">
     <!-- 搜索区域 -->
     <el-card shadow="never" class="search-card mb20">
       <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
         <el-form-item label="岗位编码" prop="postCode">
           <el-input
             v-model="queryParams.postCode"
             placeholder="请输入岗位编码"
             clearable
             style="width: 240px"
             @keyup.enter="handleQuery"
           />
         </el-form-item>
         <el-form-item label="岗位名称" prop="postName">
           <el-input
             v-model="queryParams.postName"
             placeholder="请输入岗位名称"
             clearable
             style="width: 240px"
             @keyup.enter="handleQuery"
           />
         </el-form-item>
         <el-form-item label="状态" prop="status">
           <el-select v-model="queryParams.status" placeholder="岗位状态" clearable style="width: 240px">
             <el-option
               v-for="dict in sys_normal_disable"
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
       <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['system:post:add']">
         新增岗位
       </el-button>
       <el-button type="success" icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['system:post:edit']">
         修改
       </el-button>
       <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['system:post:remove']">
         删除
       </el-button>
       <el-button type="warning" icon="Download" @click="handleExport" v-hasPermi="['system:post:export']">
         导出
       </el-button>
       <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" />
     </div>

     <!-- 岗位表格 -->
     <el-card shadow="never" class="table-card">
       <el-table
         v-loading="loading"
         :data="postList"
         @selection-change="handleSelectionChange"
         style="width: 100%"
         :row-style="{ height: '60px' }"
       >
         <el-table-column type="selection" width="55" align="center" />
         <el-table-column label="岗位编号" prop="postId" width="100" align="center" />
         <el-table-column label="岗位编码" prop="postCode" width="140" align="center" />
         <el-table-column label="岗位名称" prop="postName" min-width="180" show-overflow-tooltip />
         <el-table-column label="岗位排序" prop="postSort" width="120" align="center" />
         <el-table-column label="状态" width="100" align="center">
           <template #default="scope">
             <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
           </template>
         </el-table-column>
         <el-table-column label="创建时间" width="180" align="center">
           <template #default="scope">
             {{ parseTime(scope.row.createTime) }}
           </template>
         </el-table-column>
         <el-table-column label="操作" fixed="right" width="160" align="center">
           <template #default="scope">
             <el-button type="primary" text icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:post:edit']">修改</el-button>
             <el-button type="danger" text icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:post:remove']">删除</el-button>
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

     <!-- 添加/修改岗位对话框 -->
     <el-dialog :title="title" v-model="open" width="680px" append-to-body destroy-on-close class="post-dialog">
       <el-form ref="postRef" :model="form" :rules="rules" label-width="100px">
         <el-row :gutter="30">
           <el-col :span="12">
             <el-form-item label="岗位名称" prop="postName">
               <el-input v-model="form.postName" placeholder="请输入岗位名称" />
             </el-form-item>
           </el-col>
           <el-col :span="12">
             <el-form-item label="岗位编码" prop="postCode">
               <el-input v-model="form.postCode" placeholder="请输入岗位编码" />
             </el-form-item>
           </el-col>

           <el-col :span="12">
             <el-form-item label="岗位顺序" prop="postSort">
               <el-input-number v-model="form.postSort" :min="0" style="width: 100%" />
             </el-form-item>
           </el-col>
           <el-col :span="12">
             <el-form-item label="岗位状态">
               <el-radio-group v-model="form.status">
                 <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.value">
                   {{ dict.label }}
                 </el-radio>
               </el-radio-group>
             </el-form-item>
           </el-col>

           <el-col :span="24">
             <el-form-item label="备注">
               <el-input
                 v-model="form.remark"
                 type="textarea"
                 :rows="4"
                 placeholder="请输入备注信息（可选）"
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

<script setup name="Post">
import { listPost, addPost, delPost, getPost, updatePost } from "@/api/system/post";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const postList = ref([]);
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
    postCode: undefined,
    postName: undefined,
    status: undefined
  },
  rules: {
    postName: [{ required: true, message: "岗位名称不能为空", trigger: "blur" }],
    postCode: [{ required: true, message: "岗位编码不能为空", trigger: "blur" }],
    postSort: [{ required: true, message: "岗位顺序不能为空", trigger: "blur" }],
  }
});

const { queryParams, form, rules } = toRefs(data);

/** 查询岗位列表 */
function getList() {
  loading.value = true;
  listPost(queryParams.value).then(response => {
    postList.value = response.rows;
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
    postId: undefined,
    postCode: undefined,
    postName: undefined,
    postSort: 0,
    status: "0",
    remark: undefined
  };
  proxy.resetForm("postRef");
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
  ids.value = selection.map(item => item.postId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加岗位";
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const postId = row.postId || ids.value;
  getPost(postId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改岗位";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["postRef"].validate(valid => {
    if (valid) {
      if (form.value.postId != undefined) {
        updatePost(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addPost(form.value).then(response => {
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
  const postIds = row.postId || ids.value;
  proxy.$modal.confirm('是否确认删除岗位编号为"' + postIds + '"的数据项？').then(function() {
    return delPost(postIds);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download("system/post/export", {
    ...queryParams.value
  }, `post_${new Date().getTime()}.xlsx`);
}

getList();
</script>

<style lang="scss" scoped>
   .app-container {
     padding: 16px;
     background: #f5f7fa;
     min-height: 100%;
   }
   
   .search-card {
     border-radius: 12px;
   }
   
   .toolbar {
     display: flex;
     align-items: center;
     gap: 12px;
     flex-wrap: wrap;
     padding: 8px 0;
   }
   
   .mb16 {
     margin-bottom: 16px;
   }
   
   .pagination {
     margin-top: 20px;
     text-align: right;
   }
   
   .dialog-footer {
     text-align: right;
     padding-top: 10px;
   }
   
   /* 输入框、下拉框统一美化（与之前页面一致） */
   :deep(.el-input__wrapper) {
     height: 48px;
     border-radius: 8px;
     box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
   
     &:hover,
     &.is-focus {
       box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.2);
     }
   }
   
   :deep(.el-select-dropdown) {
     border-radius: 10px;
     box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
   }
   </style>


<style lang="scss" scoped>
   .post-management {
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
   
   /* 对话框 */
   .post-dialog {
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
