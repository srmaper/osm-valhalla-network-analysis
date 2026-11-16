<template>
  <div class="layout">
    <Sidebar />
    <MapPanel />
    <RightPanel />
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import MapPanel from './components/MapPanel.vue'
import RightPanel from './components/RightPanel.vue'
</script>
