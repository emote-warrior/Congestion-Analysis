Traffic Duration Fetcher
Overview
This Python script fetches the duration in traffic between pairs of origin and destination locations using the Google Maps Directions API. It saves the results in an Excel file for easy reference and data analysis.

Features
Fetches real-time traffic data between multiple origin-destination pairs.
Uses the Google Maps Directions API to get the best traffic estimate.
Saves the results in an Excel file with timestamped filenames.
Prerequisites
Python 3.x
Google Maps API Key: You must have an active API key from Google Cloud.
Required Python libraries:
requests
pandas
openpyxl
Setup
Clone this repository:

bash
Copy code
git clone https://github.com/your-username/Traffic-Duration-Fetcher.git
Install the required dependencies:

bash
Copy code
pip install -r requirements.txt
Set up your Google Maps API key as an environment variable:

On macOS/Linux:
bash
Copy code
export GOOGLE_MAPS_API_KEY='your-api-key'
On Windows:
bash
Copy code
set GOOGLE_MAPS_API_KEY='your-api-key'
How to Use
Add your origin and destination locations in the locations list in traffic_duration.py.

Run the script:

bash
Copy code
python traffic_duration.py
The script will create an Excel file with the traffic duration data saved as traffic_data_<timestamp>.xlsx.

Example
Example of the output in the console:

vbnet
Copy code
Duration from 28.63615,77.2139416666667 to 28.6333388888889,77.1999305555556 is 12 mins
Duration from 28.6333388888889,77.1999305555556 to 28.6466638888889,77.1952611111111 is 8 mins
...
Contributing
Feel free to submit issues or pull requests. Contributions are welcome to improve this script!

License
This project is licensed under the MIT License - see the LICENSE file for details.
