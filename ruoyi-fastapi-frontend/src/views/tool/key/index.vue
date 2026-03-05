<template>
  <div class="app-container">
    <div class="api-key-header">
      <h2>API Key 管理</h2>
      <p class="description">
        API Key 用于访问系统接口，请妥善保管您的密钥。为了安全起见，密钥只在生成时完整显示一次，
        之后将以打码形式展示。如果遗失密钥，请重新生成。
      </p>
    </div>

    <el-card class="api-key-card" shadow="hover">
      <template #header>
         <span>API Key 管理</span>
       </template>
      
      <div class="api-key-content">
        <div v-if="apiKey" class="key-display">
          <div class="key-row">
            <el-input 
              v-model="displayKey" 
              readonly 
              class="key-input"
              placeholder="暂无 API Key"
            >
            </el-input>
            <el-button 
              type="danger" 
              size="small" 
              icon="Refresh" 
              @click="handleResetKey"
              :loading="resetting"
              style="margin-left: 8px;"
            >
              重置
            </el-button>
          </div>
          <div class="key-meta">
            <span class="create-time">创建时间: {{ formatTime(keyInfo.createdTime) }}</span>
            <el-tag size="small" :type="keyInfo.status === 'active' ? 'success' : 'danger'">
              {{ keyInfo.status === 'active' ? '有效' : '已失效' }}
            </el-tag>
          </div>
        </div>
         
         <div v-else class="no-key">
           <el-button type="primary" @click="handleGenerateKey" :loading="generating">
             生成 API Key
           </el-button>
         </div>
       </div>

      <!-- 回调地址管理 -->
      <div class="callback-section">
        <div class="callback-header">
          <h4>回调地址管理</h4>
          <el-button type="primary" size="small" icon="Plus" @click="showAddCallbackDialog = true">
            新增回调地址
          </el-button>
        </div>
        
        <div class="callback-list">
          <el-table :data="callbackList" style="width: 100%" v-if="callbackList.length > 0">
            <el-table-column prop="url" label="回调地址" min-width="300">
                <template #default="{ row }">
                  <span class="callback-url-text">{{ row.url }}</span>
                </template>
              </el-table-column>
            <el-table-column prop="description" label="描述" min-width="200" />
            <el-table-column prop="createTime" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatTime(row.createTime) }}
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <el-tag size="small" :type="row.status === '0' ? 'success' : 'danger'">
                  {{ row.status === '0' ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row, $index }">
                <el-button 
                  size="small" 
                  :type="row.status === '0' ? 'warning' : 'success'"
                  @click="toggleCallbackStatus(row)">
                  {{ row.status === '0' ? '禁用' : '启用' }}
                </el-button>
                <el-button 
                  size="small" 
                  type="danger" 
                  @click="handleDeleteCallback(row, $index)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty v-else description="暂无回调地址" :image-size="60">
            <el-button type="primary" size="small" @click="showAddCallbackDialog = true">
              添加回调地址
            </el-button>
          </el-empty>
        </div> 
      </div>
    </el-card>

    <el-card class="usage-guide" shadow="never">
      <template #header>
        <span>使用说明</span>
      </template>
      <div class="guide-content">
        <h4>如何使用 API Key：</h4>
        <ol>
          <li>在请求头中添加 X-API-Token 字段</li>
          <li>格式：<code>X-API-Token: YOUR_API_KEY</code></li>
          <li>确保在 HTTPS 环境下使用，保护密钥安全</li>
          <li>定期更换密钥以提高安全性</li>
        </ol>
        
        <h4>注意事项：</h4>
        <ul>
          <li>API Key 具有与您账户相同的权限，请勿泄露</li>
          <li>如发现密钥泄露，请立即重置</li>
          <li>重置密钥后，使用旧密钥的请求将失效</li>
        </ul>
      </div>
    </el-card>

    <!-- API Key 展示弹窗 -->
    <el-dialog
      v-model="showKeyDialog"
      title="API Key 生成成功"
      width="500px"
      :close-on-click-modal="false"
      @close="closeKeyDialog"
    >
      <div class="key-dialog-content">
        <div class="success-icon">
          <el-icon size="48" color="#67c23a">
            <Check />
          </el-icon>
        </div>
        <p class="dialog-tip">请立即复制并保存您的 API Key，关闭弹窗后将无法再次查看完整密钥。</p>
        <div class="key-display">
          <el-input
            v-model="newGeneratedKey"
            readonly
            type="textarea"
            :rows="3"
            class="key-textarea"
          />
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="closeKeyDialog">关闭</el-button>
          <el-button type="primary" @click="copyNewKey">
             <el-icon><DocumentCopy /></el-icon>
             复制 API Key
           </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 添加回调地址弹窗 -->
    <el-dialog
      v-model="showAddCallbackDialog"
      title="新增回调地址"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="callbackForm" :rules="callbackRules" ref="callbackFormRef" label-width="100px">
        <el-form-item label="回调地址" prop="url">
          <el-input 
            v-model="callbackForm.url" 
            placeholder="请输入回调地址，如：https://example.com/callback"
            type="textarea"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input 
            v-model="callbackForm.description" 
            placeholder="请输入回调地址描述（可选）"
            type="textarea"
            :rows="2"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showAddCallbackDialog = false">取消</el-button>
          <el-button type="primary" @click="handleAddCallback" :loading="addingCallback">
            确定
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup name="ApiKey">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy, Check, Plus } from '@element-plus/icons-vue'
import { generateApiToken, getApiKey } from '@/api/login'
import { listCallback, addCallback, delCallback, updateCallback } from '@/api/tool/callback'

