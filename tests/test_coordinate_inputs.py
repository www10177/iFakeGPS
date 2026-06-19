import unittest

from src.ui.coordinate_inputs import (
    parse_coordinate_pair,
    parse_optional_coordinate_pair,
)


class CoordinateInputTests(unittest.TestCase):
    def test_parse_coordinate_pair_accepts_trimmed_decimal_values(self):
        self.assertEqual(parse_coordinate_pair(" 25.0277 ", " 121.4623 "), (25.0277, 121.4623))

    def test_parse_coordinate_pair_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            parse_coordinate_pair("91", "121.4623")

        with self.assertRaises(ValueError):
            parse_coordinate_pair("25.0277", "181")

    def test_parse_coordinate_pair_rejects_blank_values(self):
        with self.assertRaises(ValueError):
            parse_coordinate_pair("", "121.4623")

    def test_parse_optional_coordinate_pair_waits_for_both_values(self):
        self.assertIsNone(parse_optional_coordinate_pair("", "121.4623"))
        self.assertIsNone(parse_optional_coordinate_pair("25.0277", ""))

    def test_parse_optional_coordinate_pair_accepts_complete_values(self):
        self.assertEqual(
            parse_optional_coordinate_pair("25.0277", "121.4623"),
            (25.0277, 121.4623),
        )


if __name__ == "__main__":
    unittest.main()
