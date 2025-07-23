# Automatic Feed Update Scheduler

This document describes the automatic feed update scheduler feature in Dispatch RSS Reader.

## Overview

The scheduler service provides automatic background updates for all RSS feeds every 24 hours. This ensures your feeds stay current without manual intervention while distributing the load throughout the day.

## Features

### Automatic Updates
- **24-Hour Cycle**: All feeds are refreshed automatically every 24 hours
- **Staggered Updates**: Individual feeds are updated at different times throughout the day to avoid overwhelming the system
- **Background Operation**: Runs independently of user interactions and web requests
- **Graceful Handling**: Failed feed updates don't stop other feeds from updating

### Error Handling
- **Retry Logic**: Built-in retry mechanisms for failed requests
- **Logging**: Comprehensive logging of all scheduler activities
- **Graceful Degradation**: Manual refresh remains available if scheduler fails

### Management
- **Status Monitoring**: View scheduler status and scheduled jobs
- **Job Rescheduling**: Ability to reschedule jobs when feeds are added/removed
- **Graceful Shutdown**: Proper cleanup when application stops

## How It Works

### Initialization
1. When the application starts, the scheduler service is automatically initialized
2. Two types of jobs are scheduled:
   - **Main Job**: Updates all feeds every 24 hours
   - **Individual Jobs**: Staggered updates for each feed throughout the day

### Scheduling Logic
- Individual feeds are spaced evenly throughout the 24-hour period
- If you have 24 feeds, each will update 1 hour apart
- If you have 48 feeds, each will update 30 minutes apart
- Minimum interval between feeds is 1 minute

### Update Process
1. The scheduler calls the same feed update functions used by manual refresh
2. Each feed is processed independently
3. Success/failure is logged for monitoring
4. Database is updated with new entries as they're discovered

## API Endpoints

### Get Scheduler Status
```
GET /scheduler/status
```

Returns JSON with scheduler status and information about scheduled jobs:

```json
{
  "status": "running",
  "jobs": [
    {
      "id": "auto_refresh_feeds",
      "name": "Automatic Feed Refresh (24h)",
      "next_run": "2025-07-24T22:54:18.305581+01:00",
      "trigger": "interval[1 day, 0:00:00]"
    },
    {
      "id": "refresh_feed_1",
      "name": "Auto Refresh: Example Feed",
      "next_run": "2025-07-24T01:30:00.000000+01:00",
      "trigger": "interval[1 day, 0:00:00]"
    }
  ],
  "total_jobs": 2
}
```

### Reschedule Jobs
```
POST /scheduler/reschedule
```

Reschedules all feed refresh jobs. Useful when feeds are added or removed:

```json
{
  "message": "Feed refresh jobs rescheduled successfully",
  "status": "success"
}
```

## Settings Page Integration

The scheduler status is integrated into the Settings page with:

- **Status Check Button**: View current scheduler status and scheduled jobs
- **Reschedule Button**: Reschedule all jobs (useful after adding/removing feeds)
- **Real-time Information**: Current status and next update times

## Technical Details

### Dependencies
- **APScheduler 3.10.4**: Core scheduling library
- **ThreadPoolExecutor**: Limited to 3 concurrent threads for SQLite compatibility
- **Memory Job Store**: Jobs are stored in memory (recreated on restart)

### Configuration
- **Coalescing**: Multiple pending instances of the same job are combined into one
- **Max Instances**: Only one instance of each job runs at a time
- **Misfire Grace Time**: 5-minute grace period for missed jobs
- **Timezone**: UTC for consistency

### Database Considerations
- **SQLite Compatibility**: Thread pool limited to prevent SQLite locking issues
- **Session Management**: Each job uses its own database session
- **Atomic Operations**: Each feed update is independent and atomic

## Logging

The scheduler provides detailed logging at different levels:

- **INFO**: Successful operations, job scheduling, status changes
- **WARNING**: Failed feed updates, missing feeds
- **ERROR**: Critical errors in scheduler operation
- **DEBUG**: Detailed operation information (skipped feeds, etc.)

Example log output:
```
2025-07-23 22:53:08,768 - feed_scheduler - INFO - Feed scheduler started successfully
2025-07-23 22:53:08,781 - feed_scheduler - INFO - Scheduled automatic feed refresh every 24 hours
2025-07-23 22:53:08,807 - feed_scheduler - INFO - Scheduled 31 individual feed refresh jobs
```

## Troubleshooting

### Scheduler Not Starting
- Check that APScheduler is installed: `pip install APScheduler==3.10.4`
- Verify database connectivity
- Check application logs for initialization errors

### Jobs Not Running
- Verify scheduler status via `/scheduler/status` endpoint
- Check if jobs are scheduled with future run times
- Review scheduler logs for error messages

### Performance Issues
- Monitor system resources during update cycles
- Consider reducing concurrent thread count for slower systems
- Check database performance during bulk updates

### Manual Intervention
- Use manual refresh if automatic updates fail
- Reschedule jobs after adding/removing feeds
- Restart application to reset scheduler state if needed

## Migration from Manual Updates

If you were previously relying only on manual feed refreshes:

1. **No Action Required**: The scheduler starts automatically
2. **Existing Workflows**: Manual refresh buttons continue to work
3. **Monitoring**: Use the Settings page to monitor automatic updates
4. **Customization**: Modify `scheduler_service.py` for different update intervals

## Future Enhancements

Potential improvements being considered:

- **Configurable Intervals**: Allow users to set custom update frequencies
- **Feed-Specific Schedules**: Different update intervals for different feeds
- **Smart Scheduling**: Update active feeds more frequently
- **Persistent Job Store**: Maintain schedules across application restarts
- **Health Monitoring**: Automated alerts for scheduler issues