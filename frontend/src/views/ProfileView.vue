<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { LogOut, Save, ShieldOff, UserRoundCog } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import {
  fetchAccountStatus,
  getApiErrorMessage,
  logoutDemo,
  updateProfile,
  withdrawConsent,
} from '@/services/api'
import { clearAuthSession, currentUser, setCurrentUser } from '@/state/auth'
import { resetOnboardingAccess } from '@/state/onboarding'
import { useWorkspaceStore } from '@/stores/workspace'


const router = useRouter()
const workspace = useWorkspaceStore()
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const success = ref('')
const consentVersion = ref('')
const form = reactive({
  nickname: '',
  age_range: '25-34',
  goal: '',
  sleep_schedule: '',
  activity_baseline: '',
  constraints: '',
  preferences: '',
})

function fillForm() {
  if (!currentUser.value) return
  form.nickname = currentUser.value.nickname
  form.age_range = currentUser.value.age_range
  form.goal = currentUser.value.goal
  form.sleep_schedule = currentUser.value.sleep_schedule
  form.activity_baseline = currentUser.value.activity_baseline
  form.constraints = currentUser.value.constraints
  form.preferences = currentUser.value.preferences
}

async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const status = await fetchAccountStatus()
    setCurrentUser(status.user)
    consentVersion.value = status.consent?.version || ''
    fillForm()
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    loading.value = false
  }
}

async function saveProfile() {
  saving.value = true
  error.value = ''
  success.value = ''
  try {
    const updated = await updateProfile({ ...form })
    setCurrentUser(updated)
    workspace.$reset()
    success.value = '合成健康档案已保存。'
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    saving.value = false
  }
}

async function withdraw() {
  const confirmed = window.confirm('撤回后将停止新的健康分析，并暂停进行中的个人实验。是否继续？')
  if (!confirmed) return
  error.value = ''
  try {
    await withdrawConsent()
    resetOnboardingAccess()
    workspace.$reset()
    await router.push('/start')
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  }
}

async function signOut() {
  try {
    await logoutDemo()
  } finally {
    clearAuthSession()
    resetOnboardingAccess()
    workspace.$reset()
    await router.push('/start')
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="账号与授权"
      title="管理合成档案与授权"
      description="这些字段只用于演示个性化流程。请不要填写真实身份信息、诊断详情或联系方式。"
    />

    <div v-if="error" class="message error-message" role="alert">{{ error }}</div>
    <div v-if="success" class="message success-message" role="status">{{ success }}</div>

    <div v-if="loading" class="loading-block">正在读取演示档案…</div>
    <div v-else class="content-grid profile-grid">
      <form class="panel profile-form" @submit.prevent="saveProfile">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">合成健康档案</span>
            <h2>目标、作息与偏好</h2>
          </div>
          <UserRoundCog :size="22" class="muted-icon" />
        </div>

        <div class="form-grid two-column">
          <label>
            <span>显示名称</span>
            <input v-model.trim="form.nickname" maxlength="80" required />
          </label>
          <label>
            <span>年龄范围</span>
            <select v-model="form.age_range">
              <option value="18-24">18–24</option>
              <option value="25-34">25–34</option>
              <option value="35-44">35–44</option>
              <option value="45-54">45–54</option>
              <option value="55-64">55–64</option>
              <option value="65+">65+</option>
            </select>
          </label>
        </div>

        <label>
          <span>当前健康行为目标</span>
          <input v-model.trim="form.goal" maxlength="120" required />
        </label>
        <label>
          <span>日常作息</span>
          <input v-model.trim="form.sleep_schedule" maxlength="120" placeholder="例如：通常 23:30 入睡，07:00 起床" />
        </label>
        <label>
          <span>活动基础</span>
          <textarea v-model.trim="form.activity_baseline" rows="3" maxlength="160"></textarea>
        </label>
        <label>
          <span>限制条件</span>
          <textarea v-model.trim="form.constraints" rows="3" maxlength="500"></textarea>
        </label>
        <label>
          <span>记录偏好</span>
          <textarea v-model.trim="form.preferences" rows="3" maxlength="500"></textarea>
        </label>

        <button class="button primary" type="submit" :disabled="saving">
          <Save :size="17" />
          {{ saving ? '保存中…' : '保存档案' }}
        </button>
      </form>

      <aside class="panel account-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">权限状态</span>
            <h2>{{ currentUser?.nickname }}</h2>
          </div>
          <span class="status-badge safe">{{ currentUser?.role === 'participant' ? '参与者' : '审核角色' }}</span>
        </div>

        <dl class="account-facts">
          <div><dt>授权版本</dt><dd>{{ consentVersion || '未授权' }}</dd></div>
          <div><dt>安全初筛</dt><dd>{{ currentUser?.screening_status === 'eligible' ? '未触发拦截' : '需要专业评估' }}</dd></div>
          <div><dt>数据环境</dt><dd>仅合成数据</dd></div>
        </dl>

        <div class="account-actions">
          <button class="button danger-outline full-width" type="button" @click="withdraw">
            <ShieldOff :size="17" />撤回授权
          </button>
          <button class="button secondary full-width" type="button" @click="signOut">
            <LogOut :size="17" />退出演示账号
          </button>
        </div>
        <p class="panel-note">撤回授权后，服务端会拒绝新的报告分析和健康数据操作，并暂停当前实验。</p>
      </aside>
    </div>
  </div>
</template>
