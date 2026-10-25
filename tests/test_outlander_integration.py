"""Offline behavior tests. No credentials, network requests, or vehicle commands."""
import asyncio
import copy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

root=Path(__file__).resolve().parent.parent
folder=root/'custom_components/outlander_connect'
pkg=types.ModuleType('outlander_under_test');pkg.__path__=[str(folder)];sys.modules[pkg.__name__]=pkg
data=importlib.import_module('outlander_under_test.data')
api=importlib.import_module('outlander_under_test.api')

VIN='JA4J24A50PZ123456'
NOW=datetime(2026,10,25,20,0,tzinfo=timezone.utc)

def fixture():
 return ({'state':{'timezone':'UTC','chargingControl':{'hvBatteryLife':'6','cruisingRangeCombined':'388','cruisingRangeFirst':[{'range':'820'},{'engineType':'4'}],'cruisingRangeSecond':[{'range':'2'},{'engineType':'5'}],'hvChargingStatus':'2','hvChargingPlugStatus':'2','hvTimeToFullCharge':'0','eventTimestamp':'2026-10-25T19:47:59Z'},'odo':[{'2026-10-25 19:46:47':'12345'},{'2026-10-24 19:56:34':'12308'}],'ignitionState':'0','ignitionStateTs':'1792957607518','accessible':True,'extLocMap':{'lat':44.5,'lon':-63.5,'ts':'1792957607'},'theftAlarm':'ON'}},
 {'vhr':[{'ts':1792957601,'dt':{'diagnostic':{'eventTimestamp':{'value':'1792957598'},'batteryLife':{'value':'5'},'odo':{'value':'12345','displayMessage':'odo_km'},'odos':{'displayMessage':'odos_km'},'availRange':{'value':'387'},'breakWarn':{'warning':False},'engineOilWarn':{'warning':False},'tireStatus':{'warning':False},'timeToFullCharge':{'value':'90'}},'vehicleStatus':{'doorStatus':{'doors':[{'position':{'displayMessage':'doorFrontLeft'},'state':{'displayMessage':'#msg_close_close','value':'0'}}]},'lightStatus':{'lights':[{'position':{'displayMessage':'lightHead'},'state':{'displayMessage':'#msg_off_off','value':'3'}}]}}}}]})


class MappingTests(unittest.TestCase):
 def test_validated_values_and_independent_freshness(self):
  s,h=fixture();x=data.parse_snapshot(s,h,polled_at=NOW)
  self.assertEqual(x.readings['battery'].value,6)
  self.assertEqual(x.readings['combined_range'].value,388)
  self.assertEqual(x.readings['ev_range'].value,2)
  self.assertEqual(x.readings['odometer'].value,12345)
  self.assertEqual(x.readings['odometer'].updated_at.isoformat(),'2026-10-25T19:46:47+00:00')
  self.assertTrue(x.readings['charging'].value)
  self.assertFalse(x.readings['front_left_door'].value)
  self.assertEqual(x.gps,(44.5,-63.5))
  self.assertNotEqual(x.readings['health_updated'].value,x.readings['charging_updated'].value)
  self.assertEqual(x.readings['gasoline_range_raw'].value,820)
  self.assertIsNone(x.readings['gasoline_range_raw'].unit)
  self.assertIsNone(x.readings['time_to_full_raw'].unit)

 def test_newer_health_wins_for_shared_measurements(self):
  s,h=fixture();h['vhr'][0]['dt']['diagnostic']['eventTimestamp']['value']='1792959000'
  x=data.parse_snapshot(s,h);self.assertEqual(x.readings['battery'].value,5);self.assertEqual(x.readings['battery'].source,'health')
  self.assertEqual(x.readings['odometer_updated'].source,'health')
  self.assertEqual(x.readings['odometer_updated'].updated_at,x.readings['odometer'].updated_at)

 def test_unknown_codes_and_warning_flags_do_not_become_false(self):
  s,h=fixture();s['state']['chargingControl']['hvChargingStatus']='99';h['vhr'][0]['dt']['diagnostic']['breakWarn']['warning']='false'
  x=data.parse_snapshot(s,h);self.assertIsNone(x.readings['charging'].value);self.assertIsNone(x.readings['breakWarn'].value)
  self.assertEqual(x.readings['theft_alarm_raw'].value,'ON');self.assertNotIn('alarm_triggered',x.readings)

 def test_invalid_gps_and_numeric_values(self):
  s,h=fixture();s['state']['extLocMap']={'lat':0,'lon':0};s['state']['chargingControl']['hvBatteryLife']='nan';h['vhr'][0]['dt']['diagnostic']['batteryLife']['value']='101'
  x=data.parse_snapshot(s,h);self.assertIsNone(x.gps);self.assertIsNone(x.readings['battery'].value)
  self.assertIsNone(data.number(True));self.assertIsNone(data.timestamp('2026-10-25 19:00:00'))

 def test_missing_optional_containers(self):
  s={'state':{'chargingControl':None,'odo':None,'extLocMap':None}}
  h={'vhr':[{'dt':{'diagnostic':{'cruisingRangeSecond':{'cruisingRange':None}},'vehicleStatus':None}}]}
  self.assertIsNone(data.parse_snapshot(s,h).gps)

 def test_gasoline_range_is_never_substituted_for_ev(self):
  s,h=fixture();s['state']['chargingControl']['cruisingRangeSecond'][1]['engineType']='4'
  x=data.parse_snapshot(s,h);self.assertNotIn('ev_range',x.readings)

 def test_health_failure_does_not_discard_state(self):
  s,h=fixture();x=data.parse_snapshot(s,h,health_ok=False)
  self.assertFalse(x.health_ok);self.assertEqual(x.readings['battery'].source,'state')


