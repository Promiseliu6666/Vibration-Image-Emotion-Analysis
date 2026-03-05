<template>
  <div class="app-container">
    <!-- 搜索表单 -->
    <el-form :model="queryParams" ref="queryRef" :inline="true" v-show="showSearch" label-width="68px">
      <el-form-item label="系统名称" prop="systemName">
        <el-input
          v-model="queryParams.systemName"
          placeholder="请输入系统名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="接口名称" prop="interfaceName">
        <el-input
          v-model="queryParams.interfaceName"
          placeholder="请输入接口名称"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="接口地址" prop="interfaceUrl">
        <el-input
          v-model="queryParams.interfaceUrl"
          placeholder="请输入接口地址"
          clearable
          @keyup.enter="handleQuery"
        />
      </el-form-item>
      <el-form-item label="请求方法" prop="requestMethod">
        <el-select v-model="queryParams.requestMethod" placeholder="请选择请求方法" clearable style="width: 120px;">
          <el-option label="GET" value="GET" />
          <el-option label="POST" value="POST" />
          <el-option label="PUT" value="PUT" />
          <el-option label="DELETE" value="DELETE" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="queryParams.status" placeholder="请选择状态" clearable style="width: 120px;">
          <el-option label="成功" value="0" />
          <el-option label="失败" value="1" />
        </el-select>
      </el-form-item>
      <el-form-item label="请求时间" style="width: 308px">
        <el-date-picker
          v-model="dateRange"
          value-format="YYYY-MM-DD"
          type="daterange"
          range-separator="-"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        ></el-date-picker>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" icon="Search" @click="handleQuery">搜索</el-button>
        <el-button icon="Refresh" @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 操作按钮 -->
    <el-row :gutter="10" class="mb8">
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          :disabled="multiple"
          @click="handleDelete"
        >删除</el-button>
      </el-col>
      <el-col :span="1.5">
        <el-button
          type="danger"
          plain
          icon="Delete"
          @click="handleClean"
        >清空</el-button>
      </el-col>
      <!-- <el-col :span="1.5">
        <el-button
          type="primary"
          plain
          icon="Download"
          @click="handleExport"
        >导出</el-button>
      </el-col> -->
      <right-toolbar v-model:showSearch="showSearch" @queryTable="getList"></right-toolbar>
    </el-row>

    <!-- 日志列表 -->
    <el-table v-loading="loading" :data="logList" @selection-change="handleSelectionChange">
      <el-table-column type="selection" width="55" align="center" />
      <el-table-column label="日志编号" align="center" prop="logId" width="80" />
      <el-table-column label="系统名称" align="center" prop="systemName" width="120" />
      <el-table-column label="接口名称" align="center" prop="interfaceName" width="120" />
      <el-table-column label="接口地址" align="center" prop="interfaceUrl" width="200">
        <template #default="scope">
          <span v-if="scope.row.interfaceUrl && scope.row.interfaceUrl.length > 40" :title="scope.row.interfaceUrl">
            {{ scope.row.interfaceUrl.substring(0, 40) }}...
          </span>
          <span v-else>{{ scope.row.interfaceUrl || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="请求方法" align="center" prop="requestMethod" width="100">
        <template #default="scope">
          <el-tag :type="getMethodTagType(scope.row.requestMethod)">{{ scope.row.requestMethod }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="请求参数" align="center" prop="requestParams" width="150">
        <template #default="scope">
          <span v-if="scope.row.requestParams && scope.row.requestParams.length > 50" :title="scope.row.requestParams">
            {{ scope.row.requestParams.substring(0, 50) }}...
          </span>
          <span v-else>{{ scope.row.requestParams || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="响应状态" align="center" prop="status" width="100">
        <template #default="scope">
          <el-tag :type="scope.row.status === 0 ? 'success' : 'danger'">
            {{ scope.row.status === 0 ? '成功' : '失败' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="响应时间" align="center" prop="costTime" width="100">
        <template #default="scope">
          <span>{{ scope.row.costTime }}ms</span>
        </template>
      </el-table-column>
      <el-table-column label="错误信息" align="center" prop="errorMsg" width="150">
        <template #default="scope">
          <span v-if="scope.row.errorMsg && scope.row.errorMsg.length > 30" :title="scope.row.errorMsg">
            {{ scope.row.errorMsg.substring(0, 30) }}...
          </span>
          <span v-else>{{ scope.row.errorMsg || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="请求时间" align="center" prop="requestTime" width="180">
        <template #default="scope">
          <span>{{ parseTime(scope.row.requestTime) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" class-name="small-padding fixed-width" width="120">
        <template #default="scope">
          <el-button link type="primary" @click="handleView(scope.row)">详情</el-button>
          <el-button link type="primary" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <pagination
      v-show="total > 0"
      :total="total"
      v-model:page="queryParams.pageNum"
      v-model:limit="queryParams.pageSize"
      @pagination="getList"
    />

    <!-- 日志详情弹框 -->
    <el-dialog title="日志详情" v-model="open" width="800px" append-to-body>
      <el-form :model="form" label-width="100px">
        <el-row>
          <el-col :span="12">
            <el-form-item label="日志编号：">{{ form.logId }}</el-form-item>
            <el-form-item label="系统名称：">{{ form.systemName }}</el-form-item>
            <el-form-item label="请求方法：">
              <el-tag :type="getMethodTagType(form.requestMethod)">{{ form.requestMethod }}</el-tag>
            </el-form-item>
            <el-form-item label="响应状态：">
              <el-tag :type="form.status === 0 ? 'success' : 'danger'">
                {{ form.status === 0 ? '成功' : '失败' }}
              </el-tag>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="接口地址：">{{ form.interfaceUrl }}</el-form-item>
            <el-form-item label="响应时间：">{{ form.costTime }}ms</el-form-item>
            <el-form-item label="请求时间：">{{ parseTime(form.requestTime) }}</el-form-item>
            <el-form-item label="响应时间：">{{ parseTime(form.responseTime) }}</el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="12">
            <el-form-item label="请求IP：">{{ form.requestIp }}</el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="链路ID：">{{ form.traceId }}</el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-form-item label="用户代理：">
              <el-input
                v-model="form.userAgent"
                type="textarea"
                :rows="2"
                readonly
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-form-item label="请求参数：">
              <div class="json-viewer">
                <pre class="json-content">{{ formatJsonData(form.requestParams) }}</pre>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row>
          <el-col :span="24">
            <el-form-item label="响应结果：">
              <div class="json-viewer">
                <pre class="json-content">{{ formatJsonData(form.responseData) }}</pre>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.remark">
          <el-col :span="24">
            <el-form-item label="备注信息：">
              <el-input
                v-model="form.remark"
                type="textarea"
                :rows="2"
                readonly
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row v-if="form.errorMsg">
          <el-col :span="24">
            <el-form-item label="错误信息：">
              <el-input
                v-model="form.errorMsg"
                type="textarea"
                :rows="3"
                readonly
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="cancel">关 闭</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="SystemLog">
import { ref, reactive, onMounted, getCurrentInstance } from 'vue'
import { list, delIntegrationLog, cleanIntegrationLog, exportIntegrationLog } from '@/api/monitor/integration'
import { parseTime } from '@/utils/ruoyi'

const { proxy } = getCurrentInstance()

// 遮罩层
const loading = ref(true)
// 选中数组
const ids = ref([])
// 非多个禁用
const multiple = ref(true)
// 显示搜索条件
const showSearch = ref(true)
// 总条数
const total = ref(0)
// 日志表格数据
const logList = ref([])
// 弹出层标题
const title = ref('')
// 是否显示弹出层
const open = ref(false)
// 日期范围
const dateRange = ref([])
// 表单参数
const form = ref({})
// 查询参数
const queryParams = reactive({
  pageNum: 1,
  pageSize: 10,
  systemName: undefined,
  interfaceName: undefined,
  interfaceUrl: undefined,
  requestMethod: undefined,
  status: undefined
})

/** 查询日志列表 */
function getList() {
  loading.value = true
  const params = {
    ...queryParams,
    ...dateRange.value && dateRange.value.length === 2 ? {
      beginTime: dateRange.value[0],
      endTime: dateRange.value[1]
    } : {}
  }
  list(params).then(response => {
    console.log('response', response);
    
    logList.value = response.rows || []
    total.value = response.total || 0
    loading.value = false
  }).catch(() => {
    loading.value = false
  })
}

/** 搜索按钮操作 */
function handleQuery() {
  queryParams.pageNum = 1
  getList()
}

/** 重置按钮操作 */
function resetQuery() {
  dateRange.value = []
  proxy.resetForm('queryRef')
  handleQuery()
}

/** 多选框选中数据 */
function handleSelectionChange(selection) {
  ids.value = selection.map(item => item.logId)
  multiple.value = !selection.length
}

/** 详情按钮操作 */
function handleView(row) {
  open.value = true
  form.value = { ...row }
}

/** 删除按钮操作 */
function handleDelete(row) {
  const logIds = row.logId || ids.value.join(',')
  proxy.$modal.confirm('是否确认删除日志编号为"' + logIds + '"的数据项？').then(function() {
    delIntegrationLog(logIds).then(() => {
      proxy.$modal.msgSuccess('删除成功')
      getList()
    })
  }).catch(() => {})
}

/** 清空按钮操作 */
function handleClean() {
  proxy.$modal.confirm('是否确认清空所有日志数据项？').then(function() {
    cleanIntegrationLog().then(() => {
      proxy.$modal.msgSuccess('清空成功')
      getList()
    })
  }).catch(() => {})
}

/** 导出按钮操作 */
function handleExport() {
  const params = {
    ...queryParams,
    ...dateRange.value && dateRange.value.length === 2 ? {
      beginTime: dateRange.value[0],
      endTime: dateRange.value[1]
    } : {}
  }
  proxy.download('monitor/integration/export', params, `integration_log_${new Date().getTime()}.xlsx`)
}

/** 取消按钮 */
function cancel() {
  open.value = false
  form.value = {}
}

/** 获取请求方法标签类型 */
function getMethodTagType(method) {
  const methodTypes = {
    'GET': 'success',
    'POST': 'primary',
    'PUT': 'warning',
    'DELETE': 'danger'
  }
  return methodTypes[method] || 'info'
}

/** 格式化JSON数据 */
function formatJsonData(data) {
  if (!data) return ''
  
  // 如果数据已经是对象，直接格式化
  if (typeof data === 'object') {
    return JSON.stringify(data, null, 2)
  }
  
  // 如果是字符串，尝试解析
  if (typeof data === 'string') {
    // 去除首尾空白字符
    const trimmedData = data.trim()
    
    // 检查是否以 { 或 [ 开头（可能是JSON）
    if (trimmedData.startsWith('{') || trimmedData.startsWith('[')) {
      try {
        const parsed = JSON.parse(trimmedData)
        return JSON.stringify(parsed, null, 2)
      } catch (e) {
        // JSON解析失败，返回原始数据
        return data
      }
    }
  }
  
  // 其他情况直接返回原始数据
  return data
}

onMounted(() => {
  getList()
})
</script>

<style scoped>
.transfer-item-with-button {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.item-label {
  flex: 1;
  text-align: left;
}

.config-btn {
  margin-left: 8px;
}

.config-placeholder {
  width: 40px;
}

.json-viewer {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background-color: #f5f7fa;
  max-height: 300px;
  overflow-y: auto;
  flex: 1;
}

.json-content {
  margin: 0;
  padding: 12px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #2c3e50;
  background-color: transparent;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.json-content::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.json-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.json-content::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.json-content::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>