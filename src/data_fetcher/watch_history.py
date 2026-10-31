from nt import pipe

import polars as pl

from config import VIDEO_IDS_PATH
from logger import setup_logger
from models import Video

logger = setup_logger("Database")

def get_participant_vids(p_id : str, n = 500, random:bool=False):
    logger.info(f"Fetching {n} videos for participant {p_id}")
    query = (
        pl.scan_parquet(WATCH_HISTORY_PATH)
        .filter(pl.col("participant_id") == p_id)
    )
    if random:
        query = query.collect().sample(n=n)
    else:
        query = query.sort("time", descending=True).head(n)
        
    ids = pipe.collect()["video_id"].to_list()
    return [Video(id=_id) for _id in ids]