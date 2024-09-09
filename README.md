# Traffic Duration in Google Maps

This script fetches the estimated travel time between multiple origin and destination pairs in real-time traffic using the Google Maps Directions API. The results are saved in an Excel file with the timestamp.

## Features
- Retrieves real-time traffic data for a list of origin-destination pairs.
- Outputs travel duration in traffic.
- Saves the data to an Excel file.

## Prerequisites
Before running the script, ensure you have the following:
- A valid Google Maps API key. You can get one from the [Google Cloud Console](https://console.cloud.google.com/).
- Python 3.x installed on your system.

## Installation

1. Clone the repository or download the `traffic_duration.py` file.
2. Install the required dependencies by running:

    ```bash
    pip install -r requirements.txt
    ```

    If you don’t have a `requirements.txt` file, you can manually install the required packages:

    ```bash
    pip install requests pandas openpyxl
    ```

3. Set up your Google Maps API key as an environment variable:

    **Linux/macOS**:
    ```bash
    export GOOGLE_MAPS_API_KEY='your_api_key_here'
    ```

    **Windows**:
    ```bash
    set GOOGLE_MAPS_API_KEY=your_api_key_here
    ```

## Usage

Run the script using Python:

```bash
python traffic_duration.py
