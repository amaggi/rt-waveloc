import optparse
import logging
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
    
    
    
    else :
        # Run in true real-time mode
        raise NotImplementedError()
    
    
    
if __name__=='__main__':

    p=optparse.OptionParser()

    p.add_option('--start',action='store_true',help="start rtwl")
    p.add_option('--debug',action='store_true',help="turn on debugging output")

    (options,arguments)=p.parse_args()

    if options.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s : %(asctime)s : %(message)s')
    else:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s : %(asctime)s : %(message)s')

    if options.start:
            rtwlStart()