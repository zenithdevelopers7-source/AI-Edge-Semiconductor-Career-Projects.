"""Synthetic documentation exercises against approved revisions; disposable stores only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import maintenance_exercises as exercises
import recovery
import test_maintenance_requests as fixture


class MaintenanceExerciseTests(unittest.TestCase):
    setUp=fixture.MaintenancePlanningTests.setUp
    tearDown=fixture.MaintenancePlanningTests.tearDown
    client=fixture.MaintenancePlanningTests.client
    body=fixture.MaintenancePlanningTests.body
    create=fixture.MaintenancePlanningTests.create
    act=fixture.MaintenancePlanningTests.act
    edit_body=fixture.MaintenancePlanningTests.edit_body

    def approved(self):
        owner,headers=self.client('creator@example.invalid');reviewer,review_headers=self.client('reviewer@example.invalid')
        row=self.create(owner,headers);row=self.act(owner,headers,row,'submit');row=self.act(reviewer,review_headers,row,'approve')
        self.owner,self.headers,self.reviewer,self.review_headers=owner,headers,reviewer,review_headers
        return row

    def exercise(self,plan):
        result=self.owner.post('/api/maintenance-requests/'+plan['id']+'/exercises',headers=self.headers,json={'expected_plan_revision':plan['revision']})
        self.assertEqual(result.status_code,200,result.text)
        return result.json()['exercise']

    def edit_exercise(self,row,**changes):
        body=dict(expected_revision=row['revision'],work_note='Synthetic inspection notes only; no physical task was carried out.',
                  outcome='The synthetic documentation exercise is ready for independent review.',evidence_refs='synthetic-reference-001')
        body.update(changes)
        return self.owner.put('/api/maintenance-exercises/'+row['id'],headers=self.headers,json=body)

    def decide(self,row,action,reviewer=False):
        client,headers=(self.reviewer,self.review_headers) if reviewer else (self.owner,self.headers)
        return client.post('/api/maintenance-exercises/'+row['id']+'/actions',headers=headers,json={
            'expected_revision':row['revision'],'action':action,'note':'Reviewed synthetic documentation only; physical work remains unverified.'})

    def test_complete_review_and_edit_invalidation_preserve_original_notes(self):
        plan=self.approved();row=self.exercise(plan);row=self.edit_exercise(row).json()['exercise']
        row=self.decide(row,'submit').json()['exercise'];result=self.decide(row,'verify',True)
        self.assertEqual(result.status_code,200,result.text);data=result.json();row=data['exercise']
        self.assertEqual(row['state'],'verified');self.assertFalse(data['physical_work_verified']);self.assertFalse(data['execution_enabled'])
        revised=self.edit_exercise(row,outcome='A revised synthetic outcome must clear the earlier exercise review.').json()
        self.assertEqual(revised['exercise']['state'],'draft');self.assertIsNone(revised['exercise']['reviewer_email'])
        self.assertTrue(any(event['record']['outcome']=='The synthetic documentation exercise is ready for independent review.' for event in revised['history']))

    def test_unapproved_plan_and_wrong_owner_cannot_create_an_exercise(self):
        plan=self.approved()
        self.assertEqual(self.reviewer.post('/api/maintenance-requests/'+plan['id']+'/exercises',headers=self.review_headers,json={'expected_plan_revision':plan['revision']}).status_code,403)
        other=self.create(self.owner,self.headers)
        self.assertEqual(self.owner.post('/api/maintenance-requests/'+other['id']+'/exercises',headers=self.headers,json={'expected_plan_revision':1}).status_code,409)
        with patch.object(exercises,'MAX_PER_PLAN',0):
            self.assertEqual(self.owner.post('/api/maintenance-requests/'+plan['id']+'/exercises',headers=self.headers,json={'expected_plan_revision':plan['revision']}).status_code,409)

    def test_idempotent_concurrent_creation_and_retry_after_plan_change(self):
        plan=self.approved();url='/api/maintenance-requests/'+plan['id']+'/exercises'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.owner.post(url,headers=self.headers,json={'expected_plan_revision':plan['revision']}),range(2)))
        self.assertTrue(all(result.status_code==200 for result in results))
        self.assertEqual(sorted(result.json()['created'] for result in results),[False,True])
        self.owner.put('/api/maintenance-requests/'+plan['id'],headers=self.headers,json=self.edit_body(plan))
        retry=self.owner.post(url,headers=self.headers,json={'expected_plan_revision':plan['revision']}).json()
        self.assertFalse(retry['created']);self.assertTrue(retry['exercise']['plan_changed_since_capture'])

    def test_stale_plan_blocks_review_but_allows_withdrawal(self):
        plan=self.approved();row=self.edit_exercise(self.exercise(plan)).json()['exercise'];row=self.decide(row,'submit').json()['exercise']
        changed=self.owner.put('/api/maintenance-requests/'+plan['id'],headers=self.headers,json=self.edit_body(plan)).json()['request']
        self.assertEqual(self.decide(row,'verify',True).status_code,409)
        withdrawn=self.decide(row,'withdraw');self.assertEqual(withdrawn.status_code,200)
        self.assertTrue(withdrawn.json()['exercise']['plan_changed_since_capture'])
        self.assertEqual(self.edit_exercise(withdrawn.json()['exercise']).status_code,409)
        changed=self.act(self.owner,self.headers,changed,'submit');changed=self.act(self.reviewer,self.review_headers,changed,'approve')
        new=self.exercise(changed)
        self.assertNotEqual(new['id'],row['id'])

    def test_self_review_auditor_other_operator_and_csrf(self):
        plan=self.approved();row=self.edit_exercise(self.exercise(plan)).json()['exercise'];row=self.decide(row,'submit').json()['exercise']
        with self.server.database() as db:db.execute("UPDATE users SET role='admin' WHERE email='creator@example.invalid'")
        self.assertEqual(self.decide(row,'verify').status_code,403)
        auditor,audit_headers=self.client('audit@example.invalid')
        self.assertEqual(auditor.get('/api/maintenance-exercises/'+row['id']).status_code,200)
        self.assertEqual(auditor.post('/api/maintenance-exercises/'+row['id']+'/actions',headers=audit_headers,json={'expected_revision':row['revision'],'action':'verify','note':'Auditor must remain read only.'}).status_code,403)
        other,other_headers=self.client('other@example.invalid')
        self.assertEqual(other.get('/api/maintenance-exercises/'+row['id']).status_code,404)
        self.assertEqual(self.owner.post('/api/maintenance-requests/'+plan['id']+'/exercises',json={'expected_plan_revision':plan['revision']}).status_code,403)

    def test_missing_evidence_stale_revision_and_input_claims_are_rejected(self):
        plan=self.approved();row=self.exercise(plan)
        self.assertEqual(self.decide(row,'submit').status_code,422)
        edited=self.edit_exercise(row,evidence_refs='').json()['exercise'];self.assertEqual(self.decide(edited,'submit').status_code,422)
        self.assertEqual(self.edit_exercise(row).status_code,409)
        self.assertEqual(self.edit_exercise(edited,physical_work_verified=True).status_code,422)
        self.assertEqual(self.edit_exercise(edited,expected_revision=True).status_code,422)

    def test_rejection_withdrawal_and_bounded_history(self):
        plan=self.approved();row=self.edit_exercise(self.exercise(plan)).json()['exercise'];row=self.decide(row,'submit').json()['exercise']
        row=self.decide(row,'reject',True).json()['exercise'];self.assertEqual(row['state'],'rejected')
        row=self.edit_exercise(row).json()['exercise'];self.assertEqual(row['state'],'draft')
        with patch.object(exercises,'MAX_REVISIONS',row['revision']):self.assertEqual(self.decide(row,'submit').status_code,409)

    def test_audit_failure_rolls_back_exercise_and_event(self):
        plan=self.approved();row=self.exercise(plan)
        with self.server.database() as db:db.execute("CREATE TRIGGER deny_exercise_audit BEFORE INSERT ON audit WHEN NEW.action='maintenance_exercise_edited' BEGIN SELECT RAISE(ABORT,'fixture failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.edit_exercise(row)
        detail=self.owner.get('/api/maintenance-exercises/'+row['id']).json()
        self.assertEqual((detail['exercise']['revision'],len(detail['history'])),(1,1))

    def test_backup_restore_preserves_approved_snapshot_and_notes(self):
        plan=self.approved();row=self.edit_exercise(self.exercise(plan)).json()['exercise']
        backup=Path(self.temp.name)/'backup';restore=Path(self.temp.name)/'restore'
        recovery.create_backup(self.server.DB_PATH,backup);recovery.restore_backup(backup,restore)
        with closing(sqlite3.connect(restore/'dashboard.sqlite3')) as db:
            db.row_factory=sqlite3.Row
            saved=db.execute('SELECT * FROM maintenance_exercises').fetchone()
            self.assertEqual(saved['evidence_refs'],'synthetic-reference-001')
            self.assertIn(plan['title'],saved['plan_snapshot_json'])
            self.assertEqual(db.execute('SELECT count(*) FROM maintenance_exercise_events').fetchone()[0],2)

    def test_revoked_session_is_rechecked_inside_write(self):
        plan=self.approved();row=self.exercise(plan);original=exercises.plans.fresh_actor
        def revoke(db,current):
            db.execute('UPDATE sessions SET expires_at=0 WHERE user_id=?',(current['id'],));return original(db,current)
        with patch.object(exercises.plans,'fresh_actor',side_effect=revoke):self.assertEqual(self.edit_exercise(row).status_code,401)
