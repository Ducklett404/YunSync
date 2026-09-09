<script setup lang="ts">
import {
  Activity,
  CalendarDays,
  ClipboardCheck,
  FileScan,
  FlaskConical,
  LayoutDashboard,
  ShieldCheck,
} from 'lucide-vue-next'

const navItems = [
  { to: '/', label: '健康总览', icon: LayoutDashboard },
  { to: '/report', label: '报告确认', icon: FileScan },
  { to: '/actions', label: '候选行动', icon: ClipboardCheck },
  { to: '/experiment', label: '个人实验', icon: CalendarDays },
  { to: '/results', label: '结果评估', icon: Activity },
]
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true"><FlaskConical :size="22" /></div>
        <div>
          <strong>云循</strong>
          <span>HealthLoop</span>
        </div>
      </div>

      <nav class="primary-nav" aria-label="主要导航">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to">
          <component :is="item.icon" :size="19" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="safety-block">
        <ShieldCheck :size="19" aria-hidden="true" />
        <div>
          <strong>健康支持模式</strong>
          <span>不诊断、不处方</span>
        </div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="mobile-brand"><FlaskConical :size="20" /> 云循</div>
        <div class="environment-state">
          <span class="status-dot"></span>
          合成数据演示环境
        </div>
        <div class="profile-chip">
          <span>林同学</span>
          <span class="avatar">林</span>
        </div>
      </header>

      <main class="main-content">
        <slot />
      </main>
    </div>
  </div>
</template>

