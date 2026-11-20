"""MCP keeps short discovery replies and an explicit path to the complete compatibility response."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from optics_photonics import environments, mcp


class DetailsCompatibilityCase(unittest.TestCase):
    def setUp(self):
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        environment = patch.dict(os.environ, {'OPTICS_HOME': home.name})
        environment.start()
        self.addCleanup(environment.stop)

    def details(self, **arguments):
        reply = mcp.tool_result({'name': 'software_details', 'arguments': {'tool': 'scipy', **arguments}})
        self.assertFalse(reply['isError'], reply)
        return reply['structuredContent']

    def test_full_mcp_response_matches_the_existing_python_details_api(self):
        brief = self.details()
        self.assertEqual(brief, self.details(brief=True))
        self.assertIsInstance(brief['execution']['programs'][0]['inputs'], list)
        full = self.details(brief=False)
        self.assertEqual(full, environments.details('scipy'))
        self.assertEqual(full, self.details(brief='false'))  # Some MCP hosts encode every argument as text.
        self.assertIsInstance(full['execution']['programs'][0]['inputs'], dict)
        self.assertIn('inputs_example', full['execution']['operations'][0])
        self.assertIn('mcp', full)
        self.assertIn('skill', full)

    def test_full_details_do_not_change_the_explicit_source_contract(self):
        selected = self.details(program='nlse', brief=False)
        self.assertNotIn('source', selected)
        self.assertIsInstance(selected['inputs'], dict)
        source = self.details(program='nlse', brief=False, source=True)
        self.assertEqual(source, environments.details('scipy', program='nlse'))
        self.assertIn('PROGRAM =', source['source'])

    def test_brief_is_a_discoverable_boolean_argument(self):
        schema = next(item['inputSchema'] for item in mcp.listed() if item['name'] == 'software_details')
        self.assertEqual(schema['properties']['brief'], {'type': 'boolean', 'default': True})
        reply = mcp.tool_result({'name': 'software_details', 'arguments': {'tool': 'scipy', 'brief': 'unknown'}})
        self.assertTrue(reply['isError'])
        self.assertIn('brief', reply['content'][0]['text'])


if __name__ == '__main__':
    unittest.main()
