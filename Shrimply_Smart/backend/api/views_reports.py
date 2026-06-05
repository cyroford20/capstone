from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Avg, Min, Max, Count
from datetime import timedelta
import json, csv, io, logging

from .models import Report, SensorReading, Alert, FeedingLog, HistorySettings
from .serializers import ReportSerializer

logger = logging.getLogger(__name__)


# ── helpers ────────────────────────────────────────────────────────────

def _generate_report(report, user):
    """Compute summary + insights for a Report and save it."""
    start = report.start_date
    end = report.end_date

    # ── sensor data ───────────────────────────────────────────────
    readings = SensorReading.objects.filter(
        timestamp__gte=start, timestamp__lte=end,
    )
    sensor_agg = readings.aggregate(
        avg_temp=Avg('temperature'), min_temp=Min('temperature'), max_temp=Max('temperature'),
        avg_ph=Avg('ph'), min_ph=Min('ph'), max_ph=Max('ph'),
        avg_turb=Avg('turbidity'), min_turb=Min('turbidity'), max_turb=Max('turbidity'),
        avg_tds=Avg('tds'), min_tds=Min('tds'), max_tds=Max('tds'),
        count=Count('id'),
    )
    sensor_data = {}
    mapping = {
        'temperature': ('avg_temp', 'min_temp', 'max_temp'),
        'ph': ('avg_ph', 'min_ph', 'max_ph'),
        'turbidity': ('avg_turb', 'min_turb', 'max_turb'),
        'tds': ('avg_tds', 'min_tds', 'max_tds'),
    }
    for key, (a, mi, ma) in mapping.items():
        sensor_data[key] = {
            'avg': round(sensor_agg[a], 2) if sensor_agg[a] is not None else None,
            'min': round(sensor_agg[mi], 2) if sensor_agg[mi] is not None else None,
            'max': round(sensor_agg[ma], 2) if sensor_agg[ma] is not None else None,
            'count': sensor_agg['count'],
        }

    # ── alerts ────────────────────────────────────────────────────
    alerts_qs = Alert.objects.filter(timestamp__gte=start, timestamp__lte=end)
    by_param = {}
    for p in ['temperature', 'ph', 'turbidity', 'tds']:
        c = alerts_qs.filter(parameter=p).count()
        if c:
            by_param[p] = c
    alert_data = {
        'total': alerts_qs.count(),
        'by_parameter': by_param,
        'unresolved': alerts_qs.filter(resolved=False).count(),
    }

    # ── feeding ───────────────────────────────────────────────────
    feeds_qs = FeedingLog.objects.filter(timestamp__gte=start, timestamp__lte=end)
    by_type = {}
    for ft in ['manual', 'scheduled', 'weather_adjusted', 'smart_adjusted']:
        c = feeds_qs.filter(feed_type=ft).count()
        if c:
            by_type[ft] = c
    total_grams = sum(f.portion_grams for f in feeds_qs)
    feeding_data = {
        'total_events': feeds_qs.count(),
        'by_type': by_type,
        'total_grams': float(total_grams),
    }

    # ── period ────────────────────────────────────────────────────
    period_data = {
        'start': start.strftime('%Y-%m-%d') if hasattr(start, 'strftime') else str(start),
        'end': end.strftime('%Y-%m-%d') if hasattr(end, 'strftime') else str(end),
        'days': (end - start).days,
    }

    report.summary = {
        'sensor_data': sensor_data,
        'alerts': alert_data,
        'feeding': feeding_data,
        'period': period_data,
    }

    # ── insights (rule-based) ─────────────────────────────────────
    insights = []

    # Temperature
    avg_t = sensor_data['temperature']['avg']
    if avg_t is not None:
        if avg_t > 32:
            insights.append({'type': 'critical', 'parameter': 'temperature',
                             'message': f'Average temperature {avg_t}°C exceeded safe limit (>32°C) — increase aeration'})
        elif avg_t < 26:
            insights.append({'type': 'warning', 'parameter': 'temperature',
                             'message': f'Average temperature {avg_t}°C below optimal range (26-32°C)'})
        else:
            insights.append({'type': 'info', 'parameter': 'temperature',
                             'message': f'Temperature averaged {avg_t}°C — within optimal range'})

    # pH
    avg_ph = sensor_data['ph']['avg']
    if avg_ph is not None:
        if avg_ph < 7.5 or avg_ph > 8.5:
            insights.append({'type': 'warning', 'parameter': 'ph',
                             'message': f'pH averaged {avg_ph} — outside optimal 7.5-8.5 range'})
        else:
            insights.append({'type': 'info', 'parameter': 'ph',
                             'message': f'pH remained stable at {avg_ph} within optimal range'})

    # Turbidity
    avg_turb = sensor_data['turbidity']['avg']
    if avg_turb is not None:
        if avg_turb > 3:
            insights.append({'type': 'critical', 'parameter': 'turbidity',
                             'message': f'Turbidity averaged {avg_turb} NTU — above 3 NTU, perform water change or use clarifying agents'})
        else:
            insights.append({'type': 'info', 'parameter': 'turbidity',
                             'message': f'Turbidity averaged {avg_turb} NTU — within optimal range'})

    # Feeding
    if feeding_data['total_events']:
        insights.append({'type': 'info', 'parameter': 'feeding',
                         'message': f"{feeding_data['total_events']} feeding events, {feeding_data['total_grams']:.0f}g total"})

    # Alerts
    if alert_data['total']:
        sev = 'warning' if alert_data['unresolved'] else 'info'
        insights.append({'type': sev, 'parameter': 'alerts',
                         'message': f"{alert_data['total']} alerts generated, {alert_data['unresolved']} unresolved"})

    report.insights = insights
    report.status = 'completed'
    report.generated_at = timezone.now()
    report.save()
    return report


