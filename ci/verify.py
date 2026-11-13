"""Synthetic receipt-contract tests only; no provider, memory server or deployment."""
import copy,hashlib,json,re,unittest
from datetime import datetime,timezone,timedelta

REQUIRED={'id','project','revision','source_sha256','status','data_class','operation','approved','expires_at','superseded_by','estimated_cost_usd'}

def accept(record,*,project,revision,source,channel,at,cap):
    if set(record)!=REQUIRED:raise ValueError('unknown/missing fields')
    if not isinstance(record['id'],str) or not re.fullmatch(r'[a-z][a-z0-9-]{2,63}',record['id']):raise ValueError('invalid receipt id')
    if channel not in ['local','cloud']:raise ValueError('unknown channel')
    if record['data_class'] not in ['synthetic','public','private']:raise ValueError('unknown data class')
    if channel=='cloud' and record['data_class'] not in ['synthetic','public']:raise PermissionError('keep private data local')
    if record['project']!=project or record['revision']!=revision:raise ValueError('wrong project or revision')
    if record['source_sha256']!=hashlib.sha256(source).hexdigest():raise ValueError('source drift')
    if record['status']!='VERIFIED' or record['superseded_by']:raise ValueError('unverified/superseded claim')
    if record['operation']!='verify' or record['approved'] is not True:raise PermissionError('operation not allowed')
    expires=datetime.fromisoformat(record['expires_at'])
    if expires.tzinfo is None or expires<=at:raise ValueError('expired or timezone missing')
    cost=record['estimated_cost_usd']
    if isinstance(cost,bool) or not isinstance(cost,(float,int)) or not 0<=cost<=cap:raise ValueError('cost cap')
    return record['id']

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.at=datetime(2026,11,13,tzinfo=timezone.utc)
        self.source=b'fictional nonprivate fixture source'
        self.record={'id':'synthetic-001','project':'synthetic-ci','revision':'fixture-v1','source_sha256':hashlib.sha256(self.source).hexdigest(),'status':'VERIFIED','data_class':'synthetic','operation':'verify','approved':True,'expires_at':(self.at+timedelta(days=1)).isoformat(),'superseded_by':None,'estimated_cost_usd':0}
    def check(self,record=None,**overrides):
        args=dict(project='synthetic-ci',revision='fixture-v1',source=self.source,channel='cloud',at=self.at,cap=0)
        args.update(overrides);return accept(self.record if record is None else record,**args)
    def test_valid_receipt(self):self.assertEqual(self.check(),'synthetic-001')
    def test_export_restore(self):self.assertEqual(self.check(json.loads(json.dumps(self.record))),'synthetic-001')
    def test_private_cloud_denied(self):
        self.record['data_class']='private'
        with self.assertRaises(PermissionError):self.check()
    def test_private_local_allowed(self):
        self.record['data_class']='private';self.assertEqual(self.check(channel='local'),'synthetic-001')
    def test_stale_source(self):
        with self.assertRaises(ValueError):self.check(source=b'changed')
    def test_cross_project(self):
        with self.assertRaises(ValueError):self.check(project='other')
    def test_wrong_revision(self):
        with self.assertRaises(ValueError):self.check(revision='old')
    def test_expired_claim(self):
        with self.assertRaises(ValueError):self.check(at=self.at+timedelta(days=2))
    def test_superseded_claim(self):
        self.record['superseded_by']='new'
        with self.assertRaises(ValueError):self.check()
    def test_failed_claim(self):
        self.record['status']='FAILED'
        with self.assertRaises(ValueError):self.check()
    def test_publish_denied(self):
        self.record['operation']='publish'
        with self.assertRaises(PermissionError):self.check()
    def test_admin_denied(self):
        self.record['operation']='admin'
        with self.assertRaises(PermissionError):self.check()
    def test_approval_required(self):
        self.record['approved']=False
        with self.assertRaises(PermissionError):self.check()
    def test_unknown_field_rejected(self):
        self.record['credential']='FICTIONAL-ONLY'
        with self.assertRaises(ValueError):self.check()
    def test_budget_denial(self):
        self.record['estimated_cost_usd']=.01
        with self.assertRaises(ValueError):self.check()
    def test_unknown_channel(self):
        with self.assertRaises(ValueError):self.check(channel='unknown')
    def test_empty_id_rejected(self):
        self.record['id']=''
        with self.assertRaises(ValueError):self.check()
    def test_object_id_rejected(self):
        self.record['id']={}
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':unittest.main(verbosity=2)
