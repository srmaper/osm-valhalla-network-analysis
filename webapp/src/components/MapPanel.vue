<template>
  <main class="mapwrap">
    <div id="map"></div>

    <!-- 地名搜索(AIDA geoscope boundary)+ 地名高亮结果图层 -->
    <div class="gsearch">
      <input v-model="query" class="ginput" :class="{busy:searching}"
             placeholder="搜索地址"
             @keyup.enter="doSearch" @keydown.esc="clearSearch" />
      <button class="gbtn" @click="doSearch" :disabled="searching">{{ searching ? '…' : '搜索' }}</button>
      <div v-if="sMsg" class="gmsg" :class="{err:sFail}">{{ sMsg }}</div>
    </div>

    <!-- 指北针(原 test.html 样式,bearing 联动,点击复位北向) -->
    <div class="north" @click="resetNorth" title="点击恢复北向">
      <div class="north-in" :style="{ transform: 'rotate(' + (-bearing) + 'deg)' }">
        <svg viewBox="0 0 1024 1024" width="24" height="24">
          <path d="M509.3632 557.824l287.7952 145.408c19.1744 9.6512 39.9104-11.3408 30.3104-30.72L519.9616 18.4576C512 0.6912 486.4 0.7168 478.4128 18.5344L170.8288 671.5904c-9.6 19.456 11.1872 40.5248 30.3616 30.7968l289.024-144.5632a19.9168 19.9168 0 0 1 19.1488 0z m-10.24-54.2464a20.1472 20.1472 0 0 0-8.9856 2.4576l-249.088 126.6176L497.6128 80.0768v0.0256l1.5104 423.4752z m-118.0928 245.5552V1024h34.4064v-215.9872L557.8752 1024h36.8128V749.1328h-34.4064v215.808l-142.4384-215.808h-36.8128z" fill="#5a6a90"/>
        </svg>
      </div>
    </div>

    <!-- 底图按钮 + 比例尺(地图框右下角) -->
    <div class="scaler">
      <span class="slbl">{{ scale.label }}</span>
      <div class="sbar" :style="{width: scale.px + 'px'}"><i></i><i></i></div>
    </div>
    <div class="bdock">
      <div class="mini" :class="{on:store.bm==='carto'}" title="标准底图" @click="store.bm='carto'">淡</div>
      <div class="mini" :class="{on:store.bm==='satellite'}" title="影像底图" @click="store.bm='satellite'">影</div>
      <div class="mini" :class="{on:store.bm==='none'}" title="无底图" @click="store.bm='none'">无</div>
      <div class="mini" :class="{on:store.labelOn}" title="注记开关" @click="store.labelOn=!store.labelOn">注</div>
      <div class="mini" :class="{on:store.t3d}" title="3D 地形" @click="store.t3d=!store.t3d">3D</div>
    </div>

    <!-- 分析结果详情(底部) -->
    <ResultPanel />

    <!-- sfca 可达性图例 -->
    <div class="seg" v-if="store.mode==='sfca' && store.res && store.res.stats.max>0">
      <h4 style="font-size:12px;color:var(--ac);margin-bottom:7px">可达性得分(五档)</h4>
      <div class="bar"></div>
      <div style="display:flex;justify-content:space-between;width:180px;margin-top:4px;font-size:10px;color:var(--tx2)">
        <span>{{ store.res.stats.min }} 稀缺</span><span>{{ store.res.stats.max }} 充裕</span></div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { store } from '../store'
import { maplibregl, buildStyle, injectCartoLayers, applyBasemap, applyLabel, applyTerrain } from '../basemap'
import bus from '../bus'
import ResultPanel from './ResultPanel.vue'
import { useMap } from '../composables/useMap'
import { usePointSets } from '../composables/usePointSets'

const bearing = ref(0)
const scale = ref({ px: 110, label: '' })
let map = null

// ---- 地名搜索(geoscope boundary) ----
const query = ref('')
const searching = ref(false)
const sMsg = ref('')
const sFail = ref(false)
const API = 'https://aida.citylaydar.com/geoscope/api/boundary'

