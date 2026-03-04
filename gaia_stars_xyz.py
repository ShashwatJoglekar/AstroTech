#!/usr/bin/env python3
"""
Gaia Stellar Data Importer with XYZ Coordinates
Queries the Gaia DR3 database for stars and converts their
spherical coordinates (RA, Dec, Parallax) into heliocentric Cartesian XYZ (pc).
"""

import argparse
import sys
import numpy as np
from astroquery.gaia import Gaia
import pandas as pd


PC_TO_AU = 206264.806  # 1 parsec in AU
PC_TO_LY = 3.26156     # 1 parsec in light-years

# Default sky region: area rich in bright nearby stars
DEFAULT_RA     = 100.0   # degrees
DEFAULT_DEC    = 10.0    # degrees
DEFAULT_RADIUS = 30.0    # degrees — wide enough to get 100+ bright nearby stars


def query_stars_xyz(max_results=100, min_parallax=1.0, max_mag=12.0,
                    ra=DEFAULT_RA, dec=DEFAULT_DEC, radius=DEFAULT_RADIUS,
                    output_file='gaia_stars_xyz.csv'):
    """
    Query Gaia DR3 for stars within a sky region and calculate their 3D positions.

    Parameters:
    -----------
    max_results : int
        Maximum number of stars to retrieve.
    min_parallax : float
        Minimum parallax in mas (higher = closer stars only; 1.0 mas ~= 1000 pc).
    max_mag : float
        Maximum G-band magnitude (lower = only bright stars).
    ra : float
        Right Ascension of search cone center (degrees).
    dec : float
        Declination of search cone center (degrees).
    radius : float
        Search cone radius (degrees). Larger = more sky coverage.
    output_file : str
        Output CSV filename.
    """
    print("Connecting to Gaia archive...")
    print(f"Sky region: RA={ra}, Dec={dec}, radius={radius} deg")
    print(f"Filters: G mag < {max_mag}, parallax > {min_parallax} mas")
    print(f"Target: up to {max_results} stars")
    print("Submitting async job (this may take 30-90 seconds)...\n")

    # CONTAINS+CIRCLE lets Gaia use its spatial index, avoiding a full 1.8B-row table scan.
    # launch_job_async is required for heavy queries — launch_job times out on large tables.
    query = f"""
    SELECT TOP {max_results}
        source_id,
        ra,
        dec,
        parallax,
        parallax_error,
        parallax_over_error,
        pmra,
        pmdec,
        phot_g_mean_mag,
        phot_bp_mean_mag,
        phot_rp_mean_mag,
        radial_velocity,
        radial_velocity_error,
        l,
        b
    FROM gaiadr3.gaia_source
    WHERE CONTAINS(
        POINT('ICRS', ra, dec),
        CIRCLE('ICRS', {ra}, {dec}, {radius})
    ) = 1
      AND parallax > {min_parallax}
      AND phot_g_mean_mag < {max_mag}
      AND parallax_over_error > 10
    ORDER BY phot_g_mean_mag ASC
    """

    try:
        job = Gaia.launch_job_async(query)
        results = job.get_results()
        df = results.to_pandas()

        if len(df) == 0:
            print("No stars found. Try: raising --max-mag, lowering --min-parallax, or widening --radius.")
            sys.exit(1)

        print(f"Successfully retrieved {len(df)} stars!")
        print("Calculating 3D heliocentric Cartesian coordinates...")

        # Distance: d(pc) = 1000 / parallax(mas)
        df['distance_pc'] = 1000.0 / df['parallax']
        df['distance_ly'] = df['distance_pc'] * PC_TO_LY

        # Spherical -> Cartesian (Heliocentric ICRS)
        # X: toward RA=0,  Dec=0
        # Y: toward RA=90, Dec=0
        # Z: toward Dec=+90 (north celestial pole)
        ra_rad  = np.radians(df['ra'])
        dec_rad = np.radians(df['dec'])
        d = df['distance_pc']

        df['x_pc'] = d * np.cos(dec_rad) * np.cos(ra_rad)
        df['y_pc'] = d * np.cos(dec_rad) * np.sin(ra_rad)
        df['z_pc'] = d * np.sin(dec_rad)

        # Also in AU for direct comparison with solar system data
        df['x_au'] = df['x_pc'] * PC_TO_AU
        df['y_au'] = df['y_pc'] * PC_TO_AU
        df['z_au'] = df['z_pc'] * PC_TO_AU

        # Color index (BP - RP): lower = bluer/hotter, higher = redder/cooler
        df['bp_rp'] = df['phot_bp_mean_mag'] - df['phot_rp_mean_mag']

        print("\n" + "="*70)
        print("STELLAR 3D DATA SUMMARY (Heliocentric ICRS)")
        print("="*70)
        print(f"\nTotal stars retrieved: {len(df)}")

        print(f"\n--- BRIGHTNESS (G-band magnitude, lower = brighter) ---")
        print(f"Brightest: {df['phot_g_mean_mag'].min():.3f}")
        print(f"Faintest:  {df['phot_g_mean_mag'].max():.3f}")
        print(f"Mean:      {df['phot_g_mean_mag'].mean():.3f}")

        print(f"\n--- DISTANCE ---")
        print(f"Closest:  {df['distance_pc'].min():.3f} pc  ({df['distance_ly'].min():.3f} ly)")
        print(f"Farthest: {df['distance_pc'].max():.3f} pc  ({df['distance_ly'].max():.3f} ly)")
        print(f"Mean:     {df['distance_pc'].mean():.3f} pc  ({df['distance_ly'].mean():.3f} ly)")

        print(f"\n--- POSITION (Heliocentric Cartesian in Parsecs) ---")
        print(f"X range: {df['x_pc'].min():.3f} to {df['x_pc'].max():.3f} pc")
        print(f"Y range: {df['y_pc'].min():.3f} to {df['y_pc'].max():.3f} pc")
        print(f"Z range: {df['z_pc'].min():.3f} to {df['z_pc'].max():.3f} pc")

        print(f"\n--- POSITION (in AU for solar system comparison) ---")
        print(f"X range: {df['x_au'].min():.0f} to {df['x_au'].max():.0f} AU")
        print(f"Y range: {df['y_au'].min():.0f} to {df['y_au'].max():.0f} AU")
        print(f"Z range: {df['z_au'].min():.0f} to {df['z_au'].max():.0f} AU")
        print(f"(Solar system objects are typically < 100 AU from the Sun)")

        print(f"\n--- PROPER MOTION (mas/yr) ---")
        print(f"RA  (pmra):  {df['pmra'].min():.4f} to {df['pmra'].max():.4f}")
        print(f"Dec (pmdec): {df['pmdec'].min():.4f} to {df['pmdec'].max():.4f}")

        rv_count = df['radial_velocity'].notna().sum()
        print(f"\n--- RADIAL VELOCITY ---")
        print(f"Stars with radial velocity: {rv_count} / {len(df)}")
        if rv_count > 0:
            rv = df['radial_velocity'].dropna()
            print(f"Range: {rv.min():.3f} to {rv.max():.3f} km/s")

        valid_color = df['bp_rp'].dropna()
        if len(valid_color) > 0:
            print(f"\n--- COLOR (BP-RP, higher = redder/cooler) ---")
            print(f"Bluest:  {valid_color.min():.3f}")
            print(f"Reddest: {valid_color.max():.3f}")
            print(f"Mean:    {valid_color.mean():.3f}")

        print(f"\n--- SAMPLE STARS (brightest first) ---")
        sample_cols = ['source_id', 'ra', 'dec', 'phot_g_mean_mag', 'distance_pc', 'x_pc', 'y_pc', 'z_pc']
        print(df[sample_cols].head(10).to_string(index=False))

        df.to_csv(output_file, index=False)
        print(f"\n{'='*70}")
        print(f"Data exported to: {output_file}")
        print(f"{'='*70}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def query_specific_star(source_id, output_file=None):
    """Look up a specific star by its Gaia source_id."""
    print(f"Searching for source_id={source_id} in Gaia DR3...")

    query = f"""
    SELECT
        source_id,
        ra,
        dec,
        parallax,
        parallax_error,
        parallax_over_error,
        pmra,
        pmdec,
        phot_g_mean_mag,
        phot_bp_mean_mag,
        phot_rp_mean_mag,
        radial_velocity,
        radial_velocity_error,
        l,
        b
    FROM gaiadr3.gaia_source
    WHERE source_id = {source_id}
    """

    try:
        job = Gaia.launch_job_async(query)
        results = job.get_results()
        df = results.to_pandas()

        if len(df) == 0:
            print(f"No star found with source_id={source_id}")
            return None

        row = df.iloc[0]

        distance_pc = 1000.0 / row['parallax']
        distance_ly = distance_pc * PC_TO_LY
        ra_rad  = np.radians(row['ra'])
        dec_rad = np.radians(row['dec'])

        x_pc = distance_pc * np.cos(dec_rad) * np.cos(ra_rad)
        y_pc = distance_pc * np.cos(dec_rad) * np.sin(ra_rad)
        z_pc = distance_pc * np.sin(dec_rad)

        print(f"\nFound star: source_id={int(row['source_id'])}")

        print(f"\n--- SKY POSITION ---")
        print(f"RA:  {row['ra']:.6f} deg")
        print(f"Dec: {row['dec']:.6f} deg")
        print(f"Galactic l: {row['l']:.4f}  b: {row['b']:.4f}")

        print(f"\n--- DISTANCE ---")
        print(f"Parallax: {row['parallax']:.4f} +/- {row['parallax_error']:.4f} mas")
        print(f"Distance: {distance_pc:.4f} pc  ({distance_ly:.4f} ly)")

        print(f"\n--- HELIOCENTRIC XYZ POSITION (pc) ---")
        print(f"X: {x_pc:.6f} pc")
        print(f"Y: {y_pc:.6f} pc")
        print(f"Z: {z_pc:.6f} pc")

        print(f"\n--- BRIGHTNESS ---")
        print(f"G magnitude:  {row['phot_g_mean_mag']:.4f}")
        print(f"BP magnitude: {row['phot_bp_mean_mag']:.4f}")
        print(f"RP magnitude: {row['phot_rp_mean_mag']:.4f}")
        print(f"BP-RP color:  {row['phot_bp_mean_mag'] - row['phot_rp_mean_mag']:.4f}")

        print(f"\n--- PROPER MOTION ---")
        print(f"pmra:  {row['pmra']:.4f} mas/yr")
        print(f"pmdec: {row['pmdec']:.4f} mas/yr")

        if pd.notna(row['radial_velocity']):
            print(f"\n--- RADIAL VELOCITY ---")
            print(f"{row['radial_velocity']:.4f} +/- {row['radial_velocity_error']:.4f} km/s")

        if output_file:
            df['distance_pc'] = distance_pc
            df['distance_ly'] = distance_ly
            df['x_pc'] = x_pc
            df['y_pc'] = y_pc
            df['z_pc'] = z_pc
            df['x_au'] = x_pc * PC_TO_AU
            df['y_au'] = y_pc * PC_TO_AU
            df['z_au'] = z_pc * PC_TO_AU
            df.to_csv(output_file, index=False)
            print(f"\nData exported to: {output_file}\n")

        return df

    except Exception as e:
        print(f"Error querying Gaia database: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Query stellar data from Gaia DR3 with 3D heliocentric XYZ coordinates'
    )
    parser.add_argument('-n', '--max-results', type=int, default=100,
                        help='Maximum number of stars to retrieve (default: 100)')
    parser.add_argument('-p', '--min-parallax', type=float, default=1.0,
                        help='Minimum parallax in mas (default: 1.0, ~1000 pc limit)')
    parser.add_argument('-m', '--max-mag', type=float, default=12.0,
                        help='Maximum G-band magnitude (default: 12.0)')
    parser.add_argument('--ra', type=float, default=DEFAULT_RA,
                        help=f'RA of search cone center in degrees (default: {DEFAULT_RA})')
    parser.add_argument('--dec', type=float, default=DEFAULT_DEC,
                        help=f'Dec of search cone center in degrees (default: {DEFAULT_DEC})')
    parser.add_argument('--radius', type=float, default=DEFAULT_RADIUS,
                        help=f'Search cone radius in degrees (default: {DEFAULT_RADIUS})')
    parser.add_argument('-o', '--output', type=str, default='gaia_stars_xyz.csv',
                        help='Output CSV filename (default: gaia_stars_xyz.csv)')
    parser.add_argument('-s', '--source-id', type=int,
                        help='Look up a specific star by Gaia source_id')
    args = parser.parse_args()

    print("\n" + "="*70)
    print("GAIA STELLAR XYZ DATA IMPORTER")
    print("="*70 + "\n")

    if args.source_id:
        query_specific_star(args.source_id, args.output)
    else:
        query_stars_xyz(
            args.max_results, args.min_parallax, args.max_mag,
            args.ra, args.dec, args.radius, args.output
        )


if __name__ == '__main__':
    main()