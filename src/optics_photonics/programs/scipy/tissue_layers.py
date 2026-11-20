"""Diffuse reflectance, transmittance and absorption in depth of layered tissue (Monte Carlo photon transport).

A narrow beam enters a stack of flat layers at normal incidence. Each
layer has an absorption coefficient mu_a, a scattering coefficient mu_s, an
anisotropy g (the mean cosine of the Henyey-Greenstein phase function) and
an index n. Photon packets take free paths drawn from exp(-mu_t s),
mu_t = mu_a + mu_s, leave the fraction mu_a / mu_t of their weight at each
interaction, scatter, and at a boundary reflect or pass with the Fresnel
probability for unpolarized light; packets of small weight end by roulette
(the method of Wang, Jacques and Zheng, Comput. Methods Programs Biomed.
47, 131 (1995)). Packets carry energy and no phase, so there is no
interference. The program returns the specular and diffuse reflectance,
the transmittance, the absorbed fraction of each layer, the absorbed
fraction per depth, the fluence rate of a wide uniform beam per unit
irradiance, and the diffuse reflectance per area
against the distance from the beam. Statistical errors come from the
spread over ten groups of packets. Fluence is tallied from each packet's
weight times its path length inside each depth bin, including transparent
layers and bins that cross material interfaces. The same code computes a matched slab
whose values are known (van de Hulst: mu_a 1, mu_s 9 per mm, g 0.75,
0.2 mm thick: diffuse reflectance 0.09739, transmittance 0.66096).
"""
import numpy as np
from optics_photonics import data
from optics_photonics.programs import parameters

PROGRAM = {
    'inputs': {
        'layers': ([{'mu_a_per_mm': 0.1, 'mu_s_per_mm': 10.0, 'g': 0.9, 'n': 1.4, 'thickness_mm': 2.0}],
                   'layers from the entrance: mu_a_per_mm, mu_s_per_mm, g, n and thickness_mm of each'),
        'n_above': (1.0, 'index of the medium the beam comes from'),
        'n_below': (1.0, 'index of the medium behind the last layer'),
        'packets': (50000, 'photon packets'),
        'depth_bins': (100, 'bins of the depth profile over the total thickness'),
        'radial_mm': (5.0, 'largest distance from the beam of the radial reflectance'),
        'radial_bins': (50, 'bins of the radial reflectance'),
        'seed': (1, 'seed of the random numbers'),
    },
    'domains': ['bio'],
    'results': 'transport.npz/.json: absorbed fraction per mm and fluence rate over depth, diffuse reflectance per area over the distance '
               'from the beam; specular and diffuse reflectance, transmittance and absorbed fraction of each layer, with standard errors',
    'checks': 'balance: reflectances + transmittance + absorbed fraction - 1; reference_reflectance and reference_transmittance: '
              'the matched slab of known values minus 0.09739 and 0.66096, with reference_error the standard errors',
}
p = parameters(PROGRAM, INPUTS)
GROUPS, FLOOR, CHANCE = 10, 1e-4, 0.1


def fresnel(n_in, n_out, cosine):
    """Reflectance of unpolarized light and the cosine of the refracted direction; 1 and 0 beyond the critical angle."""
    sine = n_in / n_out * np.sqrt(np.maximum(0.0, 1 - cosine ** 2))
    total = sine >= 1
    refracted = np.sqrt(np.maximum(0.0, 1 - sine ** 2))
    with np.errstate(divide='ignore', invalid='ignore'):
        s = ((n_in * cosine - n_out * refracted) / (n_in * cosine + n_out * refracted)) ** 2
        q = ((n_in * refracted - n_out * cosine) / (n_in * refracted + n_out * cosine)) ** 2
    return np.where(total, 1.0, (s + q) / 2), np.where(total, 0.0, refracted)


