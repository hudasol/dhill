"""Physical constants (SI units)."""

SIGMA_SB = 5.670374419e-8  # Stefan-Boltzmann constant, W m^-2 K^-4
G_ACC = 9.80665  # standard gravity, m s^-2
R_GAS = 8.314462618  # universal gas constant, J mol^-1 K^-1
R_AIR = 287.05  # specific gas constant of dry air, J kg^-1 K^-1
CP_AIR = 1007.0  # specific heat of air near 300 K, J kg^-1 K^-1
K0 = 273.15  # 0 degC in kelvin
T_REF_K = 298.15  # 25 degC, reference temperature for ageing and resistance
P_SEA_LEVEL = 101325.0  # Pa


def c_to_k(t_c):
    """Celsius to kelvin (works on floats and arrays)."""
    return t_c + K0


def k_to_c(t_k):
    """Kelvin to Celsius (works on floats and arrays)."""
    return t_k - K0


def pressure_at_elevation(elev_m: float) -> float:
    """Standard-atmosphere pressure (Pa) at an elevation above sea level."""
    return P_SEA_LEVEL * (1.0 - 2.25577e-5 * elev_m) ** 5.25588
