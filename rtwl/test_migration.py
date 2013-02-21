import unittest, os, glob, h5py
import numpy as np
import am_rt_signal 
from obspy.core import Trace, UTCDateTime
from obspy.realtime import RtTrace
from options import RtWavelocOptions
from hdf5_grids import H5SingleGrid, interpolateTimeGrid
from migration import RtMigrator

def suite():
    suite = unittest.TestSuite()
    suite.addTest(SyntheticMigrationTests('test_migration_true'))
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

        self.wo.verifyDirectories()

        ttimes_path=self.wo.ttimes_dir

        time_grid_names = glob.glob(self.wo.grid_glob)
        base_names=[os.path.basename(fname) for fname in time_grid_names]
        tt_names=[os.path.join(ttimes_path,base_name) for base_name in base_names]
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

        n_test=100
        x_test=(np.random.randn(n_test)*2.0 - 1.0)*4.0
        y_test=(np.random.randn(n_test)*2.0 - 1.0)*3.0
        z_test=(np.random.randn(n_test)*2.0 - 1.0)*2.0
        x=np.empty(n_test+1)
        y=np.empty(n_test+1)
        z=np.empty(n_test+1)
        x[0]=self.x
        y[0]=self.y
        z[0]=self.z
        x[1:n_test+1]=x_test
        y[1:n_test+1]=y_test
        z[1:n_test+1]=z_test

        for i in xrange(len(time_grid_names)):
            outname,ext=os.path.splitext(tt_names[i])
            outname = outname +'_ttimes.hdf5'
            interpolateTimeGrid(time_grid_names[i], outname, x, y, z)

        # set up some synthetic parameters
        self.dt=0.01
        t = np.arange(10000) * self.dt
        #self.ot = np.random.rand(3)*70
        self.ot = 50
        self.starttime=UTCDateTime(2013,02,15)
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
        self.obs_split=[]
        for obs in self.obs_list:
            obs_split = obs / 3
            self.obs_split.append(obs_split)


    @unittest.skip('Profiling')
    def test_migration_true(self):

        # set up the ttimes matrix
        ##########################

        # get the names of the ttimes files
        ttimes_fnames=glob.glob(self.wo.ttimes_glob)
        # get basic lengths
        f=h5py.File(ttimes_fnames[0],'r')
        # copy the x, y, z data over
        x = np.array(f['x'][:])
        y = np.array(f['y'][:])
        z = np.array(f['z'][:])
        f.close()
        # read the files
        ttimes_list = []
        for fname in ttimes_fnames:
            f=h5py.File(fname,'r')
            ttimes_list.append(np.array(f['ttimes']))
            f.close()
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
                tr.trim(common_start, common_end)
            tr_common=np.vstack([tr.data for tr in tr_list])
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
            tr.trim(common_start, common_end)
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
 

    #@unittest.skip('Bla')
    #@unittest.expectedFailure
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
        max_trace=migrator.max_out.data
        tmax=np.argmax(max_trace)*self.dt
        tdiff=(migrator.max_out.stats.starttime + tmax)-(self.starttime + self.ot)
        self.assertEquals(tdiff,0)





if __name__ == '__main__':

#  import logging
#  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
