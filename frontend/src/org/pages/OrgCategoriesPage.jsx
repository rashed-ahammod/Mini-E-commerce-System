/**
 * Category management.
 *
 * Small enough that everything happens on one screen: the list doubles as
 * the editor. Deleting a category cascades to its products, so the dialog
 * says how many would go with it — and the server still refuses if any of
 * them belongs to an order.
 */

import { useCallback, useEffect, useState } from 'react';

import CatalogTabs from '../components/CatalogTabs';
import Modal from '../components/Modal';
import { catalogAdminApi, categoryApi } from '../../api/endpoints';

export default function OrgCategoriesPage() {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const [editing, setEditing] = useState(null); // category | 'new'
  const [form, setForm] = useState({ name: '', description: '' });
  const [formError, setFormError] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const [working, setWorking] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    return categoryApi
      .list({ page_size: 100, ordering: 'name' })
      .then((data) => {
        setCategories(data.results);
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

  const openEditor = (category) => {
    setEditing(category);
    setFormError(null);
    setForm(
      category === 'new'
        ? { name: '', description: '' }
        : { name: category.name, description: category.description || '' },
    );
  };

  const save = async () => {
    setWorking(true);
    setFormError(null);
    try {
      if (editing === 'new') {
        await catalogAdminApi.createCategory(form);
        setNotice(`“${form.name}” created.`);
      } else {
        await catalogAdminApi.updateCategory(editing.id, form);
        setNotice(`“${form.name}” updated.`);
      }
      setEditing(null);
      load();
    } catch (err) {
      const first = Object.values(err.fieldErrors || {})[0];
      setFormError(Array.isArray(first) ? first.join(' ') : err.message);
    } finally {
      setWorking(false);
    }
  };

  const confirmDelete = async () => {
    setWorking(true);
    setDeleteError(null);
    try {
      await catalogAdminApi.deleteCategory(deleting.id);
      setNotice(`“${deleting.name}” deleted.`);
      setDeleting(null);
      load();
    } catch (err) {
      setDeleteError(
        err.status === 409
          ? `${err.message} Move those products to another category first.`
          : err.message,
      );
    } finally {
      setWorking(false);
    }
  };

  return (
    <div className="org-page">
      <header className="org-page__header">
        <div>
          <h1>Catalog</h1>
          <p className="muted">{categories.length} categories.</p>
        </div>
        <button type="button" className="button" onClick={() => openEditor('new')}>
          Add a category
        </button>
      </header>

      <CatalogTabs />

      {notice && <p className="alert alert--success">{notice}</p>}
      {error && <p className="alert alert--error">{error}</p>}

      <section className="panel">
        {loading ? (
          <p className="status" style={{ padding: 24 }}>Loading categories…</p>
        ) : categories.length === 0 ? (
          <div className="empty-state">
            <h3>No categories yet</h3>
            <p className="muted">A product needs one before it can be added.</p>
          </div>
        ) : (
          <table className="table table--rows">
            <thead>
              <tr>
                <th>Name</th>
                <th>Description</th>
                <th>Products</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {categories.map((category) => (
                <tr key={category.id}>
                  <td><strong>{category.name}</strong></td>
                  <td className="muted">{category.description || '—'}</td>
                  <td className="nums">{category.product_count}</td>
                  <td className="table__actions">
                    <button
                      type="button"
                      className="button button--ghost button--small"
                      onClick={() => openEditor(category)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="button button--danger button--small"
                      onClick={() => {
                        setDeleting(category);
                        setDeleteError(null);
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {editing && (
        <Modal
          title={editing === 'new' ? 'Add a category' : `Edit ${editing.name}`}
          onClose={() => setEditing(null)}
          footer={
            <>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setEditing(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button"
                onClick={save}
                disabled={working || !form.name.trim()}
              >
                {working ? 'Saving…' : 'Save'}
              </button>
            </>
          }
        >
          {formError && <p className="alert alert--error">{formError}</p>}

          <div className="field">
            <label htmlFor="name">Name</label>
            <input
              id="name"
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
            />
            <p className="muted auth-form__hint">
              Category names are unique.
            </p>
          </div>

          <div className="field">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              rows="3"
              value={form.description}
              onChange={(event) =>
                setForm((current) => ({ ...current, description: event.target.value }))
              }
            />
          </div>
        </Modal>
      )}

      {deleting && (
        <Modal
          title={`Delete ${deleting.name}?`}
          onClose={() => setDeleting(null)}
          footer={
            <>
              <button
                type="button"
                className="button button--ghost"
                onClick={() => setDeleting(null)}
              >
                Keep it
              </button>
              <button
                type="button"
                className="button button--danger-solid"
                onClick={confirmDelete}
                disabled={working}
              >
                {working ? 'Deleting…' : 'Delete'}
              </button>
            </>
          }
        >
          {deleteError ? (
            <p className="alert alert--error">{deleteError}</p>
          ) : deleting.product_count > 0 ? (
            <p className="alert alert--error">
              This also deletes the {deleting.product_count} product
              {deleting.product_count === 1 ? '' : 's'} in it. If any of them
              has been ordered, the server will refuse.
            </p>
          ) : (
            <p>This category is empty, so nothing else goes with it.</p>
          )}
        </Modal>
      )}
    </div>
  );
}
