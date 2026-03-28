<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const roomId = computed(() => Number(route.params.id))

interface PollOption {
  id: number
  text: string
  sort_order: number
}

interface PollType {
  id: number
  title: string
  display_style: string
  sort_order: number
  options: PollOption[]
}

interface Member {
  user_id: number
  nickname: string
}

interface PeerState {
  has_selected?: boolean
  has_confirmed?: boolean
}

interface LastRoundOption {
  option_id: number
  text: string
  count: number
}

interface AssistRankRow {
  user_id: number
  nickname: string
  assist_count: number
}

interface LastRoundSummary {
  round_id?: number
  poll_title: string
  winning_option_id: number | null
  winner_nicknames: string[]
  options: LastRoundOption[]
  assist_ranking: AssistRankRow[]
}

function parseLastRoundSummary(raw: unknown): LastRoundSummary | null {
  if (!raw || typeof raw !== 'object') return null
  const p = raw as Record<string, unknown>
  const opts = p.options
  if (!Array.isArray(opts)) return null
  const araw = p.assist_ranking
  const assist_ranking: AssistRankRow[] = Array.isArray(araw)
    ? araw.map((r) => {
        const x = r as Record<string, unknown>
        return {
          user_id: Number(x.user_id),
          nickname: String(x.nickname ?? ''),
          assist_count: Number(x.assist_count ?? 0),
        }
      })
    : []
  return {
    round_id: p.round_id != null ? Number(p.round_id) : undefined,
    poll_title: String(p.poll_title ?? ''),
    winning_option_id: p.winning_option_id != null ? Number(p.winning_option_id) : null,
    winner_nicknames: Array.isArray(p.winner_nicknames)
      ? p.winner_nicknames.map((x) => String(x))
      : [],
    options: opts.map((o) => {
      const x = o as Record<string, unknown>
      return {
        option_id: Number(x.option_id),
        text: String(x.text ?? ''),
        count: Number(x.count ?? 0),
      }
    }),
    assist_ranking,
  }
}

const snapshot = ref<{
  room_id: number
  name: string
  poll_types: PollType[]
  phase?: string
  members?: Member[]
} | null>(null)

const members = ref<Member[]>([])
const peerStates = ref<Record<number, PeerState>>({})
const selfId = ref<number | null>(null)

const phase = ref('connecting')
const lastCountdown = ref<{ phase: string; seconds: number } | null>(null)
const selectedOptionId = ref<number | null>(null)
const selfConfirmed = ref(false)
const roundResult = ref<{ winners: string[]; optionId?: number } | null>(null)
/** 最近一次已公布的完整结果（各选项得票数），新一局出结果后覆盖 */
const lastRoundSummary = ref<LastRoundSummary | null>(null)
/** 上一轮结果面板是否折叠（仅收起展示区域，标题栏保留；默认折叠） */
const lastRoundFolded = ref(true)
/** 上一轮助力排行折叠（默认折叠） */
const lastRoundAssistFolded = ref(true)
const pageErr = ref('')

/** 开奖结果弹窗显隐（展示约 5 秒后关闭，与后端结果阶段一致） */
const resultPopupVisible = ref(false)
let resultPopupTimer: ReturnType<typeof setTimeout> | null = null

/** 本轮自己助力累计次数（assist_go 内本地累加；提交窗口内 assist_commit 同步到后端） */
const selfAssistCount = ref(0)
/** 助力阶段本地点击次数，结束时一次性 assist_commit */
const pendingAssistClicks = ref(0)
let assistPopSeq = 0
const assistPops = ref<{ id: number }[]>([])

/** 飘字通知 */
const floatMessages = ref<{ id: number; text: string; kind: 'welcome' | 'leave' | 'info' }[]>([])
let floatSeq = 0
function pushFloat(text: string, kind: 'welcome' | 'leave' | 'info' = 'info') {
  const id = ++floatSeq
  floatMessages.value.push({ id, text, kind })
  window.setTimeout(() => {
    floatMessages.value = floatMessages.value.filter((x) => x.id !== id)
  }, 5200)
}

/** 房间聊天（WS：chat_message + 快照 chat_messages） */
interface ChatMsg {
  id: number
  user_id: number
  nickname: string
  body: string
  created_at: string
}

const chatMessages = ref<ChatMsg[]>([])
const chatPanelOpen = ref(false)
const chatUnread = ref(false)
const chatInput = ref('')
const chatError = ref('')
const chatListRef = ref<HTMLElement | null>(null)
const chatInputEl = ref<HTMLInputElement | null>(null)
const chatEmojiOpen = ref(false)
const chatEmojiWrapRef = ref<HTMLElement | null>(null)

/** 常用表情（Unicode），与纯文本消息同管道发送 */
const CHAT_QUICK_EMOJIS = [
  '😀', '😃', '😄', '😁', '😅', '😂', '🤣', '😊', '😇', '🙂',
  '😉', '😍', '🥰', '😘', '😋', '😎', '🤩', '🥳', '😢', '😭',
  '😤', '😡', '🤔', '🙄', '😴', '👍', '👎', '👏', '🙌', '💪',
  '🙏', '❤️', '💔', '🔥', '✨', '🎉', '👀', '💯', '✅', '❌',
  '⭐', '🌟', '💤', '🍚', '🍜', '🍺', '☕', '🎮', '🎵', '🐶',
] as const

let chatEmojiOutsideListener: ((e: MouseEvent) => void) | null = null
let chatEscKeyListener: ((e: KeyboardEvent) => void) | null = null

function insertChatEmoji(emoji: string) {
  const el = chatInputEl.value
  const max = 512
  if (!el) {
    chatInput.value = (chatInput.value + emoji).slice(0, max)
    return
  }
  const start = el.selectionStart ?? chatInput.value.length
  const end = el.selectionEnd ?? chatInput.value.length
  const before = chatInput.value.slice(0, start)
  const after = chatInput.value.slice(end)
  const next = (before + emoji + after).slice(0, max)
  chatInput.value = next
  nextTick(() => {
    el.focus()
    const pos = Math.min(start + emoji.length, next.length)
    el.setSelectionRange(pos, pos)
  })
}

function toggleChatEmoji() {
  chatEmojiOpen.value = !chatEmojiOpen.value
}

function pickChatEmoji(em: string) {
  insertChatEmoji(em)
  chatEmojiOpen.value = false
}

watch(chatEmojiOpen, (open) => {
  if (chatEmojiOutsideListener) {
    document.removeEventListener('click', chatEmojiOutsideListener)
    chatEmojiOutsideListener = null
  }
  if (open) {
    nextTick(() => {
      chatEmojiOutsideListener = (e: MouseEvent) => {
        const wrap = chatEmojiWrapRef.value
        if (wrap && !wrap.contains(e.target as Node)) chatEmojiOpen.value = false
      }
      document.addEventListener('click', chatEmojiOutsideListener)
    })
  }
})

function formatChatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function parseChatMessages(raw: unknown): ChatMsg[] {
  if (!Array.isArray(raw)) return []
  return raw.map((x) => {
    const o = x as Record<string, unknown>
    return {
      id: Number(o.id),
      user_id: Number(o.user_id),
      nickname: String(o.nickname ?? ''),
      body: String(o.body ?? ''),
      created_at: String(o.created_at ?? ''),
    }
  })
}

