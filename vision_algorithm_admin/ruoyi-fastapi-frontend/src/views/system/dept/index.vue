<template>
   <div class="app-container dept-management">
      <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" class="search-form">
         <el-form-item label="部门名称" prop="deptName">
            <el-input
               v-model="queryParams.deptName"
               placeholder="请输入部门名称"
               clearable
               style="width: 220px"
               @keyup.enter="handleQuery"
            />
         </el-form-item>
         <el-form-item label="状态" prop="status">
            <el-select v-model="queryParams.status" placeholder="部门状态" clearable style="width: 220px">
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

      <div class="action-bar mb20">
         <el-button
            type="primary"
            plain
            icon="Plus"
            @click="handleAdd"
            v-hasPermi="['system:dept:add']"
         >新增</el-button>
         <el-button
            type="info"
            plain
            icon="Sort"
            @click="toggleExpandAll"
         >展开/折叠</el-button>
         <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
      </div>

      <el-card shadow="never" class="dept-table-card">
         <el-table
            v-if="refreshTable"
            v-loading="loading"
            :data="deptList"
            row-key="deptId"
            :default-expand-all="isExpandAll"
            :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
            style="width: 100%"
         >
            <el-table-column prop="deptName" label="部门名称" min-width="280"></el-table-column>
            <el-table-column prop="orderNum" label="排序" width="120" align="center"></el-table-column>
            <el-table-column prop="status" label="状态" width="120" align="center">
               <template #default="scope">
                  <dict-tag :options="sys_normal_disable" :value="scope.row.status" />
               </template>
            </el-table-column>
            <el-table-column label="创建时间" align="center" width="200" prop="createTime">
               <template #default="scope">
                  <span>{{ parseTime(scope.row.createTime) }}</span>
               </template>
            </el-table-column>
            <el-table-column label="操作" align="center" width="260" fixed="right">
               <template #default="scope">
                  <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:dept:edit']">修改</el-button>
                  <el-button link type="primary" icon="Plus" @click="handleAdd(scope.row)" v-hasPermi="['system:dept:add']">新增</el-button>
                  <el-button v-if="scope.row.parentId != 0" link type="danger" icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:dept:remove']">删除</el-button>
               </template>
            </el-table-column>
         </el-table>
      </el-card>

      <!-- 添加或修改部门对话框 -->
      <el-dialog :title="title" v-model="open" width="680px" append-to-body destroy-on-close class="dept-dialog">
         <el-form ref="deptRef" :model="form" :rules="rules" label-width="100px">
            <el-row :gutter="30">
               <el-col :span="24" v-if="form.parentId !== 0">
                  <el-form-item label="上级部门" prop="parentId">
                     <el-tree-select
                        v-model="form.parentId"
                        :data="deptOptions"
                        :props="{ value: 'deptId', label: 'deptName', children: 'children' }"
                        value-key="deptId"
                        placeholder="选择上级部门"
                        check-strictly
                        style="width: 100%"
                     />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="部门名称" prop="deptName">
                     <el-input v-model="form.deptName" placeholder="请输入部门名称" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="显示排序" prop="orderNum">
                     <el-input-number v-model="form.orderNum" controls-position="right" :min="0" style="width: 100%" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="负责人" prop="leader">
                     <el-input v-model="form.leader" placeholder="请输入负责人" maxlength="20" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="联系电话" prop="phone">
                     <el-input v-model="form.phone" placeholder="请输入联系电话" maxlength="11" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="邮箱" prop="email">
                     <el-input v-model="form.email" placeholder="请输入邮箱" maxlength="50" />
                  </el-form-item>
               </el-col>
               <el-col :span="12">
                  <el-form-item label="部门状态">
                     <el-radio-group v-model="form.status">
                        <el-radio
                           v-for="dict in sys_normal_disable"
                           :key="dict.value"
                           :value="dict.value"
                        >{{ dict.label }}</el-radio>
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
   </div>
</template>

<script setup name="Dept">
import { listDept, getDept, delDept, addDept, updateDept, listDeptExcludeChild } from "@/api/system/dept";

const { proxy } = getCurrentInstance();
const { sys_normal_disable } = proxy.useDict("sys_normal_disable");

const deptList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const title = ref("");
const deptOptions = ref([]);
const isExpandAll = ref(true);
const refreshTable = ref(true);

const data = reactive({
  form: {},
  queryParams: {
    deptName: undefined,
    status: undefined
  },
  rules: {
    parentId: [{ required: true, message: "上级部门不能为空", trigger: "blur" }],
    deptName: [{ required: true, message: "部门名称不能为空", trigger: "blur" }],
    orderNum: [{ required: true, message: "显示排序不能为空", trigger: "blur" }],
    email: [{ type: "email", message: "请输入正确的邮箱地址", trigger: ["blur", "change"] }],
    phone: [{ pattern: /^1[3|4|5|6|7|8|9][0-9]\d{8}$/, message: "请输入正确的手机号码", trigger: "blur" }]
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 查询部门列表 */
function getList() {
  loading.value = true;
  listDept(queryParams.value).then(response => {
    deptList.value = proxy.handleTree(response.data, "deptId");
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
    deptId: undefined,
    parentId: undefined,
    deptName: undefined,
    orderNum: 0,
    leader: undefined,
    phone: undefined,
    email: undefined,
    status: "0"
  };
  proxy.resetForm("deptRef");
}
/** 搜索按钮操作 */
function handleQuery() {
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}
/** 新增按钮操作 */
function handleAdd(row) {
  reset();
  listDept().then(response => {
    deptOptions.value = proxy.handleTree(response.data, "deptId");
  });
  if (row != undefined) {
    form.value.parentId = row.deptId;
  }
  open.value = true;
  title.value = "添加部门";
}
/** 展开/折叠操作 */
function toggleExpandAll() {
  refreshTable.value = false;
  isExpandAll.value = !isExpandAll.value;
  nextTick(() => {
    refreshTable.value = true;
  });
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  listDeptExcludeChild(row.deptId).then(response => {
    deptOptions.value = proxy.handleTree(response.data, "deptId");
  });
  getDept(row.deptId).then(response => {
    form.value = response.data;
    open.value = true;
    title.value = "修改部门";
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["deptRef"].validate(valid => {
    if (valid) {
      if (form.value.deptId != undefined) {
        updateDept(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addDept(form.value).then(response => {
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
  proxy.$modal.confirm('是否确认删除名称为"' + row.deptName + '"的数据项?').then(function() {
    return delDept(row.deptId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>
<style lang="scss" scoped>
   .dept-management {
     padding: 20px;
     background: linear-gradient(to bottom, #f8fbff, #eef2f7);
     min-height: 100vh;
     background: var(--el-bg-color-page) !important;
   }
   
   /* 搜索栏 */
   .search-form {
     background: #fff;
     padding: 20px 24px 8px;
     border-radius: 16px;
     box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
     margin-bottom: 20px;
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
   .dept-table-card {
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
   .dept-dialog {
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