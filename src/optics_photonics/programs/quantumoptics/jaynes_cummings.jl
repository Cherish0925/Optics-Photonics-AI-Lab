# Rabi oscillations and damped dynamics of a two-level atom in a cavity mode: the Jaynes-Cummings model (QuantumOptics.jl).
#
# In the frame rotating at the atomic frequency the Hamiltonian is
# H / hbar = Delta a'a + g (a' sigma- + a sigma+), with the cavity-atom
# detuning Delta and the coupling g; the cavity loses photons at the rate
# kappa and the atom decays at the rate gamma (collapse operators
# sqrt(kappa) a and sqrt(gamma) sigma-). The atom starts excited with n
# photons in the cavity. Without losses the Schroedinger equation is solved
# and the excited-state population is compared with the exact result
# P_e(t) = 1 - (4 g^2 (n+1) / Omega^2) sin^2(Omega t / 2),
# Omega^2 = Delta^2 + 4 g^2 (n+1): vacuum Rabi oscillations at 2g for n = 0.
# With losses the Lindblad master equation is solved; for kappa much larger
# than g the atom then decays at the Purcell rate 4 g^2 / kappa. Rates are
# given as frequencies in MHz (g / 2 pi and so on), times in microseconds.
#
# PROGRAM
# {"inputs": {
#   "coupling_mhz": [1.0, "atom-cavity coupling g / 2 pi in MHz"],
#   "detuning_mhz": [0.0, "cavity minus atom frequency, Delta / 2 pi, in MHz"],
#   "photons": [0, "photons in the cavity at the start"],
#   "cavity_decay_mhz": [0.0, "cavity energy decay rate kappa / 2 pi in MHz"],
#   "atom_decay_mhz": [0.0, "atomic decay rate gamma / 2 pi in MHz"],
#   "duration_us": [2.0, "duration in microseconds"],
#   "samples": [201, "times at which the state is recorded"],
#   "cutoff": [20, "largest photon number of the Fock basis"]},
#  "domains": ["quantum"],
#  "results": "dynamics.npz/.json: excited-state population and mean photon number over time, with the exact population when there are no losses; the Rabi frequency and the final populations",
#  "checks": "rabi_difference: largest difference of the excited-state population from the exact result (no losses); excitation_change: largest change of the total excitation number (no losses)"}
using QuantumOptics

g, delta = 2pi * INPUTS["coupling_mhz"], 2pi * INPUTS["detuning_mhz"]
kappa, gamma = 2pi * INPUTS["cavity_decay_mhz"], 2pi * INPUTS["atom_decay_mhz"]
n, cutoff, samples = INPUTS["photons"], INPUTS["cutoff"], INPUTS["samples"]
if g < 0 || kappa < 0 || gamma < 0 || n < 0 || cutoff <= n || samples < 2 || INPUTS["duration_us"] <= 0
    error("coupling and decay rates are not negative, photons lies below cutoff, samples >= 2 and duration_us is positive")
end

cavity, atom = FockBasis(cutoff), SpinBasis(1 // 2)
a = destroy(cavity) ⊗ identityoperator(atom)
lower = identityoperator(cavity) ⊗ sigmam(atom)
H = delta * dagger(a) * a + g * (dagger(a) * lower + a * dagger(lower))
initial = fockstate(cavity, n) ⊗ spinup(atom)
times = collect(range(0.0, INPUTS["duration_us"], length=samples))
lossless = kappa == 0 && gamma == 0
if lossless
    _, states = timeevolution.schroedinger(times, initial, H)
else
    jumps = [sqrt(rate) * operator for (rate, operator) in ((kappa, a), (gamma, lower)) if rate > 0]
    _, states = timeevolution.master(times, initial, H, jumps)
end
excited = real(expect(dagger(lower) * lower, states))
photons = real(expect(dagger(a) * a, states))

rabi = sqrt(delta^2 + 4 * g^2 * (n + 1))
exact = rabi == 0 ? ones(length(times)) : [1 - 4 * g^2 * (n + 1) / rabi^2 * sin(rabi * t / 2)^2 for t in times]
arrays = Dict{String,Any}(
    "time_us" => Dict("values" => times, "quantity" => "time", "unit" => "us"),
    "excited" => Dict("values" => excited, "quantity" => "population of the excited atomic state", "unit" => "1", "axes" => ["time_us"]),
    "photons" => Dict("values" => photons, "quantity" => "mean photon number in the cavity", "unit" => "1", "axes" => ["time_us"]))
if lossless
    arrays["excited_exact"] = Dict("values" => exact, "quantity" => "exact population of the excited state without losses", "unit" => "1", "axes" => ["time_us"])
end
RESULT = Dict{String,Any}(
    "rabi_frequency_mhz" => rabi / 2pi, "final_excited" => excited[end], "final_photons" => photons[end],
    "purcell_rate_per_us" => kappa > 0 ? 4 * g^2 / kappa : nothing,
    "checks" => Dict("rabi_difference" => lossless ? maximum(abs.(excited .- exact)) : nothing,
                     "excitation_change" => lossless ? maximum(abs.(excited .+ photons .- (n + 1))) : nothing),
    "save" => Dict("file" => "dynamics", "arrays" => arrays))
