# Ideal Gaussian beam

Use `gaussian-example/propagate` for a homogeneous medium in the paraxial
regime. `wavelength_um` is the wavelength in that medium; `waist_um` is the
field 1/e radius at the waist, and `distance_mm` is signed relative to it.
Use a wave solver for apertures, interfaces, aberrations or tightly focused
fields. At the waist, the wavefront is planar and its radius is returned as
`null`; the beam radius and Gouy phase remain defined.

`software_details(tool="gaussian-example", program="propagate")` gives all
defaults. Request `source=true` to adapt the program. The result states
length units in its field names and compares the propagated radius with the
complex beam parameter.
