<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AlertTriangle,
  Bell,
  CalendarDays,
  Check,
  CircleStop,
  Download,
  Footprints,
  LockKeyhole,
  LoaderCircle,
  Moon,
  Pause,
  Play,
  Save,
  Trophy,
  Upload,
} from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  downloadObservationTemplate,
  fetchCurrentExperiment,
  fetchProfile,
  getApiErrorMessage,
  importObservations,
  saveObservation,
  transitionExperiment,
  updateProfile,
} from '@/services/api'
import type {
  DiscomfortLevel,
  Experiment,
  ExperimentTransition,
  MissingReason,
  ScheduleDay,
} from '@/types'

const experiment = ref<Experiment | null>(null)
const selectedDay = ref<ScheduleDay | null>(null)
const loading = ref(false)
const reminderSaving = ref(false)
const importing = ref(false)
const error = ref('')
const success = ref('')
const importInput = ref<HTMLInputElement | null>(null)
const metricMissing = ref(false)
const reminder = ref({ enabled: true, time: '20:00' })

function emptyForm() {
  return {
    completed: true,
    steps_30m: 1200,
    sugary_drinks: 0,
    sleep_hours: 7,
    subjective_score: 3,
    missing_reason: '' as MissingReason | '',
    discomfort_level: 'none' as DiscomfortLevel,
    discomfort_details: '',
    unplanned_event: '',
    notes: '',
  }
}

const form = ref(emptyForm())
const now = new Date()
const today = [
  now.getFullYear(),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0'),
].join('-')

const progressPercent = computed(() => ((experiment.value?.recorded_days ?? 0) / 14) * 100)
const actionCode = computed(() => experiment.value?.action_code ?? 'postmeal_walk')
const isWalkExperiment = computed(() => actionCode.value === 'postmeal_walk')
const isDrinkExperiment = computed(() => actionCode.value === 'drink_swap')
const isMealOrderExperiment = computed(() => actionCode.value === 'meal_order')
const canRecord = computed(() => experiment.value?.status === 'active')
const reminderDue = computed(() => {
  const todaySchedule = experiment.value?.schedule.find((day) => day.date === today)
  const localTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  return Boolean(
    reminder.value.enabled
      && canRecord.value
      && todaySchedule
      && !todaySchedule.recorded
      && localTime >= reminder.value.time,
  )
})

onMounted(loadExperiment)

