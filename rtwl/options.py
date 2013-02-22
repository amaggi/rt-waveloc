import os, glob, logging

class RtWavelocOptions(object):
    """
    Class containing the options that control operation of rt-waveloc.
    """

    def __init__(self):
        self.opdict={}

    def _verifyBasePath(self):
        """
        Verifies that the base_path option is correctly set.
        """
        if not self.opdict.has_key('base_path'):
            logging.info('No base_path set in options, getting base_path \
                    from $RTWAVELOC_PATH')
            base_path=os.getenv('RTWAVELOC_PATH')
            if not os.path.isdir(base_path):
                msg="Environment variable RTWAVELOC_PATH not set correctly."
                raise ValueError(msg)
            self.opdict['base_path'] = base_path

    def _verifyLibDir(self):
        """
        Verify existance of lib directory
        """
        self._verifyBasePath()
        base_path= self.opdict['base_path']
        lib_path = os.path.join(base_path, 'lib')
        if not os.path.isdir(lib_path):
            msg="Directory %s does not exist"%lib_path
            raise IOError(msg)

    def _verifyOutDir(self):
        """
        Verify existance of outdir in $RTWAVELOC_PATH/out or create it
        """
        self._verifyBasePath()
        base_path=self.opdict['base_path']

        if not self.opdict.has_key('outdir'):
            msg='outdir option not set'
            raise ValueError(msg)

        outdir=os.path.join(base_path,'out',self.opdict['outdir'])
        if not os.path.isdir(outdir):  
            os.makedirs(outdir)
        if not os.path.isdir(os.path.join(outdir,'ttimes')):  
            os.makedirs(os.path.join(outdir,'ttimes'))
        if not os.path.isdir(os.path.join(outdir,'fig')):  
            os.makedirs(os.path.join(outdir,'fig'))

    def _getLibDir_(self):
        self._verifyLibDir()
        base_path= self.opdict['base_path']
        return os.path.join(base_path, 'lib')

    def _getOutDir_(self):
        self._verifyOutDir()
        base_path= self.opdict['base_path']
        outdir=self.opdict['outdir']
        return os.path.join(base_path, 'out', outdir)

    def _getTtimesDir_(self):
        self._verifyOutDir()
        base_path= self.opdict['base_path']
        outdir=self.opdict['outdir']
        return os.path.join(base_path, 'out', outdir, 'ttimes')

    def _getFigDir_(self):
        self._verifyOutDir()
        base_path= self.opdict['base_path']
        outdir=self.opdict['outdir']
        return os.path.join(base_path, 'out', outdir, 'fig')


    def _getTtimesGlob_(self):
        return os.path.join(self.ttimes_dir, self.opdict['time_grid']+'*_ttimes.hdf5')

    def _getGridGlob_(self):
        return os.path.join(self.lib_dir, self.opdict['time_grid']+'*.hdf5')

    def _getGaussFilter_(self):
        return self.opdict['filt_f0'], self.opdict['filt_sigma'], self.opdict['dt']

    def _getIsSyn_(self):
        if self.opdict.has_key('syn') and self.opdict['syn'] == True :
            return True
        else:
            return False

    lib_dir = property(_getLibDir_)
    out_dir = property(_getOutDir_)
    ttimes_dir = property(_getTtimesDir_)
    fig_dir = property(_getFigDir_)
    ttimes_glob = property(_getTtimesGlob_)
    grid_glob = property(_getGridGlob_)
    gauss_filter = property(_getGaussFilter_)
    is_syn = property(_getIsSyn_)


    def verifyDirectories(self):
        self._verifyBasePath()
        self._verifyLibDir()
        self._verifyOutDir()