class Response:
 def __init__(self,status=200,payload=None,headers=None):self.status=status;self.payload=payload or {};self.headers=headers or {}
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def json(self,**kwargs):return self.payload

class Session:
 def __init__(self,responses):self.responses=list(responses);self.calls=[]
 def request(self,method,url,**kwargs):
  self.calls.append((method,url,kwargs))
  if not self.responses:raise AssertionError('Unexpected network request')
  return self.responses.pop(0)

def token(**kwargs):
 return {'access_token':'test-access','refresh_token':'test-refresh','expires_in':900,'accountDN':'test-account',**kwargs}


class ClientTests(unittest.IsolatedAsyncioTestCase):
 def test_endpoint_allowlist(self):
  base='https://us-m.aerpf.com'
  self.assertTrue(api.allowed_request('POST',base+'/auth/v1/token'))
  self.assertTrue(api.allowed_request('GET',base+f'/avi/v1/vehicles/{VIN}/vehiclestate'))
  self.assertTrue(api.allowed_request('GET',base+f':15443/avi/v1/vehicles/{VIN}/vehicleStatus?count=1'))
  for method,url in [('POST',base+':15443/avi/v3/remoteOperation'),('GET','https://evil.invalid/auth/v1/token'),('POST',base+'/auth/v1/token?x=1'),('GET',base+f':15443/avi/v1/vehicles/{VIN}/vehiclestate'),('GET','http://us-m.aerpf.com/auth/v1/token')]:self.assertFalse(api.allowed_request(method,url))

 async def test_login_reused_between_polls(self):
  s,h=fixture();session=Session([Response(payload=token()),Response(payload=s),Response(payload=s)])
  c=api.CloudClient(session,'test@example.invalid','private-password');await c.async_state(VIN);await c.async_state(VIN)
  self.assertEqual([m for m,u,k in session.calls],['POST','GET','GET'])
  self.assertTrue(all(k['allow_redirects'] is False for m,u,k in session.calls))

 async def test_expired_token_refreshes(self):
  s,h=fixture();session=Session([Response(payload=token()),Response(payload=s)])
  c=api.CloudClient(session,'test','secret');c._token=token();c._expires_at=0
  await c.async_state(VIN);self.assertEqual(session.calls[0][2]['json']['grant_type'],'refresh_token')

 async def test_rejected_refresh_falls_back_once(self):
  s,h=fixture();session=Session([Response(401),Response(payload=token()),Response(payload=s)])
  c=api.CloudClient(session,'test','secret');c._token=token();c._expires_at=0
  await c.async_state(VIN);self.assertEqual([k.get('json',{}).get('grant_type') if isinstance(k.get('json'),dict) else None for m,u,k in session.calls],['refresh_token','password',None])

 async def test_repeated_401_stops(self):
  session=Session([Response(payload=token()),Response(401),Response(payload=token()),Response(401)])
  c=api.CloudClient(session,'test','secret')
  with self.assertRaises(api.AuthenticationError):await c.async_state(VIN)
  self.assertEqual(len(session.calls),4)

 async def test_rate_limit_blocks_following_requests(self):
  session=Session([Response(payload=token()),Response(429,headers={'Retry-After':'120'})]);c=api.CloudClient(session,'test','secret')
  with self.assertRaises(api.RateLimitError):await c.async_state(VIN)
  with self.assertRaises(api.RateLimitError):await c.async_state(VIN)
  self.assertEqual(len(session.calls),2)

 async def test_remote_operation_never_reaches_transport(self):
  session=Session([]);c=api.CloudClient(session,'test','secret')
  with self.assertRaises(api.CloudError):await c._send('POST','https://us-m.aerpf.com:15443/avi/v3/remoteOperation',{}, {'operation':'doorUnlock'})
  self.assertFalse(session.calls)

 async def test_errors_exclude_payloads(self):
  session=Session([Response(500,{'password':'private-password','access_token':'private-token'})]);c=api.CloudClient(session,'test','secret')
  with self.assertRaises(api.CloudError) as result:await c._send('POST','https://us-m.aerpf.com/auth/v1/token',{}, {'grant_type':'password'})
  self.assertEqual(str(result.exception),'Cloud returned HTTP 500')

 async def test_missing_state_is_a_schema_failure(self):
  session=Session([Response(payload=token()),Response(payload={'unexpected':True})]);c=api.CloudClient(session,'test','secret')
  with self.assertRaises(api.CloudError):await c.async_state(VIN)


if __name__=='__main__':unittest.main(verbosity=2)
