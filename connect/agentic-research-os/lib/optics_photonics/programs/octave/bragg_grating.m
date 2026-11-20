% Reflection, transmission and group delay of a fiber Bragg grating, uniform, apodized or chirped (coupled-mode theory).
%
% A grating of length L modulates the effective index of the mode as
% dn g(z) (1 + v cos(2 pi z / Lambda(z))), with the profile g of the
% apodization and the visibility v. Forward and backward amplitudes obey
% R' = i s R + i kappa S and S' = -i s S - i kappa R, where
% kappa = pi v dn g / lambda couples them and
% s = 2 pi n_eff (1 / lambda - 1 / lambda_B(z)) + 2 pi dn g / lambda is the
% detuning from the local Bragg wavelength lambda_B = 2 n_eff Lambda,
% including the shift by the mean index change (Erdogan, J. Lightwave
% Technol. 15, 1277 (1997)). The grating is divided into uniform sections
% whose transfer matrices are multiplied from the far end. The reflected
% group delay is -(lambda^2 / 2 pi c) d(phase)/d(lambda), measured at the
% entrance. A chirp moves lambda_B linearly along the grating, by
% chirp_nm_per_cm per centimetre about the centre: the band widens to about
% chirp times length and the delay varies across it by 2 n_eff / (c chirp).
% A uniform grating has the closed form
% R = sinh^2(q L) / (cosh^2(q L) - s^2 / kappa^2), q^2 = kappa^2 - s^2, with
% the peak tanh^2(kappa L) and the delay n_eff tanh(kappa L) / (kappa c)
% there. With zero visibility there is no reflected wave: its peak wavelength,
% bandwidth and delay are undefined (null in JSON, NaN in the saved delay array).
% The program runs in MATLAB and in GNU Octave.
%
% PROGRAM
% {"inputs": {
%   "bragg_wavelength_nm": [1550.0, "design Bragg wavelength 2 n_eff Lambda at the centre, in nm"],
%   "effective_index": [1.447, "effective index of the fiber mode"],
%   "index_change": [1e-4, "peak mean index change dn of the grating"],
%   "visibility": [1.0, "fringe visibility v, from 0 to 1"],
%   "length_mm": [10.0, "grating length in mm"],
%   "apodization": ["uniform", "uniform, gaussian or raised_cosine"],
%   "chirp_nm_per_cm": [0.0, "change of the local Bragg wavelength per centimetre"],
%   "wavelength_nm": [{"start": 1549.5, "stop": 1550.7, "points": 601}, "vacuum wavelengths in nm: a list, or {start, stop, points}"],
%   "sections": [200, "uniform sections of the grating"]},
%  "domains": ["fiber"],
%  "results": "spectrum.npz/.json: reflectance, transmittance and reflected group delay over wavelength; peak reflectance and its wavelength, the width of the band at half the peak, the mean delay slope inside it; peak wavelength, bandwidth and delays are null without reflection",
%  "checks": "energy_error: largest |1 - R - T|; uniform_difference: largest difference of the section product from the closed form of the uniform grating with the same peak index change; peak_difference: its peak minus tanh^2(kappa L); delay_difference: relative difference of its delay at the peak from n_eff tanh(kappa L) / (kappa c)"}

p = INPUTS;
if isstruct(p.wavelength_nm)
  wavelength = linspace(p.wavelength_nm.start, p.wavelength_nm.stop, p.wavelength_nm.points);
else
  wavelength = reshape(p.wavelength_nm, 1, []);
end
profiles = {'uniform', 'gaussian', 'raised_cosine'};
if ~any(strcmp(p.apodization, profiles)) || p.length_mm <= 0 || p.index_change <= 0 || p.sections < 1 || ...
    p.visibility < 0 || p.visibility > 1 || numel(wavelength) < 3 || any(diff(wavelength) <= 0)
  error('apodization is uniform, gaussian or raised_cosine; length_mm, index_change and sections are positive; visibility lies in [0, 1]; at least three increasing wavelengths');
end

c = 299792458;                              % m/s
lambda = wavelength * 1e-9;                 % m
L = p.length_mm * 1e-3;
centre = p.bragg_wavelength_nm * 1e-9;
chirp = p.chirp_nm_per_cm * 1e-7;           % metres of Bragg wavelength per metre

[rho, tau] = grating(lambda, p, L, centre, chirp, p.apodization, p.sections);
R = abs(rho) .^ 2;
T = abs(tau) .^ 2;
delay = group_delay(rho, lambda, c);

