import React, { useState } from 'react';
import { CreateTaskRequest } from '../types';

interface Props {
  onSubmit: (data: CreateTaskRequest) => Promise<void>;
  loading: boolean;
}

export const TaskForm: React.FC<Props> = ({ onSubmit, loading }) => {
  const [pageName, setPageName] = useState('Secure Auto Insurance');
  const [numPages, setNumPages] = useState(10);
  const [publicProfileUrl, setPublicProfileUrl] = useState('');
  const [profileName, setProfileName] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit({
      base_name: pageName,
      count: numPages,
      public_profile_url: publicProfileUrl,
      profile_name: profileName,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="task-form">
      <h2>Create Facebook Pages</h2>

      <div className="form-section">
        <h3 className="section-title">Page Settings</h3>

        <div className="form-group">
          <label htmlFor="numPages">Number of Pages</label>
          <input
            type="number"
            id="numPages"
            value={numPages}
            onChange={(e) => setNumPages(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))}
            min="1"
            max="100"
            required
          />
          <small className="hint">Min: 1, Max: 100 pages per task</small>
        </div>

        <div className="form-group">
          <label htmlFor="pageName">Page Name (Base Name)</label>
          <input
            type="text"
            id="pageName"
            value={pageName}
            onChange={(e) => setPageName(e.target.value)}
            placeholder="e.g., Secure Auto Insurance"
            required
          />
          <small className="hint">
            Names will be generated as "{pageName} - [Name]"
          </small>
        </div>
      </div>

      <div className="form-section">
        <h3 className="section-title">Invite Access Settings</h3>

        <div className="form-group">
          <label htmlFor="publicProfileUrl">Profile URL <span className="required">*</span></label>
          <input
            type="text"
            id="publicProfileUrl"
            value={publicProfileUrl}
            onChange={(e) => setPublicProfileUrl(e.target.value)}
            placeholder="https://www.facebook.com/profile.php?id=123456789"
            required
          />
          <small className="hint">Facebook profile URL to share created pages to</small>
        </div>

        <div className="form-group">
          <label htmlFor="profileName">Profile Name (Username) <span className="required">*</span></label>
          <input
            type="text"
            id="profileName"
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            placeholder="e.g., Marisse Dalton"
            required
          />
          <small className="hint">Exact name as shown on Facebook profile</small>
        </div>
      </div>

      <div className="form-summary">
        <div className="summary-item">
          <span className="summary-label">Pages to Create</span>
          <span className="summary-value">{numPages}</span>
        </div>
      </div>

      <button type="submit" disabled={loading || !profileName || !publicProfileUrl} className="submit-btn">
        {loading ? 'Starting Automation...' : 'Start Page Generation'}
      </button>
    </form>
  );
};
