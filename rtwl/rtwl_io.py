import numpy as np
import optparse
from options import RtWavelocOptions

"""
IO routines for rtwl
"""
def readConfig(filename):
    """
    Read rtwl configuration file rtwl.config

    :param filename: Full path to rtwl.config filename 
    :rtype: Python dictionary 
    :return: rtwl options dictionary
    """
    opdict={}

    # read the parameter file
    f=open(filename,'r')
    lines=f.readlines()
    f.close()

    # extract information into the dictionary
    for line in lines:
        words=line.split()
        if len(words)>=3 and words[1] == '=' :
            name=words[0]
            val=words[-1]
            opdict[name]=val

    _verifyParameters(opdict)

    return opdict

def _verifyParameters(p):
    """
    Private function to verify the validity of a parameter dictionary
    """

    # names of logical parameters
    logical_names=['syn','offline']
    
    # names of string parameters
    string_names=['base_path', 'outdir', 'datadir', 'data_glob', 'time_grid',
                    'sta_list']
   
    # names of floating point parameters
    float_names=['max_length','safety_margin','filt_f0','filt_sigma',
                'kwin','dt']
                
    # names of integer parameters
    int_names=['syn_npts']
    
    # cleanup types in dictionary
    try:
        # deal with the logical names
        for name in logical_names:
            val=p[name]
            if val=='.true.': 
                p[name]=True
            elif val=='.false.': 
                p[name]=False
            else : 
                raise UserWarning(
                'Parameter %s should be either .true. or .false., not %s'
                %(name,val))
        # deal with the float names
        for name in float_names:
            val=p[name]
            p[name]=np.float(val)
        # deal with the int names
        for name in int_names:
            val=p[name]
            p[name]=np.int(val)        
        # deal with the string names (just check they exist)
        for name in string_names:
            val=p[name]
    except KeyError:
        raise UserWarning('Missing parameter %s in PAR_FILE'%name)
        
def rtwlGetConfig(config_file):
    """
    Read rtwl configuration file rtwl.config 
    into an RtWavelocOptions object

    :param filename: Full path to rtwl.config filename 
    :rtype: RtWavelocOptions 
    :return: rtwl options
    """
    wo=RtWavelocOptions()
    wo.opdict=readConfig(config_file)
    return wo
    
def rtwlParseCommandLine():
    # parse command line
    p=optparse.OptionParser()

    p.add_option('--start',action='store_true',default=False, help="start rtwl")
    p.add_option('--stop',action='store_true',default=False, help="stop rtwl")
    p.add_option('--debug',action='store_true',default=False, help="turn on debugging output")

    (options,arguments)=p.parse_args()
    return options
    

        
    
    
#def setupRabbitMQ(proc_type=''):
#    # set up rabbitmq
#    connection = pika.BlockingConnection(
#                        pika.ConnectionParameters(
#                        host='localhost'))
#    channel = connection.channel()
#    
#    if proc_type == 'INFO':
#        channel.exchange_declare(exchange='info',exchange_type='fanout')        
#    elif proc_type == 'CONTROL':
#        channel.exchange_declare(exchange='raw_data',exchange_type='topic')
#        channel.exchange_declare(exchange='info',exchange_type='fanout')        
#    elif proc_type == 'STAPROC':
#        channel.exchange_declare(exchange='raw_data',exchange_type='topic')
#        channel.exchange_declare(exchange='proc_data',exchange_type='topic')
#    elif proc_type == 'DISTRIBUTE':
#        channel.exchange_declare(exchange='proc_data',exchange_type='topic')
#        channel.exchange_declare(exchange='points',exchange_type='topic')
#    elif proc_type == 'POINTPROC':
#        channel.exchange_declare(exchange='points',exchange_type='topic')
#        channel.exchange_declare(exchange='stacks',exchange_type='topic')
#        channel.exchange_declare(exchange='info',exchange_type='fanout')
#    elif proc_type == 'STACKPROC':
#        channel.exchange_declare(exchange='stacks',exchange_type='topic')
#    else:
#        channel.exchange_declare(exchange='raw_data',exchange_type='topic')
#        channel.exchange_declare(exchange='proc_data',exchange_type='topic')
#        channel.exchange_declare(exchange='points',exchange_type='topic')
#        channel.exchange_declare(exchange='stacks',exchange_type='topic')
##        channel.exchange_declare(exchange='info',exchange_type='fanout')
#        
#    
#    return connection, channel   