#!/usr/bin/env python3
"""
Gaia Solar System Data Importer with XYZ Coordinates

This script queries the Gaia DR3 database for solar system objects
and exports their heliocentric XYZ coordinates from orbital data.
"""

import argparse
import sys
import numpy as np
from astroquery.gaia import Gaia
import pandas as pd


def query_solar_system_orbits(max_results=100, output_file='gaia_solar_system_xyz.csv'):
    """
    Query Gaia DR3 for solar system objects with heliocentric XYZ coordinates.
    
    Parameters:
    -----------
    max_results : int
        Maximum number of results to retrieve (default: 100)
    output_file : str
        Output CSV filename (default: gaia_solar_system_xyz.csv)
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame containing solar system object data with XYZ coordinates
    """
    
    print("Connecting to Gaia archive...")
    print(f"Querying solar system orbital data from Gaia DR3 (up to {max_results} objects)...")
    
    # Query the sso_orbits table which contains heliocentric state vectors
    # h_state_vector format: [X, Y, Z, Vx, Vy, Vz] in AU and AU/day
    query = f"""
    SELECT TOP {max_results}
        source_id,
        denomination,
        number_mp,
        num_of_obs,
        osc_epoch,
        h_state_vector,
        semi_major_axis,
        eccentricity,
        inclination,
        longitude_ascending_node,
        argument_perihelion,
        mean_anomaly
    FROM gaiadr3.sso_orbits
    WHERE h_state_vector IS NOT NULL
    ORDER BY num_of_obs DESC
    """
    
    try:
        # Execute the query
        job = Gaia.launch_job(query)
        results = job.get_results()
        
        # Convert to pandas DataFrame
        df = results.to_pandas()
        
        print(f"\nSuccessfully retrieved {len(df)} solar system objects with orbital data!")
        
        # Extract XYZ coordinates and velocities from state vector
        print("\nExtracting heliocentric XYZ coordinates from state vectors...")
        
        # h_state_vector is an array: [X, Y, Z, Vx, Vy, Vz]
        state_vectors = np.array([sv for sv in df['h_state_vector']])
        
        # Position in AU (heliocentric)
        df['x_au'] = state_vectors[:, 0]
        df['y_au'] = state_vectors[:, 1]
        df['z_au'] = state_vectors[:, 2]
        
        # Velocity in AU/day (heliocentric)
        df['vx_au_day'] = state_vectors[:, 3]
        df['vy_au_day'] = state_vectors[:, 4]
        df['vz_au_day'] = state_vectors[:, 5]
        
        # Calculate heliocentric distance
        df['heliocentric_distance_au'] = np.sqrt(
            df['x_au']**2 + df['y_au']**2 + df['z_au']**2
        )
        
        # Calculate velocity magnitude
        df['velocity_magnitude_au_day'] = np.sqrt(
            df['vx_au_day']**2 + df['vy_au_day']**2 + df['vz_au_day']**2
        )
        
        # Display summary statistics
        print("\n" + "="*70)
        print("SOLAR SYSTEM DATA SUMMARY")
        print("="*70)
        print(f"\nTotal objects retrieved: {len(df)}")
        print(f"Average observations per object: {df['num_of_obs'].mean():.0f}")
        
        print(f"\n--- OBJECT TYPES ---")
        print(f"Objects with Minor Planet number: {(df['number_mp'] > 0).sum()}")
        print(f"Sample objects:")
        for i, name in enumerate(df['denomination'].head(5)):
            print(f"  {i+1}. {name}")
        
        print(f"\n--- POSITION (Heliocentric Cartesian Coordinates in AU) ---")
        print(f"X range: {df['x_au'].min():.3f} to {df['x_au'].max():.3f} AU")
        print(f"Y range: {df['y_au'].min():.3f} to {df['y_au'].max():.3f} AU")
        print(f"Z range: {df['z_au'].min():.3f} to {df['z_au'].max():.3f} AU")
        
        print(f"\n--- DISTANCE FROM SUN ---")
        print(f"Closest: {df['heliocentric_distance_au'].min():.3f} AU")
        print(f"Farthest: {df['heliocentric_distance_au'].max():.3f} AU")
        print(f"Mean: {df['heliocentric_distance_au'].mean():.3f} AU")
        
        print(f"\n--- VELOCITY (Heliocentric) ---")
        print(f"Vx range: {df['vx_au_day'].min():.6f} to {df['vx_au_day'].max():.6f} AU/day")
        print(f"Vy range: {df['vy_au_day'].min():.6f} to {df['vy_au_day'].max():.6f} AU/day")
        print(f"Vz range: {df['vz_au_day'].min():.6f} to {df['vz_au_day'].max():.6f} AU/day")
        print(f"Speed range: {df['velocity_magnitude_au_day'].min():.6f} to {df['velocity_magnitude_au_day'].max():.6f} AU/day")
        
        print(f"\n--- ORBITAL ELEMENTS ---")
        print(f"Semi-major axis range: {df['semi_major_axis'].min():.3f} to {df['semi_major_axis'].max():.3f} AU")
        print(f"Eccentricity range: {df['eccentricity'].min():.4f} to {df['eccentricity'].max():.4f}")
        print(f"Inclination range: {np.degrees(df['inclination'].min()):.2f}° to {np.degrees(df['inclination'].max()):.2f}°")
        
        # Drop the array column before saving (CSV doesn't handle arrays well)
        df_export = df.drop(columns=['h_state_vector'])
        
        # Save to CSV
        df_export.to_csv(output_file, index=False)
        print(f"\n{'='*70}")
        print(f"Data exported to: {output_file}")
        print(f"{'='*70}\n")
        
        return df
        
    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def query_specific_object(object_name, output_file=None):
    """
    Query Gaia DR3 for a specific solar system object by name.
    
    Parameters:
    -----------
    object_name : str
        Name or designation of the solar system object
    output_file : str
        Output CSV filename (optional)
    
    Returns:
    --------
    pandas.DataFrame
        DataFrame containing the object's orbital data
    """
    
    print(f"Searching for '{object_name}' in Gaia DR3 solar system orbits...")
    
    # Escape single quotes to prevent ADQL injection
    sanitized_name = object_name.replace("'", "''")
    
    query = f"""
    SELECT 
        source_id,
        denomination,
        number_mp,
        num_of_obs,
        osc_epoch,
        h_state_vector,
        semi_major_axis,
        eccentricity,
        inclination,
        longitude_ascending_node,
        argument_perihelion,
        mean_anomaly
    FROM gaiadr3.sso_orbits
    WHERE LOWER(denomination) LIKE LOWER('%{sanitized_name}%')
        AND h_state_vector IS NOT NULL
    """
    
    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()
        
        if len(df) == 0:
            print(f"No orbital data found for '{object_name}'")
            return None
        
        print(f"\nFound orbital data for: {df['denomination'].iloc[0]}")
        
        # Extract coordinates
        state_vector = np.array(df['h_state_vector'].iloc[0])
        x, y, z = state_vector[0:3]
        vx, vy, vz = state_vector[3:6]
        distance = np.sqrt(x**2 + y**2 + z**2)
        
        print(f"\n--- HELIOCENTRIC POSITION (AU) ---")
        print(f"X: {x:.6f}")
        print(f"Y: {y:.6f}")
        print(f"Z: {z:.6f}")
        print(f"Distance from Sun: {distance:.6f} AU")
        
        print(f"\n--- HELIOCENTRIC VELOCITY (AU/day) ---")
        print(f"Vx: {vx:.8f}")
        print(f"Vy: {vy:.8f}")
        print(f"Vz: {vz:.8f}")
        
        print(f"\n--- ORBITAL ELEMENTS ---")
        print(f"Semi-major axis: {df['semi_major_axis'].iloc[0]:.6f} AU")
        print(f"Eccentricity: {df['eccentricity'].iloc[0]:.6f}")
        print(f"Inclination: {np.degrees(df['inclination'].iloc[0]):.4f}°")
        print(f"Number of observations: {df['num_of_obs'].iloc[0]}")
        
        if output_file:
            # Add XYZ columns
            df['x_au'] = x
            df['y_au'] = y
            df['z_au'] = z
            df['vx_au_day'] = vx
            df['vy_au_day'] = vy
            df['vz_au_day'] = vz
            df['heliocentric_distance_au'] = distance
            
            df_export = df.drop(columns=['h_state_vector'])
            df_export.to_csv(output_file, index=False)
            print(f"\nData exported to: {output_file}\n")
        
        return df
        
    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main function to handle command-line arguments."""
    
    parser = argparse.ArgumentParser(
        description='Query solar system data from Gaia DR3 with heliocentric XYZ coordinates'
    )
    
    parser.add_argument(
        '-n', '--max-results',
        type=int,
        default=100,
        help='Maximum number of results to retrieve (default: 100)'
    )
    
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='gaia_solar_system_xyz.csv',
        help='Output CSV filename (default: gaia_solar_system_xyz.csv)'
    )
    
    parser.add_argument(
        '-s', '--search',
        type=str,
        help='Search for a specific solar system object by name (e.g., Ceres, Vesta)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("GAIA SOLAR SYSTEM DATA IMPORTER (with XYZ Coordinates)")
    print("="*70 + "\n")
    
    if args.search:
        # Search for specific object
        query_specific_object(args.search, args.output)
    else:
        # Query general solar system data
        query_solar_system_orbits(args.max_results, args.output)


if __name__ == '__main__':
    main()
