import unittest

from data_extraction import extract_service_counts


class ExtractServiceCountsTests(unittest.TestCase):
    def setUp(self):
        self.all_services = {
            "Tehisintellekti otstarbekuse nõustamine",
            "Finantseerimise nõustamine – Erakapitali kaasamine",
            "Finantseerimise nõustamine – Avalikud meetmed",
            "Demoprojekt",
            "Koostööpartnerite leidmine",
            "AI help desk",
            "Usaldusväärne tehisintellekt (TI määruse nõustamine)",
            "Ligipääs tehisintellekti taristule",
        }

    def assert_zero_for_other_services(self, counts, expected_non_zero_keys):
        self.assertEqual(set(counts.keys()), self.all_services)
        expected_non_zero_keys = set(expected_non_zero_keys)
        for service, value in counts.items():
            if service in expected_non_zero_keys:
                continue
            self.assertEqual(value, 0, f"Service '{service}' should be 0")

    def test_et_ai_helpdesk_detected_once(self):
        body = "Tehisintellekti eelnõustamine"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["AI help desk"], 1)
        self.assert_zero_for_other_services(counts, {"AI help desk"})

    def test_et_ai_consultancy_one(self):
        body = "Tehisintellekti otstarbekuse nõustamine"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Tehisintellekti otstarbekuse nõustamine"], 1)
        self.assert_zero_for_other_services(counts, {"Tehisintellekti otstarbekuse nõustamine"})

    def test_et_ai_consultancy_two(self):
        body = "Tehisintellekti otstarbekuse nõustamine AI nõustamine: 2 kordne"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Tehisintellekti otstarbekuse nõustamine"], 2)
        self.assert_zero_for_other_services(counts, {"Tehisintellekti otstarbekuse nõustamine"})

    def test_et_ai_consultancy_capped_at_two(self):
        body = "Tehisintellekti otstarbekuse nõustamine AI nõustamine: 5 kordne"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Tehisintellekti otstarbekuse nõustamine"], 2)
        self.assert_zero_for_other_services(counts, {"Tehisintellekti otstarbekuse nõustamine"})

    def test_et_funding_public_two(self):
        body = "Finantseerimise nõustamine Avalikud meetmed Finantseerimise nõustamine: 2 kordne"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Finantseerimise nõustamine – Avalikud meetmed"], 2)
        self.assert_zero_for_other_services(counts, {"Finantseerimise nõustamine – Avalikud meetmed"})

    def test_et_funding_private_two(self):
        body = "Finantseerimise nõustamine Erakapitali kaasamine Finantseerimise nõustamine: 2 kordne"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Finantseerimise nõustamine – Erakapitali kaasamine"], 2)
        self.assert_zero_for_other_services(counts, {"Finantseerimise nõustamine – Erakapitali kaasamine"})

    def test_et_funding_both_two(self):
        body = (
            "Finantseerimise nõustamine Avalikud meetmed Erakapitali kaasamine "
            "Finantseerimise nõustamine: 2 kordne"
        )
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Finantseerimise nõustamine – Avalikud meetmed"], 2)
        self.assertEqual(counts["Finantseerimise nõustamine – Erakapitali kaasamine"], 2)
        self.assert_zero_for_other_services(
            counts,
            {
                "Finantseerimise nõustamine – Avalikud meetmed",
                "Finantseerimise nõustamine – Erakapitali kaasamine",
            },
        )

    def test_et_demo_project_always_once(self):
        body = "Demoprojekt Demoprojekt Demoprojekt"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Demoprojekt"], 1)
        self.assert_zero_for_other_services(counts, {"Demoprojekt"})

    def test_et_matchmaking_always_once(self):
        body = "Koostööpartnerite leidmine Koostööpartnerite leidmine"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Koostööpartnerite leidmine"], 1)
        self.assert_zero_for_other_services(counts, {"Koostööpartnerite leidmine"})

    def test_et_ai_act_limited_to_one_even_if_two_requested(self):
        body = (
            "Usaldusväärne tehisintellekt (TI määruse nõustamine) "
            "Usaldusväärne tehisintellekt (TI määruse nõustamine): 2 kordne"
        )
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Usaldusväärne tehisintellekt (TI määruse nõustamine)"], 1)
        self.assert_zero_for_other_services(counts, {"Usaldusväärne tehisintellekt (TI määruse nõustamine)"})

    def test_et_eu_access_always_once(self):
        body = "Ligipääs tehisintellekti taristule Ligipääs tehisintellekti taristule"
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["Ligipääs tehisintellekti taristule"], 1)
        self.assert_zero_for_other_services(counts, {"Ligipääs tehisintellekti taristule"})

    def test_en_ai_helpdesk_detected_once(self):
        body = "AI help desk AI help desk"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["AI help desk"], 1)
        self.assert_zero_for_other_services(counts, {"AI help desk"})

    def test_en_ai_suitability_two_word(self):
        body = "AI suitability assessment: two"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Tehisintellekti otstarbekuse nõustamine"], 2)
        self.assert_zero_for_other_services(counts, {"Tehisintellekti otstarbekuse nõustamine"})

    def test_en_funding_both_two(self):
        body = "Support to find funding: 2 public measures private capital"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Finantseerimise nõustamine – Avalikud meetmed"], 2)
        self.assertEqual(counts["Finantseerimise nõustamine – Erakapitali kaasamine"], 2)
        self.assert_zero_for_other_services(
            counts,
            {
                "Finantseerimise nõustamine – Avalikud meetmed",
                "Finantseerimise nõustamine – Erakapitali kaasamine",
            },
        )

    def test_en_demo_project_always_once(self):
        body = "Demonstration project Demonstration project"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Demoprojekt"], 1)
        self.assert_zero_for_other_services(counts, {"Demoprojekt"})

    def test_en_matchmaking_always_once(self):
        body = "Matchmaking Matchmaking international partnerships"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Koostööpartnerite leidmine"], 1)
        self.assert_zero_for_other_services(counts, {"Koostööpartnerite leidmine"})

    def test_en_ai_act_limited_to_one_even_if_two_requested(self):
        body = "AI Act awareness and responsible AI: two"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Usaldusväärne tehisintellekt (TI määruse nõustamine)"], 1)
        self.assert_zero_for_other_services(counts, {"Usaldusväärne tehisintellekt (TI määruse nõustamine)"})

    def test_en_eu_access_always_once(self):
        body = "Access to EU AI infrastructure Access to EU AI infrastructure"
        counts = extract_service_counts(body, "en")

        self.assertEqual(counts["Ligipääs tehisintellekti taristule"], 1)
        self.assert_zero_for_other_services(counts, {"Ligipääs tehisintellekti taristule"})

    def test_unknown_language_returns_all_zero(self):
        body = (
            "Tehisintellekti otstarbekuse nõustamine Demoprojekt "
            "AI suitability assessment: 2 Access to EU AI infrastructure"
        )
        counts = extract_service_counts(body, "ru")

        self.assert_zero_for_other_services(counts, set())

    def test_combined_et_scenario_for_limits(self):
        body = (
            "Tehisintellekti eelnõustamine "
            "Tehisintellekti otstarbekuse nõustamine AI nõustamine: 2 kordne "
            "Finantseerimise nõustamine Avalikud meetmed Erakapitali kaasamine Finantseerimise nõustamine: 2 kordne "
            "Demoprojekt Demoprojekt "
            "Koostööpartnerite leidmine Koostööpartnerite leidmine "
            "Usaldusväärne tehisintellekt (TI määruse nõustamine) "
            "Usaldusväärne tehisintellekt (TI määruse nõustamine): 2 kordne "
            "Ligipääs tehisintellekti taristule Ligipääs tehisintellekti taristule"
        )
        counts = extract_service_counts(body, "et")

        self.assertEqual(counts["AI help desk"], 1)
        self.assertEqual(counts["Tehisintellekti otstarbekuse nõustamine"], 2)
        self.assertEqual(counts["Finantseerimise nõustamine – Avalikud meetmed"], 2)
        self.assertEqual(counts["Finantseerimise nõustamine – Erakapitali kaasamine"], 2)
        self.assertEqual(counts["Demoprojekt"], 1)
        self.assertEqual(counts["Koostööpartnerite leidmine"], 1)
        self.assertEqual(counts["Usaldusväärne tehisintellekt (TI määruse nõustamine)"], 1)
        self.assertEqual(counts["Ligipääs tehisintellekti taristule"], 1)


if __name__ == "__main__":
    unittest.main()
