<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { LogOut, Save, ShieldOff, UserRoundCog } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import {
  fetchAccountStatus,
  fetchFoodSafetyProfile,
  getApiErrorMessage,
  logoutDemo,
  updateProfile,
  updateFoodSafetyProfile,
  withdrawConsent,
} from '@/services/api'
import { clearAuthSession, currentUser, setCurrentUser } from '@/state/auth'
import { resetOnboardingAccess } from '@/state/onboarding'
import { useWorkspaceStore } from '@/stores/workspace'
import type { FoodSafetyAnswerStatus, FoodSafetyProfile, FoodSafetyProfileInput, FoodSafetySpecialStatus } from '@/types'


const router = useRouter()
const workspace = useWorkspaceStore()
const loading = ref(true)
const saving = ref(false)
const savingSafety = ref(false)
const error = ref('')
const success = ref('')
const consentVersion = ref('')
const safetyReadiness = ref<FoodSafetyProfile['readiness']>('needs_information')
const safetyForm = reactive({
  allergy_status: 'unknown' as FoodSafetyAnswerStatus,
  allergens: '',
  medication_status: 'unknown' as FoodSafetyAnswerStatus,
  medications: '',
  condition_status: 'unknown' as FoodSafetyAnswerStatus,
  conditions: '',
  liver_kidney_status: 'unknown' as FoodSafetyAnswerStatus,
  liver_kidney_conditions: '',
  clinician_restriction_status: 'unknown' as FoodSafetyAnswerStatus,
  clinician_restrictions: '',
  special_status: 'unknown' as FoodSafetySpecialStatus,
  special_details: '',
})
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

function fillSafetyForm(profile: FoodSafetyProfile) {
  safetyForm.allergy_status = profile.allergy_status
  safetyForm.allergens = profile.allergens.join('\n')
  safetyForm.medication_status = profile.medication_status
  safetyForm.medications = profile.medications.join('\n')
  safetyForm.condition_status = profile.condition_status
  safetyForm.conditions = profile.conditions.join('\n')
  safetyForm.liver_kidney_status = profile.liver_kidney_status
  safetyForm.liver_kidney_conditions = profile.liver_kidney_conditions.join('\n')
  safetyForm.clinician_restriction_status = profile.clinician_restriction_status
  safetyForm.clinician_restrictions = profile.clinician_restrictions.join('\n')
  safetyForm.special_status = profile.special_status
  safetyForm.special_details = profile.special_details
  safetyReadiness.value = profile.readiness
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
}

function safetyPayload(): FoodSafetyProfileInput {
  return {
    allergy_status: safetyForm.allergy_status,
    allergens: safetyForm.allergy_status === 'present' ? lines(safetyForm.allergens) : [],
    medication_status: safetyForm.medication_status,
    medications: safetyForm.medication_status === 'present' ? lines(safetyForm.medications) : [],
    condition_status: safetyForm.condition_status,
    conditions: safetyForm.condition_status === 'present' ? lines(safetyForm.conditions) : [],
    liver_kidney_status: safetyForm.liver_kidney_status,
    liver_kidney_conditions: safetyForm.liver_kidney_status === 'present' ? lines(safetyForm.liver_kidney_conditions) : [],
    clinician_restriction_status: safetyForm.clinician_restriction_status,
    clinician_restrictions: safetyForm.clinician_restriction_status === 'present' ? lines(safetyForm.clinician_restrictions) : [],
    special_status: safetyForm.special_status,
    special_details: safetyForm.special_status === 'other' ? safetyForm.special_details.trim() : '',
  }
}

async function saveSafetyProfile() {
  savingSafety.value = true
  error.value = ''
  success.value = ''
  try {
    fillSafetyForm(await updateFoodSafetyProfile(safetyPayload()))
    success.value = '食养安全档案已保存；正式建议仍须等待专业内容和规则审核。'
  } catch (caught) {
    error.value = getApiErrorMessage(caught)
  } finally {
    savingSafety.value = false
  }
}

