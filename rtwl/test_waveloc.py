import unittest
import os, glob
import logging

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SetupTests('test_setup'))
    return suite

def setUpModule():

    pass


class SetupTests(unittest.TestCase):

    def test_setup(self):
        self.assertTrue(True)

if __name__ == '__main__':

  import test_processing
  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 

  suite_list=[suite(),
    test_processing.suite(),
    ]

  alltests=unittest.TestSuite(suite_list)

  unittest.TextTestRunner(verbosity=2).run(alltests)
 