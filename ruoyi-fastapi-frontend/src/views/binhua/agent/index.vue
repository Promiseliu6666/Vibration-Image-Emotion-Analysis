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

        <div class="message-bubble" :class="{ 'has-image': hasImage(msg), 'has-audio': hasAudio(msg) }">
          <!-- 图片 -->
          <div v-if="getImageSrc(msg)" class="bubble-image">
            <img
              :src="getImageSrc(msg)"
              alt="图片"
              @click="previewImageFull(getImageSrc(msg))"
            />
          </div>

          <!-- 音频：只显示用户语音，AI 语音永久隐藏 -->
          <div v-if="getAudioSrc(msg) && msg.role === 'user'" class="bubble-audio">
            <audio :src="getAudioSrc(msg)" controls preload="metadata"></audio>
          </div>

          <!-- 文字内容：图片+文字同时显示 -->
          <div
            v-if="shouldShowText(msg)"
            class="bubble-text"
            :class="{ 'markdown-body': shouldRenderMarkdown(msg) }"
          >
            <div v-if="shouldRenderMarkdown(msg)" v-html="renderMarkdown(msg.content)"></div>
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

      <!-- 音频预览 -->
      <div v-if="previewAudio" class="audio-preview-bar">
        <div class="preview-item">
          <audio :src="previewAudio" controls></audio>
          <el-icon class="remove-icon" @click="removeAudio"><Close /></el-icon>
        </div>
      </div>

      <div class="input-container">
        <div class="tools">
          <!-- 语音长按录音按钮 -->
          <el-button
            circle
            :class="{ recording: isRecording }"
            @mousedown="startRecording"
            @mouseup="stopRecording"
            @mouseleave="stopRecording"
            :disabled="loading"
          >
            <el-icon><Microphone /></el-icon>
          </el-button>
          <!-- 图片上传按钮 -->
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
          placeholder="输入消息，按 Enter 发送...（支持语音+图片+文字）"
          @keyup.enter="sendMessage"
          :disabled="loading"
          clearable
          type="textarea"
          :rows="1"
          autosize
        />

        <el-button
          type="primary"
          :disabled="loading || (!inputMessage.trim() && !selectedImageFile && !selectedAudioFile)"
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
import "highlight.js/styles/github-dark.css"

import {
  chatWithAgentStream,
  getAgentHistory,
  deleteAgentConversation
} from "@/api/binhua/agent"

// 初始化 Markdown 渲染器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
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

// 音频相关
const previewAudio = ref(null)
const selectedAudioFile = ref(null)
const selectedAudioDataUrl = ref(null)
const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])

const loading = ref(false)
const currentStreamingMsg = ref(null)

const chatBodyRef = ref(null)

const userAvatar = "https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55b.png"
const aiAvatar = "https://fastly.jsdelivr.net/npm/@intergrav/devins-badges@3/assets/cozy-minimal/available/github_vector.svg"

