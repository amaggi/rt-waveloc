import numpy as np

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
    string_names=['base_path', 'outdir', 'datadir', 'data_glob', 'time_grid']
   
    # names of floating point parameters
    float_names=['max_length','safety_margin','filt_f0','filt_sigma','kwin']
    
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
        # deal with the string names (just check they exist)
        for name in string_names:
            val=p[name]
    except KeyError:
        raise UserWarning('Missing parameter %s in PAR_FILE'%name)