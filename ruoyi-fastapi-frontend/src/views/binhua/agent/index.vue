<template>
  <div class="agent-chat-page">
    <aside class="conversation-panel">
      <div class="panel-header">
        <div class="panel-title">Agent 会话</div>
        <el-button :icon="Plus" circle type="primary" @click="createNewConversation" />
      </div>

      <el-scrollbar class="conversation-list">
        <div v-if="conversations.length === 0" class="list-empty">
          暂无会话
        </div>

        <div
          v-for="item in conversations"
          :key="item.id"
          class="conversation-item"
          :class="{ active: item.id === conversationId }"
          @click="activateConversation(item.id)"
        >
          <div class="item-main">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-preview">{{ item.lastMessage || '暂无消息' }}</div>
            <div class="item-meta">
              <span>{{ formatTime(item.lastActiveTime) }}</span>
              <span>{{ item.messageCount }} 条</span>
            </div>
          </div>
          <el-button
            :icon="Delete"
            circle
            text
            size="small"
            @click.stop="deleteConversation(item.id)"
          />
        </div>
      </el-scrollbar>
    </aside>

    <section class="chat-panel">
      <header class="chat-header">
        <div class="header-left">
          <el-avatar :src="aiAvatarSrc" size="40" class="agent-avatar agent-avatar-ai">
            <el-icon><Service /></el-icon>
          </el-avatar>
          <div class="header-info">
            <div class="header-title">AI Agent 助手</div>
            <div class="header-subtitle">{{ conversationId || '--' }}</div>
          </div>
        </div>
        <div class="header-actions">
          <el-button :icon="Plus" type="primary" plain @click="createNewConversation">新建对话</el-button>
          <el-button :icon="Delete" type="danger" plain @click="deleteConversation(conversationId)" :disabled="!conversationId">
            删除当前
          </el-button>
        </div>
      </header>

      <div class="chat-body" ref="chatBodyRef">
        <div v-if="loadingHistory" class="center-state">
          <el-icon class="is-loading"><ChatDotRound /></el-icon>
          <span>加载历史中...</span>
        </div>

        <template v-else>
          <div v-if="messages.length === 0" class="center-state">
            <el-icon><ChatDotRound /></el-icon>
            <span>开始一个新对话</span>
          </div>

          <div v-for="(msg, idx) in messages" :key="idx" class="message" :class="msg.role">
            <el-avatar
              :src="getMessageAvatar(msg.role)"
              class="message-avatar agent-avatar"
              :class="msg.role === 'user' ? 'agent-avatar-user' : 'agent-avatar-ai'"
            >
              <el-icon>
                <UserFilled v-if="msg.role === 'user'" />
                <Service v-else />
              </el-icon>
            </el-avatar>
            <div class="message-bubble">
              <div v-if="msg.imageUrl" class="bubble-image">
                <img :src="msg.imageUrl" alt="image" @click="previewImage(msg.imageUrl)" />
              </div>
              <div v-if="msg.audioUrl && msg.role === 'user'" class="bubble-audio">
                <audio :src="msg.audioUrl" controls preload="metadata"></audio>
              </div>

              <div
                v-if="msg.content"
                class="bubble-text"
                :class="{ markdown: msg.role === 'assistant' }"
              >
                <div v-if="msg.role === 'assistant'" v-html="renderMessageContent(msg)"></div>
                <div v-else v-html="formatPlainText(msg.content)"></div>
                <span v-if="msg.streaming" class="cursor"></span>
              </div>
              <div v-if="msg.streaming && !msg.content" class="thinking-indicator">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
              </div>
              <div class="bubble-time">{{ formatTime(msg.created_time) }}</div>
            </div>
          </div>
        </template>
      </div>

      <footer class="chat-footer">
        <div v-if="previewImageDataUrl" class="preview-row">
          <div class="preview-item">
            <img :src="previewImageDataUrl" alt="preview" />
            <el-button :icon="Close" circle text @click="removeImage" />
          </div>
        </div>

        <div v-if="previewAudioDataUrl" class="preview-row">
          <div class="preview-item">
            <audio :src="previewAudioDataUrl" controls></audio>
            <el-button :icon="Close" circle text @click="removeAudio" />
          </div>
        </div>

        <div class="quick-actions">
          <el-button
            v-for="action in quickActions"
            :key="action.key"
            size="small"
            type="info"
            plain
            :disabled="sending"
            @click="sendQuickAction(action)"
          >
            {{ action.label }}
          </el-button>
        </div>

        <div class="input-row">
          <div class="tool-buttons">
            <el-button
              circle
              :class="{ recording: isRecording }"
              :disabled="sending"
              @mousedown="startRecording"
              @mouseup="stopRecording"
              @mouseleave="stopRecording"
              @touchstart.prevent="startRecording"
              @touchend.prevent="stopRecording"
            >
              <el-icon><Microphone /></el-icon>
            </el-button>

            <el-upload
              action="#"
              :show-file-list="false"
              :auto-upload="false"
              :disabled="sending"
              @change="handleImageSelect"
            >
              <el-button circle :disabled="sending">
                <el-icon><Picture /></el-icon>
              </el-button>
            </el-upload>
          </div>

          <el-input
            v-model="inputMessage"
            type="textarea"
            :rows="1"
            autosize
            clearable
            :disabled="sending"
            placeholder="输入消息，Enter 发送，Shift + Enter 换行"
            @keydown.enter.exact.prevent="sendMessage"
          />

          <el-button
            type="primary"
            :loading="sending"
            :disabled="sending || (!inputMessage.trim() && !selectedImageFile && !selectedAudioFile)"
            @click="sendMessage"
          >
            发送
          </el-button>
        </div>
      </footer>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Close, Delete, Microphone, Picture, Plus, Service, UserFilled } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'
