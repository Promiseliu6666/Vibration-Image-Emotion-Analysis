import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {test} from 'node:test'
import {createRouter,createMemoryHistory} from 'vue-router'

test('home and legacy home open the pinned algorithm management page',async()=>{
  const source=readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
  const declaration=source.split('export const constantRoutes =')[1].split('// 动态路由')[0]
    .replace(/\(\)\s*=>\s*import\('[^']+'\)/g,'() => Promise.resolve({render:()=>null})')
  const routes=new Function('Layout',`return (${declaration.trim()})`)({render:()=>null})
  const router=createRouter({history:createMemoryHistory(),routes})
  for(const path of ['/','/index','/algorithms']){
    await router.push(path)
    assert.equal(router.currentRoute.value.name,'AnalysisAlgorithms')
    assert.equal(router.currentRoute.value.path,'/algorithms')
    assert.equal(router.currentRoute.value.meta.affix,true)
  }
  await router.push('/analysis')
  assert.equal(router.currentRoute.value.name,'analysis')
})
