<template>
  <div class="app-container user-management">
    <el-row :gutter="24">
      <splitpanes :horizontal="appStore.device === 'mobile'" class="splitpanes-custom">
        <!-- 左侧部门树 -->
        <pane :size="appStore.device === 'mobile' ? 35 : 28" min-size="20" max-size="45">
          <el-card shadow="never" class="dept-card">
            <template #header>
              <div class="card-header-title">
                <el-icon><OfficeBuilding /></el-icon>
                部门结构
              </div>
            </template>
            <div class="dept-search">
              <el-input
                v-model="deptName"
                placeholder="搜索部门名称"
                clearable
                size="large"
                prefix-icon="Search"
              />
            </div>
            <div class="dept-tree-container">
              <el-tree
                ref="deptTreeRef"
                :data="deptOptions"
                :props="{ label: 'label', children: 'children' }"
                node-key="id"
                highlight-current
                default-expand-all
                :expand-on-click-node="true"
                :filter-node-method="filterNode"
                @node-click="handleNodeClick"
                class="modern-dept-tree"
              >
                <template #default="{ node }">
                  <div class="tree-node-item">
                    <svg-icon icon-class="dept" class="tree-node-icon" />
                    <span class="tree-node-label">{{ node.label }}</span>
                  </div>
                </template>
              </el-tree>
              <div v-if="!deptOptions?.length" class="tree-empty">
                <el-empty :image-size="100" description="暂无部门数据" />
              </div>
            </div>
          </el-card>
        </pane>

        <!-- 右侧用户列表 -->
        <pane>
          <div class="user-content">
            <!-- 搜索栏 -->
            <el-card shadow="never" class="search-card mb20">
              <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch">
                <el-form-item label="用户名称" prop="userName">
                  <el-input v-model="queryParams.userName" placeholder="请输入用户名称" clearable />
                </el-form-item>
                <el-form-item label="手机号码" prop="phonenumber">
                  <el-input v-model="queryParams.phonenumber" placeholder="请输入手机号码" clearable />
                </el-form-item>
                <el-form-item label="状态" prop="status" >
                  <el-select v-model="queryParams.status" placeholder="用户状态" clearable style="width:240px">
                    <el-option v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.label" :value="dict.value" />
                  </el-select>
                </el-form-item>
                <el-form-item label="创建时间">
                  <el-date-picker
                    v-model="dateRange"
                    type="daterange"
                    range-separator="至"
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

            <!-- 操作栏 -->
            <div class="action-bar mb20">
              <el-button type="primary" icon="Plus" @click="handleAdd" v-hasPermi="['system:user:add']">
                新增用户
              </el-button>
              <el-button type="success" icon="Edit" :disabled="single" @click="handleUpdate" v-hasPermi="['system:user:edit']">
                修改
              </el-button>
              <el-button type="danger" icon="Delete" :disabled="multiple" @click="handleDelete" v-hasPermi="['system:user:remove']">
                删除
              </el-button>
              <el-button type="info" icon="Upload" @click="handleImport" v-hasPermi="['system:user:import']">
                导入
              </el-button>
              <el-button type="warning" icon="Download" @click="handleExport" v-hasPermi="['system:user:export']">
                导出
              </el-button>
              <right-toolbar v-model:showSearch="showSearch" @queryTable="getList" :columns="columns" />
            </div>

            <!-- 用户表格 -->
            <el-card shadow="never">
              <el-table
                v-loading="loading"
                :data="userList"
                @selection-change="handleSelectionChange"
                style="width: 100%"
                :fit="true"
                :row-style="{ height: '60px' }"
              >
                <el-table-column type="selection" width="55" align="center" />
                <el-table-column label="用户编号" prop="userId" width="100" align="center" v-if="columns[0].visible" />
                <el-table-column label="用户名称" prop="userName" min-width="140" show-overflow-tooltip v-if="columns[1].visible" />
                <el-table-column label="用户昵称" prop="nickName" min-width="140" show-overflow-tooltip v-if="columns[2].visible" />
                <el-table-column label="部门" prop="dept.deptName" min-width="160" show-overflow-tooltip v-if="columns[3].visible" />
                <el-table-column label="手机号码" prop="phonenumber" width="140" v-if="columns[4].visible" />
                <el-table-column label="状态" width="100" align="center" v-if="columns[5].visible">
                  <template #default="scope">
                    <el-switch
                      v-model="scope.row.status"
                      active-value="0"
                      inactive-value="1"
                      @change="handleStatusChange(scope.row)"
                    />
                  </template>
                </el-table-column>
                <el-table-column label="创建时间" width="180" align="center" v-if="columns[6].visible">
                  <template #default="scope">
                    {{ parseTime(scope.row.createTime) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" fixed="right" width="200" align="center">
                  <template #default="scope">
                    <el-button v-if="scope.row.userId !== 1" type="primary" text icon="Edit" @click="handleUpdate(scope.row)" v-hasPermi="['system:user:edit']">修改</el-button>
                    <el-button v-if="scope.row.userId !== 1" type="danger" text icon="Delete" @click="handleDelete(scope.row)" v-hasPermi="['system:user:remove']">删除</el-button>
                    <el-button v-if="scope.row.userId !== 1" type="warning" text icon="Key" @click="handleResetPwd(scope.row)" v-hasPermi="['system:user:resetPwd']">重置密码</el-button>
                    <el-button v-if="scope.row.userId !== 1" type="success" text icon="CircleCheck" @click="handleAuthRole(scope.row)" v-hasPermi="['system:user:edit']">分配角色</el-button>
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
          </div>
        </pane>
      </splitpanes>
    </el-row>

    <!-- 添加/修改用户对话框 -->
    <el-dialog :title="title" v-model="open" width="800px" append-to-body destroy-on-close>
      <el-form ref="userRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="30">
          <el-col :span="12">
            <el-form-item label="用户昵称" prop="nickName">
              <el-input v-model="form.nickName" placeholder="请输入用户昵称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="归属部门" prop="deptId">
              <el-tree-select
                v-model="form.deptId"
                :data="enabledDeptOptions"
                :props="{ value: 'id', label: 'label', children: 'children' }"
                placeholder="请选择归属部门"
                check-strictly
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="手机号码" prop="phonenumber">
              <el-input v-model="form.phonenumber" placeholder="请输入手机号码" maxlength="11" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="form.email" placeholder="请输入邮箱" maxlength="50" />
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="!form.userId">
            <el-form-item label="登录账号" prop="userName">
              <el-input v-model="form.userName" placeholder="请输入登录账号" />
            </el-form-item>
          </el-col>
          <el-col :span="12" v-if="!form.userId">
            <el-form-item label="用户密码" prop="password">
              <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="用户性别">
              <el-select v-model="form.sex" placeholder="请选择性别" style="width: 100%">
                <el-option v-for="dict in sys_user_sex" :key="dict.value" :label="dict.label" :value="dict.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-radio-group v-model="form.status">
                <el-radio v-for="dict in sys_normal_disable" :key="dict.value" :label="dict.value">{{ dict.label }}</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="岗位">
              <el-select v-model="form.postIds" multiple placeholder="请选择岗位" style="width: 100%">
                <el-option v-for="item in postOptions" :key="item.postId" :label="item.postName" :value="item.postId" :disabled="item.status == 1" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色">
              <el-select v-model="form.roleIds" multiple placeholder="请选择角色" style="width: 100%">
                <el-option v-for="item in roleOptions" :key="item.roleId" :label="item.roleName" :value="item.roleId" :disabled="item.status == 1" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="4" placeholder="请输入备注信息" />
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

    <!-- 用户导入对话框 -->
    <el-dialog title="用户导入" v-model="upload.open" width="560px" append-to-body>
      <div class="upload-area">
        <el-upload
          ref="uploadRef"
          :limit="1"
          accept=".xlsx,.xls"
          :headers="upload.headers"
          :action="upload.url + '?updateSupport=' + upload.updateSupport"
          :disabled="upload.isUploading"
          :on-progress="handleFileUploadProgress"
          :on-success="handleFileSuccess"
          :auto-upload="false"
          drag
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="upload-text">将文件拖到此处，或 <em>点击上传</em></div>
          <div class="upload-hint">仅支持 .xlsx / .xls 格式文件</div>
        </el-upload>
        <div class="upload-options">
          <el-checkbox v-model="upload.updateSupport" label="是否更新已存在用户数据" />
          <el-link type="primary" :underline="false" @click="importTemplate">下载模板</el-link>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button type="primary" :loading="upload.isUploading" @click="submitFileForm">确 定</el-button>
          <el-button @click="upload.open = false">取 消</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="User">
import { getToken } from "@/utils/auth";
import useAppStore from "@/store/modules/app";
import {
  changeUserStatus,
  listUser,
  resetUserPwd,
  delUser,
  getUser,
  updateUser,
  addUser,
  deptTreeSelect,
} from "@/api/system/user";
import { Splitpanes, Pane } from "splitpanes";
import "splitpanes/dist/splitpanes.css";

const router = useRouter();
const appStore = useAppStore();
const { proxy } = getCurrentInstance();
const { sys_normal_disable, sys_user_sex } = proxy.useDict(
  "sys_normal_disable",
  "sys_user_sex"
);

const userList = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);
const deptName = ref("");
const deptOptions = ref(undefined);
const enabledDeptOptions = ref(undefined);
const initPassword = ref(undefined);
const postOptions = ref([]);
const roleOptions = ref([]);
/*** 用户导入参数 */
const upload = reactive({
  // 是否显示弹出层（用户导入）
  open: false,
  // 弹出层标题（用户导入）
  title: "",
  // 是否禁用上传
  isUploading: false,
  // 是否更新已经存在的用户数据
  updateSupport: 0,
  // 设置上传的请求头部
  headers: { Authorization: "Bearer " + getToken() },
  // 上传的地址
  url: import.meta.env.VITE_APP_BASE_API + "/system/user/importData",
});
// 列显隐信息
const columns = ref([
  { key: 0, label: `用户编号`, visible: true },
  { key: 1, label: `用户名称`, visible: true },
  { key: 2, label: `用户昵称`, visible: true },
  { key: 3, label: `部门`, visible: true },
  { key: 4, label: `手机号码`, visible: true },
  { key: 5, label: `状态`, visible: true },
  { key: 6, label: `创建时间`, visible: true },
]);

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    userName: undefined,
    phonenumber: undefined,
    status: undefined,
    deptId: undefined,
  },
  rules: {
    userName: [
      { required: true, message: "用户名称不能为空", trigger: "blur" },
      {
        min: 2,
        max: 20,
        message: "用户名称长度必须介于 2 和 20 之间",
        trigger: "blur",
      },
    ],
    nickName: [
      { required: true, message: "用户昵称不能为空", trigger: "blur" },
    ],
    password: [
      { required: true, message: "用户密码不能为空", trigger: "blur" },
      {
        min: 5,
        max: 20,
        message: "用户密码长度必须介于 5 和 20 之间",
        trigger: "blur",
      },
      {
        pattern: /^[^<>"'|\\]+$/,
        message: "不能包含非法字符：< > \" ' \\\ |",
        trigger: "blur",
      },
    ],
    email: [
      {
        type: "email",
        message: "请输入正确的邮箱地址",
        trigger: ["blur", "change"],
      },
    ],
    phonenumber: [
      {
        pattern: /^1[3|4|5|6|7|8|9][0-9]\d{8}$/,
        message: "请输入正确的手机号码",
        trigger: "blur",
      },
    ],
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 通过条件过滤节点  */
const filterNode = (value, data) => {
  if (!value) return true;
  return data.label.indexOf(value) !== -1;
};
/** 根据名称筛选部门树 */
watch(deptName, (val) => {
  proxy.$refs["deptTreeRef"].filter(val);
});
/** 查询用户列表 */
function getList() {
  loading.value = true;
  listUser(proxy.addDateRange(queryParams.value, dateRange.value)).then(
    (res) => {
      loading.value = false;
      userList.value = res.rows;
      total.value = res.total;
    }
  );
}
/** 查询部门下拉树结构 */
function getDeptTree() {
  deptTreeSelect().then(response => {
    deptOptions.value = response.data;
    enabledDeptOptions.value = filterDisabledDept(JSON.parse(JSON.stringify(response.data)));
  });
};
/** 过滤禁用的部门 */
function filterDisabledDept(deptList) {
  return deptList.filter(dept => {
    if (dept.disabled) {
      return false;
    }
    if (dept.children && dept.children.length) {
      dept.children = filterDisabledDept(dept.children);
    }
    return true;
  });
};
/** 节点单击事件 */
function handleNodeClick(data) {
  queryParams.value.deptId = data.id;
  handleQuery();
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
  queryParams.value.deptId = undefined;
  proxy.$refs.deptTreeRef.setCurrentKey(null);
  handleQuery();
}
/** 删除按钮操作 */
function handleDelete(row) {
  const userIds = row.userId || ids.value;
  proxy.$modal
    .confirm('是否确认删除用户编号为"' + userIds + '"的数据项？')
    .then(function () {
      return delUser(userIds);
    })
    .then(() => {
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}
/** 导出按钮操作 */
function handleExport() {
  proxy.download(
    "system/user/export",
    {
      ...queryParams.value,
    },
    `user_${new Date().getTime()}.xlsx`
  );
}
/** 用户状态修改  */
function handleStatusChange(row) {
  let text = row.status === "0" ? "启用" : "停用";
  proxy.$modal
    .confirm('确认要"' + text + '""' + row.userName + '"用户吗?')
    .then(function () {
      return changeUserStatus(row.userId, row.status);
    })
    .then(() => {
      proxy.$modal.msgSuccess(text + "成功");
    })
    .catch(function () {
      row.status = row.status === "0" ? "1" : "0";
    });
}
/** 更多操作 */
function handleCommand(command, row) {
  switch (command) {
    case "handleResetPwd":
      handleResetPwd(row);
      break;
    case "handleAuthRole":
      handleAuthRole(row);
      break;
    default:
      break;
  }
}
/** 跳转角色分配 */
function handleAuthRole(row) {
  const userId = row.userId;
  router.push("/system/user-auth/role/" + userId);
}
/** 重置密码按钮操作 */
function handleResetPwd(row) {
  proxy
    .$prompt('请输入"' + row.userName + '"的新密码', "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      closeOnClickModal: false,
      inputPattern: /^.{5,20}$/,
      inputErrorMessage: "用户密码长度必须介于 5 和 20 之间",
      inputValidator: (value) => {
        if (/<|>|"|'|\||\\/.test(value)) {
          return "不能包含非法字符：< > \" ' \\\ |";
        }
      },
    })
    .then(({ value }) => {
      resetUserPwd(row.userId, value).then((response) => {
        proxy.$modal.msgSuccess("修改成功，新密码是：" + value);
      });
    })
    .catch(() => {});
}
/** 选择条数  */
function handleSelectionChange(selection) {
  ids.value = selection.map((item) => item.userId);
  single.value = selection.length != 1;
  multiple.value = !selection.length;
}
/** 导入按钮操作 */
function handleImport() {
  upload.title = "用户导入";
  upload.open = true;
}
/** 下载模板操作 */
function importTemplate() {
  proxy.download(
    "system/user/importTemplate",
    {},
    `user_template_${new Date().getTime()}.xlsx`
  );
}
/**文件上传中处理 */
const handleFileUploadProgress = (event, file, fileList) => {
  upload.isUploading = true;
};
/** 文件上传成功处理 */
const handleFileSuccess = (response, file, fileList) => {
  upload.open = false;
  upload.isUploading = false;
  proxy.$refs["uploadRef"].handleRemove(file);
  proxy.$alert(
    "<div style='overflow: auto;overflow-x: hidden;max-height: 70vh;padding: 10px 20px 0;'>" +
      response.msg +
      "</div>",
    "导入结果",
    { dangerouslyUseHTMLString: true }
  );
  getList();
};
/** 提交上传文件 */
function submitFileForm() {
  proxy.$refs["uploadRef"].submit();
}
/** 重置操作表单 */
function reset() {
  form.value = {
    userId: undefined,
    deptId: undefined,
    userName: undefined,
    nickName: undefined,
    password: undefined,
    phonenumber: undefined,
    email: undefined,
    sex: undefined,
    status: "0",
    remark: undefined,
    postIds: [],
    roleIds: [],
  };
  proxy.resetForm("userRef");
}
/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}
/** 新增按钮操作 */
function handleAdd() {
  reset();
  getUser().then((response) => {
    postOptions.value = response.posts;
    roleOptions.value = response.roles;
    open.value = true;
    title.value = "添加用户";
    form.value.password = initPassword.value;
  });
}
/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const userId = row.userId || ids.value;
  getUser(userId).then((response) => {
    form.value = response.data;
    postOptions.value = response.posts;
    roleOptions.value = response.roles;
    form.value.postIds = response.postIds;
    form.value.roleIds = response.roleIds;
    open.value = true;
    title.value = "修改用户";
    form.value.password = undefined;
  });
}
/** 提交按钮 */
function submitForm() {
  proxy.$refs["userRef"].validate((valid) => {
    if (valid) {
      if (form.value.userId != undefined) {
        updateUser(form.value).then((response) => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addUser(form.value).then((response) => {
          proxy.$modal.msgSuccess("新增成功");
          open.value = false;
          getList();
        });
      }
    }
  });
}

getDeptTree();
getList();
</script>
<style lang="scss" scoped>
  .user-management {
    padding: 20px;
    background: linear-gradient(to bottom, #f8fbff, #eef2f7);
    min-height: 100vh;
    background: var(--el-bg-color-page) !important;
  }
  
  .splitpanes-custom {
    height: calc(100vh - 100px);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
  }
  
  /* 左侧部门卡片 */
  .dept-card {
    height: 100%;
    border-radius: 16px;
    overflow: hidden;
  
    :deep(.el-card__header) {
      background: linear-gradient(120deg, #667eea, #764ba2);
      color: #fff;
      padding: 18px 24px;
      font-size: 18px;
      font-weight: 600;
    }
  }
  
  .card-header-title {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 18px;
  }
  
  .dept-search {
    padding: 16px 20px 12px;
  }
  
  .dept-tree-container {
    flex: 1;
    padding: 0 12px 16px;
    overflow: hidden;
  }
  
  .modern-dept-tree {
    background: transparent;
    height: 100%;
  
    :deep(.el-tree-node__content) {
      height: 48px;
      border-radius: 12px;
      margin: 4px 0;
      padding-left: 8px !important;
      transition: all 0.3s;
  
      &:hover {
        background: rgba(102, 126, 234, 0.12);
      }
    }
  
    :deep(.el-tree-node.is-current > .el-tree-node__content) {
      background: linear-gradient(90deg, #667eea, #764ba2);
      color: #fff;
      font-weight: 500;
  
      .tree-node-icon {
        color: #fff !important;
      }
    }
  }
  
  .tree-node-item {
    display: flex;
    align-items: center;
    width: 100%;
    font-size: 15px;
  }
  
  .tree-node-icon {
    font-size: 18px;
    color: #667eea;
    margin-right: 10px;
  }
  
  .tree-node-label {
    flex: 1;
    font-weight: 500;
  }
  
  .tree-empty {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  /* 右侧内容 */
  .user-content {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  
  .search-card, .action-bar, :deep(.el-card) {
    border-radius: 16px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
    margin-bottom: 20px;
  }
  
  .action-bar {
  /* 删除原来的 background: #fff; */
  background: var(--el-bg-color);  /* 自动跟随主题：亮主题白，暗主题深灰 */
  padding: 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  border-radius: 16px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08);
  transition: background 0.3s; /* 可选：切换主题时平滑过渡 */
}
  
  .pagination-center {
    margin: 24px 0;
    text-align: center;
  }
  
  /* 表格美化 */
  :deep(.el-table) {
    border-radius: 16px;
    overflow: hidden;
  
    th.el-table__cell {
      background: #409eff !important;
      color: #fff !important;
      font-weight: 600;
      font-size: 15px;
    }
  }
  
  /* 输入框统一 */
  :deep(.el-input__wrapper) {
    height: 48px;
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  
    &:hover, &.is-focus {
      box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
    }
  }
  
  /* 导入弹窗 */
  .upload-area {
    text-align: center;
    padding: 40px 20px;
  }
  
  .upload-icon {
    font-size: 56px;
    color: #667eea;
    margin-bottom: 20px;
  }
  
  .upload-text {
    font-size: 18px;
    margin: 20px 0;
    color: #303133;
  }
  
  .upload-hint {
    color: #909399;
    margin-bottom: 24px;
  }
  
  .upload-options {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 30px;
    margin-top: 20px;
    font-size: 14px;
  }
  
  </style>
