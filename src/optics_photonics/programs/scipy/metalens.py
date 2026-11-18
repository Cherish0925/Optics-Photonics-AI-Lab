"""Metalens from a unit-cell library: pillar layout by the hyperbolic phase, focal spot by angular-spectrum propagation.

A lens of focal length f needs at radius r the phase phi(r) = -(2 pi /
lambda)(sqrt(r^2 + f^2) - f), modulo 2 pi. Each cell of a square lattice of
period P inside the circular aperture receives the library entry (pillar
diameter, zeroth-order transmission t and phase) whose phase is nearest the
required one; the transmitted field of the cell is sqrt(t) exp(i phase), the
local periodic approximation of a metasurface whose neighbouring cells
differ slowly. library is the library.npz that grcwa/metasurface writes
(bound as a file of an earlier step), or null for an ideal library of unit
transmission and every phase. The field just after the lens, sampled
sub_samples times per cell, is propagated to the focal plane by the angular
spectrum of scalar diffraction (exact for propagating plane waves). Reported:
the focal spot's full width at half maximum along x and its ratio to the
Airy width 0.514 lambda / NA, the Strehl ratio against the ideal lens of the
same aperture, the focusing efficiency (power within a radius of 1.5 FWHM of
the focus over the power incident on the aperture), and the phase error
left by the library. A plane wave of unit intensity lights the aperture at
normal incidence; lengths in micrometres.
"""
import math
import numpy as np
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'library': (None, 'library.npz of grcwa/metasurface (diameter_um, transmission, phase), or null for an ideal library'),
        'wavelength_um': (1.55, 'vacuum wavelength in micrometres; the library\'s wavelength'),
        'period_um': (0.6, 'lattice period of the cells in micrometres; the library\'s period'),
        'focal_um': (30.0, 'focal length in micrometres'),
        'aperture_um': (30.0, 'lens diameter in micrometres'),
        'index': (1.0, 'index of the medium between the lens and the focal plane'),
        'sub_samples': (3, 'field samples per cell along each side'),
        'window': (2.0, 'side of the computational window in aperture diameters'),
    },
    'results': 'metalens.npz/.json: pillar diameter and phase of every cell, the focal-plane intensity and its x cut; FWHM, Airy ratio, '
               'Strehl ratio, focusing efficiency, NA and library phase error',
    'checks': 'energy_error: |power in the focal plane / power after the lens - 1| over the propagating waves; '
              'ideal_airy_ratio: FWHM of the ideal lens over the Airy width',
}
p = parameters(PROGRAM, INPUTS)
wavelength, period, focal, aperture = (float(p[k]) for k in ('wavelength_um', 'period_um', 'focal_um', 'aperture_um'))
medium, sub = float(p['index']), int(p['sub_samples'])
if min(wavelength, period, focal, aperture, medium) <= 0 or sub < 1 or float(p['window']) < 1:
    raise ValueError('wavelength, period, focal length, aperture and index are positive; sub_samples >= 1; window >= 1')
k = 2 * math.pi * medium / wavelength
if p['library']:
    stored = np.load(p['library'])
    diameters, transmission, phase = (np.asarray(stored[key], float) for key in ('diameter_um', 'transmission', 'phase'))
else:
    diameters = np.linspace(0, 1, 361)                                        # an ideal library: a phase for every 1 degree
    transmission, phase = np.ones_like(diameters), diameters * 2 * math.pi

# Cells of the lattice inside the aperture, and the library entry of each.
cells = int(math.ceil(aperture / period / 2))
centres = (np.arange(-cells, cells + 1)) * period
cx, cy = np.meshgrid(centres, centres, indexing='ij')
inside = cx ** 2 + cy ** 2 <= (aperture / 2) ** 2
required = -k * (np.sqrt(cx ** 2 + cy ** 2 + focal ** 2) - focal)
choice = np.argmin(np.abs(np.exp(1j * required[..., None]) - np.exp(1j * phase[None, None, :])), axis=-1)
phase_error = np.angle(np.exp(1j * (phase[choice] - required)))
cell_field = np.where(inside, np.sqrt(np.clip(transmission[choice], 0, None)) * np.exp(1j * phase[choice]), 0)
ideal_field = np.where(inside, np.exp(1j * required), 0)

# Sample the window: each cell's field repeated sub x sub times, padded to the window.
step = period / sub
size = int(2 ** math.ceil(math.log2(float(p['window']) * aperture / step)))


