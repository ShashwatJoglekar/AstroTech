from typing import Tuple
def blackbody_wavelength(temperature: float):
    wien_constant = 2.89e-6  # Wien's displacement constant in meters Kelvin
    # Calculate the wavelength of peak emission using Wien's law
    peak_wavelength = wien_constant / temperature  # in meters
    # Convert to nanometers
    peak_wavelength_nm = peak_wavelength * 1e9  # convert to nanometers
    return peak_wavelength_nm

def wavelength_to_rgb(nm) -> Tuple:

    '''
    Takes a wavelength of visible light
    between 380 and 780 nanometres inclusive.
    Values outside this range will raise a ValueError.
    Returns a list of corresponding RGB values.
    Based on Dan Bruton's Fortran implementation.
    '''

    # raise error if nm is outside a (very generous) 
    # range of visible light
    if nm < 380 or nm > 780:

        raise ValueError("nm argument must be between 380 and 780")

    # a few variables for later use
    gamma = 0.8
    max_intensity = 255
    factor = 0

    # a dictionary with values initialised to 0
    # which will be calculated later
    rgb = {"R": 0, "G": 0, "B": 0}

    # set RGB values depending on ranges of wavelength
    if 380 <= nm <= 439:
        rgb["R"] = -(nm - 440) / (440 - 380)
        rgb["G"] = 0.0
        rgb["B"] = 1.0
    elif 440 <= nm <= 489:
        rgb["R"] = 0.0
        rgb["G"] = (nm - 440) / (490 - 440)
        rgb["B"] = 1.0
    elif 490 <= nm <= 509:
        rgb["R"] = 0.0
        rgb["G"] = 1.0
        rgb["B"] = -(nm - 510) / (510 - 490)
    elif 510 <= nm <= 579:
        rgb["R"] = (nm - 510) / (580 - 510)
        rgb["G"] = 1.0
        rgb["B"] = 0.0
    elif 580 <= nm <= 644:
        rgb["R"] = 1.0
        rgb["G"] = -(nm - 645) / (645 - 580)
        rgb["B"] = 0.0
    elif 645 <= nm <= 780:
        rgb["R"] = 1.0
        rgb["G"] = 0.0
        rgb["B"] = 0.0

    # calculate a factor (value to multiply by)
    # depending on range of nm
    if 380 <= nm <= 419:
        factor = 0.3 + 0.7 * (nm - 380) / (420 - 380)
    elif 420 <= nm <= 700:
        factor = 1.0
    elif 701 <= nm <= 780:
        factor = 0.3 + 0.7 * (780 - nm) / (780 - 700)

    # adjust RGB values using various variables if > 0
    # else set to 0
    if rgb["R"] > 0:
        rgb["R"] = int(max_intensity * ((rgb["R"] * factor) ** gamma))
    else:
        rgb["R"] = 0

    if rgb["G"] > 0:
        rgb["G"] = int(max_intensity * ((rgb["G"] * factor) ** gamma))
    else:
        rgb["G"] = 0

    if rgb["B"] > 0:
        rgb["B"] = int(max_intensity * ((rgb["B"] * factor) ** gamma))
    else:
        rgb["B"] = 0

    return (rgb["R"], rgb["G"], rgb["B"])
