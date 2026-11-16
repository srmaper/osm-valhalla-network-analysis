<template>
  <aside class="rside">
    <div class="rhalf top">
      <div class="rsec-title">图层控制</div>
      <div class="rscroll"><LayersPopover /></div>
    </div>
    <div class="rhalf bottom">
      <div class="rsec-title">历史分析</div>
      <div class="rscroll"><ResultsDrawer /></div>
    </div>
  </aside>
</template>

<script setup>
import { store } from '../store'
import LayersPopover from './LayersPopover.vue'
import ResultsDrawer from './ResultsDrawer.vue'
</script>

<style scoped>
</style>