async function doSearch(){
  const q = query.value.trim()
  if (!q || !map) return
  searching.value = true; sMsg.value = ''
  try {
    const r = await fetch(API, { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ location: q }), signal: AbortSignal.timeout(20000) })
    const j = await r.json()
    if (j.status !== 'success' || !j.geojson || !j.geojson.features.length){
      sFail.value = true; sMsg.value = '未找到「' + q + '」的边界数据'
      return
    }
    drawBoundary(j.geojson, j.location || q)
    sFail.value = false
    sMsg.value = ''
  } catch (e) {
    sFail.value = true; sMsg.value = '搜索失败: ' + (e.message || e)
  } finally {
    searching.value = false
    setTimeout(() => { if (!sFail.value) sMsg.value = '' }, 4000)
  }
}
function drawBoundary(gj, name){
  try { ['gsearch-line','gsearch-fill','gsearch-lineline','gsearch-pt','gsearch-ptlbl'].forEach(id =>
        { if (map.getLayer(id)) map.removeLayer(id) })
        if (map.getSource('gsearch')) map.removeSource('gsearch') } catch(e){}
  // 按几何类型分组,分类型渲染(点/线/面混合同样支持)
  const groups = { pts:[], lines:[], polys:[] }
  for (const f of gj.features){
    if (!f.geometry) continue
    if (f.geometry.type === 'Point') groups.pts.push(f)
    else if (f.geometry.type === 'LineString' || f.geometry.type === 'MultiLineString') groups.lines.push(f)
    else if (f.geometry.type === 'Polygon' || f.geometry.type === 'MultiPolygon') groups.polys.push(f)
  }
  const parts = features => ({ type:'FeatureCollection', features })
  map.addSource('gsearch', { type:'geojson', data: { type:'FeatureCollection', features: [
    ...groups.polys, ...groups.lines, ...groups.pts ] } })
  const anchor = ['pin-pt','res-fill','res-line','res-pt','par-points']
    .map(id => { try { return map.getLayer(id) ? id : null } catch(e){ return null } })
    .find(Boolean) || undefined
  if (groups.polys.length){
    map.addLayer({ id:'gsearch-fill', type:'fill', source:'gsearch', filter:['==','$type','Polygon'],
      paint:{ 'fill-color':'#7c5cff', 'fill-opacity':0.10 } }, anchor)
    map.addLayer({ id:'gsearch-line', type:'line', source:'gsearch', filter:['==','$type','Polygon'],
      paint:{ 'line-color':'#6d5df0', 'line-width':2.5, 'line-dasharray':[4,2] } }, anchor)
  }
  if (groups.lines.length){
    map.addLayer({ id:'gsearch-lineline', type:'line', source:'gsearch', filter:['==','$type','LineString'],
      layout:{ 'line-cap':'round','line-join':'round' },
      paint:{ 'line-color':'#6d5df0', 'line-width':3.5 } }, anchor)
  }
  if (groups.pts.length){
    map.addLayer({ id:'gsearch-pt', type:'circle', source:'gsearch', filter:['==','$type','Point'],
      paint:{ 'circle-radius':8, 'circle-color':'#6d5df0',
              'circle-stroke-color':'#fff', 'circle-stroke-width':2 } }, anchor)
    map.addLayer({ id:'gsearch-ptlbl', type:'symbol', source:'gsearch', filter:['==','$type','Point'],
      layout:{ 'text-field': name, 'text-size':13, 'text-offset':[0,-1.6],
               'text-font':['Noto Sans Regular'] },
      paint:{ 'text-color':'#41356e', 'text-halo-color':'#fff', 'text-halo-width':1.4 } }, anchor)
  }
  if (groups.pts.length && !groups.lines.length && !groups.polys.length){
    // 纯点:定位固定 15 级
    map.easeTo({ center: groups.pts[0].geometry.coordinates.slice(0,2),
                 zoom: Math.min(map.getZoom(), 15), duration: 900 })
    return
  }
  const xs = [], ys = []
  const walk = c => { if (typeof c[0] === 'number') { xs.push(c[0]); ys.push(c[1]); return }
                      c.forEach(walk) }
  gj.features.forEach(f => { try { walk(f.geometry.coordinates) } catch(e){} })
  if (xs.length){
    const b = [[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]]
    map.fitBounds(b, { padding: 60, duration: 900, maxZoom: 18 })
  }
}
function clearSearch(){ query.value = ''; sMsg.value = ''
  try { ['gsearch-line','gsearch-fill','gsearch-lineline','gsearch-pt','gsearch-ptlbl'].forEach(id =>
        { if (map.getLayer(id)) map.removeLayer(id) })
        if (map.getSource('gsearch')) map.removeSource('gsearch') } catch(e){} }

const { addPoint } = usePointSets()
const { init } = useMap((setId, lngLat) => addPoint(setId, lngLat))

function niceScale(maxpx){
  const y = map.getCenter().lat * Math.PI / 180
  const mpp = 156543.03392 * Math.cos(y) / Math.pow(2, map.getZoom())
  const maxM = mpp * maxpx
  const pow = Math.pow(10, Math.floor(Math.log10(maxM)))
  const n = maxM / pow
  let m = n >= 5 ? 5 : n >= 2 ? 2 : 1
  const target = m * pow
  return { px: target / mpp, label: target >= 1000 ? (target/1000) + ' km' : target + ' m' }
}
function updScale(){
  if (!map || !map.getZoom) return
  try { scale.value = niceScale(110) } catch(e){}
}

onMounted(() => {
  map = init('map')
  map.on('move', () => { bearing.value = map.getBearing(); updScale() })
  map.on('load', updScale)
  updScale()
})

function resetNorth(){ try { map.easeTo({ bearing:0, pitch:0, duration:400 }) } catch(e){} }
</script>
