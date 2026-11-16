import { store, toast } from '../store'
import { CAPS, svcBase } from '../lib'

export function usePointSets() {
  function norm(p, i){
    return { name:String(p.name || p.NAME || ('P' + (i + 1))), lat:c1, lon:c0,
             weight:Number(p.weight || p.Weight || 1),
             props: p.props || p }
  }
  function loadSample(id, SAMPLES, parseGeojson, toast) {
    fetch(svcBase() + '/samples/' + SAMPLES[id])
      .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json() })
      .then(g => {
        const pts = []
        ;(g.features || []).forEach(ft => {
          if (!(ft.geometry && ft.geometry.type === 'Point')) return
          const p = ft.properties || {}, c = ft.geometry.coordinates
          pts.push({ name:String(p.name||p.NAME||('P'+(pts.length+1))), lat:c[1], lon:c[0],
                     weight:Number(p.weight||p.Weight||1) })
        })
        store.points[id] = pts
        toast(SAMPLES[id] + ' 已载入 ' + pts.length + ' 点')
      })
      .catch(e => toast('示例加载失败 ' + e.message, 'err'))
  }

  function uploadFile(file, setId, parseGeojson, toast) {
    const rd = new FileReader()
    rd.onload = () => {
      try {
        const g = JSON.parse(rd.result)
        const pts = []
        ;(g.features || []).forEach(ft => {
          if (!(ft.geometry && ft.geometry.type === 'Point')) return
          const p = ft.properties || {}, c = ft.geometry.coordinates
          pts.push({ name:String(p.name||p.NAME||('P'+(pts.length+1))), lat:c[1], lon:c[0],
                     weight:Number(p.weight||p.Weight||1) })
        })
        store.points[setId] = pts
        toast('已载入 ' + pts.length + ' 点')
      } catch (err) { toast('解析失败:' + err.message, 'err') }
    }
    rd.readAsText(file)
  }

  function clearSet(id) { store.points[id] = [] }

  function addPoint(id, lngLat) {
    const cap = CAPS[id]
    const arr = store.points[id]
    if (cap && arr.length >= cap) {
      store.setMsg = { ...(store.setMsg || {}), [id]: '该类点集最多 ' + cap + ' 个,超出不再计入' }
      clearTimeout((store.__msgT = store.__msgT || {})[id])
      store.__msgT[id] = setTimeout(() => {
        const m = { ...(store.setMsg || {}) }; delete m[id]; store.setMsg = m
      }, 4500)
      return
    }
    store.points[id] = [...arr, {
      name:'' + (arr.length + 1),
      lat:+lngLat.lat.toFixed(6), lon:+lngLat.lng.toFixed(6), weight:1 }]
    const m = { ...(store.setMsg || {}) }; delete m[id]; store.setMsg = m
  }

  return { loadSample, uploadFile, clearSet, addPoint }
}
