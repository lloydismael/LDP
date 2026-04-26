# Leadership Development Program (LDP)

A web application that focuses on the records of Schools, Scholars, Awardees, Principals, Activities/Events, and Professionals.

## Technical Stack
- Python 3.11
- Django 4.2+
- Docker & Docker Compose
- Azure Web App Service compatible layout

## Core Functionalities
- **Role-based Access Control**: Admin, Encoder, Viewer, Principal, etc.
- **Partner Schools Management**: Tracking school year activations, categories, locations (default: Philippines), region/province filtering.
- **Records Management**: Students, Scholars, Leadership Awardees, College Members, Professionals.
- **Activities & Events**: Tracking trainings/seminars with approval workflows.
- **Reporting & Exports**: Data export to Excel (via `openpyxl`), structured reports based on access hierarchy.
- **Communications**: Base points planned for Email/SMS blast functionality.

## Local Development (Docker)
1. Build and run containers:
   ```bash
   docker-compose up --build
   ```
2. In a separate terminal, apply migrations inside the running container:
   ```bash
   docker-compose exec web python manage.py makemigrations
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   ```
3. Access the admin dashboard at `http://localhost:8000/admin/`.

## Azure Web App Deployment
- Ensure environment variables are configured in the Azure App Service (e.g. `DATABASE_URL`, `DJANGO_ALLOWED_HOSTS`, `SECRET_KEY`).
- Media files should utilize `azure-storage-blob` (configured via `django-storages` if fully deployed to scale). Container defaults to using `gunicorn` as standard WSGI layer.
