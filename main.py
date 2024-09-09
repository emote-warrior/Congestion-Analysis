import os
import requests
import pandas as pd
from datetime import datetime

# Your Google API key
API_KEY = os.getenv('GOOGLE_API_KEY')

# List of origin and destination pairs
locations = [
    ('28.5759808,77.2186263', '28.5827828,77.256016'),
    ('28.5513964,77.273842', '28.5952797,77.2420698'),
    ('28.5732655,77.179352', '28.5665441,77.2525954'),
    ('28.5653553,77.2470071', '28.5709028,77.1820616'),
    ('28.5714791,77.2092125', '28.5295786,77.1917679'),
    ('28.5433288,77.2098753', '28.5565,77.2685888'),
    ('28.5596205,77.2309816', '28.5460173,77.2500933'),
    ('28.4831199,77.1281886', '28.5104244,77.180204'),
    ('28.5067604,77.1755274', '28.5420982,77.1997711'),
    ('28.4919892,77.0827023', '28.5427483,77.1181807'),
    ('28.5834153,77.1462548', '28.5320683,77.1058261'),
    ('28.6194026,77.2358173', '28.6281678,77.2515234'),
    ('28.6194026,77.2358173', '28.6281678,77.2515234'),
    ('28.6153882,77.2368631', '28.6066081,77.2530604'),
    ('28.6190247,77.2404836', '28.6058065,77.2533136'),
    ('28.6642427,77.2079688', '28.6706521,77.2333587'),
    ('28.6735575,77.2257548', '28.6457822,77.2403703'),
    ('28.6450377,77.2230123', '28.6566159,77.1854754'),
    ('28.6499997,77.2387382', '28.6683998,77.2274198'),
    ('28.6191512,77.2357817', '28.6389426,77.2410317'),
    ('28.6328374,77.0862014', '28.6204838,77.0200444'),
    ('28.6672416,77.1660713', '28.642202,77.1094069'),
    ('28.7449272,77.1308618', '28.7521189,77.0781651'),
    ('28.697844,77.1860764', '28.7453743,77.1517715'),
    ('28.5112722,77.257023', '28.5229734,77.1914886')
]

def fetch_duration_in_traffic(origin, destination):
    """Fetches duration in traffic from Google Maps Directions API."""
    params = {
        'origin': origin,
        'destination': destination,
        'key': API_KEY,
        'departure_time': 'now',
        'traffic_model': 'best_guess'
    }
    response = requests.get('https://maps.googleapis.com/maps/api/directions/json', params=params)
    data = response.json()
    
    # Parsing the duration in traffic
    duration_in_traffic = data['routes'][0]['legs'][0]['duration_in_traffic']['text']
    return duration_in_traffic

def main():
    results = []
    for i, (origin, destination) in enumerate(locations, start=1):
        traffic_info = fetch_duration_in_traffic(origin, destination)
        results.append({
            "Route": f"Route {i}",
            "Origin": origin,
            "Destination": destination,
            "Duration in Traffic": traffic_info
        })
        print(f"Duration from {origin} to {destination} is {traffic_info}")
    
    # Create a DataFrame
    df = pd.DataFrame(results)
    
    # Get current timestamp for the filename
    timestamp = datetime.now().strftime("%d-%m-%Y %H-%M")
    filename = f"traffic_data_{timestamp}.xlsx"
    
    # Save the DataFrame to an Excel file
    df.to_excel(filename, index=False, engine='openpyxl')

if __name__ == "__main__":
    main()