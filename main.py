#imports
from datetime import datetime, timedelta, timezone
from pipeline.pull_data import pull_data

#*****USERS INPUT DATA HERE*****

#note that here we accept start and end dates in UTC.
#start date begins at 00:00:00 and end date ends at 23:00:00

API_KEY = "YOUR_KEY_HERE"
START_DATE = "2025-10-28"
END_DATE = "2026-06-23"
print("\n=====Beginning calibration pipeline=====")

#*****ERROR CHECKING*****

start_dt = datetime.strptime(START_DATE, "%Y-%m-%d").date()
end_dt = datetime.strptime(END_DATE, "%Y-%m-%d").date()

current_utc = datetime.now(timezone.utc)
if current_utc.hour >= 23:
    latest_end_dt = current_utc.date()
else:
    latest_end_dt = (current_utc - timedelta(days=1)).date()

if start_dt > latest_end_dt:
    raise ValueError("Start date is in the future. Latest available"
    " calibration date is",str(latest_end_dt))

if end_dt > latest_end_dt:
    end_dt = latest_end_dt
    print("\nNote: End date provided exceeds current data. Rounding down to:"
    ,str(end_dt),"23:00:00")

if end_dt <= start_dt:
    raise ValueError("\nEND_DATE must occur after START_DATE")

earliest_quant_date = datetime(2025, 10, 28).date()
if start_dt < earliest_quant_date:
    raise ValueError("Start date is too early (before all Quants were online)"
                     "\nEarliest allowable date is 2025-10-28"
                     )

hours = ((end_dt - start_dt).days + 1) * 24
MIN_HOURS = 2500
if hours < MIN_HOURS:
    difference = int(MIN_HOURS - hours)
    recommend_end_dt = start_dt + timedelta(hours=MIN_HOURS)
    raise ValueError(
        f"Calibration requires at least "
        f"{MIN_HOURS:,} hours. of data\n\n"
        f"Current range provides "
        f"{int(hours):,} hours of data.\n\n"
        f"You are short by "
        f"{difference:,} hours.\n\n"
        f"Recommended END_DATE: "
        f"{recommend_end_dt.strftime('%Y-%m-%d')}\n\n"
        f"Generally, it is recommended to utilize a full year of calibrations"
        f" that include the time of interest\n"
    )

print("\nCalibration parameters accepted.\n")

#*****DOWNLOADING AND CLEANING DATA*****

print("\n=====DOWNLOADING AND CLEANING DATA=====")
quant_df, beacon_df, download_summary = pull_data(api_key=API_KEY,
                                                  start_date=start_dt,
                                                  end_date=end_dt)
print("\n=====DOWNLOADING AND CLEANING COMPLETE=====")