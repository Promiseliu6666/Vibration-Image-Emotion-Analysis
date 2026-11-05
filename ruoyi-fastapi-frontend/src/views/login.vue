<template>
  <div class="login-container">
    <!-- 背景图 -->
    <div class="background"></div>

    <!-- 登录卡片 -->
    <div class="login-card">
      <div class="login-card-content">
        <h3 class="title">基于振动图像的心理状态识别系统</h3>

        <el-form
          ref="loginRef"
          :model="loginForm"
          :rules="loginRules"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <!-- 用户名 -->
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              type="text"
              size="large"
              auto-complete="off"
              placeholder="账号"
              clearable
            >
              <template #prefix>
                <svg-icon icon-class="user" class="input-icon" />
              </template>
            </el-input>
          </el-form-item>

          <!-- 密码 -->
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              size="large"
              auto-complete="off"
              placeholder="密码"
              show-password
            >
              <template #prefix>
                <svg-icon icon-class="password" class="input-icon" />
              </template>
            </el-input>
          </el-form-item>

          <!-- 验证码 -->
          <el-form-item prop="code" v-if="captchaEnabled">
            <div class="captcha-wrapper">
              <el-input
                v-model="loginForm.code"
                size="large"
                placeholder="验证码"
                style="width: 60%"
                @keyup.enter="handleLogin"
              >
                <template #prefix>
                  <svg-icon icon-class="validCode" class="input-icon" />
                </template>
              </el-input>
              <div class="captcha-img" @click="getCode" title="点击刷新">
                <img :src="codeUrl" alt="验证码" />
              </div>
            </div>
          </el-form-item>

          <!-- 记住密码 -->
          <el-form-item>
            <el-checkbox v-model="loginForm.rememberMe" label="记住密码" />
          </el-form-item>

          <!-- 登录按钮 & 注册链接 -->
          <el-form-item>
            <el-button
              :loading="loading"
              type="primary"
              size="large"
              style="width: 100%"
              @click.prevent="handleLogin"
            >
              {{ loading ? '登录中...' : '登 录' }}
            </el-button>
          </el-form-item>

          <div v-if="register" class="register-link">
            <router-link to="/register">立即注册</router-link>
          </div>
        </el-form>

        <!-- 底部版权 -->
        <div class="footer">
          Copyright © 2025 All Rights Reserved.
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCurrentInstance } from 'vue'
import { getCodeImg } from '@/api/login'
import Cookies from 'js-cookie'
import { encrypt, decrypt } from '@/utils/jsencrypt'
import useUserStore from '@/store/modules/user'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()
const { proxy } = getCurrentInstance()

const loginRef = ref(null)
const loginForm = ref({
  username: '',
  password: '',
  rememberMe: false,
  code: '',
  uuid: ''
})

const loginRules = {
  username: [{ required: true, trigger: 'blur', message: '请输入您的账号' }],
  password: [{ required: true, trigger: 'blur', message: '请输入您的密码' }],
  code: [{ required: true, trigger: 'blur', message: '请输入验证码' }]
}

const codeUrl = ref('')
const loading = ref(false)
const captchaEnabled = ref(true)
const register = ref(false)
const redirect = ref(undefined)

watch(
  () => route.query,
  (newQuery) => {
    redirect.value = newQuery.redirect || undefined
  },
  { immediate: true }
)

const handleLogin = () => {
  loginRef.value.validate((valid) => {
    if (!valid) return

    loading.value = true

    // 记住密码处理
    if (loginForm.value.rememberMe) {
      Cookies.set('username', loginForm.value.username, { expires: 30 })
      Cookies.set('password', encrypt(loginForm.value.password), { expires: 30 })
      Cookies.set('rememberMe', true, { expires: 30 })
    } else {
      Cookies.remove('username')
      Cookies.remove('password')
      Cookies.remove('rememberMe')
    }

    userStore
      .login(loginForm.value)
      .then(() => {
        const query = { ...route.query }
        delete query.redirect
        return router.push({ path: redirect.value || '/', query })
      })
      .catch(() => {
        if (captchaEnabled.value) getCode()
      })
      .finally(() => {
        loading.value = false
      })
  })
}

const getCode = () => {
  getCodeImg().then((res) => {
    captchaEnabled.value = res.captchaEnabled ?? true
    register.value = res.registerEnabled ?? false
    if (captchaEnabled.value) {
      codeUrl.value = 'data:image/gif;base64,' + res.img
      loginForm.value.uuid = res.uuid
      loginForm.value.code = ''
    }
  })
}

const getCookie = () => {
  const username = Cookies.get('username')
  const password = Cookies.get('password')
  const rememberMe = Cookies.get('rememberMe')

  if (username) loginForm.value.username = username
  if (password) loginForm.value.password = decrypt(password)
  if (rememberMe) loginForm.value.rememberMe = true
}

// 初始化
getCode()
getCookie()
</script>

<style lang="scss" scoped>
.login-container {
  position: relative;
  height: 100vh;
  overflow: hidden;
  display: flex;
  justify-content: center;
  align-items: center;
}

.background {
  position: absolute;
  inset: 0;
  background-image: url('../assets/images/Group1@2x.png');
  background-size: cover;
  background-position: center;
  filter: blur(8px);
  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.35); // 暗化背景突出卡片
  }
}

.login-card {
  width: 420px;
  max-width: 90vw;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
  overflow: hidden;
  z-index: 1;
}

.login-card-content {
  padding: 40px 35px 30px;
}

.title {
  text-align: center;
  font-size: 24px;
  color: #303133;
  margin-bottom: 40px;
  font-weight: 600;
}

.login-form {
  .input-icon {
    font-size: 18px;
    color: #909399;
  }

  :deep(.el-input__wrapper) {
    height: 48px;
    box-shadow: none;
    border-radius: 8px;
  }
}

.captcha-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.captcha-img {
  flex-shrink: 0;
  width: 120px;
  height: 48px;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  transition: all 0.3s;

  &:hover {
    border-color: #409eff;
    box-shadow: 0 0 8px rgba(64, 158, 255, 0.3);
  }

  img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
}

.register-link {
  text-align: right;
  margin-top: 10px;
  a {
    color: #409eff;
    font-size: 14px;
    text-decoration: none;
    &:hover {
      text-decoration: underline;
    }
  }
}

.footer {
  margin-top: 40px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
</style>
