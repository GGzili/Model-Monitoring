<template>
  <el-dialog
    title="添加模型"
    v-model="visible"
    width="680px"
    destroy-on-close
    @close="$emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="formRules" label-width="140px">
      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="API 模型名" prop="model_api_name">
        <el-input v-model="form.model_api_name" placeholder="请求体 model 字段，须与推理服务一致，如 qwen2.5-72b-vl" />
      </el-form-item>
      <el-form-item label="显示名称" prop="name">
        <el-input v-model="form.name" placeholder="可选；留空则卡片与列表使用 API 模型名" />
      </el-form-item>

      <el-divider content-position="left">主节点（节点 A）</el-divider>
      <el-form-item label="服务器 IP" prop="host">
        <el-input v-model="form.host" placeholder="如 10.0.0.1" />
      </el-form-item>
      <el-form-item label="检测端口" prop="port">
        <el-input-number v-model="form.port" :min="1" :max="65535" style="width:100%" />
      </el-form-item>
      <el-form-item label="容器名" prop="container">
        <el-input v-model="form.container" placeholder="docker 容器名" />
      </el-form-item>
      <el-form-item label="容器内启动命令" prop="exec_cmd">
        <el-input
          v-model="form.exec_cmd"
          type="textarea"
          :rows="4"
          placeholder="在容器内执行的命令，如：\ncd /usr/local/... && ./bin/mindieservice_daemon"
        />
      </el-form-item>

      <el-divider content-position="left">SSH 认证 — 节点 A（单机时仅此一组；仅保存时写入，之后不可改）</el-divider>
      <el-form-item label="SSH 用户" prop="ssh_user">
        <el-input v-model="form.ssh_user" placeholder="appadmin" />
      </el-form-item>
      <el-form-item label="SSH 密码" prop="ssh_password">
        <el-input v-model="form.ssh_password" type="password" show-password placeholder="sudo 密码" />
      </el-form-item>
      <el-form-item label="SSH 端口" prop="ssh_port">
        <el-input-number v-model="form.ssh_port" :min="1" :max="65535" style="width:100%" />
        <div class="hint">sshd 的端口，与上方「检测端口」（HTTP 推理服务）无关；非 22 时请填实际映射端口。</div>
      </el-form-item>

      <el-divider content-position="left">
        <el-space>
          双机部署（节点 B）
          <el-switch
            v-model="isDual"
            active-text="双机"
            inactive-text="单机"
            @change="onDualModeChange"
          />
        </el-space>
      </el-divider>
      <p v-if="!isDual" class="dual-hint">保持「单机」时只需上方节点 A 与一套 SSH；打开「双机」后将出现节点 B 的地址与<strong>第二套 SSH</strong>（可与 A 相同）。</p>

      <template v-if="isDual">
        <el-divider content-position="left">SSH 认证 — 节点 B（可选）</el-divider>
        <div class="section-desc">
          与节点 A 的 SSH 分开配置：用户名为空表示 B 与 A 使用同一账号、密码与端口；若 B 机器账号不同，请填写 B 的用户名（密码、端口可留空以沿用 A）。
        </div>
        <el-form-item label="SSH 用户 (B)">
          <el-input v-model="form.ssh_user_b" placeholder="留空则与节点 A 相同" />
        </el-form-item>
        <el-form-item label="SSH 密码 (B)">
          <el-input v-model="form.ssh_password_b" type="password" show-password placeholder="留空则与节点 A 相同" />
        </el-form-item>
        <el-form-item label="SSH 端口 (B)">
          <el-input-number v-model="form.ssh_port_b" :min="0" :max="65535" style="width:100%" />
          <div class="hint">填 0 表示与节点 A 的 SSH 端口相同。</div>
        </el-form-item>

        <el-divider content-position="left">节点 B — 服务器与容器</el-divider>
        <el-form-item label="服务器 IP (B)" prop="host_b">
          <el-input v-model="form.host_b" placeholder="192.168.1.102" />
        </el-form-item>
        <el-form-item label="检测端口 (B)" prop="port_b">
          <el-input-number v-model="form.port_b" :min="1" :max="65535" style="width:100%" />
        </el-form-item>
        <el-form-item label="容器名 (B)" prop="container_b">
          <el-input v-model="form.container_b" placeholder="docker 容器名" />
        </el-form-item>
        <el-form-item label="容器内启动命令 (B)">
          <el-input
            v-model="form.exec_cmd_b"
            type="textarea"
            :rows="4"
            placeholder="节点 B 的启动命令，留空则与节点 A 相同"
          />
        </el-form-item>
      </template>

      <el-divider content-position="left">网关与消息队列</el-divider>
      <div class="section-desc">
        客户端 <code>POST /v1/chat/completions</code> 的 <code>model</code> 须与上方 <strong>API 模型名</strong> 一致。
      </div>
      <el-form-item label="开放网关">
        <el-switch
          v-model="form.gateway_enabled"
          :active-value="true"
          :inactive-value="false"
          active-text="是"
          inactive-text="否"
        />
        <div class="hint">须同时开启下方「启用」；关闭后该 ID 不会出现在 <code>/v1/models</code>。</div>
      </el-form-item>
      <el-form-item label="最大并发" prop="gateway_max_concurrent">
        <el-input-number v-model="form.gateway_max_concurrent" :min="1" :max="256" style="width:100%" />
        <div class="hint">同时转发到后端的请求数；超出部分在本模型队列等待。</div>
      </el-form-item>
      <el-form-item label="消息队列容量" prop="gateway_max_queue">
        <el-input-number v-model="form.gateway_max_queue" :min="0" :max="100000" style="width:100%" />
        <div class="hint">0 表示排队长度不封顶；满则 503。</div>
      </el-form-item>

      <el-divider content-position="left">检测设置</el-divider>
      <el-form-item label="检测间隔(秒)" prop="interval">
        <el-input-number v-model="form.interval" :min="30" :step="30" style="width:100%" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" :active-value="true" :inactive-value="false" />
        <div class="hint">关闭后不探测、不参与网关。</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createModel } from '../api/index.js'

