import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {test} from 'node:test'
import {createRouter,createMemoryHistory} from 'vue-router'

test('home and camera aliases open the single pinned real-time monitor',async()=>{
  const source=readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
  const declaration=source.split('export const constantRoutes =')[1].split('// 动态路由')[0]
    .replace(/\(\)\s*=>\s*import\('[^']+'\)/g,'() => Promise.resolve({render:()=>null})')
  const routes=new Function('Layout',`return (${declaration.trim()})`)({render:()=>null})
  const router=createRouter({history:createMemoryHistory(),routes})
  for(const path of ['/','/index','/camera/live','/camera/overview','/monitor/druid']){
    await router.push(path)
    assert.equal(router.currentRoute.value.name,'ConfiguredVideoMonitor')
    assert.equal(router.currentRoute.value.path,'/monitor/druid')
    assert.equal(router.currentRoute.value.meta.affix,true)
  }
  await router.push('/algorithms')
  assert.equal(router.currentRoute.value.name,'AnalysisAlgorithms')
  assert.notEqual(router.currentRoute.value.meta.affix,true)
  await router.push('/analysis')
  assert.equal(router.currentRoute.value.name,'analysis')
})
