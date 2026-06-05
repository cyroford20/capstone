import axios from 'axios';
import * as XLSX from 'xlsx';
import API_BASE from './apiConfig';

const API_URL = API_BASE;

// Authenticated axios instance – attaches JWT token to every request
const authAxios = axios.create();
authAxios.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses by refreshing the token and retrying
authAxios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');
        const res = await axios.post(`${API_URL}/token/refresh/`, { refresh: refreshToken });
        const { access } = res.data;
        localStorage.setItem('access_token', access);
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return authAxios(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// Get all reports (paginated)
export const getReports = async (page = 1, pageSize = 10) => {
  try {
    const response = await authAxios.get(`${API_URL}/reports/?page=${page}&page_size=${pageSize}`);
    const data = response.data;
    if (data && typeof data === 'object' && 'results' in data) return data;
    return { count: Array.isArray(data) ? data.length : 0, results: Array.isArray(data) ? data : [], next: null, previous: null };
  } catch (error) {
    console.error('Error fetching reports:', error);
    throw error;
  }
};

// Get a specific report by ID
export const getReport = async (id) => {
  try {
    const response = await authAxios.get(`${API_URL}/reports/${id}/`);
    return response.data;
  } catch (error) {
    console.error('Error fetching report:', error);
    throw error;
  }
};

// Generate daily report
export const generateDailyReport = async (date = null) => {
  try {
    const response = await authAxios.post(`${API_URL}/reports/generate_daily/`, {
      date: date || new Date().toISOString().split('T')[0]
    });
    return response.data;
  } catch (error) {
    console.error('Error generating daily report:', error);
    throw error;
  }
};

// Generate weekly report
export const generateWeeklyReport = async (startDate = null) => {
  try {
    const response = await authAxios.post(`${API_URL}/reports/generate_weekly/`, {
      start_date: startDate
    });
    return response.data;
  } catch (error) {
    console.error('Error generating weekly report:', error);
    throw error;
  }
};

// Generate monthly report
export const generateMonthlyReport = async (year = null, month = null) => {
  try {
    const currentDate = new Date();
    const response = await authAxios.post(`${API_URL}/reports/generate_monthly/`, {
      year: year || currentDate.getFullYear(),
      month: month || currentDate.getMonth() + 1
    });
    return response.data;
  } catch (error) {
    console.error('Error generating monthly report:', error);
    throw error;
  }
};

// Generate custom report
export const generateCustomReport = async (startDate, endDate, title = null) => {
  try {
    const response = await authAxios.post(`${API_URL}/reports/generate_custom/`, {
      start_date: startDate,
      end_date: endDate,
      title: title || `Custom Report ${startDate} to ${endDate}`
    });
    return response.data;
  } catch (error) {
    console.error('Error generating custom report:', error);
    throw error;
  }
};

// Regenerate report
export const regenerateReport = async (id) => {
  try {
    const response = await authAxios.post(`${API_URL}/reports/${id}/regenerate/`);
    return response.data;
  } catch (error) {
    console.error('Error regenerating report:', error);
    throw error;
  }
};

// Get recent reports
export const getRecentReports = async () => {
  try {
    const response = await authAxios.get(`${API_URL}/reports/recent/`);
    return response.data;
  } catch (error) {
    console.error('Error fetching recent reports:', error);
    throw error;
  }
};

// Delete report
export const deleteReport = async (id) => {
  try {
    await authAxios.delete(`${API_URL}/reports/${id}/`);
  } catch (error) {
    console.error('Error deleting report:', error);
    throw error;
  }
};

// Export report to Excel (real .xlsx via SheetJS)
export const exportToExcel = async (reportData, filename = 'report.xlsx') => {
  try {
    const headers = ['Date', 'Temperature', 'pH', 'DO', 'TDS', 'Status'];
    const rows = reportData.map(row => [
      row.date, row.temperature, row.ph, row.do, row.tds, row.status
    ]);

    const ws = XLSX.utils.aoa_to_sheet([headers, ...rows]);

    // Auto-size columns
    ws['!cols'] = headers.map(() => ({ wch: 16 }));

    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Report');

    // Trigger download
    XLSX.writeFile(wb, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`);
  } catch (error) {
    console.error('Error exporting to Excel:', error);
    throw error;
  }
};

// Generate PDF report
export const generatePDFReport = async (reportData, title = 'Report') => {
  try {
    // Create a styled HTML template for PDF with header
    const htmlContent = `
      <html>
        <head>
          <title>${title}</title>
          <style>
            body { font-family: Arial, sans-serif; padding: 0; margin: 0; color: #1f2937; }
            .header {
              background: linear-gradient(135deg, #0ea5e9, #0284c7);
              color: #fff;
              padding: 24px 32px;
              display: flex;
              align-items: center;
              justify-content: space-between;
            }
            .header-left { display: flex; align-items: center; gap: 16px; }
            .header-icon {
              width: 56px; height: 56px;
              background: rgba(255,255,255,0.2);
              border-radius: 12px;
              display: flex; align-items: center; justify-content: center;
              font-size: 28px;
            }
            .header-title { font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }
            .header-subtitle { font-size: 12px; opacity: 0.85; margin-top: 2px; }
            .header-right { text-align: right; font-size: 11px; opacity: 0.9; }
            .content { padding: 24px 32px; }
            .report-title { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
            .report-meta { font-size: 12px; color: #6b7280; margin-bottom: 18px; }
            table { width: 100%; border-collapse: collapse; margin-top: 8px; }
            th, td { border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; font-size: 13px; }
            th { background-color: #f0f9ff; color: #0369a1; font-weight: 600; }
            tr:nth-child(even) { background-color: #f9fafb; }
            .footer { text-align: center; font-size: 10px; color: #9ca3af; margin-top: 24px; padding-top: 12px; border-top: 1px solid #e5e7eb; }
            @media print {
              .header { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
              th { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            }
          </style>
        </head>
        <body>
          <div class="header">
            <div class="header-left">
              <div class="header-icon">&#x1F990;</div>
              <div>
                <div class="header-title">ShrimplySmart</div>
                <div class="header-subtitle">Aquaculture Monitoring System</div>
              </div>
            </div>
            <div class="header-right">
              <div>${new Date().toLocaleDateString('en-PH', { year: 'numeric', month: 'long', day: 'numeric' })}</div>
              <div>${new Date().toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' })}</div>
            </div>
          </div>
          <div class="content">
            <div class="report-title">${title}</div>
            <div class="report-meta">Report generated on ${new Date().toLocaleString('en-PH')}</div>
            <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Temperature (°C)</th>
                <th>pH Level</th>
                <th>DO (mg/L)</th>
                <th>TDS (ppm)</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${reportData.map(row => `
                <tr>
                  <td>${row.date}</td>
                  <td>${row.temperature}</td>
                  <td>${row.ph}</td>
                  <td>${row.do}</td>
                  <td>${row.tds}</td>
                  <td>${row.status}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
            <div class="footer">ShrimplySmart &copy; ${new Date().getFullYear()} &mdash; Aquaculture Monitoring System &bull; Confidential Report</div>
          </div>
        </body>
      </html>
    `;

    // Open print dialog
    const printWindow = window.open('', '', 'height=600,width=800');
    printWindow.document.write(htmlContent);
    printWindow.document.close();
    printWindow.print();
  } catch (error) {
    console.error('Error generating PDF report:', error);
    throw error;
  }
};

// Email report
export const emailReport = async (reportId, email) => {
  try {
    const response = await authAxios.post(`${API_URL}/reports/${reportId}/email/`, {
      email: email
    });
    return response.data;
  } catch (error) {
    console.error('Error emailing report:', error);
    throw error;
  }
};
