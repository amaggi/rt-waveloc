import logging 
import glob
import h5py
import time
import multiprocessing
import numpy as np
from obspy.core import UTCDateTime, Trace
from obspy.realtime import RtTrace
from cPickle import dumps, loads, dump

SIG_STOP = 'SIG_STOP'
SIG_TTIMES_CHANGED = 'SIG_TTIMES_CHANGED'

#os.system('taskset -p 0xffff %d' % os.getpid())

class rtwlPointStacker(object):
    def __init__(self, wo, proc_q_dict, info_q, do_dump=False):
    
        # create a lock for the ttimes matrix
        self.ttimes_lock = multiprocessing.Lock()
        
        self.wo = wo
        self.do_dump = do_dump
        self.dt = wo.opdict['dt']
        self.q_dict = proc_q_dict
        self.info_q = info_q
        
        # keepalive is True for timed processes
        # until it is set to false by a poison pill
        # on the info channel
        self.exit = multiprocessing.Event()
        
        # create locks for each region
        self.reg_locks = {}
        for key in self.q_dict.keys():
            self.reg_locks[key] = multiprocessing.Lock()
        
        # call _load_ttimes once to set up ttimes_matrix from existing files
        # if info receives an instruction that files have changed, then
        # _load_ttimes will be relaunched internally
        # this sets self.npts and self.nsta
        self._load_ttimes()
        
        # create a process for listening to info
        p_info = multiprocessing.Process(
                            name='info_monitor',
                            target=self._receive_info, 
                            )
        p_info.start()          



        # n_regions independent process for processing regions of points
        # note : prepare processors for all regions in config
        # note : so long as there are no incoming data, none will be distributed
        #        distribution itself happens with a lock on ttimes_matrix
        #        and so should not happen while ttimes_matrix is being reloaded
        self.p_list = []
        for reg in self.q_dict.keys() :
            p = multiprocessing.Process(
                            name="distrib_%s"%reg,
                            target=self._do_distribute, 
                            args=(reg,)
                            )
            self.p_list.append(p)
            p.start()  
            p = multiprocessing.Process(
                            name="stack_%s"%reg,
                            target=self._do_pointstack, 
                            args=(reg,)
                            )
            #p_list.append(p)
            p.start()  
        
        # wait for the info_monitor process to finish
        p_info.join()
        # wait for the region processors to finish
        for p in self.p_list :
            p.join()
        # send the exit signal to the time-based processes
        time.sleep(10)
        self.exit.set()
        
    def _split_into_regions(self):
        n_regions = self.wo.opdict['n_regions']
        self.points_dict = {}
        
        regs = self.q_dict.keys()
        p_list_split = np.array_split(np.arange(self.npts), n_regions)
        for i in xrange(n_regions) :
            self.points_dict[regs[i]] = p_list_split[i]

    def _initialize_rt_memory(self):
        
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        
        mgr = multiprocessing.Manager()       
        self.test_data = mgr.dict()
        for reg in self.q_dict.keys():
            self.test_data[reg] = UTCDateTime(1970,1,1)

        logging.log(logging.INFO,
                    " [T] INITIALIZED TEST DATA : %s"%
                    (UTCDateTime(1970,1,1).isoformat()))
        
        self.last_common_end_stack = {}
        for ip in xrange(self.npts):
            self.last_common_end_stack[ip] = UTCDateTime(1970,1,1)
        
        # need nsta streams for each point we test (nsta x npts)
        # for shifted waveforms
        self.point_rt_list=[[RtTrace(max_length=self.max_length) \
                for ista in xrange(self.nsta)] for ip in xrange(self.npts)]

        # register processing of point-streams here
        for sta_list in self.point_rt_list:
            for rtt in sta_list:
                # This is where we would scale for distance (given pre-calculated
                # distances from each point to every station)
                rtt.registerRtProcess('scale', factor=1.0)

        
    def _load_ttimes(self):
        
        # initialize the travel-times 
        ttimes_fnames=glob.glob(self.wo.ttimes_glob)
        
        with self.ttimes_lock :
       
            # get basic lengths by reading the first file
            f=h5py.File(ttimes_fnames[0],'r')
        
    
            # copy the x, y, z data over
            self.x = np.array(f['x'][:])
            self.y = np.array(f['y'][:])
            self.z = np.array(f['z'][:])
            f.close()
        
            # read the files
            ttimes_list = []
            self.sta_list = []
            for fname in ttimes_fnames:
                f = h5py.File(fname,'r')
                # update the list of ttimes
                ttimes_list.append(np.array(f['ttimes']))
                sta = f['ttimes'].attrs['station']
                f.close()
                # update the list of station names
                self.sta_list.append(sta)
        
            # stack the ttimes into a numpy array
            self.ttimes_matrix = np.vstack(ttimes_list)
            (self.nsta,self.npts) = self.ttimes_matrix.shape
        
            # acquire all the regional locks
            for lock in self.reg_locks.values():
                lock.acquire()
                
            # split the points into regions for pproc
            self._split_into_regions()
            
            # re-initialize memory for real-time stacks etc.
            self._initialize_rt_memory()
            
            # release all the regional locks
            for lock in self.reg_locks.values() :
                lock.release()
            
            # if do_dump, then dump ttimes_matrix to file for debugging
            if self.do_dump:
                filename='pointproc_ttimes.dump'
                f=open(filename,'w')
                dump(self.ttimes_matrix,f,-1)
                f.close()
        
        
    def _do_distribute(self,reg):
        proc_name = multiprocessing.current_process().name
        
        # queue setup
        q = self.q_dict[reg]

        while True :
            msg = q.get()
            if msg == SIG_STOP:
                break
            else:
                tr_orig=loads(msg)
                with self.reg_locks[reg] :
                    points = self.points_dict[reg]
                npts = len(points)
                sta = tr_orig.stats.station
                logging.log(logging.INFO,
                    " [P] Proc %s received data for %s (%d points)."%
                    (proc_name,sta,npts))
                ista = self.sta_list.index(sta)

                for ip in points:
                    # do shift
                    tr = loads(msg) # reload from message each time
                    with self.ttimes_lock :
                        tr.stats.starttime -= \
                            np.round(self.ttimes_matrix[ista][ip]/self.dt) * \
                            self.dt
                    # add shifted trace
                    with self.reg_locks[reg]:
                        self.point_rt_list[ip][ista].append(tr, 
                                        gap_overlap_check = True
                                        )
                        self.test_data[reg] = UTCDateTime(2020,1,1)
                            #self.point_rt_list[ip][ista].stats.endtime
                        if ista==0 :
                            logging.log(logging.INFO,
                            " [P] Proc %s point %d sta %s (%s-%s)."%
                            (proc_name,ip, sta,
                            self.point_rt_list[ip][ista].stats.starttime.isoformat(),
                            self.point_rt_list[ip][ista].stats.endtime.isoformat(),                            
                            ))
                            logging.log(logging.INFO,
                            " [T] Proc %s test_data %s."%
                            (proc_name,self.test_data[reg].isoformat()))
                        
                        if self.do_dump:
                            if ip==0 and ista==0 :
                                f=open('pointproc_point00.dump','w')
                                dump(self.point_rt_list[ip][ista], f, -1)
                                f.close()
                    
                                      
 
        # if you get here, you must have received SIG_STOP
        logging.log(logging.INFO," [P] Proc %s received SIG_STOP signal."%
            proc_name) 
        

    def _do_pointstack(self,reg):
        proc_name = multiprocessing.current_process().name

        while not self.exit.is_set() :
            time.sleep(10)
            with self.reg_locks[reg] :
                points = self.points_dict[reg]
            for ip in points :
                logging.log(logging.INFO, " [U] Proc %s updating point %d"%
                        (proc_name,ip))
                self._updateStack(ip,reg,self.reg_locks[reg])

        # if get here then exit is set
        logging.log(logging.INFO, " [U] Proc %s exiting."%
                    (proc_name))

    def _updateStack(self,ip,reg, lock):
        proc_name = multiprocessing.current_process().name
        UTCDateTime.DEFAULT_PRECISION=2
        nsta=self.nsta
        
        # always call this with the appropriate reg_lock
        with lock:
            logging.log(logging.INFO, " [U] Proc %s on point %d station %s : %s"%
                    (proc_name, ip, self.sta_list[0],
                    self.point_rt_list[ip][0].stats.starttime.isoformat()))                       
            logging.log(logging.INFO, " [T] Proc %s on point %d test_data : %s"%
                    (proc_name, ip, 
                    self.test_data[reg].isoformat()))   
            # get common start-time for this point
            common_start=max([self.point_rt_list[ip][ista].stats.starttime \
                 for ista in xrange(nsta)])
            logging.log(logging.INFO, " [U] Proc %s on point %d : trace common start %s"%
                    (proc_name, ip, common_start.isoformat()))                 
            common_start=max(common_start,self.last_common_end_stack[ip])
            logging.log(logging.INFO, " [U] Proc %s on point %d : full common start %s"%
                    (proc_name, ip, common_start.isoformat()))
            # get list of stations for which the end-time is compatible
            # with the common_start time and the safety buffer
            ista_ok=[ista for ista in xrange(nsta) if 
                (self.point_rt_list[ip][ista].stats.endtime - common_start) 
                > self.safety_margin]
            logging.log(logging.INFO, " [U] Proc %s on point %d has %d ok sta."%
                    (proc_name, ip, len(ista_ok)))

                
            # if got data for all stations then stack (TODO : make this more robust)
            if len(ista_ok)==self.nsta:
            
                # get common end-time
                common_end=min([ self.point_rt_list[ip][ista].stats.endtime for ista in ista_ok])
                self.last_common_end_stack[ip]=common_end+self.dt
            
                # prepare stack
                c_list=[]
                for ista in ista_ok:
                    tr=self.point_rt_list[ip][ista].copy()
                    tr.trim(common_start, common_end)
                    c_list.append(np.array(tr.data[:]))
                tr_common=np.vstack(c_list)
            
                # do stack
                stack_data = np.sum(tr_common, axis=0)
            
                # prepare trace for passing up
                stats={'station':'%d'%ip, 'npts':len(stack_data), 'delta':self.dt, \
                    'starttime':common_start}
                tr=Trace(data=stack_data,header=stats)
            
                logging.log(logging.INFO,
                            " [U] Stacked data for point %s : %s - %s"
                            %(tr.stats.station, 
                            tr.stats.starttime.isoformat(), 
                            tr.stats.endtime.isoformat()))
        

    def _receive_info(self):
        proc_name = multiprocessing.current_process().name
        q = self.info_q

        logging.log(logging.INFO, " [I] Proc %s ready to receive info ..."%
                proc_name)
        
        while True :
            msg = q.get()
            logging.log(logging.INFO, " [I] Proc %s received %s"%
                    (proc_name, msg))
            if msg == SIG_STOP :
                break
            elif msg == SIG_TTIMES_CHANGED :
                self._load_ttimes()
                logging.log(logging.INFO, " [I] Proc %s reloaded ttimes"%
                            proc_name)
            else :
               logging.log(logging.INFO, " [I] Proc %s took no action"%
                            proc_name)
 
        # you will only get here after a STOP signal has been received
        logging.log(logging.INFO, " [I] Proc %s received SIG_STOP"%
                    proc_name)


                            

 

    
    
    
    
    
    
                        