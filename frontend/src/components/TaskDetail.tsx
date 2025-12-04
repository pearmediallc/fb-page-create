import React, { useState, useEffect } from 'react';
import { PageGenerationTask, PageInvite } from '../types';
import { inviteService } from '../services/api';
import { InvitePeople } from './InvitePeople';

interface Props {
  task: PageGenerationTask;
}

export const TaskDetail: React.FC<Props> = ({ task }) => {
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [pageInvites, setPageInvites] = useState<Record<string, PageInvite[]>>({});

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
      case 'created':
        return '#4caf50';
      case 'creating': return '#2196f3';
      case 'failed': return '#f44336';
      default: return '#ff9800';
    }
  };

  const getGenderIcon = (gender: string) => {
    switch (gender) {
      case 'female': return '\u2640';
      case 'male': return '\u2642';
      default: return '?';
    }
  };

  const getGenderColor = (gender: string) => {
    switch (gender) {
      case 'female': return '#e91e63';
      case 'male': return '#2196f3';
      default: return '#9e9e9e';
    }
  };

  // Calculate gender distribution
  const femaleCount = task.pages?.filter(p => p.gender === 'female').length || 0;
  const maleCount = task.pages?.filter(p => p.gender === 'male').length || 0;

  // Fetch invites for selected page
  const fetchInvites = async (pageId: string) => {
    try {
      const invites = await inviteService.getPageInvites(pageId);
      setPageInvites(prev => ({ ...prev, [pageId]: invites }));
    } catch (err) {
      console.error('Failed to fetch invites:', err);
    }
  };

  useEffect(() => {
    if (selectedPageId) {
      fetchInvites(selectedPageId);
    }
  }, [selectedPageId]);

  const handleInviteClick = (pageId: string) => {
    setSelectedPageId(selectedPageId === pageId ? null : pageId);
  };

  const handleInviteSent = () => {
    if (selectedPageId) {
      fetchInvites(selectedPageId);
    }
  };

  return (
    <div className="task-detail">
      <h2>Task Details: {task.base_page_name}</h2>
      <div className="task-info">
        <p><strong>ID:</strong> {task.id}</p>
        <p><strong>Status:</strong> <span className={`status-badge ${task.status}`}>{task.status}</span></p>
        <p><strong>Total Pages:</strong> {task.num_pages}</p>
        <p><strong>Pages Created:</strong> {task.pages_created}</p>
        <p><strong>Pages Failed:</strong> {task.pages_failed}</p>
        {task.profile_id && (
          <p><strong>Profile ID:</strong> {task.profile_id}</p>
        )}
        <p><strong>Created:</strong> {new Date(task.created_at).toLocaleString()}</p>
        {task.started_at && (
          <p><strong>Started:</strong> {new Date(task.started_at).toLocaleString()}</p>
        )}
        {task.completed_at && (
          <p><strong>Completed:</strong> {new Date(task.completed_at).toLocaleString()}</p>
        )}
        {task.error_message && (
          <p><strong>Error:</strong> <span style={{color: '#f44336'}}>{task.error_message}</span></p>
        )}
      </div>

      {task.pages && task.pages.length > 0 && (
        <div className="gender-summary">
          <h4>Gender Distribution</h4>
          <div className="gender-stats">
            <span className="female-stat" style={{ color: '#e91e63' }}>
              {'\u2640'} Female: {femaleCount} ({task.pages.length > 0 ? Math.round(femaleCount / task.pages.length * 100) : 0}%)
            </span>
            <span className="male-stat" style={{ color: '#2196f3' }}>
              {'\u2642'} Male: {maleCount} ({task.pages.length > 0 ? Math.round(maleCount / task.pages.length * 100) : 0}%)
            </span>
          </div>
        </div>
      )}

      <h3>Generated Pages ({task.pages?.length || 0})</h3>
      <div className="pages-list-detailed">
        {task.pages && task.pages.map((page, index) => (
          <div
            key={page._id || index}
            className={`page-card-detailed ${selectedPageId === page.page_id ? 'expanded' : ''}`}
            style={{ borderLeftColor: getStatusColor(page.status) }}
          >
            <div className="page-card-header">
              <div className="page-info">
                <div className="page-header">
                  <h4>{page.page_name}</h4>
                  <span
                    className="gender-badge"
                    style={{ backgroundColor: getGenderColor(page.gender), color: 'white' }}
                  >
                    {getGenderIcon(page.gender)} {page.gender}
                  </span>
                </div>
                <p className="status" style={{ color: getStatusColor(page.status) }}>
                  {page.status}
                </p>
                {page.page_id && (
                  <p className="page-id">ID: {page.page_id}</p>
                )}
                <p className="creation-time">
                  {new Date(page.creation_time).toLocaleString()}
                </p>
              </div>

              <div className="page-actions">
                {page.page_url && (
                  <a href={page.page_url} target="_blank" rel="noopener noreferrer" className="view-btn">
                    View Page
                  </a>
                )}
                {page.status === 'created' && (
                  <button
                    className={`invite-toggle-btn ${selectedPageId === page.page_id ? 'active' : ''}`}
                    onClick={() => handleInviteClick(page.page_id)}
                  >
                    {selectedPageId === page.page_id ? 'Hide Invite' : 'Invite People'}
                  </button>
                )}
              </div>
            </div>

            {selectedPageId === page.page_id && (
              <div className="invite-section">
                <InvitePeople
                  pageId={page.page_id}
                  pageName={page.page_name}
                  invites={pageInvites[page.page_id] || []}
                  onInviteSent={handleInviteSent}
                />
              </div>
            )}
          </div>
        ))}
        {(!task.pages || task.pages.length === 0) && (
          <p className="no-pages">No pages created yet</p>
        )}
      </div>
    </div>
  );
};
