"""Instrument-program records and cleanup, using a message transport without hardware."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import data, programs  # noqa: E402


class Device:
    def __init__(self, replies, write_errors=None, close_error=None, before_query=None, fail_setting=None):
        self.replies = iter(replies)
        self.write_errors = write_errors or {}
        self.close_error = close_error
        self.before_query = before_query
        self.fail_setting = fail_setting
        self.writes, self.queries = [], []
        self.closed = False

    def __setattr__(self, name, value):
        if name == getattr(self, 'fail_setting', None):
            raise RuntimeError('cannot set ' + name)
        super().__setattr__(name, value)

    def write(self, command):
        self.writes.append(command)
        if command in self.write_errors:
            raise self.write_errors[command]

    def query(self, command):
        if self.before_query:
            self.before_query(len(self.queries))
        self.queries.append(command)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


class Manager:
    address = 'USB0::test-source::INSTR'

    def __init__(self, device, list_error=None, open_error=None, close_error=None):
        self.device = device
        self.list_error, self.open_error, self.close_error = list_error, open_error, close_error
        self.opened, self.closed = [], False

    def list_resources(self):
        if self.list_error:
            raise self.list_error
        return (self.address,)

    def open_resource(self, address):
        self.opened.append(address)
        if self.open_error:
            raise self.open_error
        return self.device

    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Saving instrument arrays requires NumPy')
class InstrumentRecordsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def run_sweep(self, device, *, manager_errors=None, **inputs):
        self.manager = Manager(device, **(manager_errors or {}))
        module = types.SimpleNamespace(ResourceManager=lambda *args: self.manager)
        previous = sys.modules.get('pyvisa')
        sys.modules['pyvisa'] = module
        try:
            return programs.run('pyvisa', 'sweep', {
                'resource': self.manager.address, 'identify': '', 'values': [1, 2], **inputs,
            }, self.output)
        finally:
            if previous is None:
                sys.modules.pop('pyvisa', None)
            else:
                sys.modules['pyvisa'] = previous

    def raw(self):
        return [json.loads(line) for line in (self.output / 'sweep.raw.jsonl').read_text().splitlines()]

    def test_raw_reply_is_saved_before_next_read_and_keeps_all_columns(self):
        def before_query(index):
            if index == 1:
                self.assertEqual(self.raw()[0]['reply'], '1,10\r\n')

        device = Device(['1,10\r\n', '2,20\n'], before_query=before_query)
        result = self.run_sweep(device)
        self.assertEqual(data.load(self.output / 'sweep')['reading'].values.tolist(), [[1, 10], [2, 20]])
        self.assertIn('sweep.raw.jsonl', result['files'])
        records = self.raw()
        self.assertEqual([row['setting'] for row in records], [1, 2])
        self.assertEqual(records[0]['command'], ':WAV 1.000')
        self.assertEqual(records[0]['query'], ':WAV?')
        self.assertGreater(records[0]['unix_time_s'], 0)
        self.assertLessEqual(records[0]['time_s'], records[1]['time_s'])
        self.assertTrue(device.closed and self.manager.closed)

    def test_ragged_replies_fail_without_discarding_numbers(self):
        device = Device(['1,10', '2'])
        with self.assertRaisesRegex(ValueError, 'holds 1 numbers; expected 2'):
            self.run_sweep(device, finish=['OUTP OFF'])
        self.assertEqual([row['reply'] for row in self.raw()], ['1,10', '2'])
        self.assertFalse((self.output / 'sweep.npz').exists())
        self.assertEqual(device.writes[-1], 'OUTP OFF')

    def test_a_bad_reply_is_recorded_before_parsing_and_prior_readings_survive(self):
        device = Device(['1\n', 'ERROR\r\n'])
        with self.assertRaisesRegex(ValueError, 'holds no number'):
            self.run_sweep(device)
        self.assertEqual([row['reply'] for row in self.raw()], ['1\n', 'ERROR\r\n'])
        self.assertTrue(device.closed and self.manager.closed)

    def test_a_transport_failure_keeps_the_completed_reading(self):
        device = Device(['1', TimeoutError('read timed out')])
        with self.assertRaisesRegex(TimeoutError, 'read timed out'):
            self.run_sweep(device, finish=['OUTP OFF'])
        self.assertEqual([row['reply'] for row in self.raw()], ['1'])
        self.assertEqual(device.writes[-1], 'OUTP OFF')

    def test_cleanup_attempts_every_command_and_preserves_the_acquisition_error(self):
        device = Device(['ERROR'], write_errors={'RESET': RuntimeError('reset failed')},
                        close_error=RuntimeError('close failed'))
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors), self.assertRaisesRegex(ValueError, 'holds no number'):
            self.run_sweep(device, values=[1], finish=['RESET', 'OUTP OFF'])
        self.assertEqual(device.writes[-2:], ['RESET', 'OUTP OFF'])
        self.assertTrue(device.closed and self.manager.closed)
        cleanup = json.loads((self.output / 'sweep.cleanup.json').read_text())
        self.assertEqual(cleanup[0]['command'], 'RESET')
        self.assertEqual(cleanup[1]['operation'], 'instrument.close')
        self.assertIn('reset failed', errors.getvalue())
        self.assertEqual(self.raw()[0]['reply'], 'ERROR')

    def test_cleanup_failure_is_reported_after_a_successful_read(self):
        device = Device(['1'], write_errors={'RESET': RuntimeError('reset failed')})
        with self.assertRaisesRegex(RuntimeError, 'Instrument cleanup failed: .*reset failed'):
            self.run_sweep(device, values=[1], finish=['RESET', 'OUTP OFF'])
        self.assertEqual(device.writes[-2:], ['RESET', 'OUTP OFF'])
        self.assertEqual(self.raw()[0]['reply'], '1')
        self.assertTrue((self.output / 'sweep.cleanup.json').is_file())

    def test_discovery_with_identification_disabled_does_not_open_devices(self):
        device = Device([])
        result = self.run_sweep(device, resource='?', identify='')
        self.assertEqual(result['resources'], [{'resource': self.manager.address}])
        self.assertEqual(self.manager.opened, [])
        self.assertEqual(device.queries, [])
        self.assertTrue(self.manager.closed)

    def test_a_failed_listing_closes_the_manager_and_keeps_the_listing_error(self):
        errors = {'list_error': RuntimeError('listing failed'), 'close_error': RuntimeError('manager close failed')}
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaisesRegex(RuntimeError, '^listing failed$'):
            self.run_sweep(Device([]), resource='?', manager_errors=errors)
        self.assertTrue(self.manager.closed)
        cleanup = json.loads((self.output / 'sweep.cleanup.json').read_text())
        self.assertEqual(cleanup[0]['operation'], 'manager.close')

    def test_a_failed_open_closes_the_manager_without_sending_finish(self):
        device = Device([])
        with self.assertRaisesRegex(RuntimeError, '^opening failed$'):
            self.run_sweep(device, manager_errors={'open_error': RuntimeError('opening failed')}, finish=['OUTP OFF'])
        self.assertTrue(self.manager.closed)
        self.assertEqual(device.writes, [])

    def test_configuration_failures_close_the_session_without_sending_finish(self):
        for setting in ('timeout', 'read_termination', 'write_termination'):
            with self.subTest(setting=setting):
                device = Device([], fail_setting=setting)
                with self.assertRaisesRegex(RuntimeError, 'cannot set ' + setting):
                    self.run_sweep(device, finish=['OUTP OFF'])
                self.assertTrue(device.closed and self.manager.closed)
                self.assertEqual(device.writes, [])

    def test_invalid_inputs_release_the_manager_before_opening_an_instrument(self):
        for inputs in ({'values': []}, {'settle_s': -1}):
            with self.subTest(inputs=inputs):
                device = Device([])
                with self.assertRaises(ValueError):
                    self.run_sweep(device, **inputs)
                self.assertTrue(self.manager.closed)
                self.assertEqual(self.manager.opened, [])

    def test_identification_is_retained_with_the_measurement(self):
        device = Device(['Test instrument\n', '1'])
        result = self.run_sweep(device, identify='*IDN?', values=[1])
        self.assertEqual(result['identification'], 'Test instrument')
        self.assertEqual(device.queries, ['*IDN?', ':WAV?'])

    def test_elapsed_times_are_monotonic_when_the_wall_clock_moves_backwards(self):
        with patch('time.monotonic', side_effect=[10.0, 10.1, 10.3]), patch('time.time', side_effect=[1000.0, 900.0]):
            result = self.run_sweep(Device(['1', '2']))
        records = self.raw()
        self.assertEqual([row['unix_time_s'] for row in records], [1000, 900])
        self.assertAlmostEqual(records[0]['time_s'], 0.1)
        self.assertAlmostEqual(records[1]['time_s'], 0.3)
        self.assertAlmostEqual(result['elapsed_s'], 0.3)


if __name__ == '__main__':
    unittest.main()
