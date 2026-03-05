<template>
  <div class="app-container">
    <el-row :gutter="20">
      <!-- 左侧控制面板 -->
      <el-col :span="12">
        <el-card class="control-panel">
          <template #header>
            <div class="card-header">
              <span>人脸识别设置</span>
            </div>
          </template>
          
          <el-form 
            :model="form" 
            :rules="rules" 
            ref="formRef" 
            label-width="100px" 
            v-loading="formLoading"
          >
            <!-- 分组选择 -->
            <el-form-item label="目标分组" prop="groupId">
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
            
            <!-- 阈值设置 -->
            <el-form-item label="识别阈值" prop="threshold">
              <el-input-number 
                v-model="form.threshold" 
                :min="0" 
                :max="1" 
                :step="0.01"
                step-strictly
                controls-position="right"
                style="width: 100%"
                placeholder="请输入识别阈值(0-1)"
              />
<!--              <div class="threshold-tip">阈值越高要求越相似，建议值0.5左右</div>-->
            </el-form-item>
            
            <!-- 图片上传 -->
            <el-form-item label="上传图片" prop="image">
              <el-upload
                class="avatar-uploader"
                :show-file-list="false"
                :on-success="handleAvatarSuccess"
                :before-upload="beforeAvatarUpload"
                drag
              >
                <img v-if="form.imageUrl" :src="form.imageUrl" class="avatar" />
                <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
                <div v-if="!form.imageUrl" class="el-upload__text">
                  将文件拖到此处，或<em>点击上传</em>
                </div>
              </el-upload>
            </el-form-item>
            
            <!-- 识别按钮 -->
            <el-form-item>
              <el-button 
                type="primary" 
                @click="handleFaceCompare" 
                :loading="compareLoading"
                :disabled="!form.groupId || !form.image || compareLoading"
                style="width: 100%"
              >
                {{ compareLoading ? '识别中...' : '开始识别' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
      
      <!-- 右侧结果展示 -->
      <el-col :span="12">
        <el-card class="result-panel" v-loading="resultLoading">
          <template #header>
            <div class="card-header">
              <span>识别结果</span>
            </div>
          </template>
          
          <div v-if="result" class="result-content">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="人员编码">
                {{ result.name || '未匹配到人员' }}
              </el-descriptions-item>
              <el-descriptions-item label="相似度">
                <el-tag type="success">{{ result.similarity !== undefined ? result.similarity.toFixed(2) : 'N/A' }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>
            
            <div class="image-preview" v-if="result.pics">
              <div class="image-label">匹配人员照片：</div>
              <el-image
                :src="'data:image/png;base64,' + result.pics"
                class="preview-image"
                fit="contain"
                :preview-src-list="['data:image/png;base64,' + result.pics]"
                preview-teleported
              />
            </div>
            
            <div v-else class="no-image">
              <img src="@/assets/images/no_photo.jpg" alt="暂无匹配人员照片" class="no-photo-image">
            </div>
          </div>
          
          <div v-else class="no-result">
            <el-empty description="请先上传图片并点击识别" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup name="FaceCompare">
import { ref, reactive, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { listGroup } from '@/api/face/group'
import { faceCompare } from '@/api/face/people'
import { ElMessage } from 'element-plus'

const formRef = ref()
const groupOptions = ref([])
const formLoading = ref(false)
const compareLoading = ref(false)
const resultLoading = ref(false)
const result = ref(null)

const form = reactive({
  groupId: null,
  threshold: 0.3,
  image: '',
  imageUrl: ''
})

const rules = reactive({
  groupId: [
    { required: true, message: '请选择分组', trigger: 'change' }
  ],
  threshold: [
    { required: true, message: '请输入识别阈值', trigger: 'blur' }
  ],
  image: [
    { required: true, message: '请上传图片', trigger: 'change' }
  ]
})

// 获取分组列表
function getGroupList() {
  formLoading.value = true
  listGroup().then(res => {
    const data = res.data || {}
    groupOptions.value = data.rows || []
    formLoading.value = false
  }).catch(() => {
    formLoading.value = false
    ElMessage.error('获取分组列表失败')
  })
}

// 上传前处理
function beforeAvatarUpload(file) {
  const isJPG = file.type === 'image/jpeg' || file.type === 'image/png'
  const isLt10M = file.size / 1024 / 1024 <= 10

  if (!isJPG) {
    ElMessage.error('上传头像图片只能是 JPG/PNG 格式!')
    return false
  }
  if (!isLt10M) {
    ElMessage.error('上传头像图片大小不能超过 10MB!')
    return false
  }
  
  // 转换为base64
  const reader = new FileReader()
  reader.readAsDataURL(file)
  reader.onload = () => {
    // 分离存储：预览用完整URL，提交用纯base64
    form.imageUrl = reader.result // 完整URL用于预览
    form.image = reader.result.split(',')[1] // 纯base64用于提交
    // 清除验证错误
    formRef.value?.clearValidate('image')
  }
  
  return false // 禁用自动上传
}

// 上传成功处理
function handleAvatarSuccess(res, file) {
  form.imageUrl = URL.createObjectURL(file.raw)
  form.image = file.raw.split(',')[1]
}

// 人脸比对
function handleFaceCompare() {
  formRef.value.validate((valid) => {
    if (valid) {
      compareLoading.value = true
      resultLoading.value = true
      
      const compareData = {
        groupId: form.groupId,
        image: form.image,
        threshold: form.threshold
      }
      
      faceCompare(compareData).then(response => {
        compareLoading.value = false
        resultLoading.value = false
        
        if (response.code === 200) {
          result.value = response.data
          if (Object.keys(response.data).length === 0) {
            ElMessage.warning('未找到匹配的人员')
          } else {
            ElMessage.success('识别成功')
          }
        } else {
          ElMessage.error(response.msg || '识别失败')
        }
      }).catch(error => {
        compareLoading.value = false
        resultLoading.value = false
        ElMessage.error('识别失败: ' + error.message)
      })
    }
  })
}

onMounted(() => {
  getGroupList()
})
</script>

<style scoped>
.control-panel,
.result-panel {
  height: 100%;
}

.card-header {
  font-weight: bold;
  font-size: 16px;
}

.threshold-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.avatar-uploader {
  width: 100%;
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
  width: 100%;
  height: 300px;
  text-align: center;
}

.avatar {
  max-width: 100%;
  max-height: 300px;
  display: block;
  margin: 0 auto;
}

.result-content {
  padding: 20px 0;
}

.image-preview {
  margin-top: 20px;
}

.image-label {
  margin-bottom: 10px;
  font-weight: bold;
}

.preview-image {
  height: 300px;
  border-radius: 4px;
  margin: 0 auto;
  display: block;
}

.no-result {
  padding: 40px 0;
}

.no-image {
  text-align: center;
  padding: 20px 0;
}

.no-photo-image {
  max-width: 100%;
  max-height: 300px;
  border-radius: 4px;
}
</style>