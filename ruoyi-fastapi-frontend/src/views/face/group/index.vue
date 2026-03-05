<template>
  <div class="app-container">
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="分组名称" prop="name">
        <el-input
          v-model="queryParams.name"
          placeholder="请输入分组名称"
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

    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Plus"
          @click="handleAdd"
        >新增</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="success"
          plain
          icon="Edit"
          :disabled="single"
          @click="handleUpdate"
        >修改</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
        >删除</el-button>
      </el-col>
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <el-table v-loading="loading" :data="groupList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <!-- <el-table-column label="序号" type="index" width="80" align="center">
        <template #default="scope">
          <span>{{ (queryParams.pageNum - 1) * queryParams.pageSize + scope.$index + 1 }}</span>
        </template>
      </el-table-column> -->
      <el-table-column label="分组ID" align="center" prop="id" />
      <el-table-column label="分组名称" align="center" prop="name" :show-overflow-tooltip="true" />
      <el-table-column label="创建时间" align="center" prop="createdTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.createdTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" align="center" prop="updatedTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.updatedTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" width="160" class-name="small-padding fixed-width">
        <template #default="scope">
          <el-tooltip content="修改" placement="top">
            <el-button link type="primary" icon="Edit" @click="handleUpdate(scope.row)"></el-button>
          </el-tooltip>
          <el-tooltip content="删除" placement="top">
            <el-button link type="primary" icon="Delete" @click="handleDelete(scope.row)"></el-button>
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

    <!-- 添加或修改分组对话框 -->
    <el-dialog :title="title" v-model="open" width="500px" append-to-body>
      <el-form ref="groupRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="分组名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入分组名称" />
        </el-form-item>
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

<script setup name="Group">
import { ref, reactive, toRefs, getCurrentInstance, onMounted } from 'vue'
import { listGroup, getGroup, delGroup, addGroup, updateGroup } from '@/api/face/group'

const { proxy } = getCurrentInstance()
const { parseTime } = proxy

const groupList = ref([])
const open = ref(false)
const loading = ref(true)
const showSearch = ref(true)
const ids = ref([])
const single = ref(true)
const multiple = ref(true)
const total = ref(0)
const title = ref("")

const data = reactive({
  form: {},
  queryParams: {
    pageNum: 1,
    pageSize: 10,
    name: undefined
  },
  rules: {
    name: [{ required: true, message: "分组名称不能为空", trigger: "blur" }]
  }
})

const { queryParams, form, rules } = toRefs(data)

/** 查询分组列表 */
function getList() {
  loading.value = true
  listGroup(queryParams.value).then(response => {
    groupList.value = response.data.rows
    total.value = response.data.total
    loading.value = false
  })
}

/** 取消按钮 */
function cancel() {
  open.value = false
  reset()
}

/** 表单重置 */
function reset() {
  form.value = {
    id: null,
    name: null
  }
  proxy.resetForm("groupRef")
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.value.pageNum = 1
  getList()
}

/** 重置按钮操作 */
function resetQuery() {
  proxy.resetForm("queryRef")
  handleQuery()
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.id)
  single.value = selection.length != 1
  multiple.value = !selection.length
}

/** 新增按钮操作 */
function handleAdd() {
  reset()
  open.value = true
  title.value = "添加分组"
}

/** 修改按钮操作 */
function handleUpdate(row) {
  reset()
  const groupId = row.id || ids.value[0]
  getGroup(groupId).then(response => {
    form.value = response.data
    open.value = true
    title.value = "修改分组"
  })
}

/** 提交按钮 */
function submitForm() {
  proxy.$refs["groupRef"].validate(valid => {
    if (valid) {
      if (form.value.id != null) {
        updateGroup(form.value).then(response => {
          proxy.$modal.msgSuccess("修改成功")
          open.value = false
          getList()
        })
      } else {
        addGroup(form.value).then(response => {
          proxy.$modal.msgSuccess("新增成功")
          open.value = false
          getList()
        })
      }
    }
  })
}

/** 删除按钮操作 */
function handleDelete(row) {
  console.log('row:', row)
  console.log('ids.value:', ids.value[0])
  
  let groupIds = []
  if (row && !(row instanceof PointerEvent)) {
    groupIds = [row.id]
  } else {
    for (let i = 0; i < ids.value.length; i++) {
        console.log('ids.value[i]:', ids.value[i]);
        
      groupIds.push(ids.value[i])
    }
  }
  console.log('groupIds:', groupIds)
  
  const confirmText = groupIds.length === 1 
    ? `是否确认删除分组编号为"${groupIds[0]}"的数据项？`
    : `是否确认删除选中的${groupIds.length}个分组？`
  
  proxy.$modal.confirm(confirmText).then(async function() {
    try {
      // 逐个删除
      for (const groupId of groupIds) {
        console.log('删除ID:', groupId)
        await delGroup(groupId)
      }
      getList()
      proxy.$modal.msgSuccess("删除成功")
    } catch (error) {
      console.error('删除错误:', error)
      proxy.$modal.msgError("删除失败")
    }
  }).catch(() => {})
}

// 组件挂载时获取数据
onMounted(() => {
  getList()
})
</script>
