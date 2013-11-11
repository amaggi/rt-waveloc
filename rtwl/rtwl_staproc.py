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
    def __init__(self,wo) :
        
        # basic parameters
        self.wo = wo
        self.sta_list = wo.sta_list
        self.max_length = self.wo.opdict['max_length']
        self.safety_margin = self.wo.opdict['safety_margin']
        self.dt = self.wo.opdict['dt']
        
        # real-time streams for processing
        self.rtt={}
        for sta in self.sta_list:
            self.rtt[sta] = RtTrace(max_length=self.max_length)
        self._register_preprocessing()
        
        
        # independent process (for parallel calculation)
        self.lock=multiprocessing.Lock()
        for sta in self.sta_list:
            p = multiprocessing.Process(
                                        name='proc_%s'%sta,
                                        target=self._do_proc,
                                        args=(sta,)
                                        )
            p.start()
        
    def _register_preprocessing(self):
        wo=self.wo
        
        # if this is a synthetic
        if wo.is_syn:
            # do dummy processing only
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
        connection, channel = _setupRabbitMQ()
   
        # bind to the raw data 
        result = channel.queue_declare(exclusive=True)
        queue_name = result.method.queue
       
        channel.queue_bind(exchange='raw_data', 
                                    queue=queue_name, 
                                    routing_key=sta)
        consumer_tag=channel.basic_consume(
                                    self._callback_proc,
                                    queue=queue_name,
                                    #no_ack=True
                                    )
        #print proc_name, consumer_tag
        channel.basic_qos(prefetch_count=1)
        try:
            channel.start_consuming()
        except UserWarning:
            logging.log(logging.INFO,"Received STOP signal from %s"%proc_name)       
            channel.basic_cancel(consumer_tag)

    def _callback_proc(self, ch, method, properties, body):
        if body=='STOP':
            # acknowledge
            ch.basic_ack(delivery_tag = method.delivery_tag)
            ch.stop_consuming()
            # send on to next exchange
            ch.basic_publish(exchange='proc_data',
                            routing_key=method.routing_key,
                            body=body,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            raise UserWarning
        else:
            # unpack data packet
            sta=method.routing_key
            tr=loads(body)
            
            # pre-correct for filter_shift
            tr.stats.starttime -= self.filter_shift
            
            # make dtype of data float if it is not already
            tr.data=tr.data.astype(np.float32)
            
            # append trace from message to real-time trace
            # this automatically triggers the rt processing
            pp_data = self.rtt[sta].append(tr, gap_overlap_check = True)
            
            # send the processed data on to the proc_data exchange
            message=dumps(pp_data,-1)
            ch.basic_publish(exchange='proc_data',
                            routing_key=method.routing_key,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
            logging.log(logging.INFO,
                            " [S] Sent %r:%r" % 
                            (method.routing_key, "Processed data for station %s"
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
    channel.exchange_declare(exchange='raw_data',exchange_type='topic')
    channel.exchange_declare(exchange='info',    exchange_type='fanout')
    channel.exchange_declare(exchange='proc_data',exchange_type='topic')
    
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
    rtwlStaProcessor(wo)
    
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
                      #no_ack=True
                      )
    
    try:
        channel.start_consuming()
    except UserWarning:
        logging.log(logging.INFO,"Received STOP signal from %s"%proc_name)
        
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
 


    
    
    
    
    
    
                        