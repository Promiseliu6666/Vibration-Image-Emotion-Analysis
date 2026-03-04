<template>
   <div class="app-container auth-role-container">
     <!-- 基本信息卡片 -->
     <el-card shadow="never" class="info-card mb20">
       <template #header>
         <div class="card-title">
           <el-icon><User /></el-icon>
           基本信息
         </div>
       </template>
       <el-descriptions :column="2" border>
         <el-descriptions-item label="用户昵称">{{ form.nickName }}</el-descriptions-item>
         <el-descriptions-item label="登录账号">{{ form.userName }}</el-descriptions-item>
       </el-descriptions>
     </el-card>
 
     <!-- 角色分配卡片 -->
     <el-card shadow="never">
       <template #header>
         <div class="card-title">
           <el-icon><Lock /></el-icon>
           角色信息
         </div>
       </template>
 
       <el-table
         ref="roleRef"
         v-loading="loading"
         :data="roles.slice((pageNum - 1) * pageSize, pageNum * pageSize)"
         :row-key="getRowKey"
         @selection-change="handleSelectionChange"
         @row-click="clickRow"
         style="width: 100%"
         :fit="true"
         :row-style="{ height: '56px' }"
       >
         <el-table-column type="selection" :reserve-selection="true" width="55" align="center" />
         <el-table-column label="序号" type="index" width="80" align="center">
           <template #default="scope">
             {{ (pageNum - 1) * pageSize + scope.$index + 1 }}
           </template>
         </el-table-column>
         <el-table-column label="角色名称" prop="roleName" min-width="160" show-overflow-tooltip />
         <el-table-column label="权限字符" prop="roleKey" min-width="180" show-overflow-tooltip />
         <el-table-column label="创建时间" width="180" align="center">
           <template #default="scope">
             {{ parseTime(scope.row.createTime) }}
           </template>
         </el-table-column>
       </el-table>
 
       <pagination
         v-show="total > 0"
         :total="total"
         v-model:page="pageNum"
         v-model:limit="pageSize"
         class="pagination-center"
       />
 
       <!-- 提交按钮 -->
       <div class="submit-bar">
         <el-button type="primary" size="large" @click="submitForm">提 交</el-button>
         <el-button size="large" @click="close">返 回</el-button>
       </div>
     </el-card>
   </div>
 </template>

<script setup name="AuthRole">
import { getAuthRole, updateAuthRole } from "@/api/system/user";

const route = useRoute();
const { proxy } = getCurrentInstance();

const loading = ref(true);
const total = ref(0);
const pageNum = ref(1);
const pageSize = ref(10);
const roleIds = ref([]);
const roles = ref([]);
const form = ref({
  nickName: undefined,
  userName: undefined,
  userId: undefined
});

/** 单击选中行数据 */
function clickRow(row) {
  proxy.$refs["roleRef"].toggleRowSelection(row);
};
/** 多选框选中数据 */
function handleSelectionChange(selection) {
  roleIds.value = selection.map(item => item.roleId);
};
/** 保存选中的数据编号 */
function getRowKey(row) {
  return row.roleId;
};
/** 关闭按钮 */
function close() {
  const obj = { path: "/system/user" };
  proxy.$tab.closeOpenPage(obj);
};
/** 提交按钮 */
function submitForm() {
  const userId = form.value.userId;
  const rIds = roleIds.value.join(",");
  updateAuthRole({ userId: userId, roleIds: rIds }).then(response => {
    proxy.$modal.msgSuccess("授权成功");
    close();
  });
};

(() => {
  const userId = route.params && route.params.userId;
  if (userId) {
    loading.value = true;
    getAuthRole(userId).then(response => {
      form.value = response.user;
      roles.value = response.roles;
      total.value = roles.value.length;
      nextTick(() => {
        roles.value.forEach(row => {
          if (row.flag) {
            proxy.$refs["roleRef"].toggleRowSelection(row);
          }
        });
      });
      loading.value = false;
    });
  }
})();
</script>
<style lang="scss" scoped>
   .auth-role-container {
     padding: 20px;
     background: #f5f7fa;
     min-height: 100%;
   }
   
   .info-card,
   :deep(.el-card) {
     border-radius: 16px;
     overflow: hidden;
     margin-bottom: 20px;
   
     :deep(.el-card__header) {
       background: linear-gradient(120deg, #667eea, #764ba2);
       color: #fff;
       padding: 16px 24px;
       font-size: 16px;
       font-weight: 600;
     }
   }
   
   .card-title {
     display: flex;
     align-items: center;
     gap: 10px;
     font-size: 17px;
   
     .el-icon {
       font-size: 20px;
     }
   }
   
   :deep(.el-descriptions__label) {
     background: #f8fafc;
     font-weight: 500;
     width: 120px;
   }
   
   .submit-bar {
     text-align: center;
     margin: 30px 0 10px;
     padding-top: 20px;
     border-top: 1px solid #ebeef5;
   }
   
   .pagination-center {
     margin: 20px 0;
     text-align: center;
   }
   </style>
