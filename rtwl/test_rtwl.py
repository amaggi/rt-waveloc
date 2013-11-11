import unittest

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticMigrationTests('test_rt_migration_true'))
    return suite
    
class SyntheticMigrationTests(unittest.TestCase):

    def setUp(self):
        pass
       
    def test_rt_migration_true(self):
        self.assertTrue(True)
 

if __name__ == '__main__':

#  import logging
#  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 