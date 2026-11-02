import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { loadPanelConfig } from './store/panel'
import './styles/global.css'

loadPanelConfig().finally(() => {
  createApp(App).use(createPinia()).use(router).mount('#app')
})
