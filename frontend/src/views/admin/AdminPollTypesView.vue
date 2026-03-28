<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { VueDraggable } from 'vue-draggable-plus'
import adminHttp from '../../api/adminHttp'

const route = useRoute()
const roomId = computed(() => Number(route.params.roomId))

const err = ref('')
const ok = ref('')

const newTitle = ref('新题目')
const newStyle = ref<'plate' | 'square'>('plate')

let newOptUid = 0
function newOptRow(text: string) {
  newOptUid += 1
  return { _uid: newOptUid, text }
}
const newOptItems = ref([newOptRow('选项A'), newOptRow('选项B')])

interface OptRow {
  id: number
  text: string
  sort_order: number
}

interface TypeRow {
  id: number
  title: string
  display_style: string
  sort_order: number
  options: OptRow[]
}

const pollTypes = ref<TypeRow[]>([])
const loadingList = ref(false)
const newOptText = ref<Record<number, string>>({})

const dragOptions = computed(() => ({
  animation: 150,
  disabled: loadingList.value,
  ghostClass: 'sortable-ghost',
  chosenClass: 'sortable-chosen',
}))

/** 每个房间仅一道题；已有题目时需先删除再添加 */
const canAddPollType = computed(() => !loadingList.value && pollTypes.value.length === 0)

function apiErr(e: unknown): string {
  const x = e as { response?: { data?: { detail?: string } } }
  return x.response?.data?.detail || '请求失败'
}

async function loadPollTypes() {
  if (!Number.isFinite(roomId.value) || roomId.value < 1) return
  loadingList.value = true
  err.value = ''
  try {
    const { data } = await adminHttp.get<TypeRow[]>(`/admin/rooms/${roomId.value}/poll-types`)
    pollTypes.value = data
  } catch (e: unknown) {
    err.value = apiErr(e)
  } finally {
    loadingList.value = false
  }
}

