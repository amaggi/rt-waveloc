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

        # set up an event at the center of the grid
        self.x = 0.5 * tgrid.grid_info['nx'] * tgrid.grid_info['dx'] \
                + tgrid.grid_info['x_orig']
        self.y = 0.5 * tgrid.grid_info['ny'] * tgrid.grid_info['dy'] \
                + tgrid.grid_info['y_orig']
        self.z = 0.5 * tgrid.grid_info['nz'] * tgrid.grid_info['dz'] \
                + tgrid.grid_info['z_orig']

        # set up some synthetic parameters
        self.dt=0.01
        t = np.arange(10000) * self.dt
        #self.ot = np.random.rand(3)*70
        self.ot = 50
        self.starttime=UTCDateTime(2013,03,01)
        g_width=0.2

        # create observations
        self.obs_list=[]
        for tgrid in self.time_grids:
            ttime = tgrid.value_at_point(self.x,self.y,self.z)
            ttime = np.round(ttime / self.dt) * self.dt
            tobs = ttime+self.ot
            # set up stats
            sta=tgrid.grid_info['station']
            stats={'network':'ST', 'station':sta,\
                    'channel':'HHZ', 'npts':len(t), 'delta':self.dt,\
                    'starttime':self.starttime}
            # set up seismogram
            seis=  np.exp(-0.5*(t-tobs)**2 / (g_width**2) ) 
            tr = Trace(data=seis,header=stats)
            self.obs_list.append(tr)
            #tr.plot()



    def test_migration_true(self):
        import matplotlib.pyplot as plt

        # set up sta-times matrix
        # each row contains ttimes for all points of interest for one station
        x=np.array([self.x, self.x+3.0])
        y=np.array([self.y, self.y+3.0])
        z=np.array([self.z, self.z+1.0])
        ttimes_list=[tgrid.value_at_points(x, y, z) \
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
            for tr in tr_list:
                tr.slice(common_start, common_end)
            tr_common=np.vstack([tr.data for tr in tr_list])
            diff=tr_common[0,:] - tr_common[5,:]
            stack_trace=np.sum(tr_common, axis=0)
            # set up output seismogram
            tr=tr_list[0].copy()
            tr.stats.station = 'STACK'
            tr.stats.starttime = common_start
            tr.stats.npts = len(stack_trace)
            tr.data[:]=stack_trace[:]
            # append
            #tr.plot()
            stack_list.append(tr)


        # do final stack
        # find common start and end time
        common_start=max([tr.stats.starttime for tr in stack_list])
        common_end  =min([tr.stats.endtime for tr in stack_list])
        for tr in stack_list:
            tr.slice(common_start, common_end)
        # stack common parts of traces
        tr_common=np.vstack([tr.data for tr in stack_list])
        max_trace=np.max(tr_common, axis=0)
        max_trace_id=np.argmax(tr_common, axis=0)
        #t=np.arange(len(max_trace))*self.dt
        #plt.plot(t,max_trace_id,'bo')
        #plt.show()
        # set up output seismogram
        tr=stack_list[0].copy()
        tr.stats.station = 'MAX'
        tr.stats.starttime = common_start
        tr.stats.npts = len(max_trace)
        tr.data=max_trace
        #tr.plot()

        # check we find the same absolute origin time
        tmax=np.argmax(max_trace)*self.dt
        tdiff=(tr.stats.starttime + tmax)-(self.starttime + self.ot)
        self.assertEquals(tdiff,0)
 





if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
