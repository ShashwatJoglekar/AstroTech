#!/usr/bin/env python3
"""
Gaia Solar System Data Importer

This script queries the Gaia DR3 database for solar system objects
and exports the data to CSV format with summary statistics.
"""

import argparse
import sys
from pathlib import Path
from astroquery.gaia import Gaia
import pandas as pd
import numpy as np
import time

IMPORTANT_NAMES = [
    # Planets
    'Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune',
    # Dwarf planets
    'Pluto', 'Ceres', 'Haumea', 'Makemake', 'Eris', 'Vesta', 'Pallas', 'Hygiea',
    # Major satellites (examples, add more as needed)
    'Moon', 'Io', 'Europa', 'Ganymede', 'Callisto', 'Amalthea', 'Himalia', 'Elara', 'Pasiphae', 'Sinope', 'Lysithea', 'Carme', 'Ananke', 'Leda',
    'Metis', 'Adrastea', 'Thebe', 'Themisto', 'Megaclite', 'Taygete', 'Chaldene', 'Harpalyke', 'Kalyke', 'Iocaste', 'Erinome', 'Isonoe', 'Praxidike', 'Autonoe', 'Thyone', 'Hermippe', 'Aitne', 'Eurydome', 'Euanthe', 'Euporie', 'Orthosie', 'Sponde', 'Kale', 'Pasithee', 'Hegemone', 'Mneme', 'Aoede', 'Thelxinoe', 'Arche', 'Kallichore', 'Helike', 'Carpo', 'Eukelade', 'Cyllene', 'Kore', 'Herse',
    'Titan', 'Rhea', 'Iapetus', 'Dione', 'Tethys', 'Enceladus', 'Mimas', 'Hyperion', 'Phoebe', 'Janus', 'Epimetheus', 'Helene', 'Telesto', 'Calypso', 'Atlas', 'Prometheus', 'Pandora', 'Pan', 'Ymir', 'Paaliaq', 'Tarvos', 'Ijiraq', 'Suttungr', 'Kiviuq', 'Mundilfari', 'Albiorix', 'Skathi', 'Erriapus', 'Siarnaq', 'Thrymr', 'Narvi', 'Methone', 'Pallene', 'Polydeuces', 'Daphnis', 'Aegir', 'Bebhionn', 'Bergelmir', 'Bestla', 'Farbauti', 'Fenrir', 'Fornjot', 'Hati', 'Hyrrokkin', 'Kari', 'Loge', 'Skoll', 'Surtur', 'Anthe', 'Jarnsaxa', 'Greip', 'Tarqeq', 'Aegaeon',
    'Miranda', 'Ariel', 'Umbriel', 'Titania', 'Oberon', 'Caliban', 'Sycorax', 'Prospero', 'Setebos', 'Stephano', 'Trinculo', 'Francisco', 'Margaret', 'Ferdinand', 'Perdita', 'Mab', 'Cupid', 'Portia', 'Rosalind', 'Belinda', 'Cressida', 'Desdemona', 'Juliet', 'Ophelia', 'Bianca', 'Puck',
    'Triton', 'Nereid', 'Naiad', 'Thalassa', 'Despina', 'Galatea', 'Larissa', 'Proteus', 'Halimede', 'Psamathe', 'Sao', 'Laomedeia', 'Neso',
    'Charon', 'Styx', 'Nix', 'Kerberos', 'Hydra'
]
NAMES_LIST = "', '".join(IMPORTANT_NAMES)

