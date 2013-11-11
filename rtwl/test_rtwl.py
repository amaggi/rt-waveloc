import unittest
import multiprocessing
import os, glob
import time
import numpy as np
from cPickle import load

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticProcessingTests('test_syn_staproc'))
    suite.addTest(SyntheticProcessingTests('test_syn_ttimes_matrix'))
    return suite
    
class SyntheticProcessingTests(unittest.TestCase):

    def setUp(self):
        from rtwl_io import rtwlGetConfig
        
        # read config file
        self.wo = rtwlGetConfig('test_data/test_rtwl_syn.config')
    

    def _run_staproc(self, wo, do_dump=False):
        from rtwl_staproc import rtwlStaProcessor
        
        # run the processing, with dumping option requested
        rtwlStaProcessor(wo, do_dump=do_dump)
      
    def _run_pointproc(self, wo, do_dump=False):
        from rtwl_pointproc import rtwlPointStacker
        
        # run the procesing, dumping as requested
        rtwlPointStacker(wo, do_dump=do_dump)     
          
    def test_syn_staproc(self):
        from rtwl_control import rtwlStart, rtwlStop
        from migration import RtMigrator
        from synthetics import make_synthetic_data
 
                
        # prepare rt processing using rtwl
        p=multiprocessing.Process(target=self._run_staproc, args=(self.wo, True,))
        p.start()
        time.sleep(1)
        
        # launch process (sets up synthetic test)
        rtwlStart(self.wo)
        # stop process
        rtwlStop(self.wo)
        
        # wait for p to finish
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
            
        # cross test two results
        for tr in mig_rtt.values() :
            sta=tr.stats.station
            self.assertTrue(rtwl_rtt.has_key(sta))
            self.assertEquals(mig_rtt[sta].stats.npts, 
                              rtwl_rtt[sta].stats.npts)
            self.assertAlmostEqual(np.max(mig_rtt[sta].data), 
                                   np.max(rtwl_rtt[sta].data))
            self.assertEqual(np.argmax(mig_rtt[sta].data), 
                             np.argmax(rtwl_rtt[sta].data))
    
    
    def test_syn_ttimes_matrix(self):
        from rtwl_control import rtwlStart, rtwlStop
        from migration import RtMigrator
        
        # prepare rt processing using rtwl
        p=multiprocessing.Process(target=self._run_staproc, args=(self.wo, False,))
        q=multiprocessing.Process(target=self._run_pointproc, args=(self.wo, True,))
        
        q.start()
        p.start()
        time.sleep(1)
        
        # launch process (sets up synthetic test)
        rtwlStart(self.wo)
        # stop process
        rtwlStop(self.wo)
        
        # wait for p and q to finish
        p.join()
        q.join()
        
        # check file has been dumped correctly
        ttimes_filename='pointproc_ttimes.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        ttimes_matrix_rtwl=load(f)
        f.close()
        os.remove(ttimes_filename)
        
        # get matrix with old-style migrator
        RtMigrator(self.wo, do_dump=True)
        
        # check file has been dumped correctly
        ttimes_filename='migrator_ttimes.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        ttimes_matrix_migr=load(f)
        f.close()
        os.remove(ttimes_filename)

        # check dimensions of file
        (nsta_rtwl,npts_rtwl) = ttimes_matrix_rtwl.shape
        (nsta_migr,npts_migr) = ttimes_matrix_migr.shape
        time_grid_names = glob.glob(self.wo.ttimes_glob)

        self.assertEqual(npts_rtwl, self.wo.opdict['syn_npts'])
        self.assertEqual(nsta_rtwl, len(time_grid_names))
        self.assertEqual(npts_rtwl, npts_migr)
        self.assertEqual(nsta_rtwl, nsta_migr)
        self.assertAlmostEqual(np.min(ttimes_matrix_rtwl), np.min(ttimes_matrix_migr))
        self.assertAlmostEqual(np.max(ttimes_matrix_rtwl), np.max(ttimes_matrix_migr))
        self.assertAlmostEqual(np.average(ttimes_matrix_rtwl), np.average(ttimes_matrix_migr))

if __name__ == '__main__':

    import logging
    #logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
    unittest.TextTestRunner(verbosity=2).run(suite())
 