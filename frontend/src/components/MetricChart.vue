<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import { init, use, type EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

use([BarChart, GridComponent, CanvasRenderer])

const props = defineProps<{
  treatment: number | null
  control: number | null
  metricLabel: string
  metricUnit: string
}>()

const chartRoot = ref<HTMLDivElement | null>(null)
let chart: EChartsType | null = null

function renderChart() {
  if (!chartRoot.value) return
  chart ||= init(chartRoot.value)
  const treatment = props.treatment ?? 0
  const control = props.control ?? 0
  chart.setOption({
    animationDuration: 500,
    grid: { left: 12, right: 18, top: 12, bottom: 6, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#687078' },
      splitLine: { lineStyle: { color: '#e7eaec' } },
    },
    yAxis: {
      type: 'category',
      data: ['常规日', '提醒日'],
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: '#263238', fontSize: 13 },
    },
    series: [
      {
        type: 'bar',
        data: [
          { value: control, itemStyle: { color: '#93a5ad' } },
          { value: treatment, itemStyle: { color: '#167f78' } },
        ],
        barWidth: 22,
        label: { show: true, position: 'right', color: '#263238', formatter: `{c} ${props.metricUnit}` },
      },
    ],
  })
}

function resizeChart() {
  chart?.resize()
}

onMounted(() => {
  renderChart()
  window.addEventListener('resize', resizeChart)
})
watch(() => [props.treatment, props.control], renderChart)
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})
</script>

<template>
  <div
    ref="chartRoot"
    class="metric-chart"
    role="img"
    :aria-label="`提醒日与常规日${metricLabel}对比图`"
  ></div>
</template>
