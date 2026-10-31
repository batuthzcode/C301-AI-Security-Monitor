"""Run: python -m unittest -v Ti_Cyber_Testleri"""
import json
from pathlib import Path
import tempfile
import unittest
from ti_cyber_inventory import InventoryError, parse_topology, import_snapshot, latest, describe


def response(devices):
    return json.dumps({'_tag':'topo_x','token':'SECRET_NEVER_STORE','data':{'List':devices}},ensure_ascii=False)

A={'HostName':'Laptop','IpAddr':'192.168.1.20','MacAddr':'AA:BB:CC:11:22:33','ConnectionType':'WiFi'}
B={'DeviceName':'Telefon','ipAddress':'192.168.1.22','macAddress':'aa-bb-cc-44-55-66','ConnectionType':'WiFi'}
C={'HostName':'TV','IpAddr':'192.168.1.30','MacAddr':'AABBCC778899'}

class InventoryTests(unittest.TestCase):
    def test_nested_list(self):
        got=parse_topology(response([A,B]))
        self.assertEqual(len(got),2)
        self.assertEqual({x['name'] for x in got},{'Laptop','Telefon'})
    def test_mac_normalization(self):
        self.assertEqual(parse_topology(response([B]))[0]['mac'],'AA:BB:CC:44:55:66')
    def test_duplicate_is_one(self):
        self.assertEqual(len(parse_topology(response([A,A]))),1)
    def test_embedded_json_string(self):
        self.assertEqual(len(parse_topology(json.dumps({'Result':response([A])}))),1)
    def test_mesh_controller_status_filtered(self):
        fake={'instID':'MESH.CONTROLLER','IpAddr':'192.168.1.1','MacAddr':'AA:BB:CC:11:11:11'}
        self.assertEqual(len(parse_topology(response([fake,A]))),1)
    def test_missing_identifier(self):
        self.assertEqual(parse_topology(json.dumps([{'name':'no IP or MAC'}])),[])
    def test_valid_name_and_ip_fallback(self):
        got=parse_topology(response([{'DeviceName':'Tablet','IpAddr':'192.168.1.21'}]))
        self.assertEqual(got[0]['identity_quality'],'ad+IP')
    def test_excludes_secret_fields(self):
        rec=parse_topology(response([A]))[0]
        self.assertNotIn('token',rec)
        self.assertNotIn('SECRET_NEVER_STORE',str(rec))
    def test_limits_bytes(self):
        with self.assertRaises(InventoryError):parse_topology('x'*1_500_001)
    def test_invalid_json(self):
        with self.assertRaises(InventoryError):parse_topology('{oops')
    def test_invalid_utf8(self):
        with self.assertRaises(InventoryError):parse_topology(b'\xff')
    def test_no_devices_rejected_without_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db'
            with self.assertRaises(InventoryError):import_snapshot('{}',path)
            self.assertFalse(path.exists())
    def test_baseline_and_new(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db'
            first=import_snapshot(response([A,B]),path,now='2026-10-31T01:00:00+00:00')
            self.assertTrue(first['baseline']);self.assertEqual(first['new_count'],0)
            second=import_snapshot(response([A,B,C]),path,now='2026-10-31T01:01:00+00:00')
            self.assertFalse(second['baseline']);self.assertEqual(second['new_count'],1)
            self.assertEqual(second['new'][0]['name'],'TV')
            self.assertEqual(len(latest(path)['records']),3)
    def test_nonpresent_not_assumed_offline(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db'
            import_snapshot(response([A,B]),path,now='2026-10-31T01:00:00+00:00')
            import_snapshot(response([A]),path,now='2026-10-31T01:01:00+00:00')
            snap=latest(path)
            self.assertEqual(len(snap['records']),1)
            self.assertIn('CANLI',snap['note'])
    def test_no_raw_json_persisted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db'
            import_snapshot(response([A]),path)
            self.assertNotIn(b'SECRET_NEVER_STORE',path.read_bytes())
    def test_status_text_explicitly_manual(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'inventory.db'
            import_snapshot(response([A]),path)
            self.assertIn('canlı bağlantı değil',describe(latest(path)))
    def test_first_run_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(latest(Path(folder)/'nope.db')['imported_utc'])

if __name__=='__main__':unittest.main()
