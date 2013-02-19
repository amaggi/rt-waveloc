import unittest, os, glob
import numpy as np
import am_rt_signal 
from obspy.core import Trace, UTCDateTime
from obspy.realtime import RtTrace
from options import RtWavelocOptions
from hdf5_grids import H5SingleGrid

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
        self.obs_split=[]
        for obs in self.obs_list:
            obs_split = obs / 3
            self.obs_split.append(obs_split)


    def test_migration_true(self):
        #import matplotlib.pyplot as plt

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
    def test_rt_migration_true(self):

        max_length = 120
        safety_margin = 20

        #########################
        # set up sta-times matrix
        # each row contains ttimes for all points of interest for one station
        #########################
        x=np.array([self.x, self.x+3.0])
        y=np.array([self.y, self.y+3.0])
        z=np.array([self.z, self.z+1.0])
        ttimes_list=[tgrid.value_at_points(x, y, z) \
                for tgrid in self.time_grids]
        ttimes_matrix=np.vstack(ttimes_list)
        ttimes_matrix=np.round(ttimes_matrix / self.dt) * self.dt
        (nsta,npts) = ttimes_matrix.shape

        #########################
        # set up real-time traces
        #########################

        # need a RtTrace per station 
        obs_rt_list=[RtTrace() for sta in self.obs_list]

        # register pre-processing of data here
        for rtt in obs_rt_list:
            rtt.registerRtProcess('scale', factor=1.0)

        # need nsta streams for each point we test (nsta x npts)
        # for shifted waveforms
        point_rt_list=[[RtTrace(max_length=max_length) \
                for ista in xrange(nsta)] for ip in xrange(npts)]

        # register processing of point-streams here
        for rtt in obs_rt_list:
            # This is where we would scale for distance (given pre-calculated
            # distances from each point to every station)
            rtt.registerRtProcess('scale', factor=1.0)

        # need npts streams to store the point-stacks
        stack_list=[RtTrace(max_length=max_length) for ip in xrange(npts)]
        
        # register stack procesing here
        for rtt in stack_list:
            # This is where we would add or lower weights if we wanted to
            rtt.registerRtProcess('scale', factor=1.0)

        # need 4 output streams (max, x, y, z)
        max_out = RtTrace()
        x_out = RtTrace()
        y_out = RtTrace()
        z_out = RtTrace()

        # need a list of common start-times
        last_common_end_stack = [UTCDateTime(1970,1,1) for i in xrange(npts)]
        last_common_end_max = UTCDateTime(1970,1,1) 

        #########################
        # acquire and pre-process data
        #########################

        ntr=len(self.obs_split[0])
        #########################
        # start loops
        #########################
        # loop over segments (simulate real-time data)
        for itr in xrange(ntr):
            # update all input streams
            # loop over stations
            for ista in xrange(nsta):
                tr = self.obs_split[ista][itr]
                pp_data = obs_rt_list[ista].append(tr, gap_overlap_check = True)
                # loop over points
                for ip in xrange(npts):
                    # do time shift and append
                    pp_data_tmp = pp_data.copy()
                    pp_data_tmp.stats.starttime -= ttimes_matrix[ista,ip]
                    point_rt_list[ip][ista].append(pp_data_tmp, gap_overlap_check = True)

            # update of all input streams is done
            # now do the migration

            # loop over points once to get stacks
            for ip in xrange(npts):
                # get common start-time for this point
                common_start=max([point_rt_list[ip][ista].stats.starttime \
                        for ista in xrange(nsta)])
                common_start=max(common_start,last_common_end_stack[ip])
                # get list of stations for which the end-time is compatible
                # with the common_start time and the safety buffer
                ista_ok=[]
                for ista in xrange(nsta):
                    if (point_rt_list[ip][ista].stats.endtime - common_start) > safety_margin :
                        ista_ok.append(ista)
                # get common end-time
                common_end=min([ point_rt_list[ip][ista].stats.endtime for ista in ista_ok])
                last_common_end_stack[ip]=common_end+self.dt
                # stack
                c_list=[]
                for ista in ista_ok:
                    tr=point_rt_list[ip][ista].copy()
                    tr.trim(common_start, common_end)
                    c_list.append(tr.data)
                tr_common=np.vstack(c_list)
                stack_data = np.sum(tr_common, axis=0)
                # prepare trace for passing up
                tr=Trace(data=stack_data)
                tr.stats.station = 'STACK'
                tr.stats.npts = len(stack_data)
                tr.stats.delta = self.dt
                tr.stats.starttime=common_start
                # append to appropriate stack_list
                stack_list[ip].append(tr, gap_overlap_check = True)
                stack_list[ip].plot()

            # now extract maximum etc from stacks
            # get common start-time for this point
            common_start=max([stack_list[ip].stats.starttime \
                    for ip in xrange(npts)])
            common_start=max(common_start,last_common_end_max)
            # get list of points for which the end-time is compatible
            # with the common_start time and the safety buffer
            ip_ok = []
            for ip in xrange(npts):
                if (stack_list[ip].stats.endtime - common_start) > safety_margin:
                    ip_ok.append(ip)
            common_end=min([stack_list[ip].stats.endtime for ip in ip_ok ])
            last_common_end_max=common_end+self.dt
            # stack
            c_list=[]
            for ip in ip_ok:
                tr=stack_list[ip].copy()
                tr.trim(common_start, common_end)
                c_list.append(tr.data)
            tr_common=np.vstack(c_list)
            # get maximum and the corresponding point
            max_data = np.max(tr_common, axis=0)
            argmax_data = np.argmax(tr_common, axis=0)
            # prepare traces for passing up
            # max
            tr=Trace(data=stack_data)
            tr.stats.station = 'MAX'
            tr.stats.npts = len(max_data)
            tr.stats.delta = self.dt
            tr.stats.starttime=common_start
            max_out.append(tr, gap_overlap_check = True)
            # x coordinate
            tr_x=tr.copy()
            tr_x.stats.station = 'XMAX'
            tr_x.data=x[argmax_data]
            x_out.append(tr_x, gap_overlap_check = True)
            # y coordinate
            tr_y=tr.copy()
            tr_y.stats.station = 'YMAX'
            tr_y.data=y[argmax_data]
            y_out.append(tr_y, gap_overlap_check = True)
            # z coordinate
            tr_z=tr.copy()
            tr_z.stats.station = 'YMAX'
            tr_z.data=z[argmax_data]
            z_out.append(tr_z, gap_overlap_check = True)
            max_out.plot()

        #########################
        # end loops
        #########################

        # check we find the same absolute origin time
        max_trace=max_out.data
        tmax=np.argmax(max_trace)*self.dt
        tdiff=(tr.stats.starttime + tmax)-(self.starttime + self.ot)
        self.assertEquals(tdiff,0)






if __name__ == '__main__':

  import logging
  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
