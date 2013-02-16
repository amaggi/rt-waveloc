import os, glob, logging

class RtWavelocOptions(object):
    """
    Class containing the options that control operation of rt-waveloc.
    """

    def __init__(self):
        self.opdict={}

    def verify_base_path(self):
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

    def verify_lib_dir(self):
        """
        Verify existance of lib directory
        """
        self.verify_base_path()
        base_path= self.opdict['base_path']
        lib_path = os.path.join(base_path, 'lib')
        if not os.path.isdir(lib_path):
            msg="Directory %s does not exist"%lib_path
            raise IOError(msg)



    def verify_synthetic_options(self):
        pass
