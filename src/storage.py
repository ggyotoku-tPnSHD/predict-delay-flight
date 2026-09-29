import logging
import os
from pathlib import Path

import boto3

log = logging.getLogger(__name__)

BUCKET = os.environ.get("PIPELINE_BUCKET", "predict-data-bucket-v1")
REGION = os.environ.get("PIPELINE_REGION", "us-east-1")

s3 = boto3.client("s3", region_name=REGION)


def prefix_exists(prefix: str) -> bool:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix, MaxKeys=1)
    return resp.get("KeyCount", 0) > 0


def upload_dir(local_dir: Path, prefix: str, overwrite: bool = False) -> int:
    """Upload every file under local_dir to s3://BUCKET/prefix/. Skips if the prefix already exists."""
    prefix = prefix.rstrip("/") + "/"
    if not overwrite and prefix_exists(prefix):
        log.info("skip s3://%s/%s (exists)", BUCKET, prefix)
        return 0
    if overwrite:
        # Clear the old files first so a rewritten partition doesn't leave stale files behind.
        for obj in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", []):
            s3.delete_object(Bucket=BUCKET, Key=obj["Key"])
    files = [p for p in local_dir.rglob("*") if p.is_file()]
    for path in files:
        key = prefix + path.relative_to(local_dir).as_posix()
        s3.upload_file(str(path), BUCKET, key)
    log.info("uploaded %d files to s3://%s/%s", len(files), BUCKET, prefix)
    return len(files)


def download_dir(prefix: str, local_dir: Path) -> int:
    prefix = prefix.rstrip("/") + "/"
    objs = s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])
    for obj in objs:
        dest = local_dir / obj["Key"][len(prefix):]
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(BUCKET, obj["Key"], str(dest))
    log.info("downloaded %d files from s3://%s/%s", len(objs), BUCKET, prefix)
    return len(objs)
