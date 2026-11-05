import router, { dynamicRoutes } from './router'
import { ElMessage } from 'element-plus'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { getToken, removeToken } from '@/utils/auth'
import { isHttp, isPathMatch } from '@/utils/validate'
import { isRelogin } from '@/utils/request'
import useUserStore from '@/store/modules/user'
import useSettingsStore from '@/store/modules/settings'
import usePermissionStore, { filterDynamicRoutes } from '@/store/modules/permission'

NProgress.configure({ showSpinner: false })

const whiteList = ['/login', '/register']

const isWhiteList = (path) => {
  return whiteList.some(pattern => isPathMatch(pattern, path))
}

let initializedToken = null
let initialization = null
let removeRoutes = []

function resetRoutes() {
  removeRoutes.forEach(remove => remove())
  removeRoutes = []
  initializedToken = null
}

function initialize(token) {
  if (initialization?.token === token) return initialization.promise

  const pending = { token, promise: null }
  initialization = pending
  isRelogin.show = true
  pending.promise = (async () => {
    try {
      await useUserStore().getInfo()
      if (getToken() !== token) return false
      const accessRoutes = await usePermissionStore().generateRoutes()
      if (getToken() !== token) return false
      resetRoutes()
      const routes = filterDynamicRoutes(dynamicRoutes).concat(accessRoutes)
      for (const route of routes) {
        if (!isHttp(route.path)) removeRoutes.push(router.addRoute(route))
      }
      initializedToken = token
      return true
    } finally {
      if (initialization === pending) {
        initialization = null
        isRelogin.show = false
      }
    }
  })()
  return pending.promise
}

const loginRoute = to => ({ path: '/login', query: { redirect: to.fullPath } })

router.beforeEach(async to => {
  NProgress.start()
  const token = getToken()
  if (!token) {
    resetRoutes()
    if (isWhiteList(to.path)) return true
    return loginRoute(to)
  }

  if (to.meta.title) useSettingsStore().setTitle(to.meta.title)
  if (to.path === '/login') return { path: '/' }
  if (isWhiteList(to.path) || initializedToken === token) return true

  try {
    if (await initialize(token)) return { path: to.path, query: to.query, hash: to.hash, replace: true }
  } catch (error) {
    if (getToken() === token && (Number(error?.code) === 401 || error?.response?.status === 401)) {
      removeToken()
      useUserStore().$reset()
      usePermissionStore().$reset()
      resetRoutes()
      return loginRoute(to)
    }
    ElMessage.error('暂时无法加载用户信息或菜单，请稍后重试。')
  }
  NProgress.done()
  return false
})

router.afterEach(() => {
  NProgress.done()
})