def query_gaia_solar_system(max_results=100, output_file='gaia_solar_system_data.csv'):
    """
    Query Gaia DR3 for solar system objects, prioritizing important objects and a random sample of asteroids.
    Restrictive conditions: g_mag < 18, only up to 2 measurements per object.
    """
    print("Connecting to Gaia archive...")
    print("Querying solar system objects from Gaia DR3 (important objects + 5% random asteroids, g_mag < 18, max 2 per object)...")

    query = f"""
    SELECT TOP {max_results}
        source_id,
        denomination,
        number_mp,
        epoch,
        ra,
        dec,
        ra_error_random,
        dec_error_random,
        g_mag,
        position_angle_scan
    FROM gaiadr3.sso_observation
    WHERE (denomination IN ('{NAMES_LIST}')
           OR (number_mp IS NOT NULL AND RAND() < 0.05))
      AND g_mag < 18
    """

    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        # Keep only up to 2 measurements per object (by denomination, most recent epoch)
        df = df.sort_values(['denomination', 'epoch'], ascending=[True, False])
        df = df.groupby('denomination').head(2)

        print(f"\nSuccessfully retrieved {len(df)} solar system objects!")

        # Display summary statistics
        print("\n" + "="*60)
        print("DATA SUMMARY")
        print("="*60)
        print(f"\nTotal objects retrieved: {len(df)}")

        if len(df) > 0:
            print(f"\nObject types (denominations): {df['denomination'].nunique()} unique")

            print(f"\nSample of objects:")
            unique_objects = df['denomination'].unique()[:5]
            for obj in unique_objects:
                print(f"  - {obj}")

            print(f"\nMagnitude statistics (G-band):")
            print(f"  Mean: {df['g_mag'].mean():.2f}")
            print(f"  Min:  {df['g_mag'].min():.2f}")
            print(f"  Max:  {df['g_mag'].max():.2f}")

            print(f"\nPosition accuracy (RA random error):")
            print(f"  Mean: {df['ra_error_random'].mean():.4f} mas")
            print(f"  Min:  {df['ra_error_random'].min():.4f} mas")
            print(f"  Max:  {df['ra_error_random'].max():.4f} mas")

            print(f"\nEpoch range:")
            print(f"  Earliest: {df['epoch'].min():.2f}")
            print(f"  Latest:   {df['epoch'].max():.2f}")

        # Save to CSV
        df.to_csv(output_file, index=False)
        print(f"\n{'='*60}")
        print(f"Data exported to: {output_file}")
        print(f"{'='*60}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)

def query_specific_object(object_name, output_file=None):
    """
    Query Gaia DR3 for a specific solar system object by name.
    """
    print(f"Searching for '{object_name}' in Gaia DR3...")

    sanitized_name = object_name.replace("'", "''")

    query = f"""
    SELECT 
        source_id,
        denomination,
        number_mp,
        epoch,
        ra,
        dec,
        ra_error_random,
        dec_error_random,
        g_mag,
        position_angle_scan
    FROM gaiadr3.sso_observation
    WHERE LOWER(denomination) LIKE LOWER('%{sanitized_name}%')
      AND g_mag < 18
    """
    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        # Keep only up to 2 measurements per object (by denomination, most recent epoch)
        df = df.sort_values(['denomination', 'epoch'], ascending=[True, False])
        df = df.groupby('denomination').head(2)

        if len(df) == 0:
            print(f"No objects found matching '{object_name}'")
            return None

        print(f"\nFound {len(df)} observation(s) for '{object_name}'")
        print("\n" + "="*60)
        print(df.to_string(index=False))
        print("="*60 + "\n")

        if output_file:
            df.to_csv(output_file, index=False)
            print(f"Data exported to: {output_file}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)

def download_all_sso(batch_size=10000, output_file='gaia_sso_full.csv'):
    """
    Download all important objects and a random 5% of asteroids using source_id as a cursor,
    and keep only up to 2 measurements per object (by denomination, most recent epoch).
    Restrictive conditions: g_mag < 18.
    """
    total_rows = 0
    first_batch = True
    last_id = -9223372036854775808  # Smallest possible int64
    seen = set()  # Track objects already written

    while True:
        print(f"Querying batch starting after source_id {last_id}...")
        query = f"""
        SELECT TOP {batch_size}
            source_id,
            denomination,
            number_mp,
            epoch,
            ra,
            dec,
            ra_error_random,
            dec_error_random,
            g_mag,
            position_angle_scan
        FROM gaiadr3.sso_observation
        WHERE (denomination IN ('{NAMES_LIST}')
               OR (number_mp IS NOT NULL AND RAND() < 0.05))
          AND g_mag < 18
          AND source_id > {last_id}
        ORDER BY source_id
        """
        try:
            job = Gaia.launch_job_async(query)
            results = job.get_results()
            df = results.to_pandas()
        except Exception as e:
            print(f"Error: {e}")
            print("Retrying in 30 seconds...")
            time.sleep(30)
            continue

        if df.empty:
            print("No more data.")
            break

        # Sort and keep only up to 2 measurements per object (by denomination, most recent epoch)
        df = df.sort_values(['denomination', 'epoch'], ascending=[True, False])
        df = df.groupby('denomination').head(2)

        # Remove objects already written (to ensure max 2 per object in the whole file)
        df = df[~df['denomination'].isin(seen)]
        seen.update(df['denomination'].tolist())

        if df.empty:
            last_id = df['source_id'].max()
            continue

        df.to_csv(output_file, mode='a', header=first_batch, index=False)
        first_batch = False
        total_rows += len(df)
        print(f"Saved {len(df)} rows (total: {total_rows})")

        last_id = df['source_id'].max()

    print(f"Download complete. Total rows: {total_rows}")

def main():
    """Main function to handle command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Query and import solar system data from the Gaia DR3 database'
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
        default='gaia_solar_system_data.csv',
        help='Output CSV filename (default: gaia_solar_system_data.csv)'
    )
    parser.add_argument(
        '-s', '--search',
        type=str,
        help='Search for a specific solar system object by name'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Download the entire gaiadr3.sso_observation table in batches'
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("GAIA SOLAR SYSTEM DATA IMPORTER")
    print("="*60 + "\n")

    if args.all:
        download_all_sso(output_file=args.output)
    elif args.search:
        query_specific_object(args.search, args.output)
    else:
        query_gaia_solar_system(args.max_results, args.output)

if __name__ == '__main__':
    main()