// ====================== 辅助函数 ======================
const scrollToBottom = async () => {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

const hasImage = (msg) => !!msg.imageUrl || msg.type === "image"
const hasAudio = (msg) => !!msg.audioUrl && msg.role === "user"

const getImageSrc = (msg) => msg.imageUrl || (msg.type === "image" ? msg.content : null)
const getAudioSrc = (msg) => msg.audioUrl || null

// 核心：图片+文字 同时显示
const shouldShowText = (msg) => {
  if (!msg.content || !msg.content.trim()) return false
  return true
}

const shouldRenderMarkdown = (msg) => {
  return msg.role === "assistant" &&
         !msg.streaming &&
         msg.content &&
         msg.content.trim().length > 10
}

// 强化版内容预处理
const preprocessContent = (text) => {
  if (!text || typeof text !== 'string') return ""
  let processed = text
  processed = processed
    .replace(/^(好的[，,]?|嗯[，,]?|OK[，,]?|当然可以[，,]?|没问题[，,]?|了解了[，,]?|收到[，,]?)\s*/i, '')
    .replace(/\s*(谢谢|感谢您的提问|有帮助请点个赞|结束|完|。|～|！|!!|!!!)$/, '')
  processed = processed
    .replace(/[-—━─]{1,4}\s*###/g, '###')
    .replace(/[-—━─]{1,4}\s*(\*\*[^ ]+[^ ]*\*\*)/g, '### $1')
    .replace(/[-—━─]{1,4}\s*(详细观察|分析\/建议|总结|核心答案|图片主要内容|详细描述|建议)/gi, '### $1')
    .replace(/^[-—━─]{3,}\s*/gm, '---\n')
  processed = processed
    .replace(/^\s*[-—━─]\s*(关键元素|关键点|子项|注意事项)/gm, '- $1')
    .replace(/^\s*[-—━─]\s*/gm, '- ')
    .replace(/^\s*\*\s*/gm, '- ')
  processed = processed
    .replace(/python\s*#示例代码[：:]\s*/gi, '```python\n# 示例代码\n')
    .replace(/class([A-Za-z0-9_]+)/g, 'class $1')
    .replace(/def([a-zA-Z_]+)/g, 'def $1')
    .replace(/__init__\s*\(/g, '__init__(')
    .replace(/self\./g, 'self.')
    .replace(/([a-zA-Z0-9_]+)\s*$/m, '$1\n```')
  processed = processed
    .replace(/[-—━─]{4,}/g, '---')
    .replace(/\n{4,}/g, '\n\n')
    .replace(/([\s\S]*?)<\/think>/g, '<div class="think-block"><strong>思考过程</strong><br>$1</div>')
  return processed.trim()
}

const renderMarkdown = (content) => {
  if (!content) return ""
  const processed = preprocessContent(content)
  try {
    return md.render(processed)
  } catch (err) {
    console.error("Markdown 渲染失败", err, content)
    return escapeHtml(content).replace(/\n/g, "<br>")
  }
}

const formatPlainText = (text) => {
  if (!text) return ""
  return escapeHtml(text).replace(/\n/g, "<br>")
}

const escapeHtml = (str) => {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
}

// ====================== 录音功能 ======================
const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder.value = new MediaRecorder(stream, { mimeType: "audio/webm" })

    audioChunks.value = []
    mediaRecorder.value.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.value.push(e.data)
    }

    mediaRecorder.value.onstop = () => {
      const audioBlob = new Blob(audioChunks.value, { type: "audio/webm" })
      const reader = new FileReader()
      reader.onload = (e) => {
        previewAudio.value = e.target.result
        selectedAudioDataUrl.value = e.target.result
        selectedAudioFile.value = audioBlob
      }
      reader.readAsDataURL(audioBlob)
    }

    mediaRecorder.value.start()
    isRecording.value = true
    ElMessage.info("正在录音（松开发送）")
  } catch (err) {
    ElMessage.error("无法访问麦克风：" + err.message)
  }
}

const stopRecording = () => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop()
    mediaRecorder.value.stream.getTracks().forEach(track => track.stop())
    isRecording.value = false
  }
}

const removeAudio = () => {
  previewAudio.value = null
  selectedAudioFile.value = null
  selectedAudioDataUrl.value = null
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

// ====================== 发送消息 ======================
const sendMessage = async () => {
  const hasText = inputMessage.value.trim().length > 0
  const hasImg = !!selectedImageFile.value
  const hasAud = !!selectedAudioFile.value

  if (!hasText && !hasImg && !hasAud) return

  const messageType = hasImg && hasAud ? "audio_image" :
                      hasAud ? "audio" :
                      hasImg ? "image" : "text"

  // 添加用户消息
  messages.value.push({
    role: "user",
    content: hasText ? inputMessage.value.trim() : (hasAud ? "[语音消息]" : ""),
    imageUrl: hasImg ? selectedImageDataUrl.value : null,
    audioUrl: hasAud ? selectedAudioDataUrl.value : null,
    type: messageType,
    created_time: new Date(),
  })

  await scrollToBottom()

  // 保存发送内容
  const tempText = inputMessage.value.trim()
  const tempImage = selectedImageFile.value
  const tempAudio = selectedAudioFile.value

  // 清空输入
  inputMessage.value = ""
  removeImage()
  removeAudio()

  loading.value = true

  // AI 消息：永远不携带音频，只显示文字
  const assistantMsg = {
    role: "assistant",
    content: "",
    audioUrl: null,
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
      audio: tempAudio
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

        // AI 语音数据直接忽略，不渲染
        if (content.startsWith("[AUDIO]")) {
          continue
        } else if (content.startsWith("[ERROR]")) {
          ElMessage.error(content.substring(7))
        } else if (!content.startsWith("[USAGE]")) {
          assistantMsg.content += content
        }

        await nextTick()
        await scrollToBottom()
      }
    }

    assistantMsg.streaming = false
    await scrollToBottom()

  } catch (err) {
    console.error("[发送失败]", err)
    ElMessage.error("流式对话失败：" + (err.message || "网络错误"))

    if (messages.value.length > 0 && messages.value[messages.value.length - 1] === assistantMsg) {
      messages.value.pop()
    }
  } finally {
    loading.value = false
    currentStreamingMsg.value = null
    await scrollToBottom()
  }
}

