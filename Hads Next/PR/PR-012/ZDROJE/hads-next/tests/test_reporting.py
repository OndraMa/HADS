from pathlib import Path
import tempfile
import unittest

from hads_next.reporting import export_center, render_command_center


class ReportingTests(unittest.TestCase):
    def test_czech_functional_overview_and_escaped_details(self):
        case = {'incident': {'id': 'one', 'status': 'open', 'symptom': '<script>alert(1)</script>'},
                'occurrences': [{}, {}], 'analyses': [{'status': 'failed'}],
                'evidence': [{'password': 'TOPSECRET'}]}
        result = render_command_center([case], [{'reason': 'Oprava', 'target': {'automation_id': 'test'}}])
        for title in ('Co nefunguje', 'Co HADS vyšetřuje', 'Co ode mě potřebuje', 'Co se podařilo vyřešit', 'Co se opakuje'):
            self.assertIn(title, result)
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertNotIn('TOPSECRET', result)
        self.assertIn('<details>', result)
        self.assertIn('AI vyšetření se nedokončilo', result)
        self.assertIn('Tento statický přehled schválení nevydává', result)
        self.assertNotIn('<button', result)
        self.assertNotIn('<form', result)

    def test_latest_functional_result_controls_resolved_section(self):
        case = {'incident': {'id': 'one', 'status': 'open', 'symptom': 'Rádio nehraje'}}
        reports = [
            {'incident_id': 'one', 'created_at': 1, 'classification': 'Vyřešeno a ověřeno', 'summary': 'Success'},
            {'incident_id': 'one', 'created_at': 2, 'classification': 'Problém se opakoval', 'summary': 'Again'},
        ]
        result = render_command_center([case], reports=reports)
        solved = result.split('<h2>Co se podařilo vyřešit</h2>')[1].split('</section>')[0]
        self.assertNotIn('Success', solved)
        self.assertIn('Žádné položky', solved)
        self.assertIn('Počet zaznamenaných výskytů', result)
        reports.pop()
        result = render_command_center([case], reports=reports)
        broken = result.split('<h2>Co nefunguje</h2>')[1].split('</section>')[0]
        self.assertNotIn('Rádio nehraje', broken)
        self.assertIn('Success', result)

    def test_export_is_standalone_utf8(self):
        with tempfile.TemporaryDirectory() as directory:
            path = export_center(Path(directory) / 'center.html', [])
            self.assertTrue(path.exists())
            self.assertIn('lang="cs"', path.read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):
            render_command_center([{}] * 1001)


if __name__ == '__main__':
    unittest.main()
