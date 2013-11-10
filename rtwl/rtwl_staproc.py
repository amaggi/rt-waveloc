import logging, pika,time
import multiprocessing
from cPickle import dumps, loads
from rtwl_io import rtwlGetConfig, rtwlParseCommandLine

class rtwlStaProcessor(object):
    def __init__(self,wo,sta) :
        self.wo = wo
        self.sta = sta
        self.connection, self.channel = _setupRabbitMQ()
        self.p = multiprocessing.Process(name='proc_%s'%sta,
                                       target=self._do_proc)
        self.p.start()
        
    def _do_proc(self):
        proc_name = multiprocessing.current_process().name
    
        # bind to the raw data 
        result = self.channel.queue_declare(exclusive=True)
        queue_name = result.method.queue
        print proc_name, queue_name
        self.channel.queue_bind(exchange='raw_data', 
                                    queue=queue_name, 
                                    routing_key=self.sta)
        consumer_tag=self.channel.basic_consume(
                                    self._callback_proc,
                                    queue=queue_name)
        print proc_name, consumer_tag
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
            tr=loads(body)
            print tr.stats.station
            ch.basic_ack(delivery_tag = method.delivery_tag)
        
def _setupRabbitMQ():
    # set up rabbitmq
    connection = pika.BlockingConnection(
                        pika.ConnectionParameters(
                        host='localhost'))
    channel = connection.channel()
    
    # set up exchanges for data and info
    channel.exchange_declare(exchange='raw_data',type='direct')
    channel.exchange_declare(exchange='info',    type='fanout')
    channel.exchange_declare(exchange='proc_data',type='direct')
    
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
 


    
    
    
    
    
    
                        