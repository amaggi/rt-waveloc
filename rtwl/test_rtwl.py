import unittest, logging
import multiprocessing
import os, glob
import time
import numpy as np
from cPickle import load

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticProcessingTests('serial_parallel_comparison'))
    return suite
    
class SyntheticProcessingTests(unittest.TestCase):

    def setUp(self):
        from rtwl_io import rtwlGetConfig
                
        # read config file
        self.wo = rtwlGetConfig('test_data/test_rtwl_syn.config')
    
    def tearDown(self):
        dumpfiles=glob.glob('*.dump')
        for fname in dumpfiles :
            os.remove(fname) 

    def _run_staproc(self, wo, do_dump):
        from rtwl_staproc import rtwlStaProcessor
        
        # run the station processing, with dumping option requested
        rtwlStaProcessor(wo, do_dump=do_dump)
      
    def _run_pointproc(self, wo, do_dump):
        from rtwl_pointproc import rtwlPointStacker
        
        # run the point procesing, dumping as requested
        rtwlPointStacker(wo, do_dump=do_dump)     

    def _run_stackproc(self, wo, do_dump):
        from rtwl_stackproc import rtwlStacker
        
        # run the stacking, dumping as requested
        rtwlStacker(wo, do_dump=do_dump)     
                
    def _do_serial_migration(self):
        from migration import RtMigrator
        from synthetics import make_synthetic_data
        
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
            migrator.updateStacks()

        # migration using old_style migrator is finished 
          
    def _do_parallel_migration(self):
        from rtwl_control import rtwlControler
        
        # prepare rt processing using rtwl
        #p=multiprocessing.Process(target=self._run_staproc, args=(self.wo, True,))
        #q=multiprocessing.Process(target=self._run_pointproc, args=(self.wo, True,))
        #r=multiprocessing.Process(target=self._run_stackproc, args=(self.wo, True,))
        
        #q.start()
        #p.start()
        #r.start()
        
        # need to give time for the receiving ends to get set up before sending
        #time.sleep(1)
        
        # controler
        ctrl = rtwlControler(self.wo, do_dump=True)
        # launch process (sets up synthetic test)
        ctrl.rtwlStart()
        # stop process
        ctrl.rtwlStop()
        
        # wait for p and q to finish
        #p.join()
        #q.join()
        #r.join()
    
                
    def serial_parallel_comparison(self):
  
        # do migration both ways
        self._do_parallel_migration()     
        self._do_serial_migration()
        
        ############################
        # TESTS FOR DATA PROCESSING
        ############################
        
        # read processed data from files
        sta_list = self.wo.sta_list
        rtwl_rtt={}
        for sta in sta_list : 
            fname='staproc_%s.dump'%sta
            f=open(fname,'r')
            tr=load(f)
            f.close() 
            rtwl_rtt[sta]=tr 
                              
        # read dumped processed data from files
        mig_rtt={}
        for sta in sta_list : 
            fname='update_data_%s.dump'%sta
            f=open(fname,'r')
            tr=load(f)
            f.close() 
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

        ############################
        # TESTS FOR SHIFTED DATA
        ############################        
                        
        # check file has been dumped correctly
        ttimes_filename='pointproc_point00.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        point00_rtwl=load(f)
        f.close()
        
        # check file has been dumped correctly
        ttimes_filename='migrator_point00.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        point00_migr=load(f)
        f.close()
        
        # check the two are equal
        self.assertEquals(point00_rtwl.stats.npts, 
                          point00_migr.stats.npts)
        np.testing.assert_almost_equal(point00_rtwl.data, point00_migr.data)

        ############################
        # TESTS FOR TTIMES MATRIX
        ############################
        
        # check file has been dumped correctly
        ttimes_filename='pointproc_ttimes.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        ttimes_matrix_rtwl=load(f)
        f.close()        
        
        # check file has been dumped correctly
        ttimes_filename='migrator_ttimes.dump'
        self.assertTrue(os.path.isfile(ttimes_filename))
        f=open(ttimes_filename)
        ttimes_matrix_migr=load(f)
        f.close()

        # check dimensions of file
        (nsta_rtwl,npts_rtwl) = ttimes_matrix_rtwl.shape
        (nsta_migr,npts_migr) = ttimes_matrix_migr.shape
        time_grid_names = glob.glob(self.wo.ttimes_glob)

        self.assertEqual(npts_rtwl, self.wo.opdict['syn_npts'])
        self.assertEqual(nsta_rtwl, len(time_grid_names))
        self.assertEqual(npts_rtwl, npts_migr)
        self.assertEqual(nsta_rtwl, nsta_migr)
        np.testing.assert_almost_equal(ttimes_matrix_rtwl, ttimes_matrix_migr)

        ############################
        # TESTS FOR GRID POINTS
        ############################

        # check file has been dumped correctly
        xyz_filename='stackproc_xyz.dump'
        self.assertTrue(os.path.isfile(xyz_filename))
        f=open(xyz_filename)
        (x_rtwl, y_rtwl, z_rtwl) = load(f)
        f.close()
               
        # check file has been dumped correctly
        xyz_filename='migrator_xyz.dump'
        self.assertTrue(os.path.isfile(xyz_filename))
        f=open(xyz_filename)
        (x_migr, y_migr, z_migr) = load(f)
        f.close()
                
        np.testing.assert_almost_equal(x_migr, x_rtwl)

        ############################
        # TESTS FOR GRID STACK
        ############################

        # check file has been dumped correctly
        stack0_filename='migrator_stack0.dump'
        self.assertTrue(os.path.isfile(stack0_filename))
        f=open(stack0_filename)
        stack0_migr=load(f)
        f.close()
       
        # check file has been dumped correctly
        stack0_filename='stackproc_stack0.dump'
        self.assertTrue(os.path.isfile(stack0_filename))
        f=open(stack0_filename)
        stack0_rtwl=load(f)
        f.close()

        # check the two are equal
        self.assertEquals(stack0_rtwl.stats.npts, 
                          stack0_migr.stats.npts)
        np.testing.assert_almost_equal(stack0_rtwl.data, stack0_migr.data)


if __name__ == '__main__':

    logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
    unittest.TextTestRunner(verbosity=2).run(suite())
 