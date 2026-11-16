import { store, cur, toast, snapshotLastRun } from '../store'
import { buildBody, svcBase } from '../lib'
import bus from '../bus'

const OP = { sfca:'2sfca', loc:'loc-alloc', close:'closest', service:'service', vrp:'vrp', route:'route' }
const MODE_NAME = { sfca:'可达性', '2sfca':'可达性', loc:'选址', 'loc-alloc':'选址', close:'最近设施', closest:'最近设施', service:'等时圈', vrp:'VRP 配送', route:'路径规划' }
const SETS_BY_OP = { route:['wp'], '2sfca':['dem','fac'], 'loc-alloc':['dem','fac','comp'], closest:['dem','fac'], service:['fac'], vrp:['dep','stop'] }

function apiPost(op, body, timeoutMs = 300000) {
  const ctl = new AbortController()
  const t = setTimeout(() => ctl.abort(), timeoutMs)
  return fetch(svcBase() + '/api/' + op, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body), signal: ctl.signal
  }).then(r => r.json().then(d => {
    clearTimeout(t)
    return r.ok ? d : Promise.reject(d.error || ('HTTP ' + r.status))
  }))
}

export function useAnalysis() {
  function run() {
    const mode = store.mode
    snapshotLastRun(mode)   // 记住本次配置,供"重新尝试"还原
    const body = buildBody(mode, store)
    store.busy = true; store.res = null; store.raw = ''
    store.points = { wp:[], dem:[], fac:[], dep:[], stop:[], comp:[] }
    bus.emit('results', null)
    apiPost(OP[mode], body)
        .then(d => {
          const entry = {
            id: d.run_id || Date.now(),
            mode, modeName: MODE_NAME[mode],
            stats: d.stats, features: d.features, params: d.params,
            setsUsed: cur.value.sets.map(s => s.id),
              ts: new Date().toLocaleString('zh-CN', { hour12:false })
          }
        store.results.unshift(entry)
        store.mode = null
        store.pickSet = null
        store.raw = JSON.stringify(d, null, 2)
        setActive(entry)
        store.drawerOpen = true
      })
      .catch(e => toast('分析失败:' + e, 'err'))
      .finally(() => { store.busy = false })
  }

  function fetchHistory(force) {
    if (store.histLoaded && !force) return Promise.resolve()
    return fetch(svcBase() + '/api/runs').then(r => r.json()).then(d => {
      const have = new Set(store.results.map(r => r.id))
      ;(d.runs || []).forEach(m => {
        if (have.has(m.id)) return
        store.results.push({
          id: m.id, mode: m.op, modeName: MODE_NAME[m.op] || m.mode_name || m.op, stats: m.stats,
          setsUsed: SETS_BY_OP[m.op] || [],
          ts: (m.ts || '').slice(0, 19), features: null, hist: true
        })
      })
      store.results.sort((a, b) => (a.id < b.id ? 1 : -1))
      store.histLoaded = true
    }).catch(() => {})
  }

  function loadFeatures(entry) {
    const pq = entry.hist ? fetch(svcBase() + '/api/runs/' + entry.id + '/params')
      .then(r => r.json()).then(g => { entry.params = g }) : Promise.resolve()
    return pq.then(() => fetch(svcBase() + '/api/runs/' + entry.id + '/result')
      .then(r => r.json())
      .then(g => { entry.features = g.features || [] }))
  }

  function setActive(entry) {
    if (!entry) { store.res = null; store.raw=''; bus.emit('results', null); return }
    // 点击历史卡片:退出当前分析模式,取消点选类别,清空采点
    store.mode = null
    store.pickSet = null
    store.points = { wp:[], dem:[], fac:[], dep:[], stop:[], comp:[] }
    const jobs = []
    if (!entry.features) jobs.push(fetch(svcBase() + '/api/runs/' + entry.id + '/result').then(r => r.json()).then(g => { entry.features = g.features || [] }))
    if (!entry.params && entry.hist) jobs.push(fetch(svcBase() + '/api/runs/' + entry.id + '/params').then(r => r.json()).then(g => { entry.params = g }))
    if (jobs.length) Promise.all(jobs).then(() => applyActive(entry)).catch(() => {})
    else applyActive(entry)
  }
  function applyActive(entry) {
    store.res = entry
    store.resVis = { fill:true, line:true, od:true, asg:true, ptdem:true, ptfac:true, pt:true }
    store.resOpen = true
    store.raw = JSON.stringify({ features: entry.features, stats: entry.stats }, null, 2)
    bus.emit('results', entry.features || null)
  }

  function removeResult(id) {
    const i = store.results.findIndex(r => r.id === id)
    if (i < 0) return
    store.results.splice(i, 1)
    const base = store.settings.serviceUrl || ''
    fetch(svcBase() + '/api/runs/' + id, { method: 'DELETE' }).catch(() => {})
    if (store.res && store.res.id === id) setActive(store.results[0] || null)
  }

  return { run, setActive, removeResult, fetchHistory }
}
