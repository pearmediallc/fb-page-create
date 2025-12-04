import React, { useState } from 'react';
import { BenchmarkResult, BenchmarkRequest } from '../types';
import { automationService } from '../services/api';

export const Benchmark: React.FC = () => {
  const [config, setConfig] = useState<BenchmarkRequest>({
    base_name: 'BenchmarkPage',
    count: 5,
    headless: true,
    timeout: 30,
  });
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const runBenchmark = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const data = await automationService.runBenchmark(config);
      setResult(data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Benchmark failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="benchmark">
      <h2>Selenium Benchmark Test</h2>
      <p className="description">
        Test Selenium efficiency by simulating page creation workflows.
      </p>

      <div className="benchmark-config">
        <div className="form-group">
          <label>Base Name:</label>
          <input
            type="text"
            value={config.base_name}
            onChange={(e) => setConfig({ ...config, base_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Page Count:</label>
          <input
            type="number"
            value={config.count}
            onChange={(e) => setConfig({
              ...config,
              count: Math.max(1, Math.min(50, parseInt(e.target.value) || 1))
            })}
            min="1"
            max="50"
          />
        </div>
        <div className="form-group">
          <label>
            <input
              type="checkbox"
              checked={config.headless}
              onChange={(e) => setConfig({ ...config, headless: e.target.checked })}
            />
            Headless Mode
          </label>
        </div>
        <div className="form-group">
          <label>Timeout (seconds):</label>
          <input
            type="number"
            value={config.timeout}
            onChange={(e) => setConfig({
              ...config,
              timeout: Math.max(10, Math.min(120, parseInt(e.target.value) || 30))
            })}
            min="10"
            max="120"
          />
        </div>

        <button onClick={runBenchmark} disabled={loading}>
          {loading ? 'Running Benchmark...' : 'Run Benchmark'}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {result && (
        <div className="benchmark-results">
          <h3>Results</h3>
          <div className="metrics-summary">
            <div className="metric">
              <span className="label">Total Time:</span>
              <span className="value">{result.total_time.toFixed(2)}s</span>
            </div>
            <div className="metric">
              <span className="label">Pages Created:</span>
              <span className="value">{result.metrics.pages_created}</span>
            </div>
            <div className="metric">
              <span className="label">Errors:</span>
              <span className="value">{result.metrics.errors}</span>
            </div>
            <div className="metric">
              <span className="label">Avg Time/Page:</span>
              <span className="value">{result.metrics.avg_time_per_page.toFixed(2)}s</span>
            </div>
            <div className="metric">
              <span className="label">Success Rate:</span>
              <span className="value">{result.metrics.success_rate.toFixed(1)}%</span>
            </div>
          </div>

          <h4>Individual Pages</h4>
          <div className="pages-list">
            {result.pages.map((page, index) => (
              <div
                key={index}
                className={`page-result ${page.success ? 'success' : 'failed'}`}
              >
                <span className="name">{page.name}</span>
                <span className="duration">{page.duration.toFixed(2)}s</span>
                {page.error && <span className="error">{page.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
