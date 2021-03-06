"""33
.. module:: parcel
    :synopsis: Tool for specifying aerosol distributions.

.. moduleauthor:: Daniel Rothenberg <darothen@mit.edu>

"""
__docformat__ = 'reStructuredText'

import numpy as np

from lognorm import Lognorm, MultiModeLognorm


def dist_to_conc(dist, r_min, r_max, rule="trapezoid"):
    """Calculates the concentration in a given size bin from a spectral
    size distribution.
    """
    pdf = dist.pdf
    width = r_max - r_min
    if rule == "trapezoid":
        return width*0.5*(pdf(r_max) + pdf(r_min))
    elif rule == "simpson":
        return (width/6.)*(pdf(r_max) + pdf(r_min) + 4.*pdf(0.5*(r_max + r_min)))
    else:
        return width*pdf(0.5*(r_max + r_min))

class AerosolSpecies(object):
    """Container class for organizing and passing around important details about
    aerosol species present in the parcel model.

    To allow flexibility with how aerosols are defined in the model, this class is
    meant to act as a wrapper to contain metadata about aerosols (their species name, etc),
    their chemical composition (particle mass, hygroscopicity, etc), and the particular
    size distribution chosen for the initial dry aerosol. Because the latter could be very
    diverse - for instance, it might be desired to have a monodisperse aerosol population,
    or a bin representation of a canonical size distribution - the core of this class
    is designed to take those representations and homogenize them for use in the model.

    An :class:`AerosolSpecies` instance has the following attributes:

    **Attributes**:
        * *species* -- A string representing a name for the particular aerosol species. This is purely metadata and doesn't serve any function in the parcel model except for tagging aerosols.
        * *kappa* -- The hygroscopicity parameter :math:`\kappa` of the aerosol species used in
            :math:`\kappa`-Kohler theory. This should be a `float`, and is non-dimensional.
        * *nr* -- The number of bins in the size distribution. Can be 1, for a monodisperse aerosol.
        * *r_drys* -- A :mod:`numpy` array instance containing the representative dry radii for each bin in the aerosol size distribution. Has length equal to `nr`, and units (m).
        * *rs* -- :mod:`numpy` array instance containing the edge of each bin in the aerosol size distribution. Has length equal to `nr + 1` and units (cm).
        * *Nis* -- A :mod:`numpy` array instance of length `nr` with the number concentration in (m**-3) of each aerosol size bin.
        * *N* -- The total aerosol species number concentration in (m**-3)
        * *r_min* -- The minimum radius of aerosol in the distribution (optional)
        * *r_max* -- The maximum radius of aerosol in the distribution (optional)
        * *rho* -- The density of the dry aerosol material in kg/m^3 (optional)
        * *mw* -- Molecular weight of dry aerosol material in kg/mole (optional)

    To construct an :class:`AerosolSpecies`, only the metadata (`species` and `kappa`)
    and the size distribution needs to be specified. The size distribution
    (`distribution`) can be an instance of :class:`parcel_model.lognorm.Lognorm`, as
    long as an extra parameter `bins`, which is an `int` representing how many bins into
    which the distribution should be divided, is also passed to the constructor. In this
    case, the constructor will figure out how to slice the size distribution to
    calculate all the aerosol dry radii and their number concentrations. If `r_min` and
    `r_max` are supplied, then the size range of the aerosols will be bracketed; else,
    the supplied `distribution` will contain a shape parameter or other bounds to use.

    Alternatively, a :class:`dict` can be passed as `distribution` where that slicing has
    already occurred. In this case, `distribution` must have 2 keys: *r_drys* and *Nis*.
    Each of the values stored to those keys should fit the attribute descriptors above
    (although they don't need to be :mod:`numpy` arrays - they can be any iterable.)


    Constructing sulfate aerosol with a specified lognormal distribution -

    >>> aerosol1 = AerosolSpecies('(NH4)2SO4', Lognorm(mu=0.05, sigma=2.0, N=300.),
    >>>                           bins=200, kappa=0.6)

    Constructing a monodisperse sodium chloride distribution -

    >>> aerosol2 = AerosolSpecies('NaCl', {'r_drys': [0.25, ], 'Nis': [1000.0, ]}, kappa=0.2)

    .. warning ::

        Throws a :class:`ValueError` if an unknown type of `distribution` is passed to
        the constructor, or if `bins` isn't present when `distribution` is an instance of
        :class:`parcel_model.lognorm.Lognorm`

    """
    def __init__(self, species, distribution, kappa, 
                       rho=None, mw=None, 
                       bins=None, r_min=None, r_max=None):
        """Basic constructor for aerosol species

        Raises:
            :class:`ValueError` if there is something wrong with the specified
            distribution.
        """

        self.species = species  # Species molecular formula
        self.kappa = kappa      # Kappa hygroscopicity parameter
        self.rho = rho          # aerosol density kg/m^3
        self.mw = mw
        self.bins = bins        # Number of bins for discretizing the size distribution

        ## Handle the size distribution passed to the constructor
        self.distribution = distribution
        if isinstance(distribution, dict):
            self.r_drys = np.array(distribution['r_drys'])*1e-6
            self.rs = np.array([self.r_drys[0]*0.9, self.r_drys[0]*1.1, ])*1e6
            self.Nis = np.array(distribution['Nis'])
            self.N = np.sum(self.Nis)

        elif isinstance(distribution, Lognorm):
            # Check for missing keyword argument
            if bins is None:
                raise ValueError("Need to specify `bins` argument if passing a Lognorm distribution")

            if isinstance(bins, (list, np.ndarray)):
                self.rs = bins[:]
            else:
                if not r_min and not r_max:
                    lr = np.log10(distribution.mu/(10.*distribution.sigma))
                    rr = np.log10(distribution.mu*10.*distribution.sigma)
                else:
                    lr, rr = np.log10(r_min), np.log10(r_max)
                self.rs = np.logspace(lr, rr, num=bins+1)[:]

            nbins = len(self.rs)
            mids = np.array([np.sqrt(a*b) for a, b in zip(self.rs[:-1], self.rs[1:])])[0:nbins]
            self.Nis = np.array([0.5*(b-a)*(distribution.pdf(a) + distribution.pdf(b)) for a, b in zip(self.rs[:-1], self.rs[1:])])[0:nbins]
            self.r_drys = mids*1e-6

        elif isinstance(distribution, MultiModeLognorm):
            if bins is None:
                raise ValueError("Need to specify `bins` argument if passing a MultiModeLognorm distribution")

            small_mu = distribution.mus[0]
            small_sigma = distribution.sigmas[0]
            big_mu = distribution.mus[-1]
            big_sigma = distribution.sigmas[-1]

            if isinstance(bins, (list, np.ndarray)):
                self.rs = bins[:]
            else:
                if not r_min and not r_max:
                    lr, rr = np.log10(small_mu/(10.*small_sigma)), np.log10(big_mu*10.*big_sigma)
                else:
                    lr, rr = np.log10(r_min), np.log10(r_max)

                self.rs = np.logspace(lr, rr, num=bins+1)[:]
            mids = np.array([np.sqrt(a*b) for a, b in zip(self.rs[:-1], self.rs[1:])])[0:nbins]
            self.Nis = np.array([0.5*(b-a)*(distribution.pdf(a) + distribution.pdf(b)) for a, b in zip(self.rs[:-1], self.rs[1:])])[0:nbins]
            self.r_drys = mids*1e-6

        else:
            raise ValueError("Could not work with size distribution of type %r" % type(distribution))

        ## Correct to SI units
        # Nis: cm**-3 -> m**-3
        self.Nis *= 1e6
        self.nr = len(self.r_drys)

    def __repr__(self):
        return "%s - %r" % (self.species, self.distribution)

    '''
    ## As of 7/16/2013 these methods are deprecated and must be re-written.
    def summary_str(self):
        """Returns a string summarizing the components of this aerosol distribution.
        """
        summary_dict = { "species": self.species, "mu": self.mu, "sigma": self.sigma, "N": self.N,
                         "kappa": self.kappa, "bins": self.bins }
        return str(summary_dict)

    @staticmethod
    def from_summary_str(summary_str):
        """Reads a previously emitted `summary_str` and constructs a corresponding
        instance of the aerosol distribution.
        """
        import ast
        summary_dict = ast.literal_eval(summary_str)
        dist = Lognorm(mu=summary_dict['mu'], sigma=summary_dict['sigma'], N=summary_dict['N'])
        aerosol = AerosolSpecies(summary_dict['species'], dist, summary_dict['kappa'], summary_dict['bins'])
        return aerosol
    '''