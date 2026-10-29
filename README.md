# Delhi congestion: hourly travel time collection

`main.py` asks the Google Maps Directions API for the travel time in traffic on 24 fixed origin-destination pairs in Delhi and appends the results to `data/raw/YYYY-MM.csv`. A GitHub Actions workflow runs it every hour (on the hour in IST). `analyse.py` turns the collected data into CI, TTI and PTI by route, hour and study period.

The Excel files in the repository root are the earlier collection (Sep 2024 to Apr 2026, one file per run, UTC timestamps, durations as text).

## Data columns

| Column | Meaning |
| :---- | :---- |
| run_ist | Time the run started (IST) |
| slot_ist | IST hour the run belongs to |
| route | Route id (same numbering as the Excel files; Route 13 was a duplicate of 12 and is dropped) |
| status | Google status; only `OK` rows have times |
| distance_m | Length of the path Google chose |
| duration_s | Google's typical time for the path, without live traffic |
| duration_in_traffic_s | Travel time in current traffic |
| speed_kmph | distance / time in traffic |
| via, path_id | Road summary and a short hash of the path, to spot route changes |
| attempts | API calls used for this row (retries included) |

## Cost

Traffic requests are billed as Directions Advanced (a Pro SKU). With a billing account in India, the first 35,000 calls a month are free; hourly runs on 24 routes use about 17,900 a month. The script stops before `MONTHLY_CALL_LIMIT` (default 33,000) calls in a month. Set a daily quota cap in the Cloud Console as well.

## Running locally

```bash
pip install -r requirements.txt
export GOOGLE_API_KEY='your_api_key_here'   # Windows: set GOOGLE_API_KEY=...
python main.py
pip install pandas && python analyse.py
```

In GitHub, the key is the repository secret `GOOGLE_API_KEY`.
