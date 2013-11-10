import logging, pika,time
import multiprocessing
import numpy as np
import am_rt_signal
from obspy.realtime import RtTrace
from am_signal import gaussian_filter
from cPickle import dumps, loads
from rtwl_io import rtwlGetConfig, rtwlParseCommandLine

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
    def __init__(self,wo,sta) :
        
        # basic parameters
        self.wo = wo
        self.sta = sta
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        self.dt = self.wo.opdict['dt']
        
        # real-time stream for processing
        self.rtt = RtTrace(max_length=self.max_length+self.safety_margin)
        self._register_preprocessing()
        
        # queue setup
        self.connection, self.channel = _setupRabbitMQ()
        
        # independent process (for parallel calculation)
        self.p = multiprocessing.Process(name='proc_%s'%sta,
                                       target=self._do_proc)
        self.p.start()
        
    def _register_preprocessing(self):
        wo=self.wo
        
        # if this is a synthetic
        if wo.is_syn:
            # do dummy processing only
            self.rtt.registerRtProcess('scale', factor=1.0)

        else:
            # get gaussian filtering parameters
            f0, sigma, dt = wo.gauss_filter
            gauss, self.filter_shift = gaussian_filter(f0, sigma, dt)
            # get kwin
            # for now just use one window
            kwin = wo.opdict['kwin']
            # register pre-processing of data here
            self.rtt.registerRtProcess('convolve', conv_signal=gauss)
            self.rtt.registerRtProcess('sw_kurtosis', win=kwin)
            self.rtt.registerRtProcess('boxcar', width=50)
            self.rtt.registerRtProcess('differentiate')
            self.rtt.registerRtProcess('neg_to_zero')
            
    def _do_proc(self):
        proc_name = multiprocessing.current_process().name
    
        # bind to the raw data 
        result = self.channel.queue_declare(exclusive=True)
        queue_name = result.method.queue
        #print proc_name, queue_name
        self.channel.queue_bind(exchange='raw_data', 
                                    queue=queue_name, 
                                    routing_key=self.sta)
        consumer_tag=self.channel.basic_consume(
                                    self._callback_proc,
                                    queue=queue_name)
        #print proc_name, consumer_tag
        self.channel.basic_qos(prefetch_count=1)
        try:
            self.channel.start_consuming()
        except UserWarning:
            logging.log(logging.INFO,"Received UserWarning from %s"%proc_name)       
            self.channel.basic_cancel(consumer_tag)

    def _callback_proc(self, ch, method, properties, body):
        if body=='STOP':
            ch.basic_ack(delivery_tag = method.delivery_tag)
            raise UserWarning
        else:
            # unpack data packet
            tr=loads(body)
            
            # pre-correct for filter_shift
            tr.stats.starttime -= self.filter_shift
            
            # make dtype of data float if it is not already
            tr.data=tr.data.astype(np.float32)
            
            # append trace from message to real-time trace
            # this automatically triggers the rt processing
            pp_data = self.rtt.append(tr, gap_overlap_check = True)
            
            # send the processed data on to the proc_data exchange
            message=dumps(pp_data,-1)
            self.channel.basic_publish(exchange='proc_data',
                            routing_key=self.sta,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            logging.log(logging.INFO,
                            " [S] Sent %r:%r" % 
                            (self.sta, "Processed data for station %s"
                            %(pp_data.stats.station)))
            
            # signal to the raw_data exchange that have finished with data
            ch.basic_ack(delivery_tag = method.delivery_tag)
        
def _setupRabbitMQ():
    # set up rabbitmq
    connection = pika.BlockingConnection(
                        pika.ConnectionParameters(
                        host='localhost'))
    channel = connection.channel()
    
    # set up exchanges for data and info
    channel.exchange_declare(exchange='raw_data',exchange_type='direct')
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
    
    # set up processes to process data
    p_list=[]
    for sta in wo.sta_list:
        p=rtwlStaProcessor(wo,sta)
        p_list.append(p)
    
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
        
        channel.basic_cancel(consumer_tag)
    
  
def callback_info(ch, method, properties, body):
    
    if body=='STOP':
        logging.log(logging.INFO, "rtwl_staproc received poison pill")
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
 


    
    
    
    
    
    
                        