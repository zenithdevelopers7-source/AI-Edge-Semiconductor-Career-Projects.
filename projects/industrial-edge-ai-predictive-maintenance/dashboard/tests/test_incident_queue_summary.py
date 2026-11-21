"""Account-scoped aggregate views over persisted synthetic incident exercises."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import incidents
import test_acquisition_registry as fixture
import test_incidents as cases


class IncidentQueueSummaryTests(unittest.TestCase):
    setUp=fixture.AcquisitionRegistryApiTests.setUp
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    create=cases.IncidentApiTests.create
    action=cases.IncidentApiTests.action

    def summary(self, query=''):
        response=self.http.get('/api/incidents'+query)
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['queue_summary']

    def assign(self,row,role):
        with self.server.database() as db:target=db.execute('SELECT id FROM users WHERE role=?',(role,)).fetchone()[0]
        result=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':row['revision'],
            'assignee_id':target,'note':'Assign a synthetic exercise for the scoped overview.'})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['incident']

    def due(self,row,when):
        result=self.post('/api/incidents/'+row['id']+'/follow-up',{'expected_revision':row['revision'],
            'due_at':when,'note':'Set a date for this synthetic overview exercise.'})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['incident']

    def test_empty_summary_and_truthful_boundary(self):
        data=self.http.get('/api/incidents').json();summary=data['queue_summary']
        self.assertEqual({k:v for k,v in summary.items() if k not in ('scope','as_of')},
            dict(active=0,critical_active=0,overdue_active=0,unassigned_active=0,assigned_to_me_active=0))
        self.assertEqual(summary['scope'],'all-accessible-saved-incidents')
        self.assertIsNotNone(datetime.fromisoformat(summary['as_of']).tzinfo)
        for name in ('hardware_connected','production_ready','equipment_authorized','external_notifications_sent'):
            self.assertIs(data[name],False)

    def test_active_includes_acknowledged_excludes_resolved_and_reopen_restores(self):
        opened=self.create();ack=self.action(self.create(),'acknowledge').json()['incident']
        resolved=self.action(self.action(self.create(),'acknowledge').json()['incident'],'resolve').json()['incident']
        data=self.http.get('/api/incidents?state=active').json()
        self.assertEqual(data['total'],2);self.assertEqual({r['id'] for r in data['incidents']},{opened['id'],ack['id']})
        self.assertEqual(data['queue_summary']['active'],2)
        self.action(resolved,'reopen');self.assertEqual(self.summary()['active'],3)
        self.assertEqual(self.http.get('/api/incidents?state=invalid').status_code,422)

    def test_summary_ignores_every_filter_and_pagination(self):
        first=self.assign(self.create(),'admin');self.due(first,'2001-01-01T00:00:00Z')
        self.create();self.create()
        expected=self.summary();expected.pop('as_of')
        for query in ('?limit=1&offset=1','?state=resolved&q=absent&severity=critical&follow_up=upcoming&ownership=unassigned&sort=severity',
                      '?ownership=assigned','?ownership=created','?state=active&follow_up=overdue'):
            with self.subTest(query=query):
                summary=self.summary(query);summary.pop('as_of');self.assertEqual(summary,expected)
        self.assertEqual(expected['active'],3);self.assertEqual(expected['assigned_to_me_active'],1)
        self.assertEqual(expected['unassigned_active'],2);self.assertEqual(expected['overdue_active'],1)

    def test_operator_counts_only_created_or_assigned_records_and_handoff_removes_scope(self):
        private=self.create();shared=self.assign(self.create(),'operator')
        self.login('operator');own=self.create();summary=self.summary('?ownership=unassigned')
        self.assertEqual(summary['active'],2);self.assertEqual(summary['assigned_to_me_active'],1)
        self.assertEqual(summary['unassigned_active'],1)
        self.assertEqual(self.http.get('/api/incidents/'+private['id']).status_code,404)
        self.login('admin')
        response=self.post('/api/incidents/'+shared['id']+'/assignment',{'expected_revision':shared['revision'],
            'assignee_id':None,'note':'Remove the synthetic assignment to verify current visibility.'})
        self.assertEqual(response.status_code,200)
        self.login('operator');summary=self.summary();self.assertEqual(summary['active'],1)
        self.assertEqual(summary['assigned_to_me_active'],0)
        self.assertEqual(self.http.get('/api/incidents?state=active').json()['incidents'][0]['id'],own['id'])

    def test_current_reviewed_severity_used_without_rewriting_original(self):
        row=self.create()
        result=self.post('/api/incidents/'+row['id']+'/severity',{'expected_revision':1,'severity':'critical',
            'note':'Review this synthetic case severity for the aggregate view.'})
        self.assertEqual(result.status_code,200);self.assertEqual(self.summary()['critical_active'],1)
        data=self.http.get('/api/incidents?state=active&severity=critical').json()
        self.assertEqual(data['total'],1);self.assertEqual(data['incidents'][0]['initial_severity'],'watch')
        row=self.action(result.json()['incident'],'acknowledge').json()['incident']
        self.action(row,'resolve');self.assertEqual(self.summary()['critical_active'],0)

    def test_overdue_boundary_uses_same_clock_as_rows_and_excludes_resolved(self):
        at='2026-11-20T10:00:00.000000+00:00'
        equal=self.due(self.create(),at);self.due(self.create(),'2026-11-20T10:00:00.000001+00:00')
        past=self.due(self.create(),'2001-01-01T00:00:00Z')
        self.action(self.action(past,'acknowledge').json()['incident'],'resolve')
        self.create()
        class FixedClock(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.fromisoformat(at).astimezone(tz)
        with patch.object(incidents,'datetime',FixedClock):
            data=self.http.get('/api/incidents?state=active&follow_up=overdue').json()
        self.assertEqual(data['queue_summary']['as_of'],at);self.assertEqual(data['queue_summary']['overdue_active'],1)
        self.assertEqual(data['total'],1);self.assertEqual(data['incidents'][0]['id'],equal['id'])
        self.assertEqual(data['incidents'][0]['follow_up']['status'],'overdue')

    def test_paged_totals_and_ownership_counts_keep_distinct_meanings(self):
        for _ in range(27):self.create()
        self.assign(self.create(),'admin')
        data=self.http.get('/api/incidents?ownership=assigned&limit=1&offset=1').json()
        self.assertEqual(data['counts']['open'],1);self.assertEqual(data['total'],1)
        self.assertEqual(data['incidents'],[]);self.assertEqual(data['queue_summary']['active'],28)

    def test_auditor_can_read_all_without_writes_and_anonymous_is_denied(self):
        self.assign(self.create(),'operator');self.create();self.login('auditor')
        def snapshot():
            with self.server.database() as db:
                tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='sessions'")]
                return {name:[tuple(r) for r in db.execute('SELECT * FROM "'+name+'" ORDER BY rowid')] for name in tables}
        before=snapshot();self.assertEqual(self.summary()['active'],2)
        data=self.http.get('/api/incidents?state=active&ownership=assigned').json()
        self.assertEqual(data['total'],0);self.assertEqual(data['queue_summary']['active'],2)
        self.assertFalse(data['can_create']);self.assertEqual(snapshot(),before)
        self.http.cookies.clear();self.assertEqual(self.http.get('/api/incidents?state=active').status_code,401)
