"""Normal-incidence reflectance and transmittance of a layered stack by FDTD.

A one-dimensional Meep simulation sends a Gaussian pulse from the incident
medium onto the layers and records the reflected and transmitted flux at
every requested wavelength. The reflected flux is separated from the
incident one by subtracting the fields of a normalization run without the
stack, the standard Meep procedure. Lengths are in micrometres, so a Meep
frequency is the inverse vacuum wavelength in 1/um. Indices are real here;
dispersion and loss enter a native program as Lorentzian susceptibilities.
The transfer-matrix result is computed alongside as an independent
reference; the difference shrinks with resolution.
"""
import numpy as np
import meep as mp
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'n': ([1.0, 2.0, 1.5], 'real indices: incident medium, each layer, substrate'),
        'thickness_um': ([0.1], 'one thickness per layer in micrometres'),
        'wavelength_um': ({'start': 0.4, 'stop': 0.8, 'points': 81}, 'vacuum wavelengths: list or {"start", "stop", "points"}'),
        'resolution': (200, 'grid points per micrometre'),
        'decay': (1e-9, 'run until the transmitted field has decayed by this factor'),
    },
    'domains': ['em', 'film'],
    'results': 'spectrum.npz/.json with R, T and the transfer-matrix R_tmm, T_tmm over wavelength_um',
    'checks': 'energy_error: largest |1 - R - T|; tmm_difference: largest |R - R_tmm|',
}
p = parameters(PROGRAM, INPUTS)
n = [float(v) for v in p['n']]
d = [float(v) for v in p['thickness_um']]
if len(n) < 2 or len(d) != len(n) - 2 or min(n) < 1 or min(d, default=1) <= 0:
    raise ValueError('n lists the incident medium, each layer and the substrate (each >= 1); thickness_um has one positive value per layer')
grid = p['wavelength_um']
wavelengths = np.linspace(grid['start'], grid['stop'], int(grid['points'])) if isinstance(grid, dict) else np.atleast_1d(np.asarray(grid, float))
frequencies = 1 / wavelengths
fmin, fmax = frequencies.min(), frequencies.max()
fcen = (fmin + fmax) / 2
fwidth = max(1.5 * (fmax - fmin), 0.2 * fcen)

pad, pml = wavelengths.max(), wavelengths.max()
total = np.ceil((2 * pml + 3 * pad + sum(d)) * p['resolution']) / p['resolution']  # a whole number of grid points
left = -total / 2
source_z, reflection_z = left + pml + 0.25 * pad, left + pml + 0.75 * pad
start = left + pml + 1.5 * pad
transmission_z = start + sum(d) + 0.75 * pad


def simulate(stack):
    geometry = []
    if stack:
        z = start
        for index, thickness in zip(n[1:-1], d):
            geometry.append(mp.Block(size=mp.Vector3(mp.inf, mp.inf, thickness), center=mp.Vector3(z=z + thickness / 2),
                                     material=mp.Medium(index=index)))
            z += thickness
        geometry.append(mp.Block(size=mp.Vector3(mp.inf, mp.inf, total / 2 - z), center=mp.Vector3(z=(z + total / 2) / 2),
                                 material=mp.Medium(index=n[-1])))
    sim = mp.Simulation(cell_size=mp.Vector3(z=total), dimensions=1, resolution=p['resolution'], boundary_layers=[mp.PML(pml)],
                        default_material=mp.Medium(index=n[0]), geometry=geometry,
                        sources=[mp.Source(mp.GaussianSource(fcen, fwidth=fwidth), component=mp.Ex, center=mp.Vector3(z=source_z))])
    reflected = sim.add_flux(frequencies, mp.FluxRegion(center=mp.Vector3(z=reflection_z)))
    transmitted = sim.add_flux(frequencies, mp.FluxRegion(center=mp.Vector3(z=transmission_z)))
    return sim, reflected, transmitted


sim, reflected, transmitted = simulate(False)
sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ex, mp.Vector3(z=transmission_z), p['decay']))
incident = np.array(mp.get_fluxes(transmitted))
incident_fields = sim.get_flux_data(reflected)
sim.reset_meep()
sim, reflected, transmitted = simulate(True)
sim.load_minus_flux_data(reflected, incident_fields)
sim.run(until_after_sources=mp.stop_when_fields_decayed(50, mp.Ex, mp.Vector3(z=transmission_z), p['decay']))
R = -np.array(mp.get_fluxes(reflected)) / incident
T = np.array(mp.get_fluxes(transmitted)) / incident

# Characteristic-matrix result at normal incidence.
R_tmm, T_tmm = [], []
for wavelength in wavelengths:
    M = np.eye(2, dtype=complex)
    for index, thickness in zip(n[1:-1], d):
        phase = 2 * np.pi * index * thickness / wavelength
        M = M @ np.array([[np.cos(phase), -1j * np.sin(phase) / index], [-1j * index * np.sin(phase), np.cos(phase)]])
    B, C = M @ np.array([1, n[-1]])
    R_tmm.append(abs((n[0] * B - C) / (n[0] * B + C)) ** 2)
    T_tmm.append(4 * n[0] * n[-1] / abs(n[0] * B + C) ** 2)
R_tmm, T_tmm = np.array(R_tmm), np.array(T_tmm)
axes = ['wavelength_um']
saved = data.save(OUTPUT_DIR / 'spectrum', {
    'R': data.quantity(R, 'reflectance (FDTD)', unit='1', axes=axes, resolution_per_um=p['resolution']),
    'T': data.quantity(T, 'transmittance (FDTD)', unit='1', axes=axes),
    'R_tmm': data.quantity(R_tmm, 'reflectance (transfer matrix)', unit='1', axes=axes),
    'T_tmm': data.quantity(T_tmm, 'transmittance (transfer matrix)', unit='1', axes=axes),
    'wavelength_um': data.quantity(wavelengths, 'vacuum wavelength', unit='um'),
})
RESULT = {'data': saved['data'], 'R': [float(v) for v in R[:5]], 'T': [float(v) for v in T[:5]], 'points': len(wavelengths),
          'meep_time': float(sim.meep_time()),
          'checks': {'energy_error': float(np.max(np.abs(1 - R - T))), 'tmm_difference': float(np.max(np.abs(R - R_tmm)))}}
