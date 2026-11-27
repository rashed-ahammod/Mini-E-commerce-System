/**
 * Organization accounts — admins only.
 *
 * The server refuses to let an admin change their own role or deactivate
 * their own account, so that a shop cannot end up with nobody able to grant
 * access. This page does not re-implement that rule; it reads the signed-in
 * user's id and simply does not offer those buttons on their own row, with
 * a note saying why. The server remains the thing that enforces it — the UI
 * only avoids offering an action it knows will be refused.
 */

import { useCallback, useEffect, useState } from 'react';

import Modal from '../components/Modal';
import { orgApi } from '../../api/endpoints';
import { useAuth } from '../../auth/useAuth';
import { formatDate } from '../../utils/format';

const ROLE_LABEL = {
  admin: 'Organization admin',
  staff: 'Organization staff',
  customer: 'Customer (no console access)',
};

export default function OrgStaffPage() {
  const { user } = useAuth();

  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'staff',
    department: '',
  });
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState(null);

  const [changing, setChanging] = useState(null); // account whose role is changing
  const [newRole, setNewRole] = useState('staff');
  const [revoking, setRevoking] = useState(null);
  const [reason, setReason] = useState('');
  const [actionError, setActionError] = useState(null);
  const [working, setWorking] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return orgApi.staff
      .list({ page_size: 100, ordering: 'username' })
      .then((data) => {
        setAccounts(data.results);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const closeAll = () => {
    setAdding(false);
    setChanging(null);
    setRevoking(null);
    setReason('');
    setActionError(null);
    setFieldErrors({});
    setFormError(null);
  };

  const addAccount = async () => {
    setWorking(true);
    setFieldErrors({});
    setFormError(null);
    try {
      const created = await orgApi.staff.create(form);
      setNotice(
        `${created.username} added as ${ROLE_LABEL[created.role].toLowerCase()}. ` +
          'They sign in at the usual login page.',
      );
      setForm({ username: '', email: '', password: '', role: 'staff', department: '' });
      closeAll();
      load();
    } catch (err) {
      const errors = err.fieldErrors || {};
      setFieldErrors(errors);
      if (!Object.keys(errors).length) setFormError(err.message);
    } finally {
      setWorking(false);
    }
  };

  const applyRole = async () => {
    setWorking(true);
    setActionError(null);
    try {
      const updated = await orgApi.staff.update(changing.id, { role: newRole });
      setNotice(`${updated.username} is now ${ROLE_LABEL[updated.role].toLowerCase()}.`);
      closeAll();
      load();
    } catch (err) {
      const first = Object.values(err.fieldErrors || {})[0];
      setActionError(Array.isArray(first) ? first.join(' ') : err.message);
    } finally {
      setWorking(false);
    }
  };

  const revokeAccess = async () => {
    setWorking(true);
    setActionError(null);
    try {
      const updated = await orgApi.staff.deactivate(revoking.id, { reason });
      setNotice(`${updated.username}'s access has been revoked.`);
      closeAll();
      load();
    } catch (err) {
      const first = Object.values(err.fieldErrors || {})[0];
      setActionError(Array.isArray(first) ? first.join(' ') : err.message);
    } finally {
      setWorking(false);
    }
  };

  const restoreAccess = async (account) => {
    setWorking(true);
    setActionError(null);
    try {
      await orgApi.staff.activate(account.id);
      setNotice(`${account.username} can sign in again.`);
      load();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setWorking(false);
    }
  };

  const errorFor = (field) =>
    fieldErrors[field] && (
      <p className="field__error">
        {Array.isArray(fieldErrors[field])
          ? fieldErrors[field].join(' ')
          : String(fieldErrors[field])}
      </p>
    );

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Accounts</h1>
          <p className="muted">
            Who can use this console. Customers are managed under Customers.
          </p>
        </div>
        <button type="button" className="button" onClick={() => setAdding(true)}>
          Add a colleague
        </button>
      </header>

      {notice && <p className="alert alert--success">{notice}</p>}
      {error && <p className="alert alert--error">{error}</p>}
      {actionError && <p className="alert alert--error">{actionError}</p>}

      <section className="panel">
        <header className="panel__header">
          <h2>{loading ? 'Loading…' : `${accounts.length} account${accounts.length === 1 ? '' : 's'}`}</h2>
        </header>

        {loading ? (
          <p className="status" style={{ padding: 24 }}>Loading accounts…</p>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Name</th>
                <th>Role</th>
                <th>Department</th>
                <th>Last signed in</th>
                <th>Status</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => {
                const isYou = account.id === user?.id;
                return (
                  <tr key={account.id}>
                    <td>
                      <strong>{account.username}</strong>
                      {isYou && <span className="table__you"> you</span>}
                      {account.email && (
                        <div className="muted table__sub">{account.email}</div>
                      )}
                    </td>
                    <td>
                      <span
                        className={
                          account.role === 'admin' ? 'pill pill--info' : 'pill pill--off'
                        }
                      >
                        {account.role_display}
                      </span>
                    </td>
                    <td className="muted">{account.department || '—'}</td>
                    <td className="muted">
                      {account.last_login ? formatDate(account.last_login) : 'Never'}
                    </td>
                    <td>
                      <span className={account.is_active ? 'pill pill--ok' : 'pill pill--off'}>
                        {account.is_active ? 'Active' : 'Revoked'}
                      </span>
                    </td>
                    <td className="table__actions">
                      {isYou ? (
                        // The server refuses both of these on your own
                        // account; saying so is more useful than a button
                        // that always fails.
                        <span className="muted table__sub">
                          You cannot change your own access
                        </span>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="button button--ghost button--small"
                            onClick={() => {
                              setChanging(account);
                              setNewRole(account.role);
                              setActionError(null);
                            }}
                          >
                            Role
                          </button>
                          {account.is_active ? (
                            <button
                              type="button"
                              className="button button--danger button--small"
                              onClick={() => {
                                setRevoking(account);
                                setActionError(null);
                              }}
                            >
                              Revoke
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="button button--ghost button--small"
                              onClick={() => restoreAccess(account)}
                              disabled={working}
                            >
                              Restore
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* ---- add ---- */}
      {adding && (
        <Modal
          title="Add a colleague"
          onClose={closeAll}
          footer={
            <>
              <button type="button" className="button button--ghost" onClick={closeAll}>
                Cancel
              </button>
              <button
                type="button"
                className="button"
                onClick={addAccount}
                disabled={working || !form.username.trim() || !form.password}
              >
                {working ? 'Creating…' : 'Create account'}
              </button>
            </>
          }
        >
          {formError && <p className="alert alert--error">{formError}</p>}

          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              value={form.username}
              onChange={(event) =>
                setForm((f) => ({ ...f, username: event.target.value }))
              }
            />
            {errorFor('username')}
          </div>

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={form.email}
              onChange={(event) => setForm((f) => ({ ...f, email: event.target.value }))}
            />
            {errorFor('email')}
          </div>

          <div className="form-row">
            <div className="field">
              <label htmlFor="role">Role</label>
              <select
                id="role"
                value={form.role}
                onChange={(event) => setForm((f) => ({ ...f, role: event.target.value }))}
              >
                <option value="staff">Staff — runs the shop</option>
                <option value="admin">Admin — also manages accounts</option>
              </select>
            </div>

            <div className="field">
              <label htmlFor="department">Department</label>
              <input
                id="department"
                value={form.department}
                onChange={(event) =>
                  setForm((f) => ({ ...f, department: event.target.value }))
                }
              />
            </div>
          </div>

          <div className="field">
            <label htmlFor="password">Temporary password</label>
            <input
              id="password"
              type="password"
              value={form.password}
              onChange={(event) =>
                setForm((f) => ({ ...f, password: event.target.value }))
              }
            />
            {errorFor('password')}
            <p className="muted auth-form__hint">
              At least 8 characters, not entirely numeric and not a common
              password — the same rules customers get. Give it to them
              directly; it cannot be read back from here afterwards.
            </p>
          </div>
        </Modal>
      )}

      {/* ---- change role ---- */}
      {changing && (
        <Modal
          title={`${changing.username}'s role`}
          onClose={closeAll}
          footer={
            <>
              <button type="button" className="button button--ghost" onClick={closeAll}>
                Cancel
              </button>
              <button
                type="button"
                className="button"
                onClick={applyRole}
                disabled={working || newRole === changing.role}
              >
                {working ? 'Saving…' : 'Change role'}
              </button>
            </>
          }
        >
          {actionError && <p className="alert alert--error">{actionError}</p>}

          <div className="field">
            <label htmlFor="new_role">Role</label>
            <select
              id="new_role"
              value={newRole}
              onChange={(event) => setNewRole(event.target.value)}
            >
              <option value="staff">Staff — runs the shop</option>
              <option value="admin">Admin — also manages accounts</option>
              <option value="customer">Customer — no console access</option>
            </select>
          </div>

          {newRole === 'customer' && (
            <p className="alert alert--error">
              This removes their access to the console. The account stays, and
              they can still shop.
            </p>
          )}
        </Modal>
      )}

      {/* ---- revoke ---- */}
      {revoking && (
        <Modal
          title={`Revoke ${revoking.username}'s access?`}
          onClose={closeAll}
          footer={
            <>
              <button type="button" className="button button--ghost" onClick={closeAll}>
                Cancel
              </button>
              <button
                type="button"
                className="button button--danger-solid"
                onClick={revokeAccess}
                disabled={working || !reason.trim()}
              >
                {working ? 'Working…' : 'Revoke access'}
              </button>
            </>
          }
        >
          <p>
            They will be signed out immediately. Anything they have already
            done keeps their name against it in the order history, and you can
            restore the account later.
          </p>

          {actionError && <p className="alert alert--error">{actionError}</p>}

          <div className="field">
            <label htmlFor="revoke_reason">Reason (required)</label>
            <input
              id="revoke_reason"
              value={reason}
              placeholder="e.g. left the company"
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
        </Modal>
      )}
    </div>
  );
}
