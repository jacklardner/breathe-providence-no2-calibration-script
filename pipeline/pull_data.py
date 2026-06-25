#imports
from datetime import timedelta, datetime, time
from urllib.parse import quote

import pandas as pd
import requests

#variable for sites and serial codes
QUANTS = {
        "dpw": "MOD-00811",
        "mjf": "MOD-00809",
        "pema": "MOD-00810",
        "pha": "MOD-00812"
    }

SENSORS = {
    "Sensor01": ("Myron J. Francis Elementary", 250),
    "Sensor02": ("Silver Lake Residence", 254),
    "Sensor03": ("Reservoir Ave Elementary", 258),
    "Sensor04": ("Anthony Carnevale Elementary", 261),
    "Sensor05": ("E-Cubed Academy Senior High", 264),
    "Sensor06": ("Rochambeau Library", 267),
    "Sensor07": ("Smith Hill Library", 270),
    "Sensor08": ("Alpert Medical School", 274),
    "Sensor09": ("Department of Public Works", 276),
    "Sensor10": ("Zuccolo Recreation Center", 251),
    "Sensor11": ("West End Community Center", 252),
    "Sensor12": ("United Way", 255),
    "Sensor13": ("Providence Housing Authority", 257),
    "Sensor14": ("CCRI - Liston Campus", 259),
    "Sensor15": ("Main St. Martial Arts", 262),
    "Sensor16": ("South Providence Library", 263),
    "Sensor17": ("Blackstone Residence", 266),
    "Sensor18": ("Brown-Fox Point Early Childhood Learning Center", 269),
    "Sensor19": ("Rock Spot Climbing Gym", 272),
    "Sensor20": ("Rockefeller Library", 253),
    "Sensor21": ("Child & Family Services", 256),
    "Sensor22": ("Mt. Pleasant Hardware", 260),
    "Sensor23": ("Rhode Island College", 265),
    "Sensor24": ("Providence College", 268),
    "Sensor25": ("Providence Emergency Management Agency", 271)
}

VARIABLES = [
    "no2_wrk_aux",
    "o3_wrk_aux",
    "co_wrk_aux",
    "no_wrk_aux",
    "rh",
    "temp"
]

VARIABLE_STRING = ",".join(VARIABLES)
BASE_URL = "http://128.32.208.8/node"

def pull_data(api_key, start_date, end_date):
    quant_df = download_quant_data(api_key, start_date, end_date)
    beacon_data = download_beacon_data(start_date, end_date)
    download_summary = {
        "quant_rows": len(quant_df),
    }

    return quant_df, beacon_data, download_summary

def download_quant_data(api_key, start_date, end_date):

    quant_data = {}

    for site, sn in QUANTS.items():

        print(f"\n===== Downloading {site.upper()} =====")

        all_data = []

        #quantAQ limits downloads to 31 days, so we must download 30 days
        #of resampled data at a time

        #because the quant API is annoying and pulls requests from local time
        #we need to pull data from one day before to ensure we get the times we
        #need
        chunk_start = start_date - timedelta(days=1)
        while chunk_start <= end_date:

            chunk_end = min(chunk_start + timedelta(days=30), end_date)

            print(f"  -> {chunk_start} to {chunk_end}")

            url = "https://api.quant-aq.com/v1/data/resampled/"

            params = {
                "sn": sn,
                "start_date": chunk_start.strftime("%Y-%m-%d"),
                "end_date": chunk_end.strftime("%Y-%m-%d"),
                "period": "1h"
            }

            response = requests.get(url, params=params, auth=(api_key, ""))

            print("STATUS:", response.status_code)

            if response.status_code != 200:
                print(response.text)
                response.raise_for_status()

            payload = response.json()

            all_data.extend(payload["data"])

            chunk_start = chunk_end + timedelta(days=1)

        #construct dataframe

        df = pd.DataFrame(all_data)

        df["datetime_utc"] = pd.to_datetime(
            df["period_end_utc"],
            utc=True
        ).dt.tz_localize(None)

        requested_start = datetime.combine(
            start_date,
            datetime.min.time()
        )

        requested_end = datetime.combine(
            end_date,
            datetime.max.time().replace(
                minute=0,
                second=0,
                microsecond=0
            )
        )

        df = df[
            (df["datetime_utc"] >= requested_start) &
            (df["datetime_utc"] <= requested_end)
        ]

        df = df[["datetime_utc", "no2"]].copy()

        df = df.rename(columns={"no2": site})

        df = df.sort_values("datetime_utc")

        quant_data[site] = df

        print(f"{site.upper()} total rows: {len(df):,}")

    #merge dataframes

    merged = quant_data["dpw"]

    for site in ["mjf", "pema", "pha"]:
        merged = merged.merge(
            quant_data[site],
            on="datetime_utc",
            how="outer"
        )

    merged = merged.dropna()

    print("\nFinal Quant dataset shape:", merged.shape)
    merged.to_csv("data for analysis/cleaned_quant.csv")
    return merged

def download_beacon_data(start_date, end_date):
    print("\n===== DOWNLOADING BEACON DATA =====")

    beacon_dict = {}

    #need to add times to the datetime to then shift
    start_dt = datetime.combine(
        start_date,
        time(0, 0, 0)
    )

    end_dt = datetime.combine(
        end_date,
        time(23, 0, 0)
    )

    #need to adjust these strings here because beacon API accepts PST as input
    start_str = (start_dt - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
    end_str = (end_dt - timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")

    expected_hours = pd.date_range(
        start=start_dt,
        end=end_dt,
        freq="1h"
    )

    output_dir = "data for analysis"

    for sensor_id, (site_name, node_id) in SENSORS.items():

        print(f"\nDownloading {sensor_id} ({site_name})")

        #construct URL
        url = (
            f"{BASE_URL}/{node_id}/measurements_all/csv"
            f"?name={quote(site_name)}"
            f"&interval=60"
            f"&variables={VARIABLE_STRING}"
            f"&start={quote(start_str)}"
            f"&end={quote(end_str)}"
            f"&chart_type=measurement"
        )

        try:
            df = pd.read_csv(url)

            df["datetime_utc"] = pd.to_datetime(df["datetime"])

            #ensure all variables present
            for col in VARIABLES:
                if col not in df.columns:
                    df[col] = pd.NA

            df = df[["datetime_utc"] + VARIABLES]

            #drop missing values
            before_drop = len(df)
            df = df.dropna()
            after_drop = len(df)

            observed_hours = df["datetime_utc"].dt.floor("h").unique()

            coverage = len(observed_hours) / len(expected_hours)

            #warn if lots of data points dropped and print how many points
            #must be dropped
            if coverage < 0.75:
                print(
                    f"WARNING {sensor_id}: low coverage "
                    f"({coverage:.2%})"
                )

            print(
                f"{sensor_id}: {len(df):,} rows "
                f"(dropped {before_drop - after_drop:,} rows) "
                f"| coverage {coverage:.2%}"
            )

            #save file to csv
            df.to_csv(f"{output_dir}/{sensor_id}.csv", index=False)

            beacon_dict[sensor_id] = df

        except Exception as e:
            print(f"{sensor_id}: {e}")
            beacon_dict[sensor_id] = pd.DataFrame(columns=["datetime_utc"] + VARIABLES)

    return beacon_dict