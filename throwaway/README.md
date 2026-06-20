# Widget Service (throwaway stress-test fixture)

> ⚠️ This directory is an **intentionally flawed** fixture used to stress-test the
> AI Council review on a pull request. It is NOT real code and should never be
> deployed or merged. It exists to generate a large volume of findings and to
> exercise cross-file browsing (the files reference each other).

## Layout
- `scripts/widget_service.py` — service entrypoint (imports `scripts/db.py`)
- `docker/` — `docker-compose.yml` + `Dockerfile`
- `ansible/roles/widget/` — deploy role (`tasks/main.yml`, `defaults/main.yml`)
- `.github/workflows/deploy.yml` — deploy pipeline

## Usage

```
docker compose -f docker/docker-compose.yml up
```
