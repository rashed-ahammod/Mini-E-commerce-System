/**
 * Create or edit a product.
 *
 * One form for both, because the fields are identical and two near-copies
 * would drift. `product` being null means "create".
 *
 * Stock is only editable when creating. On an existing product it is shown
 * read-only with a pointer to the adjust-stock action, because writing the
 * number straight back is how a shop oversells: the figure on screen is
 * already stale if an order arrived while the form was open. The adjust
 * action applies a delta under a row lock instead.
 */

import { useState } from 'react';

import Modal from './Modal';

const EMPTY = {
  name: '',
  description: '',
  price: '',
  stock: '0',
  category_id: '',
  image_url: '',
};

export default function ProductFormModal({ product, categories, onClose, onSave }) {
  const isNew = !product;

  const [form, setForm] = useState(() =>
    isNew
      ? EMPTY
      : {
          name: product.name,
          description: product.description || '',
          price: String(product.price),
          stock: String(product.stock),
          category_id: String(product.category?.id ?? ''),
          image_url: product.image_url || '',
        },
  );
  const [fieldErrors, setFieldErrors] = useState({});
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  const change = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const submit = async () => {
    setSaving(true);
    setError(null);
    setFieldErrors({});

    // Only what the API accepts; `stock` is left out of an update on purpose.
    const payload = {
      name: form.name,
      description: form.description,
      price: form.price,
      category_id: form.category_id ? Number(form.category_id) : null,
      image_url: form.image_url,
    };
    if (isNew) payload.stock = Number(form.stock || 0);

    try {
      await onSave(payload);
    } catch (err) {
      const errors = err.fieldErrors || {};
      setFieldErrors(errors);
      if (!Object.keys(errors).length) setError(err.message);
      setSaving(false);
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
    <Modal
      title={isNew ? 'Add a product' : `Edit ${product.name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="button button--ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="button" onClick={submit} disabled={saving}>
            {saving ? 'Saving…' : isNew ? 'Add product' : 'Save changes'}
          </button>
        </>
      }
    >
      {error && <p className="alert alert--error">{error}</p>}

      <div className="field">
        <label htmlFor="name">Name</label>
        <input id="name" name="name" value={form.name} onChange={change} />
        {errorFor('name')}
      </div>

      <div className="field">
        <label htmlFor="category_id">Category</label>
        <select
          id="category_id"
          name="category_id"
          value={form.category_id}
          onChange={change}
        >
          <option value="">Choose a category…</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        {errorFor('category_id')}
      </div>

      <div className="form-row">
        <div className="field">
          <label htmlFor="price">Price</label>
          <input
            id="price"
            name="price"
            type="number"
            min="0"
            step="0.01"
            value={form.price}
            onChange={change}
          />
          {errorFor('price')}
        </div>

        <div className="field">
          <label htmlFor="stock">Stock</label>
          <input
            id="stock"
            name="stock"
            type="number"
            min="0"
            value={form.stock}
            onChange={change}
            disabled={!isNew}
          />
          {isNew ? (
            errorFor('stock')
          ) : (
            <p className="muted auth-form__hint">
              Use “Adjust” on the product row — it applies a change rather
              than overwriting whatever the stock is now.
            </p>
          )}
        </div>
      </div>

      <div className="field">
        <label htmlFor="description">Description</label>
        <textarea
          id="description"
          name="description"
          rows="3"
          value={form.description}
          onChange={change}
        />
        {errorFor('description')}
      </div>

      <div className="field">
        <label htmlFor="image_url">Image URL</label>
        <input
          id="image_url"
          name="image_url"
          type="url"
          placeholder="https://…"
          value={form.image_url}
          onChange={change}
        />
        {errorFor('image_url')}
        <p className="muted auth-form__hint">
          A link, not an upload: the server's filesystem is wiped on every
          deploy, so uploaded files would not survive.
        </p>
      </div>
    </Modal>
  );
}
