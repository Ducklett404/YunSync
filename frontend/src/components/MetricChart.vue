<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  treatment: number | null
  control: number | null
  treatmentMedian?: number | null
  controlMedian?: number | null
  metricLabel: string
  metricUnit: string
}>()

const chartRoot = ref<HTMLDivElement | null>(null)
const hasData = computed(() => props.treatment !== null || props.control !== null)
let chart: EChartsType | null = null

function renderChart() {
  if (!chartRoot.value) return
  chart ||= init(chartRoot.value)
  const treatment = props.treatment ?? 0
  const control = props.control ?? 0
  const treatmentMedian = props.treatmentMedian ?? 0
  const controlMedian = props.controlMedian ?? 0
  chart.setOption({
    animationDuration: 500,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0, right: 4, textStyle: { color: '#687078' } },
    grid: { left: 12, right: 18, top: 38, bottom: 6, containLabel: true },
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
        name: '均值',
        type: 'bar',
        data: [
          { value: control, itemStyle: { color: '#93a5ad' } },
          { value: treatment, itemStyle: { color: '#167f78' } },
        ],
        barWidth: 22,
        label: { show: true, position: 'right', color: '#263238', formatter: `{c} ${props.metricUnit}` },
      },
      {
        name: '中位数',
        type: 'bar',
        data: [
          { value: controlMedian, itemStyle: { color: '#c8d2d4' } },
          { value: treatmentMedian, itemStyle: { color: '#66aaa4' } },
        ],
        barWidth: 16,
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
watch(
  () => [props.treatment, props.control, props.treatmentMedian, props.controlMedian],
  renderChart,
)
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})
</script>

<template>
  <div
    v-if="hasData"
    ref="chartRoot"
    class="metric-chart"
    role="img"
    :aria-label="`提醒日与常规日${metricLabel}对比图`"
  ></div>
  <div v-else class="metric-chart chart-empty" role="img" :aria-label="`${metricLabel}有效记录不足`">
    有效记录不足，暂不绘制均值和中位数
  </div>
</template>
