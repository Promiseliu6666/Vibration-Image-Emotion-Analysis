<template>
   <div class="app-container online-management">
      <!-- 搜索区域 -->
      <el-card shadow="never" class="search-card mb20">
         <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="true">
            <el-form-item label="登录地址" prop="ipaddr">
               <el-input
                  v-model="queryParams.ipaddr"
                  placeholder="请输入登录地址"
                  clearable
                  style="width: 240px"
                  @keyup.enter="handleQuery"
               />
            </el-form-item>
            <el-form-item label="用户名称" prop="userName">
               <el-input
                  v-model="queryParams.userName"
                  placeholder="请输入用户名称"
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
      </el-card>

      <!-- 在线用户表格 -->
      <el-card shadow="never" class="table-card">
         <el-table
            v-loading="loading"
            :data="onlineList.slice((pageNum - 1) * pageSize, pageNum * pageSize)"
            style="width: 100%"
            :row-style="{ height: '60px' }"
         >
            <el-table-column label="序号" width="80" align="center">
               <template #default="scope">
                  <span>{{ (pageNum - 1) * pageSize + scope.$index + 1 }}</span>
               </template>
            </el-table-column>
            <el-table-column label="会话编号" align="center" prop="tokenId" min-width="180" show-overflow-tooltip />
            <el-table-column label="登录名称" align="center" prop="userName" width="120" show-overflow-tooltip />
            <el-table-column label="所属部门" align="center" prop="deptName" width="160" show-overflow-tooltip />
            <el-table-column label="主机" align="center" prop="ipaddr" width="140" show-overflow-tooltip />
            <el-table-column label="登录地点" align="center" prop="loginLocation" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作系统" align="center" prop="os" min-width="140" show-overflow-tooltip />
            <el-table-column label="浏览器" align="center" prop="browser" min-width="140" show-overflow-tooltip />
            <el-table-column label="登录时间" align="center" prop="loginTime" width="180">
               <template #default="scope">
                  <span>{{ parseTime(scope.row.loginTime) }}</span>
               </template>
            </el-table-column>
            <el-table-column label="操作" fixed="right" width="100" align="center">
               <template #default="scope">
                  <el-button link type="danger" icon="Delete" @click="handleForceLogout(scope.row)" v-hasPermi="['monitor:online:forceLogout']">
                     强退
                  </el-button>
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
      </el-card>
   </div>
</template>

<script setup name="Online">
import { forceLogout, list as initData } from "@/api/monitor/online";

const { proxy } = getCurrentInstance();

const onlineList = ref([]);
const loading = ref(true);
const total = ref(0);
const pageNum = ref(1);
const pageSize = ref(10);

const queryParams = ref({
  ipaddr: undefined,
  userName: undefined
});

/** 查询登录日志列表 */
function getList() {
  loading.value = true;
  initData(queryParams.value).then(response => {
    onlineList.value = response.rows;
    total.value = response.total;
    loading.value = false;
  });
}
/** 搜索按钮操作 */
function handleQuery() {
  pageNum.value = 1;
  getList();
}
/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef");
  handleQuery();
}
/** 强退按钮操作 */
function handleForceLogout(row) {
    proxy.$modal.confirm('是否确认强退名称为"' + row.userName + '"的用户?').then(function () {
  return forceLogout(row.tokenId);
  }).then(() => {
    getList();
    proxy.$modal.msgSuccess("删除成功");
  }).catch(() => {});
}

getList();
</script>
<style lang="scss" scoped>
   .online-management {
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
   
   /* 按钮美化 */
   :deep(.el-button) {
     border-radius: 12px;
     height: 44px;
     padding: 0 24px;
     font-weight: 500;
   }
   </style>