def sampled(field):
    """The cell fields on the window grid, the centre of the central cell on the window centre."""
    fine = np.kron(field, np.ones((sub, sub)))
    out = np.zeros((size, size), complex)
    start = size // 2 - (fine.shape[0] // 2)
    out[start:start + fine.shape[0], start:start + fine.shape[1]] = fine
    return out


frequency = np.fft.fftfreq(size, d=step) * 2 * math.pi
kx, ky = np.meshgrid(frequency, frequency, indexing='ij')
kz2 = k ** 2 - kx ** 2 - ky ** 2
propagating = kz2 > 0
transfer = np.where(propagating, np.exp(1j * np.sqrt(np.where(propagating, kz2, 0)) * focal), 0)


def focus(field):
    spectrum = np.fft.fft2(field)
    after = np.sum(np.abs(spectrum[propagating]) ** 2)
    focal_field = np.fft.ifft2(spectrum * transfer)
    return focal_field, after / size ** 2


lens_field, ideal_lens = sampled(cell_field), sampled(ideal_field)
focal_field, propagated_power = focus(lens_field)
ideal_focal, _ = focus(ideal_lens)
intensity, ideal_intensity = np.abs(focal_field) ** 2, np.abs(ideal_focal) ** 2   # the fields stay where they were placed
axis = (np.arange(size) - size // 2) * step
centre = size // 2


def fwhm(cut):
    half = cut[centre] / 2
    right = centre + np.argmax(cut[centre:] < half)
    left = centre - np.argmax(cut[centre::-1] < half)
    # Linear interpolation of the half-maximum crossings on both sides.
    x_right = axis[right - 1] + (cut[right - 1] - half) / (cut[right - 1] - cut[right]) * step
    x_left = axis[left + 1] - (cut[left + 1] - half) / (cut[left + 1] - cut[left]) * step
    return x_right - x_left


numerical_aperture = medium * math.sin(math.atan(aperture / (2 * focal)))
airy = 0.514 * wavelength / numerical_aperture
width, ideal_width = fwhm(intensity[:, centre]), fwhm(ideal_intensity[:, centre])
incident = np.sum(np.abs(np.kron(inside, np.ones((sub, sub))))) * step ** 2              # unit intensity on the aperture
rr = np.hypot(*np.meshgrid(axis, axis, indexing='ij'))
efficiency = float(np.sum(intensity[rr <= 1.5 * width]) * step ** 2 / incident)
energy_error = abs(np.sum(intensity) * step ** 2 / (propagated_power * step ** 2) - 1)

span = slice(max(0, centre - int(3 * airy / step)), centre + int(3 * airy / step) + 1)
saved = data.save(OUTPUT_DIR / 'metalens', {
    'x_um': data.quantity(axis[span], 'position in the focal plane', unit='um'),
    'y_um': data.quantity(axis[span], 'position in the focal plane', unit='um'),
    'intensity': data.quantity(intensity[span, span], 'focal-plane intensity for unit incident intensity', unit='1', axes=['x_um', 'y_um']),
    'ideal_intensity': data.quantity(ideal_intensity[span, span], 'focal-plane intensity of the ideal lens', unit='1', axes=['x_um', 'y_um']),
    'cell_um': data.quantity(centres, 'cell centre', unit='um'),
    'diameter': data.quantity(np.where(inside, diameters[choice], np.nan), 'pillar diameter of each cell, NaN outside the aperture',
                              unit='um' if p['library'] else 'library position', axes=['cell_um', 'cell_um']),
    'phase_error': data.quantity(np.where(inside, phase_error, np.nan), 'library phase minus the required phase', unit='rad', axes=['cell_um', 'cell_um']),
})
RESULT = {'data': saved['data'], 'numerical_aperture': numerical_aperture, 'cells': int(inside.sum()),
          'fwhm_um': float(width), 'airy_fwhm_um': airy, 'airy_ratio': float(width / airy),
          'strehl': float(intensity[centre, centre] / ideal_intensity[centre, centre]), 'focusing_efficiency': efficiency,
          'phase_error_rms_rad': float(np.sqrt(np.mean(phase_error[inside] ** 2))),
          'library_entries_used': int(len(np.unique(choice[inside]))),
          'checks': {'energy_error': float(energy_error), 'ideal_airy_ratio': float(ideal_width / airy)}}