function appendChatMessage(row: ChatMsg) {
  if (chatMessages.value.some((m) => m.id === row.id)) return
  chatMessages.value = [...chatMessages.value, row].sort((a, b) => a.id - b.id)
}

function isChatSelf(m: ChatMsg): boolean {
  if (selfId.value == null) return false
  return Number(m.user_id) === Number(selfId.value)
}

/** 已不在当前房间成员中的用户（含离线），聊天记录头像置灰 */
function isChatMemberOffline(m: ChatMsg): boolean {
  const uid = Number(m.user_id)
  if (!Number.isFinite(uid)) return false
  if (selfId.value != null && uid === Number(selfId.value)) return false
  return !members.value.some((x) => Number(x.user_id) === uid)
}

function scrollChatToBottom() {
  const el = chatListRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function toggleChatPanel() {
  chatPanelOpen.value = !chatPanelOpen.value
  if (chatPanelOpen.value) {
    chatUnread.value = false
    chatError.value = ''
    nextTick(() => scrollChatToBottom())
  }
}

function closeChatPanel() {
  chatPanelOpen.value = false
  chatEmojiOpen.value = false
}

watch(chatPanelOpen, (open) => {
  if (chatEscKeyListener) {
    document.removeEventListener('keydown', chatEscKeyListener)
    chatEscKeyListener = null
  }
  if (open) {
    chatEscKeyListener = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      closeChatPanel()
    }
    document.addEventListener('keydown', chatEscKeyListener)
  }
})

function sendChat() {
  const t = chatInput.value.trim()
  if (!t) return
  if (!ws || ws.readyState !== WebSocket.OPEN) return
  send({ msg_type: 'chat_message', body: t })
  chatInput.value = ''
  chatError.value = ''
}

watch(chatMessages, () => {
  if (chatPanelOpen.value) {
    nextTick(() => scrollChatToBottom())
  }
}, { deep: true })

/** 跑马灯 */
interface MarqueeStep {
  t_ms: number
  highlight_index: number
}
const marqueeActive = ref(false)
const marqueeHighlightOptionId = ref<number | null>(null)
let marqueeRaf = 0
let marqueeStartPerf = 0

const PHASE_LABEL: Record<string, string> = {
  connecting: '连接中…',
  waiting: '等待题目',
  selecting: '投票中',
  pending_confirm: '等待全员确认',
  countdown_5s: '全员已确认 · 可取消',
  assist_preview: '助力即将开始',
  assist_go: '疯狂助力',
  computing: '统计中',
  marquee: '跑马灯',
  result: '本轮结果',
}

const phaseLabel = computed(() => PHASE_LABEL[phase.value] || phase.value)

const canPickOptions = computed(() => phase.value === 'selecting')

/** 选题阶段未确认：始终显示「确认」按钮，未选选项时为禁用置灰 */
const showConfirmInSelecting = computed(
  () => phase.value === 'selecting' && !selfConfirmed.value,
)

const showBtnUnconfirm = computed(() => phase.value === 'selecting' && selfConfirmed.value)

const showBtnCancelCountdown = computed(() => phase.value === 'countdown_5s')

const showBtnAssist = computed(() => phase.value === 'assist_go')

const leftControlsLocked = computed(() =>
  ['computing', 'marquee', 'result', 'assist_preview', 'waiting', 'assist_go'].includes(phase.value),
)

const optionsLocked = computed(() => !canPickOptions.value)

const sortedMembers = computed(() => [...members.value].sort((a, b) => a.user_id - b.user_id))

/** 按 user_id 稳定映射小动物 + 底色（同一人始终相同） */
const ANIMAL_EMOJIS = [
  '🐱',
  '🐶',
  '🐰',
  '🦊',
  '🐻',
  '🐼',
  '🐨',
  '🐯',
  '🦁',
  '🐮',
  '🐷',
  '🐸',
  '🐵',
  '🦉',
  '🦋',
  '🐙',
  '🦔',
  '🐧',
  '🦆',
  '🐢',
  '🦎',
  '🐿️',
  '🦦',
  '🦫',
  '🐹',
] as const

const AVATAR_BACKGROUNDS = [
  '#fce7f3',
  '#e0e7ff',
  '#fef3c7',
  '#d1fae5',
  '#fecdd3',
  '#e0f2fe',
  '#ede9fe',
  '#ffedd5',
  '#ccfbf1',
  '#fbcfe8',
  '#c7d2fe',
  '#bbf7d0',
  '#fde68a',
  '#fecaca',
  '#a5f3fc',
] as const

function avatarForUser(userId: number): { emoji: string; bg: string } {
  const n = Math.imul(userId ^ 0x9e3779b9, 0x7feb352d) >>> 0
  const ei = n % ANIMAL_EMOJIS.length
  const bi = (n >>> 11) % AVATAR_BACKGROUNDS.length
  return {
    emoji: ANIMAL_EMOJIS[ei],
    bg: AVATAR_BACKGROUNDS[bi],
  }
}

const playersWithAvatars = computed(() =>
  sortedMembers.value.map((m) => ({
    ...m,
    avatar: avatarForUser(m.user_id),
  })),
)

const firstType = computed(() => snapshot.value?.poll_types?.[0])

const winningOptionLabel = computed(() => {
  const oid = roundResult.value?.optionId
  if (oid == null || !firstType.value) return ''
  const o = firstType.value.options.find((x) => x.id === oid)
  return o?.text ?? ''
})

/** 仅含得票大于 0 的选项（列表展示用） */
const lastRoundOptionsWithVotes = computed(() => {
  const s = lastRoundSummary.value
  if (!s?.options?.length) return []
  return s.options.filter((o) => o.count > 0)
})

const showLastRoundPanel = computed(
  () => lastRoundSummary.value != null && lastRoundOptionsWithVotes.value.length > 0,
)

const showLastRoundAssistPanel = computed(
  () =>
    lastRoundSummary.value != null && (lastRoundSummary.value.assist_ranking?.length ?? 0) > 0,
)

const lastRoundWinningLabel = computed(() => {
  const s = lastRoundSummary.value
  if (!s?.winning_option_id) return ''
  const o = s.options.find((x) => x.option_id === s.winning_option_id)
  return o?.text ?? ''
})

const centerModal = computed(() => {
  const p = phase.value
  const cd = lastCountdown.value
  if (p === 'countdown_5s' && cd?.phase === 'countdown_5s') {
    return {
      show: true,
      title: '所有玩家已确认',
      sub: '倒计时结束前可点击左下角「取消」重选',
      showNumber: true,
    }
  }
  if (p === 'assist_preview' && cd?.phase === 'assist_preview') {
    return {
      show: true,
      title: '助力倒计时',
      sub: '准备就绪后请狂点右下角黄色助力按钮',
      showNumber: true,
    }
  }
  if (p === 'assist_go' && cd?.phase === 'assist_go') {
    return {
      show: true,
      title: '开始助力',
      sub: '倒计时内可多次点击「助力」为选项加权',
      showNumber: true,
    }
  }
  if (p === 'computing') {
    return {
      show: true,
      title: '助力结束，正在统计',
      sub: '最终选票即将揭晓…',
      showNumber: false,
    }
  }
  /** 开奖中不挡全屏遮罩，避免压住中间跑马灯动画 */
  return { show: false, title: '', sub: '', showNumber: false }
})

