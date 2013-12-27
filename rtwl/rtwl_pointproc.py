import logging, pika,time, glob, h5py
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
        p_list = []
        for reg in self.q_dict.keys() :
            p = multiprocessing.Process(
                            name=reg,
                            target=self._do_distribute_and_stack, 
                            args=(reg,)
                            )
            p_list.append(p)
            p.start()  
        
        # wait for the info_monitor process to finish
        p_info.join()
        # wait for the region processors to finish
        for p in p_list :
            p.join()

    def _split_into_regions(self):
        n_regions = self.wo.opdict['n_regions']
        self.points_dict = {}
        
        regs = self.q_dict.keys()
        p_list_split = np.array_split(np.arange(self.npts), n_regions)
        for i in xrange(n_regions) :
            self.points_dict[regs[i]] = p_list_split[i]

        
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
            self.sta_list=[]
            for fname in ttimes_fnames:
                f=h5py.File(fname,'r')
                # update the list of ttimes
                ttimes_list.append(np.array(f['ttimes']))
                sta=f['ttimes'].attrs['station']
                f.close()
                # update the list of station names
                self.sta_list.append(sta)
        
            # stack the ttimes into a numpy array
            self.ttimes_matrix=np.vstack(ttimes_list)
            (self.nsta,self.npts) = self.ttimes_matrix.shape
        
            self._split_into_regions()
            
            # if do_dump, then dump ttimes_matrix to file for debugging
            if self.do_dump:
                filename='pointproc_ttimes.dump'
                f=open(filename,'w')
                dump(self.ttimes_matrix,f,-1)
                f.close()
        
        
    def _do_distribute_and_stack(self,reg):
        proc_name = multiprocessing.current_process().name
        
        # queue setup
        q = self.q_dict[reg]

        while True :
            msg = q.get()
            if msg == SIG_STOP:
                break
            else:
                tr=loads(msg)
                points = self.points_dict[reg]
                logging.log(logging.INFO,
                    " [P] Proc %s received data for %s (%d points)."%
                    (proc_name,tr.stats.station,len(points)))
                
                
 
        # if you get here, you must have received SIG_STOP
        logging.log(logging.INFO," [P] Proc %s received SIG_STOP signal."%proc_name) 
        
 
#        # create one queue
#        result = channel.queue_declare(exclusive=True)
#        queue_name = result.method.queue
#
#        # bind to all stations        
#        channel.queue_bind(exchange='proc_data', 
#                                    queue=queue_name, 
#                                    routing_key=sta)
#                                    
#        consumer_tag=channel.basic_consume(
#                                    self._callback_distribute,
#                                    queue=queue_name,
#                                    #no_ack=True
#                                    )
#        
#        channel.basic_qos(prefetch_count=1)
#        channel.start_consuming()
#        logging.log(logging.INFO,"Received STOP signal : %s"%proc_name)
#
#    def _callback_distribute(self, ch, method, properties, body):
#        if body=='STOP' :
#            sta=method.routing_key
#            ch.basic_ack(delivery_tag = method.delivery_tag)
#            # pass on to next exchange
#            for ip in xrange(self.npts):
#                ch.basic_publish(exchange='points',
#                            routing_key='%s.%d'%(sta,ip),
#                            body='STOP',
#                            properties=pika.BasicProperties(delivery_mode=2,)
#                            )
#            ch.stop_consuming()
#            for tag in ch.consumer_tags:
#                ch.basic_cancel(tag)
#        else:
#            # unpack data packet 
#            tr=loads(body)
#            
#            sta=method.routing_key
#            # get info to access ttimes_matrix
#            # so long as it is not being modified right now
#            with self.ttimes_lock:
#                npts = self.npts
#                ista = self.sta_list.index(sta)
#
#                for ip in xrange(npts):
#                    # do shift
#                    tr.stats.starttime -= np.round(self.ttimes_matrix[ista][ip]/self.dt) * self.dt
#                    ch.basic_publish(exchange='points',
#                            routing_key='%s.%d'%(sta,ip),
#                            body=dumps(tr,-1),
#                            properties=pika.BasicProperties(delivery_mode=2,)
#                            )
#                
#            logging.log(logging.DEBUG,
#                            " [D] Sent %r" % 
#                            ("Distributed data for station %s"%sta))
#            # acknowledge all ok            
#            ch.basic_ack(delivery_tag = method.delivery_tag)

    def _receive_info(self):
        proc_name = multiprocessing.current_process().name
        q = self.info_q

        logging.log(logging.INFO, " [I] Proc %s ready to receive info ..."%
                proc_name)
        
        while True :
            msg = q.get()
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
                    
                
        
