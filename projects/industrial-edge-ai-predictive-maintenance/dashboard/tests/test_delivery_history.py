"""Read-only bounded delivery history across ties, arrivals and supported roles."""
import base64
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from edge_delivery import Spool,history_cursor
from test_delivery import envelope
import test_acquisition_registry as fixtures


class SpoolHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-delivery-history-');self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'spool.sqlite3';self.spool=Spool(self.path)
        self.keys=[]
        for sequence in range(28):
            data=envelope();data['observation']['sequence']=sequence
            self.keys.append(self.spool.enqueue(data)['event_key'])
        with self.spool.db() as db:db.execute('UPDATE delivery_spool SET created_at=1700000000')

    def test_tied_positions_and_newer_arrivals_do_not_repeat_or_skip_old_entries(self):
        first=self.spool.status(limit=7);self.assertEqual([r['event_key'] for r in first['records']],sorted(self.keys)[:7])
        cursor=first['page']['next_before'];seen=[r['event_key'] for r in first['records']]
        new=envelope();new['observation']['sequence']=100
        newer=self.spool.enqueue(new)['event_key']
        while cursor:
            page=self.spool.status(before=cursor,limit=7)
            self.assertEqual(page['page']['before'],cursor)
            seen.extend(r['event_key'] for r in page['records']);cursor=page['page']['next_before']
        self.assertEqual(seen,sorted(self.keys));self.assertNotIn(newer,seen)
        self.assertEqual(self.spool.status()['records'][0]['event_key'],newer)

    def test_page_counts_remain_global_and_state_updates_do_not_move_positions(self):
        first=self.spool.status(limit=5);cursor=first['page']['next_before']
        key=sorted(self.keys)[6]
        with self.spool.db() as db:db.execute("UPDATE delivery_spool SET state='blocked',attempts=1,last_error='http-403',updated_at=1800000000 WHERE event_key=?",(key,))
        page=self.spool.status(before=cursor,limit=5)
        self.assertEqual([r['event_key'] for r in page['records']],sorted(self.keys)[5:10])
        self.assertEqual(page['counts'],{'pending':27,'inflight':0,'delivered':0,'blocked':1})
        self.assertEqual(next(r for r in page['records'] if r['event_key']==key)['last_error'],'http-403')
        self.assertTrue(all('payload' not in r and 'lease_token' not in r for r in page['records']))

    def test_empty_terminal_and_reopened_pages_preserve_rows(self):
        page=self.spool.status(limit=100);self.assertEqual(len(page['records']),28);self.assertIsNone(page['page']['next_before'])
        cursor=history_cursor(1700000000,sorted(self.keys)[-1])
        terminal=self.spool.status(before=cursor);self.assertEqual(terminal['records'],[]);self.assertEqual(sum(terminal['counts'].values()),28)
        self.assertIsNone(terminal['page']['next_before'])
        self.assertEqual(Spool(self.path).status(before=cursor),terminal)
        with self.spool.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM delivery_spool').fetchone()[0],28)
        empty=Spool(Path(self.temp.name)/'empty.sqlite3').status();self.assertEqual(empty['records'],[]);self.assertIsNone(empty['page']['next_before'])

    def test_malformed_cursor_and_unbounded_or_coerced_limit_are_rejected(self):
        def encode(value):return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
        bad=['!', 'abc=', 'x'*257,encode([True,1700000000,'1'*64]),encode([2,1700000000,'1'*64]),encode([1,True,'1'*64]),encode([1,-1,'1'*64]),encode([1,float('inf'),'1'*64]),encode([1,1700000000,'G'*64]),encode({'time':1700000000}),encode([1,1700000000,'1'*64,'extra'])]
        for cursor in bad:
            with self.subTest(cursor=cursor),self.assertRaises(ValueError):self.spool.status(before=cursor)
        for limit in [0,101,-1,True,1.5,'20']:
            with self.subTest(limit=limit),self.assertRaises(ValueError):self.spool.status(limit=limit)
        self.assertEqual(sum(self.spool.status()['counts'].values()),28)

    def test_filtered_ties_and_newer_arrivals_preserve_original_positions_and_global_counts(self):
        blocked=self.keys[::2]
        with self.spool.db() as db:
            db.executemany("UPDATE delivery_spool SET state='blocked',attempts=1,last_error='http-403' WHERE event_key=?",[(key,) for key in blocked])
        first=self.spool.status(state='blocked',limit=5)
        self.assertEqual(first['page']['state'],'blocked');self.assertEqual(first['counts']['pending'],14)
        self.assertEqual([r['event_key'] for r in first['records']],sorted(blocked)[:5])
        data=envelope();data['observation']['sequence']=100
        new_key=self.spool.enqueue(data)['event_key']
        with self.spool.db() as db:db.execute("UPDATE delivery_spool SET state='blocked',attempts=1,last_error='http-403' WHERE event_key=?",(new_key,))
        seen=[r['event_key'] for r in first['records']];cursor=first['page']['next_before']
        while cursor:
            page=self.spool.status(state='blocked',before=cursor,limit=5)
            self.assertEqual(page['counts']['pending'],14);self.assertEqual(page['counts']['blocked'],15)
            self.assertTrue(all(r['state']=='blocked' for r in page['records']))
            seen.extend(r['event_key'] for r in page['records']);cursor=page['page']['next_before']
        self.assertEqual(seen,sorted(blocked));self.assertEqual(self.spool.status(state='blocked')['records'][0]['event_key'],new_key)
        with self.spool.db() as db:db.execute("UPDATE delivery_spool SET state='pending',last_error=NULL WHERE event_key=?",(new_key,))
        refreshed=self.spool.status(state='blocked');self.assertEqual(refreshed['counts']['pending'],15)
        self.assertNotIn(new_key,[r['event_key'] for r in refreshed['records']])
        empty=self.spool.status(state='delivered');self.assertEqual(empty['records'],[]);self.assertIsNone(empty['page']['next_before'])

    def test_cursors_are_bound_to_filter_and_legacy_all_state_positions_remain_valid(self):
        all_cursor=self.spool.status(limit=5)['page']['next_before']
        pending_cursor=self.spool.status(state='pending',limit=5)['page']['next_before']
        for state,cursor in [('pending',all_cursor),('',pending_cursor),('blocked',pending_cursor)]:
            with self.subTest(state=state),self.assertRaises(ValueError):self.spool.status(state=state,before=cursor)
        self.assertEqual(len(self.spool.status(before=all_cursor)['records']),20)
        self.assertEqual(len(self.spool.status(state='pending',before=pending_cursor)['records']),20)
        for state in ['all','Pending','unknown',True,None]:
            with self.subTest(state=state),self.assertRaises(ValueError):self.spool.status(state=state)


