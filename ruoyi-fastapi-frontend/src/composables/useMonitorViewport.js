import {nextTick,onBeforeUnmount,onMounted,ref} from 'vue'

// Use the actual content offset, including the navigation and open page tabs.
export function useMonitorViewport(element,enabled=true){
  const height=ref('calc(100dvh - 84px)')
  let observer
  function measure(){
    if(!element.value) return
    const offset=element.value.getBoundingClientRect().top + window.scrollY
    height.value=`${Math.max(280,window.innerHeight-Math.max(0,offset)-8)}px`
  }
  onMounted(async()=>{
    if(!enabled) return
    await nextTick()
    window.scrollTo({top:0,behavior:'instant'})
    measure()
    window.addEventListener('resize',measure)
    if(typeof ResizeObserver!=='undefined'){
      observer=new ResizeObserver(measure)
      observer.observe(element.value)
    }
  })
  onBeforeUnmount(()=>{window.removeEventListener('resize',measure);observer?.disconnect()})
  return height
}
