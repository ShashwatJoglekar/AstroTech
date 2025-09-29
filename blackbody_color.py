def blackbody_wavelength(temperature: float):
    wien_constant = 2.89e-6  # Wien's displacement constant in meters Kelvin
    # Calculate the wavelength of peak emission using Wien's law
    peak_wavelength = wien_constant / temperature  # in meters
    # Convert to nanometers
    peak_wavelength_nm = peak_wavelength * 1e9  # convert to nanometers
    return peak_wavelength_nm

def wavelength_to_color(wavelength_nm: float):
    ## To be done
    return "To be done"