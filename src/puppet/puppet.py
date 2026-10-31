import logging
from typing import Literal
import pandas as pd
import random
from tenacity import retry, stop_after_attempt, wait_exponential
from lingua import Language, LanguageDetectorBuilder

from data_fetcher import get_videos_metadata
from .youtube_driver import YouTubeDriver, VideoUnavailableException, PlaybackException
import config
from logger import setup_logger

from data_fetcher import get_participant_vids
from models import Watch, Video

PuppetState = Literal["init", "training", "drifting", "closed"]

class YTPuppet():
    def __init__(self, id : str, cond : Literal["left", "center", "right", "anti-system"], headless : bool = True, train_depth = 100, drift_depth = 200, wt = 30, logger_level=logging.DEBUG, languageTargets : list[Language] = [Language.DANISH]):
        self.ID = id
        self.cond = cond

        self.train_depth = train_depth
        self.drift_depth = drift_depth
        self.wt = wt

        self.cur_state : PuppetState = "init"
        self.history : list[Watch] = []

        self.detector = LanguageDetectorBuilder.from_languages(*languageTargets).build()

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

    async def _populate_metadata(self, recs):
        return await get_videos_metadata(recs)

    async def _filter_language(self, recs : list[Video]):
        recs = await self._populate_metadata(recs)
        return [vid for vid in recs if self.detector.detect_language_of(vid.title) != None]

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _get_homepage_recs(self, driver : YouTubeDriver, depth):
        recs, topics = await driver.get_homepage_recs()
        recs = await self._filter_language(recs)

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


    async def _watch(self, driver : YouTubeDriver, vid : Video, depth) -> Watch:
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
            await self._watch(driver, vid, i + 1)
            if i % homepage_freq == 0:
                await self._get_homepage_recs(driver, i + 1)


    async def drift(self, driver : YouTubeDriver, retries_init = 10, retries_vid = 3):
        self.cur_state = "drifting"
        recs = await self._get_homepage_recs(driver, 0)
        
        for i in range(retries_init):
            try:
                next_vid = random.choice(self._filter_language(recs))
                break
            except:
                recs = await self._get_homepage_recs(driver, 0)
            if i == retries_init - 1:
                raise Exception("Could not load homepage.")
            
        for i in range(1, self.drift_depth + 1):
            try:
                watch = await self._watch(driver, next_vid, i)
                recs = watch.recs
            except: 
                recs = await self._get_homepage_recs(driver, 0)

            for i in range(retries_vid):
                try:
                    next_vid = random.choice(self._filter_language(recs))
                    break
                except:
                    recs = await self._get_homepage_recs(driver, 0)
                if i == retries_vid - 1:
                    next_vid = get_participant_vids(self.cond, 1, random=False)[0]
                    self.logger.warning(f"Failed to load recommendations {retries_vid} times. Fetching seed video instead: {next_vid.id}")

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
