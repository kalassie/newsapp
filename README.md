# The News App — HyperionDev Capstone Project

A Django + Django REST Framework news platform where independent journalists
and publication-affiliated journalists submit articles, editors review and
approve them, and readers subscribe to publishers and/or individual
journalists to receive newsletters and approved content.

---

## 1. Design

### 1.1 Functional requirements
- Journalists can write, edit and delete their own articles and newsletters.
- Editors can view, edit, delete and **approve** any article and newsletter.
- Editors can **create publishers** and assign editors and journalists to them.
- Readers can view approved articles and newsletters, and subscribe to
  publishers and/or individual journalists.
- When an editor approves an article:
  - subscribers of that journalist/publisher are emailed the article;
  - the article is logged to an internal `/api/approved/` endpoint via a
    real HTTP POST (using Python's `requests` module), simulating sharing it
    with an external system.
- A REST API exposes articles and newsletters for third-party clients,
  protected by token authentication and role-based authorisation.

### 1.2 Non-functional requirements
- PEP 8-compliant, commented, modular code with docstrings on every class,
  method and function.
- Defensive coding: model `clean()` validation, DRF serialiser validation,
  `get_object_or_404`, permission classes guarding every endpoint.
- Unique email addresses enforced at both the model and form level.
- Runs on MySQL in production; normalised relational schema (see below).
- Automated unit tests (43 tests) covering models, signals and the API.

### 1.3 Data model / normalisation
| Model | Purpose | Key relationships |
|---|---|---|
| `CustomUser` | Extends Django's `AbstractUser` with a `role` field (Reader / Editor / Journalist), a unique email field, and reader-only subscription M2M fields. | M2M to `Publisher` and to itself (journalist subscriptions). |
| `Publisher` | A curated publication. | M2M to `CustomUser` for `editors` and `journalists`. |
| `Article` | A news article. | FK to `CustomUser` (author, must be a journalist), optional FK to `Publisher`. |
| `Newsletter` | A curated bundle of articles. | FK to `CustomUser` (author), M2M to `Article`. |

The schema is in **3NF**: repeating groups are factored into M2M junction
tables, every non-key field depends only on its own table's primary key,
and there are no transitive dependencies.

### 1.4 Roles, groups & permissions
Three Django auth `Group`s are created by the `create_roles` management command:

| Role | Group permissions | What they can do |
|---|---|---|
| Reader | view only | Browse approved articles/newsletters; subscribe to publishers/journalists |
| Editor | view, change, delete | Approve articles; manage publishers; edit/delete any content |
| Journalist | add, view, change, delete | Write articles and newsletters; edit/delete their own content |

`CustomUser.save()` automatically keeps group membership in sync with the
`role` field on every save.

### 1.5 Publisher management
Editors create publishers through the **Publishers** section in the navigation
bar (or at `/publishers/new/`). From there they can assign any Editor- or
Journalist-role users to the publisher. Readers can then subscribe to a
publisher to receive approved articles from all journalists under that publisher's
banner.

### 1.6 Approval workflow (Django Signals — Option 1)
`news/signals.py` uses a `pre_save` + `post_save` pair on `Article` to detect
the exact moment `approved` flips `False → True`, then:
1. Emails every subscribed reader.
2. POSTs the article to this project's own `/api/approved/` endpoint via
   Python's `requests` module.

Both actions are wrapped in `try/except` and logged on failure.

---

## 2. Project layout

```
newsapp_project/            Django project settings and URLs
news/
  models.py                  CustomUser, Publisher, Article, Newsletter
  admin.py                    Admin site registrations
  forms.py                     Registration / article / newsletter / publisher forms
  views.py                      Session-authenticated front-end views
  urls.py                        Front-end URL routes
  signals.py                      Article-approval email + API POST
  permissions.py                   DRF role-based permission classes
  serializers.py                    DRF serialisers
  api_views.py                       DRF API views
  api_urls.py                         /api/ URL routes
  management/commands/create_roles.py  Group setup command
  templates/news/                       HTML templates (Bootstrap 5 via CDN)
  static/news/css/style.css
  tests/
    test_models.py
    test_signals.py
    test_api.py
requirements.txt
.env.example
.gitignore
```

---

## 3. Setup

> **Note:** The `venv/` folder and `.env` file are intentionally excluded from
> this repository (see `.gitignore`). Follow the steps below to create your own
> virtual environment and configure the project locally.

### 3.1 Clone the repository
```bash
git clone https://kalassie.com/<your-username>/newsapp.git
cd newsapp
```

### 3.2 Create and activate a virtual environment
```bash
# Windows (PowerShell)
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt.

### 3.3 Install dependencies
```bash
pip install -r requirements.txt
```

> **Windows note on `mysqlclient`:** if the build fails, try:
> ```bash
> pip install --only-binary :all: mysqlclient
> ```
> Alternatively, install `pymysql` and add the following two lines to the
> very top of `newsapp_project/settings.py`:
> ```python
> import pymysql
> pymysql.install_as_MySQLdb()
> ```

### 3.4 Configure the environment file
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in your editor and set at minimum:
```
DB_NAME=newsapp_db
DB_USER=newsapp_user
DB_PASSWORD=yourpassword
```

### 3.5 Create the MySQL database and user
Open MySQL Workbench or the MySQL command-line client and run:
```sql
CREATE DATABASE newsapp_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'newsapp_user'@'localhost' IDENTIFIED BY 'yourpassword';
GRANT ALL PRIVILEGES ON newsapp_db.* TO 'newsapp_user'@'localhost';
FLUSH PRIVILEGES;
```

### 3.6 Run migrations and create roles
```bash
python manage.py migrate
python manage.py create_roles
python manage.py createsuperuser
```

### 3.7 Start the development server
```bash
python manage.py runserver
```

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/` | Main site (register / login) |
| `http://127.0.0.1:8000/admin/` | Django admin |
| `http://127.0.0.1:8000/api/articles/` | REST API |
| `http://127.0.0.1:8000/api/token/` | Obtain API token |

---

## 4. Trying the full workflow

1. Register an **Editor** account → go to **Publishers → New Publisher** → create a publisher and assign journalists and editors to it.
2. Register a **Journalist** account (use a different email) → write an article, optionally selecting your publisher.
3. Back in the Editor account → go to **Pending Review** → approve the article.
4. Register a **Reader** account → browse the approved article; use the Django admin to subscribe to the publisher or journalist.

---

## 5. Running the automated tests

The test suite uses a temporary SQLite database so MySQL does not need to be
running:

```bash
# Windows PowerShell
$env:DB_ENGINE="sqlite3"
python manage.py test news -v 2

# macOS / Linux
DB_ENGINE=sqlite3 python manage.py test news -v 2
```

All **43 tests** should pass.

---

## 6. REST API reference

| Method | Endpoint | Who |
|---|---|---|
| POST | `/api/token/` | Anyone — obtain a token |
| GET | `/api/articles/` | All authenticated users |
| POST | `/api/articles/` | Journalists only |
| GET | `/api/articles/subscribed/` | Readers — subscribed content only |
| GET/PUT/PATCH/DELETE | `/api/articles/<id>/` | See permission table |
| GET/POST | `/api/newsletters/` | GET: all; POST: journalist/editor |
| GET/PUT/PATCH/DELETE | `/api/newsletters/<id>/` | Editor (any) or owning journalist |
| POST | `/api/approved/` | Internal — called by approval signal |

Authenticate with: `Authorization: Token <your-token-here>`
