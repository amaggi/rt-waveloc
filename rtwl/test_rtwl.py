import unittest
import multiprocessing
import os
import time
import numpy as np
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
    

    def _run_staproc(self, wo):
        from rtwl_staproc import rtwlStaProcessor
        
        # run the processing
        rtwlStaProcessor(wo, do_dump=True)
            
          
    def test_syn_staproc(self):
        from rtwl_control import rtwlStart, rtwlStop
        from migration import RtMigrator
        from synthetics import make_synthetic_data
 
                
        # do processing using rtwl
        p=multiprocessing.Process(target=self._run_staproc, args=(self.wo,))
        p.start()
        time.sleep(1)
        
        rtwlStart(self.wo)
        rtwlStop(self.wo)
        
        p.join()
        
        # read processed data from files
        sta_list = self.wo.sta_list
        rtwl_rtt={}
        for sta in sta_list : 
            fname='staproc_%s.dump'%sta
            f=open(fname,'r')
            tr=load(f)
            f.close() 
            os.remove(fname)
            rtwl_rtt[sta]=tr 
                      
        
        # do processing using old_style migrator
        obs_list, ot, (x0,y0,z0) = make_synthetic_data(self.wo)
        migrator = RtMigrator(self.wo, do_dump=True)
        
        # split data files to simulate packets of real-time data
        obs_split=[]
        for obs in obs_list:
            split = obs / 3
            obs_split.append(split)
        
        ntr=len(obs_split[0])

        nsta=len(obs_list)
        # loop over segments (simulate real-time data)
        for itr in xrange(ntr):
            data_list=[]
            for ista in xrange(nsta):
                tr = obs_split[ista][itr]
                data_list.append(tr)
            # do one update
            migrator.updateData(data_list)

        # migration using old_style migrator is finished
        
        # read dumped processed data from files
        sta_list = self.wo.sta_list
        mig_rtt={}
        for sta in sta_list : 
            fname='update_data_%s.dump'%sta
            f=open(fname,'r')
            tr=load(f)
            f.close() 
            os.remove(fname)
            mig_rtt[sta]=tr
            
        # sanity check on stations
        #sta_list=self.wo.sta_list
        for tr in mig_rtt.values() :
            sta=tr.stats.station
            self.assertTrue(rtwl_rtt.has_key(sta))
            self.assertEquals(mig_rtt[sta].stats.npts, rtwl_rtt[sta].stats.npts)
            self.assertAlmostEqual(np.max(mig_rtt[sta].data), np.max(rtwl_rtt[sta].data))
            self.assertEqual(np.argmax(mig_rtt[sta].data), np.argmax(rtwl_rtt[sta].data))

        

if __name__ == '__main__':

    import logging
    #logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
    unittest.TextTestRunner(verbosity=2).run(suite())
 