import defaultUserAvatar from '@/assets/images/profile.png'
import defaultAiAvatar from '@/assets/logo/logo.png'

import useUserStore from '@/store/modules/user'
import {
  chatWithAgentStream,
  deleteAgentConversation,
  getAgentConversations,
  getAgentHistory,
  getAgentStats
} from '@/api/binhua/agent'

const STORAGE_KEY = 'agent:lastConversationId'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str, lang) {
    const langClass = lang ? ` class="language-${lang}"` : ''
    if (lang && hljs.getLanguage(lang)) {
      try {
        const highlighted = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
        return `<pre class="hljs"${langClass}><code>${highlighted}</code></pre>`
      } catch (e) {}
    }
    return `<pre class="hljs"${langClass}><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
})

const userStore = useUserStore()
const currentUserId = computed(() => {
  const id = userStore?.id
  if (id === undefined || id === null) return 'user_001'
  const text = `${id}`.trim()
  return text || 'user_001'
})

const conversationId = ref('')
const conversations = ref([])
const messages = ref([])
const inputMessage = ref('')

const loadingHistory = ref(false)
const sending = ref(false)

const previewImageDataUrl = ref(null)
const selectedImageFile = ref(null)

const previewAudioDataUrl = ref(null)
const selectedAudioFile = ref(null)

const quickActions = [
  { key: 'stats_overview', label: '📊 近7天总体态势', message: '请根据数据概览分析近7天总体态势，关键指标变化和趋势。' },
  { key: 'top3_risk', label: '⚠️ 高风险人员TOP3', message: '请根据数据分析高风险人员TOP3的情况，说明主要原因和建议。' },
  { key: 'wow_change', label: '📈 周环比变化', message: '请根据周环比数据分析关键指标的变化趋势，评估整体安全态势是改善还是恶化。' },
  { key: 'full_report', label: '📋 综合分析报告', message: '请生成一份完整的近7天安全态势综合分析报告，包括总体态势、高风险人员、周环比变化和建议措施。' },
]

async function sendQuickAction(action) {
  if (sending.value) return
  inputMessage.value = action.message
  await sendMessage()
}

const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])

const chatBodyRef = ref(null)

const resolveAvatarUrl = (avatar) => {
  const raw = (avatar || '').toString().trim()
  if (!raw) return ''
  if (/^(https?:)?\/\//.test(raw) || raw.startsWith('data:') || raw.startsWith('blob:')) return raw
  if (raw.startsWith('/src/') || raw.startsWith('/assets/')) return raw

  const apiBase = (import.meta.env.VITE_APP_BASE_API || '').trim()
  if (apiBase && raw.startsWith(`${apiBase}/`)) return raw
  if (raw.startsWith('/')) return `${apiBase}${raw}`
  return raw
}

const userAvatarSrc = computed(() => resolveAvatarUrl(userStore?.avatar) || defaultUserAvatar)
const aiAvatarSrc = defaultAiAvatar
const getMessageAvatar = (role) => (role === 'user' ? userAvatarSrc.value : aiAvatarSrc)

const createConversationId = () => `conv_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

const escapeHtml = (text = '') =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const formatPlainText = (text = '') => escapeHtml(text).replace(/\n/g, '<br>')

const renderMarkdown = (text = '') => {
  try {
    return md.render(text)
  } catch (e) {
    return formatPlainText(text)
  }
}

const shouldRenderMarkdown = (msg) => msg.role === 'assistant'

const renderMessageContent = (msg) => {
  if (msg.role !== 'assistant') return formatPlainText(msg.content)
  // 流式输出时用简单渲染减少闪烁，完成后用完整 markdown
  try {
    return md.render(msg.content)
  } catch (e) {
    return formatPlainText(msg.content)
  }
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

const saveLastConversationId = (id) => {
  if (!id) return
  localStorage.setItem(STORAGE_KEY, id)
}

const readLastConversationId = () => localStorage.getItem(STORAGE_KEY) || ''

const normalizeConversation = (item = {}) => {
  const id = item.conversationId || item.conversation_id || ''
  return {
    id,
    title: item.title || `会话 ${id ? id.slice(-6) : ''}`,
    lastMessage: item.lastMessage || item.last_message || '',
    messageCount: item.messageCount ?? item.message_count ?? 0,
    createdTime: item.createdTime || item.created_time || '',
    lastActiveTime: item.lastActiveTime || item.last_active_time || item.createdTime || item.created_time || '',
    localOnly: !!item.localOnly
  }
}

const upsertConversation = (partial) => {
  const item = normalizeConversation(partial)
  if (!item.id) return
  const idx = conversations.value.findIndex((v) => v.id === item.id)
  if (idx === -1) {
    conversations.value.unshift(item)
  } else {
    conversations.value[idx] = { ...conversations.value[idx], ...item }
  }
  conversations.value.sort((a, b) => new Date(b.lastActiveTime || 0).getTime() - new Date(a.lastActiveTime || 0).getTime())
}

const removeConversationFromList = (id) => {
  conversations.value = conversations.value.filter((v) => v.id !== id)
}

const deriveTitleFromMessages = () => {
  const firstUser = messages.value.find((m) => m.role === 'user' && (m.content || '').trim())
  if (!firstUser) return ''
  const text = firstUser.content.trim().replace(/\s+/g, ' ')
  return text.length <= 28 ? text : `${text.slice(0, 28)}...`
}

const getLastMessagePreview = () => {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    const content = (messages.value[i].content || '').trim()
    if (content) return content.length <= 80 ? content : `${content.slice(0, 80)}...`
  }
  return ''
}

const refreshConversationList = async () => {
  const res = await getAgentConversations({ limit: 50 })
  const serverList = (res.data?.conversations || []).map(normalizeConversation)
  const map = new Map(serverList.map((item) => [item.id, item]))

  if (conversationId.value && !map.has(conversationId.value)) {
    map.set(conversationId.value, normalizeConversation({
      conversation_id: conversationId.value,
      title: deriveTitleFromMessages() || `会话 ${conversationId.value.slice(-6)}`,
      last_message: getLastMessagePreview(),
      message_count: messages.value.length,
      last_active_time: new Date().toISOString(),
      localOnly: true
    }))
  }

  conversations.value = Array.from(map.values()).sort(
    (a, b) => new Date(b.lastActiveTime || 0).getTime() - new Date(a.lastActiveTime || 0).getTime()
  )
}

const mapHistoryItem = (item) => {
  const metadata = item.metadataJson || item.metadata_json || {}
  return {
    role: item.role || 'assistant',
    content: item.content || '',
    type: metadata.type || 'text',
    imageUrl: metadata.imageUrl || null,
    audioUrl: metadata.audioUrl || null,
    created_time: item.createdTime || item.created_time || new Date().toISOString(),
    streaming: false
  }
}

const loadHistory = async (targetConversationId = conversationId.value) => {
  if (!targetConversationId) return
  loadingHistory.value = true
  try {
    const res = await getAgentHistory(targetConversationId, 100)
    const history = (res.data?.history || []).map(mapHistoryItem)
    conversationId.value = targetConversationId
    saveLastConversationId(targetConversationId)
    messages.value = history
    await scrollToBottom()

    upsertConversation({
      conversation_id: targetConversationId,
      title: deriveTitleFromMessages() || `会话 ${targetConversationId.slice(-6)}`,
      last_message: getLastMessagePreview(),
      message_count: history.length,
      last_active_time: history[history.length - 1]?.created_time || new Date().toISOString()
    })
  } catch (e) {
    ElMessage.error('加载历史失败')
  } finally {
    loadingHistory.value = false
  }
}

const activateConversation = async (id) => {
  if (!id || sending.value) return
  if (id === conversationId.value && messages.value.length > 0) return
  await loadHistory(id)
}

const createNewConversation = () => {
  if (sending.value) {
    ElMessage.warning('请等待当前回复完成')
    return
  }

  const id = createConversationId()
  conversationId.value = id
  saveLastConversationId(id)
  messages.value = []
  inputMessage.value = ''
  removeImage()
  removeAudio()

  upsertConversation({
    conversation_id: id,
    title: `会话 ${id.slice(-6)}`,
    last_message: '',
    message_count: 0,
    last_active_time: new Date().toISOString(),
    localOnly: true
  })
}

const deleteConversation = async (id) => {
  if (!id) return
  try {
    await ElMessageBox.confirm('确认删除这个会话？', '提示', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  try {
    await deleteAgentConversation(id)
    removeConversationFromList(id)
    ElMessage.success('会话已删除')

    if (conversationId.value === id) {
      const next = conversations.value[0]
      if (next?.id) {
        await loadHistory(next.id)
      } else {
        createNewConversation()
      }
    }
  } catch (e) {
    ElMessage.error('删除会话失败')
  }
}

const previewImage = (src) => window.open(src, '_blank')

const handleImageSelect = (file) => {
  if (!file?.raw) return false
  selectedImageFile.value = file.raw
  const reader = new FileReader()
  reader.onload = (e) => {
    previewImageDataUrl.value = e.target.result
  }
  reader.readAsDataURL(file.raw)
  return false
}

const removeImage = () => {
  selectedImageFile.value = null
  previewImageDataUrl.value = null
}

const removeAudio = () => {
  selectedAudioFile.value = null
  previewAudioDataUrl.value = null
}

const startRecording = async () => {
  if (isRecording.value) return
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder.value = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    audioChunks.value = []

    mediaRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) audioChunks.value.push(event.data)
    }

    mediaRecorder.value.onstop = () => {
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' })
      selectedAudioFile.value = audioBlob
      const reader = new FileReader()
      reader.onload = (e) => {
        previewAudioDataUrl.value = e.target.result
      }
      reader.readAsDataURL(audioBlob)
    }

    mediaRecorder.value.start()
    isRecording.value = true
    ElMessage.info('正在录音，松开按钮停止')
  } catch (e) {
    ElMessage.error(`无法录音: ${e.message}`)
  }
}

