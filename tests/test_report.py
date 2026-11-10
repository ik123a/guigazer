"""Offline report rendering regressions; no detector, browser or model needed."""
import unittest
from audit.report import generate_html_report


class ReportEscapingTests(unittest.TestCase):
    def test_page_text_is_rendered_as_text(self):
        hostile = '<img src=x onerror="alert(1)">'
        result = generate_html_report({
            'summary': {'overall_score': 75, 'total_elements': 1,
                        'contrast_issues': 0, 'touch_target_issues': 0, 'label_issues': 0},
            'details': {
                'contrast': [{'element_id': 1, 'class_name': hostile,
                              'contrast_ratio': 5, 'passes_aa': True, 'passes_aaa': False}],
                'touch_targets': [{'element_id': 1, 'class_name': hostile,
                                   'width': 50, 'height': 50, 'passes': True}],
                'labels': [{'element_id': 1, 'has_label': True, 'label_text': hostile}],
            },
        })
        self.assertNotIn(hostile, result)
        self.assertEqual(result.count('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'), 3)
        self.assertIn('75/100', result)


if __name__ == '__main__':
    unittest.main()
