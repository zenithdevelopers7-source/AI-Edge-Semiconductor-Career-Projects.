"""Append-only synthetic investigation updates and exact-retry protection."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import secrets
import sqlite3
import unittest
from unittest.mock import patch

import incidents
import recovery
import test_acquisition_registry as fixture
import test_incidents as incident_fixture


class IncidentInvestigationTests(unittest.TestCase):
    setUp=fixture.AcquisitionRegistryApiTests.setUp
    login=fixture.AcquisitionRegistryApiTests.login
    post=fixture.AcquisitionRegistryApiTests.post
    create=incident_fixture.IncidentApiTests.create
    action=incident_fixture.IncidentApiTests.action

    def body(self,row,**changes):
        return {'request_key':secrets.token_hex(16),'expected_revision':row['revision'],'kind':'update',
                'note':'Synthetic progress recorded without establishing a physical fault.', 'evidence_refs':'',**changes}

    def save(self,row,body=None,**changes):
        return self.post('/api/incidents/'+row['id']+'/investigation',body or self.body(row,**changes))

    def test_progress_analysis_evidence_history_preserves_initial_context(self):
        initial=row=self.create()
        for kind in ('update','analysis','evidence'):
            result=self.save(row,kind=kind,note='Synthetic '+kind+' note retained in incident history.',evidence_refs='fixture-evidence-001')
            self.assertEqual(result.status_code,200,result.text);data=result.json();row=data['incident']
            self.assertEqual(row['state'],'open');self.assertEqual(row['observation'],initial['observation'])
            self.assertFalse(data['hardware_connected']);self.assertFalse(data['equipment_authorized']);self.assertFalse(data['external_notifications_sent'])
        self.server.init_db();data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertEqual([h['action'] for h in data['history']],['investigation_evidence','investigation_analysis','investigation_update','create'])
        self.assertEqual(data['history'][0]['evidence_refs'],'fixture-evidence-001');self.assertEqual(row['revision'],4)

    def test_response_loss_retry_is_exact_and_returns_original_update_revision(self):
        row=self.create();body=self.body(row);first=self.save(row,body);self.assertTrue(first.json()['created'])
        row=first.json()['incident'];row=self.action(row,'acknowledge').json()['incident'];row=self.action(row,'resolve').json()['incident']
        retry=self.save(row,body);self.assertEqual(retry.status_code,200);self.assertFalse(retry.json()['created'])
        self.assertEqual(retry.json()['update_revision'],2);self.assertEqual(retry.json()['incident']['revision'],4)
        self.assertEqual(self.save(row,{**body,'note':'Changed content cannot reuse an already committed key.'}).status_code,409)

    def test_concurrent_exact_retries_commit_once_and_distinct_updates_conflict(self):
        row=self.create();body=self.body(row)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.save(row,body),range(2)))
        self.assertTrue(all(r.status_code==200 for r in results));self.assertEqual(sorted(r.json()['created'] for r in results),[False,True])
        row=results[0].json()['incident'];bodies=[self.body(row),self.body(row)]
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda b:self.save(row,b),bodies))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])

    def test_strict_input_and_evidence_requirement(self):
        row=self.create()
        for changes in ({'kind':'physical-repair'},{'kind':'evidence','evidence_refs':' '},{'expected_revision':True},
                        {'note':'short'},{'note':'x'*801},{'evidence_refs':'x'*1001},{'request_key':'bad'},
                        {'extra':'not accepted'},{'note':42}):
            self.assertEqual(self.save(row,**changes).status_code,422,str(changes))
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).json()['incident']['revision'],1)

    def test_unrelated_operator_cannot_read_or_write_and_auditor_is_readonly(self):
        row=self.create();self.login('operator');self.assertEqual(self.save(row).status_code,404)
        self.assertEqual(self.http.get('/api/incidents/'+row['id']).status_code,404)
        self.login('auditor');data=self.http.get('/api/incidents/'+row['id']).json()
        self.assertFalse(data['incident']['can_add_update']);self.assertEqual(self.save(row).status_code,403)
        self.http.cookies.clear();self.assertEqual(self.http.post('/api/incidents/'+row['id']+'/investigation',json=self.body(row)).status_code,401)

    def test_creator_and_assignee_can_record_but_reassignment_revokes_retry(self):
        row=self.create()
        with self.server.database() as db:target=db.execute("SELECT id FROM users WHERE role='operator'").fetchone()[0]
        row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':1,'assignee_id':target,'note':'Share this synthetic investigation with a local operator.'}).json()['incident']
        self.login('operator');body=self.body(row);result=self.save(row,body);self.assertEqual(result.status_code,200);row=result.json()['incident']
        self.login('admin');result=self.save(row,{**body,'expected_revision':row['revision']})
        self.assertEqual(result.status_code,200);self.assertTrue(result.json()['created']);row=result.json()['incident']
        row=self.post('/api/incidents/'+row['id']+'/assignment',{'expected_revision':row['revision'],'assignee_id':None,'note':'Remove the investigation assignment explicitly.'}).json()['incident']
        self.login('operator');self.assertEqual(self.save(row,body).status_code,404)

    def test_csrf_current_session_capacity_and_resolved_guards(self):
        row=self.create();body=self.body(row)
        self.assertEqual(self.post('/api/incidents/'+row['id']+'/investigation',body,csrf=False).status_code,403)
        with patch.object(incidents,'MAX_REVISIONS',1):self.assertEqual(self.save(row).status_code,409)
        original=incidents.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(incidents,'fresh_actor',side_effect=revoke):self.assertEqual(self.save(row).status_code,401)
        row=self.action(row,'acknowledge').json()['incident'];row=self.action(row,'resolve').json()['incident']
        self.assertEqual(self.save(row).status_code,409);row=self.action(row,'reopen').json()['incident'];self.assertEqual(self.save(row).status_code,200)

    def test_audit_or_retry_key_failure_rolls_back_entire_update(self):
        for table,condition in [('audit',"WHEN NEW.action='synthetic_incident_investigation_update'"),('incident_investigation_keys','')]:
            row=self.create()
            with self.server.database() as db:db.execute('CREATE TRIGGER fail_investigation BEFORE INSERT ON '+table+' '+condition+" BEGIN SELECT RAISE(ABORT,'synthetic rollback'); END")
            with self.assertRaises(sqlite3.IntegrityError):self.save(row)
            data=self.http.get('/api/incidents/'+row['id']).json();self.assertEqual(data['incident']['revision'],1);self.assertEqual(len(data['history']),1)
            with self.server.database() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM incident_investigation_keys WHERE incident_id=?',(row['id'],)).fetchone()[0],0)
                db.execute('DROP TRIGGER fail_investigation')

    def test_backup_restore_preserves_update_and_retry_identity(self):
        row=self.create();body=self.body(row,kind='evidence',evidence_refs='synthetic-evidence-file-ref')
        self.assertEqual(self.save(row,body).status_code,200)
        with self.server.database() as db:identity=tuple(db.execute('SELECT * FROM incident_investigation_keys').fetchone())
        backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restored'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restore)
        with closing(sqlite3.connect(restore/'dashboard.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT * FROM incident_investigation_keys').fetchone(),identity)
            self.assertEqual(db.execute("SELECT evidence_refs FROM synthetic_incident_events WHERE action='investigation_evidence'").fetchone()[0],'synthetic-evidence-file-ref')

    def test_linked_planning_snapshot_is_retained_and_change_flag_updates(self):
        row=self.create();plan=self.post('/api/incidents/'+row['id']+'/maintenance-plan',{'expected_revision':1,'proposal':'Review the initial synthetic context without altering its source.'}).json()['request']
        self.assertEqual(self.save(row).status_code,200)
        source=self.http.get('/api/maintenance-requests/'+plan['id']).json()['source_incident']
        self.assertTrue(source['changed_since_capture']);self.assertEqual(source['snapshot']['revision'],1)
        self.assertNotIn('can_add_update',source['snapshot'])
