<template>
  <div class="rpanel" v-if="store.resOpen && store.res">
    <div class="rp-head">
      <span class="rp-icon" :style="{background: chrono(store.res.mode)}">{{ ICONS[store.res.mode] }}</span>
      <div class="rp-title">
        <b>{{ store.res.modeName }}</b>
        <span>{{ store.res.ts }}</span>
      </div>
      <button class="rp-close" @click="store.resOpen = false" title="关闭">✕</button>
    </div>
    <div class="rp-chips">
      <template v-if="paramChips.length">
        <div class="rp-grouplbl">参数</div>
        <span v-for="c in paramChips" :key="c.k" class="chip dim"><i>{{ c.k }}</i><em>{{ c.v }}</em></span>
      </template>
      <template v-if="metricChips.length">
        <div class="rp-grouplbl">指标</div>
        <span v-for="c in metricChips" :key="c.k" class="chip"><i>{{ c.k }}</i><em>{{ c.v }}</em></span>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { store } from '../store'

const ICONS = { route:'🚗', service:'⏱', close:'🎯', closest:'🎯', sfca:'📊', '2sfca':'📊', vrp:'🚚', loc:'📍', 'loc-alloc':'📍' }
const COLS = { route:'#8b5cf6', service:'#0ea5c9', close:'#34d399', closest:'#34d399', sfca:'#6d5df0', '2sfca':'#6d5df0', vrp:'#e8930c', loc:'#f59e0b', 'loc-alloc':'#f59e0b' }
const DECAY_CN = { binary:'二值', gaussian:'高斯', e2sfca:'增强(三段)', power:'重力', linear:'线性', exponential:'指数' }
const PROBLEM_CN = { min_impedance:'最小阻抗(p-中值)', max_coverage:'最大覆盖', cap_coverage:'容量约束覆盖',
  min_facilities:'最少设施数', max_attendance:'最大客流', market_share:'市场份额(竞争力)' }
const LABELS = {
  n_demand:'需求点', n_facility:'设施数', radius_min:'搜索半径', decay:'衰减函数', minutes:'圈层 (min)',
  vehicles:'载具数', capacity:'容量', limit:'单线限时', p:'设施数 P', problem:'选址模型', cutoff:'截断',
  distance_km:'总里程', time_min:'耗时 (min)',
  mean:'人均可达性', pop_mean:'加权人均', gini:'基尼系数', p25:'下四分位', n_low:'短缺人数',
  low_pct:'短缺人群', served:'已服务点', total:'总点数', routes:'线路数', n:'数量', facilities:'选中设施',
  avg_time_min:'平均耗时', total_time_min:'总耗时'
}
const PARAM_ORDER = ['n_demand','n_facility','radius_min','decay','minutes','vehicles','capacity','limit','p','problem','cutoff']
const METRIC_ORDER = ['mean','pop_mean','low_pct','gini','avg_time_min','total_time_min','served','routes','n','facilities','distance_km','total']

function chrono(id){ return COLS[id] }
function fmt(k, v){
  if (k === 'decay') return DECAY_CN[v] || v
  if (k === 'problem') return PROBLEM_CN[v] || v
  if (k === 'low_pct' && typeof v === 'number') return Math.round(v * 10) / 10 + ' %'
  if (typeof v === 'number'){
    const r = Math.round(v * 10) / 10
    return r.toLocaleString('zh-CN')
  }
  return v
}
const chips = computed(() => {
  const s = store.res && store.res.stats || {}
  const params = [], metrics = []
  const seen = new Set()
  PARAM_ORDER.forEach(k => {
    if (s[k] === undefined || s[k] === null || typeof s[k] === 'object' || seen.has(k)) return
    seen.add(k); params.push({ k: LABELS[k] || k, v: fmt(k, s[k]) })
  })
  METRIC_ORDER.forEach(k => {
    if (s[k] === undefined || s[k] === null || typeof s[k] === 'object' || seen.has(k)) return
    seen.add(k); metrics.push({ k: LABELS[k] || k, v: fmt(k, s[k]) })
  })
  Object.keys(s).forEach(k => {
    if (seen.has(k) || s[k] === undefined || s[k] === null || typeof s[k] === 'object'
        || ['min','max','loads','facilities_list','uncovered'].includes(k)) return
    metrics.push({ k: LABELS[k] || k, v: fmt(k, s[k]) })
  })
  return { params, metrics }
})
const paramChips = computed(() => chips.value.params)
const metricChips = computed(() => chips.value.metrics)
</script>

<style scoped>
.rpanel{position:absolute;left:50%;transform:translateX(-50%);bottom:16px;z-index:6;
  width:min(720px,84%);border-radius:10px;overflow:hidden;
  background:rgba(255,255,255,.97);box-shadow:0 12px 40px rgba(60,80,140,.25);border:1px solid var(--line)}
.rp-head{display:flex;align-items:center;gap:11px;padding:12px 20px 8px;flex:none;
  background:linear-gradient(120deg,rgba(14,165,201,.12),rgba(109,93,240,.12))}
.rp-icon{width:36px;height:36px;border-radius:11px;background:#f2f5fc;display:flex;align-items:center;justify-content:center;font-size:18px;flex:none}
.rp-title{flex:1;min-width:0}
.rp-title b{font-size:15px;color:var(--tx);margin-right:9px}
.rp-title span{font-size:11px;color:var(--tx2)}
.rp-close{width:26px;height:26px;border-radius:9px;border:1px solid var(--line);
  background:#fff;color:var(--tx2);font-size:12px;cursor:pointer;flex:none}
.rp-close:hover{border-color:#c05050;color:#c05050}
.rp-chips{display:flex;flex-wrap:wrap;gap:8px;padding:6px 20px 14px;align-items:center}
.rp-grouplbl{font-size:11px;color:var(--tx2);font-weight:600;margin-right:2px;opacity:.75}
.chip{display:inline-flex;align-items:center;gap:6px;background:#f5f7fc;border:1px solid var(--line);
  border-radius:10px;padding:5px 12px;font-size:12px}
.chip.dim{background:#fafbfd;opacity:.92}
.chip i{font-style:normal;color:var(--tx2)}
.chip em{font-style:normal;font-weight:700;color:var(--tx);font-size:13px}
</style>
