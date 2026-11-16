<template>
  <aside class="side">
    <SettingsModal v-if="store.showSettings" />
    <div class="brand">
      <h1>网络分析 · 可达性实验台</h1>
      <button class="gear" title="分析设置" @click="store.showSettings=true">⚙</button>
    </div>

    <nav class="extbox">
      <div class="tab ext" @click="help='net'">功能介绍</div>
      <div class="tab ext" @click="tourStart">新手指引</div>
      <div class="tab ext todo" title="待定">···</div>
    </nav>

    <div class="tabs modetabs">
      <div v-for="m in MODES" :key="m.id" class="tab" :class="{on:store.mode===m.id}"
           :title="m.tip" @click="setMode(m.id)">{{ m.name }}</div>
    </div>

    <div class="body">
      <!-- 点集 -->
      <div class="sec" v-if="cur">
        <h3>点集 <template v-if="currentSet">· 在地图上点击采集「{{ currentSet.label }}」</template></h3>
        <div v-for="ps in cur.sets" :key="ps.id" class="card" :class="{hl: store.pickSet===ps.id}">
          <div class="row" style="justify-content:space-between;flex-wrap:nowrap;gap:4px">
            <span class="chip" :class="{on:store.pickSet===ps.id}" @click="store.pickSet = store.pickSet===ps.id ? null : ps.id"
                  style="flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;justify-content:flex-start">
              <span class="dot" style="flex:none"></span>
              <span style="overflow:hidden;text-overflow:ellipsis;max-width:180px">{{ ps.label }}</span>
              <b style="color:#64748b;flex:none">{{ store.points[ps.id].length }}</b>
              <b class="cap" style="color:#64748b;font-weight:600;font-size:11px;flex:none">≤{{ CAPS[ps.id] }}</b>
            </span>
            <span style="display:flex;gap:5px;flex:none">
              <button v-if="SAMPLES[ps.id]" class="btn ghost" style="padding:3px 7px;font-size:11px" :disabled="store.busy" @click="loadSample(ps.id)">示例</button>
              <button class="btn ghost" style="padding:3px 7px;font-size:11px" @click="fileInput.click()">上传</button>
              <button v-if="store.points[ps.id].length" class="btn danger" style="padding:3px 7px;font-size:11px" @click="clearSet(ps.id)">清空</button>
            </span>
          </div>
          <div v-if="store.setMsg && store.setMsg[ps.id]" class="setwarn">{{ store.setMsg[ps.id] }}</div>
          <div class="row" v-if="fields(ps.id).length">
            <label>权重字段</label>
            <select v-model="store.wf[ps.id]" style="flex:1">
              <option value="">默认(weight 属性)</option>
              <option v-for="f in fields(ps.id)" :key="f" :value="f">{{ f }}</option>
            </select>
          </div>
        </div>
        <input ref="fileInput" type="file" accept=".json,.geojson" style="display:none" @change="upload" />
      </div>

      <!-- 参数 -->
      <div class="sec">
        <h3>参数</h3>
        <div class="card">
          <template v-if="cur">
          <div class="row"><label>出行方式</label>
            <select v-model="store.costing">
              <option value="pedestrian">步行</option><option value="bicycle">自行车</option><option value="auto">小汽车</option>
            </select>
          </div>

          <template v-if="store.mode==='route'">
            <div class="hint">按顺序点击途经点(至少 2 个:起点 → 终点),输出路线几何与总里程/耗时。</div>
          </template>
          <template v-else-if="store.mode==='sfca'">
            <div class="row"><label>搜索半径</label>
              <input type="range" min="5" max="60" step="5" v-model.number="store.sfca.radius" style="flex:1" />
              <b style="min-width:56px;color:var(--ac)">{{ store.sfca.radius }} min</b></div>
            <div class="row" style="flex-wrap:nowrap"><label>衰减函数</label>
              <select v-model="store.sfca.decay" style="flex:1;min-width:0">
                <option value="gaussian">高斯 Ga2SFCA(推荐)</option>
                <option value="e2sfca">增强 E2SFCA(3 分段)</option>
                <option value="binary">经典 2SFCA(二值)</option>
                <option value="power">重力型(幂函数 β)</option>
              </select>
              <button class="btn ghost helpbtn" title="各衰减函数含义" @click="showHelp(H_SVFCA)">?</button></div>
            <div class="row" v-if="store.sfca.decay==='power'">
              <label>β</label>
              <input type="range" min="0.5" max="3" step="0.1" v-model.number="store.sfca.beta" style="flex:1" />
              <b style="color:var(--ac)">{{ store.sfca.beta }}</b></div>
            <div class="hint">需求点 <b>weight</b>=人口(缺省 1);设施点 weight=容量。输出每个需求点 <kbd>score</kbd>,地图五档着色(红=稀缺,绿=充裕)。</div>
          </template>

          <template v-else-if="store.mode==='loc'">
          <div class="row" style="flex-wrap:nowrap"><label>P</label>
            <input type="number" v-model.number="store.loc.p" min="1" max="12" style="width:66px" />
            <select v-model="store.loc.problem" style="flex:1;min-width:0">
              <option value="min_impedance">P-中值</option><option value="max_coverage">最大覆盖</option>
              <option value="cap_coverage">容量约束覆盖</option><option value="min_facilities">最少设施</option>
              <option value="max_attendance">最大客流</option><option value="market_share">市场份额</option>
            </select>
            <button class="btn ghost helpbtn" title="各选址目标含义" @click="showHelp(H_LOC)">?</button></div>
            <div class="row" v-if="['max_coverage','cap_coverage','max_attendance','market_share'].includes(store.loc.problem)">
              <label>截断 min</label><input type="number" v-model.number="store.loc.cutoff" min="2" style="width:78px" /></div>
            <div class="row" v-if="store.loc.problem==='cap_coverage'">
              <label>容量</label><input type="number" v-model.number="store.loc.capacity" min="1" style="width:88px" /></div>
            <div class="row" v-if="store.loc.problem==='market_share'">
              <span class="chip" :class="{on:store.pickSet==='comp'}" @click="store.pickSet='comp'">
                <span class="dot" style="background:#f87171"></span>竞品点 {{ store.points.comp.length }} <b class="cap" style="color:#64748b;font-weight:600;font-size:11px">≤{{ CAPS.comp }}</b></span></div>
          </template>

          <template v-else-if="store.mode==='close'">
            <div class="hint">每个需求点 → 最近设施,输出分配连线与耗时。</div>
          </template>

          <template v-else-if="store.mode==='service'">
            <div class="row"><label>圈层 (min)</label>
              <input type="text" v-model="store.service.minutes" style="flex:1"
                     placeholder="如: 5,10,15" /></div>
            <div class="hint">支持多个值(逗号分隔),如 <kbd>5,10,15</kbd>,一次生成多层等时圈。</div>
          </template>

          <template v-else-if="store.mode==='vrp'">
            <div class="row"><label>载具</label>
              <input type="number" v-model.number="store.vrp.vehicles" min="1" max="10" style="width:76px" /></div>
            <div class="row"><label>单次容量</label><input type="number" v-model.number="store.vrp.capacity" min="1" style="width:84px" /></div>
            <div class="row"><label>单线限时 min</label>
              <input type="number" v-model.number="store.vrp.limit" min="30" step="15" style="width:96px" /></div>
          </template>

          <div v-for="m in store.toasts" :key="m.t" class="msg" :class="m.kind">{{ m.txt }}</div>
          </template>
          <template v-else>
            <div class="hint" style="padding:8px 2px;text-align:center">
              请选择分析方式 —— 点击上方按钮切换,切换会清空当前地图图层和已采点。
            </div>
          </template>
        </div>
      </div>

      <!-- 执行 -->
      <div class="sec">
        <h3>执行</h3>
        <div class="card">
          <button class="btn" style="width:100%" :disabled="store.busy || (store.mode && !ready)" @click="go">
            <span v-if="store.busy" class="spin"></span>{{ execLabel }}
          </button>
          <div v-if="store.busy" class="hint" style="margin-top:6px;color:var(--ac)">
            <span class="spin"></span>请求路网矩阵…</div>
        </div>
      </div>
    </div>
    <Teleport to="body">
      <div v-if="tour >= 0" class="tourspot" :style="spotStyle"></div>
      <div v-if="tour >= 0" class="tourcard" :style="cardStyle" @click.stop>
        <div class="thead"><h4>{{ TOUR_STEPS[tour].title }}</h4><span class="tskip" @click="tour=-1">跳过</span></div>
        <p class="ttext" v-html="TOUR_STEPS[tour].text"></p>
        <div class="tbtns">
          <span class="tnum">{{ tour + 1 }} / {{ TOUR_STEPS.length }}</span>
          <button v-if="tour > 0" class="btn ghost" style="padding:6px 12px" @click="tourGo(-1)">上一步</button>
          <button class="btn" style="padding:6px 14px" @click="tourGo(1)">{{ tour === TOUR_STEPS.length - 1 ? '完成' : '下一步' }}</button>
        </div>
      </div>
    </Teleport>
    <div v-if="helpVal" class="helpmask" @click.self="help=null">
      <div class="helpcard" :class="{wide: helpVal.type==='guide'}">
        <h4>{{ helpVal.title }}</h4>
        <template v-if="helpVal.paras">
          <p v-for="(x, i) in helpVal.paras" :key="i" class="helppara">{{ x }}</p>
        </template>
        <div v-for="x in helpVal.items" :key="x.k" class="helpitem"><b>{{ x.k }}</b><span>{{ x.v }}</span></div>
        <button class="btn" style="width:100%;margin-top:10px" @click="help=null">知道了</button>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import bus from '../bus'
