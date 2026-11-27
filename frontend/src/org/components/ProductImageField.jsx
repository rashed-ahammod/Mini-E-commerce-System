/**
 * Choosing a product picture: upload a file, or point at one hosted
 * elsewhere.
 *
 * Both exist because they fail in different ways. An uploaded file lives on
 * the server's disk, which hosts like Render wipe on every deploy — fine
 * while developing, gone after the next release. A link survives deploys
 * but depends on someone else's server staying up. The component says so
 * rather than letting the choice look arbitrary.
 *
 * An uploaded file wins over the link on the server, so the preview shows
 * the upload whenever there is one.
 */

import { useEffect, useRef, useState } from 'react';

const MAX_BYTES = 2 * 1024 * 1024;

export default function ProductImageField({
  mode,
  onModeChange,
  imageUrl,
  onImageUrlChange,
  file,
  onFileChange,
  existingImage,
  hasUpload,
  error,
}) {
  const inputRef = useRef(null);
  const [preview, setPreview] = useState(null);
  const [fileError, setFileError] = useState(null);

  // A blob URL has to be released, or the page leaks one per chosen file.
  useEffect(() => {
    if (!file) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const pick = (event) => {
    const chosen = event.target.files?.[0];
    setFileError(null);

    if (!chosen) {
      onFileChange(undefined);
      return;
    }
    if (!chosen.type.startsWith('image/')) {
      setFileError('That is not an image file.');
      return;
    }
    if (chosen.size > MAX_BYTES) {
      setFileError(
        `That file is ${(chosen.size / 1024 / 1024).toFixed(1)}MB. Please keep it under 2MB.`,
      );
      return;
    }
    onFileChange(chosen);
  };

  const shown = preview || (mode === 'url' ? imageUrl : null) || existingImage;

  return (
    <div className="field">
      <label htmlFor="image-mode">Picture</label>

      <div className="segmented segmented--full" id="image-mode" role="group">
        <button
          type="button"
          className={mode === 'upload' ? 'is-active' : ''}
          onClick={() => onModeChange('upload')}
        >
          Upload a file
        </button>
        <button
          type="button"
          className={mode === 'url' ? 'is-active' : ''}
          onClick={() => onModeChange('url')}
        >
          Link to an image
        </button>
      </div>

      <div className="image-field">
        <div className="image-field__preview">
          {shown ? (
            <img src={shown} alt="" onError={(event) => { event.target.style.display = 'none'; }} />
          ) : (
            <span className="muted">No picture</span>
          )}
        </div>

        <div className="image-field__controls">
          {mode === 'upload' ? (
            <>
              <input
                ref={inputRef}
                id="image_upload"
                type="file"
                accept="image/*"
                onChange={pick}
              />
              {file && (
                <p className="muted auth-form__hint">
                  {file.name} · {(file.size / 1024).toFixed(0)} KB
                </p>
              )}
              {hasUpload && !file && (
                <button
                  type="button"
                  className="button button--danger button--small"
                  onClick={() => {
                    onFileChange(null); // null means "remove the stored file"
                    if (inputRef.current) inputRef.current.value = '';
                  }}
                >
                  Remove uploaded picture
                </button>
              )}
              {file === null && (
                <p className="field__error">
                  The uploaded picture will be removed when you save.
                </p>
              )}
              <p className="muted auth-form__hint">
                Up to 2MB. Uploads are stored on the server's disk, which is
                wiped on every deploy — use a link if the picture needs to
                outlive the next release.
              </p>
            </>
          ) : (
            <>
              <input
                id="image_url"
                type="url"
                placeholder="https://…"
                value={imageUrl}
                onChange={(event) => onImageUrlChange(event.target.value)}
              />
              <p className="muted auth-form__hint">
                Survives deploys, but depends on that server staying up.
                {hasUpload && ' An uploaded file is shown instead of this one.'}
              </p>
            </>
          )}

          {fileError && <p className="field__error">{fileError}</p>}
          {error}
        </div>
      </div>
    </div>
  );
}
