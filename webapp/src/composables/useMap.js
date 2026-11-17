import { watch } from 'vue'
import * as maplibregl from 'maplibre-gl'
import { store } from '../store'
import { buildStyle, injectCartoLayers, applyBasemap, applyLabel, applyTerrain } from '../basemap'
import bus from '../bus'

let map = null
let styleReady = false
// HKSAR viewport bounds computed from the supplied administrative boundary.
const HK_BOUNDS = [[113.834898374, 22.154044375], [114.442389815, 22.56191985]]
export function getMap() { return map }

export function useMap(onPick) {
  function init(containerId) {
    styleReady = false
    map = new maplibregl.Map({
      container: containerId,
      style: buildStyle(),
      center: [114.138644095, 22.357982112],
      zoom: 9.5,
      minZoom: 8.5,
      maxZoom: 18,
      maxBounds: HK_BOUNDS,
      maxPitch: 72,
      antialias: true,
      attributionControl: false
    })
    window.map = map
    map.on('click', e => { if (store.pickSet && onPick) onPick(store.pickSet, e.lngLat) })
    map.on('style.load', () => {
      styleReady = true
      if (!map.__hkInitialBounds) {
        map.__hkInitialBounds = true
        map.fitBounds(HK_BOUNDS, { padding: 36, maxZoom: 10.5, duration: 0 })
      }
      injectCartoLayers(map)
      applyTerrain(map, store.t3d)
      applyBasemap(map, store.bm)
      applyLabel(map, store.bm, store.labelOn)
      drawPins()
      if (store.netOn) paintNetRoads(true)
      enableLocalRoadFallback()
      if (store.res) drawResults(store.res.features)
    })
    bus.on('results', feats => drawResults(feats))
    if (typeof window !== 'undefined') window.__mapCtl = { drawResults, drawParams }
    if (typeof window !== 'undefined') window.__map = map
    return map
  }

  function drawPins(retry) {
    if (!map) return
    if (retry === undefined) drawPins.__r = 0
    if (!styleReady) { map.once('style.load', drawPins); return }
    const fc = { type:'FeatureCollection', features:[] }
    Object.keys(store.points).forEach(id => {
      if (store.pinVis && store.pinVis[id] === false) return
      store.points[id].forEach((p, i) => fc.features.push({
        type:'Feature',
        geometry:{ type:'Point', coordinates:[p.lon, p.lat] },
        properties:{ set:id, name:p.name, weight:p.weight, num:i + 1 }
      }))
    })
    if (!map.getSource('pin-src')){
      map.addSource('pin-src', { type:'geojson', data: fc })
      map.addLayer({
        id:'pin-pt', type:'circle', source:'pin-src',
        paint:{
          'circle-radius':10,
          'circle-color':['match',['get','set'],
            'wp','#8b5cf6','dem','#4da3ff','fac','#fb923c','dep','#34d399','stop','#e879f9','comp','#f87171','#8b5cf6'],
          'circle-stroke-width':2,'circle-stroke-color':'#ffffff'
        }
      })
      map.addLayer({
        id:'pin-num', type:'symbol', source:'pin-src',
        minzoom:5,
        layout:{ 'text-field':['get','num'], 'text-size':12, 'text-font':['Noto Sans Bold'],
                 'text-anchor':'center', 'text-allow-overlap':true, 'text-ignore-placement':true },
        paint:{ 'text-color':'#ffffff', 'text-halo-color':'#00000066', 'text-halo-width':1 }
      })
    } else map.getSource('pin-src').setData(fc)
  }

  const KIND_COLORS = { wp:'#8b5cf6', dem:'#4da3ff', fac:'#fb923c', dep:'#34d399', stop:'#e879f9', comp:'#f87171',
    locations:'#8b5cf6', demands:'#4da3ff', candidates:'#fb923c', facilities:'#fb923c',
    points:'#fb923c', depot:'#34d399', stops:'#e879f9', competitors:'#f87171' }
  const SET_OF = { locations:'wp', demands:'dem', candidates:'fac', facilities:'fac',
    points:'fac', depot:'dep', stops:'stop', competitors:'comp' }
  function drawParams(){
    try {
      if (typeof window !== 'undefined') window.__dp = (window.__dp || 0) + 1
      if (!map) return
      if (!styleReady) { map.once('style.load', drawParams); return }
      Object.keys(KIND_COLORS).forEach(k => {
        try { map.removeLayer('par-' + k) } catch(e){}
        try { map.removeLayer('par-num-' + k) } catch(e){}
      })
      try { map.removeSource('par-src') } catch(e){}
      const feats = store.res && store.res.params && store.res.params.features || []
      const cnt = {}
      feats.forEach(f => {
        const k = (f.properties || {}).kind
        cnt[k] = (cnt[k] || 0) + 1
        f.properties = { ...f.properties, num: cnt[k] }
      })
      if (typeof window !== 'undefined') window.__dpFeats = feats.length
      if (!feats.length) return
      const kinds = new Set(feats.map(f => (f.properties || {}).kind))
      map.addSource('par-src', { type:'geojson', data:{ type:'FeatureCollection', features:feats } })
      if (typeof window !== 'undefined') window.__dpAdded = true
      // 参数点插在结果点图层之下(不遮盖得分配色),但仍盖过结果线/面
      const anchor = ['res-pt-dem', 'res-pt-fac', 'res-pt', 'pin-pt']
        .map(id => { try { return map.getLayer(id) ? id : null } catch(e) { return null } })
        .find(Boolean) || undefined
      ;[...kinds].forEach(k => {
        map.addLayer({
          id:'par-' + k, type:'circle', source:'par-src',
          filter:['==',['get','kind'],k],
          paint:{ 'circle-radius':10, 'circle-color':KIND_COLORS[k] || '#8b5cf6',
                  'circle-stroke-width':2, 'circle-stroke-color':'#fff' }
        }, anchor)
        map.setLayoutProperty('par-' + k, 'visibility', store.pinVis[SET_OF[k] || k] === false ? 'none' : 'visible')
        map.addLayer({
          id:'par-num-' + k, type:'symbol', source:'par-src', minzoom:5,
          filter:['==',['get','kind'],k],
          layout:{ 'text-field':['get','num'], 'text-size':12, 'text-font':['Noto Sans Bold'],
                   'text-anchor':'center', 'text-allow-overlap':true, 'text-ignore-placement':true },
          paint:{ 'text-color':'#ffffff', 'text-halo-color':'#00000066', 'text-halo-width':1 }
        })
        map.setLayoutProperty('par-num-' + k, 'visibility', store.pinVis[SET_OF[k] || k] === false ? 'none' : 'visible')
      })
    } catch(e) { if (typeof window !== 'undefined') window.__dpErr = String(e && e.message || e) }
  }
  function paintParVis(){
    if (!map) return
    const feats2 = store.res && store.res.params && store.res.params.features || []
    const kinds2 = new Set(feats2.map(f => (f.properties||{}).kind))
    ;[...kinds2].forEach(kk => {
      for (const id of ['par-' + kk, 'par-num-' + kk]){
        try { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', store.pinVis[SET_OF[kk] || kk] === false ? 'none' : 'visible') } catch(e){}
      }
    })
  }

  const RAMP = ['#d73027','#fe9929','#fed976','#78c679','#1a9850']
  function drawResults(feats) {
    if (typeof window !== 'undefined') { window.__dr = (window.__dr || 0) + 1; window.__drSld = !!(map && map.isStyleLoaded()) }
    if (!map) return
    if (!styleReady) { map.once('style.load', () => drawResults(feats)); return }
    ;['res-fill','res-line','res-line-od','res-line-asg','res-pt','res-pt-dem','res-pt-fac'].forEach(id => { try { map.removeLayer(id) } catch(e){} })
    try { map.removeSource('res-src') } catch(e){}
    if (!feats || !feats.length) {
      Object.keys(KIND_COLORS).forEach(k => {
        try { map.removeLayer('par-' + k) } catch(e){}
        try { map.removeLayer('par-num-' + k) } catch(e){}
      })
      try { map.removeSource('par-src') } catch(e){}
      drawPins()
      fitParams()
      return
    }
    const normZ = (fkey, zkey) => {
      const vals = feats.map(f => (f.properties||{})[fkey]).filter(v => typeof v === 'number')
      if (!vals.length) return
      const mn = Math.min(...vals), mx = Math.max(...vals, mn + 1e-9)
      feats.forEach(f => {
        const p = f.properties = f.properties || {}
        if (typeof p[fkey] === 'number') p[zkey] = Math.round(100 * (p[fkey] - mn) / (mx - mn))
      })
    }
    normZ('score', 'score_z')
    normZ('ratio', 'ratio_z')
    feats.forEach(f => {
      const p = f.properties = f.properties || {}
      const z = p.score_z !== undefined ? p.score_z : p.ratio_z
      if (z !== undefined) p.z = z
      else {
        const near = { vrp_path:0.6, vrp_od:0.4, assignment:0.5 }[p.kind] || 0.9
        p.z = Math.round(near * 100)
      }
    })
    const zRamp = ['interpolate', ['linear'], ['get', 'z'],
      0, '#d73027', 25, '#fe9929', 50, '#fed976', 75, '#78c679', 100, '#1a9850']
    const isOD = ['==', ['get', 'kind'], 'vrp_od']
    const isAsg = ['==', ['get', 'kind'], 'assignment']
    const isDem = ['==', ['get', 'kind'], 'demand']
    const isFac = ['==', ['get', 'kind'], 'facility']
    const isOtherLine = ['all', ['!=', ['get', 'kind'], 'vrp_od'], ['!=', ['get', 'kind'], 'assignment']]
    const isOtherPt = ['all', ['!=', ['get', 'kind'], 'demand'], ['!=', ['get', 'kind'], 'facility']]
    map.addSource('res-src', { type:'geojson', data:{ type:'FeatureCollection', features: feats } })
    const before = map.getLayer('pin-pt') ? 'pin-pt' : undefined
    try {
      if (feats.some(f => /Poly/.test(f.geometry.type)))
        map.addLayer({ id:'res-fill', type:'fill', source:'res-src',
          filter:['==',['geometry-type'],'Polygon'],
          paint:{ 'fill-color':'#34b4c9','fill-opacity':.22 } }, before)
      if (feats.some(f => (f.properties||{}).kind === 'vrp_od'))
        map.addLayer({ id:'res-line-od', type:'line', source:'res-src',
          filter: isOD,
          layout:{ 'line-cap':'round','line-join':'round' },
          paint:{ 'line-color':'#e8930c','line-width':1.6,'line-opacity':.55,
                  'line-dasharray':[2,3] } }, before)
      if (feats.some(f => (f.properties||{}).kind === 'assignment'))
        map.addLayer({ id:'res-line-asg', type:'line', source:'res-src',
          filter: isAsg,
          layout:{ 'line-cap':'round','line-join':'round' },
          paint:{ 'line-color':'#3b82f6','line-width':2.2,'line-opacity':.8 } }, before)
      if (feats.some(f => f.geometry.type==='LineString' && !['vrp_od','assignment'].includes((f.properties||{}).kind)))
        map.addLayer({ id:'res-line', type:'line', source:'res-src',
          filter:['all',['==',['geometry-type'],'LineString'], isOtherLine],
          layout:{ 'line-cap':'round','line-join':'round' },
          paint:{ 'line-color':'#e8930c','line-width':3.5,'line-opacity':.95 } }, before)
      const ptRad = ['interpolate',['linear'],['zoom'],8,4,16,8]
      if (feats.some(f => (f.properties||{}).kind === 'demand'))
        map.addLayer({ id:'res-pt-dem', type:'circle', source:'res-src',
          filter: isDem,
          paint:{
            'circle-radius': ptRad,
            'circle-color': zRamp,
            'circle-stroke-width':1.5,'circle-stroke-color':'#ffffff'
          } }, before)
      if (feats.some(f => (f.properties||{}).kind === 'facility'))
        map.addLayer({ id:'res-pt-fac', type:'circle', source:'res-src',
          filter: isFac,
          paint:{
            'circle-radius': ptRad,
            'circle-color': zRamp,
            'circle-stroke-width':1.5,'circle-stroke-color':'#ffffff'
          } }, before)
      if (feats.some(f => f.geometry.type==='Point' && !['demand','facility'].includes((f.properties||{}).kind)))
        map.addLayer({ id:'res-pt', type:'circle', source:'res-src',
          filter:['all',['==',['geometry-type'],'Point'], isOtherPt],
          paint:{
            'circle-radius': ptRad,
            'circle-color':'#d73027',
            'circle-stroke-width':1.5,'circle-stroke-color':'#ffffff'
          } }, before)
      if (typeof window !== 'undefined') window.__lOK = true
    } catch(e) { if (typeof window !== 'undefined') window.__lErr = String(e && e.message || e) }
    drawParams()
    fitResults(feats)
  }

  function fitResults(feats) {
    try{
      const pts = []
      const ext = c => { if (Array.isArray(c[0])) c.forEach(ext); else pts.push(c) }
      feats.forEach(f => ext(f.geometry.coordinates))
      if (pts.length){
        const xs = pts.map(c=>c[0]), ys = pts.map(c=>c[1])
        map.fitBounds([[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]],
          {padding:70, duration:700})
      }
    }catch(e){}
  }

  function fitParams() {
    const pf = (store.res && store.res.params && store.res.params.features) || []
    if (!pf.length) return
    setTimeout(() => {
      try{
        const pts = []
        pf.forEach(f => { if (f.geometry && Array.isArray(f.geometry.coordinates)) pts.push(f.geometry.coordinates) })
        if (pts.length){
          const xs = pts.map(c=>c[0]), ys = pts.map(c=>c[1])
          map.fitBounds([[Math.min(...xs),Math.min(...ys)],[Math.max(...xs),Math.max(...ys)]],
            {padding:70, duration:700})
        }
      }catch(e){}
    }, 50)
  }

  // 联动状态
  watch(() => store.bm, t => { if (map) { applyBasemap(map, t); setTimeout(() => drawPins(), 120) } })
  watch(() => store.labelOn, v => map && applyLabel(map, store.bm, v))
  watch(() => store.t3d, v => map && applyTerrain(map, v))
  watch(() => store.netOn, v => paintNetRoads(v))
  watch(() => [store.points.dem.length, store.points.fac.length,
               store.points.dep.length, store.points.stop.length,
               store.points.comp.length, store.points.wp?.length], () => drawPins())
  watch(() => ({ ...store.pinVis }), () => { drawPins(); paintParVis() }, { deep:true })
  function paintResVis(v) {
    if (!map) return
    ;[['fill', 'res-fill'], ['line', 'res-line'], ['od', 'res-line-od'],
      ['asg', 'res-line-asg'], ['ptdem', 'res-pt-dem'], ['ptfac', 'res-pt-fac'],
      ['pt', 'res-pt']].forEach(([k, id]) => {
      try { if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', v[k] ? 'visible' : 'none') } catch(e){}
    })
  }
  watch(() => ({ ...store.resVis }), v => paintResVis(v), { deep:true })
  bus.on('results', feats => { if (feats) paintResVis({ ...store.resVis }) })

  function mvtBaseUrl() {
    const dev = location.port === '5173'
    return (dev ? 'http://127.0.0.1:8004' : location.origin)
      + (location.pathname.includes('/network') ? '/network' : '')
  }

  async function enableLocalRoadFallback() {
    try {
      const response = await fetch(mvtBaseUrl() + '/mvt/info')
      if (!response.ok) return
      const info = await response.json()
      if (info.sources && (info.sources.roads_cn || info.sources.cn)) {
        store.netOn = true
        paintNetRoads(true)
      }
    } catch (e) {
      // Local MVT is optional; the external basemap remains usable when online.
    }
  }

  function paintNetRoads(on) {
    if (!map) return
    try {
      if (map.getLayer('cn-roads')) { map.removeLayer('cn-roads'); map.removeSource('cn-roads') }
    } catch(e) {}
    if (!on) return
    const run = () => {
      if (!styleReady) { map.once('style.load', run); return }
      try { if (map.getLayer('cn-roads')) map.removeLayer('cn-roads'); } catch(e) {}
      try { if (map.getSource('cn-roads')) map.removeSource('cn-roads'); } catch(e) {}
      map.addSource('cn-roads', { type:'vector', tiles:[mvtBaseUrl() + '/mvt/cn/{z}/{x}/{y}.mvt'], maxzoom:14, minzoom:6 })
      // 插在底图层之上、参数点/结果/标点图层之下,保证不遮盖任何分析内容
      const anchor = ['pin-pt', 'res-fill', 'res-line', 'res-pt', 'pin-num']
        .map(id => { try { return map.getLayer(id) ? id : null } catch(e) { return null } })
        .find(Boolean) || undefined
      map.addLayer({
        id:'cn-roads', type:'line', source:'cn-roads', 'source-layer':'roads_cn',
        paint:{
          'line-color':'#b0b8c9',
          'line-opacity':0.85,
          'line-width':['interpolate',['linear'],['zoom'],6,0.4,10,1.2,14,2.4],
        }
      }, anchor)
    }
    run()
  }

  return { init, drawResults }
}