def _email_report(report, email):
    """Send an HTML email with the report and a CSV attachment."""
    from django.core.mail import EmailMessage
    from django.conf import settings as django_settings

    # Validate email address
    if not email or '@' not in email:
        raise ValueError(f'Invalid email address: {email}')

    summary = report.summary if isinstance(report.summary, dict) else json.loads(report.summary or '{}')
    insights = report.insights if isinstance(report.insights, list) else json.loads(report.insights or '[]')
    sd = summary.get('sensor_data', {})
    period = summary.get('period', {})

    # Build HTML body
    rows_html = ''
    for key, label, unit in [
        ('temperature', 'Temperature', '°C'), ('ph', 'pH', ''),
        ('turbidity', 'Turbidity', 'NTU'), ('tds', 'TDS', 'ppm'),
    ]:
        d = sd.get(key, {})
        avg = d.get('avg', '—')
        mn = d.get('min', '—')
        mx = d.get('max', '—')
        rows_html += f'<tr><td style="padding:8px;border:1px solid #e5e7eb">{label}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{avg} {unit}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{mn}</td>'
        rows_html += f'<td style="padding:8px;border:1px solid #e5e7eb">{mx}</td></tr>'

    insights_html = ''
    colors = {'critical': '#fecaca', 'warning': '#fef3c7', 'info': '#dbeafe'}
    for ins in insights:
        bg = colors.get(ins.get('type', 'info'), '#f3f4f6')
        insights_html += (
            f'<div style="background:{bg};padding:10px 14px;border-radius:8px;margin-bottom:6px">'
            f'<strong>{ins.get("parameter","").replace("_"," ").title()}</strong>: {ins.get("message","")}</div>'
        )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:auto">
      <div style="background:linear-gradient(135deg,#0ea5e9,#0284c7);color:#fff;padding:20px 24px;border-radius:12px 12px 0 0">
        <h2 style="margin:0">🦐 {report.title}</h2>
        <p style="margin:4px 0 0;opacity:.85">{period.get('start','')} — {period.get('end','')}</p>
      </div>
      <div style="padding:20px 24px;border:1px solid #e5e7eb;border-top:none">
        <h3>Sensor Summary</h3>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#f0f9ff"><th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Parameter</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Avg</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Min</th>
          <th style="padding:8px;border:1px solid #e5e7eb">Max</th></tr>
          {rows_html}
        </table>
        <h3 style="margin-top:18px">Insights</h3>
        {insights_html}
        <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:24px">
          Generated by ShrimplySmart &copy; {timezone.now().year}
        </p>
      </div>
    </div>
    """

    # Build CSV attachment of raw sensor readings
    start = report.start_date
    end = report.end_date
    readings = SensorReading.objects.filter(timestamp__gte=start, timestamp__lte=end).order_by('timestamp')
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Timestamp', 'Temperature', 'pH', 'Turbidity', 'TDS'])
    for r in readings[:2000]:  # cap at 2000 rows
        writer.writerow([r.timestamp.isoformat(), r.temperature, r.ph, r.turbidity, r.tds])
    csv_bytes = buf.getvalue().encode('utf-8')

    try:
        msg = EmailMessage(
            subject=report.title,
            body=html,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.content_subtype = 'html'
        msg.attach(f'sensor_data_{period.get("start","")}.csv', csv_bytes, 'text/csv')
        result = msg.send(fail_silently=False)
        logger.info(f'Email sent to {email}: {result} message(s) sent')
    except Exception as e:
        logger.error(f'Failed to send email to {email}: {str(e)}')
        raise


# ── ViewSet ────────────────────────────────────────────────────────────

class ReportPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ReportPagination

    def get_queryset(self):
        return Report.objects.all().order_by('-generated_at', '-id')

    # ── generate helpers ──────────────────────────────────────────

    def _create_and_generate(self, title, report_type, start_dt, end_dt, user):
        report = Report.objects.create(
            title=title, report_type=report_type,
            start_date=start_dt, end_date=end_dt, status='generating',
        )
        _generate_report(report, user)
        return Response(ReportSerializer(report).data, status=201)

    @action(detail=False, methods=['post'])
    def generate_daily(self, request):
        date_str = request.data.get('date')
        d = timezone.datetime.fromisoformat(date_str).date() if date_str else timezone.now().date()
        start = timezone.make_aware(timezone.datetime.combine(d, timezone.datetime.min.time()))
        end = timezone.make_aware(timezone.datetime.combine(d, timezone.datetime.max.time()))
        return self._create_and_generate(
            f"Daily Report — {d.strftime('%B %d, %Y')}", 'daily', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_weekly(self, request):
        end = timezone.now()
        start = end - timedelta(days=7)
        if request.data.get('start_date'):
            start = timezone.datetime.fromisoformat(request.data['start_date'])
        if request.data.get('end_date'):
            end = timezone.datetime.fromisoformat(request.data['end_date'])
        return self._create_and_generate(
            f"Weekly Report — {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}",
            'weekly', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_monthly(self, request):
        now = timezone.now()
        year = int(request.data.get('year', now.year))
        month = int(request.data.get('month', now.month))
        start = timezone.make_aware(timezone.datetime(year, month, 1))
        end = (timezone.make_aware(timezone.datetime(year + (1 if month == 12 else 0),
               (month % 12) + 1, 1)) - timedelta(seconds=1))
        return self._create_and_generate(
            f"Monthly Report — {start.strftime('%B %Y')}", 'monthly', start, end, request.user,
        )

    @action(detail=False, methods=['post'])
    def generate_custom(self, request):
        start = timezone.datetime.fromisoformat(request.data['start_date'])
        end = timezone.datetime.fromisoformat(request.data['end_date'])
        title = request.data.get('title',
                    f"Custom Report — {start.strftime('%b %d')} to {end.strftime('%b %d, %Y')}")
        return self._create_and_generate(title, 'custom', start, end, request.user)

    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        report = self.get_object()
        report.status = 'generating'
        report.save()
        _generate_report(report, request.user)
        return Response(ReportSerializer(report).data)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        limit = int(request.query_params.get('limit', 10))
        qs = Report.objects.all()[:limit]
        return Response(ReportSerializer(qs, many=True).data)

    # ── email action ──────────────────────────────────────────────
    @action(detail=True, methods=['post'])
    def email(self, request, pk=None):
        report = self.get_object()
        email = request.data.get('email', '')
        if not email:
            # fallback to HistorySettings
            hs = HistorySettings.objects.filter(user=request.user).first()
            email = hs.notification_email if hs else ''
        if not email:
            return Response({'error': 'No email address provided'}, status=400)
        try:
            _email_report(report, email)
            return Response({'status': 'sent', 'email': email})
        except Exception as exc:
            logger.exception('Email report failed')
            return Response({'error': f'Failed to send: {exc}'}, status=500)
