"""Resonances of a measured or computed transmission spectrum: wavelength, linewidth, Q, extinction and free spectral range.

Rings, disks, Fabry-Perot cavities and photonic-crystal cavities show dips
(or peaks) in transmission. Near a resonance of loaded quality factor Q the
transmission is a Lorentzian of full width w = lambda_0 / Q on a baseline:
T = b - A (w/2)^2 / ((lambda - lambda_0)^2 + (w/2)^2) for a dip of depth A.
The program finds the dips deeper than min_depth of the baseline, fits each
within a window of a few linewidths by least squares, and returns the
centre, width, Q and extinction of each with the standard errors of the
fit, the spacing of neighbours (the free spectral range) and, for a given
round-trip length L, the group index lambda^2 / (FSR L). The spectrum is a
CSV file with wavelength and transmission in its first two columns, or two
lists; transmission in dB is converted. Without data the program analyses
the exact spectrum of an all-pass ring with noise,
T = (a^2 - 2 r a cos(phi) + r^2) / (1 - 2 r a cos(phi) + (r a)^2),
phi = 2 pi n_g L / lambda, whose width is
(1 - r a) lambda^2 / (pi n_g L sqrt(r a)), and compares the fit with it.
With peaks, the peaks higher than min_depth of the highest are analysed
instead. Fit windows stop at the midpoints to neighbouring detected
resonances, so one fit does not include another peak. Overlapping line
shapes still require a multi-resonance model; independent Lorentzians do
not separate their tails. Resolve each resonance with several
samples per linewidth; a width near the sampling step is not a measurement.
"""
import csv
from pathlib import Path
import numpy as np
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'file': ('', 'CSV file with wavelength and transmission in the first two columns; lines that are not numbers are skipped'),
        'wavelength_nm': ([], 'wavelengths in nm, when no file is given'),
        'transmission': ([], 'transmission at each wavelength, linear, or in dB with decibel'),
        'decibel': (False, 'the transmission is in dB'),
        'peaks': (False, 'analyse peaks instead of dips'),
        'min_depth': (0.1, 'smallest depth of a dip as a share of the baseline; with peaks, smallest height as a share of the highest'),
        'window_widths': (6.0, 'half width of the fitted window, in linewidths'),
        'round_trip_um': (0.0, 'round-trip length for the group index, in micrometres; 0 skips it'),
        'ring': ({'radius_um': 20.0, 'group_index': 4.2, 'self_coupling': 0.98, 'round_trip_amplitude': 0.99, 'noise': 0.005,
                  'start_nm': 1545.0, 'stop_nm': 1555.0, 'points': 20001, 'seed': 1},
                 'the all-pass ring analysed when no data is given'),
    },
    'domains': ['lab', 'pic'],
    'results': 'resonances.npz/.json with the spectrum, the fitted curve and a table of the resonances; per resonance wavelength, '
               'width, Q and extinction with standard errors; free spectral ranges and group index',
    'checks': 'q_difference and fsr_difference: relative difference of the mean fitted Q and free spectral range from those of the '
              'exact ring spectrum, when no data is given; residual: root mean square of data minus fit over the fitted windows',
}
p = parameters(PROGRAM, INPUTS)
exact = None
if p['file']:
    rows = []
    with Path(p['file']).open(newline='', encoding='utf-8', errors='replace') as stream:
        sample = stream.read(4096)
        stream.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t ') if sample.strip() else csv.excel
        for row in csv.reader(stream, dialect):
            try:
                rows.append((float(row[0]), float(row[1])))
            except (ValueError, IndexError):
                continue
    wavelength, signal = (np.asarray(column) for column in zip(*rows)) if rows else (np.zeros(0), np.zeros(0))
elif len(p['wavelength_nm']):
    wavelength, signal = np.asarray(p['wavelength_nm'], dtype=float), np.asarray(p['transmission'], dtype=float)
else:
    ring = p['ring']
    length = 2 * np.pi * float(ring['radius_um'])
    wavelength = np.linspace(float(ring['start_nm']), float(ring['stop_nm']), int(ring['points']))
    r, a, group = float(ring['self_coupling']), float(ring['round_trip_amplitude']), float(ring['group_index'])
    phase = 2 * np.pi * group * length * 1e3 / wavelength
    signal = (a ** 2 - 2 * r * a * np.cos(phase) + r ** 2) / (1 - 2 * r * a * np.cos(phase) + (r * a) ** 2)
    signal = signal + float(ring['noise']) * np.random.default_rng(int(ring['seed'])).standard_normal(wavelength.size)
    centre = wavelength.mean()
    exact = {'fsr_nm': centre ** 2 / (group * length * 1e3), 'width_nm': (1 - r * a) * centre ** 2 / (np.pi * group * length * 1e3 * np.sqrt(r * a))}
    exact['Q'] = centre / exact['width_nm']
    p = {**p, 'round_trip_um': p['round_trip_um'] or length}
if wavelength.size != signal.size or wavelength.size < 20:
    raise ValueError('Give at least 20 wavelengths with one transmission value each')
