from __future__ import annotations

import unittest

from engine import analyze_prd_text


class ComplianceEngineTest(unittest.TestCase):
    def test_flags_child_health_biometric_product(self) -> None:
        text = (
            "Users ages 10 to 17 can create social profiles, upload avatar photos, "
            "send direct messages, and receive algorithmic feed recommendations. "
            "The app collects email address, device id, geolocation, health symptoms, "
            "and face scan liveness checks. Doctors can review patient data through "
            "a provider portal and the company may sign BAAs."
        )

        report = analyze_prd_text(text, source="sample")
        flagged = {finding.rule_id: finding for finding in report.flagged_findings()}

        self.assertEqual(flagged["coppa"].status, "review_recommended")
        self.assertEqual(flagged["hipaa"].status, "review_recommended")
        self.assertEqual(flagged["biometric_privacy"].status, "review_recommended")
        self.assertNotIn("address", report.profile.data_collected)
        self.assertIn("email", report.profile.data_collected)

    def test_health_without_healthcare_context_needs_more_hipaa_info(self) -> None:
        text = (
            "A wellness app for adults tracks symptoms, medication reminders, sleep, "
            "and mood. Users enter an email address during signup."
        )

        report = analyze_prd_text(text)
        flagged = {finding.rule_id: finding for finding in report.flagged_findings()}

        self.assertEqual(flagged["hipaa"].status, "needs_more_info")
        self.assertEqual(flagged["ftc_health_privacy"].status, "review_recommended")


if __name__ == "__main__":
    unittest.main()
