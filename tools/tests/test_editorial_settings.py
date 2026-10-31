import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editorial_settings import DEFAULT, KST, load_settings, target_at, validate
from update_editorial_settings import apply_update
from test_board_drafts import fixture
import run_board_publish as publish

REQUEST='12345678-1234-4234-8234-123456789012'


class SettingsTests(unittest.TestCase):
    def test_custom_schedule_pause_and_midnight_boundaries(self):
        config={**DEFAULT,'dailyTarget':3,'startTime':'10:30','endTime':'12:00'}
        for time,expected in [('10:29',0),('10:30',1),('11:14',1),('11:15',2),('12:00',3),('22:59',3),('23:00',3),('23:59',3)]:
            with self.subTest(time=time):
                at=dt.datetime.fromisoformat(f'2026-10-21T{time}:00+09:00')
                self.assertEqual(target_at(at,config),expected)
                self.assertEqual(target_at(at,{**config,'enabled':False}),0)
        self.assertEqual(target_at(dt.datetime(2026,10,22,9,tzinfo=KST),config),0)

    def test_invalid_limits_types_and_short_windows_are_rejected(self):
        for patch_value in [{'dailyTarget':11},{'dailyTarget':0},{'dailyTarget':True},{'dailyTarget':1.5},{'enabled':'false'},
                            {'startTime':'24:00'},{'endTime':'23:56'},{'startTime':'23:54','endTime':'23:55'},
                            {'startTime':'09:17','endTime':'09:20'},{'startTime':'9:17'}]:
            with self.subTest(value=patch_value),self.assertRaises(ValueError):validate({**DEFAULT,**patch_value})

    def test_ten_even_slots_cover_the_day_and_reset_at_korean_midnight(self):
        slots=['00:17','02:41','05:05','07:29','09:53','12:17','14:41','17:05','19:29','21:53']
        for index,time in enumerate(slots,1):
            instant=dt.datetime.fromisoformat(f'2026-11-01T{time}:00+09:00')
            self.assertEqual(target_at(instant,DEFAULT),index)
            self.assertEqual(target_at(instant-dt.timedelta(seconds=1),DEFAULT),index-1)
            self.assertEqual(target_at(instant.astimezone(dt.timezone.utc),DEFAULT),index)
        self.assertEqual(target_at(dt.datetime.fromisoformat('2026-11-01T23:59:59+09:00'),DEFAULT),10)
        self.assertEqual(target_at(dt.datetime.fromisoformat('2026-11-02T00:00:00+09:00'),DEFAULT),0)

    def test_existing_revision_remains_readable_and_keeps_its_legacy_cutoff(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            config={**DEFAULT,'startTime':'09:17','endTime':'18:17','catchUpUntil':'23:00'}
            publish.write_json(root/'data/editorial_settings.json',config)
            self.assertEqual(load_settings(root),config)
            self.assertEqual(target_at(dt.datetime.fromisoformat('2026-11-01T23:00:00+09:00'),config),0)

    def test_save_updates_only_policy_and_status_and_rejects_stale_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root)
            before=(root/'data/editorial_history.json').read_bytes()
            payload={'enabled':True,'dailyTarget':3,'startTime':'10:30','endTime':'12:00','requestId':REQUEST,'expectedRevision':'initial'}
            self.assertTrue(apply_update(root,payload,dt.datetime(2026,10,21,10,tzinfo=KST)))
            self.assertEqual(load_settings(root)['dailyTarget'],3)
            saved = root / 'data/editorial_settings_versions' / f'{REQUEST}.json'
            self.assertEqual(json.loads(saved.read_text()), load_settings(root))
            original = saved.read_bytes()
            self.assertEqual(json.loads((root/'data/editorial_status.json').read_text())['dailyTarget'],3)
            self.assertEqual((root/'data/editorial_history.json').read_bytes(),before)
            self.assertFalse(apply_update(root,payload))
            self.assertEqual(saved.read_bytes(), original)
            with self.assertRaises(ValueError):apply_update(root,{**payload,'requestId':'22345678-1234-4234-8234-123456789012'})
            with self.assertRaises(ValueError):apply_update(root,{**payload,'dailyTarget':4})
            with self.assertRaises(ValueError):apply_update(root,{**payload,'attemptLimit':100})

    def test_paused_and_lower_targets_stop_before_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);fixture(root);day=dt.date(2026,10,21)
            publish.write_json(root/'data/editorial_settings.json',{**DEFAULT,'enabled':False})
            self.assertIn('꺼져',publish.guard(root,day,'99','1'))
            publish.write_json(root/'data/editorial_settings.json',{**DEFAULT,'dailyTarget':1})
            publish.write_json(root/f'data/editorial_runs/{day}/1.json',{'status':'published'})
            self.assertIn('목표 1편',publish.guard(root,day,'99','1'))
            (root/'data/editorial_settings.json').unlink()
            with self.assertRaises(FileNotFoundError):load_settings(root,required=True)
