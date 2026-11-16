<template>
  <div class="lpop">
    <div class="lsec">
      <div class="ltitle">数据图层</div>
      <div class="lrow">
        <span class="leye" :class="{off:!store.netOn}" @click="store.netOn=!store.netOn">{{ store.netOn ? '👁' : '🚫' }}</span>
        <svg v-if="store.netOn" class="licon" viewBox="0 0 14 14">
          <path d="M1.5 10 Q 5 2, 7.5 6.5 T 13 4" :stroke="'#b0b8c9'" stroke-width="2.4" fill="none" stroke-linecap="round"/>
        </svg>
        <span v-else class="licon licon-off"></span>
        <span class="lname">路网数据集</span>
        <span class="lcount">全国 OSM</span>
      </div>
    </div>

    <template v-if="store.res">
      <div class="lsec">
        <div class="ltitle">分析图层 · 参数点</div>
        <div class="lrow zoom" v-for="k in usedSets" :key="k" @click="zoomKind(k)" title="点击缩放到该图层">
          <span class="leye" :class="{off:!store.pinVis[k]}" @click.stop="togglePin(k)">{{ store.pinVis[k] ? '👁' : '🚫' }}</span>
          <span class="ldot" :style="{background:COLORS[k]}"></span>
          <span class="lname">{{ SET_LABELS[k] || k }}</span>
          <span class="lcount">{{ (store.res.params||{features:[]}).features.filter(f => setOf((f.properties||{}).kind) === setOf(k)).length }}</span>
        </div>
      </div>

      <div class="lsec" v-if="mainRows.length">
        <div class="ltitle">分析图层 · 主要结果</div>
        <div class="lrow zoom" v-for="r in mainRows" :key="r.key" @click="zoomRow(r)" title="点击缩放到该图层">
          <span class="leye" :class="{off:!store.resVis[r.key]}" @click="store.resVis[r.key]=!store.resVis[r.key]">{{ store.resVis[r.key] ? '👁' : '🚫' }}</span>
          <svg v-if="r.shape==='poly'" class="licon" viewBox="0 0 14 14">
            <path d="M2 3.5 L12 3 L13 10 L7 12.5 L1.5 10 Z" :fill="r.color" fill-opacity=".45" :stroke="r.color" stroke-width="1.6" stroke-linejoin="round"/>
          </svg>
          <svg v-else-if="r.shape==='line'" class="licon" viewBox="0 0 14 14">
            <path d="M1.5 10 Q 5 2, 7.5 6.5 T 13 4" :stroke="r.color" stroke-width="2.4" fill="none" stroke-linecap="round"/>
          </svg>
          <span v-else-if="r.ramp" class="lramp" :style="{background:r.ramp}"></span>
          <svg v-else class="licon" viewBox="0 0 14 14">
            <circle cx="7" cy="7" r="4.5" :fill="r.color" :stroke="r.color"/>
          </svg>
          <span class="lname">{{ r.label }}</span>
          <span class="lcount">{{ r.count }} {{ r.unit || '项' }}</span>
        </div>
      </div>

      <div class="lsec" v-if="auxRows.length">
        <div class="ltitle">分析图层 · 辅助图层</div>
        <div class="lrow zoom" v-for="r in auxRows" :key="r.key" @click="zoomRow(r)" title="点击缩放到该图层">
          <span class="leye" :class="{off:!store.resVis[r.key]}" @click="store.resVis[r.key]=!store.resVis[r.key]">{{ store.resVis[r.key] ? '👁' : '🚫' }}</span>
          <span class="ldot" :style="{background:r.color}"></span>
          <span class="lname">{{ r.label }}</span>
          <span class="lcount">{{ r.count }} 项</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { store } from '../store'
import { COLORS } from '../lib'

const SET_LABELS = { wp:'途经点', dem:'需求点', fac:'设施点', dep:'仓库', stop:'停靠点', comp:'竞品点' }
function togglePin(k){ store.pinVis[k] = !store.pinVis[k] }

const SET_OF = { locations:'wp', demands:'dem', candidates:'fac', facilities:'fac',
  points:'fac', depot:'dep', stops:'stop', competitors:'comp' }
