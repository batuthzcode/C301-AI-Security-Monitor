"""Offline, network-free tests; does not capture real traffic."""
import io
import unittest
from unittest import mock
import tempfile
from pathlib import Path
import ti_network_guard as ng


def row(time,src,dst,sport='',dport='',domain='',syn='',ack=''):
    data={k:'' for k in ng.FIELDS}
    data.update({'frame.time_epoch':str(time),'ip.src':src,'ip.dst':dst,
        'tcp.srcport':str(sport),'tcp.dstport':str(dport),
        'dns.qry.name':domain,'tcp.flags.syn':syn,'tcp.flags.ack':ack})
    return '\t'.join(data[k] for k in ng.FIELDS)


class NetworkGuardTests(unittest.TestCase):
    def test_parse_names(self):
        txt='\t'.join(ng.FIELDS)+'\n'+row(1700000000,'192.168.1.4','8.8.8.8',52144,53,'example.org')
        result=ng.parse_tshark_tsv(txt)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['domain'],'example.org')

    def test_reject_invalid_packet(self):
        self.assertEqual(ng.parse_tshark_tsv(row(1700,'not an ip','8.8.8.8')),[])
        self.assertEqual(ng.parse_tshark_tsv(row('invalid','192.168.1.1','8.8.8.8')),[])

    def test_reject_url_paths(self):
        d=ng.parse_tshark_tsv(row(1700000000,'192.168.1.4','8.8.8.8',domain='example.com/private/path'))
        self.assertEqual(d[0]['domain'],'')

    def test_suspicious_multiport(self):
        data='\n'.join(row(1700000000+n,'8.8.8.8','192.168.1.4',44000,1000+n,syn='1',ack='0') for n in range(12))
        analysis=ng.classify(ng.parse_tshark_tsv(data),['192.168.1.4'])
        self.assertEqual(len(analysis['alerts']),1)
        self.assertIn('doğrulanmadı',analysis['conclusion'])

    def test_no_false_positive_single_port(self):
        data='\n'.join(row(1700000000+n,'8.8.8.8','192.168.1.4',44000,443,syn='1',ack='0') for n in range(40))
        self.assertEqual(ng.classify(ng.parse_tshark_tsv(data),['192.168.1.4'])['alerts'],[])

    def test_no_false_positive_outbound(self):
        data='\n'.join(row(1700000000+n,'192.168.1.4','8.8.8.8',44000,1000+n,syn='1',ack='0') for n in range(24))
        self.assertEqual(ng.classify(ng.parse_tshark_tsv(data),['192.168.1.4'])['alerts'],[])

    def test_capture_needs_whitelisted_interface(self):
        with mock.patch.object(ng,'interfaces',return_value=[{'id':'1','name':'Local'}]):
            with self.assertRaises(ng.GuardError):ng.capture(';del C:*',binary='fake')

    def test_capture_does_not_collect_raw_payload(self):
        fake=mock.Mock(returncode=0,stdout=row(1700000000,'192.168.1.4','8.8.8.8',5300,443,'example.com'),stderr='')
        with mock.patch.object(ng,'interfaces',return_value=[{'id':'1','name':'Ethernet'}]),mock.patch.object(ng,'_cmd',return_value=fake) as cmd:
            result=ng.capture('1',12,'faketshark',local_ips=['192.168.1.4'])
        args=cmd.call_args.args[0]
        self.assertIn('-p',args)
        self.assertNotIn('-w',args)
        self.assertNotIn('-x',args)
        self.assertIn('duration:12',args)
        self.assertFalse(result['capture']['raw_packets_saved'])

    def test_interface_bounds(self):
        with mock.patch.object(ng,'interfaces',return_value=[{'id':'1','name':'Ethernet'}]),mock.patch.object(ng,'_cmd',return_value=mock.Mock(returncode=0,stdout='',stderr='')) as cmd:
            res=ng.capture('1',999,'fake')
        self.assertIn('duration:25',cmd.call_args.args[0])
        self.assertEqual(res['packet_count'],0)

    def test_export_explicit_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=ng.export_json(Path(d)/'report.json',{'a':'Türkçe'})
            self.assertIn('Türkçe',p.read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):ng.export_json(Path(d)/'report.pcap',{})

    def test_no_tshark_error_message(self):
        with mock.patch.object(ng,'tshark_path',return_value=None):
            with self.assertRaises(ng.GuardError):ng.interfaces()

    def test_find_windows_tshark(self):
        with mock.patch.object(ng.shutil,'which',return_value=None),mock.patch.dict(ng.os.environ,{'ProgramFiles':'C:/Program Files'}),mock.patch.object(Path,'is_file',return_value=True):
            self.assertTrue(ng.tshark_path().endswith('tshark.exe'))

if __name__=='__main__':unittest.main()
