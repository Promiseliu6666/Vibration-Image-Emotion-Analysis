<template>
  <div class="app-container">
    <el-row :gutter="20">
      <splitpanes
        :horizontal="appStore.device === 'mobile'"
        class="default-theme"
      >
        <!-- 分组数据 -->
        <pane size="20">
          <el-col>
            <div class="head-container">
              <el-input
                v-model="groupName"
                placeholder="请输入分组名称"
                clearable
                prefix-icon="Search"
                style="margin-bottom: 20px"
              />
            </div>
            <div class="head-container">
              <div class="group-list">
                <div
                  class="group-item"
                  :class="{ active: selectedGroupId === null }"
                  @click="selectGroup(null)"
                >
                  <span>全部人员</span>
                  <!-- <el-badge :value="totalPeopleCount" class="item" /> -->
                </div>
                <div
                  v-for="group in filteredGroupOptions"
                  :key="group.id"
                  class="group-item"
                  :class="{ active: selectedGroupId === group.id }"
                  @click="selectGroup(group.id)"
                >
                  <span>{{ group.name }}</span>
                  <!-- <el-badge :value="group.memberCount || 0" class="item" /> -->
                </div>
              </div>
            </div>
          </el-col>
        </pane>
        <!-- 人员数据 -->
        <pane size="80">
          <el-col>
            <el-form
          :model="queryParams"
          ref="queryRef"
          :inline="true"
          v-show="showSearch"
          label-width="68px"
        >
          <el-form-item label="人脸编码" prop="name">
            <el-input
              v-model="queryParams.name"
              placeholder="请输入人脸编码"
              clearable
              style="width: 240px"
              @keyup.enter="handleQuery"
            />
          </el-form-item>

          <el-form-item>
            <el-button type="primary" icon="Search" @click="handleQuery"
              >搜索</el-button
            >
            <el-button icon="Refresh" @click="resetQuery">重置</el-button>
          </el-form-item>
        </el-form>

        <el-row :gutter="10" class="mb8">
          <el-col :span="1.5">
            <el-button
              type="primary"
              plain
              icon="Plus"
              @click="handleAdd"
              v-hasPermi="['face:people:add']"
              >新增</el-button
            >
          </el-col>
          <el-col :span="1.5">
            <el-button
              type="success"
              plain
              icon="Edit"
              :disabled="single"
              @click="handleUpdate"
              v-hasPermi="['face:people:edit']"
              >修改</el-button
            >
          </el-col>
          <el-col :span="1.5">
            <el-button
              type="danger"
              plain
              icon="Delete"
              :disabled="multiple"
              @click="handleDelete"
              v-hasPermi="['face:people:remove']"
              >删除</el-button
            >
          </el-col>
          <right-toolbar
            v-model:showSearch="showSearch"
            @queryTable="getList"
            :columns="columns"
          ></right-toolbar>
        </el-row>

        <el-table
          v-loading="loading"
          :data="peopleList"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="50" align="center" />