const setOf = k => SET_OF[k] || k
const usedSets = computed(() => {
  const pf = (store.res.params || {}).features || []
  if (!pf.length) return []
  const sets = new Set(pf.map(f => SET_OF[(f.properties || {}).kind] || (f.properties || {}).kind))
  return [...sets]
})
const kindsC = computed(() => (store.res.features || []).map(f => (f.properties || {}).kind))
const asgMain = computed(() => ['close','closest','loc','loc-alloc'].includes(store.res.mode))
const lineLabel = computed(() => {
  switch (store.res.mode) {
    case 'vrp': return '配送路径(实际路网)'
    case 'route': return '路径线'
    default: return '结果线'
  }
})
const RAMP = 'linear-gradient(90deg,#d73027,#fed976,#1a9850)'
const mainRows = computed(() => {
  const fs = store.res.features || []
  const kinds = kindsC.value
  const rows = []
  if (fs.some(f => /Poly/.test(f.geometry.type)))
    rows.push({ key:'fill', label: store.res.mode==='service' ? '等时圈/服务区' : '结果面',
      color:'#34b4c9', shape:'poly', count: fs.filter(f => /Poly/.test(f.geometry.type)).length,
      filter: f => /Poly/.test(f.geometry.type) })
  const notODAsg = f => /LineString/.test(f.geometry.type) && !['vrp_od','assignment'].includes((f.properties||{}).kind)
  const lineMain = fs.some(notODAsg)
  if (lineMain)
    rows.push({ key:'line', label: lineLabel.value, color:'#e8930c', shape:'line',
      count: fs.filter(notODAsg).length, filter: notODAsg })
  if (asgMain.value && kinds.includes('assignment'))
    rows.push({ key:'asg', label:'分配连线(需求 → 设施)', color:'#3b82f6', shape:'line',
      count: kinds.filter(k => k==='assignment').length,
      filter: f => (f.properties||{}).kind==='assignment' })
  if (kinds.includes('demand'))
    rows.push({ key:'ptdem', label:'可达性得分(需求点)', ramp:RAMP,
      count: kinds.filter(k => k==='demand').length,
      filter: f => (f.properties||{}).kind==='demand' })
  if (kinds.includes('facility'))
    rows.push({ key:'ptfac', label:'供需比(设施点)', ramp:RAMP,
      count: kinds.filter(k => k==='facility').length,
      filter: f => (f.properties||{}).kind==='facility' })
  const otherPts = fs.filter(f => /Point/.test(f.geometry.type) && !['demand','facility'].includes((f.properties||{}).kind))
  if (otherPts.length)
    rows.push({ key:'pt', label:'结果点', color:'#d73027', shape:'pt', count: otherPts.length,
      filter: f => /Point/.test(f.geometry.type) && !['demand','facility'].includes((f.properties||{}).kind) })
  return rows
})
const auxRows = computed(() => {
  const fs = store.res.features || []
  const kinds = kindsC.value
  const rows = []
  if (kinds.includes('vrp_od'))
    rows.push({ key:'od', label:'OD 直线(几何示意)', color:'#e8930c',
      count: kinds.filter(k => k==='vrp_od').length,
      filter: f => (f.properties||{}).kind==='vrp_od' })
  if (!asgMain.value && kinds.includes('assignment'))
    rows.push({ key:'asg', label:'分配连线(需求 → 最近设施)', color:'#3b82f6',
      count: kinds.filter(k => k==='assignment').length,
      filter: f => (f.properties||{}).kind==='assignment' })
  return rows
})

function fitTo(feats){
  const map = window.map
  if (!map || !feats || !feats.length) return
  const pts = []
  const ext = c => { if (Array.isArray(c[0])) c.forEach(ext); else pts.push(c) }
  feats.forEach(f => ext((f.geometry || {}).coordinates))
  if (!pts.length) return
  const xs = pts.map(c => c[0]), ys = pts.map(c => c[1])
  try { map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]],
    { padding: { top: 90, bottom: 140, left: 70, right: 90 }, duration: 700 }) } catch(e){}
}
const zoomKind = k => fitTo(((store.res.params || { features: [] }).features
  .filter(f => setOf((f.properties || {}).kind) === setOf(k))))
const zoomRow = r => fitTo((store.res.features || []).filter(f => (r.filter || (() => true))(f)))
</script>

<style scoped>
.lpop{width:100%;padding:0 0 2px}
.lsec{margin-bottom:10px}
.lsec:last-child{margin-bottom:0}
.ltitle{font-size:11px;color:var(--tx2);letter-spacing:1px;margin-bottom:7px;font-weight:600}
.licon-off{border-radius:50%;background:#cfd6e4;opacity:.5}
.lrow{display:flex;align-items:center;gap:7px;padding:4px 6px;border-radius:8px;font-size:12px;cursor:pointer}
.lrow:hover{background:rgba(14,165,201,.08)}
.lchip{display:inline-flex;padding:4px 10px;border-radius:8px;border:1px solid var(--line);
  background:#fff;color:var(--tx2);cursor:pointer;font-size:11px}
.lchip.on{color:var(--ac2);background:rgba(14,165,201,.10);border-color:rgba(14,165,201,.5)}
.lsub{font-size:10px;color:var(--tx2);margin:8px 0 3px;padding-top:6px;border-top:1px dashed var(--line)}
.leye{cursor:pointer;font-size:13px;width:20px;text-align:center}
.leye.off{opacity:.4}
.lramp{width:14px;height:10px;border-radius:5px;flex:none;display:inline-block}
.ldot{width:9px;height:9px;border-radius:50%;flex:none}
.licon{width:14px;height:14px;flex:none}
.lname{flex:1;color:var(--tx)}
.lcount{font-size:10px;color:var(--tx2)}
.lcur{font-size:10px;color:var(--ac)}
.empty{font-size:11px;color:var(--tx2);padding:4px 6px}
</style>