function mergePeerState(userId: number, patch: PeerState) {
  peerStates.value = {
    ...peerStates.value,
    [userId]: { ...peerStates.value[userId], ...patch },
  }
}

function applySnapshotPeerStates(rows: { user_id: number; has_selected?: boolean; has_confirmed?: boolean }[]) {
  const next: Record<number, PeerState> = { ...peerStates.value }
  for (const r of rows) {
    next[r.user_id] = {
      ...next[r.user_id],
      has_selected: r.has_selected,
      has_confirmed: r.has_confirmed,
    }
  }
  peerStates.value = next
}

function statusFor(uid: number): string {
  if (phase.value === 'result' && roundResult.value?.winners) {
    const nick = members.value.find((m) => m.user_id === uid)?.nickname ?? ''
    if (roundResult.value.winners.includes(nick)) return '获得本次投票胜利'
    return '遗憾失败'
  }
  if (['computing', 'marquee'].includes(phase.value)) {
    return '等待开奖'
  }
  if (phase.value === 'assist_go') return '助力中'
  if (phase.value === 'assist_preview') return '等待助力'
  if (phase.value === 'countdown_5s') {
    const ps = peerStates.value[uid]
    if (ps?.has_confirmed) return '已准备'
    return '正在选择'
  }
  const ps = peerStates.value[uid]
  if (!ps) return '…'
  if (ps.has_confirmed) return '已准备'
  return '正在选择'
}

let ws: WebSocket | null = null
let hbTimer: number | null = null

function stopMarquee() {
  if (marqueeRaf) cancelAnimationFrame(marqueeRaf)
  marqueeRaf = 0
  marqueeActive.value = false
  marqueeHighlightOptionId.value = null
}

function startMarquee(steps: MarqueeStep[], orderedIds: number[]) {
  stopMarquee()
  if (!steps.length || !orderedIds.length) return
  marqueeActive.value = true
  const lastT = steps[steps.length - 1]?.t_ms ?? 0

  function tick() {
    const elapsed = performance.now() - marqueeStartPerf
    let hi = steps[0]?.highlight_index ?? 0
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].t_ms <= elapsed) {
        hi = steps[i].highlight_index
        break
      }
    }
    const oid = orderedIds[hi]
    marqueeHighlightOptionId.value = oid ?? null
    if (elapsed < lastT + 80) {
      marqueeRaf = requestAnimationFrame(tick)
    }
  }
  marqueeStartPerf = performance.now()
  marqueeRaf = requestAnimationFrame(tick)
}

