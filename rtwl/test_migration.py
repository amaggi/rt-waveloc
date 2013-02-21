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

        x=np.array([self.x, self.x+3.0])
        y=np.array([self.y, self.y+3.0])
        z=np.array([self.z, self.z+1.0])

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

 #       max_length = 120
        safety_margin = 20

        #########################
        # set up sta-times matrix
        # each row contains ttimes for all points of interest for one station
        #########################

        migrator = RtMigrator(self.wo)

        ttimes_matrix = migrator.ttimes_matrix
        nsta = migrator.nsta
        npts = migrator.npts

        #########################
        # set up real-time traces
        #########################

        # need a RtTrace per station 
        obs_rt_list = migrator.obs_rt_list
        point_rt_list = migrator.point_rt_list
        stack_list = migrator.stack_list

        max_out = migrator.max_out
        x_out = migrator.x_out
        y_out = migrator.y_out
        z_out = migrator.z_out

        # need a list of common start-times
        last_common_end_stack = migrator.last_common_end_stack
        last_common_end_max = migrator.last_common_end_max

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
                sta=tr.stats.station
                iista=migrator.sta_list.index(sta)
                pp_data = obs_rt_list[iista].append(tr, gap_overlap_check = True)
                # loop over points
                for ip in xrange(npts):
                    # do time shift and append
                    pp_data_tmp = pp_data.copy()
                    pp_data_tmp.stats.starttime -= np.round(ttimes_matrix[ista,ip]/self.dt) * self.dt
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
                #stack_list[ip].plot()

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
            tr_max=Trace(data=max_data)
            tr_max.stats.station = 'MAX'
            tr_max.stats.npts = len(max_data)
            tr_max.stats.delta = self.dt
            tr_max.stats.starttime=common_start
            max_out.append(tr_max, gap_overlap_check = True)
            # x coordinate
            tr_x=tr_max.copy()
            tr_x.stats.station = 'XMAX'
            tr_x.data=migrator.x[argmax_data]
            x_out.append(tr_x, gap_overlap_check = True)
            # y coordinate
            tr_y=tr_max.copy()
            tr_y.stats.station = 'YMAX'
            tr_y.data=migrator.y[argmax_data]
            y_out.append(tr_y, gap_overlap_check = True)
            # z coordinate
            tr_z=tr_max.copy()
            tr_z.stats.station = 'ZMAX'
            tr_z.data=migrator.z[argmax_data]
            z_out.append(tr_z, gap_overlap_check = True)

        #########################
        # end loops
        #########################

        # check we find the same absolute origin time
        #max_out.plot()
        max_trace=max_out.data
        tmax=np.argmax(max_trace)*self.dt
        tdiff=(max_out.stats.starttime + tmax)-(self.starttime + self.ot)
        self.assertEquals(tdiff,0)





if __name__ == '__main__':

#  import logging
#  logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
 
  unittest.TextTestRunner(verbosity=2).run(suite())
 
