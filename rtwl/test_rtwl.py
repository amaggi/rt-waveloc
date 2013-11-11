import unittest
import multiprocessing
import os
from cPickle import dump, load

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticProcessingTests('test_syn_staproc'))
    return suite
    
class SyntheticProcessingTests(unittest.TestCase):

    def setUp(self):
        from rtwl_io import rtwlGetConfig
        # read config file
        self.wo = rtwlGetConfig('test_data/test_rtwl_syn.config')
        self.sp = None
        
    
    def _run_staproc(self, wo, filename):
        from rtwl_staproc import rtwlStaProcessor
        
        sp = rtwlStaProcessor(wo)
        # save stuff to check out to a file
        f=open(filename,'w')
        dump(sp.rtt,f,-1)
        f.close()
               
          
    def test_syn_staproc(self):
        from rtwl_control import rtwlStart, rtwlStop
        
        tmpfile = 'test_syn_staproc.tmp'
        
        p=multiprocessing.Process(target=self._run_staproc, args=(self.wo, tmpfile))
        p.start()
        
        rtwlStart(self.wo)        
        rtwlStop(self.wo)
        
        p.join()
        
        f=open(tmpfile,'r')
        rtt=load(f)
        f.close()
        sta_list=self.wo.sta_list
        for sta in sta_list:
            self.assertTrue(rtt.has_key(sta))
        
        os.remove(tmpfile)
        

if __name__ == '__main__':

    import logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
    unittest.TextTestRunner(verbosity=2).run(suite())
 