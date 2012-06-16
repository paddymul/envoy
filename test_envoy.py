import unittest
import envoy
import pdb

class SimpleTest(unittest.TestCase):

    def test_input(self):
        r = envoy.run("sed s/i/I/g", "Hi")
        self.assertEqual(r.std_out.rstrip(), "HI")
        self.assertEqual(r.status_code, 0)

    def test_pipe(self):
        r = envoy.run("echo -n 'hi'| tr [:lower:] [:upper:]")
        self.assertEqual(r.std_out, "HI")
        self.assertEqual(r.status_code, 0)
        r = envoy.run2("echo -n 'hi'| tr [:lower:] [:upper:]")
        self.assertEqual(r.std_out, "HI")
        self.assertEqual(r.status_code, 0)
        r = envoy.run_extproc("echo -n 'hi'| tr [:lower:] [:upper:]")
        self.assertEqual(r.std_out, "HI")
        self.assertEqual(r.status_code, 0)


    def test_expand_args(self):
        self.assertEquals(
            envoy.expand_args("echo -n 'hi'| tr [:lower:] [:upper:]"),
            [['echo', '-n', 'hi'], ['tr', '[:lower:]', '[:upper:]']])

    def test_timeout(self):
        r = envoy.run('yes | head', timeout=1)
        self.assertEqual(r.std_out, 'y\ny\ny\ny\ny\ny\ny\ny\ny\ny\n')
        self.assertEqual(r.status_code, 0)

    def test_quoted_args(self):
        sentinel = 'quoted_args' * 3
        r = envoy.run("python -c 'print \"%s\"'" % sentinel)
        self.assertEqual(r.std_out.rstrip(), sentinel)
        self.assertEqual(r.status_code, 0)

class ConnectedCommandTests(unittest.TestCase):

    def test_status_code(self):
        c = envoy.connect("sleep 5")
        self.assertEqual(c.status_code, None)

if __name__ == "__main__":
    unittest.main()
