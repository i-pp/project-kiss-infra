import unittest
from feedback import feedback


class FeedbackTests(unittest.TestCase):
    def test_candidate_diagnostic_only(self):
        output = ("/candidate/c_parse.c:5:14: error: 'NULL' undeclared\n"
                  "/suite/private.cpp:1:2: error: EXPECTED_SECRET\n"
                  "  1 | assert(result == SECRET_REFERENCE);\n")
        text = feedback({'steps':[{'phase':'compile_candidate','output':output}]},'c_parse.c')
        self.assertIn('NULL',text)
        self.assertNotIn('EXPECTED_SECRET',text)
        self.assertNotIn('SECRET_REFERENCE',text)
        self.assertNotIn('/suite',text)

    def test_runtime_output_never_forwarded(self):
        for output in ["assert(actual == SECRET_REFERENCE)","AddressSanitizer SECRET_REFERENCE", "Segmentation fault SECRET_REFERENCE"]:
            text = feedback({'steps':[{'phase':'execute_tests','output':output,'returncode':-6}]},'answer.c')
            self.assertNotIn('SECRET_REFERENCE',text)
            self.assertNotIn('assert(actual',text)

    def test_linker_output_never_forwarded(self):
        text = feedback({'steps':[{'phase':'link_tests','output':'TEST_ANSWER'}]},'answer.c')
        self.assertNotIn('TEST_ANSWER',text)


if __name__ == '__main__': unittest.main()
