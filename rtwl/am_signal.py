import numpy as np
from numpy import pi, sqrt, exp

def gaussian_filter(sigma_f, f0, dt):
    """
    Returns the time-domain expression of the gaussian filter
    of width sigma_f centered at f0, for a signal with
    sampling interval dt.
    """
    # calculate the width of the gaussian in the time domain
    sigma_t = 1 / (2*pi*sigma_f)
    # calculate the number of points required for +/- 3*sigma_t
    npts_1sigma = int(sigma_t/dt)
    npts = npts_1sigma*8 + 1 
    # calculate the time-shift of this filter
    tshift=((npts-1)/2) * dt
    # set up the t-array
    t=np.arange(npts)*dt - 4*npts_1sigma*dt 

    gauss = 1/(sqrt(2*pi)*sigma_f) * exp(-t*t/(2*sigma_t*sigma_t)) * \
            exp(complex(0,1)*2*pi*f0*t)


    return gauss, tshift
