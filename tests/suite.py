import unittest
import os
from optparse import OptionParser

"""
to run tests:

    All tests
        $ tox

    All tests in all files matching glob
        $ tox --  -p *node*

    All tests in class in module:
        $ tox -- test_node.NodeCreateTests

    Single test:
        $ tox -- test_node.NodeCreateTests.test_create_named_node
"""

parser = OptionParser('usage: %prog [options] -- [testsuite options]')

parser.add_option('-v', '--verbose',
                  action='count', dest='verbose', default=1,
                  help='increase verbosity')

parser.add_option('-p', '--pattern',
                  dest='pattern',
                  default='test*.py',
                  help='pattern for tests')

(options, args) = parser.parse_args()

loader = unittest.TestLoader()
suite = unittest.TestSuite()

if args:
    for elem in args:
        suite.addTests(loader.loadTestsFromName(elem))
else:
    tests_dir = os.path.dirname(os.path.realpath(__file__))
    suite.addTests(loader.discover(tests_dir, options.pattern))

if __name__ == '__main__':
    runner = unittest.TextTestRunner(
        verbosity=options.verbose,
    )
    runner.run(suite)
