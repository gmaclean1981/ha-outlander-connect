"""Exercise optional history polling without Home Assistant or network I/O."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime,timezone
from zoneinfo import ZoneInfo

class FakeCoordinator:
    def __init__(self,hass,*args,**kwargs):self.hass=hass
    async def async_request_refresh(self):self.data=await self._async_update_data()

class AuthFailed(Exception):pass
class UpdateFailed(Exception):pass

names=['homeassistant','homeassistant.exceptions','homeassistant.helpers','homeassistant.helpers.update_coordinator','homeassistant.util','homeassistant.util.dt']
stubs={n:types.ModuleType(n) for n in names}
stubs['homeassistant.exceptions'].ConfigEntryAuthFailed=AuthFailed
stubs['homeassistant.helpers.update_coordinator'].DataUpdateCoordinator=FakeCoordinator
stubs['homeassistant.helpers.update_coordinator'].UpdateFailed=UpdateFailed
stubs['homeassistant.util'].dt=stubs['homeassistant.util.dt']
stubs['homeassistant.util.dt'].as_local=lambda d:d.astimezone(ZoneInfo('America/Halifax'))
pkg=types.ModuleType('coordinator_under_test');pkg.__path__=[str(Path(__file__).resolve().parent.parent/'custom_components/outlander_connect')]
sys.modules[pkg.__name__]=pkg
with patch.dict(sys.modules,stubs):
    module=importlib.import_module('coordinator_under_test.coordinator')

class Clock:
    @staticmethod
    def now(tz):return datetime(2027,1,1,2,0,tzinfo=timezone.utc) # Dec 31 in Halifax

class Client:
    def __init__(self,error=None):self.calls=[];self.error=error
    async def async_state(self,vin):return {'state':{}}
    async def async_health(self,vin):return {'vhr':[]}
    async def async_mileage(self,vin,year,month,tz):
        self.calls.append((year,month,tz))
        if self.error:raise self.error
        return dict(status='Success',periodType='Monthly',distanceUnit='KM',durationUnit='MIN',data=[dict(eventPeriod=f'{year}-{month:02}-30',distance=5,duration=12)])
    async def async_yearly_mileage(self,vin,year,tz):
        if self.error:raise self.error
        return dict(status='Success',periodType='Yearly',distanceUnit='KM',durationUnit='MIN',totalDistance=100,totalDuration=60,data=[dict(eventPeriod=f'{year}-12',distance=100,duration=60)])

class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def make(self,error=None):
        client=Client(error)
        c=module.OutlanderCoordinator(SimpleNamespace(config=SimpleNamespace(time_zone='America/Halifax')),SimpleNamespace(data={'vin':'JA4J24A50PZ123456'},options={}),client)
        return c,client

    async def test_uses_local_calendar_and_reuses_month_cache(self):
        c,client=self.make()
        with patch.object(module,'datetime',Clock):
            await c._async_update_data();await c._async_update_data()
        self.assertEqual(client.calls,[(2026,12,'America/Halifax')])
        self.assertEqual(c.mileage_today.isoformat(),'2026-12-31')

    async def test_history_failure_preserves_state_and_does_not_hammer(self):
        c,client=self.make(module.CloudError('failed'))
        with patch.object(module,'datetime',Clock):
            s=await c._async_update_data();await c._async_update_data()
        self.assertIsNotNone(s.polled_at);self.assertIsNone(s.readings['today_distance_km'].value)
        self.assertEqual(len(client.calls),1)

    async def test_history_authentication_failure_requests_reauth(self):
        c,client=self.make(module.AuthenticationError('expired'))
        with patch.object(module,'datetime',Clock):
            with self.assertRaises(AuthFailed):await c._async_update_data()

    async def test_refresh_button_fetches_history_again(self):
        c,client=self.make()
        with patch.object(module,'datetime',Clock):
            await c._async_update_data();await c.async_refresh_all()
        self.assertEqual(len(client.calls),2)

if __name__=='__main__':unittest.main()
