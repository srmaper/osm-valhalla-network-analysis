import { reactive, computed } from 'vue'
import { MODES } from './lib'
import bus from './bus'

function loadSettings(){
  try { return { serviceUrl:'', walkSpeed:4.9, bikeType:'hybrid', autoHighways:0.3,
                 ...JSON.parse(localStorage.getItem('na_settings') || '{}') } }
  catch(e){ return { serviceUrl:'', walkSpeed:4.9, bikeType:'hybrid', autoHighways:0.3 } }
}
export function saveSettings(){
  localStorage.setItem('na_settings', JSON.stringify(store.settings))
  localStorage.setItem('na_serviceUrl', store.settings.serviceUrl || '')
}

export const store = reactive({
  mode: null,
  pickSet: null,
  busy: false,
  res: null,
  results: [],
  drawerOpen: true,
  resOpen: true,
  raw: '',
  setMsg: {},
  toasts: [],
  svc: '',
  bm: 'carto',           // 默认 carto Positron;可切 satellite / none
  labelOn: true,
  t3d: false,
  costing: 'auto',
  showSettings: false,
  layersOpen: false,
  pinVis: { wp:true, dem:true, fac:true, dep:true, stop:true, comp:true },
  netOn: false,   // 路网数据集预览图层(默认不打开)
  resVis: { fill:true, line:true, od:true, asg:true, ptdem:true, ptfac:true, pt:true },
  histLoaded: false,
  settings: loadSettings(),
  sfca: { radius: 15, decay: 'gaussian', beta: 1.0 },
  loc: { p: 3, problem: 'min_impedance', cutoff: 15, capacity: 100 },
  service: { minutes: '5,10,15' },
  vrp: { vehicles: 2, capacity: 6, limit: 240 },
  wf: {},   // 每点集选择的权重字段(dem/fac/stop 等);'' = 默认(weight 属性/均等 1)
  lastRun: null,   // 最近一次成功分析的还原快照 {mode, costing, points, wf, params}
  points: { wp:[], dem:[], fac:[], dep:[], stop:[], comp:[] }
})

export function snapshotLastRun(mode){
  store.lastRun = JSON.parse(JSON.stringify({
    mode, costing: store.costing, wf: store.wf,
    points: store.points,
    sfca: store.sfca, loc: store.loc, service: store.service, vrp: store.vrp
  }))
}

export const cur = computed(() => MODES.find(m => m.id === store.mode) || null)
export const currentSet = computed(() => (cur.value && cur.value.sets.find(s => s.id === store.pickSet)) || null)
export const ready = computed(() => {
  if (!cur.value) return false
  if (store.mode === 'route') return store.points.wp.length >= 2
  if (cur.value.sets.some(s => store.points[s.id].length === 0)) return false
  if (store.mode==='loc' && store.loc.problem==='market_share' && store.points.comp.length===0) return false
  return true
})

export function toast(txt, kind='ok'){
  const t = { t: Date.now()+Math.random(), txt, kind }
  store.toasts = [t]                 // 同屏只保留一条,新的替换旧的
  setTimeout(()=>{ if (store.toasts[0] === t) store.toasts = [] }, 2500)
}
export function setMode(m){
  store.mode = m
  store.pickSet = cur.value.sets[0].id
  store.points = { wp:[], dem:[], fac:[], dep:[], stop:[], comp:[] }
  store.wf = {}
  store.res = null; store.raw = ''
  store.resOpen = false
  bus.emit('results', null)
}
if (typeof window !== 'undefined') window.__store = store