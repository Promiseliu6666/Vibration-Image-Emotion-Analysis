<template>
   <div class="app-container profile-container">
     <el-row :gutter="24">
       <!-- 左侧个人信息卡片 -->
       <el-col :span="8" :md="8" :sm="24" :xs="24">
         <el-card class="profile-card" shadow="hover">
           <template #header>
             <div class="card-header">
               <span class="header-title">个人信息</span>
             </div>
           </template>
 
           <div class="profile-info">
             <!-- 头像 -->
             <div class="avatar-wrapper">
               <userAvatar class="avatar-large" />
             </div>
 
             <!-- 用户名突出显示 -->
             <div class="username text-center">
               {{ state.user.userName }}
             </div>
             <div class="nickname text-center" v-if="state.user.nickName && state.user.nickName !== state.user.userName">
               ({{ state.user.nickName }})
             </div>
 
             <!-- 信息列表 -->
             <el-descriptions :column="1" class="info-list" border>
               <el-descriptions-item label="手机号码">
                 <svg-icon icon-class="phone" class="info-icon" />
                 {{ state.user.phonenumber || '-' }}
               </el-descriptions-item>
               <el-descriptions-item label="用户邮箱">
                 <svg-icon icon-class="email" class="info-icon" />
                 {{ state.user.email || '-' }}
               </el-descriptions-item>
               <el-descriptions-item label="所属部门">
                 <svg-icon icon-class="tree" class="info-icon" />
                 {{ state.user.dept ? state.user.dept.deptName : '-' }}
               </el-descriptions-item>
               <el-descriptions-item label="岗位">
                 <svg-icon icon-class="peoples" class="info-icon" />
                 {{ state.postGroup || '-' }}
               </el-descriptions-item>
               <el-descriptions-item label="所属角色">
                 <svg-icon icon-class="role" class="info-icon" />
                 {{ state.roleGroup || '-' }}
               </el-descriptions-item>
               <el-descriptions-item label="创建日期">
                 <svg-icon icon-class="date" class="info-icon" />
                 {{ state.user.createTime || '-' }}
               </el-descriptions-item>
             </el-descriptions>
           </div>
         </el-card>
       </el-col>
 
       <!-- 右侧基本资料卡片 -->
       <el-col :span="16" :md="16" :sm="24" :xs="24">
         <el-card class="detail-card" shadow="hover">
           <template #header>
             <div class="card-header">
               <span class="header-title">基本资料</span>
             </div>
           </template>
 
           <el-tabs v-model="activeTab" class="profile-tabs">
             <el-tab-pane label="基本资料" name="userinfo">
               <userInfo :user="state.user" />
             </el-tab-pane>
             <el-tab-pane label="修改密码" name="resetPwd">
               <resetPwd />
             </el-tab-pane>
           </el-tabs>
         </el-card>
       </el-col>
     </el-row>
   </div>
 </template>
 
 <script setup name="Profile">
 import userAvatar from "./userAvatar";
 import userInfo from "./userInfo";
 import resetPwd from "./resetPwd";
 import { getUserProfile } from "@/api/system/user";
 
 const activeTab = ref("userinfo");
 
 const state = reactive({
   user: {},
   roleGroup: {},
   postGroup: {}
 });
 
 function getUser() {
   getUserProfile().then(response => {
     state.user = response.data;
     state.roleGroup = response.roleGroup;
     state.postGroup = response.postGroup;
   });
 }
 
 getUser();
 </script>
 
 <style lang="scss" scoped>
 .profile-container {
   padding: 16px;
   background: #f5f7fa;
   min-height: 100%;
 }
 
 .profile-card,
 .detail-card {
   height: 100%;
   border-radius: 12px;
   overflow: hidden;
 
   :deep(.el-card__header) {
     background: linear-gradient(90deg, #409eff, #67c23a);
     color: #fff;
     padding: 16px 20px;
   }
 }
 
 .card-header {
   display: flex;
   align-items: center;
   font-size: 16px;
   font-weight: 600;
 
   .header-title {
     display: flex;
     align-items: center;
 
     &::before {
       content: "";
       display: inline-block;
       width: 4px;
       height: 16px;
       background: #fff;
       border-radius: 2px;
       margin-right: 10px;
     }
   }
 }
 
 .profile-info {
   padding: 20px;
   text-align: center;
 }
 
 .avatar-wrapper {
   margin-bottom: 20px;
 }
 
 .avatar-large {
   width: 120px;
   height: 120px;
   border: 4px solid #fff;
   box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
 }
 
 .username {
   font-size: 20px;
   font-weight: 600;
   color: #303133;
   margin: 12px 0 4px;
 }
 
 .nickname {
   font-size: 14px;
   color: #909399;
   margin-bottom: 24px;
 }
 
 .info-list {
   margin-top: 20px;
 
   :deep(.el-descriptions__label) {
     background-color: #f8fafc;
     width: 120px;
     font-weight: 500;
     color: #606266;
   }
 
   :deep(.el-descriptions__content) {
     color: #303133;
   }
 
   .info-icon {
     font-size: 16px;
     margin-right: 8px;
     color: #409eff;
     vertical-align: middle;
   }
 }
 
 .detail-card {
   :deep(.el-card__body) {
     padding: 0;
   }
 }
 
 .profile-tabs {
   :deep(.el-tabs__header) {
     padding: 0 20px;
     background: #fff;
     margin: 0;
   }
 
   :deep(.el-tabs__content) {
     padding: 20px;
     background: #fff;
     min-height: 400px;
   }
 
   :deep(.el-tab-pane) {
     height: 100%;
   }
 }
 
 // 移动端优化
 @media (max-width: 768px) {
   .profile-container {
     padding: 12px;
   }
 
   .el-row {
     margin-bottom: 16px;
   }
 
   .profile-card,
   .detail-card {
     margin-bottom: 16px;
   }
 
   .avatar-large {
     width: 100px;
     height: 100px;
   }
 
   .username {
     font-size: 18px;
   }
 }
 </style>