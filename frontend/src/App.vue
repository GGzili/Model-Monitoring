<template>
  <el-container style="min-height:100vh;background:#f0f2f5">
    <!-- 顶栏 -->
    <el-header style="background:#001529;flex-direction:column;align-items:stretch;padding:12px 20px;height:auto">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <span style="color:#fff;font-size:18px;font-weight:600">模型监测平台</span>
        <el-button type="primary" size="small" @click="openAdd">+ 添加模型</el-button>
      </div>
      <div style="color:#a6adb4;font-size:12px;margin-top:8px;line-height:1.5">
        网关仅转发<strong style="color:#e6f0ff">本页配置的模型</strong>：请求 <code style="background:#ffffff14;padding:2px 6px;border-radius:4px">POST /v1/chat/completions</code>，
        参数 <code style="background:#ffffff14;padding:2px 6px;border-radius:4px">model</code> 须与各卡片「网关调用名」一致；须<strong style="color:#e6f0ff">启用监测且开放网关</strong>。
        每个模型单独维护<strong style="color:#e6f0ff">最大并发</strong>与<strong style="color:#e6f0ff">消息队列</strong>（超出并发先入队，队列满返回 503）。
      </div>
    </el-header>

    <el-main>
      <!-- 汇总卡片 -->
      <el-row :gutter="16" style="margin-bottom:24px">
        <el-col :span="6">
          <el-card shadow="never">
            <div class="stat"><div class="stat-num">{{ total }}</div><div class="stat-label">模型总数</div></div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="stat"><div class="stat-num ok">{{ okCount }}</div><div class="stat-label">正常</div></div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="stat"><div class="stat-num err">{{ errCount }}</div><div class="stat-label">异常</div></div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never">
            <div class="stat"><div class="stat-num unknown">{{ unknownCount }}</div><div class="stat-label">未知</div></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 模型卡片列表 -->
      <el-row :gutter="16">
        <el-col :span="8" v-for="m in dashboard" :key="m.id" style="margin-bottom:16px">
          <el-card shadow="hover">
            <template #header>
              <div style="display:flex;align-items:center;justify-content:space-between">
                <div style="display:flex;align-items:center;gap:6px">
                  <span style="font-weight:600">{{ displayName(m) }}</span>
                  <el-tag v-if="m.is_dual" type="warning" size="small" effect="plain">双机</el-tag>
                </div>
                <el-tag :type="statusTag(m.last_status)" effect="dark" size="small">
                  {{ statusLabel(m.last_status) }}
                </el-tag>
              </div>
            </template>

            <div class="info-row"><span class="label">延迟</span>
              <span>{{ m.last_latency_ms != null ? m.last_latency_ms + ' ms' : '-' }}</span>
            </div>
            <div class="info-row"><span class="label">检测时间</span>
              <span>{{ m.last_checked_at || '-' }}</span>
            </div>
            <div class="info-row gateway-block">
              <span class="label">网关调用名</span>
              <span class="gateway-call">
                <code>{{ gatewayCallName(m) }}</code>
                <el-button
                  v-if="gatewayRoutable(m)"
                  type="primary"
                  link
                  size="small"
                  @click="copyCallName(m)"
                >
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </span>
            </div>
            <div class="info-row"><span class="label">网关 / 并发 / 队列</span>
              <span>{{ gatewaySummary(m) }}</span>
            </div>

            <el-divider style="margin:12px 0" />

            <el-space wrap>
              <el-button size="small" @click="handleCheck(m)" :loading="checking[m.id]">
                <el-icon><Refresh /></el-icon> 立即检测
              </el-button>
              <el-button size="small" type="warning" @click="handleRestart(m)" :loading="restarting[m.id]">
                <el-icon><VideoPlay /></el-icon> 重启模型
              </el-button>
              <el-button size="small" type="info" @click="openHistory(m)">
                <el-icon><DataLine /></el-icon> 历史
              </el-button>
              <el-button size="small" type="primary" plain @click="openEdit(m)">
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button size="small" type="danger" plain @click="handleDelete(m)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-space>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </el-container>

  <!-- 添加 / 编辑 分两个组件挂载，避免单组件分支在部署缓存下走错 -->
  <ModelFormAdd
    v-if="formVisible && !dialogIsEdit"
    :key="'add-' + formDialogKey"
    :model-value="formVisible"
    @close="formVisible = false"
    @saved="load"
  />
  <ModelFormEdit
    v-if="formVisible && dialogIsEdit && editTarget"
    :key="'edit-' + formDialogKey"
    :model-value="formVisible"
    :model="editTarget"
    @close="formVisible = false"
    @saved="load"
  />

  <!-- 历史图表 -->
  <HistoryChart
    v-if="historyVisible"
    :model-value="historyVisible"
    :model-id="historyTarget?.id"
    :model-name="historyTarget ? displayName(historyTarget) : ''"
    @close="historyVisible = false"
  />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getDashboard, checkNow, restartModel, deleteModel } from './api/index.js'
import { DocumentCopy } from '@element-plus/icons-vue'
import ModelFormAdd from './components/ModelFormAdd.vue'
import ModelFormEdit from './components/ModelFormEdit.vue'
import HistoryChart from './components/HistoryChart.vue'