function connectWs() {
  const token = auth.token
  if (!token) {
    router.push('/login')
    return
  }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}/ws/rooms/${roomId.value}?token=${encodeURIComponent(token)}`
  ws = new WebSocket(url)
  ws.onerror = () => {
    pageErr.value = 'WebSocket 连接错误'
  }
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data as string)
    const t = msg.msg_type as string
    const p = msg.payload || {}
    if (t === 'room_snapshot') {
      snapshot.value = {
        room_id: p.room_id,
        name: p.name,
        poll_types: p.poll_types || [],
      }
      phase.value = p.phase || 'selecting'
      if (Array.isArray(p.members)) {
        members.value = p.members
      }
      if (Array.isArray(p.peer_states)) {
        applySnapshotPeerStates(p.peer_states)
      }
      lastRoundSummary.value = parseLastRoundSummary(p.last_round_summary)
      if (Array.isArray(p.chat_messages)) {
        chatMessages.value = parseChatMessages(p.chat_messages)
      }
    }
    if (t === 'chat_message') {
      appendChatMessage({
        id: Number(p.id),
        user_id: Number(p.user_id),
        nickname: String(p.nickname ?? ''),
        body: String(p.body ?? ''),
        created_at: String(p.created_at ?? ''),
      })
      const uid = Number(p.user_id)
      if (!chatPanelOpen.value && (selfId.value == null || uid !== selfId.value)) {
        chatUnread.value = true
      }
    }
    if (t === 'welcome') {
      const text = p.text || '欢迎加入'
      pushFloat(text, 'welcome')
      const nid = Number(p.user_id)
      const nn = p.nickname as string | undefined
      if (Number.isFinite(nid) && nn && !members.value.some((m) => Number(m.user_id) === nid)) {
        members.value = [...members.value, { user_id: nid, nickname: nn }]
      }
    }
    if (t === 'user_left') {
      const nid = Number(p.user_id)
      const nn = p.nickname as string | undefined
      pushFloat(`${nn ?? '一位玩家'} 退出房间`, 'leave')
      if (Number.isFinite(nid)) {
        members.value = members.value.filter((m) => Number(m.user_id) !== nid)
        const { [nid]: _, ...rest } = peerStates.value
        peerStates.value = rest
      }
    }
    if (t === 'phase_changed') {
      phase.value = p.phase || phase.value
      if (p.new_round) {
        roundResult.value = null
        selfConfirmed.value = false
        selectedOptionId.value = null
        if (resultPopupTimer != null) {
          clearTimeout(resultPopupTimer)
          resultPopupTimer = null
        }
        resultPopupVisible.value = false
      }
      if (p.phase === 'selecting' && p.cancelled_by != null) {
        selfConfirmed.value = false
      }
    }
    if (t === 'countdown') {
      lastCountdown.value = { phase: p.phase, seconds: p.seconds }
    }
    if (t === 'select_ack') {
      selectedOptionId.value = p.option_id
      selfConfirmed.value = false
    }
    if (t === 'peer_state') {
      const uid = p.user_id as number
      mergePeerState(uid, {
        has_selected: p.has_selected,
        has_confirmed: p.has_confirmed,
      })
    }
    if (t === 'marquee_start') {
      phase.value = 'marquee'
      const steps = (p.steps || []) as MarqueeStep[]
      const ids = (p.ordered_option_ids || []) as number[]
      startMarquee(steps, ids)
    }
    if (t === 'assist_submit_window') {
      send({ msg_type: 'assist_commit', count: pendingAssistClicks.value })
    }
    if (t === 'round_result') {
      stopMarquee()
      lastRoundSummary.value = parseLastRoundSummary(p) ?? lastRoundSummary.value
      roundResult.value = { winners: p.winner_nicknames || [], optionId: p.winning_option_id }
      phase.value = 'result'
      resultPopupVisible.value = true
      if (resultPopupTimer != null) {
        clearTimeout(resultPopupTimer)
        resultPopupTimer = null
      }
      resultPopupTimer = window.setTimeout(() => {
        resultPopupVisible.value = false
        resultPopupTimer = null
      }, 5000)
    }
    if (t === 'room_closed') {
      stopMarquee()
      pageErr.value = '房间已关闭'
      router.push('/rooms')
    }
    if (t === 'error') {
      if (p.scope === 'chat') {
        chatError.value = String(p.message || '错误')
        return
      }
      pageErr.value = p.message || '错误'
      selfConfirmed.value = false
    }
  }
}

function send(m: Record<string, unknown>) {
  ws?.send(JSON.stringify(m))
}

function selectOption(id: number) {
  if (!canPickOptions.value) return
  send({ msg_type: 'select_option', option_id: id })
}

function confirm() {
  if (selectedOptionId.value == null) return
  send({ msg_type: 'confirm' })
  selfConfirmed.value = true
}

function unconfirm() {
  send({ msg_type: 'cancel' })
  selfConfirmed.value = false
}

function cancelCountdown() {
  send({ msg_type: 'cancel' })
  selfConfirmed.value = false
}

function assist() {
  if (!showBtnAssist.value) return
  pendingAssistClicks.value += 1
  selfAssistCount.value = pendingAssistClicks.value
  const id = ++assistPopSeq
  assistPops.value = [...assistPops.value, { id }]
  window.setTimeout(() => {
    assistPops.value = assistPops.value.filter((x) => x.id !== id)
  }, 720)
}

watch(phase, (ph) => {
  if (ph === 'countdown_5s') {
    selfConfirmed.value = true
  }
  if (ph === 'assist_go') {
    selfAssistCount.value = 0
    pendingAssistClicks.value = 0
    assistPops.value = []
  }
})

onMounted(async () => {
  pageErr.value = ''
  try {
    const { data: me } = await http.get<{ id: number }>('/auth/me')
    selfId.value = me.id
  } catch {
    selfId.value = null
  }
  try {
    await http.post(`/rooms/${roomId.value}/join`)
  } catch (e: unknown) {
    const x = e as { response?: { data?: { detail?: string } } }
    pageErr.value = x.response?.data?.detail || '进入房间失败'
    router.push('/rooms')
    return
  }
  connectWs()
  hbTimer = window.setInterval(() => send({ msg_type: 'heartbeat' }), 20000)
})

onBeforeUnmount(() => {
  if (chatEscKeyListener) {
    document.removeEventListener('keydown', chatEscKeyListener)
    chatEscKeyListener = null
  }
  if (chatEmojiOutsideListener) {
    document.removeEventListener('click', chatEmojiOutsideListener)
    chatEmojiOutsideListener = null
  }
  stopMarquee()
  if (hbTimer != null) clearInterval(hbTimer)
  if (resultPopupTimer != null) {
    clearTimeout(resultPopupTimer)
    resultPopupTimer = null
  }
  ws?.close()
  http.post(`/rooms/${roomId.value}/leave`).catch(() => {})
})

function optionHighlight(o: PollOption) {
  if (marqueeActive.value && marqueeHighlightOptionId.value === o.id) return 'mq-on'
  if (!marqueeActive.value && selectedOptionId.value === o.id) return 'picked'
  if (marqueeActive.value && marqueeHighlightOptionId.value !== o.id) return 'mq-dim'
  return ''
}
</script>

<template>
  <div class="room-page">
    <header class="room-header">
      <h1 class="room-title">{{ snapshot?.name || `房间 #${roomId}` }}</h1>
      <p class="room-phase">
        <span class="phase-pill">{{ phaseLabel }}</span>
      </p>
      <router-link class="room-back" to="/rooms">← 房间列表</router-link>
    </header>

    <p v-if="pageErr" class="room-err">{{ pageErr }}</p>

    <!-- 上一轮结果：仅显示有得票的选项；可折叠 -->
    <section v-if="showLastRoundPanel && lastRoundSummary" class="block last-round-block">
      <div class="last-round__shell" :class="{ 'is-collapsed': lastRoundFolded }">
        <button
          type="button"
          class="last-round__toolbar"
          :aria-expanded="!lastRoundFolded"
          aria-controls="last-round-panel"
          @click="lastRoundFolded = !lastRoundFolded"
        >
          <span class="last-round__toolbar-title">上一轮投票结果</span>
          <span class="last-round__toolbar-action">
            <span class="last-round__fold-text">{{ lastRoundFolded ? '展开' : '收起' }}</span>
            <span class="last-round__chevron" :class="{ 'last-round__chevron--folded': lastRoundFolded }" aria-hidden="true"
              >▼</span
            >
          </span>
        </button>
        <div
          v-show="!lastRoundFolded"
          id="last-round-panel"
          class="last-round-card"
        >
          <p v-if="lastRoundSummary.poll_title" class="last-round__poll-title">{{ lastRoundSummary.poll_title }}</p>
          <p class="last-round__win-line">
            胜出：<strong class="last-round__win-name">{{ lastRoundWinningLabel || '—' }}</strong>
            <template v-if="lastRoundSummary.winner_nicknames.length">
              <span class="last-round__winners">
                （{{ lastRoundSummary.winner_nicknames.join('、') }}）
              </span>
            </template>
          </p>
          <ul class="last-round__counts" aria-label="有得票的选项">
            <li
              v-for="o in lastRoundOptionsWithVotes"
              :key="o.option_id"
              class="last-round__row"
              :class="{ 'last-round__row--win': o.option_id === lastRoundSummary.winning_option_id }"
            >
              <span class="last-round__opt-text">{{ o.text }}</span>
              <span class="last-round__opt-count">{{ o.count }} 票</span>
            </li>
          </ul>
        </div>
      </div>
    </section>

    <!-- 上一轮助力排行（紧挨投票结果，可折叠） -->
    <section v-if="showLastRoundAssistPanel && lastRoundSummary" class="block last-round-block last-assist-block">
      <div class="last-round__shell" :class="{ 'is-collapsed': lastRoundAssistFolded }">
        <button
          type="button"
          class="last-round__toolbar"
          :aria-expanded="!lastRoundAssistFolded"
          aria-controls="last-assist-panel"
          @click="lastRoundAssistFolded = !lastRoundAssistFolded"
        >
          <span class="last-round__toolbar-title">上一轮助力排行</span>
          <span class="last-round__toolbar-action">
            <span class="last-round__fold-text">{{ lastRoundAssistFolded ? '展开' : '收起' }}</span>
            <span
              class="last-round__chevron"
              :class="{ 'last-round__chevron--folded': lastRoundAssistFolded }"
              aria-hidden="true"
              >▼</span
            >
          </span>
        </button>
        <div v-show="!lastRoundAssistFolded" id="last-assist-panel" class="last-round-card">
          <ol class="last-assist__list" aria-label="助力次数排行">
            <li
              v-for="(row, idx) in lastRoundSummary.assist_ranking"
              :key="row.user_id"
              class="last-assist__row"
            >
              <span class="last-assist__rank">{{ idx + 1 }}</span>
              <span class="last-assist__name">{{ row.nickname }}</span>
              <span class="last-assist__num">{{ row.assist_count }} 次</span>
            </li>
          </ol>
        </div>
      </div>
    </section>

    <!-- 中央阶段提示（灵感：倒计时、助力等显眼文案） -->
    <div v-if="centerModal.show" class="phase-overlay">
      <div class="phase-card">
        <p class="phase-card__title">{{ centerModal.title }}</p>
        <p v-if="centerModal.sub" class="phase-card__sub">{{ centerModal.sub }}</p>
        <div v-if="centerModal.showNumber && lastCountdown" class="phase-card__num">
          {{ lastCountdown.seconds }}
          <span class="phase-card__unit">秒</span>
        </div>
      </div>
    </div>

    <!-- 本轮结果（约 5 秒后自动收起） -->
    <div
      v-if="phase === 'result' && roundResult?.winners?.length && resultPopupVisible"
      class="result-overlay"
      aria-hidden="true"
    >
      <div class="result-card">
        <p class="result-card__tag">本轮结果</p>
        <p class="result-card__main">
          恭喜
          <strong>{{ roundResult.winners.join('、') }}</strong>
          ！
        </p>
        <p v-if="winningOptionLabel" class="result-card__opt">胜出选项：{{ winningOptionLabel }}</p>
      </div>
    </div>

    <!-- 上：玩家（彩色小动物头像 + 姓名在上、状态在下） -->
    <section class="block players-block" aria-label="本局玩家">
      <div class="players-wrap">
        <div class="players-scroll">
          <div
            v-for="m in playersWithAvatars"
            :key="m.user_id"
            class="player-tile"
            :class="{ 'player-tile--self': selfId != null && m.user_id === selfId }"
          >
            <span class="player-tile__name">{{ m.nickname }}</span>
            <div
              class="player-tile__avatar"
              :style="{ backgroundColor: m.avatar.bg }"
              aria-hidden="true"
            >
              <span class="player-tile__emoji">{{ m.avatar.emoji }}</span>
            </div>
            <span class="player-tile__status">{{ statusFor(m.user_id) }}</span>
          </div>
          <p v-if="playersWithAvatars.length === 0" class="players-empty">暂无成员数据，连接成功后刷新可见。</p>
        </div>
        <button
          type="button"
          class="chat-fab"
          :class="{ 'chat-fab--open': chatPanelOpen }"
          aria-label="聊天"
          @click.stop="toggleChatPanel"
        >
          <svg class="chat-fab__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <span v-show="chatUnread" class="chat-fab__dot" aria-hidden="true" />
        </button>
      </div>
    </section>

    <!-- 中：投票选项 -->
    <section v-if="firstType" class="block vote-block" :aria-label="firstType.title">
      <div
        class="options-grid"
        :class="firstType.display_style === 'plate' ? 'options-grid--plate' : 'options-grid--square'"
      >
        <button
          v-for="o in firstType.options"
          :key="o.id"
          type="button"
          class="opt-tile"
          :class="optionHighlight(o)"
          :disabled="optionsLocked"
          @click="selectOption(o.id)"
        >
          <span class="opt-tile__text">{{ o.text }}</span>
        </button>
      </div>
    </section>

    <section v-else class="block vote-block vote-block--empty">
      <p>暂无投票题目，请等待管理员配置。</p>
    </section>

    <!-- 欢迎 / 退出：投票区与底栏之间的中间带弹出 -->
    <div class="float-zone">
      <div class="float-strip" aria-live="polite">
        <TransitionGroup name="float-slide">
          <div
            v-for="f in floatMessages"
            :key="f.id"
            class="float-banner"
            :class="'float-banner--' + f.kind"
          >
            {{ f.text }}
          </div>
        </TransitionGroup>
      </div>
    </div>

    <!-- 下：左确认/取消，右黄色 3D 助力（固定于视口但宽度与主列对齐，且高于阶段遮罩） -->
    <div class="bottom-bar-wrap">
      <footer class="bottom-bar">
        <div class="bottom-bar__left">
          <template v-if="showConfirmInSelecting">
            <button
              type="button"
              class="btn-rect btn-rect--confirm"
              :disabled="selectedOptionId == null"
              @click="confirm"
            >
              确认
            </button>
            <span v-if="selectedOptionId == null" class="bottom-hint muted">请选择选项后点击确认</span>
          </template>
          <template v-else-if="showBtnUnconfirm">
            <button type="button" class="btn-rect btn-rect--cancel" @click="unconfirm">取消</button>
            <span class="bottom-hint">已确认选择，等待他人</span>
          </template>
          <template v-else-if="showBtnCancelCountdown">
            <button type="button" class="btn-rect btn-rect--cancel" @click="cancelCountdown">取消</button>
            <span class="bottom-hint">重选投票</span>
          </template>
          <template v-else-if="leftControlsLocked">
            <button type="button" class="btn-rect btn-rect--disabled" disabled>已锁定</button>
            <span class="bottom-hint muted">当前阶段不可改选</span>
          </template>
          <template v-else>
            <span v-if="phase === 'connecting'" class="bottom-hint muted">连接中…</span>
          </template>
        </div>
        <div class="bottom-bar__right">
          <div class="btn-assist-wrap">
            <TransitionGroup name="assist-pop" tag="div" class="assist-pop-layer">
              <span v-for="pop in assistPops" :key="pop.id" class="assist-pop">+1</span>
            </TransitionGroup>
            <button
              type="button"
              class="btn-assist"
              :class="{ 'btn-assist--hot': showBtnAssist }"
              :disabled="!showBtnAssist"
              @click="assist"
            >
              <span class="btn-assist__label">助力</span>
              <span v-if="showBtnAssist && selfAssistCount > 0" class="btn-assist__badge">{{ selfAssistCount }}</span>
            </button>
          </div>
        </div>
      </footer>
    </div>

    <div
      v-show="chatPanelOpen"
      class="chat-panel"
      role="dialog"
      aria-label="聊天室"
      @click.stop
    >
      <div class="chat-panel__header">
        <span class="chat-panel__title">聊天室</span>
        <button type="button" class="chat-panel__close" aria-label="关闭聊天" @click="closeChatPanel">
          ×
        </button>
      </div>
      <div ref="chatListRef" class="chat-panel__list">
        <div
          v-for="m in chatMessages"
          :key="m.id"
          class="chat-msg"
          :class="{ 'chat-msg--self': isChatSelf(m), 'chat-msg--offline': isChatMemberOffline(m) }"
        >
          <div
            class="chat-msg__avatar"
            :style="{ backgroundColor: avatarForUser(m.user_id).bg }"
            aria-hidden="true"
          >
            <span>{{ avatarForUser(m.user_id).emoji }}</span>
          </div>
          <div class="chat-msg__col">
            <div class="chat-msg__meta">
              <span class="chat-msg__name">{{ m.nickname }}</span>
              <span class="chat-msg__time">{{ formatChatTime(m.created_at) }}</span>
            </div>
            <div class="chat-msg__bubble">{{ m.body }}</div>
          </div>
        </div>
        <p v-if="chatMessages.length === 0" class="chat-panel__empty">暂无消息，来说一句吧</p>
      </div>
      <div class="chat-panel__composer">
        <p v-if="chatError" class="chat-panel__err">{{ chatError }}</p>
        <div ref="chatEmojiWrapRef" class="chat-panel__composer-emoji">
          <div class="chat-panel__row">
            <button
              type="button"
              class="chat-panel__emoji-btn"
              aria-label="插入表情"
              :aria-expanded="chatEmojiOpen"
              aria-haspopup="true"
              @click.stop="toggleChatEmoji"
            >
              <span class="chat-panel__emoji-btn-icon" aria-hidden="true">😊</span>
            </button>
            <input
              ref="chatInputEl"
              v-model="chatInput"
              class="chat-panel__input"
              type="text"
              maxlength="512"
              placeholder="输入消息…"
              autocomplete="off"
              @keydown.enter.prevent="sendChat"
            />
            <button type="button" class="chat-panel__send" @click="sendChat">发送</button>
          </div>
          <div
            v-show="chatEmojiOpen"
            class="chat-emoji-pop"
            role="listbox"
            aria-label="常用表情"
            @click.stop
          >
            <button
              v-for="(em, i) in CHAT_QUICK_EMOJIS"
              :key="i"
              type="button"
              class="chat-emoji-pop__item"
              :aria-label="`插入表情 ${em}`"
              @click="pickChatEmoji(em)"
            >
              {{ em }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.room-page {
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 960px;
  margin: 0 auto;
  padding: 1rem 1rem 6.5rem;
  background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

.room-header {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  column-gap: 0.5rem;
  row-gap: 0.35rem;
  margin-bottom: 1rem;
}

.room-title {
  margin: 0;
  grid-column: 1;
  justify-self: start;
  min-width: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.room-phase {
  margin: 0;
  grid-column: 2;
  justify-self: center;
}

.phase-pill {
  display: inline-block;
  padding: 0.2rem 0.65rem;
  background: #e0e7ff;
  color: #3730a3;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.room-back {
  grid-column: 3;
  justify-self: end;
  color: #475569;
  text-decoration: none;
  font-size: 0.9rem;
  padding: 0.35rem 0.5rem;
  border-radius: 8px;
}
.room-back:hover {
  background: rgba(255, 255, 255, 0.8);
  color: #1d4ed8;
}

.room-err {
  color: #b91c1c;
  margin: 0 0 0.75rem;
}

/* 玩家列表白框内右下角 + 全屏聊天面板 */
.players-wrap {
  position: relative;
}

/* 房间聊天：右侧悬浮按钮 + 中间层面板 */
.chat-fab {
  position: absolute;
  z-index: 6;
  right: 0.4rem;
  bottom: 0.4rem;
  width: 2.55rem;
  height: 2.55rem;
  border-radius: 50%;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.12);
  color: #475569;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  pointer-events: auto;
  transition:
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s;
}

.chat-fab:hover {
  background: #f8fafc;
  color: #2563eb;
}

.chat-fab--open {
  border-color: #bfdbfe;
  color: #2563eb;
  box-shadow: 0 4px 18px rgba(37, 99, 235, 0.2);
}

.chat-fab__icon {
  width: 1.45rem;
  height: 1.45rem;
}

.chat-fab__dot {
  position: absolute;
  top: 0.3rem;
  right: 0.3rem;
  width: 0.55rem;
  height: 0.55rem;
  border-radius: 50%;
  background: #ef4444;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.35);
}

.chat-panel {
  position: fixed;
  /* 低于底栏 z-index，避免与固定操作栏抢层；底栏保持可点 */
  z-index: 99;
  left: 50%;
  transform: translateX(-50%);
  width: min(920px, calc(100vw - 2rem));
  top: 5.25rem;
  /* 底栏约 5.5–6.5rem + 安全区，多留一截避免白底与「确认/助力」条重叠 */
  bottom: calc(7.35rem + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.14);
  overflow: hidden;
  pointer-events: auto;
}

.chat-panel__header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.5rem 0.35rem 0.5rem 0.85rem;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.chat-panel__title {
  font-weight: 700;
  font-size: 0.95rem;
  color: #334155;
}

.chat-panel__close {
  margin: 0;
  padding: 0.35rem 0.65rem;
  border: none;
  border-radius: 10px;
  background: transparent;
  font: inherit;
  font-size: 1.65rem;
  line-height: 1;
  color: #64748b;
  cursor: pointer;
  transition:
    background 0.15s,
    color 0.15s;
}

.chat-panel__close:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.chat-panel__list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 0.75rem 0.85rem;
  -webkit-overflow-scrolling: touch;
  background: rgba(248, 250, 252, 0.28);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.chat-panel__composer {
  flex: 0 0 auto;
  min-height: 4.25rem;
  border-top: 1px solid #e2e8f0;
  padding: 0.55rem 0.75rem 0.7rem;
  background: #fafafa;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.chat-panel__empty {
  margin: 2rem 0;
  text-align: center;
  color: #94a3b8;
  font-size: 0.9rem;
}

.chat-panel__err {
  margin: 0;
  font-size: 0.8rem;
  color: #b91c1c;
}

.chat-panel__row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-panel__composer-emoji {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.chat-panel__emoji-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.45rem;
  height: 2.45rem;
  padding: 0;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s;
}

.chat-panel__emoji-btn:hover {
  background: #f8fafc;
  border-color: #cbd5e1;
}

.chat-panel__emoji-btn-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.chat-emoji-pop {
  padding: 0.45rem;
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 0.1rem;
  width: 100%;
  max-height: 10.5rem;
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
  box-sizing: border-box;
}

.chat-emoji-pop__item {
  margin: 0;
  padding: 0.25rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  font: inherit;
  font-size: 1.3rem;
  line-height: 1.25;
  cursor: pointer;
}

.chat-emoji-pop__item:hover {
  background: #f1f5f9;
}

.chat-panel__input {
  flex: 1;
  min-width: 0;
  padding: 0.55rem 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font: inherit;
  font-size: 0.95rem;
  background: #fff;
}

.chat-panel__input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.chat-panel__send {
  flex-shrink: 0;
  padding: 0.55rem 1rem;
  border: none;
  border-radius: 10px;
  font: inherit;
  font-size: 0.9rem;
  font-weight: 600;
  color: #fff;
  background: #2563eb;
  cursor: pointer;
}

.chat-panel__send:hover {
  background: #1d4ed8;
}

.chat-msg {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.85rem;
}

.chat-msg:last-child {
  margin-bottom: 0;
}

.chat-msg__avatar {
  flex-shrink: 0;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
}

.chat-msg--offline .chat-msg__avatar {
  filter: grayscale(1);
  opacity: 0.82;
}

.chat-msg--offline .chat-msg__name {
  color: #94a3b8;
}

.chat-msg:not(.chat-msg--self) .chat-msg__col {
  flex: 1;
  min-width: 0;
}

.chat-msg__meta {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.35rem 0.5rem;
  margin-bottom: 0.2rem;
}

.chat-msg__name {
  font-size: 0.8rem;
  font-weight: 700;
  color: #334155;
}

.chat-msg__time {
  font-size: 0.72rem;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.chat-msg__bubble {
  display: inline-block;
  max-width: 100%;
  padding: 0.45rem 0.65rem;
  border-radius: 12px;
  background: #f1f5f9;
  color: #1e293b;
  font-size: 0.9rem;
  line-height: 1.45;
  word-break: break-word;
  font-family:
    ui-sans-serif,
    system-ui,
    'Apple Color Emoji',
    'Segoe UI Emoji',
    'Segoe UI Symbol',
    'Noto Color Emoji',
    sans-serif;
}

/* 自己：整组靠右，顺序为 [文字列][头像]，避免 row-reverse 导致气泡仍在左侧 */
.chat-msg--self {
  flex-direction: row;
  justify-content: flex-end;
  align-items: flex-start;
}

.chat-msg--self .chat-msg__avatar {
  order: 2;
}

.chat-msg--self .chat-msg__col {
  order: 1;
  flex: 0 1 auto;
  min-width: 0;
  max-width: calc(100% - 2.75rem);
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.chat-msg--self .chat-msg__meta {
  justify-content: flex-end;
}

.chat-msg--self .chat-msg__time {
  order: 1;
}

.chat-msg--self .chat-msg__name {
  order: 2;
}

.chat-msg--self .chat-msg__bubble {
  background: #dbeafe;
  color: #1e3a8a;
  text-align: left;
}

/* 上一轮结果 */
.last-round-block:not(.last-assist-block) {
  margin-bottom: 0;
}

/* 两轮结果卡片之间略留缝，比负 margin 安全、又比默认块间距更紧 */
.last-round-block:not(.last-assist-block) + .last-assist-block {
  margin-top: 2px;
}

.last-round__shell {
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  overflow: hidden;
}

.last-round__toolbar {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.65rem 1rem;
  margin: 0;
  font: inherit;
  text-align: left;
  cursor: pointer;
  background: #f8fafc;
  border: none;
  border-bottom: 1px solid #e2e8f0;
  color: inherit;
  transition: background 0.15s;
}

.last-round__toolbar:hover {
  background: #f1f5f9;
}

.last-round__shell.is-collapsed .last-round__toolbar {
  border-bottom: none;
}

.last-round__toolbar-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #64748b;
}

.last-round__toolbar-action {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: #2563eb;
}

.last-round__fold-text {
  user-select: none;
}

.last-round__chevron {
  display: inline-block;
  font-size: 0.65rem;
  line-height: 1;
  transition: transform 0.2s ease;
  transform: rotate(0deg);
}

.last-round__chevron--folded {
  transform: rotate(-90deg);
}

.last-round-card {
  padding: 1rem 1.1rem 1.1rem;
  background: #fff;
  border-radius: 0;
  border: none;
  box-shadow: none;
}

.last-round__poll-title {
  margin: 0 0 0.5rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #0f172a;
}

.last-round__win-line {
  margin: 0 0 0.75rem;
  font-size: 0.88rem;
  color: #475569;
  line-height: 1.5;
}

.last-round__win-name {
  color: #1d4ed8;
  font-size: 1rem;
}

.last-round__winners {
  color: #64748b;
  font-weight: 500;
}

.last-round__counts {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.last-round__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.45rem 0.65rem;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 0.875rem;
  color: #334155;
}

.last-round__row--win {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  font-weight: 600;
}

.last-round__opt-count {
  font-variant-numeric: tabular-nums;
  color: #64748b;
  flex-shrink: 0;
}

.last-round__row--win .last-round__opt-count {
  color: #1d4ed8;
}

.last-assist-block {
  margin-top: 0;
}

.last-assist__list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.last-assist__row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.5rem;
  border-radius: 10px;
  background: #f8fafc;
  font-size: 0.875rem;
  color: #334155;
}

.last-assist__row + .last-assist__row {
  margin-top: 0.35rem;
}

.last-assist__rank {
  flex-shrink: 0;
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 8px;
  background: linear-gradient(180deg, #e0e7ff, #c7d2fe);
  color: #3730a3;
  font-size: 0.75rem;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

.last-assist__name {
  flex: 1;
  min-width: 0;
  font-weight: 600;
}

.last-assist__num {
  font-variant-numeric: tabular-nums;
  color: #64748b;
  flex-shrink: 0;
}

/* 欢迎/退出：占满标题与底栏之间的剩余高度，条幅在带内垂直居中 */
.float-zone {
  flex: 1 1 auto;
  min-height: 4rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: stretch;
  width: 100%;
  padding: 0.35rem 0 0.25rem;
  pointer-events: none;
}

.float-strip {
  position: relative;
  min-height: 0;
  width: 100%;
  pointer-events: none;
}

.float-banner {
  margin-bottom: 0.5rem;
  padding: 0.65rem 1rem;
  border-radius: 12px;
  font-weight: 600;
  text-align: center;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08);
  animation: float-in 0.45s ease-out;
}

.float-banner:last-child {
  margin-bottom: 0;
}

.float-banner--welcome {
  background: linear-gradient(180deg, #fffbeb, #fef3c7);
  color: #78350f;
  border: 1px solid rgba(253, 230, 138, 0.85);
}

.float-banner--leave {
  background: linear-gradient(180deg, #f8fafc, #f1f5f9);
  color: #475569;
  border: 1px solid #e2e8f0;
}

.float-banner--info {
  background: #fff;
  color: #334155;
  border: 1px solid #e2e8f0;
}

@keyframes float-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.float-slide-enter-active,
.float-slide-leave-active {
  transition: all 0.35s ease;
}
.float-slide-enter-from,
.float-slide-leave-to {
  opacity: 0;
  transform: translateY(10px);
}

/* 中央阶段遮罩（低于底栏 z-index，避免压暗、挡住底部操作） */
.phase-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  padding-bottom: calc(5.5rem + env(safe-area-inset-bottom));
  background: rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(3px);
  pointer-events: none;
}

.phase-card {
  max-width: 22rem;
  padding: 1.5rem 1.75rem;
  background: #fff;
  border-radius: 20px;
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.2);
  text-align: center;
  border: 1px solid rgba(226, 232, 240, 0.9);
}

.phase-card__title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: #0f172a;
}

.phase-card__sub {
  margin: 0.5rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
  line-height: 1.45;
}

.phase-card__num {
  margin-top: 1rem;
  font-size: 3rem;
  font-weight: 800;
  color: #2563eb;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.phase-card__unit {
  font-size: 1rem;
  font-weight: 600;
  color: #64748b;
  margin-left: 0.15rem;
}

/* 结果弹层（同样为底栏留出层叠优先级） */
.result-overlay {
  position: fixed;
  inset: 0;
  z-index: 45;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  padding-bottom: calc(5.5rem + env(safe-area-inset-bottom));
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
  animation: fade-in 0.35s ease;
  pointer-events: none;
}

@keyframes fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.result-card {
  max-width: 24rem;
  padding: 2rem 1.75rem;
  background: linear-gradient(145deg, #fefce8 0%, #fef9c3 50%, #fff 100%);
  border-radius: 24px;
  text-align: center;
  box-shadow: 0 28px 56px rgba(202, 138, 4, 0.25);
  border: 2px solid rgba(250, 204, 21, 0.6);
  pointer-events: auto;
}

.result-card__tag {
  margin: 0;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #a16207;
  font-weight: 700;
}

.result-card__main {
  margin: 0.75rem 0 0;
  font-size: 1.2rem;
  color: #422006;
  line-height: 1.5;
}

.result-card__main strong {
  color: #b45309;
  font-size: 1.35rem;
}

.result-card__opt {
  margin: 1rem 0 0;
  font-size: 0.95rem;
  color: #713f12;
}

/* 玩家条 */
.block {
  margin-bottom: 1.5rem;
}

.players-scroll {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  padding: 0.75rem;
  /* 为右下角聊天按钮留出空隙，避免压住头像区 */
  padding-right: 3rem;
  padding-bottom: 2.75rem;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}

.player-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 4.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: 12px;
  transition:
    background 0.2s,
    box-shadow 0.2s;
}

.player-tile--self {
  background: #eff6ff;
  box-shadow: inset 0 0 0 2px #3b82f6;
}

.player-tile__name {
  font-size: 0.8rem;
  font-weight: 700;
  color: #1e293b;
  text-align: center;
  max-width: 6rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.player-tile__avatar {
  width: 52px;
  height: 52px;
  margin: 0.25rem 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.65),
    0 2px 8px rgba(15, 23, 42, 0.12);
  border: 2px solid rgba(255, 255, 255, 0.85);
}

.player-tile__emoji {
  font-size: 1.65rem;
  line-height: 1;
  user-select: none;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.08));
}

