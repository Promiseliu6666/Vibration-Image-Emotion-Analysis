"""Per-device short temporal windows; never attach old alerts to new frames."""
from collections import deque, OrderedDict

class TemporalAnalysis:
    def __init__(self):
        self.devices = OrderedDict()
    def update(self, device, candidate, now, present=True):
        history = self.devices.setdefault(device, deque(maxlen=24))
        self.devices.move_to_end(device)
        while len(self.devices) > 64: self.devices.popitem(last=False)
        if not present or (history and now-history[-1][0] > 6): history.clear()
        if not present: return 'absent', {'samples': 0, 'duration_s': 0, 'confirmed': False}
        if history and now <= history[-1][0]:
            return 'thinking', {'samples':0,'duration_s':0,'confirmed':False,'duplicate_or_out_of_order':True}
        history.append((now,candidate))
        while history and now-history[0][0] > 12: history.popleft()
        # Only the current run supplies evidence. A previous phone/fatigue result cannot carry over.
        run=[]
        for item in reversed(history):
            if item[1]!=candidate: break
            run.append(item)
        duration=now-run[-1][0]
        minimum=2 if candidate in ('engaged_reading','engaged_writing','engaged_screen','engaged_computer') else 3
        confirmed=len(run)>=minimum and duration>=2
        state=candidate if confirmed or candidate=='thinking' else 'thinking'
        return state, {'samples':len(run),'duration_s':round(duration,2),'confirmed':confirmed,'required_samples':minimum}

temporal = TemporalAnalysis()
