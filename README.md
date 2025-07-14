![Alt text](https://raw.githubusercontent.com/diegoMasin/landing-maximumtech/master/assets/img/new-logo-mt-01.png)

# Orfin Django API ![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)

###### Personal and family financial management system

## Requirements

- Python 3.11.0

## Install project manually

```
- clone this repository
- cd <repository-folder>
- python -m venv .venv
- source .venv/bin/activate
- pip install -r requirements.txt
- python contrib/env_gen.py
  - edit .env
- python manage.py migrate
- python manage.py createsuperuser --username="admin" --email=""
```

## For debugging

Use this as a breakpoint into the code and run server or test

```
import pdb
pdb.set_trace()
```

## Some utils internal commands/tasks

- python manage.py restart_db (Drop all the database tables and create them)
- python manage.py test (Run all unit tests)
- coverage run manage.py test (Run all unit tests with coverage)
- coverage report -m (Show coverage report)
- python contrib/update_coverage.py (Update readme with coverage)
- python manage.py seed api --number=15 (Run seed; --number defines how much things will be created per model)