async function addPollType() {
  if (!canAddPollType.value) return
  err.value = ''
  ok.value = ''
  const opts = newOptItems.value
    .filter((r) => r.text.trim())
    .map((r, i) => ({ text: r.text.trim(), sort_order: i }))
  if (opts.length < 2) {
    err.value = '至少 2 个非空选项'
    return
  }
  try {
    await adminHttp.post(`/admin/rooms/${roomId.value}/poll-types`, {
      title: newTitle.value,
      display_style: newStyle.value,
      sort_order: pollTypes.value.length,
      options: opts,
    })
    ok.value = '题目已添加'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

async function saveType(t: TypeRow) {
  err.value = ''
  ok.value = ''
  try {
    await adminHttp.patch(`/admin/rooms/${roomId.value}/poll-types/${t.id}`, {
      title: t.title,
      display_style: t.display_style as 'plate' | 'square',
      sort_order: t.sort_order,
    })
    ok.value = '题目已保存'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

async function persistPollTypeOrder(evt?: { oldIndex?: number; newIndex?: number }) {
  if (evt && evt.oldIndex === evt.newIndex) return
  err.value = ''
  ok.value = ''
  pollTypes.value.forEach((t, i) => {
    t.sort_order = i
  })
  try {
    await Promise.all(
      pollTypes.value.map((t, i) =>
        adminHttp.patch(`/admin/rooms/${roomId.value}/poll-types/${t.id}`, {
          title: t.title,
          display_style: t.display_style as 'plate' | 'square',
          sort_order: i,
        }),
      ),
    )
    ok.value = '题目顺序已更新'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
    await loadPollTypes()
  }
}

async function deleteType(id: number) {
  if (!confirm('确定删除该题目及全部选项？')) return
  err.value = ''
  try {
    await adminHttp.delete(`/admin/rooms/${roomId.value}/poll-types/${id}`)
    ok.value = '已删除'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

async function saveOption(typeId: number, o: OptRow) {
  err.value = ''
  ok.value = ''
  try {
    await adminHttp.patch(`/admin/rooms/${roomId.value}/poll-types/${typeId}/options/${o.id}`, {
      text: o.text,
      sort_order: o.sort_order,
    })
    ok.value = '选项已保存'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

async function persistOptionOrder(typeId: number, evt?: { oldIndex?: number; newIndex?: number }) {
  if (evt && evt.oldIndex === evt.newIndex) return
  const t = pollTypes.value.find((x) => x.id === typeId)
  if (!t) return
  err.value = ''
  ok.value = ''
  t.options.forEach((o, i) => {
    o.sort_order = i
  })
  try {
    await Promise.all(
      t.options.map((o, i) =>
        adminHttp.patch(`/admin/rooms/${roomId.value}/poll-types/${typeId}/options/${o.id}`, {
          text: o.text,
          sort_order: i,
        }),
      ),
    )
    ok.value = '选项顺序已更新'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
    await loadPollTypes()
  }
}

async function deleteOption(typeId: number, optionId: number) {
  if (!confirm('确定删除该选项？（每题至少保留 2 项）')) return
  err.value = ''
  try {
    await adminHttp.delete(`/admin/rooms/${roomId.value}/poll-types/${typeId}/options/${optionId}`)
    ok.value = '选项已删除'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

async function addOptionRow(typeId: number) {
  const text = (newOptText.value[typeId] || '').trim()
  if (!text) {
    err.value = '请输入新选项文案'
    return
  }
  err.value = ''
  try {
    const t = pollTypes.value.find((x) => x.id === typeId)
    const sort = t ? t.options.length : 0
    await adminHttp.post(`/admin/rooms/${roomId.value}/poll-types/${typeId}/options`, {
      text,
      sort_order: sort,
    })
    newOptText.value[typeId] = ''
    ok.value = '选项已添加'
    await loadPollTypes()
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

function addNewOptRow() {
  newOptItems.value.push(newOptRow(''))
}

function removeNewOptRow(i: number) {
  if (newOptItems.value.length > 2) {
    newOptItems.value.splice(i, 1)
  }
}

async function openRoom() {
  err.value = ''
  ok.value = ''
  try {
    await adminHttp.patch(`/admin/rooms/${roomId.value}`, { status: 'open' })
    ok.value = '房间已开放，玩家可从房间列表进入'
  } catch (e: unknown) {
    err.value = apiErr(e)
  }
}

watch(
  () => route.params.roomId,
  () => {
    loadPollTypes()
  },
)

onMounted(() => {
  loadPollTypes()
})
</script>

<template>
  <div class="admin-polls">
    <header class="admin-polls__header">
      <div>
        <h1 class="admin-polls__title">题库管理</h1>
        <p class="admin-polls__sub">房间 ID：{{ roomId }}</p>
      </div>
      <button type="button" class="admin-polls__open" @click="openRoom">开放房间供玩家进入</button>
    </header>

    <p v-if="err" class="admin-polls__msg admin-polls__msg--err">{{ err }}</p>
    <p v-if="ok" class="admin-polls__msg admin-polls__msg--ok">{{ ok }}</p>

    <section class="admin-polls__section">
      <h2 class="admin-polls__h2">新建投票题</h2>
      <p class="admin-polls__hint">每题 2～10 个选项；拖动 ⋮⋮ 可调整选项顺序</p>
      <p v-if="pollTypes.length > 0 && !loadingList" class="admin-polls__hint admin-polls__hint--single">
        每个房间仅一道题。若要换题，请先删除下方已有题目。
      </p>
      <div class="admin-polls__grid">
        <label class="admin-polls__field">
          <span>标题</span>
          <input v-model="newTitle" type="text" />
        </label>
        <label class="admin-polls__field">
          <span>展示样式</span>
          <select v-model="newStyle">
            <option value="plate">圆盘 plate</option>
            <option value="square">方块 square</option>
          </select>
        </label>
      </div>
      <VueDraggable
        v-model="newOptItems"
        class="admin-polls__new-opts"
        handle=".poll-new-opt__handle"
        v-bind="dragOptions"
      >
        <div v-for="(row, i) in newOptItems" :key="row._uid" class="poll-new-opt">
          <button
            type="button"
            class="poll-new-opt__handle"
            aria-label="拖动排序"
            tabindex="-1"
          >
            ⋮⋮
          </button>
          <label class="poll-new-opt__main">
            <span class="poll-new-opt__label">选项 {{ i + 1 }}</span>
            <div class="admin-polls__opt-input">
              <input v-model="row.text" type="text" />
              <button v-if="newOptItems.length > 2" type="button" class="btn-tiny" @click="removeNewOptRow(i)">
                删除
              </button>
            </div>
          </label>
        </div>
      </VueDraggable>
      <div class="admin-polls__toolbar">
        <button v-if="newOptItems.length < 10" type="button" class="btn-secondary" @click="addNewOptRow">
          加一行选项
        </button>
        <button
          type="button"
          class="btn-primary"
          :disabled="!canAddPollType"
          :title="canAddPollType ? undefined : '每个房间仅一道题，请先删除已有题目'"
          @click="addPollType"
        >
          添加题目
        </button>
      </div>
    </section>

    <section class="admin-polls__section">
      <h2 class="admin-polls__h2">题目与选项 {{ loadingList ? '…' : '' }}</h2>
      <p class="admin-polls__hint admin-polls__hint--drag">拖动题目或选项左侧的 ⋮⋮ 可调整顺序，松手后自动保存</p>

      <VueDraggable
        v-model="pollTypes"
        class="poll-types-draggable"
        handle=".poll-card__drag-handle"
        v-bind="dragOptions"
        @end="persistPollTypeOrder"
      >
        <article v-for="t in pollTypes" :key="t.id" class="poll-card">
          <div class="poll-card__head">
            <div class="poll-card__head-left">
              <button
                type="button"
                class="poll-card__drag-handle"
                aria-label="拖动调整题目顺序"
                tabindex="-1"
              >
                ⋮⋮
              </button>
              <h3 class="poll-card__title">题目 #{{ t.id }}</h3>
            </div>
            <div class="poll-card__head-actions">
              <button type="button" class="btn-tiny danger" @click="deleteType(t.id)">删除题目</button>
            </div>
          </div>
          <div class="poll-card__fields">
            <label class="admin-polls__field poll-card__field--title">
              <span>标题</span>
              <input v-model="t.title" type="text" />
            </label>
            <label class="admin-polls__field poll-card__field--style">
              <span>样式</span>
              <select v-model="t.display_style">
                <option value="plate">plate</option>
                <option value="square">square</option>
              </select>
            </label>
            <button type="button" class="btn-secondary poll-card__save-type" @click="saveType(t)">保存题目</button>
          </div>

          <div class="poll-card__options">
            <div class="poll-opt-head">
              <span class="poll-opt-head__cell poll-opt-head__cell--handle" aria-hidden="true" />
              <span class="poll-opt-head__cell poll-opt-head__cell--id">ID</span>
              <span class="poll-opt-head__cell poll-opt-head__cell--text">选项文案</span>
              <span class="poll-opt-head__cell poll-opt-head__cell--act">操作</span>
            </div>
            <VueDraggable
              v-model="t.options"
              handle=".poll-opt-row__handle"
              :group="{ name: 'room-' + roomId + '-type-' + t.id, pull: false, put: false }"
              v-bind="dragOptions"
              class="poll-opt-draggable"
              @end="(e) => persistOptionOrder(t.id, e)"
            >
              <div v-for="o in t.options" :key="o.id" class="poll-opt-row">
                <button
                  type="button"
                  class="poll-opt-row__handle"
                  aria-label="拖动调整选项顺序"
                  tabindex="-1"
                >
                  ⋮⋮
                </button>
                <span class="poll-opt-row__id">{{ o.id }}</span>
                <input v-model="o.text" type="text" class="poll-opt-row__text" />
                <div class="poll-opt-row__actions">
                  <button type="button" class="btn-tiny" @click="saveOption(t.id, o)">保存</button>
                  <button type="button" class="btn-tiny danger" @click="deleteOption(t.id, o.id)">删除</button>
                </div>
              </div>
            </VueDraggable>
          </div>
          <div class="poll-card__add-opt">
            <input v-model="newOptText[t.id]" type="text" placeholder="新选项文案" />
            <button
              type="button"
              class="btn-secondary"
              :disabled="(t.options?.length || 0) >= 10"
              @click="addOptionRow(t.id)"
            >
              添加选项
            </button>
          </div>
        </article>
      </VueDraggable>

      <p v-if="!loadingList && pollTypes.length === 0" class="admin-polls__empty">暂无题目，请在上方添加。</p>
    </section>
  </div>
</template>

<style scoped>
.admin-polls {
  max-width: 720px;
  margin: 0 auto;
}

.admin-polls__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.admin-polls__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  color: #0f172a;
}

.admin-polls__sub {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
  color: #64748b;
}

.admin-polls__open {
  padding: 0.5rem 1rem;
  font-size: 0.9rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.admin-polls__open:hover {
  filter: brightness(1.03);
}

.admin-polls__msg {
  margin: 0 0 1rem;
  font-size: 0.9rem;
}

.admin-polls__msg--err {
  color: #b91c1c;
}

.admin-polls__msg--ok {
  color: #15803d;
}

.admin-polls__section {
  margin-bottom: 1.75rem;
  padding: 1.25rem;
  background: #fff;
  border-radius: 14px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}

.admin-polls__h2 {
  margin: 0 0 0.35rem;
  font-size: 1.05rem;
  font-weight: 600;
  color: #0f172a;
}

.admin-polls__hint {
  margin: 0 0 1rem;
  font-size: 0.85rem;
  color: #64748b;
}

.admin-polls__hint--drag {
  margin-top: -0.25rem;
  margin-bottom: 0.75rem;
}

.admin-polls__grid {
  display: grid;
  gap: 1rem;
  margin-bottom: 1rem;
}

@media (min-width: 520px) {
  .admin-polls__grid {
    grid-template-columns: 1fr 1fr;
  }
}

.admin-polls__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.8rem;
  color: #475569;
}

.admin-polls__field input,
.admin-polls__field select {
  padding: 0.45rem 0.6rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-size: 0.95rem;
}

.admin-polls__new-opts {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.poll-new-opt {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}

.poll-new-opt__handle {
  flex-shrink: 0;
  width: 2rem;
  height: 2.25rem;
  margin-top: 1.35rem;
  padding: 0;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.85rem;
  line-height: 1;
  cursor: grab;
}

.poll-new-opt__handle:active {
  cursor: grabbing;
}

.poll-new-opt__main {
  flex: 1;
  min-width: 0;
}

.poll-new-opt__label {
  display: block;
  font-size: 0.8rem;
  color: #475569;
  margin-bottom: 0.25rem;
}

.admin-polls__opt-input {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.admin-polls__opt-input input {
  flex: 1;
  padding: 0.45rem 0.6rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.admin-polls__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.btn-primary {
  padding: 0.5rem 1rem;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 10px;
  cursor: pointer;
}

.btn-primary:disabled {
  cursor: not-allowed;
  color: #94a3b8;
  background: #e2e8f0;
  box-shadow: none;
}

.admin-polls__hint--single {
  margin-top: -0.35rem;
  color: #b45309;
}

.btn-secondary {
  padding: 0.45rem 0.85rem;
  font-size: 0.875rem;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  cursor: pointer;
}

.btn-tiny {
  padding: 0.25rem 0.5rem;
  font-size: 0.8rem;
  border-radius: 6px;
  border: 1px solid #cbd5e1;
  background: #fff;
  cursor: pointer;
}

.btn-tiny.danger {
  border-color: #fecaca;
  color: #b91c1c;
}

.poll-types-draggable {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.poll-card {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px dashed #e2e8f0;
}

.poll-card:first-of-type {
  margin-top: 0.5rem;
  padding-top: 0;
  border-top: none;
}

.poll-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.poll-card__head-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.poll-card__drag-handle {
  flex-shrink: 0;
  width: 2rem;
  height: 2rem;
  padding: 0;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.85rem;
  line-height: 1;
  cursor: grab;
}

.poll-card__drag-handle:active {
  cursor: grabbing;
}

.poll-card__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1e293b;
}

.poll-card__fields {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: flex-end;
  margin-bottom: 1rem;
}

.poll-card__field--title {
  flex: 1 1 200px;
  min-width: 0;
}

.poll-card__field--style {
  flex: 0 1 11rem;
  min-width: 8rem;
}

.poll-card__save-type {
  flex: 0 0 auto;
  white-space: nowrap;
}

.poll-card__options {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}

.poll-opt-draggable {
  display: flex;
  flex-direction: column;
}

.poll-opt-head {
  display: none;
}

@media (min-width: 600px) {
  .poll-opt-head {
    display: grid;
    grid-template-columns: 2rem 3rem minmax(0, 1fr) 9rem;
    gap: 0.5rem;
    align-items: center;
    padding: 0.45rem 0.65rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: #64748b;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
  }
}

.poll-opt-head__cell--act {
  text-align: right;
}

.poll-opt-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.55rem 0.65rem;
  font-size: 0.85rem;
  border-bottom: 1px solid #f1f5f9;
}

.poll-opt-row:last-child {
  border-bottom: none;
}

.poll-opt-row__handle {
  flex-shrink: 0;
  width: 1.75rem;
  height: 1.75rem;
  padding: 0;
  border: 1px dashed #cbd5e1;
  border-radius: 6px;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.7rem;
  line-height: 1;
  cursor: grab;
}

.poll-opt-row__handle:active {
  cursor: grabbing;
}

.poll-opt-row__id {
  flex: 0 0 2.25rem;
  color: #94a3b8;
  font-size: 0.75rem;
  text-align: center;
}

.poll-opt-row__text {
  flex: 1 1 140px;
  min-width: 0;
  padding: 0.4rem 0.55rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.875rem;
}

.poll-opt-row__actions {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.35rem;
  flex: 0 0 auto;
  margin-left: auto;
}

@media (min-width: 600px) {
  .poll-opt-row {
    display: grid;
    grid-template-columns: 2rem 3rem minmax(0, 1fr) 9rem;
    gap: 0.5rem;
    align-items: center;
  }

  .poll-opt-row__id {
    flex: unset;
  }

  .poll-opt-row__text {
    flex: unset;
    min-width: 0;
  }

  .poll-opt-row__actions {
    margin-left: 0;
    justify-content: flex-end;
    width: auto;
  }
}

@media (max-width: 599px) {
  .poll-opt-row__actions {
    width: 100%;
    margin-left: 0;
    justify-content: flex-end;
    padding-left: calc(1.75rem + 0.5rem + 2.25rem + 0.5rem);
    box-sizing: border-box;
  }
}

.poll-card__add-opt {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
  align-items: center;
}

.poll-card__add-opt input {
  flex: 1;
  min-width: 140px;
  padding: 0.4rem 0.6rem;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
}

.admin-polls__empty {
  margin: 1rem 0 0;
  color: #64748b;
  font-size: 0.9rem;
}

:deep(.sortable-ghost) {
  opacity: 0.45;
  background: #eff6ff !important;
}

:deep(.sortable-chosen) {
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.12);
}
</style>