const stopRecording = () => {
  if (!mediaRecorder.value || !isRecording.value) return
  mediaRecorder.value.stop()
  mediaRecorder.value.stream.getTracks().forEach((track) => track.stop())
  isRecording.value = false
}

const parseSseDataBlock = (block) => {
  const lines = block.split(/\r?\n/)
  const dataLines = lines
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
  if (!dataLines.length) return null
  const text = dataLines.join('\n')
  if (!text || text === '[DONE]') return null
  return text
}

const handleStreamPayload = (payloadText, assistantMsg) => {
  let payload = null
  try {
    payload = JSON.parse(payloadText)
  } catch {
    payload = null
  }

  if (payload && typeof payload === 'object') {
    const type = payload.type
    if (type === 'meta') {
      if (payload.conversation_id) {
        conversationId.value = payload.conversation_id
        saveLastConversationId(payload.conversation_id)
      }
      return
    }
    if (type === 'content' || type === 'delta') {
      assistantMsg.content += payload.content || ''
      return
    }
    if (type === 'reasoning' || type === 'run_info' || type === 'metrics' || type === 'usage') {
      return
    }
    if (type === 'error') {
      throw new Error(payload.content || '生成失败')
    }
    return
  }

  if (payloadText.startsWith('[ERROR]')) {
    throw new Error(payloadText.slice(7).trim())
  }
  if (!payloadText.startsWith('[USAGE]') && !payloadText.startsWith('[AUDIO]')) {
    assistantMsg.content += payloadText
  }
}