def transport(layers, n_above, n_below, packets, rng, depth_bins, radial_max, radial_bins):
    """Tallies of one group of packets: specular, diffuse reflectance, transmittance, absorbed per layer, per depth and R per radius."""
    mu_a, mu_s, g, n, thickness = (np.asarray([layer[key] for layer in layers], dtype=float)
                                   for key in ('mu_a_per_mm', 'mu_s_per_mm', 'g', 'n', 'thickness_mm'))
    edges = np.concatenate([[0.0], np.cumsum(thickness)])
    indices = np.concatenate([[n_above], n, [n_below]])
    mu_t = mu_a + mu_s
    specular = ((n_above - n[0]) / (n_above + n[0])) ** 2
    x, y, z = np.zeros(packets), np.zeros(packets), np.zeros(packets)
    ux, uy, uz = np.zeros(packets), np.zeros(packets), np.ones(packets)
    weight, layer, left = np.full(packets, 1 - specular), np.zeros(packets, dtype=int), np.zeros(packets)
    absorbed_layer, depth, radial = np.zeros(len(layers)), np.zeros(depth_bins), np.zeros(radial_bins)
    fluence, full_bins = np.zeros(depth_bins), np.zeros(depth_bins)
    bin_width = edges[-1] / depth_bins
    reflected = transmitted = 0.0
    while weight.size:
        fresh = left == 0
        left[fresh] = -np.log(1 - rng.random(fresh.sum()))              # free path in units of 1 / mu_t
        down = uz > 0
        boundary = np.where(down, edges[layer + 1], edges[layer])
        with np.errstate(divide='ignore', invalid='ignore'):
            to_boundary = np.where(uz != 0, (boundary - z) / uz, np.inf)
            to_event = left / mu_t[layer]
        hit = to_boundary <= to_event
        step = np.where(hit, to_boundary, to_event)
        x += ux * step
        y += uy * step
        end_z = np.where(hit, boundary, z + uz * step)
        # Track-length fluence: split each weighted path between the depth bins it crosses.
        low, high = np.minimum(z, end_z), np.maximum(z, end_z)
        first = np.clip((low / bin_width).astype(int), 0, depth_bins - 1)
        last = np.clip((high / bin_width).astype(int), 0, depth_bins - 1)
        crosses = first != last
        np.add.at(fluence, first[~crosses], weight[~crosses] * step[~crosses])
        density = weight[crosses] * step[crosses] / (high[crosses] - low[crosses])
        np.add.at(fluence, first[crosses], density * ((first[crosses] + 1) * bin_width - low[crosses]))
        np.add.at(fluence, last[crosses], density * (high[crosses] - last[crosses] * bin_width))
        # A difference array adds the full interior bins without a packets-by-bins allocation.
        np.add.at(full_bins, first[crosses] + 1, density * bin_width)
        np.add.at(full_bins, last[crosses], -density * bin_width)
        z = end_z
        left = np.where(hit, left - to_boundary * mu_t[layer], 0.0)
        alive = np.ones(weight.size, dtype=bool)

        event = np.flatnonzero(~hit)
        if event.size:
            lost = weight[event] * mu_a[layer[event]] / mu_t[layer[event]]
            weight[event] -= lost
            np.add.at(absorbed_layer, layer[event], lost)
            np.add.at(depth, np.minimum((z[event] / edges[-1] * depth_bins).astype(int), depth_bins - 1), lost)
            # Henyey-Greenstein deflection and a uniform azimuth.
            gl, r = g[layer[event]], rng.random(event.size)
            with np.errstate(divide='ignore', invalid='ignore'):
                cosine = np.where(gl == 0, 2 * r - 1, (1 + gl ** 2 - ((1 - gl ** 2) / (1 - gl + 2 * gl * r)) ** 2) / (2 * gl))
            cosine = np.clip(cosine, -1, 1)
            sine, azimuth = np.sqrt(1 - cosine ** 2), 2 * np.pi * rng.random(event.size)
            a, b, c = ux[event], uy[event], uz[event]
            across = np.sqrt(np.maximum(1e-30, 1 - c ** 2))
            steep = np.abs(c) > 0.99999
            ux[event] = np.where(steep, sine * np.cos(azimuth), sine * (a * c * np.cos(azimuth) - b * np.sin(azimuth)) / across + a * cosine)
            uy[event] = np.where(steep, sine * np.sin(azimuth), sine * (b * c * np.cos(azimuth) + a * np.sin(azimuth)) / across + b * cosine)
            uz[event] = np.where(steep, np.sign(c) * cosine, -sine * np.cos(azimuth) * across + c * cosine)

        wall = np.flatnonzero(hit)
        if wall.size:
            beyond = layer[wall] + np.where(down[wall], 1, -1)
            n_in, n_out = n[layer[wall]], indices[beyond + 1]
            reflectance, refracted = fresnel(n_in, n_out, np.abs(uz[wall]))
            back = rng.random(wall.size) < reflectance
            uz[wall[back]] *= -1
            through, target = wall[~back], beyond[~back]
            out_top, out_bottom = through[target < 0], through[target >= len(layers)]
            reflected += weight[out_top].sum()
            transmitted += weight[out_bottom].sum()
            ring = (np.hypot(x[out_top], y[out_top]) / radial_max * radial_bins).astype(int)
            np.add.at(radial, ring[ring < radial_bins], weight[out_top][ring < radial_bins])
            alive[out_top] = alive[out_bottom] = False
            inside = (target >= 0) & (target < len(layers))
            stay, ratio = through[inside], (n_in[~back] / n_out[~back])[inside]
            ux[stay] *= ratio
            uy[stay] *= ratio
            uz[stay] = np.sign(uz[stay]) * refracted[~back][inside]
            layer[stay] = target[inside]

        faint = np.flatnonzero(alive & (weight < FLOOR))
        if faint.size:
            survive = rng.random(faint.size) < CHANCE
            weight[faint[survive]] /= CHANCE
            alive[faint[~survive]] = False
        if not alive.all():
            x, y, z, ux, uy, uz, weight, layer, left = (v[alive] for v in (x, y, z, ux, uy, uz, weight, layer, left))
    return {'specular': specular, 'reflected': reflected / packets, 'transmitted': transmitted / packets,
            'absorbed': absorbed_layer / packets, 'depth': depth / packets, 'radial': radial / packets,
            'fluence': (fluence + np.cumsum(full_bins)) / packets}