<!--          <el-table-column-->
<!--            label="编号"-->
<!--            align="center"-->
<!--            key="id"-->
<!--            prop="id"-->
<!--            v-if="columns.find(col => col.key === '0')?.visible"-->
<!--          />-->
          <el-table-column
            label="分组名称"
            align="center"
            key="groupName"
            prop="groupName"
            v-if="columns.find(col => col.key === '2')?.visible"
            :show-overflow-tooltip="true"
          />
          <el-table-column
            label="人脸编码"
            align="center"
            key="name"
            prop="name"
            v-if="columns.find(col => col.key === '1')?.visible"
            :show-overflow-tooltip="true"
          />
          <el-table-column
            label="照片"
            align="center"
            key="pics"
            v-if="columns.find(col => col.key === '3')?.visible"
            width="120"
          >
            <template #default="scope">
              <el-image
                v-if="scope.row.pics"
                :src="'data:image/png;base64,' + scope.row.pics"
                style="width: 60px; height: 60px"
                fit="cover"
                :preview-src-list="['data:image/png;base64,' + scope.row.pics]"
                preview-teleported
              />
              <span v-else>暂无照片</span>
            </template>
          </el-table-column>
          <el-table-column
            label="创建时间"
            align="center"
            prop="createdTime"
            v-if="columns.find(col => col.key === '4')?.visible"
            width="160"
          >
            <template #default="scope">
              <span>{{ parseTime(scope.row.createdTime) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            label="操作"
            align="center"
            width="150"
            class-name="small-padding fixed-width"
          >
            <template #default="scope">
              <el-tooltip content="修改" placement="top">
                <el-button
                  link
                  type="primary"
                  icon="Edit"
                  @click="handleUpdate(scope.row)"
                ></el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button
                  link
                  type="primary"
                  icon="Delete"
                  @click="handleDelete(scope.row)"
                ></el-button>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>
        <pagination
          v-show="total > 0"
          :total="total"
          v-model:page="queryParams.pageNum"
          v-model:limit="queryParams.pageSize"
          @pagination="getList"
        />
          </el-col>
        </pane>
      </splitpanes>
    </el-row>

    <!-- 添加或修改人员对话框 -->
    <el-dialog :title="title" v-model="open" width="600px" append-to-body>
      <el-form :model="form" :rules="rules" ref="peopleRef" label-width="80px">
        <el-row>
          <el-col :span="12">
            <el-form-item label="人脸编码" prop="name">
              <el-input
                v-model="form.name"
                placeholder="请输入人脸编码"
                maxlength="30"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分组" prop="groupId">
              <el-select
                v-model="form.groupId"
                placeholder="请选择分组"
                style="width: 100%"
              >
                <el-option
                  v-for="group in groupOptions"
                  :key="group.id"
                  :label="group.name"
                  :value="group.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-form-item label="照片" prop="pics">
              <el-upload
                class="avatar-uploader"
                :show-file-list="false"
                :on-success="handleAvatarSuccess"
                :before-upload="beforeAvatarUpload"
              >
                <img v-if="form.picsUrl" :src="form.picsUrl" class="avatar" />
                <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
              </el-upload>
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

<script setup name="PeopleList">
import { parseTime } from "@/utils/ruoyi";
import { getToken } from "@/utils/auth";
import useAppStore from "@/store/modules/app";
import {
  listPeople,
  addPeople,
  updatePeople,
  delPeople,
} from "@/api/face/people";
import { listGroup } from "@/api/face/group";
import { Plus } from "@element-plus/icons-vue";
import { Splitpanes, Pane } from "splitpanes";
import "splitpanes/dist/splitpanes.css";

const { proxy } = getCurrentInstance();
const appStore = useAppStore();

const peopleList = ref([]);
const groupOptions = ref([]);
const open = ref(false);
const loading = ref(true);
const showSearch = ref(true);
const ids = ref([]);
const single = ref(true);
const multiple = ref(true);
const total = ref(0);
const title = ref("");
const dateRange = ref([]);
const selectedGroupId = ref(null);
const totalPeopleCount = ref(0);
const groupName = ref("");

// 列显隐信息
const columns = ref([
  { key: "0", label: `编号`, visible: true },
  { key: "1", label: `人脸编码`, visible: true },
  { key: "2", label: `分组`, visible: true },
  { key: "3", label: `照片`, visible: true },
  { key: "4", label: `创建时间`, visible: true },
]);

// 过滤后的分组选项
const filteredGroupOptions = computed(() => {
  if (!groupName.value) {
    return groupOptions.value;
  }
  return groupOptions.value.filter(group => 
    group.name.toLowerCase().includes(groupName.value.toLowerCase())
  );
});

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    name: undefined,
    groupId: undefined,
  },
  rules: {
    name: [
      { required: true, message: "人脸编码不能为空", trigger: "blur" },
      {
        min: 2,
        max: 20,
        message: "人脸编码长度必须介于 2 和 20 之间",
        trigger: "blur",
      },
    ],
    groupId: [
      { required: true, message: "分组不能为空", trigger: "change" },
    ],
    pics: [
      { required: true, message: "照片不能为空", trigger: "change" },
    ],
  },
});

const { queryParams, form, rules } = toRefs(data);

/** 查询人员列表 */
function getList() {
  loading.value = true;
  const params = proxy.addDateRange(queryParams.value, dateRange.value);
  
  // 添加分组参数
  if (selectedGroupId.value) {
    params.group = selectedGroupId.value;
  } else {
    // 当选择全部分组时，确保删除group参数
    delete params.group;
  }
    
  listPeople(params).then((res) => {
    loading.value = false;
    const data = res.data || {};
    peopleList.value = (data.rows || []).map(item => {
      const group = groupOptions.value.find(g => g.id === item.groupId);
      return {
        ...item,
        groupName: group ? group.name : '未分组'
      };
    });
    total.value = data.total || 0;
  }).catch(() => {
    loading.value = false;
  });
}

