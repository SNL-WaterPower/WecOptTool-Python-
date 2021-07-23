#!/usr/bin/env python3

import os

import autograd.numpy as np
import capytaine as cpy
import xarray as xr

import WecOptTool as wot
from preprocess import rho, f0, num_freq


# I/O
data_dir = 'data'
results_dir = 'results'
case = 'P'
if not os.path.exists(results_dir):
    os.makedirs(results_dir)

# Capytaine floating body
mesh_file = os.path.join(data_dir, 'mesh.stl')
fb = cpy.FloatingBody.from_file(mesh_file, name='WaveBot')
fb.add_translation_dof(name="Heave")

# mass and hydrostatic stiffness
M = np.atleast_2d(np.loadtxt(os.path.join(data_dir, 'mass_matrix')))
K = np.atleast_2d(np.loadtxt(os.path.join(data_dir, 'hydrostatic_stiffness')))

# PTO: state, force, power (objective function)
kinematics = np.eye(fb.nb_dofs)
num_x_pto, f_pto, power_pto, pto_postproc = \
    wot.pto.proportional_pto(kinematics)

# create WEC
wec = wot.WEC(fb, M, K, f0, num_freq, f_add=f_pto, rho=rho)

# read BEM
bem_file = os.path.join(data_dir, 'BEM.nc')
wec.read_bem(bem_file)

# wave
waves = xr.open_dataset(os.path.join(data_dir, 'waves.nc'))

# Scale # TODO (makes it worst in some cases ... why?)
scale_wec = 1.0  # 1e-4
scale_opt = 1.0  # 1e-3
scale_obj = 1.0  # 1e-8

# Constraints
constraints = []

# Solve dynamics & opt control
options = {'maxiter': 1000, }

FD, TD, x_opt, res = wec.solve(
    waves, power_pto, num_x_pto,
    constraints=constraints, optim_options=options,
    scale_x_wec=scale_wec, scale_x_opt=scale_opt, scale_obj=scale_obj)

# post-process: PTO
TD, FD = pto_postproc(wec, TD, FD, x_opt)

# save
td_file = os.path.join(results_dir, f'TD_{case}.nc')
TD.to_netcdf(td_file)

fd_file = os.path.join(results_dir, f'FD_{case}.nc')
wot.to_netcdf(fd_file, FD)