.player-tile--self .player-tile__avatar {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.65),
    0 2px 8px rgba(15, 23, 42, 0.12),
    0 0 0 3px rgba(59, 130, 246, 0.45);
  border-color: #fff;
}

.player-tile__status {
  font-size: 0.68rem;
  color: #64748b;
  text-align: center;
  line-height: 1.2;
  max-width: 5.5rem;
}

.players-empty {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
}

/* 选项区 */
.vote-block--empty {
  padding: 1.5rem;
  background: #fff;
  border-radius: 16px;
  color: #64748b;
  text-align: center;
}

.options-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: center;
  padding: 1rem;
  background: #fff;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  min-height: 5rem;
}

.options-grid--plate .opt-tile {
  border-radius: 999px;
  min-width: 6.5rem;
  min-height: 3rem;
  padding: 0.65rem 1.25rem;
  border: 2px solid #e2e8f0;
  background: radial-gradient(ellipse at 30% 20%, #ffffff 0%, #f1f5f9 45%, #e2e8f0 100%);
  box-shadow:
    0 4px 0 #cbd5e1,
    0 8px 20px rgba(15, 23, 42, 0.08);
}

.options-grid--square .opt-tile {
  border-radius: 14px;
  min-width: 5.5rem;
  min-height: 4rem;
  padding: 0.75rem 1rem;
  border: 2px solid #e2e8f0;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
}

.opt-tile {
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  color: #334155;
  transition:
    transform 0.12s,
    border-color 0.15s,
    background 0.15s,
    box-shadow 0.15s;
}

.opt-tile:hover:not(:disabled) {
  transform: translateY(-2px);
}

.opt-tile:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.opt-tile.picked {
  border-color: #2563eb !important;
  background: linear-gradient(180deg, #3b82f6, #2563eb) !important;
  color: #fff !important;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.45);
}

.opt-tile.mq-on {
  border-color: #ca8a04 !important;
  background: linear-gradient(180deg, #fef9c3, #fde047) !important;
  color: #713f12 !important;
  box-shadow: 0 0 0 4px rgba(234, 179, 8, 0.45);
}

.opt-tile.mq-dim {
  opacity: 0.4;
}

.opt-tile__text {
  display: block;
  text-align: center;
}

/* 底栏：宽度与 .room-page 内容区一致（960 内再减左右 1rem），不超出灰色主栏 */
.bottom-bar-wrap {
  position: fixed;
  left: 50%;
  right: auto;
  bottom: 0;
  transform: translateX(-50%);
  z-index: 101;
  width: min(calc(960px - 2rem), calc(100vw - 2rem));
  max-width: 100%;
  display: flex;
  justify-content: center;
  padding: 0;
  padding-bottom: env(safe-area-inset-bottom);
  box-sizing: border-box;
  pointer-events: none;
}

.bottom-bar {
  pointer-events: auto;
  width: 100%;
  max-width: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.85rem 1.25rem 0.85rem;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(12px);
  border: 1px solid #e2e8f0;
  border-bottom: none;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.1);
}

.bottom-bar__left {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  min-height: 2.75rem;
}

.bottom-bar__right {
  flex-shrink: 0;
}

.btn-assist-wrap {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.assist-pop-layer {
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  width: 5rem;
  height: 3.5rem;
  pointer-events: none;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.assist-pop {
  position: absolute;
  bottom: 0;
  font-size: 1rem;
  font-weight: 800;
  color: #ca8a04;
  text-shadow:
    0 0 2px #fff,
    0 1px 0 #fff;
  animation: assist-pop-burst 0.72s ease-out forwards;
}

@keyframes assist-pop-burst {
  0% {
    opacity: 0;
    transform: translateY(8px) scale(0.5);
  }
  18% {
    opacity: 1;
    transform: translateY(0) scale(1.2);
  }
  100% {
    opacity: 0;
    transform: translateY(-40px) scale(1);
  }
}

.assist-pop-enter-active,
.assist-pop-leave-active {
  transition: none;
}

.bottom-hint {
  font-size: 0.8rem;
  color: #475569;
}
.bottom-hint.muted {
  color: #94a3b8;
}

.btn-rect {
  padding: 0.55rem 1.35rem;
  border-radius: 14px;
  font-size: 0.95rem;
  font-weight: 700;
  border: none;
  cursor: pointer;
  transition:
    transform 0.1s,
    box-shadow 0.15s;
}

.btn-rect--confirm {
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45);
}

.btn-rect--confirm:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  box-shadow: none;
  cursor: not-allowed;
  opacity: 1;
}

.btn-rect--cancel {
  background: linear-gradient(180deg, #f87171, #dc2626);
  color: #fff;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35);
}

.btn-rect--disabled {
  background: #e2e8f0;
  color: #94a3b8;
  cursor: not-allowed;
}

.btn-rect:not(:disabled):active {
  transform: scale(0.97);
}

.btn-assist {
  position: relative;
  width: 5.25rem;
  height: 5.25rem;
  border-radius: 50%;
  border: none;
  cursor: not-allowed;
  background: linear-gradient(145deg, #fde047 0%, #eab308 45%, #ca8a04 100%);
  color: #422006;
  font-weight: 800;
  font-size: 1.1rem;
  box-shadow:
    0 6px 0 #a16207,
    0 12px 24px rgba(202, 138, 4, 0.45),
    inset 0 2px 0 rgba(255, 255, 255, 0.45);
  transition:
    transform 0.08s,
    box-shadow 0.12s,
    filter 0.12s;
}

.btn-assist:not(:disabled) {
  cursor: pointer;
}

.btn-assist:not(:disabled):active {
  transform: translateY(4px);
  box-shadow:
    0 2px 0 #a16207,
    0 6px 16px rgba(202, 138, 4, 0.4),
    inset 0 2px 0 rgba(255, 255, 255, 0.35);
}

.btn-assist:disabled {
  opacity: 0.45;
  filter: grayscale(0.3);
  box-shadow: 0 4px 0 #78716c;
}

.btn-assist--hot:not(:disabled) {
  animation: assist-pulse 0.9s ease-in-out infinite;
}

@keyframes assist-pulse {
  0%,
  100% {
    filter: brightness(1);
  }
  50% {
    filter: brightness(1.08);
  }
}

.btn-assist__label {
  display: block;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.4);
}

.btn-assist__badge {
  position: absolute;
  top: 2px;
  right: 2px;
  min-width: 1.35rem;
  height: 1.35rem;
  padding: 0 5px;
  border-radius: 999px;
  background: linear-gradient(180deg, #f87171, #dc2626);
  color: #fff;
  font-size: 0.72rem;
  font-weight: 800;
  line-height: 1.35rem;
  text-align: center;
  border: 2px solid #fff;
  box-shadow: 0 2px 8px rgba(220, 38, 38, 0.45);
  font-variant-numeric: tabular-nums;
}
</style>
