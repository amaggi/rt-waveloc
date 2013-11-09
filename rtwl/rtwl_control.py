import optparse
import logging
import pika
from cPickle import dumps, loads
from options import RtWavelocOptions
from rtwl_io import readConfig

def rtwlStart():
    """
    Starts rtwl. Configuration is read from 'rtwl.config' file.
    """
      
    config_file='rtwl.config'
    
    # read options into waveloc options objet
    wo=RtWavelocOptions()
    wo.opdict=readConfig(config_file)
    
    # set up rabbitmq
    connection = pika.BlockingConnection(pika.ConnectionParameters(
                        host='localhost'))
    channel = connection.channel()

    channel.exchange_declare(exchange='raw_data',
                         type='direct')
    
    if wo.run_offline:
        # Run in offline mode
        print "Starting rtwl in offline mode"
        import glob,os
        from obspy.core import read
        
        # read data
        fnames=glob.glob(os.path.join(wo.data_dir, wo.opdict['data_glob']))
        obs_list=[]
        for name in fnames:
            st=read(name)
            obs_list.append(st[0])
        nsta=len(obs_list)
    
        # use data to set dt in waveloc options
        dt=obs_list[0].stats.delta
        wo.opdict['dt'] = dt

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
                # The message is just a pickled version of the trace
                message=dumps(tr,-1)
                channel.basic_publish(exchange='raw_data',
                            routing_key=sta,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2,)
                            )
                tr_test=loads(message)
                print " [x] Sent %r:%r" % (sta, "New data (%d) for station %s"
                                                %(itr,tr_test.stats.station))
        
    
    else :
        # Run in true real-time mode
        raise NotImplementedError()
    
    connection.close()
    
if __name__=='__main__':

    # parse command line
    p=optparse.OptionParser()

    p.add_option('--start',action='store_true',help="start rtwl")
    p.add_option('--debug',action='store_true',help="turn on debugging output")

    (options,arguments)=p.parse_args()

    if options.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s : %(asctime)s : %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')

   

    if options.start:
            rtwlStart() # start process
            