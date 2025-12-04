import React, { useEffect, useState } from 'react';
import { EfficiencyReport as Report } from '../types';
import { taskService } from '../services/api';

export const EfficiencyReport: React.FC = () => {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchReport = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await taskService.getEfficiencyReport();
      setReport(data);
    } catch (err) {
      setError('Failed to fetch efficiency report');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReport();
  }, []);

  if (loading) return <div className="loading">Loading report...</div>;
  if (error) return <div className="error">{error}</div>;
  if (!report) return null;

  return (
    <div className="efficiency-report">
      <h2>Selenium Efficiency Report</h2>
      <button onClick={fetchReport} className="refresh-btn">Refresh</button>

      <div className="metrics-grid">
        <div className="metric-card">
          <h3>Total Tasks</h3>
          <p className="value">{report.total_tasks}</p>
        </div>
        <div className="metric-card">
          <h3>Total Pages</h3>
          <p className="value">{report.total_pages}</p>
        </div>
        <div className="metric-card success">
          <h3>Pages Created</h3>
          <p className="value">{report.pages_created}</p>
        </div>
        <div className="metric-card error">
          <h3>Pages Failed</h3>
          <p className="value">{report.pages_failed}</p>
        </div>
        <div className="metric-card highlight">
          <h3>Success Rate</h3>
          <p className="value">{report.success_rate.toFixed(1)}%</p>
        </div>
        <div className="metric-card">
          <h3>Avg Pages/Task</h3>
          <p className="value">{report.avg_pages_per_task.toFixed(1)}</p>
        </div>
      </div>
    </div>
  );
};
