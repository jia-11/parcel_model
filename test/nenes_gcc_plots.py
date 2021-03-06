'''
Created on Sep 10, 2012

@author: daniel
'''

import numpy as np
import pandas

import nenes_parcel_aux as npa

from nenes_parcel import AerosolSpecies, ParcelModel
from micro import Mw, rho_w, kohler_crit
from lognorm import Lognorm

from pylab import *

## Initial conditions
P0 = 100000. # Pressure, Pa
T0 = 294. # Temperature, K
S0 = -0.05 # Supersaturation. 1-RH from wv term
V = 0.5 # m/s

def make_ammonium_sulfate(epsilon=0.3, N=200.):
    ammonium_sulfate = { 'Ms': 0.13214, # Molecular weight, kg/mol
                         'rho_s': 1.769*1e-3*1e6,
                         'rho_u': 1.769*1e-3*1e6,
                         'nu': 3.0, # number of ions into which a solute dissolve
                         'epsilon': epsilon # mass fraction of soluble material in the dry particle
                       }
    ammonium_sulfate['rho_p'] = 1.769*1e-3*1e6
    mu, sigma, bins, N = 0.05, 2.0, 50, N
    l = 0
    r = bins
    aerosol_dist = Lognorm(mu=mu, sigma=sigma, N=N)
    rs = np.logspace(np.log10(mu/(sigma*10.)), np.log10(mu*sigma*10), num=bins+1)[:]
    mids = np.array([np.sqrt(a*b) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    Nis = np.array([0.5*(b-a)*(aerosol_dist.pdf(a) + aerosol_dist.pdf(b)) for a, b in zip(rs[:-1], rs[1:])])[l:r]
    r_drys = mids*1e-6

    ammonium_sulfate['distribution'] = aerosol_dist
    ammonium_sulfate['r_drys'] = r_drys
    ammonium_sulfate['rs'] = rs
    ammonium_sulfate['Nis'] = Nis*1e6
    ammonium_sulfate['species'] = '(NH4)2SO4'
    ammonium_sulfate['nr'] = len(r_drys)

    return AerosolSpecies(**ammonium_sulfate)


initial_aerosol = [make_ammonium_sulfate(), ]
aerosol = initial_aerosol[0]
pm = ParcelModel(initial_aerosol, V, T0, S0, P0, console=False)
parcel, aerosols = pm.run(P0, T0, S0, z_top=200.0, dt=0.05, max_steps=1000)


## Process aerosols
xs = np.arange(501)
parcel = parcel.ix[parcel.index % 1 == 0]
aero_subset = {}
for key in aerosols:
    aerosol = aerosols[key]
    subset = aerosol.ix[aerosol.index % 1 == 0]
    aero_subset[key] = subset
aerosols = pandas.Panel(aero_subset)

S_max = np.max(parcel.S)
S_max_ind = np.argmax(parcel.S)

aerosol = initial_aerosol[0]
T = parcel['T'].ix[S_max_ind]
rs = aerosols[aerosol.species].ix[S_max_ind]
r_drys = aerosol.r_drys

r_crits, s_crits = zip(*[kohler_crit(T, r_dry, aerosol.epsilon, aerosol.rho_p, aerosol.Ms, aerosol.nu) for r_dry in aerosol.r_drys])
r_crits, s_crits = np.array(r_crits), np.array(s_crits)
Nis = aerosol.Nis
Neq = np.sum(Nis[S_max > s_crits])

colors = 'bgrcmyk'

figure(1, figsize=(10, 15))
clf()
subplot(311)
p = parcel.S.plot(logx=False)
max_idx = np.argmax(parcel.S)
max_z = parcel.index[max_idx]
vlines([max_z], ylim()[0], ylim()[1], color='k', linestyle='dashed')
ylabel("Supersaturation (%)")

subplot(312)
aerosol = aerosols.ix[0]
for r in aerosol:
    (aerosol[r]*1e6).plot(logy=True)
vlines([max_z], ylim()[0], ylim()[1], color='k', linestyle='dashed')
xlabel("Parcel Height (m)")
ylabel("Wet Radius " + r"($\mu$m)")

subplot(313)
rs, Nis = initial_aerosol[0].rs, initial_aerosol[0].Nis*1e-6
bar(rs[:-1], Nis, diff(rs), color=colors[0], alpha=0.2)

rs, Nis = aerosol.ix[-1]*1e6, initial_aerosol[0].Nis*1e-6
plot(rs, Nis, color='k', alpha=0.5)
semilogx(); #semilogy()

rs, Nis = aerosol.ix[0]*1e6, initial_aerosol[0].Nis*1e-6
plot(rs, Nis, color='r', alpha=0.5)
xlabel("Radius " + r"($\mu$m)")
ylabel("Number concentration (per cc)")