// ====================== 历史 & 清空 ======================
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
        audioUrl: m.metadataJson?.audioUrl || null,
        created_time: m.createdTime || m.created_time,
        streaming: false,
      }))
      await scrollToBottom()
    }
  } catch (err) {
    ElMessage.error("加载历史失败")
  } finally {
    loading.value = false
  }
}

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

const formatTime = (time) => {
  if (!time) return ""
  return new Date(time).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}
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

/* ========== 优化：聊天框内图片大小，防止遮挡 ========== */
.bubble-image {
  margin-bottom: 8px;
  max-width: 240px;
  width: fit-content;
}
.bubble-image img {
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  cursor: pointer;
}

.bubble-audio {
  margin: 8px 0 12px 0;
}
.bubble-audio audio {
  width: 280px;
  max-width: 100%;
  border-radius: 8px;
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
}
.message.user .bubble-text {
  background: #409eff;
  color: white;
  border-bottom-right-radius: 6px;
  border-bottom-left-radius: 18px;
  margin-top: 8px;
}

.bubble-text.markdown-body {
  padding: 12px 18px;
  background: #fff;
}
.message.user .bubble-text.markdown-body {
  background: #409eff;
  color: white;
}

.bubble-text :deep(h1), .bubble-text :deep(h2), .bubble-text :deep(h3),
.bubble-text :deep(h4), .bubble-text :deep(h5), .bubble-text :deep(h6) {
  font-weight: 600;
  margin: 0.8em 0 0.4em;
}
.bubble-text :deep(ul), .bubble-text :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}
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
.bubble-text :deep(a) {
  color: #409eff;
}
.message.user .bubble-text :deep(a) {
  color: #fff;
}

.message-time {
  font-size: 12.5px;
  color: #a8a8a8;
  margin-top: 6px;
  padding-left: 8px;
}

.loading-bubble {
  background: white;
  padding: 13px 20px;
  border-radius: 18px;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.08);
}
.typing {
  color: #909399;
  font-style: italic;
}

.chat-footer {
  padding: 16px 24px;
  background: #fff;
  border-top: 1px solid #eee;
}

/* ========== 优化：底部预览图片大小，不遮挡输入框 ========== */
.image-preview-bar, .audio-preview-bar {
  margin-bottom: 8px;
  padding: 6px 10px;
  background: #f7f8fa;
  border-radius: 8px;
}
.preview-item {
  position: relative;
  display: inline-block;
}
.preview-item img {
  max-height: 60px;
  border-radius: 6px;
}
.remove-icon {
  position: absolute;
  top: -6px;
  right: -6px;
  color: #f56c6c;
  cursor: pointer;
  background: #fff;
  border-radius: 50%;
  padding: 1px;
  font-size: 14px;
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

.cursor {
  display: inline-block;
  width: 3px;
  background: #409eff;
  animation: blink 0.8s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }

.recording {
  background-color: #f56c6c !important;
  color: white !important;
  animation: pulse 1.2s infinite;
}
@keyframes pulse {
  0%,100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}
</style>