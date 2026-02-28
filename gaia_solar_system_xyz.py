#!/usr/bin/env python3
"""
Gaia Solar System Data Importer with XYZ Coordinates
Queries named solar system objects only (excludes provisional designations).
"""

import argparse
import sys
import numpy as np
from astroquery.gaia import Gaia
import pandas as pd


def is_provisional_designation(name):
    """Returns True if the name looks like a provisional designation (e.g. 1993_DV, 2000 CJ82)."""
    import re
    return bool(re.match(r'^\d{4}[_ ]', str(name)))


def query_solar_system_orbits(max_results=100, output_file='gaia_solar_system_xyz.csv'):
    print("Connecting to Gaia archive...")
    print(f"Querying named solar system objects from Gaia DR3 (target: {max_results} objects)...")

    # Fetch more than needed from SQL so we have enough left after filtering unnamed ones
    fetch_limit = max_results * 5

    query = f"""
    SELECT TOP {fetch_limit}
        denomination,
        number_mp,
        num_observations,
        osc_epoch,
        h_state_vector,
        semi_major_axis,
        eccentricity,
        inclination,
        long_asc_node,
        arg_perihelion,
        mean_anomaly
    FROM gaiadr3.sso_orbits
    WHERE h_state_vector IS NOT NULL
      AND number_mp IS NOT NULL
    ORDER BY num_observations DESC
    """

    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        # Filter out provisional designations (e.g. 1993_DV, 2000_CJ82)
        df = df[~df['denomination'].apply(is_provisional_designation)].reset_index(drop=True)

        # Trim to requested limit
        df = df.head(max_results)

        if len(df) == 0:
            print("No named objects found after filtering. Try increasing fetch_limit.")
            sys.exit(1)

        print(f"\nSuccessfully retrieved {len(df)} named solar system objects!")
        print("\nExtracting heliocentric XYZ coordinates from state vectors...")

        state_vectors = np.array([sv for sv in df['h_state_vector']])

        df['x_au'] = state_vectors[:, 0]
        df['y_au'] = state_vectors[:, 1]
        df['z_au'] = state_vectors[:, 2]
        df['vx_au_day'] = state_vectors[:, 3]
        df['vy_au_day'] = state_vectors[:, 4]
        df['vz_au_day'] = state_vectors[:, 5]

        df['heliocentric_distance_au'] = np.sqrt(df['x_au']**2 + df['y_au']**2 + df['z_au']**2)
        df['velocity_magnitude_au_day'] = np.sqrt(df['vx_au_day']**2 + df['vy_au_day']**2 + df['vz_au_day']**2)

        print("\n" + "="*70)
        print("SOLAR SYSTEM DATA SUMMARY")
        print("="*70)
        print(f"\nTotal named objects retrieved: {len(df)}")
        print(f"Average observations per object: {df['num_observations'].mean():.0f}")

        print(f"\n--- SAMPLE OBJECTS ---")
        for i, row in df[['denomination', 'number_mp']].head(10).iterrows():
            print(f"  {i+1}. {row['denomination']} (MP #{int(row['number_mp'])})")

        print(f"\n--- POSITION (Heliocentric Cartesian Coordinates in AU) ---")
        print(f"X range: {df['x_au'].min():.3f} to {df['x_au'].max():.3f} AU")
        print(f"Y range: {df['y_au'].min():.3f} to {df['y_au'].max():.3f} AU")
        print(f"Z range: {df['z_au'].min():.3f} to {df['z_au'].max():.3f} AU")

        print(f"\n--- DISTANCE FROM SUN ---")
        print(f"Closest:  {df['heliocentric_distance_au'].min():.3f} AU")
        print(f"Farthest: {df['heliocentric_distance_au'].max():.3f} AU")
        print(f"Mean:     {df['heliocentric_distance_au'].mean():.3f} AU")

        print(f"\n--- VELOCITY (Heliocentric) ---")
        print(f"Vx range: {df['vx_au_day'].min():.6f} to {df['vx_au_day'].max():.6f} AU/day")
        print(f"Vy range: {df['vy_au_day'].min():.6f} to {df['vy_au_day'].max():.6f} AU/day")
        print(f"Vz range: {df['vz_au_day'].min():.6f} to {df['vz_au_day'].max():.6f} AU/day")
        print(f"Speed range: {df['velocity_magnitude_au_day'].min():.6f} to {df['velocity_magnitude_au_day'].max():.6f} AU/day")

        print(f"\n--- ORBITAL ELEMENTS ---")
        print(f"Semi-major axis range: {df['semi_major_axis'].min():.3f} to {df['semi_major_axis'].max():.3f} AU")
        print(f"Eccentricity range:    {df['eccentricity'].min():.4f} to {df['eccentricity'].max():.4f}")
        print(f"Inclination range:     {np.degrees(df['inclination'].min()):.2f}° to {np.degrees(df['inclination'].max()):.2f}°")

        df_export = df.drop(columns=['h_state_vector'])
        df_export.to_csv(output_file, index=False)
        print(f"\n{'='*70}")
        print(f"Data exported to: {output_file}")
        print(f"{'='*70}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def query_specific_object(object_name, output_file=None):
    print(f"Searching for '{object_name}' in Gaia DR3 solar system orbits...")
    sanitized_name = object_name.replace("'", "''")

    query = f"""
    SELECT
        denomination,
        number_mp,
        num_observations,
        osc_epoch,
        h_state_vector,
        semi_major_axis,
        eccentricity,
        inclination,
        long_asc_node,
        arg_perihelion,
        mean_anomaly
    FROM gaiadr3.sso_orbits
    WHERE LOWER(denomination) LIKE LOWER('%{sanitized_name}%')
      AND h_state_vector IS NOT NULL
      AND number_mp IS NOT NULL
    """

    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        # Filter out provisional designations
        df = df[~df['denomination'].apply(is_provisional_designation)].reset_index(drop=True)

        if len(df) == 0:
            print(f"No named orbital data found for '{object_name}'")
            return None

        print(f"\nFound orbital data for: {df['denomination'].iloc[0]} (MP #{int(df['number_mp'].iloc[0])})")

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
        print(f"Semi-major axis:      {df['semi_major_axis'].iloc[0]:.6f} AU")
        print(f"Eccentricity:         {df['eccentricity'].iloc[0]:.6f}")
        print(f"Inclination:          {np.degrees(df['inclination'].iloc[0]):.4f}°")
        print(f"Number of observations: {df['num_observations'].iloc[0]}")

        if output_file:
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
    parser = argparse.ArgumentParser(
        description='Query named solar system objects from Gaia DR3 with heliocentric XYZ coordinates'
    )
    parser.add_argument('-n', '--max-results', type=int, default=100,
                        help='Number of named objects to retrieve (default: 100)')
    parser.add_argument('-o', '--output', type=str, default='gaia_solar_system_xyz.csv',
                        help='Output CSV file path')
    parser.add_argument('-s', '--search', type=str,
                        help='Search for a specific named object (e.g. --search ceres)')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("GAIA SOLAR SYSTEM DATA IMPORTER (Named Objects Only)")
    print("="*70 + "\n")

    if args.search:
        query_specific_object(args.search, args.output)
    else:
        query_solar_system_orbits(args.max_results, args.output)


if __name__ == '__main__':
    main()