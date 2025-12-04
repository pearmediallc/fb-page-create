import React, { useEffect, useState } from 'react';
import { GeneratedPage } from '../types';
import { taskService } from '../services/api';

export const CreatedPagesList: React.FC = () => {
  const [pages, setPages] = useState<GeneratedPage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchPages = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await taskService.getAllPages();
      setPages(data);
    } catch (err) {
      setError('Failed to fetch pages');
    } finally {
      setLoading(false);
    }
  };

  // Only fetch pages once on initial load - use Refresh button for updates
  useEffect(() => {
    fetchPages();
  }, []);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString();
  };

  if (loading && pages.length === 0) return <div className="loading">Loading pages...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="created-pages-list">
      <div className="list-header">
        <h2>Created Pages List</h2>
        <button onClick={fetchPages} className="refresh-btn">Refresh</button>
      </div>

      <div className="pages-count">
        <span>Total Pages: <strong>{pages.length}</strong></span>
      </div>

      {pages.length === 0 ? (
        <div className="no-pages">
          <p>No pages created yet. Create a task and start it to generate pages.</p>
        </div>
      ) : (
        <div className="pages-table-container">
          <table className="pages-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Page Name</th>
                <th>Gender</th>
                <th>Page URL</th>
                <th>Created At</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {pages.map((page, index) => (
                <tr key={page._id || index}>
                  <td>{index + 1}</td>
                  <td className="page-name">{page.page_name}</td>
                  <td>
                    <span className={`gender-badge ${page.gender}`}>
                      {page.gender}
                    </span>
                  </td>
                  <td>
                    {page.page_url ? (
                      <a href={page.page_url} target="_blank" rel="noopener noreferrer">
                        View Page
                      </a>
                    ) : (
                      <span className="no-url">-</span>
                    )}
                  </td>
                  <td className="date">{formatDate(page.creation_time)}</td>
                  <td>
                    <span className={`status-badge status-${page.status}`}>
                      {page.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
