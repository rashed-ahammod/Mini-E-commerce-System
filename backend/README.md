# Backend — Mini E-commerce REST API

Django 5 + Django REST Framework API for categories, products, token
authentication and orders.

## Layout

```
backend/
├── config/           # project settings, root URLs, shared pagination
├── accounts/         # registration, token login/logout, current user
├── catalog/          # Category and Product models + APIs
├── orders/           # Order model + APIs (authenticated users only)
├── manage.py
├── requirements.txt
└── .env.example      # copy to .env and edit
```

## Running locally

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env          # cp on macOS/Linux
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The API is then served at <http://127.0.0.1:8000/api/> and the admin site at
<http://127.0.0.1:8000/admin/>.

## Configuration

All environment variables are documented in [.env.example](.env.example).
Nothing secret is hard-coded in `config/settings.py`; the defaults there are
development-only.
