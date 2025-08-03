#!/usr/bin/env python3
"""
Scheduler service for automatic RSS feed refreshing.
Handles periodic background tasks for feed updates.
"""

import logging
from datetime import datetime, timedelta

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from models import RssFeed, Session

from services.entry_service import add_rss_entries_for_feed


class FeedScheduler:
    """Manages automatic RSS feed refreshing using APScheduler."""

    def __init__(self):
        """Initialize the scheduler with appropriate configuration."""
        self.scheduler = None
        self.is_running = False
        self.is_lazy_mode = False
        self.jobs_scheduled = False
        self.logger = self._setup_logging()

        self._configure_scheduler()

    def _setup_logging(self):
        """Set up logging for the scheduler."""
        logger = logging.getLogger("feed_scheduler")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _configure_scheduler(self):
        """Configure the APScheduler with appropriate settings."""
        jobstores = {"default": MemoryJobStore()}

        executors = {"default": ThreadPoolExecutor(max_workers=3)}

        job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

    def start(self, lazy=False):
        """Start the scheduler and set up automatic feed refresh jobs."""
        if self.is_running:
            self.logger.warning("Scheduler is already running")
            return

        try:
            self.scheduler.start()
            self.is_running = True
            self.is_lazy_mode = lazy

            if lazy:
                self.logger.info("Feed scheduler started in lazy mode")
                self._schedule_basic_refresh()
                self.logger.info(
                    "Individual feed jobs will be scheduled on first request"
                )
            else:
                self.logger.info("Feed scheduler started successfully")
                self._schedule_feed_refresh()

        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            raise

    def stop(self):
        """Stop the scheduler gracefully."""
        if not self.is_running:
            self.logger.warning("Scheduler is not running")
            return

        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            self.logger.info("Feed scheduler stopped successfully")

        except Exception as e:
            self.logger.error(f"Error stopping scheduler: {e}")
            raise

    def _schedule_basic_refresh(self):
        """Schedule only the basic automatic refresh job (for lazy mode)."""
        try:
            self.scheduler.remove_job("auto_refresh_feeds")
        except:
            pass

        self.scheduler.add_job(
            func=self._refresh_all_feeds_job,
            trigger=IntervalTrigger(hours=24),
            id="auto_refresh_feeds",
            name="Automatic Feed Refresh (24h)",
            replace_existing=True,
        )

        self.logger.info("Scheduled basic automatic feed refresh every 24 hours")

    def _schedule_feed_refresh(self):
        """Schedule automatic refresh for all feeds every 24 hours."""
        self._schedule_basic_refresh()

        self._schedule_staggered_feed_checks()
        self.jobs_scheduled = True

    def _schedule_staggered_feed_checks(self):
        """Schedule individual feed checks staggered throughout the day."""
        session = Session()
        try:
            feeds = session.query(RssFeed).filter(RssFeed.id != "all").all()

            if not feeds:
                self.logger.info("No feeds found to schedule")
                return

            interval_minutes = max(1, (24 * 60) // len(feeds))

            for i, feed in enumerate(feeds):
                job_id = f"refresh_feed_{feed.id}"
                try:
                    self.scheduler.remove_job(job_id)
                except:
                    pass

                start_time = datetime.now() + timedelta(minutes=i * interval_minutes)

                self.scheduler.add_job(
                    func=self._refresh_single_feed_job,
                    args=[feed.id],
                    trigger=IntervalTrigger(hours=24),
                    id=job_id,
                    name=f"Auto Refresh: {feed.title}",
                    next_run_time=start_time,
                    replace_existing=True,
                )

            self.logger.info(f"Scheduled {len(feeds)} individual feed refresh jobs")

        except Exception as e:
            self.logger.error(f"Error scheduling staggered feed checks: {e}")
        finally:
            session.close()

    def schedule_jobs_on_demand(self):
        """Schedule individual feed jobs on demand (for lazy mode)."""
        if not self.is_running:
            self.logger.warning("Cannot schedule jobs - scheduler not running")
            return False

        if self.jobs_scheduled:
            self.logger.debug("Jobs already scheduled")
            return True

        self.logger.info("Scheduling individual feed jobs on demand...")
        try:
            self._schedule_staggered_feed_checks()
            self.jobs_scheduled = True
            return True
        except Exception as e:
            self.logger.error(f"Error scheduling jobs on demand: {e}")
            return False

    def _refresh_all_feeds_job(self):
        """Background job to refresh all feeds."""
        self.logger.info("Starting automatic refresh of all feeds")

        session = Session()
        try:
            feeds = session.query(RssFeed).filter(RssFeed.id != "all").all()
            success_count = 0
            error_count = 0
            skipped_count = 0

            for feed in feeds:
                try:
                    success, message = add_rss_entries_for_feed(feed.id)

                    if success:
                        if (
                            "not modified" in message.lower()
                            or "unchanged" in message.lower()
                        ):
                            skipped_count += 1
                            self.logger.debug(f"Skipped {feed.title}: {message}")
                        else:
                            success_count += 1
                            self.logger.info(f"Refreshed {feed.title}: {message}")
                    else:
                        error_count += 1
                        self.logger.warning(
                            f"Failed to refresh {feed.title}: {message}"
                        )

                except Exception as e:
                    error_count += 1
                    self.logger.error(f"Error refreshing feed {feed.title}: {e}")

            self.logger.info(
                f"Automatic feed refresh completed: "
                f"{success_count} updated, {skipped_count} skipped, {error_count} errors"
            )

        except Exception as e:
            self.logger.error(f"Error in automatic feed refresh job: {e}")
        finally:
            session.close()

    def _refresh_single_feed_job(self, feed_id):
        """Background job to refresh a single feed."""
        session = Session()
        try:
            feed = session.query(RssFeed).filter_by(id=feed_id).first()
            if not feed:
                self.logger.warning(f"Feed {feed_id} not found for automatic refresh")
                return

            success, message = add_rss_entries_for_feed(feed_id)

            if success:
                if "not modified" in message.lower() or "unchanged" in message.lower():
                    self.logger.debug(f"Auto-refresh skipped {feed.title}: {message}")
                else:
                    self.logger.info(f"Auto-refreshed {feed.title}: {message}")
            else:
                self.logger.warning(f"Auto-refresh failed for {feed.title}: {message}")

        except Exception as e:
            self.logger.error(f"Error in single feed refresh job for {feed_id}: {e}")
        finally:
            session.close()

    def get_job_status(self):
        """Get status of all scheduled jobs."""
        if not self.is_running:
            return {"status": "stopped", "jobs": [], "lazy_mode": self.is_lazy_mode}

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat()
                    if job.next_run_time
                    else None,
                    "trigger": str(job.trigger),
                }
            )

        return {
            "status": "running",
            "jobs": jobs,
            "total_jobs": len(jobs),
            "lazy_mode": self.is_lazy_mode,
            "jobs_scheduled": self.jobs_scheduled,
        }

    def reschedule_feeds(self):
        """Reschedule all feed refresh jobs (useful when feeds are added/removed)."""
        if not self.is_running:
            self.logger.warning("Cannot reschedule jobs - scheduler not running")
            return

        self.logger.info("Rescheduling all feed refresh jobs")
        self._schedule_staggered_feed_checks()


_scheduler_instance = None


def get_scheduler():
    """Get the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = FeedScheduler()
    return _scheduler_instance


def start_scheduler(lazy=False):
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start(lazy=lazy)
    return scheduler


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()


def get_scheduler_status():
    """Get the status of the global scheduler."""
    scheduler = get_scheduler()
    return scheduler.get_job_status()


def reschedule_feeds():
    """Reschedule all feed refresh jobs."""
    scheduler = get_scheduler()
    scheduler.reschedule_feeds()


def schedule_jobs_on_first_request():
    """Schedule individual feed jobs on first request (for lazy mode)."""
    scheduler = get_scheduler()
    return scheduler.schedule_jobs_on_demand()