const sendMessage = async () => {
  const hasText = inputMessage.value.trim().length > 0
  const hasImage = !!selectedImageFile.value
  const hasAudio = !!selectedAudioFile.value
  if (!hasText && !hasImage && !hasAudio) return
  if (sending.value) return

  if (!conversationId.value) {
    conversationId.value = createConversationId()
  }

  saveLastConversationId(conversationId.value)

  const userText = inputMessage.value.trim()
  const localUserMessage = {
    role: 'user',
    content: userText || (hasAudio ? '[语音消息]' : ''),
    imageUrl: hasImage ? previewImageDataUrl.value : null,
    audioUrl: hasAudio ? previewAudioDataUrl.value : null,
    type: hasImage && hasAudio ? 'audio_image' : hasImage ? 'image' : hasAudio ? 'audio' : 'text',
    created_time: new Date().toISOString(),
    streaming: false
  }
  messages.value.push(localUserMessage)

  const assistantMsg = {
    role: 'assistant',
    content: '',
    type: 'text',
    imageUrl: null,
    audioUrl: null,
    created_time: new Date().toISOString(),
    streaming: true
  }
  messages.value.push(assistantMsg)
  await scrollToBottom()

  const payloadText = userText
  const payloadImage = selectedImageFile.value
  const payloadAudio = selectedAudioFile.value

  inputMessage.value = ''
  removeImage()
  removeAudio()
  sending.value = true

  upsertConversation({
    conversation_id: conversationId.value,
    title: deriveTitleFromMessages() || `会话 ${conversationId.value.slice(-6)}`,
    last_message: payloadText || '[多模态消息]',
    message_count: messages.value.length,
    last_active_time: new Date().toISOString()
  })

  try {
    const response = await chatWithAgentStream({
      conversation_id: conversationId.value,
      user_id: currentUserId.value,
      message: payloadText,
      image: payloadImage,
      audio: payloadAudio
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let boundaryIndex = buffer.indexOf('\n\n')
      while (boundaryIndex !== -1) {
        const block = buffer.slice(0, boundaryIndex)
        buffer = buffer.slice(boundaryIndex + 2)
        const payload = parseSseDataBlock(block)
        if (payload) {
          handleStreamPayload(payload, assistantMsg)
          await scrollToBottom()
        }
        boundaryIndex = buffer.indexOf('\n\n')
      }
    }

    if (buffer.trim()) {
      const payload = parseSseDataBlock(buffer)
      if (payload) {
        handleStreamPayload(payload, assistantMsg)
      }
    }

    assistantMsg.streaming = false
    upsertConversation({
      conversation_id: conversationId.value,
      title: deriveTitleFromMessages() || `会话 ${conversationId.value.slice(-6)}`,
      last_message: assistantMsg.content || getLastMessagePreview(),
      message_count: messages.value.length,
      last_active_time: new Date().toISOString()
    })
    await refreshConversationList()
    await scrollToBottom()
  } catch (e) {
    assistantMsg.streaming = false
    assistantMsg.content = assistantMsg.content || `请求失败：${e.message || '网络异常'}`
    ElMessage.error(assistantMsg.content)
  } finally {
    sending.value = false
  }
}

const initializePage = async () => {
  try {
    await refreshConversationList()
  } catch (e) {
    conversations.value = []
  }

  const lastConversationId = readLastConversationId()
  const preferred = conversations.value.find((item) => item.id === lastConversationId)

  if (preferred?.id) {
    await loadHistory(preferred.id)
    return
  }

  if (conversations.value.length > 0) {
    await loadHistory(conversations.value[0].id)
    return
  }

  createNewConversation()
}

const formatTime = (time) => {
  if (!time) return '--'
  const dt = new Date(time)
  if (Number.isNaN(dt.getTime())) return '--'
  return dt.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

onMounted(() => {
  initializePage()
})
</script>

<style scoped>
.agent-chat-page {
  height: calc(100vh - 84px);
  min-height: 640px;
  display: flex;
  background: #f4f6f8;
  color: #1f2329;
}

.conversation-panel {
  width: 300px;
  border-right: 1px solid #e8edf3;
  background: #fff;
  display: flex;
  flex-direction: column;
}

.panel-header {
  height: 64px;
  padding: 0 14px;
  border-bottom: 1px solid #edf1f5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
}

.conversation-list {
  flex: 1;
  padding: 8px;
}

.list-empty {
  color: #8b95a5;
  font-size: 13px;
  text-align: center;
  margin-top: 24px;
}

.conversation-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 10px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
}

.conversation-item:hover {
  background: #f8fafc;
}

.conversation-item.active {
  background: #eef5ff;
  border-color: #cfe1ff;
}

.item-main {
  min-width: 0;
  flex: 1;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-preview {
  margin-top: 4px;
  color: #6f7b8a;
  font-size: 12px;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.item-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #9ba7b7;
  display: flex;
  justify-content: space-between;
}

.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  height: 64px;
  background: #fff;
  border-bottom: 1px solid #e8edf3;
  padding: 0 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.2;
}

.header-subtitle {
  font-size: 12px;
  color: #6f7b8a;
  line-height: 1.2;
  margin-top: 4px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: #f4f6f8;
}

.center-state {
  height: 100%;
  min-height: 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8793a4;
  gap: 10px;
}

.message {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  max-width: 82%;
}

.message.user {
  margin-left: auto;
  flex-direction: row-reverse;
}

.message-avatar {
  flex: 0 0 40px;
}

.agent-avatar {
  border: 1px solid #e5ebf2;
  background: #ffffff;
  color: #4f5d73;
}

.agent-avatar-ai {
  background: #f0f7ff;
  border-color: #cfe1ff;
}

.agent-avatar-user {
  background: #f6f8fb;
  border-color: #dfe6ee;
}

.message-bubble {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.bubble-image {
  max-width: 300px;
}

.bubble-image img {
  width: 100%;
  max-height: 240px;
  object-fit: contain;
  border-radius: 8px;
  cursor: pointer;
}

.bubble-audio {
  margin-bottom: 8px;
}

.bubble-text {
  background: #fff;
  border: 1px solid #e7ecf1;
  border-radius: 12px;
  padding: 12px 16px;
  line-height: 1.62;
  font-size: 14px;
  word-break: break-word;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.15s;
}
.bubble-text:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.07);
}

