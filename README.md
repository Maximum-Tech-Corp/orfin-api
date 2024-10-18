![Alt text](https://raw.githubusercontent.com/diegoMasin/landing-maximumtech/master/assets/img/new-logo-mt-01.png)
<br><br>

# Orfin Django Backend

###### Personal and family financial management system

## Requirements

- Python 3.11.0

## Install project anually

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

## For Debbuging

Use this as a breakpoint into the code and run it

```
import pdb
pdb.set_trace()
```
