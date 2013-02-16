import unittest, os, glob
import numpy as np
from obspy.core import Trace, UTCDateTime
from options import RtWavelocOptions
from hdf5_grids import H5SingleGrid

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticMigrationTests('test_migration_true'))
    return suite

class SyntheticMigrationTests(unittest.TestCase):

    def setUp(self):
        import matplotlib.pyplot as plt
        self.wo = RtWavelocOptions()
        self.wo.verify_base_path()
        self.wo.verify_lib_dir()
        self.wo.opdict['time_grid'] = 'Slow_len.100m.P'

        base_path=self.wo.opdict['base_path']
        lib_path=os.path.join(base_path,'lib')

        time_grid_names = glob.glob(os.path.join(lib_path, \
                self.wo.opdict['time_grid'] + '*.hdf5'))
        self.time_grids=[H5SingleGrid(fname) for fname in time_grid_names]

        # get grid extent from first time-grid
        tgrid = self.time_grids[0]

        tmp=np.array([0.15, 0.35, 0.75])

        # set up three events
        #self.x = np.random.rand(3) * tgrid.grid_info['nx'] * tgrid.grid_info['dx'] \
        self.x = np.array([0.25,0.5,0.75]) * tgrid.grid_info['nx'] * tgrid.grid_info['dx'] \
                + tgrid.grid_info['x_orig']
        #self.y = np.random.rand(3) * tgrid.grid_info['ny'] * tgrid.grid_info['dy'] \
        self.y = np.array([0.25,0.5,0.75]) * tgrid.grid_info['ny'] * tgrid.grid_info['dy'] \
                + tgrid.grid_info['y_orig']
        #self.z = np.random.rand(3) * tgrid.grid_info['nz'] * tgrid.grid_info['dz'] \
        self.z = np.array([0.33333,0.5,0.66666]) * tgrid.grid_info['nz'] * tgrid.grid_info['dz'] \
                + tgrid.grid_info['z_orig']
        #amp = np.random.rand(3)
        amp = np.ones(3)

        # set up some synthetic parameters
        self.dt=0.01
        t = np.arange(10000) * self.dt
        #self.ot = np.random.rand(3)*70
        self.ot = np.array([30, 50, 70])
        self.starttime=UTCDateTime(2013,01,01)
        g_width=0.2

        # create observations
        self.obs_list=[]
        for tgrid in self.time_grids:
            ttime = tgrid.value_at_points(self.x,self.y,self.z)
            ttime = np.round(ttime / self.dt) * self.dt
            tobs = ttime+self.ot
            # set up stats
            sta=tgrid.grid_info['station']
            stats={'network':'ST', 'station':sta,\
                    'channel':'HHZ', 'npts':len(t), 'sampling_rate':self.dt,\
                    'starttime':self.starttime}
            # set up seismogram
            seis=  amp[0]*np.exp(-0.5*(t-tobs[0])**2 / (g_width**2) ) +\
                   amp[1]*np.exp(-0.5*(t-tobs[1])**2 / (g_width**2) ) +\
                   amp[2]*np.exp(-0.5*(t-tobs[2])**2 / (g_width**2) )
            tr = Trace(data=seis,header=stats)
            self.obs_list.append(tr)
            #tr.plot()



    def test_migration_true(self):
        import matplotlib.pyplot as plt

        # set up sta-times matrix
        # each row contains ttimes for all points of interest for one station
        ttimes_list=[tgrid.value_at_points(self.x, self.y, self.z) \
                for tgrid in self.time_grids]
        ttimes_matrix=np.vstack(ttimes_list)
        ttimes_matrix=np.round(ttimes_matrix / self.dt) * self.dt
        (nsta,npts) = ttimes_matrix.shape

        stack_list=[]
        for ip in xrange(npts):
            tr_list=[]
            # shift according to travel-times
            for ista in xrange(nsta):
                tr=self.obs_list[ista].copy()
                tr.stats.starttime -= ttimes_matrix[ista,ip]
                tr_list.append(tr)
            # find common start and end time
            common_start=max([tr.stats.starttime for tr in tr_list])
            common_end  =min([tr.stats.endtime for tr in tr_list])
            # stack common parts of traces
            tr_common=np.vstack([tr.slice(common_start, common_end).data for tr in tr_list])
            diff=tr_common[0,:] - tr_common[5,:]
            print np.max(diff), np.argmax(diff)
            stack_trace=np.sum(tr_common, axis=0)
            # set up output seismogram
            tr=tr_list[0].copy()
            tr.stats.station = 'STACK'
            tr.stats.starttime = common_start
            tr.stats.npts = len(stack_trace)
            tr.data[:]=stack_trace[:]
            # append
            tr.plot()
            stack_list.append(tr)

        # do final stack
        # find common start and end time
        common_start=max([tr.stats.starttime for tr in stack_list])
        common_end  =min([tr.stats.endtime for tr in stack_list])
        # stack common parts of traces
        tr_common=np.vstack([tr.slice(common_start, common_end).data for tr in stack_list])
        max_trace=np.max(tr_common, axis=0)
        max_trace_id=np.argmax(tr_common, axis=0)
        t=np.arange(len(max_trace))*self.dt
        plt.plot(t,max_trace_id,'bo')
        plt.show()
        diff=tr_common[0,:]-tr_common[2,:]
        print np.max(diff)
        # set up output seismogram
        tr=stack_list[0].copy()
        tr.stats.station = 'MAX'
        tr.stats.starttime = common_start
        tr.stats.npts = len(max_trace)
        tr.data=max_trace
        tr.plot()
 





if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
