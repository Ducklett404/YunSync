<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CalendarDays, Check, Footprints, LoaderCircle, Moon, Save } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { fetchCurrentExperiment, getApiErrorMessage, saveObservation } from '@/services/api'
import type { Experiment, ScheduleDay } from '@/types'

const experiment = ref<Experiment | null>(null)
const selectedDay = ref<ScheduleDay | null>(null)
const loading = ref(false)
const error = ref('')
const success = ref('')
const form = ref({
  completed: true,
  steps_30m: 1200,
  sugary_drinks: 0,
  sleep_hours: 7,
  subjective_score: 3,
  notes: '',
})

const now = new Date()
const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-')

const progressPercent = computed(() => ((experiment.value?.progress ?? 0) / 14) * 100)
const actionCode = computed(() => experiment.value?.action_code ?? 'postmeal_walk')
const isWalkExperiment = computed(() => actionCode.value === 'postmeal_walk')
const isDrinkExperiment = computed(() => actionCode.value === 'drink_swap')

onMounted(async () => {
  try {
    experiment.value = await fetchCurrentExperiment()
    selectedDay.value = experiment.value.schedule.find((day) => !day.completed && day.date <= today)
      ?? experiment.value.schedule.find((day) => day.date === today)
      ?? experiment.value.schedule[0]
      ?? null
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  }
})

function chooseDay(day: ScheduleDay) {
  if (day.date > today) return
  selectedDay.value = day
  success.value = ''
}

async function submitObservation() {
  if (!experiment.value || !selectedDay.value) return
  loading.value = true
  error.value = ''
  try {
    const payload: Parameters<typeof saveObservation>[1] = {
      observed_on: selectedDay.value.date,
      completed: form.value.completed,
      sleep_hours: form.value.sleep_hours,
      subjective_score: form.value.subjective_score,
      notes: form.value.notes,
    }
    if (isWalkExperiment.value) payload.steps_30m = form.value.steps_30m
    if (isDrinkExperiment.value) payload.sugary_drinks = form.value.sugary_drinks
    await saveObservation(experiment.value.id, payload)
    experiment.value = await fetchCurrentExperiment()
    selectedDay.value = experiment.value.schedule.find((day) => day.date === selectedDay.value?.date) ?? null
    success.value = '记录已保存，结果看板已更新。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 3"
      title="14 天个人微实验"
      description="提醒日与常规日由系统随机安排，用户不需要主动采取不健康行为。"
    />

    <div v-if="error" class="message error-message">{{ error }}</div>
    <template v-if="experiment">
      <section class="panel experiment-overview">
        <div class="experiment-summary">
          <div class="summary-icon teal"><Footprints :size="21" /></div>
          <div><span>当前行动</span><strong>{{ experiment.action_title }}</strong></div>
        </div>
        <div class="experiment-summary">
          <div class="summary-icon gray"><CalendarDays :size="21" /></div>
          <div><span>观察周期</span><strong>{{ experiment.start_date }} 至 {{ experiment.end_date }}</strong></div>
        </div>
        <div class="progress-summary">
          <span>已完成 {{ experiment.progress }} / 14 天</span>
          <div class="progress-track"><span :style="{ width: `${progressPercent}%` }"></span></div>
        </div>
      </section>

      <div class="content-grid experiment-grid">
        <section class="panel">
          <div class="panel-heading"><div><span class="section-kicker">随机日程</span><h2>实验日历</h2></div></div>
          <div class="calendar-legend"><span><i class="legend-dot treatment"></i>提醒日</span><span><i class="legend-dot control"></i>常规日</span></div>
          <div class="experiment-calendar">
            <button
              v-for="day in experiment.schedule"
              :key="day.day"
              :class="['calendar-day', { treatment: day.treatment, selected: selectedDay?.day === day.day, completed: day.completed }]"
              :aria-label="`第 ${day.day} 天，${day.label}`"
              :disabled="day.date > today"
              @click="chooseDay(day)"
            >
              <span>D{{ day.day }}</span>
              <strong>{{ day.label }}</strong>
              <Check v-if="day.completed" :size="15" />
            </button>
          </div>
          <p class="panel-note">随机安排保存在实验记录中，创建后不会随意修改。</p>
        </section>

        <section class="panel log-panel">
          <div class="panel-heading"><div><span class="section-kicker">每日记录</span><h2>D{{ selectedDay?.day }} · {{ selectedDay?.label }}</h2></div></div>
          <form class="record-form" @submit.prevent="submitObservation">
            <label class="toggle-row">
              <input v-model="form.completed" type="checkbox" />
              <span>已完成当天安排</span>
            </label>
            <label v-if="isWalkExperiment">
              <span><Footprints :size="16" /> 饭后 30 分钟步数</span>
              <input v-model.number="form.steps_30m" type="number" min="0" max="20000" />
            </label>
            <label v-if="isDrinkExperiment">
              <span>当天含糖饮料次数</span>
              <input v-model.number="form.sugary_drinks" type="number" min="0" max="20" />
            </label>
            <label>
              <span><Moon :size="16" /> 昨晚睡眠时长</span>
              <div class="input-suffix"><input v-model.number="form.sleep_hours" type="number" min="0" max="24" step="0.1" /><em>小时</em></div>
            </label>
            <label>
              <span>{{ actionCode === 'meal_order' ? '餐后状态评分' : '主观状态' }}</span>
              <select v-model.number="form.subjective_score">
                <option :value="1">1 · 很差</option><option :value="2">2 · 较差</option><option :value="3">3 · 一般</option><option :value="4">4 · 良好</option><option :value="5">5 · 很好</option>
              </select>
            </label>
            <label><span>备注</span><textarea v-model="form.notes" rows="3" placeholder="可记录餐食、天气或身体感受"></textarea></label>
            <div v-if="success" class="message success-message">{{ success }}</div>
            <button class="button primary full-width" :disabled="loading" type="submit">
              <LoaderCircle v-if="loading" :size="17" class="spinning" /><Save v-else :size="17" />保存记录
            </button>
          </form>
        </section>
      </div>
    </template>
  </div>
</template>
