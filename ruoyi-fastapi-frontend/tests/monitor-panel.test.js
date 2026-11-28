import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { parse,compileScript } from '@vue/compiler-sfc'
import { createRenderer,h,nextTick,onMounted,onBeforeUnmount,ref } from 'vue'

test('tabs and the top-level metric selector preserve both running algorithms and display one result',async()=>{
  const source=readFileSync(new URL('../src/components/MonitorPanel/index.vue',import.meta.url),'utf8')
  const {descriptor}=parse(source)
  const code=compileScript(descriptor,{id:'panel-test',inlineTemplate:true}).content.replace(/from ['"]vue['"]/g,`from '${import.meta.resolve('vue')}'`)
  const {default:Panel}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
  const active=new Set()
  const stub=name=>({setup(){onMounted(()=>active.add(name));onBeforeUnmount(()=>active.delete(name));return()=>h('span',name)}})
  const Psych=stub('vibration'),Fatigue=stub('fatigue')
  const algorithms=ref(['vibration','fatigue'])
  const activeMetric=ref('vibration'),hideTabs=ref(false)
  const nodes=[]
  const node=(type,text='')=>{const n={type,text,children:[],props:{},parent:null,style:{}};nodes.push(n);return n}
  const renderer=createRenderer({createElement:node,createText:t=>node('text',t),createComment:t=>node('comment',t),
    setText:(n,t)=>n.text=t,setElementText:(n,t)=>n.text=t,patchProp:(n,k,o,v)=>n.props[k]=v,
    parentNode:n=>n.parent,nextSibling:()=>null,insert(n,p){n.parent=p;p.children.push(n)},remove(n){if(n.parent)n.parent.children=n.parent.children.filter(x=>x!==n)}})
  const app=renderer.createApp({setup:()=>()=>h(Panel,{algorithmIds:algorithms.value,activeMetric:activeMetric.value,hideTabs:hideTabs.value,'onUpdate:activeMetric':id=>{activeMetric.value=id}},{psychological:()=>h(Psych),fatigue:()=>h(Fatigue)})})
  const root=node('root')
  app.mount(root)
  const rendered=n=>[n,...n.children.flatMap(rendered)]
  const panels=()=>rendered(root).filter(n=>n.props.role==='tabpanel')
  try {
    await nextTick()
    assert.deepEqual([...active].sort(),['fatigue','vibration'])
    const tabs=nodes.filter(n=>n.props.role==='tab')
    assert.equal(tabs.length,2)
    assert.equal(tabs[0].props['aria-selected'],true)
    tabs[1].props.onClick()
    await nextTick()
    assert.equal(tabs[1].props['aria-selected'],true)
    assert.equal(tabs[0].props['aria-selected'],false)
    assert.deepEqual([...active].sort(),['fatigue','vibration'])
    hideTabs.value=true
    await nextTick()
    assert.equal(rendered(root).filter(n=>n.props.role==='tab').length,0)
    activeMetric.value='vibration'
    await nextTick()
    assert.notEqual(panels().find(n=>n.props['aria-label']==='心理状态').style.display,'none')
    assert.equal(panels().find(n=>n.props['aria-label']==='疲劳状态').style.display,'none')
    activeMetric.value='fatigue'
    await nextTick()
    assert.equal(panels().find(n=>n.props['aria-label']==='心理状态').style.display,'none')
    assert.notEqual(panels().find(n=>n.props['aria-label']==='疲劳状态').style.display,'none')
    assert.deepEqual([...active].sort(),['fatigue','vibration'])
    algorithms.value=['vibration']
    await nextTick()
    assert.deepEqual([...active],['vibration'])
    assert.notEqual(panels()[0].style.display,'none')
  } finally {app.unmount()}
})
