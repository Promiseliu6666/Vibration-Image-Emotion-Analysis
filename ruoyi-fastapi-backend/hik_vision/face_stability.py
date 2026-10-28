"""Time-based face stability for low-FPS streams, independent of identity lookup."""
import math
class FaceStabilityGate:
    def __init__(self,seconds=1.2,observations=3,loss_grace=1.5):
        self.seconds=seconds;self.observations=observations;self.loss_grace=loss_grace
        self.rect=None;self.since=None;self.last_seen=None;self.count=0;self.ready=False
    def observe(self,rect,now):
        changed=False;lost=False
        if rect is None:
            if self.last_seen is not None and now-self.last_seen>=self.loss_grace:
                lost=self.rect is not None;self.rect=None;self.since=None;self.count=0;self.ready=False
            return {'changed':False,'lost':lost,'ready':self.ready,'progress':self.progress(now)}
        x,y,w,h=rect
        if min(w,h)<24:return self.observe(None,now)
        if self.rect is not None:
            px,py,pw,ph=self.rect
            shift=math.hypot(x+w/2-px-pw/2,y+h/2-py-ph/2)/max(pw,ph,1)
            scale=max(abs(w-pw)/max(pw,1),abs(h-ph)/max(ph,1))
            changed=shift>.18 or scale>.30
        if self.rect is None or changed:
            self.since=now;self.count=1;self.ready=False
        else:self.count+=1
        self.rect=tuple(int(v) for v in rect);self.last_seen=now
        self.ready=self.count>=self.observations and now-self.since>=self.seconds
        return {'changed':changed,'lost':False,'ready':self.ready,'progress':self.progress(now)}
    def visible(self,now):return self.rect is not None and self.last_seen is not None and now-self.last_seen<.9
    def progress(self,now):
        if self.since is None:return 0.
        return min(1.,max(0.,(now-self.since)/self.seconds),self.count/self.observations)
