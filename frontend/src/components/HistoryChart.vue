<template>
  <el-dialog title="检测历史" v-model="visible" width="800px" @close="$emit('close')">
    <v-chart :option="chartOption" style="height:320px" autoresize />
    <el-table :data="rows" size="small" max-height="260" style="margin-top:16px">
      <el-table-column label="时间" prop="checked_at" width="180" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="tagType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="延迟(ms)" prop="latency_ms" width="100" />
      <el-table-column label="错误信息" prop="error_msg" show-overflow-tooltip />
    </el-table>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getHistory } from '../api/index.js'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps({
  modelValue: Boolean,
  modelId: { type: Number, default: null },
  modelName: { type: String, default: '' },
})
const emit = defineEmits(['close'])
const visible = ref(props.modelValue)
watch(() => props.modelValue, v => (visible.value = v))

const rows = ref([])

watch(() => props.modelId, async id => {
  if (!id) return
  const res = await getHistory(id, 100)
  rows.value = res.data.slice().reverse()
}, { immediate: true })

const tagType = s => ({ ok: 'success', error: 'danger', timeout: 'warning', unknown: 'info' }[s] ?? 'info')

const chartOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: rows.value.map(r => r.checked_at.slice(11, 19)), axisLabel: { rotate: 30 } },
  yAxis: { type: 'value', name: '延迟 ms' },
  series: [{
    name: '延迟',
    type: 'line',
    smooth: true,
    data: rows.value.map(r => r.latency_ms),
    itemStyle: { color: '#409EFF' },
  }],
}))
</script>
