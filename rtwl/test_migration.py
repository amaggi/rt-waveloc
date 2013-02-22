import unittest, os, glob, h5py
import numpy as np
import am_rt_signal 
from obspy.core import Trace, UTCDateTime
from obspy.realtime import RtTrace
from options import RtWavelocOptions
from hdf5_grids import H5SingleGrid, interpolateTimeGrid
from migration import RtMigrator
from plotting import plotMaxXYZ
from synthetics import make_synthetic_data, generate_random_test_points

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticMigrationTests('test_rt_migration_true'))
    return suite

class SyntheticMigrationTests(unittest.TestCase):

    def setUp(self):
        import obspy.realtime
        rt_dict= obspy.realtime.rttrace.REALTIME_PROCESS_FUNCTIONS
        rt_dict['neg_to_zero']=(am_rt_signal.neg_to_zero,0)
        rt_dict['convolve']=(am_rt_signal.convolve,1)
        
        self.wo = RtWavelocOptions()
        self.wo.opdict['outdir'] = 'Test'
        self.wo.opdict['time_grid'] = 'Slow_len.100m.P'
        self.wo.opdict['max_length'] = 120
        self.wo.opdict['safety_margin'] = 20

#        self.wo.verifyDirectories()

        # make synthetic data
        self.obs_list, self.ot, (x0,y0,z0) = make_synthetic_data(self.wo)

        self.starttime=self.obs_list[0].stats.starttime
        self.dt=self.obs_list[0].stats.delta

        # split data files to simulate packets of real-time data
        self.obs_split=[]
        for obs in self.obs_list:
            obs_split = obs / 3
            self.obs_split.append(obs_split)

        # generate ttimes_files for test
        n_test=150
        generate_random_test_points(self.wo, n_test, (x0, y0, z0))

    def test_rt_migration_true(self):

        migrator = RtMigrator(self.wo)
        nsta = migrator.nsta


        ntr=len(self.obs_split[0])
        #########################
        # start loops
        #########################
        # loop over segments (simulate real-time data)
        for itr in xrange(ntr):
            # update all input streams
            # loop over stations
            data_list=[]
            for ista in xrange(nsta):
                tr = self.obs_split[ista][itr]
                data_list.append(tr)

            # update data
            migrator.updateData(data_list)

            # update stacks
            migrator.updateStacks()
            
            # update max
            migrator.updateMax()

        #########################
        # end loops
        #########################

        # check we find the same absolute origin time
        #migrator.max_out.plot()
        st=migrator.max_out.stats.starttime+45
        ed=migrator.max_out.stats.starttime+55
        max_out=migrator.max_out.slice(st,ed)
        x_out=migrator.x_out.slice(st,ed)
        y_out=migrator.y_out.slice(st,ed)
        z_out=migrator.z_out.slice(st,ed)
        #plotMaxXYZ(max_out, x_out, y_out, z_out, 'test_out.png')
        max_trace=migrator.max_out.data
        tmax=np.argmax(max_trace)*self.dt
        tdiff=(migrator.max_out.stats.starttime + tmax)-(self.starttime + self.ot)
        self.assertEquals(tdiff,0)






if __name__ == '__main__':

#  import logging
#  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
