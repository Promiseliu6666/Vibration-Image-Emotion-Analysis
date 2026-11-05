"""Run with the backend environment, or a stdlib Python for service-only tests."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace, ModuleType
from unittest.mock import patch
import importlib.util
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT/'ruoyi-fastapi-backend'
# The same tests also work in the review/deployment staging directory.
if not (BACKEND/'module_interaction').exists():
    BACKEND = PROJECT_ROOT
sys.path.insert(0,str(BACKEND))
from module_interaction.rest_service import RestService, RestError

class Clock:
    def __init__(self):self.now=datetime(2026,11,3,3,tzinfo=timezone.utc).timestamp()
    def __call__(self):return self.now
    def advance(self,seconds):self.now+=seconds

class RestServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'rest.sqlite3'
        self.clock=Clock()
        self.service=RestService(self.path,self.clock)
    def assertRestError(self,status,function,*args):
        with self.assertRaises(RestError) as context:function(*args)
        self.assertEqual(context.exception.status_code,status)
    def test_no_early_completion_then_gesture_confirmation_is_idempotent(self):
        session=self.service.create_session(1,'breathing')
        self.assertRestError(409,self.service.act,1,session['id'],'finish','gesture')
        self.clock.advance(59.9)
        self.assertRestError(409,self.service.act,1,session['id'],'finish')
        self.clock.advance(.1)
        self.assertEqual(self.service.get_state(1)['active']['phase'],'awaiting_confirmation')
        completed=self.service.act(1,session['id'],'finish','gesture')
        self.assertEqual(completed['phase'],'completed')
        self.assertEqual(completed['completed_by'],'gesture')
        self.clock.advance(20)
        repeated=self.service.act(1,session['id'],'finish','button')
        self.assertEqual(completed,repeated)
        state=self.service.get_state(1)
        self.assertIsNone(state['active'])
        self.assertEqual(len(state['records']),1)
        self.assertEqual(state['today_completed'],1)
    def test_pause_does_not_count_time_and_resume_uses_server_time(self):
        session=self.service.create_session(1,'stretch')
        self.clock.advance(20)
        self.assertEqual(self.service.act(1,session['id'],'pause')['elapsed_seconds'],20)
        self.clock.advance(100)
        self.assertEqual(self.service.get_state(1)['active']['elapsed_seconds'],20)
        self.service.act(1,session['id'],'resume')
        self.clock.advance(69)
        self.assertRestError(409,self.service.act,1,session['id'],'finish')
        self.clock.advance(1)
        self.assertEqual(self.service.act(1,session['id'],'finish')['elapsed_seconds'],90)
    def test_each_user_has_separate_active_and_history_and_cannot_touch_others(self):
        first=self.service.create_session(1,'eyes','xiaozhi:watcher-one','小智一号')
        second=self.service.create_session(2,'breathing','xiaozhi:watcher-two','小智二号')
        self.assertRestError(404,self.service.act,2,first['id'],'cancel')
        self.clock.advance(60)
        self.service.act(1,first['id'],'finish')
        self.assertEqual(self.service.get_state(2)['records'],[])
        self.assertEqual(self.service.get_state(2)['active']['id'],second['id'])
        self.assertEqual(self.service.get_state(1)['records'][0]['device_label'],'小智一号')
    def test_repeated_start_and_parallel_requests_create_one_active(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            sessions=list(pool.map(lambda _:self.service.create_session(1,'breathing'),range(12)))
        self.assertEqual(len({s['id'] for s in sessions}),1)
        self.assertRestError(409,self.service.create_session,1,'stretch')
        self.assertRestError(409,self.service.create_session,1,'breathing','rtsp')
    def test_cancel_is_not_a_completed_record_and_allows_new_session(self):
        session=self.service.create_session(1,'breathing')
        self.clock.advance(20)
        cancelled=self.service.act(1,session['id'],'cancel')
        self.assertEqual(cancelled['elapsed_seconds'],20)
        self.assertEqual(self.service.act(1,session['id'],'cancel'),cancelled)
        self.assertRestError(409,self.service.act,1,session['id'],'finish')
        state=self.service.get_state(1)
        self.assertEqual(state,{'active':None,'records':[],'today_completed':0})
        self.assertNotEqual(self.service.create_session(1,'eyes')['id'],session['id'])
    def test_restart_keeps_active_session_and_records(self):
        session=self.service.create_session(1,'breathing')
        self.clock.advance(17)
        self.service=RestService(self.path,self.clock)
        self.assertEqual(self.service.get_state(1)['active']['elapsed_seconds'],17)
        self.clock.advance(43)
        self.service.act(1,session['id'],'finish')
        self.service=RestService(self.path,self.clock)
        self.assertEqual(self.service.get_state(1)['records'][0]['id'],session['id'])
    def test_history_is_bounded_but_today_count_is_not(self):
        for _ in range(23):
            session=self.service.create_session(1,'breathing')
            self.clock.advance(60)
            self.service.act(1,session['id'],'finish')
        state=self.service.get_state(1)
        self.assertEqual(len(state['records']),20)
        self.assertEqual(state['today_completed'],23)
        self.clock.advance(86400)
        self.assertEqual(self.service.get_state(1)['today_completed'],0)
    def test_project_source_action_and_owner_are_validated(self):
        self.assertRestError(400,self.service.create_session,1,'unknown')
        for source in ['xiaozhi','xiaozhi:','xiaozhi:../camera','http://host','local;other', 'xiaozhi:'+'a'*65]:
            self.assertRestError(400,self.service.create_session,1,'breathing',source)
        self.assertRestError(400,self.service.create_session,1,'breathing','local','x'*81)
        self.assertRestError(401,self.service.get_state,None)
        self.assertRestError(401,self.service.get_state,False)
        self.assertRestError(400,self.service.act,1,'missing','finish','other')
        self.assertRestError(404,self.service.act,1,'missing','finish')
        self.assertEqual(self.service.get_state(1)['records'],[])
    def test_catalog_cannot_be_changed_by_caller(self):
        catalog=self.service.catalog();catalog[0]['duration_seconds']=1
        self.assertEqual(self.service.catalog()[0]['duration_seconds'],60)
    def test_backward_clock_does_not_produce_negative_elapsed(self):
        session=self.service.create_session(1,'breathing')
        self.clock.advance(-100)
        self.assertEqual(self.service.get_state(1)['active']['elapsed_seconds'],0)
        self.assertRestError(409,self.service.act,1,session['id'],'finish')

# The production login dependency remains real. Test it through a small fake only
# to avoid connecting to the application's Redis/MySQL or reading their config.
try:
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.testclient import TestClient
    API_AVAILABLE=True
except ImportError:
    API_AVAILABLE=False

@unittest.skipUnless(API_AVAILABLE,'FastAPI/httpx require the backend Python environment')
class RestAPITests(unittest.TestCase):
    def setUp(self):
        RestServiceTests.setUp(self)
        fake=ModuleType('module_admin.service.login_service')
        async def logged_in(request: Request):
            token=request.headers.get('authorization')
            if token not in ('Bearer one','Bearer two'):raise HTTPException(401,'not logged in')
            return SimpleNamespace(user=SimpleNamespace(user_id=1 if token=='Bearer one' else 2))
        fake.LoginService=SimpleNamespace(get_current_user=logged_in)
        with patch.dict(sys.modules,{'module_admin.service.login_service':fake}):
            sys.modules.pop('module_interaction.rest_controller',None)
            import module_interaction.rest_controller as controller
        self.controller=controller
        self.app=FastAPI();self.app.include_router(controller.rest_controller)
        self.app.dependency_overrides[controller.get_rest_service]=lambda:self.service
        self.client=TestClient(self.app)
        self.addCleanup(self.client.close)
    def request(self,method,path,**kwargs):
        return self.client.request(method,'/interaction/rest'+path,headers={'Authorization':'Bearer one'},**kwargs)
    def test_authentication_required_even_for_frame_and_catalog(self):
        for path in ['/catalog','/state','/frame?source=local']:
            self.assertEqual(self.client.get('/interaction/rest'+path).status_code,401)
    def test_api_completion_and_cross_user_access(self):
        created=self.request('POST','/sessions',json={'project_id':'breathing'}).json()['data']
        # The API wraps mutation results in data.session.
        created=created.get('session',created)
        forbidden=self.client.post('/interaction/rest/sessions/'+created['id']+'/action',headers={'Authorization':'Bearer two'},json={'action':'cancel'})
        self.assertEqual(forbidden.status_code,404)
        self.assertEqual(self.request('POST','/sessions/'+created['id']+'/action',json={'action':'finish'}).status_code,409)
        self.clock.advance(60)
        self.assertEqual(self.request('POST','/sessions/'+created['id']+'/action',json={'action':'finish','method':'gesture'}).status_code,200)
        state=self.request('GET','/state').json()['data']
        self.assertEqual(state['today_completed'],1)
        self.assertEqual(len(state['records']),1)
    def test_api_body_and_source_validation(self):
        self.assertEqual(self.request('POST','/sessions',json={'project_id':'breathing','duration_seconds':1}).status_code,422)
        self.assertEqual(self.request('POST','/sessions',json={'project_id':'breathing','source':'xiaozhi'}).status_code,400)
        self.assertEqual(self.request('GET','/frame?source=unknown').status_code,400)
    def test_frame_metadata_and_same_authenticated_endpoint(self):
        from fastapi.responses import Response
        async def frame(source):
            self.assertEqual(source,'xiaozhi:watcher-one')
            return Response(b'jpeg',media_type='image/jpeg',headers={'X-Frame-Sequence':'12','X-Frame-Captured-At':'1793674800','Cache-Control':'no-store'})
        with patch.object(self.controller,'read_camera_frame',frame):
            response=self.request('GET','/frame?source=xiaozhi:watcher-one')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'jpeg')
        self.assertEqual(response.headers['X-Frame-Sequence'],'12')
        self.assertEqual(response.headers['X-Frame-Captured-At'],'1793674800')

if __name__=='__main__':unittest.main()
