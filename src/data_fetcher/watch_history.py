import polars as pl

from config import VIDEO_IDS_PATH
from logger import setup_logger
from models import Video

logger = setup_logger("Database")

def get_participant_vids(p_id : str, n = 500, random:bool=False):
    logger.info(f"Fetching {n} videos for participant {p_id}")
    query = (
        pl.scan_parquet(VIDEO_IDS_PATH)
        .filter(pl.col("ideology") == p_id)
    )
    if random:
        df = query.collect()
        df = df.sample(n=min(n, len(df)))
    else:
        df = query.sort("time", descending=True).head(n).collect()
        
    ids = df["video_id"].to_list()
    return [Video(id=_id) for _id in ids]