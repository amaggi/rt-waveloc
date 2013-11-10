import logging, pika,time, glob, h5py
import multiprocessing
import numpy as np
from obspy.core import UTCDateTime, Trace
from obspy.realtime import RtTrace
from cPickle import dumps, loads
from rtwl_io import rtwlGetConfig, rtwlParseCommandLine

class rtwlPointStacker(object):
    def __init__(self,wo):
    
        # initialize the travel-times        
        ttimes_fnames=glob.glob(wo.ttimes_glob)
        
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
        
        # create a processor for each point
#        for ip in xrange(self.npts):
        for ip in xrange(10):
            p_times=self.ttimes_matrix[:,ip]
            rtwlPointProcessor(wo,self.sta_list,p_times,ip)
        
        
class rtwlPointProcessor(object):
    def __init__(self,wo,sta_list,p_times,ip) :
        
        # basic parameters
        self.wo = wo
        self.ip = ip
        self.sta_list=sta_list
        self.nsta=len(sta_list)
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        self.dt = self.wo.opdict['dt']
        self.last_common_end_stack=UTCDateTime(1970,1,1)
        
        # Traveltimes and rt streams must be indexed by station name
        self.tt_dict = {}
        self.pt_sta_dict = {}
        for i in xrange(self.nsta):
            self.tt_dict[sta_list[i]] = p_times[i]
            self.pt_sta_dict[sta_list[i]] = \
                    RtTrace(max_length=self.max_length)
               
        # real-time stream for stacked stream
        self.rt_stack = RtTrace(max_length=self.max_length)
       
        # queue setup
        self.connection, self.channel = _setupRabbitMQ()
        
        # independent process (for parallel calculation)
        self.p = multiprocessing.Process(name='proc_%d'%ip,
                                       target=self._do_proc)
        self.p.start()
        
            
    def _do_proc(self):
        proc_name = multiprocessing.current_process().name
    
        # create one queue
        result = self.channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        # bind to all stations
        for sta in self.sta_list:            
            self.channel.queue_bind(exchange='proc_data', 
                                    queue=queue_name, 
                                    routing_key=sta)
                                    
        consumer_tag=self.channel.basic_consume(
                                    self._callback_proc,
                                    queue=queue_name,
                                    no_ack=True)
        
        self.channel.basic_qos(prefetch_count=1)
        try:
            self.channel.start_consuming()
        except UserWarning:
            logging.log(logging.INFO,"Received UserWarning from %s"%proc_name)
            self.channel.basic_cancel(consumer_tag)

    def _callback_proc(self, ch, method, properties, body):
        if body=='STOP' :
            self.channel.stop_consuming()
            # pass on to next exchange
            self.channel.basic_publish(exchange='stacks',
                            routing_key='%d'%self.ip,
                            body='STOP_%d'%self.ip,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            raise UserWarning
        else:
            # unpack data packet
            tr=loads(body)
            sta=tr.stats.station
            
            # do shift
            tr.stats.starttime -= np.round(self.tt_dict[sta]/self.dt) * self.dt
            
            # add shifted trace
            self.pt_sta_dict[sta].append(tr, gap_overlap_check = True)
            
            # update stack if possible
            self._updateStack()

    def _updateStack(self):
        
        UTCDateTime.DEFAULT_PRECISION=2
        
        # get common start-time for this point
        common_start=max(val.stats.starttime for val in self.pt_sta_dict.values())
        common_start=max(common_start,self.last_common_end_stack)
        
        # get list of stations for which the end-time is compatible
        # with the common_start time and the safety buffer
        sta_ok=[sta for sta in self.sta_list if 
                (self.pt_sta_dict[sta].stats.endtime - common_start) 
                > self.safety_margin]
        
        # if got data for all stations then stack (TODO : make this more robust)
        if len(sta_ok)==self.nsta:
            
            # get common end-time
            common_end=min([ self.pt_sta_dict[sta].stats.endtime for sta in sta_ok])
            self.last_common_end_stack=common_end+self.dt
            
            # prepare stack
            c_list=[]
            for sta in sta_ok:
                tr=self.pt_sta_dict[sta].copy()
                tr.trim(common_start, common_end)
                c_list.append(np.array(tr.data[:]))
            tr_common=np.vstack(c_list)
            
            # do stack
            stack_data = np.sum(tr_common, axis=0)
            
            # prepare trace for passing up
            stats={'station':'%d'%self.ip, 'npts':len(stack_data), 'delta':self.dt, \
                'starttime':common_start}
            tr=Trace(data=stack_data,header=stats)
            
            # send the stack on to the stacks exchange
            message=dumps(tr,-1)
            self.channel.basic_publish(exchange='stacks',
                            routing_key='%d'%self.ip,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            logging.log(logging.INFO,
                            " [P] Sent %r:%r" % 
                            ("%d"%self.ip, "Stacked data for point %s"
                            %(tr.stats.station)))
                            
def _setupRabbitMQ():
    # set up rabbitmq
    connection = pika.BlockingConnection(
                        pika.ConnectionParameters(
                        host='localhost'))
    channel = connection.channel()
    
    # set up exchanges for data and info
    channel.exchange_declare(exchange='stacks',exchange_type='direct')
    channel.exchange_declare(exchange='info',    exchange_type='fanout')
    channel.exchange_declare(exchange='proc_data',exchange_type='direct')
    
    return connection, channel   
 
def rtwlStop(wo):
    connection, channel = _setupRabbitMQ()
    #sendPoisonPills(channel,wo)
    time.sleep(4)
    connection.close()
       
def rtwlStart(wo):
    """
    Starts processing.
    """

    # set up process to listen to info
    p_info = multiprocessing.Process(name='receive_info',target=receive_info)                     
    p_info.start()
    
    rtwlPointStacker(wo)
    


    
def receive_info():
    proc_name = multiprocessing.current_process().name
    connection, channel = _setupRabbitMQ()

    # bind to the info fanout
    result = channel.queue_declare(exclusive=True)
    info_queue_name = result.method.queue
    channel.queue_bind(exchange='info', queue=info_queue_name)
    
    print " [+] Ready to receive info ..."
    
    consumer_tag=channel.basic_consume(callback_info,
                      queue=info_queue_name,
                      no_ack=True)
    
    try:
        channel.start_consuming()
    except UserWarning:
        logging.log(logging.INFO,"Received UserWarning from %s"%proc_name)
        channel.stop_consuming()
        channel.basic_cancel(consumer_tag)
    
  
def callback_info(ch, method, properties, body):
    
    if body=='STOP':
        logging.log(logging.INFO, "rtwl_pointproc received poison pill")
        raise UserWarning


    
if __name__=='__main__':

    # read config file
    wo=rtwlGetConfig('rtwl.config')
    
    # parse command line
    options=rtwlParseCommandLine()

    if options.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s : %(asctime)s : %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')
    

    if options.start:          
        rtwlStart(wo) # start
            
    if options.stop:
        rtwlStop(wo)
 


    
    
    
    
    
    
                        