const dashboard = ref([])
const checking  = ref({})
const restarting = ref({})
const formVisible   = ref(false)
const historyVisible = ref(false)
const editTarget    = ref(null)
/** 与 editTarget 同步：点「编辑」为 true，点「添加」为 false，避免子组件靠 id 推断失败 */
const dialogIsEdit  = ref(false)
const historyTarget = ref(null)
/** 每次打开添加/编辑递增，强制重挂载表单，避免 el-switch 等状态错乱 */
const formDialogKey = ref(0)

const total        = computed(() => dashboard.value.length)
const okCount      = computed(() => dashboard.value.filter(m => m.last_status === 'ok').length)
const errCount     = computed(() => dashboard.value.filter(m => ['error','timeout'].includes(m.last_status)).length)
const unknownCount = computed(() => dashboard.value.filter(m => m.last_status === 'unknown').length)

const statusTag   = s => ({ ok: 'success', error: 'danger', timeout: 'warning' }[s] ?? 'info')
const statusLabel = s => ({ ok: '正常', error: '异常', timeout: '超时', unknown: '未知' }[s] ?? s)

function truthy(v) {
  return v === true || v === 1 || v === '1'
}

/** 卡片列表展示名：有显示名称用名称，否则用 API 模型名 */
function displayName(m) {
  const n = (m.name || '').trim()
  return n || (m.model_api_name || '').trim() || '未命名'
}

/** 网关 / 客户端请求的 model 字段，与 API 模型名一致 */
function gatewayCallName(m) {
  const s = (m.model_api_name || '').trim()
  return s || displayName(m)
}

/** 监测启用且开放网关时，该模型才接受 /v1 转发 */
function gatewayRoutable(m) {
  return truthy(m.enabled) && truthy(m.gateway_enabled)
}

function gatewaySummary(m) {
  if (!truthy(m.enabled)) return '监测未启用（请打开检测设置里的「启用」）'
  if (!truthy(m.gateway_enabled)) return '网关未开放'
  const c = m.gateway_max_concurrent ?? 1
  const q = m.gateway_max_queue
  const qStr = q === 0 || q === '0' ? '队列不限长' : `队列最多等 ${q} 个`
  return `已开放 · 并发 ${c} · ${qStr}`
}

async function copyCallName(m) {
  const t = gatewayCallName(m)
  try {
    await navigator.clipboard.writeText(t)
    ElMessage.success('已复制网关调用名：' + t)
  } catch {
    ElMessage.error('复制失败，请手动选择复制')
  }
}

async function load() {
  const res = await getDashboard()
  dashboard.value = res.data
}

async function handleCheck(m) {
  checking.value[m.id] = true
  try {
    await checkNow(m.id)
    await load()
    ElMessage.success('检测完成')
  } catch (e) {
    ElMessage.error('检测失败：' + (e.response?.data?.detail ?? e.message))
  } finally {
    checking.value[m.id] = false
  }
}

async function handleRestart(m) {
  await ElMessageBox.confirm(
    m.is_dual
      ? `确认重启「${displayName(m)}」？\n将同时在两台服务器上执行 docker restart + 容器内启动命令。`
      : `确认重启「${displayName(m)}」？\n将执行 docker restart + 容器内启动命令。`,
    '重启确认', { type: 'warning' }
  )
  restarting.value[m.id] = true
  try {
    const res = await restartModel(m.id)
    if (res.data.success) {
      ElMessage.success('重启成功：' + res.data.message)
    } else {
      ElMessage.error('重启失败：' + res.data.message)
    }
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('请求失败：' + (e.response?.data?.detail ?? e.message))
  } finally {
    restarting.value[m.id] = false
  }
}

async function handleDelete(m) {
  await ElMessageBox.confirm(`确认删除「${displayName(m)}」？`, '删除确认', { type: 'warning' })
  await deleteModel(m.id)
  ElMessage.success('已删除')
  await load()
}

function openAdd() {
  editTarget.value = null
  dialogIsEdit.value = false
  formDialogKey.value += 1
  formVisible.value = true
}
function openEdit(m) {
  editTarget.value = m
  dialogIsEdit.value = true
  formDialogKey.value += 1
  formVisible.value = true
}
function openHistory(m) { historyTarget.value = m; historyVisible.value = true }

let timer
onMounted(() => { load(); timer = setInterval(load, 30000) })
onUnmounted(() => clearInterval(timer))
</script>

<style>
body { margin: 0; font-family: sans-serif; }
.stat { text-align: center; padding: 8px 0; }
.stat-num { font-size: 32px; font-weight: 700; }
.stat-num.ok  { color: #67c23a; }
.stat-num.err { color: #f56c6c; }
.stat-num.unknown { color: #909399; }
.stat-label { font-size: 13px; color: #909399; margin-top: 4px; }
.info-row { display: flex; justify-content: space-between; font-size: 13px;
            padding: 3px 0; border-bottom: 1px solid #f5f5f5; }
.info-row .label { color: #909399; }
.gateway-block { align-items: flex-start; }
.gateway-call { display: flex; align-items: center; gap: 4px; text-align: right; flex-wrap: wrap; justify-content: flex-end; max-width: 68%; }
.gateway-call code { font-size: 12px; background: #f4f4f5; padding: 2px 8px; border-radius: 4px; word-break: break-all; }
</style>
