<template>
  <div class="mask" @click.self="close">
    <div class="modal">
      <div class="mhead">
        <b>分析设置</b>
        <span class="x" @click="close">✕</span>
      </div>
      <div class="mbody">
        <div class="frow">
          <label>网络分析服务地址</label>
          <input type="text" v-model="f.serviceUrl" placeholder="留空 = 同源" />
        </div>

        <div class="fsec">出行方式默认参数</div>
        <div class="frow">
          <label>步行速度 (km/h)</label>
          <input type="number" v-model.number="f.walkSpeed" min="0.5" max="10" step="0.1" style="width:90px" />
        </div>
        <div class="frow">
          <label>自行车类型</label>
          <select v-model="f.bikeType">
            <option value="road">公路车 ≈25 km/h</option>
            <option value="hybrid">城市车 ≈18 km/h</option>
            <option value="cross">越野车 ≈20 km/h</option>
            <option value="mountain">山地车 ≈16 km/h</option>
          </select>
        </div>
      </div>
      <div class="mfoot">
        <button class="btn ghost" @click="close">取消</button>
        <button class="btn" @click="save">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { store, saveSettings, toast } from '../store'

const f = reactive({ ...store.settings })
function close(){ store.showSettings = false }
function save(){
  store.settings = { ...f }
  saveSettings()
  toast('设置已保存')
  close()
}
</script>

<style scoped>
.mask{position:fixed;inset:0;background:rgba(40,50,80,.35);backdrop-filter:blur(3px);z-index:50;
  display:flex;align-items:center;justify-content:center}
.modal{width:min(480px,92vw);background:#fff;border-radius:16px;box-shadow:0 18px 60px rgba(60,80,140,.25);overflow:hidden}
.mhead{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;
  border-bottom:1px solid var(--line);font-size:15px;color:var(--tx)}
.x{cursor:pointer;color:var(--tx2);font-size:15px;padding:2px 6px}
.x:hover{color:var(--tx)}
.mbody{padding:14px 18px}
.frow{display:flex;align-items:center;gap:9px;margin-bottom:10px;flex-wrap:wrap}
.frow label{width:110px;flex:none;color:var(--tx2);font-size:12px}
.frow input[type=text]{flex:1;min-width:200px}
.fsec{font-size:12px;color:var(--ac2);font-weight:600;margin:12px 0 8px;padding-top:10px;border-top:1px dashed var(--line)}
.fhint{font-size:11px;color:var(--tx2);line-height:1.6;margin-bottom:6px}
.fhint2{font-size:11px;color:var(--tx2)}
.mfoot{display:flex;justify-content:flex-end;gap:8px;padding:12px 18px;border-top:1px solid var(--line)}
</style>
