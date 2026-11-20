-- Transmission and reflection of a photonic-crystal slab at normal incidence over frequency (S4, Fourier modal method).
--
-- A dielectric slab of permittivity epsilon and thickness d carries a square
-- lattice of period a of round air holes of radius r; vacuum lies above and
-- below. S4 expands the fields of each layer in harmonics plane waves of the
-- lattice and matches them at the interfaces (Liu and Fan, Comput. Phys.
-- Commun. 183, 2233 (2012)). A plane wave polarized along x arrives along z.
-- Lengths are in periods a and frequencies in c/a, so that the vacuum
-- wavelength is a / frequency. The spectrum shows the Fabry-Perot fringes of
-- the slab with sharp asymmetric (Fano) lines where the wave couples to
-- guided resonances of the patterned slab, as in Fan and Joannopoulos, Phys.
-- Rev. B 65, 235112 (2002), whose slab is the default (epsilon 12, d = 0.5 a,
-- r = 0.2 a). The same slab without holes is computed as well and compared
-- with the Airy formula T = 1 / (1 + F sin^2(2 pi n d f)), F = 4R/(1-R)^2,
-- R = ((n-1)/(n+1))^2. Results converge with the number of harmonics.
--
-- PROGRAM
-- {"inputs": {
--   "epsilon": [12.0, "relative permittivity of the slab"],
--   "thickness": [0.5, "slab thickness in periods"],
--   "radius": [0.2, "hole radius in periods; 0 leaves the slab uniform"],
--   "frequency": [{"start": 0.25, "stop": 0.6, "points": 141}, "frequencies in c/a: a list, or {start, stop, points}"],
--   "harmonics": [80, "plane-wave harmonics retained"]},
--  "results": "spectrum.npz/.json: transmittance and reflectance over frequency; the deepest transmission minimum and its frequency, the mean transmittance",
--  "checks": "energy_error: largest |1 - R - T|; airy_difference: largest difference of the slab without holes from the Airy formula"}

local frequencies = {}
if INPUTS.frequency.points then
  local f = INPUTS.frequency
  for i = 0, f.points - 1 do
    frequencies[#frequencies + 1] = f.start + (f.stop - f.start) * i / math.max(f.points - 1, 1)
  end
else
  frequencies = INPUTS.frequency
end
if INPUTS.epsilon <= 1 or INPUTS.thickness <= 0 or INPUTS.radius < 0 or INPUTS.radius >= 0.5 then
  error("epsilon exceeds 1, thickness is positive and radius lies in [0, 0.5)")
end

local function spectrum(radius, harmonics)
  local S = S4.NewSimulation()
  S:SetLattice({1, 0}, {0, 1})
  S:SetNumG(harmonics)
  S:AddMaterial("Vacuum", {1, 0})
  S:AddMaterial("Dielectric", {INPUTS.epsilon, 0})
  S:AddLayer("Above", 0, "Vacuum")
  S:AddLayer("Slab", INPUTS.thickness, "Dielectric")
  if radius > 0 then
    S:SetLayerPatternCircle("Slab", "Vacuum", {0, 0}, radius)
  end
  S:AddLayerCopy("Below", 0, "Above")
  S:SetExcitationPlanewave({0, 0}, {0, 0}, {1, 0})
  local T, R = {}, {}
  for i, frequency in ipairs(frequencies) do
    S:SetFrequency(frequency)
    local incident, reflected = S:GetPoyntingFlux("Above", 0)
    T[i] = S:GetPoyntingFlux("Below", 0) / incident
    R[i] = -reflected / incident
  end
  return T, R
end

local T, R = spectrum(INPUTS.radius, INPUTS.harmonics)
local uniform = spectrum(0, 1)
local n = math.sqrt(INPUTS.epsilon)
local reflectance = ((n - 1) / (n + 1)) ^ 2
local finesse = 4 * reflectance / (1 - reflectance) ^ 2
local energy, airy, lowest, at, mean = 0, 0, math.huge, 0, 0
for i, frequency in ipairs(frequencies) do
  energy = math.max(energy, math.abs(1 - R[i] - T[i]))
  local exact = 1 / (1 + finesse * math.sin(2 * math.pi * n * INPUTS.thickness * frequency) ^ 2)
  airy = math.max(airy, math.abs(uniform[i] - exact))
  if T[i] < lowest then lowest, at = T[i], frequency end
  mean = mean + T[i] / #frequencies
end

RESULT = {
  minimum_transmittance = lowest, minimum_at_frequency = at, mean_transmittance = mean,
  checks = {energy_error = energy, airy_difference = airy},
  save = {file = "spectrum", arrays = {
    frequency = {values = frequencies, quantity = "frequency in units of c/a", unit = "c/a"},
    T = {values = T, quantity = "transmittance", unit = "1", axes = {"frequency"}},
    R = {values = R, quantity = "reflectance", unit = "1", axes = {"frequency"}},
    T_uniform = {values = uniform, quantity = "transmittance of the slab without holes", unit = "1", axes = {"frequency"}}}}
}
