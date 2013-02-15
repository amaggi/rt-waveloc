import numpy as np
from numpy import pi, sqrt, exp

def gaussian_filter(sigma_f, f0, dt):
    """
    Calculates the time-domain impulse response of the gaussian filter of width
    sigma_f centered at f0, for a signal with sampling interval dt. All
    frequencies are expressed in Hz.

    :type sigma_f: float
    :param sigma_f: half-width of the gaussian filter in the frequency domain
    :type f0: float
    :param f0: center frequency of the filter
    :type dt: float
    :param dt: sampling interval in seconds for the output impulse response
    :rtype gauss: Numpy :class:`numpy.ndarray`
    :return gauss: The time domain impulse response
    :rtype tshift: float
    :return tshift: The time-shift corresponding to this filter
    "
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