const props = defineProps({
  modelValue: Boolean,
})
const emit = defineEmits(['close', 'saved'])

const visible = ref(props.modelValue)
const formRef = ref()
const saving = ref(false)
const isDual = ref(false)
const syncingDualFromData = ref(false)

const defaultForm = () => ({
  name: '',
  model_api_name: '',
  host: '', port: 8000, container: '', exec_cmd: '',
  host_b: '', port_b: 8000, container_b: '', exec_cmd_b: '',
  ssh_user: 'root', ssh_password: '', ssh_port: 22,
  ssh_user_b: '', ssh_password_b: '', ssh_port_b: 0,
  interval: 300, enabled: true,
  gateway_enabled: true, gateway_max_concurrent: 1, gateway_max_queue: 64,
})
const form = ref(defaultForm())

const formRules = {
  model_api_name: [
    { required: true, message: '请填写 API 模型名' },
    { min: 1, message: '不能为空', trigger: 'blur' },
  ],
  host: [{ required: true, message: '请填写主节点 IP' }],
  port: [{ required: true }],
  container: [{ required: true, message: '请填写容器名' }],
  ssh_user: [{ required: true, message: '请填写 SSH 用户' }],
  ssh_password: [{ required: true, message: '请填写 SSH 密码' }],
  interval: [{ required: true, message: '请设置检测间隔' }],
  gateway_max_concurrent: [{ required: true }],
  gateway_max_queue: [{ required: true }],
}

watch(
  () => props.modelValue,
  (v) => {
    visible.value = v
    if (v) {
      form.value = defaultForm()
      isDual.value = false
    }
  },
  { immediate: true },
)

function onDualModeChange(on) {
  if (syncingDualFromData.value) return
  if (!on) {
    form.value = {
      ...form.value,
      host_b: '',
      port_b: 8000,
      container_b: '',
      exec_cmd_b: '',
      ssh_user_b: '',
      ssh_password_b: '',
      ssh_port_b: 0,
    }
  }
}

async function submit() {
  await formRef.value.validate()
  const sp = Number(form.value.ssh_port)
  if (!Number.isFinite(sp) || sp < 1 || sp > 65535) {
    ElMessage.error('请填写有效的 SSH 端口（1–65535）')
    return
  }
  const f = form.value
  const payload = {
    name: (f.name || '').trim(),
    model_api_name: (f.model_api_name || '').trim(),
    host: f.host,
    port: Number(f.port),
    container: f.container,
    exec_cmd: f.exec_cmd || '',
    host_b: '',
    port_b: 0,
    container_b: '',
    exec_cmd_b: '',
    ssh_user: f.ssh_user,
    ssh_password: f.ssh_password,
    ssh_port: Math.trunc(sp),
    ssh_user_b: '',
    ssh_password_b: '',
    ssh_port_b: 0,
    interval: Number(f.interval),
    enabled: !!f.enabled,
    gateway_enabled: !!f.gateway_enabled,
    gateway_max_concurrent: Number(f.gateway_max_concurrent),
    gateway_max_queue: Number(f.gateway_max_queue),
  }
  if (isDual.value) {
    const spb = Number(f.ssh_port_b)
    if (!Number.isFinite(spb) || spb < 0 || spb > 65535) {
      ElMessage.error('节点 B SSH 端口须为 0–65535（0 表示与 A 相同）')
      return
    }
    payload.host_b = (f.host_b || '').trim()
    payload.port_b = Number(f.port_b)
    payload.container_b = f.container_b || ''
    payload.exec_cmd_b = f.exec_cmd_b || ''
    payload.ssh_user_b = f.ssh_user_b || ''
    payload.ssh_password_b = f.ssh_password_b || ''
    payload.ssh_port_b = Math.trunc(spb)
    if (!payload.exec_cmd_b) {
      payload.exec_cmd_b = payload.exec_cmd
    }
  }
  saving.value = true
  try {
    await createModel(payload)
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.section-desc { font-size: 12px; color: #606266; margin: -8px 0 12px; line-height: 1.5; }
.section-desc code { background: #f4f4f5; padding: 1px 6px; border-radius: 4px; font-size: 11px; }
.hint { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.45; }
.hint code { background: #f4f4f5; padding: 0 4px; border-radius: 3px; font-size: 11px; }
.dual-hint { font-size: 12px; color: #909399; margin: -8px 0 12px; line-height: 1.5; }
</style>
