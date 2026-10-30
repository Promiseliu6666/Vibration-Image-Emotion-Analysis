"""Bounded fair queue: at most one waiting frame per device, newest wins."""
import asyncio
import os
class LatestFrames(asyncio.Queue):
    def put_nowait(self, item):
        for old in list(self._queue):
            if old['device_id']==item['device_id']:
                self._queue.remove(old)
                self.task_done()
                try: os.remove(old['filepath'])
                except OSError: pass
        super().put_nowait(item)