.message.user .bubble-text {
  background: linear-gradient(135deg, #2f88ff, #1a6fe8);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 2px 6px rgba(47, 136, 255, 0.25);
}
.message.user .bubble-text:hover {
  box-shadow: 0 3px 12px rgba(47, 136, 255, 0.32);
}

.bubble-text.markdown :deep(h1) {
  font-size: 1.32em;
  font-weight: 700;
  margin: 0.8em 0 0.4em;
  padding-bottom: 0.3em;
  border-bottom: 1px solid #e8ecf1;
  color: #1a2332;
}
.bubble-text.markdown :deep(h2) {
  font-size: 1.18em;
  font-weight: 700;
  margin: 0.7em 0 0.35em;
  padding-bottom: 0.25em;
  border-bottom: 1px solid #edf1f5;
  color: #1f2a3a;
}
.bubble-text.markdown :deep(h3) {
  font-size: 1.06em;
  font-weight: 600;
  margin: 0.6em 0 0.3em;
  color: #2c3a4e;
}
.bubble-text.markdown :deep(h4),
.bubble-text.markdown :deep(h5),
.bubble-text.markdown :deep(h6) {
  font-size: 1em;
  font-weight: 600;
  margin: 0.5em 0 0.25em;
  color: #3d4d63;
}
.bubble-text.markdown :deep(p) {
  margin: 0.4em 0;
}
.bubble-text.markdown :deep(p:first-child) {
  margin-top: 0;
}
.bubble-text.markdown :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble-text.markdown :deep(ul),
.bubble-text.markdown :deep(ol) {
  padding-left: 1.6em;
  margin: 0.35em 0;
}
.bubble-text.markdown :deep(li) {
  margin: 0.15em 0;
  line-height: 1.55;
}
.bubble-text.markdown :deep(blockquote) {
  margin: 0.5em 0;
  padding: 6px 14px;
  border-left: 3px solid #2f88ff;
  background: #f4f8fc;
  border-radius: 0 6px 6px 0;
  color: #4a5c72;
}
.bubble-text.markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5em 0;
  font-size: 13px;
}
.bubble-text.markdown :deep(th),
.bubble-text.markdown :deep(td) {
  border: 1px solid #dee4ec;
  padding: 6px 10px;
  text-align: left;
}
.bubble-text.markdown :deep(th) {
  background: #f4f7fb;
  font-weight: 600;
  color: #2c3a4e;
}
.bubble-text.markdown :deep(tr:nth-child(even) td) {
  background: #fafbfd;
}
.bubble-text.markdown :deep(hr) {
  border: none;
  border-top: 1px solid #e4e9f1;
  margin: 0.8em 0;
}
.bubble-text.markdown :deep(a) {
  color: #2f88ff;
  text-decoration: none;
}
.bubble-text.markdown :deep(a:hover) {
  text-decoration: underline;
}
.bubble-text.markdown :deep(strong) {
  font-weight: 700;
  color: #1a2332;
}
.bubble-text.markdown :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 0.4em 0;
}
.bubble-text.markdown :deep(code) {
  font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', Consolas, monospace;
  font-size: 0.88em;
}
.bubble-text.markdown :deep(p > code),
.bubble-text.markdown :deep(li > code),
.bubble-text.markdown :deep(td > code) {
  background: #edf1f7;
  color: #c7254e;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.85em;
}
.bubble-text.markdown :deep(pre) {
  background: #1f2430;
  border-radius: 8px;
  padding: 14px 16px;
  overflow-x: auto;
  margin: 0.5em 0;
  position: relative;
}
.bubble-text.markdown :deep(pre code) {
  font-size: 0.82em;
  line-height: 1.55;
  color: #cccac2;
  background: none;
  padding: 0;
}

