"""The organization-facing API.

Everything the people who *run* the shop use, mounted under /api/org/ and
closed to customers.

This app deliberately owns no models. The domain lives where it belongs —
orders in `orders`, the catalog in `catalog`, roles in `accounts` — and this
app is the staff-facing surface over them. Keeping it separate means the
customer API cannot accidentally gain an organization capability by someone
editing a shared viewset.
"""