% The uniform grating with the same peak index change, by sections and in closed form.
plain = grating(lambda, p, L, centre, 0, 'uniform', p.sections);
kappa = pi * p.visibility * p.index_change ./ lambda;
s = 2 * pi * p.effective_index * (1 ./ lambda - 1 / centre) + 2 * pi * p.index_change ./ lambda;
q = sqrt(complex(kappa .^ 2 - s .^ 2));
sh = L * ones(size(q));                    % sinh(q L) / q, including the limit q = 0
nonzero = q ~= 0;
sh(nonzero) = sinh(q(nonzero) * L) ./ q(nonzero);
exact = abs(1i * kappa .* sh ./ (cosh(q * L) - 1i * s .* sh)) .^ 2;
peak_wavelength = centre * (1 + p.index_change / p.effective_index);   % where s = 0
near = peak_wavelength * (1 + [-1, 0, 1] * 1e-7);
at_peak = grating(near, p, L, centre, 0, 'uniform', p.sections);
kappa_peak = pi * p.visibility * p.index_change / peak_wavelength;
delay_difference = NaN;
if kappa_peak > 0
  exact_delay = p.effective_index * tanh(kappa_peak * L) / (kappa_peak * c);
  delays = group_delay(at_peak, near, c);
  delay_difference = delays(2) / exact_delay - 1;
end

[peak, at] = max(R);
peak_position = NaN;
band = NaN;
slope = NaN;
if peak > 0
  peak_position = wavelength(at);
  inside = find(R >= peak / 2);
  band = wavelength(inside(end)) - wavelength(inside(1));
  slope = 0;
  if numel(inside) > 2
    fit = polyfit(wavelength(inside), delay(inside) * 1e12, 1);
    slope = fit(1);
  end
end

RESULT = struct();
RESULT.peak_reflectance = peak;
RESULT.peak_wavelength_nm = peak_position;
RESULT.bandwidth_nm = band;
RESULT.delay_slope_ps_per_nm = slope;
RESULT.coupling_times_length = kappa_peak * L;
RESULT.checks = struct('energy_error', max(abs(1 - R - T)), ...
  'uniform_difference', max(abs(abs(plain) .^ 2 - exact)), ...
  'peak_difference', abs(at_peak(2)) ^ 2 - tanh(kappa_peak * L) ^ 2, ...
  'delay_difference', delay_difference);
over = {{'wavelength_nm'}};
RESULT.save = struct('file', 'spectrum', 'arrays', struct( ...
  'wavelength_nm', struct('values', wavelength, 'quantity', 'vacuum wavelength', 'unit', 'nm'), ...
  'R', struct('values', R, 'quantity', 'reflectance', 'unit', '1', 'axes', over), ...
  'T', struct('values', T, 'quantity', 'transmittance', 'unit', '1', 'axes', over), ...
  'delay_ps', struct('values', delay * 1e12, 'quantity', 'group delay of the reflected light', 'unit', 'ps', 'axes', over)));


function [rho, tau] = grating(lambda, p, L, centre, chirp, apodization, sections)
  % Amplitude reflection and transmission of the grating at each wavelength: the product of its section matrices.
  dz = L / sections;
  forward = ones(size(lambda));              % amplitudes at the far end: only the transmitted wave
  backward = zeros(size(lambda));
  for m = sections:-1:1
    z = (m - 0.5) * dz;
    switch apodization
      case 'gaussian'
        g = exp(-4 * log(2) * ((z - L / 2) / (L / 3)) ^ 2);    % full width at half maximum L/3
      case 'raised_cosine'
        g = 0.5 * (1 + cos(pi * (z - L / 2) / (L / 2)));
      otherwise
        g = 1;
    end
    kappa = pi * p.visibility * p.index_change * g ./ lambda;
    s = 2 * pi * p.effective_index * (1 ./ lambda - 1 / (centre + chirp * (z - L / 2))) + 2 * pi * p.index_change * g ./ lambda;
    q = sqrt(complex(kappa .^ 2 - s .^ 2));
    q(q == 0) = eps;
    ch = cosh(q * dz);
    sh = sinh(q * dz) ./ q;
    next = (ch - 1i * s .* sh) .* forward - 1i * kappa .* sh .* backward;
    backward = 1i * kappa .* sh .* forward + (ch + 1i * s .* sh) .* backward;
    forward = next;
  end
  rho = backward ./ forward;
  tau = 1 ./ forward;
end


function delay = group_delay(rho, lambda, c)
  % Seconds: -(lambda^2 / 2 pi c) d(phase)/d(lambda), by central differences inside and one-sided at the ends.
  if ~any(abs(rho))
    delay = NaN(size(lambda));
    return;
  end
  phase = unwrap(angle(rho));
  slope = zeros(size(lambda));
  slope(2:end-1) = (phase(3:end) - phase(1:end-2)) ./ (lambda(3:end) - lambda(1:end-2));
  slope(1) = (phase(2) - phase(1)) / (lambda(2) - lambda(1));
  slope(end) = (phase(end) - phase(end-1)) / (lambda(end) - lambda(end-1));
  delay = -lambda .^ 2 / (2 * pi * c) .* slope;
end
