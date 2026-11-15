import unittest

from app import (
    ERR_EMPTY,
    ERR_NOT_OBJECT,
    ERR_NOT_STRING,
    ERR_NULL,
    ERR_TOO_LONG,
    content_from_payload,
    validate_content,
)


class ValidateContentTest(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_content("")
        self.assertEqual(str(caught.exception), ERR_EMPTY)

    def test_whitespace_rejected(self):
        for raw in (" ", "   ", "\n", "\t", " \n\t "):
            with self.assertRaises(ValueError) as caught:
                validate_content(raw)
            self.assertEqual(str(caught.exception), ERR_EMPTY)

    def test_non_string_rejected(self):
        for raw in (None, 1, 1.5, True, ["привет"], {"text": "привет"}):
            with self.assertRaises(ValueError) as caught:
                validate_content(raw)
            self.assertEqual(str(caught.exception), ERR_NOT_STRING)

    def test_too_long_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_content("я" * 4001)
        self.assertEqual(str(caught.exception), ERR_TOO_LONG)
        with self.assertRaises(ValueError) as caught_padded:
            validate_content("  " + ("a" * 4001) + "  ")
        self.assertEqual(str(caught_padded.exception), ERR_TOO_LONG)

    def test_boundary_and_normal_text_accepted(self):
        self.assertEqual(validate_content("a" * 4000), "a" * 4000)
        self.assertEqual(validate_content("  привет  "), "привет")
        self.assertEqual(validate_content("привет\nмир"), "привет\nмир")

    def test_quotes_and_sql_fragments_stay_text(self):
        raw = "O'Brien said \"'; DROP TABLE messages; -- OR 1=1\""
        accepted = validate_content(raw)
        self.assertEqual(accepted, raw)
        self.assertIn("'", accepted)
        self.assertIn('"', accepted)
        self.assertIn("DROP TABLE messages", accepted)
        self.assertEqual(content_from_payload({"content": raw}), raw)

    def test_null_byte_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_content("привет\x00")
        self.assertEqual(str(caught.exception), ERR_NULL)

    def test_non_object_rejected(self):
        for payload in (None, ["content"], "привет", 5):
            with self.assertRaises(ValueError) as caught:
                content_from_payload(payload)
            self.assertEqual(str(caught.exception), ERR_NOT_OBJECT)


if __name__ == "__main__":
    unittest.main()
