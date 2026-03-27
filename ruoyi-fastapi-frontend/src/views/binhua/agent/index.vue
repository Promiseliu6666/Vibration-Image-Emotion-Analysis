<template>
  <div class="agent-chat-page">
    <div class="chat-header">
      <div class="header-left">
        <el-avatar :src="aiAvatar" size="42" class="ai-avatar" />
        <div class="header-info">
          <h3>AI Agent 助手</h3>
          <p class="status">在线 •</p>
        </div>
      </div>
      <div class="header-right">
        <el-input
          v-model="conversationId"
          placeholder="会话ID"
          size="small"
          style="width: 260px"
          clearable
        />
        <el-button type="primary" size="small" @click="loadHistory">加载历史</el-button>
        <el-button type="danger" size="small" plain @click="clearConversation">清空会话</el-button>
      </div>
    </div>

    <div class="chat-body" ref="chatBodyRef">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar-wrapper">
          <el-avatar
            :src="msg.role === 'user' ? userAvatar : aiAvatar"
            size="42"
            class="message-avatar"
          />
        </div>

        <div class="message-bubble" :class="{ 'has-image': hasImage(msg) }">
          <!-- 图片 -->
          <div v-if="getImageSrc(msg)" class="bubble-image">
            <img
              :src="getImageSrc(msg)"
              alt="图片"
              @click="previewImageFull(getImageSrc(msg))"
            />
          </div>

          <!-- 文字内容 - 根据消息类型选择渲染方式 -->
          <div
            v-if="msg.content && msg.content.trim() && msg.type !== 'image'"
            class="bubble-text"
            :class="{ 'markdown-body': shouldRenderMarkdown(msg) }"
          >
            <!-- AI 最终回复：使用 Markdown 渲染 -->
            <div v-if="shouldRenderMarkdown(msg)" v-html="renderMarkdown(msg.content)"></div>
            <!-- 用户消息 / AI 流式输出中：纯文本格式（支持换行） -->
            <div v-else v-html="formatPlainText(msg.content)"></div>
            <span v-if="msg.streaming" class="cursor">|</span>
          </div>

          <div class="message-time">{{ formatTime(msg.created_time) }}</div>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-if="loading && !currentStreamingMsg" class="message assistant">
        <div class="message-avatar-wrapper">
          <el-avatar :src="aiAvatar" size="42" class="message-avatar" />
        </div>
        <div class="message-bubble loading-bubble">
          <span class="typing">AI 正在思考...</span>
        </div>
      </div>
    </div>

    <div class="chat-footer">
      <!-- 图片预览 -->
      <div v-if="previewImage" class="image-preview-bar">
        <div class="preview-item">
          <img :src="previewImage" />
          <el-icon class="remove-icon" @click="removeImage"><Close /></el-icon>
        </div>
      </div>

      <div class="input-container">
        <div class="tools">
          <el-button
            circle
            @mousedown="startRecording"
            @mouseup="stopRecording"
            @mouseleave="stopRecording"
            :disabled="loading"
          >
            <el-icon><Microphone /></el-icon>
          </el-button>
          <el-upload
            action="#"
            :show-file-list="false"
            :auto-upload="false"
            @change="handleImageSelect"
          >
            <el-button circle :disabled="loading">
              <el-icon><Picture /></el-icon>
            </el-button>
          </el-upload>
        </div>

        <el-input
          v-model="inputMessage"
          placeholder="输入消息，按 Enter 发送..."
          @keyup.enter="sendMessage"
          :disabled="loading"
          clearable
          type="textarea"
          :rows="1"
          autosize
        />

        <el-button
          type="primary"
          :disabled="loading || (!inputMessage.trim() && !selectedImageFile)"
          @click="sendMessage"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from "vue"
import { ElMessage } from "element-plus"
import { Microphone, Picture, Close } from "@element-plus/icons-vue"
import MarkdownIt from "markdown-it"
import hljs from "highlight.js"
import "highlight.js/styles/github-dark.css" // 代码高亮样式

