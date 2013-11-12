import h5py, glob, time, logging
import numpy as np
from obspy.core import Trace, UTCDateTime
from obspy.realtime import RtTrace
from am_signal import gaussian_filter
from cPickle import dump

class RtMigrator(object):
    """
    Class of objects for real-time migration.
    """

    # attributes
    x=np.array([])
    y=np.array([])
    z=np.array([])
    ttimes_matrix=np.empty((0,0), dtype=float)
    npts=0
    nsta=0
    sta_list=[]

    obs_rt_list=[]
    point_rt_list=[]
    stack_list=[]

    max_out=None
    x_out=None
    y_out=None
    z_out=None

    last_common_end_stack=[]
    last_common_end_max=None

    dt=1.0
    filter_shift=0.0


    def __init__(self,waveloc_options, do_dump=False):
        """
        Initialize from a set of travel-times as hdf5 files
        """
        wo=waveloc_options
        self.do_dump = do_dump
        # initialize the travel-times
        #############################
        ttimes_fnames=glob.glob(wo.ttimes_glob)
        # get basic lengths
        f=h5py.File(ttimes_fnames[0],'r')
        # copy the x, y, z data over
        self.x = np.array(f['x'][:])
        self.y = np.array(f['y'][:])
        self.z = np.array(f['z'][:])
        f.close()
        # read the files
        ttimes_list = []
        self.sta_list=[]
        for fname in ttimes_fnames:
            f=h5py.File(fname,'r')
            # update the list of ttimes
            ttimes_list.append(np.array(f['ttimes']))
            sta=f['ttimes'].attrs['station']
            f.close()
            # update the dictionary of station names
            self.sta_list.append(sta)
        # stack the ttimes into a numpy array
        self.ttimes_matrix=np.vstack(ttimes_list)
        (self.nsta,self.npts) = self.ttimes_matrix.shape

        
        # if do_dump, then dump ttimes_matrix to file for debugging
        if self.do_dump:
            filename='migrator_ttimes.dump'
            f=open(filename,'w')
            dump(self.ttimes_matrix,f,-1)
            f.close()
            
        # initialize the RtTrace(s)
        ##########################
        max_length = wo.opdict['max_length']
        self.safety_margin = wo.opdict['safety_margin']
        self.dt = wo.opdict['dt']

        # need a RtTrace per station 
        self.obs_rt_list=[RtTrace() for sta in self.sta_list]

        # register pre-processing
        self._register_preprocessing(wo)

        # need nsta streams for each point we test (nsta x npts)
        # for shifted waveforms
        self.point_rt_list=[[RtTrace(max_length=max_length) \
                for ista in xrange(self.nsta)] for ip in xrange(self.npts)]

        # register processing of point-streams here
        for sta_list in self.point_rt_list:
            for rtt in sta_list:
                # This is where we would scale for distance (given pre-calculated
                # distances from each point to every station)
                rtt.registerRtProcess('scale', factor=1.0)

        # need npts streams to store the point-stacks
        self.stack_list=[RtTrace(max_length=max_length) for ip in xrange(self.npts)]
        
        # register stack procesing here
        for rtt in self.stack_list:
            # This is where we would add or lower weights if we wanted to
            rtt.registerRtProcess('scale', factor=1.0)

        # need 4 output streams (max, x, y, z)
        self.max_out = RtTrace()
        self.x_out = RtTrace()
        self.y_out = RtTrace()
        self.z_out = RtTrace()

        if not wo.is_syn:
            self.max_out.registerRtProcess('boxcar', width=50)

        # need a list of common start-times
        self.last_common_end_stack = [UTCDateTime(1970,1,1) for i in xrange(self.npts)]
        self.last_common_end_max = UTCDateTime(1970,1,1) 

    def _register_preprocessing(self, waveloc_options):
        wo=waveloc_options
        
        # if this is a synthetic
        if wo.is_syn:
            # do dummy processing only
            self.filter_shift = 0.0
            for rtt in self.obs_rt_list:
                rtt.registerRtProcess('scale', factor=1.0)

        else:
            # get gaussian filtering parameters
            f0, sigma, dt = wo.gauss_filter
            gauss, self.filter_shift = gaussian_filter(f0, sigma, dt)
            # get kwin
            # for now just use one window
            kwin = wo.opdict['kwin']
            # register pre-processing of data here
            for rtt in self.obs_rt_list:
                rtt.registerRtProcess('convolve', conv_signal=gauss)
                rtt.registerRtProcess('sw_kurtosis', win=kwin)
                rtt.registerRtProcess('boxcar', width=50)
                rtt.registerRtProcess('differentiate')
                rtt.registerRtProcess('neg_to_zero')

    def updateData(self, tr_list):
        """
        Adds a list of traces (one per station) to the system
        """
        t_copy=0.0
        t_append=0.0
        t_append_proc=0.0
        t0_update=time.time()
        for tr in tr_list:
            if (self.dt!=tr.stats.delta):
                msg = 'Value of dt from options file %.2f does not match dt from data %2f'%(self.dt, tr.stats.delta)
                raise ValueError(msg)
            # pre-correct for filter_shift
            #tr.stats.starttime -= np.round(self.filter_shift/self.dt) * self.dt
            tr.stats.starttime -= self.filter_shift
            sta=tr.stats.station
            ista=self.sta_list.index(sta)
            # make dtype of data float if it is not already
            tr.data=tr.data.astype(np.float32)
            t0=time.time()
            pp_data = self.obs_rt_list[ista].append(tr, gap_overlap_check = True)
            t_append_proc += time.time() - t0
            if self.do_dump:
                filename='update_data_%s.dump'%sta
                f=open(filename,'w')
                dump(self.obs_rt_list[ista],f,-1)
                f.close()

            # loop over points
            for ip in xrange(self.npts):
                # do time shift and append
                t0=time.time()
                pp_data_tmp = pp_data.copy()
                t_copy += time.time() - t0
                pp_data_tmp.stats.starttime -= np.round(self.ttimes_matrix[ista,ip]/self.dt) * self.dt
                t0=time.time()
                self.point_rt_list[ip][ista].append(pp_data_tmp, gap_overlap_check = True)
                t_append += time.time() - t0

        logging.log(logging.INFO,
            "In updateData : %.2f s in process and %.2f s in data copy and %.2f s in append and a total of %.2f s" 
            % (t_append_proc, t_copy, t_append, time.time()-t0_update))

    def updateStacks(self):

        npts=self.npts
        
        for ip in xrange(npts):
            self._updateStack(ip)

    def _updateStack(self,ip):
        UTCDateTime.DEFAULT_PRECISION=2
        nsta=self.nsta
        # get common start-time for this point
        common_start=max([self.point_rt_list[ip][ista].stats.starttime \
                 for ista in xrange(nsta)])
        common_start=max(common_start,self.last_common_end_stack[ip])
        # get list of stations for which the end-time is compatible
        # with the common_start time and the safety buffer
        ista_ok=[ista for ista in xrange(nsta) if (self.point_rt_list[ip][ista].stats.endtime - common_start) > self.safety_margin]
        # get common end-time
        common_end=min([ self.point_rt_list[ip][ista].stats.endtime for ista in ista_ok])
        self.last_common_end_stack[ip]=common_end+self.dt
        # stack
        c_list=[]
        for ista in ista_ok:
            tr=self.point_rt_list[ip][ista].copy()
            tr.trim(common_start, common_end)
            c_list.append(np.array(tr.data[:]))
        tr_common=np.vstack(c_list)
        # prepare trace for passing up
        stack_data = np.sum(tr_common, axis=0)
        stats={'station':'STACK', 'npts':len(stack_data), 'delta':self.dt, \
                'starttime':common_start}
        tr=Trace(data=stack_data,header=stats)
        #import pdb; pdb.set_trace()
        # append to appropriate stack_list
        self.stack_list[ip].append(tr, gap_overlap_check = True)

    def updateMax(self):

        npts=self.npts
        nsta=self.nsta

        # now extract maximum etc from stacks
        # get common start-time for this point
        common_start=max([self.stack_list[ip].stats.starttime \
                    for ip in xrange(npts)])
        common_start=max(common_start,self.last_common_end_max)
        # get list of points for which the end-time is compatible
        # with the common_start time and the safety buffer
        ip_ok=[ip for ip in xrange(npts) if (self.stack_list[ip].stats.endtime - common_start) > self.safety_margin]
        common_end=min([self.stack_list[ip].stats.endtime for ip in ip_ok ])
        self.last_common_end_max=common_end+self.dt
        # stack
        c_list=[]
        for ip in ip_ok:
            tr=self.stack_list[ip].copy()
            tr.trim(common_start, common_end)
            c_list.append(tr.data)
        tr_common=np.vstack(c_list)
        # get maximum and the corresponding point
        max_data = np.max(tr_common, axis=0)
        argmax_data = np.argmax(tr_common, axis=0)
        # prepare traces for passing up
        # max
        stats={'station':'Max', 'npts':len(max_data), 'delta':self.dt, \
                'starttime':common_start}
        tr_max=Trace(data=max_data,header=stats)
        self.max_out.append(tr_max, gap_overlap_check = True)
        # x coordinate
        stats['station'] = 'xMax'
        tr_x=Trace(data=self.x[argmax_data],header=stats)
        self.x_out.append(tr_x, gap_overlap_check = True)
        # y coordinate
        stats['station'] = 'yMax'
        tr_y=Trace(data=self.y[argmax_data],header=stats)
        self.y_out.append(tr_y, gap_overlap_check = True)
        # z coordinate
        stats['station'] = 'zMax'
        tr_z=Trace(data=self.z[argmax_data],header=stats)
        self.z_out.append(tr_z, gap_overlap_check = True)







