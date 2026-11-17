import * as maplibregl from 'maplibre-gl'
import cartoPositron from './assets/carto-positron.json'

// Optional key: set VITE_TDT_KEY in webapp/.env.local. Never commit provider keys.
export const TDT_KEY = import.meta.env.VITE_TDT_KEY || ''
export const VBG_IDS = []

// 模板标准:初始一次注入全部源;切换底图只改 visibility,禁止重建 style
// 底图集合:carto(默认,内置 Positron) / satellite(ArcGIS 影像) / none
// 注:天地图仅保留注记(cva/cia)作为 overlay,不再提供矢量/地形底图
export function buildStyle() {
  const sources = {
    'tianditu-satellite': { type:'raster', tileSize:256, maxzoom:18,
      tiles:['https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'] },
    'terrain-dem': { type:'raster-dem', tileSize:256, encoding:'terrarium', minzoom:11, maxzoom:14,
      tiles:['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'] }
  }
  const layers = [
    { id:'bg', type:'background', paint:{'background-color':'#eef1f7'} },
    { id:'tianditu-satellite-layer', source:'tianditu-satellite', type:'raster',
      layout:{visibility:'none'}, paint:{'raster-opacity':1} }
  ]
  // An empty key makes Tianditu reject every tile and can stall style readiness.
  if (TDT_KEY) {
    sources['tdt-label-cva'] = { type:'raster', tileSize:256,
      tiles:[`https://t6.tianditu.gov.cn/cva_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cva&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TDT_KEY}`] }
    sources['tdt-label-cia'] = { type:'raster', tileSize:256,
      tiles:[`https://t6.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TDT_KEY}`] }
    layers.push(
      { id:'carto-label-layer', source:'tdt-label-cva', type:'raster', layout:{visibility:'none'}, paint:{'raster-opacity':.75} },
      { id:'imagery-label-layer', source:'tdt-label-cia', type:'raster', layout:{visibility:'none'}, paint:{'raster-opacity':.75} }
    )
  }
  return {
    version: 8,
    glyphs: 'https://tiles.basemaps.cartocdn.com/fonts/{fontstack}/{range}.pbf',
    sources,
    layers
  }
}

// Carto Positron 内置层(离线 JSON,过滤 boundary 与非 fill/line/background)
export function injectCartoLayers(map) {
  if (map.getSource('vbg-openmaptiles')) return
  map.addSource('vbg-openmaptiles', {
    type:'vector',
    tiles:['https://tiles.basemaps.cartocdn.com/vectortiles/carto.streets/v1/{z}/{x}/{y}.mvt'],
    maxzoom: 14
  })
  const anchor = map.getLayer('tianditu-satellite-layer') ? 'tianditu-satellite-layer' : undefined
  VBG_IDS.length = 0
  cartoPositron.layers.forEach(ly => {
    if (ly.type!=='background' && ly.type!=='fill' && ly.type!=='line') return
    if (ly['source-layer'] === 'boundary') return
    const d = JSON.parse(JSON.stringify(ly))
    d.id = 'vbg-' + d.id
    d.source = 'vbg-openmaptiles'
    d.layout = d.layout || {}
    d.layout.visibility = 'none'
    d.paint = { ...(d.paint||{}) }
    if (d.type === 'fill') d.paint['fill-opacity'] = 0.7
    if (d.type === 'line') d.paint['line-opacity'] = 0.7
    try { map.addLayer(d, anchor); VBG_IDS.push(d.id) } catch(e) { console.warn('vbg skip', d.id, e) }
  })
}

const LABEL_MAP = { carto:'carto-label-layer', satellite:'imagery-label-layer', none:'carto-label-layer' }
export const BASEMAP_KEYS = ['carto', 'satellite', 'none']

export function applyBasemap(map, t) {
  const all = ['tianditu-satellite-layer', ...VBG_IDS]
  all.forEach(id => { try { if (map.getLayer(id)) map.setLayoutProperty(id,'visibility','none') } catch(e){} })
  const show = t==='carto' ? VBG_IDS : t==='satellite' ? ['tianditu-satellite-layer'] : []
  show.forEach(id => { try { if (map.getLayer(id)) map.setLayoutProperty(id,'visibility','visible') } catch(e){} })
  ;['carto-label-layer','imagery-label-layer'].forEach(id => {
    try { if (map.getLayer(id)) map.setLayoutProperty(id,'visibility','none') } catch(e){}
  })
  const label = LABEL_MAP[t] || 'carto-label-layer'
  try { if (map.getLayer(label)) map.setLayoutProperty(label,'visibility','visible') } catch(e){}
}

export function applyLabel(map, t, on) {
  const label = LABEL_MAP[t] || 'carto-label-layer'
  try { if (map.getLayer(label)) map.setLayoutProperty(label,'visibility', on?'visible':'none') } catch(e){}
}
export function applyTerrain(map, on) {
  try { map.setTerrain(on ? { source:'terrain-dem', exaggeration:1 } : null) } catch(e){}
}
export { maplibregl }
