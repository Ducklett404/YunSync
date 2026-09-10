<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, CheckCircle2, CircleAlert, FileLock2, LoaderCircle, LogIn, ShieldCheck } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { resetOnboardingAccess, unlockHealthFlow } from '@/state/onboarding'
import { currentUser, isAuthenticated, setAuthSession, setCurrentUser } from '@/state/auth'
import {
  acceptConsent,
  fetchAccountStatus,
  fetchConsentNotice,
  getApiErrorMessage,
  loginDemo,
  saveSafetyScreening,
} from '@/services/api'

type Answer = 'yes' | 'no' | ''

interface SafetyQuestion {
  id: string
  label: string
}

const router = useRouter()
resetOnboardingAccess()
const consentVersion = ref('')
const consentTitle = ref('云循合成数据演示知情说明')
const hasActiveConsent = ref(false)
const loadingAccount = ref(true)
const submitting = ref(false)
const accountError = ref('')
const savedMessage = ref('')
const acceptedBoundaries = ref(false)
const acceptedSyntheticOnly = ref(false)
const acceptedProcessing = ref(false)
const safetyAnswers = ref<Record<string, Answer>>({
  acute_symptoms: '',
  clinician_restriction: '',
  recent_discomfort: '',
  support_needed: '',
})

const safetyQuestions: SafetyQuestion[] = [
  { id: 'acute_symptoms', label: '目前是否有胸痛、明显呼吸困难、晕厥或持续眩晕？' },
  { id: 'clinician_restriction', label: '医生是否明确要求你限制运动或饮食改变？' },
  { id: 'recent_discomfort', label: '最近一次运动或饮食改变后，是否出现明显不适？' },
  { id: 'support_needed', label: '你是否认为当前情况需要专业人员先行评估？' },
]

const allQuestionsAnswered = computed(() =>
  safetyQuestions.every((question) => safetyAnswers.value[question.id] !== ''),
)
const hasSafetyFlag = computed(() =>
  Object.values(safetyAnswers.value).some((answer) => answer === 'yes'),
)
const consentReady = computed(() =>
  acceptedBoundaries.value && acceptedSyntheticOnly.value && acceptedProcessing.value,
)
const canSubmit = computed(() =>
  isAuthenticated.value && consentReady.value && allQuestionsAnswered.value && !submitting.value,
)

function applyAccountStatus(status: Awaited<ReturnType<typeof fetchAccountStatus>>) {
  setCurrentUser(status.user)
  consentVersion.value = status.required_consent_version
  hasActiveConsent.value = Boolean(status.consent)
  if (status.consent) {
    acceptedBoundaries.value = true
    acceptedSyntheticOnly.value = true
    acceptedProcessing.value = true
  }
  for (const question of safetyQuestions) {
    const answer = status.user.screening_answers[question.id]
    safetyAnswers.value[question.id] = answer === undefined ? '' : answer ? 'yes' : 'no'
  }
  if (status.consent && status.user.screening_status === 'eligible' && !status.user.high_risk) {
    unlockHealthFlow()
  }
}

async function loadAccount() {
  loadingAccount.value = true
  accountError.value = ''
  try {
    const notice = await fetchConsentNotice()
    consentVersion.value = notice.version
    consentTitle.value = notice.title
    if (isAuthenticated.value) applyAccountStatus(await fetchAccountStatus())
  } catch (error) {
    accountError.value = getApiErrorMessage(error)
  } finally {
    loadingAccount.value = false
  }
}

async function signInDemo() {
  loadingAccount.value = true
  accountError.value = ''
  try {
    setAuthSession(await loginDemo())
    applyAccountStatus(await fetchAccountStatus())
  } catch (error) {
    accountError.value = getApiErrorMessage(error)
  } finally {
    loadingAccount.value = false
  }
}

async function continueToReport() {
  if (!canSubmit.value) return
  submitting.value = true
  accountError.value = ''
  savedMessage.value = ''
  try {
    if (!hasActiveConsent.value) {
      await acceptConsent(consentVersion.value)
      hasActiveConsent.value = true
    }
    const profile = await saveSafetyScreening(
      Object.fromEntries(
        safetyQuestions.map((question) => [question.id, safetyAnswers.value[question.id] === 'yes']),
      ),
    )
    setCurrentUser(profile)
    if (profile.high_risk) {
      resetOnboardingAccess()
      savedMessage.value = '初筛结果已保存，本次自助实验流程已停止。'
      return
    }
    unlockHealthFlow()
    await router.push('/report')
  } catch (error) {
    accountError.value = getApiErrorMessage(error)
  } finally {
    submitting.value = false
  }
}

onMounted(loadAccount)
</script>