class DeliveryHistoryApiTests(unittest.TestCase):
    login=fixtures.AcquisitionRegistryApiTests.login
    def setUp(self):
        fixtures.AcquisitionRegistryApiTests.setUp(self)
        self.spool_path=Path(self.temp.name)/'history-spool.sqlite3'
        env=patch.dict(os.environ,{'EDGEOPS_DELIVERY_SPOOL_DB':str(self.spool_path)})
        env.start();self.addCleanup(env.stop)
        self.spool=Spool(self.spool_path)
        for sequence in range(24):
            data=copy.deepcopy(envelope());data['observation']['sequence']=sequence;self.spool.enqueue(data)

    def test_roles_can_page_without_mutating_queue_or_gaining_write_authority(self):
        with self.spool.db() as db:before=[tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')]
        for role in ('admin','operator','auditor'):
            self.login(role)
            first=self.http.get('/api/acquisition/delivery');self.assertEqual(first.status_code,200)
            data=first.json();self.assertEqual(len(data['records']),20);self.assertEqual(data['page']['limit'],20)
            self.assertEqual(data['page']['order'],'created-desc-event-asc')
            older=self.http.get('/api/acquisition/delivery',params={'before':data['page']['next_before']});self.assertEqual(older.status_code,200)
            self.assertEqual(len(older.json()['records']),4);self.assertEqual(older.json()['counts']['pending'],24)
            self.assertFalse(set(r['event_key'] for r in data['records'])&set(r['event_key'] for r in older.json()['records']))
            for flag in ('hardware_connected','production_ready','equipment_authorized','model_deployed'):self.assertIs(data[flag],False)
        self.http.cookies.clear();self.assertEqual(self.http.get('/api/acquisition/delivery').status_code,401)
        with self.spool.db() as db:self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM delivery_spool ORDER BY event_key')],before)

    def test_cursor_and_page_size_boundaries_return_safe_errors(self):
        for params in [{'before':'bad!cursor'},{'before':'x'*257},{'limit':0},{'limit':101},{'limit':'true'}]:
            response=self.http.get('/api/acquisition/delivery',params=params)
            with self.subTest(params=params):self.assertEqual(response.status_code,422)
        self.assertEqual(len(self.http.get('/api/acquisition/delivery',params={'limit':1}).json()['records']),1)
        self.assertEqual(len(self.http.get('/api/acquisition/delivery',params={'limit':100}).json()['records']),24)

    def test_state_filters_roles_empty_matches_and_context_mismatch(self):
        for role in ('admin','operator','auditor'):
            self.login(role)
            response=self.http.get('/api/acquisition/delivery',params={'state':'pending','limit':5})
            self.assertEqual(response.status_code,200);data=response.json()
            self.assertEqual(data['page']['state'],'pending');self.assertEqual(len(data['records']),5)
            self.assertEqual(data['counts']['pending'],24)
            older=self.http.get('/api/acquisition/delivery',params={'state':'pending','before':data['page']['next_before']})
            self.assertEqual(older.status_code,200);self.assertEqual(len(older.json()['records']),19)
            empty=self.http.get('/api/acquisition/delivery',params={'state':'blocked'}).json()
            self.assertEqual(empty['records'],[]);self.assertEqual(empty['counts']['pending'],24)
            for state in ('','blocked'):
                self.assertEqual(self.http.get('/api/acquisition/delivery',params={'state':state,'before':data['page']['next_before']}).status_code,422)
        for state in ('all','Pending','unknown'):
            self.assertEqual(self.http.get('/api/acquisition/delivery',params={'state':state}).status_code,422)