/** 查询分组列表 */
function getGroupList() {
  return listGroup().then((res) => {
    const data = res.data || {};
    groupOptions.value = data.rows || [];
    // 计算总人员数量
    totalPeopleCount.value = groupOptions.value.reduce((total, group) => {
      return total + (group.memberCount || 0);
    }, 0);
  });
}

/** 选择分组 */
function selectGroup(groupId) {
  selectedGroupId.value = groupId;
  queryParams.value.pageNum = 1;
  getList();
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
  ids.value = selection.map((item) => item.id);
  single.value = selection.length !== 1;
  multiple.value = !selection.length;
}

/** 新增按钮操作 */
function handleAdd() {
  reset();
  open.value = true;
  title.value = "添加人员";
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset();
  const peopleId = row.id || ids.value[0];
  // 这里可以调用获取详情接口，暂时直接使用行数据
  form.value = { ...row };
  // 设置图片回显
  if (row.pics) {
    form.value.picsUrl = 'data:image/png;base64,' + row.pics;
  }
  open.value = true;
  title.value = "修改人员";
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["peopleRef"].validate((valid) => {
    if (valid) {
      if (form.value.id != undefined) {
        updatePeople(form.value.id, {
          name: form.value.name,
          groupId: form.value.groupId,
          pics: form.value.pics,
        }).then((response) => {
          proxy.$modal.msgSuccess("修改成功");
          open.value = false;
          getList();
        });
      } else {
        addPeople(form.value).then((response) => {
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
  const peopleIds = row && row.id ? [row.id] : [...ids.value];
  const confirmText = row && row.id 
    ? `是否确认删除人脸编码为"${row.name}"的人员？`
    : `是否确认删除选中的${peopleIds.length}个人员？`;
    
  proxy.$modal
    .confirm(confirmText)
    .then(async function () {
      // 逐个删除
      for (const peopleId of peopleIds) {
        try {
          await delPeople(peopleId);
        } catch (error) {
          console.error(`删除人员${peopleId}失败:`, error);
          proxy.$modal.msgError(`删除人员${peopleId}失败`);
          return;
        }
      }
      getList();
      proxy.$modal.msgSuccess("删除成功");
    })
    .catch(() => {});
}

/** 取消按钮 */
function cancel() {
  open.value = false;
  reset();
}

/** 表单重置 */
function reset() {
  form.value = {
    id: undefined,
    name: undefined,
    groupId: undefined,
    pics: undefined,
    remark: undefined,
  };
  proxy.resetForm("peopleRef");
}

/** 上传前校验并转换base64 */
function beforeAvatarUpload(file) {
  const isJPG = file.type === "image/jpeg" || file.type === "image/png";
  const isLt10M = file.size / 1024 / 1024 < 10;

  if (!isJPG) {
    proxy.$modal.msgError("上传头像图片只能是 JPG/PNG 格式!");
  }
  if (!isLt10M) {
    proxy.$modal.msgError("上传头像图片大小不能超过 10MB!");
  }
  
  // 转换base64并分离数据
  if (isJPG && isLt10M) {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      // 分离存储：预览用完整URL，提交用纯base64
      form.value.picsUrl = reader.result; // 完整URL用于预览
      form.value.pics = reader.result.split(",")[1]; // 纯base64用于提交
      // 清除pics字段的验证错误
      proxy.$refs["peopleRef"]?.clearValidate("pics");
    };
  }
  
  return false; // 禁用自动上传
}

onMounted(() => {
  getGroupList().then(() => {
    getList();
  });
});
</script>

<style scoped>
.group-list {
  max-height: calc(100vh - 300px);
  overflow-y: auto;
}

.group-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid #e4e7ed;
}

.group-item:hover {
  background-color: #f5f7fa;
  border-color: #c0c4cc;
}

.group-item.active {
  background-color: #ecf5ff;
  border-color: #409eff;
  color: #409eff;
}

.group-item span {
  font-size: 14px;
  font-weight: 500;
}

.head-container {
  padding: 16px;
}
</style>

<style scoped>
.avatar-uploader .avatar {
  width: 178px;
  height: 178px;
  display: block;
}

.avatar-uploader :deep(.el-upload) {
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: var(--el-transition-duration-fast);
}

.avatar-uploader :deep(.el-upload:hover) {
  border-color: var(--el-color-primary);
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 178px;
  height: 178px;
  text-align: center;
}
</style>
