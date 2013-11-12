import logging, time, glob, h5py
import multiprocessing
from obspy.core import UTCDateTime, Trace
from obspy.realtime import RtTrace
from cPickle import dumps, loads
from rtwl_io import rtwlGetConfig, rtwlParseCommandLine, setupRabbitMQ
from plotting import plotMaxXYZ


import os
import numpy as np
#os.system('taskset -p 0xffff %d' % os.getpid())

class rtwlStacker(object):
    def __init__(self,wo):
    
        self.dt = wo.opdict['dt']
        self.max_length = wo.opdict['max_length']
        self.safety_margin = wo.opdict['safety_margin']

        # initialize the travel-times        
        ttimes_fnames=glob.glob(wo.ttimes_glob)
        
        # get basic lengths by reading the first file
        f=h5py.File(ttimes_fnames[0],'r')
    
        # copy the x, y, z data over
        self.x = np.array(f['x'][:])
        self.y = np.array(f['y'][:])
        self.z = np.array(f['z'][:])
        f.close()
        self.npts=len(self.x)
        #self.npts=70

        
        # need npts streams to store the point-stacks
        self.stack_dict={}
        for ip in xrange(self.npts):
            self.stack_dict[ip] = RtTrace(max_length=self.max_length)
        
        # register stack procesing here
        for rtt in self.stack_dict.values():
            # This is where we would add or lower weights if we wanted to
            rtt.registerRtProcess('scale', factor=1.0)
            
        # need 4 output streams (max, x, y, z)
        self.max_out = RtTrace()
        self.x_out = RtTrace()
        self.y_out = RtTrace()
        self.z_out = RtTrace()
        
        # need a common start-time        
        self.last_common_end_max = UTCDateTime(1970,1,1) 

        # register smoothing for max_out if not synthetic
        if not wo.is_syn:
            self.max_out.registerRtProcess('boxcar', width=50)

        connection, channel = setupRabbitMQ('STACKPROC')
        
        # create one queue
        result = channel.queue_declare(exclusive=True)
        queue_name = result.method.queue

        # bind to all stacks            
        channel.queue_bind(exchange='stacks', 
                                    queue=queue_name, 
                                    routing_key='#')

        consumer_tag=channel.basic_consume(
                                    self._callback_proc,
                                    queue=queue_name,
                                    #no_ack=True
                                    )
        
        channel.basic_qos(prefetch_count=1)
        channel.start_consuming()
        logging.log(logging.INFO,"Received STOP signal : stackproc")
            
    def _callback_proc(self, ch, method, properties, body):
        if body=='STOP' :
            
            ch.basic_ack(delivery_tag = method.delivery_tag)
            ch.stop_consuming()
            for tag in ch.consumer_tags:
                ch.basic_cancel(tag)

        else:
            
            ip=int(method.routing_key)
            
            # unpack data packet
            tr=loads(body)
            
            # add shifted trace
            endtime=self.stack_dict[ip].stats.endtime
            logging.log(logging.DEBUG," [S] %d = %s Adding data with startime %s to endtime %s"
                %(ip, tr.stats.station, tr.stats.starttime.isoformat(),endtime.isoformat()))
            self.stack_dict[ip].append(tr, gap_overlap_check = True)

            # update stack if possible
            self._updateStack()
            
            # acknowledge all ok
            ch.basic_ack(delivery_tag = method.delivery_tag)

    def _updateStack(self):
        
        UTCDateTime.DEFAULT_PRECISION=2
        
        npts=self.npts        
        
        # get common start-time for this point
        common_start=max([self.stack_dict[ip].stats.starttime \
                    for ip in xrange(npts)])
        common_start=max(common_start,self.last_common_end_max)
        
        # get list of points for which the end-time is compatible
        # with the common_start time and the safety buffer
        ip_ok=[ip for ip in xrange(npts) if (self.stack_dict[ip].stats.endtime - common_start) > self.safety_margin]
        logging.log(logging.DEBUG," [U] len(ip_ok) = %d < %d : %r"%(len(ip_ok),npts,ip_ok))
        
        # if all points are ok, then go ahead
        if len(ip_ok) == npts:
            common_end=min([self.stack_dict[ip].stats.endtime for ip in ip_ok ])
            logging.log(logging.INFO," [E] Stacking with starttime %s and endtime %s"
                %(common_start.isoformat(),common_end.isoformat()))
            self.last_common_end_max=common_end+self.dt
            # stack
            c_list=[]
            for ip in ip_ok:
                tr=self.stack_dict[ip].copy()
                tr.trim(common_start, common_end)
                c_list.append(tr.data)
            tr_common=np.vstack(c_list)
            
            # get maximum and the corresponding point
            max_data = np.max(tr_common, axis=0)
            argmax_data = np.argmax(tr_common, axis=0)
            
            # prepare traces for passing up
            # max
            stats={'station':'Max', 'npts':len(max_data), 'delta':self.dt, \
                'starttime':common_start}
            tr_max=Trace(data=max_data,header=stats)
            self.max_out.append(tr_max, gap_overlap_check = True)
            
            # x coordinate
            stats['station'] = 'xMax'
            tr_x=Trace(data=self.x[argmax_data],header=stats)
            self.x_out.append(tr_x, gap_overlap_check = True)
            
            # y coordinate
            stats['station'] = 'yMax'
            tr_y=Trace(data=self.y[argmax_data],header=stats)
            self.y_out.append(tr_y, gap_overlap_check = True)
            
            # z coordinate
            stats['station'] = 'zMax'
            tr_z=Trace(data=self.z[argmax_data],header=stats)
            self.z_out.append(tr_z, gap_overlap_check = True)

                
def rtwlStop(wo):
    connection, channel = setupRabbitMQ('INFO')
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
    
    migrator=rtwlStacker(wo)
    
    max_out=migrator.max_out
    x_out=migrator.x_out
    y_out=migrator.y_out
    z_out=migrator.z_out

    figname=os.path.join(wo.fig_dir,'synthetic_test_out_rt.png')
    plotMaxXYZ(max_out, x_out, y_out, z_out, figname)
    print "View output in file : %s"%figname
    


    
def receive_info():
    proc_name = multiprocessing.current_process().name
    connection, channel = setupRabbitMQ('INFO')

    # bind to the info fanout
    result = channel.queue_declare(exclusive=True)
    info_queue_name = result.method.queue
    channel.queue_bind(exchange='info', queue=info_queue_name)
    
    print " [+] Ready to receive info ..."
    
    consumer_tag=channel.basic_consume(callback_info,
                      queue=info_queue_name,
                      #no_ack=True
                      )
    
    channel.start_consuming()
    logging.log(logging.INFO,"Received UserWarning : %s"%proc_name)
    
  
def callback_info(ch, method, properties, body):
    
    if body=='STOP':
        logging.log(logging.INFO, "rtwl_pointproc received poison pill")
        ch.stop_consuming()
        for tag in ch.consumer_tags:
            ch.basic_cancel(tag)

    

if __name__=='__main__':

    # read config file
    wo=rtwlGetConfig('rtwl.config')
    
    # parse command line
    options=rtwlParseCommandLine()

    if options.debug:
        logging.basicConfig(
                #filename='rtwl_stackproc.log',
                level=logging.DEBUG, 
                format='%(levelname)s : %(asctime)s : %(message)s'
                )
    else:
        logging.basicConfig(
                #filename='rtwl_stackproc.log',
                level=logging.INFO, 
                format='%(levelname)s : %(asctime)s : %(message)s'
                )

    if options.start:          
        rtwlStart(wo) # start
            
    if options.stop:
        rtwlStop(wo)
 

