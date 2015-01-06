
import numpy as np
import matplotlib.pyplot as plt


def subsetData(tobs, inputDict, t0=0.0, tf=3000.0, minValid=1, checkOnly=False, ndays=None,
               statlist=None, subfactor=1):
    """
    Subsets GPS data based on a window of observation times.
    """
    # First check if a list of stations to keep is provided
    statnames = list(inputDict.keys())
    if statlist is not None:
        for statname in statnames:
            if statname.lower() not in statlist:
                del inputDict[statname]
    statnames = list(inputDict.keys())

    # Boolean array of valid observation times
    tbool = tobs >= t0
    if ndays is None:
        tbool *= tobs <= tf
    else:
        beg_ind = tbool.nonzero()[0][0]
        end_ind = beg_ind + ndays
        tbool = np.arange(beg_ind, end_ind, dtype=int)[::subfactor]
    print(('Subset time window:', tobs[tbool][0], '->', tobs[tbool][-1]))

    # Subset data
    if not checkOnly:
        tobs = tobs[tbool]
    nvalidsss = []
    for statname in statnames:
        stat = inputDict[statname]
        # Test to see if station has enough valid data
        indValid = np.isfinite(stat.east[tbool]).nonzero()[0]
        if indValid.size < minValid:
            del inputDict[statname]
        else:
            if checkOnly:
                continue
            else:
                for attr in ('east', 'north', 'up', 'w_east', 'w_north', 'w_up'):
                    dat = getattr(stat, attr)
                    setattr(stat, attr, dat[tbool])
                    try:
                        filtdat = getattr(stat, 'filt_' + attr)
                        setattr(stat, 'filt_' + attr, filtdat[tbool])
                    except AttributeError:
                        pass
                nvalidsss.append(indValid.size)

    #plt.plot(nvalidsss, 'o'); plt.show(); assert False

    return tobs