.bubble-time {
  margin-top: 5px;
  font-size: 12px;
  color: #99a4b4;
}

.chat-footer {
  border-top: 1px solid #e8edf3;
  background: #fff;
  padding: 12px 18px 16px;
}

.preview-row {
  margin-bottom: 8px;
}

.preview-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: #f6f8fb;
  border: 1px solid #e7edf5;
  border-radius: 8px;
  padding: 8px;
}

.preview-item img {
  max-height: 64px;
  border-radius: 6px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #e8edf3;
}
.quick-actions .el-button {
  font-size: 12px;
  border-radius: 14px;
  padding: 4px 14px;
  transition: all 0.2s;
}
.quick-actions .el-button:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(47, 136, 255, 0.18);
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.tool-buttons {
  display: flex;
  gap: 8px;
  margin-bottom: 2px;
}

.cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  margin-left: 2px;
  background: currentColor;
  animation: blink 1s step-end infinite;
  vertical-align: middle;
}

.thinking-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  margin-top: 4px;
  background: #f4f7fb;
  border-radius: 10px;
}
.thinking-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #b0bec5;
  animation: dotPulse 1.4s ease-in-out infinite;
}
.thinking-indicator .dot:nth-child(1) { animation-delay: 0s; }
.thinking-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-indicator .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes blink {
  50% { opacity: 0; }
}
@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.recording {
  background: #ff5f56 !important;
  color: #fff !important;
}

@media (max-width: 1100px) {
  .conversation-panel {
    width: 250px;
  }
}

@media (max-width: 900px) {
  .conversation-panel {
    display: none;
  }

  .chat-header {
    padding: 0 12px;
  }

  .chat-body {
    padding: 14px 12px;
  }

  .chat-footer {
    padding: 10px 12px 12px;
  }
}
</style>