<template>
  <div class="page-stack">
    <PageHeader
      eyebrow="流程起点"
      title="登录并确认使用边界"
      description="这是合成数据演示环境。登录、授权和初筛结果会保存到本地演示数据库，不应填写或上传真实个人信息。"
    />

    <ol class="journey-steps" aria-label="云循使用流程">
      <li class="active"><span>1</span>知情与初筛</li>
      <li><span>2</span>报告确认</li>
      <li><span>3</span>选择行动</li>
      <li><span>4</span>每日记录</li>
      <li><span>5</span>结果评估</li>
    </ol>

    <section class="panel account-gate" aria-labelledby="demo-account-title">
      <div>
        <span class="section-kicker">演示账号</span>
        <h2 id="demo-account-title">{{ isAuthenticated ? '已登录合成账号' : '先登录，再完成授权与初筛' }}</h2>
        <p v-if="currentUser">{{ currentUser.nickname }} · {{ currentUser.role === 'participant' ? '参与者' : '审核角色' }}</p>
        <p v-else>系统只签发短期演示会话，不需要手机号、邮箱或真实身份信息。</p>
      </div>
      <button v-if="!isAuthenticated" class="button primary" :disabled="loadingAccount" @click="signInDemo">
        <LoaderCircle v-if="loadingAccount" :size="17" class="spinning" />
        <LogIn v-else :size="17" />
        登录演示账号
      </button>
      <span v-else class="status-badge safe">会话有效</span>
    </section>

    <div v-if="accountError" class="message error-message" role="alert">{{ accountError }}</div>
    <div v-if="savedMessage" class="message success-message" role="status">{{ savedMessage }}</div>

    <div class="content-grid onboarding-grid">
      <section class="panel consent-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">知情说明</span>
            <h2>{{ consentTitle }}</h2>
          </div>
          <FileLock2 :size="22" class="muted-icon" />
        </div>

        <div class="boundary-card">
          <ShieldCheck :size="21" />
          <div>
            <strong>健康教育与生活方式支持工具</strong>
            <p>云循用于理解健康信息、记录低风险行动和观察个人短期变化，不提供疾病诊断、治疗、处方或药物调整意见。</p>
          </div>
        </div>

        <div class="consent-list">
          <label class="consent-option">
            <input v-model="acceptedBoundaries" type="checkbox" :disabled="!isAuthenticated" />
            <span><strong>我已理解产品边界</strong>实验结果只表示个人短期观察，不等同于医疗结论。</span>
          </label>
          <label class="consent-option">
            <input v-model="acceptedSyntheticOnly" type="checkbox" :disabled="!isAuthenticated" />
            <span><strong>我只使用合成或已脱敏材料</strong>当前开发版本不应上传姓名、证件号码、联系方式等真实个人信息。</span>
          </label>
          <label class="consent-option">
            <input v-model="acceptedProcessing" type="checkbox" :disabled="!isAuthenticated" />
            <span><strong>我同意本次演示处理</strong>系统可以为完成演示流程临时处理所选文件和填写内容。</span>
          </label>
        </div>
        <p class="consent-version">授权版本：{{ consentVersion || '读取中' }} · 可在账号与档案页随时撤回</p>
      </section>

      <section class="panel screening-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">安全初筛</span>
            <h2>以下情况是否适用于你</h2>
          </div>
          <CircleAlert :size="22" class="muted-icon" />
        </div>
        <p class="screening-intro">请选择“是”或“否”。任一项选择“是”时，原型会停止生成自助实验。</p>

        <fieldset v-for="(question, index) in safetyQuestions" :key="question.id" class="safety-question">
          <legend><span>{{ index + 1 }}</span>{{ question.label }}</legend>
          <div class="segmented-options">
            <label :class="{ selected: safetyAnswers[question.id] === 'no' }">
              <input v-model="safetyAnswers[question.id]" type="radio" :name="question.id" value="no" :disabled="!isAuthenticated" />
              否
            </label>
            <label :class="{ selected: safetyAnswers[question.id] === 'yes', danger: safetyAnswers[question.id] === 'yes' }">
              <input v-model="safetyAnswers[question.id]" type="radio" :name="question.id" value="yes" :disabled="!isAuthenticated" />
              是
            </label>
          </div>
        </fieldset>

        <div v-if="hasSafetyFlag" class="safety-stop" role="alert">
          <CircleAlert :size="20" />
          <div>
            <strong>本次流程已停止</strong>
            <span>当前回答触发安全边界。请先寻求专业人员评估，不要在云循中自行开始实验。</span>
          </div>
        </div>
        <div v-else-if="allQuestionsAnswered" class="safety-pass" role="status">
          <CheckCircle2 :size="19" />
          <span>未触发当前原型中的安全拦截条件。</span>
        </div>

        <button class="button primary full-width" :disabled="!canSubmit" @click="continueToReport">
          <LoaderCircle v-if="submitting" :size="17" class="spinning" />
          {{ hasSafetyFlag ? '保存并停止自助流程' : '保存并继续到报告确认' }}
          <ArrowRight :size="17" />
        </button>
        <p v-if="!isAuthenticated" class="form-hint">请先登录演示账号。</p>
        <p v-else-if="!consentReady" class="form-hint">请先勾选全部知情说明。</p>
        <p v-else-if="!allQuestionsAnswered" class="form-hint">请完成全部安全问题。</p>
      </section>
    </div>
  </div>
</template>
