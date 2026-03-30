<template>
  <el-dialog :title="isEdit ? '编辑模型' : '添加模型'" v-model="visible" width="680px" @close="$emit('close')">
    <el-form :model="form" :rules="rules" ref="formRef" label-width="130px">

      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="如：DeepSeek-V3.1 (双机)" />
      </el-form-item>
      <el-form-item label="API 模型名" prop="model_api_name">
        <el-input v-model="form.model_api_name" placeholder="推理服务中的模型 ID，如：DSV3.1（留空则使用名称）" />
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
          type="textarea" :rows="4"
          placeholder="在容器内执行的命令，如：\ncd /usr/local/... && ./bin/mindieservice_daemon"
        />
      </el-form-item>

      <el-divider content-position="left">
        <el-space>
          节点 B（双机专用）
          <el-switch v-model="isDual" active-text="启用" inactive-text="单机" />
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
            type="textarea" :rows="4"
            placeholder="节点 B 的启动命令，留空则与节点 A 相同"
          />
        </el-form-item>
      </template>

      <el-divider content-position="left">SSH 认证</el-divider>
      <el-form-item label="SSH 用户" prop="ssh_user">
        <el-input v-model="form.ssh_user" placeholder="appadmin" />
      </el-form-item>
      <el-form-item label="SSH 密码" prop="ssh_password">
        <el-input v-model="form.ssh_password" type="password" show-password placeholder="sudo 密码" />
      </el-form-item>
      <el-form-item label="SSH 端口" prop="ssh_port">
        <el-input-number v-model="form.ssh_port" :min="1" :max="65535" style="width:100%" />
      </el-form-item>

      <el-divider content-position="left">网关与消息队列（每模型独立）</el-divider>
      <div class="section-desc">
        仅此处配置的模型可通过本站 <code>/v1/chat/completions</code> 访问；每个模型各自维护并发上限与等待队列，互不影响。
        <span class="warn-inline">「API 模型名」留空时网关调用名等于「名称」；请勿让多条配置使用相同调用名（先匹配到的生效）。</span>
      </div>
      <el-form-item label="开放网关">
        <el-switch v-model="form.gateway_enabled" active-text="是" inactive-text="否" />
        <div class="hint">关闭后该模型不会出现在 <code>/v1/models</code>，且请求 <code>model</code> 匹配本配置时将 404。</div>
      </el-form-item>
      <el-form-item label="最大并发" prop="gateway_max_concurrent">
        <el-input-number v-model="form.gateway_max_concurrent" :min="1" :max="256" style="width:100%" />
        <div class="hint">同时转发到后端的请求数。超出部分进入<strong>本模型</strong>的消息队列等待（FIFO），不会打到其他模型。</div>
      </el-form-item>
      <el-form-item label="消息队列容量" prop="gateway_max_queue">
        <el-input-number v-model="form.gateway_max_queue" :min="0" :max="100000" style="width:100%" />
        <div class="hint">等待槽上限（正在排队、尚未获得并发名额的请求数）。满则新请求立即 503；<strong>0</strong> 表示不限制队列长度（慎用）。</div>
      </el-form-item>

      <el-divider content-position="left">检测设置</el-divider>
      <el-form-item label="检测间隔(秒)" prop="interval">
        <el-input-number v-model="form.interval" :min="30" :step="30" style="width:100%" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>

    </el-form>
    <template #footer>
      <el-button @click="$emit('close')">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { createModel, updateModel } from '../api/index.js'

const props = defineProps({
  modelValue: Boolean,
  editData: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

const visible = ref(props.modelValue)
watch(() => props.modelValue, v => (visible.value = v))

const isEdit  = ref(false)
const saving  = ref(false)
const formRef = ref()
const isDual  = ref(false)

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

watch(() => props.editData, d => {
  if (d) {
    isEdit.value = true
    form.value = { ...defaultForm(), ...d }
    isDual.value = !!d.host_b
  } else {
    isEdit.value = false
    form.value = defaultForm()
    isDual.value = false
  }
}, { immediate: true })

// 关闭双机时清空 B 节点字段
watch(isDual, v => {
  if (!v) {
    form.value.host_b = ''
    form.value.port_b = 8000
    form.value.container_b = ''
    form.value.exec_cmd_b = ''
  }
})

const rules = {
  name:         [{ required: true, message: '请填写名称' }],
  host:         [{ required: true, message: '请填写主节点 IP' }],
  port:         [{ required: true }],
  container:    [{ required: true, message: '请填写容器名' }],
  ssh_user:     [{ required: true, message: '请填写 SSH 用户' }],
  ssh_password: [{ required: true, message: '请填写 SSH 密码' }],
}

async function submit() {
  await formRef.value.validate()
  saving.value = true
  // 双机时若 B 的启动命令为空，复用 A 的
  const payload = { ...form.value }
  if (isDual.value && !payload.exec_cmd_b) {
    payload.exec_cmd_b = payload.exec_cmd
  }
  try {
    if (isEdit.value) {
      await updateModel(payload.id, payload)
    } else {
      await createModel(payload)
    }
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
.warn-inline { display: block; margin-top: 6px; color: #e6a23c; }
.hint { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.45; }
.hint code { background: #f4f4f5; padding: 0 4px; border-radius: 3px; font-size: 11px; }
</style>
