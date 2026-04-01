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
        <el-input v-model="form.host" placeholder="192.168.1.101" />
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

      <el-divider content-position="left">
        <el-space>
          节点 B（双机专用）
          <el-switch v-model="isDual" active-text="启用" inactive-text="单机" @change="onDualModeChange" />
        </el-space>
      </el-divider>

      <template v-if="isDual">
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

      <el-divider content-position="left">SSH 认证（仅保存时写入，之后不可改）</el-divider>
      <el-form-item label="SSH 用户" prop="ssh_user">
        <el-input v-model="form.ssh_user" placeholder="appadmin" />
      </el-form-item>
      <el-form-item label="SSH 密码" prop="ssh_password">
        <el-input v-model="form.ssh_password" type="password" show-password placeholder="sudo 密码" />
      </el-form-item>
      <el-form-item label="SSH 端口" prop="ssh_port">
        <el-input-number v-model="form.ssh_port" :min="1" :max="65535" style="width:100%" />
      </el-form-item>

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
    }
  }
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { ...form.value }
    payload.name = (payload.name || '').trim()
    payload.model_api_name = (payload.model_api_name || '').trim()
    payload.enabled = !!payload.enabled
    payload.gateway_enabled = !!payload.gateway_enabled
    if (isDual.value && !payload.exec_cmd_b) {
      payload.exec_cmd_b = payload.exec_cmd
    }
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
</style>