// 响应式数据
const apiKey = ref('')
const displayKey = ref('')
const generating = ref(false)
const resetting = ref(false)

const keyInfo = reactive({
  createdTime: '',
  status: 'active'
})

// 回调地址管理数据
const callbackList = ref([])
const showAddCallbackDialog = ref(false)
const addingCallback = ref(false)
const callbackFormRef = ref(null)

const callbackForm = reactive({
  url: '',
  description: ''
})

const callbackRules = {
  url: [
    { required: true, message: '请输入回调地址', trigger: 'blur' },
    { 
      pattern: /^https?:\/\/.+/,
      message: '请输入有效的HTTP(S)地址',
      trigger: 'blur'
    }
  ],
  description: [
    { max: 200, message: '描述不能超过200个字符', trigger: 'blur' }
  ]
}

// 格式化时间
const formatTime = (time) => {
  if (!time) return ''
  return new Date(time).toLocaleString('zh-CN')
}

// 打码显示密钥
const maskKey = (key) => {
  if (!key) return ''
  if (key.length <= 8) return key
  return key.substring(0, 4) + '*'.repeat(key.length - 8) + key.substring(key.length - 4)
}

// 生成API Key
const generateApiKey = () => {
  // 模拟生成32位随机字符串
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = 'sk-'
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

// 弹窗相关状态
const showKeyDialog = ref(false)
const newGeneratedKey = ref('')

// 处理生成密钥
const handleGenerateKey = async () => {
  try {
    generating.value = true
    
    const response = await generateApiToken()
      if (response.code === 200) {
        const newKey = response.api_token
        apiKey.value = newKey
        displayKey.value = maskKey(newKey) // 直接打码显示
        keyInfo.createdTime = new Date().toISOString()
        keyInfo.status = 'active'
        
        // 显示弹窗展示完整密钥
        newGeneratedKey.value = newKey
        showKeyDialog.value = true
        
        ElMessage.success('API Key 生成成功')
      } else {
        ElMessage.error(response.msg || 'API Key 生成失败')
      }
    
  } catch (error) {
    console.error('生成API Key失败:', error)
    ElMessage.error('生成 API Key 失败')
  } finally {
    generating.value = false
  }
}

// 处理重置密钥
const handleResetKey = async () => {
  try {
    await ElMessageBox.confirm(
      '重置后旧密钥将立即失效，确定要重置 API Key 吗？',
      '确认重置',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    resetting.value = true
    
    const response = await generateApiToken()
      if (response.code === 200) {
        const newKey = response.api_token
        apiKey.value = newKey
        displayKey.value = maskKey(newKey) // 直接打码显示
        keyInfo.createdTime = new Date().toISOString()
        keyInfo.status = 'active'
        
        // 显示弹窗展示完整密钥
        newGeneratedKey.value = newKey
        showKeyDialog.value = true
        
        ElMessage.success('API Key 重置成功')
      } else {
        ElMessage.error(response.msg || '重置 API Key 失败')
      }
    
  } catch (error) {
    if (error !== 'cancel') {
      console.error('重置API Key失败:', error)
      ElMessage.error('重置 API Key 失败')
    }
  } finally {
    resetting.value = false
  }
}

// 复制密钥
const copyKey = async () => {
  if (!apiKey.value) return
  
  try {
    await navigator.clipboard.writeText(apiKey.value)
    ElMessage.success('API Key 已复制到剪贴板')
  } catch (error) {
    // 降级方案
    const textArea = document.createElement('textarea')
    textArea.value = apiKey.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    ElMessage.success('API Key 已复制到剪贴板')
  }
}

// 复制弹窗中的新密钥
const copyNewKey = async () => {
  try {
    await navigator.clipboard.writeText(newGeneratedKey.value)
    ElMessage.success('API Key 已复制到剪贴板')
  } catch (error) {
    // 降级方案
    const textArea = document.createElement('textarea')
    textArea.value = newGeneratedKey.value
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
    ElMessage.success('API Key 已复制到剪贴板')
  }
}

// 关闭密钥弹窗
const closeKeyDialog = () => {
  showKeyDialog.value = false
  newGeneratedKey.value = ''
}

// 初始化数据
const initData = async () => {
  try {
    const response = await getApiKey()
     if (response.code === 200) {
       if (response.has_key) {
         apiKey.value = response.api_key // 这里是打码后的key
         displayKey.value = response.api_key
         // 从本地存储获取创建时间
         const savedData = localStorage.getItem('apiKeyInfo')
         if (savedData) {
           const parsed = JSON.parse(savedData)
           keyInfo.createdTime = parsed.createdTime || new Date().toISOString()
         } else {
           keyInfo.createdTime = new Date().toISOString()
         }
         keyInfo.status = 'active'
       } else {
         apiKey.value = ''
         displayKey.value = ''
         keyInfo.createdTime = ''
         keyInfo.status = 'active'
       }
     }
  } catch (error) {
    console.error('查询API Key失败:', error)
    // 如果接口调用失败，尝试从本地存储恢复数据
    const existingKey = localStorage.getItem('apiKey')
    const existingKeyInfo = localStorage.getItem('apiKeyInfo')
    
    if (existingKey && existingKeyInfo) {
      apiKey.value = existingKey
      displayKey.value = maskKey(existingKey)
      Object.assign(keyInfo, JSON.parse(existingKeyInfo))
    }
  }
}

// 保存到本地存储（实际项目中应该保存到后端）
const saveToStorage = () => {
  if (apiKey.value) {
    localStorage.setItem('apiKey', apiKey.value)
    localStorage.setItem('apiKeyInfo', JSON.stringify(keyInfo))
  }
}

// 回调地址管理函数
const loadCallbackList = async () => {
  try {
    const response = await listCallback({ pageNum: 1, pageSize: 100 })
    if (response.code === 200) {
      callbackList.value = response.rows
    }
  } catch (error) {
    console.error('加载回调地址列表失败:', error)
    callbackList.value = []
  }
}

const handleAddCallback = async () => {
  try {
    await callbackFormRef.value.validate()
    addingCallback.value = true
    
    const newCallback = {
      url: callbackForm.url.trim(),
      description: callbackForm.description.trim(),
      status: '0'
    }
    
    const response = await addCallback(newCallback)
    if (response.code === 200) {
      ElMessage.success('回调地址添加成功')
      showAddCallbackDialog.value = false
      resetCallbackForm()
      loadCallbackList()
    } else {
      ElMessage.error(response.msg || '添加回调地址失败')
    }
  } catch (error) {
    console.error('添加回调地址失败:', error)
  } finally {
    addingCallback.value = false
  }
}

const handleDeleteCallback = async (row, index) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除回调地址 "${row.url}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const response = await delCallback(row.callbackId)
    if (response.code === 200) {
      ElMessage.success('回调地址删除成功')
      loadCallbackList()
    } else {
       ElMessage.error(response.msg || '删除回调地址失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除回调地址失败:', error)
    }
  }
}

