"""Recover research across conversations and pages while new work arrives."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import jobs, mcp


class RunDiscoveryCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.add('a', 'Ring spectrum', 'scipy', 'succeeded', 10, 'ring-request')
        self.add('b', 'Thin film 50%_sample', 'tmm', 'failed', 10, 'film-request')
        self.add('c', '腔模计算', 'scipy', 'succeeded', 10, 'cavity-request')
        self.add('d', 'Fibre dispersion', 'modes', 'succeeded', 11, 'fibre-request')

    def tearDown(self):
        self.temp.cleanup()

    def add(self, run, name, tool, state, created, request):
        with jobs.database(self.home) as db:
            db.execute('INSERT INTO runs(id,name,state,created,finished) VALUES(?,?,?,?,?)',
                       (run, name, state, created, created + 1))
            db.execute('INSERT INTO requests VALUES(?,?,?)', (request, '{}', run))
            db.execute('INSERT INTO steps(run_id,id,specification,environment,state,result) VALUES(?,?,?,?,?,?)',
                       (run, 'solve', json.dumps({'id': 'solve', 'tool': tool, 'source': 'large program' * 1000}),
                        '{}', state, json.dumps({'large_array': list(range(1000))})))

    def found(self, **options):
        return jobs.list_runs(path=self.home, **options)

    def test_find_by_name_request_software_and_state_without_loading_results(self):
        for query, expected in (('ring', ['a']), ('cavity-request', ['c']), ('scipy', ['c', 'a']),
                                ('腔模', ['c']), ('50%_', ['b'])):
            self.assertEqual([r['id'] for r in self.found(search=query)['runs']], expected)
        rows = self.found(tool='scipy', state='succeeded')['runs']
        self.assertEqual([r['id'] for r in rows], ['c', 'a'])
        self.assertEqual(rows[0]['tools'], ['scipy'])
        self.assertEqual(rows[0]['counts'], {'succeeded': 1})
        self.assertNotIn('source', json.dumps(rows))
        self.assertNotIn('large_array', json.dumps(rows))
        self.assertEqual(self.found(search='not present')['runs'], [])

    def test_cursor_remains_stable_with_equal_timestamps_and_new_submissions(self):
        first = self.found(limit=2)
        self.assertEqual([r['id'] for r in first['runs']], ['d', 'c'])
        self.assertEqual(first['next_before'], 'c')
        self.add('new', 'A newer experiment', 'scipy', 'succeeded', 12, 'new-request')
        second = self.found(limit=2, before=first['next_before'])
        self.assertEqual([r['id'] for r in second['runs']], ['b', 'a'])
        self.assertIsNone(second['next_before'])
        self.assertIsNone(second['next_offset'])
        self.assertEqual([r['id'] for r in self.found(limit=2, offset=3)['runs']], ['b', 'a'])

    def test_schema_upgrade_preserves_existing_work(self):
        with jobs.database(self.home) as db:
            db.execute('DROP INDEX runs_created_id')
            db.execute('DROP INDEX requests_run')
            db.execute('DROP INDEX steps_tool_run')
            db.execute('PRAGMA user_version=3')
        self.assertEqual(len(self.found()['runs']), 4)
        with jobs.database(self.home) as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 4)
            self.assertIn('runs_created_id', {r[1] for r in db.execute("PRAGMA index_list('runs')")})

    def test_invalid_filters_are_explained(self):
        for options in ({'state': 'complete'}, {'limit': True}, {'offset': .5}, {'search': []},
                        {'before': 'missing'}, {'before': 'b', 'offset': 1}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.found(**options)

    def test_mcp_filters_reach_the_same_saved_work(self):
        with patch.dict('os.environ', {'OPTICS_HOME': str(self.home)}):
            result = mcp.invoke('list_runs', {'search': 'film', 'tool': 'tmm', 'state': 'failed'})
        self.assertEqual(result['runs'][0]['id'], 'b')


if __name__ == '__main__':
    unittest.main()
