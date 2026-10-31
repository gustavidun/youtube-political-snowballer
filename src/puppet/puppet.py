import logging
from typing import Literal
import pandas as pd
import random
from tenacity import retry, stop_after_attempt, wait_exponential

from .youtube_driver import YouTubeDriver, VideoUnavailableException, PlaybackException
import config
from logger import setup_logger

from data_fetcher import get_participant_vids
from models import Watch, Video

PuppetState = Literal["init", "training", "drifting", "closed"]

class YTPuppet():
    def __init__(self, id : str, cond : Literal["left", "center", "right", "anti-system"], headless : bool = True, train_depth = 100, drift_depth = 200, wt = 30, logger_level=logging.DEBUG):
        self.ID = id
        self.cond = cond

        self.train_depth = train_depth
        self.drift_depth = drift_depth
        self.wt = wt

        self.cur_state : PuppetState = "init"
        self.history : list[Watch] = []

        self.logger = setup_logger(
            self.ID,
            level=logger_level,
            file_out=config.LOG_DIR / self.ID
        )

        self.driver = YouTubeDriver
        self.driver_args = {
            "session_dir": config.SESSION_DIR / id,
            "headless": headless,
            "ublock_path": config.UBLOCK_PATH,
            "logger": self.logger
        }


    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _get_homepage_recs(self, driver : YouTubeDriver, depth):
        recs, topics = await driver.get_homepage_recs()

        self.history.append(
            Watch(
                state=self.cur_state,
                puppet=self,
                puppet_cond=self.cond,
                depth=depth,
                video=None,
                recs=recs,
                errors=[],
                source="homepage",
                watch_time=0,
                topics=topics
            )
        )

        return recs


    async def _watch(self, driver : YouTubeDriver, vid : Video, depth, get_slants : bool) -> Watch:
        error_log = []

        try:
            vid, recs = await driver.play_video(vid)
        except VideoUnavailableException as e:
            error_log.append(e)
            self.logger.info(f"Video {vid.id} unavailable.")
            recs=[]
        except Exception as e:
            error_log.append(e)
            raise

        try:
            if VideoUnavailableException not in error_log: 
                wt = await driver.wait_wt(self.wt)
        except PlaybackException as e:
            error_log.append(e)
            self.logger.info(f"Can't play video {vid.id}.")
            wt = 0
        except Exception as e:
            error_log.append(e)
            raise 

        watch = Watch(
            state=self.cur_state, 
            puppet=self,
            puppet_cond=self.cond,
            depth=depth,
            video=vid,
            recs=recs,
            errors=error_log,
            source="video",
            watch_time=wt
        )

        self.history.append(watch)
        if not error_log: self.logger.info(f"Finished watch without error. {watch}")
        else: self.logger.warning(f"Recorded watch with error. {watch}") 

        return watch


    async def train(self, driver : YouTubeDriver, homepage_freq=10):
        self.cur_state = "training"

        train_vids = get_participant_vids(
            p_id=self.cond,
            n=self.train_depth,
            random=True
        )

        self.logger.debug(f"TRAIN DEPTH: {self.train_depth}")
        self.logger.debug(f"VIDEOS AVAILABLE: {len(train_vids)}")

        for i, vid in enumerate(train_vids):
            await self._watch(driver, vid, i + 1, get_slants=False)
            if i % homepage_freq == 0:
                await self._get_homepage_recs(driver, i + 1)


    async def drift(self, driver : YouTubeDriver):
        self.cur_state = "drifting"
        recs = await self._get_homepage_recs(driver, 0)
        next_vid = random.choice(recs)

        for i in range(1, self.drift_depth + 1):
            try:
                watch = await self._watch(driver, next_vid, i, get_slants=True)
                recs = watch.recs
            except: 
                recs = await self._get_homepage_recs(driver, 0)

            next_vid = random.choice(recs)     


    async def serialize(self):
        rows = [
            {
                "puppet_id": self.ID,
                "puppet_state": w.state,
                "puppet_cond": w.puppet_cond,
                "depth": w.depth,
                "video_id": getattr(w.video, "id", None),
                "video_slant": getattr(w.video, "slant", None),
                "recs_id": [r.id for r in w.recs],
                "errors": w.errors,
                "source": w.source,
                "watch_time": w.watch_time,
                "topics": w.topics,
            }
            for w in self.history
        ]
        return pd.DataFrame.from_records(rows)


    async def run(self):
        async with self.driver(**self.driver_args) as driver:

            self.logger.info("Initialising training...")
            await self.train(driver)

            self.logger.info("Initialising drifting...")
            await self.drift(driver)

            self.logger.info("Finished run. Saving...")
            df = await self.serialize()

            path = config.PUPPETS_DIR / f"{self.ID}.pkl"
            df.to_pickle(path)

            self.logger.info(f"Puppet data saved to {path}. Closing...")
            self.cur_state = "closed"
