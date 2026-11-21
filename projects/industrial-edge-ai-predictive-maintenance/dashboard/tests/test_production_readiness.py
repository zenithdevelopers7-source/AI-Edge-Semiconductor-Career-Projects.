"""Completeness, scope binding and non-certification of the evidence register."""
import importlib
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class ProductionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='edgeops-readiness-');self.password=secrets.token_urlsafe(24)
        self.env=patch.dict(os.environ,{'EDGEOPS_DASHBOARD_DB':str(Path(self.temp.name)/'auth.db'),'EDGEOPS_ADMIN_EMAIL':'author@example.invalid','EDGEOPS_ADMIN_PASSWORD':self.password});self.env.start()
        import server
        self.server=importlib.reload(server);self.server.init_db();encoded=self.server.password_hash(self.password)
        with self.server.database() as db:
            for email,role in [('reviewer@example.invalid','admin'),('audit@example.invalid','auditor'),('operator@example.invalid','operator')]:db.execute('INSERT INTO users(email,password_hash,role) VALUES(?,?,?)',(email,encoded,role))
        self.clients=[]

    def tearDown(self):
        for client in self.clients:client.close()
        self.env.stop();self.temp.cleanup()

    def client(self,email='author@example.invalid'):
        client=TestClient(self.server.app);self.clients.append(client)
        self.assertEqual(client.post('/api/auth/login',json={'email':email,'password':self.password}).status_code,200)
        return client,{'x-edgeops-csrf':client.cookies.get('edgeops_csrf')}

    def scope(self,client,headers):
        values={key:'Test acceptance reference and scope: '+key for key in self.server.production_readiness.SCOPE_FIELDS};values['blocking_defects']='none'
        response=client.put('/api/production-readiness/release-scope',headers=headers,json={'expected_revision':0,'values':values});self.assertEqual(response.status_code,200,response.text);return response.json()

    def edit(self,client,headers,item='REQ-01',revision=0,status='evidence_ready',**extra):
        body={'expected_revision':revision,'status':status,'owner':'Test responsible engineer','evidence':'TEST-ONLY external evidence reference; not actual commissioning.','notes':'Controlled test register record.','target_value':'10 agreed test units with stated conditions',**extra}
        return client.put('/api/production-readiness/items/'+item,headers=headers,json=body)

    def review(self,client,headers,item='REQ-01',revision=1,scope=1,**extra):
        return client.post('/api/production-readiness/items/'+item+'/review',headers=headers,json={'expected_revision':revision,'expected_scope_revision':scope,'decision':'accepted','note':'Test-only recorded evidence decision; external verification is separate.','qualification_reference':'TEST-ONLY reviewer reference and declared qualification.',**extra})

    def test_01_complete_catalog_and_hardware_export(self):
        client,headers=self.client();data=client.get('/api/production-readiness').json()
        self.assertEqual(data['total'],53);self.assertEqual(data['accepted'],0)
        self.assertEqual({kind:sum(x['kind']==kind for x in data['catalog']['items']) for kind in ['requirement','demonstration','target']},{'requirement':18,'demonstration':15,'target':20})
        self.assertEqual(len({x['group'] for x in data['catalog']['items'] if x['kind']=='target'}),7)
        self.assertTrue(all(x['description'] and x['evidence_required'] and x['current_boundary'] for x in data['catalog']['items']))
        exported=client.get('/api/production-readiness/export').json()
        self.assertEqual(len(exported['hardware']),30);self.assertEqual(len(exported['histories']),53)
        self.assertTrue(all(not item['physical_inventory_verified'] for item in exported['hardware']))
        self.assertFalse(exported['production_ready']);self.assertFalse(exported['physical_acceptance_verified'])

    def test_02_auth_csrf_and_read_only_roles(self):
        guest=TestClient(self.server.app);self.clients.append(guest)
        self.assertEqual(guest.get('/api/production-readiness').status_code,401)
        self.assertEqual(guest.get('/api/production-readiness/export').status_code,401)
        author,headers=self.client()
        self.assertEqual(self.edit(author,{},status='in_progress').status_code,403)
        for email in ['audit@example.invalid','operator@example.invalid']:
            client,csrf=self.client(email);self.assertFalse(client.get('/api/production-readiness').json()['can_edit'])
            self.assertEqual(self.edit(client,csrf).status_code,403)
            self.assertEqual(client.get('/api/production-readiness/items/REQ-01').status_code,200)

    def test_03_evidence_validation_and_revision_conflict(self):
        client,headers=self.client()
        self.assertEqual(self.edit(client,headers,owner='').status_code,422)
        self.assertEqual(self.edit(client,headers,evidence='').status_code,422)
        self.assertEqual(self.edit(client,headers,item='TARGET-01',target_value='TBD').status_code,422)
        self.assertEqual(self.edit(client,headers,status='accepted').status_code,422)
        self.assertEqual(self.edit(client,headers,revision=True).status_code,422)
        first=self.edit(client,headers);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.edit(client,headers).status_code,409)
        self.assertEqual(len(client.get('/api/production-readiness/items/REQ-01').json()['history']),1)
        self.assertEqual(self.edit(client,headers,item='UNKNOWN').status_code,404)

    def test_04_independent_review_and_edit_invalidation(self):
        author,headers=self.client();reviewer,review_headers=self.client('reviewer@example.invalid');self.scope(author,headers)
        self.assertEqual(self.edit(author,headers).status_code,200)
        self.assertEqual(self.review(author,headers).status_code,403)
        approved=self.review(reviewer,review_headers);self.assertEqual(approved.status_code,200,approved.text)
        self.assertEqual(approved.json()['record']['status'],'accepted');self.assertFalse(approved.json()['production_ready'])
        self.assertEqual(self.review(reviewer,review_headers).status_code,409)
        edited=self.edit(author,headers,revision=2,status='in_progress');self.assertEqual(edited.status_code,200)
        self.assertIsNone(edited.json()['record']['reviewer']);self.assertEqual(edited.json()['history'][1]['action'],'accepted')
        self.assertIn('TEST-ONLY',edited.json()['history'][1]['snapshot']['qualification_reference'])

    def test_05_scope_binding_invalidation_and_reference_updates(self):
        author,headers=self.client();reviewer,review_headers=self.client('reviewer@example.invalid');scope=self.scope(author,headers)
        self.edit(author,headers);self.review(reviewer,review_headers);self.edit(author,headers,item='DEMO-01')
        values=scope['release']['values'];values['final_acceptance_ref']='Additional external acceptance reference only.'
        references=author.put('/api/production-readiness/release-scope',headers=headers,json={'expected_revision':1,'values':values});self.assertEqual(references.status_code,200)
        self.assertEqual(references.json()['accepted'],1);self.assertEqual(references.json()['release']['binding_revision'],1)
        values['equipment']='Changed physical equipment scope'
        changed=author.put('/api/production-readiness/release-scope',headers=headers,json={'expected_revision':2,'values':values});self.assertEqual(changed.status_code,200)
        self.assertEqual(changed.json()['accepted'],0);self.assertEqual(changed.json()['release']['binding_revision'],2)
        self.assertEqual(author.get('/api/production-readiness/items/DEMO-01').json()['record']['status'],'in_progress')
        self.assertEqual(self.review(reviewer,review_headers,item='DEMO-01',revision=1,scope=1).status_code,409)
        self.assertEqual(author.put('/api/production-readiness/release-scope',headers=headers,json={'expected_revision':1,'values':values}).status_code,409)

    def test_06_scope_required_and_revocation_rechecked(self):
        author,headers=self.client();reviewer,review_headers=self.client('reviewer@example.invalid');self.edit(author,headers)
        self.assertEqual(self.review(reviewer,review_headers,scope=0).status_code,409)
        self.scope(author,headers)
        with self.server.database() as db:
            stale=dict(db.execute("SELECT u.id,u.email,u.role,s.csrf_hash,s.expires_at FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.email='reviewer@example.invalid'").fetchone())
            db.execute("UPDATE users SET role='auditor' WHERE email='reviewer@example.invalid'")
        with patch.object(self.server,'auth_context',return_value=stale):self.assertEqual(self.review(reviewer,review_headers).status_code,403)

    def test_07_full_recorded_register_never_certifies_production(self):
        author,headers=self.client();reviewer,review_headers=self.client('reviewer@example.invalid');self.scope(author,headers)
        for item in self.server.production_readiness.DEFINITIONS:
            response=self.edit(author,headers,item=item);self.assertEqual(response.status_code,200,response.text)
            response=self.review(reviewer,review_headers,item=item);self.assertEqual(response.status_code,200,response.text)
        data=author.get('/api/production-readiness').json()
        self.assertEqual(data['accepted'],53);self.assertTrue(data['tracking_complete'])
        self.assertFalse(data['production_ready']);self.assertFalse(data['physical_acceptance_verified']);self.assertFalse(data['equipment_authorized'])
        with self.server.database() as db:self.assertEqual(db.execute('SELECT count(*) FROM readiness_events').fetchone()[0],106)


if __name__=='__main__':unittest.main()
