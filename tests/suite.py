import unittest

import test_cluster as cluster
import test_network as network
import test_bmcsetup as bmcsetup
import test_utils_ip as utils_ip
import test_utils_freelist as utils_freelist
import test_osimage as osimage

from optparse import OptionParser


parser = OptionParser('usage: %prog [options] -- [testsuite options]')
parser.add_option('-v', '--verbose',
                  action='count', dest='verbose', default=1,
                  help='increase verbosity')

(options, args) = parser.parse_args()

loader = unittest.TestLoader()
suite = unittest.TestSuite()

suite.addTests(loader.loadTestsFromModule(utils_ip))
suite.addTests(loader.loadTestsFromModule(utils_freelist))
suite.addTests(loader.loadTestsFromModule(cluster))
suite.addTests(loader.loadTestsFromModule(network))
suite.addTests(loader.loadTestsFromModule(bmcsetup))
suite.addTests(loader.loadTestsFromModule(osimage))

if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=options.verbose)
    runner.run(suite)