import { store, cur, ready, setMode, toast, snapshotLastRun } from '../store'
import SettingsModal from './SettingsModal.vue'
import { MODES, COLORS, SAMPLES, CAPS, getJson, parseGeojson, propFields } from '../lib'
import { useAnalysis } from '../composables/useAnalysis'

const fileInput = ref(null)
const { run } = useAnalysis()
const MODE_NAME = { wp:'路径规划', route:'路径规划', service:'等时圈', close:'最近设施', sfca:'可达性', vrp:'VRP 配送', loc:'选址' }

const execLabel = computed(() => store.busy ? '计算中…'
  : (store.mode ? '开始分析'
     : (store.lastRun ? '重新尝试 · ' + (MODE_NAME[store.lastRun.mode] || store.lastRun.mode) : '开始分析')))

function go(){
  if (store.mode) return run()
  const L = store.lastRun
  if (!L) return
  store.mode = L.mode
  store.pickSet = (cur.value && cur.value.sets[0].id) || null
  store.points = JSON.parse(JSON.stringify(L.points))
  store.wf = JSON.parse(JSON.stringify(L.wf || {}))
  store.costing = L.costing
  store.sfca = { ...L.sfca }; store.loc = { ...L.loc }
  store.service = { ...L.service }; store.vrp = { ...L.vrp }
  store.res = null; store.raw = ''; store.resOpen = false
  bus.emit('results', null)
}