const toggleCallbackStatus = async (row) => {
  try {
    const newStatus = row.status === '0' ? '1' : '0'
    const response = await updateCallback({
      callbackId: row.callbackId,
      status: newStatus
    })
    
    if (response.code === 200) {
      ElMessage.success(`回调地址已${newStatus === '0' ? '启用' : '禁用'}`)
      loadCallbackList()
    } else {
      ElMessage.error(response.msg || '修改状态失败')
    }
  } catch (error) {
    console.error('修改状态失败:', error)
  }
}

const resetCallbackForm = () => {
  callbackForm.url = ''
  callbackForm.description = ''
  if (callbackFormRef.value) {
    callbackFormRef.value.clearValidate()
  }
}

// 监听数据变化并保存
watch(() => apiKey.value, saveToStorage)
watch(() => keyInfo, saveToStorage, { deep: true })

onMounted(async () => {
  await initData()
  loadCallbackList()
})
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.api-key-header {
  margin-bottom: 24px;
}

.api-key-header h2 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 24px;
  font-weight: 600;
}

.description {
  color: #606266;
  line-height: 1.6;
  margin: 0;
  font-size: 14px;
}

.api-key-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.api-key-content {
  padding: 16px 0;
}

.key-display {
  margin-bottom: 16px;
}

