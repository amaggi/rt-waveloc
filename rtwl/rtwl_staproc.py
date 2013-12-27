import logging
import multiprocessing
import numpy as np
import am_rt_signal
from obspy.realtime import RtTrace
from am_signal import gaussian_filter
from cPickle import dumps, loads, dump

SIG_STOP = 'SIG_STOP'
#os.system('taskset -p 0xffff %d' % os.getpid())


###############
# stuff that needs doing while I still have 
# realtime functions that are not part of obspy
import obspy.realtime
rt_dict= obspy.realtime.rttrace.REALTIME_PROCESS_FUNCTIONS
rt_dict['neg_to_zero']=(am_rt_signal.neg_to_zero,0)
rt_dict['convolve']=(am_rt_signal.convolve,1)
rt_dict['sw_kurtosis']=(am_rt_signal.sw_kurtosis,1)
rt_dict['dx2']=(am_rt_signal.dx2,2)
###############

class rtwlStaProcessor(object):
    def __init__(self,wo, sta_q_dict, sta_lock_dict, proc_q_dict, proc_lock, 
                 do_dump=False) :
        
        # basic parameters
        self.wo = wo
        self.do_dump = do_dump
        self.sta_list = wo.sta_list
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        self.dt = self.wo.opdict['dt']
        self.q_dict = sta_q_dict
        self.lock_dict = sta_lock_dict
        self.proc_q_dict = proc_q_dict
        self.proc_lock = proc_lock
        
        # real-time streams for processing
        self.rtt={}
        for sta in self.sta_list:
            self.rtt[sta] = RtTrace(max_length=self.max_length)
        self._register_preprocessing()
        
        
        # independent processes (for parallel calculation)
        p_list=[]
        for sta in self.sta_list:
            p = multiprocessing.Process(
                                        name='staproc_%s'%sta,
                                        target=self._do_proc,
                                        args=(sta,)
                                        )
            p_list.append(p)
            p.start()
        
        # once they are all started, wait for them to finish before exiting
        for p in p_list:
            p.join()
                
    def _register_preprocessing(self):
        wo=self.wo
        
        # if this is a synthetic
        if wo.is_syn:
            # do dummy processing only
            self.filter_shift = 0.0
            for tr in self.rtt.values():
                tr.registerRtProcess('scale', factor=1.0)

        else:
            # get gaussian filtering parameters
            f0, sigma, dt = wo.gauss_filter
            gauss, self.filter_shift = gaussian_filter(f0, sigma, dt)
            # get kwin
            # for now just use one window
            kwin = wo.opdict['kwin']
            # register pre-processing of data here
            for tr in self.rtt.values():
                tr.registerRtProcess('convolve', conv_signal=gauss)
                tr.registerRtProcess('sw_kurtosis', win=kwin)
                tr.registerRtProcess('boxcar', width=50)
                tr.registerRtProcess('differentiate')
                tr.registerRtProcess('neg_to_zero')
            
    def _do_proc(self,sta):
        proc_name = multiprocessing.current_process().name
 
        #queue setup
        q = self.q_dict[sta]
        lock = self.lock_dict[sta]
        
        while True :
            msg = q.get()
            if msg == SIG_STOP:
                break
      
            else:
                # unpack data packet
                tr=loads(msg)
            
                # pre-correct for filter_shift
                tr.stats.starttime -= self.filter_shift
            
                # make dtype of data float if it is not already
                tr.data=tr.data.astype(np.float32)
            
                # append trace from message to real-time trace
                # this automatically triggers the rt processing
                with lock :
                    pp_data = self.rtt[sta].append(tr, gap_overlap_check = True)
                    logging.log(logging.INFO,
                    " [S] Proc %s processed data for station %s"%
                    (proc_name, pp_data.stats.station))

                    # if requested, dump rtt trace
                    if self.do_dump:
                        filename='staproc_%s.dump'%sta
                        f=open(filename,'w')
                        dump(self.rtt[sta],f,-1)
                        f.close()
                
                # send the processed data onwards to n_regions queues
                msg = dumps(pp_data, -1)
                with self.proc_lock :#
                    for proc_q in self.proc_q_dict.values() :
                        proc_q.put(msg)
                        #proc_q.get() # necessary until pointproc is working
                logging.log(logging.INFO,
                    " [S] Proc %s sent processed data for station %s to %d regions"%
                    (proc_name, pp_data.stats.station, len(self.proc_q_dict)))
                    
 
        # if you get here, you must have received the STOP signal
        logging.log(logging.INFO," [S] Proc %s received SIG_STOP signal."%proc_name) 
               


    
    
    
    
    
    
                        