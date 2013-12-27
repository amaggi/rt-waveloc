import logging
import glob
import os
from multiprocessing import Queue, Lock, Process
from cPickle import dumps, loads
from obspy.core import read
from rtwl_io import rtwlGetConfig
from synthetics import make_synthetic_data, generate_random_test_points
from rtwl_staproc import rtwlStaProcessor

# define SIG_STOP
SIG_STOP = 'SIG_STOP'
SIG_TTIMES_CHANGED = 'SIG_TTIMES_CHANGED'

class rtwlControler(object):
    """
    rtwlControler class
    """
    def __init__(self, wo, do_dump=False):
        self.wo = wo
        self.do_dump = do_dump
        self._setupQueues()
        self.staproc_p = Process(
                                name='staproc_all',
                                target=self._setupStaProc,
                                )
        self.staproc_p.start()
    
    def _setupQueues(self):
        # sets up Queues for rtwl on a single, parallel processing machine
        
        self.info_q_dict = {}
        for qname in ['info_top']:
            self.info_q_dict[qname] = Queue()
        
        self.sta_q_dict = {}  
        self.sta_lock_dict = {}      
        for sta in self.wo.sta_list:
            self.sta_q_dict[sta] = Queue()
            self.sta_lock_dict[sta] = Lock()
        
        # queues of processed data
        # one for each region to be treated by independent processes
        n_regions = self.wo.opdict['n_regions']
        self.proc_q_list = []
        for i in xrange(n_regions) :
            self.proc_q_list.append(Queue())
        self.proc_lock = Lock()
       
    def _setupStaProc(self):
        staProc = rtwlStaProcessor(self.wo, self.sta_q_dict, 
                                   self.sta_lock_dict, 
                                   self.proc_q_list, self.proc_lock, 
                                   self.do_dump)
    
    def rtwlStop(self):
        """
        Stop the real-time process by sending poisoned pills
        on all the queues.
        """
        q_dicts = [self.info_q_dict, self.sta_q_dict]
        # sends the poison pills to all queues
        for qdict in q_dicts :
            for name,q in qdict.iteritems() :
                q.put(SIG_STOP)
                logging.log(logging.INFO, 
                            " [C] rtwl_control sent %s on queue %s" %
                            (SIG_STOP, name))
                q.close()

        # wait for the station processor to finish            
        self.staproc_p.join()

          
    def rtwlStart(self):
        """
        Starts rtwl. Selects mode from information in rtwl.config file
        """
        wo = self.wo

        if wo.run_offline:
            # Run in offline mode
            logging.log(logging.INFO," [C] Starting rtwl in offline mode")
       
            if wo.is_syn :
                obs_list, ot, (x0,y0,z0) = make_synthetic_data(wo)
                generate_random_test_points(wo,loc0=(x0,y0,z0))

                for name,q in self.info_q_dict.iteritems():
                    q.put(SIG_TTIMES_CHANGED)
                logging.log(logging.INFO, 
                            " [C] rtwl_control sent %s on queue %s" %
                            (SIG_TTIMES_CHANGED, name))

            else:
                # read data
                fnames = glob.glob(os.path.join(wo.data_dir, 
                                                wo.opdict['data_glob']))
                obs_list = []
                sta_list = []
                for name in fnames:
                    st = read(name)
                    sta_list.append(st[0].stats.station)
                    obs_list.append(st[0])

            # regardless of how the obs_list is created
            # use it to set the number of stations                       
            nsta = len(obs_list)
    
            # split data files to simulate packets of real-time data
            obs_split = []
            for obs in obs_list:
                split = obs / 3
                obs_split.append(split)
            ntr = len(obs_split[0])
        
            for itr in xrange(ntr):
                # publish data to "seiscomp" stream
                for ista in xrange(nsta):
                    tr = obs_split[ista][itr]
                    sta = tr.stats.station
                    # sanity check for dt
                    if (wo.opdict['dt'] != tr.stats.delta):
                        msg =\
                        'Value of dt from config %.2f does not match dt from data %2f'\
                        %(wo.opdict['dt'], tr.stats.delta)
                        raise ValueError(msg)
                    # The message is just a pickled version of the trace
                    message=dumps(tr,-1)
                    self.sta_q_dict[sta].put(message)
                    tr_test=loads(message)
                    logging.log(logging.INFO,
                                " [C] Sent %r:%r" % 
                                (sta, "New data (%d) for station %s" %
                                (itr,tr_test.stats.station)))
    
        else :
            # Run in true real-time mode
            raise NotImplementedError()
 

if __name__=='__main__':

    logging.basicConfig(level=logging.INFO, 
                        format='%(levelname)s : %(asctime)s : %(message)s')

    # read config file
    wo=rtwlGetConfig('rtwl.config')

    controler = rtwlControler(wo)
    controler.rtwlStart()
    controler.rtwlStop()
            