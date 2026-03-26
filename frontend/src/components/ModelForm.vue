<template>
  <el-dialog :title="isEdit ? '编辑模型' : '添加模型'" v-model="visible" width="680px" @close="$emit('close')">
    <el-form :model="form" :rules="rules" ref="formRef" label-width="130px">

      <el-divider content-position="left">基本信息</el-divider>
      <el-form-item label="名称" prop="name">
        <el-input v-model="form.name" placeholder="如：DeepSeek-V3.1 (双机)" />
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
  host: '', port: 8000, container: '', exec_cmd: '',
  host_b: '', port_b: 8000, container_b: '', exec_cmd_b: '',
  ssh_user: 'root', ssh_password: '', ssh_port: 22,
  interval: 300, enabled: true,
})
const form = ref(defaultForm())

watch(() => props.editData, d => {
  if (d) {
    isEdit.value = true
    form.value = { ...d }
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
