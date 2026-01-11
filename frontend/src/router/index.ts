import { createRouter, createWebHistory } from 'vue-router'
import Upload from '../views/Upload.vue'
import TaskList from '../views/TaskList.vue'
import Settings from '../views/Settings.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/upload'
    },
    {
      path: '/upload',
      name: 'upload',
      component: Upload
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: TaskList
    },
    {
      path: '/settings',
      name: 'settings',
      component: Settings
    }
  ]
})

export default router
