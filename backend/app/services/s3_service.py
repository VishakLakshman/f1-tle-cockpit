"""
Runtime S3 service — Lambda just fetches pre-processed JSON from S3.
No FastF1, no Pandas, no heavy dependencies at runtime.

S3 key structure (written by pipeline/process_season.py):
  processed/{year}/{gp}/{session}/session_info.json
  processed/{year}/{gp}/{session}/{driver1}_{driver2}.json
  (driver codes are always stored sorted alphabetically)
"""

import os
import json
import boto3
from botocore.exceptions import ClientError

S3_BUCKET = os.getenv("FF1_S3_BUCKET", "")
_s3 = boto3.client("s3")


def _get(key: str) -> dict:
    try:
        resp = _s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(resp["Body"].read())
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("NoSuchKey", "404"):
            raise FileNotFoundError(f"No pre-processed data at s3://{S3_BUCKET}/{key}")
        raise


def _gp_slug(gp: str) -> str:
    """Convert GP name to S3 slug matching pipeline output.
    e.g. 'Monaco Grand Prix' → 'Monaco'
         'Monaco'            → 'Monaco'
         'Saudi Arabia'      → 'Saudi_Arabia'
    """
    return gp.replace(" Grand Prix", "").replace(" ", "_")


def get_session_info(year: int, gp: str, session: str) -> dict:
    key = f"processed/{year}/{_gp_slug(gp)}/{session}/session_info.json"
    return _get(key)


def get_ghost_lap_data(year: int, gp: str, session: str,
                       driver1: str, driver2: str) -> dict:
    pair = "_".join(sorted([driver1.upper(), driver2.upper()]))
    key = f"processed/{year}/{_gp_slug(gp)}/{session}/{pair}.json"
    data = _get(key)
    data["cached"] = False
    return data