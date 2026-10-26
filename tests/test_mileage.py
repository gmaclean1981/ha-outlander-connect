"""Synthetic history tests; no account, location data or network access."""
import importlib
from pathlib import Path
import sys
import types
import unittest
from datetime import date

pkg = types.ModuleType('mileage_under_test')
pkg.__path__ = [str(Path(__file__).resolve().parent.parent/'custom_components/outlander_connect')]
sys.modules[pkg.__name__] = pkg
mileage = importlib.import_module('mileage_under_test.mileage')
data = importlib.import_module('mileage_under_test.data')
api = importlib.import_module('mileage_under_test.api')

def report(rows=None, **kwargs):
    return dict(status='Success', periodType='Monthly', startYear=2023, startMonth=2,
                distanceUnit='MI', durationUnit='MIN', data=rows if rows is not None else [
                    dict(eventPeriod='2026-10-25',distance=10,duration=62)], **kwargs)

class MileageTests(unittest.TestCase):
    def test_explicit_miles_and_minutes(self):
        row=mileage.parse_month(report(),2026,10)[date(2026,10,25)]
        self.assertEqual(row,dict(distance_km=16.09344,driving_minutes=62))

    def test_kilometres_not_converted_twice(self):
        r=report();r['distanceUnit']='KM'
        self.assertEqual(mileage.parse_month(r,2026,10)[date(2026,10,25)]['distance_km'],10)

    def test_availability_start_is_not_query_period(self):
        self.assertEqual(len(mileage.parse_month(report(),2026,10)),1)

    def test_unknown_units_and_failed_reports_rejected(self):
        for key,value in [('distanceUnit','yards'),('durationUnit','hours'),('status','Error'),('periodType','Yearly')]:
            r=report();r[key]=value
            with self.assertRaises(ValueError):mileage.parse_month(r,2026,10)

    def test_duplicate_and_wrong_month_rejected(self):
        for rows in [[dict(eventPeriod='2026-09-25',distance=1,duration=1)],report()['data']*2]:
            with self.assertRaises(ValueError):mileage.parse_month(report(rows),2026,10)

    def test_missing_day_is_unknown_and_explicit_zero_preserved(self):
        rows=[dict(eventPeriod='2026-10-24',distance=0,duration=0)]
        records=mileage.parse_month(report(rows),2026,10)
        s=mileage.apply_mileage(data.Snapshot(),{(2026,10):dict(ok=True,records=records)},date(2026,10,25))
        self.assertIsNone(s.readings['today_distance_km'].value)
        self.assertEqual(s.readings['yesterday_distance_km'].value,0)

    def test_invalid_metrics_independent_and_finite(self):
        rows=[dict(eventPeriod='2026-10-25',distance=True,duration=48)]
        r=mileage.parse_month(report(rows),2026,10)[date(2026,10,25)]
        self.assertIsNone(r['distance_km']);self.assertEqual(r['driving_minutes'],48)
        for v in [-1,float('nan'),float('inf')]:
            r=mileage.parse_month(report([dict(eventPeriod='2026-10-25',distance=v,duration=v)]),2026,10)[date(2026,10,25)]
            self.assertIsNone(r['distance_km']);self.assertIsNone(r['driving_minutes'])

    def test_midnight_and_year_boundary_select_previous_month(self):
        reports={(2026,12):dict(ok=True,records={date(2026,12,31):dict(distance_km=8,driving_minutes=10)})}
        s=mileage.apply_mileage(data.Snapshot(),reports,date(2027,1,1))
        self.assertIsNone(s.readings['today_distance_km'].value)
        self.assertEqual(s.readings['yesterday_distance_km'].value,8)

    def test_failed_report_hides_cached_values(self):
        reports={(2026,10):dict(ok=False,records=mileage.parse_month(report(),2026,10))}
        s=mileage.apply_mileage(data.Snapshot(),reports,date(2026,10,25))
        self.assertIsNone(s.readings['today_distance_km'].value)

    def test_mileage_allowlist_rejects_extra_fields_methods_ports(self):
        url='https://us-m.aerpf.com:15443/api/v1/services/metrics/mileage/JA4J24A50PZ123456?year=2026&month=10&timezone=America%2FHalifax'
        self.assertTrue(api.allowed_request('GET',url))
        for method,u in [('POST',url),('GET',url+'&command=unlock'),('GET',url+'&month=11'),('GET',url.replace('month=10','month=13')),('GET',url.replace(':15443',':443')),('GET',url.replace('America%2FHalifax','invalid'))]:
            self.assertFalse(api.allowed_request(method,u))

    def test_yearly_totals_and_monthly_units(self):
        p=report([dict(eventPeriod='2026-01',distance=10,duration=62)])
        p.update(periodType='Yearly',totalDistance=10,totalDuration=62)
        self.assertEqual(mileage.totals(p),dict(distance_km=16.09344,driving_minutes=62))
        self.assertEqual(mileage.parse_year(p,2026)[date(2026,1,1)]['distance_km'],16.09344)

    def test_yearly_wrong_period_and_duplicates_rejected(self):
        for rows in [[dict(eventPeriod='2025-12',distance=1,duration=1)],[dict(eventPeriod='2026-02',distance=1,duration=1)]*2]:
            p=report(rows);p['periodType']='Yearly'
            with self.assertRaises(ValueError):mileage.parse_year(p,2026)

    def test_yearly_query_requires_safe_parameters(self):
        self.assertTrue(api.valid_mileage_query('year=2026&timezone=America%2FHalifax'))
        for q in ['year=2026&timezone=America%2FHalifax&extra=1','year=2026&timezone=invalid','year=2026&year=2025&timezone=UTC']:
            self.assertFalse(api.valid_mileage_query(q))

    def test_month_and_year_readings_are_independent(self):
        reports={(2026,10):dict(ok=True,totals=dict(distance_km=100,driving_minutes=62))}
        s=mileage.apply_mileage(data.Snapshot(),reports,date(2026,10,25),dict(ok=False,totals=dict(distance_km=500)))
        self.assertEqual(s.readings['month_distance_km'].value,100)
        self.assertEqual(s.readings['month_driving_minutes'].value,62)
        self.assertIsNone(s.readings['year_distance_km'].value)

if __name__=='__main__':unittest.main()
