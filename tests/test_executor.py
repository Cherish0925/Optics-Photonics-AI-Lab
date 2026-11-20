import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from optics_photonics import execution, processes
from optics_photonics.signals import Cancellation


class ExecutorCase(unittest.TestCase):
    def test_invalid_deadlines_do_not_start_or_truncate_output(self):
        binary = processes.native_binary()
        if binary is None:
            self.skipTest('Native executor is built by the native distribution job')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, errors, started = root/'stdout', root/'stderr', root/'started'
            output.write_text('previous output')
            for timeout in (-1, True, '3', 1e300):
                with self.subTest(timeout=timeout):
                    request = {'id': 'invalid-timeout', 'params': {
                        'command': [sys.executable, '-c', 'from pathlib import Path;Path("started").touch()'],
                        'cwd': str(root), 'stdout': str(output), 'stderr': str(errors), 'timeout': timeout}}
                    result = subprocess.run([str(binary)], input=json.dumps(request)+'\n',
                        capture_output=True, text=True, timeout=5, check=True)
                    reply = json.loads(result.stdout)
                    self.assertEqual(reply['id'], request['id'])
                    self.assertIn('timeout', reply['error'])
                    self.assertFalse(started.exists())
                    self.assertEqual(output.read_text(), 'previous output')
                    self.assertFalse(errors.exists())

    def test_executor_owns_descendants_after_parent_exits(self):
        binary=processes.native_binary()
        if binary is None:
            self.skipTest('Native executor is built by the native distribution job')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);child=root/'child';parent=root/'parent.py'
            parent.write_text('import subprocess,sys,time\nfrom pathlib import Path\np=Path(sys.argv[1])\nsubprocess.Popen([sys.executable,"-c","import time;from pathlib import Path;p=Path("+repr(str(p))+");[(p.write_text(str(i)),time.sleep(.02)) for i in range(1000)]"])\nwhile not p.exists():time.sleep(.01)\n')
            config={'kind':'command','command':[sys.executable,str(parent),str(child)],'threads':1}
            execution.run('arbitrary',{},output=root/'out',configuration=config)
            content=child.read_bytes();time.sleep(.15)
            self.assertEqual(child.read_bytes(),content)

    def test_cancellation_before_start_does_not_run_a_program(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); token=Cancellation();token.set()
            config={'kind':'command','command':[sys.executable,'-c','import time;time.sleep(20)'],'threads':1}
            with self.assertRaises(execution.Cancelled):
                execution.run('arbitrary',{},output=root/'out',configuration=config,cancel=token)
