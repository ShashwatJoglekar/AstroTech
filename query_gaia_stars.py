#!/usr/bin/env python3
"""
Gaia Stellar Data Importer
This script queries the Gaia DR3 database for non-solar system objects (stars)
and exports the data to CSV format with summary statistics.
"""

import argparse
import sys
from astroquery.gaia import Gaia
import pandas as pd
import numpy as np

# Default sky region: area rich in bright nearby stars
DEFAULT_RA     = 100.0  # degrees
DEFAULT_DEC    = 10.0   # degrees
DEFAULT_RADIUS = 30.0   # degrees


def query_gaia_stars(max_results=100, min_parallax=1.0, max_mag=15.0,
                     ra=DEFAULT_RA, dec=DEFAULT_DEC, radius=DEFAULT_RADIUS,
                     output_file='gaia_stars_data.csv'):
    """
    Query Gaia DR3 for stars within a sky region.

    Parameters:
    -----------
    max_results : int
        Maximum number of results to retrieve.
    min_parallax : float
        Minimum parallax in mas (1.0 mas ~= 1000 pc).
    max_mag : float
        Maximum G-band magnitude (brighter than this).
    ra : float
        Right Ascension of search cone center (degrees).
    dec : float
        Declination of search cone center (degrees).
    radius : float
        Search cone radius (degrees).
    output_file : str
        Output CSV filename.
    """
    print("Connecting to Gaia archive...")
    print(f"Sky region: RA={ra}, Dec={dec}, radius={radius} deg")
    print(f"Querying stars from Gaia DR3 (G mag < {max_mag}, parallax > {min_parallax} mas, max {max_results})...")

    # No ORDER BY — forces a full sort of all matches before returning results, causing timeouts.
    # No inline SQL comments (--) — ADQL does not support them.
    # CONTAINS+CIRCLE uses Gaia's spatial index to avoid scanning the full 1.8B-row table.
    query = f"""
    SELECT TOP {max_results}
        source_id,
        ra,
        dec,
        parallax,
        parallax_error,
        pmra,
        pmdec,
        phot_g_mean_mag,
        phot_bp_mean_mag,
        phot_rp_mean_mag,
        radial_velocity,
        l,
        b
    FROM gaiadr3.gaia_source
    WHERE CONTAINS(
        POINT('ICRS', ra, dec),
        CIRCLE('ICRS', {ra}, {dec}, {radius})
    ) = 1
      AND phot_g_mean_mag < {max_mag}
      AND parallax > {min_parallax}
      AND parallax_over_error > 10
    """

    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        if len(df) == 0:
            print("No objects found. Try raising --max-mag, lowering --min-parallax, or widening --radius.")
            sys.exit(1)

        print(f"\nSuccessfully retrieved {len(df)} objects!")

        df['distance_pc'] = 1000.0 / df['parallax']
        df['bp_rp'] = df['phot_bp_mean_mag'] - df['phot_rp_mean_mag']

        print("\n" + "="*60)
        print("STELLAR DATA SUMMARY")
        print("="*60)
        print(f"Total objects retrieved: {len(df)}")
        print(f"Magnitude range (G): {df['phot_g_mean_mag'].min():.2f} to {df['phot_g_mean_mag'].max():.2f}")
        print(f"Distance range: {df['distance_pc'].min():.1f} to {df['distance_pc'].max():.1f} pc")

        rv_count = df['radial_velocity'].notna().sum()
        print(f"Objects with radial velocity: {rv_count}")

        df.to_csv(output_file, index=False)
        print(f"\n{'='*60}")
        print(f"Data exported to: {output_file}")
        print(f"{'='*60}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def query_by_region(ra, dec, radius=0.1, max_results=100, output_file=None):
    """Query stars within a circular region around given RA/Dec."""
    print(f"Searching region around RA={ra}, Dec={dec} (radius={radius} deg)...")

    query = f"""
    SELECT TOP {max_results}
        source_id, ra, dec, parallax, phot_g_mean_mag, radial_velocity
    FROM gaiadr3.gaia_source
    WHERE CONTAINS(
        POINT('ICRS', ra, dec),
        CIRCLE('ICRS', {ra}, {dec}, {radius})
    ) = 1
    """

    try:
        job = Gaia.launch_job(query)
        results = job.get_results()
        df = results.to_pandas()

        if len(df) == 0:
            print("No objects found in this region.")
            return None

        print(f"Found {len(df)} objects in region.")
        print(df.head())

        if output_file:
            df.to_csv(output_file, index=False)
            print(f"Saved to {output_file}")

        return df

    except Exception as e:
        print(f"Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Query stellar data from Gaia DR3')
    parser.add_argument('-n', '--num', type=int, default=100,
                        help='Max results (default: 100)')
    parser.add_argument('-p', '--min-parallax', type=float, default=1.0,
                        help='Min parallax in mas (default: 1.0)')
    parser.add_argument('-m', '--max-mag', type=float, default=15.0,
                        help='Max G-band magnitude (default: 15.0)')
    parser.add_argument('-o', '--output', type=str, default='gaia_stars_data.csv',
                        help='Output CSV')
    parser.add_argument('--ra', type=float, default=DEFAULT_RA,
                        help=f'RA of search cone center in degrees (default: {DEFAULT_RA})')
    parser.add_argument('--dec', type=float, default=DEFAULT_DEC,
                        help=f'Dec of search cone center in degrees (default: {DEFAULT_DEC})')
    parser.add_argument('--radius', type=float, default=DEFAULT_RADIUS,
                        help=f'Search cone radius in degrees (default: {DEFAULT_RADIUS})')

    args = parser.parse_args()

    if args.ra is not None and args.dec is not None:
        query_gaia_stars(args.num, args.min_parallax, args.max_mag,
                         args.ra, args.dec, args.radius, args.output)
    else:
        query_gaia_stars(args.num, args.min_parallax, args.max_mag,
                         output_file=args.output)


if __name__ == '__main__':
    main()