function fields(id){ return propFields(store.points[id] || []) }

const help = ref(null)
const showHelp = h => { help.value = h }
const helpVal = computed(() => typeof help.value === 'string' ? HELP_EXT[help.value] : help.value)

const HELP_EXT = {
  net: {
    title:'功能介绍 · 实现原理', items:[
      { k:'数据来源', v:'全国范围 OpenStreetMap 路网(osm.pbf),经 Valhalla 构建为空间引用图结构(Dijkstra 搜索 + Contraction Hierarchies 分层加速)' },
      { k:'离线加速', v:'路网预编译为 Valhalla 瓦片并常驻内存,查询时不回文件系统;矩阵/等时圈等分析直接在图上计算' },
      { k:'服务架构', v:'路由服务(Valhalla)+ 路网矢量瓦片(MVT 预览)+ 分析 API 与前端,三个轻量服务并列;全链路离线运行,不依赖外部 API' },
    ]},
  guide: {
    title:'新手指引 · 三步上手', items:[
      { k:'第 1 步 选模块', v:'点击下方 6 个模块之一:路径规划 / 等时圈 / 最近设施 / 可达性 / 选址 / VRP 配送' },
      { k:'第 2 步 备数据', v:'每个模块列出所需点集;可在地图上逐个点击采集,也可用点集卡上的「示例」「上传」按钮快速准备' },
      { k:'第 3 步 开始分析', v:'点「开始分析」,结果叠加在地图上;右侧「图层控制」可分层开关,历史分析可随时回看' },
    ]},
}
const H_SVFCA = { title:'服务水平 / 衰减函数', items:[
  { k:'高斯 Ga2SFCA(推荐)', v:'距离按钟形曲线连续衰减,越远贡献越小、边缘趋 0。最贴近真实出行行为,分数连续无跳变,是当前文献主流。' },
  { k:'增强 E2SFCA(3 分段)', v:'把搜索半径内分成 3 段(约 0-1/3、1/3-2/3、2/3-1),各给固定权重 1/0.68/0.22 计数。计算简单易解释,但分段边界处分数会跳变。' },
  { k:'经典 2SFCA(二值)', v:'1971 年的最原始版本:半径内贡献一律记 1,半径外为 0。最简单,会高估边缘位置,一般只作对照基准。' },
  { k:'重力型(幂函数 β)', v:'来自引力模型,贡献按 d^-β 衰减,β 越大对远距离惩罚越狠(用 β 滑杆调节)。适合"远一点就明显更差"的研究场景。' }
]}
const H_LOC = { title:'选址目标含义', items:[
  { k:'P-中值', v:'从候选点中选 P 个,使所有需求点到各自最近设施的总加权行程成本最小。追求整体效率与公平,最常用的目标。' },
  { k:'最大覆盖', v:'在给定截断时间内(截断 min 参数),使被覆盖的需求人口最多。只看"多快能到",适合急救站等有响应时限的设施。' },
  { k:'容量约束覆盖', v:'最大覆盖 + 每个设施有容量上限(设了设施权重字段则用各自容量,否则用统一"容量"参数),避免超员假覆盖。' },
  { k:'最少设施', v:'用尽可能少的设施数,使全部需求都在截断时间内被覆盖。目标是省投资。' },
  { k:'最大客流', v:'不按最近分配,需求者按设施吸引力(设施权重字段×时间衰减)决定去向,最大化设施总承接客流,类似商业选址逻辑。' },
  { k:'市场份额', v:'存在竞品点时,按你的候选点 vs 竞品的吸引力(竞品权重×时间衰减)计算抢到的需求份额,最大化自身市场份额。' }
]}