import {
  chatWithAgentStream,
  getAgentHistory,
  deleteAgentConversation
} from "@/api/binhua/agent"

// 初始化 Markdown 渲染器
const md = new MarkdownIt({
  html: false,        // 不解析 HTML 标签，防止 XSS
  linkify: true,      // 自动识别 URL 并转换为链接
  typographer: true,  // 优化排版
  breaks: true,       // 将换行符转换为 <br>
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>'
      } catch (__) {}
    }
    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

const conversationId = ref("conv_" + Date.now())
const messages = ref([])
const inputMessage = ref("")
const previewImage = ref(null)
const selectedImageFile = ref(null)
const selectedImageDataUrl = ref(null)
const loading = ref(false)
const currentStreamingMsg = ref(null)

const chatBodyRef = ref(null)

// 头像资源（使用高质量、比例正常的图片）
const userAvatar = "https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55b.png"
const aiAvatar = "https://fastly.jsdelivr.net/npm/@intergrav/devins-badges@3/assets/cozy-minimal/available/github_vector.svg"
// 备用头像（防止图片加载失败）
const fallbackAvatar = "https://cube.elemecdn.com/9/15/4e8a6b7f7b0b7e7b7e7b7e7b7e7b7e7b.png"

// ====================== 辅助函数 ======================
const scrollToBottom = async () => {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

const hasImage = (msg) => !!msg.imageUrl || msg.type === "image"

const getImageSrc = (msg) => msg.imageUrl || (msg.type === "image" ? msg.content : null)

// 判断是否应该使用 Markdown 渲染（仅 AI 且已完成流式输出的消息）
const shouldRenderMarkdown = (msg) => {
  return msg.role === "assistant" && !msg.streaming && msg.content && msg.content.trim()
}

// ====================== 核心修复：renderMarkdown 函数 ======================
// 修复标题（###）无法渲染的问题，同时处理转义和行首空格
const renderMarkdown = (content) => {
  if (!content) return ""

  // 1. 反转义常见的 # 转义形式（如后端返回的 &#35; 或 \#）
  let processed = content
    .replace(/&#35;/g, '#')
    .replace(/\\u0023/g, '#')
    .replace(/\\#/g, '#')

  // 2. 移除标题行前面的空格（只针对行首以 ### 开头的情况）
  //    这能解决因 AI 返回内容中标题前有空格导致无法识别的问题
  processed = processed.replace(/^[ \t]+(?=###)/gm, '')

  try {
    const html = md.render(processed)
    return html
  } catch (err) {
    console.error("Markdown 渲染失败", err)
    return escapeHtml(content).replace(/\n/g, "<br>")
  }
}

// 格式化纯文本（转义 HTML 并保留换行）
const formatPlainText = (text) => {
  if (!text) return ""
  return escapeHtml(text).replace(/\n/g, "<br>")
}

// 简单的 HTML 转义
const escapeHtml = (str) => {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

// ====================== 加载历史 ======================
const loadHistory = async () => {
  if (!conversationId.value) {
    ElMessage.warning("请输入会话ID")
    return
  }
  loading.value = true
  try {
    const res = await getAgentHistory(conversationId.value)
    if (res.data?.code === 200) {
      messages.value = (res.data.data.history || []).map((m) => ({
        role: m.role,
        content: m.content,
        type: m.metadataJson?.type || "text",
        imageUrl: m.metadataJson?.imageUrl || null,
        created_time: m.createdTime || m.created_time,
        streaming: false, // 历史消息无流式状态
      }))
      await scrollToBottom()
    }
  } catch (err) {
    ElMessage.error("加载历史失败")
  } finally {
    loading.value = false
  }
}

// ====================== 发送消息 ======================
const sendMessage = async () => {
  if ((!inputMessage.value.trim() && !selectedImageFile.value) || loading.value) return

  const hasText = inputMessage.value.trim().length > 0
  const hasImg = !!selectedImageFile.value

  const messageType = hasImg && hasText ? "mixed" : hasImg ? "image" : "text"

  messages.value.push({
    role: "user",
    content: hasText ? inputMessage.value.trim() : "",
    imageUrl: hasImg ? selectedImageDataUrl.value : null,
    type: messageType,
    created_time: new Date(),
  })

  await scrollToBottom()

  const tempText = inputMessage.value.trim()
  const tempImage = selectedImageFile.value

  inputMessage.value = ""
  removeImage()

  loading.value = true

  const assistantMsg = {
    role: "assistant",
    content: "",
    type: "text",
    created_time: new Date(),
    streaming: true,
  }
  messages.value.push(assistantMsg)
  currentStreamingMsg.value = assistantMsg
  await scrollToBottom()

  try {
    const response = await chatWithAgentStream({
      conversation_id: conversationId.value,
      message: tempText,
      image: tempImage,
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder("utf-8")
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() || ""

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith("data: ")) continue

        let content = trimmed.substring(6).trim()
        if (content === "[DONE]") continue

        assistantMsg.content += content
        await nextTick()
        await scrollToBottom()
      }
    }

    assistantMsg.streaming = false
    await scrollToBottom()
  } catch (err) {
    console.error("[发送失败]", err)
    ElMessage.error("流式对话失败：" + (err.message || "网络错误"))
    // 移除失败的 AI 消息
    if (messages.value.length > 0 && messages.value[messages.value.length - 1] === assistantMsg) {
      messages.value.pop()
    }
  } finally {
    loading.value = false
    currentStreamingMsg.value = null
    await scrollToBottom()
  }
}

// ====================== 图片处理 ======================
const handleImageSelect = (file) => {
  selectedImageFile.value = file.raw
  const reader = new FileReader()
  reader.onload = (e) => {
    previewImage.value = e.target.result
    selectedImageDataUrl.value = e.target.result
  }
  reader.readAsDataURL(file.raw)
  return false
}

const removeImage = () => {
  previewImage.value = null
  selectedImageFile.value = null
  selectedImageDataUrl.value = null
}

const previewImageFull = (src) => window.open(src, "_blank")

const formatTime = (time) => {
  if (!time) return ""
  return new Date(time).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

// ====================== 清空会话 ======================
const clearConversation = async () => {
  if (!conversationId.value) return
  try {
    await deleteAgentConversation(conversationId.value)
    messages.value = []
    ElMessage.success("会话已清空")
  } catch (err) {
    ElMessage.error("清空失败")
  }
}

// 录音占位（避免 warning）
const startRecording = () => console.log("录音开始（占位）")
const stopRecording = () => console.log("录音结束（占位）")
</script>

<style scoped>
.agent-chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;
  font-family: "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.chat-header {
  height: 72px;
  background: #fff;
  border-bottom: 1px solid #eee;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.header-info h3 {
  margin: 0;
  font-size: 19px;
  font-weight: 600;
}
.status {
  margin: 4px 0 0;
  font-size: 13px;
  color: #67c23a;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px 28px;
  background: linear-gradient(to bottom, #f8f9fa, #f0f2f5);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message {
  display: flex;
  gap: 14px;
  max-width: 78%;
  align-items: flex-start;
}
.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

/* 头像容器 - 防止头像被压缩 */
.message-avatar-wrapper {
  flex-shrink: 0;
  width: 42px;
  height: 42px;
}
.message-avatar {
  width: 42px !important;
  height: 42px !important;
  flex-shrink: 0;
  object-fit: cover;
}

.message-bubble {
  max-width: 100%;
  display: flex;
  flex-direction: column;
}

.bubble-text {
  background: #fff;
  padding: 13px 18px;
  border-radius: 18px;
  border-bottom-left-radius: 6px;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.09);
  line-height: 1.58;
  font-size: 15.2px;
  word-break: break-word;
  overflow-x: auto;
}
.message.user .bubble-text {
  background: #409eff;
  color: white;
  border-bottom-right-radius: 6px;
  border-bottom-left-radius: 18px;
}

/* Markdown 渲染样式覆盖 */
.bubble-text.markdown-body {
  padding: 12px 18px;
  background: #fff;
}
.message.user .bubble-text.markdown-body {
  background: #409eff;
  color: white;
}

/* 新增：确保 Markdown 标题和列表正常显示 */
.bubble-text :deep(h1),
.bubble-text :deep(h2),
.bubble-text :deep(h3),
.bubble-text :deep(h4),
.bubble-text :deep(h5),
.bubble-text :deep(h6) {
  font-weight: 600;
  margin: 0.8em 0 0.4em;
  line-height: 1.3;
  color: inherit;
}
.bubble-text :deep(h1) { font-size: 1.8em; }
.bubble-text :deep(h2) { font-size: 1.5em; }
.bubble-text :deep(h3) { font-size: 1.3em; }
.bubble-text :deep(h4) { font-size: 1.2em; }
.bubble-text :deep(h5) { font-size: 1.1em; }
.bubble-text :deep(h6) { font-size: 1em; }

.bubble-text :deep(ul),
.bubble-text :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}
.bubble-text :deep(li) {
  margin: 0.2em 0;
}

/* 确保加粗文本生效 */
.bubble-text :deep(strong),
.bubble-text :deep(b) {
  font-weight: 700;
}

/* 针对 Markdown 内容的代码块样式 */
.bubble-text :deep(pre) {
  background: #2d2d2d;
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  margin: 12px 0;
}
.bubble-text :deep(code) {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}
.bubble-text :deep(p) {
  margin: 0 0 8px 0;
}
.bubble-text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble-text :deep(a) {
  color: #409eff;
  text-decoration: none;
}
.message.user .bubble-text :deep(a) {
  color: #fff;
  text-decoration: underline;
}
.bubble-text :deep(blockquote) {
  border-left: 4px solid #409eff;
  margin: 8px 0;
  padding-left: 16px;
  color: #666;
}
.message.user .bubble-text :deep(blockquote) {
  border-left-color: rgba(255,255,255,0.5);
  color: rgba(255,255,255,0.9);
}
.bubble-text :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.bubble-text :deep(th),
.bubble-text :deep(td) {
  border: 1px solid #ddd;
  padding: 6px 12px;
  text-align: left;
}
.message.user .bubble-text :deep(th),
.message.user .bubble-text :deep(td) {
  border-color: rgba(255,255,255,0.3);
}

.bubble-image img {
  max-width: 300px;
  max-height: 380px;
  border-radius: 14px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
  background: #f8f9fa;
  cursor: pointer;
  transition: transform 0.2s;
}
.bubble-image img:hover {
  transform: scale(1.02);
}

.has-image .bubble-image {
  margin-bottom: 10px;
}

.message-time {
  font-size: 12.5px;
  color: #a8a8a8;
  margin-top: 6px;
  padding-left: 8px;
  opacity: 0.9;
}

.loading-bubble {
  background: white;
  padding: 13px 20px;
  border-radius: 18px;
  width: fit-content;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.08);
}
.typing {
  color: #909399;
  font-style: italic;
  background: linear-gradient(90deg, #909399 25%, #c0c4cc 50%, #909399 75%);
  background-size: 200% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: shine 1.8s linear infinite;
}
@keyframes shine {
  to { background-position: -200% 0; }
}

.chat-footer {
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #eee;
  box-shadow: 0 -4px 15px rgba(0, 0, 0, 0.06);
}

.image-preview-bar {
  margin-bottom: 12px;
}
.preview-item {
  position: relative;
  display: inline-block;
}
.preview-item img {
  max-height: 92px;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}
.remove-icon {
  position: absolute;
  top: -8px;
  right: -8px;
  color: #f56c6c;
  cursor: pointer;
  background: white;
  border-radius: 50%;
  padding: 2px;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}
.tools {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}
.input-container :deep(.el-textarea) {
  flex: 1;
}
.input-container :deep(.el-textarea__inner) {
  resize: none;
  font-family: inherit;
}

.cursor {
  display: inline-block;
  width: 3px;
  background: #409eff;
  animation: blink 0.8s step-end infinite;
  margin-left: 2px;
}
@keyframes blink {
  50% { opacity: 0; }
}
</style>