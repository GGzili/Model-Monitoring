<template>
  <el-dialog
    title="调整运行参数"
    v-model="visible"
    width="680px"
    destroy-on-close
    @close="$emit('close')"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
      <p class="edit-mode-hint">
        连接信息、API 模型名与 SSH 不在此修改；仅可调整网关与队列。若需改地址、SSH 端口或模型 ID，请删除该模型后重新添加。
      </p>
      <el-divider content-position="left">网关与消息队列</el-divider>
      <el-form-item label="开放网关">
        <el-switch
          v-model="form.gateway_enabled"
          :active-value="true"
          :inactive-value="false"
          active-text="是"
          inactive-text="否"
        />
        <div class="hint">关闭后该 ID 不会出现在 <code>/v1/models</code>。</div>
      </el-form-item>
      <el-form-item label="最大并发" prop="gateway_max_concurrent">
        <el-input-number v-model="form.gateway_max_concurrent" :min="1" :max="256" style="width:100%" />
        <div class="hint">同时转发到后端的请求数。</div>
      </el-form-item>
      <el-form-item label="消息队列容量" prop="gateway_max_queue">
        <el-input-number v-model="form.gateway_max_queue" :min="0" :max="100000" style="width:100%" />
        <div class="hint">0 表示排队不封顶；满则 503。</div>
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
import { updateModel } from '../api/index.js'

const props = defineProps({
  modelValue: Boolean,
  model: { type: Object, required: true },
})
const emit = defineEmits(['close', 'saved'])

const visible = ref(props.modelValue)
const formRef = ref()
const saving = ref(false)

function apiBool(v) {
  if (v === true || v === 1 || v === '1') return true
  if (v === false || v === 0 || v === '0') return false
  return Boolean(v)
}

const form = ref({
  id: null,
  gateway_enabled: true,
  gateway_max_concurrent: 1,
  gateway_max_queue: 64,
})

const rules = {
  gateway_max_concurrent: [{ required: true, message: '请设置最大并发' }],
  gateway_max_queue: [{ required: true, message: '请设置队列容量' }],
}

function applyModel(m) {
  if (!m) return
  form.value = {
    id: m.id,
    gateway_enabled: apiBool(m.gateway_enabled),
    gateway_max_concurrent: m.gateway_max_concurrent ?? 1,
    gateway_max_queue: m.gateway_max_queue ?? 64,
  }
}

watch(
  () => [props.modelValue, props.model],
  () => {
    visible.value = props.modelValue
    if (props.modelValue && props.model) applyModel(props.model)
  },
  { immediate: true, deep: true },
)

async function submit() {
  await formRef.value.validate()
  saving.value = true
  try {
    await updateModel(form.value.id, {
      gateway_enabled: !!form.value.gateway_enabled,
      gateway_max_concurrent: form.value.gateway_max_concurrent,
      gateway_max_queue: form.value.gateway_max_queue,
    })
    emit('saved')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.edit-mode-hint {
  font-size: 13px;
  color: #606266;
  line-height: 1.55;
  margin: 0 0 16px;
  padding: 10px 12px;
  background: #f4f4f5;
  border-radius: 6px;
}
.hint { font-size: 12px; color: #909399; margin-top: 4px; line-height: 1.45; }
.hint code { background: #f4f4f5; padding: 0 4px; border-radius: 3px; font-size: 11px; }
</style>