class rtwlPointProcessor(object):
    def __init__(self,wo,sta_list,npts, do_dump = False) :
        
        # basic parameters
        self.point_lock = multiprocessing.Lock()
        
        self.do_dump = do_dump
        self.wo = wo
        self.sta_list=sta_list
        self.nsta = len(sta_list)
        self.npts = npts
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        self.dt = self.wo.opdict['dt']
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


        # rt streams must be indexed by station name
        self.pt_sta_dict = {}
        for sta in sta_list:
            self.pt_sta_dict[sta] = RtTrace(max_length=self.max_length)
               
        
        # independent process (for parallel calculation)
        # get number of processes automatically somehow (config file ?)
        # for now set to 10
        nprocs = 10
        for i in xrange(nprocs):
            p = multiprocessing.Process(
                                        name='proc_%d'%i,
                                        target=self._do_proc,
                                        )
            p.start()
        
            

    def _callback_proc(self, ch, method, properties, body):
        if body=='STOP' :
            sta = method.routing_key.split('.')[0]
            ip = int(method.routing_key.split('.')[1])
            
            ch.basic_ack(delivery_tag = method.delivery_tag)
            
            # pass on to next exchange
            ch.basic_publish(exchange='stacks',
                            routing_key='%d'%ip,
                            body='STOP',
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            ch.stop_consuming()
            for tag in ch.consumer_tags:
                ch.basic_cancel(tag)
        else:
            
            sta = method.routing_key.split('.')[0]
            ista=self.sta_list.index(sta)
            ip = int(method.routing_key.split('.')[1])

            # unpack data packet
            tr=loads(body)
            
            # add shifted trace
            with self.point_lock:
                self.point_rt_list[ip][ista].append(tr, 
                                        gap_overlap_check = True
                                        )
                if self.do_dump:
                    if ip==0 and ista==0 :
                        f=open('pointproc_point00.dump','w')
                        dump(self.point_rt_list[ip][ista], f, -1)
                        f.close()

            # update stack if possible
            self._updateStack(ip,ch)
            
            # acknowledge all ok
            ch.basic_ack(delivery_tag = method.delivery_tag)


    def _updateStack(self,ip,ch):
        
        UTCDateTime.DEFAULT_PRECISION=2
        
        nsta=self.nsta
        # get common start-time for this point
        with self.point_lock :
            common_start=max([self.point_rt_list[ip][ista].stats.starttime \
                 for ista in xrange(nsta)])
            common_start=max(common_start,self.last_common_end_stack[ip])
            # get list of stations for which the end-time is compatible
            # with the common_start time and the safety buffer
            ista_ok=[ista for ista in xrange(nsta) if 
                (self.point_rt_list[ip][ista].stats.endtime - common_start) 
                > self.safety_margin]
        
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
            
                # send the stack on to the stacks exchange
                message=dumps(tr,-1)
                ch.basic_publish(exchange='stacks',
                            routing_key='%d'%ip,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
                logging.log(logging.INFO,
                            " [P] Sent %r:%r" % 
                            ("%d"%ip, "Stacked data for point %s : %s - %s"
                            %(tr.stats.station, 
                            tr.stats.starttime.isoformat(), 
                            tr.stats.endtime.isoformat())))
                            

 

    
    
    
    
    
    
                        