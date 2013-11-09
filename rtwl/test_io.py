import unittest
from options import RtWavelocOptions
from rtwl_io import readConfig

def suite():
    suite = unittest.TestSuite()
    suite.addTest(IoTests('test_readConfig'))
    return suite
    
class IoTests(unittest.TestCase):
    
    def setUp(self):
        # set up expected waveloc options
        self.wo = RtWavelocOptions()
        self.wo.opdict['outdir'] = 'RealDataTest'
        self.wo.opdict['datadir'] = 'RealDataTest'
        self.wo.opdict['data_glob'] = 'YA*MSEED'
        self.wo.opdict['time_grid'] = 'Slow_len.100m.P'
        self.wo.opdict['max_length'] = 120
        self.wo.opdict['safety_margin'] = 20
        self.wo.opdict['syn'] = False
        self.wo.opdict['filt_f0'] = 27.0
        self.wo.opdict['filt_sigma'] = 7.0
        self.wo.opdict['kwin'] = 3.0
        
        # filename for test waveloc options
        self.config_file = 'test_data/test_rtwl.config'
        
    def test_readConfig(self) :
        
        opdict = readConfig(self.config_file)
        
        for key in self.wo.opdict.keys():
            self.assertEqual(opdict[key],self.wo.opdict[key])
            
if __name__ == '__main__':
 
    unittest.TextTestRunner(verbosity=2).run(suite())