def groups(layers, n_above, n_below, packets, seed, depth_bins, radial_max, radial_bins):
    """Mean and standard error of every tally over GROUPS independent groups of packets."""
    rng = np.random.default_rng(seed)
    runs = [transport(layers, n_above, n_below, max(packets // GROUPS, 1), rng, depth_bins, radial_max, radial_bins) for _ in range(GROUPS)]
    stacked = {key: np.asarray([run[key] for run in runs]) for key in runs[0]}
    return ({key: values.mean(axis=0) for key, values in stacked.items()},
            {key: values.std(axis=0, ddof=1) / np.sqrt(GROUPS) for key, values in stacked.items()})


layers = p['layers']
names = ('mu_a_per_mm', 'mu_s_per_mm', 'g', 'n', 'thickness_mm')
if not layers or any(set(names) - set(layer) for layer in layers) or \
        any(layer['mu_a_per_mm'] < 0 or layer['mu_s_per_mm'] < 0 or not -1 < layer['g'] < 1 or layer['n'] < 1 or layer['thickness_mm'] <= 0
            for layer in layers) or int(p['packets']) < GROUPS or min(p['n_above'], p['n_below']) < 1:
    raise ValueError('Each layer has ' + ', '.join(names) + '; coefficients are not negative, g lies inside (-1, 1), indices are at least 1, '
                     f'thickness is positive and packets is at least {GROUPS}')
depth_bins, radial_bins, radial_max = int(p['depth_bins']), int(p['radial_bins']), float(p['radial_mm'])
if min(depth_bins, radial_bins, radial_max) <= 0:
    raise ValueError('depth_bins, radial_bins and radial_mm are positive')
mean, error = groups(layers, float(p['n_above']), float(p['n_below']), int(p['packets']), int(p['seed']), depth_bins, radial_max, radial_bins)
known, known_error = groups([{'mu_a_per_mm': 1.0, 'mu_s_per_mm': 9.0, 'g': 0.75, 'n': 1.0, 'thickness_mm': 0.2}], 1.0, 1.0,
                            50000, int(p['seed']) + 1, 1, 1.0, 1)

total = sum(layer['thickness_mm'] for layer in layers)
z_edges = np.linspace(0, total, depth_bins + 1)
z = (z_edges[:-1] + z_edges[1:]) / 2
per_mm = mean['depth'] / (total / depth_bins)
fluence = mean['fluence'] / (total / depth_bins)
r_edges = np.linspace(0, radial_max, radial_bins + 1)
r = (r_edges[:-1] + r_edges[1:]) / 2
area = np.pi * (r_edges[1:] ** 2 - r_edges[:-1] ** 2)
saved = data.save(OUTPUT_DIR / 'transport', {
    'absorbed_per_mm': data.quantity(per_mm, 'absorbed fraction of the incident power per depth', unit='1/mm', axes=['depth_mm']),
    'fluence_rate': data.quantity(fluence, 'fluence rate of a wide uniform beam per unit irradiance, from weighted path lengths', unit='1',
                                  axes=['depth_mm']),
    'depth_mm': data.quantity(z, 'depth from the entrance surface', unit='mm'),
    'reflectance_per_area': data.quantity(mean['radial'] / area, 'diffuse reflectance per area for unit incident power', unit='1/mm^2',
                                          axes=['radius_mm']),
    'reflectance_per_area_error': data.quantity(error['radial'] / area, 'standard error of the reflectance per area', unit='1/mm^2',
                                                axes=['radius_mm']),
    'radius_mm': data.quantity(r, 'distance from the beam on the entrance surface', unit='mm'),
})
RESULT = {
    'specular_reflectance': float(mean['specular']),
    'diffuse_reflectance': float(mean['reflected']), 'diffuse_reflectance_error': float(error['reflected']),
    'transmittance': float(mean['transmitted']), 'transmittance_error': float(error['transmitted']),
    'absorbed': [float(v) for v in mean['absorbed']], 'absorbed_error': [float(v) for v in error['absorbed']],
    'packets': int(p['packets']) // GROUPS * GROUPS, 'data': saved['data'],
    'checks': {'balance': float(mean['specular'] + mean['reflected'] + mean['transmitted'] + mean['absorbed'].sum() - 1),
               'reference_reflectance': float(known['reflected'] - 0.09739), 'reference_transmittance': float(known['transmitted'] - 0.66096),
               'reference_error': [float(known_error['reflected']), float(known_error['transmitted'])]},
}
