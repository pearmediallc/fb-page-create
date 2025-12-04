import React, { useState } from 'react';
import { inviteService } from '../services/api';
import { PageInvite } from '../types';

interface Props {
  pageId: string;
  pageName: string;
  invites: PageInvite[];
  onInviteSent: () => void;
}

const ROLES = [
  { value: 'admin', label: 'Admin', description: 'Full control over the Page' },
  { value: 'editor', label: 'Editor', description: 'Can edit Page and create posts' },
  { value: 'moderator', label: 'Moderator', description: 'Can respond to comments and messages' },
  { value: 'advertiser', label: 'Advertiser', description: 'Can create ads for the Page' },
  { value: 'analyst', label: 'Analyst', description: 'Can view Page insights' },
];

export const InvitePeople: React.FC<Props> = ({ pageId, pageName, invites, onInviteSent }) => {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('editor');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const result = await inviteService.invitePerson(pageId, { email, role });
      if (result.success) {
        setSuccess(`Invite sent to ${email}!`);
        setEmail('');
        onInviteSent();
        setTimeout(() => setSuccess(''), 3000);
      } else {
        setError(result.error || 'Failed to send invite');
      }
    } catch (err) {
      setError('Failed to send invite. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'accepted': return 'status-accepted';
      case 'declined': return 'status-declined';
      case 'expired': return 'status-expired';
      default: return 'status-pending';
    }
  };

  return (
    <div className="invite-people">
      <h4>Invite People to "{pageName}"</h4>

      <form onSubmit={handleSubmit} className="invite-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="inviteEmail">Email Address:</label>
            <input
              type="email"
              id="inviteEmail"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="inviteRole">Role:</label>
            <select
              id="inviteRole"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          <button type="submit" disabled={loading} className="invite-btn">
            {loading ? 'Sending...' : 'Send Invite'}
          </button>
        </div>

        <p className="role-description">
          {ROLES.find(r => r.value === role)?.description}
        </p>
      </form>

      {error && <div className="invite-error">{error}</div>}
      {success && <div className="invite-success">{success}</div>}

      {invites.length > 0 && (
        <div className="invites-list">
          <h5>Sent Invites ({invites.length})</h5>
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Sent</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((invite) => (
                <tr key={invite._id}>
                  <td>{invite.invitee_email}</td>
                  <td className="role-cell">{invite.role}</td>
                  <td>
                    <span className={`status-badge ${getStatusBadgeClass(invite.status)}`}>
                      {invite.status}
                    </span>
                  </td>
                  <td>{new Date(invite.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
