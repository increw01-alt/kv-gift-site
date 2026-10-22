import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from board_archive import build_archive
from board_status import write_status


class ArchiveTests(unittest.TestCase):
    def put(self, root, path, data):
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(data),encoding='utf-8')

    def test_failed_costs_and_kst_charge_dates_remain_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.put(root,'data/editorial_runs/2026-10-20/1.json',{
                'run_id':'1','date_kst':'2026-10-20','status':'error','secret':'never-publish',
                'api_usage':{'estimated_total_usd':None,'known_subtotal_usd':.1,'records':[
                    {'kind':'text','estimated_usd':.1,'recorded_at_utc':'2026-10-20T15:01:00Z',
                     'usage':{'input_tokens':20,'output_tokens':10},'private_prompt':'never-publish'}]}})
            result=build_archive(root)
            self.assertEqual(result['records'][0]['dateKst'],'2026-10-20')
            self.assertEqual(result['charges'][0]['dateKst'],'2026-10-21')
            self.assertEqual(sum(row['knownSubtotalUsd'] for row in result['charges']),.1)
            self.assertIsNone(result['charges'][-1]['estimatedUsd'])
            self.assertNotIn('never-publish',json.dumps(result))

    def test_approved_published_posts_are_included_once_and_drafts_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.put(root,'data/editorial_history.json',[
                {'board':'gc_tip','id':1,'topic':'approved','drafted_at':'2026-10-19'},
                {'board':'gc_tip','id':2,'topic':'draft only','drafted_at':'2026-10-19'},
                {'board':'gc_tip','id':3,'topic':'automatic','drafted_at':'2026-10-20'}])
            self.put(root,'board/gc_tip/1.html',{})
            self.put(root,'board/gc_tip/3.html',{})
            self.put(root,'data/editorial_runs/2026-10-20/3.json',{'run_id':'3','status':'published',
                'url':'https://kv-gift.co.kr/board/gc_tip/3','api_usage':{'estimated_total_usd':.2}})
            result=build_archive(root)
            self.assertEqual(len(result['records']),2)
            self.assertEqual(result['coverageStart'],'2026-10-19')
            self.assertIsNone(result['records'][-1]['estimatedUsd'])
            self.assertEqual(sum(row['knownSubtotalUsd'] for row in result['charges']),.2)
            write_status(root,dt.date(2026,10,20))
            self.assertTrue((root/'data/editorial_archive.json').exists())