async function loadExperiment() {
  loading.value = true
  error.value = ''
  try {
    const [currentExperiment, profile] = await Promise.all([
      fetchCurrentExperiment(),
      fetchProfile(),
    ])
    experiment.value = currentExperiment
    reminder.value = {
      enabled: profile.reminder_enabled,
      time: profile.reminder_time,
    }
    const initialDay = currentExperiment.schedule.find((day) => !day.recorded && day.date <= today)
      ?? currentExperiment.schedule.find((day) => day.date === today)
      ?? currentExperiment.schedule[0]
      ?? null
    selectDay(initialDay)
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

function selectDay(day: ScheduleDay | null) {
  selectedDay.value = day
  form.value = emptyForm()
  metricMissing.value = false
  const observation = day?.observation
  if (!observation) return
  form.value = {
    completed: observation.completed,
    steps_30m: observation.steps_30m ?? 1200,
    sugary_drinks: observation.sugary_drinks ?? 0,
    sleep_hours: observation.sleep_hours ?? 7,
    subjective_score: observation.subjective_score ?? 3,
    missing_reason: observation.missing_reason ?? '',
    discomfort_level: observation.discomfort_level,
    discomfort_details: observation.discomfort_details ?? '',
    unplanned_event: observation.unplanned_event ?? '',
    notes: observation.notes ?? '',
  }
  const primaryValue = isWalkExperiment.value
    ? observation.steps_30m
    : isDrinkExperiment.value
      ? observation.sugary_drinks
      : observation.subjective_score
  metricMissing.value = primaryValue === null
}

function chooseDay(day: ScheduleDay) {
  if (day.date > today || !canRecord.value) return
  selectDay(day)
  success.value = ''
}

function clearMissingReason() {
  if (!metricMissing.value) form.value.missing_reason = ''
}

function allows(action: ExperimentTransition) {
  return experiment.value?.allowed_transitions.includes(action) ?? false
}

async function changeState(action: ExperimentTransition) {
  if (!experiment.value) return
  if (action === 'terminate' && !window.confirm('终止后不能恢复，确定终止本轮实验吗？')) return
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    experiment.value = await transitionExperiment(experiment.value.id, action)
    const messages: Record<ExperimentTransition, string> = {
      pause: '实验已暂停，暂停期间不能保存每日记录。',
      resume: '实验已恢复，可以继续按锁定日程记录。',
      terminate: '本轮实验已终止，历史日程与记录仍会保留。',
      complete: '14 天实验已完成，可以查看结果评估。',
    }
    success.value = messages[action]
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function submitObservation() {
  if (!experiment.value || !selectedDay.value || !canRecord.value) return
  if (metricMissing.value && !form.value.missing_reason) {
    error.value = '主要指标未填写时，请选择缺失原因。'
    return
  }
  if (form.value.discomfort_level !== 'none' && !form.value.discomfort_details.trim()) {
    error.value = '记录身体不适时，请补充简要说明。'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const payload: Parameters<typeof saveObservation>[1] = {
      observed_on: selectedDay.value.date,
      completed: form.value.completed,
      sleep_hours: form.value.sleep_hours,
      discomfort_level: form.value.discomfort_level,
      discomfort_details: form.value.discomfort_details,
      unplanned_event: form.value.unplanned_event,
      notes: form.value.notes,
    }
    if (metricMissing.value) {
      payload.missing_reason = form.value.missing_reason
    } else if (isWalkExperiment.value) {
      payload.steps_30m = form.value.steps_30m
    } else if (isDrinkExperiment.value) {
      payload.sugary_drinks = form.value.sugary_drinks
    } else {
      payload.subjective_score = form.value.subjective_score
    }
    if (!isMealOrderExperiment.value) payload.subjective_score = form.value.subjective_score

    const savedDay = selectedDay.value.date
    const response = await saveObservation(experiment.value.id, payload)
    experiment.value = await fetchCurrentExperiment()
    selectDay(experiment.value.schedule.find((day) => day.date === savedDay) ?? null)
    success.value = `${response.message}；重复提交同一天只会更新原记录。`
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function saveReminderSettings() {
  reminderSaving.value = true
  error.value = ''
  success.value = ''
  try {
    const profile = await updateProfile({
      reminder_enabled: reminder.value.enabled,
      reminder_time: reminder.value.time,
    })
    reminder.value = { enabled: profile.reminder_enabled, time: profile.reminder_time }
    success.value = reminder.value.enabled
      ? `应用内提醒已设为每天 ${reminder.value.time}。`
      : '应用内提醒已关闭。'
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    reminderSaving.value = false
  }
}

async function downloadTemplate(format: 'csv' | 'json') {
  if (!experiment.value) return
  error.value = ''
  try {
    const blob = await downloadObservationTemplate(experiment.value.id, format)
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `yunsync-observations.${format}`
    link.click()
    URL.revokeObjectURL(link.href)
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  }
}

function openImportPicker() {
  importInput.value?.click()
}

async function importFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !experiment.value) return
  importing.value = true
  error.value = ''
  success.value = ''
  try {
    if (file.size > 200_000) throw new Error('导入文件不能超过 200 KB。')
    const format = file.name.toLowerCase().endsWith('.json') ? 'json' : 'csv'
    const result = await importObservations(experiment.value.id, format, await file.text())
    experiment.value = await fetchCurrentExperiment()
    const nextDay = experiment.value.schedule.find((day) => !day.recorded && day.date <= today)
      ?? selectedDay.value
    selectDay(nextDay ?? null)
    success.value = `${result.message}：新增 ${result.created_days} 天，更新 ${result.updated_days} 天。`
  } catch (requestError) {
    error.value = getApiErrorMessage(requestError)
  } finally {
    importing.value = false
    input.value = ''
  }
}
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="步骤 3"
      title="14 天个人微实验"
      description="提醒日与常规日由系统随机安排；日程创建后锁定，分组以服务端记录为准。"
    />

    <div v-if="error" class="message error-message">{{ error }}</div>
    <div v-if="success" class="message success-message">{{ success }}</div>
    <div v-if="loading && !experiment" class="loading-block">正在读取实验计划…</div>

    <template v-if="experiment">
      <section class="experiment-state-panel" :class="`status-${experiment.status}`">
        <div class="experiment-state-copy">
          <span class="status-badge">{{ experiment.status_label }}</span>
          <div>
            <strong>本轮状态由服务端状态机管理</strong>
            <span><LockKeyhole :size="14" /> 日程 {{ experiment.schedule_version }} · 随机种子 {{ experiment.randomization_seed }}</span>
          </div>
        </div>
        <div class="experiment-state-actions">
          <button v-if="allows('pause')" class="button secondary" :disabled="loading" @click="changeState('pause')"><Pause :size="16" />暂停</button>
          <button v-if="allows('resume')" class="button secondary" :disabled="loading" @click="changeState('resume')"><Play :size="16" />恢复</button>
          <button v-if="allows('complete')" class="button primary" :disabled="loading" @click="changeState('complete')"><Trophy :size="16" />完成实验</button>
          <button v-if="allows('terminate')" class="button danger-outline" :disabled="loading" @click="changeState('terminate')"><CircleStop :size="16" />终止</button>
        </div>
      </section>

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
          <span>已记录 {{ experiment.recorded_days }} / 14 天 · 完成行动 {{ experiment.completed_days }} 天</span>
          <div class="progress-track"><span :style="{ width: `${progressPercent}%` }"></span></div>
        </div>
      </section>

      <div v-if="reminderDue" class="reminder-due" role="status">
        <Bell :size="18" />
        <div><strong>今天的记录还未完成</strong><span>你设置的 {{ reminder.time }} 应用内提醒已到。</span></div>
      </div>

      <div v-if="!canRecord" class="recording-lock-notice">
        当前实验为“{{ experiment.status_label }}”，只有进行中状态可以保存每日记录。
      </div>

      <section class="record-support-grid">
        <div class="panel compact-support-panel">
          <div class="support-heading"><Bell :size="18" /><div><strong>应用内提醒</strong><span>页面打开时按设备本地时间提示</span></div></div>
          <div class="reminder-controls">
            <label class="toggle-row compact-toggle"><input v-model="reminder.enabled" type="checkbox" /><span>启用</span></label>
            <input v-model="reminder.time" type="time" aria-label="每日提醒时间" :disabled="!reminder.enabled" />
            <button class="button secondary" :disabled="reminderSaving" type="button" @click="saveReminderSettings">
              <LoaderCircle v-if="reminderSaving" :size="16" class="spinning" /><Save v-else :size="16" />保存
            </button>
          </div>
        </div>
        <div class="panel compact-support-panel">
          <div class="support-heading"><Upload :size="18" /><div><strong>批量导入记录</strong><span>先下载当前行动对应模板，单次最多 14 天</span></div></div>
          <div class="import-actions">
            <button class="button secondary" type="button" @click="downloadTemplate('csv')"><Download :size="16" />CSV 模板</button>
            <button class="button secondary" type="button" @click="downloadTemplate('json')"><Download :size="16" />JSON 模板</button>
            <button class="button primary" :disabled="importing || !canRecord" type="button" @click="openImportPicker">
              <LoaderCircle v-if="importing" :size="16" class="spinning" /><Upload v-else :size="16" />导入文件
            </button>
            <input ref="importInput" class="visually-hidden" type="file" accept=".csv,.json,text/csv,application/json" @change="importFile" />
          </div>
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
              :class="['calendar-day', { treatment: day.treatment, selected: selectedDay?.day === day.day, recorded: day.recorded }]"
              :aria-label="`第 ${day.day} 天，${day.label}${day.recorded ? '，已记录' : ''}`"
              :disabled="day.date > today || !canRecord"
              @click="chooseDay(day)"
            >
              <span>D{{ day.day }}</span><strong>{{ day.label }}</strong><Check v-if="day.recorded" :size="15" />
            </button>
          </div>
          <p class="panel-note">随机种子、完整日程和校验摘要已保存；日期、顺序或分组发生变化时，服务端会停止操作。</p>
        </section>

        <section class="panel log-panel">
          <div class="panel-heading"><div><span class="section-kicker">每日记录</span><h2>D{{ selectedDay?.day }} · {{ selectedDay?.label }}</h2></div></div>
          <form class="record-form" @submit.prevent="submitObservation">
            <label class="toggle-row">
              <input v-model="form.completed" type="checkbox" :disabled="!canRecord" />
              <span>已完成当天安排</span>
            </label>
            <label class="toggle-row missing-toggle">
              <input v-model="metricMissing" type="checkbox" :disabled="!canRecord" @change="clearMissingReason" />
              <span>今天没有主要指标记录</span>
            </label>
            <label v-if="isWalkExperiment && !metricMissing">
              <span><Footprints :size="16" /> 饭后 30 分钟步数</span>
              <input v-model.number="form.steps_30m" type="number" min="0" max="20000" required :disabled="!canRecord" />
            </label>
            <label v-if="isDrinkExperiment && !metricMissing">
              <span>当天含糖饮料次数</span>
              <input v-model.number="form.sugary_drinks" type="number" min="0" max="20" required :disabled="!canRecord" />
            </label>
            <label v-if="isMealOrderExperiment && !metricMissing">
              <span>餐后状态评分</span>
              <select v-model.number="form.subjective_score" required :disabled="!canRecord">
                <option :value="1">1 · 很差</option><option :value="2">2 · 较差</option><option :value="3">3 · 一般</option><option :value="4">4 · 良好</option><option :value="5">5 · 很好</option>
              </select>
            </label>
            <label v-if="metricMissing">
              <span>缺失原因</span>
              <select v-model="form.missing_reason" required :disabled="!canRecord">
                <option value="" disabled>请选择</option>
                <option value="forgot">忘记记录</option>
                <option value="device_unavailable">设备或数据不可用</option>
                <option value="physical_discomfort">身体不适</option>
                <option value="unplanned_event">计划外事件</option>
                <option value="other">其他</option>
              </select>
            </label>
            <label>
              <span><Moon :size="16" /> 昨晚睡眠时长</span>
              <div class="input-suffix"><input v-model.number="form.sleep_hours" type="number" min="0" max="24" step="0.1" :disabled="!canRecord" /><em>小时</em></div>
            </label>
            <label v-if="!isMealOrderExperiment">
              <span>主观状态</span>
              <select v-model.number="form.subjective_score" :disabled="!canRecord">
                <option :value="1">1 · 很差</option><option :value="2">2 · 较差</option><option :value="3">3 · 一般</option><option :value="4">4 · 良好</option><option :value="5">5 · 很好</option>
              </select>
            </label>
            <fieldset class="context-fieldset">
              <legend><AlertTriangle :size="16" /> 身体不适</legend>
              <select v-model="form.discomfort_level" :disabled="!canRecord">
                <option value="none">没有</option><option value="mild">轻微</option><option value="significant">明显，需要暂停实验</option>
              </select>
              <textarea v-if="form.discomfort_level !== 'none'" v-model="form.discomfort_details" rows="2" maxlength="300" placeholder="请简要描述；明显不适会自动暂停实验" :disabled="!canRecord"></textarea>
            </fieldset>
            <label><span>计划外事件</span><input v-model="form.unplanned_event" maxlength="300" placeholder="例如聚餐、出差；没有可留空" :disabled="!canRecord" /></label>
            <label><span>备注</span><textarea v-model="form.notes" rows="3" maxlength="500" placeholder="可记录餐食、天气或其他感受" :disabled="!canRecord"></textarea></label>
            <button class="button primary full-width mobile-save-button" :disabled="loading || !canRecord" type="submit">
              <LoaderCircle v-if="loading" :size="17" class="spinning" /><Save v-else :size="17" />{{ selectedDay?.recorded ? '更新当天记录' : '保存记录' }}
            </button>
          </form>
        </section>
      </div>
    </template>
  </div>
</template>
