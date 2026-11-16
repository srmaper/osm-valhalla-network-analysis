<template>
  <div class="cards">
    <!-- 卡片:每跑一次分析生成一张 -->
    <div v-for="r in store.results" :key="r.id" class="rcard" :class="{active: store.res && store.res.id===r.id}">
        <div class="chead" @click="setActive(r)">
          <span class="cicon" :style="{background: chrono(r.mode)}">{{ ICONS[r.mode] }}</span>
          <div class="ctitle"><b>{{ r.modeName }}</b></div>
          <button v-if="r.mode === 'route'" class="mini-btn drive" @click.stop="drive(r)" title="模拟驾驶">🚗</button>
          <button class="mini-btn" @click.stop="packDown(r)" title="整包下载(元数据+结果)">⬇</button>
          <button class="mini-btn danger" @click.stop="removeResult(r.id)" title="删除">✕</button>
        </div>
        <div class="cmeta">{{ r.ts }}</div>
      </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { store, toast } from '../store'
import { useAnalysis } from '../composables/useAnalysis'
const { setActive, removeResult, fetchHistory } = useAnalysis()

const ICONS = { route:'🚗', service:'⏱', close:'🎯', closest:'🎯', sfca:'📊', '2sfca':'📊', vrp:'🚚', loc:'📍', 'loc-alloc':'📍' }
const COLS = { route:'#8b5cf6', service:'#0ea5c9', close:'#34d399', closest:'#34d399', sfca:'#6d5df0', '2sfca':'#6d5df0', vrp:'#e8930c', loc:'#f59e0b', 'loc-alloc':'#f59e0b' }

onMounted(() => fetchHistory())

function chrono(id){ return COLS[id] }
function packDown(r){
  const a = document.createElement('a')
  const base = localStorage.getItem('na_serviceUrl') || ''
  a.href = base + '/api/runs/' + r.id + '/download'
  a.download = 'na_' + r.id + '.zip'
  a.click()
}

async function drive(r){
  const base = localStorage.getItem('na_serviceUrl') || ''
  try{
    const response = await fetch(base + '/api/runs/' + r.id + '/result')
    if(!response.ok) throw new Error('HTTP ' + response.status)
    const res = await response.json()
    const feats = res.features || (res.type === 'FeatureCollection' ? res.features : []) || []
    const line = feats.find(f => (f.properties || {}).kind === 'route' && f.geometry && f.geometry.type === 'LineString')
      || feats.find(f => f.geometry && f.geometry.type === 'LineString')
    if(!line){ toast('该结果没有可模拟的路线', 'error'); return }
    localStorage.setItem('na_drive_route', JSON.stringify({ type:'FeatureCollection', features:[line] }))
  }catch(e){ toast('读取结果失败: ' + e.message, 'error'); return }
  window.open('./driving.html', '_blank', 'noopener')
}
</script>

<style scoped>
.empty{font-size:12px;color:var(--tx2);text-align:center;padding:14px 6px}

.rcard{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 11px;transition:.15s}
.rcard + .rcard{margin-top:8px}
.rcard.active{border-color:rgba(14,165,201,.55);box-shadow:0 0 0 2px rgba(14,165,201,.14)}
.chead{display:flex;align-items:center;gap:9px;cursor:pointer}
.cicon{width:30px;height:30px;border-radius:9px;background:#f2f5fc;display:flex;align-items:center;justify-content:center;font-size:15px;flex:none}
.ctitle{flex:1;min-width:0}
.ctitle b{font-size:13px;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;display:block}
.cmeta{display:block;font-size:10px;color:var(--tx2);margin-top:1px;white-space:nowrap}
.mini-btn{padding:4px 9px;border-radius:8px;border:1px solid var(--line);background:#fff;color:var(--tx);
  font-size:11px;cursor:pointer;transition:.15s;white-space:nowrap;flex:none}
.mini-btn:hover{border-color:var(--ac);color:var(--ac)}
.mini-btn.ghost{color:var(--tx2)}
.mini-btn.drive{color:#0e7490;border-color:rgba(14,165,201,.45);background:rgba(14,165,201,.08)}
.mini-btn.drive:hover{border-color:#0ea5c9;color:#0b5f75}
.mini-btn.danger{color:#c05050;border-color:rgba(200,80,80,.35)}
.mini-btn.danger:hover{border-color:#c05050;color:#a04040}
.mini-btn:disabled{opacity:.45;cursor:default}

</style>
