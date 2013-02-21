import h5py, glob
import numpy as np
from obspy.core import Trace, UTCDateTime
from obspy.realtime import RtTrace

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


    def __init__(self,waveloc_options):
        """
        Initialize from a set of travel-times as hdf5 files
        """
        # initialize the travel-times
        #############################
        ttimes_fnames=glob.glob(waveloc_options.ttimes_glob)
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

        # initialize the RtTrace(s)
        ##########################
        max_length = waveloc_options.opdict['max_length']
        self.safety_margin = waveloc_options.opdict['safety_margin']

        # need a RtTrace per station 
        self.obs_rt_list=[RtTrace() for sta in self.sta_list]

        # register pre-processing of data here
        for rtt in self.obs_rt_list:
            rtt.registerRtProcess('scale', factor=1.0)

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

        # need a list of common start-times
        self.last_common_end_stack = [UTCDateTime(1970,1,1) for i in xrange(self.npts)]
        self.last_common_end_max = UTCDateTime(1970,1,1) 


    def updateData(self, tr_list):
        """
        Adds a list of traces (one per station) to the system
        """
        for tr in tr_list:
            self.dt=tr.stats.delta
            sta=tr.stats.station
            ista=self.sta_list.index(sta)
            pp_data = self.obs_rt_list[ista].append(tr, gap_overlap_check = True)
            # loop over points
            for ip in xrange(self.npts):
                # do time shift and append
                pp_data_tmp = pp_data.copy()
                pp_data_tmp.stats.starttime -= np.round(self.ttimes_matrix[ista,ip]/self.dt) * self.dt
                self.point_rt_list[ip][ista].append(pp_data_tmp, gap_overlap_check = True)

    def updateStacks(self):

        npts=self.npts
        nsta=self.nsta

        for ip in xrange(npts):
            # get common start-time for this point
            common_start=max([self.point_rt_list[ip][ista].stats.starttime \
                     for ista in xrange(nsta)])
            common_start=max(common_start,self.last_common_end_stack[ip])
            # get list of stations for which the end-time is compatible
            # with the common_start time and the safety buffer
            ista_ok=[]
            for ista in xrange(nsta):
                if (self.point_rt_list[ip][ista].stats.endtime - common_start) > self.safety_margin :
                        ista_ok.append(ista)
            # get common end-time
            common_end=min([ self.point_rt_list[ip][ista].stats.endtime for ista in ista_ok])
            self.last_common_end_stack[ip]=common_end+self.dt
            # stack
            c_list=[]
            for ista in ista_ok:
                tr=self.point_rt_list[ip][ista].copy()
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
            self.stack_list[ip].append(tr, gap_overlap_check = True)
            #stack_list[ip].plot()







