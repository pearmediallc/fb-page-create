import React, { useState } from 'react';
import { inviteService } from '../services/api';

export const TestInvite: React.FC = () => {
  const [pageUrl, setPageUrl] = useState('');
  const [profileUrl, setProfileUrl] = useState('');
  const [profileName, setProfileName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    message: string;
    details?: string;
  } | null>(null);

  const extractPageId = (url: string): string => {
    // Extract page ID from URL like https://www.facebook.com/profile.php?id=61584296746538
    // or https://www.facebook.com/61584296746538
    if (url.includes('profile.php?id=')) {
      return url.split('profile.php?id=')[1]?.split('&')[0] || '';
    }
    // Extract from path
    const parts = url.replace(/\/$/, '').split('/');
    return parts[parts.length - 1] || '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!pageUrl || !profileUrl || !profileName) {
      setResult({
        success: false,
        message: 'Page URL, Profile URL, and Profile Name are required'
      });
      return;
    }

    if (!pageUrl.includes('facebook.com') || !profileUrl.includes('facebook.com')) {
      setResult({
        success: false,
        message: 'Both URLs must be valid Facebook URLs'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const pageId = extractPageId(pageUrl);
      const response = await inviteService.testInviteAccess(pageId, profileUrl, profileName);

      setResult({
        success: response.success,
        message: response.success
          ? 'Invite access process completed!'
          : `Failed: ${response.error}`,
        details: response.details
      });
    } catch (err: any) {
      setResult({
        success: false,
        message: err.response?.data?.error || 'Failed to test invite access'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="test-invite">
      <h2>Test Invite Access</h2>

      <form onSubmit={handleSubmit} className="test-invite-form">
        <div className="form-group">
          <label htmlFor="pageUrl">Page URL (the page to give access to)</label>
          <input
            type="text"
            id="pageUrl"
            value={pageUrl}
            onChange={(e) => setPageUrl(e.target.value)}
            placeholder="https://www.facebook.com/profile.php?id=61584296746538"
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="profileUrl">Profile URL (who will receive access)</label>
          <input
            type="text"
            id="profileUrl"
            value={profileUrl}
            onChange={(e) => setProfileUrl(e.target.value)}
            placeholder="https://www.facebook.com/profile.php?id=61581753605988"
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="profileName">Profile Name (exact name as shown on Facebook)</label>
          <input
            type="text"
            id="profileName"
            value={profileName}
            onChange={(e) => setProfileName(e.target.value)}
            placeholder="Marisse Dalton"
            disabled={loading}
          />
        </div>

        <button type="submit" disabled={loading} className="submit-btn">
          {loading ? 'Testing Invite Access...' : 'Test Invite Access'}
        </button>
      </form>

      {result && (
        <div className={`result ${result.success ? 'success' : 'error'}`}>
          <h3>{result.success ? 'Success!' : 'Failed'}</h3>
          <p>{result.message}</p>
          {result.details && (
            <pre className="details">{result.details}</pre>
          )}
        </div>
      )}
    </div>
  );
};
