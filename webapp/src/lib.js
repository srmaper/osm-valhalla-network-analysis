export function svcBase() {
  const base = localStorage.getItem('na_serviceUrl') || ''
  if (base) return base
  return location.pathname.includes('/network') ? '/network' : ''
}
export function apiPost(op, body, timeoutMs = 300000) {
  const base = svcBase()
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  return fetch(base + '/api/' + op, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: ctl.signal
  }).then(r => r.json().then(d => {
    clearTimeout(t)
    return r.ok ? d : Promise.reject(d.error || ('HTTP ' + r.status))
  }))
}
export function getJson(url) {
  const base = svcBase()
  return fetch(base + url).then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
}
export const COLORS = { wp:'#8b5cf6', dem:'#4da3ff', fac:'#fb923c', dep:'#34d399', stop:'#e879f9', comp:'#f87171' }
export const CAPS = { wp:12, dem:300, fac:60, dep:5, stop:60, comp:60 }
export const MODES = [
  { id:'route', name:'路径规划', tip:'点对点路径规划,支持备选',
    sets:[{id:'wp', label:'途经点', hint:'按顺序点击 2 个及以上途经点(起→终)'}] },
  { id:'service', name:'等时圈', tip:'批量等时圈',
    sets:[{id:'fac', label:'设施点', hint:''}] },
  { id:'close', name:'最近设施', tip:'最近设施分配',
    sets:[{id:'dem', label:'需求点', hint:''},{id:'fac', label:'设施点', hint:''}] },
  { id:'sfca', name:'可达性', tip:'2SFCA 公共设施可达性',
    sets:[{id:'dem', label:'需求点', hint:'社区/小区;weight 属性=人口(缺省 1)'},
          {id:'fac', label:'设施点', hint:'医院/学校/公园;weight=容量规模(缺省 1)'}] },
  { id:'vrp', name:'VRP 配送', tip:'车辆路径规划',
    sets:[{id:'dep', label:'仓库', hint:'最多 5 个起点,按最近仓库分簇配送'},{id:'stop', label:'停靠点', hint:'weight=需求量'}] },
  { id:'loc', name:'选址', tip:'位置分配 p-median / 最大覆盖等',
    sets:[{id:'dem', label:'需求点', hint:'weight=人口'},
          {id:'fac', label:'候选点', hint:'候选地址'}] }
]
export const SAMPLES = { dem:'sample_demands.geojson', fac:'sample_facilities.geojson',
                         dep:'sample_depot.geojson', stop:'sample_stops.geojson' }
export function plain(arr, st, id){
  const f = st && st.wf ? st.wf[id] : ''
  return arr.map(p=>{
    let w = p.weight || 1
    if (f && p.props && p.props[f] != null && p.props[f] !== '') {
      const v = Number(p.props[f]); if (isFinite(v)) w = v
    }
    return {name:p.name, lat:p.lat, lon:p.lon, weight:w}
  })
}
export function parseGeojson(g){
  const J=[]
  ;(g.features||[]).forEach(ft=>{
    if(!(ft.geometry && ft.geometry.type==='Point')) return
    const p=ft.properties||{}, c=ft.geometry.coordinates
    J.push({name:String(p.name||p.NAME||('P'+(J.length+1))), lat:c[1], lon:c[0],
            weight:Number(p.weight||p.Weight||1), props:p})
  })
  return J
}
export function propFields(arr){
  const keys = []
  arr.forEach(p => { for (const k of Object.keys(p.props||{})) if (!keys.includes(k) && keys.length<60) keys.push(k) })
  return keys
}
export function costingOptions(st){
  const s = st.settings || {}
  const c = st.costing
  if (c === 'pedestrian') return { pedestrian: { walking_speed: Number(s.walkSpeed) || 4.9 } }
  if (c === 'bicycle') return { bicycle: { bicycle_type: s.bikeType || 'hybrid' } }
  return {}
}
export function buildBody(mode, st){
  const pts=st.points, c=st.costing
  const co = costingOptions(st)
  if(mode==='route') return {locations:plain(pts.wp,st,'wp'), costing:c, costing_options: co}
  if(mode==='sfca') return {demands:plain(pts.dem,st,'dem'), facilities:plain(pts.fac,st,'fac'),
    radius_min:st.sfca.radius, decay:st.sfca.decay, beta:st.sfca.beta, costing:c, costing_options: co}
  if(mode==='loc') return {demands:plain(pts.dem,st,'dem'), candidates:plain(pts.fac,st,'fac'), p:st.loc.p,
    problem:st.loc.problem, cutoff:st.loc.cutoff,
    capacity:(st.loc.problem==='cap_coverage' && st.wf && st.wf.fac) ? 'weight' : st.loc.capacity,
    competitors: pts.comp.length?plain(pts.comp,st,'comp'):undefined, costing:c, costing_options: co}
  if(mode==='close') return {demands:plain(pts.dem,st,'dem'), facilities:plain(pts.fac,st,'fac'), costing:c, costing_options: co}
  if(mode==='service') return {points:plain(pts.fac,st,'fac'), minutes:parseMinutes(st.service.minutes), costing:c, costing_options: co}
  return {depot:plain(pts.dep,st,'dep'), stops:plain(pts.stop,st,'stop'), vehicles:st.vrp.vehicles,
    capacity:st.vrp.capacity, time_limit_min:st.vrp.limit, costing:c, costing_options: co}
}
export function parseMinutes(txt){
  const arr = String(txt).split(/[,，;；\s]+/).map(x => parseFloat(x))
    .filter(x => isFinite(x) && x > 0 && x <= 300)
  return arr.length ? arr : [10]
}