order = np.argsort(wavelength)
wavelength, signal = wavelength[order], signal[order]
if not np.all(np.isfinite(wavelength)) or not np.all(np.isfinite(signal)) or np.any(np.diff(wavelength) <= 0):
    raise ValueError('Wavelengths and transmission are finite, and wavelengths are distinct')
if p['decibel']:
    signal = 10 ** (signal / 10)
if not 0 < float(p['min_depth']) < 1 or float(p['window_widths']) < 1:
    raise ValueError('min_depth lies between 0 and 1 and window_widths is at least 1')

sign = 1.0 if p['peaks'] else -1.0
baseline = float(np.median(signal))
sample_index = np.arange(wavelength.size)
scale = float(signal.max() - baseline) if p['peaks'] else abs(baseline)
found, properties = find_peaks(sign * signal, prominence=float(p['min_depth']) * scale, width=1)


def lorentzian(x, base, amplitude, centre, width):
    return base + sign * amplitude * (width / 2) ** 2 / ((x - centre) ** 2 + (width / 2) ** 2)


table, fitted, squares, counted = [], np.full(signal.shape, np.nan), 0.0, 0
for number, (index, left, right) in enumerate(zip(found, properties['left_ips'], properties['right_ips'])):
    # Peak widths are fractional sample indices; map their crossings to the actual wavelength grid.
    guess_width = max(np.interp(right, sample_index, wavelength) - np.interp(left, sample_index, wavelength),
                      wavelength[index + 1] - wavelength[index - 1])
    half = float(p['window_widths']) * guess_width
    low = (wavelength[found[number - 1]] + wavelength[index]) / 2 if number else wavelength[0]
    high = (wavelength[found[number + 1]] + wavelength[index]) / 2 if number + 1 < len(found) else wavelength[-1]
    near = (wavelength >= max(low, wavelength[index] - half)) & (wavelength <= min(high, wavelength[index] + half))
    if near.sum() < 8:
        continue
    try:
        values, covariance = curve_fit(lorentzian, wavelength[near], signal[near],
                                       p0=[baseline, abs(signal[index] - baseline), wavelength[index], guess_width])
    except RuntimeError:
        continue
    base, amplitude, centre, width = values
    width = abs(width)
    errors = np.sqrt(np.diag(covariance))
    if not wavelength[near][0] < centre < wavelength[near][-1] or not np.all(np.isfinite(errors)):
        continue
    fitted[near] = lorentzian(wavelength[near], *values)
    squares += float(np.sum((signal[near] - fitted[near]) ** 2))
    counted += int(near.sum())
    # Extinction of a dip: baseline over the transmission at its centre.
    ratio = (base - amplitude) / base if not p['peaks'] and base > 0 else None
    samples = np.interp(centre + width / 2, wavelength, sample_index) - np.interp(centre - width / 2, wavelength, sample_index)
    table.append({'wavelength_nm': float(centre), 'wavelength_error_nm': float(errors[2]), 'width_pm': float(width * 1e3),
                  'width_error_pm': float(errors[3] * 1e3), 'Q': float(centre / width), 'Q_error': float(centre / width * errors[3] / width),
                  'extinction_db': float(-10 * np.log10(ratio)) if ratio and ratio > 0 else None, 'samples_per_width': float(samples)})
if not table:
    raise ValueError('No resonance deeper than min_depth was found; lower min_depth, or set peaks for a spectrum of peaks')

centres = np.asarray([row['wavelength_nm'] for row in table])
spacing = np.diff(centres)
length = float(p['round_trip_um'])
group_index = [float(value) for value in (centres[:-1] + spacing / 2) ** 2 / (spacing * length * 1e3)] if length and spacing.size else []
names = ('wavelength_nm', 'width_pm', 'Q', 'extinction_db')
saved = data.save(OUTPUT_DIR / 'resonances', {
    'transmission': data.quantity(signal, 'transmission', unit='1', axes=['wavelength_nm']),
    'fit': data.quantity(fitted, 'fitted Lorentzian inside each window; empty elsewhere', unit='1', axes=['wavelength_nm']),
    'wavelength_nm': data.quantity(wavelength, 'vacuum wavelength', unit='nm'),
    'resonance': data.quantity(np.asarray([[row[name] if row[name] is not None else np.nan for name in names] for row in table]),
                               'centre wavelength (nm), width (pm), Q and extinction (dB) of each resonance', unit='mixed',
                               axes=['number', {'name': 'quantity', 'labels': list(names)}]),
    'number': data.quantity(np.arange(len(table)), 'resonance by increasing wavelength', unit='1'),
})
mean_q = float(np.mean([row['Q'] for row in table]))
RESULT = {
    'resonances': table if len(table) <= 12 else table[:12], 'count': len(table), 'mean_Q': mean_q,
    'fsr_nm': [float(value) for value in spacing[:12]], 'group_index': group_index[:12], 'baseline': baseline, 'data': saved['data'],
    'checks': {'q_difference': mean_q / exact['Q'] - 1 if exact else None,
               'fsr_difference': float(spacing.mean() / exact['fsr_nm'] - 1) if exact and spacing.size else None,
               'residual': float(np.sqrt(squares / counted))},
}