.key-row {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.key-input {
  font-family: 'Courier New', monospace;
  flex: 1;
}

.key-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #909399;
}

.create-time {
  color: #606266;
}

.usage-guide {
  margin-top: 24px;
}

.guide-content h4 {
  margin: 0 0 12px 0;
  color: #303133;
  font-size: 16px;
}

.guide-content ol,
.guide-content ul {
  margin: 0 0 20px 0;
  padding-left: 20px;
}

.guide-content li {
  margin-bottom: 8px;
  line-height: 1.5;
  color: #606266;
}

.guide-content code {
  background-color: #f1f2f3;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #e74c3c;
}

.no-key {
  text-align: center;
  padding: 40px 0;
}

/* 弹窗样式 */
.key-dialog-content {
  text-align: center;
}

.success-icon {
  margin-bottom: 16px;
}

.dialog-tip {
  color: #606266;
  font-size: 14px;
  margin-bottom: 20px;
  line-height: 1.6;
}

.key-display {
  margin-bottom: 20px;
}

.key-textarea {
  font-family: 'Courier New', monospace;
  font-size: 13px;
}

.key-textarea .el-textarea__inner {
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  resize: none;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* 回调地址管理样式 */
.callback-section {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #e4e7ed;
}

.callback-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.callback-header h4 {
  margin: 0;
  color: #303133;
  font-size: 16px;
  font-weight: 600;
}

.callback-list {
  background-color: #fafafa;
  border-radius: 6px;
  padding: 16px;
}

:deep(.el-table) {
  background-color: transparent;
}

:deep(.el-table th) {
  background-color: #f5f7fa;
}

:deep(.el-table--enable-row-hover .el-table__body tr:hover > td) {
  background-color: #f0f2f5;
}

.callback-url-text {
  color: #409eff;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  word-break: break-all;
  line-height: 1.4;
}
</style>