const setMsgTimers = {}

// ---- 新手指引(聚光灯式交互引导) ----
const TOUR_STEPS = [
  { title:'欢迎使用「网络分析·可达性实验台」',
    text:'花 30 秒过一遍界面结构。每一步会高亮目标区域,<b>点「下一步」</b>继续,随时可点右上「跳过」。' },
  { sel:'.tabs.modetabs', title:'第 1 步 · 选择分析模块',
    text:'6 种网络分析在这里切换:路径规划 / 等时圈 / 最近设施 / 可达性 / 选址 / VRP 配送。鼠标悬停有说明。' },
  { selT:'点集', title:'第 2 步 · 准备点集',
    text:'选定模块后,这里列出所需点集(如需求点/设施点)。点击卡片名,再<b>在地图上直接点击</b>采点;卡片右侧可用「示例」一键载入或「上传」导入 JSON。' },
  { selT:'参数', title:'第 3 步 · 调整参数',
    text:'出行方式(步行/自行车/小汽车)与分析参数(搜索半径、P 值、载具数等)都在这里设置。' },
  { selBtn:'开始分析', title:'第 4 步 · 开始分析',
    text:'一切就绪后点这个按钮。结果会直接叠加在地图上,并弹出指标卡。' },
  { selT:'图层控制', title:'第 5 步 · 图层控制',
    text:'参数点与结果按类分层:可用 👁 开关每一类,点行名会<b>缩放到该图层</b>;路网数据集也可在此开关。' },
  { selT:'历史分析', title:'第 6 步 · 历史分析',
    text:'每次分析自动存档于此。点击卡片即可回看当年结果,⬇ 下载整包 GeoJSON。' },
]
const tour = ref(-1)
const spotRect = ref(null)
let vw = () => window.innerWidth
let vh = () => window.innerHeight
function tourFind(){
  const s = TOUR_STEPS[tour.value]
  if (!s) return null
  if (s.sel) return document.querySelector(s.sel)
  if (s.selBtn) return [...document.querySelectorAll('button')].find(b => b.textContent.includes(s.selBtn))
  if (s.selT){
    const h = [...document.querySelectorAll('h3,.rsec-title')].find(e => e.textContent.trim().startsWith(s.selT))
    return h && h.closest('.sec,.rhalf')
  }
  return null
}
function tourPlace(){
  const s = TOUR_STEPS[tour.value]
  if (s && s.selT === '点集' && !tourFind() && !store.mode){
    const b = document.querySelector('.tabs.modetabs .tab')
    if (b){ b.click(); setTimeout(tourPlace, 260); return }
  }
  const el = tourFind()
  if (!el || tour.value < 0){ spotRect.value = null; return }
  el.scrollIntoView({ block:'center', behavior:'smooth' })
  setTimeout(() => {
    const el2 = tourFind()
    if (!el2){ spotRect.value = null; return }
    const r = el2.getBoundingClientRect()
    spotRect.value = { l:r.left - 6, t:r.top - 6, w:r.width + 12, h:r.height + 12 }
  }, 160)
}
const spotStyle = computed(() => {
  if (!spotRect.value) return { display:'none' }
  const r = spotRect.value
  return { left:r.l + 'px', top:r.t + 'px', width:r.w + 'px', height:r.h + 'px' }
})
const cardStyle = computed(() => {
  const W = 320, H = 175
  let left, top
  if (spotRect.value){
    const r = spotRect.value
    if (r.l > vw() * 0.55){
      left = r.l - W - 16
      top = Math.min(Math.max(14, r.t + r.h / 2 - H / 2), vh() - H - 14)
    } else {
      left = Math.min(Math.max(14, r.l), vw() - W - 14)
      top = (r.t + r.h + 16 + H < vh()) ? r.t + r.h + 16 : Math.max(14, r.t - H - 16)
    }
  } else {
    left = (vw() - W) / 2; top = (vh() - H) / 2
  }
  return { left:left + 'px', top:top + 'px', width:W + 'px' }
})
function tourGo(d){
  const n = tour.value + d
  if (n < 0 || n >= TOUR_STEPS.length){ tour.value = -1; return }
  tour.value = n
  nextTick(tourPlace)
}
function tourStart(){ tour.value = 0; nextTick(tourPlace) }
const onKey = e => { if (e.key === 'Escape') tour.value = -1 }
const onReflow = () => { if (tour.value >= 0) tourPlace() }
onMounted(() => { window.addEventListener('keydown', onKey); window.addEventListener('resize', onReflow) })
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); window.removeEventListener('resize', onReflow) })