async function loadProfile() {
  loading.value = true
  error.value = ''
  try {
    const [status, safety] = await Promise.all([fetchAccountStatus(), fetchFoodSafetyProfile()])
    setCurrentUser(status.user)
    consentVersion.value = status.consent?.version || ''
    fillForm()
    fillSafetyForm(safety)
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
      description="这些字段只用于合成数据演示。请不要填写真实身份、疾病、过敏或用药信息。"
    />

    <div v-if="error" class="message error-message" role="alert">{{ error }}</div>
    <div v-if="success" class="message success-message" role="status">{{ success }}</div>

    <div v-if="loading" class="loading-block">正在读取演示档案…</div>
    <div v-else class="content-grid profile-grid">
      <div class="page-stack">
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

      <form class="panel profile-form" @submit.prevent="saveSafetyProfile">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">V2 · 食养安全信息</span>
            <h2>明确回答个人饮食风险</h2>
          </div>
          <span class="status-badge" :class="safetyReadiness === 'needs_professional_review' ? 'danger' : 'pending'">
            {{ safetyReadiness === 'needs_information' ? '信息未完整' : safetyReadiness === 'needs_professional_review' ? '需专业评估' : '等待规则审核' }}
          </span>
        </div>
        <p class="panel-note">“尚未回答”不会被当作“没有”。目前只保存合成演示信息，完成填写也不会自动开放食养方案。</p>

        <div class="form-grid two-column">
          <label>
            <span>食物或原料过敏</span>
            <select v-model="safetyForm.allergy_status">
              <option value="unknown">尚未回答</option><option value="none">明确没有</option><option value="present">有</option>
            </select>
          </label>
          <label>
            <span>正在用药</span>
            <select v-model="safetyForm.medication_status">
              <option value="unknown">尚未回答</option><option value="none">明确没有</option><option value="present">有</option>
            </select>
          </label>
        </div>
        <label v-if="safetyForm.allergy_status === 'present'">
          <span>过敏原（每行一项）</span>
          <textarea v-model="safetyForm.allergens" rows="3" maxlength="1200" placeholder="例如：花生"></textarea>
        </label>
        <label v-if="safetyForm.medication_status === 'present'">
          <span>用药信息（每行一项）</span>
          <textarea v-model="safetyForm.medications" rows="3" maxlength="1200" placeholder="仅填写合成演示信息"></textarea>
        </label>

        <div class="form-grid two-column">
          <label>
            <span>已知疾病或健康状况</span>
            <select v-model="safetyForm.condition_status">
              <option value="unknown">尚未回答</option><option value="none">明确没有</option><option value="present">有</option>
            </select>
          </label>
          <label>
            <span>医生提出的饮食限制</span>
            <select v-model="safetyForm.clinician_restriction_status">
              <option value="unknown">尚未回答</option><option value="none">明确没有</option><option value="present">有</option>
            </select>
          </label>
        </div>
        <label v-if="safetyForm.condition_status === 'present'">
          <span>健康状况（每行一项）</span>
          <textarea v-model="safetyForm.conditions" rows="3" maxlength="1200" placeholder="仅填写合成演示信息"></textarea>
        </label>
        <label>
          <span>肝肾相关疾病或异常情况</span>
          <select v-model="safetyForm.liver_kidney_status">
            <option value="unknown">尚未回答</option><option value="none">明确没有</option><option value="present">有</option>
          </select>
        </label>
        <label v-if="safetyForm.liver_kidney_status === 'present'">
          <span>肝肾相关情况（每行一项）</span>
          <textarea v-model="safetyForm.liver_kidney_conditions" rows="3" maxlength="1200" placeholder="仅填写合成演示信息"></textarea>
        </label>
        <label v-if="safetyForm.clinician_restriction_status === 'present'">
          <span>饮食限制（每行一项）</span>
          <textarea v-model="safetyForm.clinician_restrictions" rows="3" maxlength="1200" placeholder="仅填写合成演示信息"></textarea>
        </label>

        <label>
          <span>孕哺或其他需要专业营养指导的状态</span>
          <select v-model="safetyForm.special_status">
            <option value="unknown">尚未回答</option>
            <option value="none">没有或不适用</option>
            <option value="pregnant">孕期</option>
            <option value="breastfeeding">哺乳期</option>
            <option value="other">其他特殊状态</option>
          </select>
        </label>
        <label v-if="safetyForm.special_status === 'other'">
          <span>特殊状态说明</span>
          <textarea v-model="safetyForm.special_details" rows="3" maxlength="240" placeholder="仅填写合成演示信息"></textarea>
        </label>

        <button class="button primary" type="submit" :disabled="savingSafety">
          <Save :size="17" />
          {{ savingSafety ? '保存中…' : '保存食养安全信息' }}
        </button>
      </form>
      </div>

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
          <div><dt>食养安全档案</dt><dd>{{ safetyReadiness === 'needs_information' ? '待补充' : safetyReadiness === 'needs_professional_review' ? '需专业评估' : '等待规则审核' }}</dd></div>
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
