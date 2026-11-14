"""
Command-Line Interface for the Planetary Analog Similarity Model
Run with arguments or interactively.
"""

import argparse
import sys
from planetary_analog_model import PlanetaryAnalogModel, FAMOUS_SITES

def print_results(res):
    body = res['body']
    target_in = res['target_input']
    target_pt = res['target_matched_point']
    analogs = res['analogs']
    site_name = res.get('site_name')
    
    print("\n" + "=" * 80)
    title = f"PLANETARY ANALOG SEARCH RESULTS: {body.upper()}"
    if site_name:
        title += f" ({site_name})"
    print(f" {title.center(78)} ")
    print("=" * 80)
    
    print(f"\n[TARGET LOCATION ON {body.upper()}]:")
    print(f"  Input Coordinates   : Lat {target_in['lat']}°, Lon {target_in['lon']}°")
    print(f"  Nearest Grid Point  : Lat {target_pt['lat']}°, Lon {target_pt['lon']}°")
    print("\n  Target Environmental & Physical Features:")
    for feat, info in res['features_used'].items():
        val = info['raw_value']
        used = info['used_value']
        unit = "m" if "elev" in feat or "rough" in feat else "deg" if "slope" in feat else "K" if "temp" in feat else ""
        if feat == 'elevation_m' and val != used:
            print(f"    - {feat:20s}: {val:10.2f} {unit} (scaled to Earth land bounds: {used:.2f} {unit})")
        else:
            print(f"    - {feat:20s}: {val:10.4f} {unit}")
            
    print("\n" + "-" * 80)
    print(f"TOP {len(analogs)} MOST SIMILAR EARTH ANALOG SITES:")
    print("-" * 80)
    
    for rank, (_, row) in enumerate(analogs.iterrows(), 1):
        gmaps_url = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
        t_day_c = row['temperature_day_K'] - 273.15
        t_night_c = row['temperature_night_K'] - 273.15
        
        print(f"\n#{rank} [Similarity: {row['similarity_score']:.1f}% | Distance Metric: {row['distance']:.3f}]")
        print(f"   Region / Country : {row['region']}")
        print(f"   Coordinates      : Lat {row['lat']:.3f}°, Lon {row['lon']:.3f}°")
        print(f"   Google Maps Link : {gmaps_url}")
        print(f"   Elevation        : {row['elevation_m']:.1f} m")
        print(f"   Slope & Roughness: {row['slope_deg']:.2f}°, {row['roughness_m']:.2f} m")
        print(f"   Broadband Albedo : {row['albedo']:.3f}")
        print(f"   Surface Temps    : Day: {row['temperature_day_K']:.1f} K ({t_day_c:.1f}°C) | Night: {row['temperature_night_K']:.1f} K ({t_night_c:.1f}°C)")
        if 'atm_dust_opacity' in row and not pd.isna(row['atm_dust_opacity']):
            print(f"   Dust Opacity     : {row['atm_dust_opacity']:.4f}")
            
    print("\n" + "=" * 80 + "\n")

def interactive_mode(model):
    print("\n" + "=" * 60)
    print("   WELCOME TO THE PLANETARY ANALOG SIMILARITY MODEL")
    print("=" * 60)
    print("Find the closest Earth environmental analogs for any place on Mars or the Moon.")
    
    while True:
        print("\nSelect Celestial Body:")
        print("  [1] Mars")
        print("  [2] Moon")
        print("  [Q] Quit")
        choice = input("Enter choice (1, 2, or Q): ").strip()
        if choice.lower() in ('q', 'quit', 'exit'):
            print("Exiting.")
            sys.exit(0)
            
        body = 'mars' if choice == '1' else 'moon' if choice == '2' else None
        if not body:
            print("Invalid choice, please enter 1 or 2.")
            continue
            
        print(f"\nSelect input method for {body.upper()}:")
        print("  [1] Choose a famous landmark / crater")
        print("  [2] Enter custom Latitude and Longitude coordinates")
        subchoice = input("Enter choice (1 or 2): ").strip()
        
        if subchoice == '1':
            sites = list(FAMOUS_SITES[body].items())
            print(f"\nPredefined {body.upper()} sites:")
            for i, (name, coords) in enumerate(sites, 1):
                print(f"  [{i}] {name} (Lat: {coords[0]}°, Lon: {coords[1]}°)")
            try:
                site_idx = int(input(f"Select site (1-{len(sites)}): ").strip()) - 1
                site_name, coords = sites[site_idx]
                lat, lon = coords
            except (ValueError, IndexError):
                print("Invalid selection. Retrying.")
                continue
        elif subchoice == '2':
            try:
                lat = float(input(f"Enter {body.upper()} Latitude (-90 to 90): ").strip())
                lon = float(input(f"Enter {body.upper()} Longitude (-180 to 180): ").strip())
                site_name = None
            except ValueError:
                print("Invalid number entered. Retrying.")
                continue
        else:
            print("Invalid option.")
            continue
            
        print(f"\nSearching 6.38M Earth observation locations for {body.upper()} (Lat: {lat}, Lon: {lon})...")
        res = model.find_analogs(body, lat, lon, top_k=5)
        if site_name:
            res['site_name'] = site_name
        print_results(res)
        
        again = input("Search another location? (y/n): ").strip().lower()
        if again not in ('y', 'yes'):
            print("Thank you for using the Planetary Analog Model!")
            break

def main():
    parser = argparse.ArgumentParser(description="Find the top Earth analog sites for any Mars or Moon location.")
    parser.add_argument("--body", choices=['mars', 'moon'], help="Target celestial body ('mars' or 'moon')")
    parser.add_argument("--lat", type=float, help="Latitude on target body (-90 to 90)")
    parser.add_argument("--lon", type=float, help="Longitude on target body (-180 to 180)")
    parser.add_argument("--site", type=str, help="Name of famous landmark (e.g. 'Jezero', 'Gale', 'Apollo 11', 'Olympus Mons')")
    parser.add_argument("--top_k", type=int, default=5, help="Number of top Earth analogs to return (default: 5)")
    parser.add_argument("--interactive", action="store_true", help="Launch interactive prompt mode")
    
    args = parser.parse_args()
    
    # Initialize model
    model = PlanetaryAnalogModel()
    
    if args.interactive or (not args.body and not args.site):
        interactive_mode(model)
        return
        
    if args.site:
        body = args.body or ('mars' if any(args.site.lower() in k.lower() for k in FAMOUS_SITES['mars']) else 'moon')
        res = model.find_analogs_by_name(body, args.site, top_k=args.top_k)
        print_results(res)
    elif args.body and args.lat is not None and args.lon is not None:
        res = model.find_analogs(args.body, args.lat, args.lon, top_k=args.top_k)
        print_results(res)
    else:
        parser.print_help()

if __name__ == "__main__":
    import pandas as pd
    main()