function setMsg(id, txt){
  store.setMsg = { ...(store.setMsg || {}), [id]: txt }
  clearTimeout(setMsgTimers[id])
  setMsgTimers[id] = setTimeout(() => {
    const m = { ...(store.setMsg || {}) }; delete m[id]
    store.setMsg = m
  }, 4500)
}
function sliceCap(id, arr){
  const cap = CAPS[id]
  if (arr.length > cap) { setMsg(id, '该类最多 ' + cap + ' 个,已截取前 ' + cap + ' 个'); return arr.slice(0, cap) }
  return arr
}
function loadSample(id){
  if (!SAMPLES[id]) { toast('该点集无内置示例','err'); return }
  getJson('/samples/' + SAMPLES[id])
    .then(g => { store.points[id] = sliceCap(id, parseGeojson(g)); toast(SAMPLES[id] + ' 已载入 ' + store.points[id].length + ' 点') })
    .catch(e => toast('示例加载失败 ' + e.message,'err'))
}
function upload(e){
  const setId = store.pickSet
  const fl = e.target.files[0]; if (!fl || !setId) { if (!setId) toast('请先在点集中选择要上传的类别','err'); e.target.value = ''; return }
  const rd = new FileReader()
  rd.onload = () => {
    try { store.points[setId] = sliceCap(setId, parseGeojson(JSON.parse(rd.result))); toast('已载入 ' + store.points[setId].length + ' 点') }
    catch (err) { toast('解析失败:' + err.message,'err') }
  }
  rd.readAsText(fl); e.target.value = ''
}
function clearSet(id){ store.points[id] = []; const m = { ...(store.setMsg || {}) }; delete m[id]; store.setMsg = m }
</script>
