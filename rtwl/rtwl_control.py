import logging
import pika
import time
from cPickle import dumps, loads
from rtwl_io import rtwlGetConfig, rtwlParseCommandLine, setupRabbitMQ
from synthetics import make_synthetic_data, generate_random_test_points


def rtwlStop(wo):
    connection, channel = setupRabbitMQ('CONTROL')
    sendPoisonPills(channel,wo)
    time.sleep(1)
    connection.close()
    
def rtwlStart(wo):
    """
    Starts rtwl.
    """
    connection, channel = setupRabbitMQ('CONTROL')

    if wo.run_offline:
        # Run in offline mode
        logging.log(logging.INFO," [C] Starting rtwl in offline mode")

        import glob,os
        from obspy.core import read
        
        if wo.is_syn :
            obs_list, ot, (x0,y0,z0) = make_synthetic_data(wo)
            generate_random_test_points(wo,loc0=(x0,y0,z0))

        # read data
        fnames=glob.glob(os.path.join(wo.data_dir, wo.opdict['data_glob']))
        obs_list=[]
        sta_list=[]
        for name in fnames:
            st=read(name)
            sta_list.append(st[0].stats.station)
            obs_list.append(st[0])
        nsta=len(sta_list)
    

        # split data files to simulate packets of real-time data
        obs_split=[]
        for obs in obs_list:
            split = obs / 3
            obs_split.append(split)
        ntr=len(obs_split[0])
        
        for itr in xrange(ntr):
            # publish data to "seiscomp" stream
            for ista in xrange(nsta):
                tr = obs_split[ista][itr]
                sta=tr.stats.station
                # sanity check for dt
                if (wo.opdict['dt']!=tr.stats.delta):
                    msg =\
                    'Value of dt from config %.2f does not match dt from data %2f'\
                    %(wo.opdict['dt'], tr.stats.delta)
                    raise ValueError(msg)
                # The message is just a pickled version of the trace
                message=dumps(tr,-1)
                channel.basic_publish(exchange='raw_data',
                            routing_key=sta,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
                tr_test=loads(message)
                logging.log(logging.INFO,
                            " [C] Sent %r:%r" % 
                            (sta, "New data (%d) for station %s"
                            %(itr,tr_test.stats.station)))

    else :
        # Run in true real-time mode
        raise NotImplementedError()
 
def sendPoisonPills(channel,wo):
    channel.basic_publish(exchange='info',
                            routing_key='',
                            body='STOP',
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
    for sta in wo.sta_list:
        channel.basic_publish(exchange='raw_data',
                            routing_key=sta,
                            body='STOP',
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
    logging.log(logging.INFO," [C] Sent poison pill")
      
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
        rtwlStop(wo) # stop

            