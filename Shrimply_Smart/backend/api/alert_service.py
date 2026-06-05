"""
Alert Service for Water Quality Monitoring
Checks sensor readings against thresholds and generates alerts
"""

from django.utils import timezone
from django.db.models import Q
from .models import Alert, Threshold, SensorReading
from datetime import timedelta
import logging
import time

# Create a dedicated logger for alert service
logger = logging.getLogger('alert_service')
logger.setLevel(logging.DEBUG)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class AlertService:
    """Service for generating and managing water quality alerts"""
    
    # Alert thresholds (beyond min/max, trigger alerts)
    CRITICAL_THRESHOLD_PERCENT = 0.15  # 15% beyond threshold triggers critical alert
    WARNING_THRESHOLD_PERCENT = 0.10   # 10% beyond threshold triggers warning
    
    # Parameters that decrease when they drop (oxygen, pH)
    DECREASING_PARAMS = ['oxygen', 'ph']
    # Parameters that increase when they spike (temperature, tds, ec)
    INCREASING_PARAMS = ['temperature', 'tds', 'ec']
    
    @staticmethod
    def check_reading_and_create_alerts(sensor_reading):
        """Check a single sensor reading against thresholds and create alerts if needed"""
        start_time = time.time()
        logger.info(f'═══════════════════════════════════════════════════════════')
        logger.info(f'[ALERT_CHECK] Starting alert check for reading #{sensor_reading.id}')
        logger.info(f'[READING_TIME] {sensor_reading.timestamp.isoformat()}')
        logger.debug(f'  ├─ Temperature: {sensor_reading.temperature}°C')
        logger.debug(f'  ├─ pH: {sensor_reading.ph}')
        logger.debug(f'  ├─ Turbidity: {sensor_reading.turbidity} NTU')
        logger.debug(f'  └─ TDS: {sensor_reading.tds} ppm')
        
        created_alerts = []
        thresholds = Threshold.objects.all()
        
        if not thresholds.exists():
            logger.warning('[ALERT_CHECK] ⚠️  NO THRESHOLDS SET UP - Skipping alert check')
            return created_alerts
        
        logger.debug(f'[THRESHOLDS] Found {thresholds.count()} configured thresholds')
        
        for idx, threshold in enumerate(thresholds, 1):
            param = threshold.parameter
            value = getattr(sensor_reading, param, None)
            
            logger.debug(f'  [{idx}/{thresholds.count()}] Checking {param}:')
            logger.debug(f'      Value: {value} | Range: {threshold.min_value}-{threshold.max_value} {threshold.unit}')
            
            if value is None or value <= 0:
                logger.debug(f'      ⊘ Skipped: Invalid value (None or ≤0)')
                continue
            
            # Check if reading is outside acceptable range
            alert = AlertService.evaluate_parameter(
                param=param,
                value=value,
                threshold=threshold,
                sensor_reading=sensor_reading
            )
            
            if alert:
                created_alerts.append(alert)
                logger.warning(f'      ✅ ALERT CREATED: {alert.severity.upper()} - {alert.parameter.upper()} = {alert.value}')
            else:
                logger.debug(f'      ▪ OK: Within acceptable range')
        
        elapsed_time = time.time() - start_time
        logger.info(f'[ALERT_CHECK] ✓ Completed: {len(created_alerts)} alerts created in {elapsed_time:.3f}s')
        logger.info(f'═══════════════════════════════════════════════════════════')
        return created_alerts
    
    @staticmethod
    def evaluate_parameter(param, value, threshold, sensor_reading):
        """Evaluate a single parameter against its threshold"""
        min_val = threshold.min_value
        max_val = threshold.max_value
        unit = threshold.unit or ''
        
        # Calculate critical and warning boundaries
        param_range = max_val - min_val
        critical_margin = param_range * AlertService.CRITICAL_THRESHOLD_PERCENT
        warning_margin = param_range * AlertService.WARNING_THRESHOLD_PERCENT
        
        critical_min = min_val - critical_margin
        critical_max = max_val + critical_margin
        warning_min = min_val - warning_margin
        warning_max = max_val + warning_margin
        
        logger.debug(f'        Range: {min_val}-{max_val} {unit}')
        logger.debug(f'        Warning Zone: {warning_min:.2f}-{warning_max:.2f} {unit}')
        logger.debug(f'        Critical Zone: {critical_min:.2f}-{critical_max:.2f} {unit}')
        
        # Determine severity
        severity = None
        message = None
        
        if value < critical_min or value > critical_max:
            severity = 'critical'
            logger.debug(f'        Status: 🔴 CRITICAL (outside {critical_min:.2f}-{critical_max:.2f})')
        elif value < warning_min or value > warning_max:
            severity = 'warning'
            logger.debug(f'        Status: 🟡 WARNING (outside {warning_min:.2f}-{warning_max:.2f})')
        elif value < min_val or value > max_val:
            severity = 'warning'
            logger.debug(f'        Status: 🟡 WARNING (outside optimal {min_val}-{max_val})')
        
        if severity is None:
            logger.debug(f'        Status: 🟢 OK (within range)')
            return None  # No alert needed
        
        # Generate message
        if param in AlertService.DECREASING_PARAMS:
            if value < min_val:
                message = f"{param.upper()} CRITICAL LOW: {value:.2f}{unit} (minimum: {min_val}{unit})"
        else:  # INCREASING_PARAMS
            if value > max_val:
                message = f"{param.upper()} CRITICAL HIGH: {value:.2f}{unit} (maximum: {max_val}{unit})"
        
        if not message:
            if value < min_val:
                message = f"{param.upper()} below threshold: {value:.2f}{unit} < {min_val}{unit}"
            else:
                message = f"{param.upper()} above threshold: {value:.2f}{unit} > {max_val}{unit}"
        
        logger.debug(f'        Message: {message}')
        
        # Check if similar alert already exists (avoid duplicates)
        one_hour_ago = timezone.now() - timedelta(hours=1)
        existing_alert = Alert.objects.filter(
            parameter=param,
            severity=severity,
            resolved=False,
            timestamp__gte=one_hour_ago
        ).first()
        
        if existing_alert:
            logger.debug(f'        ⊘ Duplicate prevented: Recent {severity} alert exists from {existing_alert.timestamp.isoformat()}')
            return None  # Alert already exists recently
        
        # Create new alert (safe: no multi-row lookup)
        try:
            alert = Alert.objects.create(
                parameter=param,
                severity=severity,
                value=value,
                threshold_min=threshold.min_value,
                threshold_max=threshold.max_value,
                message=message,
                timestamp=timezone.now(),
            )
            logger.info(f'        ✅ Created {severity.upper()} alert (ID: {alert.id})')
            return alert
        except Exception as e:
            logger.error(f'        ❌ Failed to create alert: {str(e)}', exc_info=True)
            return None
    
    @staticmethod
    def get_active_alerts(limit=10):
        """Get currently active (unresolved) alerts"""
        logger.debug(f'[FETCH_ACTIVE] Retrieving up to {limit} active alerts...')
        alerts = Alert.objects.filter(
            resolved=False,
            timestamp__gte=timezone.now() - timedelta(days=1)
        ).order_by('-timestamp')[:limit]
        logger.debug(f'[FETCH_ACTIVE] Found {alerts.count()} active alerts')
        return alerts
    
    @staticmethod
    def get_alerts_for_parameter(parameter, days=7):
        """Get alerts for a specific parameter in the last N days"""
        logger.debug(f'[FETCH_PARAM_ALERTS] Getting {parameter} alerts from last {days} days...')
        alerts = Alert.objects.filter(
            parameter=parameter,
            timestamp__gte=timezone.now() - timedelta(days=days)
        ).order_by('-timestamp')
        logger.debug(f'[FETCH_PARAM_ALERTS] Found {alerts.count()} {parameter} alerts')
        return alerts
    
    @staticmethod
    def resolve_alert(alert_id):
        """Mark an alert as resolved"""
        logger.debug(f'[RESOLVE_ALERT] Resolving alert ID: {alert_id}')
        try:
            alert = Alert.objects.get(id=alert_id)
            alert.resolved = True
            alert.save()
            logger.info(f'[RESOLVE_ALERT] ✅ Alert {alert_id} marked as resolved')
            return alert
        except Alert.DoesNotExist:
            logger.warning(f'[RESOLVE_ALERT] ⚠️  Alert {alert_id} not found')
            return None
    
    @staticmethod
    def get_alert_summary():
        """Get summary of active alerts by severity"""
        logger.debug(f'[ALERT_SUMMARY] Generating alert summary...')
        active_alerts = Alert.objects.filter(
            resolved=False,
            timestamp__gte=timezone.now() - timedelta(days=1)
        )
        
        critical = active_alerts.filter(severity='critical').count()
        warning = active_alerts.filter(severity='warning').count()
        low = active_alerts.filter(severity='low').count()
        
        summary = {
            'total': active_alerts.count(),
            'critical': critical,
            'warning': warning,
            'low': low,
            'alerts': list(active_alerts.values('id', 'parameter', 'severity', 'value', 'message', 'timestamp'))
        }
        
        logger.info(f'[ALERT_SUMMARY] Total: {summary["total"]} | 🔴 Critical: {critical} | 🟡 Warning: {warning} | 🔵 Low: {low}')
        return summary
    
    @staticmethod
    def cleanup_old_alerts(days=30):
        """Delete alerts older than N days"""
        logger.debug(f'[CLEANUP] Starting cleanup of alerts older than {days} days...')
        cutoff_date = timezone.now() - timedelta(days=days)
        deleted_count, _ = Alert.objects.filter(
            timestamp__lt=cutoff_date,
            resolved=True
        ).delete()
        logger.info(f'[CLEANUP] ✓ Deleted {deleted_count} old alerts from before {cutoff_date.isoformat()}')
        return deleted_count
